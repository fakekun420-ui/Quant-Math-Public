"""JSONLKnowledgeBase tests: interface parity, atomic upsert,
search by status/symbol, zero-loss roundtrip."""

import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.autonomous_research.adapters.postgres_kb import (
    JSONLKnowledgeBase,
    KBPersistence,
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


def make_kb(tmp):
    return JSONLKnowledgeBase(jsonl_path=os.path.join(tmp, "hypotheses.jsonl"))


def make_persistence(tmp):
    return KBPersistence(kb_path=os.path.join(tmp, "hypotheses.jsonl"))


def test_roundtrip_zero_field_loss():
    """All fields survive a store/load cycle untouched."""
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        rec = dict(RECORD)
        rec["future_unknown_field"] = {"nested": [1, 2, 3]}
        hid = kb.register_hypothesis(rec)
        assert hid == RECORD["hypothesis_id"]
        loaded = kb.retrieve_hypothesis(hid)
        for key, val in rec.items():
            assert loaded[key] == val, f"campo perdido: {key}"
        kb.delete_hypothesis(hid)
        assert kb.retrieve_hypothesis(hid) is None
    print("PASS roundtrip: all fields intact")


def test_atomic_upsert():
    """Upsert merges without losing fields."""
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        hid = kb.register_hypothesis(dict(RECORD))
        # Update only status, other fields preserved
        kb.update_hypothesis(hid, {"status": "validated"})
        loaded = kb.retrieve_hypothesis(hid)
        assert loaded["status"] == "validated"
        assert loaded["expectancy"] == RECORD["expectancy"]
        assert loaded["symbol"] == RECORD["symbol"]
        kb.delete_hypothesis(hid)
    print("PASS atomic upsert: fields preserved")


def test_search_by_status():
    """Search by status returns correct subset."""
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        r1 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_s1",
                   symbol=f"A{UNIQUE}/USDT", status="backtested")
        r2 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_s2",
                   symbol=f"B{UNIQUE}/USDT", status="validated")
        r3 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_s3",
                   symbol=f"C{UNIQUE}/USDT", status="backtested")
        kb.register_hypothesis(r1)
        kb.register_hypothesis(r2)
        kb.register_hypothesis(r3)

        bt = kb.search_by_status("backtested")
        assert len(bt) == 2
        assert all(h["status"] == "backtested" for h in bt)

        val = kb.search_by_status("validated")
        assert len(val) == 1

        kb.delete_hypothesis(r1["hypothesis_id"])
        kb.delete_hypothesis(r2["hypothesis_id"])
        kb.delete_hypothesis(r3["hypothesis_id"])
    print("PASS search_by_status")


def test_search_by_symbol():
    """Search by symbol returns correct subset."""
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        sym = f"SYM{UNIQUE}/USDT"
        r1 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_y1",
                   symbol=sym, status="backtested")
        r2 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_y2",
                   symbol=f"OTHER{UNIQUE}/USDT", status="backtested")
        kb.register_hypothesis(r1)
        kb.register_hypothesis(r2)

        hits = kb.search_by_symbol(sym)
        assert len(hits) == 1
        assert hits[0]["symbol"] == sym

        kb.delete_hypothesis(r1["hypothesis_id"])
        kb.delete_hypothesis(r2["hypothesis_id"])
    print("PASS search_by_symbol")


def test_search_by_status_and_symbol():
    """Combined search by status + symbol."""
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        sym = f"SYM2{UNIQUE}/USDT"
        r1 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_c1",
                   symbol=sym, status="backtested")
        r2 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_c2",
                   symbol=sym, status="validated")
        r3 = dict(RECORD, hypothesis_id=f"hyp_test_{UNIQUE}_c3",
                   symbol=f"OTHER{UNIQUE}/USDT", status="backtested")
        kb.register_hypothesis(r1)
        kb.register_hypothesis(r2)
        kb.register_hypothesis(r3)

        hits = kb.search_by_status_and_symbol("backtested", sym)
        assert len(hits) == 1
        assert hits[0]["symbol"] == sym
        assert hits[0]["status"] == "backtested"

        kb.delete_hypothesis(r1["hypothesis_id"])
        kb.delete_hypothesis(r2["hypothesis_id"])
        kb.delete_hypothesis(r3["hypothesis_id"])
    print("PASS search_by_status_and_symbol")


def test_update_search_statistics():
    """update_hypothesis persists; search filters; stats count."""
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
    print("PASS update/search/statistics")


def test_kbpersistence_facade():
    """KBPersistence facade works identically."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_persistence(tmp)
        hid = p.save(dict(RECORD))
        assert hid == RECORD["hypothesis_id"]
        all_recs = p.load_all()
        assert hid in all_recs
        assert all_recs[hid]["expectancy"] == RECORD["expectancy"]
    print("PASS KBPersistence facade")


def test_no_synthetic_results_on_empty_search():
    """Empty KB returns [] — no dummy data."""
    with tempfile.TemporaryDirectory() as tmp:
        kb = make_kb(tmp)
        assert kb.search_hypotheses({}) == []
        assert kb.get_statistics()["total"] == 0
    print("PASS empty search returns []")


if __name__ == "__main__":
    run = [
        test_roundtrip_zero_field_loss,
        test_atomic_upsert,
        test_search_by_status,
        test_search_by_symbol,
        test_search_by_status_and_symbol,
        test_update_search_statistics,
        test_kbpersistence_facade,
        test_no_synthetic_results_on_empty_search,
    ]
    failed = 0
    for fn in run:
        try:
            fn()
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{len(run)-failed}/{len(run)} tests passed")
    sys.exit(1 if failed else 0)
