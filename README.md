# QUANT-MATH v1.0.1 — Autonomous Quantitative Research System

Self-improving quantitative trading research system: an AQDE engine generates
market-driven hypotheses, a mathematical gate validates them against **real
Bybit data**, and an unsupervised learning loop (SIS) learns from every closed
operation to continuously improve what gets generated next.

> **v1.0.1** — SIS unsupervised learning over operations, family-level AQDE
> feedback, persistent PostgreSQL knowledge base (qcow2 microVM), SL 2:1 risk
> rule, intra-cycle market-data cache, CLI operations history.

## How It Works

```
Bybit (real OHLCV)
   │
   ▼
AQDE Runner ── templates + ARIMA/GARCH candidates + adaptive mutations
   │            (feedback from previous backtests; rotation per cycle;
   │             dedupe vs KB with refresh window)
   ▼
Orchestrator ── publish to Knowledge Base (PostgreSQL ⇄ JSONL fallback)
   │
   ▼
Decision Engine ── expectancy gate (LEARN_MODE can bypass temporarily)
   │                 · TP = entry ± take_profit_pct
   │                 · SL = take_profit_pct / 2  (risk ratio 2:1, mandatory)
   │                 · checked each cycle against REAL close prices
   ▼
Paper executions ── permanent append-only ledger (paper_executions.jsonl)
   │                  closures recorded with motivo_cierre = tp/sl/manual
   ▼
SIS Unsupervised Learning ── KMeans clustering of closed trades,
                             regime × family performance tables,
                             losing-streak detector → exploration bursts
   │
   └──► feeds back into generation priorities (advisory only)
```

**The decision gate is sacred**: no ML component can open a trade. Entry
requires each hypothesis's own real backtested `expectancy > 0`
(temporarily bypassable via `QUANTMATH_LEARN_MODE=1` for deliberate
loss-collection experiments, paper-only).

## Quick Start

```bash
# Interactive CLI (menu → wizard → orchestrator in background process)
python -m quant_math.cli.main

# Run the full test suite (58+ tests across all modules)
python -m pytest test_integration.py tests/ \
    algo_trading/test_standalone.py backtesting/test_standalone.py \
    ml_quant/test_standalone.py order_management/test_standalone.py \
    portfolio_construction/test_standalone.py regime_detection/test_standalone.py \
    risk_management/test_standalone.py

# Refresh the code-graph index after refactors
graphify update .
```

## CLI Features

| Menu option | What it does |
|---|---|
| Iniciar Quant-Math | Config wizard → orchestrator in background process |
| Detener investigación | Graceful stop (positions are preserved) |
| Monitor | Live dashboard: cycles, hypotheses, open/closed ops, wins/losses, MtM + realized PnL split, legacy PnL separated |
| Ver log | Paginated log viewer |
| Historial de operaciones | Permanent trade book: paginated closures with entry/exit prices, PnL USD/%, motivo (tp/sl/manual) + summary |

`ESC` navigates back everywhere without stopping background work;
`Ctrl+C` performs full clean shutdown.

## Persistence

- **Knowledge Base**: PostgreSQL (microVM with persistent 4 GB qcow2 disk,
  port-forwarded to `127.0.0.1:15432`) with automatic JSONL fallback.
  - The CLI auto-boots the VM if unreachable (`QUANTMATH_PG_BOOT_TIMEOUT`,
    default 480 s).
  - On first connect an empty table is seeded automatically from the JSONL
    mirror — server restarts lose nothing.
  - Every PostgreSQL access is wrapped in try/except: if the DB is down the
    system keeps running on JSONL and logs the fallback explicitly.
- **Operations ledger**: `runtime/state/paper_executions.jsonl` is
  append-only and never truncated — it is the permanent trade book.
- **Open positions**: recovered automatically on restart
  (`[posiciones] recuperadas N...`) and monitored for TP/SL as if the
  system never stopped.

## Machine Learning Systems

| System | Type | Learns from | Effect |
|---|---|---|---|
| Hypothesis Prior | Supervised (shrunk rates) | Historical backtest outcomes (900+ records) | Reorders candidate generation |
| SIS Unsupervised | KMeans + regime tables | Closed paper operations (post-integration cutoff) | Family/regime priority for generation; exploration bursts on losing streaks |
| Model-Based Generator | ARIMA(1,1,0) / GARCH(1,1) | Real price series at generation time | Adds executable candidates (breakout/rsi/macd variants) chosen by regime |
| Adaptive Mutations | Evolutionary | Backtest results (best/worst strategies) | Parameter mutations toward winners, counter-strategies vs losers |

All learning is **advisory**: it biases *what gets generated*, never whether
a trade happens. Data-starvation safe: below minimum sample thresholds every
learner stays in "collecting" mode.

## Environment Flags

| Flag | Default | Purpose |
|---|---|---|
| `QUANTMATH_LEARN_MODE` | `0` (CLI sets `1`) | Temporarily bypass expectancy gate to collect negative-outcome data |
| `QUANTMATH_PG_DISABLE` | unset | Force JSONL-only knowledge base |
| `QUANTMATH_PG_DSN` | localhost:15432 | PostgreSQL connection string |
| `QUANTMATH_PG_BOOT_TIMEOUT` | `480` | Seconds to wait for VM auto-boot |
| `QUANTMATH_VM_STOP_ON_EXIT` | ask | Stop PG VM when leaving the CLI (`1`/`0`) |
| `QUANTMATH_SIG_REFRESH_CYCLES` | `5` | Cycles before a known hypothesis signature is re-backtested |
| `QUANTMATH_SIS_MIN_ROWS` | `30` | Closed ops required before SIS activates |
| `QUANTMATH_ML_MIN_RECORDS` | `100` | Records required before the prior activates |

## Data Policy

Every candle, ticker and price in the pipeline comes from **real Bybit
endpoints**. The legacy synthetic-data generator exists solely for offline
unit tests behind `dry_run AND NOT force_real_data` — unreachable from the
orchestrator (hardcoded `force_real_data=True`). Monte-Carlo randomness only
resamples already-real trade PnLs (statistical bootstrap).

## Project Structure (real)

```
├── aqde_runner.py              # AQDE engine: generation + backtesting
├── model_based_generator.py    # ARIMA/GARCH hypothesis candidates
├── quant_math/
│   ├── cli/main.py             # Interactive CLI (menu/wizard/monitor/history)
│   ├── orchestrator.py         # Cycle orchestration + dedupe + SIS hook
│   ├── decision_engine/        # Expectancy gate, TP/SL, positions, feedback
│   ├── ml/                     # Prior, feature store, SIS loop, KB reset
│   └── autonomous_research/    # Research manager, adapters, KB backends
├── runtime/state/              # Positions, ledger, counters, stats
├── runtime/hypotheses.jsonl    # KB mirror (fallback seed)
├── tools/                      # Migration & maintenance utilities
├── tests/                      # Behavior suites (gate, SIS, risk, KB…)
├── */test_standalone.py        # Per-module test scripts
└── graphify-out/               # Code knowledge graph (Graphify index)
```

Legacy planning documents (`ARCHITECTURE.md`, `IMPLEMENTATION_STATUS.md`,
`ARCHITECTURE_REUSE_REPORT.md`, `SYSTEM_DEPENDENCY_MAP.md`) describe earlier
visions and module checklists; `ARCHITECTURE_GUIDE.md` is partially updated.

## Testing

58 tests, zero warnings: integration workflow, decision-engine gate
behavior, SIS clustering/recommendations, family feedback buckets,
SL 2:1 exactness, position recovery, KB round-trip + fallback, prior
activation thresholds, model-based generator contracts.

## License

MIT

## Disclaimer

Research/paper-trading system. Not financial advice. Trading involves risk.
