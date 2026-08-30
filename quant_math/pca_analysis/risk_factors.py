"""
Risk Factor Analysis using PCA

Extracts risk factors from asset return covariance structure.
Useful for understanding risk drivers and constructing factor portfolios.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List
from .pca import PCAAnalyzer


@dataclass
class FactorLoadings:
    """Risk factor loadings and statistics."""
    loadings: np.ndarray
    eigenvalues: np.ndarray
    variance_explained: np.ndarray
    cumulative_variance: np.ndarray
    n_factors: int
    asset_names: Optional[List[str]] = None

    @property
    def n_assets(self) -> int:
        return self.loadings.shape[0]

    def get_dominant_assets(self, factor_idx: int, top_n: int = 5) -> List[tuple]:
        """Get assets with highest absolute loading on a given factor."""
        loadings = np.abs(self.loadings[:, factor_idx])
        top_idx = np.argsort(loadings)[::-1][:top_n]
        result = []
        for i in top_idx:
            name = self.asset_names[i] if self.asset_names else f"asset_{i}"
            result.append((name, float(self.loadings[i, factor_idx])))
        return result

    def get_factor_correlation(self) -> np.ndarray:
        """Get correlation matrix between factors (should be ~diagonal)."""
        # Factor returns are orthogonal by construction
        return np.eye(self.n_factors)


class RiskFactorAnalyzer:
    """
    Extracts risk factors from return covariance structure using PCA.

    The first principal component typically represents market risk (beta),
    the second represents a spread/curve factor, etc.
    """

    def __init__(self, n_factors: Optional[int] = None,
                 variance_threshold: float = 0.90):
        self.n_factors = n_factors
        self.variance_threshold = variance_threshold
        self._pca: Optional[PCAAnalyzer] = None

    def fit(self, returns: np.ndarray,
            asset_names: Optional[List[str]] = None) -> FactorLoadings:
        """
        Fit risk factor model to return data.

        Parameters
        ----------
        returns : np.ndarray
            Return matrix (n_periods, n_assets).
        asset_names : list of str, optional
            Asset names.

        Returns
        -------
        FactorLoadings
        """
        returns = np.asarray(returns, dtype=float)
        if returns.ndim == 1:
            returns = returns.reshape(-1, 1)

        n_periods, n_assets = returns.shape

        # Center
        mean_ret = np.mean(returns, axis=0)
        centered = returns - mean_ret

        # Fit PCA
        self._pca = PCAAnalyzer(n_components=self.n_factors)
        self._pca.fit(centered)

        # Determine factors
        if self.n_factors is None:
            n_factors = self._pca.get_n_components_for_variance(
                self.variance_threshold)
        else:
            n_factors = self.n_factors

        return FactorLoadings(
            loadings=self._pca.components_[:n_factors].T,  # (n_assets, n_factors)
            eigenvalues=self._pca.explained_variance_[:n_factors],
            variance_explained=self._pca.explained_variance_ratio_[:n_factors],
            cumulative_variance=np.cumsum(
                self._pca.explained_variance_ratio_[:n_factors]),
            n_factors=n_factors,
            asset_names=asset_names,
        )

    def transform(self, returns: np.ndarray) -> np.ndarray:
        """Transform returns to factor space."""
        if self._pca is None:
            raise ValueError("Must call fit() first.")
        returns = np.asarray(returns, dtype=float)
        centered = returns - self._pca.mean_
        return centered @ self._pca.components_[:self.n_factors].T

    def reconstruct(self, factor_returns: np.ndarray) -> np.ndarray:
        """Reconstruct asset returns from factor returns."""
        if self._pca is None:
            raise ValueError("Must call fit() first.")
        factor_returns = np.asarray(factor_returns, dtype=float)
        return factor_returns @ self._pca.components_[:self.n_factors] + self._pca.mean_
