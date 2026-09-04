"""
CCXT Exchange Integration
Provides unified interface to multiple cryptocurrency exchanges
"""

import os

import ccxt
from typing import List, Dict, Any, Optional
import time
from datetime import datetime
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Load .env if present (Bybit keys for future live trading)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def api_keys_present() -> bool:
    """True if both BYBIT_API_KEY and BYBIT_API_SECRET are set (env or .env)."""
    return bool(os.getenv("BYBIT_API_KEY") and os.getenv("BYBIT_API_SECRET"))


def is_testnet() -> bool:
    """True unless BYBIT_TESTNET is explicitly false."""
    return os.getenv("BYBIT_TESTNET", "true").lower() not in ("0", "false", "no")


class ExchangeAPI:
    """
    CCXT-based exchange interface
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = False
    ):
        """
        Initialize exchange connection

        Args:
            exchange_id: Exchange identifier (e.g., 'binance', 'bybit')
                or 'synthetic' for offline/simulated mode
            api_key: API key (optional)
            api_secret: API secret (optional)
            sandbox: Use testnet/sandbox environment
        """
        self.exchange = None
        self.exchange_id = exchange_id

        if exchange_id == 'synthetic':
            # Offline / simulated mode: no real exchange connection.
            # Data must be provided via generate_synthetic_data().
            logger.info("Initialized synthetic (offline) exchange mode")
            return

        exchange_class = getattr(ccxt, exchange_id)

        # Auto-load from .env if not passed explicitly (for future live trading)
        if api_key is None:
            api_key = os.getenv("BYBIT_API_KEY") or None
        if api_secret is None:
            api_secret = os.getenv("BYBIT_API_SECRET") or None
        env_testnet = os.getenv("BYBIT_TESTNET", "").lower() in ("1", "true", "yes")
        if env_testnet:
            sandbox = True

        exchange_config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # USDT perpetuals (Futures)
            }
        }

        if api_key:
            exchange_config['apiKey'] = api_key
        if api_secret:
            exchange_config['secret'] = api_secret

        if sandbox:
            exchange_config['sandbox'] = True

        self.exchange = exchange_class(exchange_config)

        logger.info(f"Initialized {exchange_id} exchange connection")

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        since: Optional[int] = None,
        limit: int = 1000
    ) -> List[List]:
        """
        Fetch OHLCV (candlestick) data

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            since: Timestamp in milliseconds
            limit: Number of candles to fetch

        Returns:
            List of [timestamp, open, high, low, close, volume] lists
        """
        # Reintentos con backoff: un timeout transitorio de una pagina no
        # debe abortar el ciclo completo del orchestrator (F1).
        last_err = None
        for attempt in range(1, 4):
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe,
                    since=since,
                    limit=limit
                )
                logger.info(f"Fetched {len(ohlcv)} candles for {symbol}")
                return ohlcv
            except Exception as e:
                last_err = e
                if attempt < 3:
                    wait_s = 2 ** attempt
                    logger.warning(
                        f"OHLCV intento {attempt}/3 fallo ({e}); reintento "
                        f"en {wait_s}s")
                    time.sleep(wait_s)
        logger.error(f"Failed to fetch OHLCV tras 3 intentos: {last_err}")
        raise last_err

    def fetch_order_book(
        self,
        symbol: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Fetch order book data

        Args:
            symbol: Trading pair
            limit: Number of depth levels

        Returns:
            Order book as dictionary
        """
        try:
            order_book = self.exchange.fetch_order_book(symbol, limit)
            return order_book

        except Exception as e:
            logger.error(f"Failed to fetch order book: {e}")
            raise

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker information

        Args:
            symbol: Trading pair

        Returns:
            Ticker data dictionary
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker

        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            raise

    def fetch_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Fetch recent trades

        Args:
            symbol: Trading pair
            limit: Number of recent trades

        Returns:
            List of trade dictionaries
        """
        try:
            trades = self.exchange.fetch_trades(symbol, limit=limit)
            return trades

        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            raise

    def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance

        Returns:
            Balance information dictionary
        """
        try:
            balance = self.exchange.fetch_balance()
            return balance

        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise

    # ------------------------------------------------------------------
    # Live trading (Fase 2-4: Bybit USDT perpetuals). All methods require
    # API keys (.env BYBIT_API_KEY/SECRET) and raise RuntimeError otherwise.
    # Nothing here is called while dry_run=True.
    # ------------------------------------------------------------------

    def _require_auth(self) -> None:
        if self.exchange is None:
            raise RuntimeError("exchange not initialized")
        if not self.exchange.apiKey or not self.exchange.secret:
            raise RuntimeError(
                "live trading needs BYBIT_API_KEY and BYBIT_API_SECRET in .env"
            )

    @staticmethod
    def _to_swap_symbol(symbol: str) -> str:
        """BTC/USDT -> BTC/USDT:USDT for Bybit perpetuals."""
        if ":" not in symbol and symbol.endswith("/USDT"):
            return symbol + ":USDT"
        return symbol

    def set_sandbox_mode(self, enabled: bool = True) -> None:
        """Route to Bybit Testnet (sandbox) or Mainnet."""
        self.exchange.set_sandbox_mode(enabled)
        logger.info("sandbox mode: %s", enabled)

    def set_leverage(self, symbol: str, leverage: int,
                     params: Optional[Dict] = None) -> Any:
        """Set leverage for a perpetual symbol."""
        self._require_auth()
        swap = self._to_swap_symbol(symbol)
        result = self.exchange.set_leverage(int(leverage), swap, params or {})
        logger.info("set leverage %sx on %s", leverage, swap)
        return result

    def set_margin_mode(self, symbol: str, mode: str = "isolated",
                        params: Optional[Dict] = None) -> Any:
        """Set margin mode ('isolated' or 'cross') for a perpetual symbol."""
        self._require_auth()
        if mode not in ("isolated", "cross"):
            raise ValueError("margin mode must be 'isolated' or 'cross'")
        swap = self._to_swap_symbol(symbol)
        result = self.exchange.set_margin_mode(mode, swap, params or {})
        logger.info("set margin mode %s on %s", mode, swap)
        return result

    def create_order(self, symbol: str, side: str, amount: float,
                     price: Optional[float] = None,
                     order_type: str = "market",
                     params: Optional[Dict] = None) -> Dict[str, Any]:
        """Place a live order. Returns the ccxt order dict."""
        self._require_auth()
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        swap = self._to_swap_symbol(symbol)
        amount = float(self.exchange.amount_to_precision(swap, amount))
        if price is not None:
            price = float(self.exchange.price_to_precision(swap, price))
        order = self.exchange.create_order(swap, order_type, side,
                                           amount, price, params or {})
        logger.info("live order %s %s %s @ %s -> id=%s",
                    side, amount, swap, price, order.get("id"))
        return order

    def cancel_order(self, order_id: str, symbol: str) -> Any:
        self._require_auth()
        return self.exchange.cancel_order(order_id, self._to_swap_symbol(symbol))

    def fetch_position(self, symbol: str) -> Dict[str, Any]:
        self._require_auth()
        positions = self.exchange.fetch_positions([self._to_swap_symbol(symbol)])
        return positions[0] if positions else {}

    def get_available_symbols(self) -> List[str]:
        """
        Get list of available trading symbols

        Returns:
            List of trading pairs
        """
        try:
            markets = self.exchange.load_markets()
            symbols = list(markets.keys())
            return symbols

        except Exception as e:
            logger.error(f"Failed to get available symbols: {e}")
            raise

    def ohlcv_to_dataframe(
        self,
        ohlcv: List[List],
        timeframe: str = '1h'
    ) -> pd.DataFrame:
        """
        Convert OHLCV list to DataFrame

        Args:
            ohlcv: OHLCV data
            timeframe: Timeframe label

        Returns:
            DataFrame with OHLCV data
        """
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['timeframe'] = timeframe

        return df

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get trading pair information

        Args:
            symbol: Trading pair

        Returns:
            Symbol info dictionary
        """
        try:
            markets = self.exchange.load_markets()
            return markets.get(symbol)

        except Exception as e:
            logger.error(f"Failed to get symbol info: {e}")
            return None

    def check_rate_limit(self):
        """Check and enforce rate limits"""
        return self.exchange.checkRateLimit()

    def close(self):
        """Close exchange connection"""
        self.exchange.close()
        logger.info("Exchange connection closed")


def get_available_exchanges() -> List[str]:
    """
    Get list of available exchanges

    Returns:
        List of exchange names
    """
    exchanges = ccxt.exchanges
    return exchanges


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example usage
    exchange = ExchangeAPI(
        exchange_id='bybit',
        sandbox=False
    )

    # Fetch OHLCV data
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=100)
    print(f"Fetched {len(ohlcv)} candles")

    # Convert to DataFrame
    df = exchange.ohlcv_to_dataframe(ohlcv)
    print(df.head())

    # Get ticker
    ticker = exchange.fetch_ticker('BTC/USDT')
    print(f"Current price: {ticker['last']}")

    exchange.close()
