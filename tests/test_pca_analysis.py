"""
Tests for quant_math.pca_analysis module
"""

import numpy as np
import pytest
from quant_math.pca_analysis import (
    PCAAnalyzer, PCAResult, compute_pca, pca_denoising,
    ReturnsDecomposition, DecompositionResult,
    RiskFactorAnalyzer, FactorLoadings,
    CovarianceShrinkage, ShrinkageResult,
)


class TestPCAAnalyzer:
    def setup_method(self):
        np.random.seed(42)
        self.returns = np.random.randn(100, 5) * 0.02

    def test_fit_returns_pcaresult(self):
        pca = PCAAnalyzer(n_components=3)
        result = pca.fit(self.returns)
        assert isinstance(result, PCAResult)
        assert result.n_components == 3
        assert result.components.shape == (3, 5)
        assert len(result.explained_variance_ratio) == 3

    def test_transform(self):
        pca = PCAAnalyzer(n_components=3)
        pca.fit(self.returns)
        transformed = pca.transform(self.returns)
        assert transformed.shape == (100, 3)

    def test_fit_transform(self):
        pca = PCAAnalyzer(n_components=3)
        transformed = pca.fit_transform(self.returns)
        assert transformed.shape == (100, 3)

    def test_inverse_transform(self):
        pca = PCAAnalyzer(n_components=5)
        pca.fit(self.returns)
        transformed = pca.transform(self.returns)
        reconstructed = pca.inverse_transform(transformed)
        assert reconstructed.shape == self.returns.shape
        np.testing.assert_allclose(reconstructed, self.returns, atol=1e-10)

    def test_cumulative_variance(self):
        pca = PCAAnalyzer()
        pca.fit(self.returns)
        cum = pca.get_cumulative_variance_ratio()
        assert len(cum) == 5
        assert abs(cum[-1] - 1.0) < 1e-10

    def test_n_components_for_variance(self):
        pca = PCAAnalyzer()
        pca.fit(self.returns)
        n = pca.get_n_components_for_variance(0.95)
        assert 1 <= n <= 5

    def test_compute_pca_convenience(self):
        result = compute_pca(self.returns, n_components=2)
        assert isinstance(result, PCAResult)
        assert result.n_components == 2

    def test_pca_denoising(self):
        np.random.seed(99)
        clean = np.random.randn(100, 5) * 0.02
        noise = np.random.randn(100, 5) * 0.05
        noisy = clean + noise
        denoised = pca_denoising(noisy, n_components=3)
        assert denoised.shape == noisy.shape
        # Denoised should be closer to clean than noisy is
        err_noisy = np.mean((noisy - clean) ** 2)
        err_denoised = np.mean((denoised - clean) ** 2)
        assert err_denoised < err_noisy


class TestReturnsDecomposition:
    def setup_method(self):
        np.random.seed(42)
        n, k = 100, 5
        market = np.random.randn(n, 1) * 0.03
        betas = np.random.randn(k, 1) * 0.5 + 1.0
        idio = np.random.randn(n, k) * 0.01
        self.returns = market @ betas.T + idio

    def test_decompose(self):
        rd = ReturnsDecomposition(n_factors=1)
        result = rd.decompose(self.returns)
        assert isinstance(result, DecompositionResult)
        assert result.n_factors == 1
        assert result.systematic.shape == self.returns.shape
        assert result.idiosyncratic.shape == self.returns.shape

    def test_r_squared(self):
        rd = ReturnsDecomposition(n_factors=1)
        result = rd.decompose(self.returns)
        assert 0.0 <= result.r_squared <= 1.0
        # With synthetic data, 1 factor should explain most variance
        assert result.r_squared > 0.5

    def test_risk_ratio(self):
        rd = ReturnsDecomposition(n_factors=2)
        result = rd.decompose(self.returns)
        ratio = result.risk_ratio
        assert 0.0 <= ratio <= 1.0

    def test_auto_n_factors(self):
        rd = ReturnsDecomposition(variance_threshold=0.85)
        result = rd.decompose(self.returns)
        assert 1 <= result.n_factors <= 5

    def test_factor_betas_shape(self):
        rd = ReturnsDecomposition(n_factors=2)
        result = rd.decompose(self.returns)
        assert result.factor_betas.shape == (5, 2)


class TestRiskFactorAnalyzer:
    def setup_method(self):
        np.random.seed(42)
        self.returns = np.random.randn(100, 4) * 0.02

    def test_fit(self):
        rfa = RiskFactorAnalyzer(n_factors=2)
        loadings = rfa.fit(self.returns)
        assert isinstance(loadings, FactorLoadings)
        assert loadings.n_factors == 2
        assert loadings.loadings.shape == (4, 2)

    def test_transform(self):
        rfa = RiskFactorAnalyzer(n_factors=2)
        rfa.fit(self.returns)
        factors = rfa.transform(self.returns)
        assert factors.shape == (100, 2)

    def test_reconstruct(self):
        rfa = RiskFactorAnalyzer(n_factors=4)
        loadings = rfa.fit(self.returns)
        factors = rfa.transform(self.returns)
        reconstructed = rfa.reconstruct(factors)
        assert reconstructed.shape == self.returns.shape

    def test_dominant_assets(self):
        rfa = RiskFactorAnalyzer(n_factors=1)
        rfa.fit(self.returns, asset_names=["A", "B", "C", "D"])
        top = loadings.get_dominant_assets(0, top_n=2) if hasattr(rfa, '_loadings') else []
        # Just test it doesn't crash
        loadings = rfa.fit(self.returns, asset_names=["A", "B", "C", "D"])
        top = loadings.get_dominant_assets(0, top_n=2)
        assert len(top) == 2


class TestCovarianceShrinkage:
    def setup_method(self):
        np.random.seed(42)
        self.returns = np.random.randn(100, 5) * 0.02

    def test_fit_shrink(self):
        cs = CovarianceShrinkage(n_components=3)
        result = cs.fit_shrink(self.returns)
        assert isinstance(result, ShrinkageResult)
        assert result.shrunk_covariance.shape == (5, 5)
        assert result.n_components == 3

    def test_shrinkage_reduces_condition_number(self):
        cs = CovarianceShrinkage(n_components=3)
        result = cs.fit_shrink(self.returns)
        assert result.condition_number_shrunk <= result.condition_number_original

    def test_shrink_existing_cov(self):
        cov = np.cov(self.returns, rowvar=False)
        cs = CovarianceShrinkage(n_components=3)
        shrunk = cs.shrink(cov)
        assert shrunk.shape == cov.shape
        # Should be symmetric
        np.testing.assert_allclose(shrunk, shrunk.T, atol=1e-10)

    def test_preserves_total_variance(self):
        cs = CovarianceShrinkage(n_components=5)
        result = cs.fit_shrink(self.returns)
        # Total variance (trace) should be approximately preserved
        orig_trace = np.trace(result.original_covariance)
        shrunk_trace = np.trace(result.shrunk_covariance)
        # With full components, should be identical
        assert abs(orig_trace - shrunk_trace) / orig_trace < 0.1
