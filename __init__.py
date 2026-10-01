"""
QUANT-MATH: Quantitative Trading Framework

A modular research framework for quantitative trading systems.
All modules consolidated under quant_math/ package.
"""

from __future__ import annotations

__version__ = "1.5.0"
__author__ = "QUANT-MATH Team"
__all__ = [
    # Expectation
    'SharpeMetrics',
    'StatisticalTests',

    # Risk
    'KellyCriterion',
    'kelly_fraction',
    'RiskManager',
    'PositionSizer',
    'ValueAtRisk',
    'ExpectedShortfall',

    # Monte Carlo

    # Optimization
    'MeanVarianceOptimizer',
    'AdaptiveSizer',

    # PCA
    'PCAAnalyzer',
    'ReturnsDecomposition',
    'RiskFactorAnalyzer',
    'CovarianceShrinkage',
]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in ('SharpeMetrics', 'StatisticalTests'):
        from quant_math.expectation import SharpeMetrics, StatisticalTests
        return locals()[name]
    if name in ('KellyCriterion', 'kelly_fraction', 'RiskManager', 'PositionSizer', 'ValueAtRisk', 'ExpectedShortfall'):
        from quant_math.risk import KellyCriterion, kelly_fraction, RiskManager, PositionSizer, ValueAtRisk, ExpectedShortfall
        return locals()[name]
    if name in ('MeanVarianceOptimizer', 'AdaptiveSizer'):
        from legacy.optimization import MeanVarianceOptimizer, AdaptiveSizer
        return locals()[name]
    if name in ('PCAAnalyzer', 'ReturnsDecomposition', 'RiskFactorAnalyzer', 'CovarianceShrinkage'):
        from quant_math.pca_analysis import PCAAnalyzer, ReturnsDecomposition, RiskFactorAnalyzer, CovarianceShrinkage
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
