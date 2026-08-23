# Adaptive Sizing Module
from typing import List, Dict
import numpy as np

class AdaptiveSizer:
    """Adaptive position sizing based on market conditions."""

    def calculate(self, new_position: float = None, current_portfolio: float = None,
                  volatility: float = None, trend_strength: float = 0.5, *,
                  portfolio_value: float = None, risk_per_trade: float = None,
                  stop_loss_distance: float = None,
                  kelly_fraction: float = None) -> float:
        """
        Calculate adaptive position size.

        Supports two modes:

        Risk-based mode (keyword args):
            portfolio_value : float - Total portfolio value
            risk_per_trade : float - Fraction of portfolio to risk per trade
            stop_loss_distance : float - Relative distance to stop loss
            kelly_fraction : float - Kelly criterion fraction (confidence scale)

        Volatility/trend mode (positional args):
            new_position : float
            current_portfolio : float
            volatility : float
            trend_strength : float

        Returns
        -------
        float
            Adaptive position size
        """
        if portfolio_value is not None:
            # Risk-based sizing mode
            risk_capital = portfolio_value * (risk_per_trade if risk_per_trade else 0.02)
            base_units = risk_capital / stop_loss_distance if stop_loss_distance else 0.0
            if kelly_fraction is not None:
                kelly_scale = max(0.0, min(1.0, kelly_fraction / 0.25))
                base_units *= kelly_scale
            return max(0.0, base_units)

        # Legacy volatility/trend sizing mode
        base_size = new_position

        # Adjust based on volatility (inverse relationship)
        volatility_adjustment = 1.0 - min(0.5, volatility * 2)
        adjusted_size = base_size * volatility_adjustment

        # Adjust based on trend strength (higher trend = higher size)
        trend_adjustment = 0.5 + trend_strength * 0.5
        final_size = adjusted_size * trend_adjustment

        return max(0.0, final_size)

    @staticmethod
    def calculate_from_trades(trade_history: List[Dict], n_trades: int = 20) -> float:
        """
        Calculate position size based on recent trade performance.

        Parameters:
        -----------
        trade_history : List[Dict]
            Recent trade history
        n_trades : int

        Returns:
        --------
        float
            Position sizing multiplier
        """
        if len(trade_history) == 0:
            return 1.0

        recent_trades = trade_history[-n_trades:]
        avg_win = np.mean([t['pnl'] for t in recent_trades if t['pnl'] > 0])
        avg_loss = np.mean([abs(t['pnl']) for t in recent_trades if t['pnl'] < 0])

        if avg_loss == 0:
            return 1.0

        win_rate = len([t for t in recent_trades if t['pnl'] > 0]) / len(recent_trades)
        kelly = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
        return max(0.2, min(1.0, kelly))

    @staticmethod
    def calculate_from_market_regime(regime: str, base_size: float) -> float:
        """
        Calculate position size based on market regime.

        Parameters:
        -----------
        regime : str
            Market regime ('trending', 'volatile', 'mean_reverting', 'stable')
        base_size : float

        Returns:
        --------
        float
            Regime-adjusted position size
        """
        regime_multipliers = {
            'trending': 1.2,
            'volatile': 0.6,
            'mean_reverting': 0.8,
            'stable': 1.0
        }

        multiplier = regime_multipliers.get(regime, 1.0)
        return base_size * multiplier
