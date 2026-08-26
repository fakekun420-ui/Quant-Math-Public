# QUANT-MATH v1.2.0 — Autonomous Quantitative Research System

Self-improving quantitative trading research system: an AQDE engine generates
market-driven hypotheses, a mathematical gate validates them against **real
Bybit data**, and an unsupervised learning loop (SIS) learns from every closed
operation to continuously improve what gets generated next.

> **v1.2.0** — Burst Scalping mode (margin×leverage, $0.20–$0.60 net target),
> separate burst/classic records, interactive Top-20 asset selector,
> dedicated burst monitor + history, hardened graduation (IC90 + diversity).

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
# Interactive CLI (menu → wizard → orchestrator in background process)
python -m quant_math.cli.main

# Run the full test suite (95 tests across all modules)
python -m pytest tests/ -q

# Refresh the code-graph index after refactors
graphify update .
```

## CLI Features

| Menu option | What it does |
|---|---|
| Iniciar Quant-Math | Config wizard with Top-20 asset selector → orchestrator in background |
| Detener investigación | Graceful stop (positions are preserved) |
| Monitor | Live dashboard (classic or burst): cycles, hypotheses, open/closed ops, wins/losses, MtM + realized PnL split |
| Ver log | Paginated log viewer (quant_math.log or quant_math_burst.log) |
| Historial de operaciones | Permanent trade book with entry/exit prices, PnL USD/%, motivo + summary |
| Iniciar Burst Scalping | Burst wizard: Top-20 selector, margin/leverage config → burst orchestrator |
| Historial Burst | Burst-only trade book with margin/leverage columns (enabled when burst active) |
| Ver log Burst | Burst-only log viewer (enabled when burst active) |

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
| Live Expectancy (PA) | Bayesian shrinkage blend | Realized paper PnL per closed trade (`[exp-refresh]`) | Re-scores hypothesis records after every closure; ranking self-improves toward what actually works |
| Auto-Graduation (PB) | Rolling-window rule | Mean of last N closures | Automatically disables LEARN_MODE when learning succeeds; decision persisted in `graduation.json` |
| Graduation Hardening (O1) | Statistical gate on PB | Window mean must clear IC90 lower bound > 0 with ≥2 distinct families | Prevents lucky-streak graduations; audit fields stored in `graduation.json` |
| Slippage Model (O2) | Adverse-fill simulation | Every paper execution | Entries and exits filled at ±QUANTMATH_SLIPPAGE_PCT against the trader — realistic net PnL |
| Vol-Target Sizing (O6) | Inverse-volatility scaler | Realized per-cycle returns | Post-graduation notional scales x0.5–x2 toward a 2% vol target instead of fixed sizing |
| Burst Scalping (V2) | Margin×leverage sizing | EMA trend + momentum spike + pullback entry | $10 margin × 10× leverage = $100 notional; TP 0.4–0.8% = $0.20–$0.60 net; cooldown 10 cycles, max $50 exposure |

All generation-side learning is **advisory**: it biases *what gets generated*,
never whether a trade happens. PA changes *which ranked candidate is best*
(the gate itself stays sacred); PB only flips the gate back on. Data-starvation
safe: below minimum sample thresholds every learner stays in "collecting" mode.

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
│   ├── orchestrator.py         # Cycle orchestration + dedupe + SIS hook + BurstStateTracker
│   ├── decision_engine/        # Expectancy gate, TP/SL, positions, feedback, burst sizing
│   ├── ml/                     # Prior, feature store, SIS loop, KB reset
│   └── autonomous_research/    # Research manager, adapters, KB backends
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

95 tests, zero warnings: integration workflow, decision-engine gate
behavior + skip-fallback (P1), live-expectancy shrinkage (PA),
hardened auto-graduation IC90+families (O1/PB), adverse-slippage fills
(O2), generative-novelty metric (O4), vol-targeted sizing (O6),
energy-burst & range-pressure families (O7), multi-symbol isolation
(O3), SIS clustering/recommendations, family
feedback buckets, SL 2:1 exactness, position recovery, KB round-trip +
fallback, prior activation thresholds, model-based generator contracts,
burst infrastructure (cooldown, trend filter, exposure, sizing),
burst history/log separation, burst monitor.

## License

MIT

## Disclaimer

Research/paper-trading system. Not financial advice. Trading involves risk.
