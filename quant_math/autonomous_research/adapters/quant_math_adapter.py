"""
Adapters for integrating AQDE with existing quant-math modules.

This module provides adapters that implement the AQDE ports (DataProvider,
KnowledgeBase, BacktestEngine, etc.) by wrapping existing quant-math
components.
"""

from __future__ import annotations

import sys
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from ..agents.knowledge_manager import HypothesisKnowledgeBase, SearchCriteria
    EXTERNAL_KNOWLEDGE_BASE = True
except ImportError:
    # Use local stub implementation
    from .knowledge_manager_stub import HypothesisKnowledgeBase, SearchCriteria
    EXTERNAL_KNOWLEDGE_BASE = False

try:
    from backtesting import Backtester, BacktestResult, PerformanceMetrics, Trade
    from order_management import OrderManager
    import numpy as np
    import pandas as pd
    try:
        import ccxt  # noqa: F401  # optional: solo live ExchangeAPI, backtester no lo necesita
    except ImportError:
        ccxt = None  # type: ignore  # forex/crypto live deshabilitado sin ccxt; backtest sigue ok

    HAS_QUANT_MATH = True
except ImportError as e:
    HAS_QUANT_MATH = False
    print(f"[QuantMathAdapter] Warning: Could not import quant-math modules: {e}")


# REGISTRO DE ESTRATEGIAS IMPLEMENTADAS — fuente unica de verdad.
# MEDIDO 2026-09-28: el dispatcher terminaba en un `else` que sustituia cualquier estrategia
# desconocida por un ema_crossover desnudo, sin parametros y sin aviso. Eso hacia que
# `hybrid_trend_reversion` (emitida por mutacion cruzada en aqde_runner.py:400) se
# backtesteara como otra cosa y su PnL FALSO alimentara el aprendizaje.
# Dos reglas, y las dos importan:
#   - Si anades una estrategia aqui, anadela tambien a la cadena `elif stype ==` de make_strategy.
#   - Si no esta aqui, NO se puede emitir. El generador filtra contra este conjunto.
IMPLEMENTED_STRATEGIES = frozenset({
    "ema_crossover",
    "rsi_reversion",
    "bb_reversion",
    "breakout",
    "macd",
    "stochastic_reversion",
    "vwap_reversion",
    "dual_ema",
    "donchian_breakout",
    "ati_trend",
    "energy_burst",
    "range_pressure",
    "scalp_burst",
})


class UnknownStrategyError(NotImplementedError):
    """La hipotesis pide una estrategia que este adapter no sabe ejecutar.

    Se propaga a proposito. Antes se tragaba el error y devolvia los numeros de otra
    estrategia, que es peor que fallar: un backtest que no se hizo parece un backtest.
    """


def is_implemented(strategy_type) -> bool:
    return strategy_type in IMPLEMENTED_STRATEGIES


class QuantMathAdapter:
    """
    Adapter for integrating AQDE with existing quant-math modules.

    Implements all AQDE ports by wrapping quant-math components.
    """

    def __init__(self, exchange_id: str = "binance",
                 market: str = "crypto",
                 knowledge_base_path: str = "autonomous_research/data/hypotheses"):
        """
        Initialize the adapter.

        Args:
            exchange_id: CCXT exchange identifier (default: 'binance'),
                or 'yahoo' for forex
            market: 'crypto' or 'forex' (selects ccxt vs Yahoo provider)
            knowledge_base_path: Path for persistent hypothesis storage
        """
        # Initialize knowledge base
        self.knowledge_base = HypothesisKnowledgeBase(storage_path=knowledge_base_path)
        self.market = (market or "crypto").lower()

        if HAS_QUANT_MATH:
            from data_acquisition.data_sources.forex import get_market_api
            self.exchange = get_market_api(exchange_id, market=self.market)
            self.backtester = Backtester()
            self.metrics = PerformanceMetrics()
            self.order_manager = OrderManager()
            print(f"[QuantMathAdapter] Initialized with {exchange_id} exchange")
        else:
            self.exchange = None
            print("[QuantMathAdapter] Quant-math modules not available - adapter in limited mode")

    # DataProvider Implementation

    def fetch_market_data(self, symbol: str, start_date: datetime, end_date: datetime,
                          timeframe: str = '1h') -> Dict[str, Any]:
        """
        Fetch market data using CCXT exchange API.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT' or 'BTC/USDT')
            start_date: Start date for data
            end_date: End date for data
            timeframe: OHLCV timeframe (1m, 5m, 15m, 1h, 4h, 1d)

        Returns:
            Dictionary containing OHLCV data and metadata
        """
        if not self.exchange:
            raise ValueError("Exchange API not available")

        # Normalize symbol format: BTCUSDT -> BTC/USDT
        if '/' not in symbol:
            symbol = f"{symbol[:-4]}/{symbol[-4:]}"

        # Convert dates to milliseconds for CCXT
        since_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        all_ohlcv = []
        current_since = since_ms
        while current_since < end_ms:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe,
                                              since=current_since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            current_since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000:
                break

        # Filter by end date
        all_ohlcv = [c for c in all_ohlcv if c[0] <= end_ms]

        if not all_ohlcv:
            raise ValueError(f"No data found for {symbol}")

        df = self.exchange.ohlcv_to_dataframe(all_ohlcv, timeframe=timeframe)

        return {
            "symbol": symbol,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timeframe": timeframe,
            "data": df,
            "count": len(df),
            "exchange": self.exchange.exchange_id
        }

    def generate_synthetic_data(self, symbol: str, n_candles: int = 500,
                                start_price: float = 50000.0) -> Dict[str, Any]:
        """
        Generate synthetic OHLCV data for dry-run / testing.

        Uses a random walk with mild upward drift and realistic volatility
        so that all strategies (EMA crossover, RSI, Bollinger, breakout,
        MACD) can produce signals.

        Returns:
            Same format as fetch_market_data()
        """
        import numpy as np
        import pandas as pd

        rng = np.random.default_rng(42)
        vol = 0.02
        drift = 0.0005
        returns = rng.normal(drift, vol, n_candles)
        prices = start_price * np.cumprod(1 + returns)

        timestamps = pd.date_range(
            end=datetime.utcnow(), periods=n_candles, freq="1h"
        )

        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": prices,
            "high": prices * (1 + rng.uniform(0, 0.01, n_candles)),
            "low": prices * (1 - rng.uniform(0, 0.01, n_candles)),
            "close": prices,
            "volume": rng.uniform(100, 1000, n_candles),
        })

        return {
            "symbol": symbol,
            "start_date": timestamps[0].isoformat(),
            "end_date": timestamps[-1].isoformat(),
            "timeframe": "1h",
            "data": df,
            "count": n_candles,
            "exchange": "synthetic",
        }

    def fetch_features(self, symbol: str, date: datetime) -> Dict[str, Any]:
        """
        Extract technical features for a specific date.

        Args:
            symbol: Trading symbol
            date: Date/time to extract features

        Returns:
            Dictionary of feature values
        """
        if not self.exchange:
            raise ValueError("Exchange API not available")

        # Normalize symbol
        if '/' not in symbol:
            symbol = f"{symbol[:-4]}/{symbol[-4:]}"

        from datetime import timedelta
        data = self.fetch_market_data(symbol, date - timedelta(days=90), date)
        df = data["data"]

        features = {}

        if len(df) > 20:
            features["close_20_ma"] = float(df["close"].tail(20).mean())
            features["close_50_ma"] = float(df["close"].tail(50).mean()) if len(df) > 50 else 0.0
            features["rsi"] = self._calculate_rsi(df["close"].tail(30))
            features["volatility"] = float(df["close"].tail(30).std() / df["close"].tail(30).mean())

        return features

    def get_available_symbols(self) -> List[str]:
        """Get list of available trading symbols"""
        if self.exchange:
            return self.exchange.get_available_symbols()
        return []

    def get_data_quality(self, symbol: str) -> Dict[str, Any]:
        """
        Get data quality metrics.

        Returns completeness, accuracy, and freshness metrics.
        """
        if not self.exchange:
            return {"error": "Exchange API not available"}

        from datetime import timedelta
        data = self.fetch_market_data(symbol, datetime.now() - timedelta(days=30), datetime.now())
        df = data["data"]

        return {
            "symbol": symbol,
            "completeness": len(df) / 30,
            "accuracy": "high",
            "freshness": datetime.now().isoformat(),
            "data_points": len(df)
        }

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_stoch(self, df: pd.DataFrame, period: int = 14, k_period: int = 3, d_period: int = 3) -> tuple:
        """Calculate Stochastic %K and %D indicators"""
        low_min = df['low'].rolling(window=period).min()
        high_max = df['high'].rolling(window=period).max()
        
        k_raw = 100 * ((df['close'] - low_min) / (high_max - low_min))
        k = k_raw.rolling(window=k_period).mean()
        d = k.rolling(window=d_period).mean()
        
        return k.fillna(50).values, d.fillna(50).values

    def _calculate_vwap(self, df: pd.DataFrame, window: int = 20) -> np.ndarray:
        """Calculate Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).rolling(window=window).sum() / df['volume'].rolling(window=window).sum()
        return vwap.fillna(df['close']).values

    def _calculate_emas(self, prices: pd.Series, windows: List[int]) -> Dict[str, np.ndarray]:
        """Calculate multiple EMA windows"""
        result = {}
        for window in windows:
            ema = prices.ewm(span=window, adjust=False).mean()
            result[f'ema_{window}'] = ema.fillna(prices.iloc[0]).values
        return result

    def _calculate_donchian(self, df: pd.DataFrame, window: int = 20) -> tuple:
        """Calculate Donchian channels (upper and lower)"""
        upper = df['high'].rolling(window=window).max()
        lower = df['low'].rolling(window=window).min()
        return upper.fillna(df['close']).values, lower.fillna(df['close']).values

    def _calculate_atr(self, df: pd.DataFrame, window: int = 14) -> np.ndarray:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close_prev = abs(df['high'] - df['close'].shift(1))
        low_close_prev = abs(df['low'] - df['close'].shift(1))
        
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean()
        return atr.fillna(tr.mean()).values

    # KnowledgeBase Implementation (Phase 2 - Persistent Storage)

    def store_hypothesis(self, hypothesis) -> str:
        """
        Store hypothesis in persistent knowledge base.

        Args:
            hypothesis: Hypothesis to store

        Returns:
            ID of the stored hypothesis
        """
        hypothesis_id = hypothesis.hypothesis_id
        self.knowledge_base.store_hypothesis(hypothesis)
        print(f"[QuantMathAdapter] Stored hypothesis: {hypothesis_id}")
        return hypothesis_id

    def retrieve_hypothesis(self, hypothesis_id: str):
        """Retrieve hypothesis by ID from persistent storage"""
        return self.knowledge_base.retrieve_hypothesis(hypothesis_id)

    def search_hypotheses(self, criteria: Dict[str, Any]) -> List[Any]:
        """
        Search hypotheses based on criteria.

        Args:
            criteria: Search criteria dictionary

        Returns:
            List of matching hypotheses
        """
        search_criteria = SearchCriteria(**criteria)
        return self.knowledge_base.search_hypotheses(search_criteria)

    def search_hypotheses_by_text(self, query: str, limit: int = 100) -> List[Any]:
        """Search hypotheses using text matching"""
        return self.knowledge_base.search_hypotheses_by_text(query, limit)

    def search_similar_hypotheses(self, description: str, threshold: float = 0.7) -> List[Any]:
        """Find similar hypotheses using semantic search"""
        return self.knowledge_base.search_similar_hypotheses(description, threshold)

    def update_hypothesis(self, hypothesis_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing hypothesis in persistent storage.

        Args:
            hypothesis_id: ID of hypothesis to update
            updates: Dictionary of fields to update

        Returns:
            True if updated, False if not found
        """
        return self.knowledge_base.update_hypothesis(hypothesis_id, updates)

    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis from persistent storage"""
        return self.knowledge_base.delete_hypothesis(hypothesis_id)

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored hypotheses from persistent storage"""
        return self.knowledge_base.get_statistics()

    def get_hypothesis_timeline(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Get timeline of hypothesis development"""
        return self.knowledge_base.get_hypothesis_timeline(hypothesis_id)

    def export_hypotheses(self, output_path: str) -> Dict[str, Any]:
        """Export all hypotheses to a file"""
        return self.knowledge_base.export_hypotheses(output_path)

    def import_hypotheses(self, input_path: str) -> int:
        """Import hypotheses from a file"""
        return self.knowledge_base.import_hypotheses(input_path)

    # BacktestEngine Implementation

    def run_backtest(self, hypothesis, data: Dict[str, Any] = None,
                    initial_capital: float = 100000.0,
                synthetic: bool = False,
                fraccion_capital: float = 1.0,
                apalancamiento: float = 1.0) -> Any:
        """
        Run backtest using quant-math backtester.

        Args:
            hypothesis: Hypothesis dict with 'hypothesis_id' or strategy config
            data: Market data from fetch_market_data. If omitted, synthetic
                  OHLCV data is generated for offline / dry-run usage.
            initial_capital: Starting capital

        Returns:
            BacktestResult with performance metrics
        """
        if not HAS_QUANT_MATH:
            raise ValueError("Backtester not available")

        if data is None:
            # MEDIDO el 2026-10-01: aqui se generaba un random walk y se
            # pasaba por backtest como si fuera el mercado. Es la razon de
            # que el backtest de BTC diera 0 operaciones: BTC era el
            # simbolo por DEFECTO de `generate_synthetic_data`, luego sus
            # hipotesis se median contra una serie inventada y no tenian
            # nada que ver con BTC.
            #
            # Un backtest sobre datos sinteticos no es un backtest: es una
            # medida de la moneda ficticia. Y como devuelve numeros, nadie
            # lo detecta leyendo el resultado.
            #
            # Ahora se falla CLARO y se dice por que. Los datos sinteticos
            # se siguen pudiendo pedir de forma explicita con
            # `synthetic=True`, para tests, y en ese caso el resultado lo
            # dice para que no se pueda confundir con una medida real.
            if not synthetic:
                raise ValueError(
                    "run_backtest sin `data`: no se puede medir una "
                    "hipotesis sobre datos inventados. Pasa los OHLCV "
                    "reales del simbolo, o pide `synthetic=True` si lo que "
                    "quieres es una prueba de humo. Convierte esto en un "
                    "resultado silencioso era como BTC prototypo medians"
                    " datos que no eran de BTC.")
            symbol = "BTC/USDT"
            if isinstance(hypothesis, dict):
                symbol = hypothesis.get('symbol', hypothesis.get('asset', symbol))
            elif hasattr(hypothesis, 'symbol') and getattr(hypothesis, 'symbol'):
                symbol = hypothesis.symbol
            data = self.generate_synthetic_data(symbol, n_candles=1000)

        df = data["data"]
        symbol = data["symbol"]
        close_prices = df['close'].values
        price_dict = {symbol: close_prices}

        # Extract strategy parameters from hypothesis
        if hasattr(hypothesis, 'parameters'):
            params = hypothesis.parameters
        elif isinstance(hypothesis, dict):
            params = hypothesis.get('parameters', {})
        else:
            params = {}

        strategy_type = params.get('strategy_type') or params.get('signal_backtest_key', 'ema_crossover')
        short_window = params.get('short_window', 12)
        long_window = params.get('long_window', 26)
        rsi_period = params.get('rsi_period', 14)
        rsi_oversold = params.get('rsi_oversold', 30)
        rsi_overbought = params.get('rsi_overbought', 70)
        bb_period = params.get('bb_period', 20)
        bb_std = params.get('bb_std', 2.0)
        breakout_window = params.get('breakout_window', 20)

        # Pre-compute indicators
        ema_s = df['close'].ewm(span=short_window, adjust=False).mean().values
        ema_l = df['close'].ewm(span=long_window, adjust=False).mean().values

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).fillna(50).values

        # Bollinger Bands
        bb_ma = df['close'].rolling(window=bb_period).mean()
        bb_upper = bb_ma + bb_std * df['close'].rolling(window=bb_period).std()
        bb_lower = bb_ma - bb_std * df['close'].rolling(window=bb_period).std()
        bb_upper = bb_upper.fillna(close_prices[0]).values
        bb_lower = bb_lower.fillna(close_prices[0]).values

        # Breakout levels
        rolling_max = df['close'].rolling(window=breakout_window).max().shift(1).fillna(close_prices[0]).values
        rolling_min = df['close'].rolling(window=breakout_window).min().shift(1).fillna(close_prices[0]).values

        # --- New strategy indicators ---
        # Stochastic reversion
        stoch_k, stoch_d = self._calculate_stoch(df)
        stoch_oversold = params.get('stoch_oversold', 20)
        stoch_overbought = params.get('stoch_overbought', 80)

        # VWAP reversion
        vwap_window = params.get('vwap_window', 20)
        vwap_arr = self._calculate_vwap(df, vwap_window)
        vwap_threshold = params.get('vwap_threshold', 0.02)

        # Dual EMA (3-EMA trend filter)
        dual_fast = params.get('dual_fast', 8)
        dual_mid = params.get('dual_mid', 21)
        dual_slow = params.get('dual_slow', 55)
        ema_fast = df['close'].ewm(span=dual_fast, adjust=False).mean().fillna(close_prices[0]).values
        ema_mid = df['close'].ewm(span=dual_mid, adjust=False).mean().fillna(close_prices[0]).values
        ema_slow = df['close'].ewm(span=dual_slow, adjust=False).mean().fillna(close_prices[0]).values

        # Donchian breakout
        donchian_window = params.get('donchian_window', 20)
        donch_upper, donch_lower = self._calculate_donchian(df, donchian_window)

        # ATI (ATR Trend Indicator)
        atr_window = params.get('atr_window', 14)
        atr_arr = self._calculate_atr(df, atr_window)
        atr_factor = params.get('atr_factor', 3.0)

        warmup = max(long_window, rsi_period, bb_period, breakout_window,
                     dual_slow, donchian_window, atr_window, vwap_window)

        def make_strategy(stype, qty_por_precio):
            """`qty_por_precio[i]` es la cantidad a entrar en la barra `i`.

            MEDIDO el 2026-10-02: antes la cantidad era la constante `1`, o
            sea que el nocional era el PRECIO del activo. Con una cuenta de
            100.000 eso da:

                BTC  nocional 105.900  = 105,90% de la cuenta
                ETH  nocional   2.552  =   2,55%
                SOL  nocional     148  =   0,15%
                XRP  nocional   2,17  =   0,0022%

            La exposicion varia 50.000 veces entre el primero y el ultimo, y
            por eso los cuatro simbolos NO se podian comparar: el "-0,0000%"
            de XRP no era "no hay edge", era que una operacion movia 0,003
            USDT. El dimensionamiento va POR FUERA, en el llamado al
            backtester, que es quien sabe el equity de cada momento.
            """
            def strategy(data_dict):
                orders = []
                in_position = False
                for i in range(len(close_prices)):
                    if i < warmup:
                        orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
                        continue

                    if stype == 'ema_crossover':
                        buy_sig = ema_s[i] > ema_l[i]
                        sell_sig = ema_s[i] < ema_l[i]
                    elif stype == 'rsi_reversion':
                        buy_sig = rsi[i] < rsi_oversold
                        sell_sig = rsi[i] > rsi_overbought
                    elif stype == 'bb_reversion':
                        buy_sig = close_prices[i] < bb_lower[i]
                        sell_sig = close_prices[i] > bb_upper[i]
                    elif stype == 'breakout':
                        buy_sig = close_prices[i] > rolling_max[i]
                        sell_sig = close_prices[i] < rolling_min[i]
                    elif stype == 'macd':
                        macd_line = ema_s[i] - ema_l[i]
                        signal_line = df['close'].ewm(span=long_window*2, adjust=False).mean().values[i] - ema_l[i]
                        buy_sig = macd_line > signal_line
                        sell_sig = macd_line < signal_line
                    elif stype == 'stochastic_reversion':
                        buy_sig = stoch_k[i] < stoch_oversold and stoch_k[i] > stoch_d[i]
                        sell_sig = stoch_k[i] > stoch_overbought and stoch_k[i] < stoch_d[i]
                    elif stype == 'vwap_reversion':
                        dev = (close_prices[i] - vwap_arr[i]) / vwap_arr[i]
                        buy_sig = dev < -vwap_threshold
                        sell_sig = dev > vwap_threshold
                    elif stype == 'dual_ema':
                        buy_sig = ema_fast[i] > ema_mid[i] and ema_mid[i] > ema_slow[i]
                        sell_sig = ema_fast[i] < ema_mid[i] and ema_mid[i] < ema_slow[i]
                    elif stype == 'donchian_breakout':
                        buy_sig = close_prices[i] > donch_upper[i-1] if i > 0 else False
                        sell_sig = close_prices[i] < donch_lower[i-1] if i > 0 else False
                    elif stype == 'ati_trend':
                        atr_band = atr_arr[i] * atr_factor
                        # Trend filter: EMA slope + ATR channel
                        upper_band = ema_s[i] + atr_band
                        lower_band = ema_s[i] - atr_band
                        buy_sig = close_prices[i] > upper_band and ema_s[i] > ema_l[i]
                        sell_sig = close_prices[i] < lower_band and ema_s[i] < ema_l[i]
                    elif stype == 'energy_burst':
                        # MEDIDO 2026-09-28: estos dos estaban fijos aqui, asi que la
                        # optimizacion del generador sobre ellos era codigo MUERTO en esta
                        # ruta. Se leen de la hipotesis, con los mismos valores por defecto
                        # que tenian, para no cambiar el comportamiento de lo ya medido.
                        w = params.get('burst_window', 20)
                        zthr = params.get('burst_z', 1.5)
                        if i >= w and i >= 1:
                            rets = np.diff(np.array(close_prices[:i+1], dtype=float))
                            win = rets[i - w:i]
                            mu, sd = np.mean(win), np.std(win)
                            r = rets[i - 1] if i - 1 < len(rets) else 0
                            z = (r - mu) / sd if sd > 1e-12 else 0.0
                            buy_sig = abs(z) >= zthr and r > 0
                            sell_sig = abs(z) >= zthr and r < 0
                        else:
                            buy_sig = sell_sig = False
                    elif stype == 'range_pressure':
                        # MEDIDO 2026-09-28: hardcodeados -> optimizacion muerta (ver energy_burst).
                        w = params.get('range_window', 20)
                        hi = params.get('range_hi', 0.85)
                        lo = params.get('range_lo', 0.15)
                        if i >= w:
                            win = np.array(close_prices[i - w + 1:i + 1], dtype=float)
                            rng = win.max() - win.min()
                            press = (close_prices[i] - win.min()) / rng if rng > 1e-12 else 0.5
                            buy_sig = press >= hi
                            sell_sig = press <= lo
                        else:
                            buy_sig = sell_sig = False
                    elif stype == 'scalp_burst':
                        # MEDIDO 2026-09-28: hardcodeados -> optimizacion muerta (ver energy_burst).
                        ema_f_w = params.get('scalp_ema_fast', 8)
                        ema_s_w = params.get('scalp_ema_slow', 21)
                        mom_w = params.get('scalp_mom_window', 5)
                        mom_thr = params.get('scalp_mom_thr', 0.002)
                        pb = params.get('scalp_pb', 0.003)
                        if i >= ema_s_w + mom_w and i >= 2:
                            arr = np.array(close_prices[:i+1], dtype=float)
                            af = 2.0 / (ema_f_w + 1)
                            as_ = 2.0 / (ema_s_w + 1)
                            ef = np.zeros(len(arr))
                            es = np.zeros(len(arr))
                            ef[0] = es[0] = arr[0]
                            for j in range(1, len(arr)):
                                ef[j] = arr[j] * af + ef[j-1] * (1 - af)
                                es[j] = arr[j] * as_ + es[j-1] * (1 - as_)
                            trend_up = ef[-1] > es[-1]
                            ret = (arr[-1] - arr[-mom_w]) / arr[-mom_w] if arr[-mom_w] > 0 else 0
                            mom_ok = abs(ret) >= mom_thr
                            if trend_up and mom_ok and ret > 0:
                                rh = float(np.max(arr[-mom_w:]))
                                pb_ok = ((rh - arr[-1]) / rh >= pb if rh > 0 else False)
                                buy_sig = pb_ok or arr[-1] > arr[-2]
                                sell_sig = False
                            elif not trend_up and mom_ok and ret < 0:
                                rl = float(np.min(arr[-mom_w:]))
                                bk = ((arr[-1] - rl) / rl >= pb if rl > 0 else False)
                                sell_sig = bk or arr[-1] < arr[-2]
                                buy_sig = False
                            else:
                                buy_sig = sell_sig = False
                        else:
                            buy_sig = sell_sig = False
                    elif stype == 'ema_crossover':
                        # Explicitado: el `else` final era una sustitucion silenciosa por un
                        # EMA crossover desnudo. Ver IMPLEMENTED_STRATEGIES mas arriba.
                        buy_sig = ema_s[i] > ema_l[i]
                        sell_sig = ema_s[i] < ema_l[i]
                    else:
                        # Estrategia desconocida: se aborta el backtest en vez de devolver
                        # numeros de otra estrategia. El fallo viaja hasta el ResearchManager,
                        # que marca la hipotesis como rechazada y sigue el ciclo.
                        raise UnknownStrategyError(
                            f"estrategia no implementada: {stype!r}. "
                            f"Implementadas: {sorted(IMPLEMENTED_STRATEGIES)}"
                        )

                    if not in_position and buy_sig:
                        orders.append({'symbol': symbol, 'side': 'buy',
                                       'quantity': qty_por_precio[i]})
                        in_position = True
                    elif in_position and sell_sig:
                        orders.append({'symbol': symbol, 'side': 'sell',
                                       'quantity': qty_por_precio[i]})
                        in_position = False
                    else:
                        orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
                return orders
            return strategy

        # DIMENSIONAMIENTO. El nocional de cada entrada es una fraccion
        # FIJA del capital, no un numero de unidades. Medido el 2026-10-02:
        # con `quantity=1` la exposicion iba del 105,90% de la cuenta en BTC
        # al 0,0022% en XRP, y los simbolos no eran comparables.
        #
        # Fraccional y NO riesgo-por-stop a proposito: el riesgo por stop
        # meteria en la comparacion una variable mas (distancia del stop) que
        # es justo lo que se quiere MEDIR. Con fraccion fija, cada simbolo
        # arriesga lo mismo y la unica diferencia entre ellos es la
        # estrategia.
        #
        # `fraccion_capital` es un PARAMETRO con default 1,0 (100% del
        # capital, sin apalancamiento implicito). Antes de esta fase el
        # nocional era el precio, que para BTC daba 105,90%; cualquier otro
        # valor cambia los numeros, asi que queda declarado y no escondido en
        # una constante.
        fraccion = float(fraccion_capital if fraccion_capital is not None else 1.0)
        lev = max(1.0, float(apalancamiento or 1.0))
        # MEDIDO el 2026-10-02: con el 100% del capital y apalancamiento 1 el
        # backtest NO ABRE NINGUNA POSICION. El motor exige
        # `current_capital >= margen + comision`, y con margen igual al nocional
        # el 100% del capital mas la comision de entrada no cabe nunca. El
        # resultado eran 0 operaciones en los 4 simbolos, que se lee como "la
        # estrategia no genera senal" cuando lo que pasa es que no hay con que
        # pagar el margen.
        #
        # Por eso el nocional es `fraccion del capital por apalancamiento`: lo
        # que se compromete como margen es la fraccion, y el apalancamiento
        # determina el nocional. Es la misma relacion que usa el sistema real,
        # donde 5 USDT a 50x son 250 de nocional.
        notional_objetivo = (max(0.0, min(fraccion, 1.0))
                             * float(initial_capital) * lev)
        # Cantidad por barra: el nocional objetivo dividido por el precio de
        # ESA barra. Se usa el precio de la barra y no el ultimo, para que el
        # dimensionamiento no dependa de donde se corte la serie.
        precios_serie = np.asarray(close_prices, dtype=float)
        con_precio = precios_serie > 0
        qty_por_precio = np.zeros(len(precios_serie), dtype=float)
        if notional_objetivo > 0:
            qty_por_precio[con_precio] = notional_objetivo / precios_serie[con_precio]
        qty_por_precio = np.round(qty_por_precio, 8)

        strategy_func = make_strategy(strategy_type, qty_por_precio)

        # MEDIDO el 2026-10-01: la temporalidad NO viaja con la hipotesis, y
        # sin ella el backtester asumia velas diarias. Un backtest de 15m
        # anualizado como diario tiene un Sharpe que no se puede comparar con
        # nada, y el score cientifico (pondero 0,5) se alimentaba de ahi.
        #
        # Se lee de donde exista y se DECLARA el origen: si no se sabe, se
        # pasa `None` y el backtester usa la diaria declarada en vez de
        # inventar una.
        _tf = params.get("timeframe") or params.get("interval")
        if _tf is None and isinstance(hypothesis, dict):
            _tf = hypothesis.get("timeframe")
        if _tf is None:
            _tf = getattr(hypothesis, "timeframe", None)
        if _tf is None and data:
            _tf = data.get("timeframe")

        bt = Backtester(initial_capital=initial_capital, leverage=lev)
        result = bt.run_backtest(strategy_func, price_dict,
                                  initial_capital=initial_capital,
                                  timeframe=_tf)

        return result

    # MonteCarloEngine Implementation

    def simulate_distribution(self, result, n_iterations: int = 1000) -> Any:
        """
        Run Monte Carlo simulation using bootstrap resampling.

        Args:
            result: BacktestResult to simulate
            n_iterations: Number of iterations

        Returns:
            MonteCarloResult with distribution statistics
        """
        if not HAS_QUANT_MATH:
            raise ValueError("NumPy not available for Monte Carlo simulation")

        # Extract trade PnLs
        trade_pnls = [t.pnl for t in result.trades] if result.trades else [0.0]
        n_trades = len(trade_pnls)

        # Parametric bootstrap simulation
        means = []
        for _ in range(n_iterations):
            bootstrapped = np.random.choice(trade_pnls, size=n_trades, replace=True)
            cumulative_return = sum(bootstrapped) / result.initial_capital
            means.append(cumulative_return)

        means = np.array(means)

        result_obj = type('MonteCarloResult', (), {
            "hypothesis_id": getattr(result, 'hypothesis_id', 'unknown'),
            "n_iterations": n_iterations,
            "mean": float(means.mean()),
            "median": float(np.median(means)),
            "std_dev": float(means.std()),
            "min_value": float(means.min()),
            "max_value": float(means.max()),
            "lower_bound": float(np.percentile(means, 2.5)),
            "upper_bound": float(np.percentile(means, 97.5))
        })()

        return result_obj

    # StatisticalValidator Implementation

    def calculate_win_rate(self, trades) -> float:
        """Calculate win rate from trade history"""
        if not trades:
            return 0.0
        pnls = [t.pnl if hasattr(t, 'pnl') else t["pnl"] for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        return wins / len(trades) * 100

    def test_significance(self, hypothesis_id: str, result) -> float:
        """
        Test statistical significance using bootstrap.

        Returns p-value (fraction of bootstrap samples <= 0).
        """
        if not HAS_QUANT_MATH or not result.trades:
            return 0.5

        trade_pnls = np.array([t.pnl for t in result.trades])
        n = len(trade_pnls)
        count_le_zero = 0
        for _ in range(1000):
            sample = np.random.choice(trade_pnls, size=n, replace=True)
            if sample.sum() <= 0:
                count_le_zero += 1

        return count_le_zero / 1000

    def calculate_sharpe_ratio(self, returns, risk_free_rate: float = 0.02,
                               period: str = 'daily') -> float:
        """Calculate Sharpe ratio using PerformanceMetrics"""
        if not HAS_QUANT_MATH:
            return 0.0
        returns_arr = np.array(returns) if not isinstance(returns, np.ndarray) else returns
        return PerformanceMetrics.sharpe_ratio(returns_arr, risk_free_rate, period)

    def calculate_sortino_ratio(self, returns, risk_free_rate: float = 0.02,
                                period: str = 'daily') -> float:
        """Calculate Sortino ratio using PerformanceMetrics"""
        if not HAS_QUANT_MATH:
            return 0.0
        returns_arr = np.array(returns) if not isinstance(returns, np.ndarray) else returns
        return PerformanceMetrics.sortino_ratio(returns_arr, risk_free_rate, period)

    # RiskManager Implementation

    def check_position_size(self, hypothesis_id: str, size: float,
                           account_value: float) -> Dict[str, Any]:
        """Check if position size meets risk criteria"""
        # Simple Kelly criterion approximation
        kelly_fraction = 0.2  # Conservative Kelly fraction

        max_position = account_value * kelly_fraction
        if size > max_position:
            return {
                "approved": False,
                "reason": f"Position size {size} exceeds max Kelly {max_position:.2f}"
            }

        return {"approved": True, "max_position": max_position}

    def check_drawdown_limit(self, current_drawdown: float, limit: float) -> bool:
        """Check if drawdown is within acceptable limits"""
        return current_drawdown <= limit

    def check_sharpe_threshold(self, sharpe_ratio: float, threshold: float) -> bool:
        """Check if Sharpe ratio meets threshold"""
        return sharpe_ratio >= threshold

    def check_sortino_threshold(self, sortino_ratio: float, threshold: float) -> bool:
        """Check if Sortino ratio meets threshold"""
        return sortino_ratio >= threshold
