"""
Forex market data via Yahoo Finance (no API key required).

Same minimal interface as ExchangeAPI (fetch_ohlcv / fetch_ticker /
ohlcv_to_dataframe) so orchestrator, decision engine and AQDE adapter work
unchanged with market="forex".

Symbols use CCXT style ("EUR/USD") and are mapped to Yahoo ("EURUSD=X").
Notes:
- Yahoo intraday history is limited: 1m ~7d, 5m/15m ~60d. The wizard
  clamps lookback_days per timeframe accordingly.
- "4h" is not a native Yahoo interval: 1h candles are resampled.
- Forex has no central order book: fetch_order_book returns a synthetic
  top-of-book from the last price with a 1bp spread.
- Weekend gaps (24/5 market) are left as-is; DataCleaner ffill handles them.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Yahoo interval per Quant-Math timeframe ("4h" handled via resample)
_YF_INTERVAL = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "1h",   # resampled below
    "1d": "1d",
}

# Max sane lookback_days per timeframe on Yahoo (wizard clamps to these)
MAX_LOOKBACK_DAYS = {
    "1m": 2,
    "5m": 7,
    "15m": 14,
    "1h": 30,
    "4h": 60,
    "1d": 90,
}

# Sensible paper-leverage ladder for FX (spot forex brokers offer up to 500)
FOREX_LEVERAGE_LEVELS = [1, 2, 5, 10, 20, 30, 50, 100, 200, 500]
FOREX_MAX_LEVERAGE = 500

MAJORS = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
          "AUD/USD", "USD/CAD", "NZD/USD"]


def to_yahoo_symbol(symbol: str) -> str:
    """EUR/USD -> EURUSD=X (already-Yahoo symbols pass through)."""
    s = symbol.strip().upper()
    if s.endswith("=X"):
        return s
    return s.replace("/", "") + "=X"


class ForexAPI:
    """Yahoo-backed forex data source with ExchangeAPI-compatible surface."""

    exchange_id = "yahoo"

    def __init__(self, exchange_id: str = "yahoo",
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 sandbox: bool = False):
        # Keys unused (Yahoo needs none); accepted for interface parity.
        self.exchange_id = "yahoo"
        logger.info("Initialized yahoo forex data source")

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h",
                    since: Optional[int] = None,
                    limit: int = 1000) -> List[List]:
        """Return [[ts_ms, o, h, l, c, v], ...] oldest-first."""
        import yfinance as yf

        ysym = to_yahoo_symbol(symbol)
        tf = (timeframe or "1h").strip()
        interval = _YF_INTERVAL.get(tf, "1h")
        resample_4h = (tf == "4h")

        kwargs: Dict[str, Any] = {"interval": interval, "progress": False,
                                  "auto_adjust": True}
        if since is not None:
            kwargs["start"] = datetime.fromtimestamp(since / 1000,
                                                    tz=timezone.utc)
            kwargs["period"] = "max"
        else:
            # Enough history for typical lookbacks without hammering Yahoo
            kwargs["period"] = {"1m": "2d", "5m": "7d", "15m": "14d",
                                "1h": "1mo", "4h": "3mo",
                                "1d": "6mo"}.get(tf, "1mo")
        for attempt in range(3):
            try:
                df = yf.download(ysym, **kwargs)
                break
            except Exception as exc:
                logger.warning("Yahoo %s intento %d/3 fallo (%s)",
                               ysym, attempt + 1, exc)
                time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"Yahoo download failed for {ysym}")

        if df is None or len(df) == 0:
            raise ValueError(f"No data found for {symbol}")

        # Flatten MultiIndex columns (yfinance >= 0.2.40)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df = df.rename(columns=str.lower)

        if resample_4h:
            df = (df.resample("4h", origin="start")
                    .agg({"open": "first", "high": "max",
                          "low": "min", "close": "last",
                          "volume": "sum"}).dropna(subset=["close"]))

        df = df.dropna(subset=["open", "high", "low", "close"])
        if "volume" not in df.columns:
            df["volume"] = 0.0
        df["volume"] = df["volume"].fillna(0.0)
        df = df.tail(limit)

        out = []
        for ts, row in df.iterrows():
            out.append([int(ts.timestamp() * 1000),
                        float(row["open"]), float(row["high"]),
                        float(row["low"]), float(row["close"]),
                        float(row["volume"])])
        logger.info("Fetched %d candles for %s", len(out), symbol)
        return out

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        ohlcv = self.fetch_ohlcv(symbol, timeframe="1m", limit=2)
        last = ohlcv[-1][4] if ohlcv else 0.0
        return {"symbol": symbol, "last": last, "close": last,
                "bid": last, "ask": last * 1.0001}

    def fetch_order_book(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        t = self.fetch_ticker(symbol)
        last = float(t.get("last") or 0.0)
        return {"symbol": symbol,
                "bids": [[last, 1.0]],
                "asks": [[last * 1.0001, 1.0]]}

    def fetch_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        return []

    def fetch_balance(self) -> Dict[str, Any]:
        raise RuntimeError("Yahoo is data-only; no account balance")

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        return {"symbol": symbol, "yahoo": to_yahoo_symbol(symbol),
                "type": "forex"}

    def ohlcv_to_dataframe(self, ohlcv: List[List],
                           timeframe: str = "1h") -> pd.DataFrame:
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["timeframe"] = timeframe
        return df

    def check_rate_limit(self):
        return None

    def close(self):
        logger.info("Yahoo forex source closed (no-op)")


def get_market_api(exchange_id: str, market: Optional[str] = None,
                   **kwargs):
    """Factory: 'yahoo'/market='forex' -> ForexAPI, else ccxt ExchangeAPI."""
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    if (exchange_id or "").lower() == "yahoo" or (market or "").lower() == "forex":
        return ForexAPI(exchange_id="yahoo", **kwargs)
    return ExchangeAPI(exchange_id=exchange_id or "bybit", **kwargs)
