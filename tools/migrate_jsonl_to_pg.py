#!/usr/bin/env python3
"""Migrate every record from the JSONL Knowledge Base into PostgreSQL.

Idempotent: re-running only upserts (ON CONFLICT DO UPDATE). Verifies after
migration that no hypothesis_id is missing from PostgreSQL. Exits non-zero
on mismatch or if PostgreSQL is unreachable.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.autonomous_research.adapters.postgres_kb import (
    PostgreSQLKnowledgeBase,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", default="runtime/hypotheses.jsonl")
    ap.add_argument("--dsn", default=None)
    args = ap.parse_args()

    if not os.path.exists(args.jsonl):
        print(f"JSONL no encontrado: {args.jsonl}")
        return 1

    kb = PostgreSQLKnowledgeBase(
        storage_path=os.path.dirname(args.jsonl) or ".",
        dsn=args.dsn,
        jsonl_fallback=args.jsonl,
    )
    if not kb.is_available():
        print("PostgreSQL no disponible — migración abortada "
              "(el sistema sigue operando en modo JSONL).")
        return 1

    source = {}
    with open(args.jsonl, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = _safe_loads(line)
            if rec and rec.get("hypothesis_id"):
                hid = rec["hypothesis_id"]
                if hid in source:
                    source[hid].update(rec)
                else:
                    source[hid] = rec

    migrated = 0
    for hid, rec in source.items():
        try:
            kb._pg_upsert(rec)
            migrated += 1
        except Exception as exc:
            print(f"ERROR upsert {hid}: {exc}")
            return 2

    in_pg = kb._pg_load_all()
    missing = set(source) - set(in_pg)
    print(f"JSONL registros únicos : {len(source)}")
    print(f"Upserts aplicados      : {migrated}")
    print(f"Registros en PostgreSQL: {len(in_pg)}")
    print(f"Faltantes              : {len(missing)}")
    if missing:
        for hid in sorted(missing)[:20]:
            print(f"  FALTA {hid}")
        return 2
    print("MIGRACIÓN COMPLETA — sin pérdida de registros.")
    return 0


def _safe_loads(line):
    import json
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    sys.exit(main())
