# Position Sizing Module
from typing import Optional

class PositionSizer:
    """Position sizing calculator based on risk management."""

    @staticmethod
    def calculate(portfolio_value: float, risk_per_trade: float = 0.02,
                  stop_loss_distance: float = 0.05) -> float:
        """
        Calculate position size based on portfolio value and risk per trade.

        Parameters:
        -----------
        portfolio_value : float
            Total portfolio value
        risk_per_trade : float
            Percentage of portfolio to risk per trade (default 2%)
        stop_loss_distance : float
            Percentage distance for stop loss (default 5%)

        Returns:
        --------
        float
            Position size in shares
        """
        risk_amount = portfolio_value * risk_per_trade
        position_size = risk_amount / stop_loss_distance
        return position_size

    @staticmethod
    def fixed_fraction(portfolio_value: float, fraction: float = 0.1) -> float:
        """
        Calculate fixed fractional position size.

        Parameters:
        -----------
        portfolio_value : float
            Total portfolio value
        fraction : float
            Fraction of portfolio to allocate (default 10%)

        Returns:
        --------
        float
            Position size in shares
        """
        return portfolio_value * fraction

    @staticmethod
    def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate Kelly fraction.

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
