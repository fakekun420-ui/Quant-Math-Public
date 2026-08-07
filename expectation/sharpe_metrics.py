# Sharpe Metrics Module
import numpy as np
from typing import List

class SharpeMetrics:
    """Calculate Sharpe ratio and related metrics."""

    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe ratio.

        Parameters:
        -----------
        returns : List[float]
            Period returns
        risk_free_rate : float
            Annual risk-free rate

        Returns:
        --------
        float
            Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Convert annualized
        annualized_return = (1 + mean_return) ** 252 - 1
        annualized_std = std_return * np.sqrt(252)

        sharpe = (annualized_return - risk_free_rate) / annualized_std
        return sharpe

    @staticmethod
    def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino ratio (downside deviation).

        Parameters:
        -----------
        returns : List[float]
            Period returns
        risk_free_rate : float
            Annual risk-free rate

        Returns:
        --------
        float
            Sortino ratio
        """
        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        downside_returns = [r for r in returns if r < mean_return]

        if len(downside_returns) == 0:
            return float('inf')

        downside_deviation = np.std(downside_returns)

        if downside_deviation == 0:
            return float('inf')

        # Convert annualized
        annualized_return = (1 + mean_return) ** 252 - 1
        annualized_downside = downside_deviation * np.sqrt(252)

        sortino = (annualized_return - risk_free_rate) / annualized_downside
        return sortino

    @staticmethod
    def calculate_information_ratio(returns: List[float], benchmark_returns: List[float]) -> float:
        """
        Calculate information ratio.

        Parameters:
        -----------
        returns : List[float]
            Portfolio returns
        benchmark_returns : List[float]
            Benchmark returns

        Returns:
        --------
        float
            Information ratio
        """
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0.0

        active_returns = [r - br for r, br in zip(returns, benchmark_returns)]

        if len(active_returns) == 0:
            return 0.0

        tracking_error = np.std(active_returns)
        excess_return = np.mean(active_returns)

        if tracking_error == 0:
            return float('inf')

        ir = excess_return / tracking_error
        return ir
