"""
Unified Risk Manager

Consolidated risk management implementation using Quant-Math core modules.
"""

import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from quant_math.core.types import StrategyResult
from quant_math.risk.position_sizing import PositionSizer
from quant_math.risk.stop_loss import StopLoss
from quant_math.risk.kelly import KellyCriterion
from quant_math.risk.var import ValueAtRisk, ExpectedShortfall
from quant_math.expectation import DrawdownAnalyzer, SharpeMetrics


class RiskManager:
    """
    Unified Risk Manager implementing the RiskManager protocol.

    Consolidates position sizing, drawdown monitoring, risk metrics,
    and stress testing using Quant-Math core modules.
    """

    def __init__(
        self,
        max_position_size_pct: float = 0.2,
        max_daily_loss_pct: float = 0.05,
        max_overall_loss_pct: float = 0.15,
        kelly_fraction: float = 0.3,
        drawdown_limit: float = 0.2
    ):
        """
        Initialize the risk management engine.

        Args:
            max_position_size_pct: Maximum position size as % of capital (default: 20%)
            max_daily_loss_pct: Maximum daily loss as % of capital (default: 5%)
            max_overall_loss_pct: Maximum overall loss as % of capital (default: 15%)
            kelly_fraction: Fraction of Kelly criterion to use (default: 30%)
            drawdown_limit: Maximum acceptable drawdown (default: 20%)
        """
        self.max_position_size_pct = max_position_size_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_overall_loss_pct = max_overall_loss_pct
        self.kelly_fraction = kelly_fraction
        self.drawdown_limit = drawdown_limit

        # Initialize Quant-Math components
        self.position_sizer = PositionSizer()
        self.stop_loss = StopLoss()
        self.kelly = KellyCriterion()
        self.var_calculator = ValueAtRisk()
        self.es_calculator = ExpectedShortfall()
        self.drawdown_analyzer = DrawdownAnalyzer()
        self.sharpe_metrics = SharpeMetrics()

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
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        **risk_params
    ) -> Dict[str, Any]:
        """
        Check if position size meets risk criteria.

        Args:
            hypothesis_id: Hypothesis ID
            requested_size: Requested position size (absolute value)
            account_value: Total account value
            win_rate: Win rate for Kelly calculation (optional)
            avg_win: Average win for Kelly calculation (optional)
            avg_loss: Average loss for Kelly calculation (optional)
            **risk_params: Additional risk parameters

        Returns:
            Dictionary with risk check results
        """
        # Apply position limits
        max_position = account_value * self.max_position_size_pct

        # Calculate Kelly optimal position size
        kelly_size = self._calculate_kelly_position_size(
            hypothesis_id, account_value, win_rate, avg_win, avg_loss
        )

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

        # Check overall loss limit
        current_loss = self.overall_pnl.get(hypothesis_id, 0.0)
        if current_loss < -account_value * self.max_overall_loss_pct:
            approved = False
            reasons.append(f"Overall loss {current_loss:.2f} exceeds limit")

        # Store position size
        self.position_sizes[hypothesis_id] = actual_size if approved else 0.0

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

    def _calculate_kelly_position_size(
        self,
        hypothesis_id: str,
        account_value: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None
    ) -> float:
        """
        Calculate Kelly optimal position size.

        Args:
            hypothesis_id: Hypothesis ID
            account_value: Total account value
            win_rate: Win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount

        Returns:
            Kelly optimal position size
        """
        # Use provided values or defaults
        wr = win_rate if win_rate is not None else 0.5
        aw = avg_win if avg_win is not None else 1.0
        al = avg_loss if avg_loss is not None else 1.0

        # Kelly formula: f = p - q/b where p=win_rate, q=1-p, b=win_loss_ratio
        if aw <= 0:
            return 0.0

        win_loss_ratio = aw / al if al != 0 else 0.0
        if win_loss_ratio <= 0:
            return 0.0

        f = wr - (1 - wr) / win_loss_ratio

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
        limit = limit or self.drawdown_limit

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
        metrics = {}

        # Basic metrics from result
        metrics["sharpe_ratio"] = result.sharpe_ratio
        metrics["sortino_ratio"] = result.sortino_ratio
        metrics["max_drawdown"] = result.max_drawdown
        metrics["win_rate"] = result.win_rate
        metrics["total_trades"] = result.total_trades
        metrics["profit_factor"] = result.profit_factor

        # VaR/ES using Quant-Math
        if result.trades and len(result.trades) > 0:
            # Extract returns from trades
            returns = []
            for trade in result.trades:
                if isinstance(trade, dict):
                    pnl = trade.get('pnl') or trade.get('PnL')
                    if pnl is not None:
                        returns.append(float(pnl))
                elif hasattr(trade, 'pnl'):
                    returns.append(float(trade.pnl))

            if returns:
                returns_arr = np.array(returns)
                metrics["var_95"] = float(self.var_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.95))
                metrics["var_99"] = float(self.var_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.99))
                metrics["expected_shortfall_95"] = float(self.es_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.95))
                metrics["expected_shortfall_99"] = float(self.es_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.99))

        # Recovery factor
        if result.max_drawdown != 0:
            metrics["recovery_factor"] = abs(result.net_profit) / result.max_drawdown
        else:
            metrics["recovery_factor"] = float('inf')

        return metrics

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

        if "return_shock" in scenario:
            shocked_return = result.total_return + scenario["return_shock"]
            stressed_metrics["stressed_total_return"] = shocked_return
            stressed_metrics["return_impact"] = scenario["return_shock"]

        if "volatility_multiplier" in scenario:
            stressed_sharpe = result.sharpe_ratio / scenario["volatility_multiplier"]
            stressed_metrics["stressed_sharpe_ratio"] = stressed_sharpe
            stressed_metrics["volatility_impact"] = scenario["volatility_multiplier"]

        if "slippage_multiplier" in scenario:
            # Approximate slippage impact on returns
            stressed_return = result.total_return * (1 - scenario["slippage_multiplier"] * 0.001)
            stressed_metrics["stressed_total_return"] = stressed_return
            stressed_metrics["slippage_impact"] = scenario["slippage_multiplier"]

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


# Convenience function
def create_risk_manager(**kwargs) -> RiskManager:
    """Create a RiskManager with custom parameters."""
    return RiskManager(**kwargs)