"""
Continuous Wavelet Transform (CWT)

This module provides Continuous Wavelet Transform for multi-resolution
frequency analysis of time series data.
"""

import numpy as np
from typing import Tuple, Optional
import matplotlib.pyplot as plt
from scipy.signal import cwt, ricker


class ContinuousWaveletTransform:
    """
    Continuous Wavelet Transform (CWT) analyzer.
    
    This class performs CWT analysis to identify time-frequency patterns
    and multi-resolution features in time series data.
    
    Parameters
    ----------
    scales : np.ndarray, optional
        Wavelet scales to compute. Default: logarithmic scale from 1 to 128
    wavelet : str or callable, optional
        Wavelet type ('morlet', 'mexican_hat', 'gaussian'). Default: 'morlet'
    
    Examples
    --------
    >>> cwt = ContinuousWaveletTransform(scales=np.logspace(0, 4, 128))
    >>> coeffs, freqs = cwt.compute_cwt(time_series)
    >>> cwt.plot_cwt(time_series, coeffs, freqs)
    """
    
    def __init__(self, scales: Optional[np.ndarray] = None, 
                 wavelet: str = 'morlet'):
        if scales is None:
            self.scales = np.logspace(0, 4, 128)
        else:
            self.scales = scales
        
        self.wavelet = wavelet
        self.coeffs = None
        self.freqs = None
    
    def get_wavelet_function(self) -> callable:
        """
        Get wavelet function based on type.
        
        Returns
        -------
        wavelet_func : callable
            Wavelet function
        """
        if self.wavelet == 'morlet':
            return lambda x: np.exp(1j * x) * np.exp(-0.5 * x ** 2)
        elif self.wavelet == 'mexican_hat':
            return ricker
        elif self.wavelet == 'gaussian':
            return lambda x: np.exp(-0.5 * x ** 2)
        else:
            raise ValueError(f"Unknown wavelet type: {self.wavelet}")
    
    def compute_cwt(self, data: np.ndarray, 
                    sampling_rate: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Continuous Wavelet Transform.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float, optional
            Sampling rate (Hz). Default: 1.0
        
        Returns
        -------
        coeffs : np.ndarray
            Wavelet coefficients
        freqs : np.ndarray
            Corresponding frequencies
        """
        wavelet_func = self.get_wavelet_function()
        
        # Compute CWT
        if self.wavelet == 'mexican_hat':
            # scipy.signal.cwt expects 1D arrays
            coeffs = cwt(data, ricker, self.scales)
        else:
            coeffs = cwt(data, wavelet_func, self.scales)
        
        self.coeffs = np.abs(coeffs)
        
        # Convert scales to frequencies
        if sampling_rate > 0:
            # Approximate relationship: f = 1 / scale
            self.freqs = 1.0 / self.scales
        else:
            self.freqs = self.scales.copy()
        
        return self.coeffs, self.freqs
    
    def compute_energy_spectrum(self, data: np.ndarray, 
                               sampling_rate: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute energy spectrum from CWT.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float, optional
            Sampling rate (Hz). Default: 1.0
        
        Returns
        -------
        energy : np.ndarray
            Energy spectrum
        freqs : np.ndarray
            Frequencies
        """
        coeffs, freqs = self.compute_cwt(data, sampling_rate)
        energy = np.sum(np.abs(coeffs) ** 2, axis=1)
        return energy, freqs
    
    def detect_transients(self, data: np.ndarray, 
                         sampling_rate: float = 1.0,
                         threshold: float = 1.5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect transient events in the time series.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float, optional
            Sampling rate (Hz). Default: 1.0
        threshold : float, optional
            Threshold for transient detection. Default: 1.5
        
        Returns
        -------
        times : np.ndarray
            Time points of transients
        amplitudes : np.ndarray
            Amplitudes of transients
        """
        coeffs, freqs = self.compute_cwt(data, sampling_rate)
        
        # Find maximum coefficient across all scales at each time point
        max_coeffs = np.max(coeffs, axis=0)
        
        # Detect transients above threshold
        transients = max_coeffs > threshold
        times = np.where(transients)[0]
        amplitudes = max_coeffs[transients]
        
        return times, amplitudes
    
    def plot_cwt(self, data: np.ndarray, 
                 figsize: Tuple[int, int] = (14, 6),
                 title: str = 'Continuous Wavelet Transform'):
        """
        Plot CWT coefficients.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        figsize : tuple, optional
            Figure size
        title : str, optional
            Plot title
        """
        if self.coeffs is None:
            self.compute_cwt(data)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)
        
        # Time series
        ax1.plot(data, 'b-')
        ax1.set_title('Time Series')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Amplitude')
        ax1.grid(True, alpha=0.3)
        
        # CWT heatmap
        extent = [0, len(data), 0, self.freqs[-1]]
        im = ax2.imshow(self.coeffs, aspect='auto', extent=extent,
                       origin='lower', cmap='viridis')
        
        ax2.set_title('CWT Coefficients')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Frequency (Hz)')
        
        cbar = plt.colorbar(im, ax=ax2)
        cbar.set_label('Magnitude')
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def plot_time_frequency_heatmap(self, data: np.ndarray, 
                                    sampling_rate: float = 1.0,
                                    figsize: Tuple[int, int] = (14, 6),
                                    title: str = 'Time-Frequency Heatmap'):
        """
        Plot time-frequency heatmap with CWT coefficients.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float, optional
            Sampling rate (Hz). Default: 1.0
        figsize : tuple, optional
            Figure size
        title : str, optional
            Plot title
        """
        coeffs, freqs = self.compute_cwt(data, sampling_rate)
        
        extent = [0, len(data), freqs[0], freqs[-1]]
        
        fig, ax = plt.subplots(figsize=figsize)
        im = ax.imshow(coeffs, aspect='auto', extent=extent,
                      origin='lower', cmap='RdBu_r', vmin=-np.max(np.abs(coeffs)),
                      vmax=np.max(np.abs(coeffs)))
        
        ax.set_title(title)
        ax.set_xlabel('Time')
        ax.set_ylabel('Frequency (Hz)')
        
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Wavelet Coefficient')
        
        plt.tight_layout()
        plt.show()
    
    def get_dominant_frequencies(self, data: np.ndarray, 
                                 sampling_rate: float = 1.0,
                                 top_n: int = 5) -> np.ndarray:
        """
        Get dominant frequencies from CWT energy spectrum.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float, optional
            Sampling rate (Hz). Default: 1.0
        top_n : int, optional
            Number of top frequencies to return. Default: 5
        
        Returns
        -------
        freqs : np.ndarray
            Top frequencies
        """
        energy, freqs = self.compute_energy_spectrum(data, sampling_rate)
        
        top_indices = np.argsort(energy)[-top_n:]
        return freqs[top_indices]
