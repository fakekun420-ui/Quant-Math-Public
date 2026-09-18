"""
Statistical Tests for Market Regime Detection

This module provides statistical test-based methods to identify different market regimes
based on return distributions and autocorrelation patterns.
"""

import numpy as np
from scipy import stats
from typing import Tuple, Optional


class ZScoreTest:
    """
    Z-score based regime detection.
    
    The Z-score measures how many standard deviations a value is from the mean.
    Extreme Z-scores indicate potential regime shifts.
    
    Parameters
    ----------
    threshold : float, optional
        Z-score threshold for regime detection. Default: 2.0
    alpha : float, optional
        Significance level for hypothesis testing. Default: 0.05
    
    Examples
    --------
    >>> z_test = ZScoreTest(threshold=2.0)
    >>> regimes = z_test.detect(returns)
    >>> regimes[:10]
    array([0, 0, 0, 1, 0, 0, 0, 0, 1, 0])
    """
    
    def __init__(self, threshold: float = 2.0, alpha: float = 0.05):
        self.threshold = threshold
        self.alpha = alpha
        self.history = []
    
    def detect(self, returns: np.ndarray, rolling_window: Optional[int] = None) -> np.ndarray:
        """
        Detect regimes based on Z-score of rolling mean.
        
        Parameters
        ----------
        returns : np.ndarray
            Daily returns series
        rolling_window : int, optional
            Window size for rolling statistics. If None, uses full series.
        
        Returns
        -------
        regimes : np.ndarray
            Binary regime indicator (0: normal, 1: extreme)
        """
        if rolling_window is None:
            rolling_window = len(returns)
        
        rolling_mean = np.convolve(returns, np.ones(rolling_window)/rolling_window, mode='valid')
        rolling_std = np.convolve(returns**2, np.ones(rolling_window)/rolling_window, mode='valid')**0.5
        
        # Avoid division by zero
        rolling_std[rolling_std == 0] = 1.0
        
        z_scores = (returns[:len(rolling_mean)] - rolling_mean) / rolling_std
        
        regimes = (np.abs(z_scores) >= self.threshold).astype(int)
        
        # Pad with zeros for early periods
        regimes = np.pad(regimes, (0, len(returns) - len(regimes)), mode='constant')
        
        return regimes
    
    def get_extremes(self, returns: np.ndarray, rolling_window: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get indices and values of extreme observations.
        
        Returns
        -------
        indices : np.ndarray
            Indices of extreme observations
        values : np.ndarray
            Values of extreme observations
        z_scores : np.ndarray
            Z-scores for all observations
        """
        if rolling_window is None:
            rolling_window = len(returns)
        
        rolling_mean = np.convolve(returns, np.ones(rolling_window)/rolling_window, mode='valid')
        rolling_std = np.convolve(returns**2, np.ones(rolling_window)/rolling_window, mode='valid')**0.5
        rolling_std[rolling_std == 0] = 1.0
        
        z_scores = (returns[:len(rolling_mean)] - rolling_mean) / rolling_std
        extremes = np.abs(z_scores) >= self.threshold
        
        indices = np.where(extremes)[0]
        values = returns[indices]
        
        return indices, values, z_scores


class RunsTest:
    """
    Runs test for random sequence analysis.
    
    The runs test checks whether a sequence is random by counting the number of runs
    (consecutive sequences of same sign). Non-random sequences show clustering patterns.
    
    Parameters
    ----------
    alpha : float, optional
        Significance level for hypothesis testing. Default: 0.05
    
    Examples
    --------
    >>> runs_test = RunsTest(alpha=0.05)
    >>> z_score, p_value = runs_test.test(returns)
    >>> p_value < 0.05  # Returns are non-random
    """
    
    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.z_score = None
        self.p_value = None
        self.history = []
    
    def test(self, returns: np.ndarray) -> Tuple[float, float]:
        """
        Perform runs test on return series.
        
        Parameters
        ----------
        returns : np.ndarray
            Daily returns series
        
        Returns
        -------
        z_score : float
            Z-score statistic
        p_value : float
            P-value for hypothesis test
        """
        if len(returns) < 2:
            raise ValueError("Returns series must have at least 2 elements")
        
        # Calculate mean
        mean = np.mean(returns)
        
        # Count positive and negative returns
        positive = np.sum(returns > mean)
        negative = np.sum(returns <= mean)
        total = positive + negative
        
        # Calculate expected and observed runs
        expected_runs = 1 + 2 * positive * negative / total
        var_runs = (2 * positive * negative * (2 * positive * negative - total)) / (total**2 * (total - 1))
        
        # Calculate observed runs
        signs = np.sign(returns)
        runs = 1
        for i in range(1, len(signs)):
            if signs[i] != signs[i-1]:
                runs += 1
        
        # Z-score and p-value
        if var_runs == 0:
            z_score = 0
            p_value = 1.0
        else:
            z_score = (runs - expected_runs) / np.sqrt(var_runs)
            p_value = 2 * (1 - stats.norm.cdf(np.abs(z_score)))
        
        self.z_score = z_score
        self.p_value = p_value
        self.history.append({
            'z_score': z_score,
            'p_value': p_value,
            'returns_count': len(returns)
        })
        
        return z_score, p_value
    
    def is_significant(self) -> bool:
        """Check if the test result is statistically significant."""
        return self.p_value is not None and self.p_value < self.alpha


class VarianceRatioTest:
    """
    Variance ratio test for mean reversion.
    
    The variance ratio test compares the variance of returns at different time horizons.
    A ratio > 1 suggests trending behavior (random walk), while < 1 suggests mean reversion.
    
    Parameters
    ----------
    lag : int, optional
        Lag for comparison. Default: 5
    alpha : float, optional
        Significance level. Default: 0.05
    
    Examples
    --------
    >>> vr_test = VarianceRatioTest(lag=5, alpha=0.05)
    >>> z_score, p_value = vr_test.test(returns)
    >>> z_score < 0  # Suggests mean reversion
    """
    
    def __init__(self, lag: int = 5, alpha: float = 0.05):
        self.lag = lag
        self.alpha = alpha
        self.z_score = None
        self.p_value = None
        self.history = []
    
    def test(self, returns: np.ndarray) -> Tuple[float, float]:
        """
        Perform variance ratio test.
        
        Parameters
        ----------
        returns : np.ndarray
            Daily returns series
        
        Returns
        -------
        z_score : float
            Z-score statistic
        p_value : float
            P-value for hypothesis test
        """
        if len(returns) < self.lag + 1:
            raise ValueError(f"Returns series must have at least {self.lag + 1} elements")
        
        T = len(returns) - self.lag
        y_t = returns[:T]
        y_t_lagged = returns[self.lag:T+self.lag]
        
        # Calculate variances
        var_1 = np.var(returns, ddof=1)
        var_lag = np.var(y_t - y_t_lagged, ddof=1)
        
        # Variance ratio
        qr = var_lag / var_1
        
        # Standard error
        se = np.sqrt(2 * (self.lag - 1) / self.lag)
        
        # Z-score
        z_score = (qr - 1) / se
        
        # P-value (two-tailed test)
        p_value = 2 * (1 - stats.norm.cdf(np.abs(z_score)))
        
        self.z_score = z_score
        self.p_value = p_value
        self.history.append({
            'lag': self.lag,
            'qr': qr,
            'z_score': z_score,
            'p_value': p_value
        })
        
        return z_score, p_value
    
    def is_trending(self) -> bool:
        """Check if series shows trending behavior (random walk)."""
        return self.z_score is not None and self.z_score > 0 and self.p_value < self.alpha
    
    def is_mean_reverting(self) -> bool:
        """Check if series shows mean reversion."""
        return self.z_score is not None and self.z_score < 0 and self.p_value < self.alpha


def regime_indicator(returns: np.ndarray, window: int = 20, threshold: float = 2.0) -> np.ndarray:
    """
    Combined regime indicator using multiple statistical tests.
    
    Parameters
    ----------
    returns : np.ndarray
        Daily returns series
    window : int, optional
        Rolling window size. Default: 20
    threshold : float, optional
        Z-score threshold. Default: 2.0
    
    Returns
    -------
    regimes : np.ndarray
        Regime indicator (0: normal, 1: volatile, 2: trending, 3: mean-reverting)
    """
    regimes = np.zeros(len(returns), dtype=int)
    
    # Calculate rolling statistics
    rolling_mean = np.convolve(returns, np.ones(window)/window, mode='valid')
    rolling_std = np.convolve(returns**2, np.ones(window)/window, mode='valid')**0.5
    rolling_std[rolling_std == 0] = 1.0
    
    rolling_returns = returns[:len(rolling_mean)]
    
    # Normal regime (low volatility, near mean)
    normal_mask = (np.abs(rolling_returns - rolling_mean) / rolling_std) < threshold
    
    # Volatile regime (high volatility)
    volatile_mask = (rolling_std / np.std(returns)) > 1.5
    
    # Trending regime (positive or negative autocorrelation)
    autocorr = np.array([np.corrcoef(rolling_returns[:-i], rolling_returns[i:])[0, 1] 
                        for i in range(1, min(5, window))])
    trending_mask = np.mean(np.abs(autocorr)) > 0.3
    
    # Mean-reverting regime (negative autocorrelation)
    mean_reverting_mask = np.mean(autocorr) < -0.3
    
    # Fill regimes
    regime_map = np.zeros(len(returns))
    regime_map[normal_mask] = 0
    regime_map[volatile_mask & ~normal_mask] = 1
    regime_map[trending_mask & ~normal_mask & ~volatile_mask] = 2
    regime_map[mean_reverting_mask & ~normal_mask & ~volatile_mask & ~trending_mask] = 3
    
    # Add padding
    regimes = np.pad(regime_map, (window-1, 0), mode='constant')
    
    return regimes
