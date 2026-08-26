"""
QUANT-MATH: Quantitative Trading Framework

A modular research framework for quantitative trading systems with core modules:
- Core Types & Protocols
- Expectation Calculation (Module 8)
- Risk Management (Module 9)
- Monte Carlo Simulation (Module 10)
- Position Sizing Optimization (Module 10+)
- Autonomous Research (AQDE)
"""

__version__ = "1.2.0"
__author__ = "QUANT-MATH Team"

# Core types and protocols
from quant_math.core.types import (
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

from quant_math.core.protocols import (
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

# Expectation Calculation (Module 8)
from quant_math.expectation import (
    ReturnCalculator,
    DrawdownAnalyzer,
    SharpeMetrics,
    StatisticalTests,
    one_sample_ttest,
    jarque_bera_test,
    bootstrap_p_value,
)

# Risk Management (Module 9)
from quant_math.risk import (
    KellyCriterion,
    kelly_fraction,
    RiskManager,
    create_risk_manager,
    ValueAtRisk,
    ExpectedShortfall,
    PositionSizer,
    StopLoss,
)

# Monte Carlo Simulation
from quant_math.monte_carlo import (
    MonteCarloSimulator,
    MonteCarloConfig,
    bootstrap_simulation,
    parametric_simulation,
    calculate_var_es,
)

# Optimization
from optimization import (
    KellyCriterion as OptKellyCriterion,
    MeanVarianceOptimizer,
    AdaptiveSizer,
)

# Autonomous Research (AQDE)
from quant_math.autonomous_research import (
    ResearchManager,
    AgentRegistry,
)

# Main public API
__all__ = [
    # Core types
    "StrategyType",
    "SignalStrength",
    "StrategyStatus",
    "Hypothesis",
    "StrategyResult",
    "MonteCarloResult",
    "Trade",
    "AgentMessage",
    "SearchCriteria",

    # Core protocols
    "DataProvider",
    "KnowledgeBase",
    "StatisticalValidator",
    "BacktestEngine",
    "MonteCarloEngine",
    "Auditor",
    "RiskManager",
    "Agent",
    "AgentRegistry",

    # Expectation (Module 8)
    "ReturnCalculator",
    "DrawdownAnalyzer",
    "SharpeMetrics",
    "StatisticalTests",
    "one_sample_ttest",
    "jarque_bera_test",
    "bootstrap_p_value",

    # Risk (Module 9)
    "KellyCriterion",
    "kelly_fraction",
    "RiskManager",
    "create_risk_manager",
    "ValueAtRisk",
    "ExpectedShortfall",
    "PositionSizer",
    "StopLoss",

    # Monte Carlo
    "MonteCarloSimulator",
    "MonteCarloConfig",
    "bootstrap_simulation",
    "parametric_simulation",
    "calculate_var_es",

    # Optimization
    "OptKellyCriterion",
    "MeanVarianceOptimizer",
    "AdaptiveSizer",

    # Autonomous Research
    "ResearchManager",
    "AgentRegistry",
]