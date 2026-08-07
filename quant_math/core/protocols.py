"""
Quant-Math Core Protocols

Hexagonal architecture ports that separate the domain from implementation details.
Domain contracts are used by adapters to communicate with the domain core.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar
from datetime import datetime

from .types import (
    Hypothesis,
    StrategyResult,
    MonteCarloResult,
    AgentMessage,
    StrategyType,
    SignalStrength,
    StrategyStatus,
    SearchCriteria,
    Trade,
)


# Type alias for Strategy implementations
StrategyT = TypeVar("StrategyT")


# Protocol interfaces (similar to ABC but allow duck typing)


class DataProvider(Protocol):
    """
    Port for data access in Quant-Math.

    Adapters implement this to provide market data, features, and
    other data sources to the discovery engine.
    """

    def fetch_market_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Fetch market data for a given symbol and date range.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            start_date: Start date for data
            end_date: End date for data

        Returns:
            Dictionary containing market data (OHLCV, features, etc.)
        """
        ...

    def fetch_features(self, symbol: str, date: datetime) -> Dict[str, Any]:
        """
        Extract features for a specific date/time.

        Features can include technical indicators, statistical features, etc.

        Args:
            symbol: Trading symbol
            date: Date/time to extract features

        Returns:
            Dictionary of feature names to values
        """
        ...

    def get_available_symbols(self) -> List[str]:
        """Get list of available trading symbols"""
        ...

    def get_data_quality(self, symbol: str) -> Dict[str, Any]:
        """
        Get data quality metrics for a symbol.

        Returns completeness, accuracy, and freshness metrics.
        """
        ...


class KnowledgeBase(Protocol):
    """
    Port for hypothesis knowledge management.

    Adapters implement this to store, retrieve, and search hypotheses.
    """

    def store_hypothesis(self, hypothesis: Hypothesis) -> str:
        """Store a hypothesis and return its ID"""
        ...

    def retrieve_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve a hypothesis by ID"""
        ...

    def search_hypotheses(self, criteria: Dict[str, Any]) -> List[Hypothesis]:
        """
        Search hypotheses based on criteria.

        Criteria can include:
        - strategy_type
        - tag
        - author
        - date_range
        - performance thresholds
        """
        ...

    def search_hypotheses_by_text(self, query: str, limit: int = 100) -> List[Hypothesis]:
        """Search hypotheses using text matching"""
        ...

    def search_similar_hypotheses(self, description: str, threshold: float = 0.7) -> List[Hypothesis]:
        """Find similar hypotheses using semantic search"""
        ...

    def update_hypothesis(self, hypothesis_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing hypothesis"""
        ...

    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis"""
        ...

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored hypotheses"""
        ...

    def get_hypothesis_timeline(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Get timeline of hypothesis development"""
        ...

    def export_hypotheses(self, output_path: str) -> Dict[str, Any]:
        """Export all hypotheses to a file"""
        ...

    def import_hypotheses(self, input_path: str) -> int:
        """Import hypotheses from a file"""
        ...


class StatisticalValidator(Protocol):
    """
    Port for statistical validation of hypotheses.

    Adapters implement this to provide statistical tests and validation
    methods for hypothesis evaluation.
    """

    def calculate_win_rate(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate win rate from trade history"""
        ...

    def test_significance(self, hypothesis_id: str, result: StrategyResult) -> float:
        """
        Test statistical significance of strategy performance.

        Returns p-value or similar measure of significance.
        """
        ...

    def calculate_sharpe_ratio(self, trades: List[Dict[str, Any]], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio"""
        ...

    def calculate_sortino_ratio(self, trades: List[Dict[str, Any]], risk_free_rate: float = 0.0) -> float:
        """Calculate Sortino ratio"""
        ...

    def calculate_calmar_ratio(self, result: StrategyResult) -> float:
        """Calculate Calmar ratio"""
        ...

    def bootstrap_significance(self, result: StrategyResult, n_iterations: int = 1000) -> float:
        """
        Use bootstrap resampling to estimate significance.

        Returns bootstrap p-value.
        """
        ...


class BacktestEngine(Protocol):
    """
    Port for backtesting hypotheses.

    Adapters implement this to execute backtests and generate results.
    """

    def run_backtest(self, hypothesis: Hypothesis, data: Dict[str, Any],
                    initial_capital: float = 100000.0) -> StrategyResult:
        """
        Run backtest on a hypothesis.

        Args:
            hypothesis: Hypothesis to test
            data: Market data for backtesting
            initial_capital: Starting capital

        Returns:
            StrategyResult with performance metrics
        """
        ...

    def get_trade_history(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Get trade history for a hypothesis"""
        ...

    def get_performance_metrics(self, hypothesis_id: str) -> Dict[str, Any]:
        """Get all performance metrics for a hypothesis"""
        ...

    def optimize_parameters(self, hypothesis: Hypothesis, data: Dict[str, Any],
                           parameter_ranges: Dict[str, List[Any]]) -> Dict[str, Any]:
        """
        Optimize hypothesis parameters over a search space.

        Returns the best parameters and their performance.
        """
        ...


class MonteCarloEngine(Protocol):
    """
    Port for Monte Carlo simulation.

    Adapters implement this to run Monte Carlo simulations for
    robustness testing and confidence estimation.
    """

    def simulate_distribution(self, result: StrategyResult, n_iterations: int = 1000) -> MonteCarloResult:
        """Run Monte Carlo simulation on strategy results"""
        ...

    def get_confidence_interval(self, metric: str, n_iterations: int = 1000) -> tuple:
        """Get confidence interval for a metric"""
        ...

    def test_robustness(self, hypothesis_id: str, n_iterations: int = 1000) -> Dict[str, Any]:
        """
        Test robustness across multiple simulated scenarios.

        Returns distribution statistics and any failure patterns.
        """
        ...

    def calculate_var(self, result: StrategyResult, confidence_level: float = 0.95,
                      n_iterations: int = 10000) -> Dict[str, float]:
        """Calculate Value at Risk"""
        ...

    def calculate_probability_of_loss(self, result: StrategyResult,
                                      n_iterations: int = 10000) -> float:
        """Calculate probability of loss"""
        ...


class Auditor(Protocol):
    """
    Port for audit and compliance.

    Adapters implement this to track experiments, validate methodology,
    and ensure reproducibility.
    """

    def log_experiment(self, experiment_name: str, details: Dict[str, Any]) -> str:
        """Log an experiment run with full details"""
        ...

    def get_experiment_history(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Get experiment history for a hypothesis"""
        ...

    def verify_reproducibility(self, experiment_id: str) -> bool:
        """Verify that an experiment can be reproduced"""
        ...

    def audit_backtest(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get audit trail for a backtest.

        Includes data versioning, parameter logs, execution context.
        """
        ...


class RiskManager(Protocol):
    """
    Port for risk management checks.

    Adapters implement this to ensure hypotheses meet risk criteria.
    """

    def check_position_size(self, hypothesis_id: str, size: float,
                           account_value: float) -> Dict[str, Any]:
        """
        Check if position size meets risk criteria.

        Returns OK or failure reasons.
        """
        ...

    def check_drawdown_limit(self, current_drawdown: float, limit: float) -> bool:
        """Check if drawdown is within acceptable limits"""
        ...

    def check_sharpe_threshold(self, sharpe_ratio: float, threshold: float) -> bool:
        """Check if Sharpe ratio meets threshold"""
        ...

    def check_sortino_threshold(self, sortino_ratio: float, threshold: float) -> bool:
        """Check if Sortino ratio meets threshold"""
        ...

    def check_calmar_threshold(self, calmar_ratio: float, threshold: float) -> bool:
        """Check if Calmar ratio meets threshold"""
        ...

    def calculate_risk_metrics(self, result: StrategyResult) -> Dict[str, float]:
        """Calculate comprehensive risk metrics"""
        ...

    def stress_test_strategy(self, result: StrategyResult,
                            stress_scenarios: List[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        """Perform stress testing on strategy"""
        ...


class Agent(Protocol):
    """
    Port for agent communication and coordination.

    Abstract base for specialized research agents.
    """

    def __init__(self, agent_id: str, name: str, capabilities: List[str]):
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific task"""
        ...

    def communicate(self, message: AgentMessage) -> AgentMessage:
        """Send/receive a message"""
        ...

    def get_capabilities(self) -> List[str]:
        """Get list of agent capabilities"""
        return self.capabilities.copy()

    def register_with_registry(self, registry: "AgentRegistry"):
        """Register this agent with the registry"""
        ...


class AgentRegistry(Protocol):
    """
    Port for agent registry and communication.
    """

    def register_agent(self, agent: Agent):
        """Register an agent"""
        ...

    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        ...

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        ...

    def broadcast(self, message: AgentMessage) -> List[AgentMessage]:
        """Broadcast message to all agents"""
        ...

    def send_message(self, message: AgentMessage) -> AgentMessage:
        """Send message to specific agent"""
        ...

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics"""
        ...