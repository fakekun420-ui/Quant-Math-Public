"""Generador de hipotesis basado en modelos cientificos (ARIMA/GARCH).

Conecta los modelos de statsmodels/arch al flujo de AQDE como una fuente
ADICIONAL de candidatos junto a las plantillas clasicas. Los modelos solo
DECIDEN familia y parametros de estrategias ya ejecutables por el backtester
(donchian_breakout, rsi_reversion, macd); nunca alteran el gate de decision.

Flag: HAS_MODEL_BASED_GENERATOR = True si hay al menos una familia de
modelos importable. Su ausencia jamas rompe el sistema (try/except en el
punto de consumo).
"""

from __future__ import annotations

import logging
import numpy as np

logger = logging.getLogger(__name__)

HAS_MODEL_BASED_GENERATOR = False
_HAS_TS = False
_HAS_GARCH = False

try:
    from statsmodels.tsa.arima.model import ARIMA  # noqa: F401
    from statsmodels.tsa.statespace.sarimax import SARIMAX  # noqa: F401,F401
    _HAS_TS = True
    HAS_MODEL_BASED_GENERATOR = True
except Exception:
    pass

try:
    from arch import arch_model  # noqa: F401
    _HAS_GARCH = True
    HAS_MODEL_BASED_GENERATOR = True
except Exception:
    pass

MIN_CLOSES = 80


def _dominant_cycle(closes):
    """Ciclo dominante en velas via FFT del paquete spectral_analysis
    existente (sin duplicar implementacion). None si no hay pico claro."""
    try:
        import numpy as _np
        from spectral_analysis.fft import FastFourierTransform
        rets = _np.diff(_np.log(_np.asarray(closes, dtype=float)))
        fft = FastFourierTransform(sampling_rate=1.0)
        peak_freq, peak_mag = fft.find_peak_frequency(
            rets, min_freq=1 / 120, max_freq=0.4)
        if peak_freq <= 0 or peak_mag <= 0:
            return None
        cycle = int(round(1.0 / peak_freq))
        return cycle if 5 <= cycle <= 120 else None
    except Exception as exc:
        logger.debug("FFT ciclo fallo: %s", exc)
        return None


def analyze_series(closes) -> dict:
    """ARIMA(1,1,0): signo del forecast; GARCH(1,1): percentil de la volatilidad
    condicional actual vs su propia historia. Todo explicable."""
    out = {"n": len(closes), "forecast_up": None, "vol_pct": None,
           "cycle_len": None, "k_slope": 0.0, "k_noise": 1.0}
    try:
        from quant_math.ml.kalman_feature import kalman_features
        kf = kalman_features(list(closes))
        out["k_slope"] = kf["kalman_slope_pct"]
        out["k_noise"] = kf["kalman_noise"]
    except Exception as exc:
        logger.debug("kalman fallo: %s", exc)
    out["cycle_len"] = _dominant_cycle(list(closes))
    closes = np.asarray(closes, dtype=float)
    if _HAS_TS and len(closes) >= MIN_CLOSES:
        try:
            fit = ARIMA(closes, order=(1, 1, 0)).fit()
            fc = float(np.asarray(fit.forecast(1)).ravel()[0])
            out["forecast_up"] = bool(fc > float(closes[-1]))
        except Exception as exc:
            logger.debug("ARIMA fallo: %s", exc)
    if _HAS_GARCH and len(closes) >= MIN_CLOSES:
        try:
            rets = np.diff(np.log(closes)) * 100.0
            res = arch_model(rets, vol="GARCH", p=1, q=1,
                             rescale=False).fit(disp="off")
            cond = res.conditional_volatility
            out["vol_pct"] = float((cond[-1] >= cond).mean()) * 100.0
        except Exception as exc:
            logger.debug("GARCH fallo: %s", exc)
    return out


def generate_model_hypotheses(symbol: str, closes, max_hypotheses: int = 2):
    """Devuelve plantillas compatibles con create_hypotheses_for_symbol.

    Regla explicable:
      vol alta (>=70 pct) + forecast alcista -> breakout donchian corto
      vol baja  (<=30 pct)                   -> reversion RSI con bandas anchas
      resto / sin modelos                    -> macd estandar
    """
    if not HAS_MODEL_BASED_GENERATOR or len(closes) < MIN_CLOSES:
        return []
    info = analyze_series(closes)
    sym = symbol.replace("/", "")
    # Contexto de mercado persistente: viaja dentro de parameters hasta el
    # KB para que el aprendizaje no supervisado pueda usarlo como feature.
    regime = {"vol_pct": info.get("vol_pct"),
              "forecast_up": info.get("forecast_up"),
              "cycle_len": info.get("cycle_len"),
              "k_slope": info.get("k_slope"),
              "k_noise": info.get("k_noise")}
    out = []

    def _attach(params):
        p = dict(params)
        p["_regime"] = regime
        return p

    from quant_math.autonomous_research.interfaces import StrategyType

    up = info.get("forecast_up")
    vol = info.get("vol_pct")
    if up is not None and vol is not None and vol >= 70:
        cycle = info.get("cycle_len")
        window = max(7, min(40, round(cycle / 2))) if cycle \
            else (10 if up else 20)
        out.append({
            "name": f"MGARCH_Breakout_{window}_{sym}",
            "description": (f"GARCH vol_p={vol:.0f}% ARIMA_up={up} -> "
                            f"donchian {window} para {symbol}"),
            "strategy_type": StrategyType.BREAKOUT,
            "parameters": _attach({"strategy_type": "donchian_breakout",
                           "donchian_window": window, "symbol": symbol}),
        })
    elif vol is not None and vol <= 30:
        out.append({
            "name": f"MLowVol_RSI_{sym}",
            "description": (f"GARCH vol_p={vol:.0f}% baja -> RSI "
                            f"reversion bandas 25/75 para {symbol}"),
            "strategy_type": StrategyType.MEAN_REVERSION,
            "parameters": _attach({"strategy_type": "rsi_reversion",
                           "rsi_period": 14, "rsi_oversold": 25,
                           "rsi_overbought": 75, "symbol": symbol}),
        })
    if len(out) < max_hypotheses and up is not None:
        fast, slow = (8, 21) if up else (13, 34)
        out.append({
            "name": f"MARIMA_MACD_{fast}_{slow}_{sym}",
            "description": (f"ARIMA forecast_up={up} -> MACD {fast}/{slow} "
                            f"para {symbol}"),
            "strategy_type": StrategyType.MOMENTUM,
            "parameters": _attach({"strategy_type": "macd",
                           "short_window": fast, "long_window": slow,
                           "symbol": symbol}),
        })

    # O7: familias adicionales derivadas solo de closes
    # 1) energy_burst: pico de |retorno| z-score -> momentum en su direccion
    if len(out) < max_hypotheses:
        z = info.get("k_noise")
        burst_z = 2.0 if (z is None or z < 1) else 1.5
        out.append({
            "name": f"MEnergy_Burst_{burst_z}_{sym}",
            "description": (f"Pico |ret| z>{burst_z} -> momentum de energia "
                            f"para {symbol}"),
            "strategy_type": StrategyType.CUSTOM,
            "parameters": _attach({"strategy_type": "energy_burst",
                           "burst_window": 20, "burst_z": burst_z,
                           "symbol": symbol}),
        })
    # 2) range_pressure: posicion del close en su rango rodante como presion
    if len(out) < max_hypotheses:
        out.append({
            "name": f"MRange_Pressure_20_{sym}",
            "description": (f"Presion (c-min)/(max-min) w20 umbral "
                            f"0.85/0.15 para {symbol}"),
            "strategy_type": StrategyType.CUSTOM,
            "parameters": _attach({"strategy_type": "range_pressure",
                           "range_window": 20, "pressure_hi": 0.85,
                           "pressure_lo": 0.15, "symbol": symbol}),
        })
    return out[:max_hypotheses]
