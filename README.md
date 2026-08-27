# QUANT-MATH v1.4.0 — Autonomous Quantitative Research System

Self-improving quantitative trading research system: an AQDE engine generates
market-driven hypotheses, a mathematical gate validates them against **real
Bybit data**, and an unsupervised learning loop (SIS) learns from every closed
operation to continuously improve what gets generated next.

> **v1.4.0** — PostgreSQL VM eliminated, JSONL-only KB with atomic upsert,
> stop buttons fixed, realistic $50 defaults, 108 tests.

## How It Works

```
Bybit (real OHLCV)
   │
   ▼
AQDE Runner ── templates + ARIMA/GARCH candidates + adaptive mutations
   │            (feedback from previous backtests; rotation per cycle;
   │             dedupe vs KB with refresh window; parallel per-symbol)
   ▼
Orchestrator ── publish to Knowledge Base (JSONL with atomic upsert)
   │             check_exits runs in parallel with publish (ThreadPool)
   ▼
Decision Engine ── ranked candidates (expectancy DESC, score DESC);
   │                 falls back to next-best candidate when the top one
   │                 already has an open position (P1)
   │                 · expectancy gate (LEARN_MODE can bypass temporarily;
   │                   auto-graduates when the last N closures turn net
   │                   positive — PB)
   │                 · live expectancy: after each closure the record's
   │                   expectancy is re-blended toward realized results with
   │                   Bayesian shrinkage (PA) so ranking self-improves
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
# Interactive CLI (menu → wizard → orchestrator in background)
python -m quant_math.cli.main

# Run the full test suite (108 tests across all modules)
python -m pytest tests/ -q

# Refresh the code-graph index after refactors
graphify update .
```

## CLI Features

| Menu option | What it does |
|---|---|
| Iniciar Quant-Math | Config wizard → classic orchestrator in background |
| Iniciar Burst Scalping | Burst wizard: Top-20 selector, margin/leverage → burst orchestrator |
| Detener Quant-Math | Stop classic mode only |
| Detener Burst | Stop burst mode only |
| Detener ambos | Stop both classic and burst |
| Monitor | Live dashboard: cycles, hypotheses, open/closed ops, wins/losses, MtM + realized PnL split |
| Ver log | Paginated log viewer (classic or burst, auto-selects if only one running) |
| Historial de operaciones | Permanent trade book with entry/exit prices, PnL USD/%, motivo + summary |
| Minimizar (seguir en background) | Shows running PIDs, keeps processes alive after CLI closes |
| Salir | Graceful shutdown of all processes |

- `ESC` navigates back everywhere without stopping background work
- `Ctrl+C` performs full clean shutdown
- Re-entering the CLI detects orphan processes and offers to stop them

## Simultaneous Mode

Both classic and burst modes can run simultaneously from a single CLI session.
Each mode has its own:
- Process and PID file (`runtime/state_{mode}/orchestrator.pid`)
- State directory (`runtime/state/` vs `runtime/state_burst/`)
- Log file (`quant_math.log` vs `quant_math_burst.log`)
- Knowledge base entries (isolated by mode)

When both are running, monitor/log/history ask which mode to display.

## Background Persistence

The orchestrator processes are spawned with `daemon=False` and write PID
files to `runtime/state_{mode}/orchestrator.pid`. This means:
- Closing the CLI does **not** kill background processes
- Re-entering the CLI detects live processes via PID files
- On Android/Termux, `termux-wake-lock` is acquired during cycle execution
  and released during sleep to prevent OS from killing the process

## Resource Optimization

| Optimization | Effect |
|---|---|
| `os.nice(10)` | Lower process priority — doesn't compete with foreground apps |
| Adaptive sleep | Burst mode sleeps 60s when idle (no entries possible) vs 15s active |
| Memory pruning | `performance_history` capped at 500, `all_hypotheses` capped at 200 active |
| Buffered log I/O | 8KB buffers reduce syscalls by ~90% |
| Parallel generation | ThreadPoolExecutor generates + backtests symbols in parallel (up to 3 workers) |
| Parallel exits+publish | `check_exits_all()` runs concurrently with `_publish_to_kb()` |

## Persistence

- **Knowledge Base**: Pure JSONL with atomic upsert (no external dependencies).
  - `JSONLKnowledgeBase` reads → merges → writes atomically per file, thread-safe via per-file locks.
  - In-memory index for fast search by status, symbol, or combined filters.
  - `KBPersistence` facade provides a unified API; legacy `PostgreSQLKnowledgeBase` is an alias.
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
| Live Expectancy (PA) | Bayesian shrinkage blend | Realized paper PnL per closed trade (`[exp-refresh]`) | Re-scores hypothesis records after every closure; ranking self-improves toward what actually works |
| Auto-Graduation (PB) | Rolling-window rule | Mean of last N closures | Automatically disables LEARN_MODE when learning succeeds; decision persisted in `graduation.json` |
| Graduation Hardening (O1) | Statistical gate on PB | Window mean must clear IC90 lower bound > 0 with ≥2 distinct families | Prevents lucky-streak graduations; audit fields stored in `graduation.json` |
| Slippage Model (O2) | Adverse-fill simulation | Every paper execution | Entries and exits filled at ±QUANTMATH_SLIPPAGE_PCT against the trader — realistic net PnL |
| Vol-Target Sizing (O6) | Inverse-volatility scaler | Realized per-cycle returns | Post-graduation notional scales x0.5–x2 toward a 2% vol target instead of fixed sizing |
| Burst Scalping (V2) | Margin×leverage sizing | EMA trend + momentum spike + pullback entry | $1 margin × 5× leverage = $5 notional; TP 25% = $1.25 net; cooldown 10 cycles |
| Parallel Generation (V3) | ThreadPool per-symbol | Cross-symbol parallelism | Up to 3 symbols generate + backtest simultaneously; check_exits overlaps with KB publish |
| Resource Optimization (V3) | Adaptive sleep + pruning | Idle detection, memory caps | Burst sleeps 60s when idle; performance_history capped at 500; os.nice(10) for battery savings |

All generation-side learning is **advisory**: it biases *what gets generated*,
never whether a trade happens. PA changes *which ranked candidate is best*
(the gate itself stays sacred); PB only flips the gate back on. Data-starvation
safe: below minimum sample thresholds every learner stays in "collecting" mode.

## Environment Flags

| Flag | Default | Purpose |
|---|---|---|
| `QUANTMATH_LEARN_MODE` | `0` (CLI sets `1`) | Temporarily bypass expectancy gate to collect negative-outcome data |
| `QUANTMATH_SIG_REFRESH_CYCLES` | `5` | Cycles before a known hypothesis signature is re-backtested |
| `QUANTMATH_SIS_MIN_ROWS` | `30` | Closed ops required before SIS activates |
| `QUANTMATH_ML_MIN_RECORDS` | `100` | Records required before the prior activates |
| `QUANTMATH_AUTO_GRADUATE` | `1` | Enable PB auto-graduation of LEARN_MODE (`0` to disable) |
| `QUANTMATH_GRAD_WINDOW` | `30` | Closures in the rolling window that must average positive to graduate |
| `QUANTMATH_GRAD_MIN_FAMILIES` | `2` | O1: distinct families required in the graduation window |
| `QUANTMATH_SLIPPAGE_PCT` | `0.0005` | O2: adverse fill slippage per side applied to paper executions (`0` disables) |
| `QUANTMATH_VOL_TARGET` | `1` (post-graduation) | O6: volatility-targeted position sizing once the gate is active (`0` disables) |
| `QUANTMATH_VOL_TARGET_PCT` | `2.0` | O6: target per-cycle return volatility (%) the sizer aims for; multiplier clamped x0.5–x2 |
| `QUANTMATH_BURST_SLIPPAGE_PCT` | `0.0003` | V2: burst-mode adverse fill slippage per side (0.03%) |
| `QUANTMATH_BURST_GRAD_WINDOW` | `100` | V2: burst graduation window (closures) |
| `QUANTMATH_BURST_GRAD_MIN_NET` | `0.05` | V2: burst graduation min mean net % per trade |
| `QUANTMATH_BURST_MAX_ENTRIES` | `5` | V2: max burst entries per cycle |
| `QUANTMATH_BURST_COOLDOWN_CYCLES` | `10` | V2: cooldown cycles between burst entries |

## Data Policy

Every candle, ticker and price in the pipeline comes from **real Bybit
endpoints**. The legacy synthetic-data generator exists solely for offline
unit tests behind `dry_run AND NOT force_real_data` — unreachable from the
orchestrator (hardcoded `force_real_data=True`). Monte-Carlo randomness only
resamples already-real trade PnLs (statistical bootstrap).

## Project Structure (real)

```
├── aqde_runner.py              # AQDE engine: generation + backtesting
├── model_based_generator.py    # ARIMA/GARCH hypothesis candidates + burst template
├── quant_math/
│   ├── cli/main.py             # Interactive CLI (menu/wizard/monitor/history/burst)
│   ├── orchestrator.py         # Cycle orchestration + dedupe + SIS hook + BurstStateTracker + stop button
│   ├── decision_engine/        # Expectancy gate, TP/SL, positions, feedback, burst sizing
│   ├── ml/                     # Prior, feature store, SIS loop, KB reset
│   └── autonomous_research/    # Research manager, adapters, JSONL KB backend
├── runtime/state/              # Classic: positions, ledger, counters, stats
├── runtime/state_burst/        # Burst: isolated state (positions, ledger, burst_state)
├── runtime/hypotheses.jsonl    # Classic KB mirror (fallback seed)
├── runtime/hypotheses_burst.jsonl  # Burst KB mirror
├── quant_math.log              # Classic orchestrator log
├── quant_math_burst.log        # Burst orchestrator log
├── tools/                      # Migration & maintenance utilities
├── tests/                      # Behavior suites (gate, SIS, risk, KB, burst…)
├── */test_standalone.py        # Per-module test scripts
└── graphify-out/               # Code knowledge graph (Graphify index)
```

Legacy planning documents (`ARCHITECTURE.md`, `IMPLEMENTATION_STATUS.md`,
`ARCHITECTURE_REUSE_REPORT.md`, `SYSTEM_DEPENDENCY_MAP.md`) describe earlier
visions and module checklists; `ARCHITECTURE_GUIDE.md` is partially updated.

## Testing

108 tests, zero warnings: integration workflow, decision-engine gate
behavior + skip-fallback (P1), live-expectancy shrinkage (PA),
hardened auto-graduation IC90+families (O1/PB), adverse-slippage fills
(O2), generative-novelty metric (O4), vol-targeted sizing (O6),
energy-burst & range-pressure families (O7), multi-symbol isolation
(O3), SIS clustering/recommendations, family
feedback buckets, SL 2:1 exactness, position recovery, KB round-trip +
fallback (JSONL atomic upsert, search by status/symbol/combined),
prior activation thresholds, model-based generator contracts,
burst infrastructure (cooldown, trend filter, exposure, sizing),
burst history/log separation, burst monitor,
two-pass MtM fix, multi-process RuntimeState, memory pruning.

## License

MIT

## Disclaimer

Research/paper-trading system. Not financial advice. Trading involves risk.
