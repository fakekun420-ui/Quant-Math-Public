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
        n_closures: Optional[int] = None,
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
            n_closures: Numero de cierres de los que salen esas medidas.
                Si viene y es menor que MIN_CLOSURES_FOR_KELLY, NO se
                calcula Kelly: una muestra chica lo mueve una sola
                operacion y el tamano resultante seria una invencion.
            **risk_params: Additional risk parameters

        Returns:
            Dictionary with risk check results. El registro incluye
            `kelly_status` + `kelly_note` (por que hay o no hay Kelly) y
            `kelly_advisory` (aviso si el pedido supera el Kelly medido).
        """
        # Apply position limits
        max_position = account_value * self.max_position_size_pct

        # Kelly con la formula canonica del modulo y datos medidos, o con
        # un estado EXPLICITO de por que no lo hay. Antes esto devolia un
        # 0.0 silencioso con los defaults (wr=0.5, aw=1, al=1), y ese cero
        # desactivaba el aviso de Kelly sin que nadie supiera que no habia
        # medida que lo sustentara.
        kelly = self._kelly_assessment(
            account_value, win_rate, avg_win, avg_loss, n_closures
        )
        kelly_size = kelly["size"]  # float | None: nunca un 0 sin explicar

        # Check constraints
        approved = True
        reasons = []
        actual_size = requested_size

        # Check maximum position size
        if requested_size > max_position:
            approved = False
            reasons.append(f"Position size {requested_size:.2f} exceeds max {max_position:.2f}")
            actual_size = min(requested_size, max_position)

        # Aviso de Kelly: supera el tamano recomendado, pero NO cambia la
        # aprobacion.
        #
        # Por que NO va en `reasons`: el orquestador lee `reasons` para
        # decidir entre RECORTAR el margen (si todo razon es "exceeds max")
        # y RECHAZAR la entrada (si hay cualquier otra razon). Con Kelly
        # medido su fraccion va SIEMPRE por debajo de max_position_pct
        # (0.03-0.17 medido frente a 0.20), asi que meter aqui el aviso
        # haria que cada tope de margen se convirtiera en un rechazo
        # cerrado: el dimensionamiento en vivo cambiaria sin medirse.
        # El aviso se expone aparte, en `kelly_advisory`.
        kelly_advisory = None
        if kelly_size is not None and kelly_size > 0 and requested_size > kelly_size:
            kelly_advisory = (f"Position size exceeds Kelly optimal "
                              f"(Kelly={kelly_size:.2f})")

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
            "kelly_status": kelly["status"],
            "kelly_note": kelly["note"],
            "kelly_fraction_applied": kelly["fraction"],
            "kelly_advisory": kelly_advisory,
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

    # Muestra minima de cierres para dar por bueno un win_rate medido del
    # libro de operaciones. No es un capricho: con N=20 un solo cierre
    # mueve el win_rate 5 puntos porcentuales (1/N), y por debajo de eso
    # el Kelly se dispara o se anula por el ruido de UNA operacion — el
    # tamano resultante dejaria de ser una medida para ser una invencion.
    MIN_CLOSURES_FOR_KELLY = 20

    def _kelly_assessment(
        self,
        account_value: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        n_closures: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Kelly con la formula CANONICA del modulo (`KellyCriterion.calculate`).

        Antes estaba reimplementada a mano en este mismo fichero
        (`f = wr - (1 - wr) / win_loss_ratio`, con defaults wr=0.5,
        aw=1.0, al=1.0 que daban exactamente 0.0), y ese 0.0 silencioso
        desactivaba el aviso de Kelly pareciendo una medida. Por eso el
        resultado ahora es un estado explicito:

          - "sin_datos"       -> size=None: faltan win_rate/avg_win/avg_loss
          - "insuficiente"    -> size=None: hay muestra pero < piso
          - "datos_invalidos" -> size=None: valores fuera de dominio
          - "no_viable"       -> size=0.0: el Kelly MEDIDO no compensa
          - "ok"              -> size=float: Kelly medido

        Un 0.0 numerico solo puede salir de "no_viable", que lo explica.
        Los cuatro estados no-"ok" declaran ademas en que metodo se cae
        el dimensionado (el tope declarado max_position_size_pct).

        Si `n_closures` no se informa, las estadisticas se dan por buenas:
        quien las pasa se responsabiliza de su muestra. El orquestador
        pasa siempre la n medido del ledger.
        """
        faltantes = [nombre for nombre, valor in
                     (("win_rate", win_rate), ("avg_win", avg_win),
                      ("avg_loss", avg_loss)) if valor is None]
        if faltantes:
            return {
                "status": "sin_datos",
                "size": None,
                "fraction": None,
                "note": (
                    f"sin {', '.join(faltantes)} medidos: NO se dimensiona "
                    "con Kelly. Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%} "
                    f"(= {account_value * self.max_position_size_pct:.2f} "
                    f"USD de margen sobre cuenta {account_value:.2f})"
                ),
            }

        if n_closures is not None and n_closures < self.MIN_CLOSURES_FOR_KELLY:
            return {
                "status": "insuficiente",
                "size": None,
                "fraction": None,
                "note": (
                    f"solo {n_closures} cierres medidos (piso "
                    f"{self.MIN_CLOSURES_FOR_KELLY}): una sola operacion "
                    "mueve el win_rate mas de "
                    f"{100.0 / max(1, int(n_closures)):.1f} pp. NO se "
                    "dimensiona con Kelly. Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%} "
                    f"(= {account_value * self.max_position_size_pct:.2f} "
                    "USD de margen)"
                ),
            }

        try:
            wr, aw, al = float(win_rate), float(avg_win), float(avg_loss)
            valido = (0.0 <= wr <= 1.0) and (aw > 0) and (al > 0)
        except (TypeError, ValueError):
            valido = False
        if not valido:
            return {
                "status": "datos_invalidos",
                "size": None,
                "fraction": None,
                "note": (
                    f"datos de Kelly fuera de dominio (win_rate={win_rate}, "
                    f"avg_win={avg_win}, avg_loss={avg_loss}): se ignora el "
                    "Kelly. Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%}"
                ),
            }

        # Unico punto de calculo, y es la formula canonica del modulo.
        # Antes estaba duplicada a mano aqui: dos fuentes de verdad para
        # la misma formula es como se acaba midiendo una cosa creyendo
        # que se mide la otra.
        full = float(self.kelly.calculate(wr, aw, al))

        if full <= 0.0:
            # El cero MEDIDO: con estos datos no compensa apostar. Se
            # declara para que sea distinguible de "no hay datos".
            n_txt = (f"{n_closures} cierres" if n_closures is not None
                     else "cierres no informados")
            return {
                "status": "no_viable",
                "size": 0.0,
                "fraction": 0.0,
                "note": (
                    f"Kelly medido = {full:.4f} <= 0 con win_rate={wr:.4f}, "
                    f"avg_win={aw:.6f}, avg_loss={al:.6f} ({n_txt}): no "
                    "compensa apostar (0.0 es una medida, no la ausencia de "
                    "ella). Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%}"
                ),
            }

        fraction = max(0.0, min(1.0, full * self.kelly_fraction))
        n_txt = (f"{n_closures} cierres" if n_closures is not None
                 else "cierres no informados")
        return {
            "status": "ok",
            "size": account_value * fraction,
            "fraction": fraction,
            "note": (
                f"Kelly medido = {full:.4f} x fraccion "
                f"{self.kelly_fraction} = {fraction:.4f} -> "
                f"{account_value * fraction:.2f} USD de margen "
                f"(win_rate={wr:.4f}, {n_txt})"
            ),
        }

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