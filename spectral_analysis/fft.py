"""
Fast Fourier Transform (FFT)

This module provides Fast Fourier Transform functionality for frequency domain analysis
of time series data. Includes magnitude spectrum, phase spectrum, and power spectrum
analysis.
"""

import numpy as np
from typing import Tuple, Optional
import matplotlib.pyplot as plt


class FastFourierTransform:
    """
    Fast Fourier Transform (FFT) analyzer.
    
    This class performs FFT analysis on time series data to identify
    periodic patterns and dominant frequencies.
    
    Parameters
    ----------
    sampling_rate : float
        Sampling rate of the time series (Hz)
    window_size : int, optional
        Number of samples per window for FFT. Default: 256
    overlap : int, optional
        Overlap between windows. Default: 0 (no overlap)
    
    Examples
    --------
    >>> fft = FastFourierTransform(sampling_rate=1000, window_size=256)
    >>> magnitude, frequencies = fft.compute_fft(time_series)
    >>> fft.plot_spectrum(time_series, frequencies, magnitude)
    """
    
    def __init__(self, sampling_rate: float, window_size: int = 256, overlap: int = 0):
        self.sampling_rate = sampling_rate
        self.window_size = window_size
        self.overlap = overlap
    
    def compute_fft(self, data: np.ndarray, normalize: bool = True) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute FFT magnitude and phase spectra.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        normalize : bool, optional
            Normalize FFT output. Default: True
        
        Returns
        -------
        magnitude : np.ndarray
            Magnitude spectrum
        frequencies : np.ndarray
            Frequency axis
        phase : np.ndarray
            Phase spectrum
        """
        n = len(data)
        
        # Handle even/odd window sizes
        if n < self.window_size:
            padded_data = np.zeros(self.window_size)
            padded_data[:n] = data
            data = padded_data
        
        # Apply window (Hamming)
        window = np.hamming(len(data))
        data_windowed = data * window
        
        # Compute FFT
        fft_result = np.fft.fft(data_windowed)
        
        # Get positive frequencies only
        n_freqs = len(fft_result) // 2 + 1
        magnitude = np.abs(fft_result[:n_freqs])
        phase = np.angle(fft_result[:n_freqs])
        
        # Create frequency axis
        frequencies = np.linspace(0, self.sampling_rate / 2, n_freqs)
        
        # Normalize
        if normalize:
            magnitude = magnitude / n
        
        return magnitude, frequencies, phase
    
    def compute_power_spectrum(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute power spectrum.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        
        Returns
        -------
        power : np.ndarray
            Power spectrum
        frequencies : np.ndarray
            Frequency axis
        """
        magnitude, frequencies, _ = self.compute_fft(data)
        power = magnitude ** 2
        return power, frequencies
    
    def find_peak_frequency(self, data: np.ndarray, 
                            min_freq: float = 0.0,
                            max_freq: Optional[float] = None) -> Tuple[float, float]:
        """
        Find dominant frequency in the data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        min_freq : float, optional
            Minimum frequency to consider. Default: 0.0
        max_freq : float, optional
            Maximum frequency to consider. Default: Nyquist frequency
        
        Returns
        -------
        peak_freq : float
            Dominant frequency (Hz)
        peak_magnitude : float
            Peak magnitude
        """
        if max_freq is None:
            max_freq = self.sampling_rate / 2
        
        power, frequencies = self.compute_power_spectrum(data)
        
        mask = (frequencies >= min_freq) & (frequencies <= max_freq)
        mask_freqs = frequencies[mask]
        mask_power = power[mask]
        
        if len(mask_freqs) == 0:
            return 0.0, 0.0
        
        peak_idx = np.argmax(mask_power)
        peak_freq = mask_freqs[peak_idx]
        peak_magnitude = mask_power[peak_idx]
        
        return peak_freq, peak_magnitude
    
    def compute_fft_spectrum(self, data: np.ndarray, 
                             normalize: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute FFT spectrum (magnitude squared).
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        normalize : bool, optional
            Normalize output. Default: True
        
        Returns
        -------
        spectrum : np.ndarray
            FFT spectrum (magnitude squared)
        frequencies : np.ndarray
            Frequency axis
        """
        power, frequencies = self.compute_power_spectrum(data)
        if normalize:
            power = power / len(data)
        return power, frequencies
    
    def detect_seasonality(self, data: np.ndarray, 
                           max_period: float = 365.0) -> float:
        """
        Detect presence of seasonality in the data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        max_period : float, optional
            Maximum period to check (days). Default: 365.0
        
        Returns
        -------
        seasonal_strength : float
            Strength of seasonality (0 to 1)
        """
        power, frequencies = self.compute_power_spectrum(data)
        
        # Convert frequencies to periods (days)
        if self.sampling_rate > 0:
            periods = 1.0 / frequencies
            periods = np.clip(periods, 1.0, max_period)
        else:
            return 0.0
        
        # Find peak period
        peak_idx = np.argmax(power)
        peak_period = periods[peak_idx]
        peak_power = power[peak_idx]
        
        # Calculate seasonal strength
        total_power = np.sum(power)
        seasonal_strength = peak_power / (total_power + 1e-10)
        
        return seasonal_strength
    
    def plot_spectrum(self, data: np.ndarray, 
                     figsize: Tuple[int, int] = (12, 5),
                     title: str = 'Frequency Spectrum'):
        """
        Plot FFT magnitude spectrum.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        figsize : tuple, optional
            Figure size
        title : str, optional
            Plot title
        """
        magnitude, frequencies, _ = self.compute_fft(data)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Magnitude spectrum
        ax1.plot(frequencies, magnitude, 'b-')
        ax1.set_title('Magnitude Spectrum')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Magnitude')
        ax1.grid(True, alpha=0.3)
        
        # Log-log scale
        ax2.loglog(frequencies, magnitude, 'b-')
        ax2.set_title('Magnitude Spectrum (Log-Log)')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Magnitude')
        ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def plot_phase_spectrum(self, data: np.ndarray,
                           figsize: Tuple[int, int] = (12, 5),
                           title: str = 'Phase Spectrum'):
        """
        Plot FFT phase spectrum.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        figsize : tuple, optional
            Figure size
        title : str, optional
            Plot title
        """
        _, frequencies, phase = self.compute_fft(data)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Phase spectrum
        ax1.plot(frequencies, phase, 'r-')
        ax1.set_title('Phase Spectrum')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Phase (radians)')
        ax1.grid(True, alpha=0.3)
        
        # Wrapped phase
        ax2.plot(frequencies, np.angle(np.exp(1j * phase)), 'r-')
        ax2.set_title('Wrapped Phase Spectrum')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Wrapped Phase')
        ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()


def compute_fft(data: np.ndarray, 
                sampling_rate: float,
                normalize: bool = True) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convenience function to compute FFT.
    
    Parameters
    ----------
    data : np.ndarray
        Time series data
    sampling_rate : float
        Sampling rate (Hz)
    normalize : bool, optional
        Normalize output. Default: True
    
    Returns
    -------
    magnitude : np.ndarray
        Magnitude spectrum
    frequencies : np.ndarray
        Frequency axis
    phase : np.ndarray
        Phase spectrum
    """
    fft = FastFourierTransform(sampling_rate=sampling_rate)
    return fft.compute_fft(data, normalize=normalize)
