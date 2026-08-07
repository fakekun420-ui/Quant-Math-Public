"""
High-Pass Filter Module

Implements high-pass filters to remove low-frequency trends and market noise.
Filters are designed using Butterworth, Chebyshev, and Elliptic filters with configurable
cutoff frequencies.

Key Uses:
- Remove long-term trends to analyze short-term price movements
- Separate signal from trend components
- Filter out low-frequency market noise

Mathematical Foundation:
High-pass filters attenuate frequencies below cutoff while preserving higher frequencies.
The filter transfer function is:
    H(f) = 1 / (1 + (f_cutoff/f)^2n) for n-th order Butterworth

Where:
- f_cutoff: Cutoff frequency (Hz)
- n: Filter order (determines roll-off rate)
- f: Signal frequency
"""

import numpy as np
from scipy import signal
from typing import Union, Tuple, Optional


class HighPassFilter:
    """
    High-pass filter implementation for removing low-frequency trends and noise.
    
    This class implements multiple filter types and designs:
    - Butterworth: Maximally flat passband (maximal flatness in passband)
    - Chebyshev I: Elliptic-like passband ripple
    - Chebyshev II: Elliptic-like stopband ripple
    - Elliptic: Tiestcheff filter with ripple in both bands
    
    All filters are implemented using scipy.signal.butter/filter design functions.
    """
    
    def __init__(self, cutoff: float, fs: float, filter_type: str = 'butter',
                 order: int = 4, btype: str = 'high'):
        """
        Initialize high-pass filter.
        
        Parameters
        ----------
        cutoff : float
            Cutoff frequency in Hz (Nyquist frequency = fs/2)
        fs : float
            Sampling frequency in Hz
        filter_type : str, optional
            Filter type: 'butter', 'cheby1', 'cheby2', 'ellip'
            Default: 'butter'
        order : int, optional
            Filter order (higher = steeper roll-off but more phase distortion)
            Default: 4
        btype : str, optional
            Filter type: 'high', 'low', 'band', 'bandpass', 'bandstop'
            Default: 'high'
        
        Raises
        ------
        ValueError
            If cutoff > fs/2 (exceeds Nyquist frequency)
            If filter_type not recognized
        """
        if cutoff >= fs / 2:
            raise ValueError(f"Cutoff frequency {cutoff} must be < Nyquist frequency {fs/2}")
        
        self.cutoff = cutoff
        self.fs = fs
        self.filter_type = filter_type.lower()
        self.order = order
        self.btype = btype
        
        # Design filter coefficients
        nyquist = 0.5 * fs
        normal_cutoff = cutoff / nyquist
        
        if self.filter_type == 'butter':
            self.b, self.a = signal.butter(order, normal_cutoff, btype=btype)
        elif self.filter_type == 'cheby1':
            self.b, self.a = signal.cheby1(order, 0.5, normal_cutoff, btype=btype)
        elif self.filter_type == 'cheby2':
            self.b, self.a = signal.cheby2(order, 40, normal_cutoff, btype=btype)
        elif self.filter_type == 'ellip':
            self.b, self.a = signal.ellip(order, 0.5, 40, normal_cutoff, btype=btype)
        else:
            raise ValueError(f"Unknown filter_type: {filter_type}")
        
        # Pre-calculate filter coefficients for zero-phase filtering
        self.zf = np.zeros(order - 1)
    
    def apply(self, data: Union[np.ndarray, list]) -> np.ndarray:
        """
        Apply high-pass filter to input data.
        
        Parameters
        ----------
        data : array-like
            Input time series data (should be uniformly sampled)
        
        Returns
        -------
        filtered_data : ndarray
            Filtered output data
        
        Notes
        -----
        This implementation uses filtfilt for zero-phase filtering, which:
        - Avoids phase distortion by filtering forward and backward
        - Requires twice the number of operations
        - May amplify noise at boundaries
        """
        data = np.asarray(data)
        
        if len(data) < 2 * self.order:
            raise ValueError(f"Data length {len(data)} too short for order {self.order} filter")
        
        # Zero-phase filtering (forward and backward)
        filtered = signal.filtfilt(self.b, self.a, data, method='gust')
        
        return filtered
    
    def apply_zpk(self, data: Union[np.ndarray, list]) -> np.ndarray:
        """
        Apply filter using zero-pole-gain representation (more stable for long data).
        
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
        Uses lfilter instead of filtfilt, which maintains phase but has delay.
        Use this for real-time filtering where phase delay is acceptable.
        """
        data = np.asarray(data)
        z, p, k = signal.tf2zpk(self.b, self.a)
        
        if len(data) < 2 * self.order:
            raise ValueError(f"Data length {len(data)} too short for order {self.order} filter")
        
        # Apply filter with stable pole-zero realization
        filtered = signal.lfilter(z, p, data)
        
        return filtered
    
    def frequency_response(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute frequency response of the filter.
        
        Returns
        -------
        w : ndarray
            Angular frequencies
        h : ndarray
            Frequency response magnitude
        
        Notes
        -----
        This can be used to:
        - Visualize filter characteristics
        - Verify filter design parameters
        - Tune cutoff frequency
        """
        w, h = signal.freqz(self.b, self.a)
        
        # Convert to Hz
        w_hz = w * self.fs / (2 * np.pi)
        
        return w_hz, h
    
    def bandwidth_analysis(self, signal_data: Union[np.ndarray, list]) -> dict:
        """
        Analyze signal bandwidth before and after filtering.
        
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
            - 'power_before': Total power before filtering
            - 'power_after': Total power after filtering
            - 'attenuation': Relative attenuation in low frequencies
        
        Notes
        -----
        Calculates power spectral density using Welch's method for frequency domain
        analysis. Useful for validating filter performance on real data.
        """
        from scipy.signal import welch
        
        signal_data = np.asarray(signal_data)
        if len(signal_data) < 2 * self.order:
            raise ValueError("Data too short for frequency analysis")
        
        # Compute PSD for raw signal
        raw_ps, raw_freq = welch(signal_data, fs=self.fs, nperseg=min(256, len(signal_data)))
        
        # Apply filter
        filtered = self.apply(signal_data)
        
        # Compute PSD for filtered signal
        filtered_ps, filtered_freq = welch(filtered, fs=self.fs, nperseg=min(256, len(filtered)))
        
        # Find intersection of frequencies
        min_len = min(len(raw_freq), len(filtered_freq))
        raw_freq = raw_freq[:min_len]
        filtered_freq = filtered_freq[:min_len]
        raw_ps = raw_ps[:min_len]
        filtered_ps = filtered_ps[:min_len]
        
        # Calculate total power in low-frequency band (0 to cutoff/2)
        low_freq_mask = raw_freq < (self.cutoff / 2)
        power_before = np.trapz(raw_ps[low_freq_mask], raw_freq[low_freq_mask])
        power_after = np.trapz(filtered_ps[low_freq_mask], raw_freq[low_freq_mask])
        
        # Calculate attenuation
        attenuation = 10 * np.log10(power_after / power_before) if power_before > 0 else float('inf')
        
        return {
            'raw_ps': raw_ps,
            'filtered_ps': filtered_ps,
            'power_before': power_before,
            'power_after': power_after,
            'attenuation_db': attenuation,
            'attenuation_pct': 100 * (1 - power_after / power_before) if power_before > 0 else 0,
        }


def design_and_apply_high_pass(data: Union[np.ndarray, list],
                               cutoff: float,
                               fs: float,
                               filter_type: str = 'butter',
                               order: int = 4) -> np.ndarray:
    """
    Convenience function to design and apply high-pass filter in one step.
    
    Parameters
    ----------
    data : array-like
        Input time series data
    cutoff : float
        Cutoff frequency in Hz
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
    >>> cutoff = 1.0  # 1 Hz cutoff
    >>> filtered = design_and_apply_high_pass(data, cutoff, fs, order=2)
    """
    filter_obj = HighPassFilter(cutoff, fs, filter_type=filter_type, order=order)
    return filter_obj.apply(data)
