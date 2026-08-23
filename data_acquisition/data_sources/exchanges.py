"""
CCXT Exchange Integration
Provides unified interface to multiple cryptocurrency exchanges
"""

import ccxt
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import logging

logger = logging.getLogger(__name__)


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

        exchange_config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
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
            logger.error(f"Failed to fetch OHLCV: {e}")
            raise

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
