"""
Portfolio Construction Module

This module provides portfolio construction and optimization tools including:
- Efficient Frontier (Markowitz)
- Mean-Variance Optimization (MVO)
- Black-Litterman Model
- Risk Parity
- Portfolio rebalancing
- Factor investing implementation
- Multi-objective optimization
"""

import numpy as np
from typing import Tuple, Dict, List, Any, Optional
from scipy import optimize
from dataclasses import dataclass
import warnings


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""
    weights: np.ndarray
    expected_return: float
    volatility: float
    sharpe_ratio: float
    efficient_frontier: Optional[np.ndarray] = None


@dataclass
class RiskParityResult:
    """Result of risk parity optimization."""
    weights: np.ndarray
    risk_contributions: np.ndarray
    total_risk: float
    log_returns: np.ndarray


class EfficientFrontier:
    """
    Efficient Frontier (Markowitz)

    Computes the efficient frontier of risky assets.
    """

    def __init__(self, returns: np.ndarray, risk_free_rate: float = 0.02):
        """
        Initialize efficient frontier calculator.

        Parameters
        ----------
        returns : np.ndarray
            Asset returns (n_observations x n_assets)
        risk_free_rate : float
            Risk-free rate
        """
        self.returns = returns
        self.risk_free_rate = risk_free_rate

        # Compute statistics
        self.expected_returns = np.mean(returns, axis=0)
        self.cov_matrix = np.cov(returns, rowvar=False)

    def optimize_portfolio(self, target_return: float) -> np.ndarray:
        """
        Optimize portfolio for a target return.

        Parameters
        ----------
        target_return : float
            Target portfolio expected return

        Returns
        -------
        weights : np.ndarray
            Optimal portfolio weights
        """
        n_assets = len(self.expected_returns)

        # Negative Sharpe ratio for minimization
        def negative_sharpe(w):
            portfolio_return = w @ self.expected_returns
            portfolio_vol = np.sqrt(w @ self.cov_matrix @ w.T)
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else -np.inf
            return -sharpe

        # Constraints
        bounds = tuple((0, 1) for _ in range(n_assets))
        constraints = [
            {'type': 'eq', 'fun': lambda w: w @ self.expected_returns - target_return},
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        ]

        # Initial guess: equal weights
        w0 = np.ones(n_assets) / n_assets

        # Optimize
        result = optimize.minimize(
            negative_sharpe,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        return result.x

    def compute_efficient_frontier(self, n_points: int = 50) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute the entire efficient frontier.

        Parameters
        ----------
        n_points : int
            Number of points to compute

        Returns
        -------
        returns : np.ndarray
            Portfolio expected returns
        volatilities : np.ndarray
            Portfolio volatilities
        weights : np.ndarray
            Portfolio weights at each point
        """
        min_return = np.min(self.expected_returns)
        max_return = np.max(self.expected_returns)

        returns = np.linspace(min_return, max_return, n_points)
        volatilities = []
        weights_list = []

        for target_return in returns:
            weights = self.optimize_portfolio(target_return)
            portfolio_return = weights @ self.expected_returns
            portfolio_vol = np.sqrt(weights @ self.cov_matrix @ weights)

            volatilities.append(portfolio_vol)
            weights_list.append(weights)

        return returns, np.array(volatilities), np.array(weights_list)

    def find_max_sharpe(self) -> Tuple[np.ndarray, float, float]:
        """
        Find portfolio with maximum Sharpe ratio.

        Returns
        -------
        weights : np.ndarray
            Optimal weights
        return : float
            Expected return
        vol : float
            Volatility
        """
        def negative_sharpe(w):
            portfolio_return = w @ self.expected_returns
            portfolio_vol = np.sqrt(w @ self.cov_matrix @ w.T)
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else -np.inf
            return -sharpe

        n_assets = len(self.expected_returns)
        bounds = tuple((0, 1) for _ in range(n_assets))
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

        w0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            negative_sharpe,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        weights = result.x
        return_val = weights @ self.expected_returns
        vol_val = np.sqrt(weights @ self.cov_matrix @ weights)

        return weights, return_val, vol_val

    def find_minimum_variance(self) -> Tuple[np.ndarray, float]:
        """
        Find portfolio with minimum variance.

        Returns
        -------
        weights : np.ndarray
            Minimum variance weights
        var : float
            Minimum variance
        """
        def portfolio_variance(w):
            return w @ self.cov_matrix @ w

        n_assets = len(self.expected_returns)
        bounds = tuple((0, 1) for _ in range(n_assets))
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

        w0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            portfolio_variance,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        weights = result.x
        var = weights @ self.cov_matrix @ weights

        return weights, var


class BlackLitterman:
    """
    Black-Litterman Portfolio Optimization

    Combines market equilibrium with investor views.
    """

    def __init__(self, expected_returns: np.ndarray, cov_matrix: np.ndarray):
        """
        Initialize Black-Litterman model.

        Parameters
        ----------
        expected_returns : np.ndarray
            Market expected returns
        cov_matrix : np.ndarray
            Covariance matrix
        """
        self.expected_returns = expected_returns
        self.cov_matrix = cov_matrix

    def optimize(self, views: Dict[int, Tuple[float, float]],
                 tau: float = 0.025) -> np.ndarray:
        """
        Optimize portfolio with views.

        Parameters
        ----------
        views : dict
            Views as {asset_index: (expected_return, confidence)}
        tau : float
            Uncertainty parameter

        Returns
        -------
        weights : np.ndarray
            Optimized portfolio weights
        """
        n_assets = len(self.expected_returns)

        # Build view vector and uncertainty matrix
        P = np.zeros((len(views), n_assets))
        Q = np.zeros(len(views))

        for i, (asset_idx, (view_return, confidence)) in enumerate(views.items()):
            P[i, asset_idx] = confidence
            Q[i] = view_return

        # Omega matrix
        Omega = np.diag(np.diag(tau * cov_matrix))

        # Posterior expected returns
        mean = np.linalg.inv(np.linalg.inv(tau * cov_matrix) + P.T @ np.linalg.inv(Omega) @ P) @ (
            np.linalg.inv(tau * cov_matrix) @ self.expected_returns +
            P.T @ np.linalg.inv(Omega) @ Q
        )

        # Posterior covariance
        cov = np.linalg.inv(np.linalg.inv(tau * cov_matrix) + P.T @ np.linalg.inv(Omega) @ P)

        # Optimize
        def negative_sharpe(w):
            return_val = w @ mean
            vol_val = np.sqrt(w @ cov @ w)
            sharpe = (return_val - 0.02) / vol_val if vol_val > 0 else -np.inf
            return -sharpe

        bounds = tuple((0, 1) for _ in range(n_assets))
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

        w0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            negative_sharpe,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        return result.x


class RiskParity:
    """
    Risk Parity Portfolio

    Equalizes risk contributions across assets.
    """

    def __init__(self, returns: np.ndarray, method: str = 'equal'):
        """
        Initialize risk parity optimizer.

        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        method : str
            Risk parity method ('equal', 'lp', 'squared')
        """
        self.returns = returns
        self.method = method
        self.cov_matrix = np.cov(returns, rowvar=False)
        self.n_assets = returns.shape[1]

    def optimize(self, target_risk: float = None) -> RiskParityResult:
        """
        Optimize risk parity portfolio.

        Parameters
        ----------
        target_risk : float, optional
            Target portfolio volatility

        Returns
        -------
        result : RiskParityResult
            Optimization result
        """
        if self.method == 'equal':
            # Equal risk contribution
            weights = self._equal_risk_contribution()
        else:
            # Optimized risk parity
            weights = self._optimized_risk_parity()

        # Calculate risk contributions
        risk_contributions = self._calculate_risk_contributions(weights)

        # Total risk
        total_risk = np.sqrt(weights @ self.cov_matrix @ weights)

        # Calculate log returns
        log_returns = np.log(1 + self.returns)

        return RiskParityResult(
            weights=weights,
            risk_contributions=risk_contributions,
            total_risk=total_risk,
            log_returns=log_returns
        )

    def _equal_risk_contribution(self) -> np.ndarray:
        """Equal risk contribution portfolio."""
        # Start with equal weights
        weights = np.ones(self.n_assets) / self.n_assets

        # Iterate to equalize risk contributions
        for _ in range(100):
            risk_contributions = self._calculate_risk_contributions(weights)
            ratio = risk_contributions / risk_contributions.sum()

            # Update weights
            weights = weights * ratio / weights.sum()

            # Convergence check
            if np.max(np.abs(ratio - weights)) < 1e-6:
                break

        return weights

    def _optimized_risk_parity(self) -> np.ndarray:
        """Optimized risk parity using optimization."""
        def risk_contribution_deviation(w):
            risk_contributions = self._calculate_risk_contributions(w)
            avg_risk = risk_contributions.mean()
            return np.sum((risk_contributions - avg_risk) ** 2)

        bounds = tuple((0, 1) for _ in range(self.n_assets))
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

        w0 = np.ones(self.n_assets) / self.n_assets

        result = optimize.minimize(
            risk_contribution_deviation,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        return result.x

    def _calculate_risk_contributions(self, weights: np.ndarray) -> np.ndarray:
        """Calculate risk contributions for each asset."""
        cov_matrix = self.cov_matrix
        total_vol = np.sqrt(weights @ cov_matrix @ weights)

        marginal_risk = cov_matrix @ weights
        risk_contributions = weights * marginal_risk / total_vol

        return risk_contributions
