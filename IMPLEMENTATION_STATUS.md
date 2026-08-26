# QUANT-MATH Implementation Status — v1.1.0

Estado real verificado con la suite completa (76+ tests, 0 warnings).

## ✅ Núcleo en producción

| Módulo | Estado | Notas |
|---|---|---|
| `data_acquisition/` | ✅ | Bybit CCXT con retry×3/backoff por página |
| `expectation/` | ✅ | Sharpe/Sortino/Calmar/drawdown |
| `risk/` | ✅ | VaR, Expected Shortfall, position sizing, stop-loss |
| `optimization/` | ✅ | Kelly criterion, mean-variance, adaptive sizing |
| `backtesting/` | ✅ | Comisión proporcional 0.1% (fix wr=0%), sortino NaN-safe, WFV con cache intra-ciclo |
| `regime_detection/` | ✅ | Clustering + features; conectable como feature SIS |
| `quant_math/orchestrator.py` | ✅ | Ciclos, dedupe+refresh-K, publish KB, stats runtime |
| `quant_math/decision_engine/` | ✅ | Gate expectancy, LEARN_MODE, TP/SL 2:1 por ciclo, recuperación de posiciones, feedback key+familia, fallback al siguiente mejor candidato (P1), expectancy viva con shrinkage bayesiano (PA), auto-graduación de LEARN_MODE (PB) |
| `quant_math/cli/main.py` | ✅ | Menú/wizard/monitor/historial, autoarranque VM PG, log rotativo |
| `quant_math/ml/` | ✅ | Prior supervisado (active), SIS KMeans+regímenes, feature store con cutoff, reset base |
| `model_based_generator.py` | ✅ | ARIMA/GARCH → candidatos ejecutables con contexto `_regime` |
| PostgreSQL KB | ✅ | MicroVM qcow2 persistente (:15432), tabla por kb_path, seed JSONL↔PG, fallback total |

## 🟡 En recolección (activación automática por umbral)

| Sistema | Umbral | Actual |
|---|---|---|
| Prior supervisado → advisory ranking | 100 registros KB | activo (>900 históricos archivados; base nueva creciendo) |
| SIS clustering + recomendaciones | 30 cierres post-cutoff | creciendo (cutoff v1.0.1 fijado) |
| Family feedback AQDE | 3 ops por familia×símbolo | disparando por múltiplos |
| Auto-graduación LEARN_MODE (PB) | 30 cierres con media > 0 (`QUANTMATH_GRAD_WINDOW`) | armada; decisión persistida en `runtime/state/graduation.json` |

## ✅ Implementados en v1.0.1 (ex-propuestas del README v0.x)

| Sistema | Ubicación | Integración |
|---|---|---|
| Kalman filter features | `quant_math/ml/kalman_feature.py` | `_regime.k_slope/.k_noise` → SIS features |
| Spectral FFT ciclo dominante | reutiliza `spectral_analysis.fft.find_peak_frequency` | `_regime.cycle_len` → ventana donchian adaptativa |
| Prior Bayesiano formal (IC90) | `hypothesis_prior.beta_posterior()` | CI90 por celda en summary/logs |
| Cross-symbol validation | `orchestrator._result_to_kb_record` | familia ganadora en otro símbolo eleva backtested→validated (nunca rescata failed) |

Compat shim incluido: `spectral_analysis/wavelet_analysis.py` soporta
scipy>=1.12 (cwt/ricker eliminadas upstream).

## ✅ Implementados en v1.0.1 (mejoras de decisión, commits 6414e71 / d99d3cd)

| Sistema | Ubicación | Efecto |
|---|---|---|
| P1: fallback de ranking | `decision_engine.main.ranked_candidates` + `decide` | si el mejor candidato tiene posición abierta, entra el siguiente mejor (gate por candidato); fin del idling por guard |
| PA: expectancy viva | `decision_engine.main._refresh_live_expectancy` | tras cada cierre re-blendea la expectancy del registro hacia resultados reales (`est = (n·propia+3·familia)/(n+3)`; `exp = w·gen+(1-w)·est`, w=n/(n+5)); persiste en PG+JSONL; log `[exp-refresh]` |
| PB: auto-graduación | `decision_engine.main._maybe_graduate` | con los últimos N cierres de media positiva desactiva LEARN_MODE y restaura el gate; persiste en `runtime/state/graduation.json`; flags `QUANTMATH_AUTO_GRADUATE` / `QUANTMATH_GRAD_WINDOW` |

## ✅ Implementados en v1.1.0 — plan de optimización O1–O7 de la evaluación

| Ítem | Implementación | Verificación |
|---|---|---|
| **O1** Graduación endurecida | `_maybe_graduate`: media>0 **y** IC90_lb>0 (normal approx, z=1.2816) **y** ≥ `QUANTMATH_GRAD_MIN_FAMILIES` (default 2) familias distintas; payload auditable en graduation.json | 3 tests (marginal bloqueada / diversidad / criterio completo) |
| **O2** Slippage paper | ±`QUANTMATH_SLIPPAGE_PCT` (0.05% default) adverso en entrada y salida (`_slip`), conservador para ambos lados del libro | test aritmética exacta |
| **O4** Novedad generativa | `novelty_rate_last_cycle`, `novelty_cum_avg` en runtime_stats + línea `[novedad]` por ciclo; helper testeable `_novelty_rate` | incluido en suite orchestrator |
| **O6** Sizing vol-targetado | Post-graduación: `signal["sizing_mult"] = clamp(target/vol_realizada, 0.5, 2)`; orchestrator escala notional; flags VOL_TARGET/VOL_TARGET_PCT | test clamp+gate |
| **O7** Familias nuevas | `energy_burst` (pico \|ret\| z-score) y `range_pressure` (posición en rango rodante) en model_based_generator + ramas de señal y grids WFV en aqde_runner; StrategyType.CUSTOM → familia "custom" compartida para feedback | test generación+señal |
| **O3** Multi-símbolo | Verificado e2e: keys por hipótesis×símbolo aisladas, P1 fallback por símbolo; ids deben ser únicos por símbolo (documentado) | test integración 2 símbolos |
| **O5** Panel CLI aprendizaje | Monitor: curva PnL sparkline (últimos 30), estado/progreso graduación con IC90_lb en vivo, trayectoria libro (últ10 vs prev10), novedad generativa | manual via CLI |

**Diferidos con criterio explícito**: familia seasonality (requiere plombr
de timestamps hasta el interface de señales — closes-only hoy);
order-flow real (sin fuente L2/taker-volume en el stack actual).
Estos dos puntos quedan como follow-up documentado, no descartados.

## ❌ Descartados (no implementar)

- VectorBT / Backtrader / pykalman — backtester propio ya corregido.
- Ruta sintética en producción — soldada cerrada (`force_real_data=True`).
- Estructura `models/ strategies/ research/ notebooks/` del README v0.x.

## Suite de verificación

```bash
python -m pytest test_integration.py tests/ \
    algo_trading/test_standalone.py backtesting/test_standalone.py \
    ml_quant/test_standalone.py order_management/test_standalone.py \
    portfolio_construction/test_standalone.py regime_detection/test_standalone.py \
    risk_management/test_standalone.py
# 76+ passed · 0 warnings
```
