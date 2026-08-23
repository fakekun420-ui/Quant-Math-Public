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
    ):
        self.symbols = list(symbols)
        self.kb_path = kb_path
        self.state_dir = state_dir
        self.exchange_id = exchange_id
        self.timeframe = timeframe
        self.candle_limit = candle_limit
        self.min_paper_trades = min_paper_trades

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
        self._load_jsonl()

        self.positions_path = os.path.join(state_dir, "positions.jsonl")
        self.paper_trades_path = os.path.join(state_dir, "paper_trades.jsonl")
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

    def _load_jsonl(self):
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
        with open(self.kb_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

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

    def _append_state(self, path: str, record: Dict[str, Any]):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _position_key(hypothesis_id: str, symbol: str) -> str:
        return f"{hypothesis_id}:{symbol}"

    def has_open_position(self, hypothesis_id: str, symbol: str) -> bool:
        return self._position_key(hypothesis_id, symbol) in self.open_positions

    def close_position(self, hypothesis_id: str, symbol: str):
        self.open_positions.pop(self._position_key(hypothesis_id, symbol), None)

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
    # Main loop
    # ------------------------------------------------------------------

    def decide(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Run one decision cycle for a symbol."""
        best = self.select_best_hypothesis(symbol)

        if best is None or float(best.get("expectancy", 0.0)) <= 0:
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
            "expectancy": float(best.get("expectancy", 0.0)),
            "scientific_score": float(best.get("scientific_score", 0.0)),
            "timestamp": time.time(),
            "price": candles[-1]["close"],
        }

        key = self._position_key(hypothesis_id, symbol)
        position = {"key": key, "opened_at": signal["timestamp"],
                    "side": side, "entry_price": signal["price"]}
        self.open_positions[key] = position
        self._append_state(self.positions_path, position)

        count = self.paper_trade_counts.get(key, 0) + 1
        self.paper_trade_counts[key] = count
        self._append_state(self.paper_trades_path, {"key": key, "count": count})

        self._maybe_deliver_feedback(best, symbol)

        logger.info("[entry] %s %s (hyp=%s, expectancy=%.4f)",
                    side.upper(), symbol, hypothesis_id, signal["expectancy"])
        return signal

    def run_cycle(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """Decide for all configured symbols."""
        return {symbol: self.decide(symbol) for symbol in self.symbols}
