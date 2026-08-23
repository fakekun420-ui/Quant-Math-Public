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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from quant_math.decision_engine import DecisionEngine

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
        if self.dry_run is False:
            raise NotImplementedError(
                "trading real no implementado aún: dry_run=False no disponible "
                "(los datos son SIEMPRE reales; dry_run solo controla ejecución)"
            )


class Orchestrator:
    """Continuous generation -> decision -> feedback loop."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._build_runner()
        self.engine = self._build_engine()
        self.cycle_count = 0
        # Runtime stats consumed by external monitors (CLI)
        self.stats = {
            "state": "RUNNING",
            "cycles_completed": 0,
            "hypotheses_generated": 0,
            "hypotheses_evaluated": 0,
            "signals": 0,
            "no_entry": 0,
            "skipped_position": 0,
            "paper_trades_taken": 0,
            "started_at": time.time(),
            "last_cycle_at": None,
        }
        self.stats_path = os.path.join(self.config.state_dir, "runtime_stats.json")
        self._write_stats()

    def _write_stats(self):
        try:
            os.makedirs(self.config.state_dir, exist_ok=True)
            with open(self.stats_path, "w", encoding="utf-8") as fh:
                json.dump({**self.stats,
                           "config": {
                               "symbols": self.config.symbols,
                               "initial_capital": self.config.initial_capital,
                               "entry_pct": self.config.entry_pct,
                               "timeframe": self.config.timeframe,
                               "take_profit_pct": self.config.take_profit_pct,
                               "lookback_days": self.config.lookback_days,
                               "min_paper_trades": self.config.min_paper_trades,
                               "hypotheses_per_cycle": self.config.hypotheses_per_cycle,
                               "exchange_id": self.config.exchange_id,
                               "mode": "paper" if self.config.dry_run else "live",
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
        )

    def _build_engine(self) -> DecisionEngine:
        return DecisionEngine(
            symbols=self.config.symbols,
            kb_path=self.config.kb_path,
            state_dir=self.config.state_dir,
            exchange_id=self.config.exchange_id,
            timeframe=self.config.timeframe,
            min_paper_trades=self.config.min_paper_trades,
        )

    # ------------------------------------------------------------------
    # Stage 1: hypothesis generation + backtest on REAL data
    # ------------------------------------------------------------------

    def _generate_and_backtest(self) -> List[Dict]:
        """Generate N hypotheses across configured symbols and backtest them."""
        new_records = []
        symbols = self.config.symbols
        n = self.config.hypotheses_per_cycle

        made = 0
        for i, symbol in enumerate(symbols):
            if made >= n:
                break

            # Reuse AQDE generation logic (base templates on first pass,
            # adaptive on later cycles via iteration counter)
            hyp_ids = self.runner.create_hypotheses_for_symbol(symbol, self.cycle_count)
            if not hyp_ids:
                continue

            # Backtest on REAL Bybit data (force_real_data=True upstream)
            batch = hyp_ids[: max(1, n - made)]
            results = self.runner.run_backtest_for_symbol(symbol, batch)

            for result in results:
                record = self._result_to_kb_record(result, symbol)
                if record is not None:
                    new_records.append(record)
                    made += 1

        return new_records

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

        return {
            "hypothesis_id": hyp_id,
            "name": getattr(hyp, "name", hyp_id),
            "description": getattr(hyp, "description", ""),
            "strategy_type": getattr(getattr(hyp, "strategy_type", None), "value",
                                     str(getattr(hyp, "strategy_type", ""))),
            "symbol": symbol,
            "status": status,
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

    def _publish_to_kb(self, records: List[Dict]):
        for record in records:
            self.engine.register_hypothesis(record)
        if records:
            self.engine._load_jsonl()

    def _execute_paper_trade(self, signal: Dict) -> Dict:
        """Fill a paper trade at the signal price with configured sizing/TP."""
        price = float(signal["price"])
        side = signal["side"]
        notional = self.config.initial_capital * self.config.entry_pct
        quantity = notional / price
        tp_price = price * (1 + self.config.take_profit_pct) if side == "buy" \
            else price * (1 - self.config.take_profit_pct)

        trade = {
            "mode": "paper",
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
        trades_path = os.path.join(self.config.state_dir, "paper_executions.jsonl")
        os.makedirs(self.config.state_dir, exist_ok=True)
        with open(trades_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(trade, ensure_ascii=False) + "\n")

        logger.info("[paper_trade] %s %s qty=%.6f @ %.2f TP=%.2f (hyp=%s)",
                    side.upper(), trade["symbol"], quantity, price, tp_price,
                    trade["hypothesis_id"])
        return trade

    # ------------------------------------------------------------------
    # One full cycle
    # ------------------------------------------------------------------

    def run_cycle(self) -> Dict:
        """generate -> persist -> decide -> paper execute -> feedback."""
        self.cycle_count += 1
        cfg = self.config
        print(f"\n{'=' * 60}")
        print(f"ORCHESTRATOR CYCLE {self.cycle_count} "
              f"(modo={'paper' if cfg.dry_run else 'LIVE'}, datos=REALES/{cfg.exchange_id})")
        print(f"{'=' * 60}")

        summary = {"cycle": self.cycle_count, "generated": 0, "signals": 0,
                   "no_entry": 0, "skipped_position": 0, "trades": []}

        # 1-2. Generate + backtest on real data
        records = self._generate_and_backtest()
        summary["generated"] = len(records)
        for r in records:
            print(f"  [hyp] {r['hypothesis_id']} {r['name']} "
                  f"expectancy={r['expectancy']:+.5f} score={r['scientific_score']:.2f} "
                  f"status={r['status']}")

        # 3. Publish to shared JSONL KB
        self._publish_to_kb(records)

        # 4-5. Decide per symbol; execute paper trades; engine handles feedback
        for symbol in cfg.symbols:
            outcome = self.engine.decide(symbol)
            action = outcome["action"] if outcome else "none"
            if action == "entry":
                summary["signals"] += 1
                trade = self._execute_paper_trade(outcome)
                summary["trades"].append(trade)
            elif action == "no_entry":
                summary["no_entry"] += 1
                print(f"  [decision] {symbol}: NO_ENTRY ({outcome['reason']})")
            elif action == "skip_position_guard":
                summary["skipped_position"] += 1
                print(f"  [decision] {symbol}: SKIP posición abierta "
                      f"({outcome.get('hypothesis_id')})")

        print(f"[cycle {self.cycle_count}] generadas={summary['generated']} "
              f"señales={summary['signals']} no_entry={summary['no_entry']} "
              f"skip_pos={summary['skipped_position']}")

        self.stats["cycles_completed"] = self.cycle_count
        self.stats["hypotheses_generated"] += summary["generated"]
        self.stats["hypotheses_evaluated"] += len(records)
        self.stats["signals"] += summary["signals"]
        self.stats["no_entry"] += summary["no_entry"]
        self.stats["skipped_position"] += summary["skipped_position"]
        self.stats["paper_trades_taken"] += len(summary["trades"])
        self.stats["last_cycle_at"] = time.time()
        self._write_stats()
        return summary

    def run_forever(self, max_cycles: Optional[int] = None):
        """Continuous loop (Ctrl+C to stop)."""
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            try:
                self.run_cycle()
            except Exception as exc:
                logger.exception("Cycle failed: %s", exc)
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                time.sleep(self.config.interval_seconds)
