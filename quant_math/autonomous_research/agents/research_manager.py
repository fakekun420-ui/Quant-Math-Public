"""
Research Manager - Main Orchestrator for AQDE.

The Research Manager coordinates all research activities across the
autonomous discovery pipeline. It manages the research workflow,
deploys agents for specific tasks, and tracks hypothesis lifecycle.
"""

import uuid
from datetime import datetime
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
from .agent_registry import AgentRegistry


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
        agent_registry: "AgentRegistry" = None
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

        # Research state
        self.current_phase = ResearchPhase.HYPOTHESIS_GENERATION
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.results: Dict[str, StrategyResult] = {}
        self.monte_carlo_results: Dict[str, MonteCarloResult] = {}
        self.experiments: List[Dict[str, Any]] = []

        print(f"[ResearchManager] Initialized with knowledge_base, backtest_engine, "
              f"monte_carlo_engine, statistical_validator, risk_manager")

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

        # Execute backtest
        result = self.backtest_engine.run_backtest(hypothesis, **backtest_kwargs)

        # Store result
        self.results[hypothesis_id] = result
        hypothesis.status = StrategyStatus.BACKTESTED

        # Update knowledge base
        self.knowledge_base.update_hypothesis(hypothesis_id, {
            "status": StrategyStatus.BACKTESTED.value
        })

        print(f"[ResearchManager] Backtest complete: {result}")
        return result

    def run_monte_carlo(self, hypothesis_id: str, n_iterations: int = 1000) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on a hypothesis.

        Args:
            hypothesis_id: ID of hypothesis to simulate
            n_iterations: Number of simulation iterations

        Returns:
            MonteCarloResult with distribution statistics
        """
        print(f"[ResearchManager] Running Monte Carlo for {hypothesis_id} ({n_iterations} iterations)")

        result = self.monte_carlo_engine.simulate_distribution(
            self.results[hypothesis_id],
            n_iterations=n_iterations
        )

        self.monte_carlo_results[hypothesis_id] = result

        # Update knowledge base
        self.knowledge_base.update_hypothesis(hypothesis_id, {
            "monte_carlo_score": result.mean,
            "status": StrategyStatus.MONTE_CARLO_TESTED.value
        })

        print(f"[ResearchManager] Monte Carlo complete: mean={result.mean:.2%}")
        return result

    def score_hypothesis(self, hypothesis_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive score for a hypothesis.

        Combines validation, backtest, and Monte Carlo scores.

        Args:
            hypothesis_id: ID of hypothesis to score

        Returns:
            Dictionary with scoring details
        """
        print(f"[ResearchManager] Scoring hypothesis: {hypothesis_id}")

        hypothesis = self.hypotheses.get(hypothesis_id)

        # Get scores from different phases
        validation_score = hypothesis.validation_score
        backtest_score = self._calculate_backtest_score(self.results.get(hypothesis_id))
        monte_carlo_score = self.monte_carlo_results.get(hypothesis_id).mean if hypothesis_id in self.monte_carlo_results else 0.0

        # Weighted scientific score
        scientific_score = (
            0.2 * validation_score +
            0.5 * backtest_score +
            0.3 * monte_carlo_score
        )

        hypothesis.scientific_score = scientific_score
        hypothesis.status = StrategyStatus.VALIDATED if scientific_score > 0.6 else StrategyStatus.FAILED

        # Update knowledge base
        self.knowledge_base.update_hypothesis(hypothesis_id, {
            "scientific_score": scientific_score,
            "status": hypothesis.status.value
        })

        print(f"[ResearchManager] Scientific score: {scientific_score:.2%}")

        return {
            "hypothesis_id": hypothesis_id,
            "validation_score": validation_score,
            "backtest_score": backtest_score,
            "monte_carlo_score": monte_carlo_score,
            "scientific_score": scientific_score
        }

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
