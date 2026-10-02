"""
Backtesting & Evaluation Module

This module provides backtesting and performance evaluation capabilities including:
- Backtesting engine
- Walk-forward validation
- Performance metrics (Sharpe, Sortino, drawdown, etc.)
- Portfolio performance tracking
- Trade analysis
- Risk-adjusted returns
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from order_management import OrderManager, ExecutionReport


@dataclass
class Trade:
    """Represents a single trade."""
    trade_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    hold_duration: float
    entry_time: float
    exit_time: float
    commission: float
    liquidated: bool = False       # True if closed by liquidation (leverage)
    funding_paid: float = 0.0      # total funding paid while holding


@dataclass
class BacktestResult:
    """Result of backtesting."""
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    annualized_volatility: float
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    trades: List[Trade]
    equity_curve: List[Tuple[float, float]]
    num_liquidations: int = 0
    total_funding_paid: float = 0.0


@dataclass
class WalkForwardResult:
    """Result of walk-forward validation."""
    windows: List[Dict[str, Any]]
    is_stats: Dict[str, float]
    oos_stats: Dict[str, float]
    robustness_score: float
    parameter_stability: float


class WalkForwardValidator:
    """
    Walk-Forward Validation Engine

    Implements walk-forward analysis for robust strategy validation:
    - Anchored/rolling window walk-forward
    - In-sample optimization, out-of-sample testing
    - Robustness scoring
    - Parameter stability analysis
    """

    def __init__(
        self,
        backtester: 'Backtester',
        train_window: int = 252,  # ~1 year for daily
        test_window: int = 63,    # ~3 months for daily
        step_size: int = 63,      # Step by 3 months
        anchored: bool = True,    # Anchored (expanding) vs rolling
        min_train_size: int = 100
    ):
        self.backtester = backtester
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size
        self.anchored = anchored
        self.min_train_size = min_train_size

    def validate(
        self,
        strategy_func: Callable,
        data: Dict[str, np.ndarray],
        param_grid: Optional[Dict[str, List]] = None,
        initial_capital: Optional[float] = None
    ) -> WalkForwardResult:
        """
        Run walk-forward validation.

        Parameters
        ----------
        strategy_func : callable
            Strategy function that takes data and params, returns orders
        data : dict
            Dictionary of {symbol: price_array}
        param_grid : dict, optional
            Parameter grid for optimization {param_name: [values]}
        initial_capital : float, optional
            Initial capital

        Returns
        -------
        result : WalkForwardResult
            Walk-forward validation results
        """
        if initial_capital is None:
            initial_capital = self.backtester.initial_capital

        # Get data length (assume all symbols same length)
        symbol = list(data.keys())[0]
        n_bars = len(data[symbol])

        windows = []
        is_returns = []
        oos_returns = []
        is_sharpes = []
        oos_sharpes = []
        best_params_per_window = []

        # Walk-forward loop
        start = 0
        window_idx = 0

        while start + self.train_window + self.test_window <= n_bars:
            train_end = start + self.train_window
            test_end = min(train_end + self.test_window, n_bars)

            if test_end - train_end < 10:
                break

            # Extract train/test slices
            train_data = {s: prices[start:train_end] for s, prices in data.items()}
            test_data = {s: prices[train_end:test_end] for s, prices in data.items()}

            # In-sample optimization (if param_grid provided)
            if param_grid:
                best_params, best_score = self._optimize_params(
                    strategy_func, train_data, param_grid, initial_capital
                )
            else:
                best_params = {}
                best_score = None

            best_params_per_window.append(best_params)

            # In-sample backtest with best params
            is_result = self._run_with_params(
                strategy_func, train_data, best_params, initial_capital
            )

            # Out-of-sample backtest with best params
            oos_result = self._run_with_params(
                strategy_func, test_data, best_params, initial_capital
            )

            # Collect metrics
            is_ret = is_result.total_return_pct
            oos_ret = oos_result.total_return_pct
            is_sharpe = is_result.sharpe_ratio
            oos_sharpe = oos_result.sharpe_ratio

            is_returns.append(is_ret)
            oos_returns.append(oos_ret)
            is_sharpes.append(is_sharpe)
            oos_sharpes.append(oos_sharpe)

            windows.append({
                'window': window_idx,
                'train_start': start,
                'train_end': train_end,
                'test_start': train_end,
                'test_end': test_end,
                'train_bars': train_end - start,
                'test_bars': test_end - train_end,
                'best_params': best_params,
                'is_return': is_ret,
                'oos_return': oos_ret,
                'is_sharpe': is_sharpe,
                'oos_sharpe': oos_sharpe,
                'is_trades': is_result.num_trades,
                'oos_trades': oos_result.num_trades,
                'is_win_rate': is_result.win_rate,
                'oos_win_rate': oos_result.win_rate,
            })

            window_idx += 1

            # Move window
            if self.anchored:
                # Anchored: expand training window
                start += self.step_size
                self.train_window += self.step_size
            else:
                # Rolling: fixed window size
                start += self.step_size

        # Calculate aggregate statistics
        is_stats = self._compute_stats(is_returns, is_sharpes, 'IS')
        oos_stats = self._compute_stats(oos_returns, oos_sharpes, 'OOS')

        # Robustness score
        robustness = self._compute_robustness(is_returns, oos_returns, is_sharpes, oos_sharpes)

        # Parameter stability
        param_stability = self._compute_param_stability(best_params_per_window)

        return WalkForwardResult(
            windows=windows,
            is_stats=is_stats,
            oos_stats=oos_stats,
            robustness_score=robustness,
            parameter_stability=param_stability
        )

    def _optimize_params(
        self,
        strategy_func: Callable,
        train_data: Dict[str, np.ndarray],
        param_grid: Dict[str, List],
        initial_capital: float
    ) -> Tuple[Dict, float]:
        """Grid search optimization on training data."""
        import itertools

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        best_score = -float('inf')
        best_params = {}

        for combo in itertools.product(*param_values):
            params = dict(zip(param_names, combo))

            try:
                result = self._run_with_params(
                    strategy_func, train_data, params, initial_capital
                )
                # Score: combination of return and sharpe
                score = result.total_return_pct * 0.5 + result.sharpe_ratio * 50 * 0.5
                if result.num_trades < 5:
                    score -= 100  # Penalty for too few trades

                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception:
                continue

        return best_params, best_score

    def _run_with_params(
        self,
        strategy_func: Callable,
        data: Dict[str, np.ndarray],
        params: Dict,
        initial_capital: float
    ) -> BacktestResult:
        """Run backtest with specific parameters."""

        def param_strategy(d):
            return strategy_func(d, **params)

        return self.backtester.run_backtest(param_strategy, data, initial_capital)

    def _compute_stats(self, returns: List[float], sharpes: List[float], prefix: str) -> Dict:
        """Compute aggregate statistics."""
        if not returns:
            return {f'{prefix}_mean_return': 0, f'{prefix}_mean_sharpe': 0,
                    f'{prefix}_std_return': 0, f'{prefix}_win_rate': 0,
                    f'{prefix}_profit_factor': 0, f'{prefix}_consistency': 0}

        returns_arr = np.array(returns)
        sharpes_arr = np.array(sharpes)

        # Profit factor
        gross_profit = np.sum(returns_arr[returns_arr > 0])
        gross_loss = abs(np.sum(returns_arr[returns_arr < 0]))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Consistency: percentage of positive windows
        consistency = np.mean(returns_arr > 0) * 100

        return {
            f'{prefix}_mean_return': float(np.mean(returns_arr)),
            f'{prefix}_median_return': float(np.median(returns_arr)),
            f'{prefix}_std_return': float(np.std(returns_arr)),
            f'{prefix}_mean_sharpe': float(np.mean(sharpes_arr)),
            f'{prefix}_median_sharpe': float(np.median(sharpes_arr)),
            f'{prefix}_win_rate': float(np.mean(returns_arr > 0) * 100),
            f'{prefix}_profit_factor': pf if pf != float('inf') else 999,
            f'{prefix}_consistency': consistency,
            f'{prefix}_best_window': float(np.max(returns_arr)),
            f'{prefix}_worst_window': float(np.min(returns_arr)),
        }

    def _compute_robustness(
        self,
        is_returns: List[float],
        oos_returns: List[float],
        is_sharpes: List[float],
        oos_sharpes: List[float]
    ) -> float:
        """Compute robustness score (0-100)."""
        if not is_returns or not oos_returns:
            return 0.0

        # Correlation between IS and OOS performance
        try:
            corr = np.corrcoef(is_returns, oos_returns)[0, 1]
            if np.isnan(corr):
                corr = 0
        except Exception:
            corr = 0

        # OOS consistency
        oos_consistency = np.mean(np.array(oos_returns) > 0)

        # OOS Sharpe quality
        oos_mean_sharpe = np.mean(oos_sharpes)
        oos_sharpe_quality = min(max(oos_mean_sharpe / 2.0, 0), 1)  # Normalize to 0-1

        # Degradation factor (IS vs OOS)
        is_mean = np.mean(is_returns)
        oos_mean = np.mean(oos_returns)
        if is_mean != 0:
            degradation = max(0, min(oos_mean / is_mean, 2))  # Cap at 2x
        else:
            degradation = 0

        # Combined robustness score
        robustness = (
            0.3 * max(0, corr) * 100 +      # IS-OOS correlation (0-100)
            0.3 * oos_consistency * 100 +   # OOS win rate (0-100)
            0.2 * oos_sharpe_quality * 100 + # OOS Sharpe quality (0-100)
            0.2 * degradation * 50          # Degradation factor (0-100)
        )

        return float(max(0, min(robustness, 100)))

    def _compute_param_stability(self, params_per_window: List[Dict]) -> float:
        """Compute parameter stability across windows (0-100)."""
        if len(params_per_window) < 2:
            return 100.0

        # Get all parameter names
        all_names = set()
        for p in params_per_window:
            all_names.update(p.keys())

        if not all_names:
            return 100.0

        stabilities = []
        for name in all_names:
            values = [p.get(name) for p in params_per_window if name in p]
            if len(values) < 2:
                stabilities.append(100)
                continue

            # Coefficient of variation
            mean_val = np.mean(values)
            if mean_val != 0:
                cv = np.std(values) / abs(mean_val)
                # Convert to stability (lower CV = higher stability)
                stability = max(0, 100 * (1 - min(cv, 1)))
            else:
                stability = 100 if np.std(values) == 0 else 0
            stabilities.append(stability)

        return float(np.mean(stabilities))


class PerformanceMetrics:
    # ... (rest of existing class)
    """
    Performance Metrics Calculator

    Calculates various performance metrics for trading strategies.
    """

    @staticmethod
    def total_return(initial: float, final: float) -> float:
        """Calculate total return."""
        return final - initial

    @staticmethod
    def total_return_pct(initial: float, final: float) -> float:
        """Calculate total return percentage."""
        return (final - initial) / initial * 100

    @staticmethod
    def cumulative_returns(prices: List[float]) -> List[float]:
        """Calculate cumulative returns."""
        returns = np.diff(prices) / prices[:-1]
        cumulative = 1.0
        cumulative_returns = [cumulative]

        for r in returns:
            cumulative *= (1 + r)
            cumulative_returns.append(cumulative)

        return np.array(cumulative_returns)

    #: Velas por año por temporalidad de Bybit. MEDIDO el 2026-10-01: el
    #: numero de barras al año es `365,25 dias * velas/dia`, y las velas por
    #: dia son 1440/horas. Un año tiene 35.040 barras de 15m, no 252.
    #:
    #: Se declara aqui y no se calcula con `sqrt(252)` porque el error de
    #: antes no era de precision: era de UNIDADES. Un Sharpe calculado con
    #: 252 sobre velas de 15m compara una media de 15 minutos contra una
    #: desviacion de un dia.
    PERIODOS_POR_ANIO = {
        "1m": 525_600, "3m": 175_200, "5m": 105_120, "15m": 35_040,
        "30m": 17_520, "1h": 8_760, "2h": 4_380, "4h": 2_190, "1d": 365,
    }

    @classmethod
    def periodos_por_anio(cls, timeframe: Optional[str]) -> int:
        """Velas al año de una temporalidad. `None` o desconocida -> diaria.

        Se cae a 365 y no a 252 a proposito: 252 son DIAS DE MERCADO sobre
        velas diarias, y cualquier otra temporalidad necesita velas. Con
        `None` el valor es una aproximacion declarada, no una medida, y el
        llamante puede ver cual es por el propio resultado.
        """
        if not timeframe:
            return cls.PERIODOS_POR_ANIO["1d"]
        return cls.PERIODOS_POR_ANIO.get(str(timeframe).strip().lower(),
                                        cls.PERIODOS_POR_ANIO["1d"])

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02,
                     period: str = 'daily',
                     periods_per_year: Optional[int] = None) -> float:
        """
        Calculate Sharpe ratio.

        Parameters
        ----------
        returns : np.ndarray
            Period returns
        risk_free_rate : float
            Risk-free rate (annualized)
        period : str
            Period type ('daily', 'weekly', 'monthly')

        Returns
        -------
        sharpe : float
            Sharpe ratio
        """
        if len(returns) == 0:
            return 0.0

        # CORREGIDO el 2026-10-01. Antes el numero de periodos al año estaba
        # FIJO en 252 sin importar la temporalidad, con lo que un backtest de
        # 15m se annualizaba como si cada vela fuera un dia. Y el riesgo sin
        # riesgo, que es ANUAL, se restaba de una media ya multiplicada.
        #
        # Ahora `periods_per_year` se puede pasar explicito (lo hace
        # `run_backtest` con la temporalidad real) y el riesgo sin riesgo se
        # escala al periodo ANTES de restar, que es la unica forma de que los
        # dos terminos sean de la misma unidad:
        #
        #     sharpe_anual = (media - rf_anual/P) * sqrt(P) / sigma
        #
        # Si se deja `period` y no `periods_per_year`, manda `period` (se
        # conserva el comportamiento historico para los llamantes viejos).
        if periods_per_year is None:
            if period == 'daily':
                periods_per_year = 252
            elif period == 'weekly':
                periods_per_year = 52
            else:
                periods_per_year = 12
        periods_per_year = max(1, int(periods_per_year))

        rf_periodo = risk_free_rate / periods_per_year
        media = np.mean(returns)
        sigma = np.std(returns)
        if sigma == 0:
            return 0.0
        sharpe = (media - rf_periodo) * np.sqrt(periods_per_year) / sigma

        return float(sharpe)

    @staticmethod
    def sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.02,
                      period: str = 'daily') -> float:
        """
        Calculate Sortino ratio.

        Parameters
        ----------
        returns : np.ndarray
            Period returns
        risk_free_rate : float
            Risk-free rate (annualized)
        period : str
            Period type

        Returns
        -------
        sortino : float
            Sortino ratio
        """
        if len(returns) == 0:
            return 0.0

        # Convert to annualized
        if period == 'daily':
            periods_per_year = 252
        elif period == 'weekly':
            periods_per_year = 52
        else:
            periods_per_year = 12

        mean_return = np.mean(returns) * periods_per_year
        downside_returns = returns[returns < 0]
        if downside_returns.size == 0:
            # sin periodos perdedores: riesgo a la baja indefinidamente bajo
            return float("inf") if returns.size else 0.0
        downside_std = np.std(downside_returns) * np.sqrt(periods_per_year)

        if not np.isfinite(downside_std) or downside_std == 0:
            return 0.0

        sortino = (mean_return - risk_free_rate) / downside_std

        return sortino

    @staticmethod
    def max_drawdown(prices: List[float]) -> float:
        """
        Calculate maximum drawdown.

        Parameters
        ----------
        prices : List[float]
            Price series

        Returns
        -------
        max_dd : float
            Maximum drawdown percentage
        """
        if len(prices) == 0:
            return 0.0

        prices_array = np.array(prices)
        cumulative = np.maximum.accumulate(prices_array)
        drawdowns = (prices_array - cumulative) / cumulative * 100
        # CORREGIDO el 2026-10-01. Aqui estaba `np.max(drawdowns)`, y eso
        # devolvia 0.0 SIEMPRE, no "casi siempre": por construccion
        # `prices <= maximo_acumulado`, luego todos los drawdowns son <= 0, y
        # el maximo de una serie no positiva es el MAS CERCANO a cero.
        # Demostrado: [100, 90, 80, 85, 90, 110] cae un 20% y devolvia 0,0.
        #
        # Un drawdown es una PERDIDA, asi que el peor es el mas negativo y se
        # reporta en positivo. Con `np.max` el motor de riesgo recibia "no he
        #endido ninguna perdida" en cada operacion perdedora que tuviera,
        # que es justo cuando tiene que verla.
        max_drawdown = abs(float(np.min(drawdowns)))

        return max_drawdown

    @staticmethod
    def win_rate(trades: List[Trade]) -> float:
        """
        Calculate win rate.

        Parameters
        ----------
        trades : List[Trade]
            Trade history

        Returns
        -------
        win_rate : float
            Win rate percentage
        """
        if len(trades) == 0:
            return 0.0

        wins = sum(1 for t in trades if t.pnl > 0)
        return wins / len(trades) * 100

    @staticmethod
    def profit_factor(trades: List[Trade]) -> float:
        """
        Calculate profit factor.

        Parameters
        ----------
        trades : List[Trade]
            Trade history

        Returns
        -------
        pf : float
            Profit factor
        """
        if len(trades) == 0:
            return 0.0

        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

        if gross_loss == 0:
            return float('inf')

        return gross_profit / gross_loss


class Backtester:
    """
    Backtesting Engine

    Executes strategy backtests and calculates performance metrics.
    """

    # Futures realism defaults (Bybit USDT perpetuals)
    DEFAULT_FUNDING_8H = 0.0001      # 0.01% per 8h funding interval
    DEFAULT_SLIPPAGE_PCT = 0.0001   # 1bp adverse fill
    #: MMR por defecto = 0,0033, LEIDO del endpoint publico de Bybit el
    #: 2026-09-30 (`/v5/market/risk-limit`, primer tramo, que es el que
    #: corresponde a un nocional pequeno). Antes estaba HARDCODEADO en 0,005,
    #: que era el segundo tramo y ademas un supuesto: eso ponia la
    #: liquidacion MAS CERCA de lo real, o sea que el backtest era
    #: OPTIMISTA y se:"-subestimaba" el riesgo de liquidacion.
    #: El MMR real es ESCALONADO por nocional; ver
    #: `quant_math.risk.roe_targets.BYBIT_MMR_TIERS` y `mmr_for_notional()`.
    MAINTENANCE_MARGIN_RATE = 0.0033  # primer tramo real de Bybit (2026-09-30)

    def __init__(self, initial_capital: float = 100000.0,
                 commission_rate: float = 0.001,
                 min_commission: float = 0.0,
                 slippage_pct: float = 0.0,
                 leverage: float = 1.0,
                 funding_rate_8h: float = 0.0,
                 timeframe: str = "1h",
                 maintenance_margin_rate: Optional[float] = None):
        """
        Initialize backtester.

        Parameters
        ----------
        initial_capital : float
            Initial capital
        commission_rate : float
            Commission rate
        min_commission : float
            Minimum commission
        slippage_pct : float
            Adverse slippage per fill as fraction (e.g. 0.0001 = 1bp).
            0.0 preserves legacy exact-fill behaviour.
        leverage : float
            Position leverage. 1.0 = spot (legacy behaviour). >1 scales PnL,
            posts margin instead of full notional, and enables liquidation.
        funding_rate_8h : float
            Perpetual funding rate per 8h as fraction of notional
            (e.g. 0.0001 = 0.01%). 0.0 disables.
        timeframe : str
            Candle timeframe ('1m','5m','15m','1h','4h','1d') used to convert
            bars held into hours for funding accrual.
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage_pct = max(0.0, float(slippage_pct))
        self.leverage = max(1.0, float(leverage))
        self.funding_rate_8h = float(funding_rate_8h)
        self.timeframe = timeframe
        # MMR configurable: el real de Bybit es escalonado por nocional y el
        # valor hardcodeado (0,005) era del segundo tramo. Con None se usa el
        # primer tramo real, que es el que corresponde a un nocional pequeno.
        self.maintenance_margin_rate = float(
            self.MAINTENANCE_MARGIN_RATE
            if maintenance_margin_rate is None else maintenance_margin_rate)

    # ------------------------------------------------------------------
    # Futures realism helpers
    # ------------------------------------------------------------------

    def _timeframe_hours(self) -> float:
        """Hours per candle for funding accrual."""
        tf = (self.timeframe or "1h").strip().lower()
        try:
            if tf.endswith("m"):
                return float(tf[:-1]) / 60.0
            if tf.endswith("h"):
                return float(tf[:-1])
            if tf.endswith("d"):
                return float(tf[:-1]) * 24.0
        except ValueError:
            pass
        return 1.0

    def _adverse_fill(self, price: float, side: str) -> float:
        """Adverse slippage fill: buy pays more, sell receives less."""
        if side == "buy":
            return price * (1.0 + self.slippage_pct)
        return price * (1.0 - self.slippage_pct)

    def _fee(self, notional: float) -> float:
        return max(self.min_commission, notional * self.commission_rate)

    def _funding_cost(self, notional: float, bars_held: int) -> float:
        """Funding paid for holding `bars_held` bars at current notional."""
        if self.funding_rate_8h == 0.0 or bars_held <= 0:
            return 0.0
        hours = bars_held * self._timeframe_hours()
        return notional * self.funding_rate_8h * (hours / 8.0)

    def _liq_price_long(self, entry_price: float) -> Optional[float]:
        """Liquidation price for a long at configured leverage (None if spot)."""
        if self.leverage <= 1.0:
            return None
        drop = 1.0 / self.leverage - self.maintenance_margin_rate
        if drop <= 0:
            return None
        return entry_price * (1.0 - drop)

    def _touched_liq(self, series: np.ndarray, entry_idx: int,
                     exit_idx: int, liq_price: Optional[float]) -> bool:
        """True if any bar low (close series proxy) touched liquidation."""
        if liq_price is None:
            return False
        lo = int(max(0, entry_idx))
        hi = int(min(len(series), exit_idx + 1))
        if hi <= lo:
            return False
        return bool(np.min(series[lo:hi]) <= liq_price)

    def run_backtest(self, strategy_func: Callable, data: Dict[str, np.ndarray],
                    initial_capital: Optional[float] = None,
                    timeframe: Optional[str] = None) -> BacktestResult:
        """
        Run backtest for a strategy.

        Parameters
        ----------
        strategy_func : callable
            Strategy function that takes data and returns orders
        data : dict
            Dictionary of {symbol: price_array}
        initial_capital : float, optional
            Initial capital

        Returns
        -------
        result : BacktestResult
            Backtest results
        """
        if initial_capital is None:
            initial_capital = self.initial_capital

        capital = initial_capital
        orders = strategy_func(data)
        trades = []
        # Mutable counters shared with fill logic below
        num_liquidations = [0]
        total_funding_paid = [0.0]

        # Simulate execution - only process non-hold orders
        executed_orders = []
        for i, order in enumerate(orders):
            if order['symbol'] in data and order['side'] != 'hold':
                price = data[order['symbol']][i]
                quantity = order['quantity']

                trade_value = quantity * price
                commission = max(self.min_commission, trade_value * self.commission_rate)

                executed_orders.append({
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'quantity': quantity,
                    'price': price,
                    'commission': commission,
                    'index': i
                })

        # Calculate equity curve
        equity_curve = [initial_capital]
        current_capital = initial_capital

        # Track positions for proper trade pairing
        open_positions = {}  # symbol -> {side, quantity, entry_price, entry_commission, entry_index}

        for i, order in enumerate(orders):
            symbol = order['symbol']
            side = order['side']
            quantity = order['quantity']

            if symbol not in data:
                equity_curve.append(current_capital)
                continue

            price = data[symbol][i]

            if side == 'buy' and quantity > 0:
                fill = self._adverse_fill(price, 'buy')
                margin = quantity * fill / self.leverage
                entry_fee = self._fee(quantity * fill)
                if current_capital >= margin + entry_fee:
                    current_capital -= (margin + entry_fee)
                    # Track open position
                    open_positions[symbol] = {
                        'side': 'long',
                        'quantity': quantity,
                        'entry_price': fill,
                        'margin': margin,
                        'entry_commission': entry_fee,
                        'entry_index': i
                    }
                equity_curve.append(current_capital)

            elif side == 'sell' and quantity > 0:
                fill = self._adverse_fill(price, 'sell')
                exit_fee = self._fee(quantity * fill)
                # Close position if exists (return margin + net PnL)
                if symbol in open_positions and open_positions[symbol]['side'] == 'long':
                    pos = open_positions[symbol]
                    margin = pos.get('margin', pos['quantity'] * pos['entry_price'])
                    bars_held = max(0, i - pos['entry_index'])
                    funding = self._funding_cost(pos['quantity'] * fill, bars_held)
                    total_funding_paid[0] += funding
                    liq = self._liq_price_long(pos['entry_price'])
                    liquidated = self._touched_liq(data[symbol], pos['entry_index'], i, liq)
                    if liquidated:
                        exit_px = liq if liq is not None else fill
                        exit_fee = self._fee(quantity * exit_px)
                        # Margin lost; only exit fee + funding leave the account
                        # (entry fee + margin were already deducted at entry)
                        current_capital -= (exit_fee + funding)
                        pnl = -margin - pos['entry_commission'] - exit_fee - funding
                        num_liquidations[0] += 1
                    else:
                        exit_px = fill
                        # Return margin + price PnL net of exit fee + funding
                        # (entry fee already deducted at entry)
                        current_capital += (margin + (fill - pos['entry_price'])
                                            * pos['quantity'] - exit_fee - funding)
                        pnl = ((fill - pos['entry_price']) * pos['quantity']
                               - pos['entry_commission'] - exit_fee - funding)
                    pnl_pct = pnl / margin * 100 if margin else 0.0
                    trade = Trade(
                        trade_id=f"TRD-{len(trades):06d}",
                        symbol=symbol,
                        side='buy',
                        quantity=pos['quantity'],
                        entry_price=pos['entry_price'],
                        exit_price=exit_px,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        hold_duration=float(bars_held),
                        entry_time=pos['entry_index'],
                        exit_time=i,
                        commission=pos['entry_commission'] + exit_fee,
                        liquidated=liquidated,
                        funding_paid=funding
                    )
                    trades.append(trade)
                    del open_positions[symbol]
                equity_curve.append(current_capital)

            else:  # hold
                equity_curve.append(current_capital)

        # Cerrar las posiciones vivas al precio de la ultima vela.
        # El PnL se suma al capital, no es solo registro: si el Trade
        # cuenta en n_trades y en win_rate, su PnL tiene que contar
        # tambien en final_capital. Si no, el retorno mide una
        # poblacion distinta de la que cuentan las metricas de trade.
        for symbol, pos in open_positions.items():
            fill = self._adverse_fill(data[symbol][-1], 'sell')
            commission = self._fee(pos['quantity'] * fill)
            margin = pos.get('margin', pos['quantity'] * pos['entry_price'])
            bars_held = max(0, len(orders) - 1 - pos['entry_index'])
            funding = self._funding_cost(pos['quantity'] * fill, bars_held)
            total_funding_paid[0] += funding
            liq = self._liq_price_long(pos['entry_price'])
            liquidated = self._touched_liq(data[symbol], pos['entry_index'],
                                           len(orders) - 1, liq)
            if liquidated:
                exit_px = liq if liq is not None else fill
                # El margen y la comision de entrada ya se descontaron
                # al abrir: de la cuenta solo salen salida y funding.
                current_capital -= (commission + funding)
                pnl = -margin - pos['entry_commission'] - commission - funding
                num_liquidations[0] += 1
            else:
                exit_px = fill
                # Se devuelve margen + PnL de precio - salida - funding
                # (la comision de entrada ya se desconto al abrir).
                current_capital += (margin + (fill - pos['entry_price'])
                                   * pos['quantity'] - commission - funding)
                pnl = ((fill - pos['entry_price']) * pos['quantity']
                       - pos['entry_commission'] - commission - funding)
            pnl_pct = pnl / margin * 100 if margin else 0.0
            trade = Trade(
                trade_id=f"TRD-{len(trades):06d}",
                symbol=symbol,
                side='buy',
                quantity=pos['quantity'],
                entry_price=pos['entry_price'],
                exit_price=exit_px,
                pnl=pnl,
                pnl_pct=pnl_pct,
                hold_duration=float(bars_held),
                entry_time=pos['entry_index'],
                exit_time=len(orders) - 1,
                commission=pos['entry_commission'] + commission,
                liquidated=liquidated,
                funding_paid=funding
            )
            trades.append(trade)

        # Punto extra de la curva: la ultima vela ya esta liquidada.
        # Uno solo, no uno por posicion: la curva es un punto por vela
        # y final_capital sale de equity_curve[-1].
        if open_positions:
            # Misma regla que el resto de la curva: equity = efectivo + no
            # realizado. Con `current_capital` aqui, `final_capital` salia
            # como el efectivo sin el margen de la posicion que seguia
            # abierta, o sea el resultado de una venta que no ocurrio.
            equity_curve.append(current_capital)

        # Calculate metrics
        final_capital = equity_curve[-1]
        total_return = PerformanceMetrics.total_return(initial_capital, final_capital)
        total_return_pct = PerformanceMetrics.total_return_pct(initial_capital, final_capital)

        # Create price series for metrics
        price_series = equity_curve

        returns = np.diff(price_series) / price_series[:-1] if len(price_series) > 1 else np.array([0.0])
        # MEDIDO el 2026-10-01: esto iba fijo en 252 velas al año, sin
        # mirar la temporalidad. Un backtest de 15m tiene 35.040 velas al
        # año, luego la volatilidad y el Sharpe salian calculados con un
        # 139x de error en el numerador y un 11,8x en el denominador.
        _ppa = PerformanceMetrics.periodos_por_anio(timeframe)
        annualized_vol = (np.std(returns) * np.sqrt(_ppa)
                          if len(returns) > 0 else 0.0)
        sharpe = PerformanceMetrics.sharpe_ratio(returns, periods_per_year=_ppa)
        sortino = PerformanceMetrics.sortino_ratio(returns)
        max_dd = PerformanceMetrics.max_drawdown(price_series)

        # Trade metrics
        win_rate = PerformanceMetrics.win_rate(trades)
        avg_win = np.mean([t.pnl for t in trades if t.pnl > 0]) if any(t.pnl > 0 for t in trades) else 0.0
        avg_loss = np.mean([t.pnl for t in trades if t.pnl < 0]) if any(t.pnl < 0 for t in trades) else 0.0
        pf = PerformanceMetrics.profit_factor(trades)

        result = BacktestResult(
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            annualized_volatility=annualized_vol,
            num_trades=len(trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=pf,
            trades=trades,
            equity_curve=list(zip(range(len(equity_curve)), equity_curve)),
            num_liquidations=num_liquidations[0],
            total_funding_paid=total_funding_paid[0]
        )

        return result

    def print_summary(self, result: BacktestResult):
        """Print backtest summary."""
        print("\n" + "="*70)
        print("BACKTEST SUMMARY")
        print("="*70)

        print(f"\nCapital:")
        print(f"  Initial: ${result.initial_capital:,.2f}")
        print(f"  Final: ${result.final_capital:,.2f}")
        print(f"  Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.2f}%)")

        print(f"\nPerformance Metrics:")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.4f}")
        print(f"  Sortino Ratio: {result.sortino_ratio:.4f}")
        print(f"  Max Drawdown: {result.max_drawdown:.2f}%")
        print(f"  Annualized Volatility: {result.annualized_volatility:.2f}%")

        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {result.num_trades}")
        print(f"  Win Rate: {result.win_rate:.2f}%")
        print(f"  Average Win: ${result.avg_win:.2f}")
        print(f"  Average Loss: ${result.avg_loss:.2f}")
        print(f"  Profit Factor: {result.profit_factor:.2f}")

        print("\n" + "="*70 + "\n")
