"""Script de migracion y saneamiento de la KB operativa y cuarentena de descartes.

Mueve registros con n_trades == 0 o None desde la KB operativa hacia
runtime/hypotheses_rejects.jsonl, garantizando idempotencia y preservando
todos los datos para auditoria.
"""

import json
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sanitize_kb")


def sanitize_kb(kb_path: str, rejects_path: str = None) -> dict:
    if rejects_path is None:
        rejects_path = os.path.join(os.path.dirname(kb_path) or ".", "hypotheses_rejects.jsonl")

    if not os.path.exists(kb_path):
        logger.error("El archivo KB no existe: %s", kb_path)
        return {"error": "file_not_found"}

    with open(kb_path, "r", encoding="utf-8") as f:
        raw_lines = [line.strip() for line in f if line.strip()]

    total_before = len(raw_lines)
    logger.info("Total filas antes en %s: %d", kb_path, total_before)

    valid_lines = []
    reject_records = []

    for line in raw_lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        n_trades = rec.get("n_trades")
        if n_trades is None or int(n_trades) <= 0:
            rec_reject = dict(rec)
            rec_reject["quarantine_reason"] = "no_trades"
            if "quarantined_at" not in rec_reject:
                rec_reject["quarantined_at"] = time.time()
            reject_records.append(rec_reject)
        else:
            valid_lines.append(line)

    logger.info("Filas validas a conservar en KB: %d", len(valid_lines))
    logger.info("Filas a mover a cuarentena: %d", len(reject_records))

    # Cargar cuarentena existente para garantizar idempotencia por hypothesis_id
    existing_reject_ids = set()
    if os.path.exists(rejects_path):
        with open(rejects_path, "r", encoding="utf-8") as rf:
            for l in rf:
                l = l.strip()
                if not l:
                    continue
                try:
                    obj = json.loads(l)
                    hid = obj.get("hypothesis_id")
                    if hid:
                        existing_reject_ids.add(hid)
                except json.JSONDecodeError:
                    continue

    # Escribir en cuarentena los nuevos descartes
    new_quarantined = 0
    with open(rejects_path, "a", encoding="utf-8") as qf:
        for r in reject_records:
            hid = r.get("hypothesis_id")
            if hid and hid in existing_reject_ids:
                continue
            qf.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            if hid:
                existing_reject_ids.add(hid)
            new_quarantined += 1

    logger.info("Nuevos descartes agregados a cuarentena (%s): %d", rejects_path, new_quarantined)

    # Reescribir atomicamente la KB operativa
    tmp_kb = kb_path + ".tmp"
    with open(tmp_kb, "w", encoding="utf-8") as wf:
        for vl in valid_lines:
            wf.write(vl + "\n")
        wf.flush()
        os.fsync(wf.fileno())
    os.replace(tmp_kb, kb_path)

    total_after = len(valid_lines)
    logger.info("Total filas despues en KB operativa (%s): %d", kb_path, total_after)

    return {
        "total_before": total_before,
        "total_after": total_after,
        "quarantined": len(reject_records),
        "new_quarantined": new_quarantined,
    }


if __name__ == "__main__":
    target_kb = sys.argv[1] if len(sys.argv) > 1 else "runtime/hypotheses_classic-xrp.jsonl"
    sanitize_kb(target_kb)
