"""
PCA Analysis Module

Provides Principal Component Analysis implementation for dimensionality reduction
and feature extraction in financial time series analysis.
"""

import numpy as np
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PCAResult:
    """Result of PCA computation."""
    components: np.ndarray
    explained_variance: np.ndarray
    explained_variance_ratio: np.ndarray
    singular_values: np.ndarray
    mean: np.ndarray
    n_components: int


class PCAAnalyzer:
    """
    Principal Component Analysis (PCA) Analyzer

    Performs PCA on financial data for dimensionality reduction
    and noise filtering.
    """

    def __init__(self, n_components: Optional[int] = None,
                 whiten: bool = False,
                 random_state: Optional[int] = None):
        """
        Initialize PCA analyzer.

        Parameters
        ----------
        n_components : int, optional
            Number of components to keep. If None, keeps all.
        whiten : bool
            Whether to whiten the components (unit variance)
        random_state : int, optional
            Random seed for reproducibility
        """
        self.n_components = n_components
        self.whiten = whiten
        self.random_state = random_state
        
        self.components_ = None
        self.explained_variance_ = None
        self.explained_variance_ratio_ = None
        self.singular_values_ = None
        self.mean_ = None
        self.n_features_in_ = None

    def fit(self, X: np.ndarray) -> 'PCAResult':
        """
        Fit PCA model to data.

        Parameters
        ----------
        X : np.ndarray
            Training data (n_samples, n_features)

        Returns
        -------
        result : PCAResult
            Fitted PCA results
        """
        X = np.asarray(X)
        n_samples, n_features = X.shape
        
        self.n_features_in_ = n_features
        
        # Center the data
        self.mean_ = np.mean(X, axis=0)
        X_centered = X - self.mean_
        
        # Compute SVD
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        
        # Components are the right singular vectors
        self.components_ = Vt
        
        # Explained variance
        self.explained_variance_ = (S ** 2) / (n_samples - 1)
        
        # Total variance
        total_variance = np.sum(self.explained_variance_)
        self.explained_variance_ratio_ = self.explained_variance_ / total_variance
        
        self.singular_values_ = S
        
        # Determine number of components to keep
        if self.n_components is None:
            n_components = n_features
        else:
            n_components = min(self.n_components, n_features)
        
        # Truncate components if needed
        if n_components < n_features:
            self.components_ = self.components_[:n_components]
            self.explained_variance_ = self.explained_variance_[:n_components]
            self.explained_variance_ratio_ = self.explained_variance_ratio_[:n_components]
            self.singular_values_ = self.singular_values_[:n_components]
        
        # Whiten if requested
        if self.whiten:
            self.components_ = self.components_ / np.sqrt(self.explained_variance_[:, np.newaxis])
        
        return PCAResult(
            components=self.components_,
            explained_variance=self.explained_variance_,
            explained_variance_ratio=self.explained_variance_ratio_,
            singular_values=self.singular_values_,
            mean=self.mean_,
            n_components=n_components
        )

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Transform data to PCA space.

        Parameters
        ----------
        X : np.ndarray
            Data to transform (n_samples, n_features)

        Returns
        -------
        X_transformed : np.ndarray
            Transformed data (n_samples, n_components)
        """
        if self.components_ is None:
            raise ValueError("PCA not fitted yet. Call fit() first.")
        
        X = np.asarray(X)
        X_centered = X - self.mean_
        return X_centered @ self.components_.T

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """
        Fit PCA and transform data.

        Parameters
        ----------
        X : np.ndarray
            Training data

        Returns
        -------
        X_transformed : np.ndarray
            Transformed data
        """
        self.fit(X)
        return self.transform(X)

    def inverse_transform(self, X_transformed: np.ndarray) -> np.ndarray:
        """
        Reconstruct original data from transformed data.

        Parameters
        ----------
        X_transformed : np.ndarray
            Transformed data (n_samples, n_components)

        Returns
        -------
        X_reconstructed : np.ndarray
            Reconstructed data (n_samples, n_features)
        """
        if self.components_ is None:
            raise ValueError("PCA not fitted yet. Call fit() first.")
        
        return X_transformed @ self.components_ + self.mean_

    def get_cumulative_variance_ratio(self) -> np.ndarray:
        """
        Get cumulative explained variance ratio.

        Returns
        -------
        cumulative_ratio : np.ndarray
            Cumulative variance ratio
        """
        if self.explained_variance_ratio_ is None:
            raise ValueError("PCA not fitted yet.")
        return np.cumsum(self.explained_variance_ratio_)

    def get_n_components_for_variance(self, variance_threshold: float = 0.95) -> int:
        """
        Get number of components needed to explain variance threshold.

        Parameters
        ----------
        variance_threshold : float
            Minimum variance to explain (0-1)

        Returns
        -------
        n_components : int
            Number of components needed
        """
        if self.explained_variance_ratio_ is None:
            raise ValueError("PCA not fitted yet.")
        
        cumulative = np.cumsum(self.explained_variance_ratio_)
        return np.searchsorted(cumulative, variance_threshold) + 1


def compute_pca(X: np.ndarray, n_components: Optional[int] = None,
                whiten: bool = False) -> PCAResult:
    """
    Convenience function to compute PCA.

    Parameters
    ----------
    X : np.ndarray
        Data matrix (n_samples, n_features)
    n_components : int, optional
        Number of components
    whiten : bool
        Whether to whiten

    Returns
    -------
    result : PCAResult
        PCA results
    """
    analyzer = PCAAnalyzer(n_components=n_components, whiten=whiten)
    return analyzer.fit(X)


def pca_denoising(X: np.ndarray, n_components: Optional[int] = None,
                  variance_threshold: float = 0.95) -> np.ndarray:
    """
    Denoise data using PCA reconstruction.

    Parameters
    ----------
    X : np.ndarray
        Noisy data (n_samples, n_features)
    n_components : int, optional
        Number of components to keep
    variance_threshold : float
        If n_components is None, use this threshold to determine components

    Returns
    -------
    X_denoised : np.ndarray
        Denoised data
    """
    if n_components is None:
        analyzer = PCAAnalyzer()
        analyzer.fit(X)
        n_components = analyzer.get_n_components_for_variance(variance_threshold)
    
    analyzer = PCAAnalyzer(n_components=n_components)
    analyzer.fit(X)
    X_transformed = analyzer.transform(X)
    return analyzer.inverse_transform(X_transformed)