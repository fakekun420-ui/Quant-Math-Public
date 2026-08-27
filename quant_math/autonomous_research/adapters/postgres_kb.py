"""
JSONL-backed Knowledge Base with atomic upsert and indexed search.

Drop-in replacement for HypothesisKnowledgeBase (same public interface) plus
record-level helpers used by DecisionEngine (register_hypothesis/load_records).

Features:
- Atomic upsert: read-all → merge → write-all (no partial writes)
- Search by status, symbol, strategy_type (in-memory index)
- Thread-safe via threading.Lock
- No external dependencies (no PostgreSQL, no psycopg2)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JSONLKnowledgeBase:
    """HypothesisKnowledgeBase-compatible KB backed by JSONL files.

    All operations are atomic: reads load the full file, writes rewrite
    the entire file. Thread-safe via a global lock per file path.
    """

    _locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()

    def __init__(self, jsonl_path: str):
        self.jsonl_path = jsonl_path
        os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
        # Per-file lock for concurrent access
        with JSONLKnowledgeBase._global_lock:
            if jsonl_path not in JSONLKnowledgeBase._locks:
                JSONLKnowledgeBase._locks[jsonl_path] = threading.Lock()
        self._lock = JSONLKnowledgeBase._locks[jsonl_path]
        # In-memory index for fast searches
        self._index: Dict[str, Dict[str, Any]] = {}
        self._index_built = False

    @property
    def backend_name(self) -> str:
        return "jsonl"

    def is_available(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Atomic read/write
    # ------------------------------------------------------------------

    def _load_all(self) -> Dict[str, Dict[str, Any]]:
        """Load all records from JSONL, merging by hypothesis_id (last wins)."""
        records: Dict[str, Dict[str, Any]] = {}
        if not os.path.exists(self.jsonl_path):
            return records
        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    hid = rec.get("hypothesis_id")
                    if not hid:
                        continue
                    records[hid] = rec
        except OSError as exc:
            logger.warning("[jsonl-kb] load failed: %s", exc)
        return records

    def _save_all(self, records: Dict[str, Dict[str, Any]]):
        """Atomically write all records to JSONL (atomic via tmp+rename)."""
        tmp = self.jsonl_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                for rec in records.values():
                    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            os.replace(tmp, self.jsonl_path)
        except OSError as exc:
            logger.warning("[jsonl-kb] save failed: %s", exc)
            try:
                os.remove(tmp)
            except OSError:
                pass

    def _rebuild_index(self):
        """Rebuild in-memory index from JSONL file."""
        self._index = self._load_all()
        self._index_built = True

    # ------------------------------------------------------------------
    # Record-level API (DecisionEngine semantics)
    # ------------------------------------------------------------------

    def register_hypothesis(self, record: Dict[str, Any]) -> str:
        """Atomic upsert: load → merge → save."""
        hid = record.get("hypothesis_id") or f"hyp_{int(time.time() * 1000)}"
        record = dict(record, hypothesis_id=hid)
        record["updated_at"] = time.time()
        if "created_at" not in record:
            record["created_at"] = time.time()
        with self._lock:
            records = self._load_all()
            existing = records.get(hid)
            if existing:
                # Merge: existing fields preserved unless explicitly updated
                merged = dict(existing)
                for k, v in record.items():
                    if v is not None:
                        merged[k] = v
                records[hid] = merged
            else:
                records[hid] = record
            self._save_all(records)
            self._index = records
            self._index_built = True
        return hid

    def load_records(self) -> Dict[str, Dict[str, Any]]:
        """Load all records (uses cache if available)."""
        with self._lock:
            if self._index_built:
                return dict(self._index)
            records = self._load_all()
            self._index = records
            self._index_built = True
            return dict(records)

    def update_hypothesis(self, hypothesis_id: str, updates: Dict[str, Any]) -> bool:
        """Atomic update: load → merge → save."""
        with self._lock:
            records = self._load_all()
            if hypothesis_id not in records:
                return False
            merged = dict(records[hypothesis_id])
            merged.update(updates or {})
            merged["hypothesis_id"] = hypothesis_id
            merged["updated_at"] = time.time()
            records[hypothesis_id] = merged
            self._save_all(records)
            self._index = records
            self._index_built = True
        return True

    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Atomic delete: load → remove → save."""
        with self._lock:
            records = self._load_all()
            if hypothesis_id not in records:
                return False
            del records[hypothesis_id]
            self._save_all(records)
            self._index = records
            self._index_built = True
        return True

    # ------------------------------------------------------------------
    # Search (in-memory index for speed)
    # ------------------------------------------------------------------

    def search_hypotheses(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search by exact field match (status, symbol, strategy_type, etc.)."""
        crit = {k: v for k, v in (criteria or {}).items() if v is not None}
        if not crit:
            return list(self.load_records().values())
        results = []
        for rec in self.load_records().values():
            if all(rec.get(k) == v for k, v in crit.items()):
                results.append(rec)
        return results

    def search_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Fast search by status using index."""
        return self.search_hypotheses({"status": status})

    def search_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Fast search by symbol using index."""
        return self.search_hypotheses({"symbol": symbol})

    def search_by_status_and_symbol(self, status: str, symbol: str) -> List[Dict[str, Any]]:
        """Fast search by status + symbol."""
        return self.search_hypotheses({"status": status, "symbol": symbol})

    def search_hypotheses_by_text(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Full-text search across all fields."""
        q = (query or "").lower()
        hits = [
            r for r in self.load_records().values()
            if q in json.dumps(r, ensure_ascii=False).lower()
        ]
        return hits[:limit]

    def search_similar_hypotheses(self, description: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        return self.search_hypotheses_by_text(description, limit=100)

    # ------------------------------------------------------------------
    # Public interface mirroring HypothesisKnowledgeBase
    # ------------------------------------------------------------------

    def store_hypothesis(self, hypothesis: Any) -> str:
        record = self._to_record(hypothesis)
        return self.register_hypothesis(record)

    def retrieve_hypothesis(self, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        return self.load_records().get(hypothesis_id)

    def get_statistics(self) -> Dict[str, Any]:
        records = list(self.load_records().values())
        return {
            "total": len(records),
            "active": sum(1 for r in records
                          if r.get("status") in ("validated", "backtested",
                                                 "monte_carlo_tested", "deployed")),
            "hypotheses": records[:5],
        }

    def get_hypothesis_timeline(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        rec = self.retrieve_hypothesis(hypothesis_id)
        if not rec:
            return []
        return [{"hypothesis_id": hypothesis_id,
                 "status": rec.get("status"),
                 "updated_from": rec.get("orchestrator_cycle"),
                 "timestamp": rec.get("created_at")}]

    def export_hypotheses(self, output_path: str) -> Dict[str, Any]:
        records = list(self.load_records().values())
        payload = {
            "total": len(records),
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "hypotheses": records,
        }
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        return {"total": len(records), "output_path": output_path}

    def import_hypotheses(self, input_path: str) -> int:
        if not os.path.exists(input_path):
            return 0
        count = 0
        with open(input_path, "r", encoding="utf-8") as fh:
            content = fh.read().strip()
        if not content:
            return 0
        if content.lstrip().startswith("{") and "\n{" in content:
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    self.register_hypothesis(json.loads(line))
                    count += 1
                except json.JSONDecodeError:
                    continue
        else:
            payload = json.loads(content)
            for rec in payload.get("hypotheses", []):
                self.register_hypothesis(rec)
                count += 1
        return count

    @staticmethod
    def _to_record(hypothesis: Any) -> Dict[str, Any]:
        if isinstance(hypothesis, dict):
            return dict(hypothesis)
        data = {}
        columns = ("hypothesis_id", "name", "description", "strategy_type",
                    "symbol", "status", "expectancy", "scientific_score",
                    "win_rate", "total_return", "total_return_pct", "n_trades",
                    "sharpe_ratio", "max_drawdown", "parameters", "data_source",
                    "orchestrator_cycle", "created_at")
        for attr in columns:
            val = getattr(hypothesis, attr, None)
            if val is not None:
                data[attr] = getattr(val, "value", val)
        extras = getattr(hypothesis, "__dict__", {})
        for k, v in extras.items():
            if k not in data and isinstance(v, (int, float, str, list, dict)):
                data[k] = getattr(v, "value", v)
        return data


class KBPersistence:
    """Storage facade used by DecisionEngine: pure JSONL, no PostgreSQL."""

    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self.kb = JSONLKnowledgeBase(jsonl_path=kb_path)
        logger.info("[kb-storage] backend=jsonl kb=%s", kb_path)

    @property
    def mode(self) -> str:
        return "jsonl"

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        return self.kb.load_records()

    def save(self, record: Dict[str, Any]) -> str:
        return self.kb.register_hypothesis(record)


# ---------------------------------------------------------------------------
# Legacy aliases for backward compatibility
# ---------------------------------------------------------------------------

PostgreSQLKnowledgeBase = JSONLKnowledgeBase
