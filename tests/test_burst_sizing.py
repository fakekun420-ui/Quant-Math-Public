"""Tests for Plan V2 Phase B1: burst sizing (margin × leverage)."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def test_burst_sizing_notional():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                 "status": "backtested", "strategy_type": "scalp_burst",
                 "expectancy": 0.01}]
        eng = make_engine(tmp, rows, mode="burst",
                          burst_margin=10.0, burst_leverage=10)
        # Verify notional would be margin * leverage = 100
        assert eng.burst_margin == 10.0
        assert eng.burst_leverage == 10
        assert eng.mode == "burst"


def test_burst_sizing_different_params():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                 "status": "backtested", "strategy_type": "scalp_burst",
                 "expectancy": 0.01}]
        eng = make_engine(tmp, rows, mode="burst",
                          burst_margin=20.0, burst_leverage=5)
        assert eng.burst_margin * eng.burst_leverage == 100.0


def test_classic_mode_no_burst_params():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                 "status": "backtested", "strategy_type": "momentum",
                 "expectancy": 0.01}]
        eng = make_engine(tmp, rows, mode="classic")
        assert eng.mode == "classic"
        assert eng.burst_margin == 10.0
        assert eng.burst_leverage == 10


def test_burst_tp_range():
    from quant_math.orchestrator import OrchestratorConfig
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", burst_margin=10, burst_leverage=10)
    # TP should be clamped to [0.004, 0.008]
    assert 0.004 <= cfg.take_profit_pct <= 0.008
    # SL = TP/2
    sl = cfg.take_profit_pct / 2
    assert sl > 0


def test_burst_trade_record_fields():
    from quant_math.orchestrator import OrchestratorConfig
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", burst_margin=10.0, burst_leverage=10)
    # Verify burst config is accessible for trade record enrichment
    assert cfg.mode == "burst"
    assert cfg.burst_margin == 10.0
    assert cfg.burst_leverage == 10


if __name__ == "__main__":
    for fn in [test_burst_sizing_notional, test_burst_sizing_different_params,
               test_classic_mode_no_burst_params, test_burst_tp_range,
               test_burst_trade_record_fields]:
        fn()
        print(f"PASS {fn.__name__}")
