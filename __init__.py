"""
QUANT-MATH: Quantitative Trading Framework

A modular research framework for quantitative trading systems with 14 modules.

Implemented Modules:
- Module 8: Expectation Calculation (expectation/)
- Module 9: Risk Management (risk/)
- Module 10: Position Sizing Optimization (optimization/)
- Module 11: Execution Engine (execution/)
- Module 12: Order Management (order_management/)
- Module 13: Algorithmic Trading (algo_trading/)
- Module 14: Backtesting & Evaluation (backtesting/)

The quant_math/ package contains the newer refactored architecture
(core, expectation, risk, monte_carlo, autonomous_research/AQDE).
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "QUANT-MATH Team"
__all__ = [
    # Expectation Calculation (Module 8)
    'ReturnCalculator',
    'ExpectationCalculator',  # backwards-compat alias of ReturnCalculator
    'DrawdownAnalyzer',
    'SharpeMetrics',
    'StatisticalTests',

    # Risk Management (Module 9)
    'PositionSizer',
    'StopLoss',
    'ValueAtRisk',
    'ExpectedShortfall',

    # Position Sizing Optimization (Module 10)
    'KellyCriterion',
    'MeanVarianceOptimizer',
    'AdaptiveSizer',

    # Execution Engine (Module 11)
    'ExchangeManager',
    'OrderType',
    'Order',
    'OrderRouter',

    # Order Management (Module 12)
    'OrderManager',
    'OrderBook',
    'ExecutionReport',
    'SlippageModel',
    'ExecutionStrategy',
    'TransactionCostModel',

    # Algorithmic Trading (Module 13)
    'TWAP',
    'VWAP',
    'POV',
    'AlgoTradingSystem',
    'AlgoExecution',

    # Backtesting & Evaluation (Module 14)
    'Backtester',
    'PerformanceMetrics',
    'WalkForwardValidator',
    'WalkForwardResult',
    'BacktestResult',
    'Trade',
]

# Import aliases for backwards compatibility
from expectation import (
    ReturnCalculator,
    DrawdownAnalyzer,
    SharpeMetrics,
    StatisticalTests,
)
ExpectationCalculator = ReturnCalculator

from risk import PositionSizer, StopLoss, ValueAtRisk, ExpectedShortfall
from optimization import KellyCriterion, MeanVarianceOptimizer, AdaptiveSizer
from execution import ExchangeManager, OrderType, Order, OrderRouter
from order_management import (
    OrderManager,
    OrderBook,
    ExecutionReport,
    SlippageModel,
    ExecutionStrategy,
    TransactionCostModel,
)
from algo_trading import TWAP, VWAP, POV, AlgoTradingSystem, AlgoExecution
from backtesting import (
    Backtester,
    PerformanceMetrics,
    WalkForwardValidator,
    WalkForwardResult,
    BacktestResult,
    Trade,
)
