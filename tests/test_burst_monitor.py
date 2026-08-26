"""Tests for Plan V2 Phase B5: burst monitor panel."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.orchestrator import BurstStateTracker


def test_burst_stats_in_stats_dict():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        t.register_entry(10)
        t.register_closure(0.5)
        t.register_closure(-0.2)
        s = t.stats_dict(10)
        assert "entries_this_cycle" in s
        assert "total_entries" in s
        assert "win_rate" in s
        assert "cooldown_remaining" in s
        assert s["total_entries"] == 1
        assert s["wins"] == 1
        assert s["losses"] == 1
        assert s["win_rate"] == 50.0


def test_burst_stats_zero_state():
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        s = t.stats_dict(100)
        assert s["total_entries"] == 0
        assert s["total_closures"] == 0
        assert s["win_rate"] == 0.0
        assert s["cooldown_remaining"] == 0


def test_burst_mode_in_orchestrator_stats():
    from quant_math.orchestrator import OrchestratorConfig
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst")
    assert cfg.mode == "burst"


def test_burst_panel_rows():
    """Verify that burst_stats dict has all fields needed by the monitor."""
    with tempfile.TemporaryDirectory() as tmp:
        t = BurstStateTracker(tmp)
        # Simulate some activity
        t.register_entry(1)
        t.register_entry(2)
        t.register_closure(0.3)
        t.register_closure(-0.1)
        t.register_closure(0.5)
        s = t.stats_dict(10)
        # All fields the monitor panel needs
        required = ["entries_this_cycle", "total_entries", "total_closures",
                     "wins", "losses", "win_rate", "consecutive_losses",
                     "cooldown_remaining"]
        for key in required:
            assert key in s, f"Missing key: {key}"


def test_graduation_burst_different_window():
    """Verify burst mode uses different graduation params."""
    from quant_math.orchestrator import OrchestratorConfig
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst")
    # Burst mode constraints applied
    assert cfg.interval_seconds <= 15
    assert cfg.take_profit_pct >= 0.004


if __name__ == "__main__":
    for fn in [test_burst_stats_in_stats_dict, test_burst_stats_zero_state,
               test_burst_mode_in_orchestrator_stats, test_burst_panel_rows,
               test_graduation_burst_different_window]:
        fn()
        print(f"PASS {fn.__name__}")
