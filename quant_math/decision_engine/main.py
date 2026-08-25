"""
Trading Decision Engine.

Selects the best hypothesis per symbol from the JSONL-backed Knowledge Base,
fetches REAL market data (Bybit via ExchangeAPI), and generates buy/sell
signals only when the selected hypothesis has positive expectancy.

Reuses:
- quant_math.autonomous_research.adapters.HypothesisKnowledgeBase
- data_acquisition.data_sources.exchanges.ExchangeAPI
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

QUERYABLE_STATUSES = ("validated", "backtested", "monte_carlo_tested", "failed")
NO_ENTRY_REASON = "sin hipótesis de expectativa positiva disponible"
DEFAULT_MIN_PAPER_TRADES = 3

# LEARN MODE: cuando esta activo, el gate expectancy>0 se desactiva TEMPORAL-
# MENTE para que el sistema opere tambien hipotesis negativas y aprenda de
# sus errores (solo paper: el sistema nunca implementa ejecucion real).
# Default "0" (gate intacto); la ruta del CLI lo activa con setdefault.
def _learn_mode_default() -> bool:
    return os.environ.get("QUANTMATH_LEARN_MODE", "0") == "1"


class DecisionEngine:
    """
    Expectancy-gated decision loop.

    For each configured symbol:
      1. Pick best hypothesis: expectancy DESC, scientific_score DESC tiebreak.
      2. Abstain ('no_entry') unless expectancy > 0.
      3. Skip if a position is already open for (hypothesis, symbol).
      4. Evaluate direction on REAL exchange data and emit the signal.
      5. Count paper trades; deliver feedback to AQDE after min_paper_trades.
    """

    def __init__(
        self,
        symbols: List[str],
        kb_path: str = "autonomous_research/data/hypotheses.jsonl",
        state_dir: str = "quant_math/decision_engine/state",
        exchange_id: str = "bybit",
        timeframe: str = "1h",
        candle_limit: int = 100,
        min_paper_trades: int = DEFAULT_MIN_PAPER_TRADES,
        knowledge_base=None,
        data_provider: Optional[Callable[[str], List[List]]] = None,
        use_postgres: bool = True,
        take_profit_pct: Optional[float] = None,
        learn_mode: Optional[bool] = None,
    ):
        self.symbols = list(symbols)
        self.kb_path = kb_path
        self.state_dir = state_dir
        self.exchange_id = exchange_id
        self.timeframe = timeframe
        self.candle_limit = candle_limit
        self.min_paper_trades = min_paper_trades
        self.take_profit_pct = (
            float(take_profit_pct) if take_profit_pct is not None else None)
        self.learn_mode = (_learn_mode_default() if learn_mode is None
                           else bool(learn_mode))
        if self.learn_mode:
            logger.warning(
                "[LEARN MODE] gate expectancy>0 DESACTIVADO temporalmente — "
                "el sistema operara tambien hipotesis negativas (paper) para "
                "alimentar el aprendizaje no supervisado")

        os.makedirs(os.path.dirname(kb_path) or ".", exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

        self._kb = knowledge_base
        if self._kb is None:
            try:
                from quant_math.autonomous_research.adapters import (
                    HypothesisKnowledgeBase,
                )
                self._kb = HypothesisKnowledgeBase(
                    storage_path=os.path.dirname(kb_path) or "."
                )
            except ImportError:
                self._kb = None

        # JSONL persistence layer over the KB
        self.hypotheses: Dict[str, Dict[str, Any]] = {}
        self.storage = None
        if use_postgres:
            try:
                from quant_math.autonomous_research.adapters.postgres_kb import \
                    KBPersistence
                self.storage = KBPersistence(kb_path)
            except Exception as exc:
                logger.warning(
                    "[kb-storage] inicialización PostgreSQL falló (%s) — "
                    "usando JSONL puro: %s", exc.__class__.__name__, kb_path)
        else:
            logger.info("[kb-storage] backend=jsonl (use_postgres=False)")
        self._load_jsonl()

        self.positions_path = os.path.join(state_dir, "positions.jsonl")
        self.paper_trades_path = os.path.join(state_dir, "paper_trades.jsonl")
        self.ledger_path = os.path.join(state_dir, "paper_executions.jsonl")
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.paper_trade_counts: Dict[str, int] = {}
        self.feedback_delivered: Dict[str, bool] = {}
        self._load_state()

        if data_provider is not None:
            self._data_provider = data_provider
            self._exchange = None
        else:
            from data_acquisition.data_sources.exchanges import ExchangeAPI
            self._exchange = ExchangeAPI(exchange_id=exchange_id)
            self._data_provider = lambda symbol: self._exchange.fetch_ohlcv(
                symbol, self.timeframe, limit=self.candle_limit)

    # ------------------------------------------------------------------
    # Knowledge Base (JSONL)
    # ------------------------------------------------------------------

    @property
    def storage_mode(self) -> str:
        return self.storage.mode if self.storage is not None else "jsonl"

    def _load_jsonl(self):
        if self.storage is not None:
            self.hypotheses = self.storage.load_all()
            return
        if not os.path.exists(self.kb_path):
            return
        with open(self.kb_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                hid = record.get("hypothesis_id")
                if hid:
                    existing = self.hypotheses.get(hid)
                    if existing:
                        existing.update(record)
                    else:
                        self.hypotheses[hid] = record

    def _save_hypothesis(self, record: Dict[str, Any]):
        hid = record["hypothesis_id"]
        self.hypotheses[hid] = record
        if self.storage is not None:
            self.storage.save(record)
            return
        with open(self.kb_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False,
                                default=str) + "\n")

    def register_hypothesis(self, record: Dict[str, Any]) -> str:
        """Register/overwrite a hypothesis record in the JSONL KB."""
        hid = record.get("hypothesis_id") or f"hyp_{int(time.time() * 1000)}"
        record = dict(record, hypothesis_id=hid)
        self._save_hypothesis(record)
        return hid

    def select_best_hypothesis(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Best hypothesis for symbol by (expectancy DESC, scientific_score DESC)."""
        candidates = [
            h for h in self.hypotheses.values()
            if h.get("symbol", h.get("asset")) == symbol
            and h.get("status") in QUERYABLE_STATUSES
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda h: (
                float(h.get("expectancy", 0.0)),
                float(h.get("scientific_score", 0.0)),
            ),
        )

    # ------------------------------------------------------------------
    # State (open positions / paper trade counters)
    # ------------------------------------------------------------------

    def _load_state(self):
        for path, target in (
            (self.positions_path, self.open_positions),
            (self.paper_trades_path, self.paper_trade_counts),
        ):
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if target is self.open_positions:
                        self.open_positions[rec["key"]] = rec
                    else:
                        self.paper_trade_counts[rec["key"]] = rec["count"]
        if self.open_positions:
            logger.info(
                "[posiciones] recuperadas %d posicion(es) abierta(s) del "
                "estado previo: %s", len(self.open_positions),
                ", ".join(self.open_positions.keys()))

    def _persist_positions(self):
        """Reescribe positions.jsonl con las posiciones vivas (atomico)."""
        tmp = self.positions_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for rec in self.open_positions.values():
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, self.positions_path)

    def _append_state(self, path: str, record: Dict[str, Any]):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _position_key(hypothesis_id: str, symbol: str) -> str:
        return f"{hypothesis_id}:{symbol}"

    @property
    def stop_loss_pct(self) -> Optional[float]:
        """SL obligatorio 2:1 — siempre take_profit_pct / 2, sin excepcion."""
        if self.take_profit_pct is None:
            return None
        return self.take_profit_pct / 2.0

    def has_open_position(self, hypothesis_id: str, symbol: str) -> bool:
        return self._position_key(hypothesis_id, symbol) in self.open_positions

    def close_position(self, hypothesis_id: str, symbol: str,
                       motivo: str = "manual",
                       exit_price: Optional[float] = None):
        """Cierra una posicion: la quita del estado vivo y la registra en el
        libro de operaciones permanente (paper_executions.jsonl,
        append-only: este archivo NUNCA se trunca ni se resetea)."""
        key = self._position_key(hypothesis_id, symbol)
        pos = self.open_positions.pop(key, None)
        if pos is None:
            return None
        self._persist_positions()
        entry_price = float(pos.get("entry_price", 0.0))
        side = pos.get("side", "buy")
        direction = 1 if side == "buy" else -1
        qty, notional = self._last_entry_sizing(key)
        exit_px = float(exit_price) if exit_price is not None else entry_price
        pnl = qty * (exit_px - entry_price) * direction
        pnl_pct = (pnl / notional * 100.0) if notional else 0.0
        closure = {
            "type": "closure",
            "key": key,
            "symbol": symbol,
            "hypothesis_id": hypothesis_id,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_px,
            "quantity": qty,
            "pnl": round(pnl, 10),
            "pnl_pct": round(pnl_pct, 6),
            "entry_time": pos.get("opened_at"),
            "exit_time": time.time(),
            "motivo_cierre": motivo,
        }
        self._append_state(self.ledger_path, closure)
        logger.info("[cierre] %s %s motivo=%s exit=%.8g pnl=%.4f (%+.3f%%)",
                    side.upper(), symbol, motivo, exit_px, pnl, pnl_pct)
        return closure

    def _last_entry_sizing(self, key: str):
        """Cantidad/notional de la ultima entrada abierta para key segun el
        libro permanente; fallback 1.0 si no hay ejecucion registrada."""
        qty, notional = 1.0, 0.0
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or '"closure"' in line[:24]:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (rec.get("key") or f"{rec.get('hypothesis_id')}:"
                            f"{rec.get('symbol')}") != key \
                            or "motivo_cierre" in rec:
                        continue
                    qty = float(rec.get("quantity", qty))
                    notional = float(rec.get("notional_usd",
                                             qty * float(
                                                 rec.get("entry_price",
                                                         0.0))))
        return qty, notional

    def _entry_stop_loss_from_ledger(self, key: str) -> Optional[float]:
        """SL vigente EN el momento de la entrada para key, derivado del
        take_profit_price registrado en el libro (SL obligatorio = TP/2).
        Devuelve None si no hay entrada con TP en el libro."""
        sl = None
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or '"closure"' in line[:24]:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rec_key = rec.get("key") or (
                        f"{rec.get('hypothesis_id')}:{rec.get('symbol')}")
                    if rec_key != key or "motivo_cierre" in rec:
                        continue
                    entry = float(rec.get("entry_price", 0.0))
                    tp_px = rec.get("take_profit_price")
                    if entry > 0 and tp_px is not None:
                        tp_frac = abs(float(tp_px) - entry) / entry
                        sl = tp_frac / 2.0
        return sl

    def _position_exit_thresholds(self, pos: Dict[str, Any]):
        """Umbrales TP/SL de la posicion. Prioridad: los guardados al abrir
        la posicion -> los del libro en la entrada -> los configurados ahora.
        Evita que un cambio de config mueva retroactivamente el SL."""
        entry = float(pos["entry_price"])
        tp = pos.get("take_profit_pct")
        if tp is None and self.take_profit_pct is not None:
            tp = self.take_profit_pct
        sl = pos.get("stop_loss_pct")
        if sl is None:
            key = pos.get("key")
            sl = self._entry_stop_loss_from_ledger(key) if key else None
        if sl is None:
            sl = self.stop_loss_pct
        return (
            float(tp) if tp is not None else None,
            float(sl) if sl is not None else None,
        )

    # ------------------------------------------------------------------
    # TP/SL sobre posiciones abiertas (SL obligatorio = TP/2, ratio 2:1)
    # ------------------------------------------------------------------

    def _check_exits(self, symbol: str):
        """Comprueba precio actual vs entrada para cada posicion abierta del
        simbolo y cierra por SL o TP. SL primero (riesgo antes que nada)."""
        keys = [k for k, p in self.open_positions.items()
                if k.endswith(f":{symbol}")]
        if not keys:
            return []
        candles = self.fetch_real_data(symbol)
        cur = float(candles[-1]["close"])
        closed = []
        for key in keys:
            pos = self.open_positions[key]
            side = pos.get("side", "buy")
            entry = float(pos["entry_price"])
            tp, sl = self._position_exit_thresholds(pos)
            if sl is None and tp is None:
                continue
            hyp_id = key.rsplit(f":{symbol}", 1)[0]
            if side == "buy":
                hit_sl = sl is not None and cur <= entry * (1 - sl)
                hit_tp = tp is not None and cur >= entry * (1 + tp)
            else:
                hit_sl = sl is not None and cur >= entry * (1 + sl)
                hit_tp = tp is not None and cur <= entry * (1 - tp)
            if hit_sl:
                closed.append(self.close_position(hyp_id, symbol,
                                                  motivo="sl",
                                                  exit_price=cur))
            elif hit_tp:
                closed.append(self.close_position(hyp_id, symbol,
                                                  motivo="tp",
                                                  exit_price=cur))
        return closed

    def check_exits_all(self):
        """SL/TP para TODAS las posiciones abiertas, incluidas las de simbolos
        que ya no estan en la configuracion (posiciones huerfas tras un cambio
        de universo). Sin esto quedan abiertas para siempre."""
        symbols = sorted({k.rsplit(":", 1)[-1]
                          for k in self.open_positions})
        closed = []
        for symbol in symbols:
            try:
                closed.extend(self._check_exits(symbol))
            except Exception as exc:
                logger.warning("[exits] fallo revisando %s: %s",
                               symbol, exc.__class__.__name__)
        return [c for c in closed if c is not None]

    # ------------------------------------------------------------------
    # Market data (REAL Bybit data only)
    # ------------------------------------------------------------------

    def fetch_real_data(self, symbol: str) -> List[Dict[str, float]]:
        ohlcv = self._data_provider(symbol)
        if not ohlcv:
            raise RuntimeError(f"No real market data returned for {symbol}")
        return [
            {"timestamp": c[0], "open": c[1], "high": c[2],
             "low": c[3], "close": c[4], "volume": c[5]}
            for c in ohlcv
        ]

    def _evaluate_direction(
        self, hypothesis: Dict[str, Any], candles: List[Dict[str, float]]
    ) -> str:
        """Direction from momentum on real closes (lookback from params)."""
        lookback = int(hypothesis.get("parameters", {}).get("lookback", 5))
        closes = [c["close"] for c in candles]
        if len(closes) <= lookback:
            lookback = len(closes) - 1
        if lookback < 1:
            return "buy"
        return "buy" if closes[-1] > closes[-1 - lookback] else "sell"

    # ------------------------------------------------------------------
    # Feedback gating to AQDE
    # ------------------------------------------------------------------

    def _maybe_deliver_feedback(self, hypothesis: Dict[str, Any], symbol: str):
        key = self._position_key(hypothesis["hypothesis_id"], symbol)
        count = self.paper_trade_counts.get(key, 0)
        if count < self.min_paper_trades:
            return
        if self.feedback_delivered.get(key):
            return

        updates = {
            "feedback_paper_trades": count,
            "last_feedback_expectancy": hypothesis.get("expectancy", 0.0),
            "status": hypothesis.get("status"),
            "aqde_feedback_delivered_at": time.time(),
        }
        delivered = False
        if self._kb is not None and hasattr(self._kb, "update_hypothesis"):
            try:
                delivered = bool(
                    self._kb.update_hypothesis(hypothesis["hypothesis_id"], updates)
                )
            except Exception as exc:
                logger.warning("AQDE feedback failed for %s: %s", key, exc)
        if not delivered:
            merged = dict(self.hypotheses[hypothesis["hypothesis_id"]])
            merged.update(updates)
            self._save_hypothesis(merged)

        self.feedback_delivered[key] = True
        logger.info(
            "Feedback entregado a AQDE para %s tras %d paper trades", key, count
        )

    # ------------------------------------------------------------------
    # Feedback agregado por FAMILIA x SIMBOLO (opcion B)
    # ------------------------------------------------------------------

    def _family_of(self, hypothesis_id: str) -> str:
        rec = self.hypotheses.get(hypothesis_id) or {}
        st = rec.get("strategy_type", "")
        st = getattr(st, "value", None) or str(st)
        for fam in ("breakout", "mean_reversion", "momentum",
                    "trend_following"):
            if fam in st:
                return fam
        return st or "unknown"

    def _family_ops_all(self, symbol: str):
        """Cierres del simbolo en el libro (todas las familias)."""
        out = []
        if not os.path.exists(self.ledger_path):
            return out
        with open(self.ledger_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "motivo_cierre" in rec and rec.get("symbol") == symbol:
                    out.append(rec)
        return out

    def _family_ops(self, family: str, symbol: str):
        """Operaciones cerradas de la familia+simbolo segun el libro
        permanente (fuente durable; sobrevive reinicios)."""
        ops = []
        if not os.path.exists(self.ledger_path):
            return ops
        with open(self.ledger_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "motivo_cierre" not in rec or rec.get("symbol") != symbol:
                    continue
                hid = rec.get("hypothesis_id", "")
                if self._family_of(hid) == family:
                    ops.append(rec)
        ops.sort(key=lambda r: float(r.get("exit_time") or 0))
        return ops

    def _maybe_deliver_family_feedback(self, symbol: str,
                                       family: Optional[str] = None):
        """Entrega feedback AGREGADO por familia cuando las operaciones de esa
        familia cruzan multiplos del umbral — resuelve la rotacion de keys que
        impedaba llegar a min_paper_trades individual."""
        if not self.ledger_path or self.min_paper_trades < 1:
            return []
        delivered = []
        families = {family} if family else {
            self._family_of(r.get("hypothesis_id", ""))
            for r in self._family_ops_all(symbol)}
        for fam in list(families):
            if not fam or fam == "unknown":
                continue
            ops = self._family_ops(fam, symbol)
            n = len(ops)
            bucket = n // self.min_paper_trades
            if bucket == 0:
                continue
            mean_pnl = sum(float(o.get("pnl_pct") or 0) for o in ops) / n
            wins = sum(1 for o in ops
                       if float(o.get("pnl_pct") or 0) > 0)
            updates = {
                "feedback_family": fam,
                "feedback_family_ops": n,
                "feedback_family_wins": wins,
                "feedback_family_mean_pnl_pct": round(mean_pnl, 6),
                "aqde_family_feedback_at": time.time(),
                "status": None,
            }
            targets = [hid for hid, rec in self.hypotheses.items()
                       if rec.get("symbol") == symbol
                       and self._family_of(hid) == fam]
            for hid in targets:
                merged = dict(self.hypotheses[hid])
                merged.pop("status", None)          # no pisar estado real
                merged.update({k: v for k, v in updates.items()
                               if k != "status"})
                merged["status"] = self.hypotheses[hid].get("status")
                try:
                    if self._kb is not None and hasattr(
                            self._kb, "update_hypothesis"):
                        self._kb.update_hypothesis(hid, {
                            k: v for k, v in updates.items() if k != "status"})
                        self._save_hypothesis(merged)
                        continue
                except Exception as exc:
                    logger.warning("family feedback KB update fallo (%s)", exc)
                self._save_hypothesis(merged)
            last_bucket = getattr(self, "_family_last_bucket", {})
            if targets and bucket > last_bucket.get((fam, symbol), 0):
                delivered.append((fam, n, round(mean_pnl, 4)))
                logger.info(
                    "[family-feedback] %s/%s ops=%d wins=%d mean_pnl_pct=%.4f "
                    "-> %d registros del KB", fam, symbol, n, wins, mean_pnl,
                    len(targets))
                self._family_last_bucket = getattr(
                    self, "_family_last_bucket", {})
                self._family_last_bucket[(fam, symbol)] = bucket
        return delivered

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def decide(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Run one decision cycle for a symbol."""
        closed = self._check_exits(symbol)
        # feedback por familia tras cada posible cierre (fuente: ledger)
        self._maybe_deliver_family_feedback(symbol)

        best = self.select_best_hypothesis(symbol)
        exp = float(best.get("expectancy", 0.0)) if best else 0.0

        if best is None or (exp <= 0 and not self.learn_mode):
            logger.info("[no_entry] %s — %s", symbol, NO_ENTRY_REASON)
            return {
                "action": "no_entry",
                "symbol": symbol,
                "reason": NO_ENTRY_REASON,
                "signal": None,
            }

        hypothesis_id = best["hypothesis_id"]

        if self.has_open_position(hypothesis_id, symbol):
            logger.info(
                "[skip] %s/%s — posición ya abierta para esta hipótesis",
                hypothesis_id, symbol,
            )
            return {
                "action": "skip_position_guard",
                "symbol": symbol,
                "hypothesis_id": hypothesis_id,
                "reason": "posicion_abierta",
                "signal": None,
            }

        candles = self.fetch_real_data(symbol)
        side = self._evaluate_direction(best, candles)

        signal = {
            "action": "entry",
            "symbol": symbol,
            "side": side,
            "hypothesis_id": hypothesis_id,
            "expectancy": exp,
            "learn_entry": bool(self.learn_mode and exp <= 0),
            "scientific_score": float(best.get("scientific_score", 0.0)),
            "timestamp": time.time(),
            "price": candles[-1]["close"],
        }

        key = self._position_key(hypothesis_id, symbol)
        position = {"key": key, "opened_at": signal["timestamp"],
                    "side": side, "entry_price": signal["price"]}
        if self.take_profit_pct is not None:
            position["take_profit_pct"] = self.take_profit_pct
            position["stop_loss_pct"] = self.stop_loss_pct
        self.open_positions[key] = position
        self._append_state(self.positions_path, position)

        count = self.paper_trade_counts.get(key, 0) + 1
        self.paper_trade_counts[key] = count
        self._append_state(self.paper_trades_path, {"key": key, "count": count})

        self._maybe_deliver_feedback(best, symbol)
        fam = self._family_of(hypothesis_id)
        self._maybe_deliver_family_feedback(symbol, family=fam)

        logger.info("[entry] %s %s (hyp=%s, expectancy=%.4f)",
                    side.upper(), symbol, hypothesis_id, signal["expectancy"])
        return signal

    def run_cycle(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """Decide for all configured symbols."""
        return {symbol: self.decide(symbol) for symbol in self.symbols}
