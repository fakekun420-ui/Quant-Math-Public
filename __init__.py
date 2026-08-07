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

Remaining Modules (1-7): Architecture defined but not yet implemented
"""

__version__ = "0.1.0"
__author__ = "QUANT-MATH Team"
__all__ = [
    # Expectation Calculation (Module 8)
    'ExpectationCalculator',
    'DrawdownAnalyzer',
    'SharpeMetrics',

    # Risk Management (Module 9)
    'PositionSizer',
    'StopLoss',
    'RiskManager',
    'ValueAtRisk',
    'ExpectedShortfall',

    # Position Sizing Optimization (Module 10)
    'KellyCriterion',
    'MeanVarianceOptimizer',
    'AdaptiveSizer',

    # Execution Engine (Module 11)
    'OrderExecutor',
    'OrderTypes',
    'OrderRouting',

    # Order Management (Module 12)
    'OrderManager',
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
    'BacktestResult',
    'Trade',
]

# Import aliases for backwards compatibility
from expectation import ExpectationCalculator, DrawdownAnalyzer, SharpeMetrics
from risk import PositionSizer, StopLoss, RiskManager, ValueAtRisk, ExpectedShortfall
from optimization import KellyCriterion, MeanVarianceOptimizer, AdaptiveSizer
from execution import OrderExecutor, OrderTypes, OrderRouting
from order_management import OrderManager, SlippageModel, ExecutionStrategy, TransactionCostModel
from algo_trading import TWAP, VWAP, POV, AlgoTradingSystem, AlgoExecution
from backtesting import Backtester, PerformanceMetrics, BacktestResult, Trade
