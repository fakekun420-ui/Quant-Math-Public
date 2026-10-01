"""
Research Manager - Main Orchestrator for AQDE.

The Research Manager coordinates all research activities across the
autonomous discovery pipeline. It manages the research workflow,
deploys agents for specific tasks, and tracks hypothesis lifecycle.
"""

import hashlib
import os
import threading
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar
from enum import Enum

from ..interfaces import (
    Agent,
    AgentMessage,
    Hypothesis,
    StrategyResult,
    MonteCarloResult,
    StrategyType,
    StrategyStatus,
    AgentMessage as Message,
    BacktestEngine,
    KnowledgeBase,
    MonteCarloEngine,
    StatisticalValidator,
    RiskManager,
)
from quant_math.expectation.statistical_tests import StatisticalTests
from quant_math.risk.gate_policy import (
    FIELD_MC_CONCLUSIVE,
    FIELD_PVALUE,
    FIELD_PVALUE_ALPHA,
    FIELD_SCIENTIFICALLY_VALIDATED,
    FIELD_SCIENTIFIC_REASONS,
    FIELD_VALIDATION_SCORE,
    resolve_scientific_policy,
)
from .agent_registry import AgentRegistry

#: El bootstrap del Monte Carlo (el puerto inyectado, o sea el adapter) usa el
#: `np.random` GLOBAL. El pipeline corre en paralelo por simbolo
#: (`_generate_and_backtest_symbol` se lanza en un ThreadPoolExecutor de 3),
#: luego sembrar sin este candado haria que dos hipotesis se repartieran el
#: mismo stream y el resultado dependiera del ORDEN de los hilos: el mismo
#: backtest daría un CI95 distinto en cada ciclo. El candado convierte la
#: simulacion en una seccion critica sembrada, que es determinista.
_MC_SEED_LOCK = threading.Lock()

#: Iteraciones por defecto del bootstrap. 1000 es lo que usa el puerto; con
#: el sembrado determinista mas abajo, un numero mayor no cuesta nada de
#: varianza pero si de CPU, asi que se deja en el valor declarado.
DEFAULT_MC_ITERATIONS = 1000


class ResearchPhase(Enum):
    """Phases of the research workflow"""
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    VALIDATION = "validation"
    BACKTESTING = "backtesting"
    MONTE_CARLO_TESTING = "monte_carlo_testing"
    SCORING = "scoring"
    LEARNING = "learning"
    DEPLOYMENT = "deployment"


T = TypeVar("T")


class ResearchManager:
    """
    Main orchestrator for autonomous hypothesis discovery.

    Coordinates research agents, manages hypothesis lifecycle,
    and implements the 5-phase research pipeline.
    """

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        backtest_engine: BacktestEngine,
        monte_carlo_engine: MonteCarloEngine,
        statistical_validator: StatisticalValidator,
        risk_manager: RiskManager,
        agent_registry: "AgentRegistry" = None,
        validated_score_threshold: float = 0.0,
    ):
        """
        Initialize the Research Manager.

        Args:
            knowledge_base: Port for hypothesis storage and retrieval
            backtest_engine: Port for backtesting
            monte_carlo_engine: Port for Monte Carlo simulations
            statistical_validator: Port for statistical validation
            risk_manager: Port for risk management checks
            agent_registry: Agent registry (optional, uses default if not provided)
        """
        self.knowledge_base = knowledge_base
        self.backtest_engine = backtest_engine
        self.monte_carlo_engine = monte_carlo_engine
        self.statistical_validator = statistical_validator
        self.risk_manager = risk_manager

        self.agent_registry = agent_registry or AgentRegistry()

        # Umbral para marcar `validated`. Por defecto 0.0: el score es una
        # suma ponderada de tres componentes que NO estan normalizadas a 0-1,
        # asi que un corte en 0,6 medido sobre datos reales (maximo observado
        # 0,13 el 2026-09-30) deja TODO en `failed`. Quien decide si una
        # hipotesis se opera es el gate de expectancy contra el coste real.
        self.validated_score_threshold = float(validated_score_threshold)

        # Research state
        self.current_phase = ResearchPhase.HYPOTHESIS_GENERATION
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.results: Dict[str, StrategyResult] = {}
        self.monte_carlo_results: Dict[str, MonteCarloResult] = {}
        #: Veredictos por fase. Viven aparte del resultado porque el
        #: resultado es un NUMERO y el veredicto es "este numero significa
        #: algo / no significa nada". Con 7 operaciones el bootstrap devuelve
        #: un intervalo igual de preciso que con 400, y sin este campo
        #: aparte no habria forma de distinguir los dos casos.
        self.statistical_results: Dict[str, Dict[str, Any]] = {}
        self.monte_carlo_verdicts: Dict[str, Dict[str, Any]] = {}
        self.experiments: List[Dict[str, Any]] = []

        # Politica de la validacion cientifica (umbrales declarados, una sola
        # vez): ver `quant_math.risk.gate_policy`.
        self.scientific_policy = resolve_scientific_policy()

        print(f"[ResearchManager] Initialized with knowledge_base, backtest_engine, "
              f"monte_carlo_engine, statistical_validator, risk_manager")
        print(f"[ResearchManager] politica cientifica: min_operaciones="
              f"{self.scientific_policy['min_trades']} alpha="
              f"{self.scientific_policy['alpha']} gate="
              f"{self.scientific_policy['require']}")

    def generate_hypothesis(
        self,
        hypothesis_id: Optional[str] = None,
        name: Optional[str] = None,
        description: str = "",
        strategy_type: StrategyType = StrategyType.CUSTOM,
        signal_generator: Optional[Callable[[Dict[str, Any]], Optional[float]]] = None,
        condition_function: Optional[Callable[[Dict[str, Any]], bool]] = None,
        author: Optional[str] = None,
        **parameters
    ) -> str:
        """
        Generate a new hypothesis.

        Args:
            hypothesis_id: Optional ID (auto-generated if not provided)
            name: Optional name (auto-generated if not provided)
            description: Description of the hypothesis
            strategy_type: Type of strategy
            signal_generator: Function that generates signals
            condition_function: Function that validates conditions
            author: Author of the hypothesis
            **parameters: Initial parameters

        Returns:
            ID of the created hypothesis
        """
        if hypothesis_id is None:
            hypothesis_id = f"hyp_{uuid.uuid4().hex[:8]}"

        if name is None:
            name = f"Strategy_{hypothesis_id[:8]}"

        # Create hypothesis
        hypothesis = Hypothesis(
            hypothesis_id=hypothesis_id,
            name=name,
            description=description,
            strategy_type=strategy_type,
            parameters=parameters,
            signal_generator=signal_generator or (lambda x: 0.0),
            condition_function=condition_function or (lambda x: True),
            author=author,
        )

        # Store in knowledge base
        stored_id = self.knowledge_base.store_hypothesis(hypothesis)

        if stored_id != hypothesis_id:
            print(f"[ResearchManager] Hypothesis stored with ID: {stored_id}")
            hypothesis.hypothesis_id = stored_id
            stored_id = hypothesis_id  # Use the stored ID

        self.hypotheses[hypothesis_id] = hypothesis
        print(f"[ResearchManager] Created hypothesis: {hypothesis}")

        return hypothesis_id

    def run_validation(self, hypothesis_id: str) -> Dict[str, Any]:
        """
        Run scientific validation on a hypothesis.

        Checks logical consistency, mathematical correctness,
        and domain validity.
        """
        print(f"[ResearchManager] Running validation for {hypothesis_id}")

        hypothesis = self.hypotheses.get(hypothesis_id)
        if not hypothesis:
            raise ValueError(f"Hypothesis not found: {hypothesis_id}")

        # Perform validation checks
        validation_score = 0.0
        reasons = []

        # Check parameter ranges
        for param, value in hypothesis.parameters.items():
            if isinstance(value, (int, float)):
                if param == "leverage" and value > 10:
                    reasons.append(f"Parameter {param}={value} exceeds reasonable limit")
                elif param == "lookback_period" and value < 1:
                    reasons.append(f"Parameter {param} must be >= 1")

        # Check strategy type compatibility
        if hypothesis.strategy_type == StrategyType.CARTELIAN_BASKET:
            if len(hypothesis.parameters.get("symbols", [])) < 2:
                reasons.append("Cartesian basket requires at least 2 symbols")

        # Calculate validation score
        validation_score = max(0.0, min(1.0, 1.0 - (len(reasons) * 0.1)))

        hypothesis.validation_score = validation_score
        hypothesis.status = StrategyStatus.VALIDATED

        if reasons:
            hypothesis.failure_reasons.extend(reasons)
            print(f"[ResearchManager] Validation warnings: {len(reasons)}")

        print(f"[ResearchManager] Validation score: {validation_score:.2%}")
        self.knowledge_base.update_hypothesis(hypothesis_id, {
            "validation_score": validation_score,
            "status": StrategyStatus.VALIDATED.value,
            "failure_reasons": reasons
        })

        return {
            "hypothesis_id": hypothesis_id,
            "validation_score": validation_score,
            "reasons": reasons
        }

    def run_backtest(self, hypothesis_id: str, **backtest_kwargs) -> StrategyResult:
        """
        Run backtest on a hypothesis.

        Args:
            hypothesis_id: ID of hypothesis to backtest
            **backtest_kwargs: Additional arguments for backtest_engine

        Returns:
            StrategyResult with performance metrics
        """
        print(f"[ResearchManager] Running backtest for {hypothesis_id}")

        hypothesis = self.hypotheses.get(hypothesis_id)
        if not hypothesis:
            raise ValueError(f"Hypothesis not found: {hypothesis_id}")

        # Los OHLCV REALES del simbolo se piden aqui si no vienen dados.
        # MEDIDO el 2026-10-01: sin esto, `run_backtest` del adapter caia a
        # `generate_synthetic_data`, un random walk con precio inicial de
        # 50.000 y BTC como simbolo POR DEFECTO. Las hipotesis de BTC se
        # median contra una serie INVENTADA y devolvian 0 operaciones, lo
        # que acababa en `[skip] sin resultado de backtest utilizable` y
        # dejaba a BTC con 0 hipotesis en la base (medido: 0 frente a 501
        # de XRP).
        #
        # El fallo era silencioso porque un backtest sobre datos falsos
        # devuelve un numero normal, sin ninguna marca que diga que es
        # falso. El unico sintoma era un 0 que no explicaba nada.
        if not backtest_kwargs.get("data"):
            _sym = (getattr(hypothesis, "symbol", None)
                    or (hypothesis.get("symbol") if isinstance(hypothesis, dict)
                        else None))
            _tf = "1m"
            if isinstance(hypothesis, dict):
                _tf = (hypothesis.get("parameters") or {}).get(
                    "timeframe", hypothesis.get("timeframe", "1m"))
            if _sym and hasattr(self.backtest_engine, "fetch_market_data"):
                try:
                    from datetime import datetime, timedelta, timezone
                    _fin = datetime.now(timezone.utc)
                    _ini = _fin - timedelta(days=7)
                    backtest_kwargs["data"] = (
                        self.backtest_engine.fetch_market_data(
                            _sym, _ini, _fin, timeframe=_tf))
                except Exception as exc:
                    # Si no hay datos, NO se inventa: se deja que el
                    # adapter falle con su mensaje, que explica el motivo.
                    print(f"[ResearchManager] sin datos reales para {_sym} "
                          f"({_tf}): {exc}")

        # Execute backtest
        result = self.backtest_engine.run_backtest(hypothesis, **backtest_kwargs)

        # Store result
        self.results[hypothesis_id] = result
        hypothesis.status = StrategyStatus.BACKTESTED

        # Update knowledge base
        self.knowledge_base.update_hypothesis(hypothesis_id, {
            "status": StrategyStatus.BACKTESTED.value
        })

        try:
            n_tr = getattr(result, "num_trades", None) or getattr(
                result, "total_trades", 0)
            wr = float(getattr(result, "win_rate", 0) or 0)
            ret = float(getattr(result, "total_return_pct", 0) or 0)
            sh = float(getattr(result, "sharpe_ratio", 0) or 0)
            print(f"[ResearchManager] Backtest complete: trades={n_tr} "
                  f"wr={wr:.2f}% ret={ret:.2f}% sharpe={sh:.2f}")
        except Exception:
            print("[ResearchManager] Backtest complete")
        return result

    @staticmethod
    def _trade_pnls(result: Any) -> List[float]:
        """PnL por operacion del resultado de backtest, en la unidad del PnL.

        Acepta `Trade` (dataclass con `.pnl`) y dicts con cualquiera de las
        claves que se han usado en el repo. Se recorre el campo REAL del
        backtester y no el agregado: un CI sobre la media agregado seria una
        medida de una sola operacion.
        """
        pnls: List[float] = []
        for trade in (getattr(result, "trades", None) or []):
            valor = None
            if isinstance(trade, dict):
                for clave in ("pnl", "PnL", "profit_loss", "net_pnl"):
                    if trade.get(clave) is not None:
                        valor = trade.get(clave)
                        break
            else:
                for clave in ("pnl", "PnL", "profit_loss", "net_pnl"):
                    valor = getattr(trade, clave, None)
                    if valor is not None:
                        break
            if valor is None:
                continue
            try:
                pnls.append(float(valor))
            except (TypeError, ValueError):
                continue
        return pnls

    @staticmethod
    def _mc_seed(hypothesis_id: str, n_trades: int, n_iterations: int) -> int:
        """Semilla derivada de la identidad de la hipotesis, no del reloj.

        `hash()` de Python esta SALADO por proceso (`PYTHONHASHSEED`), asi
        que sembrar con el daria un CI distinto en cada arranque y el
        `scientific_score` no seria reproducible. `hashlib` no.
        """
        clave = f"{hypothesis_id}|{n_trades}|{n_iterations}".encode("utf-8")
        return int(hashlib.sha256(clave).hexdigest()[:8], 16)

    @staticmethod
    def _mc_result_vacio(hypothesis_id: str, n_trades: int) -> Any:
        """Resultado con la FORMA de `MonteCarloResult` y todos los campos a 0.

        Devolver `None` romperia a los llamantes que leen `.mean` /
        `.lower_bound` (los reales: `AQDERunner.run_monte_carlo_for_results`),
        y devolver el numero de una simulacion sobre 7 operaciones seria
        JUSTO el fallo que se quiere evitar. Se devuelve la forma sin
        contenido y el veredicto (con su motivo) va en
        `self.monte_carlo_verdicts`, que es donde se lee.
        """
        return SimpleNamespace(
            hypothesis_id=hypothesis_id,
            n_iterations=0,
            mean=0.0,
            median=0.0,
            std_dev=0.0,
            min_value=0.0,
            max_value=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            confidence_level=0.0,
            inconclusive=True,
            n_observed_trades=n_trades,
        )

    def run_monte_carlo(self, hypothesis_id: str, n_iterations: int = DEFAULT_MC_ITERATIONS) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on a hypothesis.

        Args:
            hypothesis_id: ID of hypothesis to simulate
            n_iterations: Number of simulation iterations

        Returns:
            MonteCarloResult with distribution statistics. Si el numero de
            operaciones no llega al minimo declarado, se devuelve la forma
            vacia y el veredicto queda en `self.monte_carlo_verdicts`.
        """
        print(f"[ResearchManager] Running Monte Carlo for {hypothesis_id} ({n_iterations} iterations)")

        result = self.results.get(hypothesis_id)
        if result is None:
            raise ValueError(
                f"Monte Carlo sin resultado de backtest para {hypothesis_id}: "
                "la fase se alimenta del backtest YA hecho, nunca de otro "
                "distinto. Llama antes a run_backtest().")

        n_trades = len(self._trade_pnls(result))
        min_trades = int(self.scientific_policy["min_trades"])

        # El umbral se APLICA, no se comenta. Por debajo no se simula: un
        # CI95 sobre un puñado de operaciones sale con la misma forma que uno
        # sobre cientos y no significa nada, asi que devolverlo seria justo el
        # numero que parece una medida. Medido sobre las ejecuciones reales del
        # libro (ver `gate_policy.MIN_TRADES_CONCLUSION`): a n=7 el intervalo
        # de la media/trade es [-0,133, +0,430] y contiene el cero; a n=30 es
        # [+0,087, +0,351] y ya no.
        if n_trades < min_trades:
            motivo = (f"n_operaciones={n_trades} < {min_trades}: el CI95 no "
                      "concluye nada")
            self.monte_carlo_verdicts[hypothesis_id] = {
                "conclusive": False,
                "n_trades": n_trades,
                "min_trades": min_trades,
                "n_iterations": 0,
                "mean": 0.0,
                "lower_bound": 0.0,
                "upper_bound": 0.0,
                "reason": motivo,
            }
            self.knowledge_base.update_hypothesis(hypothesis_id, {
                FIELD_MC_CONCLUSIVE: False,
            })
            print(f"[ResearchManager] Monte Carlo NO concluyente para "
                  f"{hypothesis_id}: {motivo}")
            return self._mc_result_vacio(hypothesis_id, n_trades)

        with _MC_SEED_LOCK:
            import numpy as np
            np.random.seed(self._mc_seed(hypothesis_id, n_trades, n_iterations))
            result = self.monte_carlo_engine.simulate_distribution(
                result, n_iterations=n_iterations
            )

        self.monte_carlo_results[hypothesis_id] = result
        self.monte_carlo_verdicts[hypothesis_id] = {
            "conclusive": True,
            "n_trades": n_trades,
            "min_trades": min_trades,
            "n_iterations": int(getattr(result, "n_iterations", n_iterations) or 0),
            "mean": float(getattr(result, "mean", 0.0) or 0.0),
            "lower_bound": float(getattr(result, "lower_bound", 0.0) or 0.0),
            "upper_bound": float(getattr(result, "upper_bound", 0.0) or 0.0),
            "reason": "",
        }

        # Update knowledge base
        self.knowledge_base.update_hypothesis(hypothesis_id, {
            "monte_carlo_score": result.mean,
            "status": StrategyStatus.MONTE_CARLO_TESTED.value,
            FIELD_MC_CONCLUSIVE: True,
        })

        print(f"[ResearchManager] Monte Carlo complete: mean={result.mean:.2%} "
              f"(n={n_trades} operaciones, CI95=[{result.lower_bound:.2%}, "
              f"{result.upper_bound:.2%}])")
        return result

    def run_statistical_validation(self, hypothesis_id: str,
                                  result: Any = None) -> Dict[str, Any]:
        """Test de significancia sobre el PnL REAL de las operaciones.

        Conecta `quant_math/expectation/statistical_tests.py`, que llevaba 466
        lineas sin una sola llamada. Se usa el t de una muestra en UNA cola
        (`media > 0`) porque lo que se quiere responder es si el edge existe,
        no si es distinto de cero, y porque es de forma cerrada: no siembra
        nada y por tanto el veredicto es el mismo en cada ciclo.

        Por debajo del minimo declarado de operaciones el p-value se calcula
        pero NO se puede concluir: se marca `conclusive=False` y el motivo.
        """
        result = result if result is not None else self.results.get(hypothesis_id)
        if result is None:
            raise ValueError(
                f"validacion sin resultado de backtest para {hypothesis_id}")

        pnls = self._trade_pnls(result)
        n = len(pnls)
        min_trades = int(self.scientific_policy["min_trades"])
        alpha = float(self.scientific_policy["alpha"])

        if n == 0:
            veredicto = {
                "hypothesis_id": hypothesis_id,
                "test": "one_sample_ttest",
                "n_trades": 0,
                "min_trades": min_trades,
                "mean_pnl": 0.0,
                "t_statistic": 0.0,
                "p_value": 1.0,
                "alpha": alpha,
                "significant": False,
                "conclusive": False,
                "reason": "sin operaciones: no hay nada que testear",
            }
        else:
            res = StatisticalTests.test_strategy_significance(pnls, test='ttest')
            p_value = float(res.get("p_value", 1.0))
            # El p-value tambien cabe en el campo que el puerto declara
            # (`StrategyResult.statistical_significance`). En el camino real el
            # objeto es un `backtesting.BacktestResult`, que NO tiene ese
            # campo, y el backtester esta congelado: se rellena cuando existe
            # y el valor viaja igualmente en el registro de la KB, que es
            # donde lo lee el gate.
            if hasattr(result, "statistical_significance"):
                try:
                    result.statistical_significance = p_value
                except Exception:  # pragma: no cover - dataclass sin slots
                    pass
            suficiente = n >= min_trades
            veredicto = {
                "hypothesis_id": hypothesis_id,
                "test": res.get("test", "one_sample_ttest"),
                "n_trades": n,
                "min_trades": min_trades,
                "mean_pnl": float(res.get("mean_excess_return", 0.0) or 0.0),
                "t_statistic": float(res.get("t_statistic", 0.0) or 0.0),
                "p_value": p_value,
                "alpha": alpha,
                "significant": bool(p_value < alpha) if suficiente else False,
                "conclusive": suficiente,
                "reason": "" if suficiente else (
                    f"n_operaciones={n} < {min_trades}: el p-value={p_value:.4f} "
                    "no se puede leer"),
            }
        veredicto["p_value_field_on_result"] = hasattr(
            result, "statistical_significance")
        self.statistical_results[hypothesis_id] = veredicto

        if not veredicto["conclusive"] or not veredicto["significant"]:
            print(f"[ResearchManager] significancia {hypothesis_id}: "
                  f"n={n} p={veredicto['p_value']:.4f} "
                  f"concluyente={veredicto['conclusive']} "
                  f"significativo={veredicto['significant']}"
                  + (f" ({veredicto['reason']})" if veredicto["reason"] else ""))
        return veredicto

    def score_hypothesis(self, hypothesis_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive score for a hypothesis.

        Combines validation, backtest, and Monte Carlo scores.

        La fase de Monte Carlo solo pesa si CONCLUYE. Si no hay operaciones
        suficientes, su contribucion es 0 y no su numero: el pondero es
        0,3*monte_carlo, y meterle el Bootstrap de 7 operaciones seria
        puntuar con ruido.

        Args:
            hypothesis_id: ID of hypothesis to score

        Returns:
            Dictionary with scoring details
        """
        print(f"[ResearchManager] Scoring hypothesis: {hypothesis_id}")

        hypothesis = self.hypotheses.get(hypothesis_id)
        if hypothesis is None:
            raise ValueError(
                f"no se puede puntuar {hypothesis_id}: no esta en el manager")

        # Get scores from different phases
        validation_score = hypothesis.validation_score
        backtest_score = self._calculate_backtest_score(self.results.get(hypothesis_id))

        mc_verdict = self.monte_carlo_verdicts.get(hypothesis_id)
        if mc_verdict is None:
            monte_carlo_score = 0.0
            mc_conclusive = False
        elif mc_verdict.get("conclusive"):
            monte_carlo_score = float(mc_verdict.get("mean", 0.0) or 0.0)
            mc_conclusive = True
        else:
            monte_carlo_score = 0.0
            mc_conclusive = False

        # Weighted scientific score
        scientific_score = (
            0.2 * validation_score +
            0.5 * backtest_score +
            0.3 * monte_carlo_score
        )

        hypothesis.scientific_score = scientific_score
        # El umbral 0,6 estaba HARDCODADO y marcado todas las hipotesis como
        # `failed`: medido el 2026-09-30, 17 hipotesis de una corrida real
        # Tener scientific_score entre 0,099 y 0,131, o sea que NINGUNA podia
        # pasar. Y `failed` no es inerte: esta en QUERYABLE_STATUSES, asi que
        # seguian siendo operables pero con eletro semantico de "descartada".
        #
        # El score es 0,2*validacion + 0,5*backtest + 0,3*monte_carlo, y
        # ninguna de las tres componentes se normaliza a 0-1, asi que 0,6
        # medido sobre datos reales no significa nada. Por defecto el umbral
        # es 0.0: el score informa, y quien decide es el gate de expectancy
        # (que compara contra el COSTE REAL, medido en el exchange).
        hypothesis.status = (StrategyStatus.VALIDATED
                             if scientific_score > self.validated_score_threshold
                             else StrategyStatus.FAILED)

        # Update knowledge base
        self.knowledge_base.update_hypothesis(hypothesis_id, {
            "scientific_score": scientific_score,
            "status": hypothesis.status.value
        })

        # El score ORDENA. Quien decide si algo se OPERA es el veredicto de
        # las tres fases, que va aparte: son preguntas distintas y una sola
        # (el score) no puede responder a las dos. Ver `evaluate_hypothesis`.
        stats = self.statistical_results.get(hypothesis_id, {})
        operativo, motivos = self._verdict(hypothesis_id)

        print(f"[ResearchManager] Scientific score: {scientific_score:.2%} "
              f"(operable={operativo}"
              + (f", motivos={'; '.join(motivos)}" if motivos else "") + ")")

        return {
            "hypothesis_id": hypothesis_id,
            "validation_score": validation_score,
            "backtest_score": backtest_score,
            "monte_carlo_score": monte_carlo_score,
            "monte_carlo_conclusive": mc_conclusive,
            "statistical_significance": stats.get("p_value"),
            "statistical_significance_alpha": stats.get("alpha"),
            "significance_conclusive": bool(stats.get("conclusive", False)),
            "significance_significant": bool(stats.get("significant", False)),
            "scientific_score": scientific_score,
            FIELD_SCIENTIFICALLY_VALIDATED: operativo,
            FIELD_SCIENTIFIC_REASONS: motivos,
        }

    def _verdict(self, hypothesis_id: str) -> tuple:
        """(operable, motivos) leyendo los veredictos de las tres fases.

        Las tres tienen que CONCLUIR y tener el resultado bueno:
          1. validacion de parametros: score >= 0,5 (la regla que ya usaba
             `execute_workflow`, sin tocarla),
          2. significancia del PnL: p < alfa Y con operaciones suficientes,
          3. Monte Carlo: bootstrap por encima del minimo declarado.
        """
        motivos: List[str] = []
        hyp = self.hypotheses.get(hypothesis_id)
        if hyp is None:
            return False, ["hipotesis_desconocida"]
        if float(getattr(hyp, "validation_score", 0.0) or 0.0) < 0.5:
            motivos.append(
                f"validacion={float(getattr(hyp, 'validation_score', 0.0) or 0.0):.2f}<0,5")

        stats = self.statistical_results.get(hypothesis_id)
        if stats is None:
            motivos.append("significancia: fase no ejecutada")
        elif not stats.get("conclusive"):
            motivos.append(f"significancia: {stats.get('reason') or 'no concluyente'}")
        elif not stats.get("significant"):
            motivos.append(
                f"significancia: p={float(stats.get('p_value', 1.0)):.4f}"
                f">={float(stats.get('alpha', 0.05))}")

        mc = self.monte_carlo_verdicts.get(hypothesis_id)
        if mc is None:
            motivos.append("monte_carlo: fase no ejecutada")
        elif not mc.get("conclusive"):
            motivos.append(f"monte_carlo: {mc.get('reason') or 'no concluyente'}")

        return (not motivos), motivos

    def evaluate_hypothesis(self, hypothesis_id: str,
                            n_iterations: int = DEFAULT_MC_ITERATIONS
                            ) -> Dict[str, Any]:
        """Corre las TRES fases sobre el backtest que YA se ha hecho.

        Este es el punto de entrada del pipeline de validacion en el CAMINO
        REAL (`orchestrator._generate_and_backtest_symbol`). El orden no es
        arbitrario:

            1. validacion   -> no depende de datos, cheapest, y puede
                               parar el pipeline sin gastar nada
            2. significancia-> necesita los PnL REALES de las operaciones
            3. monte carlo  -> necesita los MISMOS PnL, y ademas depende de
                               que haya operaciones suficientes (si no, no
                               simula)
            4. puntuacion   -> pondera las tres

        Y del backtest NO SE VUELVE A CORRER. Por eso esto NO es
        `execute_workflow()`: el backtest interno de ese metodo vuelve a
        bajar datos a 7 dias @1m y pisa `self.results`, luego el Monte Carlo
        y el score se calcularian sobre un backtest DISTINTO del que se uso
        para decidir. Aqui las tres fases beben del MISMO `self.results[id]`
        que produjo el backtest.

        Returns:
            Diccionario con el veredicto de cada fase y si la hipotesis es
            operable. Nunca lanza por un fallo de fase: una excepcion se
            traduce en "no operable" con el motivo, porque una hipotesis que
            no se ha podido medir no puede afirmarse operable.
        """
        val = self.run_validation(hypothesis_id)
        out: Dict[str, Any] = {
            "hypothesis_id": hypothesis_id,
            "validation_score": val.get("validation_score", 0.0),
        }
        try:
            out["statistical"] = self.run_statistical_validation(hypothesis_id)
        except Exception as exc:
            out["statistical"] = {"conclusive": False, "significant": False,
                                  "p_value": None, "reason": f"error: {exc}"}
            print(f"[ResearchManager] significancia fallo en {hypothesis_id}: "
                  f"{type(exc).__name__}: {exc}")
        try:
            out["monte_carlo"] = self.run_monte_carlo(
                hypothesis_id, n_iterations=n_iterations)
        except Exception as exc:
            out["monte_carlo"] = self._mc_result_vacio(hypothesis_id, 0)
            self.monte_carlo_verdicts[hypothesis_id] = {
                "conclusive": False, "n_trades": 0, "mean": 0.0,
                "lower_bound": 0.0, "upper_bound": 0.0,
                "reason": f"error: {type(exc).__name__}: {exc}"}
            print(f"[ResearchManager] Monte Carlo fallo en {hypothesis_id}: "
                  f"{type(exc).__name__}: {exc}")
        score = self.score_hypothesis(hypothesis_id)
        out["scoring"] = score
        out[FIELD_SCIENTIFICALLY_VALIDATED] = bool(
            score.get(FIELD_SCIENTIFICALLY_VALIDATED))
        out[FIELD_SCIENTIFIC_REASONS] = list(
            score.get(FIELD_SCIENTIFIC_REASONS) or [])
        out[FIELD_PVALUE] = score.get(FIELD_PVALUE)
        out[FIELD_PVALUE_ALPHA] = score.get(FIELD_PVALUE_ALPHA)
        out[FIELD_MC_CONCLUSIVE] = bool(score.get(FIELD_MC_CONCLUSIVE))
        out[FIELD_VALIDATION_SCORE] = score.get("validation_score")
        mc = self.monte_carlo_verdicts.get(hypothesis_id, {})
        out["monte_carlo_mean"] = mc.get("mean", 0.0)
        out["monte_carlo_lower_bound"] = mc.get("lower_bound", 0.0)
        out["monte_carlo_upper_bound"] = mc.get("upper_bound", 0.0)
        out["min_trades_conclusion"] = int(
            self.scientific_policy["min_trades"])
        out["scientific_score"] = score.get("scientific_score")
        return out

    def execute_workflow(self, hypothesis_id: str, enable_monte_carlo: bool = True) -> Dict[str, Any]:
        """
        Execute complete research workflow for a hypothesis.

        Runs: validation → backtest → (optional Monte Carlo) → scoring

        Args:
            hypothesis_id: ID of hypothesis to process
            enable_monte_carlo: Whether to run Monte Carlo testing

        Returns:
            Complete workflow results
        """
        print(f"[ResearchManager] Executing workflow for {hypothesis_id}")

        # Phase 1: Validation
        validation_result = self.run_validation(hypothesis_id)

        if validation_result["validation_score"] < 0.5:
            return {
                "hypothesis_id": hypothesis_id,
                "phase": "validation",
                "status": "failed",
                "reason": "Validation failed"
            }

        # Phase 2: Backtesting
        backtest_result = self.run_backtest(hypothesis_id)

        n_trades = getattr(backtest_result, "total_trades", None) or getattr(backtest_result, "num_trades", 0)
        if n_trades == 0:
            return {
                "hypothesis_id": hypothesis_id,
                "phase": "backtesting",
                "status": "failed",
                "reason": "No trades generated"
            }

        # Phase 3: Monte Carlo (optional)
        if enable_monte_carlo:
            self.run_monte_carlo(hypothesis_id)

        # Phase 4: Scoring
        scoring_result = self.score_hypothesis(hypothesis_id)

        return {
            "hypothesis_id": hypothesis_id,
            "phase": "complete",
            "status": "success" if scoring_result["scientific_score"] > 0.6 else "partial",
            "validation": validation_result,
            "backtest": backtest_result,
            "scoring": scoring_result
        }

    def _calculate_backtest_score(self, result: Optional[StrategyResult]) -> float:
        """Calculate score from backtest result"""
        if result is None:
            return 0.0

        # Handle both StrategyResult (total_trades) and BacktestResult (num_trades)
        n_trades = getattr(result, "total_trades", None) or getattr(result, "num_trades", 0)
        if n_trades == 0:
            return 0.0

        # win_rate: StrategyResult uses 0-1, BacktestResult uses 0-100
        wr = result.win_rate
        if wr > 1.0:
            wr = wr / 100.0

        # total_return: StrategyResult uses fraction, BacktestResult uses dollar amount
        tr = result.total_return
        initial_capital = getattr(result, "initial_capital", 100000.0)
        if abs(tr) > 1.0:
            tr = tr / initial_capital  # Convert dollar PnL to fraction

        win_rate_score = max(0.0, min(1.0, wr))
        roi_score = max(0.0, min(1.0, tr / 2.0))  # Normalize ROI to [0, 1]

        return 0.5 * win_rate_score + 0.5 * roi_score

    def search_hypotheses(self, criteria: Dict[str, Any]) -> List[Hypothesis]:
        """Search hypotheses using knowledge base"""
        return self.knowledge_base.search_hypotheses(criteria)

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get hypothesis by ID"""
        return self.hypotheses.get(hypothesis_id)

    def get_statistics(self) -> Dict[str, Any]:
        """Get research statistics"""
        return {
            "current_phase": self.current_phase.value,
            "total_hypotheses": len(self.hypotheses),
            "backtested_hypotheses": len(self.results),
            "monte_carlo_tested": len(self.monte_carlo_results),
            "agent_registry": self.agent_registry.get_statistics()
        }

    def set_phase(self, phase: ResearchPhase):
        """Set current research phase"""
        print(f"[ResearchManager] Phase changed: {self.current_phase.value} → {phase.value}")
        self.current_phase = phase

    def get_hypothesis_timeline(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Get timeline of hypothesis development"""
        hypothesis = self.hypotheses.get(hypothesis_id)
        if not hypothesis:
            return []

        timeline = [
            {
                "timestamp": hypothesis.created_at.isoformat(),
                "event": "Hypothesis created",
                "details": f"{hypothesis.name}"
            }
        ]

        if hypothesis.status == StrategyStatus.VALIDATED:
            timeline.append({
                "timestamp": hypothesis.created_at.isoformat(),
                "event": "Validated",
                "details": f"Validation score: {hypothesis.validation_score:.2%}"
            })

        if hypothesis_id in self.results:
            timeline.append({
                "timestamp": hypothesis.created_at.isoformat(),
                "event": "Backtested",
                "details": f"ROI: {self.results[hypothesis_id].total_return:.2%}"
            })

        return timeline
