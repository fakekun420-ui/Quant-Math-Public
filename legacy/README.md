# Legacy / Research modules (no cableados al flujo vivo)

> Estos módulos **no son usados por** `quant_math/cli`, `quant_math/orchestrator`, `quant_math/decision_engine` ni `data_acquisition` (verificado via `graphify-out/graph.json`: 0 `incoming_from_quant_math`).
> Se conservan para investigación / backtest académico. No se importan en el loop paper/live.

| Módulo | Líneas | Estado graphify |
|--------|--------|-----------------|
| `ml_quant/` | 441 | 51 nodos, 0 incoming |
| `portfolio_construction/` | 422 | 50 nodos, 0 incoming |
| `optimization/` | 308 (kelly+mean_variance+adaptive) | 6 incoming solo vía `quant_math/__init__.py` re-export fantasma — cortado |
| `regime_detection/` | ~1.6k (clustering, feature_extraction, statistical_tests, volatility) | 185 nodos, 0 incoming |
| `spectral_analysis/` | ~1.2k (fft, periodogram, psd, wavelet, harmonic) | 128 nodos, 0 incoming |
| `signal_processing/` | ~1.5k (band/high pass, kalman, emd, wavelet) | 107 nodos, 0 incoming |
| `algo_trading/` | 527 | solo tests→order_management |
| `execution/` | 300 | 0 incoming desde quant_math |
| `statistical_models.py` | 491 | 35 nodos, 0 incoming |

**Si se quiere reactivar** alguno, cablearlo vía `quant_math/orchestrator.py:338 load_loop()` o `model_based_generator.py` y quitar su línea de `.graphifyignore`.

**Risk duplicado eliminado:** `risk_management/` (1267 líneas, `portfolio_risk.py` byte-idéntico a `quant_math/risk/portfolio_risk.py`) → `quant_math/risk/examples.py`.
