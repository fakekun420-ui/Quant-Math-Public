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

# `ReturnCalculator` y `DrawdownAnalyzer` se exportaban aqui y se retiraron
# con sus modulos el 2026-10-01. Ninguno se instanciaba fuera de si mismo.
# `ReturnCalculator` devolvia ademas un PnL con un factor de error medido de
# 6,67x (= la cantidad): `pnl/entry_price` daba 3,61% cuando el PnL real era
# 0,54%. Un modulo que devuelve el numero mal y al que nadie llama no se
# detecta nunca, y por eso es peor que no tenerlo.
from quant_math.expectation.sharpe_metrics import SharpeMetrics

__all__ = [
    "StatisticalTests",
    "one_sample_ttest",
    "jarque_bera_test",
    "bootstrap_p_value",
    "SharpeMetrics",
]