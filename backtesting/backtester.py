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

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02,
                     period: str = 'daily') -> float:
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

        # Convert to annualized
        if period == 'daily':
            periods_per_year = 252
        elif period == 'weekly':
            periods_per_year = 52
        else:
            periods_per_year = 12

        mean_return = np.mean(returns) * periods_per_year
        std_return = np.std(returns) * np.sqrt(periods_per_year)

        if std_return == 0:
            return 0.0

        sharpe = (mean_return - risk_free_rate) / std_return

        return sharpe

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
        max_drawdown = np.max(drawdowns)

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

    def __init__(self, initial_capital: float = 100000.0,
                 commission_rate: float = 0.001,
                 min_commission: float = 0.0):
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
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission

    def run_backtest(self, strategy_func: Callable, data: Dict[str, np.ndarray],
                    initial_capital: Optional[float] = None) -> BacktestResult:
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
                cost = quantity * price + max(self.min_commission, quantity * price * self.commission_rate)
                if current_capital >= cost:
                    current_capital -= cost
                    # Track open position
                    open_positions[symbol] = {
                        'side': 'long',
                        'quantity': quantity,
                        'entry_price': price,
                        'entry_commission': max(self.min_commission, quantity * price * self.commission_rate),
                        'entry_index': i
                    }
                equity_curve.append(current_capital)

            elif side == 'sell' and quantity > 0:
                proceeds = quantity * price - max(self.min_commission, quantity * price * self.commission_rate)
                current_capital += proceeds
                # Close position if exists
                if symbol in open_positions and open_positions[symbol]['side'] == 'long':
                    pos = open_positions[symbol]
                    pnl = (price - pos['entry_price']) * pos['quantity'] - pos['entry_commission'] - max(self.min_commission, quantity * price * self.commission_rate)
                    pnl_pct = (price - pos['entry_price']) / pos['entry_price'] * 100
                    trade = Trade(
                        trade_id=f"TRD-{len(trades):06d}",
                        symbol=symbol,
                        side='buy',
                        quantity=pos['quantity'],
                        entry_price=pos['entry_price'],
                        exit_price=price,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        hold_duration=1.0,
                        entry_time=pos['entry_index'],
                        exit_time=i,
                        commission=pos['entry_commission'] + max(self.min_commission, quantity * price * self.commission_rate)
                    )
                    trades.append(trade)
                    del open_positions[symbol]
                equity_curve.append(current_capital)

            else:  # hold
                equity_curve.append(current_capital)

        # Close any remaining open positions at final price
        for symbol, pos in open_positions.items():
            final_price = data[symbol][-1]
            commission = max(self.min_commission, pos['quantity'] * final_price * self.commission_rate)
            pnl = (final_price - pos['entry_price']) * pos['quantity'] - pos['entry_commission'] - commission
            pnl_pct = (final_price - pos['entry_price']) / pos['entry_price'] * 100
            trade = Trade(
                trade_id=f"TRD-{len(trades):06d}",
                symbol=symbol,
                side='buy',
                quantity=pos['quantity'],
                entry_price=pos['entry_price'],
                exit_price=final_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                hold_duration=1.0,
                entry_time=pos['entry_index'],
                exit_time=len(orders) - 1,
                commission=pos['entry_commission'] + commission
            )
            trades.append(trade)

        # Calculate metrics
        final_capital = equity_curve[-1]
        total_return = PerformanceMetrics.total_return(initial_capital, final_capital)
        total_return_pct = PerformanceMetrics.total_return_pct(initial_capital, final_capital)

        # Create price series for metrics
        price_series = equity_curve

        returns = np.diff(price_series) / price_series[:-1] if len(price_series) > 1 else np.array([0.0])
        annualized_vol = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0.0
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
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
            equity_curve=list(zip(range(len(equity_curve)), equity_curve))
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
