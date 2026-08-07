"""
Structural Break Detection Module
Detects changes in data distribution and statistical properties
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
import logging

logger = logging.getLogger(__name__)


class StructuralBreakDetector:
    """
    Detect structural breaks in time series data
    """

    @staticmethod
    def chow_test(
        df: pd.DataFrame,
        break_point: int,
        regression_col: str = 'close'
    ) -> Tuple[float, float]:
        """
        Chow test for structural break at specified point

        Args:
            df: Input DataFrame
            break_point: Index where break occurs
            regression_col: Column to test for break

        Returns:
            Tuple of (F-statistic, p-value)
        """
        data = df[regression_col].values
        x = sm.add_constant(np.arange(len(data)))

        # Split data at break point
        x1 = x[:break_point]
        y1 = data[:break_point]
        x2 = x[break_point:]
        y2 = data[break_point:]

        # Regression for full sample
        model_full = sm.OLS(y, x).fit()

        # Regression for two sub-samples
        model1 = sm.OLS(y1, x1).fit()
        model2 = sm.OLS(y2, x2).fit()

        # Concatenate residuals
        residuals = np.concatenate([model1.resid, model2.resid])
        df_resid = len(residuals) - 2 * len(x1)

        # Chow test statistic
        ssr_r = model_full.ssr
        ssr_b = model1.ssr + model2.ssr

        f_stat = ((ssr_r - ssr_b) / 2) / (ssr_b / df_resid)

        # Critical value at 5% significance
        from scipy.stats import f
        p_value = 1 - f.cdf(f_stat, 2, df_resid)

        logger.info(f"Chow test at break point {break_point}: F={f_stat:.4f}, p={p_value:.4f}")

        return f_stat, p_value

    @staticmethod
    def find_multiple_breaks(
        df: pd.DataFrame,
        max_breaks: int = 5,
        regression_col: str = 'close'
    ) -> list:
        """
        Find multiple structural breaks using recursive Chow test

        Args:
            df: Input DataFrame
            max_breaks: Maximum number of breaks to find
            regression_col: Column to test for breaks

        Returns:
            List of break point indices
        """
        breaks = []
        test_points = range(10, len(df) - 10)

        best_pvalue = 1.0

        for test_point in test_points:
            f_stat, p_value = StructuralBreakDetector.chow_test(
                df, test_point, regression_col
            )

            if p_value < 0.05 and p_value < best_pvalue:
                best_pvalue = p_value
                best_break = test_point

                # Stop if we've found enough breaks
                if len(breaks) >= max_breaks:
                    break

                breaks.append(best_break)

        breaks.sort()
        logger.info(f"Found {len(breaks)} structural breaks at indices: {breaks}")

        return breaks

    @staticmethod
    def detect_regime_change(
        df: pd.DataFrame,
        col: str = 'close',
        method: str = 'statistical_test'
    ) -> pd.Series:
        """
        Detect regime changes in time series

        Args:
            df: Input DataFrame
            col: Column to analyze
            method: 'statistical_test', 'change_point', or 'volatility'

        Returns:
            Series indicating regime change points
        """
        regime_changes = pd.Series(False, index=df.index)
        prev_mean = df[col].iloc[0]
        prev_std = df[col].iloc[1:].std()

        for i in range(1, len(df)):
            current_mean = df[col].iloc[:i+1].mean()
            current_std = df[col].iloc[:i+1].std()

            if method == 'statistical_test':
                # Z-test for mean change
                n = len(df[col].iloc[:i+1])
                z_score = (current_mean - prev_mean) / (prev_std / np.sqrt(n))

                if abs(z_score) > 2:  # 95% confidence
                    regime_changes.iloc[i] = True

            elif method == 'change_point':
                # Cumulative sum test
                cumsum = np.cumsum(df[col].iloc[:i+1] - prev_mean)
                if abs(cumsum.max()) > 2 * prev_std * np.sqrt(n):
                    regime_changes.iloc[i] = True

            elif method == 'volatility':
                # Change in volatility
                if abs(current_std - prev_std) / prev_std > 0.5:
                    regime_changes.iloc[i] = True

            prev_mean = current_mean
            prev_std = current_std

        return regime_changes

    @staticmethod
    def stationarity_test(
        df: pd.DataFrame,
        col: str = 'close',
        method: str = 'adf'
    ) -> dict:
        """
        Test stationarity of time series

        Args:
            df: Input DataFrame
            col: Column to test
            method: 'adf' or 'kpss'

        Returns:
            Dictionary with test results
        """
        data = df[col].dropna()

        if method == 'adf':
            result = adfuller(data)
            test_type = 'Augmented Dickey-Fuller'
        else:
            from statsmodels.tsa.stattools import kpss
            result = kpss(data, regression='c')
            test_type = 'KPSS'

        test_results = {
            'test_type': test_type,
            'statistic': result[0],
            'p_value': result[1],
            'critical_values': result[4]
        }

        if method == 'adf':
            is_stationary = result[1] < 0.05
        else:
            is_stationary = result[1] > 0.05

        test_results['is_stationary'] = is_stationary

        logger.info(f"{test_type}: stat={result[0]:.4f}, p={result[1]:.4f}, stationary={is_stationary}")

        return test_results

    @staticmethod
    def find_trend_change(
        df: pd.DataFrame,
        col: str = 'close',
        window: int = 30
    ) -> pd.Series:
        """
        Detect changes in trend using linear regression

        Args:
            df: Input DataFrame
            col: Column to analyze
            window: Rolling window size

        Returns:
            Series indicating trend change points
        """
        trends = pd.Series(0.0, index=df.index)

        for i in range(window, len(df)):
            window_data = df[col].iloc[i-window:i]

            # Simple linear regression
            x = np.arange(window)
            slope, _ = np.polyfit(x, window_data, 1)

            trends.iloc[i] = slope

        # Detect significant changes
        changes = pd.Series(False, index=df.index)
        prev_slope = trends.iloc[window]
        prev_std = trends.iloc[window:].std()

        for i in range(window, len(trends)):
            current_slope = trends.iloc[i]
            n = window

            z_score = abs(current_slope - prev_slope) / (prev_std / np.sqrt(n))

            if z_score > 2:  # 95% confidence
                changes.iloc[i] = True

            prev_slope = current_slope

        return changes

    @staticmethod
    def analyze_breaks(
        df: pd.DataFrame,
        col: str = 'close',
        max_breaks: int = 3
    ) -> dict:
        """
        Comprehensive structural break analysis

        Args:
            df: Input DataFrame
            col: Column to analyze
            max_breaks: Maximum number of breaks to find

        Returns:
            Dictionary with analysis results
        """
        results = {
            'stationarity': StructuralBreakDetector.stationarity_test(df, col),
            'breaks': StructuralBreakDetector.find_multiple_breaks(df, max_breaks, col),
            'regime_changes': StructuralBreakDetector.detect_regime_change(df, col),
            'trend_changes': StructuralBreakDetector.find_trend_change(df, col)
        }

        return results
