# Drawdown Analyzer Module
import numpy as np
from typing import List

class DrawdownAnalyzer:
    """Analyze drawdowns from price series."""

    @staticmethod
    def calculate_drawdown(prices: List[float]) -> List[float]:
        """
        Calculate drawdowns from price series.

        Parameters:
        -----------
        prices : List[float]
            Historical price series

        Returns:
        --------
        List[float]
            Drawdown values
        """
        max_price = prices[0]
        drawdowns = []

        for price in prices:
            max_price = max(max_price, price)
            drawdowns.append((max_price - price) / max_price)

        return drawdowns

    @staticmethod
    def calculate_max_drawdown(drawdowns: List[float]) -> float:
        """
        Calculate maximum drawdown.

        Parameters:
        -----------
        drawdowns : List[float]
            Drawdown values

        Returns:
        --------
        float
            Maximum drawdown
        """
        if len(drawdowns) == 0:
            return 0.0
        return max(drawdowns)

    @staticmethod
    def calculate_average_drawdown(drawdowns: List[float]) -> float:
        """
        Calculate average drawdown.

        Parameters:
        -----------
        drawdowns : List[float]
            Drawdown values

        Returns:
        --------
        float
            Average drawdown
        """
        if len(drawdowns) == 0:
            return 0.0
        return np.mean(drawdowns)

    @staticmethod
    def calculate_drawdown_duration(prices: List[float]) -> tuple:
        """
        Calculate drawdown duration (time from peak to valley).

        Parameters:
        -----------
        prices : List[float]
            Historical price series

        Returns:
        --------
        tuple
            (max_drawdown_duration, max_peak_index, max_valley_index)
        """
        max_price = prices[0]
        max_peak_idx = 0
        max_valley_idx = 0
        max_duration = 0

        for i, price in enumerate(prices):
            if price > max_price:
                max_price = price
                max_peak_idx = i
            elif price < prices[max_valley_idx]:
                max_valley_idx = i
                duration = max_valley_idx - max_peak_idx
                if duration > max_duration:
                    max_duration = duration

        return max_duration, max_peak_idx, max_valley_idx
