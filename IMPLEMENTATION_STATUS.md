# QUANT-MATH Implementation Status — v1.5.0

Estado real verificado con la suite completa (137 tests, 0 warnings).

## ✅ Núcleo en producción

| Módulo | Estado | Notas |
|---|---|---|
| `data_acquisition/` | ✅ | Bybit CCXT con retry×3/backoff, **futures swap (USDT perpetuals)** |
| `expectation/` | ✅ | Sharpe/Sortino/Calmar/drawdown |
| `risk/` | ✅ | VaR, Expected Shortfall, position sizing, stop-loss — **integrado al orchestrator** |
| `optimization/` | ✅ | Kelly criterion, mean-variance, adaptive sizing |
| `backtesting/` | ✅ | Comisión proporcional 0.1% (fix wr=0%), sortino NaN-safe, WFV con cache intra-ciclo |
| `regime_detection/` | ✅ | Clustering + features; conectable como feature SIS |
| `quant_math/orchestrator.py` | ✅ | Ciclos, dedupe+refresh-K, publish KB, stats runtime, **risk circuit breakers**, **live order placement** |
| `quant_math/decision_engine/` | ✅ | Gate expectancy, LEARN_MODE, TP/SL 2:1 por ciclo, recuperación de posiciones, feedback key+familia, fallback al siguiente mejor candidato (P1), expectancy viva con shrinkage bayesiano (PA), auto-graduación de LEARN_MODE (PB) |
| `quant_math/cli/main.py` | ✅ | Menú/wizard/monitor/historial, autoarranque VM PG, log rotativo |
| `quant_math/ml/` | ✅ | Prior supervisado (active), SIS KMeans+regímenes, feature store con cutoff, reset base |
| `model_based_generator.py` | ✅ | ARIMA/GARCH → candidatos ejecutables con contexto `_regime` |

## 🔧 v1.4.1 — Mantenimiento (2026-08-29)

| Fix | Detalle |
|---|---|
| **FFT lazy import** | `spectral_analysis/*.py`: `matplotlib.pyplot` movido a lazy import dentro de métodos `plot_*`. `_dominant_cycle()` ahora funciona en entornos sin display. |
| **Dependencias CLI** | `questionary` y `rich` añadidos a `requirements.txt` y `pyproject.toml`. CLI instalable desde limpio. |
| **Versión unificada** | `pyproject.toml` sincronizado a v1.5.0 (consistente con README). |
| **Gitignore** | Añadidos `*.pyo`, `*.log` genérico, `.pytest_cache/`, `.opencode/`, `graphify-out/`. |
| **Limpieza tracking** | `__pycache__/*.pyc` y `graphify-out/` eliminados del índice git. |

## ✅ v1.5.0 — Refactor + PCA + Consolidación (2026-08-30)

| Feature | Estado | Detalle |
|---|---|---|
| **pca_analysis** | ✅ | PCA financiero, returns decomposition, risk factors, covariance shrinkage (21 tests) |
| **Consolidación módulos** | ✅ | `expectation/`, `risk/`, `monte_carlo/` consolidados bajo `quant_math/` |
| **risk_management → quant_math.risk** | ✅ | `PortfolioRisk`, `RiskBudget`, `StressTesting` integrados |
| **Limpieza stubs** | ✅ | Eliminados `modeling/`, `volatility/`, `utils/`, `Monitor`, `progreso_qwen.txt` |
| **CI/CD** | ✅ | GitHub Actions con matrix Python 3.10/3.11/3.12 |
| **Graphify index** | ✅ | Knowledge graph regenerado (2,713 nodos, 4,488 edges) |
| **Versión** | ✅ | Unificada a 1.5.0 en todo el codebase |

## ✅ v1.6.0 — Real-money groundwork (Fases 1-4, solo CLI)

| Feature | Estado | Detalle |
|---|---|---|
| Backtester futuros | ✅ | `slippage_pct`, `leverage` (margen + liquidación), `funding_rate_8h` — defaults preservan números legacy |
| Circuit breaker | ✅ | `DailyGuard` (`daily_pnl.json`): max_daily_loss_usd=$2.50, drawdown 20%, max 5 posiciones — bloquea entradas, no ciclos |
| `RiskManager` cableado | ✅ | Cap de margen por entrada vía `check_position_size` en `_execute_paper_trade` |
| `ExchangeAPI` live | ✅ | `create_order`/`set_leverage`/`set_margin_mode`/`fetch_position` (swap USDT perps), requiere keys, `.env` + `BYBIT_TESTNET` |
| Shadow live | ✅ | `shadow_orders.jsonl` + validación de keys al inicio (warn-only) |
| Testnet live | ✅ | `dry_run=False` solo con `testnet=True` + keys; wizard con confirmación; `live_failed` no tumba el ciclo |
| Mainnet | 🔒 | Bloqueado por diseño: exige `QUANTMATH_ALLOW_MAINNET=1` + keys + doble confirmación |
| WebUI live | ⏸️ | Congelada por decisión — controles reales quedan para futuro |

## 🟡 v1.5.0 — Futures Integration + Risk Management (previo, alcance papel)

| Feature | Estado | Detalle |
|---|---|---|
| Bybit futures (`defaultType='swap'`) | ✅ | USDT perpetuals, symbol format `BTC/USDT:USDT` |
| `set_leverage()` / `set_margin_mode()` | ✅ | Configurable isolated/cross, 1-100x |
| Live order placement (`create_order`) | ✅ | Market orders via CCXT, fill confirmation |
| Risk circuit breakers | ✅ | Daily loss limit, max drawdown, max open positions |
| Daily PnL tracking | ✅ | Resetea a medianoche, pico de equity |
| `RiskManager` integration | ✅ | Position sizing, drawdown check, Kelly |
| API key infrastructure | ✅ | Fields en config, wizard prompt, env ready |
| Config fields: `max_daily_loss_pct`, `max_drawdown_pct`, `max_open_positions` | ✅ | Defaults sensatos |
| Config fields: `api_key`, `api_secret`, `sandbox`, `margin_mode` | ✅ | Para live trading futuro |
| Monitor display: leverage, risk stats, daily PnL | ✅ | Clásico y Burst |
| `_write_stats()` completo | ✅ | Incluye leverage, burst_leverage, burst_margin, dry_run, risk stats |

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


## ✅ Implementados en v1.2.0 — Plan V2: Burst Scalping

| Fase | Implementación | Verificación |
|---|---|---|
| **C1** Infraestructura de modo | `OrchestratorConfig.mode` ("classic"/"burst"), `burst_margin`, `burst_leverage`; burst constraints en `__post_init__` (interval≤15s, margin≥$5, leverage 1-20×, TP∈[0.4%,0.8%]) | 7 tests (constraints, clamps, notional) |
| **C1** Selector Top-20 | `fetch_top_volume_assets()` via ccxt `fetch_tickers`, exclude stables, fallback list; `burst_wizard()` con `questionary.checkbox` | manual CLI + test |
| **C1** Menú burst | Opción 7 "Iniciar Burst Scalping" en menú principal; `burst_wizard()` con paths aislados (`runtime/state_burst/`, `hypotheses_burst.jsonl`) | test config generation |
| **B1** Sizing margin×leverage | `_execute_paper_trade`: burst mode usa `margin × leverage` (default $10×10=$100 notional); ledger records `margin_usd`, `leverage` backward-compatible | 5 tests |
| **B1** Plantilla scalp_burst | `model_based_generator.py`: EMA trend + momentum spike + pullback entry; params: ema_fast=8, ema_slow=21, momentum_window=5, threshold=0.2%, pullback=0.3% | 2 tests |
| **B2** Estrategia scalp_burst | `aqde_runner._create_strategy_from_hypothesis`: branch completo con EMA, momentum, pullback; `quant_math_adapter.make_strategy`: branches para energy_burst, range_pressure, scalp_burst (fix bug old fallthrough) | 3 tests |
| **B2** Grid WFV | scalp_burst: ema_fast[5,8,12]×ema_slow[18,21,26]×momentum_window[3,5,8]×threshold[0.1%,0.2%,0.3]×pullback[0.2%,0.3%,0.5%] | test grid keys |
| **B2** Priorización burst | `_generate_and_backtest`: burst mode prioriza scalp_burst en la generación (+1 other for exploration) | test config |
| **B3** BurstStateTracker | `BurstStateTracker` con cooldown (10 ciclos), max 5 entries/cycle, max $50 exposure; persiste en `burst_state.json`; `reset_cycle()`, `register_entry()`, `register_closure()` | 8 tests |
| **B3** Trend filter EMA | `decide()` burst mode: side must align with EMA(8)>EMA(21); `_ema_simple()` helper | test trend blocks |
| **B4** Slippage burst | `QUANTMATH_BURST_SLIPPAGE_PCT` (default 0.03%/side vs classic 0.05%); `_slip()` usa burst-specific rate | 2 tests |
| **B4** Exposure cap | `_execute_paper_trade`: verifica Σmargin abierto ≤ $50 antes de nueva entrada burst | test cap |
| **B5** Monitor burst | Panel dedicado en `render_monitor`: entries/ciclo, cierres, win rate, cooldown, pérdidas consecutivas | 5 tests |
| **B6** Records separados | `BURST_LOG_PATH` (quant_math_burst.log) vs `LOG_PATH`; `BURST_STATE_DIR` (runtime/state_burst/) aislado; `log_path` inyectado vía config_dict al proceso hijo | 9 tests |
| **B7** Historial burst | `view_burst_history()`: libro permanente burst con columnas margin/leverage; solo habilitado cuando burst está activo | test integración |
| **B8** Monitor burst dedicado | `burst_monitor_loop()` + `render_burst_monitor()`: panel propio con exposición margin/notional, entries por ciclo, cooldown, win rate, Pérdidas consecutivas, KB trajectory, config burst | test render |
| **B9** Selector interactivo monitor | Al seleccionar "Monitor" en modo clásico, pregunta Quant-Math o Burst; en modo burst entra directo | manual CLI |

**Suite completa: 95 passed, 0 warnings.**

## ✅ Implementados en v1.3.0 — Multi-Proceso, Paralelismo, Optimización

| Feature | Implementación | Verificación |
|---|---|---|
| **Fix Monitor MtM** | Two-pass scan: primero closure keys, luego entries sin closure. Arregla conteo de 7→2 posiciones abiertas y MtM de -$5.25→+$0.24 | 2 tests (entries cerradas no cuentan, mixed open/closed) |
| **Multi-Proceso simultáneo** | `RuntimeState.processes: Dict[str, Process]` soporta classic+burst al mismo tiempo; `running_mode()`, `stop_mode()`, `stop_all()`; menu 10 items con start/stop per-mode | 5 tests (running_mode, any_running, stats_for, config_dict legacy, clear_pid) |
| **Minimizar + Background** | PID files en `runtime/state_{mode}/orchestrator.pid`; detección de huérfanos al re-entrar al CLI; `termux-wake-lock` durante ejecución, `termux-wake-unlock` durante sleep | manual (Termux) |
| **Paralelismo generación** | `ThreadPoolExecutor` para generar+backtestear símbolos en paralelo (max 3 workers); `threading.Lock` protege `runner.all_hypotheses` compartido | manual (performance) |
| **Paralelismo exits+publish** | `check_exits_all()` corre en paralelo con `_publish_to_kb()` via ThreadPool (datos independientes) | manual (performance) |
| **Sleep adaptativo** | Burst mode duerme 60s cuando idle (sin pos abiertas ni cooldown) vs 15s activo | test (config) |
| **Memory pruning** | `performance_history` cap 500 registros; `all_hypotheses` cap 200 activas (retired/failed removidas) | 2 tests (prune_history, prune_hypotheses) |
| **Buffered logs** | `_CappedStream` usa `buffering=8192` en vez de `1` (~90% menos syscalls) | code review |
| **os.nice(10)** | Prioridad baja en child process para no competir con apps foreground en Android | code review |

**Suite completa: 137 passed, 0 warnings.**
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
# 137 passed · 0 warnings
```
