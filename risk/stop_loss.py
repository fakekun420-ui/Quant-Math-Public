# Stop Loss Module
from typing import Optional

class StopLoss:
    """Stop loss calculator and manager."""

    @staticmethod
    def get_optimal(entry_price: float, volatility: float, lookback: int = 20,
                    atr: Optional[float] = None) -> float:
        """
        Calculate optimal stop loss distance.

        Parameters:
        -----------
        entry_price : float
            Entry price
        volatility : float
            Historical volatility
        lookback : int
            Lookback period for volatility
        atr : float, optional
            Average True Range (alternative to volatility)

        Returns:
        --------
        float
            Stop loss distance in price points
        """
        if atr is not None:
            sl_distance = atr * 1.5
        else:
            sl_distance = volatility * entry_price * 0.03  # 3% of entry

        return sl_distance

    @staticmethod
    def get_percentage(entry_price: float, stop_distance: float) -> float:
        """Calculate stop loss as percentage of entry price."""
        return (stop_distance / entry_price) * 100

    @staticmethod
    def calculate_stop_loss(entry_price: float, volatility: float,
                           stop_distance: float) -> float:
        """Calculate stop loss price."""
        return entry_price - stop_distance

    @staticmethod
    def calculate_take_profit(entry_price: float, stop_distance: float,
                              risk_reward_ratio: float = 2.0) -> float:
        """Calculate take profit price."""
        return entry_price + (stop_distance * risk_reward_ratio)
