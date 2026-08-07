"""
Quant-Math Core Types

Shared domain types used across Quant-Math and AQDE modules.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


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

    # Domain logic (callable)
    signal_generator: Any = None  # Callable[[Dict[str, Any]], Optional[float]]
    condition_function: Any = None  # Callable[[Dict[str, Any]], bool]

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
class Trade:
    """Represents a single trade."""
    trade_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    hold_duration: float
    entry_time: float
    exit_time: float
    commission: float


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
    callback: Any = None  # Optional[Callable[[AgentMessage], None]]
    references: List[str] = field(default_factory=list)  # Related messages or hypotheses

    def __str__(self) -> str:
        return f"Message({self.sender}→{self.receiver}: {str(self.content)[:50]}...)"


@dataclass
class SearchCriteria:
    """Search criteria for hypothesis search"""
    strategy_type: Optional[str] = None
    status: Optional[str] = None
    min_win_rate: Optional[float] = None
    min_sharpe_ratio: Optional[float] = None