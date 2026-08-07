#!/usr/bin/env python3
"""
Module 9: Regime Detection - Comprehensive Examples

This module demonstrates all regime detection capabilities including:
- Hidden Markov Models (HMM) for regime classification
- Regime switching models
- Regime stability analysis
- Regime transition matrices
- Regime clustering (k-means, hierarchical)
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def example_hmm():
    """Example: Hidden Markov Model regime detection."""
    print("\n" + "="*70)
    print("Module 9.1: Hidden Markov Model (HMM) Regime Detection")
    print("="*70)

    # Generate synthetic returns with regime switching
    np.random.seed(42)
    n_obs = 1000
    n_assets = 3

    # Generate two regimes
    regime_1_returns = np.random.normal(0.01, 0.02, 500)  # Bull market
    regime_2_returns = np.random.normal(-0.01, 0.03, 500)  # Bear market

    combined_returns = np.vstack([regime_1_returns, regime_2_returns])

    print(f"\nGenerated {n_obs} returns with 2 regimes:")
    print(f"  Regime 1 (Bull): mean={np.mean(regime_1_returns):.4f}, std={np.std(regime_1_returns):.4f}")
    print(f"  Regime 2 (Bear): mean={np.mean(regime_2_returns):.4f}, std={np.std(regime_2_returns):.4f}")

    # Fit HMM
    from regime_detection import RegimeDetector

    detector = RegimeDetector(n_regimes=2)
    detector.fit(combined_returns)

    # Predict regimes
    predicted_regimes = detector.predict(combined_returns)

    print(f"\nPredicted regimes (first 20 observations):")
    for i in range(min(20, len(predicted_regimes))):
        regime_type = "Bull" if predicted_regimes[i] == 0 else "Bear"
        print(f"  Day {i}: {regime_type} (Regime {predicted_regimes[i]})")

    # Analyze regimes
    result = detector.analyze(combined_returns)

    print(f"\n--- Regime Analysis ---")
    print(f"Current regime: {result.current_regime}")
    print(f"Regime probabilities:")
    for i, prob in enumerate(result.regime_probabilities):
        regime_type = "Bull" if i == 0 else "Bear"
        print(f"  Regime {i} ({regime_type}): {prob:.2%}")

    print(f"\n--- Regime Sharpe Ratios ---")
    for i, sharpe in enumerate(result.regime_sharpe_ratios):
        regime_type = "Bull" if i == 0 else "Bear"
        print(f"  Regime {i} ({regime_type}): {sharpe:.4f}")

    print(f"\n--- Transition Matrix ---")
    for i in range(2):
        print(f"  From Regime {i}:")
        for j in range(2):
            print(f"    To Regime {j}: {result.transition_matrix[i, j]:.3f}")

    # Get regime statistics
    print(f"\n--- Regime Statistics ---")
    for regime in result.regimes:
        print(f"  Regime {regime.regime_id}:")
        print(f"    Mean return: {regime.mean:.4f}")
        print(f"    Volatility: {regime.volatility:.4f}")
        print(f"    Sharpe ratio: {regime.sharpe_ratio:.4f}")
        print(f"    Occurrences: {regime.occurrences}")


def example_clustering():
    """Example: Regime clustering."""
    print("\n" + "="*70)
    print("Module 9.2: Regime Clustering")
    print("="*70)

    # Generate returns
    np.random.seed(42)
    n_obs = 500
    n_assets = 3

    # Two clusters (regimes)
    cluster_1 = np.random.normal(0.01, 0.02, 250, n_assets)
    cluster_2 = np.random.normal(-0.01, 0.03, 250, n_assets)

    returns = np.vstack([cluster_1, cluster_2])

    print(f"\nGenerated {n_obs} returns with 2 clusters:")
    print(f"  Cluster 1 (Bull): mean={np.mean(cluster_1):.4f}, std={np.std(cluster_1):.4f}")
    print(f"  Cluster 2 (Bear): mean={np.mean(cluster_2):.4f}, std={np.std(cluster_2):.4f}")

    # K-means clustering
    from regime_detection import RegimeClusterer

    clusterer = RegimeClusterer(method='kmeans')
    labels = clusterer.fit(returns, n_clusters=2)

    print(f"\n--- K-Means Clustering Results ---")
    unique_labels = np.unique(labels)
    for label in unique_labels:
        cluster_returns = returns[labels == label]
        mean = np.mean(cluster_returns)
        std = np.std(cluster_returns)
        sharpe = (mean - 0.02) / std if std > 0 else 0

        print(f"  Cluster {label}:")
        print(f"    Mean: {mean:.4f}")
        print(f"    Std: {std:.4f}")
        print(f"    Sharpe: {sharpe:.4f}")
        print(f"    Size: {len(cluster_returns)}")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("QUANT-MATH MODULE 9: Regime Detection")
    print("="*70)

    try:
        example_hmm()
        example_clustering()

        print("\n" + "="*70)
        print("All Module 9 examples completed successfully!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
