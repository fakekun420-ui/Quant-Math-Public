"""Filtro de Kalman escalar (modelo de nivel constante) en numpy puro.

Feature de mercado para el SIS: nivel suavizado + pendiente + relacion
ruido/innovacion. Sin dependencias externas (pykalman no requerido).
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np


def kalman_level(closes: List[float], q: float = 1e-4,
                 r_initial: float = 1e-2) -> np.ndarray:
    """Nivel filtrado por Kalman 1D (x_t = x_{t-1}, medicion = close)."""
    prices = np.asarray(closes, dtype=float)
    n = len(prices)
    if n == 0:
        return prices
    x = float(prices[0])
    p = 1.0
    r = r_initial
    levels = np.empty(n)
    innovations = np.empty(n)
    for i in range(n):
        p_pred = p + q
        z = float(prices[i])
        innov = z - x
        k = p_pred / (p_pred + r)
        x += k * innov
        p = (1 - k) * p_pred
        levels[i] = x
        innovations[i] = innov
        # adaptacion lenta de R con la varianza de innovaciones recientes
        if i > 10:
            r = max(1e-8, float(np.var(innovations[max(0, i - 30):i])))
    return levels


def kalman_features(closes: List[float]) -> Dict[str, float]:
    """Features explicables derivadas del filtro:
      kalman_slope_pct : pendiente del nivel suavizado en % del precio
      kalman_noise     : |residuo| reciente / rango del nivel (calidad senal)
    """
    closes_f = [float(c) for c in closes]
    if len(closes_f) < 5:
        return {"kalman_slope_pct": 0.0, "kalman_noise": 1.0}
    levels = kalman_level(closes_f)
    price = abs(levels[-1]) or 1.0
    slope_pct = (levels[-1] - levels[-2]) / price * 100.0
    span = float(np.ptp(levels)) or 1.0
    residual = abs(float(closes_f[-1]) - levels[-1]) / span
    return {
        "kalman_slope_pct": round(slope_pct, 6),
        "kalman_noise": round(min(1.0, residual), 6),
    }
