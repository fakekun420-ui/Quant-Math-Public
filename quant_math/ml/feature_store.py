"""Feature store del aprendizaje no supervisado.

Une el libro permanente de operaciones (paper_executions.jsonl, cierres con
motivo_cierre) con los registros de hipotesis del KB (parametros + contexto
de mercado _regime persistido por el model-gen), produciendo un dataset por
operacion listo para clustering.

Cutoff de integracion: si existe runtime/state/learning_meta.json con
"integration_ts", las operaciones ANTERIORES a ese timestamp se excluyen del
aprendizaje (la base no se contamina con datos pre-integracion). El libro en
si NUNCA se toca: sigue siendo el historial permanente visible.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

NUMERIC_PARAM_KEYS = ("donchian_window", "rsi_period", "bb_period",
                      "short_window", "atr_window")


def integration_cutoff(state_dir: str) -> Optional[float]:
    path = os.path.join(state_dir, "learning_meta.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return float(json.load(fh).get("integration_ts") or 0) or None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def set_integration_cutoff(state_dir: str, ts: float):
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "learning_meta.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"integration_ts": ts}, fh)


def read_closures(ledger_path: str,
                  since_ts: Optional[float] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(ledger_path):
        return out
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "motivo_cierre" not in rec:
                continue
            if since_ts and float(rec.get("exit_time") or 0) < since_ts:
                continue
            out.append(rec)
    return out


def build_trade_dataset(kb_records: Dict[str, Dict[str, Any]],
                        ledger_path: str,
                        state_dir: str) -> List[Dict[str, Any]]:
    """Una fila por cierre post-cutoff, enriquecida con KB + _regime."""
    cutoff = integration_cutoff(state_dir)
    rows: List[Dict[str, Any]] = []
    for c in read_closures(ledger_path, cutoff):
        hid = c.get("hypothesis_id", "")
        h = kb_records.get(hid, {})
        params = h.get("parameters") or {}
        regime = params.get("_regime") or {}
        p_num = next((float(params[k]) for k in NUMERIC_PARAM_KEYS
                      if k in params and params[k] is not None), None)
        fu = regime.get("forecast_up")
        st_raw = h.get("strategy_type")
        st = getattr(st_raw, "value", None) or str(st_raw or "")
        rows.append({
            "strategy_type": st.split(".")[-1],
            "symbol": c.get("symbol", ""),
            "motivo": c.get("motivo_cierre", ""),
            "pnl_pct": c.get("pnl_pct"),
            "duration_s": (float(c.get("exit_time") or 0)
                           - float(c.get("entry_time") or 0)),
            "p_window": p_num,
            "vol_pct": regime.get("vol_pct"),
            "forecast_up": (1.0 if fu else 0.0) if fu is not None else None,
            "cycle_len": regime.get("cycle_len"),
            "k_slope": regime.get("k_slope"),
            "k_noise": regime.get("k_noise"),
        })
    return rows


def encode_row(row: Dict[str, Any]) -> List[float]:
    """Vector fijo para clustering; None -> -1."""
    fam = {"breakout": 0, "mean_reversion": 1, "momentum": 2,
           "trend_following": 3}.get(str(row.get("strategy_type")), -1)
    mot = {"tp": 0, "sl": 1}.get(str(row.get("motivo")), 2)

    def num(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return -1.0
        return v
    return [fam, mot, num(row.get("pnl_pct")), num(row.get("p_window")),
            num(row.get("vol_pct")), num(row.get("forecast_up")),
            num(row.get("cycle_len")), num(row.get("k_slope")),
            num(row.get("k_noise"))]


def encode_dataset(rows: List[Dict[str, Any]]) -> List[List[float]]:
    return [encode_row(r) for r in rows]
