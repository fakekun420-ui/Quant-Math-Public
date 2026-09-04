"""
Quant-Math Orchestrator.

Connects the full discovery -> decision -> feedback cycle:

    AQDE hypothesis generation (aqde_runner.AQDERunner)
        -> backtest on REAL Bybit data (never synthetic)
        -> JSONL Knowledge Base
        -> DecisionEngine.decide() per configured symbol
        -> paper trade execution on entry signals
        -> feedback to AQDE (delivered by DecisionEngine at min_paper_trades)

dry_run controls ONLY paper vs live execution mode. Market data is ALWAYS
real exchange data in every mode.
"""

from __future__ import annotations

import json
import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from quant_math.decision_engine import DecisionEngine
from quant_math.risk.circuit_breaker import DailyGuard, utc_day_start_ts

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Explicit configuration. Required fields have NO hidden defaults."""

    # Universe & market data
    symbols: List[str]
    timeframe: str                          # e.g. '1h', '4h'
    lookback_days: int                      # backtest window in days

    # Capital & risk
    initial_capital: float                  # total paper/live capital (USD)
    entry_pct: float                        # fraction of capital per entry (0-1]
    take_profit_pct: float                  # TP distance as fraction (e.g. 0.02)

    # Cycle behaviour (explicit; mirrors DecisionEngine contract)
    min_paper_trades: int                   # feedback gate — must match intent (3)
    hypotheses_per_cycle: int               # N new hypotheses generated per cycle

    # Infrastructure
    kb_path: str                            # JSONL shared with DecisionEngine
    state_dir: str                          # DecisionEngine state directory
    interval_seconds: int = 3600            # period between continuous cycles
    exchange_id: str = "bybit"              # REAL data source, always
    dry_run: bool = True                    # True=paper trading ONLY (no live path yet)
    use_postgres: bool = False               # KB storage: always JSONL (PG removed)
    mode: str = "classic"                   # "classic" or "burst"

    # Burst-mode specifics (only used when mode == "burst")
    burst_margin: float = 10.0              # USD margin per burst entry
    burst_leverage: int = 10                # leverage multiplier (1-20)

    # Classic-mode leverage (1 = no leverage)
    leverage: int = 1                       # leverage multiplier for classic mode

    # Circuit breaker (Fase 1b) — enforced in run_cycle before new entries
    max_daily_loss_usd: float = 2.5         # block entries rest of UTC day
    max_open_positions: int = 5             # block entries at/above this count
    drawdown_limit: float = 0.2             # block entries past this drawdown
    max_position_pct: float = 0.2           # max margin per entry vs account

    # Live-trading path (Fase 2-4)
    shadow_live: bool = False               # log shadow_orders.jsonl intent
    testnet: bool = True                    # live orders only allowed on testnet

    def __post_init__(self):
        if not self.symbols:
            raise ValueError("symbols no puede estar vacío")
        if not 0 < self.entry_pct <= 1:
            raise ValueError(f"entry_pct debe estar en (0, 1], recibido {self.entry_pct}")
        if self.take_profit_pct <= 0:
            raise ValueError(f"take_profit_pct debe ser > 0, recibido {self.take_profit_pct}")
        if self.min_paper_trades < 1:
            raise ValueError(f"min_paper_trades inválido: {self.min_paper_trades}")
        if self.hypotheses_per_cycle < 1:
            raise ValueError(f"hypotheses_per_cycle inválido: {self.hypotheses_per_cycle}")
        if self.mode not in ("classic", "burst"):
            raise ValueError(f"mode debe ser 'classic' o 'burst', recibido '{self.mode}'")
        # Circuit-breaker sanity
        if self.max_daily_loss_usd < 0:
            raise ValueError("max_daily_loss_usd debe ser >= 0")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions debe ser >= 1")
        if not 0 < self.drawdown_limit <= 1:
            raise ValueError("drawdown_limit debe estar en (0, 1]")
        if not 0 < self.max_position_pct <= 1:
            raise ValueError("max_position_pct debe estar en (0, 1]")
        if self.dry_run is False:
            # Fase 3: testnet live OK con API keys.
            # Fase 4: mainnet exige acción explícita del operador:
            #   QUANTMATH_ALLOW_MAINNET=1 en el entorno + doble confirmación
            #   en el wizard. Sin eso, bloqueado por diseño.
            from data_acquisition.data_sources.exchanges import api_keys_present
            if not api_keys_present():
                raise RuntimeError(
                    "dry_run=False requiere BYBIT_API_KEY y BYBIT_API_SECRET "
                    "en .env (los datos son SIEMPRE reales; dry_run solo "
                    "controla ejecución)"
                )
            if not self.testnet and os.environ.get(
                    "QUANTMATH_ALLOW_MAINNET") != "1":
                raise NotImplementedError(
                    "mainnet bloqueado por diseño: exporta "
                    "QUANTMATH_ALLOW_MAINNET=1 y confirma dos veces en el "
                    "wizard para operar con dinero real"
                )
        # Burst-mode constraints — dynamic per-asset max (BTC 150, SOL 100, etc.)
        # Wizard already validates against Bybit max via get_max_leverage(); here we
        # only enforce lower bound and absolute Bybit ceiling 150.
        if self.mode == "burst":
            self.interval_seconds = min(self.interval_seconds, 15)
            self.burst_margin = max(1.0, self.burst_margin)
            self.burst_leverage = max(1, min(150, int(self.burst_leverage)))
            self.take_profit_pct = max(0.02, min(0.50, self.take_profit_pct))
        # Classic leverage validation — same 150 ceiling (Bybit max for BTC/ETH)
        self.leverage = max(1, min(150, int(self.leverage)))


# ---------------------------------------------------------------------------
# Burst state tracker (V2 B3)
# ---------------------------------------------------------------------------

import dataclasses as _dc


@_dc.dataclass
class _BurstState:
    """Estado persistente de la ráfaga burst."""
    entries_this_cycle: int = 0
    last_entry_cycle: int = 0
    consecutive_losses: int = 0
    total_entries: int = 0
    total_closures: int = 0
    wins: int = 0
    losses: int = 0


class BurstStateTracker:
    """Maneja cooldown, max entries, y streak de burst."""

    MAX_ENTRIES_PER_CYCLE = 5
    COOLDOWN_CYCLES = 10
    MAX_EXPOSURE_USD = 50.0  # 5 x $10 margin

    def __init__(self, state_dir: str):
        self.path = os.path.join(state_dir, "burst_state.json")
        self.state = self._load()

    def _load(self) -> _BurstState:
        if os.path.exists(self.path):
            try:
                with open(self.path) as fh:
                    d = json.load(fh)
                return _BurstState(**{k: d.get(k, 0)
                                      for k in _BurstState.__dataclass_fields__})
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        return _BurstState()

    def _save(self):
        with open(self.path, "w") as fh:
            json.dump(_dc.asdict(self.state), fh)

    def can_enter(self, current_cycle: int) -> bool:
        if self.state.entries_this_cycle >= self.MAX_ENTRIES_PER_CYCLE:
            return False
        if current_cycle - self.state.last_entry_cycle < self.COOLDOWN_CYCLES:
            return False
        return True

    def register_entry(self, current_cycle: int):
        self.state.entries_this_cycle += 1
        self.state.last_entry_cycle = current_cycle
        self.state.total_entries += 1
        self._save()

    def register_closure(self, pnl: float):
        self.state.total_closures += 1
        if pnl > 0:
            self.state.wins += 1
            self.state.consecutive_losses = 0
        else:
            self.state.losses += 1
            self.state.consecutive_losses += 1
        self._save()

    def reset_cycle(self):
        self.state.entries_this_cycle = 0
        self._save()

    def cooldown_remaining(self, current_cycle: int) -> int:
        elapsed = current_cycle - self.state.last_entry_cycle
        return max(0, self.COOLDOWN_CYCLES - elapsed)

    def stats_dict(self, current_cycle: int) -> Dict:
        s = self.state
        win_rate = (s.wins / s.total_closures * 100
                    if s.total_closures > 0 else 0.0)
        return {
            "entries_this_cycle": s.entries_this_cycle,
            "total_entries": s.total_entries,
            "total_closures": s.total_closures,
            "wins": s.wins,
            "losses": s.losses,
            "win_rate": win_rate,
            "consecutive_losses": s.consecutive_losses,
            "cooldown_remaining": self.cooldown_remaining(current_cycle),
        }


class Orchestrator:
    """Continuous generation -> decision -> feedback loop."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._stop_requested = False
        self._build_runner()
        self.engine = self._build_engine()
        self.cycle_count = 0
        self._runner_lock = threading.Lock()  # protects runner.all_hypotheses
        # V2 B3: burst state tracker (only for burst mode)
        self.burst_tracker = (BurstStateTracker(config.state_dir)
                              if config.mode == "burst" else None)
        # Reset cooldown from previous sessions — cycle_count starts at 0
        # so last_entry_cycle from a prior session creates negative elapsed
        if self.burst_tracker and self.burst_tracker.state.last_entry_cycle > 0:
            self.burst_tracker.state.last_entry_cycle = 0
            self.burst_tracker._save()
        # Fase 1b: circuit breaker (persistent daily guard per mode)
        self.guard = DailyGuard(
            config.state_dir,
            max_daily_loss_usd=config.max_daily_loss_usd,
            max_open_positions=config.max_open_positions,
            drawdown_limit=config.drawdown_limit,
        )
        self._risk_manager = None  # lazy RiskManager (margin checks)
        self._last_realized_total = 0.0
        # Runtime stats consumed by external monitors (CLI)
        self.stats = {
            "state": "RUNNING",
            "mode": config.mode,
            "cycles_completed": 0,
            "hypotheses_generated": 0,
            "hypotheses_evaluated": 0,
            "signals": 0,
            "no_entry": 0,
            "skipped_position": 0,
            "paper_trades_taken": 0,
            "started_at": time.time(),
            "last_cycle_at": None,
            "risk_halt": None,
            "realized_today": 0.0,
            "realized_total": 0.0,
        }
        self.stats_path = os.path.join(self.config.state_dir, "runtime_stats.json")
        self._write_stats()
        # Fase 2: validate live access once at startup (warn-only).
        # Paper trading proceeds regardless; shadow records flag validated.
        self._live_validated = (
            self._validate_live_access() if config.shadow_live else False
        )

    def _write_stats(self):
        try:
            os.makedirs(self.config.state_dir, exist_ok=True)
            kb_backend = getattr(getattr(self, "engine", None),
                                 "storage_mode", "jsonl")
            with open(self.stats_path, "w", encoding="utf-8") as fh:
                json.dump({**self.stats,
                           "config": {
                               "symbols": self.config.symbols,
                               "initial_capital": self.config.initial_capital,
                               "entry_pct": self.config.entry_pct,
                               "timeframe": self.config.timeframe,
                               "take_profit_pct": self.config.take_profit_pct,
                               "stop_loss_pct": self.config.take_profit_pct / 2,
                               "lookback_days": self.config.lookback_days,
                               "min_paper_trades": self.config.min_paper_trades,
                               "hypotheses_per_cycle": self.config.hypotheses_per_cycle,
                               "exchange_id": self.config.exchange_id,
                               "mode": "paper" if self.config.dry_run else "live",
                               "kb_backend": kb_backend,
                           }}, fh, ensure_ascii=False, indent=2)
        except OSError:
            logger.warning("No se pudo escribir runtime_stats.json")

    def mark_stopped(self):
        self.stats["state"] = "STOPPED"
        self._write_stats()

    # ------------------------------------------------------------------
    # Component wiring
    # ------------------------------------------------------------------

    def _build_runner(self):
        from aqde_runner import AQDERunner
        self.runner = AQDERunner(
            exchange_id=self.config.exchange_id,
            timeframe=self.config.timeframe,
            lookback_days=self.config.lookback_days,
            dry_run=self.config.dry_run,
            force_real_data=True,
            hypothesis_ranker=self._rank_hypotheses,
        )

    def _rank_hypotheses(self, templates: List[Dict], symbol: str) -> List[Dict]:
        """Advisory ML reordering of candidate hypotheses (gate untouched)."""
        try:
            from quant_math.ml.hypothesis_prior import build_prior_from_kb
            top_n = self.config.hypotheses_per_cycle
            prior = build_prior_from_kb(self.config.kb_path)
            ordered, info = prior.rank_templates(templates, symbol, top_n)
            print(f"  [ml-prior] modo={info['mode']} registros={info['total']} "
                  f"rate_global={info['global_rate']} "
                  f"reordenado={info['reordered']}")
        except Exception as exc:
            logger.warning("[ml-prior] fallo (%s); orden original", exc)
            ordered = templates

        # SIS no supervisado: refuerza familias con exito historico en el
        # regimen actual; nunca altera el gate.
        try:
            from quant_math.ml.regime_learning import load_loop
            loop = load_loop(self.config.kb_path, self.config.state_dir)
            s = loop.summary()
            regime = None
            for t in ordered:
                r = (t.get("parameters") or {}).get("_regime")
                if r:
                    regime = r
                    break
            fams = loop.rank_families(symbol, regime)
            if fams and loop.mode == "active":
                def prio(t):
                    st = str(getattr(t.get("strategy_type"), "value",
                                     t.get("strategy_type", "")))
                    for i, f in enumerate(fams):
                        if f in st:
                            return i
                    return len(fams)
                boosted = sorted(enumerate(ordered),
                                 key=lambda kv: (prio(kv[1]), kv[0]))
                ordered = [t for _, t in boosted]
                print(f"[sis] modo={s['mode']} ops={s['rows']} familias="
                      f"{fams[:3]} reordenado_advisory=True")
            else:
                print(f"[sis] modo={s['mode']} ops={s['rows']} (recolectando)")
            self._explore_burst = (
                loop.should_explore() if loop.mode == "active" else False)
        except Exception as exc:
            logger.warning("[sis] fallo (%s); sin boost", exc)
            self._explore_burst = False
        return ordered

    def _build_engine(self) -> DecisionEngine:
        return DecisionEngine(
            symbols=self.config.symbols,
            kb_path=self.config.kb_path,
            state_dir=self.config.state_dir,
            exchange_id=self.config.exchange_id,
            timeframe=self.config.timeframe,
            min_paper_trades=self.config.min_paper_trades,
            use_postgres=self.config.use_postgres,
            take_profit_pct=self.config.take_profit_pct,
            mode=self.config.mode,
            burst_margin=self.config.burst_margin,
            burst_leverage=self.config.burst_leverage,
        )

    # ------------------------------------------------------------------
    # Stage 1: hypothesis generation + backtest on REAL data
    # ------------------------------------------------------------------

    def _generate_and_backtest(self) -> List[Dict]:
        """Generate N hypotheses across configured symbols and backtest them."""
        cycle_generated = 0
        cycle_fresh = 0
        new_records = []
        symbols = self.config.symbols
        n = self.config.hypotheses_per_cycle

        # Firmas ya publicadas en el KB: evita regenerar la misma hipotesis
        # identica ciclo tras ciclo (mismo tipo+simbolo+parametros).
        import json as _json
        # Firma -> ultimo ciclo publicado. Una firma conocida se puede
        # re-backtestear cada K ciclos para refrescar expectancy con datos
        # nuevos (evita el estancamiento generadas=0).
        K = int(os.environ.get("QUANTMATH_SIG_REFRESH_CYCLES", "5"))
        seen = {}
        for h in self.engine.hypotheses.values():
            sig = _json.dumps(
                [h.get("strategy_type"), h.get("symbol"),
                 sorted((h.get("parameters") or {}).items())],
                sort_keys=True, default=str)
            last = int(h.get("orchestrator_cycle") or 0)
            seen[sig] = max(seen.get(sig, 0), last)

        made = 0
        for i, symbol in enumerate(symbols):
            if made >= n:
                break

            # El contador de iteracion alimenta la rotacion de exploracion
            self.runner.iteration = self.cycle_count

            # Reuse AQDE generation logic (base templates on first pass,
            # adaptive on later cycles via iteration counter)
            hyp_ids = self.runner.create_hypotheses_for_symbol(symbol, self.cycle_count)

            # Dedupe contra el KB: solo hipotesis NUEVAS van a backtest
            fresh = []
            for hid in hyp_ids:
                hyp = self.runner.all_hypotheses.get(hid)
                if hyp is None:
                    continue
                params = getattr(hyp, "parameters", {}) or {}
                st = getattr(hyp.strategy_type, "value", None)
                if not isinstance(st, str):
                    st = str(hyp.strategy_type)
                sig = _json.dumps([st, symbol, sorted(params.items())],
                                  sort_keys=True, default=str)
                last = seen.get(sig)
                if last is not None and (self.cycle_count - last) < K:
                    continue
                seen[sig] = self.cycle_count
                fresh.append(hid)
            skipped = len(hyp_ids) - len(fresh)
            cycle_generated += len(hyp_ids)
            cycle_fresh += len(fresh)
            if skipped:
                print(f"  [dedupe] {skipped} duplicadas omitidas "
                      f"(ya existen en el KB)")
            if not fresh:
                continue

            # V2 B2: burst mode — prioritize scalp_burst family
            if self.config.mode == "burst":
                scalp_hyps = [hid for hid in fresh
                              if self.runner.all_hypotheses.get(hid)
                              and self.runner.all_hypotheses[hid].parameters.get(
                                  "strategy_type") == "scalp_burst"]
                other_hyps = [hid for hid in fresh if hid not in scalp_hyps]
                # Take all scalp_burst + at most 1 other for exploration
                fresh = scalp_hyps + other_hyps[:1] if other_hyps else scalp_hyps

            # Backtest on REAL Bybit data (force_real_data=True upstream);
            # resultados alimentan el feedback adaptativo del runner.
            # En rafaga de exploracion (rachas de perdidas) se permite
            # backtestear TODAS las candidatas nuevas, no solo el top-N.
            cap = len(fresh) if getattr(self, "_explore_burst", False) \
                else max(1, n - made)
            batch = fresh[:cap]
            results = self.runner.run_backtest_for_symbol(symbol, batch)
            self.runner.performance_history.extend(results)
            self.runner._prune_memory()

            for result in results:
                record = self._result_to_kb_record(result, symbol)
                if record is not None:
                    new_records.append(record)
                    made += 1
        self.last_novelty = self._novelty_rate(cycle_generated, cycle_fresh)
        self._last_novelty_fresh = cycle_fresh
        if cycle_generated:
            print(f"  [novedad] {cycle_fresh}/{cycle_generated} frescas "
                  f"({self.last_novelty * 100:.0f}%)")

        return new_records

    def _generate_and_backtest_symbol(self, symbol: str, n: int,
                                       seen: Dict, K: int) -> List[Dict]:
        """Generate + backtest hypotheses for a single symbol (thread-safe)."""
        import json as _json
        records = []
        with self._runner_lock:
            self.runner.iteration = self.cycle_count
            hyp_ids = self.runner.create_hypotheses_for_symbol(symbol, self.cycle_count)

        fresh = []
        for hid in hyp_ids:
            with self._runner_lock:
                hyp = self.runner.all_hypotheses.get(hid)
            if hyp is None:
                continue
            params = getattr(hyp, "parameters", {}) or {}
            st = getattr(hyp.strategy_type, "value", None)
            if not isinstance(st, str):
                st = str(hyp.strategy_type)
            sig = _json.dumps([st, symbol, sorted(params.items())],
                              sort_keys=True, default=str)
            last = seen.get(sig)
            if last is not None and (self.cycle_count - last) < K:
                continue
            with self._runner_lock:
                seen[sig] = self.cycle_count
            fresh.append(hid)

        if not fresh:
            return records

        if self.config.mode == "burst":
            with self._runner_lock:
                scalp_hyps = [hid for hid in fresh
                              if self.runner.all_hypotheses.get(hid)
                              and self.runner.all_hypotheses[hid].parameters.get(
                                  "strategy_type") == "scalp_burst"]
            other_hyps = [hid for hid in fresh if hid not in scalp_hyps]
            fresh = scalp_hyps + other_hyps[:1] if other_hyps else scalp_hyps

        cap = len(fresh) if getattr(self, "_explore_burst", False) \
            else max(1, n)
        batch = fresh[:cap]
        with self._runner_lock:
            results = self.runner.run_backtest_for_symbol(symbol, batch)
            self.runner.performance_history.extend(results)
            self.runner._prune_memory()

        for result in results:
            record = self._result_to_kb_record(result, symbol)
            if record is not None:
                records.append(record)
        return records

    def _result_to_kb_record(self, result: Dict, symbol: str) -> Optional[Dict]:
        """Convert an AQDE backtest result into a KB JSONL record."""
        from quant_math.autonomous_research.interfaces import StrategyStatus

        hyp_id = result.get("hypothesis_id")
        hyp = self.runner.research_manager.get_hypothesis(hyp_id)
        if hyp is None or result.get("status") != "success":
            logger.info("[skip] %s sin resultado de backtest utilizable", hyp_id)
            return None

        n_trades = int(result.get("n_trades") or 0)
        # Cambio real de capital en % ((final-initial)/initial*100).
        # NO usar result["total_return"]: es PnL absoluto en USD.
        total_return_pct = float(result.get("total_return_pct")
                                 or 0.0)
        win_rate = float(result.get("win_rate") or 0.0)

        # Expectancy = mean expected return per trade (%)
        expectancy = total_return_pct / n_trades if n_trades > 0 else 0.0

        status = StrategyStatus.BACKTESTED.value
        scientific_score = getattr(hyp, "scientific_score", 0.0) or max(
            0.0, min(1.0, 0.3 * (win_rate / 100)
                     + 0.4 * max(0.0, total_return_pct / 2 / 100)
                     + 0.3 * max(0.0, float(result.get("sharpe_ratio") or 0) / 3))
        )
        # Low scientific score degrades to failed (still queryable downstream)
        if scientific_score <= 0.6:
            status = StrategyStatus.FAILED.value

        # Validacion cruzada entre simbolos: una familia que ya rinde
        # positivo en OTRO simbolo (>=MIN_CROSS_OPS ops, win_rate>=40%)
        # eleva backtested->validated. Nunca degrada ni toca el gate.
        cross_validated = False
        min_kb_rows = int(os.environ.get("QUANTMATH_MIN_KB_ROWS", "100"))
        if os.environ.get("QUANTMATH_CROSS_SYMBOL_VALIDATION", "1") == "1" \
                and len(self.engine.hypotheses) >= min_kb_rows:
            st_raw = getattr(hyp, "strategy_type", "")
            st_val = getattr(st_raw, "value", None)
            if not isinstance(st_val, str):
                st_val = str(st_raw)
            fam = str(st_val).split(".")[-1]
            for rec in self.engine.hypotheses.values():
                if rec.get("symbol") == symbol:
                    continue
                other_fam = str(rec.get("strategy_type", "")).split(".")[-1]
                if (other_fam == fam
                        and int(rec.get("n_trades") or 0) >= 5
                        and float(rec.get("win_rate") or 0) >= 40.0):
                    cross_validated = True
                    if status == "backtested":
                        status = "validated"
                    break

        return {
            "hypothesis_id": hyp_id,
            "name": getattr(hyp, "name", hyp_id),
            "description": getattr(hyp, "description", ""),
            "strategy_type": getattr(getattr(hyp, "strategy_type", None), "value",
                                     str(getattr(hyp, "strategy_type", ""))),
            "symbol": symbol,
            "status": status,
            "cross_symbol_validated": cross_validated,
            "expectancy": expectancy,
            "scientific_score": scientific_score,
            "win_rate": win_rate,
            "total_return": float(result.get("total_return") or 0.0),
            "total_return_pct": total_return_pct,
            "n_trades": n_trades,
            "sharpe_ratio": float(result.get("sharpe_ratio") or 0.0),
            "max_drawdown": float(result.get("max_drawdown") or 0.0),
            "parameters": getattr(hyp, "parameters", {}),
            "data_source": f"{self.config.exchange_id}:real",
            "orchestrator_cycle": self.cycle_count,
            "created_at": time.time(),
        }

    # ------------------------------------------------------------------
    # Stage 3: persistence + decisions + paper execution
    # ------------------------------------------------------------------

    def _open_burst_entries(self) -> list:
        """V2 B4: list of open burst entries from the permanent ledger."""
        ledger_path = os.path.join(self.config.state_dir, "paper_executions.jsonl")
        if not os.path.exists(ledger_path):
            return []
        open_keys = set()
        entries = []
        try:
            with open(ledger_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = rec.get("key", "")
                    if "motivo_cierre" in rec:
                        open_keys.discard(key)
                    elif rec.get("margin_usd"):
                        entries.append(rec)
                        open_keys.add(key)
        except OSError:
            pass
        return [e for e in entries if e.get("key") in open_keys]

    def _publish_to_kb(self, records: List[Dict]):
        for record in records:
            self.engine.register_hypothesis(record)

    def _ledger_pnl(self) -> Tuple[float, float]:
        """(realized_today, realized_total) scanned from the permanent ledger.

        realized_today counts closures with exit_time >= UTC midnight.
        Cheap full scan; ledger is small (hundreds of lines).
        """
        day_start = utc_day_start_ts()
        today = total = 0.0
        path = os.path.join(self.config.state_dir, "paper_executions.jsonl")
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "motivo_cierre" not in rec:
                        continue
                    try:
                        pnl = float(rec.get("pnl", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        continue
                    total += pnl
                    try:
                        if float(rec.get("exit_time") or 0) >= day_start:
                            today += pnl
                    except (TypeError, ValueError):
                        pass
        except OSError:
            pass
        return today, total

    def _apply_margin_cap(self, notional: float, lev_used: int,
                          hypothesis_id: str) -> float:
        """Fase 1b: enforce RiskManager max margin per entry.

        Returns possibly-capped notional. Never raises (fail-open with log).
        """
        try:
            from quant_math.risk.risk_manager import RiskManager
            if self._risk_manager is None:
                self._risk_manager = RiskManager(
                    max_position_size_pct=self.config.max_position_pct,
                    drawdown_limit=self.config.drawdown_limit,
                )
            margin_used = notional / max(1, lev_used)
            account = self.config.initial_capital + self._last_realized_total
            chk = self._risk_manager.check_position_size(
                hypothesis_id, margin_used, account)
            if not chk["approved"]:
                capped = float(chk["approved_size"]) * max(1, lev_used)
                print(f"  [risk] margin cap: notional ${notional:.2f} -> "
                      f"${capped:.2f} ({'; '.join(chk['reasons'])})")
                return capped
        except Exception as exc:
            logger.warning("[risk] margin check fallo (%s); sin cap", exc)
        return notional

    def _execute_paper_trade(self, signal: Dict) -> Dict:
        """Fill a paper trade at the signal price with configured sizing/TP."""
        price = float(signal["price"])
        side = signal["side"]
        # Burst mode: margin × leverage; Classic: capital × entry_pct × vol-mult
        if self.config.mode == "burst":
            margin = float(signal.get("margin", self.config.burst_margin))
            leverage = int(signal.get("leverage", self.config.burst_leverage))
            # V2 B4: exposure cap — check total open margin
            open_margin = sum(
                float(rec.get("margin_usd", 0))
                for rec in self._open_burst_entries()
            )
            if open_margin + margin > BurstStateTracker.MAX_EXPOSURE_USD:
                print(f"  [burst] EXPOSURE CAP: open={open_margin:.0f} "
                      f"+ new={margin:.0f} > {BurstStateTracker.MAX_EXPOSURE_USD:.0f}")
                return {"action": "exposure_capped"}
            notional = margin * leverage
            lev_used = leverage
        else:
            # O6: nocional escalado por vol-target (clampeado en el engine)
            base_notional = (self.config.initial_capital * self.config.entry_pct
                             * float(signal.get("sizing_mult", 1.0)))
            notional = base_notional * self.config.leverage
            lev_used = max(1, self.config.leverage)
        # Fase 1b: RiskManager margin cap (never raises)
        notional = self._apply_margin_cap(
            notional, lev_used, str(signal.get("hypothesis_id", "")))
        if self.config.mode == "burst":
            margin = notional / max(1, lev_used)
        # Fase 3: live path (config guard guarantees testnet + keys,
        # or mainnet with QUANTMATH_ALLOW_MAINNET=1 — see __post_init__).
        if not self.config.dry_run:
            return self._execute_live_order(
                signal, price, side, notional, lev_used,
                margin if self.config.mode == "burst" else None)
        quantity = notional / price
        tp_price = price * (1 + self.config.take_profit_pct) if side == "buy" \
            else price * (1 - self.config.take_profit_pct)

        trade = {
            "mode": "paper",
            "key": f"{signal['hypothesis_id']}:{signal['symbol']}",
            "symbol": signal["symbol"],
            "side": side,
            "quantity": quantity,
            "entry_price": price,
            "notional_usd": notional,
            "take_profit_price": tp_price,
            "hypothesis_id": signal["hypothesis_id"],
            "expectancy": signal["expectancy"],
            "timestamp": signal["timestamp"],
            "cycle": self.cycle_count,
        }
        if self.config.mode == "burst":
            trade["margin_usd"] = margin
            trade["leverage"] = leverage
        elif self.config.leverage > 1:
            trade["leverage"] = self.config.leverage
        trades_path = os.path.join(self.config.state_dir, "paper_executions.jsonl")
        os.makedirs(self.config.state_dir, exist_ok=True)
        with open(trades_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(trade, ensure_ascii=False) + "\n")

        logger.info("[paper_trade] %s %s qty=%.6f @ %.2f TP=%.2f (hyp=%s)",
                    side.upper(), trade["symbol"], quantity, price, tp_price,
                    trade["hypothesis_id"])
        # Fase 2: shadow live intent — what WOULD be sent to the exchange.
        # No API call; paper trading continues untouched.
        if self.config.shadow_live:
            self._log_shadow_order(trade, signal, price)
        return trade

    def _execute_live_order(self, signal: Dict, price: float, side: str,
                            notional: float, lev_used: int,
                            margin: Optional[float]) -> Dict:
        """Fase 3/4: place a REAL order (testnet or mainnet per config).

        Never raises: failures return {"action": "live_failed", ...} so one
        bad order does not kill the cycle.
        """
        from data_acquisition.data_sources.exchanges import ExchangeAPI
        trade: Dict = {"action": "live_failed", "symbol": signal.get("symbol")}
        try:
            api = ExchangeAPI(self.config.exchange_id,
                              sandbox=self.config.testnet)
            try:
                api.set_margin_mode(signal["symbol"], "isolated")
            except Exception as exc:
                logger.warning("[live] set_margin_mode fallo (%s); continúo", exc)
            try:
                api.set_leverage(signal["symbol"], lev_used)
            except Exception as exc:
                logger.warning("[live] set_leverage fallo (%s); continúo", exc)
            qty = notional / price
            order = api.create_order(signal["symbol"], side, qty,
                                     order_type="market")
            try:
                api.close()
            except Exception:
                pass
            mode = "live-testnet" if self.config.testnet else "live-mainnet"
            trade = {
                "mode": mode,
                "key": f"{signal['hypothesis_id']}:{signal['symbol']}",
                "symbol": signal["symbol"],
                "side": side,
                "quantity": float(order.get("amount") or qty),
                "entry_price": float(order.get("average")
                                     or order.get("price") or price),
                "notional_usd": notional,
                "take_profit_price": (
                    price * (1 + self.config.take_profit_pct)
                    if side == "buy"
                    else price * (1 - self.config.take_profit_pct)),
                "hypothesis_id": signal["hypothesis_id"],
                "expectancy": signal["expectancy"],
                "timestamp": signal["timestamp"],
                "cycle": self.cycle_count,
                "leverage": lev_used,
                "exchange_order_id": order.get("id"),
                "testnet": self.config.testnet,
            }
            if margin is not None:
                trade["margin_usd"] = margin
            trades_path = os.path.join(self.config.state_dir,
                                       "paper_executions.jsonl")
            os.makedirs(self.config.state_dir, exist_ok=True)
            with open(trades_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(trade, ensure_ascii=False,
                                    default=str) + "\n")
            logger.info("[live_order] %s %s qty=%.6f (hyp=%s id=%s)",
                        side.upper(), trade["symbol"], trade["quantity"],
                        trade["hypothesis_id"], trade.get("exchange_order_id"))
        except Exception as exc:
            logger.error("[live_order] fallo (%s)", exc)
            trade = {"action": "live_failed", "symbol": signal.get("symbol"),
                     "error": str(exc)}
        return trade

    def _log_shadow_order(self, trade: Dict, signal: Dict, price: float) -> None:
        """Append a shadow live-order intent record (no API call)."""
        try:
            lev = int(trade.get("leverage")
                      or signal.get("leverage")
                      or self.config.leverage or 1)
            swap = trade["symbol"]
            if ":" not in swap and swap.endswith("/USDT"):
                swap += ":USDT"
            rec = {
                "type": "shadow_order",
                "symbol": swap,
                "side": trade["side"],
                "quantity": trade["quantity"],
                "price": price,
                "order_type": "market",
                "leverage": lev,
                "margin_mode": "isolated",
                "reduce_only": False,
                "testnet": self.config.testnet,
                "paper_notional_usd": trade.get("notional_usd"),
                "hypothesis_id": trade.get("hypothesis_id"),
                "expectancy": trade.get("expectancy"),
                "                timestamp": trade.get("timestamp"),
                "cycle": self.cycle_count,
                "validated": bool(getattr(self, "_live_validated", False)),
            }
            path = os.path.join(self.config.state_dir, "shadow_orders.jsonl")
            os.makedirs(self.config.state_dir, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            logger.warning("[shadow] log fallo (%s)", exc)

    def _validate_live_access(self) -> bool:
        """Fase 2: verify API keys + testnet balance. Warn-only (never raises).

        Returns True when keys exist and a sandbox balance fetch succeeds.
        """
        try:
            from data_acquisition.data_sources.exchanges import (
                ExchangeAPI, api_keys_present,
            )
            if not api_keys_present():
                logger.warning("[live] sin API keys en .env — shadow sin validar; "
                               "paper trading continúa")
                return False
            api = ExchangeAPI(self.config.exchange_id,
                              sandbox=self.config.testnet)
            bal = api.fetch_balance()
            total = (bal.get("total") or {}).get("USDT", "?")
            logger.info("[live] keys OK (testnet=%s) balance USDT=%s",
                        self.config.testnet, total)
            try:
                api.close()
            except Exception:
                pass
            return True
        except Exception as exc:
            logger.warning("[live] validación falló (%s); paper trading continúa",
                           exc)
            return False

    # ------------------------------------------------------------------
    # One full cycle
    # ------------------------------------------------------------------

    @staticmethod
    def _novelty_rate(generated: int, fresh: int) -> float:
        """O4: fraccion de hipotesis generadas que sobreviven el dedupe."""
        return round(fresh / generated, 4) if generated else 0.0

    def run_cycle(self) -> Dict:
        """generate -> persist -> decide -> paper execute -> feedback."""
        self.cycle_count += 1
        self.runner.invalidate_market_cache()   # datos frescos por ciclo
        cfg = self.config
        print(f"\n{'=' * 60}")
        print(f"ORCHESTRATOR CYCLE {self.cycle_count} "
              f"(modo={cfg.mode}, datos=REALES/{cfg.exchange_id})")
        print(f"{'=' * 60}")

        # V2 B3: reset burst cycle counter
        if self.burst_tracker:
            self.burst_tracker.reset_cycle()

        summary = {"cycle": self.cycle_count, "generated": 0, "signals": 0,
                   "no_entry": 0, "skipped_position": 0, "trades": []}

        # 1-2. Generate + backtest on real data (parallel per symbol)
        import json as _json
        K = int(os.environ.get("QUANTMATH_SIG_REFRESH_CYCLES", "5"))
        seen = {}
        for h in self.engine.hypotheses.values():
            sig = _json.dumps(
                [h.get("strategy_type"), h.get("symbol"),
                 sorted((h.get("parameters") or {}).items())],
                sort_keys=True, default=str)
            last = int(h.get("orchestrator_cycle") or 0)
            seen[sig] = max(seen.get(sig, 0), last)

        n_per_sym = max(1, cfg.hypotheses_per_cycle // max(1, len(cfg.symbols)))
        all_records = []
        max_workers = min(len(cfg.symbols), 3) if len(cfg.symbols) > 1 else 1
        if max_workers > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(self._generate_and_backtest_symbol,
                                sym, n_per_sym, seen, K): sym
                    for sym in cfg.symbols
                }
                for f in as_completed(futures):
                    sym = futures[f]
                    try:
                        sym_records = f.result()
                        all_records.extend(sym_records)
                    except Exception as exc:
                        logger.exception("Generation failed for %s: %s", sym, exc)
        else:
            for sym in cfg.symbols:
                try:
                    sym_records = self._generate_and_backtest_symbol(
                        sym, n_per_sym, seen, K)
                    all_records.extend(sym_records)
                except Exception as exc:
                    logger.exception("Generation failed for %s: %s", sym, exc)

        records = all_records
        summary["generated"] = len(records)
        for r in records:
            print(f"  [hyp] {r['hypothesis_id']} {r['name']} "
                  f"expectancy={r['expectancy']:+.5f} score={r['scientific_score']:.2f} "
                  f"status={r['status']}")

        # 3+4. Publish to KB and check exits in parallel (independent data)
        exits = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            pub_future = pool.submit(self._publish_to_kb, records)
            exit_future = pool.submit(self.engine.check_exits_all)
            pub_future.result()  # MUST complete before decide()
            exits = exit_future.result()

        for closure in exits:
            print(f"  [exit] {closure['motivo_cierre'].upper()} "
                  f"{closure['symbol']} exit={closure['exit_price']:.8g} "
                  f"pnl={closure['pnl']:+.4f}")
        summary["exits"] = len(exits)

        # Fase 1b: circuit breaker — block NEW entries on breach.
        # Exits already ran above; monitoring continues regardless.
        realized_today, realized_total = self._ledger_pnl()
        self._last_realized_total = realized_total
        equity = self.config.initial_capital + realized_total
        open_count = len(getattr(self.engine, "open_positions", {}) or {})
        risk_ok, risk_reason = self.guard.check(
            realized_today, equity, open_count)
        self.stats["risk_halt"] = risk_reason
        self.stats["realized_today"] = round(realized_today, 4)
        self.stats["realized_total"] = round(realized_total, 4)
        if not risk_ok:
            print(f"  [RISK-HALT] {risk_reason}")

        # 5. Decide per symbol; execute paper trades; engine handles feedback
        for symbol in cfg.symbols:
            if not risk_ok:
                summary["no_entry"] += 1
                continue
            # V2 B3: burst cooldown gate
            if (self.burst_tracker
                    and not self.burst_tracker.can_enter(self.cycle_count)):
                print(f"  [burst] {symbol}: COOLDOWN "
                      f"({self.burst_tracker.cooldown_remaining(self.cycle_count)} "
                      f"ciclos restantes)")
                summary["no_entry"] += 1
                continue
            outcome = self.engine.decide(symbol)
            action = outcome["action"] if outcome else "none"
            if action == "entry":
                summary["signals"] += 1
                trade = self._execute_paper_trade(outcome)
                if trade.get("action") == "exposure_capped":
                    summary["no_entry"] += 1
                elif trade.get("action") == "live_failed":
                    summary["live_failed"] = summary.get("live_failed", 0) + 1
                    print(f"  [live] orden fallida {symbol}: "
                          f"{trade.get('error', '?')}")
                else:
                    summary["trades"].append(trade)
                    if self.burst_tracker:
                        self.burst_tracker.register_entry(self.cycle_count)
            elif action == "no_entry":
                summary["no_entry"] += 1
                print(f"  [decision] {symbol}: NO_ENTRY ({outcome['reason']})")
            elif action == "skip_position_guard":
                summary["skipped_position"] += 1
                print(f"  [decision] {symbol}: SKIP posición abierta "
                      f"({outcome.get('hypothesis_id')})")

        # V2 B3: register closures for burst stats
        if self.burst_tracker:
            for closure in exits:
                self.burst_tracker.register_closure(
                    float(closure.get("pnl", 0.0)))

        print(f"[cycle {self.cycle_count}] generadas={summary['generated']} "
              f"señales={summary['signals']} no_entry={summary['no_entry']} "
              f"skip_pos={summary['skipped_position']}")

        # O4: metrica de novedad generativa del ciclo
        novelty = getattr(self, "last_novelty", 0.0)
        summary["novelty_rate"] = novelty

        self.stats["cycles_completed"] = self.cycle_count
        self.stats["hypotheses_generated"] += summary["generated"]
        self.stats["hyp_fresh_last_cycle"] = getattr(
            self, "_last_novelty_fresh", 0)
        self.stats["novelty_rate_last_cycle"] = novelty
        self.stats["novelty_cum_avg"] = round(
            (self.stats.get("novelty_cum_avg", 0.0)
             * self.stats.get("novelty_cycles", 0) + novelty)
            / max(1, self.stats.get("novelty_cycles", 0) + 1), 4)
        self.stats["novelty_cycles"] = self.stats.get(
            "novelty_cycles", 0) + 1
        self.stats["hypotheses_evaluated"] += len(records)
        self.stats["signals"] += summary["signals"]
        self.stats["no_entry"] += summary["no_entry"]
        self.stats["skipped_position"] += summary["skipped_position"]
        self.stats["paper_trades_taken"] += len(summary["trades"])
        self.stats["last_cycle_at"] = time.time()
        # V2 B3: burst stats for monitor
        if self.burst_tracker:
            self.stats["burst_stats"] = self.burst_tracker.stats_dict(
                self.cycle_count)
        self._write_stats()
        return summary

    def run_forever(self, max_cycles: Optional[int] = None):
        """Continuous loop (Ctrl+C to stop)."""
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            if self._stop_requested:
                break
            try:
                self.run_cycle()
            except Exception as exc:
                logger.exception("Cycle failed: %s", exc)
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                # Adaptive sleep: shorter intervals to allow signal processing
                sleep_time = self.config.interval_seconds
                if self.config.mode == "burst":
                    can_enter = (self.burst_tracker is None
                                 or self.burst_tracker.can_enter(self.cycle_count))
                    has_open = len(self.engine.open_positions) > 0
                    if not can_enter and not has_open:
                        sleep_time = max(sleep_time, 60)
                # Sleep in 1s increments to allow SIGINT processing
                elapsed = 0
                while elapsed < sleep_time and not self._stop_requested:
                    time.sleep(min(1.0, sleep_time - elapsed))
                    elapsed += 1

    def request_stop(self):
        """Request the orchestrator to stop after the current cycle."""
        self._stop_requested = True
