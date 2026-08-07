"""
Spectral Analysis

This module provides frequency domain analysis techniques including:
- Fast Fourier Transform (FFT) for frequency domain analysis
- Continuous Wavelet Transform for multi-resolution analysis
- Power Spectral Density estimation
- Harmonic component analysis
- Periodogram-based frequency analysis

Components:
- spectral_analysis/fft.py
- spectral_analysis/wavelet_analysis.py
- spectral_analysis/power_spectral_density.py
- spectral_analysis/harmonic_analysis.py
- spectral_analysis/periodogram.py
"""

from .fft import FastFourierTransform, compute_fft
from .wavelet_analysis import ContinuousWaveletTransform
from .power_spectral_density import PowerSpectralDensity
from .harmonic_analysis import HarmonicComponentAnalyzer
from .periodogram import PeriodogramAnalyzer

__all__ = [
    'FastFourierTransform',
    'compute_fft',
    'ContinuousWaveletTransform',
    'PowerSpectralDensity',
    'HarmonicComponentAnalyzer',
    'PeriodogramAnalyzer'
]
