"""
PCA Analysis for Quantitative Finance

Provides PCA decomposition, risk factor analysis, covariance shrinkage,
and signal denoising for financial time series.
"""

from .pca import PCAAnalyzer, PCAResult, compute_pca, pca_denoising
from .returns_decomposition import ReturnsDecomposition, DecompositionResult
from .risk_factors import RiskFactorAnalyzer, FactorLoadings
from .covariance_shrinkage import CovarianceShrinkage, ShrinkageResult

__all__ = [
    'PCAAnalyzer',
    'PCAResult',
    'compute_pca',
    'pca_denoising',
    'ReturnsDecomposition',
    'DecompositionResult',
    'RiskFactorAnalyzer',
    'FactorLoadings',
    'CovarianceShrinkage',
    'ShrinkageResult',
]
