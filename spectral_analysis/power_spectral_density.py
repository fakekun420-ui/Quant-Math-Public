"""
Power Spectral Density (PSD)

This module provides Power Spectral Density estimation using
Welch's method and other spectral estimation techniques.
"""

import numpy as np
from typing import Tuple, Optional
from scipy import signal
from statsmodels.stats.diagnostic import acorr_ljungbox


class PowerSpectralDensity:
    """
    Power Spectral Density (PSD) analyzer.
    
    This class computes PSD using Welch's method and other techniques
    to analyze frequency content of time series data.
    
    Parameters
    ----------
    fs : float, optional
        Sampling frequency (Hz). Default: 1.0
    nperseg : int, optional
        Length of each segment. Default: 256
    noverlap : int, optional
        Number of overlapping points. Default: 128
    
    Examples
    --------
    >>> psd = PowerSpectralDensity(fs=1000, nperseg=256)
    >>> freqs, power = psd.compute_psd(time_series)
    >>> psd.plot_psd(time_series)
    """
    
    def __init__(self, fs: float = 1.0, nperseg: int = 256, noverlap: int = 128):
        self.fs = fs
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.freqs = None
        self.power = None
    
    def compute_psd(self, data: np.ndarray, 
                    method: str = 'welch') -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Power Spectral Density.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use ('welch', 'periodogram', 'mls'). Default: 'welch'
        
        Returns
        -------
        freqs : np.ndarray
            Frequency axis
        power : np.ndarray
            Power spectral density
        """
        if method == 'welch':
            freqs, power = signal.welch(data, fs=self.fs, 
                                        nperseg=self.nperseg, 
                                        noverlap=self.noverlap)
        elif method == 'periodogram':
            freqs, power = signal.periodogram(data, fs=self.fs)
        elif method == 'mls':
            freqs, power = signal.welch(data, fs=self.fs, 
                                        nperseg=self.nperseg,
                                        noverlap=self.noverlap,
                                        scaling='spectrum')
        else:
            raise ValueError(f"Unknown method: {method}")
        
        self.freqs = freqs
        self.power = power
        
        return freqs, power
    
    def compute_psd_density(self, data: np.ndarray, 
                           method: str = 'welch') -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute PSD density (power per unit frequency).
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use. Default: 'welch'
        
        Returns
        -------
        freqs : np.ndarray
            Frequency axis
        power_density : np.ndarray
            PSD density
        """
        freqs, power = self.compute_psd(data, method)
        power_density = power / self.fs
        return freqs, power_density
    
    def compute_spectral_centroid(self, data: np.ndarray, 
                                  method: str = 'welch') -> float:
        """
        Compute spectral centroid.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use. Default: 'welch'
        
        Returns
        -------
        centroid : float
            Spectral centroid (Hz)
        """
        freqs, power = self.compute_psd(data, method)
        centroid = np.sum(freqs * power) / np.sum(power)
        return centroid
    
    def compute_spectral_bandwidth(self, data: np.ndarray,
                                   method: str = 'welch') -> float:
        """
        Compute spectral bandwidth.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use. Default: 'welch'
        
        Returns
        -------
        bandwidth : float
            Spectral bandwidth
        """
        freqs, power = self.compute_psd(data, method)
        centroid = np.sum(freqs * power) / np.sum(power)
        variance = np.sum((freqs - centroid) ** 2 * power) / np.sum(power)
        bandwidth = np.sqrt(variance)
        return bandwidth
    
    def compute_spectral_rolloff(self, data: np.ndarray,
                                 method: str = 'welch',
                                 cutoff: float = 0.95) -> float:
        """
        Compute spectral rolloff.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use. Default: 'welch'
        cutoff : float, optional
            Percentage of total power. Default: 0.95
        
        Returns
        -------
        rolloff : float
            Spectral rolloff frequency (Hz)
        """
        freqs, power = self.compute_psd(data, method)
        total_power = np.sum(power)
        cumulative_power = np.cumsum(power)
        rolloff_idx = np.where(cumulative_power >= cutoff * total_power)[0]
        
        if len(rolloff_idx) == 0:
            return freqs[-1]
        
        return freqs[rolloff_idx[0]]
    
    def compute_spectral_flux(self, data1: np.ndarray, 
                              data2: np.ndarray,
                              method: str = 'welch') -> float:
        """
        Compute spectral flux between two signals.
        
        Parameters
        ----------
        data1 : np.ndarray
            First time series
        data2 : np.ndarray
            Second time series
        method : str, optional
            Method to use. Default: 'welch'
        
        Returns
        -------
        flux : float
            Spectral flux
        """
        _, power1 = self.compute_psd(data1, method)
        _, power2 = self.compute_psd(data2, method)
        
        flux = np.sqrt(np.sum((power2 - power1) ** 2) / np.sum(power1 ** 2))
        return flux
    
    def detect_flicker_noise(self, data: np.ndarray,
                            method: str = 'welch',
                            n_lags: int = 10) -> float:
        """
        Detect 1/f noise characteristics.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        method : str, optional
            Method to use. Default: 'welch'
        n_lags : int, optional
            Number of lags for autocorrelation. Default: 10
        
        Returns
        -------
        log_slope : float
            Log-slope of power spectrum (flicker noise indicator)
        """
        freqs, power = self.compute_psd(data, method)
        
        # Use log-log slope
        mask = (freqs > 0) & (freqs < np.max(freqs) * 0.9)
        log_freq = np.log(freqs[mask])
        log_power = np.log(power[mask])
        
        # Fit line
        coeffs = np.polyfit(log_freq, log_power, 1)
        log_slope = coeffs[0]
        
        return log_slope
    
    def plot_psd(self, data: np.ndarray,
                 figsize: Tuple[int, int] = (12, 5),
                 method: str = 'welch',
                 log_scale: bool = True,
                 title: str = 'Power Spectral Density'):
        """
        Plot Power Spectral Density.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        figsize : tuple, optional
            Figure size
        method : str, optional
            Method to use. Default: 'welch'
        log_scale : bool, optional
            Use log scale for power. Default: True
        title : str, optional
            Plot title
        """
        import matplotlib.pyplot as plt
        freqs, power = self.compute_psd(data, method)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # PSD
        ax1.plot(freqs, power, 'b-')
        ax1.set_title('Power Spectral Density')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Power')
        ax1.grid(True, alpha=0.3)
        
        if log_scale:
            ax2.loglog(freqs, power, 'b-')
            ax2.set_title('Power Spectral Density (Log-Log)')
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Power')
            ax2.grid(True, alpha=0.3)
        else:
            ax2.plot(freqs, power, 'b-')
            ax2.set_title('Power Spectral Density (Linear)')
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Power')
            ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def plot_psd_multi_signal(self, data_list: list,
                             labels: Optional[list] = None,
                             figsize: Tuple[int, int] = (12, 5),
                             log_scale: bool = True,
                             title: str = 'Power Spectral Density Comparison'):
        """
        Plot PSD for multiple signals.
        
        Parameters
        ----------
        data_list : list
            List of time series data
        labels : list, optional
            Labels for each signal
        figsize : tuple, optional
            Figure size
        log_scale : bool, optional
            Use log scale for power. Default: True
        title : str, optional
            Plot title
        """
        import matplotlib.pyplot as plt
        if labels is None:
            labels = [f'Signal {i}' for i in range(len(data_list))]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        for data, label in zip(data_list, labels):
            freqs, power = self.compute_psd(data)
            ax1.plot(freqs, power, label=label)
            
            if log_scale:
                ax2.loglog(freqs, power, label=label)
            else:
                ax2.plot(freqs, power, label=label)
        
        ax1.set_title('Power Spectral Density')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Power')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2.set_title('Power Spectral Density (Log-Log)')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Power')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def get_bandpower(self, data: np.ndarray, 
                      low_freq: float,
                      high_freq: float,
                      method: str = 'welch') -> float:
        """
        Get power in frequency band.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        low_freq : float
            Lower frequency bound (Hz)
        high_freq : float
            Upper frequency bound (Hz)
        method : str, optional
            Method to use. Default: 'welch'
        
        Returns
        -------
        power : float
            Power in frequency band
        """
        freqs, power = self.compute_psd(data, method)
        
        mask = (freqs >= low_freq) & (freqs <= high_freq)
        band_power = np.trapz(power[mask], freqs[mask])
        
        return band_power
