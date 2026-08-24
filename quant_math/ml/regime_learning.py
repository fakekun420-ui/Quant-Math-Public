"""Aprendizaje NO supervisado sobre operaciones cerradas.

OperationLearningLoop:
  - Clustering (KMeans) del dataset de operaciones para descubrir
    estructuras sin etiquetas humanas.
  - Tabla (regimen de mercado x familia) con tasa de exito por grupo,
    construida post-hoc contra pnl_pct.
  - recommend(): familias priorizadas para el simbolo/regimen actual.
  - should_explore(): detector de rachas/anomalias que dispara ráfagas
    de exploracion automatica.

Modo "collecting" hasta MIN_ROWS operaciones post-cutoff; nunca toca el
gate de decision (solo sesga el orden de generacion).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from quant_math.ml import feature_store as fs

logger = logging.getLogger(__name__)

MIN_ROWS = int(os.environ.get("QUANTMATH_SIS_MIN_ROWS", "30"))
STREAK_LOSS_LIMIT = 5
HAS_OPERATION_LEARNING = True


def vol_bucket(vol_pct: Optional[float]) -> str:
    if vol_pct is None:
        return "?"
    if vol_pct >= 70:
        return "high"
    if vol_pct <= 30:
        return "low"
    return "mid"


def family_of(row: Dict[str, Any]) -> str:
    st = str(row.get("strategy_type", ""))
    for fam in ("breakout", "mean_reversion", "momentum", "trend_following"):
        if fam in st:
            return fam
    return st or "?"


class OperationLearningLoop:
    """Refit barato por ciclo: KMeans + tablas agregadas."""

    def __init__(self, kb_records: Dict[str, Dict[str, Any]],
                 ledger_path: str, state_dir: str):
        self.mode = "collecting"
        self.rows: List[Dict[str, Any]] = []
        self.labels: Optional[np.ndarray] = None
        self.cluster_stats: List[Dict[str, Any]] = []
        self.regime_table: Dict[Tuple[str, str], Dict[str, float]] = {}
        self._fit(kb_records, ledger_path, state_dir)

    # ------------------------------------------------------------------

    def _fit(self, kb_records, ledger_path, state_dir):
        self.rows = fs.build_trade_dataset(kb_records, ledger_path, state_dir)
        if len(self.rows) < MIN_ROWS:
            self.mode = "collecting"
            logger.info("[SIS] recolectando: %d/%d operaciones post-corte",
                        len(self.rows), MIN_ROWS)
            return
        X = np.array(fs.encode_dataset(self.rows), dtype=float)
        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
            k = max(2, min(4, len(self.rows) // 25))
            Xs = StandardScaler().fit_transform(X)
            km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(Xs)
            self.labels = km.labels_
        except Exception as exc:
            logger.warning("[SIS] clustering no disponible (%s); "
                           "solo tablas agregadas", exc)
            self.labels = None

        # stats por cluster (post-hoc contra pnl_pct)
        self.cluster_stats = []
        if self.labels is not None:
            pnls = X[:, 2]
            for cid in range(int(self.labels.max()) + 1):
                idx = np.where(self.labels == cid)[0]
                if not len(idx):
                    continue
                p = pnls[idx]
                self.cluster_stats.append({
                    "cluster": cid, "n": int(len(idx)),
                    "win_rate": float((p > 0).mean()),
                    "mean_pnl_pct": float(np.nanmean(p)),
                })

        # tabla regimen x familia
        table: Dict[Tuple[str, str], List[float]] = {}
        streak_symbol_rows = sorted(
            self.rows, key=lambda r: float(r.get("duration_s") or 0))
        for r in self.rows:
            key = (f"{r.get('symbol')}|{vol_bucket(r.get('vol_pct'))}|"
                   f"{r.get('forecast_up')}", family_of(r))
            table.setdefault(key, []).append(float(r.get("pnl_pct") or 0.0))
        self.regime_table = {
            key: {"n": len(v), "win_rate": sum(1 for p in v if p > 0)
                  / len(v), "mean_pnl_pct": sum(v) / len(v)}
            for key, v in table.items() if v}
        self.mode = "active"

    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        top_clusters = sorted(self.cluster_stats,
                              key=lambda c: -c["mean_pnl_pct"])[:3]
        return {"mode": self.mode, "rows": len(self.rows),
                "clusters": top_clusters}

    def rank_families(self, symbol: str,
                      regime: Optional[Dict[str, Any]]) -> List[str]:
        """Familias ordenadas por exito historico en el regimen actual."""
        if self.mode != "active" or not self.regime_table:
            return []
        vb = vol_bucket(regime.get("vol_pct") if regime else None)
        fu = regime.get("forecast_up") if regime else None
        scored: Dict[str, Tuple[int, float]] = {}
        for (key, fam), s in self.regime_table.items():
            sym_r, vb_r, fu_r = key.split("|")
            match = (sym_r == symbol and (vb == "?" or vb_r == vb)
                     and (fu is None or fu_r in ("1.0", "0.0")
                          and (fu_r == "1.0") == bool(fu)))
            if not match:
                continue
            prev = scored.get(fam, (-1, -1e9))
            cand = (prev[0] + s["n"], max(prev[1], s["mean_pnl_pct"]))
            scored[fam] = cand
        ranked = sorted(scored.items(), key=lambda kv: -kv[1][1])
        families = [fam for fam, _ in ranked]
        for fallback in ("breakout", "momentum", "mean_reversion"):
            if fallback not in families:
                families.append(fallback)
        return families

    def _consecutive_losses(self) -> int:
        n = 0
        for r in reversed(sorted(
                self.rows, key=lambda x: float(x.get("duration_s") or 0))):
            if float(r.get("pnl_pct") or 0) <= 0:
                n += 1
            else:
                break
        return n

    def should_explore(self) -> bool:
        """Rafaga de exploracion si la racha de perdidas es larga."""
        if self.mode != "active":
            return False
        return self._consecutive_losses() >= STREAK_LOSS_LIMIT


def load_loop(kb_path: str, state_dir: str) -> OperationLearningLoop:
    """Construye el loop desde las fuentes durables (PG->JSONL fallback)."""
    records: Dict[str, Dict[str, Any]] = {}
    try:
        from quant_math.autonomous_research.adapters.postgres_kb import (
            KBPersistence)
        records = KBPersistence(kb_path).load_all()
    except Exception as exc:
        logger.warning("[SIS] carga KB fallo (%s); intento JSONL puro",
                       exc.__class__.__name__)
        if os.path.exists(kb_path):
            with open(kb_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    hid = rec.get("hypothesis_id")
                    if hid:
                        existing = records.get(hid)
                        if existing:
                            existing.update(rec)
                        else:
                            records[hid] = rec
    ledger = os.path.join(state_dir, "paper_executions.jsonl")
    return OperationLearningLoop(records, ledger, state_dir)

