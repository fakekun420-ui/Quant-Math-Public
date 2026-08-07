"""
Risk Management Module

This module provides comprehensive risk measurement and management tools including:
- Value at Risk (VaR) calculations (parametric, historical, Monte Carlo)
- Expected Shortfall (ES) calculations
- Portfolio risk metrics (diversification, concentration)
- Risk budgeting and allocation
- Stress testing
- Tail risk measures
"""

import numpy as np
from typing import Tuple, Dict, Any, Optional, List
from scipy import stats, optimize
from dataclasses import dataclass


@dataclass
class VaRResult:
    """Result of VaR calculation."""
    value_at_risk: float
    confidence_level: float
    method: str
    tail_loss: float  # Expected Shortfall if available
    distribution: Optional[str] = None


@dataclass
class PortfolioRiskResult:
    """Result of portfolio risk analysis."""
    total_var: float
    total_expected_shortfall: float
    component_var: Dict[str, float]
    component_es: Dict[str, float]
    diversification_benefit: float
    concentration_risk: float
    correlations: Dict[str, float]


class ValueAtRisk:
    """
    Value at Risk (VaR) Calculator

    Computes VaR at various confidence levels using different methods.
    """
    
    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize VaR calculator.
        
        Parameters
        ----------
        confidence_level : float
            Confidence level for VaR (0-1)
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
    
    def parametric_normal(self, returns: np.ndarray) -> VaRResult:
        """
        Parametric VaR (assuming normal distribution).
        
        Formula: VaR = mu - z_alpha * sigma
        where z_alpha = inv_norm(1 - alpha)
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        
        Returns
        -------
        result : VaRResult
            VaR calculation result
        """
        mu = np.mean(returns)
        sigma = np.std(returns)
        z_alpha = stats.norm.ppf(1 - self.alpha)
        
        var = mu - z_alpha * sigma
        
        return VaRResult(
            value_at_risk=var,
            confidence_level=self.confidence_level,
            method="parametric_normal",
            tail_loss=0.0,
            distribution="normal"
        )
    
    def parametric_student_t(self, returns: np.ndarray, df: float = 3.0) -> VaRResult:
        """
        Parametric VaR (assuming Student's t distribution).
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        df : float
            Degrees of freedom
        
        Returns
        -------
        result : VaRResult
            VaR calculation result
        """
        mu = np.mean(returns)
        sigma = np.std(returns)
        z_alpha = stats.t.ppf(1 - self.alpha, df)
        
        var = mu - z_alpha * sigma
        
        return VaRResult(
            value_at_risk=var,
            confidence_level=self.confidence_level,
            method="parametric_student_t",
            tail_loss=0.0,
            distribution="student_t"
        )
    
    def historical(self, returns: np.ndarray) -> VaRResult:
        """
        Historical VaR (empirical method).
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        
        Returns
        -------
        result : VaRResult
            VaR calculation result
        """
        var = np.percentile(returns, self.alpha * 100)
        
        return VaRResult(
            value_at_risk=var,
            confidence_level=self.confidence_level,
            method="historical",
            tail_loss=0.0
        )
    
    def conditional_tail_expectation(self, returns: np.ndarray,
                                       confidence_level: float = 0.95) -> VaRResult:
        """
        Calculate Conditional Tail Expectation (Expected Shortfall).
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        confidence_level : float
            Confidence level for VaR
        
        Returns
        -------
        result : VaRResult
            VaR with ES
        """
        alpha = 1 - confidence_level
        var = np.percentile(returns, alpha * 100)
        
        # ES = E[R | R <= VaR]
        es = np.mean(returns[returns <= var])
        
        return VaRResult(
            value_at_risk=var,
            confidence_level=confidence_level,
            method="conditional_tail_expectation",
            tail_loss=es,
            distribution="empirical"
        )


class ExpectedShortfall:
    """
    Expected Shortfall (ES) Calculator

    Computes Expected Shortfall at various confidence levels.
    """
    
    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize ES calculator.
        
        Parameters
        ----------
        confidence_level : float
            Confidence level (0-1)
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
    
    def historical(self, returns: np.ndarray) -> float:
        """
        Historical ES calculation.
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        
        Returns
        -------
        es : float
            Expected Shortfall
        """
        alpha = self.alpha
        var = np.percentile(returns, alpha * 100)
        es = np.mean(returns[returns <= var])
        
        return es
    
    def parametric_normal(self, returns: np.ndarray) -> float:
        """
        Parametric ES (assuming normal distribution).
        
        Formula: ES = mu - sigma * phi(z_alpha) / alpha
        where phi(z_alpha) is the standard normal PDF at z_alpha
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        
        Returns
        -------
        es : float
            Expected Shortfall
        """
        mu = np.mean(returns)
        sigma = np.std(returns)
        z_alpha = stats.norm.ppf(1 - self.alpha)
        
        phi_z = stats.norm.pdf(z_alpha)
        es = mu - sigma * phi_z / self.alpha
        
        return es
    
    def conditional_tail_expectation(self, returns: np.ndarray) -> float:
        """
        Conditional Tail Expectation (ES) calculation.
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        
        Returns
        -------
        es : float
            Expected Shortfall
        """
        return self.historical(returns)
    
    def calculate_es_var(self, returns: np.ndarray,
                          confidence_level: float = 0.95) -> Tuple[float, float]:
        """
        Calculate both VaR and ES.
        
        Parameters
        ----------
        returns : np.ndarray
            Historical returns
        confidence_level : float
            Confidence level
        
        Returns
        -------
        var : float
            Value at Risk
        es : float
            Expected Shortfall
        """
        alpha = 1 - confidence_level
        var = np.percentile(returns, alpha * 100)
        es = np.mean(returns[returns <= var])
        
        return var, es


class PortfolioRisk:
    """
    Portfolio Risk Analysis

    Analyzes portfolio risk using diversification, concentration, and correlation metrics.
    """
    
    def __init__(self, returns: np.ndarray, weights: np.ndarray):
        """
        Initialize portfolio risk analyzer.
        
        Parameters
        ----------
        returns : np.ndarray
            Asset returns (n_observations x n_assets)
        weights : np.ndarray
            Portfolio weights (n_assets,)
        """
        self.returns = returns
        self.weights = weights
        self.n_assets = len(weights)
        
        # Compute portfolio statistics
        self.portfolio_returns = returns @ weights
        self.portfolio_mean = np.mean(self.portfolio_returns)
        self.portfolio_std = np.std(self.portfolio_returns)
        
        # Compute covariance matrix
        self.cov_matrix = np.cov(returns, rowvar=False)
        
        # Compute correlations
        self.correlations = np.zeros((self.n_assets, self.n_assets))
        for i in range(self.n_assets):
            for j in range(self.n_assets):
                self.correlations[i, j] = self.cov_matrix[i, j] / (
                    np.sqrt(self.cov_matrix[i, i]) * np.sqrt(self.cov_matrix[j, j])
                )
    
    def calculate_component_var(self, returns: np.ndarray, weights: np.ndarray,
                                 confidence_level: float = 0.95) -> Dict[str, float]:
        """
        Calculate component VaR (marginal VaR).
        
        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        weights : np.ndarray
            Portfolio weights
        confidence_level : float
            Confidence level
        
        Returns
        -------
        var_components : dict
            Component VaR for each asset
        """
        var = ValueAtRisk(confidence_level).parametric_normal(returns @ weights)
        z_alpha = stats.norm.ppf(1 - (1 - confidence_level))
        
        # Component VaR = weight_i * portfolio_variance * z_alpha
        var_components = {}
        for i, w in enumerate(weights):
            var_components[f"asset_{i}"] = w * var
        
        return var_components
    
    def calculate_diversification_benefit(self) -> Dict[str, float]:
        """
        Calculate diversification benefit.
        
        Benefit = (sum of individual VaR) - portfolio VaR
        
        Returns
        -------
        benefit : dict
            Diversification benefit at different confidence levels
        """
        # Individual asset VaR (parametric)
        individual_vars = []
        for i in range(self.n_assets):
            asset_returns = self.returns[:, i]
            asset_var = ValueAtRisk(0.95).parametric_normal(asset_returns)
            individual_vars.append(asset_var)
        
        # Portfolio VaR
        portfolio_var = ValueAtRisk(0.95).parametric_normal(self.portfolio_returns)
        
        # Calculate benefits at different confidence levels
        benefits = {}
        for conf in [0.9, 0.95, 0.99]:
            var = ValueAtRisk(conf).parametric_normal(self.portfolio_returns)
            sum_individual = sum(individual_vars)
            benefit = sum_individual - var
            benefits[conf] = benefit
        
        return benefits
    
    def calculate_concentration_risk(self) -> Dict[str, Any]:
        """
        Calculate concentration risk metrics.
        
        Returns
        -------
        metrics : dict
            Concentration risk measures
        """
        # Herfindahl-Hirschman Index (HHI)
        hhi = np.sum(self.weights ** 2) * 10000
        
        # Top 3 concentration
        top3_weights = np.sort(self.weights)[-3:]
        top3_concentration = np.sum(top3_weights ** 2)
        
        # Number of assets
        n_assets = self.n_assets
        
        return {
            'hhi': hhi,
            'top3_concentration': top3_concentration,
            'n_assets': n_assets,
            'weights': self.weights.tolist()
        }
    
    def calculate_risk_metrics(self, confidence_level: float = 0.95) -> PortfolioRiskResult:
        """
        Calculate comprehensive portfolio risk metrics.
        
        Parameters
        ----------
        confidence_level : float
            Confidence level
        
        Returns
        -------
        result : PortfolioRiskResult
            Portfolio risk analysis
        """
        # VaR calculations
        es = ExpectedShortfall(confidence_level)
        
        var_parametric = ValueAtRisk(confidence_level).parametric_normal(self.portfolio_returns)
        var_historical = ValueAtRisk(confidence_level).historical(self.portfolio_returns)
        var_es = ValueAtRisk(confidence_level).conditional_tail_expectation(self.portfolio_returns)
        
        # Component VaR
        var_components = self.calculate_component_var(self.returns, self.weights, confidence_level)
        
        # Component ES
        es_components = {}
        for i in range(self.n_assets):
            asset_returns = self.returns[:, i]
            es_components[f"asset_{i}"] = es.historical(asset_returns)
        
        # Diversification benefit
        div_benefit = self.calculate_diversification_benefit()
        
        # Concentration risk
        conc_risk = self.calculate_concentration_risk()
        
        # Sharpe ratio
        risk_free_rate = 0.02
        sharpe_ratio = (self.portfolio_mean - risk_free_rate) / self.portfolio_std
        
        return PortfolioRiskResult(
            total_var=var_parametric,
            total_expected_shortfall=es.historical(self.portfolio_returns),
            component_var=var_components,
            component_es=es_components,
            diversification_benefit=div_benefit,
            concentration_risk=conc_risk,
            correlations=self.correlations
        )


class RiskBudget:
    """
    Risk Budgeting and Allocation

    Allocates risk budgets across portfolio assets.
    """
    
    def __init__(self, target_var: float, confidence_level: float = 0.95):
        """
        Initialize risk budget allocator.
        
        Parameters
        ----------
        target_var : float
            Target portfolio VaR
        confidence_level : float
            Confidence level
        """
        self.target_var = target_var
        self.confidence_level = confidence_level
    
    def equal_risk_budget(self, returns: np.ndarray) -> np.ndarray:
        """
        Allocate risk equally across assets.
        
        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        
        Returns
        -------
        weights : np.ndarray
            Equal risk allocation weights
        """
        n_assets = returns.shape[1]
        return np.ones(n_assets) / n_assets
    
    risk_budget = equal_risk_budget
    
    def marginal_contributions(self, returns: np.ndarray, weights: np.ndarray,
                               confidence_level: float = 0.95) -> Dict[str, float]:
        """
        Calculate marginal contributions to VaR.
        
        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        weights : np.ndarray
            Portfolio weights
        confidence_level : float
            Confidence level
        
        Returns
        -------
        mcr : dict
            Marginal contribution to risk for each asset
        """
        var_calculator = ValueAtRisk(confidence_level)
        portfolio_var = var_calculator.parametric_normal(returns @ weights)
        z_alpha = stats.norm.ppf(1 - (1 - confidence_level))
        
        mcr = {}
        for i in range(len(weights)):
            # Perturbation method: add small epsilon to weight i
            epsilon = 1e-4
            perturbed_weights = weights.copy()
            perturbed_weights[i] += epsilon
            perturbed_weights /= perturbed_weights.sum()
            
            portfolio_var_perturbed = var_calculator.parametric_normal(returns @ perturbed_weights)
            mcr[f"asset_{i}"] = (portfolio_var_perturbed - portfolio_var) / epsilon
        
        return mcr
    
    def optimal_allocation(self, returns: np.ndarray,
                          target_sharpe: float = 1.5) -> np.ndarray:
        """
        Calculate optimal risk allocation using optimization.
        
        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        target_sharpe : float
            Target Sharpe ratio
        
        Returns
        -------
        weights : np.ndarray
            Optimal risk allocation weights
        """
        n_assets = returns.shape[1]
        n_obs = returns.shape[0]
        
        # Expected returns and covariance
        expected_returns = np.mean(returns, axis=0)
        cov_matrix = np.cov(returns, rowvar=False)
        
        # Negative Sharpe ratio for minimization
        def negative_sharpe(w):
            portfolio_return = w @ expected_returns
            portfolio_vol = np.sqrt(w @ cov_matrix @ w.T)
            sharpe = (portfolio_return - 0.02) / portfolio_vol if portfolio_vol > 0 else -np.inf
            return -sharpe
        
        # Constraints
        bounds = tuple((0, 1) for _ in range(n_assets))
        constraints = [
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


class StressTesting:
    """
    Stress Testing and Scenario Analysis

    Tests portfolio performance under extreme scenarios.
    """
    
    def __init__(self, returns: np.ndarray):
        """
        Initialize stress tester.
        
        Parameters
        ----------
        returns : np.ndarray
            Asset returns
        """
        self.returns = returns
    
    def historical_scenarios(self, n_scenarios: int = 100) -> np.ndarray:
        """
        Generate historical scenarios (bootstrap).
        
        Parameters
        ----------
        n_scenarios : int
            Number of scenarios to generate
        
        Returns
        -------
        scenarios : np.ndarray
            Historical scenarios
        """
        n_obs = len(self.returns)
        scenarios = np.random.choice(self.returns, size=(n_scenarios, n_obs))
        return scenarios
    
    def industry_scenarios(self, multiplier: float = 1.5) -> np.ndarray:
        """
        Generate industry standard stress scenarios.
        
        Typical stress scenarios:
        - Market crash: -30% to -50%
        - Financial crisis: -50% to -70%
        - Black Swan: -70% to -90%
        
        Parameters
        ----------
        multiplier : float
        Multiplier for typical market returns
        
        Returns
        -------
        scenarios : np.ndarray
            Stress test scenarios
        """
        typical_returns = np.array([0.10, 0.05, -0.05, -0.10, -0.30, -0.50])
        stressed_returns = typical_returns * multiplier
        
        scenarios = np.zeros((len(stressed_returns), len(self.returns)))
        for i, stress_return in enumerate(stressed_returns):
            scenarios[i, :] = stress_return
        
        return scenarios
    
    def monte_carlo_stress_test(self, n_scenarios: int = 1000,
                                 confidence_level: float = 0.95) -> Dict[str, Any]:
        """
        Monte Carlo stress testing.
        
        Parameters
        ----------
        n_scenarios : int
            Number of scenarios
        confidence_level : float
            Confidence level
        
        Returns
        -------
        results : dict
            Stress test results
        """
        # Generate extreme scenarios
        scenarios = np.random.normal(0, 0.05, n_scenarios)
        extreme_scenarios = scenarios[scenarios < 0]
        
        # Calculate losses
        losses = np.abs(extreme_scenarios)
        
        # Calculate VaR and ES
        var = np.percentile(losses, (1 - confidence_level) * 100)
        es = np.mean(losses[losses <= var])
        
        return {
            'n_scenarios': n_scenarios,
            'var': var,
            'expected_shortfall': es,
            'extreme_loss_percentiles': {
                '90th': np.percentile(losses, 90),
                '95th': np.percentile(losses, 95),
                '99th': np.percentile(losses, 99)
            }
        }
    
    def backtest_risk_limits(self, returns: np.ndarray,
                             var_threshold: float, confidence_level: float = 0.95) -> Dict[str, Any]:
        """
        Backtest if risk limits are respected.
        
        Parameters
        ----------
        returns : np.ndarray
            Portfolio returns
        var_threshold : float
            Maximum allowed VaR
        confidence_level : float
            Confidence level
        
        Returns
        -------
        results : dict
            Backtest results
        """
        var_calculator = ValueAtRisk(confidence_level)
        actual_var = var_calculator.parametric_normal(returns)
        
        # Check if threshold is exceeded
        exceeded = actual_var > var_threshold
        n_exceedances = np.sum(exceeded)
        exceedance_ratio = n_exceedances / len(returns)
        
        # Expected number of exceedances under normality
        expected_exceedances = len(returns) * (1 - confidence_level)
        
        return {
            'actual_var': actual_var,
            'var_threshold': var_threshold,
            'exceeded': exceeded,
            'n_exceedances': n_exceedances,
            'exceedance_ratio': exceedance_ratio,
            'expected_exceedances': expected_exceedances,
            'is_within_limits': not exceeded,
            'confidence_level': confidence_level
        }
