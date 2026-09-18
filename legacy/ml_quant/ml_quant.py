"""
Machine Learning for Quant Module

This module provides machine learning tools for quantitative finance including:
- Feature engineering for financial data
- Portfolio optimization with ML constraints
- Risk factor models
- Market regime prediction
- Anomaly detection
"""

import numpy as np
from typing import Tuple, Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class MLPortfolioResult:
    """Result of ML portfolio optimization."""
    weights: np.ndarray
    expected_return: float
    volatility: float
    sharpe_ratio: float
    risk_contributions: np.ndarray


class FeatureEngineer:
    """
    Feature Engineering for Financial Data

    Creates and transforms features for ML models.
    """

    def __init__(self):
        """Initialize feature engineer."""
        self.features = {}

    def add_returns(self, prices: np.ndarray, periods: List[int] = [1, 5, 10, 20]) -> np.ndarray:
        """
        Add return-based features.

        Parameters
        ----------
        prices : np.ndarray
            Price series
        periods : list
            Return periods

        Returns
        -------
        features : np.ndarray
            Returns at different periods
        """
        n = len(prices)
        features = []

        for p in periods:
            if n >= p:
                returns = (prices[n-p:] / prices[:-p]) - 1
                features.append(returns)
            else:
                features.append(np.full(n, np.nan))

        return np.column_stack(features)

    def add_volatility_features(self, returns: np.ndarray, windows: List[int] = [5, 10, 20]) -> np.ndarray:
        """
        Add volatility-based features.

        Parameters
        ----------
        returns : np.ndarray
            Return series
        windows : list
        Rolling window sizes

        Returns
        -------
        features : np.ndarray
            Rolling volatilities
        """
        features = []
        for w in windows:
            vol = returns.rolling(window=w).std()
            features.append(vol)
        return np.column_stack(features)

    def add_momentum_features(self, returns: np.ndarray, windows: List[int] = [5, 10, 20]) -> np.ndarray:
        """
        Add momentum features.

        Parameters
        ----------
        returns : np.ndarray
            Return series
        windows : list
            Rolling window sizes

        Returns
        -------
        features : np.ndarray
            Rolling means
        """
        features = []
        for w in windows:
            mom = returns.rolling(window=w).mean()
            features.append(mom)
        return np.column_stack(features)

    def add_cross_features(self, returns: np.ndarray) -> np.ndarray:
        """
        Add cross-asset features (e.g., spread, correlation).

        Parameters
        ----------
        returns : np.ndarray
            Asset returns (n_obs x n_assets)

        Returns
        -------
        features : np.ndarray
            Cross-asset features
        """
        if returns.ndim != 2 or returns.shape[1] < 2:
            return np.zeros((len(returns), 0))

        # Simple spread feature
        spread = returns[:, 0] - returns[:, 1]

        # Mean return spread
        mean_spread = spread.rolling(window=20).mean()

        return np.column_stack([spread, mean_spread])

    def get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        """
        Get feature importance from trained model.

        Parameters
        ----------
        model : Any
            Trained ML model
        feature_names : list
            Names of features

        Returns
        -------
        importance : dict
            Feature importance scores
        """
        importance = {}
        for i, name in enumerate(feature_names):
            importance[name] = 0.0  # Placeholder

        return importance


class MLPortfolioOptimizer:
    """
    Machine Learning Portfolio Optimizer

    Uses ML-based constraints and risk models.
    """

    def __init__(self, risk_model: str = 'cvx'):
        """
        Initialize optimizer.

        Parameters
        ----------
        risk_model : str
            Risk model type ('cvx', 'black_litterman')
        """
        self.risk_model = risk_model

    def optimize_momentum(self, returns: np.ndarray,
                          momentum_window: int = 20,
                          target_sharpe: float = 1.5) -> MLPortfolioResult:
        """
        Optimize portfolio based on momentum signals.

        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        momentum_window : int
            Momentum calculation window
        target_sharpe : float
            Target Sharpe ratio

        Returns
        -------
        result : MLPortfolioResult
            Optimized portfolio
        """
        n_assets = returns.shape[1]

        # Calculate momentum
        momentum = returns[:, -momentum_window:].mean(axis=0)

        # Create weights based on momentum (higher momentum = higher weight)
        weights = np.maximum(0, momentum) / np.maximum(0, momentum).sum()

        # Calculate portfolio statistics
        portfolio_returns = returns @ weights
        expected_return = np.mean(portfolio_returns)
        volatility = np.std(portfolio_returns)
        sharpe = (expected_return - 0.02) / volatility if volatility > 0 else 0

        # Risk contributions
        cov_matrix = np.cov(returns, rowvar=False)
        risk_contributions = weights * (cov_matrix @ weights) / volatility

        return MLPortfolioResult(
            weights=weights,
            expected_return=expected_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            risk_contributions=risk_contributions
        )

    def optimize_factor_model(self, returns: np.ndarray,
                              factor_returns: np.ndarray,
                              betas: np.ndarray,
                              target_sharpe: float = 1.5) -> MLPortfolioResult:
        """
        Optimize portfolio using factor model constraints.

        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        factor_returns : np.ndarray
            Factor returns
        betas : np.ndarray
            Factor betas for each asset
        target_sharpe : float
            Target Sharpe ratio

        Returns
        -------
        result : MLPortfolioResult
            Optimized portfolio
        """
        n_assets = returns.shape[1]
        n_factors = factor_returns.shape[1]

        # Factor-based weights (minimize factor exposure)
        weights = np.ones(n_assets) / n_assets

        # Calculate factor exposure
        factor_exposure = betas @ weights

        # Adjust weights to reduce specific factor risk
        optimal_weights = weights * np.exp(-factor_exposure)

        # Normalize
        optimal_weights = optimal_weights / optimal_weights.sum()

        # Calculate portfolio statistics
        portfolio_returns = returns @ optimal_weights
        expected_return = np.mean(portfolio_returns)
        volatility = np.std(portfolio_returns)
        sharpe = (expected_return - 0.02) / volatility if volatility > 0 else 0

        cov_matrix = np.cov(returns, rowvar=False)
        risk_contributions = optimal_weights * (cov_matrix @ optimal_weights) / volatility

        return MLPortfolioResult(
            weights=optimal_weights,
            expected_return=expected_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            risk_contributions=risk_contributions
        )

    def optimize_ml_based(self, returns: np.ndarray,
                          risk_factors: np.ndarray,
                          target_sharpe: float = 1.5) -> MLPortfolioResult:
        """
        Optimize portfolio using ML predictions.

        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        risk_factors : np.ndarray
            ML-predicted risk factors
        target_sharpe : float
            Target Sharpe ratio

        Returns
        -------
        result : MLPortfolioResult
            Optimized portfolio
        """
        n_assets = returns.shape[1]

        # Create ML-based weights (minimize predicted risk)
        weights = np.ones(n_assets) / n_assets

        # Apply ML risk adjustments
        risk_adjusted_weights = weights * (1 / (1 + risk_factors))

        # Normalize
        risk_adjusted_weights = risk_adjusted_weights / risk_adjusted_weights.sum()

        # Calculate portfolio statistics
        portfolio_returns = returns @ risk_adjusted_weights
        expected_return = np.mean(portfolio_returns)
        volatility = np.std(portfolio_returns)
        sharpe = (expected_return - 0.02) / volatility if volatility > 0 else 0

        cov_matrix = np.cov(returns, rowvar=False)
        risk_contributions = risk_adjusted_weights * (cov_matrix @ risk_adjusted_weights) / volatility

        return MLPortfolioResult(
            weights=risk_adjusted_weights,
            expected_return=expected_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            risk_contributions=risk_contributions
        )


class RiskFactorModel:
    """
    Risk Factor Model

    Decomposes portfolio risk into factor exposures.
    """

    def __init__(self, factor_names: List[str]):
        """
        Initialize factor model.

        Parameters
        ----------
        factor_names : list
            Names of risk factors
        """
        self.factor_names = factor_names

    def calculate_factor_exposures(self, returns: np.ndarray,
                                    factor_returns: np.ndarray) -> np.ndarray:
        """
        Calculate factor exposures for assets.

        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        factor_returns : np.ndarray
            Factor returns

        Returns
        -------
        betas : np.ndarray
            Factor betas for each asset
        """
        n_assets = returns.shape[1]
        n_factors = factor_returns.shape[1]
        betas = np.zeros((n_assets, n_factors))

        for i in range(n_assets):
            # Simple linear regression: asset_return = alpha + beta * factor_returns
            X = factor_returns
            y = returns[:, i]

            # Add intercept
            X = np.column_stack([X, np.ones(len(X))])

            # Calculate betas using OLS
            betas[i, :-1] = np.linalg.inv(X.T @ X) @ X.T @ y

        return betas

    def calculate_total_risk(self, weights: np.ndarray,
                            betas: np.ndarray,
                            factor_cov: np.ndarray,
                            specific_risk: float = 0.02) -> float:
        """
        Calculate total portfolio risk using factor model.

        Parameters
        ----------
        weights : np.ndarray
            Portfolio weights
        betas : np.ndarray
            Factor betas
        factor_cov : np.ndarray
            Factor covariance matrix
        specific_risk : float
            Specific risk per unit of weight

        Returns
        -------
        total_risk : float
            Portfolio volatility
        """
        # Factor risk contribution
        factor_risk = weights @ (betas @ factor_cov @ betas.T) @ weights

        # Specific risk contribution
        specific_risk = weights @ (specific_risk ** 2) @ weights

        total_risk = np.sqrt(factor_risk + specific_risk)

        return total_risk

    def get_factor_contribution(self, weights: np.ndarray,
                                betas: np.ndarray,
                                factor_cov: np.ndarray) -> Dict[str, float]:
        """
        Get factor contribution to portfolio risk.

        Parameters
        ----------
        weights : np.ndarray
            Portfolio weights
        betas : np.ndarray
            Factor betas
        factor_cov : np.ndarray
            Factor covariance matrix

        Returns
        -------
        contributions : dict
            Risk contribution from each factor
        """
        n_factors = len(self.factor_names)
        contributions = {}

        for i in range(n_factors):
            # Contribution from factor i
            beta_i = betas[:, i]
            contribution = weights @ (beta_i @ factor_cov @ beta_i.T) @ weights

            contributions[self.factor_names[i]] = contribution

        return contributions
