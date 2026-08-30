"""
PCA-based Covariance Shrinkage

Reduces noise in covariance matrix estimation by projecting onto the
leading principal components. Useful for portfolio optimization.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional
from .pca import PCAAnalyzer


@dataclass
class ShrinkageResult:
    """Result of PCA covariance shrinkage."""
    shrunk_covariance: np.ndarray
    original_covariance: np.ndarray
    n_components: int
    shrinkage_ratio: float
    eigenvalues_original: np.ndarray
    eigenvalues_shrunk: np.ndarray

    @property
    def condition_number_original(self) -> float:
        """Condition number of original covariance."""
        eigs = self.eigenvalues_original
        return float(eigs[0] / eigs[-1]) if eigs[-1] > 1e-10 else float('inf')

    @property
    def condition_number_shrunk(self) -> float:
        """Condition number of shrunk covariance."""
        eigs = self.eigenvalues_shrunk
        positive = eigs[eigs > 1e-10]
        return float(positive[0] / positive[-1]) if len(positive) > 1 else 1.0


class CovarianceShrinkage:
    """
    Shrinks covariance matrix using PCA truncation.

    Replaces small eigenvalues (noise) with their average, improving
    the condition number and out-of-sample performance of Markowitz
    and other covariance-sensitive portfolios.
    """

    def __init__(self, n_components: Optional[int] = None,
                 variance_threshold: float = 0.90):
        """
        Parameters
        ----------
        n_components : int, optional
            Number of principal components to keep. If None, determined
            automatically by variance_threshold.
        variance_threshold : float
            Minimum cumulative variance to retain.
        """
        self.n_components = n_components
        self.variance_threshold = variance_threshold
        self._pca: Optional[PCAAnalyzer] = None

    def fit_shrink(self, returns: np.ndarray) -> ShrinkageResult:
        """
        Compute shrunk covariance matrix from return data.

        Parameters
        ----------
        returns : np.ndarray
            Return matrix (n_periods, n_assets).

        Returns
        -------
        ShrinkageResult
        """
        returns = np.asarray(returns, dtype=float)
        if returns.ndim == 1:
            returns = returns.reshape(-1, 1)

        n_periods, n_assets = returns.shape

        # Original sample covariance
        centered = returns - np.mean(returns, axis=0)
        cov_original = np.cov(centered, rowvar=False)
        if cov_original.ndim == 0:
            cov_original = cov_original.reshape(1, 1)

        # PCA
        self._pca = PCAAnalyzer()
        self._pca.fit(centered)

        eigenvalues = self._pca.explained_variance_.copy()

        # Determine components
        if self.n_components is not None:
            n_comp = min(self.n_components, n_assets)
        else:
            n_comp = self._pca.get_n_components_for_variance(
                self.variance_threshold)

        # Shrinkage: keep top eigenvalues, replace rest with mean of discarded
        shrunk_eigenvalues = eigenvalues.copy()
        if n_comp < n_assets:
            discarded_mean = np.mean(eigenvalues[n_comp:])
            shrunk_eigenvalues[n_comp:] = discarded_mean

        # Reconstruct covariance: V @ diag(lambda_shrunk) @ V.T
        V = self._pca.components_  # (n_components, n_assets) or (n_assets, n_assets)
        # Ensure V is full rank for reconstruction
        if V.shape[0] < n_assets:
            # Pad with zeros for discarded components
            V_full = np.zeros((n_assets, n_assets))
            V_full[:V.shape[0], :] = V
            # Add identity-like rows for the remaining
            for i in range(V.shape[0], n_assets):
                V_full[i, i % n_assets] = 1.0
            V = V_full

        shrunk_cov = V.T @ np.diag(shrunk_eigenvalues) @ V

        # Symmetrize
        shrunk_cov = (shrunk_cov + shrunk_cov.T) / 2

        return ShrinkageResult(
            shrunk_covariance=shrunk_cov,
            original_covariance=cov_original,
            n_components=n_comp,
            shrinkage_ratio=n_comp / n_assets,
            eigenvalues_original=eigenvalues,
            eigenvalues_shrunk=shrunk_eigenvalues,
        )

    def shrink(self, cov_matrix: np.ndarray) -> np.ndarray:
        """
        Shrink an existing covariance matrix using PCA truncation.

        Parameters
        ----------
        cov_matrix : np.ndarray
            Covariance matrix (n_assets, n_assets).

        Returns
        -------
        shrunk : np.ndarray
            Shrunk covariance matrix.
        """
        cov_matrix = np.asarray(cov_matrix, dtype=float)
        n = cov_matrix.shape[0]

        # Eigendecomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # Determine components
        if self.n_components is not None:
            n_comp = min(self.n_components, n)
        else:
            total = np.sum(eigenvalues)
            cumulative = np.cumsum(eigenvalues) / total
            n_comp = np.searchsorted(cumulative, self.variance_threshold) + 1

        # Shrink
        shrunk_eigenvalues = eigenvalues.copy()
        if n_comp < n:
            discarded_mean = np.mean(eigenvalues[n_comp:])
            shrunk_eigenvalues[n_comp:] = discarded_mean

        # Reconstruct
        shrunk = eigenvectors @ np.diag(shrunk_eigenvalues) @ eigenvectors.T
        shrunk = (shrunk + shrunk.T) / 2

        return shrunk
