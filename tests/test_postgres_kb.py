"""PostgreSQLKnowledgeBase tests: interface parity, zero-loss roundtrip,
automatic JSONL fallback when PostgreSQL is down. Skips PG-backed tests if
the server is unreachable (the system itself must never crash on that)."""

import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.autonomous_research.adapters.postgres_kb import (
    PostgreSQLKnowledgeBase,
)

UNIQUE = str(int(time.time() * 1000) % 10**9)

RECORD = {
    "hypothesis_id": f"hyp_test_{UNIQUE}_0001",
    "name": "Breakout_10_TESTUSDT",
    "description": "Donchian breakout 10 for TEST/USDT",
    "strategy_type": "breakout",
    "symbol": f"TEST{UNIQUE}/USDT",
    "status": "backtested",
    "expectancy": 0.0123,
    "scientific_score": 0.87,
    "win_rate": 54.5,
    "total_return": 1234.56,
    "total_return_pct": 12.3456,
    "n_trades": 42,
    "sharpe_ratio": 1.31,
    "max_drawdown": 0.08,
    "parameters": {"donchian_window": 10, "symbol": f"TEST{UNIQUE}/USDT"},
    "data_source": "bybit:real",
    "orchestrator_cycle": 7,
    "created_at": 1787464263.02,
}

PG_UP = None


def pg_available() -> bool:
    global PG_UP
    if PG_UP is None:
        with tempfile.TemporaryDirectory() as tmp:
            kb = PostgreSQLKnowledgeBase(
                storage_path=tmp, dsn=os.environ.get("QUANTMATH_PG_DSN"))
            PG_UP = kb.is_available()
    return PG_UP


def make_kb(tmp):
    return PostgreSQLKnowledgeBase(
        storage_path=tmp,
        dsn=os.environ.get("QUANTMATH_PG_DSN"),
        jsonl_fallback=os.path.join(tmp, "hypotheses.jsonl"),
    )


def test_roundtrip_zero_field_loss():
    """All 18 fields survive a PG store/load cycle untouched."""
    if not pg_available():
        pytest.skip("PostgreSQL no disponible en este entorno")
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        assert kb.backend_name == "postgresql"
        rec = dict(RECORD)
        rec["future_unknown_field"] = {"nested": [1, 2, 3]}
        hid = kb.register_hypothesis(rec)
        assert hid == RECORD["hypothesis_id"]
        loaded = kb.retrieve_hypothesis(hid)
        for key, val in rec.items():
            assert loaded[key] == val, f"campo perdido: {key}"
        kb.delete_hypothesis(hid)
        assert kb.retrieve_hypothesis(hid) is None
    print("PASS roundtrip: 18 campos + campos nuevos intactos en PG")


def test_update_search_statistics():
    """update_hypothesis persists; search filters; stats count."""
    if not pg_available():
        pytest.skip("PostgreSQL no disponible en este entorno")
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        try:
            kb.register_hypothesis(dict(RECORD))
            other = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_0002",
                         symbol=f"OTHER{UNIQUE}/USDT", status="failed",
                         expectancy=-0.01)
            kb.register_hypothesis(other)

            ok = kb.update_hypothesis(other["hypothesis_id"],
                                      {"status": "backtested"})
            assert ok is True
            assert kb.retrieve_hypothesis(
                other["hypothesis_id"])["status"] == "backtested"

            hits = kb.search_hypotheses({"symbol": RECORD["symbol"]})
            assert len(hits) >= 1
            assert all(h["symbol"] == RECORD["symbol"] for h in hits)

            stats = kb.get_statistics()
            ids = {h["hypothesis_id"] for h in stats["hypotheses"]}
            assert stats["total"] >= 2

            text = kb.search_hypotheses_by_text(f"TEST{UNIQUE}")
            assert len(text) >= 1
        finally:
            kb.delete_hypothesis(RECORD["hypothesis_id"])
            kb.delete_hypothesis(f"hyp_test_{UNIQUE}_0002")
    print("PASS update/search/statistics sobre PostgreSQL")


def test_fallback_to_jsonl_when_pg_down():
    """Unreachable DSN -> every op lands in JSONL, no exception ever."""
    dead_dsn = "host=127.0.0.1 port=59999 dbname=x user=x password=x connect_timeout=1"
    with tempfile.TemporaryDirectory() as tmp:
        fallback = os.path.join(tmp, "kb.jsonl")
        kb = PostgreSQLKnowledgeBase(
            storage_path=tmp, dsn=dead_dsn, jsonl_fallback=fallback)
        assert kb.backend_name == "jsonl"

        hid = kb.register_hypothesis(dict(RECORD))
        assert hid == RECORD["hypothesis_id"]
        assert os.path.exists(fallback)

        loaded = kb.load_records()
        assert loaded[hid]["expectancy"] == RECORD["expectancy"]

        assert kb.update_hypothesis(hid, {"status": "validated"}) is True
        with open(fallback) as fh:
            lines = [json.loads(l) for l in fh]
        assert lines[-1]["status"] == "validated"

        assert kb.retrieve_hypothesis(hid)["status"] == "validated"
        assert kb.delete_hypothesis(hid) is True
        assert kb.retrieve_hypothesis(hid) is None
        assert kb.get_statistics()["total"] == 0
    print("PASS fallback: PG caído -> JSONL en todas las operaciones, sin crash")


def test_no_synthetic_results_on_empty_search():
    """Empty KB returns [] — the stub's demo_001 dummy must NOT reappear."""
    dead_dsn = "host=127.0.0.1 port=59999 dbname=x user=x password=x connect_timeout=1"
    with tempfile.TemporaryDirectory() as tmp:
        kb = PostgreSQLKnowledgeBase(
            storage_path=tmp, dsn=dead_dsn,
            jsonl_fallback=os.path.join(tmp, "kb.jsonl"))
        assert kb.search_hypotheses({}) == []
        assert kb.get_statistics()["total"] == 0
    print("PASS anti-datos-sintéticos: búsqueda vacía devuelve []")


if __name__ == "__main__":
    run = [
        test_roundtrip_zero_field_loss,
        test_update_search_statistics,
        test_fallback_to_jsonl_when_pg_down,
        test_no_synthetic_results_on_empty_search,
    ]
    failed = 0
    for fn in run:
        try:
            fn()
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{len(run)-failed}/{len(run)} postgres_kb tests passed")
    sys.exit(1 if failed else 0)
