"""
Regime Detection Module

This module provides tools for detecting and analyzing market regimes including:
- Hidden Markov Models (HMM) for regime classification
- Regime switching models
- Regime stability analysis
- Regime transition matrices
- Regime clustering (k-means, hierarchical)
- Regime feature importance
"""

import numpy as np
from typing import Tuple, Dict, List, Any, Optional
from scipy.stats import multivariate_normal
from dataclasses import dataclass
import warnings


@dataclass
class Regime:
    """Represents a market regime."""
    regime_id: int
    mean: np.ndarray
    cov_matrix: np.ndarray
    volatility: float
    sharpe_ratio: float
    duration: int = 0
    occurrences: int = 0


@dataclass
class RegimeResult:
    """Result of regime detection."""
    regimes: List[Regime]
    transition_matrix: np.ndarray
    current_regime: int
    regime_probabilities: np.ndarray
    regime_sharpe_ratios: np.ndarray


class HiddenMarkovModel:
    """
    Hidden Markov Model for Regime Detection

    Uses Baum-Welch algorithm for parameter estimation.
    """

    def __init__(self, n_regimes: int = 2, max_iter: int = 100):
        """
        Initialize HMM.

        Parameters
        ----------
        n_regimes : int
            Number of hidden states (regimes)
        max_iter : int
            Maximum number of EM iterations
        """
        self.n_regimes = n_regimes
        self.max_iter = max_iter

        # Transition matrix (learned)
        self.A = None

        # Emission parameters (means and covariances)
        self.means = None
        self.covs = None
        self.pi = None  # Initial state probabilities

    def fit(self, returns: np.ndarray) -> 'HiddenMarkovModel':
        """
        Fit HMM to returns data.

        Parameters
        ----------
        returns : np.ndarray
            Asset returns (n_observations x n_assets)

        Returns
        -------
        self : HiddenMarkovModel
            Fitted model
        """
        n_obs = returns.shape[0]
        n_assets = returns.shape[1]

        # Initialize parameters
        self.means = np.zeros((self.n_regimes, n_assets))
        self.covs = np.array([np.eye(n_assets) for _ in range(self.n_regimes)])
        self.A = np.full((self.n_regimes, self.n_regimes), 1.0 / self.n_regimes)
        self.pi = np.full(self.n_regimes, 1.0 / self.n_regimes)

        # Baum-Welch algorithm
        for iteration in range(self.max_iter):
            # E-step: Compute posterior probabilities
            gamma, xi = self._compute_posterior(returns)

            # M-step: Update parameters
            self._update_parameters(returns, gamma, xi)

            # Check convergence
            if iteration > 0 and np.linalg.norm(self.means - old_means) < 1e-6:
                break

            old_means = self.means.copy()

        return self

    def _compute_posterior(self, returns: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute posterior probabilities using forward-backward algorithm.
        """
        n_obs = returns.shape[0]
        n_regimes = self.n_regimes

        # Forward pass
        alpha = np.zeros((n_obs, n_regimes))
        alpha[0] = self.pi * self._emission_pdf(returns[0], 0)

        for t in range(1, n_obs):
            alpha[t] = self._emission_pdf(returns[t], 0) * (alpha[t-1] @ self.A)

        # Normalize
        alpha = alpha / alpha.sum(axis=1, keepdims=True)

        # Backward pass
        beta = np.zeros((n_obs, n_regimes))
        beta[-1] = 1.0

        for t in range(n_obs - 2, -1, -1):
            beta[t] = self.A @ (self._emission_pdf(returns[t+1], 0) * beta[t+1])
            beta[t] = beta[t] / beta[t].sum()

        # Compute gamma and xi
        gamma = alpha * beta
        gamma = gamma / gamma.sum(axis=1, keepdims=True)

        xi = np.zeros((n_obs - 1, n_regimes, n_regimes))
        for t in range(n_obs - 1):
            denominator = alpha[t] @ self.A * self._emission_pdf(returns[t+1], 0) * beta[t+1]
            for i in range(n_regimes):
                for j in range(n_regimes):
                    xi[t, i, j] = alpha[t, i] * self.A[i, j] * \
                                  self._emission_pdf(returns[t+1], 0) * beta[t+1, j]

        xi = xi / denominator

        return gamma, xi

    def _emission_pdf(self, x: np.ndarray, regime_id: int) -> np.ndarray:
        """Compute emission probability density function."""
        return multivariate_normal.pdf(x, mean=self.means[regime_id],
                                       cov=self.covs[regime_id],
                                       allow_singular=True)

    def _update_parameters(self, returns: np.ndarray,
                          gamma: np.ndarray, xi: np.ndarray):
        """Update model parameters (M-step)."""
        n_obs = returns.shape[0]

        # Update means
        for i in range(self.n_regimes):
            denominator = gamma[:, i].sum()
            if denominator > 0:
                self.means[i] = (returns.T @ gamma[:, i]) / denominator

        # Update covariances
        for i in range(self.n_regimes):
            numerator = np.zeros((returns.shape[1], returns.shape[1]))
            for t in range(n_obs):
                diff = returns[t] - self.means[i]
                numerator += gamma[t, i] * np.outer(diff, diff)
            self.covs[i] = numerator / gamma[:, i].sum()

        # Update transition matrix
        for i in range(self.n_regimes):
            denominator = gamma[:-1, i].sum()
            if denominator > 0:
                for j in range(self.n_regimes):
                    self.A[i, j] = xi[:, i, j].sum() / denominator

        # Renormalize transition matrix
        self.A = self.A / self.A.sum(axis=1, keepdims=True)

    def predict(self, returns: np.ndarray) -> np.ndarray:
        """
        Predict most likely regimes.

        Parameters
        ----------
        returns : np.ndarray
            Returns data

        Returns
        -------
        regimes : np.ndarray
            Predicted regime sequence
        """
        n_obs = returns.shape[0]
        n_regimes = self.n_regimes

        # Forward pass
        alpha = np.zeros((n_obs, n_regimes))
        alpha[0] = self.pi * self._emission_pdf(returns[0], 0)

        for t in range(1, n_obs):
            alpha[t] = self._emission_pdf(returns[t], 0) * (alpha[t-1] @ self.A)
            alpha[t] = alpha[t] / alpha[t].sum()

        # Most likely state at each time step
        regimes = np.argmax(alpha, axis=1)

        return regimes

    def get_regime_statistics(self, returns: np.ndarray) -> List[Regime]:
        """
        Get regime statistics (mean, volatility, Sharpe ratio).
        """
        regimes = self.predict(returns)

        regime_stats = []
        for i in range(self.n_regimes):
            regime_returns = returns[regimes == i]
            mean = np.mean(regime_returns)
            vol = np.std(regime_returns)
            sharpe = (mean - 0.02) / vol if vol > 0 else 0

            regime = Regime(
                regime_id=i,
                mean=mean,
                cov_matrix=self.covs[i],
                volatility=vol,
                sharpe_ratio=sharpe,
                duration=0,
                occurrences=len(regime_returns)
            )
            regime_stats.append(regime)

        return regime_stats


class RegimeDetector:
    """
    Regime Detection Framework

    Combines multiple detection methods for robust regime identification.
    """

    def __init__(self, n_regimes: int = 2):
        """
        Initialize regime detector.

        Parameters
        ----------
        n_regimes : int
            Number of regimes to detect
        """
        self.n_regimes = n_regimes
        self.hmm = HiddenMarkovModel(n_regimes=n_regimes)

    def fit(self, returns: np.ndarray) -> 'RegimeDetector':
        """
        Fit regime detection model.

        Parameters
        ----------
        returns : np.ndarray
            Returns data (n_observations x n_assets)

        Returns
        -------
        self : RegimeDetector
            Fitted detector
        """
        self.hmm.fit(returns)
        return self

    def predict(self, returns: np.ndarray) -> np.ndarray:
        """
        Predict regimes.

        Parameters
        ----------
        returns : np.ndarray
            Returns data

        Returns
        -------
        regimes : np.ndarray
            Predicted regime sequence
        """
        return self.hmm.predict(returns)

    def analyze(self, returns: np.ndarray) -> RegimeResult:
        """
        Perform comprehensive regime analysis.

        Parameters
        ----------
        returns : np.ndarray
            Returns data

        Returns
        -------
        result : RegimeResult
            Analysis results
        """
        regimes = self.predict(returns)
        regime_stats = self.hmm.get_regime_statistics(returns)

        # Calculate transition matrix
        n_obs = len(regimes)
        transition_matrix = np.zeros((self.n_regimes, self.n_regimes))
        for t in range(n_obs - 1):
            transition_matrix[regimes[t], regimes[t+1]] += 1

        # Normalize
        row_sums = transition_matrix.sum(axis=1, keepdims=True)
        transition_matrix = transition_matrix / row_sums

        # Current regime (most recent)
        current_regime = regimes[-1]

        # Regime probabilities
        regime_probs = []
        for i in range(self.n_regimes):
            prob = np.sum(regimes == i) / n_obs
            regime_probs.append(prob)

        regime_sharpe_ratios = np.array([stat.sharpe_ratio for stat in regime_stats])

        return RegimeResult(
            regimes=regime_stats,
            transition_matrix=transition_matrix,
            current_regime=current_regime,
            regime_probabilities=np.array(regime_probs),
            regime_sharpe_ratios=regime_sharpe_ratios
        )


class RegimeClusterer:
    """
    Regime Clustering

    Clusters returns data into regimes using unsupervised methods.
    """

    def __init__(self, method: str = 'kmeans'):
        """
        Initialize clusterer.

        Parameters
        ----------
        method : str
            Clustering method ('kmeans', 'hierarchical')
        """
        self.method = method

    def fit(self, returns: np.ndarray, n_clusters: int = 2) -> np.ndarray:
        """
        Fit clustering model.

        Parameters
        ----------
        returns : np.ndarray
            Returns data (n_observations x n_assets)
        n_clusters : int
            Number of clusters

        Returns
        -------
        labels : np.ndarray
            Cluster assignments
        """
        if self.method == 'kmeans':
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            labels = kmeans.fit_predict(returns)
        elif self.method == 'hierarchical':
            from sklearn.cluster import AgglomerativeClustering
            clustering = AgglomerativeClustering(n_clusters=n_clusters)
            labels = clustering.fit_predict(returns)
        else:
            raise ValueError(f"Unknown method: {self.method}")

        return labels

    def get_regime_statistics(self, returns: np.ndarray, labels: np.ndarray) -> List[Regime]:
        """Get statistics for each cluster."""
        regime_stats = []

        for i in range(len(np.unique(labels))):
            regime_returns = returns[labels == i]
            mean = np.mean(regime_returns)
            vol = np.std(regime_returns)
            sharpe = (mean - 0.02) / vol if vol > 0 else 0

            regime = Regime(
                regime_id=i,
                mean=mean,
                cov_matrix=np.eye(returns.shape[1]),
                volatility=vol,
                sharpe_ratio=sharpe,
                duration=0,
                occurrences=len(regime_returns)
            )
            regime_stats.append(regime)

        return regime_stats
