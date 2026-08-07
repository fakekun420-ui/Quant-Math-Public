"""
Risk Manager Implementation.

Implements the RiskManager port for risk assessment and management
of trading strategies.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime, timedelta

from ..interfaces import RiskManager, StrategyResult


class RiskManagementEngine(RiskManager):
    """
    Implementation of RiskManager port.

    Provides risk management functionality including:
    - Position sizing calculations
    - Risk limit checking
    - Drawdown monitoring
    - Risk metrics calculation
    """

    def __init__(
        self,
        max_position_size_pct: float = 0.2,
        max_daily_loss_pct: float = 0.05,
        max_overall_loss_pct: float = 0.15,
        kelly_fraction: float = 0.3
    ):
        """
        Initialize the risk management engine.

        Args:
            max_position_size_pct: Maximum position size as % of capital (default: 20%)
            max_daily_loss_pct: Maximum daily loss as % of capital (default: 5%)
            max_overall_loss_pct: Maximum overall loss as % of capital (default: 15%)
            kelly_fraction: Fraction of Kelly criterion to use (default: 30%)
        """
        self.max_position_size_pct = max_position_size_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_overall_loss_pct = max_overall_loss_pct
        self.kelly_fraction = kelly_fraction

        # Risk monitoring state
        self.position_sizes: Dict[str, float] = {}
        self.daily_pnl: Dict[str, float] = {}
        self.overall_pnl: Dict[str, float] = {}
        self.risk_checks: Dict[str, List[Dict[str, Any]]] = {}
        self.risk_violations: Dict[str, List[str]] = {}

    def check_position_size(
        self,
        hypothesis_id: str,
        requested_size: float,
        account_value: float,
        **risk_params
    ) -> Dict[str, Any]:
        """
        Check if position size meets risk criteria.

        Args:
            hypothesis_id: Hypothesis ID
            requested_size: Requested position size (absolute value)
            account_value: Total account value
            **risk_params: Additional risk parameters

        Returns:
            Dictionary with risk check results
        """
        print(f"[RiskManagementEngine] Checking position size for {hypothesis_id}")

        # Apply position limits
        max_position = account_value * self.max_position_size_pct

        # Calculate Kelly optimal position size
        kelly_size = self._calculate_kelly_position_size(hypothesis_id, account_value)

        # Check constraints
        approved = True
        reasons = []
        actual_size = requested_size

        # Check maximum position size
        if requested_size > max_position:
            approved = False
            reasons.append(f"Position size {requested_size:.2f} exceeds max {max_position:.2f}")
            actual_size = min(requested_size, max_position)

        # Check Kelly criterion
        if kelly_size > 0 and requested_size > kelly_size:
            warning = f"Position size exceeds Kelly optimal (Kelly={kelly_size:.2f})"
            reasons.append(warning)
            # This is a warning, not necessarily a rejection

        # Check overall loss limit
        current_loss = self.overall_pnl.get(hypothesis_id, 0.0)
        if current_loss < -account_value * self.max_overall_loss_pct:
            approved = False
            reasons.append(f"Overall loss {current_loss:.2f} exceeds limit")

        # Store position size
        self.position_sizes[hypothesis_id] = actual_size

        # Record risk check
        check_record = {
            "timestamp": datetime.now().isoformat(),
            "requested_size": requested_size,
            "approved_size": actual_size if approved else 0.0,
            "approved": approved,
            "reasons": reasons,
            "max_position": max_position,
            "kelly_size": kelly_size,
            "account_value": account_value
        }

        if hypothesis_id not in self.risk_checks:
            self.risk_checks[hypothesis_id] = []
        self.risk_checks[hypothesis_id].append(check_record)

        if not approved:
            if hypothesis_id not in self.risk_violations:
                self.risk_violations[hypothesis_id] = []
            self.risk_violations[hypothesis_id].extend(reasons)

        return check_record

    def _calculate_kelly_position_size(self, hypothesis_id: str, account_value: float) -> float:
        """
        Calculate Kelly optimal position size.

        Args:
            hypothesis_id: Hypothesis ID
            account_value: Total account value

        Returns:
            Kelly optimal position size
        """
        # Default Kelly calculation (simplified)
        win_rate = 0.5  # Placeholder, should come from strategy analysis
        win_loss_ratio = 2.0  # Placeholder

        if win_loss_ratio <= 0:
            return 0.0

        # Kelly formula: f = p - q/b where p=win_rate, q=1-p, b=win_loss_ratio
        f = win_rate - (1 - win_rate) / win_loss_ratio

        # Apply fraction
        kelly_fraction = max(0.0, min(1.0, f * self.kelly_fraction))

        return account_value * kelly_fraction

    def check_drawdown_limit(
        self,
        hypothesis_id: str,
        current_drawdown: float,
        limit: Optional[float] = None
    ) -> bool:
        """
        Check if drawdown is within acceptable limits.

        Args:
            hypothesis_id: Hypothesis ID
            current_drawdown: Current drawdown (positive number)
            limit: Custom drawdown limit (uses default if None)

        Returns:
            True if drawdown is acceptable
        """
        limit = limit or self.max_overall_loss_pct

        acceptable = current_drawdown <= limit

        if not acceptable:
            violation = f"Drawdown {current_drawdown:.2%} exceeds limit {limit:.2%}"
            if hypothesis_id not in self.risk_violations:
                self.risk_violations[hypothesis_id] = []
            self.risk_violations[hypothesis_id].append(violation)

        return acceptable

    def check_sharpe_threshold(
        self,
        sharpe_ratio: float,
        threshold: float = 1.0
    ) -> bool:
        """
        Check if Sharpe ratio meets threshold.

        Args:
            sharpe_ratio: Sharpe ratio to check
            threshold: Minimum acceptable Sharpe ratio

        Returns:
            True if Sharpe ratio meets threshold
        """
        return sharpe_ratio >= threshold

    def check_sortino_threshold(
        self,
        sortino_ratio: float,
        threshold: float = 1.0
    ) -> bool:
        """
        Check if Sortino ratio meets threshold.

        Args:
            sortino_ratio: Sortino ratio to check
            threshold: Minimum acceptable Sortino ratio

        Returns:
            True if Sortino ratio meets threshold
        """
        return sortino_ratio >= threshold

    def check_calmar_threshold(
        self,
        calmar_ratio: float,
        threshold: float = 0.5
    ) -> bool:
        """
        Check if Calmar ratio meets threshold.

        Args:
            calmar_ratio: Calmar ratio to check
            threshold: Minimum acceptable Calmar ratio

        Returns:
            True if Calmar ratio meets threshold
        """
        return calmar_ratio >= threshold

    def calculate_risk_metrics(
        self,
        result: StrategyResult
    ) -> Dict[str, float]:
        """
        Calculate comprehensive risk metrics for strategy.

        Args:
            result: StrategyResult from backtest

        Returns:
            Dictionary with risk metrics
        """
        metrics = {
            "sharpe_ratio": result.sharpe_ratio,
            "sortino_ratio": 0.0,  # Placeholder, would need downside deviation
            "calmar_ratio": 0.0,  # Placeholder, would need annual return
            "max_drawdown": result.max_drawdown,
            "var_95": self._calculate_var_95(result),
            "var_99": self._calculate_var_99(result),
            "win_rate": result.win_rate,
            "profit_factor": self._calculate_profit_factor(result),
            "recovery_factor": self._calculate_recovery_factor(result),
            "ulcer_index": self._calculate_ulcer_index(result)
        }

        return metrics

    def _calculate_var_95(self, result: StrategyResult) -> float:
        """Calculate Value at Risk at 95% confidence level"""
        if not result.trades or len(result.trades) == 0:
            return 0.0

        # Simplified VaR calculation using normal distribution
        # This should be enhanced with actual trade PnL data
        return result.max_drawdown * 0.7  # Placeholder

    def _calculate_var_99(self, result: StrategyResult) -> float:
        """Calculate Value at Risk at 99% confidence level"""
        if not result.trades or len(result.trades) == 0:
            return 0.0

        return result.max_drawdown * 0.8  # Placeholder

    def _calculate_profit_factor(self, result: StrategyResult) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        if not result.trades or len(result.trades) == 0:
            return 0.0

        # Placeholder calculation
        gross_profit = result.win_rate * result.total_trades * 100  # Example
        gross_loss = (1 - result.win_rate) * result.total_trades * 50  # Example

        return gross_profit / gross_loss if gross_loss > 0 else float('inf')

    def _calculate_recovery_factor(self, result: StrategyResult) -> float:
        """Calculate recovery factor (net profit / max drawdown)"""
        if result.max_drawdown == 0:
            return float('inf')

        return abs(result.net_profit) / result.max_drawdown

    def _calculate_ulcer_index(self, result: StrategyResult) -> float:
        """Calculate Ulcer Performance Index"""
        if not result.trades or len(result.trades) == 0:
            return 0.0

        # Placeholder: simplified calculation
        return np.sqrt(result.max_drawdown) * 10  # Placeholder

    def check_correlation_risk(
        self,
        hypothesis_id: str,
        correlations: Dict[str, float],
        max_correlation: float = 0.7
    ) -> Dict[str, Any]:
        """
        Check correlation risk with other strategies.

        Args:
            hypothesis_id: Hypothesis ID
            correlations: Dictionary of correlation coefficients
            max_correlation: Maximum acceptable correlation

        Returns:
            Dictionary with correlation risk assessment
        """
        high_correlations = {}
        for other_id, correlation in correlations.items():
            if abs(correlation) > max_correlation:
                high_correlations[other_id] = correlation

        result = {
            "hypothesis_id": hypothesis_id,
            "max_correlation": max_correlation,
            "high_correlations": high_correlations,
            "has_high_correlation": len(high_correlations) > 0
        }

        if high_correlations:
            warning = f"High correlation detected with {len(high_correlations)} strategies"
            if hypothesis_id not in self.risk_violations:
                self.risk_violations[hypothesis_id] = []
            self.risk_violations[hypothesis_id].append(warning)

        return result

    def stress_test_strategy(
        self,
        result: StrategyResult,
        stress_scenarios: List[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Perform stress testing on strategy.

        Args:
            result: StrategyResult from backtest
            stress_scenarios: List of stress scenarios

        Returns:
            Dictionary with stress test results
        """
        if stress_scenarios is None:
            stress_scenarios = [
                {"name": "market_crash", "return_shock": -0.20},
                {"name": "volatility_spike", "volatility_multiplier": 3.0},
                {"name": "liquidity_crisis", "slippage_multiplier": 5.0}
            ]

        results = {}
        for scenario in stress_scenarios:
            scenario_name = scenario["name"]
            stressed_result = self._apply_stress_scenario(result, scenario)
            results[scenario_name] = stressed_result

        return results

    def _apply_stress_scenario(self, result: StrategyResult, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Apply stress scenario to strategy results"""
        stressed_metrics = {
            "original_total_return": result.total_return,
            "original_sharpe_ratio": result.sharpe_ratio,
            "original_max_drawdown": result.max_drawdown
        }

        # Apply scenario adjustments (simplified)
        if "return_shock" in scenario:
            shocked_return = result.total_return + scenario["return_shock"]
            stressed_metrics["stressed_total_return"] = shocked_return
            stressed_metrics["return_impact"] = scenario["return_shock"]

        if "volatility_multiplier" in scenario:
            stressed_sharpe = result.sharpe_ratio / scenario["volatility_multiplier"]
            stressed_metrics["stressed_sharpe_ratio"] = stressed_sharpe
            stressed_metrics["volatility_impact"] = scenario["volatility_multiplier"]

        return stressed_metrics

    def get_risk_check_history(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Get risk check history for a hypothesis"""
        return self.risk_checks.get(hypothesis_id, [])

    def get_risk_violations(self, hypothesis_id: str) -> List[str]:
        """Get risk violations for a hypothesis"""
        return self.risk_violations.get(hypothesis_id, [])

    def clear_risk_data(self, hypothesis_id: str = None):
        """Clear risk data for a hypothesis or all hypotheses"""
        if hypothesis_id:
            self.position_sizes.pop(hypothesis_id, None)
            self.daily_pnl.pop(hypothesis_id, None)
            self.overall_pnl.pop(hypothesis_id, None)
            self.risk_checks.pop(hypothesis_id, None)
            self.risk_violations.pop(hypothesis_id, None)
        else:
            self.position_sizes.clear()
            self.daily_pnl.clear()
            self.overall_pnl.clear()
            self.risk_checks.clear()
            self.risk_violations.clear()