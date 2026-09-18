"""
Feature Extraction for Regime Detection

This module provides feature extraction methods to identify market regimes
from price, volume, and other market data.
"""

import numpy as np
from typing import Dict, List, Tuple
from scipy import stats
from scipy.stats import skew, kurtosis
from collections import deque


class RegimeFeatureExtractor:
    """
    Extract features for market regime detection.
    
    Features are based on statistical properties of price changes, volume patterns,
    and market microstructure characteristics.
    
    Parameters
    ----------
    lookback : int, optional
        Lookback window for feature calculation. Default: 20
    
    Examples
    --------
    >>> extractor = RegimeFeatureExtractor(lookback=20)
    >>> features = extractor.extract_features(returns, volumes)
    >>> features['volatility']
    0.015
    """
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
        self.feature_history = deque(maxlen=lookback)
    
    def extract_features(self, returns: np.ndarray, 
                         volumes: np.ndarray = None,
                         prices: np.ndarray = None) -> Dict[str, float]:
        """
        Extract comprehensive set of regime features.
        
        Parameters
        ----------
        returns : np.ndarray
            Daily returns series
        volumes : np.ndarray, optional
            Volume series
        prices : np.ndarray, optional
            Price series
        
        Returns
        -------
        features : dict
            Dictionary of feature values
        """
        features = {}
        
        # Basic return statistics
        features.update(self._extract_return_features(returns))
        
        # Volume features (if volumes provided)
        if volumes is not None:
            features.update(self._extract_volume_features(volumes, returns))
        
        # Price-based features (if prices provided)
        if prices is not None:
            features.update(self._extract_price_features(prices, returns))
        
        # Volatility features
        features.update(self._extract_volatility_features(returns))
        
        # Autocorrelation features
        features.update(self._extract_autocorrelation_features(returns))
        
        # Higher moments
        features.update(self._extract_moments(returns))
        
        self.feature_history.append(features)
        return features
    
    def _extract_return_features(self, returns: np.ndarray) -> Dict[str, float]:
        """Extract return-based features."""
        features = {}
        
        # Recent average return
        features['recent_mean_return'] = np.mean(returns[-self.lookback:])
        
        # Return volatility
        features['recent_volatility'] = np.std(returns[-self.lookback:])
        
        # Skewness
        features['skewness'] = skew(returns)
        
        # Kurtosis
        features['kurtosis'] = kurtosis(returns)
        
        # Range (max - min)
        features['range'] = np.max(returns) - np.min(returns)
        
        # Average absolute returns
        features['avg_abs_return'] = np.mean(np.abs(returns))
        
        return features
    
    def _extract_volume_features(self, volumes: np.ndarray, 
                                  returns: np.ndarray) -> Dict[str, float]:
        """Extract volume-based features."""
        features = {}
        
        # Recent average volume
        features['recent_avg_volume'] = np.mean(volumes[-self.lookback:])
        
        # Volume ratio
        features['volume_ratio'] = np.mean(volumes[-self.lookback:]) / np.mean(volumes[:len(volumes)-self.lookback])
        
        # Volume volatility
        features['volume_volatility'] = np.std(volumes[-self.lookback:])
        
        # Volume-returns correlation
        if len(volumes) == len(returns):
            correlation = np.corrcoef(volumes[-self.lookback:], returns[-self.lookback:])[0, 1]
            features['volume_return_correlation'] = correlation if not np.isnan(correlation) else 0
        
        return features
    
    def _extract_price_features(self, prices: np.ndarray, 
                                 returns: np.ndarray) -> Dict[str, float]:
        """Extract price-based features."""
        features = {}
        
        # Price trend (slope)
        if len(prices) >= self.lookback:
            x = np.arange(self.lookback)
            slope, _, _, _, _ = stats.linregress(x, prices[-self.lookback:])
            features['price_slope'] = slope
        
        # Price relative to moving average
        if len(prices) >= self.lookback:
            ma = np.mean(prices[-self.lookback:])
            features['price_to_ma_ratio'] = prices[-1] / ma
        
        return features
    
    def _extract_volatility_features(self, returns: np.ndarray) -> Dict[str, float]:
        """Extract volatility-based features."""
        features = {}
        
        # Rolling standard deviation
        rolling_std = np.std(returns[-self.lookback:])
        features['recent_volatility'] = rolling_std
        
        # Rolling maximum
        features['recent_max_volatility'] = np.max(np.std(returns[-self.lookback*5:]))
        
        # Rolling minimum
        features['recent_min_volatility'] = np.min(np.std(returns[-self.lookback*5:]))
        
        # Volatility ratio (max/min)
        features['volatility_ratio'] = features['recent_max_volatility'] / features['recent_min_volatility']
        
        # Volatility change
        if len(returns) >= self.lookback * 2:
            features['volatility_change'] = np.std(returns[-self.lookback:]) - np.std(returns[-self.lookback*2:-self.lookback])
        
        return features
    
    def _extract_autocorrelation_features(self, returns: np.ndarray) -> Dict[str, float]:
        """Extract autocorrelation features."""
        features = {}
        
        # 1-day autocorrelation
        if len(returns) >= 2:
            acf_1 = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            features['autocorr_1'] = acf_1 if not np.isnan(acf_1) else 0
        
        # 3-day autocorrelation
        if len(returns) >= 4:
            acf_3 = np.corrcoef(returns[:-3], returns[3:])[0, 1]
            features['autocorr_3'] = acf_3 if not np.isnan(acf_3) else 0
        
        # 7-day autocorrelation
        if len(returns) >= 8:
            acf_7 = np.corrcoef(returns[:-7], returns[7:])[0, 1]
            features['autocorr_7'] = acf_7 if not np.isnan(acf_7) else 0
        
        return features
    
    def _extract_moments(self, returns: np.ndarray) -> Dict[str, float]:
        """Extract higher moments of returns distribution."""
        features = {}
        
        # Skewness (already in return features)
        features['skewness'] = skew(returns)
        
        # Kurtosis (already in return features)
        features['kurtosis'] = kurtosis(returns)
        
        # Tail ratio (|max|/|min|)
        features['tail_ratio'] = np.abs(np.max(returns)) / np.abs(np.min(returns))
        
        # Outlier count (returns beyond 3 sigma)
        std = np.std(returns)
        if std > 0:
            outliers = np.sum(np.abs(returns) > 3 * std)
            features['outlier_count'] = outliers
        
        return features
    
    def extract_trend_features(self, returns: np.ndarray) -> Dict[str, float]:
        """
        Extract trend-based features.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        
        Returns
        -------
        features : dict
            Trend features
        """
        features = {}
        
        # Linear trend slope
        x = np.arange(len(returns))
        slope, _, _, _, _ = stats.linregress(x, returns)
        features['trend_slope'] = slope
        
        # R-squared of linear fit
        y_pred = slope * x + np.mean(returns)
        ss_res = np.sum((returns - y_pred)**2)
        ss_tot = np.sum((returns - np.mean(returns))**2)
        features['trend_r2'] = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Percentage gain over period
        features['total_return'] = (returns[-1] / returns[0] - 1) * 100 if len(returns) > 1 else 0
        
        # Number of upward/downward days
        upward_days = np.sum(returns > 0)
        downward_days = np.sum(returns < 0)
        features['upward_days_ratio'] = upward_days / len(returns) if len(returns) > 0 else 0
        features['downward_days_ratio'] = downward_days / len(returns) if len(returns) > 0 else 0
        
        return features
    
    def extract_volatility_features(self, returns: np.ndarray) -> Dict[str, float]:
        """
        Extract volatility-specific features.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        
        Returns
        -------
        features : dict
            Volatility features
        """
        features = {}
        
        # Historical volatility (rolling std)
        features['volatility'] = np.std(returns)
        
        # Volatility of volatility (rolling std of rolling std)
        rolling_std = np.array([np.std(returns[max(0, i-20):i+1]) for i in range(len(returns))])
        features['volatility_of_volatility'] = np.std(rolling_std)
        
        # Realized volatility (square root of sum of squared returns)
        features['realized_volatility'] = np.sqrt(np.sum(returns**2))
        
        # Average true range
        features['atr'] = self._calculate_atr(returns)
        
        return features
    
    def _calculate_atr(self, returns: np.ndarray, window: int = 14) -> float:
        """Calculate Average True Range (ATR)."""
        # Convert returns to price changes
        price_changes = np.abs(np.diff(returns))
        
        if len(price_changes) < window:
            return np.mean(price_changes)
        
        atr = np.convolve(price_changes, np.ones(window)/window, mode='valid')
        atr = np.concatenate([np.full(window-1, atr[0]), atr])
        
        return atr[-1]


class RegimeClassifier:
    """
    Classify market regimes based on extracted features.
    
    This is a rule-based classifier that categorizes markets into different regimes
    based on predefined thresholds.
    
    Examples
    --------
    >>> classifier = RegimeClassifier()
    >>> regimes = classifier.classify(features)
    >>> regimes['label']
    'bullish'
    """
    
    def __init__(self):
        self.regime_labels = {
            0: 'normal',
            1: 'bullish',
            2: 'bearish',
            3: 'volatile',
            4: 'trending',
            5: 'mean_reverting'
        }
    
    def classify(self, features: Dict[str, float]) -> Dict[str, str]:
        """
        Classify market regime based on features.
        
        Parameters
        ----------
        features : dict
            Extracted features
        
        Returns
        -------
        regime : dict
            Dictionary with regime label and confidence
        """
        regime = {}
        
        # Basic classification rules
        if features.get('recent_volatility', 0) > features.get('recent_min_volatility', 1) * 1.5:
            regime['label'] = 'volatile'
        else:
            regime['label'] = 'normal'
        
        # Trend classification
        if features.get('trend_slope', 0) > 0.0005:
            regime['label'] = 'bullish'
        elif features.get('trend_slope', 0) < -0.0005:
            regime['label'] = 'bearish'
        
        # Volatility-enhanced regimes
        if regime['label'] == 'bullish' and features.get('recent_volatility', 0) > 0.02:
            regime['label'] = 'volatile_bullish'
        elif regime['label'] == 'bearish' and features.get('recent_volatility', 0) > 0.02:
            regime['label'] = 'volatile_bearish'
        
        # Mean reversion detection
        autocorr = features.get('autocorr_1', 0)
        if autocorr < -0.1:
            regime['label'] = 'mean_reverting'
        
        # Trending detection
        autocorr_pos = features.get('autocorr_7', 0)
        if autocorr_pos > 0.1:
            regime['label'] = 'trending'
        
        regime['confidence'] = 0.7  # Base confidence
        
        return regime
    
    def classify_series(self, features_series: List[Dict[str, float]]) -> List[Dict[str, str]]:
        """
        Classify a series of feature sets.
        
        Parameters
        ----------
        features_series : list of dict
            List of extracted feature dictionaries
        
        Returns
        -------
        regimes : list of dict
            List of regime classifications
        """
        return [self.classify(features) for features in features_series]
