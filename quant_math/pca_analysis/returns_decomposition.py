"""
Returns Decomposition using PCA

Decomposes asset returns into systematic (market) and idiosyncratic components.
Useful for risk attribution and portfolio construction.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List
from .pca import PCAAnalyzer


@dataclass
class DecompositionResult:
    """Result of PCA-based returns decomposition."""
    systematic: np.ndarray
    idiosyncratic: np.ndarray
    factor_betas: np.ndarray
    r_squared: float
    n_factors: int
    explained_variance_ratio: np.ndarray

    @property
    def systematic_risk(self) -> float:
        """Variance of systematic component."""
        return float(np.var(self.systematic))

    @property
    def idiosyncratic_risk(self) -> float:
        """Variance of idiosyncratic component."""
        return float(np.var(self.idiosyncratic))

    @property
    def risk_ratio(self) -> float:
        """Fraction of total risk that is systematic."""
        total = self.systematic_risk + self.idiosyncratic_risk
        return self.systematic_risk / total if total > 0 else 0.0


class ReturnsDecomposition:
    """
    Decomposes asset returns into systematic and idiosyncratic components
    using PCA factor extraction.
    """

    def __init__(self, n_factors: Optional[int] = None,
                 variance_threshold: float = 0.90):
        """
        Parameters
        ----------
        n_factors : int, optional
            Number of systematic factors to extract. If None, determined
            automatically by variance_threshold.
        variance_threshold : float
            Minimum cumulative variance to explain (used when n_factors is None).
        """
        self.n_factors = n_factors
        self.variance_threshold = variance_threshold
        self._pca: Optional[PCAAnalyzer] = None

    def decompose(self, returns: np.ndarray,
                  asset_names: Optional[List[str]] = None) -> DecompositionResult:
        """
        Decompose return matrix into systematic and idiosyncratic components.

        Parameters
        ----------
        returns : np.ndarray
            Matrix of shape (n_periods, n_assets) where each column is an
            asset's return series.
        asset_names : list of str, optional
            Asset names for debugging.

        Returns
        -------
        DecompositionResult
        """
        returns = np.asarray(returns, dtype=float)
        if returns.ndim == 1:
            returns = returns.reshape(-1, 1)

        n_periods, n_assets = returns.shape

        # Center returns
        mean_returns = np.mean(returns, axis=0)
        centered = returns - mean_returns

        # Fit PCA
        self._pca = PCAAnalyzer(n_components=self.n_factors)
        self._pca.fit(centered)

        # Determine number of factors
        if self.n_factors is None:
            n_factors = self._pca.get_n_components_for_variance(
                self.variance_threshold)
        else:
            n_factors = self.n_factors

        # Truncate to n_factors
        components = self._pca.components_[:n_factors]
        explained = self._pca.explained_variance_ratio_[:n_factors]

        # Factor scores (systematic component in factor space)
        factor_scores = centered @ components.T

        # Reconstruct systematic returns
        systematic = factor_scores @ components

        # Idiosyncratic = total - systematic
        idiosyncratic = centered - systematic

        # Factor betas (sensitivities of each asset to each factor)
        factor_betas = components.T  # (n_assets, n_factors)

        # R-squared (fraction of variance explained)
        total_var = np.sum(np.var(centered, axis=0))
        sys_var = np.sum(np.var(systematic, axis=0))
        r_squared = sys_var / total_var if total_var > 0 else 0.0

        return DecompositionResult(
            systematic=systematic,
            idiosyncratic=idiosyncratic,
            factor_betas=factor_betas,
            r_squared=r_squared,
            n_factors=n_factors,
            explained_variance_ratio=explained,
        )

    def get_factor_loadings(self, returns: np.ndarray) -> np.ndarray:
        """Get factor loadings (betas) for each asset."""
        result = self.decompose(returns)
        return result.factor_betas

    def predict_systematic(self, returns: np.ndarray,
                           n_factors: Optional[int] = None) -> np.ndarray:
        """Predict systematic component for new returns."""
        if self._pca is None:
            raise ValueError("Must call decompose() first.")

        returns = np.asarray(returns, dtype=float)
        centered = returns - self._pca.mean_

        components = self._pca.components_
        if n_factors is not None:
            components = components[:n_factors]

        factor_scores = centered @ components.T
        return factor_scores @ components
