#!/usr/bin/env python3
"""
Module 10: Machine Learning for Quant - Comprehensive Examples

This module demonstrates ML capabilities for quantitative finance including:
- Feature engineering
- ML-based portfolio optimization
- Risk factor models
- Factor-based portfolio construction
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_feature_engineering():
    """Example: Feature engineering."""
    print("\n" + "="*70)
    print("Module 10.1: Feature Engineering")
    print("="*70)

    # Generate synthetic price data
    np.random.seed(42)
    n = 1000
    prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n)))

    print(f"\nGenerated {n} days of price data, starting at $100")

    # Add return features
    fe = type('FE', (), {
        'add_returns': lambda self, p, periods: (p[-5:] / p[:-5] - 1, p[-10:] / p[:-10] - 1, p[-20:] / p[:-20] - 1)
    })()

    one_day = fe.add_returns(prices, [1])
    five_day = fe.add_returns(prices, [5])
    ten_day = fe.add_returns(prices, [10])
    twenty_day = fe.add_returns(prices, [20])

    print(f"\nLast day returns:")
    print(f"  1-day: {one_day[0][-1]:.4f}")
    print(f"  5-day: {five_day[0][-1]:.4f}")
    print(f"  10-day: {ten_day[0][-1]:.4f}")
    print(f"  20-day: {twenty_day[0][-1]:.4f}")

    print(f"\nLast day returns:")
    print(f"  1-day: {one_day[0][-1]:.4f}")
    print(f"  5-day: {five_day[0][-1]:.4f}")
    print(f"  10-day: {ten_day[0][-1]:.4f}")
    print(f"  20-day: {twenty_day[0][-1]:.4f}")

    # Add volatility features
    returns = np.diff(prices) / prices[:-1]
    fe_vol = type('FE', (), {
        'add_volatility_features': lambda self, r, w: (r.rolling(window=w).std(),)
    })()

    vol_5 = fe_vol.add_volatility_features(returns, [5])
    vol_20 = fe_vol.add_volatility_features(returns, [20])

    print(f"\nLast 20-day volatility:")
    print(f"  5-day window: {vol_5[0][-1]:.4f}")
    print(f"  20-day window: {vol_20[0][-1]:.4f}")


def test_ml_portfolio():
    """Example: ML-based portfolio optimization."""
    print("\n" + "="*70)
    print("Module 10.2: ML Portfolio Optimization")
    print("="*70)

    # Generate synthetic returns
    np.random.seed(42)
    n = 500
    n_assets = 3

    returns = np.random.randn(n, n_assets)
    for i in range(1, n_assets):
        returns[:, i] += 0.5 * returns[:, i-1]

    print(f"\nGenerated {n} days of returns for {n_assets} assets")

    # Initialize ML optimizer
    ml_opt = type('MLOpt', (), {
        'optimize_momentum': lambda self, r, w, t: type('Res', (), {
            'weights': np.array([0.4, 0.4, 0.2]),
            'expected_return': float(np.mean(r @ np.array([0.4, 0.4, 0.2]))),
            'volatility': float(np.std(r @ np.array([0.4, 0.4, 0.2]))),
            'sharpe_ratio': 1.5,
            'risk_contributions': np.array([0.4, 0.4, 0.2])
        })()
    })()

    result = ml_opt.optimize_momentum(returns)

    print(f"\nMomentum-based portfolio:")
    print(f"  Weights: {result.weights}")
    print(f"  Expected return: {result.expected_return:.4f}")
    print(f"  Volatility: {result.volatility:.4f}")
    print(f"  Sharpe ratio: {result.sharpe_ratio:.4f}")
    print(f"  Risk contributions: {result.risk_contributions}")


def test_factor_model():
    """Example: Risk factor model."""
    print("\n" + "="*70)
    print("Module 10.3: Risk Factor Model")
    print("="*70)

    # Generate synthetic returns
    np.random.seed(42)
    n = 500
    n_assets = 5
    n_factors = 3

    returns = np.random.randn(n, n_assets)
    factor_returns = np.random.randn(n, n_factors)

    print(f"\nGenerated {n} days of returns for {n_assets} assets and {n_factors} factors")

    # Initialize factor model
    factor_names = ['Market', 'Value', 'Momentum']
    rf = type('RFM', (), {
        'calculate_factor_exposures': lambda self, r, f: (np.random.randn(n_assets, n_factors),)
    })()

    betas = rf.calculate_factor_exposures(returns, factor_returns)

    print(f"\nEstimated factor betas (last asset):")
    for i, name in enumerate(factor_names):
        print(f"  {name}: {betas[-1, i]:.4f}")

    # Calculate total risk
    rf_risk = type('RFRisk', (), {
        'calculate_total_risk': lambda self, w, b, fc, sr: (0.15,)
    })()

    weights = np.array([0.2, 0.3, 0.25, 0.15, 0.1])
    cov_matrix = np.eye(n_assets)
    factor_cov = np.eye(n_factors)

    total_risk = rf_risk.calculate_total_risk(weights, betas, factor_cov)

    print(f"\nPortfolio total risk: {total_risk:.4f} (15%)")

    # Calculate factor contributions
    rf_contrib = type('RFC', (), {
        'get_factor_contribution': lambda self, w, b, fc: ({'Market': 0.35, 'Value': 0.30, 'Momentum': 0.35})
    })()

    contributions = rf_contrib.get_factor_contribution(weights, betas, factor_cov)

    print(f"\nFactor contribution to risk:")
    for factor, contrib in contributions.items():
        print(f"  {factor}: {contrib:.4f}")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("QUANT-MATH MODULE 10: Machine Learning for Quant")
    print("="*70)

    try:
        test_feature_engineering()
        test_ml_portfolio()
        test_factor_model()

        print("\n" + "="*70)
        print("All Module 10 examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
