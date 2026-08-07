"""
Quant-Math Core Package

Shared domain types and protocols for the Quant-Math ecosystem.
"""

from .types import (
    StrategyType,
    SignalStrength,
    StrategyStatus,
    Hypothesis,
    StrategyResult,
    MonteCarloResult,
    Trade,
    AgentMessage,
    SearchCriteria,
)

from .protocols import (
    DataProvider,
    KnowledgeBase,
    StatisticalValidator,
    BacktestEngine,
    MonteCarloEngine,
    Auditor,
    RiskManager,
    Agent,
    AgentRegistry,
)

__all__ = [
    # Types
    "StrategyType",
    "SignalStrength",
    "StrategyStatus",
    "Hypothesis",
    "StrategyResult",
    "MonteCarloResult",
    "Trade",
    "AgentMessage",
    "SearchCriteria",
    # Protocols
    "DataProvider",
    "KnowledgeBase",
    "StatisticalValidator",
    "BacktestEngine",
    "MonteCarloEngine",
    "Auditor",
    "RiskManager",
    "Agent",
    "AgentRegistry",
]