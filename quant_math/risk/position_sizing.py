"""
Position Sizing Module

Various position sizing algorithms for risk management.
"""

import numpy as np
from typing import Optional, Dict, Any


class PositionSizer:
    """
    Unified position sizing calculator.

    Supports multiple sizing algorithms:
    - Fixed fractional
    - Kelly criterion
    - Volatility targeting
    - ATR-based
    """

    def __init__(self, default_method: str = "fixed_fractional", default_risk_pct: float = 0.02):
        """
        Initialize position sizer.

        Args:
            default_method: Default sizing method
            default_risk_pct: Default risk percentage per trade
        """
        self.default_method = default_method
        self.default_risk_pct = default_risk_pct

    def calculate_size(
        self,
        account_value: float,
        entry_price: float,
        stop_price: float,
        method: Optional[str] = None,
        risk_pct: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate position size based on method.

        Args:
            account_value: Total account value
            entry_price: Entry price
            stop_price: Stop loss price
            method: Sizing method (uses default if None)
            risk_pct: Risk percentage (uses default if None)
            **kwargs: Additional parameters for specific methods

        Returns:
            Dictionary with size and metadata
        """
        method = method or self.default_method
        risk_pct = risk_pct or self.default_risk_pct

        if method == "fixed_fractional":
            return self._fixed_fractional(account_value, entry_price, stop_price, risk_pct)
        elif method == "kelly":
            return self._kelly_sizing(account_value, entry_price, stop_price, **kwargs)
        elif method == "volatility_target":
            return self._volatility_targeting(account_value, entry_price, stop_price, **kwargs)
        elif method == "atr_based":
            return self._atr_based(account_value, entry_price, stop_price, **kwargs)
        else:
            raise ValueError(f"Unknown sizing method: {method}")

    def _fixed_fractional(self, account_value: float, entry_price: float,
                          stop_price: float, risk_pct: float) -> Dict[str, Any]:
        """Fixed fractional position sizing."""
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return {"size": 0, "method": "fixed_fractional", "risk_per_share": 0}

        max_risk = account_value * risk_pct
        size = max_risk / risk_per_share

        return {
            "size": size,
            "method": "fixed_fractional",
            "risk_per_share": risk_per_share,
            "max_risk": max_risk,
            "risk_pct": risk_pct
        }

    def _kelly_sizing(self, account_value: float, entry_price: float,
                      stop_price: float, win_rate: float = 0.5,
                      avg_win: float = 1.0, avg_loss: float = 1.0,
                      kelly_fraction: float = 0.5) -> Dict[str, Any]:
        """Kelly criterion position sizing."""
        from quant_math.risk.kelly import KellyCriterion

        kelly_full = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
        kelly_adjusted = kelly_full * kelly_fraction

        # Calculate size based on Kelly fraction
        # Kelly gives fraction of capital to risk
        max_risk = account_value * kelly_adjusted
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return {"size": 0, "method": "kelly", "kelly_fraction": kelly_adjusted}

        size = max_risk / risk_per_share

        return {
            "size": size,
            "method": "kelly",
            "kelly_full": kelly_full,
            "kelly_adjusted": kelly_adjusted,
            "risk_per_share": risk_per_share,
            "max_risk": max_risk
        }

    def _volatility_targeting(self, account_value: float, entry_price: float,
                              stop_price: float, target_vol: float = 0.15,
                              current_vol: float = 0.20) -> Dict[str, Any]:
        """Volatility targeting position sizing."""
        # Scale position to target volatility
        vol_ratio = target_vol / current_vol if current_vol > 0 else 1.0
        base_size = account_value * 0.1 * vol_ratio  # Base 10% position scaled by vol

        # Limit by stop loss risk
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return {"size": 0, "method": "volatility_target"}

        max_risk = account_value * 0.02  # Max 2% risk per trade
        size_by_risk = max_risk / risk_per_share
        size = min(base_size / entry_price, size_by_risk)

        return {
            "size": size,
            "method": "volatility_target",
            "vol_ratio": vol_ratio,
            "base_size": base_size,
            "size_by_risk": size_by_risk
        }

    def _atr_based(self, account_value: float, entry_price: float,
                   stop_price: float, atr: float = None,
                   atr_multiplier: float = 2.0,
                   risk_pct: float = 0.02) -> Dict[str, Any]:
        """ATR-based position sizing."""
        if atr is None:
            # Use stop distance as proxy for ATR
            atr = abs(entry_price - stop_price)

        # Set stop at ATR multiples
        atr_stop = atr * atr_multiplier

        # Calculate size based on risk
        max_risk = account_value * risk_pct
        size = max_risk / atr_stop if atr_stop > 0 else 0

        return {
            "size": size,
            "method": "atr_based",
            "atr": atr,
            "atr_stop": atr_stop,
            "atr_multiplier": atr_multiplier,
            "max_risk": max_risk
        }

    @staticmethod
    def calculate(portfolio_value: float, risk_per_trade: float,
                  stop_loss_distance: float) -> float:
        """Legacy static API: calculate position size in shares."""
        if stop_loss_distance == 0:
            return 0.0
        max_risk = portfolio_value * risk_per_trade
        return max_risk / stop_loss_distance