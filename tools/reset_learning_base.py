#!/usr/bin/env python3
"""CLI del reset de base de aprendizaje (ver quant_math/ml/learning_reset.py)."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quant_math.ml.learning_reset import reset_learning_base


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kb", default="runtime/hypotheses.jsonl")
    ap.add_argument("--state-dir", default="runtime/state")
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--force", action="store_true",
                    help="proceder aunque runtime_stats diga RUNNING")
    args = ap.parse_args()
    ok, msg = reset_learning_base(args.kb, args.state_dir, dsn=args.dsn,
                                  force=args.force)
    print(("[OK] " if ok else "[ABORTADO] ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
