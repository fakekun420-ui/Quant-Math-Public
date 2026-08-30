# System Dependency Map — Quant-Math + AQDE Ecosystem

> ⚠️ **SNAPSHOT HISTÓRICO — era Termux (2026-08-05).** Este audit fue
> generado en el entorno anterior (`/data/data/com.termux/...`) y refleja
> 84 archivos Python pre-reconstrucción. La arquitectura y dependencias
> VIGENTES de Quant-Math v1.5.0 están en `ARCHITECTURE.md`.
>
> **Δ principal desde este snapshot:** nuevo stack ML/SIS
> (`quant_math/ml/`: prior, feature_store, regime_learning, kalman,
> learning_reset), Knowledge Base PostgreSQL persistente con fallback
> JSONL (`adapters/postgres_kb.py`), model-based generator ARIMA/GARCH,
> CLI completa con historial, SL 2:1 + libro permanente, cache intra-ciclo.

---

# System Dependency Map — Quant-Math + AQDE Ecosystem

**Generated:** 2026-08-05  
**Audit Method:** Static analysis + import testing + cross-reference verification  
**Scope:** `/data/data/com.termux/files/home/quant-math/` (excluding `autonomous-research/`) + `/data/data/com.termux/files/home/quant-math/autonomous-research/`

---

## Executive Summary

| Metric | Quant-Math Core | AQDE (autonomous-research) | Combined |
|--------|-----------------|----------------------------|----------|
| Total Python files | 84 | 23 | 107 |
| Importable modules | 43/56 (77%) | 18/23 (78%) | — |
| Standalone scripts (compile OK) | 28/28 (100%) | 3/3 (100%) | — |
| **Essential (main flow)** | **17** | **13** | **30** |
| **Shared (both systems)** | **4** | **4** | **4** |
| **Optional / Standalone** | **28** | **3** | **31** |
| **Orphaned / Unreferenced** | **11** | **2** | **13** |
| **Broken refs / Missing deps** | **13 modules** | **5 modules** | **18 modules** |
| **Duplicate / Conflicting** | **2 pairs** | **0** | **2 pairs** |
| **Obsolete / Stale artifacts** | **22 CSV/TXT** | **2 JSON** | **24** |

**Overall Health:** The core integration between Quant-Math and AQDE **works** — the `QuantMathAdapter` successfully wraps Quant-Math's `backtesting`, `data_acquisition`, `order_management` modules, and the hypothesis flow (AQDE → Quant-Math → AQDE) executes end-to-end. However, ~23% of Quant-Math modules and ~22% of AQDE adapters fail to import due to missing optional dependencies (`scipy`, `matplotlib`, `pywt`, `psycopg2`, `sklearn`, `arch`, `statsmodels`, `vectorbt`, `backtrader`, `cvxpy`, `pykalman`).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUANT-MATH CORE SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  Entry Points:                                                               │
│    • run_aqde.py           → Launches AQDE pipeline (via run_aqde.py)       │
│    • test_integration.py   → Integration test (6 tests)                     │
│    • test_backtest.py      → Backtest test                                  │
│    • Various standalone backtest/optimization scripts                       │
│                                                                              │
│  Core Pipeline (imported by QuantMathAdapter):                               │
│    backtesting → Backtester, BacktestResult, PerformanceMetrics, Trade      │
│    data_acquisition.data_sources.exchanges → ExchangeAPI                    │
│    order_management → OrderManager                                           │
│    expectation → ReturnCalculator, DrawdownAnalyzer, SharpeMetrics          │
│    risk → PositionSizer, ValueAtRisk, ExpectedShortfall                     │
│    optimization → KellyCriterion, MeanVarianceOptimizer, AdaptiveSizing     │
│    execution → ExchangeAPI, OrderTypes, Routing                             │
│    regime_detection, signal_processing, spectral_analysis,                  │
│    probabilistic_modeling, algo_trading, ml_quant,                          │
│    portfolio_construction, pca_analysis, monte_carlo, modeling,             │
│    volatility, utils, backtest                                               │
│                                                                              │
│  Missing optional deps: scipy, sklearn, matplotlib, psycopg2, pywt,        │
│    arch, statsmodels, vectorbt, backtrader, cvxpy, pykalman                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    QuantMathAdapter (implements ALL 5 AQDE ports)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AQDE (autonomous-research)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Entry Points:                                                               │
│    • aqde_pipeline.py     → 5-phase pipeline (main CLI)                    │
│    • cli/__main__.py      → CLI entry point (setup.py: aqde=cli:cli)       │
│    • api/main.py          → FastAPI REST API (currently broken: pydantic)  │
│    • run_aqde.py          → Wrapper that fixes hyphenated package name     │
│                                                                              │
│  Core Domain (all import OK):                                                │
│    core/interfaces.py      → Hypothesis, StrategyResult, MonteCarloResult, │
│                              AgentMessage, StrategyType, StrategyStatus    │
│    agents/research_manager.py → ResearchManager (orchestrator)             │
│    agents/agent_registry.py   → AgentRegistry (communication)              │
│    agents/knowledge_manager/  → KnowledgeBase (file-based, SQLite-style)   │
│                                                                              │
│  Adapters (Quant-Math integration layer):                                    │
│    adapters/quant_math_adapter.py → ESSENTIAL (main integration)           │
│    adapters/knowledge_manager_stub.py → Fallback KB                        │
│    adapters/backtest_engine.py → AQDE protocol (not used directly)         │
│    adapters/monte_carlo_engine.py → BROKEN (needs scipy)                   │
│    adapters/risk_manager.py → OK                                            │
│    adapters/statistical_validator.py → BROKEN (needs scipy)                │
│                                                                              │
│  Testing / Verification:                                                     │
│    tests/__init__.py        → Comprehensive integration tests (12 tests)   │
│    smoke_test.py            → Phase 4 infrastructure check (not E2E)       │
│    final_integration_test.py → Legacy E2E test                             │
│    phase5_deployment_verification.py → Deployment verification             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Quant-Math — Essential Files (Used in Main Flow / by AQDE)

| File / Module | Classification | Justification |
|---------------|----------------|---------------|
| `backtesting/backtester.py` | **ESSENTIAL** | Exports `Backtester`, `BacktestResult`, `PerformanceMetrics`, `Trade` — directly used by `QuantMathAdapter.run_backtest()` |
| `data_acquisition/data_sources/exchanges.py` | **ESSENTIAL** | Exports `ExchangeAPI` with `fetch_ohlcv`, `ohlcv_to_dataframe` — used by `QuantMathAdapter.fetch_market_data()` |
| `order_management/order_management.py` | **ESSENTIAL** | Exports `OrderManager` — instantiated by `QuantMathAdapter` |
| `expectation/calculator.py` | **ESSENTIAL** | Exports `ReturnCalculator`, `DrawdownAnalyzer`, `SharpeMetrics` — used by standalone backtest scripts |
| `risk/position_sizing.py`, `risk/stop_loss.py`, `risk/var.py` | **ESSENTIAL** | Exports `PositionSizer`, `ValueAtRisk`, `ExpectedShortfall` — used by standalone scripts |
| `optimization/kelly.py`, `optimization/mean_variance.py`, `optimization/adaptive_sizing.py` | **ESSENTIAL** | Exports `KellyCriterion`, `MeanVarianceOptimizer`, `AdaptiveSizing` — used by standalone scripts |
| `execution/exchanges.py`, `execution/order_types.py`, `execution/routing.py` | **ESSENTIAL** | Execution engine components — available for adapter use |
| `regime_detection/regime_detection.py` | **ESSENTIAL** | Regime detection — used by `test_integration.py` |
| `algo_trading/algo_trading.py` | **ESSENTIAL** | `AlgoTradingSystem` — used by `test_integration.py` |
| `ml_quant/ml_quant.py` | **ESSENTIAL** | ML quant module — used by `test_integration.py` |
| `monte_carlo/__init__.py` | **ESSENTIAL** | Monte Carlo simulation — used by `test_integration.py` |
| `__init__.py` | **ESSENTIAL** | Root package init — enables `import quant_math` style |
| `run_aqde.py` | **ESSENTIAL** | Main AQDE launcher — fixes hyphenated package name for imports |
| `test_integration.py` | **ESSENTIAL** | 6 integration tests — validates all 6 core modules work together |
| `requirements.txt` | **ESSENTIAL** | Core dependency manifest |
| `README.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_STATUS.md` | **ESSENTIAL** | Architecture & status documentation |

---

## Quant-Math — Shared Files (Used by Both Systems)

| File / Module | Classification | Justification |
|---------------|----------------|---------------|
| `backtesting/backtester.py` | **SHARED** | Used by Quant-Math tests AND `QuantMathAdapter` |
| `data_acquisition/data_sources/exchanges.py` | **SHARED** | Used by Quant-Math AND `QuantMathAdapter.fetch_market_data()` |
| `order_management/order_management.py` | **SHARED** | Used by Quant-Math AND `QuantMathAdapter` |
| `risk_management/risk_management.py` | **SHARED** | Used by Quant-Math tests AND available to adapter |

---

## Quant-Math — Optional / Standalone Scripts (Compile OK, Not in Main Flow)

These scripts compile without syntax errors but are **not imported by any other file** — they are standalone analysis/backtest tools:

| File | Classification | Notes |
|------|----------------|-------|
| `check_volatility.py` | **OPTIONAL** | Volatility analysis utility |
| `crypto_bollinger_optimized.py` | **OPTIONAL** | Bollinger band backtest |
| `crypto_bollinger_scalp.py` | **OPTIONAL** | Scalping variant |
| `crypto_hybrid_backtest.py` | **OPTIONAL** | Hybrid strategy backtest |
| `crypto_hybrid_backtest_extended.py` | **OPTIONAL** | Extended version |
| `crypto_momentum_backtest.py` | **OPTIONAL** | Momentum strategy — imports core modules |
| `crypto_rsi_backtest.py` | **OPTIONAL** | RSI strategy backtest |
| `crypto_zscore_reversion.py` | **OPTIONAL** | Z-score mean reversion |
| `debug_pnl.py` | **OPTIONAL** | PnL debugging utility |
| `debug_realistic.py` | **OPTIONAL** | Realistic simulation debug |
| `debug_signals.py` | **OPTIONAL** | Signal debugging utility |
| `download_crypto_data.py` | **OPTIONAL** | Data downloader |
| `download_historical_data.py` | **OPTIONAL** | Historical data downloader |
| `download_scalping_data.py` | **OPTIONAL** | Scalping data downloader |
| `ema_cross_scalping_backtest.py` | **OPTIONAL** | EMA crossover backtest |
| `ema_cross_scalping_fast.py` | **OPTIONAL** | Fast variant |
| `fast_optimization.py` | **OPTIONAL** | Quick optimization script |
| `optimize_sl_tp.py` | **OPTIONAL** | Stop-loss/take-profit optimization |
| `optimize_sl_tp_fixed.py` | **OPTIONAL** | Fixed variant |
| `optimize_sl_tp_realistic.py` | **OPTIONAL** | Realistic variant |
| `optimize_sl_tp_volatility_filtered.py` | **OPTIONAL** | Volatility-filtered variant |
| `optimized_ema_cross.py` | **OPTIONAL** | Optimized EMA crossover |
| `quick_test.py` | **OPTIONAL** | Quick test script |
| `scalping_backtest_1m_5m.py` | **OPTIONAL** | Multi-timeframe scalping |
| `scan_multiple_strategies.py` | **OPTIONAL** | Strategy scanner |
| `statistical_models.py` | **OPTIONAL** | Statistical modeling utility |
| `test_backtest.py` | **OPTIONAL** | Backtest test |
| `verify_market.py` | **OPTIONAL** | Market verification utility |
| `risk_management.py` (root) | **OPTIONAL** | **DUPLICATE** — same name as package, only imports `scipy` |

---

## Quant-Math — Orphaned / Unreferenced Modules (No incoming imports)

| Module | Classification | Issue |
|--------|----------------|-------|
| `data_processing/*` (cleaning, normalization, resampling, structural_breaks) | **ORPHAN** | All require `sklearn` (not installed); no file imports them |
| `signal_processing/*` (band_pass_filter, high_pass_filter, wavelet_decomposition) | **ORPHAN** | Require `scipy`/`pywt`; no file imports them |
| `spectral_analysis/*` (fft, harmonic_analysis, periodogram, psd, wavelet) | **ORPHAN** | Require `matplotlib`; only `spectral_analysis/__main__.py` references |
| `probabilistic_modeling/*` (hidden_markov, monte_carlo, probabilistic_forecasting, probabilistic_regression) | **ORPHAN** | Require `statistical_models` module (broken import chain); only `run_example.py` references |
| `pca_analysis` (pca, scree_plot, explained_variance, component_rotation) | **ORPHAN** | `__init__.py` imports `pca_analysis.pca` which **does not exist**; no file imports this package |
| `portfolio_construction/portfolio_construction.py` | **ORPHAN** | Requires `scipy`; only `__main__.py` and `test_standalone.py` reference |
| `modeling/__init__.py` | **ORPHAN** | Empty package; no imports |
| `volatility/__init__.py` | **ORPHAN** | Empty package; no imports |
| `utils/__init__.py` | **ORPHAN** | Empty package; no imports |
| `backtest/__init__.py` | **ORPHAN** | **DUPLICATE** of `backtesting/` — only comment, no exports |

---

## Quant-Math — Broken References / Missing Dependencies

| Module | Missing Dependency | Impact |
|--------|-------------------|--------|
| `data_acquisition.storage.database` | `psycopg2` | Database storage unavailable |
| `data_processing.*` | `sklearn` | Data processing pipeline unavailable |
| `risk_management` (package) | `scipy` | Risk metrics unavailable |
| `regime_detection.*` | `scipy` | Regime detection unavailable |
| `signal_processing.band_pass_filter` | `scipy` | Filter unavailable |
| `signal_processing.high_pass_filter` | `scipy` | Filter unavailable |
| `signal_processing.wavelet_decomposition` | `pywt` | Wavelet unavailable |
| `spectral_analysis.*` | `matplotlib` | Visualization/analysis unavailable |
| `probabilistic_modeling.*` | **[REMOVED - module does not exist on disk]** | Previously reported as broken; module never existed |
| `pca_analysis` | `pca_analysis.pca` (file missing) | PCA unavailable |
| `portfolio_construction` | `scipy` | Portfolio construction unavailable |
| `statistical_models.py` (root) | `scipy.stats`, `scipy.optimize` | Root utility broken |

**Total missing optional deps from `requirements.txt`:** `scipy`, `sklearn`, `matplotlib`, `psycopg2`, `pywt`, `arch`, `statsmodels`, `vectorbt`, `backtrader`, `cvxpy`, `pykalman` — 11 packages.

---

## Quant-Math — Duplicate / Conflicting Files

| Conflict | Classification | Resolution |
|----------|----------------|------------|
| `backtest/__init__.py` vs `backtesting/__init__.py` | **DUPLICATE** | `backtesting/` is the real module (has exports); `backtest/` is empty — **remove `backtest/`** |
| `risk_management.py` (root) vs `risk_management/` (package) | **DUPLICATE** | Root file only imports `scipy`; package is real — **remove root `risk_management.py`** |

---

## Quant-Math — Obsolete / Stale Artifacts

| File | Classification | Reason |
|------|----------------|--------|
| `aqde_results.json` | **STALE** | Old AQDE run results (2026-08-04) |
| `backtest_summary_20260804_030502.txt` | **STALE** | Old backtest output |
| `scalping_trades_*.csv` (4 files) | **STALE** | Old trade logs from 2026-08-04 |
| `scan_signals_*.csv` (20 files) | **STALE** | Old signal scan outputs from 2026-08-04 |

---

## AQDE (autonomous-research) — Essential Files

| File / Module | Classification | Justification |
|---------------|----------------|---------------|
| `aqde_pipeline.py` | **ESSENTIAL** | Main 5-phase pipeline CLI — entry point for `run_aqde.py` |
| `core/interfaces.py` | **ESSENTIAL** | All domain contracts: `Hypothesis`, `StrategyResult`, `MonteCarloResult`, `AgentMessage`, protocols |
| `agents/research_manager.py` | **ESSENTIAL** | Orchestrator — implements 5-phase workflow, used by `aqde_pipeline.py` |
| `agents/agent_registry.py` | **ESSENTIAL** | Agent communication — used by `ResearchManager` and `aqde_pipeline.py` |
| `agents/knowledge_manager/knowledge_base.py` | **ESSENTIAL** | Persistent KB (JSONL) — used by `QuantMathAdapter` via `knowledge_manager_stub` |
| `adapters/quant_math_adapter.py` | **ESSENTIAL** | **Main integration bridge** — implements all 5 AQDE ports using Quant-Math |
| `adapters/knowledge_manager_stub.py` | **ESSENTIAL** | Fallback KB — used when `knowledge_manager` not installed |
| `adapters/risk_manager.py` | **ESSENTIAL** | Risk port implementation — used by `ResearchManager` |
| `adapters/backtest_engine.py` | **ESSENTIAL** | Backtest port (protocol) — defines interface |
| `cli/__main__.py`, `cli/__init__.py` | **ESSENTIAL** | CLI entry point — `setup.py` declares `aqde=cli:cli` |
| `__init__.py` | **ESSENTIAL** | Package init with version, enables `autonomous_research` import |
| `setup.py` | **ESSENTIAL** | Package metadata, entry point |
| `README.md`, `ARCHITECTURE.md`, `DEPLOYMENT.md` | **ESSENTIAL** | Documentation |
| `requirements.txt`, `requirements_simplified.txt`, `pytest.ini` | **ESSENTIAL** | Dependencies & test config |

---

## AQDE — Shared Files (Used by Both Systems)

Same 4 files as Quant-Math shared list — the integration layer:

| File / Module | Classification |
|---------------|----------------|
| `backtesting/backtester.py` | **SHARED** |
| `data_acquisition/data_sources/exchanges.py` | **SHARED** |
| `order_management/order_management.py` | **SHARED** |
| `risk_management/risk_management.py` | **SHARED** |

---

## AQDE — Optional / Standalone Scripts

| File | Classification | Notes |
|------|----------------|-------|
| `smoke_test.py` | **OPTIONAL** | Phase 4 infrastructure test (directory structure, imports, CLI) — not E2E |
| `final_integration_test.py` | **OPTIONAL** | Legacy E2E test — may be superseded by `tests/__init__.py` |
| `phase5_deployment_verification.py` | **OPTIONAL** | Deployment verification script |

---

## AQDE — Orphaned / Unreferenced / Broken

| File / Module | Classification | Issue |
|---------------|----------------|-------|
| `adapters/monte_carlo_engine.py` | **BROKEN** | Requires `scipy` — import fails |
| `adapters/statistical_validator.py` | **BROKEN** | Requires `scipy` — import fails |
| `core/backtest_engine.py` | **BROKEN** | Imports `backtest_legacy` — **file does not exist** |
| `api/main.py` | **BROKEN** | `pydantic==1.10.13` incompatibility — `ConfigError: unable to infer type for attribute "name"` |
| `api/__init__.py` | **ORPHAN** | Only exports broken `api.main` |
| `agents/knowledge_manager/__init__.py` | **ORPHAN** | Empty; `knowledge_base.py` not re-exported |

---

## AQDE — Missing Dependencies

| Missing Package | Required By | Impact |
|-----------------|-------------|--------|
| `scipy` | `adapters/monte_carlo_engine.py`, `adapters/statistical_validator.py` | Monte Carlo & statistical validation unavailable |
| `fastapi>=0.104`, `pydantic>=2.0` | `api/main.py` | REST API broken (version conflict: requires `pydantic==1.10.13` per `requirements.txt` but code needs v2) |

---

## Cross-System Communication Verification

| Flow | Status | Evidence |
|------|--------|----------|
| Quant-Math → AQDE (import) | **N/A** | Quant-Math does not import AQDE (one-way dependency) |
| AQDE → Quant-Math (adapter imports) | **PASS** | `QuantMathAdapter` imports `backtesting`, `data_acquisition.exchanges`, `order_management` successfully |
| `QuantMathAdapter.HAS_QUANT_MATH` | **TRUE** | All 3 core modules available |
| KnowledgeBase resolution | **FALLBACK** | `knowledge_manager` module **missing** → falls back to `knowledge_manager_stub` |
| Hypothesis generation (AQDE) | **PASS** | `ResearchManager.generate_hypothesis()` creates `Hypothesis` object |
| Hypothesis storage (KB) | **PASS** | `adapter.store_hypothesis()` → `knowledge_base.store_hypothesis()` works |
| Hypothesis retrieval (KB) | **PASS** | `adapter.retrieve_hypothesis()` returns stored hypothesis |
| Backtest execution (Quant-Math) | **PASS** | `ResearchManager.run_backtest()` → `adapter.run_backtest()` → `Backtester.run_backtest()` |
| Scoring (AQDE) | **PASS** | `ResearchManager.score_hypothesis()` computes `scientific_score` |
| State transition (AQDE) | **PASS** | `Hypothesis.status`: `draft` → `validated` → `backtested` → `failed`/`validated` |
| Agent communication | **PASS** | `AgentRegistry.broadcast()` sends messages to 5 registered agents |
| Full E2E dry-run | **PASS** | `python3 run_aqde.py --dry-run --strategies ema_crossover` completes |

**Critical Gap:** The `knowledge_manager` Python package (referenced in `quant_math_adapter.py` try/except) **does not exist** anywhere in the repository. The adapter always falls back to the stub implementation. This means persistent hypothesis storage uses JSONL files in `autonomous_research/data/hypotheses/` rather than a proper database.

---

## Dependency Summary

### Quant-Math `requirements.txt` (Core)
```
numpy>=1.24.0           ✓ INSTALLED (1.26.4)
pandas>=2.0.0           ✓ INSTALLED (3.0.5)
scipy>=1.11.0           ✗ MISSING — breaks 13 modules
statsmodels>=0.14.0     ✗ MISSING
scikit-learn>=1.3.0     ✗ MISSING — breaks data_processing, regime_detection
arch>=6.2.0             ✗ MISSING
pykalman>=0.9.7         ✗ MISSING
pywavelets>=1.4.0       ✗ MISSING — breaks signal_processing.wavelet
vectorbt>=0.26.0        ✗ MISSING
backtrader>=1.9.78      ✗ MISSING
psycopg2-binary>=2.9.0  ✗ MISSING — breaks data_acquisition.storage
plotly>=5.18.0          ✗ MISSING
matplotlib>=3.8.0       ✗ MISSING — breaks spectral_analysis
cvxpy>=1.4.0            ✗ MISSING
pytest>=7.4.0           ✓ INSTALLED (9.1.1)
pytest-cov>=4.1.0       ✗ MISSING
pytest-mock>=3.12.0     ✗ MISSING
ccxt>=4.0.0             ✓ INSTALLED (4.5.70)
jupyter>=1.0.0          ✗ MISSING
notebook>=7.0.0         ✗ MISSING
tqdm>=4.66.0            ✗ MISSING
python-dateutil>=2.8.2  ✗ MISSING
pytz>=2023.3            ✗ MISSING
```

### AQDE `requirements.txt`
```
fastapi==0.95.2         ✓ INSTALLED
uvicorn[standard]==0.24.0  ✗ MISSING
pydantic==1.10.13       ✓ INSTALLED (but API needs pydantic>=2.0)
pytest==7.4.3           ✓ INSTALLED (9.1.1)
pytest-asyncio==0.21.1  ✓ INSTALLED (1.4.0)
python-multipart==0.0.6 ✗ MISSING
```

### AQDE `requirements_simplified.txt` (More current)
```
fastapi>=0.104.0        (conflicts with requirements.txt)
uvicorn[standard]>=0.24.0
pydantic>=2.0.0         (conflicts with requirements.txt — API needs this)
click>=8.0.0
pytest>=7.0.0
pytest-asyncio>=0.20.0
python-multipart>=0.0.0
```

---

## Recommended Cleanup Candidates

| Priority | Item | Action | Classification |
|----------|------|--------|----------------|
| HIGH | `backtest/` directory | Remove — duplicate of `backtesting/` | **DUPLICATE** |
| HIGH | `risk_management.py` (root) | Remove — conflicts with `risk_management/` package | **DUPLICATE** |
| HIGH | `knowledge_manager` import attempt | Either implement or remove try/except in `quant_math_adapter.py` | **BROKEN REF** |
| HIGH | `adapters/monte_carlo_engine.py` | Fix `scipy` import or mark optional | **BROKEN** |
| HIGH | `adapters/statistical_validator.py` | Fix `scipy` import or mark optional | **BROKEN** |
| HIGH | `core/backtest_engine.py` | Remove `backtest_legacy` import or create module | **BROKEN REF** |
| HIGH | `api/main.py` | Upgrade to `pydantic>=2.0` and fix `ConfigError` | **BROKEN** |
| HIGH | `pca_analysis/__init__.py` | Fix import of missing `pca_analysis.pca` | **BROKEN REF** |
| MEDIUM | 24 stale CSV/TXT/JSON artifacts | Archive or delete | **STALE** |
| MEDIUM | `requirements.txt` vs `requirements_simplified.txt` | Consolidate; use `requirements_simplified.txt` as base | **OBSOLETE** |
| LOW | 28 standalone backtest scripts | Move to `scripts/` or `examples/` subdirectory | **OPTIONAL** |
| LOW | 11 orphaned Quant-Math modules | Either install deps or remove if unused | **ORPHAN** |
| LOW | 2 orphaned AQDE modules (`api/`, `knowledge_manager/__init__.py`) | Remove or implement | **ORPHAN** |

---

## Module Reference Graph (Key Connections)

```
aqde_pipeline.py
    ├── imports QuantMathAdapter (adapters/quant_math_adapter.py)
    ├── imports ResearchManager (agents/research_manager.py)
    ├── imports AgentRegistry (agents/agent_registry.py)
    ├── imports STRATEGY_CATALOGUE, signal generators (self)
    └── calls generate_hypotheses() → ResearchManager.generate_hypothesis()
    
ResearchManager
    ├── uses knowledge_base (QuantMathAdapter → knowledge_manager_stub)
    ├── uses backtest_engine (QuantMathAdapter → backtesting.Backtester)
    ├── uses monte_carlo_engine (QuantMathAdapter → adapters.monte_carlo_engine)
    ├── uses statistical_validator (QuantMathAdapter → adapters.statistical_validator)
    ├── uses risk_manager (QuantMathAdapter → adapters.risk_manager)
    └── uses agent_registry (AgentRegistry)

QuantMathAdapter
    ├── implements DataProvider → fetch_market_data() → ExchangeAPI
    ├── implements KnowledgeBase → store/retrieve/search → knowledge_manager_stub
    ├── implements BacktestEngine → run_backtest() → Backtester
    ├── implements MonteCarloEngine → simulate_distribution() → numpy bootstrap
    ├── implements StatisticalValidator → win_rate, sharpe, sortino, significance
    └── implements RiskManager → position_size, drawdown, sharpe thresholds

ExchangeAPI (data_acquisition)
    ├── fetch_ohlcv() → ccxt
    ├── ohlcv_to_dataframe() → pandas
    └── get_available_symbols() → ccxt

Backtester (backtesting)
    ├── run_backtest(strategy_func, price_dict, initial_capital)
    └── returns BacktestResult with trades, metrics

OrderManager (order_management)
    └── Order management logic (used by adapter)
```

---

## Final Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **Core Integration (Quant-Math ↔ AQDE)** | ✅ **WORKING** | Adapter successfully wraps 3/3 critical Quant-Math modules |
| **AQDE Pipeline (5 phases)** | ✅ **WORKING** | End-to-end dry-run passes all phases |
| **Knowledge Base Persistence** | ⚠️ **STUB ONLY** | Real `knowledge_manager` missing; falls back to JSONL files |
| **Quant-Math Module Coverage** | ⚠️ **23% BROKEN** | 13/56 modules fail import due to missing optional deps |
| **AQDE Adapter Coverage** | ⚠️ **22% BROKEN** | 5/23 adapters/modules fail import (scipy, pydantic, backtest_legacy) |
| **API Layer** | ❌ **BROKEN** | FastAPI/pydantic version conflict |
| **Test Coverage** | ✅ **GOOD** | 6 Quant-Math integration tests + 12 AQDE integration tests |
| **Documentation** | ✅ **CURRENT** | README, ARCHITECTURE, IMPLEMENTATION_STATUS all present |
| **Dead Code / Stale Artifacts** | ⚠️ **22 files** | Old CSV/TXT/JSON from 2026-08-04 runs |

**Recommendation:** The system is **functionally integrated** for the core hypothesis→backtest→scoring loop. Priority fixes: (1) implement or remove `knowledge_manager` reference, (2) fix `scipy`/`pydantic` dependencies for full adapter coverage, (3) remove duplicate `backtest/` and root `risk_management.py`, (4) archive stale artifacts.