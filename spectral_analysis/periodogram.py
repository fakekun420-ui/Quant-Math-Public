"""
Periodogram Analysis

This module provides periodogram-based frequency analysis for
identifying periodic patterns and seasonal components in time series.
"""

import numpy as np
from typing import Tuple, Dict, Optional
from scipy import signal
from scipy.signal import periodogram
from statsmodels.tsa.stattools import acf


class PeriodogramAnalyzer:
    """
    Periodogram analyzer.
    
    This class performs periodogram analysis to identify periodic
    components and seasonal patterns in time series data.
    
    Parameters
    ----------
    fs : float, optional
        Sampling frequency (Hz). Default: 1.0
    nperseg : int, optional
        Number of samples per segment. Default: 256
    
    Examples
    --------
    >>> analyzer = PeriodogramAnalyzer(fs=1000, nperseg=256)
    >>> freqs, power = analyzer.compute_periodogram(time_series)
    >>> analyzer.plot_periodogram(time_series)
    """
    
    def __init__(self, fs: float = 1.0, nperseg: int = 256):
        self.fs = fs
        self.nperseg = nperseg
        self.freqs = None
        self.power = None
    
    def compute_periodogram(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute periodogram.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        
        Returns
        -------
        freqs : np.ndarray
            Frequency axis
        power : np.ndarray
            Power spectrum
        """
        freqs, power = periodogram(data, fs=self.fs, nperseg=self.nperseg)
        
        self.freqs = freqs
        self.power = power
        
        return freqs, power
    
    def compute_smoothed_periodogram(self, data: np.ndarray, 
                                     window_size: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute smoothed periodogram using moving average.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        window_size : int, optional
            Window size for smoothing. Default: 5
        
        Returns
        -------
        freqs : np.ndarray
            Frequency axis
        power : np.ndarray
            Smoothed power spectrum
        """
        freqs, power = self.compute_periodogram(data)
        
        if len(power) < window_size:
            return freqs, power
        
        # Apply moving average
        smoothed = np.convolve(power, np.ones(window_size) / window_size, mode='same')
        
        return freqs, smoothed
    
    def detect_periodicities(self, data: np.ndarray, 
                             min_period: float = 0.0,
                             max_period: float = np.inf,
                             confidence: float = 0.95) -> list:
        """
        Detect significant periodicities in the data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        min_period : float, optional
            Minimum period to consider. Default: 0.0
        max_period : float, optional
            Maximum period to consider. Default: inf
        confidence : float, optional
            Confidence level for detection. Default: 0.95
        
        Returns
        -------
        periods : list
            List of detected periods with metadata
        """
        freqs, power = self.compute_periodogram(data)
        
        # Convert frequencies to periods
        periods = 1.0 / freqs
        
        # Filter by period range
        mask = (periods >= min_period) & (periods <= max_period)
        valid_periods = periods[mask]
        valid_power = power[mask]
        
        # Calculate significance threshold
        total_power = np.sum(valid_power)
        significance_threshold = confidence * total_power
        
        detected = []
        
        for period, pw in zip(valid_periods, valid_power):
            if pw > significance_threshold:
                detected.append({
                    'period': period,
                    'frequency': 1.0 / period,
                    'power': pw,
                    'significance': pw / total_power
                })
        
        # Sort by power
        detected.sort(key=lambda x: x['power'], reverse=True)
        
        return detected
    
    def detect_seasonality(self, data: np.ndarray,
                          min_period: float = 1.0,
                          max_period: float = 365.0,
                          confidence: float = 0.95) -> Dict:
        """
        Detect seasonality in the data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        min_period : float, optional
            Minimum period to consider. Default: 1.0
        max_period : float, optional
            Maximum period to consider. Default: 365.0
        confidence : float, optional
            Confidence level for detection. Default: 0.95
        
        Returns
        -------
        analysis : dict
            Seasonality analysis results
        """
        detected = self.detect_periodicities(data, min_period, max_period, confidence)
        
        analysis = {
            'has_seasonality': len(detected) > 0,
            'dominant_period': detected[0]['period'] if detected else None,
            'dominant_frequency': detected[0]['frequency'] if detected else None,
            'detected_periods': detected
        }
        
        return analysis
    
    def compute_spectral_flatness(self, data: np.ndarray,
                                 method: str = 'periodogram') -> float:
        """
        Compute spectral flatness.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use ('periodogram', 'welch'). Default: 'periodogram'
        
        Returns
        -------
        flatness : float
            Spectral flatness (0 to 1)
        """
        if method == 'periodogram':
            freqs, power = self.compute_periodogram(data)
        elif method == 'welch':
            freqs, power = signal.welch(data, fs=self.fs, nperseg=self.nperseg)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Harmonic mean / Geometric mean
        geometric_mean = np.exp(np.mean(np.log(power + 1e-10)))
        arithmetic_mean = np.mean(power)
        
        flatness = geometric_mean / (arithmetic_mean + 1e-10)
        
        return flatness
    
    def compute_spectral_kurtosis(self, data: np.ndarray,
                                  method: str = 'periodogram') -> float:
        """
        Compute spectral kurtosis.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use ('periodogram', 'welch'). Default: 'periodogram'
        
        Returns
        -------
        kurtosis : float
            Spectral kurtosis
        """
        if method == 'periodogram':
            freqs, power = self.compute_periodogram(data)
        elif method == 'welch':
            freqs, power = signal.welch(data, fs=self.fs, nperseg=self.nperseg)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        mean = np.mean(power)
        std = np.std(power)
        centered_power = (power - mean) / (std + 1e-10)
        
        kurtosis = np.mean(centered_power ** 4)
        
        return kurtosis
    
    def compute_auto_spectral_correlation(self, data: np.ndarray,
                                          max_lag: int = 10) -> np.ndarray:
        """
        Compute auto-correlation of power spectrum.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        max_lag : int, optional
            Maximum lag for correlation. Default: 10
        
        Returns
        -------
        correlation : np.ndarray
            Auto-correlation coefficients
        """
        freqs, power = self.compute_periodogram(data)
        
        # Normalize power
        power_norm = power / np.sum(power)
        
        # Compute auto-correlation
        correlation = np.zeros(max_lag)
        
        for lag in range(max_lag):
            shifted = np.roll(power_norm, lag)
            shifted[:lag] = 0
            correlation[lag] = np.sum(power_norm * shifted)
        
        return correlation
    
    def plot_periodogram(self, data: np.ndarray,
                         figsize: Tuple[int, int] = (12, 5),
                         log_scale: bool = True,
                         title: str = 'Periodogram'):
        """
        Plot periodogram.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        figsize : tuple, optional
            Figure size
        log_scale : bool, optional
            Use log scale for power. Default: True
        title : str, optional
            Plot title
        """
        import matplotlib.pyplot as plt
        freqs, power = self.compute_periodogram(data)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # Periodogram
        ax1.plot(freqs, power, 'b-')
        ax1.set_title('Periodogram')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Power')
        ax1.grid(True, alpha=0.3)
        
        # Log-log scale
        if log_scale:
            ax2.loglog(freqs, power, 'b-')
            ax2.set_title('Periodogram (Log-Log)')
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Power')
            ax2.grid(True, alpha=0.3)
        else:
            ax2.plot(freqs, power, 'b-')
            ax2.set_title('Periodogram (Linear)')
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Power')
            ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def plot_smoothed_periodogram(self, data: np.ndarray,
                                  window_size: int = 5,
                                  figsize: Tuple[int, int] = (12, 5),
                                  log_scale: bool = True,
                                  title: str = 'Smoothed Periodogram'):
        """
        Plot smoothed periodogram.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        window_size : int, optional
            Window size for smoothing. Default: 5
        figsize : tuple, optional
            Figure size
        log_scale : bool, optional
            Use log scale for power. Default: True
        title : str, optional
            Plot title
        """
        import matplotlib.pyplot as plt
        freqs, power = self.compute_smoothed_periodogram(data, window_size)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Smoothed periodogram
        ax1.plot(freqs, power, 'b-')
        ax1.set_title('Smoothed Periodogram')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Power')
        ax1.grid(True, alpha=0.3)
        
        # Log-log scale
        if log_scale:
            ax2.loglog(freqs, power, 'b-')
            ax2.set_title('Smoothed Periodogram (Log-Log)')
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Power')
            ax2.grid(True, alpha=0.3)
        else:
            ax2.plot(freqs, power, 'b-')
            ax2.set_title('Smoothed Periodogram (Linear)')
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Power')
            ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def plot_detected_periods(self, data: np.ndarray,
                              min_period: float = 1.0,
                              max_period: float = 365.0,
                              confidence: float = 0.95,
                              figsize: Tuple[int, int] = (12, 5),
                              title: str = 'Detected Periodicities'):
        """
        Plot periodogram highlighting detected periodicities.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        min_period : float, optional
            Minimum period. Default: 1.0
        max_period : float, optional
            Maximum period. Default: 365.0
        confidence : float, optional
            Confidence level. Default: 0.95
        figsize : tuple, optional
            Figure size
        title : str, optional
            Plot title
        """
        import matplotlib.pyplot as plt
        freqs, power = self.compute_periodogram(data)

        detected = self.detect_periodicities(data, min_period, max_period, confidence)

        fig, ax = plt.subplots(figsize=figsize)
        
        ax.plot(freqs, power, 'b-', label='Periodogram')
        
        # Highlight detected periods
        for period_info in detected:
            freq = period_info['frequency']
            power = period_info['power']
            ax.plot(freq, power, 'ro', markersize=10, markeredgecolor='black')
            ax.text(freq, power, f'{period_info["period"]:.1f}',
                   fontsize=10, ha='center')
        
        ax.set_title(title)
        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('Power')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
