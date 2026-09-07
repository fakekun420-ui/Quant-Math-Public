"""Forex (Yahoo) + named background sessions.

Yahoo network is mocked: CI must not depend on external data.
A live-Yahoo smoke test can be run manually (see bottom).
"""
import os
import sys
import types

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_acquisition.data_sources.forex import (
    ForexAPI, MAJORS, MAX_LOOKBACK_DAYS, FOREX_MAX_LEVERAGE,
    get_market_api, to_yahoo_symbol,
)
from quant_math.cli.main import (
    RuntimeState, _clamp_lookback, _sanitize_session, _session_mode,
    _session_paths,
)
from quant_math.orchestrator import OrchestratorConfig


def _fake_yahoo(monkeypatch, periods=50):
    idx = pd.date_range("2026-01-01", periods=periods, freq="h", tz="UTC")
    df = pd.DataFrame({"open": 1.10, "high": 1.12, "low": 1.09,
                       "close": 1.11, "volume": 0}, index=idx)
    fake = types.SimpleNamespace(download=lambda *a, **k: df)
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    return df


# ---------------------------------------------------------------- symbols

def test_to_yahoo_symbol():
    assert to_yahoo_symbol("EUR/USD") == "EURUSD=X"
    assert to_yahoo_symbol("EURUSD=X") == "EURUSD=X"
    assert len(MAJORS) >= 7
    assert FOREX_MAX_LEVERAGE == 500
    assert MAX_LOOKBACK_DAYS["1m"] == 2


def test_factory_routes_by_market():
    assert type(get_market_api("yahoo")).__name__ == "ForexAPI"
    assert type(get_market_api("bybit", market="forex")).__name__ == "ForexAPI"
    assert type(get_market_api("bybit")).__name__ == "ExchangeAPI"


def test_forex_fetch_ohlcv_shape(monkeypatch):
    _fake_yahoo(monkeypatch)
    rows = ForexAPI().fetch_ohlcv("EUR/USD", timeframe="1h", limit=5)
    assert len(rows) == 5
    ts, o, h, l, c, v = rows[0]
    assert ts > 0 and o == 1.10 and c == 1.11


def test_forex_resample_4h(monkeypatch):
    _fake_yahoo(monkeypatch, periods=24)
    rows = ForexAPI().fetch_ohlcv("EUR/USD", timeframe="4h", limit=10)
    assert 1 <= len(rows) <= 6  # 24x1h -> 6x4h


def test_forex_ticker_and_book(monkeypatch):
    _fake_yahoo(monkeypatch)
    api = ForexAPI()
    t = api.fetch_ticker("GBP/USD")
    assert t["last"] == 1.11
    ob = api.fetch_order_book("GBP/USD")
    assert ob["asks"][0][0] > ob["bids"][0][0]


# ---------------------------------------------------------------- sessions

def test_sanitize_session():
    assert _sanitize_session("Classic BTC/USDT!") == "classic-btc-usdt"
    assert _sanitize_session("burst-EURUSD") == "burst-eurusd"
    assert _sanitize_session("") == "session"


def test_session_paths_legacy():
    sd, kb, log = _session_paths("classic")
    assert sd.endswith("runtime/state") and kb.endswith("hypotheses.jsonl")
    assert log.endswith("quant_math.log")
    sd, kb, log = _session_paths("burst")
    assert sd.endswith("runtime/state_burst")
    assert kb.endswith("hypotheses_burst.jsonl")


def test_session_paths_isolated():
    sd, kb, log = _session_paths("classic-eth")
    assert sd.endswith("state_classic-eth")
    assert "hypotheses_classic-eth" in kb
    assert log.endswith("quant_math_classic-eth.log")


def test_runtime_state_session_keys():
    rs = RuntimeState()
    assert rs._pid_file("classic").endswith("runtime/state/orchestrator.pid")
    assert rs._pid_file("burst").endswith("runtime/state_burst/orchestrator.pid")
    assert rs._pid_file("classic-eth").endswith(
        "state_classic-eth/orchestrator.pid")
    assert _session_mode(rs, "burst") == "burst"
    assert _session_mode(rs, "classic-eth") == "classic"


def test_clamp_lookback():
    assert _clamp_lookback("crypto", "1m", 30) == 30
    assert _clamp_lookback("forex", "1m", 30) == 2
    assert _clamp_lookback("forex", "1h", 14) == 14


def test_config_market_validation():
    c = OrchestratorConfig(symbols=["EUR/USD"], timeframe="15m",
                           lookback_days=14, initial_capital=50.0,
                           entry_pct=0.02, take_profit_pct=0.005,
                           min_paper_trades=3, hypotheses_per_cycle=3,
                           kb_path="/tmp/k.jsonl", state_dir="/tmp/s",
                           market="forex", exchange_id="yahoo")
    assert c.market == "forex"
    try:
        OrchestratorConfig(symbols=["X"], timeframe="1h", lookback_days=7,
                           initial_capital=50.0, entry_pct=0.02,
                           take_profit_pct=0.25, min_paper_trades=3,
                           hypotheses_per_cycle=3, kb_path="/tmp/k.jsonl",
                           state_dir="/tmp/s", market="stocks")
        raise AssertionError("should have raised")
    except ValueError:
        pass


if __name__ == "__main__":
    print("run via pytest (needs fixtures for some tests)")
