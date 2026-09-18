"""
Band-Pass Filter Module

Implements band-pass filters to retain only specific frequency bands.
Filters separate signals into meaningful frequency ranges for analysis.

Key Uses:
- Isolate trading range frequency bands
- Extract cycle components from price data
- Filter out both low-frequency trends and high-frequency noise
- Analyze market microstructure time scales

Mathematical Foundation:
Band-pass filters attenuate frequencies outside a specified range [f1, f2]:
    H(f) = 1 for f1 ≤ f ≤ f2
    H(f) = 0 for f < f1 or f > f2
"""

import numpy as np
from scipy import signal
from typing import Union, Tuple


class BandPassFilter:
    """
    Band-pass filter implementation for retaining only specific frequency bands.
    
    This class implements multiple filter types for band-pass filtering:
    - Butterworth: Maximally flat passband
    - Chebyshev I: Elliptic-like passband ripple
    - Chebyshev II: Elliptic-like stopband ripple
    - Elliptic: Tiestcheff filter with ripple in both bands
    
    Band-pass filters are essential for isolating trading-relevant time scales
    while removing both trend and noise components.
    """
    
    def __init__(self, low_cutoff: float, high_cutoff: float, fs: float,
                 filter_type: str = 'butter', order: int = 4, btype: str = 'bandpass'):
        """
        Initialize band-pass filter.
        
        Parameters
        ----------
        low_cutoff : float
            Lower cutoff frequency in Hz
        high_cutoff : float
            Upper cutoff frequency in Hz
        fs : float
            Sampling frequency in Hz
        filter_type : str, optional
            Filter type: 'butter', 'cheby1', 'cheby2', 'ellip'
            Default: 'butter'
        order : int, optional
            Filter order (higher = steeper roll-off)
            Default: 4
        btype : str, optional
            Filter type: 'bandpass' or 'bandstop'
            Default: 'bandpass'
        
        Raises
        ------
        ValueError
            If low_cutoff < 0 or high_cutoff > fs/2
            If low_cutoff >= high_cutoff
            If cutoff frequencies exceed Nyquist frequency
        """
        if low_cutoff < 0 or high_cutoff > fs / 2:
            raise ValueError(
                f"Cutoff frequencies must be in range [0, {fs/2}] Hz. "
                f"Got low={low_cutoff}, high={high_cutoff}, fs={fs}"
            )
        if low_cutoff >= high_cutoff:
            raise ValueError(f"low_cutoff ({low_cutoff}) must be < high_cutoff ({high_cutoff})")
        
        self.low_cutoff = low_cutoff
        self.high_cutoff = high_cutoff
        self.fs = fs
        self.filter_type = filter_type.lower()
        self.order = order
        self.btype = btype
        
        # Design filter coefficients
        nyquist = 0.5 * fs
        normal_low = low_cutoff / nyquist
        normal_high = high_cutoff / nyquist
        
        if self.filter_type == 'butter':
            self.b, self.a = signal.butter(order, [normal_low, normal_high], btype=btype)
        elif self.filter_type == 'cheby1':
            self.b, self.a = signal.cheby1(order, 0.5, [normal_low, normal_high], btype=btype)
        elif self.filter_type == 'cheby2':
            self.b, self.a = signal.cheby2(order, 40, [normal_low, normal_high], btype=btype)
        elif self.filter_type == 'ellip':
            self.b, self.a = signal.ellip(order, 0.5, 40, [normal_low, normal_high], btype=btype)
        else:
            raise ValueError(f"Unknown filter_type: {filter_type}")
    
    def apply(self, data: Union[np.ndarray, list]) -> np.ndarray:
        """
        Apply band-pass filter to input data.
        
        Parameters
        ----------
        data : array-like
            Input time series data
        
        Returns
        -------
        filtered_data : ndarray
            Filtered output data
        
        Notes
        -----
        Uses filtfilt for zero-phase filtering. This is ideal for offline analysis
        where phase distortion is undesirable.
        """
        data = np.asarray(data)
        
        if len(data) < 2 * self.order:
            raise ValueError(f"Data length {len(data)} too short for order {self.order} filter")
        
        # Zero-phase filtering
        filtered = signal.filtfilt(self.b, self.a, data, method='gust')
        
        return filtered
    
    def apply_realtime(self, data: Union[np.ndarray, list]) -> np.ndarray:
        """
        Apply filter in real-time with phase delay (for online applications).
        
        Parameters
        ----------
        data : array-like
            Input time series data
        
        Returns
        -------
        filtered_data : ndarray
            Filtered output data with phase delay
        
        Notes
        -----
        Uses lfilter for real-time applications. The filtered signal will have
        a phase delay of approximately half the filter order.
        """
        data = np.asarray(data)
        
        if len(data) < 2 * self.order:
            raise ValueError(f"Data length {len(data)} too short for order {self.order} filter")
        
        # Apply filter with phase delay
        z, p, k = signal.tf2zpk(self.b, self.a)
        filtered = signal.lfilter(z, p, data)
        
        return filtered
    
    def frequency_response(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute frequency response of the band-pass filter.
        
        Returns
        -------
        w : ndarray
            Angular frequencies
        h : ndarray
            Frequency response magnitude
        
        Notes
        -----
        Returns a response that shows 1 (passband) between low and high cutoff,
        and 0 (stopband) outside this range. This helps visualize filter behavior.
        """
        w, h = signal.freqz(self.b, self.a)
        w_hz = w * self.fs / (2 * np.pi)
        
        return w_hz, h
    
    def bandwidth_analysis(self, signal_data: Union[np.ndarray, list]) -> dict:
        """
        Analyze signal power in passband vs stopbands.
        
        Parameters
        ----------
        signal_data : array-like
            Input signal data
        
        Returns
        -------
        analysis : dict
            Dictionary containing:
            - 'raw_ps': Power spectral density of raw signal
            - 'filtered_ps': Power spectral density of filtered signal
            - 'passband_power': Total power in passband [low_cutoff, high_cutoff]
            - 'stopband_low_power': Power in low-frequency stopband
            - 'stopband_high_power': Power in high-frequency stopband
            - 'bandwidth_ratio': Ratio of passband power to total power
            - 'noise_reduction': Percentage of noise removed
        
        Notes
        -----
        This analysis quantifies how effectively the filter isolates the desired
        frequency band while rejecting unwanted components.
        """
        from scipy.signal import welch
        
        signal_data = np.asarray(signal_data)
        if len(signal_data) < 2 * self.order:
            raise ValueError("Data too short for frequency analysis")
        
        # Compute PSD for raw signal
        raw_ps, raw_freq = welch(signal_data, fs=self.fs, nperseg=min(256, len(signal_data)))
        
        # Apply filter
        filtered = self.apply(signal_data)
        filtered_ps, filtered_freq = welch(filtered, fs=self.fs, nperseg=min(256, len(filtered)))
        
        # Find intersection of frequencies
        min_len = min(len(raw_freq), len(filtered_freq))
        raw_freq = raw_freq[:min_len]
        filtered_freq = filtered_freq[:min_len]
        raw_ps = raw_ps[:min_len]
        filtered_ps = filtered_ps[:min_len]
        
        # Define frequency bands
        passband_mask = (raw_freq >= self.low_cutoff) & (raw_freq <= self.high_cutoff)
        low_stopband_mask = raw_freq < self.low_cutoff
        high_stopband_mask = raw_freq > self.high_cutoff
        
        # Calculate power in each band
        passband_power = np.trapz(raw_ps[passband_mask], raw_freq[passband_mask])
        low_stopband_power = np.trapz(raw_ps[low_stopband_mask], raw_freq[low_stopband_mask])
        high_stopband_power = np.trapz(raw_ps[high_stopband_mask], raw_freq[high_stopband_mask])
        total_power = passband_power + low_stopband_power + high_stopband_power
        
        # Calculate noise reduction
        noise_reduction = 100 * (1 - passband_power / total_power)
        
        return {
            'raw_ps': raw_ps,
            'filtered_ps': filtered_ps,
            'passband_power': passband_power,
            'low_stopband_power': low_stopband_power,
            'high_stopband_power': high_stopband_power,
            'bandwidth_ratio': passband_power / total_power if total_power > 0 else 0,
            'noise_reduction': noise_reduction,
        }


def design_and_apply_band_pass(data: Union[np.ndarray, list],
                               low_cutoff: float,
                               high_cutoff: float,
                               fs: float,
                               filter_type: str = 'butter',
                               order: int = 4) -> np.ndarray:
    """
    Convenience function to design and apply band-pass filter in one step.
    
    Parameters
    ----------
    data : array-like
        Input time series data
    low_cutoff : float
        Lower cutoff frequency in Hz
    high_cutoff : float
        Upper cutoff frequency in Hz
    fs : float
        Sampling frequency in Hz
    filter_type : str, optional
        Filter type: 'butter', 'cheby1', 'cheby2', 'ellip'
    order : int, optional
        Filter order
    
    Returns
    -------
    filtered_data : ndarray
        Filtered output data
    
    Examples
    --------
    >>> import numpy as np
    >>> fs = 100  # 100 Hz sampling
    >>> data = np.random.randn(1000)
    >>> # Filter 1-10 Hz band
    >>> filtered = design_and_apply_band_pass(data, 1.0, 10.0, fs, order=2)
    """
    filter_obj = BandPassFilter(low_cutoff, high_cutoff, fs,
                               filter_type=filter_type, order=order)
    return filter_obj.apply(data)
