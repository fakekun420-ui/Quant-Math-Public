"""
Volatility Clustering Analysis

This module provides methods to detect and analyze volatility clustering in financial time series,
including ARCH and GARCH models for conditional variance estimation.
"""

import numpy as np
from scipy import stats
from typing import Tuple, Optional
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
from arch.univariate import ARCH, GARCH, EWMAVariance
from arch.unitroot import EngleVolatilityTest
from arch.univariate.conditional_volatility_model import ConditionalVolatilityModel
from arch.unitroot import EngleVolatilityTest


class VolatilityClusteringAnalyzer:
    """
    Analyze volatility clustering patterns in financial time series.
    
    Volatility clustering is the observation that large changes in asset prices
    tend to be followed by large changes, and small changes tend to be followed by small changes.
    
    Parameters
    ----------
    window : int, optional
        Rolling window size for volatility estimation. Default: 20
    
    Examples
    --------
    >>> analyzer = VolatilityClusteringAnalyzer(window=20)
    >>> vol = analyzer.calculate_volatility(returns)
    >>> arch_effects = analyzer.test_arch_effects(returns)
    """
    
    def __init__(self, window: int = 20):
        self.window = window
        self.rolling_volatility = None
        self.high_volatility_periods = None
    
    def calculate_volatility(self, returns: np.ndarray, method: str = 'rolling_std') -> np.ndarray:
        """
        Calculate rolling volatility.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        method : str, optional
            Method for volatility calculation. Options:
            - 'rolling_std': Standard rolling standard deviation
            - 'ewma': Exponentially weighted moving average
            - 'garbahi': GARCH(1,1) conditional variance
        
        Returns
        -------
        volatility : np.ndarray
            Volatility series
        """
        if method == 'rolling_std':
            volatility = np.convolve(returns**2, np.ones(self.window)/self.window, mode='valid')**0.5
        elif method == 'ewma':
            volatility = self._ewma_volatility(returns)
        elif method == 'garbahi':
            volatility = self._garbahi_volatility(returns)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Pad with initial volatility
        if method != 'garbahi':
            initial_vol = np.std(returns[:self.window])
            volatility = np.concatenate([np.full(self.window - 1, initial_vol), volatility])
        
        self.rolling_volatility = volatility
        return volatility
    
    def _ewma_volatility(self, returns: np.ndarray) -> np.ndarray:
        """Calculate exponentially weighted moving average volatility."""
        T = len(returns)
        ewma = np.zeros(T)
        lambda_ = 0.94  # Standard lambda for EWMA
        
        for i in range(T):
            if i == 0:
                ewma[i] = returns[i]**2
            else:
                ewma[i] = lambda_ * ewma[i-1] + (1 - lambda_) * returns[i]**2
        
        return np.sqrt(ewma)
    
    def _garbahi_volatility(self, returns: np.ndarray) -> np.ndarray:
        """Calculate GARCH(1,1) conditional volatility."""
        model = GARCH(p=1, q=1)
        model.fit(returns)
        conditional_vol = model.conditional_volatility
        
        # Pad with initial volatility
        initial_vol = np.std(returns[:self.window])
        padded_vol = np.concatenate([np.full(self.window - 1, initial_vol), conditional_vol])
        
        return padded_vol
    
    def detect_volatility_clustering(self, returns: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
        """
        Detect volatility clusters using rolling volatility.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        threshold : float, optional
            Volatility threshold. If None, uses 1.5x standard deviation of volatility
        
        Returns
        -------
        clusters : np.ndarray
            Volatility cluster indicator (0: normal, 1: high volatility)
        """
        volatility = self.calculate_volatility(returns)
        
        if threshold is None:
            threshold = np.mean(volatility) + 0.5 * np.std(volatility)
        
        clusters = (volatility >= threshold).astype(int)
        self.high_volatility_periods = clusters
        
        return clusters
    
    def test_arch_effects(self, returns: np.ndarray, max_lag: int = 20) -> Tuple[float, float]:
        """
        Test for ARCH effects (autoregressive conditional heteroskedasticity).
        
        The Engle's ARCH test checks whether squared returns are autocorrelated,
        indicating volatility clustering.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        max_lag : int, optional
            Maximum lag for test. Default: 20
        
        Returns
        -------
        lb_stat : float
            Ljung-Box statistic
        p_value : float
            P-value for the test
        """
        # Test squared returns for autocorrelation
        squared_returns = returns**2
        lb_stat, p_value = acorr_ljungbox(squared_returns, lags=max_lag, return_df=False)
        
        return float(lb_stat[-1]), float(p_value[-1])
    
    def is_volatility_clustering_present(self, returns: np.ndarray, max_lag: int = 20) -> bool:
        """
        Check if ARCH effects are present (indicating volatility clustering).
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        max_lag : int, optional
            Maximum lag for test. Default: 20
        
        Returns
        -------
        has_clustering : bool
            True if ARCH effects are present
        """
        _, p_value = self.test_arch_effects(returns, max_lag)
        return p_value < 0.05
    
    def calculate_volatility_ratio(self, high_vol_clusters: np.ndarray, 
                                   low_vol_clusters: np.ndarray) -> float:
        """
        Calculate the ratio of high volatility variance to low volatility variance.
        
        Parameters
        ----------
        high_vol_clusters : np.ndarray
            High volatility cluster indicator
        low_vol_clusters : np.ndarray
            Low volatility cluster indicator
        
        Returns
        -------
        ratio : float
            Variance ratio
        """
        high_vol_var = np.var(returns[high_vol_clusters == 1])
        low_vol_var = np.var(returns[low_vol_clusters == 0])
        
        return high_vol_var / low_vol_var if low_vol_var > 0 else float('inf')
    
    def get_volatility_statistics(self, returns: np.ndarray, 
                                  high_vol_threshold: Optional[float] = None) -> dict:
        """
        Get comprehensive volatility statistics.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        high_vol_threshold : float, optional
            Threshold for high volatility. If None, uses 1.5x standard deviation
        
        Returns
        -------
        stats : dict
            Dictionary with volatility statistics
        """
        vol = self.calculate_volatility(returns)
        
        if high_vol_threshold is None:
            high_vol_threshold = np.mean(vol) + 0.5 * np.std(vol)
        
        high_vol = vol >= high_vol_threshold
        low_vol = vol < high_vol_threshold
        
        stats = {
            'mean_volatility': np.mean(vol),
            'std_volatility': np.std(vol),
            'min_volatility': np.min(vol),
            'max_volatility': np.max(vol),
            'high_volatility_mean': np.mean(vol[high_vol]),
            'low_volatility_mean': np.mean(vol[low_vol]),
            'high_volatility_count': np.sum(high_vol),
            'low_volatility_count': np.sum(low_vol),
            'volatility_ratio': self.calculate_volatility_ratio(high_vol, low_vol),
            'arch_test_p_value': self.test_arch_effects(returns)[1],
            'has_clustering': self.is_volatility_clustering_present(returns)
        }
        
        return stats
    
    def plot_volatility_clusters(self, returns: np.ndarray, 
                                  threshold: Optional[float] = None,
                                  figsize: Tuple[int, int] = (14, 6)):
        """
        Plot returns and volatility clusters.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        threshold : float, optional
            Volatility threshold
        figsize : tuple, optional
            Figure size
        """
        import matplotlib.pyplot as plt
        
        vol = self.calculate_volatility(returns)
        
        if threshold is None:
            threshold = np.mean(vol) + 0.5 * np.std(vol)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)
        
        ax1.plot(returns, label='Returns', color='blue')
        ax1.axhline(y=threshold, color='r', linestyle='--', label='High Vol Threshold')
        ax1.set_title('Returns with Volatility Clusters')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2.plot(vol, label='Volatility', color='orange', linewidth=2)
        ax2.fill_between(range(len(vol)), threshold, vol, where=(vol >= threshold),
                         color='red', alpha=0.3, label='High Volatility')
        ax2.set_title('Rolling Volatility')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()


class GARCHModel:
    """
    GARCH (Generalized Autoregressive Conditional Heteroskedasticity) model.
    
    GARCH models are widely used to model and forecast volatility clustering.
    This implementation uses the ARCH library.
    
    Parameters
    ----------
    p : int, optional
            Number of lagged squared returns (ARCH terms). Default: 1
    q : int, optional
            Number of lagged conditional variances (GARCH terms). Default: 1
    mean_model : str, optional
            Mean model. Default: 'Constant'
    dist : str, optional
            Distribution for innovations. Default: 'normal'
    
    Examples
    --------
    >>> garch = GARCHModel(p=1, q=1)
    >>> results = garch.fit(returns)
    >>> forecast = garch.forecast(horizon=10)
    """
    
    def __init__(self, p: int = 1, q: int = 1, mean_model: str = 'Constant', 
                 dist: str = 'normal'):
        self.p = p
        self.q = q
        self.mean_model = mean_model
        self.dist = dist
        self.model = None
        self.results = None
    
    def fit(self, returns: np.ndarray, update_freq: int = 1, 
            disp: str = 'off') -> 'GARCHModel':
        """
        Fit GARCH model to returns.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        update_freq : int, optional
            Update frequency. Default: 1
        disp : str, optional
            Display output. Default: 'off'
        
        Returns
        -------
        self : GARCHModel
            Fitted model
        """
        self.model = GARCH(p=self.p, q=self.q)
        self.model.fit(returns, update_freq=update_freq, disp=disp)
        self.results = self.model
        
        return self
    
    def forecast(self, horizon: int = 1) -> dict:
        """
        Forecast conditional variance.
        
        Parameters
        ----------
        horizon : int, optional
            Forecast horizon. Default: 1
        
        Returns
        -------
        forecast : dict
            Dictionary with forecast results
        """
        if self.results is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        forecast = self.results.forecast(horizon=horizon)
        
        return {
            'variance_forecast': forecast.variance.values[-1, :],
            'volatility_forecast': np.sqrt(forecast.variance.values[-1, :]),
            'confidence_intervals': forecast.conf_int()
        }
    
    def summary(self) -> str:
        """
        Get model summary.
        
        Returns
        -------
        summary : str
            Model summary
        """
        if self.results is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        return str(self.results.summary())


class EWMAVolatility:
    """
    Exponentially Weighted Moving Average (EWMA) volatility.
    
    EWMA volatility gives more weight to recent observations, making it
    responsive to changing market conditions.
    
    Parameters
    ----------
    lambda_ : float, optional
            Decay factor (0 < lambda_ < 1). Default: 0.94
            Lower lambda_ = more weight to recent observations
    
    Examples
    --------
    >>> ewma = EWMAVolatility(lambda_=0.94)
    >>> vol = ewma.calculate_volatility(returns)
    """
    
    def __init__(self, lambda_: float = 0.94):
        self.lambda_ = lambda_
    
    def calculate_volatility(self, returns: np.ndarray) -> np.ndarray:
        """
        Calculate EWMA volatility.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        
        Returns
        -------
        volatility : np.ndarray
            EWMA volatility series
        """
        T = len(returns)
        ewma = np.zeros(T)
        
        for i in range(T):
            if i == 0:
                ewma[i] = returns[i]**2
            else:
                ewma[i] = self.lambda_ * ewma[i-1] + (1 - self.lambda_) * returns[i]**2
        
        return np.sqrt(ewma)
    
    def update(self, new_return: float, previous_volatility: float) -> float:
        """
        Update volatility with new observation.
        
        Parameters
        ----------
        new_return : float
            New return observation
        previous_volatility : float
            Previous volatility estimate
        
        Returns
        -------
        updated_volatility : float
            Updated volatility
        """
        new_squared_return = new_return**2
        updated_variance = self.lambda_ * previous_volatility**2 + (1 - self.lambda_) * new_squared_return
        return np.sqrt(updated_variance)
