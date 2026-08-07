"""
Principal Component Analysis (PCA)

This module provides tools for dimensionality reduction using PCA.
"""

from .pca import (
    PCAAnalyzer,
    compute_pca,
    pca_denoising,
    PCAResult
)

__all__ = [
    'PCAAnalyzer',
    'compute_pca',
    'pca_denoising',
    'PCAResult'
]
