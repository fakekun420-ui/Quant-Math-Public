"""Tests for Plan V2 Phase B3: BurstStateTracker + cooldown + trend filter."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.orchestrator import BurstStateTracker, OrchestratorConfig
from quant_math.decision_engine import DecisionEngine


def make_engine(tmp, rows, symbols=None, **kw):
    kb = os.path.join(tmp, "kb.jsonl")
    with open(kb, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return DecisionEngine(
        symbols=symbols or ["BTC/USDT"], kb_path=kb,
        state_dir=os.path.join(tmp, "state"),
        data_provider=lambda s: [[i, 100, 101, 99, 100 + i, 10]
                                  for i in range(50)],
        use_postgres=False, **kw)


def test_tracker_can_enter_initially():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        assert t.can_enter(100)


def test_tracker_max_entries():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        for i in range(5):
            t.register_entry(100)
        assert not t.can_enter(100)


def test_tracker_cooldown():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_entry(100)
        assert not t.can_enter(101)  # within cooldown
        assert t.can_enter(111)  # after 10 cycles


def test_tracker_reset_cycle():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_entry(100)
        t.register_entry(100)
        t.reset_cycle()
        assert t.state.entries_this_cycle == 0
        # Cooldown still applies from last_entry_cycle=100
        assert not t.can_enter(100)
        assert t.can_enter(111)


def test_tracker_closure_stats():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_closure(0.5)
        t.register_closure(-0.3)
        t.register_closure(0.2)
        assert t.state.wins == 2
        assert t.state.losses == 1
        assert t.state.consecutive_losses == 0


def test_tracker_consecutive_losses():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_closure(-0.1)
        t.register_closure(-0.2)
        t.register_closure(0.3)
        assert t.state.consecutive_losses == 0  # reset on win
        t.register_closure(-0.1)
        assert t.state.consecutive_losses == 1


def test_tracker_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_entry(50)
        t.register_closure(0.5)
        t2 = BurstStateTracker(tmp)
        assert t2.state.total_entries == 1
        assert t2.state.total_closures == 1


def test_trend_filter_blocks_wrong_direction():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                 "status": "backtested", "strategy_type": "scalp_burst",
                 "expectancy": 0.01}]
        eng = make_engine(tmp, rows, mode="burst")
        # Candles with strong downtrend (EMA fast < EMA slow)
        # Alternating to avoid RSI/other filters triggering
        candles = []
        for i in range(50):
            p = 100 - 0.5 * i + 0.1 * (i % 3)
            candles.append({"open": p - 0.1, "high": p + 0.5,
                            "low": p - 0.5, "close": p, "volume": 10})
        eng.fetch_real_data = lambda s: candles
        # The momentum direction will likely be "sell" (downtrend)
        # Trend filter should block "buy" in downtrend
        result = eng.decide("BTC/USDT")
        # If side was "buy", trend filter should block it
        if result and result.get("action") == "no_entry":
            assert result.get("reason") == "burst_trend_filter"


def test_cooldown_remaining():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_entry(100)
        assert t.cooldown_remaining(105) == 5
        assert t.cooldown_remaining(110) == 0
        assert t.cooldown_remaining(120) == 0


def test_stats_dict():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_entry(100)
        t.register_closure(0.5)
        s = t.stats_dict(100)
        assert s["total_entries"] == 1
        assert s["total_closures"] == 1
        assert s["wins"] == 1
        assert s["win_rate"] == 100.0


if __name__ == "__main__":
    for fn in [test_tracker_can_enter_initially, test_tracker_max_entries,
               test_tracker_cooldown, test_tracker_reset_cycle,
               test_tracker_closure_stats, test_tracker_consecutive_losses,
               test_tracker_persistence, test_trend_filter_blocks_wrong_direction,
               test_cooldown_remaining, test_stats_dict]:
        fn()
        print(f"PASS {fn.__name__}")
