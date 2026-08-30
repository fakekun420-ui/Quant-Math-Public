# ARCHITECTURE GUIDE (v0.x — referencia histórica por módulo)

> ⚠️ **DOCUMENTO HISTÓRICO (v0.x).** La arquitectura EN EJECUCIÓN de
> Quant-Math v1.5.0 vive en `ARCHITECTURE.md` (pipeline AQDE → gate → SIS,
> Knowledge Base JSONL con atomic upsert, LEARN_MODE, riesgo 2:1).
> Las secciones siguientes permanecen válidas como detalle profundo de los
> módulos base; los estados/checklists que contengan pueden estar desactualizados.

---

# Quant-Math + AQDE Consolidated Architecture Guide

**Generated:** 2026-08-06
**Based on:** Full static analysis of both systems
**Status:** Recommended restructure — NOT yet implemented

---

## Executive Summary

This document describes the **target architecture** where **Quant-Math is the single core system** and **AQDE becomes an internal module** (`quant_math.autonomous_research`) that exclusively uses Quant-Math's engines, services, and utilities.

### Key Principles

1. **Single Source of Truth** — Quant-Math owns ALL engines: backtesting, Monte Carlo, risk, expectation, execution, data
2. **AQDE is a Consumer** — AQDE uses Quant-Math via well-defined interfaces; it does NOT reimplement core logic
3. **No Duplicate Logic** — All duplicated adapters are removed; AQDE ports are implemented by thin wrappers over Quant-Math
4. **Dependency Direction** — `quant_math` → `quant_math.autonomous_research` (one-way)
5. **Zero Behavioral Change** — All existing tests (integration + standalone) must continue to pass

---

## Current Problems Identified

### Duplicate Implementations (Must Consolidate)

| AQDE Adapter | Quant-Math Module | Duplicate Logic |
|--------------|-------------------|-----------------|
| `backtest_engine.py` | `backtesting/backtester.py` | Full backtest engine, metrics, trade simulation |
| `monte_carlo_engine.py` | `monte_carlo/` (empty) + `backtesting.PerformanceMetrics` | Bootstrap/parametric simulation, VaR, stress testing |
| `statistical_validator.py` | `expectation/` + `sharpe_metrics.py` | Sharpe, Sortino, Calmar, t-tests, bootstrap |
| `risk_manager.py` | `risk/` + `risk_management/` | Kelly, position sizing, drawdown, VaR, ES |
| `knowledge_manager_stub.py` | `autonomous_research/agents/knowledge_manager/` | Hypothesis storage (keep AQDE version, migrate to Quant-Math) |

### Broken / Orphaned Files (Cleanup Required)

| File | Issue | Action |
|------|-------|--------|
| `backtest/__init__.py` | Empty duplicate of `backtesting/` | **REMOVE** |
| `risk_management.py` (root) | Conflicts with `risk_management/` package | **REMOVE** |
| `adapters/monte_carlo_engine.py` | Requires `scipy` (not installed) | **REMOVE** — use Quant-Math |
| `adapters/statistical_validator.py` | Requires `scipy` (not installed) | **REMOVE** — use Quant-Math |
| `core/backtest_engine.py` | Imports missing `backtest_legacy` | **REMOVE** |
| `api/main.py` | `pydantic` v1 vs v2 conflict | **REMOVE** (not used in main flow) |
| `pca_analysis/__init__.py` | Imports missing `pca_analysis.pca` | **FIX or REMOVE** |
| `probabilistic_modeling/__init__.py` | **[REMOVED - module does not exist on disk]** | Module never existed; no action needed |

### Stale Artifacts (Archive/Delete)

- `aqde_results.json`, `backtest_summary_*.txt`
- `scalping_trades_*.csv`, `scan_signals_*.csv` (24 files from 2026-08-04)

---

## Target Module Structure

```
quant_math/                          # ROOT PACKAGE (single entry point)
├── __init__.py                      # Exports: all public APIs, version
├── requirements.txt                 # Consolidated: core + optional extras
├── README.md                        # Project overview
├── ARCHITECTURE.md                  # This document (updated)
│
├── core/                            # SHARED DOMAIN TYPES (used by both)
│   ├── __init__.py
│   ├── types.py                     # StrategyType, SignalStrength, StrategyStatus
│   ├── hypothesis.py                # Hypothesis dataclass (moved from AQDE)
│   ├── results.py                   # StrategyResult, MonteCarloResult, Trade
│   ├── messages.py                  # AgentMessage
│   └── protocols.py                 # DataProvider, KnowledgeBase, BacktestEngine,
│                                    # MonteCarloEngine, StatisticalValidator,
│                                    # RiskManager, Auditor, Agent
│
├── autonomous_research/             # AQDE MODULE (internal to Quant-Math)
│   ├── __init__.py                  # Exports: run_pipeline, ResearchManager
│   ├── pipeline.py                  # Main 5-phase pipeline (was aqde_pipeline.py)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── research_manager.py      # Orchestrator (uses Quant-Math ports)
│   │   ├── agent_registry.py        # Agent communication
│   │   └── knowledge_manager/
│   │       ├── __init__.py
│   │       ├── knowledge_base.py    # Persistent KB (JSONL/SQLite) — KEPT
│   │       └── search_criteria.py   # SearchCriteria dataclass
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── catalogue.py             # STRATEGY_CATALOGUE (signal generators)
│   │   └── generators.py            # Signal generator functions
│   ├── orchestration/
│   │   ├── __init__.py
│   │   └── agent_setup.py           # _setup_agent_registry()
│   └── reporting/
│       ├── __init__.py
│       ├── summary.py               # print_summary()
│       └── persistence.py           # save_results()
│
├── backtesting/                     # QUANT-MATH CORE: Backtesting Engine
│   ├── __init__.py                  # Exports: Backtester, BacktestResult,
│                                    # PerformanceMetrics, Trade
│   ├── backtester.py                # Core engine (EXISTING — keep)
│   └── metrics.py                   # PerformanceMetrics (EXISTING — keep)
│
├── monte_carlo/                     # QUANT-MATH CORE: Monte Carlo (NEW)
│   ├── __init__.py                  # Exports: MonteCarloSimulator,
│                                    # bootstrap_simulation, VaR, ES
│   ├── simulator.py                 # Unified Monte Carlo (replaces AQDE adapter)
│   ├── bootstrap.py                 # Non-parametric bootstrap
│   ├── parametric.py                # Parametric simulation
│   └── risk_metrics.py              # VaR, ES, stress testing (from risk_management)
│
├── expectation/                     # QUANT-MATH CORE: Expectation & Stats
│   ├── __init__.py                  # Exports: ReturnCalculator, DrawdownAnalyzer,
│                                    # SharpeMetrics, StatisticalTests
│   ├── calculator.py                # EXISTING — keep
│   ├── drawdown_analysis.py         # EXISTING — keep
│   ├── sharpe_metrics.py            # EXISTING — keep
│   └── statistical_tests.py         # NEW: t-tests, bootstrap significance (from AQDE)
│
├── risk/                            # QUANT-MATH CORE: Risk Management
│   ├── __init__.py                  # Exports: PositionSizer, StopLoss, KellyCriterion,
│                                    # ValueAtRisk, ExpectedShortfall, RiskManager
│   ├── position_sizing.py           # EXISTING — keep
│   ├── stop_loss.py                 # EXISTING — keep
│   ├── kelly.py                     # EXISTING (from optimization/) — MOVE HERE
│   ├── var.py                       # EXISTING — keep
│   ├── expected_shortfall.py        # NEW: merge from risk_management/
│   └── risk_manager.py              # NEW: unified RiskManager port impl
│
├── risk_management/                 # QUANT-MATH ADVANCED: Portfolio Risk (KEEP)
│   ├── __init__.py                  # Exports: PortfolioRisk, RiskBudget, StressTesting
│   ├── value_at_risk.py             # RENAME from risk_management.py → value_at_risk.py
│   ├── expected_shortfall.py        # RENAME from risk_management.py
│   ├── portfolio_risk.py            # RENAME from risk_management.py
│   ├── risk_budget.py               # RENAME from risk_management.py
│   └── stress_testing.py            # RENAME from risk_management.py
│
├── data_acquisition/                # QUANT-MATH CORE: Data (KEEP)
│   ├── __init__.py
│   └── data_sources/
│       ├── __init__.py
│       └── exchanges.py             # ExchangeAPI (EXISTING — keep)
│
├── order_management/                # QUANT-MATH CORE: Orders (KEEP)
│   ├── __init__.py                  # Exports: OrderManager, SlippageModel,
│                                    # ExecutionStrategy, TransactionCostModel
│   └── order_management.py          # EXISTING — keep
│
├── execution/                       # QUANT-MATH CORE: Execution (KEEP)
│   ├── __init__.py
│   ├── exchanges.py
│   ├── order_types.py
│   └── routing.py
│
├── optimization/                    # QUANT-MATH CORE: Optimization (KEEP)
│   ├── __init__.py
│   ├── kelly.py                     # MOVE to risk/kelly.py (keep alias)
│   ├── mean_variance.py
│   └── adaptive_sizing.py
│
├── algo_trading/                    # QUANT-MATH CORE: Algo Execution (KEEP)
│   ├── __init__.py
│   └── algo_trading.py
│
├── ml_quant/                        # QUANT-MATH CORE: ML (KEEP)
│   ├── __init__.py
│   └── ml_quant.py
│
├── regime_detection/                # QUANT-MATH CORE: Regimes (KEEP)
│   ├── __init__.py
│   └── regime_detection.py
│
├── signal_processing/               # QUANT-MATH: Signal (root package)
├── spectral_analysis/               # QUANT-MATH: Spectral (root package)
├── portfolio_construction/          # QUANT-MATH: Portfolio (root package)
│
├── tests/                           # UNIFIED TEST SUITE
│   ├── __init__.py
│   ├── test_integration.py          # EXISTING — Quant-Math integration
│   ├── test_backtest.py             # EXISTING — Backtest test
│   └── autonomous_research/         # AQDE tests
│       ├── __init__.py
│       ├── test_pipeline.py         # Phase 1-5 pipeline tests
│       ├── test_research_manager.py # ResearchManager tests
│       └── test_knowledge_base.py   # KB tests
│
├── scripts/                         # STANDALONE SCRIPTS (moved from root)
│   ├── backtests/                   # 28 crypto_*.py, ema_*.py, optimize_*.py
│   ├── data/                        # download_*.py
│   ├── analysis/                    # check_volatility.py, debug_*.py, scan_*.py
│   └── verify/                      # verify_market.py, quick_test.py
│
├── config/                          # CONFIGURATION
│   ├── __init__.py
│   ├── defaults.py                  # Default parameters
│   └── logging.py                   # Logging setup
│
└── data/                            # DATA STORAGE (git-ignored)
    ├── hypotheses/                  # AQDE persistent KB
    ├── cache/                       # Market data cache
    └── results/                     # Backtest/Monte Carlo outputs
```

---

## Shared Dependencies (Consolidated)

### Core Dependencies (Required — Always Installed)

```txt
# quant-math/requirements.txt
numpy>=1.24.0
pandas>=2.0.0
ccxt>=4.0.0
pytest>=7.4.0
python-dateutil>=2.8.2
pytz>=2023.3
tqdm>=4.66.0
```

### Optional Extras (Install as needed)

```txt
# quant-math/requirements.txt [extras]
[scientific]
scipy>=1.11.0
scikit-learn>=1.3.0
statsmodels>=0.14.0
arch>=6.2.0
pykalman>=0.9.7
pywavelets>=1.4.0

[portfolio]
cvxpy>=1.4.0

[backtesting]
vectorbt>=0.26.0
backtrader>=1.9.78

[database]
psycopg2-binary>=2.9.0

[visualization]
matplotlib>=3.8.0
plotly>=5.18.0

[api]
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
python-multipart>=0.0.6

[dev]
pytest-cov>=4.1.0
pytest-mock>=3.12.0
jupyter>=1.0.0
notebook>=7.0.0
```

---

## Quant-Math → AQDE → Quant-Math Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        QUANT-MATH CORE (quant_math/)                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ backtesting  │ │ monte_carlo  │ │ expectation  │ │ risk/              │  │
│  │ Backtester   │ │ Simulator    │ │ Calculator   │ │ PositionSizer      │  │
│  │ Performance  │ │ Bootstrap    │ │ Drawdown     │ │ StopLoss           │  │
│  │ Metrics      │ │ VaR/ES       │ │ Sharpe/Sort. │ │ Kelly              │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬───────────┘  │
│         │                │                │                 │              │
│         └────────────────┴────────────────┴─────────────────┘              │
│                              │                                             │
│                              ▼                                             │
│                    ┌─────────────────────┐                                │
│                    │  Shared Protocols   │  (core/protocols.py)           │
│                    │ DataProvider        │                                │
│                    │ KnowledgeBase       │                                │
│                    │ BacktestEngine      │                                │
│                    │ MonteCarloEngine    │                                │
│                    │ StatisticalValidator│                                │
│                    │ RiskManager         │                                │
│                    └──────────┬──────────┘                                │
└──────────────────────────────│────────────────────────────────────────────┘
                               │
                               ▼ (implements ALL ports via thin wrappers)
┌─────────────────────────────────────────────────────────────────────────────┐
│                  AQDE MODULE (quant_math.autonomous_research)              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ResearchManager                                                     │   │
│  │  ├─ knowledge_base    → QuantMathAdapter (wraps KB)                │   │
│  │  ├─ backtest_engine   → QuantMathAdapter (wraps Backtester)        │   │
│  │  ├─ monte_carlo_engine→ QuantMathAdapter (wraps Simulator)         │   │
│  │  ├─ statistical_valid.→ QuantMathAdapter (wraps SharpeMetrics)     │   │
│  │  └─ risk_manager      → QuantMathAdapter (wraps RiskManager)       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                             │
│                              ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Pipeline (5 phases)                                                 │   │
│  │  1. Hypothesis Generation  → STRATEGY_CATALOGUE + generators        │   │
│  │  2. Validation             → StatisticalValidator (Quant-Math)      │   │
│  │  3. Backtesting            → BacktestEngine (Quant-Math)            │   │
│  │  4. Monte Carlo            → MonteCarloEngine (Quant-Math)          │   │
│  │  5. Scoring & Learning     → All metrics combined                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                             │
│                              ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Knowledge Base (persistent)                                         │   │
│  │  → JSONL/SQLite storage (autonomous_research/data/hypotheses/)     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼ (results, hypotheses, metrics)
                    ┌─────────────────────┐
                    │  Quant-Math Core    │  ← Receives results for further
                    │  (analysis, viz,    │     optimization, reporting
                    │   reporting)        │
                    └─────────────────────┘
```

---

## Port Implementations (QuantMathAdapter)

The `QuantMathAdapter` becomes a **thin façade** implementing all 6 AQDE ports by delegating to Quant-Math modules:

```python
# quant_math/autonomous_research/adapters/quant_math_adapter.py (NEW)

class QuantMathAdapter:
    """Thin adapter implementing ALL AQDE ports via Quant-Math core."""

    def __init__(self, exchange_id: str = "binance",
                 knowledge_base_path: str = "data/hypotheses"):
        # Knowledge Base (AQDE-owned, persistent)
        self.knowledge_base = HypothesisKnowledgeBase(storage_path=knowledge_base_path)

        # Quant-Math Core Engines
        from quant_math.backtesting import Backtester, PerformanceMetrics
        from quant_math.monte_carlo import MonteCarloSimulator
        from quant_math.expectation import SharpeMetrics, StatisticalTests
        from quant_math.risk import RiskManager
        from quant_math.data_acquisition.data_sources.exchanges import ExchangeAPI
        from quant_math.order_management import OrderManager

        self.exchange = ExchangeAPI(exchange_id)
        self.backtester = Backtester()
        self.metrics = PerformanceMetrics()
        self.monte_carlo = MonteCarloSimulator()
        self.sharpe = SharpeMetrics()
        self.stats = StatisticalTests()
        self.risk_manager = RiskManager()
        self.order_manager = OrderManager()

    # ── DataProvider ─────────────────────────────────────────────
    def fetch_market_data(self, symbol, start_date, end_date, timeframe='1h'):
        return self.exchange.fetch_ohlcv(...)  # → DataFrame

    # ── KnowledgeBase ────────────────────────────────────────────
    def store_hypothesis(self, hypothesis): ...
    def retrieve_hypothesis(self, hypothesis_id): ...
    def search_hypotheses(self, criteria): ...
    def update_hypothesis(self, hypothesis_id, updates): ...
    # ... (delegate to self.knowledge_base)

    # ── BacktestEngine ───────────────────────────────────────────
    def run_backtest(self, hypothesis, data, initial_capital=100000):
        # Convert hypothesis → strategy_func + price_dict
        # Call self.backtester.run_backtest(...)
        return result  # BacktestResult

    # ── MonteCarloEngine ─────────────────────────────────────────
    def simulate_distribution(self, result, n_iterations=1000):
        return self.monte_carlo.bootstrap(result.trades, n_iterations)

    # ── StatisticalValidator ─────────────────────────────────────
    def calculate_win_rate(self, trades): ...
    def test_significance(self, hypothesis_id, result): ...
    def calculate_sharpe_ratio(self, returns, ...): ...
    def calculate_sortino_ratio(self, returns, ...): ...

    # ── RiskManager ──────────────────────────────────────────────
    def check_position_size(self, hypothesis_id, size, account_value): ...
    def check_drawdown_limit(self, current_drawdown, limit): ...
    def check_sharpe_threshold(self, sharpe_ratio, threshold): ...
```

---

## Action Plan (Implementation Steps)

### Phase 1: Cleanup (Safe, No Behavioral Changes)

| Step | Action | Files Affected | Risk |
|------|--------|----------------|------|
| 1.1 | Remove `backtest/` directory | `backtest/__init__.py` | None (empty) |
| 1.2 | Remove root `risk_management.py` | Root file | None (conflicts with package) |
| 1.3 | Remove broken AQDE adapters | `adapters/monte_carlo_engine.py`, `adapters/statistical_validator.py`, `adapters/backtest_engine.py`, `core/backtest_engine.py` | None (not used in main flow) |
| 1.4 | Remove unused API | `api/main.py`, `api/__init__.py` | None (broken, not in main flow) |
| 1.5 | Fix/remove orphaned Quant-Math modules | `pca_analysis/__init__.py` | Low |
| 1.6 | Archive stale artifacts | `aqde_results.json`, `*.csv`, `*.txt` to `archive/` | None |

### Phase 2: Core Module Consolidation

| Step | Action | Files Created/Modified |
|------|--------|------------------------|
| 2.1 | Create `quant_math/core/` with shared protocols | `core/types.py`, `core/hypothesis.py`, `core/results.py`, `core/messages.py`, `core/protocols.py` |
| 2.2 | Move `Hypothesis`, `StrategyResult`, `MonteCarloResult`, `AgentMessage` from AQDE → `quant_math/core/` | `core/hypothesis.py`, `core/results.py`, `core/messages.py` |
| 2.3 | Create `quant_math/monte_carlo/` module | `monte_carlo/simulator.py`, `monte_carlo/bootstrap.py`, `monte_carlo/risk_metrics.py` (merge from AQDE adapter + risk_management) |
| 2.4 | Create `quant_math/expectation/statistical_tests.py` | Merge AQDE statistical_validator logic + Quant-Math sharpe |
| 2.5 | Create `quant_math/risk/risk_manager.py` | Unified RiskManager port implementation (merge AQDE + Quant-Math) |
| 2.6 | Move `optimization/kelly.py` → `risk/kelly.py` (keep alias) | `risk/kelly.py`, update `optimization/__init__.py` |

### Phase 3: AQDE Restructure

| Step | Action | Files Created/Modified |
|------|--------|------------------------|
| 3.1 | Rename `autonomous-research/` → `quant_math/autonomous_research/` | Directory rename, fix imports |
| 3.2 | Move `aqde_pipeline.py` → `pipeline.py` | Restructure imports |
| 3.3 | Move STRATEGY_CATALOGUE → `strategies/catalogue.py` | Extract signal generators |
| 3.4 | Create `QuantMathAdapter` in `autonomous_research/adapters/` | Single thin adapter |
| 3.5 | Remove `knowledge_manager_stub.py` | Use real `HypothesisKnowledgeBase` |
| 3.6 | Update `ResearchManager` to use Quant-Math core ports | Import from `quant_math.core.protocols` |
| 3.7 | Remove `run_aqde.py` wrapper | Direct import from `quant_math.autonomous_research.pipeline` |

### Phase 4: Configuration & Entry Points

| Step | Action | Files |
|------|--------|-------|
| 4.1 | Consolidate `requirements.txt` (core + extras) | Root `requirements.txt` |
| 4.2 | Create unified `__init__.py` at root | Export all public APIs |
| 4.3 | Add CLI entry point | `console_scripts: aqde = quant_math.autonomous_research.pipeline:main` |
| 4.4 | Move standalone scripts to `scripts/` | Organize by category |

### Phase 5: Testing & Verification

| Step | Action | Verification |
|------|--------|--------------|
| 5.1 | Run `test_integration.py` | All 6 Quant-Math tests pass |
| 5.2 | Run AQDE pipeline dry-run | `python -m quant_math.autonomous_research.pipeline --dry-run` |
| 5.3 | Run AQDE pipeline full | `python -m quant_math.autonomous_research.pipeline --symbol BTCUSDT` |
| 5.4 | Verify no duplicate logic | grep for duplicated class/function names |
| 5.5 | Verify import graph | `python -c "import quant_math; import quant_math.autonomous_research"` |

---

## Verification Checklist

After restructure, **ALL** of these must work without modification:

- [ ] `python test_integration.py` → 6 tests pass
- [ ] `python test_backtest.py` → passes
- [ ] `python -m quant_math.autonomous_research.pipeline --dry-run --strategies ema_crossover` → completes
- [ ] `python -m quant_math.autonomous_research.pipeline --symbol BTCUSDT --days 30` → completes
- [ ] `python -c "from quant_math import Backtester, MonteCarloSimulator, SharpeMetrics, RiskManager; print('OK')"` → works
- [ ] `python -c "from quant_math.autonomous_research import ResearchManager, run_pipeline; print('OK')"` → works
- [ ] No `ImportError` for `scipy`, `sklearn`, `matplotlib` in main flow
- [ ] `knowledge_base` persists hypotheses across runs
- [ ] Agent communication works (5 agents registered)

---

## Migration Notes

### Import Changes Required

| Old Import | New Import |
|------------|------------|
| `from autonomous_research.core.interfaces import Hypothesis` | `from quant_math.core import Hypothesis` |
| `from autonomous_research.adapters import QuantMathAdapter` | `from quant_math.autonomous_research.adapters import QuantMathAdapter` |
| `from autonomous_research.agents import ResearchManager` | `from quant_math.autonomous_research import ResearchManager` |
| `from backtesting import Backtester` | `from quant_math.backtesting import Backtester` |
| `from risk_management import ValueAtRisk` | `from quant_math.risk_management import ValueAtRisk` |

### Backward Compatibility

Add `autonomous_research/` as a **namespace package alias** in `quant_math/__init__.py`:

```python
# quant_math/__init__.py
import sys
import importlib.util

# Allow `import autonomous_research` to work as alias
spec = importlib.util.spec_from_file_location(
    "autonomous_research",
    __file__.replace("__init__.py", "autonomous_research/__init__.py"),
    submodule_search_locations=[__file__.replace("__init__.py", "autonomous_research")],
)
sys.modules["autonomous_research"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules["autonomous_research"])
```

This ensures **zero breaking changes** for any external code.

---

## Appendix: File-by-File Mapping

### AQDE → Quant-Math Core (Duplicates Eliminated)

| AQDE File | Quant-Math Replacement | Status |
|-----------|------------------------|--------|
| `adapters/backtest_engine.py` | `backtesting/backtester.py` | REMOVE adapter |
| `adapters/monte_carlo_engine.py` | `monte_carlo/simulator.py` (NEW) | REMOVE adapter |
| `adapters/statistical_validator.py` | `expectation/sharpe_metrics.py` + `statistical_tests.py` (NEW) | REMOVE adapter |
| `adapters/risk_manager.py` | `risk/risk_manager.py` (NEW) + `risk/position_sizing.py` | REMOVE adapter |
| `core/interfaces.py` → split | `core/protocols.py`, `core/types.py`, `core/hypothesis.py`, `core/results.py`, `core/messages.py` | RESTRUCTURE |

### Quant-Math Orphans (Decide: Fix or Remove)

| Module | Dependencies | Recommendation |
|--------|--------------|----------------|
| `data_processing/` | sklearn | Move to `[scientific]` extra; remove if unused |
| `signal_processing/` | scipy, pywt | Move to `[scientific]` extra; remove if unused |
| `spectral_analysis/` | matplotlib | Move to `[visualization]` extra; remove if unused |
| `pca_analysis/` | missing file | **REMOVE** or fix import |
| `portfolio_construction/` | scipy | Move to `[scientific]` extra |
| `modeling/` | empty | **REMOVE** |
| `volatility/` | empty | **REMOVE** |
| `utils/` | empty | **REMOVE** |

---

*End of ARCHITECTURE_GUIDE.md*
## Riesgo: overshoot del Stop Loss (documentado)

El TP/SL se comprueba una vez por ciclo contra el precio de cierre actual
(vela real Bybit). Entre chequeos el precio puede sobrepasar el nivel, por
lo que el movimiento de cierre real puede exceder el SL teorico
(ej. SL 2.5% -> cierres observados 2.52-2.81%). Es slippage estructural del
diseno, no un bug. Mitigacion futura posible: evaluar high/low intrabar.
