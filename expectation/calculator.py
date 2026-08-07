# Return Calculator Module
import numpy as np
from typing import List

class ReturnCalculator:
    """Calculate various return metrics."""

    @staticmethod
    def calculate_return(prices: List[float]) -> List[float]:
        """
        Calculate simple returns from price series.

        Parameters:
        -----------
        prices : List[float]
            Historical price series

        Returns:
        --------
        List[float]
            Simple returns
        """
        return [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]

    @staticmethod
    def calculate_log_return(prices: List[float]) -> List[float]:
        """
        Calculate log returns from price series.

        Parameters:
        -----------
        prices : List[float]
            Historical price series

        Returns:
        --------
        List[float]
            Log returns
        """
        return [np.log(prices[i] / prices[i-1]) for i in range(1, len(prices))]

    @staticmethod
    def calculate_annualized_return(returns: List[float], period: int = 252) -> float:
        """
        Calculate annualized return.

        Parameters:
        -----------
        returns : List[float]
            Period returns
        period : int
            Number of periods per year (default: 252 trading days)

        Returns:
        --------
        float
            Annualized return
        """
        if len(returns) == 0:
            return 0.0
        mean_return = np.mean(returns)
        return (1 + mean_return) ** period - 1

    @staticmethod
    def calculate_cumulative_return(prices: List[float]) -> float:
        """
        Calculate cumulative return from price series.

        Parameters:
        -----------
        prices : List[float]
            Historical price series

        Returns:
        --------
        float
            Cumulative return
        """
        if len(prices) < 2:
            return 0.0
        return (prices[-1] - prices[0]) / prices[0]
