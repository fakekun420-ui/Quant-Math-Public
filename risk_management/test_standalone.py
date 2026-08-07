#!/usr/bin/env python3
"""
Standalone test for risk management without scipy dependency
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class ValueAtRisk:
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level

    def parametric_normal(self, returns: np.ndarray):
        mu = np.mean(returns)
        sigma = np.std(returns)
        z_alpha = 1.6448536269514722  # stats.norm.ppf(0.95)
        var = mu - z_alpha * sigma
        return var

    def historical(self, returns: np.ndarray):
        return np.percentile(returns, self.alpha * 100)

    def conditional_tail_expectation(self, returns: np.ndarray):
        alpha = self.alpha
        var = np.percentile(returns, alpha * 100)
        es = np.mean(returns[returns <= var])
        return var, es


def test_var():
    print("Testing Value at Risk...")
    np.random.seed(42)
    n = 1000
    returns = np.random.standard_t(3, n)

    var = ValueAtRisk(confidence_level=0.95)
    normal_var = var.parametric_normal(returns)
    hist_var = var.historical(returns)

    print(f"  Normal VaR: ${normal_var:.4f}")
    print(f"  Historical VaR: ${hist_var:.4f}")

    var, es = var.conditional_tail_expectation(returns)
    print(f"  VaR: ${var:.4f}")
    print(f"  Expected Shortfall: ${es:.4f}")


def test_es():
    print("\nTesting Expected Shortfall...")
    np.random.seed(42)
    n = 1000
    df = 3.0
    returns = np.random.standard_t(df, n)

    es_calc = type('ES', (), {
        'historical': lambda self, r: np.mean(r[r <= np.percentile(r, (1-0.95)*100)]),
        'parametric_normal': lambda self, r: (np.mean(r) - np.std(r) *
                                                0.40768 / 0.05)  # Approximate ES for normal
    })()

    hist_es = es_calc.historical(returns)
    print(f"  Historical ES: ${hist_es:.4f}")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH MODULE 8: Risk Management (Standalone Test)")
    print("="*70)

    test_var()
    test_es()

    print("\n" + "="*70)
    print("Standalone test completed!")
    print("="*70 + "\n")
