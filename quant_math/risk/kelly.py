"""
Kelly Criterion Module

Kelly criterion position sizing for optimal bet sizing.
"""

import numpy as np


class KellyCriterion:
    """Kelly criterion position sizing."""

    @staticmethod
    def calculate(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate full Kelly fraction.

        Parameters:
        -----------
        win_rate : float
            Win rate (0-1)
        avg_win : float
            Average win amount
        avg_loss : float
            Average loss amount

        Returns:
        --------
        float
            Kelly fraction
        """
        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        return max(0.0, kelly)

    @staticmethod
    def calculate_discrete(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate discrete Kelly fraction (fractional Kelly)."""
        kelly = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
        return max(0.0, min(1.0, kelly))

    @staticmethod
    def calculate_growth_optimal(win_rate: float, avg_win: float, avg_loss: float,
                                 n_trades: int = 100) -> float:
        """Calculate growth-optimal fraction."""
        kelly = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
        # Adjust for finite n
        return max(0.0, kelly - (1.0 / n_trades))


# Convenience function
def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float, fraction: float = 1.0) -> float:
    """
    Calculate Kelly fraction with optional scaling.

    Args:
        win_rate: Win rate (0-1)
        avg_win: Average win amount
        avg_loss: Average loss amount
        fraction: Fraction of Kelly to use (default: 1.0 = full Kelly)

    Returns:
        Scaled Kelly fraction
    """
    return KellyCriterion.calculate(win_rate, avg_win, avg_loss) * fraction