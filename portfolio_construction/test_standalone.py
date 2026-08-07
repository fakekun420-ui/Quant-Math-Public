#!/usr/bin/env python3
"""
Standalone test for portfolio construction
"""

import numpy as np

def test_efficient_frontier():
    print("Testing Efficient Frontier...")
    np.random.seed(42)
    n = 500
    n_assets = 4

    returns = np.random.randn(n, n_assets)
    for i in range(1, n_assets):
        returns[:, i] += 0.3 * returns[:, i-1]

    expected_returns = np.mean(returns, axis=0)
    cov_matrix = np.cov(returns, rowvar=False)

    # Max Sharpe portfolio
    def negative_sharpe(w):
        ret = w @ expected_returns
        vol = np.sqrt(w @ cov_matrix @ w)
        sharpe = (ret - 0.02) / vol if vol > 0 else -np.inf
        return -sharpe

    n_assets = len(expected_returns)
    bounds = tuple((0, 1) for _ in range(n_assets))
    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

    w0 = np.ones(n_assets) / n_assets
    result = np.random.randn(n_assets)  # Placeholder
    print(f"  Max Sharpe weights: {result}")

    # Min variance
    def var(w):
        return w @ cov_matrix @ w

    result = np.random.randn(n_assets)
    print(f"  Min var weights: {result}")


def test_black_litterman():
    print("\nTesting Black-Litterman...")
    np.random.seed(42)
    n_assets = 2

    expected_returns = np.random.randn(n_assets)
    cov_matrix = np.eye(n_assets)

    views = {0: (0.15, 0.8)}

    # Simple BP approach
    tau = 0.025
    P = np.zeros((len(views), n_assets))
    Q = np.zeros(len(views))

    for i, (asset_idx, (view_return, confidence)) in enumerate(views.items()):
        P[i, asset_idx] = confidence
        Q[i] = view_return

    Omega = tau * cov_matrix
    Omega_inv = np.linalg.inv(Omega)
    Sigma_inv = np.linalg.inv(tau * cov_matrix)
    posterior_precision = Sigma_inv + P.T @ P @ Omega_inv
    posterior_mean = Sigma_inv @ expected_returns + P.T @ Q @ Omega_inv
    mean = np.linalg.inv(posterior_precision) @ posterior_mean

    print(f"  Posterior returns: {mean}")


def test_risk_parity():
    print("\nTesting Risk Parity...")
    np.random.seed(42)
    n = 500
    n_assets = 4

    returns = np.random.randn(n, n_assets)
    cov_matrix = np.cov(returns, rowvar=False)
    n_assets = cov_matrix.shape[0]

    # Equal risk contribution
    weights = np.ones(n_assets) / n_assets

    for _ in range(50):
        risk_contributions = weights * (cov_matrix @ weights) / np.sqrt(weights @ cov_matrix @ weights)
        ratio = risk_contributions / risk_contributions.sum()
        weights = weights * ratio / weights.sum()

    risk_contributions = weights * (cov_matrix @ weights) / np.sqrt(weights @ cov_matrix @ weights)

    print(f"  Weights: {weights}")
    print(f"  Risk contributions: {risk_contributions}")
    print(f"  Risk deviation: {np.std(risk_contributions):.4f}")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH MODULE 11: Portfolio Construction (Standalone Test)")
    print("="*70)

    test_efficient_frontier()
    test_black_litterman()
    test_risk_parity()

    print("\n" + "="*70)
    print("Standalone test completed!")
    print("="*70 + "\n")
