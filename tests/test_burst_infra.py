"""Tests for Plan V2 Phase C1: burst infrastructure."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.orchestrator import OrchestratorConfig


def test_mode_classic_default():
    cfg = OrchestratorConfig(
        symbols=["XRP/USDT"], timeframe="1h", lookback_days=7,
        initial_capital=10000, entry_pct=0.05, take_profit_pct=0.02,
        min_paper_trades=3, hypotheses_per_cycle=3,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state")
    assert cfg.mode == "classic"


def test_mode_burst_forces_interval():
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", interval_seconds=60)
    assert cfg.interval_seconds == 15


def test_mode_burst_clamps_margin():
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=50, entry_pct=0.1, take_profit_pct=0.20,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", burst_margin=0.5)
    assert cfg.burst_margin == 1.0


def test_mode_burst_clamps_leverage():
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=50, entry_pct=0.1, take_profit_pct=0.20,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", burst_leverage=50)
    assert cfg.burst_leverage == 50
    # Absolute ceiling 150 (Bybit max for BTC)
    cfg2 = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=50, entry_pct=0.1, take_profit_pct=0.20,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", burst_leverage=200)
    assert cfg2.burst_leverage == 150


def test_mode_burst_clamps_tp():
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=50, entry_pct=0.1, take_profit_pct=0.80,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst")
    assert cfg.take_profit_pct == 0.50


def test_mode_invalid_raises():
    try:
        OrchestratorConfig(
            symbols=["XRP/USDT"], timeframe="1h", lookback_days=7,
            initial_capital=10000, entry_pct=0.05, take_profit_pct=0.02,
            min_paper_trades=3, hypotheses_per_cycle=3,
            kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
            mode="invalid")
        assert False, "should have raised"
    except ValueError as e:
        assert "mode" in str(e)


def test_burst_notional_calculation():
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", burst_margin=10.0, burst_leverage=10)
    notional = cfg.burst_margin * cfg.burst_leverage
    assert notional == 100.0


if __name__ == "__main__":
    for fn in [test_mode_classic_default, test_mode_burst_forces_interval,
               test_mode_burst_clamps_margin, test_mode_burst_clamps_leverage,
               test_mode_burst_clamps_tp, test_mode_invalid_raises,
               test_burst_notional_calculation]:
        fn()
        print(f"PASS {fn.__name__}")
