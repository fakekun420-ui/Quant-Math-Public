"""
Risk Management Module

This module provides comprehensive risk measurement and management tools including:
- Value at Risk (VaR) calculations (parametric, historical, Monte Carlo)
- Expected Shortfall (ES) calculations
- Portfolio risk metrics (diversification, concentration)
- Risk budgeting and allocation
- Stress testing
- Tail risk measures
"""

from .risk_management import (
    ValueAtRisk, ExpectedShortfall, PortfolioRisk, RiskBudget, StressTesting
)

__version__ = "1.0.0"
__all__ = [
    'ValueAtRisk',
    'ExpectedShortfall',
    'PortfolioRisk',
    'RiskBudget',
    'StressTesting'
]
