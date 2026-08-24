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

    # 4) cutoff de aprendizaje: operaciones previas quedan fuera del dataset
    from quant_math.ml.feature_store import set_integration_cutoff
    set_integration_cutoff(state_dir, time.time())

    msg = (f"KB archivado en {archived}{pg_info}; JSONL reiniciado; "
           f"cutoff de aprendizaje fijado (libro permanente intacto)")
    return True, msg
