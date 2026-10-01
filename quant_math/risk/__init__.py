"""
Risk Management Module Exports
"""

from .sizing import KellyCriterion, kelly_fraction, PositionSizer
from .risk_manager import RiskManager, create_risk_manager
from .var import ValueAtRisk, ExpectedShortfall
# `StopLoss` y `PortfolioRisk`/`RiskBudget`/`StressTesting` se exportaban
# aqui y se retiraron con sus modulos el 2026-10-01. No eran placeholders:
# los modulos existian, se instanciaban y no se llamaban. El `except
# ImportError` que habia ya era una pista de que la cadena se estaba
# sosteniendo a mano; ahora no hace falta sostenerla.
from .circuit_breaker import DailyGuard, utc_today, utc_day_start_ts
from .roe_targets import (
    DEFAULT_MAINTENANCE_MARGIN_RATE,
    DEFAULT_SL_LIQUIDATION_SAFETY_FRAC,
    MODE_ROE_TARGETS,
    LeverageRiskError,
    RoePlan,
    build_and_validate,
    build_roe_plan,
    liquidation_price_distance,
    max_sl_price_distance,
    roe_to_price_distance,
    sl_is_reachable,
    tp_sl_prices,
    validate_roe_plan,
)

__all__ = [
    "KellyCriterion",
    "kelly_fraction",
    "RiskManager",
    "create_risk_manager",
    "PositionSizer",
    "ValueAtRisk",
    "ExpectedShortfall",
    "DailyGuard",
    "utc_today",
    "utc_day_start_ts",
    "MODE_ROE_TARGETS",
    "LeverageRiskError",
    "RoePlan",
    "build_roe_plan",
    "build_and_validate",
    "validate_roe_plan",
    "roe_to_price_distance",
    "liquidation_price_distance",
    "max_sl_price_distance",
    "sl_is_reachable",
    "tp_sl_prices",
    "DEFAULT_MAINTENANCE_MARGIN_RATE",
    "DEFAULT_SL_LIQUIDATION_SAFETY_FRAC",
]