"""
Drawdown Analyzer Module

Calculates drawdown metrics for risk assessment.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple


class DrawdownAnalyzer:
    """
    Analyze drawdowns from equity curve or returns.
    """

    @staticmethod
    def calculate_drawdowns(equity_curve: np.ndarray) -> Dict[str, Any]:
        """
        Calculate drawdown series and metrics from equity curve.

        Args:
            equity_curve: Array of equity values over time

        Returns:
            Dictionary with drawdown series and metrics
        """
        if len(equity_curve) == 0:
            return {"drawdowns": np.array([]), "max_drawdown": 0.0}

        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_curve)

        # Calculate drawdown
        drawdowns = (equity_curve - running_max) / running_max

        # Find max drawdown
        max_drawdown = np.min(drawdowns)  # Most negative (largest drawdown)

        # Find drawdown periods
        dd_periods = DrawdownAnalyzer._find_drawdown_periods(drawdowns)

        return {
            "drawdowns": drawdowns,
            "max_drawdown": float(abs(max_drawdown)),
            "drawdown_periods": dd_periods,
            "current_drawdown": float(abs(drawdowns[-1])) if len(drawdowns) > 0 else 0.0
        }

    @staticmethod
    def _find_drawdown_periods(drawdowns: np.ndarray) -> List[Dict[str, Any]]:
        """Find individual drawdown periods."""
        periods = []
        in_drawdown = False
        start_idx = 0

        for i, dd in enumerate(drawdowns):
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                start_idx = i
            elif dd >= 0 and in_drawdown:
                in_drawdown = False
                periods.append({
                    "start": start_idx,
                    "end": i - 1,
                    "depth": float(abs(np.min(drawdowns[start_idx:i]))),
                    "duration": i - start_idx
                })

        # Handle case where we're still in drawdown at end
        if in_drawdown:
            periods.append({
                "start": start_idx,
                "end": len(drawdowns) - 1,
                "depth": float(abs(np.min(drawdowns[start_idx:]))),
                "duration": len(drawdowns) - start_idx
            })

        return periods

    @staticmethod
    def calculate_from_returns(returns: np.ndarray) -> Dict[str, Any]:
        """Calculate drawdowns from returns series."""
        if len(returns) == 0:
            return {"max_drawdown": 0.0}

        equity_curve = np.cumprod(1 + returns)
        equity_curve = np.insert(equity_curve, 0, 1.0)  # Start at 1.0

        return DrawdownAnalyzer.calculate_drawdowns(equity_curve)

    @staticmethod
    def average_drawdown(drawdown_periods: List[Dict[str, Any]]) -> float:
        """Calculate average drawdown depth."""
        if not drawdown_periods:
            return 0.0
        depths = [p["depth"] for p in drawdown_periods]
        return np.mean(depths)

    @staticmethod
    def average_drawdown_duration(drawdown_periods: List[Dict[str, Any]]) -> float:
        """Calculate average drawdown duration."""
        if not drawdown_periods:
            return 0.0
        durations = [p["duration"] for p in drawdown_periods]
        return np.mean(durations)

    @staticmethod
    def max_drawdown_duration(drawdown_periods: List[Dict[str, Any]]) -> int:
        """Calculate maximum drawdown duration."""
        if not drawdown_periods:
            return 0
        return max(p["duration"] for p in drawdown_periods)

    @staticmethod
    def ulcer_index(equity_curve: np.ndarray) -> float:
        """
        Calculate Ulcer Index (root mean square of drawdowns).

        Ulcer Index = sqrt(mean(drawdown^2))
        """
        if len(equity_curve) == 0:
            return 0.0

        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - running_max) / running_max
        squared_dd = drawdowns ** 2

        return float(np.sqrt(np.mean(squared_dd)))