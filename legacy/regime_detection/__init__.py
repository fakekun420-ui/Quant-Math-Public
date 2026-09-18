"""
Regime Detection Module

This module provides tools for detecting and analyzing market regimes including:
- Hidden Markov Models (HMM) for regime classification
- Regime switching models
- Regime stability analysis
- Regime transition matrices
- Regime clustering (k-means, hierarchical)
"""

from .regime_detection import (
    HiddenMarkovModel, RegimeDetector, RegimeClusterer
)

__version__ = "1.5.0"
__all__ = [
    'HiddenMarkovModel',
    'RegimeDetector',
    'RegimeClusterer'
]
