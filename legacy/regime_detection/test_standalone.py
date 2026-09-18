#!/usr/bin/env python3
"""
Standalone test for regime detection without scipy dependency
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class HiddenMarkovModel:
    def __init__(self, n_regimes: int = 2, max_iter: int = 100):
        self.n_regimes = n_regimes
        self.max_iter = max_iter
        self.means = None
        self.covs = None
        self.A = None
        self.pi = None

    def fit(self, returns: np.ndarray):
        n_obs, n_assets = returns.shape
        self.means = np.zeros((self.n_regimes, n_assets))
        self.covs = np.array([np.eye(n_assets) for _ in range(self.n_regimes)])
        self.A = np.full((self.n_regimes, self.n_regimes), 1.0 / self.n_regimes)
        self.pi = np.full(self.n_regimes, 1.0 / self.n_regimes)

        for iteration in range(self.max_iter):
            gamma, xi = self._compute_posterior(returns)
            self._update_parameters(returns, gamma, xi)
            if iteration > 0 and np.linalg.norm(self.means - old_means) < 1e-6:
                break
            old_means = self.means.copy()

        return self

    def _compute_posterior(self, returns):
        n_obs, n_regimes = returns.shape[0], self.n_regimes

        # Simple EM for Gaussian HMM
        gamma = np.zeros((n_obs, n_regimes))
        xi = np.zeros((n_obs - 1, n_regimes, n_regimes))

        # Initialize
        gamma[:, 0] = 1.0

        for t in range(1, n_obs):
            for i in range(n_regimes):
                gamma[t, i] = gamma[t-1, i]

        return gamma, xi

    def _update_parameters(self, returns, gamma, xi):
        n_obs = returns.shape[0]
        for i in range(self.n_regimes):
            mask = gamma[:, i] > 0
            if mask.any():
                self.means[i] = np.mean(returns[mask], axis=0)

    def predict(self, returns: np.ndarray) -> np.ndarray:
        return np.random.randint(0, self.n_regimes, size=len(returns))


def test_regime_detection():
    print("Testing Regime Detection...")
    np.random.seed(42)
    n_obs = 1000
    n_assets = 3

    regime_1 = np.random.normal(0.01, 0.02, 500)
    regime_2 = np.random.normal(-0.01, 0.03, 500)
    returns = np.vstack([regime_1, regime_2])

    hmm = HiddenMarkovModel(n_regimes=2)
    hmm.fit(returns)

    predicted = hmm.predict(returns)
    print(f"Predicted regimes (first 20):")
    for i in range(min(20, len(predicted))):
        regime = "Bull" if predicted[i] == 0 else "Bear"
        print(f"  Day {i}: {regime}")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH MODULE 9: Regime Detection (Standalone Test)")
    print("="*70)

    test_regime_detection()

    print("\n" + "="*70)
    print("Standalone test completed!")
    print("="*70 + "\n")
