"""
Wavelet Decomposition Module

Implements wavelet-based denoising and signal decomposition using wavelet transforms.
Wavelets provide multi-resolution analysis, capturing both time and frequency information.

Key Uses:
- Multi-resolution analysis of market data
- Adaptive noise filtering
- Feature extraction for trading signals
- Edge detection and turning point identification
- Denoising without assuming stationary signals

Mathematical Foundation:
Wavelet transform decomposes signal into scaling coefficients (approximation) and wavelet
coefficients (detail) at multiple scales. This allows:
- Time-frequency localization (unlike Fourier)
- Multi-resolution analysis
- Adaptive decomposition based on signal characteristics
"""

import numpy as np
import pywt
from typing import Union, Tuple, List, Optional


class WaveletDenoiser:
    """
    Wavelet-based denoising and signal decomposition.
    
    This class implements wavelet thresholding for denoising and multi-resolution
    decomposition using various wavelet families:
    - Daubechies: Good time-frequency localization
    - Symlets: Symmetric wavelets with compact support
    - Coiflets: Higher-order vanishing moments
    - Morlet: Complex wavelet for frequency analysis
    - Mexican Hat: Second derivative of Gaussian
    
    All denoising uses soft thresholding with universal thresholding or custom
    thresholds based on noise estimation.
    """
    
    def __init__(self, wavelet: str = 'db4', level: Optional[int] = None,
                 threshold_method: str = 'universal', threshold_param: float = None):
        """
        Initialize wavelet denoiser.
        
        Parameters
        ----------
        wavelet : str, optional
            Wavelet family: 'db4', 'sym4', 'coif4', 'morl', 'mexh', etc.
            Default: 'db4' (Daubechies 4)
        level : int, optional
            Decomposition level. If None, automatically determined by signal length.
            Default: None
        threshold_method : str, optional
            Thresholding method: 'universal', 'visureshrink', 'SURE', 'heursure'
            Default: 'universal'
        threshold_param : float, optional
            Custom threshold parameter. If None, computed automatically.
            Default: None
        
        Raises
        ------
        ValueError
            If wavelet is not supported by pywt
        """
        if wavelet not in pywt.wavelist():
            raise ValueError(f"Unsupported wavelet: {wavelet}. Available: {pywt.wavelist()}")
        
        self.wavelet = wavelet
        self.level = level
        self.threshold_method = threshold_method.lower()
        self.threshold_param = threshold_param
    
    def decompose(self, signal: Union[np.ndarray, list]) -> Tuple[np.ndarray, List[np.ndarray]]:
        """
        Decompose signal into approximation and detail coefficients.
        
        Parameters
        ----------
        signal : array-like
            Input signal data
        
        Returns
        -------
        coeffs : tuple
            Tuple of (cA_n, [cD_n, cD_{n-1}, ..., cD_1]) where:
            - cA_n: Approximation coefficients at level n
            - cD_n: Detail coefficients at level n
            - cD_{n-1}: Detail coefficients at level n-1
            - etc.
        
        Notes
        -----
        Decomposition is performed using `pywt.wavedec` which implements the
        Discrete Wavelet Transform (DWT). Higher levels provide coarser approximations.
        """
        signal = np.asarray(signal)
        
        # Determine decomposition level if not specified
        if self.level is None:
            # Use recommended level based on signal length
            self.level = pywt.dwt_max_level(len(signal), self.wavelet)
        
        # Perform wavelet decomposition
        coeffs = pywt.wavedec(signal, self.wavelet, level=self.level)
        
        return coeffs
    
    def denoise(self, signal: Union[np.ndarray, list],
                threshold: Optional[float] = None,
                mode: str = 'soft') -> np.ndarray:
        """
        Denoise signal using wavelet thresholding.
        
        Parameters
        ----------
        signal : array-like
            Input signal data
        threshold : float, optional
            Threshold value. If None, computed automatically.
        mode : str, optional
            Thresholding mode: 'soft' (shrinks coefficients toward zero) or 'hard'
            (zeros out coefficients below threshold)
            Default: 'soft'
        
        Returns
        -------
        denoised_signal : ndarray
            Denoised output signal
        
        Notes
        -----
        Soft thresholding (default) is recommended for denoising as it:
        - Continuously shrinks coefficients toward zero
        - Avoids introducing discontinuities
        - Provides smoother denoising
        
        Hard thresholding may create artifacts and discontinuities.
        """
        signal = np.asarray(signal)
        
        if len(signal) < 2 ** self.level:
            # Reduce level if signal is too short
            self.level = pywt.dwt_max_level(len(signal), self.wavelet)
        
        # Compute threshold if not provided
        if threshold is None:
            # Universal threshold (donoho-johnstone threshold)
            sigma = np.median(np.abs(signal)) / 0.6745  # Noise standard deviation
            threshold = sigma * np.sqrt(2 * np.log(len(signal)))
        
        # Decompose signal
        coeffs = self.decompose(signal)
        
        # Apply threshold to detail coefficients only
        denoised_coeffs = [coeffs[0]]  # Keep approximation coefficients
        
        for detail_coeff in coeffs[1:]:
            if self.threshold_method == 'universal':
                # Universal threshold
                sigma = np.median(np.abs(detail_coeff)) / 0.6745
                threshold = sigma * np.sqrt(2 * np.log(len(detail_coeff)))
                denoised = pywt.threshold(detail_coeff, threshold, mode=mode)
            elif self.threshold_method == 'visureshrink':
                # VisuShrink: adaptive threshold
                sigma = np.median(np.abs(detail_coeff)) / 0.6745
                threshold = sigma * np.sqrt(2 * np.log(len(detail_coeff)))
                denoised = pywt.threshold(detail_coeff, threshold, mode=mode)
            elif self.threshold_method == 'sure':
                # SURE (Stein's Unbiased Risk Estimate)
                denoised = pywt.threshold(detail_coeff, threshold_param, mode=mode)
            elif self.threshold_method == 'heursure':
                # Heuristic SURE
                sigma = np.median(np.abs(detail_coeff)) / 0.6745
                threshold = sigma * np.sqrt(2 * np.log(len(detail_coeff)))
                denoised = pywt.threshold(detail_coeff, threshold, mode=mode)
            else:
                # Custom threshold
                denoised = pywt.threshold(detail_coeff, threshold_param, mode=mode)
            
            denoised_coeffs.append(denoised)
        
        # Reconstruct signal
        denoised_signal = pywt.waverec(denoised_coeffs, self.wavelet)
        
        # Trim to original length
        denoised_signal = denoised_signal[:len(signal)]
        
        return denoised_signal
    
    def get_scale_info(self, signal: Union[np.ndarray, list]) -> dict:
        """
        Get multi-resolution analysis information.
        
        Parameters
        ----------
        signal : array-like
            Input signal data
        
        Returns
        -------
        info : dict
            Dictionary containing:
            - 'levels': Number of decomposition levels
            - 'signal_length': Length of input signal
            - 'approximation_power': Total power in approximation coefficients
            - 'detail_powers': List of powers for each detail level
            - 'energy_distribution': Energy distribution across scales
        
        Notes
        -----
        Energy distribution helps identify which frequency bands contain most
        of the signal's power. This can guide strategy development.
        """
        signal = np.asarray(signal)
        coeffs = self.decompose(signal)
        
        # Energy calculation
        approx_energy = np.sum(coeffs[0]**2)
        detail_energies = [np.sum(detail**2) for detail in coeffs[1:]]
        total_energy = approx_energy + sum(detail_energies)
        
        return {
            'levels': self.level,
            'signal_length': len(signal),
            'approximation_power': approx_energy,
            'detail_powers': detail_energies,
            'energy_distribution': detail_energies + [approx_energy],
            'approx_power_pct': 100 * approx_energy / total_energy if total_energy > 0 else 0,
        }


def design_and_apply_wavelet_denoise(signal: Union[np.ndarray, list],
                                     wavelet: str = 'db4',
                                     level: int = None,
                                     mode: str = 'soft') -> np.ndarray:
    """
    Convenience function to denoise signal in one step.
    
    Parameters
    ----------
    signal : array-like
        Input signal data
    wavelet : str, optional
        Wavelet family
    level : int, optional
        Decomposition level
    mode : str, optional
        Thresholding mode ('soft' or 'hard')
    
    Returns
    -------
    denoised_signal : ndarray
        Denoised output signal
    
    Examples
    --------
    >>> import numpy as np
    >>> signal = np.random.randn(1000) + np.sin(np.linspace(0, 10, 1000))
    >>> denoised = design_and_apply_wavelet_denoise(signal, wavelet='db4', mode='soft')
    """
    denoiser = WaveletDenoiser(wavelet=wavelet, level=level)
    return denoiser.denoise(signal, mode=mode)
