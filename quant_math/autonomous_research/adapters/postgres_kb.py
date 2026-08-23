"""
PostgreSQL-backed Knowledge Base with automatic JSONL fallback.

Drop-in replacement for HypothesisKnowledgeBase (same public interface) plus
record-level helpers used by DecisionEngine (register_hypothesis/load_records).

Hard guarantees:
- psycopg2 import is optional: missing driver == JSONL mode, never a crash.
- Every operation wraps PostgreSQL access in try/except; any failure flips
  the instance to JSONL fallback mode with an explicit log line.
- No synthetic/demo records are ever injected on empty results.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_DSN = (
    "host=127.0.0.1 port=15432 dbname=quantmath_kb "
    "user=quantmath password=quantmath connect_timeout=2"
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS {{table}} (
    hypothesis_id     TEXT PRIMARY KEY,
    name              TEXT,
    description       TEXT,
    strategy_type     TEXT,
    symbol            TEXT,
    status            TEXT,
    expectancy        DOUBLE PRECISION,
    scientific_score  DOUBLE PRECISION,
    win_rate          DOUBLE PRECISION,
    total_return      DOUBLE PRECISION,
    total_return_pct  DOUBLE PRECISION,
    n_trades          INTEGER,
    sharpe_ratio      DOUBLE PRECISION,
    max_drawdown      DOUBLE PRECISION,
    parameters        JSONB,
    data_source       TEXT,
    orchestrator_cycle INTEGER,
    created_at        DOUBLE PRECISION,
    updated_at        DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM now()),
    raw               JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_{{table}}_status ON {{table}}(status);
CREATE INDEX IF NOT EXISTS idx_{{table}}_symbol ON {{table}}(symbol);
CREATE INDEX IF NOT EXISTS idx_{{table}}_type_symbol ON {{table}}(strategy_type, symbol);
"""

COLUMNS = (
    "hypothesis_id", "name", "description", "strategy_type", "symbol",
    "status", "expectancy", "scientific_score", "win_rate",
    "total_return", "total_return_pct", "n_trades", "sharpe_ratio",
    "max_drawdown", "parameters", "data_source", "orchestrator_cycle",
    "created_at",
)


def resolve_dsn() -> str:
    return os.environ.get("QUANTMATH_PG_DSN", DEFAULT_DSN)


def _psycopg2():
    """Import psycopg2 lazily; returns module or None (never raises)."""
    try:
        import psycopg2
        import psycopg2.extras
        return psycopg2
    except Exception:
        return None


class PostgreSQLKnowledgeBase:
    """HypothesisKnowledgeBase-compatible KB backed by PostgreSQL.

    If PostgreSQL is unreachable at any point, every method transparently
    executes against a JSONL mirror file instead and logs the fallback.
    """

    _fail_until: Dict[str, float] = {}
    FAIL_TTL_SECONDS = 30.0

    def __init__(self, storage_path: str = "runtime/state",
                 dsn: Optional[str] = None, jsonl_fallback: Optional[str] = None):
        self.storage_path = storage_path
        self.dsn = dsn or resolve_dsn()
        if jsonl_fallback:
            self.jsonl_path = jsonl_fallback
        elif storage_path.endswith(".jsonl"):
            self.jsonl_path = storage_path
        else:
            self.jsonl_path = os.path.join(storage_path, "hypotheses.jsonl")

        import hashlib
        self.table = "hyp_" + hashlib.md5(
            os.path.abspath(self.jsonl_path).encode()).hexdigest()[:10]

        self._pg2 = _psycopg2()
        self._conn = None
        self._pg_ok = False
        self._lock = threading.Lock()
        if self._pg2 is None:
            logger.warning(
                "[kb-storage] psycopg2 no disponible — usando JSONL (%s)",
                self.jsonl_path)
        else:
            self._connect()

    # ------------------------------------------------------------------
    # Connection plumbing
    # ------------------------------------------------------------------

    def _connect(self) -> bool:
        now = time.time()
        until = PostgreSQLKnowledgeBase._fail_until.get(self.dsn, 0.0)
        if now < until and self._conn is None:
            self._pg_ok = False
            return False
        try:
            if self._conn is not None:
                try:
                    with self._conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    self._pg_ok = True
                    PostgreSQLKnowledgeBase._fail_until.pop(self.dsn, None)
                    return True
                except Exception:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                    self._conn = None
            self._conn = self._pg2.connect(self.dsn)
            self._conn.autocommit = True
            self._ensure_schema()
            self._maybe_seed_from_jsonl()
            self._pg_ok = True
            PostgreSQLKnowledgeBase._fail_until.pop(self.dsn, None)
            return True
        except Exception as exc:
            self._pg_ok = False
            PostgreSQLKnowledgeBase._fail_until[self.dsn] = \
                time.time() + PostgreSQLKnowledgeBase.FAIL_TTL_SECONDS
            logger.warning(
                "[kb-storage] PostgreSQL no disponible (%s) — fallback a JSONL: %s",
                exc.__class__.__name__, self.jsonl_path)
            return False

    def _ensure_schema(self):
        with self._conn.cursor() as cur:
            cur.execute(SCHEMA_SQL.replace("{{table}}", self.table))

    def _maybe_seed_from_jsonl(self):
        """Bootstrap: if the PG table is empty but the JSONL mirror has
        records, import them so the KB survives server restarts. The seed
        only fires on an empty table, keeping PG authoritative afterwards."""
        try:
            with self._conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {self.table}")
                if cur.fetchone()[0] > 0:
                    return
            records = self._jsonl_load_all()
            if not records:
                return
            for rec in records.values():
                self._pg_upsert(rec)
            logger.info(
                "[kb-storage] sembrados %d registros del JSONL (%s) a "
                "PostgreSQL tabla=%s", len(records), self.jsonl_path,
                self.table)
        except Exception as exc:
            logger.warning("[kb-storage] seeding omitido: %s", exc)

    def is_available(self) -> bool:
        with self._lock:
            return self._connect()

    @property
    def backend_name(self) -> str:
        return "postgresql" if self._pg_ok else "jsonl"

    def _try_pg(self) -> bool:
        """Return True if a healthy PG connection is present."""
        if self._pg2 is None:
            return False
        with self._lock:
            if self._pg_ok:
                return True
            return self._connect()

    def _downgrade(self, exc: Exception):
        self._pg_ok = False
        logger.warning(
            "[kb-storage] fallo PostgreSQL en operación (%s: %s) — fallback a JSONL: %s",
            exc.__class__.__name__, exc, self.jsonl_path)

    # ------------------------------------------------------------------
    # Record-level API (DecisionEngine semantics: upsert, last-wins load)
    # ------------------------------------------------------------------

    def register_hypothesis(self, record: Dict[str, Any]) -> str:
        hid = record.get("hypothesis_id") or f"hyp_{int(time.time() * 1000)}"
        record = dict(record, hypothesis_id=hid)
        if self._try_pg():
            try:
                self._pg_upsert(record)
                return hid
            except Exception as exc:
                self._downgrade(exc)
        self._jsonl_append(record)
        return hid

    def load_records(self) -> Dict[str, Dict[str, Any]]:
        if self._try_pg():
            try:
                return self._pg_load_all()
            except Exception as exc:
                self._downgrade(exc)
        return self._jsonl_load_all()

    def _pg_upsert(self, record: Dict[str, Any]):
        params = json.dumps(record.get("parameters", {}), ensure_ascii=False)
        raw = json.dumps(record, ensure_ascii=False, default=str)
        values = []
        for col in COLUMNS:
            v = record.get(col)
            if col == "parameters":
                v = params
            values.append(v)
        values.append(raw)
        placeholders = ", ".join(["%s"] * (len(COLUMNS) + 1))
        cols_sql = ", ".join(COLUMNS + ("raw",))
        updates = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in COLUMNS[1:] + ("raw",))
        sql = (f"INSERT INTO {self.table} ({cols_sql}) VALUES ({placeholders}) "
               f"ON CONFLICT (hypothesis_id) DO UPDATE SET {updates}, "
               "updated_at = EXTRACT(EPOCH FROM now())")
        with self._conn.cursor() as cur:
            cur.execute(sql, values)

    def _pg_load_all(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT raw FROM {self.table} ORDER BY created_at ASC NULLS FIRST")
            for (raw,) in cur.fetchall():
                rec = raw if isinstance(raw, dict) else json.loads(raw)
                out[rec["hypothesis_id"]] = rec
        return out

    # ------------------------------------------------------------------
    # JSONL mirror (identical semantics to DecisionEngine file format)
    # ------------------------------------------------------------------

    def _jsonl_append(self, record: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.jsonl_path) or ".", exist_ok=True)
        with open(self.jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _jsonl_load_all(self) -> Dict[str, Dict[str, Any]]:
        records: Dict[str, Dict[str, Any]] = {}
        if not os.path.exists(self.jsonl_path):
            return records
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
                if hid in records:
                    records[hid].update(rec)
                else:
                    records[hid] = rec
        return records

    # ------------------------------------------------------------------
    # Public interface mirroring HypothesisKnowledgeBase
    # ------------------------------------------------------------------

    def store_hypothesis(self, hypothesis: Any) -> str:
        record = self._to_record(hypothesis)
        return self.register_hypothesis(record)

    def retrieve_hypothesis(self, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        return self.load_records().get(hypothesis_id)

    def search_hypotheses(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        crit = dict(criteria)
        if hasattr(crit, "__dict__") and not isinstance(crit, dict):
            crit = vars(crit)
        crit = {k: v for k, v in (crit or {}).items() if v is not None}
        results = []
        for rec in self.load_records().values():
            if all(rec.get(k) == v for k, v in crit.items()):
                results.append(rec)
        return results

    def search_hypotheses_by_text(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        q = (query or "").lower()
        hits = [
            r for r in self.load_records().values()
            if q in json.dumps(r, ensure_ascii=False).lower()
        ]
        return hits[:limit]

    def search_similar_hypotheses(self, description: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        return self.search_hypotheses_by_text(description, limit=100)

    def update_hypothesis(self, hypothesis_id: str, updates: Dict[str, Any]) -> bool:
        records = self.load_records()
        if hypothesis_id not in records:
            return False
        merged = dict(records[hypothesis_id])
        merged.update(updates or {})
        merged["hypothesis_id"] = hypothesis_id
        if self._try_pg():
            try:
                self._pg_upsert(merged)
                return True
            except Exception as exc:
                self._downgrade(exc)
        self._jsonl_append(merged)
        return True

    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        existed = False
        if self._try_pg():
            try:
                with self._conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM {self.table} WHERE hypothesis_id = %s",
                        (hypothesis_id,))
                    existed = cur.rowcount > 0
            except Exception as exc:
                self._downgrade(exc)
        records = self.load_records()
        if hypothesis_id in records:
            remaining = [r for k, r in records.items() if k != hypothesis_id]
            self._rewrite_jsonl(remaining)
            existed = True
        return existed

    def _rewrite_jsonl(self, records: List[Dict[str, Any]]):
        os.makedirs(os.path.dirname(self.jsonl_path) or ".", exist_ok=True)
        tmp = self.jsonl_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        os.replace(tmp, self.jsonl_path)

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
        for attr in COLUMNS:
            val = getattr(hypothesis, attr, None)
            if val is not None:
                data[attr] = getattr(val, "value", val)
        extras = getattr(hypothesis, "__dict__", {})
        for k, v in extras.items():
            if k not in data and isinstance(v, (int, float, str, list, dict)):
                data[k] = getattr(v, "value", v)
        return data


class KBPersistence:
    """Storage facade used by DecisionEngine: PostgreSQL first, JSONL fallback."""

    _availability_cache: Dict[str, bool] = {}

    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        if os.environ.get("QUANTMATH_PG_DISABLE") == "1":
            self.kb = None
            logger.info("[kb-storage] backend=jsonl (QUANTMATH_PG_DISABLE=1)")
            return
        self.kb = PostgreSQLKnowledgeBase(
            storage_path=os.path.dirname(kb_path) or ".",
            jsonl_fallback=kb_path)
        logger.info("[kb-storage] backend=%s kb=%s",
                    self.kb.backend_name, kb_path)
        KBPersistence._availability_cache[self.kb.dsn] = \
            self.kb.backend_name == "postgresql"

    @property
    def mode(self) -> str:
        if self.kb is None:
            return "jsonl"
        return self.kb.backend_name

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        if self.kb is not None:
            return self.kb.load_records()
        records: Dict[str, Dict[str, Any]] = {}
        if not os.path.exists(self.kb_path):
            return records
        with open(self.kb_path, "r", encoding="utf-8") as fh:
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
                if hid in records:
                    records[hid].update(rec)
                else:
                    records[hid] = rec
        return records

    def save(self, record: Dict[str, Any]) -> str:
        if self.kb is not None:
            return self.kb.register_hypothesis(record)
        hid = record.get("hypothesis_id") or f"hyp_{int(time.time() * 1000)}"
        os.makedirs(os.path.dirname(self.kb_path) or ".", exist_ok=True)
        with open(self.kb_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(record, hypothesis_id=hid),
                                ensure_ascii=False, default=str) + "\n")
        return hid
