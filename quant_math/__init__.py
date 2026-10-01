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

__version__ = "1.5.0"
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
)

# Monte Carlo Simulation
# RETIRADO el 2026-10-01: `monte_carlo.simulator` era duplicado de
# `adapter.simulate_distribution`, que es el que se usa. El duplicado
# devolvia PnL en USD donde el vivo devuelve fraccion de capital, y al
# compartir el pondero 0,3 del score habria mezclado dos unidades.
# Ver la nota completa en `quant_math/monte_carlo/__init__.py`.

# Optimization — legacy/research (ver legacy/optimization/). No re-export fantasma.
# Usar: from legacy.optimization import KellyCriterion, MeanVarianceOptimizer, AdaptiveSizer
# o el canónico: from quant_math.risk import KellyCriterion, PositionSizer

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

    # Monte Carlo

    # Autonomous Research
    "ResearchManager",
    "AgentRegistry",
]