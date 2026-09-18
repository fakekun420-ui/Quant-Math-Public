"""
Sizing Module — Kelly + PositionSizer consolidation.

Canónico para todo position sizing. Reemplaza:
- quant_math/risk/kelly.py        (KellyCriterion, kelly_fraction)
- quant_math/risk/position_sizing.py (PositionSizer)

Backward compat: ambos re-exportan desde aquí.
"""

import numpy as np
from typing import Optional, Dict, Any


class KellyCriterion:
    """Kelly criterion position sizing."""

    @staticmethod
    def calculate(win_rate: float, avg_win: float, avg_loss: float) -> float:
        kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        return max(0.0, kelly)

    @staticmethod
    def calculate_discrete(win_rate: float, avg_win: float, avg_loss: float) -> float:
        kelly = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
        return max(0.0, min(1.0, kelly))

    @staticmethod
    def calculate_growth_optimal(win_rate: float, avg_win: float, avg_loss: float,
                                 n_trades: int = 100) -> float:
        kelly = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
        return max(0.0, kelly - (1.0 / n_trades))


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float, fraction: float = 1.0) -> float:
    return KellyCriterion.calculate(win_rate, avg_win, avg_loss) * fraction


class PositionSizer:
    """Unified position sizing: fixed_fractional, kelly, volatility_target, atr_based."""

    def __init__(self, default_method: str = "fixed_fractional", default_risk_pct: float = 0.02):
        self.default_method = default_method
        self.default_risk_pct = default_risk_pct

    def calculate_size(self, account_value: float, entry_price: float, stop_price: float,
                       method: Optional[str] = None, risk_pct: Optional[float] = None,
                       **kwargs) -> Dict[str, Any]:
        method = method or self.default_method
        risk_pct = risk_pct or self.default_risk_pct
        if method == "fixed_fractional":
            return self._fixed_fractional(account_value, entry_price, stop_price, risk_pct)
        elif method == "kelly":
            return self._kelly_sizing(account_value, entry_price, stop_price, **kwargs)
        elif method == "volatility_target":
            return self._volatility_targeting(account_value, entry_price, stop_price, **kwargs)
        elif method == "atr_based":
            return self._atr_based(account_value, entry_price, stop_price, **kwargs)
        else:
            raise ValueError(f"Unknown sizing method: {method}")

    def _fixed_fractional(self, account_value: float, entry_price: float,
                          stop_price: float, risk_pct: float) -> Dict[str, Any]:
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return {"size": 0, "method": "fixed_fractional", "risk_per_share": 0}
        max_risk = account_value * risk_pct
        size = max_risk / risk_per_share
        return {"size": size, "method": "fixed_fractional", "risk_per_share": risk_per_share,
                "max_risk": max_risk, "risk_pct": risk_pct}

    def _kelly_sizing(self, account_value: float, entry_price: float, stop_price: float,
                      win_rate: float = 0.5, avg_win: float = 1.0, avg_loss: float = 1.0,
                      kelly_fraction: float = 0.5) -> Dict[str, Any]:
        kelly_full = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
        kelly_adjusted = kelly_full * kelly_fraction
        max_risk = account_value * kelly_adjusted
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return {"size": 0, "method": "kelly", "kelly_fraction": kelly_adjusted}
        size = max_risk / risk_per_share
        return {"size": size, "method": "kelly", "kelly_full": kelly_full,
                "kelly_adjusted": kelly_adjusted, "risk_per_share": risk_per_share, "max_risk": max_risk}

    def _volatility_targeting(self, account_value: float, entry_price: float, stop_price: float,
                              target_vol: float = 0.15, current_vol: float = 0.20) -> Dict[str, Any]:
        vol_ratio = target_vol / current_vol if current_vol > 0 else 1.0
        base_size = account_value * 0.1 * vol_ratio
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return {"size": 0, "method": "volatility_target"}
        max_risk = account_value * 0.02
        size_by_risk = max_risk / risk_per_share
        size = min(base_size / entry_price, size_by_risk)
        return {"size": size, "method": "volatility_target", "vol_ratio": vol_ratio,
                "base_size": base_size, "size_by_risk": size_by_risk}

    def _atr_based(self, account_value: float, entry_price: float, stop_price: float,
                   atr: float = None, atr_multiplier: float = 2.0,
                   risk_pct: float = 0.02) -> Dict[str, Any]:
        if atr is None:
            atr = abs(entry_price - stop_price)
        atr_stop = atr * atr_multiplier
        max_risk = account_value * risk_pct
        size = max_risk / atr_stop if atr_stop > 0 else 0
        return {"size": size, "method": "atr_based", "atr": atr, "atr_stop": atr_stop,
                "atr_multiplier": atr_multiplier, "max_risk": max_risk}

    @staticmethod
    def calculate(portfolio_value: float, risk_per_trade: float, stop_loss_distance: float) -> float:
        if stop_loss_distance == 0:
            return 0.0
        max_risk = portfolio_value * risk_per_trade
        return max_risk / stop_loss_distance
