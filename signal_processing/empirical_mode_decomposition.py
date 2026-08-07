"""
Empirical Mode Decomposition Module

Implements Empirical Mode Decomposition (EMD) for analyzing non-stationary signals.
EMD decomposes signals into Intrinsic Mode Functions (IMFs) that represent
different time scales and frequencies.

Key Uses:
- Analyze complex market signals with multiple time scales
- Extract IMF components for separate analysis
- Denoising by filtering specific IMFs
- Feature extraction for regime detection
- Analyze multi-scale price movements

Mathematical Foundation:
EMD iteratively decomposes signal S(t) into N intrinsic mode functions:
    S(t) = Σ_{i=1}^{N} IMF_i(t) + r_N(t)
where IMF_i(t) satisfies:
- Extrema are symmetric
- Mean of upper and lower envelopes is zero
- Each IMF represents a specific frequency scale

Advantages over Fourier/Wavelet:
- Data-driven decomposition
- Adapts to signal characteristics
- Works well with non-stationary data
- No a priori basis functions required
"""

import numpy as np
from typing import Union, List, Tuple, Optional


class EmpiricalModeDecomposition:
    """
    Empirical Mode Decomposition (EMD) for signal decomposition.
    
    EMD is a data-driven method that decomposes signals into a set of
    Intrinsic Mode Functions (IMFs) and a residue. Each IMF satisfies:
    - It has at least one extremum and one zero crossing
    - The mean of the upper and lower envelopes is zero
    - The number of extrema and zero crossings must be equal or differ by one
    
    This implementation includes ensemble EMD (EEMD) for improved stability.
    """
    
    def __init__(self, noise_level: float = 0.2, max_imf: int = 10,
                 max_iterations: int = 20, stopping_criterion: float = 1e-9):
        """
        Initialize EMD decomposer.
        
        Parameters
        ----------
        noise_level : float, optional
            Noise level for EEMD (relative to signal standard deviation)
            Default: 0.2
        max_imf : int, optional
            Maximum number of IMFs to extract
            Default: 10
        max_iterations : int, optional
            Maximum number of sifting iterations per IMF
            Default: 20
        stopping_criterion : float, optional
            Stopping criterion for sifting (relative standard deviation of mean)
            Default: 1e-9
        
        Notes
        -----
        EEMD adds white noise to the signal and averages multiple decompositions
        to reduce the statistical spurious mode decomposition problem.
        """
        self.noise_level = noise_level
        self.max_imf = max_imf
        self.max_iterations = max_iterations
        self.stopping_criterion = stopping_criterion
    
    def _get_extrema(self, signal: np.ndarray) -> Tuple[List[float], List[float]]:
        """
        Find extrema (maxima and minima) in signal.
        
        Parameters
        ----------
        signal : ndarray
            Input signal
        
        Returns
        -------
        maxima : list
            List of maximum values
        minima : list
            List of minimum values
        """
        maxima = []
        minima = []
        
        for i in range(1, len(signal) - 1):
            if signal[i] > signal[i - 1] and signal[i] > signal[i + 1]:
                maxima.append(signal[i])
            elif signal[i] < signal[i - 1] and signal[i] < signal[i + 1]:
                minima.append(signal[i])
        
        return maxima, minima
    
    def _interpolate_extrema(self, signal: np.ndarray, extrema: List[float]) -> np.ndarray:
        """
        Interpolate between extrema using spline interpolation.
        
        Parameters
        ----------
        signal : ndarray
            Input signal
        extrema : list
            List of extrema values
        
        Returns
        -------
        interpolated : ndarray
            Interpolated envelope
        """
        if len(extrema) < 3:
            return signal.copy()
        
        # Create indices
        indices = np.arange(len(signal))
        
        # Interpolate using cubic spline
        interpolated = np.interp(indices, np.arange(len(extrema)), extrema)
        
        return interpolated
    
    def _sift(self, signal: np.ndarray, IMF: np.ndarray) -> np.ndarray:
        """
        Sifting process to extract one IMF from signal.
        
        Parameters
        ----------
        signal : ndarray
            Current signal to decompose
        IMF : ndarray
            Current IMF being extracted
        
        Returns
        -------
        IMF : ndarray
            Extracted IMF
        
        Notes
        -----
        Sifting iteratively extracts high-frequency components from the signal.
        The process continues until the sifting stops criterion is met.
        """
        for iteration in range(self.max_iterations):
            # Get extrema
            maxima, minima = self._get_extrema(IMF)
            
            # Calculate upper and lower envelopes
            upper_envelope = self._interpolate_extrema(IMF, maxima)
            lower_envelope = self._interpolate_extrema(IMF, minima)
            
            # Calculate mean envelope
            mean_envelope = (upper_envelope + lower_envelope) / 2
            
            # Calculate mean difference
            mean_diff = np.mean(np.abs(IMF - mean_envelope))
            
            # Check stopping criterion
            if mean_diff < self.stopping_criterion:
                break
            
            # Update IMF
            IMF = IMF - mean_envelope
        
        return IMF
    
    def decompose(self, signal: Union[np.ndarray, list]) -> Tuple[List[np.ndarray], np.ndarray]:
        """
        Decompose signal into IMFs and residue.
        
        Parameters
        ----------
        signal : array-like
            Input signal data
        
        Returns
        -------
        imfs : list
            List of Intrinsic Mode Functions (IMFs)
        residue : ndarray
            Residual component after all IMFs are extracted
        
        Notes
        -----
        Returns IMF_1, IMF_2, ..., IMF_N, r_N where:
        - IMF_i are extracted in order from highest frequency to lowest
        - r_N is the final residue (trend)
        """
        signal = np.asarray(signal)
        imfs = []
        residue = signal.copy()
        
        # Decompose until residue is too small or max IMFs reached
        for _ in range(self.max_imf):
            IMF = self._sift(residue, residue.copy())
            
            # Check if IMF is not improving
            if np.max(np.abs(IMF)) < self.stopping_criterion:
                break
            
            imfs.append(IMF)
            residue = residue - IMF
        
        return imfs, residue
    
    def eemd_decompose(self, signal: Union[np.ndarray, list],
                      n_ensembles: int = 100) -> Tuple[List[np.ndarray], np.ndarray]:
        """
        Perform Ensemble EMD (EEMD) for improved stability.
        
        Parameters
        ----------
        signal : array-like
            Input signal data
        n_ensembles : int, optional
            Number of noise-added decompositions to average
            Default: 100
        
        Returns
        -------
        imfs : list
            List of averaged IMFs
        residue : ndarray
            Averaged residual component
        
        Notes
        -----
        EEMD adds white noise to the signal multiple times, performs EMD on each,
        and averages the results. This reduces the statistical spurious mode
        decomposition problem inherent in standard EMD.
        """
        signal = np.asarray(signal)
        n_samples = len(signal)
        noise_std = np.std(signal) * self.noise_level
        
        # Initialize arrays for averaging
        ensemble_imfs = []
        
        for ensemble in range(n_ensembles):
            # Add noise
            noise = np.random.randn(n_samples) * noise_std
            noisy_signal = signal + noise
            
            # Decompose noisy signal
            imfs, residue = self.decompose(noisy_signal)
            
            # Initialize ensemble storage if first iteration
            if ensemble == 0:
                ensemble_imfs = [imf.copy() for imf in imfs]
            else:
                # Accumulate IMFs
                for i, imf in enumerate(imfs):
                    ensemble_imfs[i] += imf
        
        # Average the IMFs
        averaged_imfs = [imf / n_ensembles for imf in ensemble_imfs]
        
        return averaged_imfs, residue


class EmpiricalModeAnalysis:
    """
    Convenience class for empirical mode analysis.
    
    This class provides additional analysis capabilities on top of EMD,
    including IMF statistics and energy distribution analysis.
    """
    
    def __init__(self, signal: Union[np.ndarray, list]):
        """
        Initialize with signal for analysis.
        
        Parameters
        ----------
        signal : array-like
            Input signal data
        """
        self.signal = np.asarray(signal)
        self.imfs, self.residue = EmpiricalModeDecomposition().decompose(self.signal)
    
    def get_imf_stats(self) -> dict:
        """
        Get statistics for each IMF.
        
        Returns
        -------
        stats : dict
            Dictionary containing statistics for each IMF:
            - 'amplitude': Max absolute amplitude
            - 'variance': Variance
            - 'energy': Energy (sum of squares)
            - 'frequency': Approximate frequency (from autocorrelation)
        """
        stats = {}
        
        for i, imf in enumerate(self.imfs):
            stats[f'imf_{i+1}'] = {
                'amplitude': float(np.max(np.abs(imf))),
                'variance': float(np.var(imf)),
                'energy': float(np.sum(imf**2)),
                'std': float(np.std(imf)),
                'mean': float(np.mean(imf)),
            }
        
        return stats


def design_and_apply_emd(signal: Union[np.ndarray, list],
                         noise_level: float = 0.2,
                         n_ensembles: int = 100) -> Tuple[List[np.ndarray], np.ndarray]:
    """
    Convenience function to decompose signal using EMD in one step.
    
    Parameters
    ----------
    signal : array-like
        Input signal data
    noise_level : float, optional
        Noise level for EEMD
    n_ensembles : int, optional
        Number of ensembles
    
    Returns
    -------
    imfs : list
        List of IMFs
    residue : ndarray
        Residual component
    
    Examples
    --------
    >>> import numpy as np
    >>> signal = np.sin(np.linspace(0, 10, 1000)) + 0.5 * np.random.randn(1000)
    >>> imfs, residue = design_and_apply_emd(signal, noise_level=0.1)
    """
    emd = EmpiricalModeDecomposition(noise_level=noise_level)
    return emd.eemd_decompose(signal, n_ensembles=n_ensembles)
