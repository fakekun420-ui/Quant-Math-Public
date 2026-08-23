"""
Monte Carlo Simulation Engine

Unified Monte Carlo simulation for backtest robustness testing and risk assessment.
"""

import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from types import SimpleNamespace

from quant_math.core.types import StrategyResult, MonteCarloResult


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation."""
    n_iterations: int = 1000
    confidence_level: float = 0.95
    method: str = "bootstrap"  # "bootstrap" or "parametric"
    random_seed: Optional[int] = None


class MonteCarloSimulator:
    """
    Unified Monte Carlo simulator for trading strategy validation.

    Provides bootstrap resampling, parametric simulation, VaR/ES calculation,
    and stress testing capabilities.
    """

    def __init__(self, config: Optional[MonteCarloConfig] = None):
        """
        Initialize Monte Carlo simulator.

        Args:
            config: Simulation configuration
        """
        self.config = config or MonteCarloConfig()
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

        self.simulations: Dict[str, MonteCarloResult] = {}
        self.simulation_params: Dict[str, Dict[str, Any]] = {}

    def simulate_distribution(
        self,
        result: StrategyResult,
        n_iterations: Optional[int] = None,
        confidence_level: Optional[float] = None,
        method: Optional[str] = None
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on backtest results.

        Args:
            result: StrategyResult from backtest
            n_iterations: Number of simulation iterations (overrides config)
            confidence_level: Confidence level for intervals (overrides config)
            method: Simulation method 'bootstrap' or 'parametric' (overrides config)

        Returns:
            MonteCarloResult with distribution statistics
        """
        n_iter = n_iterations or self.config.n_iterations
        conf = confidence_level or self.config.confidence_level
        meth = method or self.config.method

        # Accept either a StrategyResult or a raw list/array of trade PnLs
        if isinstance(result, (list, tuple, np.ndarray)):
            result = SimpleNamespace(
                hypothesis_id="direct_pnls",
                trades=[{"pnl": float(p)} for p in result],
                total_return=float(np.mean(result)) if len(result) else 0.0,
                total_trades=len(result),
            )

        if not result.trades or len(result.trades) == 0:
            return MonteCarloResult(
                hypothesis_id=result.hypothesis_id,
                n_iterations=0,
                mean=0.0,
                median=0.0,
                std_dev=0.0,
                min_value=0.0,
                max_value=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
                confidence_level=conf
            )

        # Extract trade PnLs from StrategyResult.trades
        trade_pnls = self._extract_trade_pnls(result.trades)
        n_trades = len(trade_pnls)

        if meth == "bootstrap":
            simulated_returns = self._bootstrap_simulation(trade_pnls, n_iter, n_trades)
        elif meth == "parametric":
            simulated_returns = self._parametric_simulation(trade_pnls, n_iter, n_trades)
        else:
            raise ValueError(f"Unknown simulation method: {meth}")

        # Calculate statistics
        mean_return = float(np.mean(simulated_returns))
        median_return = float(np.median(simulated_returns))
        std_dev = float(np.std(simulated_returns))

        # Calculate confidence intervals
        alpha = 1 - conf
        lower_bound = float(np.percentile(simulated_returns, alpha/2 * 100))
        upper_bound = float(np.percentile(simulated_returns, (1 - alpha/2) * 100))

        # Create result
        mc_result = MonteCarloResult(
            hypothesis_id=result.hypothesis_id,
            n_iterations=n_iter,
            mean=mean_return,
            median=median_return,
            std_dev=std_dev,
            min_value=float(np.min(simulated_returns)),
            max_value=float(np.max(simulated_returns)),
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence_level=conf
        )

        # Store simulation
        self.simulations[result.hypothesis_id] = mc_result
        self.simulation_params[result.hypothesis_id] = {
            "n_iterations": n_iter,
            "method": meth,
            "confidence_level": conf,
            "original_trades": n_trades
        }

        return mc_result

    def _extract_trade_pnls(self, trades: List[Dict[str, Any]]) -> np.ndarray:
        """Extract PnL values from trade records."""
        pnls = []
        for trade in trades:
            if isinstance(trade, dict):
                # Try multiple possible keys
                pnl = trade.get('pnl') or trade.get('PnL') or trade.get('profit_loss')
                if pnl is not None:
                    pnls.append(float(pnl))
            elif hasattr(trade, 'pnl'):
                pnls.append(float(trade.pnl))
            elif hasattr(trade, 'PnL'):
                pnls.append(float(trade.PnL))

        if not pnls:
            # Fallback: generate synthetic returns based on overall metrics
            if result.total_return != 0 and result.total_trades > 0:
                avg_return = result.total_return / result.total_trades
                pnls = np.random.normal(avg_return, abs(avg_return) * 2, result.total_trades).tolist()
            else:
                pnls = [0.0]

        return np.array(pnls)

    def _bootstrap_simulation(
        self,
        returns: np.ndarray,
        n_iterations: int,
        n_trades: int
    ) -> np.ndarray:
        """Bootstrap simulation (non-parametric resampling)."""
        simulated_returns = []

        for _ in range(n_iterations):
            # Sample with replacement
            bootstrap_sample = np.random.choice(returns, size=n_trades, replace=True)
            # Calculate cumulative return
            total_return = np.sum(bootstrap_sample)
            simulated_returns.append(total_return)

        return np.array(simulated_returns)

    def _parametric_simulation(
        self,
        returns: np.ndarray,
        n_iterations: int,
        n_trades: int
    ) -> np.ndarray:
        """Parametric simulation assuming normal distribution."""
        if len(returns) < 2:
            return np.zeros(n_iterations)

        # Fit normal distribution to returns
        mu, sigma = np.mean(returns), np.std(returns, ddof=1)

        simulated_returns = []
        for _ in range(n_iterations):
            # Generate synthetic returns
            synthetic_returns = np.random.normal(mu, sigma, n_trades)
            total_return = np.sum(synthetic_returns)
            simulated_returns.append(total_return)

        return np.array(simulated_returns)

    def calculate_var(
        self,
        result: StrategyResult,
        confidence_level: float = 0.95,
        n_iterations: int = 10000
    ) -> Dict[str, float]:
        """
        Calculate Value at Risk (VaR) using Monte Carlo.

        Args:
            result: StrategyResult from backtest
            confidence_level: VaR confidence level
            n_iterations: Number of Monte Carlo iterations

        Returns:
            Dictionary with VaR metrics
        """
        if not result.trades or len(result.trades) == 0:
            return {"var": 0.0, "expected_shortfall": 0.0}

        trade_pnls = self._extract_trade_pnls(result.trades)
        n_trades = len(trade_pnls)

        # Bootstrap simulation for portfolio values
        simulated_portfolio_values = []

        for _ in range(n_iterations):
            # Sample trades
            sample_returns = np.random.choice(trade_pnls, size=n_trades, replace=True)
            # Calculate portfolio value (starting from 100)
            portfolio_value = 100 * np.prod(1 + sample_returns / 10000)  # Normalize
            simulated_portfolio_values.append(portfolio_value)

        simulated_portfolio_values = np.array(simulated_portfolio_values)

        # Calculate VaR (loss relative to 100)
        var = 100 - np.percentile(simulated_portfolio_values, (1 - confidence_level) * 100)

        # Calculate Expected Shortfall (CVaR)
        alpha = 1 - confidence_level
        worst_tail = simulated_portfolio_values[simulated_portfolio_values <= np.percentile(simulated_portfolio_values, alpha * 100)]
        expected_shortfall = 100 - np.mean(worst_tail) if len(worst_tail) > 0 else var

        return {
            "var": float(var),
            "expected_shortfall": float(expected_shortfall),
            "confidence_level": confidence_level,
            "n_iterations": n_iterations
        }

    def calculate_probability_of_loss(
        self,
        result: StrategyResult,
        n_iterations: int = 10000
    ) -> float:
        """
        Calculate probability of loss using Monte Carlo.

        Args:
            result: StrategyResult from backtest
            n_iterations: Number of Monte Carlo iterations

        Returns:
            Probability of loss (0-1)
        """
        if not result.trades or len(result.trades) == 0:
            return 1.0

        trade_pnls = self._extract_trade_pnls(result.trades)
        n_trades = len(trade_pnls)

        losses = 0
        for _ in range(n_iterations):
            # Bootstrap sample
            sample_returns = np.random.choice(trade_pnls, size=n_trades, replace=True)
            # Check if total return is negative
            total_return = np.sum(sample_returns)
            if total_return < 0:
                losses += 1

        return losses / n_iterations

    def stress_test(
        self,
        result: StrategyResult,
        stress_scenarios: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Perform stress testing on strategy.

        Args:
            result: StrategyResult from backtest
            stress_scenarios: Dictionary of stress scenarios

        Returns:
            Dictionary with stress test results
        """
        if stress_scenarios is None:
            stress_scenarios = {
                "market_crash": {"return_shift": -0.15, "volatility_multiplier": 2.0},
                "high_volatility": {"return_shift": 0.0, "volatility_multiplier": 3.0},
                "low_volatility": {"return_shift": 0.02, "volatility_multiplier": 0.5},
                "flash_crash": {"return_shift": -0.30, "volatility_multiplier": 5.0}
            }

        trade_pnls = self._extract_trade_pnls(result.trades)
        results = {}

        for scenario_name, params in stress_scenarios.items():
            # Apply stress scenario
            stressed_returns = trade_pnls.copy()
            stressed_returns = stressed_returns * params["volatility_multiplier"] + params["return_shift"]

            # Calculate stressed performance
            total_return = np.sum(stressed_returns)
            mean_return = np.mean(stressed_returns)
            std_return = np.std(stressed_returns)

            results[scenario_name] = {
                "total_return": float(total_return),
                "mean_return": float(mean_return),
                "std_return": float(std_return),
                "sharpe_ratio": float(mean_return / std_return) if std_return > 0 else 0.0
            }

        return results

    def get_simulation(self, hypothesis_id: str) -> Optional[MonteCarloResult]:
        """Get Monte Carlo simulation result by hypothesis ID"""
        return self.simulations.get(hypothesis_id)

    def get_all_simulations(self) -> Dict[str, MonteCarloResult]:
        """Get all Monte Carlo simulation results"""
        return self.simulations

    def clear_simulations(self):
        """Clear all simulation results"""
        self.simulations.clear()
        self.simulation_params.clear()


# Convenience functions for direct use

def bootstrap_simulation(
    returns: np.ndarray,
    n_iterations: int = 1000
) -> np.ndarray:
    """
    Bootstrap resampling of returns.

    Args:
        returns: Array of returns
        n_iterations: Number of bootstrap samples

    Returns:
        Array of bootstrap means
    """
    n = len(returns)
    if n == 0:
        return np.zeros(n_iterations)

    bootstrap_means = []
    for _ in range(n_iterations):
        sample = np.random.choice(returns, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))

    return np.array(bootstrap_means)


def parametric_simulation(
    returns: np.ndarray,
    n_iterations: int = 1000
) -> np.ndarray:
    """
    Parametric simulation assuming normal distribution.

    Args:
        returns: Array of returns
        n_iterations: Number of simulations

    Returns:
        Array of simulated means
    """
    n = len(returns)
    if n < 2:
        return np.zeros(n_iterations)

    mu, sigma = np.mean(returns), np.std(returns, ddof=1)

    simulated_means = []
    for _ in range(n_iterations):
        sample = np.random.normal(mu, sigma, n)
        simulated_means.append(np.mean(sample))

    return np.array(simulated_means)


def calculate_var_es(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    n_iterations: int = 10000
) -> Dict[str, float]:
    """
    Calculate VaR and Expected Shortfall.

    Args:
        returns: Array of returns
        confidence_level: Confidence level
        n_iterations: Number of bootstrap iterations

    Returns:
        Dictionary with var and expected_shortfall
    """
    n = len(returns)
    if n == 0:
        return {"var": 0.0, "expected_shortfall": 0.0}

    simulated_returns = bootstrap_simulation(returns, n_iterations)
    alpha = 1 - confidence_level

    var = -np.percentile(simulated_returns, alpha * 100)
    es = -np.mean(simulated_returns[simulated_returns <= np.percentile(simulated_returns, alpha * 100)])

    return {"var": float(var), "expected_shortfall": float(es)}