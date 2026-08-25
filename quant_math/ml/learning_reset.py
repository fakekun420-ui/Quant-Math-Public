"""Reset de la base de aprendizaje para la nueva integracion SIS.

Archiva (NUNCA destruye) el KB actual — JSONL y tabla PostgreSQL — y deja
el KB vacio para que solo hipotesis generadas CON la integracion nueva
(contexto _regime + aprendizaje no supervisado) lo pueblen.

El libro permanente de operaciones NO se toca; en su lugar se fija un
cutoff temporal (learning_meta.json) para que el dataset de aprendizaje
ignore operaciones previas a la integracion.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any, Dict, Optional, Tuple


def _close_pre_cutoff_entries(ledger_path: str, positions_path: str,
                              cutoff_ts: float, price_fn=None) -> int:
    """Convierte entradas sin closure en cierres 'manual' al precio actual
    (o entry_price si no hay red). Evita fantasmas que arrastren MtM para
    siempre tras un reset. Idempotente."""
    if not os.path.exists(ledger_path):
        return 0
    rows: List[Dict[str, Any]] = []
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    closed_keys = {r.get("key") for r in rows if "motivo_cierre" in r}
    ghosts = [r for r in rows
              if "motivo_cierre" not in r
              and (r.get("key") or f"{r.get('hypothesis_id')}:{r.get('symbol')}")
              not in closed_keys
              and float(r.get("timestamp") or 0) < cutoff_ts]
    if not ghosts:
        return 0
    if price_fn is None:
        def price_fn(symbol):
            try:
                import ccxt
                ex = getattr(ccxt, "bybit")({"enableRateLimit": True})
                return (ex.fetch_ticker(symbol).get("last")
                        or ex.fetch_ticker(symbol).get("close"))
            except Exception:
                return None
    now = time.time()
    appended = 0
    with open(ledger_path, "a", encoding="utf-8") as fh:
        for g in ghosts:
            key = g.get("key") or f"{g.get('hypothesis_id')}:{g.get('symbol')}"
            sym = g.get("symbol", "")
            side = g.get("side", "buy")
            entry = float(g.get("entry_price", 0.0))
            qty = float(g.get("quantity", 1.0))
            cur = price_fn(sym) if sym else None
            exit_px = float(cur) if cur else entry
            direction = 1 if side == "buy" else -1
            pnl = qty * (exit_px - entry) * direction
            notional = float(g.get("notional_usd") or qty * entry)
            fh.write(json.dumps({
                "type": "closure", "key": key, "symbol": sym,
                "hypothesis_id": g.get("hypothesis_id"), "side": side,
                "entry_price": entry, "exit_price": exit_px,
                "quantity": qty, "pnl": round(pnl, 10),
                "pnl_pct": round(pnl / notional * 100, 6)
                           if notional else 0.0,
                "entry_time": g.get("timestamp"),
                "exit_time": now, "motivo_cierre": "manual",
            }, ensure_ascii=False, default=str) + "\n")
            appended += 1
    # limpiar posiciones.jsonl de esas keys
    if os.path.exists(positions_path):
        kept = []
        with open(positions_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("key") in {g.get("key") or
                                      f"{g.get('hypothesis_id')}:{g.get('symbol')}"
                                      for g in ghosts}:
                    continue
                kept.append(rec)
        tmp = positions_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for rec in kept:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, positions_path)
    return appended


def reset_learning_base(kb_jsonl: str, state_dir: str,
                        archive_dir: Optional[str] = None,
                        dsn: Optional[str] = None,
                        force: bool = False) -> Tuple[bool, str]:
    """Devuelve (ok, mensaje). Rehusa actuar si runtime_stats dice RUNNING
    salvo force=True."""
    stats_path = os.path.join(state_dir, "runtime_stats.json")
    if not force and os.path.exists(stats_path):
        try:
            with open(stats_path, encoding="utf-8") as fh:
                if json.load(fh).get("state") == "RUNNING":
                    return False, ("orchestrator RUNNNING: detenlo desde la "
                                   "CLI antes de limpiar la base")
        except (OSError, json.JSONDecodeError):
            pass

    ts = time.strftime("%Y%m%d_%H%M%S")
    archive_dir = archive_dir or os.path.join(
        os.path.dirname(kb_jsonl), "archive")
    os.makedirs(archive_dir, exist_ok=True)

    # 1) archivar JSONL del KB si existe
    archived = None
    if os.path.exists(kb_jsonl):
        archived = os.path.join(archive_dir, f"hypotheses_{ts}.jsonl")
        shutil.copy2(kb_jsonl, archived)

    # 2) archivar y vaciar tabla(s) PostgreSQL si alcanzables
    pg_info = ""
    try:
        from quant_math.autonomous_research.adapters.postgres_kb import (
            PostgreSQLKnowledgeBase)
        kb = PostgreSQLKnowledgeBase(
            storage_path=os.path.dirname(kb_jsonl) or ".",
            dsn=dsn, jsonl_fallback=kb_jsonl)
        if kb.is_available():
            records = kb._pg_load_all()
            if records:
                dump = os.path.join(archive_dir, f"hypotheses_pg_{ts}.jsonl")
                with open(dump, "w", encoding="utf-8") as fh:
                    for rec in records.values():
                        fh.write(json.dumps(rec, ensure_ascii=False,
                                            default=str) + "\n")
                with kb._conn.cursor() as cur:
                    cur.execute(f"DELETE FROM {kb.table}")
                pg_info = f"; PG: {len(records)} registros archivados+borrados"
            else:
                pg_info = "; PG ya estaba vacio"
    except Exception as exc:
        pg_info = f"; PG no tocado ({exc.__class__.__name__})"

    # 3) truncar JSONL del KB (queda vacio para la nueva integracion)
    with open(kb_jsonl, "w", encoding="utf-8") as fh:
        fh.write("")

    # 4) cerrar entradas huerfanas pre-reset (evita fantasmas MtM eternos)
    ledger = os.path.join(state_dir, "paper_executions.jsonl")
    positions = os.path.join(state_dir, "positions.jsonl")
    closed_n = _close_pre_cutoff_entries(ledger, positions, time.time())

    # 5) cutoff de aprendizaje: operaciones previas quedan fuera del dataset
    from quant_math.ml.feature_store import set_integration_cutoff
    set_integration_cutoff(state_dir, time.time())
    if closed_n:
        nonlocal_msg = f"; {closed_n} entrada(s) fantasma cerrada(s) al precio actual"
    else:
        nonlocal_msg = ""

    msg = (f"KB archivado en {archived}{pg_info}; JSONL reiniciado; "
           f"cutoff de aprendizaje fijado (libro permanente intacto)"
           f"{nonlocal_msg}")
    return True, msg
