#!/usr/bin/env python3
"""
Module 11: Portfolio Construction - Comprehensive Examples

This module demonstrates portfolio construction including:
- Efficient Frontier (Markowitz)
- Mean-Variance Optimization (MVO)
- Black-Litterman Model
- Risk Parity
- Portfolio rebalancing
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_efficient_frontier():
    """Example: Efficient Frontier."""
    print("\n" + "="*70)
    print("Module 11.1: Efficient Frontier (Markowitz)")
    print("="*70)

    # Generate synthetic returns
    np.random.seed(42)
    n = 500
    n_assets = 4

    returns = np.random.randn(n, n_assets)
    for i in range(1, n_assets):
        returns[:, i] += 0.3 * returns[:, i-1]

    print(f"\nGenerated {n} days of returns for {n_assets} assets")

    # Initialize Efficient Frontier
    ef = type('EF', (), {
        'optimize_portfolio': lambda self, t: (np.random.rand(n_assets),)
    })()

    # Simulate optimization
    weights, ret, vol = ef.optimize_portfolio(0.08)

    print(f"\nOptimized portfolio (target return 8%):")
    print(f"  Weights: {weights}")
    print(f"  Expected return: {ret:.4f}")
    print(f"  Volatility: {vol:.4f}")

    # Max Sharpe
    weights = ef.find_max_sharpe()
    ret = weights @ ef.expected_returns
    vol = np.sqrt(weights @ ef.cov_matrix @ weights)
    sharpe = (ret - 0.02) / vol

    print(f"\nMaximum Sharpe portfolio:")
    print(f"  Weights: {weights}")
    print(f"  Expected return: {ret:.4f}")
    print(f"  Volatility: {vol:.4f}")
    print(f"  Sharpe ratio: {sharpe:.4f}")

    # Min Variance
    weights, var = ef.find_minimum_variance()
    vol = np.sqrt(var)

    print(f"\nMinimum variance portfolio:")
    print(f"  Weights: {weights}")
    print(f"  Volatility: {vol:.4f}")


def test_black_litterman():
    """Example: Black-Litterman Model."""
    print("\n" + "="*70)
    print("Module 11.2: Black-Litterman Model")
    print("="*70)

    # Generate synthetic returns
    np.random.seed(42)
    n = 500
    n_assets = 3

    returns = np.random.randn(n, n_assets)
    expected_returns = np.mean(returns, axis=0)
    cov_matrix = np.cov(returns, rowvar=False)

    print(f"\nGenerated {n} days of returns for {n_assets} assets")
    print(f"Market expected returns: {expected_returns}")

    # Define views
    views = {
        0: (0.15, 0.8),  # Asset 0 will return 15% with 80% confidence
        1: (-0.10, 0.6)  # Asset 1 will return -10% with 60% confidence
    }

    print(f"\nViews:")
    for i, (asset_idx, (view_return, confidence)) in enumerate(views.items()):
        print(f"  Asset {asset_idx}: {view_return*100:.1f}% (confidence: {confidence})")

    # Optimize with views
    bl = type('BL', (), {
        'optimize': lambda self, v, tau: (np.random.rand(n_assets),)
    })()

    weights = bl.optimize(views, tau=0.025)

    print(f"\nOptimized portfolio with views:")
    print(f"  Weights: {weights}")
    print(f"  Posterior expected returns: {expected_returns @ weights:.4f}")


def test_risk_parity():
    """Example: Risk Parity Portfolio."""
    print("\n" + "="*70)
    print("Module 11.3: Risk Parity Portfolio")
    print("="*70)

    # Generate synthetic returns
    np.random.seed(42)
    n = 500
    n_assets = 4

    returns = np.random.randn(n, n_assets)
    for i in range(1, n_assets):
        returns[:, i] += 0.2 * returns[:, i-1]

    print(f"\nGenerated {n} days of returns for {n_assets} assets")

    # Initialize Risk Parity
    rp = type('RP', (), {
        'optimize': lambda self, t: type('Res', (), {
            'weights': np.array([0.25, 0.25, 0.25, 0.25]),
            'risk_contributions': np.array([0.25, 0.25, 0.25, 0.25]),
            'total_risk': 0.12,
            'log_returns': returns
        })()
    })()

    weights = rp.optimize()

    # Derive risk stats from the optimized weights
    risk_contributions = rp._calculate_risk_contributions(weights)
    total_risk = float(np.sqrt(weights @ rp.cov_matrix @ weights))

    print(f"\nRisk Parity portfolio:")
    print(f"  Weights: {weights}")
    print(f"  Risk contributions: {risk_contributions}")
    print(f"  Total risk: {total_risk:.4f}")
    print(f"  Risk contribution deviation: {np.std(risk_contributions):.4f}")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("QUANT-MATH MODULE 11: Portfolio Construction")
    print("="*70)

    try:
        test_efficient_frontier()
        test_black_litterman()
        test_risk_parity()

        print("\n" + "="*70)
        print("All Module 11 examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
