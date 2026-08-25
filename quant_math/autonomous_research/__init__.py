"""
Autonomous Quant Discovery Engine (AQDE)

A modular system for autonomous hypothesis discovery and validation
within the quant-math framework.
"""

__version__ = "1.0.1"
__author__ = "AQDE Team"
__description__ = "Autonomous hypothesis discovery engine for quantitative trading"

# Core types and protocols
from quant_math.autonomous_research.interfaces import (
    StrategyType,
    SignalStrength,
    StrategyStatus,
    Hypothesis,
    StrategyResult,
    MonteCarloResult,
    AgentMessage,
    DataProvider,
    KnowledgeBase,
    StatisticalValidator,
    BacktestEngine,
    MonteCarloEngine,
    Auditor,
    RiskManager,
    Agent,
)

# Main orchestrator
from quant_math.autonomous_research.agents.research_manager import ResearchManager

# Agent registry
from quant_math.autonomous_research.agents.agent_registry import AgentRegistry

# Adapters
from quant_math.autonomous_research.adapters import (
    QuantMathAdapter,
    RiskManagementEngine,
    HypothesisKnowledgeBase,
)

__all__ = [
    # Core types
    "StrategyType",
    "SignalStrength",
    "StrategyStatus",
    "Hypothesis",
    "StrategyResult",
    "MonteCarloResult",
    "AgentMessage",

    # Core protocols
    "DataProvider",
    "KnowledgeBase",
    "StatisticalValidator",
    "BacktestEngine",
    "MonteCarloEngine",
    "Auditor",
    "RiskManager",
    "Agent",

    # Main orchestrator
    "ResearchManager",

    # Agent registry
    "AgentRegistry",

    # Adapters
    "QuantMathAdapter",
    "RiskManagementEngine",
    "HypothesisKnowledgeBase",
]