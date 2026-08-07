"""
Return Calculator Module

Calculates various return metrics for trading strategies.
"""

import numpy as np
from typing import List, Dict, Any, Optional


class ReturnCalculator:
    """
    Calculate various return metrics from trade history or price series.
    """

    @staticmethod
    def calculate_returns(trades: List[Dict[str, Any]]) -> np.ndarray:
        """
        Calculate returns from trade history.

        Args:
            trades: List of trade dictionaries

        Returns:
            Array of returns
        """
        returns = []
        for trade in trades:
            if isinstance(trade, dict):
                pnl = trade.get('pnl') or trade.get('PnL')
                entry = trade.get('entry_price') or trade.get('entry')
                if pnl is not None and entry is not None and entry != 0:
                    returns.append(float(pnl) / float(entry))
        return np.array(returns)

    @staticmethod
    def calculate_cumulative_return(returns: np.ndarray) -> float:
        """Calculate cumulative return from returns series."""
        if len(returns) == 0:
            return 0.0
        return np.prod(1 + returns) - 1

    @staticmethod
    def calculate_annualized_return(
        returns: np.ndarray,
        periods_per_year: int = 252
    ) -> float:
        """Calculate annualized return."""
        if len(returns) == 0:
            return 0.0
        total_return = ReturnCalculator.calculate_cumulative_return(returns)
        years = len(returns) / periods_per_year
        if years <= 0:
            return 0.0
        return (1 + total_return) ** (1 / years) - 1

    @staticmethod
    def calculate_geometric_mean(returns: np.ndarray) -> float:
        """Calculate geometric mean of returns."""
        if len(returns) == 0:
            return 0.0
        return np.prod(1 + returns) ** (1 / len(returns)) - 1

    @staticmethod
    def calculate_arithmetic_mean(returns: np.ndarray) -> float:
        """Calculate arithmetic mean of returns."""
        if len(returns) == 0:
            return 0.0
        return np.mean(returns)

    @staticmethod
    def calculate_volatility(returns: np.ndarray, annualize: bool = True,
                             periods_per_year: int = 252) -> float:
        """Calculate volatility (standard deviation) of returns."""
        if len(returns) < 2:
            return 0.0
        vol = np.std(returns, ddof=1)
        if annualize:
            vol *= np.sqrt(periods_per_year)
        return vol