"""Saneador idempotente del ledger permanente de ejecuciones.

Corrige la semantica del ledger (paper_executions.jsonl) deduplicando cierres
multiples pertenecientes a una misma operacion/posicion (clave: key, entry_time, quantity).
Los cierres descartados (superseded) se mueven a un fichero de cuarentena con su motivo
(execution_closures_rejects.jsonl en el mismo directorio de estado), nunca se borran.
"""

import json
import logging
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def sanitize_paper_executions(
    ledger_path: str,
    quarantine_path: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Sanea el fichero paper_executions.jsonl de forma estrictamente idempotente.

    Semantica de deduplicacion:
    - Una operacion fisica en el libro queda identificada por la tupla:
      (key, entry_time, quantity).
    - Si para una misma operacion existen multiples filas de tipo closure,
      se conserva UNICAMENTE el ultimo cierre (el definitivo, que refleja el
      cierre real del exchange o la marca final antes de salir del ciclo).
    - Los cierres obsoletos se mueven a cuarentena sin ser eliminados.
    - Las filas de apertura (type != 'closure' y sin motivo_cierre) se conservan intactas.
    - La operacion es atomica: escribe en temporal y renombra con fsync.
    - Es idempotente: si se ejecuta de nuevo sobre un ledger ya saneado,
      quarantine_added es 0 y el ledger no sufre modificaciones.
    """
    if not os.path.exists(ledger_path):
        return {
            "status": "not_found",
            "kept_entries": 0,
            "kept_closures": 0,
            "quarantined": 0,
            "realized_pnl": 0.0,
        }

    state_dir = os.path.dirname(ledger_path) or "."
    if quarantine_path is None:
        quarantine_path = os.path.join(state_dir, "execution_closures_rejects.jsonl")

    # Leer todas las lineas del ledger
    raw_lines: List[Dict[str, Any]] = []
    with open(ledger_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                raw_lines.append(rec)
            except json.JSONDecodeError:
                continue

    # Agrupar cierres por (key, entry_time, quantity)
    # y preservar el orden cronologico de aparicion
    entries: List[Dict[str, Any]] = []
    closure_groups: Dict[Tuple[str, Any, Any], List[Dict[str, Any]]] = {}

    for rec in raw_lines:
        is_closure = (rec.get("type") == "closure") or ("motivo_cierre" in rec)
        if not is_closure:
            entries.append(rec)
        else:
            k = (
                str(rec.get("key") or f"{rec.get('hypothesis_id')}:{rec.get('symbol')}"),
                rec.get("entry_time"),
                rec.get("quantity"),
            )
            closure_groups.setdefault(k, []).append(rec)

    kept_closures: List[Dict[str, Any]] = []
    to_quarantine: List[Dict[str, Any]] = []

    for k, items in closure_groups.items():
        # El cierre definitivo es el ultimo emitido
        kept_closures.append(items[-1])
        for it in items[:-1]:
            q_item = dict(it)
            q_item["quarantine_reason"] = "superseded_duplicate_closure"
            q_item["quarantined_for_group"] = {
                "key": k[0],
                "entry_time": k[1],
                "quantity": k[2],
            }
            to_quarantine.append(q_item)

    # Reconstruir el ledger en su orden cronologico de cierre o apertura
    # Para mantener el orden original del archivo, intercalamos segun aparicion del elemento mantenido
    kept_records: List[Dict[str, Any]] = []
    # Conjunto de objetos descartados para omitirlos
    # Usamos id() o comparacion directa
    discarded_ids = {id(x) for x in to_quarantine}
    # Pero to_quarantine son copias, asociaremos con las instancias en raw_lines
    discarded_raw = []
    for k, items in closure_groups.items():
        for it in items[:-1]:
            discarded_raw.append(id(it))
    discarded_set = set(discarded_raw)

    for rec in raw_lines:
        if id(rec) not in discarded_set:
            kept_records.append(rec)

    realized_pnl = sum(
        float(r.get("pnl", 0.0) or 0.0)
        for r in kept_records
        if (r.get("type") == "closure") or ("motivo_cierre" in r)
    )

    if dry_run or not to_quarantine:
        return {
            "status": "dry_run" if dry_run else "already_clean",
            "total_initial": len(raw_lines),
            "kept_entries": len(entries),
            "kept_closures": len(kept_closures),
            "quarantined_now": len(to_quarantine),
            "realized_pnl": round(realized_pnl, 6),
            "modified": False,
        }

    # Escribir en cuarentena (append de los duplicados)
    with open(quarantine_path, "a", encoding="utf-8") as qf:
        for q_rec in to_quarantine:
            qf.write(json.dumps(q_rec, ensure_ascii=False) + "\n")
        qf.flush()
        os.fsync(qf.fileno())

    # Escribir el nuevo ledger atomicamente (tempfile -> replace)
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, prefix="ledger_clean_", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as tf:
        for r in kept_records:
            tf.write(json.dumps(r, ensure_ascii=False) + "\n")
        tf.flush()
        os.fsync(tf.fileno())

    os.replace(tmp_path, ledger_path)

    logger.info(
        "[sanitize_ledger] Ledger saneado: %d iniciales -> %d mantenidos (%d cierres, %d entradas). "
        "%d cierres movidos a %s. PnL acumulado: %.6f",
        len(raw_lines),
        len(kept_records),
        len(kept_closures),
        len(entries),
        len(to_quarantine),
        quarantine_path,
        realized_pnl,
    )

    return {
        "status": "sanitized",
        "total_initial": len(raw_lines),
        "kept_entries": len(entries),
        "kept_closures": len(kept_closures),
        "quarantined_now": len(to_quarantine),
        "realized_pnl": round(realized_pnl, 6),
        "modified": True,
    }


if __name__ == "__main__":
    import sys

    target_ledger = sys.argv[1] if len(sys.argv) > 1 else "runtime/state_classic-xrp/paper_executions.jsonl"
    dry = "--dry-run" in sys.argv
    res = sanitize_paper_executions(target_ledger, dry_run=dry)
    print(json.dumps(res, indent=2))
