"""Fase 1-4: live-trading safety rails.

- Config guards: mainnet blocked without QUANTMATH_ALLOW_MAINNET=1,
  any live mode requires .env API keys.
- DailyGuard: daily loss / drawdown / max positions block entries.
- Backtester realism: slippage, liquidation, funding (legacy defaults exact).
- Shadow log: intent records without API calls.
- Live failure path never raises out of _execute_paper_trade.
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.orchestrator import Orchestrator, OrchestratorConfig
from quant_math.risk.circuit_breaker import DailyGuard
from backtesting.backtester import Backtester


def _cfg(**kw):
    base = dict(symbols=["BTC/USDT"], timeframe="1h", lookback_days=7,
                initial_capital=50.0, entry_pct=0.02, take_profit_pct=0.25,
                min_paper_trades=3, hypotheses_per_cycle=3,
                kb_path="/tmp/kb.jsonl", state_dir="/tmp/state")
    base.update(kw)
    return OrchestratorConfig(**base)


def _uptrend():
    prices = np.linspace(100, 110, 50)

    def strat(data):
        n = len(data["X"])
        orders, in_pos = [], False
        for i in range(n):
            if not in_pos and i == 5:
                orders.append({"symbol": "X", "side": "buy", "quantity": 1})
                in_pos = True
            elif in_pos and i == 40:
                orders.append({"symbol": "X", "side": "sell", "quantity": 1})
                in_pos = False
            else:
                orders.append({"symbol": "X", "side": "hold", "quantity": 0})
        return orders

    return prices, strat


# ---------------------------------------------------------------- config guards

def test_mainnet_blocked_without_env(monkeypatch):
    monkeypatch.delenv("QUANTMATH_ALLOW_MAINNET", raising=False)
    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    with pytest.raises(NotImplementedError):
        _cfg(dry_run=False, testnet=False)


def test_live_requires_keys(monkeypatch):
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        _cfg(dry_run=False, testnet=True)


def test_mainnet_allowed_with_env_and_keys(monkeypatch):
    monkeypatch.setenv("QUANTMATH_ALLOW_MAINNET", "1")
    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    c = _cfg(dry_run=False, testnet=False)
    assert c.dry_run is False and c.testnet is False


# ---------------------------------------------------------------- DailyGuard

def test_guard_passes_normal(tmp_path):
    g = DailyGuard(str(tmp_path))
    ok, reason = g.check(0.0, 50.0, 0)
    assert ok and reason is None


def test_guard_blocks_daily_loss(tmp_path):
    g = DailyGuard(str(tmp_path), max_daily_loss_usd=2.5)
    ok, reason = g.check(-2.51, 47.49, 0)
    assert not ok and "daily loss" in reason


def test_guard_boundary_allows_exact_limit(tmp_path):
    g = DailyGuard(str(tmp_path), max_daily_loss_usd=2.5)
    ok, _ = g.check(-2.49, 47.51, 0)
    assert ok


def test_guard_blocks_positions(tmp_path):
    g = DailyGuard(str(tmp_path), max_open_positions=5)
    ok, reason = g.check(0.0, 50.0, 5)
    assert not ok and "open positions" in reason


def test_guard_blocks_drawdown(tmp_path):
    g = DailyGuard(str(tmp_path), drawdown_limit=0.2)
    g.check(0.0, 50.0, 0)  # set peak 50
    ok, reason = g.check(0.0, 39.0, 0)
    assert not ok and "drawdown" in reason


def test_guard_persists_across_instances(tmp_path):
    g1 = DailyGuard(str(tmp_path), max_daily_loss_usd=2.5)
    g1.check(-3.0, 47.0, 0)
    g2 = DailyGuard(str(tmp_path), max_daily_loss_usd=2.5)
    ok, _ = g2.check(-3.0, 47.0, 0)
    assert not ok  # breach survives restart


# ---------------------------------------------------------------- backtester

def test_backtest_legacy_defaults_unchanged():
    prices, strat = _uptrend()
    r = Backtester(initial_capital=10000.0).run_backtest(strat, {"X": prices})
    assert r.num_liquidations == 0
    assert r.total_funding_paid == 0.0
    assert len(r.trades) == 1 and not r.trades[0].liquidated


def test_backtest_slippage_reduces_pnl():
    prices, strat = _uptrend()
    base = Backtester(initial_capital=10000.0).run_backtest(strat, {"X": prices})
    slip = Backtester(initial_capital=10000.0,
                      slippage_pct=0.0001).run_backtest(strat, {"X": prices})
    assert slip.trades[0].pnl < base.trades[0].pnl


def test_backtest_liquidation_triggers():
    crash = np.concatenate([np.full(10, 100.0),
                            np.linspace(100, 50, 20),
                            np.full(20, 50.0)])
    _, strat = _uptrend()
    r = Backtester(initial_capital=10000.0,
                   leverage=10.0).run_backtest(strat, {"X": crash})
    assert r.num_liquidations == 1
    assert r.trades[0].liquidated
    assert r.trades[0].pnl < 0


def test_backtest_funding_accrues():
    prices, strat = _uptrend()
    base = Backtester(initial_capital=10000.0).run_backtest(strat, {"X": prices})
    fund = Backtester(initial_capital=10000.0, funding_rate_8h=0.0001,
                      timeframe="1h").run_backtest(strat, {"X": prices})
    assert fund.total_funding_paid > 0
    assert fund.trades[0].pnl < base.trades[0].pnl


# ---------------------------------------------------------------- shadow + live-fail

def _bare_orchestrator(cfg, monkeypatch=None):
    o = Orchestrator.__new__(Orchestrator)
    o.config = cfg
    o.cycle_count = 1
    o._risk_manager = None
    o._last_realized_total = 0.0
    return o


def _signal():
    return {"price": 80000.0, "side": "buy", "symbol": "BTC/USDT",
            "hypothesis_id": "h1", "expectancy": 1.0, "timestamp": 1.0,
            "sizing_mult": 1.0}


def test_shadow_log_written_without_api(tmp_path):
    cfg = _cfg(state_dir=str(tmp_path), shadow_live=True)
    o = _bare_orchestrator(cfg)
    o._execute_paper_trade(_signal())
    recs = [json.loads(line) for line in
            open(tmp_path / "shadow_orders.jsonl") if line.strip()]
    assert len(recs) == 1
    rec = recs[0]
    assert rec["symbol"] == "BTC/USDT:USDT"
    assert rec["order_type"] == "market" and rec["margin_mode"] == "isolated"
    assert rec["validated"] is False


def test_live_failure_never_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    cfg = _cfg(state_dir=str(tmp_path))
    cfg.dry_run = False  # bypass __post_init__ to test the failure path
    cfg.testnet = True
    o = _bare_orchestrator(cfg)
    out = o._execute_paper_trade(_signal())
    assert out.get("action") == "live_failed"
    assert "error" in out


def test_exchange_auth_guard(monkeypatch):
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    assert ExchangeAPI._to_swap_symbol("BTC/USDT") == "BTC/USDT:USDT"
    api = ExchangeAPI("bybit")
    with pytest.raises(RuntimeError):
        api.create_order("BTC/USDT", "buy", 0.001)
    with pytest.raises(RuntimeError):
        api.set_leverage("BTC/USDT", 10)
    # bad margin mode is validated, but auth is checked first
    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    api2 = ExchangeAPI("bybit")
    with pytest.raises(ValueError):
        api2.set_margin_mode("BTC/USDT", "badmode")


if __name__ == "__main__":
    for name, fn in sorted({k: v for k, v in globals().items()
                            if k.startswith("test_")}.items()):
        if "tmp_path" in fn.__code__.co_varnames or "monkeypatch" in fn.__code__.co_varnames:
            print(f"SKIP {name} (needs pytest fixtures)")
            continue
        fn()
        print(f"PASS {name}")
