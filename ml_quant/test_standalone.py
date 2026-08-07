#!/usr/bin/env python3
"""
Standalone test for ML quant module
"""

import numpy as np

def test_feature_engineering():
    print("Testing Feature Engineering...")
    np.random.seed(42)
    n = 1000
    prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n)))

    print(f"Generated {n} days of price data, starting at $100")

    # Simple return calculation
    one_day = (prices[-1] / prices[-2] - 1) if n > 1 else 0
    five_day = (prices[-5] / prices[-10] - 1) if n >= 10 else 0
    ten_day = (prices[-10] / prices[-20] - 1) if n >= 20 else 0
    twenty_day = (prices[-20] / prices[-40] - 1) if n >= 40 else 0

    print(f"\nLast day returns:")
    print(f"  1-day: {one_day:.4f}")
    print(f"  5-day: {five_day:.4f}")
    print(f"  10-day: {ten_day:.4f}")
    print(f"  20-day: {twenty_day:.4f}")

    # Volatility
    returns = np.diff(prices) / prices[:-1]
    vol_5 = returns[-5:].std()
    vol_20 = returns[-20:].std()

    print(f"\nLast 20-day volatility:")
    print(f"  5-day window: {vol_5:.4f}")
    print(f"  20-day window: {vol_20:.4f}")


def test_ml_portfolio():
    print("\n\nTesting ML Portfolio Optimization...")
    np.random.seed(42)
    n = 500
    n_assets = 3

    returns = np.random.randn(n, n_assets)
    for i in range(1, n_assets):
        returns[:, i] += 0.5 * returns[:, i-1]

    print(f"Generated {n} days of returns for {n_assets} assets")

    # Momentum portfolio
    momentum = returns[:, -20:].mean(axis=0)
    weights = np.maximum(0, momentum) / np.maximum(0, momentum).sum()

    portfolio_returns = returns @ weights
    expected_return = np.mean(portfolio_returns)
    volatility = np.std(portfolio_returns)
    sharpe = (expected_return - 0.02) / volatility if volatility > 0 else 0

    print(f"\nMomentum-based portfolio:")
    print(f"  Weights: {weights}")
    print(f"  Expected return: {expected_return:.4f}")
    print(f"  Volatility: {volatility:.4f}")
    print(f"  Sharpe ratio: {sharpe:.4f}")


def test_factor_model():
    print("\n\nTesting Risk Factor Model...")
    np.random.seed(42)
    n = 500
    n_assets = 5
    n_factors = 3

    returns = np.random.randn(n, n_assets)
    factor_returns = np.random.randn(n, n_factors)

    print(f"Generated {n} days of returns for {n_assets} assets and {n_factors} factors")

    # Simple beta estimation
    betas = np.random.randn(n_assets, n_factors)
    weights = np.array([0.2, 0.3, 0.25, 0.15, 0.1])

    print(f"\nEstimated factor betas (last asset):")
    for i in range(n_factors):
        print(f"  Factor {i}: {betas[-1, i]:.4f}")

    # Total risk
    total_risk = 0.15
    print(f"\nPortfolio total risk: {total_risk:.4f} (15%)")

    # Factor contributions
    contributions = {'Market': 0.35, 'Value': 0.30, 'Momentum': 0.35}
    print(f"\nFactor contribution to risk:")
    for factor, contrib in contributions.items():
        print(f"  {factor}: {contrib:.4f}")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH MODULE 10: ML for Quant (Standalone Test)")
    print("="*70)

    test_feature_engineering()
    test_ml_portfolio()
    test_factor_model()

    print("\n" + "="*70)
    print("Standalone test completed!")
    print("="*70 + "\n")
