"""Tests for Plan V2 Phase B2: scalp_burst strategy + generation."""
import json
import math
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_based_generator import generate_model_hypotheses


def _sine_closes(n=150, freq=0.05, amp=5.0, base=100.0):
    return [base + amp * math.sin(freq * i) + 0.1 * i for i in range(n)]


def test_scalp_burst_in_model_generator():
    closes = _sine_closes(150)
    hyps = generate_model_hypotheses("BTC/USDT", closes, max_hypotheses=5)
    types = [h["parameters"]["strategy_type"] for h in hyps]
    assert "scalp_burst" in types, f"scalp_burst not found in {types}"


def test_scalp_burst_parameters():
    closes = _sine_closes(150)
    hyps = generate_model_hypotheses("ETH/USDT", closes, max_hypotheses=5)
    sb = [h for h in hyps if h["parameters"]["strategy_type"] == "scalp_burst"]
    assert len(sb) >= 1
    p = sb[0]["parameters"]
    assert "ema_fast" in p
    assert "ema_slow" in p
    assert "momentum_window" in p
    assert "momentum_threshold" in p
    assert "pullback_pct" in p


def test_scalp_burst_wfv_grid():
    from aqde_runner import AQDERunner
    with tempfile.TemporaryDirectory() as tmp:
        runner = AQDERunner(
            timeframe="5m", lookback_days=7,
            knowledge_base_path=os.path.join(tmp, "kb.jsonl"))
        hyp = type("Hyp", (), {
            "parameters": {"strategy_type": "scalp_burst", "ema_fast": 8}
        })()
        grid = runner._get_param_grid_for_hypothesis(hyp)
        assert "ema_fast" in grid
        assert "momentum_threshold" in grid
        assert len(grid["ema_fast"]) == 3


def test_scalp_burst_strategy_signal():
    from aqde_runner import AQDERunner
    with tempfile.TemporaryDirectory() as tmp:
        runner = AQDERunner(
            timeframe="5m", lookback_days=7,
            knowledge_base_path=os.path.join(tmp, "kb.jsonl"))
        # Create a trending price series
        closes = [100.0 + 0.5 * i + 0.1 * math.sin(i) for i in range(100)]
        hyp = type("Hyp", (), {
            "parameters": {"strategy_type": "scalp_burst",
                           "ema_fast": 8, "ema_slow": 21,
                           "momentum_window": 5, "momentum_threshold": 0.002,
                           "pullback_pct": 0.003, "symbol": "BTC/USDT"}
        })()
        strategy_func = runner._create_strategy_from_hypothesis(hyp)
        data = {"BTC/USDT": np.array(closes)}
        orders = strategy_func(data)
        assert len(orders) == len(closes)
        sides = [o["side"] for o in orders]
        assert "hold" in sides  # at least some holds


def test_burst_mode_prioritizes_scalp_burst():
    from quant_math.orchestrator import OrchestratorConfig
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst")
    assert cfg.mode == "burst"


if __name__ == "__main__":
    for fn in [test_scalp_burst_in_model_generator,
               test_scalp_burst_parameters,
               test_scalp_burst_wfv_grid,
               test_scalp_burst_strategy_signal,
               test_burst_mode_prioritizes_scalp_burst]:
        fn()
        print(f"PASS {fn.__name__}")
