"""
Stop Loss Module

Stop loss calculation and management for risk management.
"""

import numpy as np
from typing import Optional, Dict, Any, List


class StopLoss:
    """
    Stop loss calculator with multiple methods.

    Supports:
    - Fixed percentage
    - ATR-based
    - Trailing stops
    - Chandelier exits
    - Volatility-adjusted
    """

    def __init__(self, default_method: str = "fixed_pct", default_pct: float = 0.02):
        """
        Initialize stop loss calculator.

        Args:
            default_method: Default stop loss method
            default_pct: Default percentage for fixed methods
        """
        self.default_method = default_method
        self.default_pct = default_pct

    def calculate_stop(
        self,
        entry_price: float,
        side: str,
        method: Optional[str] = None,
        pct: Optional[float] = None,
        atr: Optional[float] = None,
        atr_mult: float = 2.0,
        high: Optional[float] = None,
        low: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate stop loss price.

        Args:
            entry_price: Entry price
            side: 'long' or 'short'
            method: Stop method (uses default if None)
            pct: Percentage for fixed methods
            atr: ATR value for ATR-based methods
            atr_mult: ATR multiplier
            high: Recent high (for chandelier)
            low: Recent low (for chandelier)
            **kwargs: Additional parameters

        Returns:
            Dictionary with stop price and metadata
        """
        method = method or self.default_method
        pct = pct or self.default_pct

        if method == "fixed_pct":
            return self._fixed_percentage(entry_price, side, pct)
        elif method == "atr":
            return self._atr_stop(entry_price, side, atr, atr_mult)
        elif method == "trailing":
            return self._trailing_stop(entry_price, side, pct, **kwargs)
        elif method == "chandelier":
            return self._chandelier_exit(entry_price, side, high, low, atr, atr_mult)
        elif method == "volatility":
            return self._volatility_stop(entry_price, side, atr, atr_mult, **kwargs)
        else:
            raise ValueError(f"Unknown stop method: {method}")

    def _fixed_percentage(self, entry_price: float, side: str, pct: float) -> Dict[str, Any]:
        """Fixed percentage stop loss."""
        if side == "long":
            stop = entry_price * (1 - pct)
        else:
            stop = entry_price * (1 + pct)

        return {
            "stop_price": stop,
            "method": "fixed_pct",
            "entry_price": entry_price,
            "side": side,
            "pct": pct,
            "distance_pct": pct
        }

    def _atr_stop(self, entry_price: float, side: str, atr: float, atr_mult: float) -> Dict[str, Any]:
        """ATR-based stop loss."""
        if atr is None or atr <= 0:
            raise ValueError("ATR must be provided and positive for ATR stop")

        atr_distance = atr * atr_mult

        if side == "long":
            stop = entry_price - atr_distance
        else:
            stop = entry_price + atr_distance

        return {
            "stop_price": stop,
            "method": "atr",
            "entry_price": entry_price,
            "side": side,
            "atr": atr,
            "atr_mult": atr_mult,
            "atr_distance": atr_distance
        }

    def _trailing_stop(self, entry_price: float, side: str, pct: float,
                       current_price: Optional[float] = None,
                       trail_pct: Optional[float] = None) -> Dict[str, Any]:
        """Trailing stop loss."""
        trail = trail_pct or pct

        if side == "long":
            if current_price is None:
                stop = entry_price * (1 - trail)
            else:
                stop = current_price * (1 - trail)
        else:
            if current_price is None:
                stop = entry_price * (1 + trail)
            else:
                stop = current_price * (1 + trail)

        return {
            "stop_price": stop,
            "method": "trailing",
            "entry_price": entry_price,
            "current_price": current_price,
            "side": side,
            "trail_pct": trail,
            "initial_stop_pct": pct
        }

    def _chandelier_exit(self, entry_price: float, side: str,
                         high: float, low: float,
                         atr: float, atr_mult: float) -> Dict[str, Any]:
        """Chandelier exit stop loss."""
        if high is None or low is None or atr is None:
            raise ValueError("High, low, and ATR required for Chandelier exit")

        chandelier_distance = atr * atr_mult

        if side == "long":
            stop = high - chandelier_distance
        else:
            stop = low + chandelier_distance

        return {
            "stop_price": stop,
            "method": "chandelier",
            "entry_price": entry_price,
            "side": side,
            "high": high,
            "low": low,
            "atr": atr,
            "atr_mult": atr_mult,
            "chandelier_distance": chandelier_distance
        }

    def _volatility_stop(self, entry_price: float, side: str,
                         atr: float, atr_mult: float,
                         volatility_lookback: int = 20,
                         price_history: Optional[List[float]] = None) -> Dict[str, Any]:
        """Volatility-adjusted stop loss."""
        if atr is None or atr <= 0:
            # Calculate from price history if available
            if price_history and len(price_history) >= 2:
                returns = np.diff(np.log(price_history))
                atr = np.std(returns) * np.sqrt(252) * entry_price  # Annualized
            else:
                raise ValueError("ATR or price_history required for volatility stop")

        return self._atr_stop(entry_price, side, atr, atr_mult)

    def calculate_multiple_levels(
        self,
        entry_price: float,
        side: str,
        levels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate multiple stop loss levels.

        Args:
            entry_price: Entry price
            side: 'long' or 'short'
            levels: List of level configurations

        Returns:
            List of stop loss dictionaries
        """
        stops = []
        for level_config in levels:
            level_config["entry_price"] = entry_price
            level_config["side"] = side
            stop = self.calculate_stop(**level_config)
            stops.append(stop)

        return stops