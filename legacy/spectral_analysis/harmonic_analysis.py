"""
Harmonic Component Analysis

This module provides harmonic component analysis for identifying
periodic patterns and frequency components in time series data.
"""

import numpy as np
from typing import Tuple, Dict, Optional
from scipy.fft import fft, fftfreq


class HarmonicComponentAnalyzer:
    """
    Harmonic component analyzer.
    
    This class identifies and analyzes harmonic components in time series
    data, including periodic patterns and dominant frequencies.
    
    Parameters
    ----------
    min_harmonic : int, optional
        Minimum harmonic number to consider. Default: 1
    max_harmonic : int, optional
        Maximum harmonic number to consider. Default: 10
    
    Examples
    --------
    >>> analyzer = HarmonicComponentAnalyzer(min_harmonic=1, max_harmonic=10)
    >>> harmonics = analyzer.detect_harmonics(time_series)
    >>> analyzer.plot_harmonics(time_series, harmonics)
    """
    
    def __init__(self, min_harmonic: int = 1, max_harmonic: int = 10):
        self.min_harmonic = min_harmonic
        self.max_harmonic = max_harmonic
        self.harmonics = None
    
    def detect_harmonics(self, data: np.ndarray, 
                        sampling_rate: float) -> Dict[int, Tuple[float, float]]:
        """
        Detect harmonic components.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float
            Sampling rate (Hz)
        
        Returns
        -------
        harmonics : dict
            Dictionary mapping harmonic number to (frequency, magnitude)
        """
        # Compute FFT
        n = len(data)
        fft_result = fft(data)
        magnitude = np.abs(fft_result[:n // 2 + 1])
        frequencies = fftfreq(n, 1/sampling_rate)[:n // 2 + 1]
        
        # Sort by magnitude
        sorted_indices = np.argsort(magnitude)[::-1]
        
        harmonics = {}
        
        for idx in sorted_indices:
            if idx == 0:
                continue  # Skip DC component
            
            freq = frequencies[idx]
            mag = magnitude[idx]
            
            # Find harmonic number
            for h in range(self.min_harmonic, self.max_harmonic + 1):
                fundamental_freq = freq / h
                
                # Check if this is a harmonic of a lower frequency
                if fundamental_freq in harmonics:
                    # Check if this is a higher harmonic
                    ratio = freq / fundamental_freq
                    if abs(ratio - h) < 1e-3:
                        harmonics[h] = (freq, mag)
                        break
        
        self.harmonics = harmonics
        return harmonics
    
    def extract_harmonic_components(self, data: np.ndarray,
                                    sampling_rate: float,
                                    n_harmonics: Optional[int] = None) -> list:
        """
        Extract harmonic components from time series.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float
            Sampling rate (Hz)
        n_harmonics : int, optional
            Number of top harmonics to extract. Default: all
        
        Returns
        -------
        components : list
            List of harmonic components as tuples (frequency, magnitude, signal)
        """
        n = len(data)
        fft_result = fft(data)
        magnitude = np.abs(fft_result[:n // 2 + 1])
        frequencies = fftfreq(n, 1/sampling_rate)[:n // 2 + 1]
        
        components = []
        
        for idx in np.argsort(magnitude)[::-1]:
            if idx == 0:
                continue  # Skip DC component
            
            freq = frequencies[idx]
            mag = magnitude[idx]
            
            # Create harmonic component
            component = {
                'frequency': freq,
                'magnitude': mag,
                'signal': 2 * mag * np.cos(2 * np.pi * freq * np.arange(n) / sampling_rate),
                'phase': np.angle(fft_result[idx])
            }
            
            components.append(component)
            
            if n_harmonics and len(components) >= n_harmonics:
                break
        
        return components
    
    def reconstruct_signal(self, data: np.ndarray,
                          sampling_rate: float,
                          n_harmonics: int = 5) -> np.ndarray:
        """
        Reconstruct signal from top harmonics.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float
            Sampling rate (Hz)
        n_harmonics : int, optional
            Number of top harmonics to use. Default: 5
        
        Returns
        -------
        reconstructed : np.ndarray
            Reconstructed signal
        """
        n = len(data)
        reconstructed = np.zeros(n)
        
        components = self.extract_harmonic_components(data, sampling_rate, n_harmonics)
        
        for comp in components:
            reconstructed += comp['signal']
        
        return reconstructed
    
    def compute_harmonic_ratio(self, data: np.ndarray,
                              sampling_rate: float,
                              ratio_type: str = 'even_odd') -> float:
        """
        Compute ratio between harmonic components.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float
            Sampling rate (Hz)
        ratio_type : str, optional
            Type of ratio to compute ('even_odd', 'odd_only', 'even_only'). Default: 'even_odd'
        
        Returns
        -------
        ratio : float
            Harmonic ratio
        """
        harmonics = self.detect_harmonics(data, sampling_rate)
        
        even_powers = []
        odd_powers = []
        
        for h, (freq, mag) in harmonics.items():
            power = mag ** 2
            if h % 2 == 0:
                even_powers.append(power)
            else:
                odd_powers.append(power)
        
        if ratio_type == 'even_odd':
            if len(even_powers) > 0 and len(odd_powers) > 0:
                return np.mean(even_powers) / np.mean(odd_powers)
            return 0.0
        elif ratio_type == 'odd_only':
            return np.mean(odd_powers) if len(odd_powers) > 0 else 0.0
        elif ratio_type == 'even_only':
            return np.mean(even_powers) if len(even_powers) > 0 else 0.0
        else:
            raise ValueError(f"Unknown ratio_type: {ratio_type}")
    
    def analyze_periodicity(self, data: np.ndarray,
                           sampling_rate: float) -> Dict[str, float]:
        """
        Analyze periodicity in the data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float
            Sampling rate (Hz)
        
        Returns
        -------
        analysis : dict
            Analysis results including fundamental frequency, period, etc.
        """
        harmonics = self.detect_harmonics(data, sampling_rate)
        
        analysis = {}
        
        if len(harmonics) > 0:
            # Get dominant harmonic
            dominant_h, (dom_freq, dom_mag) = max(harmonics.items(), key=lambda x: x[1][1])
            analysis['fundamental_frequency'] = dom_freq
            analysis['fundamental_period'] = 1.0 / dom_freq
            analysis['dominant_harmonic'] = dominant_h
            analysis['dominant_magnitude'] = dom_mag
        else:
            analysis['fundamental_frequency'] = 0.0
            analysis['fundamental_period'] = np.inf
            analysis['dominant_harmonic'] = 0
            analysis['dominant_magnitude'] = 0.0
        
        return analysis
    
    def plot_harmonics(self, data: np.ndarray,
                      sampling_rate: float,
                      n_harmonics: int = 5,
                      figsize: Tuple[int, int] = (14, 6),
                      title: str = 'Harmonic Component Analysis'):
        """
        Plot harmonic components.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float
            Sampling rate (Hz)
        n_harmonics : int, optional
            Number of top harmonics to show. Default: 5
        figsize : tuple, optional
            Figure size
        title : str, optional
            Plot title
        """
        import matplotlib.pyplot as plt
        components = self.extract_harmonic_components(data, sampling_rate, n_harmonics)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)

        # Original signal
        ax1.plot(data, 'b-', label='Original Signal')
        ax1.set_title('Original Signal')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Amplitude')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Harmonic decomposition
        reconstructed = np.zeros(len(data))
        
        for i, comp in enumerate(components):
            ax2.plot(comp['signal'], color=plt.cm.tab10(i), 
                    label=f'H{len(components)-i}: {comp["frequency"]:.2f} Hz')
            reconstructed += comp['signal']
        
        ax2.plot(reconstructed, 'k--', label='Reconstructed')
        ax2.set_title('Harmonic Components')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Amplitude')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title)
        plt.tight_layout()
        plt.show()
    
    def plot_spectrum_with_harmonics(self, data: np.ndarray,
                                    sampling_rate: float,
                                    n_harmonics: int = 5,
                                    figsize: Tuple[int, int] = (12, 5),
                                    title: str = 'Frequency Spectrum with Harmonics'):
        """
        Plot frequency spectrum highlighting harmonics.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        sampling_rate : float
            Sampling rate (Hz)
        n_harmonics : int, optional
            Number of top harmonics to highlight. Default: 5
        figsize : tuple, optional
            Figure size
        title : str, optional
            Plot title
        """
        import matplotlib.pyplot as plt
        n = len(data)
        fft_result = fft(data)
        magnitude = np.abs(fft_result[:n // 2 + 1])
        frequencies = fftfreq(n, 1/sampling_rate)[:n // 2 + 1]

        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot spectrum
        ax.plot(frequencies, magnitude, 'b-', label='Spectrum')
        
        # Highlight harmonics
        components = self.extract_harmonic_components(data, sampling_rate, n_harmonics)
        
        for comp in components:
            ax.plot(comp['frequency'], comp['magnitude'], 'ro',
                   markersize=10, markeredgecolor='black')
            ax.text(comp['frequency'], comp['magnitude'], f'H{len(components)}',
                   fontsize=10, ha='center')
        
        ax.set_title(title)
        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('Magnitude')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
