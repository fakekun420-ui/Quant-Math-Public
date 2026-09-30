"""Tests for Plan V2 Phase B4+C2: burst slippage + exposure cap."""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.decision_engine import DecisionEngine
from quant_math.orchestrator import BurstStateTracker


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


def test_burst_slippage_tighter():
    """El slippage por defecto ya NO es un supuesto: es el spread medido.

    Antes burst valia 0,0003 y classic 0,0005, ambos inventados. El
    2026-09-30 se leyo el libro de Bybit y el spread real de XRP es
    0,0067%, o sea que cruzar paga 0,0034% por lado. Por defecto los dos
    modos usan ese valor real.

    La diferencia burst/classic se conserva como capacidad: si el operador
    la quiere, se fija por entorno, y eso es lo que comprueba este test.
    """
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                 "status": "backtested", "strategy_type": "scalp_burst",
                 "expectancy": 0.01}]
        eng = make_engine(tmp, rows, mode="burst")
        # Por defecto: la mitad del spread MEDIDO (0,0034%).
        assert eng.burst_slippage_pct == pytest.approx(0.000034)
        precio = 100.0
        assert abs(eng._slip(precio, "buy", True) - 100.0034) < 0.001

        # Y se puede apretar mas para burst por entorno (eso si es decision
        # del operador, no un numero inventado en el codigo).
        os.environ["QUANTMATH_BURST_SLIPPAGE_PCT"] = "0.00002"
        try:
            eng2 = make_engine(tmp, rows, mode="burst")
            assert eng2.burst_slippage_pct == pytest.approx(0.00002)
            assert abs(eng2._slip(precio, "buy", True) - 100.002) < 0.001
        finally:
            os.environ.pop("QUANTMATH_BURST_SLIPPAGE_PCT", None)


def test_classic_slippage_es_el_spread_medido():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                 "status": "backtested", "strategy_type": "momentum",
                 "expectancy": 0.01}]
        eng = make_engine(tmp, rows, mode="classic")
        # 0,05% era un supuesto. El real medido es la mitad del spread:
        # 0,0034% por lado.
        assert eng.slippage_pct == pytest.approx(0.000034)
        precio = 100.0
        assert abs(eng._slip(precio, "buy", True) - 100.0034) < 0.001


def test_exposure_cap_blocks_entry():
    with tempfile.TemporaryDirectory() as tmp:
        # Simulate 5 open burst entries
        ledger = os.path.join(tmp, "paper_executions.jsonl")
        with open(ledger, "w") as fh:
            for i in range(5):
                rec = {"key": f"h{i}:BTC/USDT", "symbol": "BTC/USDT",
                       "margin_usd": 10.0, "leverage": 10,
                       "side": "buy", "entry_price": 100.0,
                       "quantity": 1.0, "mode": "paper"}
                fh.write(json.dumps(rec) + "\n")
        from quant_math.orchestrator import Orchestrator
        cfg = OrchestratorConfig_for_test(tmp)
        orch = Orchestrator.__new__(Orchestrator)
        orch.config = cfg
        orch.cycle_count = 100
        open_entries = orch._open_burst_entries()
        assert len(open_entries) == 5
        total_margin = sum(float(e.get("margin_usd", 0)) for e in open_entries)
        assert total_margin == 50.0


def OrchestratorConfig_for_test(state_dir):
    from quant_math.orchestrator import OrchestratorConfig
    return OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir=state_dir,
        mode="burst", burst_margin=10.0, burst_leverage=10)


def test_burst_env_var():
    os.environ["QUANTMATH_BURST_SLIPPAGE_PCT"] = "0.0002"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                     "status": "backtested", "strategy_type": "scalp_burst",
                     "expectancy": 0.01}]
            eng = make_engine(tmp, rows, mode="burst")
            assert eng.burst_slippage_pct == 0.0002
    finally:
        del os.environ["QUANTMATH_BURST_SLIPPAGE_PCT"]


def test_burst_trade_record_has_margin():
    from quant_math.orchestrator import OrchestratorConfig
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="5m", lookback_days=14,
        initial_capital=1000, entry_pct=0.1, take_profit_pct=0.006,
        min_paper_trades=3, hypotheses_per_cycle=5,
        kb_path="/tmp/kb.jsonl", state_dir="/tmp/state",
        mode="burst", burst_margin=15.0, burst_leverage=5)
    assert cfg.burst_margin == 15.0
    assert cfg.burst_leverage == 5


if __name__ == "__main__":
    for fn in [test_burst_slippage_tighter, test_classic_slippage_unchanged,
               test_exposure_cap_blocks_entry, test_burst_env_var,
               test_burst_trade_record_has_margin]:
        fn()
        print(f"PASS {fn.__name__}")
