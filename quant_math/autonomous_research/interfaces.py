"""
Core domain interfaces for AQDE.

This module defines the hexagonal architecture ports that separate the
Autonomous Quant Discovery Engine domain from implementation details.
Domain contracts are used by adapters to communicate with the domain core.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar, Union
from datetime import datetime
from enum import Enum

# Type alias for Strategy implementations
StrategyT = TypeVar("StrategyT")


class StrategyType(Enum):
    """Type of trading strategy"""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    CARTELIAN_BASKET = "cartesian_basket"
    VOLATILITY_TRADING = "volatility_trading"
    SENTIMENT_DRIVEN = "sentiment_driven"
    CUSTOM = "custom"


class SignalStrength(Enum):
    """Signal strength classification"""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class StrategyStatus(Enum):
    """Status of a hypothesis/strategy"""
    DRAFT = "draft"
    VALIDATED = "validated"
    BACKTESTED = "backtested"
    MONTE_CARLO_TESTED = "monte_carlo_tested"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"
    FAILED = "failed"


@dataclass
class Hypothesis:
    """
    Represents a discovered hypothesis about market behavior.

    A hypothesis is a mathematical model or strategy that generates a
    signal when market conditions meet specific criteria.
    """
    # Core identity
    hypothesis_id: str
    name: str
    description: str
    strategy_type: StrategyType
    parameters: Dict[str, Any]

    # Domain logic
    signal_generator: Callable[[Dict[str, Any]], Optional[float]]
    condition_function: Callable[[Dict[str, Any]], bool]

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)

    # Scientific evaluation
    validation_score: float = 0.0
    scientific_score: float = 0.0
    implementation_effort: str = "low"  # low, medium, high
    robustness_score: float = 0.0

    # Status
    status: StrategyStatus = StrategyStatus.DRAFT
    failure_reasons: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name} ({self.hypothesis_id})"

    def get_params(self) -> Dict[str, Any]:
        """Get current parameters"""
        return self.parameters.copy()


@dataclass
class StrategyResult:
    """
    Result of backtesting a hypothesis/strategy.

    Contains performance metrics and statistical validation results.
    """
    # Core identification
    hypothesis_id: str
    backtest_start: datetime
    backtest_end: datetime

    # Performance metrics
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    net_profit: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    total_return: float = 0.0

    # Statistical validation
    statistical_significance: float = 0.0  # p-value or similar
    confidence_interval: Optional[tuple] = None

    # Additional information
    initial_capital: float = 100000.0
    final_capital: float = 100000.0
    trades: List[Dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"StrategyResult({self.hypothesis_id}, ROI={self.total_return:.2%})"


@dataclass
class MonteCarloResult:
    """
    Result of Monte Carlo simulation.

    Provides statistical distribution of strategy performance metrics.
    """
    hypothesis_id: str
    n_iterations: int = 1000
    metric_name: str = "total_return"
    distribution: List[float] = field(default_factory=list)
    confidence_level: float = 0.95

    # Statistical summary
    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0

    # Confidence intervals
    lower_bound: float = 0.0
    upper_bound: float = 0.0

    def __str__(self) -> str:
        return f"MonteCarloResult({self.hypothesis_id}, mean={self.mean:.2%})"


@dataclass
class AgentMessage:
    """
    Communication message between agents.

    Supports both synchronous and asynchronous communication patterns.
    """
    message_id: str
    sender: str
    receiver: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)

    # Delivery metadata
    priority: str = "normal"  # low, normal, high
    callback: Optional[Callable[[AgentMessage], None]] = None
    references: List[str] = field(default_factory=list)  # Related messages or hypotheses

    def __str__(self) -> str:
        return f"Message({self.sender}→{self.receiver}: {str(self.content)[:50]}...)"


# Protocol interfaces (similar to ABC but allow duck typing)


class DataProvider(Protocol):
    """
    Port for data access in AQDE.

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

    def update_hypothesis(self, hypothesis_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing hypothesis"""
        ...

    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis"""
        ...

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored hypotheses"""
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

    def monte_carlo_simulation(self, hypothesis_id: str, trades: List[Dict[str, Any]],
                              n_iterations: int = 1000) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on strategy performance.

        Uses bootstrapping or parametric methods to estimate distribution.
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
