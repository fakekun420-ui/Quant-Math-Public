"""
Sharpe Metrics Module

Calculates Sharpe, Sortino, Calmar and other risk-adjusted return metrics.
"""

import numpy as np
from typing import List, Dict, Any, Optional


class SharpeMetrics:
    """
    Calculate risk-adjusted performance metrics.
    """

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0,
                     periods_per_year: int = 252) -> float:
        """
        Calculate Sharpe ratio.

        Args:
            returns: Array of returns
            risk_free_rate: Risk-free rate (annualized)
            periods_per_year: Periods per year for annualization

        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free_rate / periods_per_year
        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns, ddof=1)

        if std_excess == 0:
            return 0.0

        sharpe = mean_excess / std_excess * np.sqrt(periods_per_year)
        return float(sharpe)

    @staticmethod
    def sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.0,
                      periods_per_year: int = 252) -> float:
        """
        Calculate Sortino ratio (uses downside deviation).

        Args:
            returns: Array of returns
            risk_free_rate: Risk-free rate (annualized)
            periods_per_year: Periods per year for annualization

        Returns:
            Annualized Sortino ratio
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free_rate / periods_per_year
        mean_excess = np.mean(excess_returns)

        # Downside deviation (only negative returns)
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) == 0:
            return float('inf') if mean_excess > 0 else 0.0

        downside_dev = np.std(downside_returns, ddof=1)

        if downside_dev == 0:
            return float('inf') if mean_excess > 0 else 0.0

        sortino = mean_excess / downside_dev * np.sqrt(periods_per_year)
        return float(sortino)

    @staticmethod
    def calmar_ratio(returns: np.ndarray, max_drawdown: float,
                     periods_per_year: int = 252) -> float:
        """
        Calculate Calmar ratio (annualized return / max drawdown).

        Args:
            returns: Array of returns
            max_drawdown: Maximum drawdown (positive number)
            periods_per_year: Periods per year for annualization

        Returns:
            Calmar ratio
        """
        if len(returns) == 0 or max_drawdown == 0:
            return 0.0

        annual_return = SharpeMetrics._annualized_return(returns, periods_per_year)
        return float(annual_return / max_drawdown)

    @staticmethod
    def _annualized_return(returns: np.ndarray, periods_per_year: int = 252) -> float:
        """Calculate annualized return."""
        if len(returns) == 0:
            return 0.0
        total_return = np.prod(1 + returns) - 1
        years = len(returns) / periods_per_year
        if years <= 0:
            return 0.0
        return (1 + total_return) ** (1 / years) - 1

    @staticmethod
    def information_ratio(returns: np.ndarray, benchmark_returns: np.ndarray,
                          periods_per_year: int = 252) -> float:
        """
        Calculate Information Ratio (active return / tracking error).

        Args:
            returns: Strategy returns
            benchmark_returns: Benchmark returns
            periods_per_year: Periods per year

        Returns:
            Information ratio
        """
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 0.0

        active_returns = returns - benchmark_returns
        mean_active = np.mean(active_returns)
        tracking_error = np.std(active_returns, ddof=1)

        if tracking_error == 0:
            return 0.0

        ir = mean_active / tracking_error * np.sqrt(periods_per_year)
        return float(ir)

    @staticmethod
    def treynor_ratio(returns: np.ndarray, beta: float,
                      risk_free_rate: float = 0.0,
                      periods_per_year: int = 252) -> float:
        """
        Calculate Treynor ratio (excess return / beta).

        Args:
            returns: Strategy returns
            beta: Portfolio beta
            risk_free_rate: Risk-free rate (annualized)
            periods_per_year: Periods per year

        Returns:
            Treynor ratio
        """
        if len(returns) == 0 or beta == 0:
            return 0.0

        annual_return = SharpeMetrics._annualized_return(returns, periods_per_year)
        excess_return = annual_return - risk_free_rate
        return float(excess_return / beta)

    @staticmethod
    def omega_ratio(returns: np.ndarray, threshold: float = 0.0) -> float:
        """
        Calculate Omega ratio (probability-weighted gains / losses).

        Args:
            returns: Array of returns
            threshold: Return threshold (MAR)

        Returns:
            Omega ratio
        """
        if len(returns) == 0:
            return 0.0

        excess = returns - threshold
        gains = excess[excess > 0]
        losses = excess[excess <= 0]

        if len(losses) == 0:
            return float('inf')

        return float(np.sum(gains) / abs(np.sum(losses)))

    @staticmethod
    def calculate_all(returns: np.ndarray, risk_free_rate: float = 0.0,
                      max_drawdown: float = 0.0, beta: float = 1.0,
                      benchmark_returns: Optional[np.ndarray] = None,
                      periods_per_year: int = 252) -> Dict[str, float]:
        """
        Calculate all risk-adjusted metrics.

        Returns:
            Dictionary with all metrics
        """
        metrics = {}

        metrics["sharpe_ratio"] = SharpeMetrics.sharpe_ratio(returns, risk_free_rate, periods_per_year)
        metrics["sortino_ratio"] = SharpeMetrics.sortino_ratio(returns, risk_free_rate, periods_per_year)

        if max_drawdown > 0:
            metrics["calmar_ratio"] = SharpeMetrics.calmar_ratio(returns, max_drawdown, periods_per_year)

        if benchmark_returns is not None:
            metrics["information_ratio"] = SharpeMetrics.information_ratio(returns, benchmark_returns, periods_per_year)

        if beta != 0:
            metrics["treynor_ratio"] = SharpeMetrics.treynor_ratio(returns, beta, risk_free_rate, periods_per_year)

        metrics["omega_ratio"] = SharpeMetrics.omega_ratio(returns)

        return metrics