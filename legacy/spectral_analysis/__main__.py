"""
Spectral Analysis Examples

This module demonstrates the usage of spectral analysis techniques.
"""

import numpy as np
from spectral_analysis import (
    FastFourierTransform, compute_fft,
    ContinuousWaveletTransform,
    PowerSpectralDensity,
    HarmonicComponentAnalyzer,
    PeriodogramAnalyzer
)


def generate_sample_data(fs: float = 1000, duration: float = 1.0,
                         freqs: list = [50, 120, 200, 350],
                         noise_level: float = 0.1) -> np.ndarray:
    """
    Generate sample time series data with multiple frequencies.
    
    Parameters
    ----------
    fs : float
        Sampling frequency (Hz)
    duration : float
        Duration in seconds
    freqs : list
        Frequencies to include (Hz)
    noise_level : float
        Noise level
    
    Returns
    -------
    data : np.ndarray
        Sample data
    """
    t = np.arange(0, duration, 1/fs)
    data = np.zeros_like(t)
    
    for freq in freqs:
        data += 1.0 * np.sin(2 * np.pi * freq * t)
    
    # Add noise
    data += np.random.normal(0, noise_level, len(t))
    
    return data


def example_fft_analysis(data: np.ndarray, fs: float = 1000):
    """Example: FFT Analysis"""
    print("\n=== FFT Analysis ===")
    
    fft = FastFourierTransform(sampling_rate=fs)
    magnitude, frequencies, phase = fft.compute_fft(data)
    
    peak_freq, peak_magnitude = fft.find_peak_frequency(data)
    print(f"Peak frequency: {peak_freq:.2f} Hz, Magnitude: {peak_magnitude:.2f}")
    
    seasonal_strength = fft.detect_seasonality(data, max_period=365.0)
    print(f"Seasonality strength: {seasonal_strength:.2f}")
    
    fft.plot_spectrum(data, title='FFT Spectrum Analysis')


def example_wavelet_analysis(data: np.ndarray, fs: float = 1000):
    """Example: Continuous Wavelet Transform"""
    print("\n=== Continuous Wavelet Transform ===")
    
    scales = np.logspace(0, 3, 64)
    cwt = ContinuousWaveletTransform(scales=scales)
    
    coeffs, freqs = cwt.compute_cwt(data)
    
    times, amplitudes = cwt.detect_transients(data)
    print(f"Detected {len(times)} transient events")
    
    dominant_freqs = cwt.get_dominant_frequencies(data, top_n=3)
    print(f"Dominant frequencies: {dominant_freqs}")
    
    cwt.plot_cwt(data, title='CWT Analysis')


def example_psd_analysis(data: np.ndarray, fs: float = 1000):
    """Example: Power Spectral Density"""
    print("\n=== Power Spectral Density ===")
    
    psd = PowerSpectralDensity(fs=fs, nperseg=256)
    freqs, power = psd.compute_psd(data, method='welch')
    
    centroid = psd.compute_spectral_centroid(data)
    bandwidth = psd.compute_spectral_bandwidth(data)
    rolloff = psd.compute_spectral_rolloff(data)
    
    print(f"Spectral centroid: {centroid:.2f} Hz")
    print(f"Spectral bandwidth: {bandwidth:.2f} Hz")
    print(f"Spectral rolloff: {rolloff:.2f} Hz")
    
    # Band power
    band_power = psd.get_bandpower(data, low_freq=50, high_freq=150)
    print(f"Band power (50-150 Hz): {band_power:.2f}")
    
    psd.plot_psd(data, title='PSD Analysis')


def example_harmonic_analysis(data: np.ndarray, fs: float = 1000):
    """Example: Harmonic Component Analysis"""
    print("\n=== Harmonic Component Analysis ===")
    
    analyzer = HarmonicComponentAnalyzer(min_harmonic=1, max_harmonic=10)
    harmonics = analyzer.detect_harmonics(data, fs)
    
    print(f"Detected {len(harmonics)} harmonics")
    for h, (freq, mag) in sorted(harmonics.items()):
        print(f"  H{h}: {freq:.2f} Hz, Mag: {mag:.2f}")
    
    periodicity = analyzer.analyze_periodicity(data, fs)
    print(f"Fundamental frequency: {periodicity['fundamental_frequency']:.2f} Hz")
    print(f"Fundamental period: {periodicity['fundamental_period']:.2f} s")
    
    analyzer.plot_harmonics(data, fs, n_harmonics=5)


def example_periodogram_analysis(data: np.ndarray, fs: float = 1000):
    """Example: Periodogram Analysis"""
    print("\n=== Periodogram Analysis ===")
    
    analyzer = PeriodogramAnalyzer(fs=fs, nperseg=256)
    freqs, power = analyzer.compute_periodogram(data)
    
    periodicities = analyzer.detect_periodicities(data, min_period=1.0, max_period=365.0)
    print(f"Detected {len(periodicities)} periodicities")
    
    seasonality = analyzer.detect_seasonality(data, min_period=7.0, max_period=365.0)
    print(f"Has seasonality: {seasonality['has_seasonality']}")
    if seasonality['dominant_period']:
        print(f"  Dominant period: {seasonality['dominant_period']:.1f} periods")
    
    flatness = analyzer.compute_spectral_flatness(data)
    print(f"Spectral flatness: {flatness:.2f}")
    
    analyzer.plot_detected_periods(data, min_period=7.0, max_period=365.0)


def main():
    """Run all examples"""
    # Generate sample data
    fs = 1000  # Sampling rate (Hz)
    duration = 2.0  # Duration (seconds)
    
    data = generate_sample_data(fs=fs, duration=duration,
                                freqs=[50, 120, 200, 350],
                                noise_level=0.1)
    
    print("=" * 50)
    print("Spectral Analysis Examples")
    print("=" * 50)
    
    # Run all examples
    example_fft_analysis(data, fs)
    example_wavelet_analysis(data, fs)
    example_psd_analysis(data, fs)
    example_harmonic_analysis(data, fs)
    example_periodogram_analysis(data, fs)
    
    print("\n" + "=" * 50)
    print("All examples completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
