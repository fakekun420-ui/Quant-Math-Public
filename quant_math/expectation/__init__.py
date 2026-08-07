"""
Expectation Calculation Module (Module 8)

Statistical significance testing and performance metric calculation
for trading strategy validation.
"""

from quant_math.expectation.statistical_tests import (
    StatisticalTests,
    one_sample_ttest,
    jarque_bera_test,
    bootstrap_p_value,
)

from quant_math.expectation.return_calculator import ReturnCalculator
from quant_math.expectation.drawdown_analyzer import DrawdownAnalyzer
from quant_math.expectation.sharpe_metrics import SharpeMetrics

__all__ = [
    "StatisticalTests",
    "one_sample_ttest",
    "jarque_bera_test",
    "bootstrap_p_value",
    "ReturnCalculator",
    "DrawdownAnalyzer",
    "SharpeMetrics",
]