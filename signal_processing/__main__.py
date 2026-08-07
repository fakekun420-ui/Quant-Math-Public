"""
Signal Processing Module Example Usage

This module demonstrates how to use the various noise filtering techniques
implemented in the signal_processing module.
"""

import numpy as np
import matplotlib.pyplot as plt
from high_pass_filter import HighPassFilter
from band_pass_filter import BandPassFilter
from wavelet_decomposition import WaveletDenoiser
from empirical_mode_decomposition import design_and_apply_emd
from kalman_filter import design_and_apply_kalman_filter


def generate_test_signal(fs: float, duration: float = 10.0) -> tuple:
    """
    Generate a test signal with multiple frequency components.
    
    Parameters
    ----------
    fs : float
        Sampling frequency in Hz
    duration : float, optional
        Duration in seconds
        Default: 10.0
    
    Returns
    -------
    t : ndarray
        Time vector
    signal : ndarray
        Noisy signal
    true_signal : ndarray
        Clean signal for comparison
    """
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    
    # Generate signal with multiple components
    true_signal = (
        np.sin(2 * np.pi * 1.0 * t) +          # 1 Hz component
        0.5 * np.sin(2 * np.pi * 5.0 * t) +    # 5 Hz component
        0.3 * np.sin(2 * np.pi * 10.0 * t)     # 10 Hz component
    )
    
    # Add noise
    noise_level = 0.5
    signal = true_signal + noise_level * np.random.randn(len(t))
    
    return t, signal, true_signal


def example_high_pass_filter():
    """Example: High-pass filtering to remove trends."""
    print("=" * 60)
    print("Example 1: High-Pass Filter")
    print("=" * 60)
    
    fs = 100  # 100 Hz sampling
    t, signal, true_signal = generate_test_signal(fs)
    
    # Apply high-pass filter
    cutoff = 1.0  # 1 Hz cutoff
    filter_obj = HighPassFilter(cutoff, fs, filter_type='butter', order=4)
    filtered = filter_obj.apply(signal)
    
    # Analyze frequency response
    w, h = filter_obj.frequency_response()
    
    # Plot results
    plt.figure(figsize=(12, 8))
    plt.subplot(3, 1, 1)
    plt.plot(t, true_signal, label='True Signal', linewidth=2)
    plt.plot(t, signal, label='Noisy Signal', alpha=0.5)
    plt.plot(t, filtered, label='Filtered', linewidth=2)
    plt.legend()
    plt.title('High-Pass Filtering (Cutoff: 1 Hz)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    
    plt.subplot(3, 1, 2)
    plt.plot(w, 20 * np.log10(np.abs(h)), label='Frequency Response')
    plt.axvline(x=cutoff, color='r', linestyle='--', label=f'Cutoff ({cutoff} Hz)')
    plt.title('Filter Frequency Response')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude (dB)')
    plt.grid(True)
    
    # Bandwidth analysis
    plt.subplot(3, 1, 3)
    analysis = filter_obj.bandwidth_analysis(signal)
    plt.plot(20 * np.log10(analysis['raw_ps'][:256]), label='Raw Signal', alpha=0.5)
    plt.plot(20 * np.log10(analysis['filtered_ps'][:256]), label='Filtered Signal', linewidth=2)
    plt.axvline(x=cutoff, color='r', linestyle='--')
    plt.title(f'Signal Power Spectrum\nAttenuation: {analysis["attenuation_db"]:.2f} dB ({analysis["attenuation_pct"]:.1f}%)')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Power (dB)')
    plt.legend()
    plt.tight_layout()
    plt.show()


def example_band_pass_filter():
    """Example: Band-pass filtering to isolate specific frequency bands."""
    print("=" * 60)
    print("Example 2: Band-Pass Filter")
    print("=" * 60)
    
    fs = 100
    t, signal, true_signal = generate_test_signal(fs)
    
    # Apply band-pass filter
    low_cutoff = 5.0
    high_cutoff = 10.0
    
    filter_obj = BandPassFilter(low_cutoff, high_cutoff, fs, filter_type='butter', order=4)
    filtered = filter_obj.apply(signal)
    
    # Analyze frequency bands
    analysis = filter_obj.bandwidth_analysis(signal)
    
    print(f"Passband Power: {analysis['passband_power']:.4f}")
    print(f"Low-Frequency Power: {analysis['low_stopband_power']:.4f}")
    print(f"High-Frequency Power: {analysis['high_stopband_power']:.4f}")
    print(f"Noise Reduction: {analysis['noise_reduction']:.2f}%")
    
    # Plot results
    plt.figure(figsize=(12, 8))
    plt.subplot(3, 1, 1)
    plt.plot(t, true_signal, label='True Signal', linewidth=2)
    plt.plot(t, signal, label='Noisy Signal', alpha=0.5)
    plt.plot(t, filtered, label=f'Filtered ({low_cutoff}-{high_cutoff} Hz)', linewidth=2)
    plt.legend()
    plt.title(f'Band-Pass Filtering ({low_cutoff}-{high_cutoff} Hz)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    
    plt.subplot(3, 1, 2)
    plt.plot(t, true_signal, label='True Signal', linewidth=2)
    plt.plot(t, filtered, label='Filtered', linewidth=2)
    plt.legend()
    plt.title('Filtered Signal (Frequency Components: 5-10 Hz)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    
    plt.subplot(3, 1, 3)
    plt.bar(['Low Band', 'Passband', 'High Band'], 
            [analysis['low_stopband_power'], analysis['passband_power'], analysis['high_stopband_power']])
    plt.title('Power Distribution Across Frequency Bands')
    plt.ylabel('Power')
    plt.tight_layout()
    plt.show()


def example_wavelet_denoising():
    """Example: Wavelet-based denoising."""
    print("=" * 60)
    print("Example 3: Wavelet Denoising")
    print("=" * 60)
    
    fs = 100
    t, signal, true_signal = generate_test_signal(fs)
    
    # Apply wavelet denoising
    denoiser = WaveletDenoiser(wavelet='db4', level=4, mode='soft')
    denoised = denoiser.denoise(signal)
    
    # Get scale information
    scale_info = denoiser.get_scale_info(signal)
    
    print(f"Decomposition Level: {scale_info['levels']}")
    print(f"Signal Length: {scale_info['signal_length']}")
    print(f"Approximation Power: {scale_info['approximation_power']:.4f}")
    print(f"Detail Powers: {[f'{p:.4f}' for p in scale_info['detail_powers']]}")
    
    # Plot results
    plt.figure(figsize=(12, 8))
    plt.subplot(3, 1, 1)
    plt.plot(t, true_signal, label='True Signal', linewidth=2)
    plt.plot(t, signal, label='Noisy Signal', alpha=0.5)
    plt.plot(t, denoised, label='Wavelet Denoised', linewidth=2)
    plt.legend()
    plt.title('Wavelet Denoising (db4, 4 levels, soft thresholding)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    
    plt.subplot(3, 1, 2)
    plt.plot(t, true_signal, label='True Signal', linewidth=2)
    plt.plot(t, denoised, label='Denoised', linewidth=2)
    plt.legend()
    plt.title('Comparison: True vs Wavelet-Denoised')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    
    plt.subplot(3, 1, 3)
    detail_powers = scale_info['detail_powers']
    plt.bar(range(1, len(detail_powers) + 1), detail_powers)
    plt.title('Energy Distribution Across Scales')
    plt.xlabel('Scale Level')
    plt.ylabel('Energy')
    plt.xticks(range(1, len(detail_powers) + 1))
    plt.tight_layout()
    plt.show()


def example_emd():
    """Example: Empirical Mode Decomposition."""
    print("=" * 60)
    print("Example 4: Empirical Mode Decomposition (EEMD)")
    print("=" * 60)
    
    fs = 100
    t, signal, true_signal = generate_test_signal(fs)
    
    # Apply EMD
    imfs, residue = design_and_apply_emd(signal, noise_level=0.1, n_ensembles=50)
    
    print(f"Number of IMFs: {len(imfs)}")
    for i, imf in enumerate(imfs):
        print(f"IMF {i+1}: Energy = {np.sum(imf**2):.4f}, Std = {np.std(imf):.4f}")
    print(f"Residue: Energy = {np.sum(residue**2):.4f}")
    
    # Plot results
    plt.figure(figsize=(12, 10))
    plt.subplot(len(imfs) + 2, 1, 1)
    plt.plot(t, true_signal, label='True Signal', linewidth=2)
    plt.plot(t, signal, label='Noisy Signal', alpha=0.5)
    plt.plot(t, residue, label='Residue', linestyle='--')
    plt.legend()
    plt.title('Original Signal and Residue')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    
    # Plot each IMF
    for i, imf in enumerate(imfs):
        plt.subplot(len(imfs) + 2, 1, i + 2)
        plt.plot(t, imf, label=f'IMF {i+1}', linewidth=1.5)
        plt.title(f'IMF {i+1} - Energy: {np.sum(imf**2):.4f}')
        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()


def example_kalman_filter():
    """Example: Kalman filtering."""
    print("=" * 60)
    print("Example 5: Kalman Filter")
    print("=" * 60)
    
    fs = 100
    t, signal, true_signal = generate_test_signal(fs)
    
    # Apply Kalman smoothing
    denoised = design_and_apply_kalman_filter(signal, smoothing=True)
    
    # Plot results
    plt.figure(figsize=(12, 8))
    plt.subplot(2, 1, 1)
    plt.plot(t, true_signal, label='True Signal', linewidth=2)
    plt.plot(t, signal, label='Noisy Signal', alpha=0.5)
    plt.plot(t, denoised, label='Kalman Smoothed', linewidth=2)
    plt.legend()
    plt.title('Kalman Smoothing (Constant Velocity Model)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    
    plt.subplot(2, 1, 2)
    plt.plot(t, true_signal - denoised, label='Error', linewidth=1.5)
    plt.title('Error: True Signal - Kalman Smoothed')
    plt.xlabel('Time (s)')
    plt.ylabel('Error')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # Run examples
    print("\n" + "=" * 60)
    print("SIGNAL PROCESSING MODULE EXAMPLES")
    print("=" * 60 + "\n")
    
    example_high_pass_filter()
    example_band_pass_filter()
    example_wavelet_denoising()
    example_emd()
    example_kalman_filter()
