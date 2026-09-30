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
from collections import deque
from typing import Any, Callable, Dict, List, Optional

from quant_math.decision_engine.event_bus import bus
from quant_math.risk.gate_policy import (
    append_gate_audit,
    resolve_gate_thresholds,
    resolve_learn_mode,
    round_trip_cost_pct,
)

logger = logging.getLogger(__name__)

QUERYABLE_STATUSES = ("validated", "backtested", "monte_carlo_tested", "failed")
NO_ENTRY_REASON = "sin hipótesis de expectativa positiva disponible"
DEFAULT_MIN_PAPER_TRADES = 3

# PA (expectancy viva): al cerrar operaciones se recalcula la expectancy del
# registro mezclando el valor estatico de generacion con el resultado real,
# con shrinkage bayesiano: primero la media propia hacia la media de familia,
# y luego el estimador realizado hacia la expectancy original.
LIVE_SHRINK_E = 5.0      # peso del dato propio vs expectancy de generacion
FAMILY_SHRINK_K = 3.0    # shrinkage de la media propia hacia la de familia

# LEARN MODE (correccion no3, 2026-09-29): con la exploracion activa el
# gate expectancy>0 se desactiva para que el sistema opere tambien
# hipotesis negativas y aprenda de sus errores (solo paper: el sistema
# nunca implementa ejecucion real).
#
# El default es GATE CERRADO y la politica vive en UN solo sitio,
# quant_math/risk/gate_policy.py. Antes se resolvia aqui con
# `os.environ.get(..., "0")` y los dos launchers la encendian con
# `setdefault(..., "1")`: por la puerta real el gate NUNCA estuvo cerrado.
# La auto-graduacion de mas abajo (que se desactiva sola cuando los
# ultimos cierres son netamente positivos) SE RESPETA tal cual; aqui solo
# se registra que se ha resuelto y por que.
def _learn_mode_default(explicit: Optional[bool] = None,
                       state_dir: Optional[str] = None,
                       event: str = "startup") -> bool:
    learn, source = resolve_learn_mode(explicit, state_dir, event)
    logger.info("[gate] LEARN_MODE=%s (origen=%s)", learn, source)
    return learn


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
        market: str = "crypto",
        timeframe: str = "1h",
        candle_limit: int = 100,
        min_paper_trades: int = DEFAULT_MIN_PAPER_TRADES,
        knowledge_base=None,
        data_provider: Optional[Callable[[str], List[List]]] = None,
        use_postgres: bool = True,
        take_profit_pct: Optional[float] = None,
        # Correccion no2 (2026-09-29): el SL ya NO se deriva de TP/2 a pelo.
        # En modo ROE llega DERIVADO y CLAMPADO contra la liquidacion. Si se
        # deja en None se conserva el legacy TP/2.
        stop_loss_pct: Optional[float] = None,
        # Objetivos declarados en ROE (fraccion del margen). Se guardan en la
        # posicion para que el ROE realizado sea medible en el libro.
        take_profit_roe: Optional[float] = None,
        stop_loss_roe: Optional[float] = None,
        leverage: int = 1,
        learn_mode: Optional[bool] = None,
        auto_graduate: Optional[bool] = None,
        graduate_window: Optional[int] = None,
        # Umbrales del gate (correccion no3). min_expectancy esta en la
        # MISMA unidad que el expectancy del KB: % de capital por trade.
        # 0.0 conserva la semantica anterior (solo el signo). El suelo de
        # score cierra, si el operador lo quiere, el agujero de que
        # `failed` sigue siendo operable (esta en QUERYABLE_STATUSES).
        min_expectancy: Optional[float] = None,
        min_scientific_score: Optional[float] = None,
        mode: str = "classic",
        burst_margin: float = 10.0,
        burst_leverage: int = 10,
    ):
        self.symbols = list(symbols)
        self.kb_path = kb_path
        self.state_dir = state_dir
        self.exchange_id = exchange_id
        self.market = (market or "crypto").lower()
        self.timeframe = timeframe
        self.candle_limit = candle_limit
        self.min_paper_trades = min_paper_trades
        self.mode = mode
        self.burst_margin = burst_margin
        self.burst_leverage = burst_leverage
        self.take_profit_pct = (
            float(take_profit_pct) if take_profit_pct is not None else None)
        self._stop_loss_pct_override = (
            float(stop_loss_pct) if stop_loss_pct is not None else None)
        self.take_profit_roe = (
            float(take_profit_roe) if take_profit_roe is not None else None)
        self.stop_loss_roe = (
            float(stop_loss_roe) if stop_loss_roe is not None else None)
        try:
            self.leverage = max(1, int(leverage))
        except (TypeError, ValueError):
            self.leverage = 1
        # Politica en un solo sitio + rastro en learn_mode_audit.jsonl.
        # El argumento explicito gana sobre la variable de entorno; si no
        # hay ninguno de los dos, el gate queda CERRADO.
        self.learn_mode, self.learn_mode_source = resolve_learn_mode(
            learn_mode, state_dir, "startup")
        self.learn_mode_requested = (None if learn_mode is None
                                     else bool(learn_mode))
        self.min_expectancy, self.min_scientific_score = (
            resolve_gate_thresholds(min_expectancy, min_scientific_score))
        logger.info(
            "[gate] umbral: expectancy > %.5f (%% capital/trade), "
            "scientific_score > %.3f",
            self.min_expectancy, self.min_scientific_score)
        if self.min_scientific_score > 0:
            logger.warning(
                "[gate] suelo de scientific_score activo (%.3f): las "
                "hipotesis `failed` por score dejan de ser operables",
                self.min_scientific_score)
        if self.learn_mode:
            logger.warning(
                "[LEARN MODE] gate expectancy>0 DESACTIVADO (origen=%s) — "
                "el sistema operara tambien hipotesis negativas (paper); "
                "cada entrada queda marcada learn_entry=true en el libro",
                self.learn_mode_source)

        # PB (auto-graduacion): cuando los ultimos N cierres tienen media
        # positiva, LEARN_MODE se desactiva solo y el gate expectancy>0
        # vuelve; la decision queda registrada y sobrevive reinicios.
        # O2: slippage adverso en fills paper (entrada Y salida)
        #
        # El 0,0005 que habia aqui era un SUPUESTO de un barrido propio, y
        # era 15 VECES mas caro que el spread real. El 2026-09-30 se leyo
        # el libro de Bybit: XRP/USDT:USDT tiene un spread de 0,0067%
        # estable, o sea que cruzar paga ~0,0034% por lado. Con el supuesto
        # el paper decia que operar costaba 0,10% cuando entrar A MERCADO
        # de verdad cuesta 0,127%: era OPTIMISTA para quien opera a mercado,
        # que es el fallo en la direccion contraria a la que protege.
        #
        # `order_type` distingue COMO se ejecuta, porque el coste depende de
        # eso y no del timeframe:
        #   market -> paga spread (mitad) y comision TAKER
        #   maker  -> no paga spread, paga comision MAKER
        try:
            self.order_type = str(os.environ.get(
                "QUANTMATH_ORDER_TYPE", "market")).strip().lower()
            if self.order_type not in ("market", "maker", "maker_only"):
                self.order_type = "market"
        except Exception:
            self.order_type = "market"
        self.taker = self.order_type == "market"

        # Default = mitad del spread REAL medido, no el supuesto.
        try:
            self.slippage_pct = abs(float(os.environ.get(
                "QUANTMATH_SLIPPAGE_PCT", "0.000034")))
        except ValueError:
            self.slippage_pct = 0.000034
        if self.slippage_pct:
            logger.info("[slippage] %.4f%% por lado | ejecucion=%s | "
                        "spread MEDIDO en Bybit 2026-09-30 "
                        "(QUANTMATH_SLIPPAGE_PCT para override)",
                        self.slippage_pct * 100, self.order_type)

        # V2 B4: burst-specific slippage (tighter for faster trades)
        if self.mode == "burst":
            try:
                self.burst_slippage_pct = abs(float(os.environ.get(
                    "QUANTMATH_BURST_SLIPPAGE_PCT", "0.000034")))
            except ValueError:
                self.burst_slippage_pct = 0.000034
        else:
            self.burst_slippage_pct = self.slippage_pct

        # Suelo de coste del motor de paper: ahora incluye la COMISION segun
        # como se ejecuta, que es lo que faltaba. El gate creia que operar
        # costaba 0,10% cuando a mercado son 0,127%.
        _slip = (self.burst_slippage_pct if self.mode == "burst"
                 else self.slippage_pct)
        self.cost_floor_pct = round_trip_cost_pct(_slip, taker=self.taker)

        # O6: sizing vol-targetado solo con gate activo (post-graduacion)
        self.vol_target_enabled = (
            self.learn_mode is False
            and os.environ.get("QUANTMATH_VOL_TARGET", "1") != "0")
        try:
            self.vol_target_pct = float(os.environ.get(
                "QUANTMATH_VOL_TARGET_PCT", "2.0"))
        except ValueError:
            self.vol_target_pct = 2.0

        self.graduated = False
        self.graduation_path = os.path.join(state_dir, "graduation.json")
        _ag = (os.environ.get("QUANTMATH_AUTO_GRADUATE", "1") != "0"
               if auto_graduate is None else bool(auto_graduate))
        _gw = (graduate_window if graduate_window is not None
               else int(os.environ.get("QUANTMATH_GRAD_WINDOW", "30")))
        self.auto_graduate = _ag
        self.graduate_window = max(1, int(_gw))
        _prev = {}
        if os.path.exists(self.graduation_path):
            try:
                with open(self.graduation_path, encoding="utf-8") as fh:
                    _prev = json.load(fh)
            except (OSError, json.JSONDecodeError):
                _prev = {}
        if _prev.get("graduated"):
            self.graduated = True
            if self.learn_mode:
                self.learn_mode = False
                logger.warning(
                    "[graduacion] previa detectada (%s) — gate "
                    "expectancy>0 permanece restaurado",
                    time.strftime("%Y-%m-%d %H:%M",
                                  time.localtime(_prev.get("at") or 0)))
        elif self.learn_mode and self.auto_graduate:
            logger.info("[graduacion] automatica armada: se desactivara "
                        "LEARN_MODE con %d cierres de media positiva",
                        self.graduate_window)

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
        # Ultimo cierre real visto por simbolo con su marca de tiempo. Lo
        # rellena la traza de cierres y lo reutiliza el marcado a mercado,
        # para no pagar una segunda descarga en el mismo ciclo.
        self._close_cache: Dict[str, Any] = {}
        self.paper_trade_counts: Dict[str, int] = {}
        self.feedback_delivered: Dict[str, bool] = {}
        self._load_state()

        if data_provider is not None:
            self._data_provider = data_provider
            self._exchange = None
        else:
            from data_acquisition.data_sources.forex import get_market_api
            self._exchange = get_market_api(exchange_id, market=self.market)
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
        # dual-write SIEMPRE: el espejo JSONL es la fuente de arranque del
        # engine; si solo escribiera PG, un reinicio perderia los updates
        # (bug post-graduacion: gate activo con universo cargado vacio)
        with open(self.kb_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False,
                                default=str) + "\n")

    def register_hypothesis(self, record: Dict[str, Any]) -> str:
        """Register/overwrite a hypothesis record in the JSONL KB."""
        hid = record.get("hypothesis_id") or f"hyp_{int(time.time() * 1000)}"
        record = dict(record, hypothesis_id=hid)
        self._save_hypothesis(record)
        return hid

    def ranked_candidates(self, symbol: str) -> List[Dict[str, Any]]:
        """Todos los candidatos consultables ordenados por
        (expectancy DESC, scientific_score DESC)."""
        candidates = [
            h for h in self.hypotheses.values()
            if h.get("symbol", h.get("asset")) == symbol
            and h.get("status") in QUERYABLE_STATUSES
        ]
        return sorted(
            candidates,
            key=lambda h: (-float(h.get("expectancy", 0.0)),
                           -float(h.get("scientific_score", 0.0))),
        )

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
        """SL en fraccion de PRECIO.

        Prioridad: el SL explicito (derivado del objetivo de ROE y CLAMPADO
        contra la liquidacion) -> si no, el legacy take_profit_pct / 2.
        El fallback se mantiene para no romper llamantes que no pasan ROE.
        """
        if self._stop_loss_pct_override is not None:
            return self._stop_loss_pct_override
        if self.take_profit_pct is None:
            return None
        return self.take_profit_pct / 2.0

    def has_open_position(self, hypothesis_id: str, symbol: str) -> bool:
        return self._position_key(hypothesis_id, symbol) in self.open_positions

    def record_external_closure(self, hypothesis_id: str, symbol: str,
                                exit_price: float,
                                motivo: str = "cerrada_en_el_exchange",
                                opened_at: Optional[float] = None,
                                extra: Optional[Dict[str, Any]] = None):
        """Registra un cierre que YA OCURRIO en el exchange, no aqui.

        Existe por un fallo medido el 2026-09-30: el TP/SL que puso el
        propio exchange ejecuto el cierre, y el motor no se entero porque
        `close_position` solo se llama cuando el cierre lo decide el motor.
        El resultado era doble y malo a la vez:

        - el libro no recibia el cierre, o sea que el SIS no tenia nada que
          aprender (que es justo para lo que se le puso a aprender);
        - el estado local seguia diciendo "abierta", luego con
          `max_open_positions=1` el brazo se quedaba bloqueado para
          siempre con `[RISK-HALT] open positions 1 >= max 1`.

        Por eso esto escribe el MISMO closure que `close_position`, con la
        misma forma, para que el SIS lo vea igual. Y con TRES diferencias
        deliberadas:

        1. NO se aplica `_slip()`: el precio es el relleno real que ya
           pago el exchange. Aplicar el adverso otra vez seria cobrar dos
           veces por lo mismo, que es justo el error que se corrigio en
           el modelo de coste.
        2. NO se llama a `live_close_hook`: no hay nada que cerrar, el
           exchange ya lo hizo.
        3. NO se inventa nada: si no se sabe el precio de salida, este
           metodo no se llama. Un PnL inventado seria exactamente el
           "operar con datos falsos" que no se permite.

        Idempotente por construccion: si la posicion ya no esta en
        `open_positions` devuelve None y no escribe nada.
        """
        key = self._position_key(hypothesis_id, symbol)
        pos = self.open_positions.pop(key, None)
        if pos is None:
            return None
        self._persist_positions()

        entry_price = float(pos.get("entry_price", 0.0))
        side = pos.get("side", "buy")
        direction = 1 if side == "buy" else -1
        qty, notional = self._last_entry_sizing(key)
        exit_px = float(exit_price)
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
            "entry_time": opened_at if opened_at is not None
                           else pos.get("opened_at"),
            "exit_time": time.time(),
            "motivo_cierre": motivo,
            # Que el cierre lo hizo el exchange y no este codigo. Sin esto
            # no se podria distinguir un TP normal de uno disparado a
            # mercado, que rellena al libro y no al precio del trigger.
            "cierre_externo": True,
        }
        if extra:
            closure.update(extra)
        self._append_state(self.ledger_path, closure)
        try:
            bus.publish("trade_closed", closure)
        except Exception as exc:            # pragma: no cover
            logger.warning("[cierre_externo] no se pudo publicar: %s", exc)
        logger.info("[cierre_externo] %s %s motivo=%s exit=%.8g pnl=%.4f "
                    "(%+.3f%%) | lo ejecuto el exchange, no el motor",
                    side.upper(), symbol, motivo, exit_px, pnl, pnl_pct)
        self._refresh_live_expectancy(hypothesis_id, symbol)
        self._maybe_graduate()
        return closure

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
        # O2: slippage adverso tambien al cerrar
        exit_px = self._slip(exit_px, side, entering=False)
        # En LIVE hay que mandar la orden de cierre al exchange; sin esto la
        # posicion se quita del estado local y se queda ABIERTA en Bybit
        # (correccion 6). En paper no se toca la red.
        live_result = None
        closer = getattr(self, "live_close_hook", None)
        if closer is not None:
            try:
                live_result = closer(symbol, side, qty)
            except Exception as exc:
                # No se borra la posicion local: si el cierre fallo, la
                # verdad sigue siendo que sigue abierta. Se registra el fallo
                # para que la reconciliacion lo recupere.
                logger.error("[live] cierre fallo %s %s: %s", symbol, side, exc)
                live_result = {"ok": False, "error": str(exc)}
                self.open_positions[key] = pos
                self._persist_positions()
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
        if live_result is not None:
            # Rastro de si el cierre fue de verdad al exchange o solo local
            # (correccion 6). Sin esto no se puede afirmar que algo se cerro.
            closure["live_close"] = live_result
        self._append_state(self.ledger_path, closure)
        
        # Publish Event (Architect Pub/Sub Enhancement)
        bus.publish("trade_closed", closure)
        
        logger.info("[cierre] %s %s motivo=%s exit=%.8g pnl=%.4f (%+.3f%%)",
                    side.upper(), symbol, motivo, exit_px, pnl, pnl_pct)
        self._refresh_live_expectancy(hypothesis_id, symbol)
        self._maybe_graduate()
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
        """SL vigente EN el momento de la entrada para key.

        Prioridad: el `stop_loss_pct` registrado en la fila de entrada (que es
        el clampado contra la liquidacion); si la fila es vieja y no lo trae,
        se deriva del take_profit_price con la regla legacy TP/2.
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
                    # El SL vigente en la entrada, si la fila nueva lo trae:
                    # es el unico que respeta el clamp de liquidacion (con
                    # apalancamientos altos SL != TP/2).
                    recorded_sl = rec.get("stop_loss_pct")
                    if recorded_sl is not None:
                        try:
                            sl = abs(float(recorded_sl))
                            continue
                        except (TypeError, ValueError):
                            pass
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
        # Misma cifra que usa el cierre -> la marca del flotante y el
        # precio de salida no pueden discrepar.
        self._close_cache[symbol] = (time.time(), cur)
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
        # La clave es "{hipotesis_id}:{simbolo}" y el simbolo PERPETUAL
        # contiene dos puntos ("BTC/USDT:USDT"). Con rsplit(":", 1) se
        # parte por el ULTIMO y sale "USDT" pelado: medido en el run real
        # del 2026-09-30, "bybit does not have market symbol USDT", y las
        # salidas de los perps no se podian comprobar. El hipotesis_id
        # nunca lleva dos puntos, asi que partir por el PRIMERO devuelve
        # el simbolo entero.
        symbols = sorted({k.split(":", 1)[-1]
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
    # Mark-to-market (correccion no3: el guard veia 0,00% de drawdown
    # con 5 posiciones abiertas en el SL)
    # ------------------------------------------------------------------

    #: Antiguedad maxima (s) para reutilizar el precio que ya se
    #: descargo en este ciclo. El ciclo dura 60-3600 s segun el modo;
    #: 300 s es un termino medio: no vuelve a bajar al exchange lo que se
    #: acaba de mirar, y a la vez una posicion de hace 10 min no se
    #: marca con un precio rancio.
    MTM_MAX_AGE_S = 300.0

    def _last_close(self, symbol: str,
                    max_age_s: Optional[float] = None) -> Optional[float]:
        """Ultimo cierre real del simbolo, o None si no se puede.

        Reutiliza el precio que la traza de cierres ya trajo en este
        ciclo (`_close_cache`); si no hay o esta rancio, lo pide otra
        vez por la MISMA fuente que usa el cierre: `fetch_real_data`.
        NUNCA inventa un precio: sin precio, la posicion queda sin
        marcar y el guard lo cuenta como no marcado (falla cerrado).
        """
        age_limit = (self.MTM_MAX_AGE_S if max_age_s is None
                     else float(max_age_s))
        hit = self._close_cache.get(symbol)
        if hit and (time.time() - hit[0]) <= age_limit:
            return float(hit[1])
        try:
            candles = self.fetch_real_data(symbol)
        except Exception as exc:
            logger.warning("[mtm] sin precio de %s: %s", symbol,
                           exc.__class__.__name__)
            return None
        cur = float(candles[-1]["close"])
        self._close_cache[symbol] = (time.time(), cur)
        return cur

    def mark_to_market(self) -> Dict[str, Any]:
        """PnL NO REALIZADO de las posiciones VIVAS, al precio actual.

        Devuelve `{"pnl_usd", "rows", "unpriced", "open"}`.

        Convenciones IDENTICAS a las del cierre real (`close_position`):
        - precio: el mismo ultimo cierre que usa la traza de SL/TP;
        - signo: `direction = +1 buy / -1 sell`;
        - costes: `_slip(..., entering=False)`, o sea el mismo slippage
          adverso de salida que sufre el cierre;
        - tamano: `_last_entry_sizing` (mismo qty/nocional que el libro).
        Duplicar estas reglas aqui fabricaria stop-loss falsos: por eso se
        reutilizan las funciones y no se recalcula nada a mano.

        `unpriced` = posiciones vivas que NO se han podido marcar (sin
        precio, o sin tamano en el libro). No se las inventa a cero: se
        declaran para que el guard decida.
        """
        rows = []
        unpriced = []
        total = 0.0
        by_symbol: Dict[str, List[str]] = {}
        for key in self.open_positions:
            # Partir por el PRIMERO dos puntos: el simbolo perp los lleva
            # (ver nota en check_exits_all).
            symbol = key.split(":", 1)[-1]
            by_symbol.setdefault(symbol, []).append(key)
        for symbol, keys in sorted(by_symbol.items()):
            price = self._last_close(symbol)
            for key in keys:
                pos = self.open_positions[key]
                side = pos.get("side", "buy")
                entry = float(pos.get("entry_price", 0.0) or 0.0)
                qty, notional = self._last_entry_sizing(key)
                if price is None or notional <= 0:
                    # Sin precio o sin nocional conocido NO hay PnL que
                    # calcular. Se declara; no se estima.
                    unpriced.append(key)
                    continue
                direction = 1 if side == "buy" else -1
                mark = self._slip(price, side, entering=False)
                pnl = qty * (mark - entry) * direction
                total += pnl
                rows.append({
                    "key": key,
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry,
                    "mark_price": mark,
                    "quantity": qty,
                    "notional_usd": notional,
                    "pnl_usd": pnl,
                    "pnl_pct": (pnl / notional * 100.0) if notional else 0.0,
                    "opened_at": pos.get("opened_at"),
                })
        if unpriced:
            logger.warning(
                "[mtm] %d posicion(es) SIN marcar: %s — el guard las "
                "cuenta como riesgo no medido",
                len(unpriced), ", ".join(unpriced))
        return {"pnl_usd": total, "rows": rows, "unpriced": unpriced,
                "open": len(self.open_positions)}

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
        """Familia canonica de una hipotesis (feedback agregado por familia).

        Delega en `quant_math.ml.families.family_of`: aqui habia una QUINTA
        copia del vocabulario con su propia semantica, y con un
        `strategy_type` en hoja o en mayusculas fragmentaba el agregado en
        un bucket que nadie consultaba (correccion 4).
        """
        from quant_math.ml.families import family_of
        rec = self.hypotheses.get(hypothesis_id) or {}
        return family_of(rec.get("strategy_type", ""))

    def _slip(self, price: float, side: str, entering: bool) -> float:
        """O2: precio adverso por slippage. Comprar entra caro y sale barato
        (al cerrar vendo); vender es el espejo. Siempre en contra del que
        ejecuta -> estimacion conservadora.

        En MAKER no se aplica: una orden que COLOCA en el libro no cruza y
        por tanto no es adverse; lo que paga es la comision maker, que va
        aparte en `cost_floor_pct`. Aplicar aqui el slippage en maker seria
        cobrar dos veces por lo mismo.
        """
        if not getattr(self, "taker", True):
            return price
        s = self.burst_slippage_pct if self.mode == "burst" else self.slippage_pct
        if not s or price <= 0:
            return price
        adverse_up = (side == "buy") == entering
        return price * (1 + s) if adverse_up else price * (1 - s)

    @staticmethod
    def _ema_simple(prices, span):
        """V2 B3: EMA simple para trend filter burst."""
        alpha = 2.0 / (span + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = p * alpha + ema * (1 - alpha)
        return ema

    def _sizing_vol_multiplier(self, candles) -> float:
        """O6: multiplicador de nocional por volatilidad realizada
        (objetivo QUANTMATH_VOL_TARGET_PCT % por ciclo), clampeado x0.5-x2."""
        import statistics as _st
        closes = [float(c["close"]) for c in candles[-21:]]
        if len(closes) < 6 or min(closes) <= 0:
            return 1.0
        rets = [(closes[i] / closes[i - 1] - 1.0)
                for i in range(1, len(closes))]
        vol = _st.pstdev(rets)
        if vol <= 1e-9:
            return 1.0
        target = self.vol_target_pct / 100.0
        return max(0.5, min(2.0, target / vol))

    def _own_ops(self, hypothesis_id: str, symbol: str):
        """Cierres de UNA hipotesis+simbolo segun el libro permanente."""
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
                if ("motivo_cierre" in rec
                        and rec.get("hypothesis_id") == hypothesis_id
                        and rec.get("symbol") == symbol):
                    ops.append(rec)
        return ops

    def _refresh_live_expectancy(self, hypothesis_id: str, symbol: str):
        """PA: expectancy viva con shrinkage bayesiano doble.

        1) est = (n*media_propia + K_fam*media_familia) / (n + K_fam)
        2) exp_new = w*exp_generacion + (1-w)*est,  w = n/(n + E)

        Con pocos datos domina la expectancy de generacion; con muchos,
        el resultado real. Persiste en KB (o JSONL) y actualiza la copia
        en memoria, por lo que el ranking de decide() se auto-mejora."""
        rec = self.hypotheses.get(hypothesis_id)
        if rec is None or rec.get("symbol", rec.get("asset")) != symbol:
            return
        own = self._own_ops(hypothesis_id, symbol)
        n = len(own)
        if n == 0:
            return
        own_mean = sum(float(o.get("pnl_pct") or 0.0) for o in own) / n

        fam_ops = self._family_ops(self._family_of(hypothesis_id), symbol)
        fam_mean = None
        if fam_ops:
            fam_mean = sum(float(o.get("pnl_pct") or 0.0)
                           for o in fam_ops) / len(fam_ops)
            est = ((n * own_mean + FAMILY_SHRINK_K * fam_mean)
                   / (n + FAMILY_SHRINK_K))
        else:
            est = own_mean

        exp_gen = float(rec.get("expectancy", 0.0))
        w = n / (n + LIVE_SHRINK_E)
        exp_new = w * exp_gen + (1.0 - w) * est
        if abs(exp_new - exp_gen) < 1e-9:
            return

        updates = {
            "expectancy": round(exp_new, 8),
            "expectancy_source": "live_shrunk",
            "live_expectancy_updated_at": time.time(),
            "live_expectancy_n": n,
        }
        delivered = False
        if self._kb is not None and hasattr(self._kb, "update_hypothesis"):
            try:
                delivered = bool(
                    self._kb.update_hypothesis(hypothesis_id, updates))
            except Exception as exc:
                logger.warning("[exp-refresh] fallo KB para %s: %s",
                               hypothesis_id, exc.__class__.__name__)
        rec.update(updates)
        # persistencia SIEMPRE: ademas del KB (PG), el JSONL local queda
        # sincronizado como fuente de carga del engine (ultimo registro gana)
        merged = dict(rec)
        merged.update(updates)
        self._save_hypothesis(merged)
        logger.info("[exp-refresh] %s/%s exp %.4f -> %.4f "
                    "(n=%d fam_mean=%s)",
                    hypothesis_id, symbol, exp_gen, exp_new, n,
                    f"{fam_mean:.4f}" if fam_mean is not None else "-")

    def _maybe_graduate(self):
        """O1/PB: desactiva LEARN_MODE cuando la ventana movil de cierres es
        estadisticamente positiva: media > 0 CON limite inferior del IC90
        (normal approx) > 0 Y diversidad minima de familias. Unica vez;
        persistida en runtime/state/graduation.json."""
        if (self.graduated or not self.learn_mode or not self.auto_graduate
                or not os.path.exists(self.ledger_path)):
            return
        try:
            min_fams = int(os.environ.get("QUANTMATH_GRAD_MIN_FAMILIES", "2"))
        except ValueError:
            min_fams = 2
        rows = deque(maxlen=self.graduate_window)   # (pnl_pct, familia)
        with open(self.ledger_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "motivo_cierre" in rec:
                    hid = rec.get("hypothesis_id", "")
                    rows.append((float(rec.get("pnl_pct") or 0.0),
                                 self._family_of(hid)))
        n = len(rows)
        if n < self.graduate_window:
            return
        vals = [v for v, _ in rows]
        mean = sum(vals) / n
        if mean <= 0:
            return
        # IC90 (alpha=10%) limite inferior: mean - z*sd/sqrt(n)
        import statistics as _st
        sd = _st.pstdev(vals)
        ic90_lb = mean - 1.2816 * sd / (n ** 0.5)
        fams = {f for _, f in rows}
        if ic90_lb <= 0:
            logger.info("[graduacion] media %+.3f%% positiva pero IC90_lb "
                        "%.3f%% <= 0 — sigo aprendiendo", mean, ic90_lb)
            return
        if len(fams) < max(1, min_fams):
            logger.info("[graduacion] IC90_lb %.3f%% OK pero familias %d < "
                        "%d — sigo aprendiendo", ic90_lb, len(fams), min_fams)
            return
        self.learn_mode = False
        self.graduated = True
        append_gate_audit(os.path.dirname(self.graduation_path), {
            "ts": time.time(),
            "event": "auto_graduation",
            "learn_mode": False,
            "source": "auto_graduate",
            "window": self.graduate_window,
            "mean_pnl_pct": round(mean, 6),
            "ic90_lower_bound": round(ic90_lb, 6),
            "families": sorted(fams),
            "pid": os.getpid(),
        })
        payload = {
            "graduated": True,
            "at": time.time(),
            "window": self.graduate_window,
            "mean_pnl_pct": round(mean, 6),
            "ic90_lower_bound": round(ic90_lb, 6),
            "families": sorted(fams),
            "criterion": "O1: mean>0 AND ic90_lb>0 AND families>=min",
        }
        try:
            with open(self.graduation_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.warning("[graduacion] no se pudo persistir: %s",
                           exc.__class__.__name__)
        logger.warning(
            "[graduacion O1] LEARN_MODE DESACTIVADO automaticamente — "
            "media %+.3f%% (IC90_lb %+.3f%%) en %d cierres de %d familias; "
            "gate expectancy>0 restaurado", mean, ic90_lb, n, len(fams))

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

        # P1: ranking completo con fallback — si el mejor candidato tiene
        # posicion abierta, se prueba el siguiente mejor (gate por candidato).
        candidates = self.ranked_candidates(symbol)
        chosen = None
        first_guard_hyp = None

        for cand in candidates:
            exp_c = float(cand.get("expectancy", 0.0))
            # El ranking es por expectancy DESC: en cuanto uno cae al
            # umbral, todos los siguientes tambien (o son <= 0).
            if exp_c <= self.min_expectancy and not self.learn_mode:
                break
            # El suelo de score solo muerde si el operador lo SUBE. Con
            # el default 0.0 no filtra nada: es la semantica anterior
            # exacta y no introduce un cambio de comportamiento medido
            # por la correccion no3. Medido en el KB: 0 de 495 filas
            # tienen score 0, asi que el filtro existe pero es inerte.
            if (self.min_scientific_score > 0
                    and float(cand.get("scientific_score", 0.0))
                    <= self.min_scientific_score and not self.learn_mode):
                continue    # no pasa el suelo de score: probar la
                             # siguiente, que puede tenerlo mas bajo
            cand_id = cand["hypothesis_id"]
            if self.has_open_position(cand_id, symbol):
                if first_guard_hyp is None:
                    first_guard_hyp = cand_id
                continue                   # probar siguiente mejor
            chosen = cand
            break

        if chosen is None:
            if first_guard_hyp is not None:
                logger.info(
                    "[skip] %s/%s — posicion ya abierta para esta hipotesis "
                    "(sin candidatos libres)", first_guard_hyp, symbol)
                return {
                    "action": "skip_position_guard",
                    "symbol": symbol,
                    "hypothesis_id": first_guard_hyp,
                    "reason": "posicion_abierta",
                    "signal": None,
                }
            logger.info("[no_entry] %s — %s", symbol, NO_ENTRY_REASON)
            return {
                "action": "no_entry",
                "symbol": symbol,
                "reason": NO_ENTRY_REASON,
                "signal": None,
            }

        best = chosen
        exp = float(best.get("expectancy", 0.0))
        hypothesis_id = best["hypothesis_id"]

        candles = self.fetch_real_data(symbol)
        side = self._evaluate_direction(best, candles)

        # V2 B3: burst trend filter — side must align with EMA trend
        if self.mode == "burst":
            closes = [float(c["close"]) for c in candles]
            if len(closes) >= 21:
                ef, es = self._ema_simple(closes, 8), self._ema_simple(closes, 21)
                trend_up = ef > es
                if (side == "buy" and not trend_up) or (side == "sell" and trend_up):
                    return {
                        "action": "no_entry",
                        "symbol": symbol,
                        "hypothesis_id": hypothesis_id,
                        "reason": "burst_trend_filter",
                        "signal": None,
                    }

        # O2: fill adverso en la entrada
        fill_price = self._slip(float(candles[-1]["close"]), side, True)
        # O6: multiplicador vol-target solo con gate activo
        sizing_mult = (self._sizing_vol_multiplier(candles)
                       if self.vol_target_enabled else 1.0)

        signal = {
            "action": "entry",
            "symbol": symbol,
            "side": side,
            "hypothesis_id": hypothesis_id,
            "expectancy": exp,
            "learn_entry": bool(self.learn_mode and exp <= 0),
            "gate_open": bool(self.learn_mode),
            "gate_min_expectancy": self.min_expectancy,
            "min_scientific_score": self.min_scientific_score,
            # Diagnostico de coste (ver __init__): el edge del backtest
            # frente a lo que cuesta entrar y salir en paper.
            "cost_floor_pct": self.cost_floor_pct,
            "scientific_score": float(best.get("scientific_score", 0.0)),
            "sizing_mult": round(sizing_mult, 4),
            "timestamp": time.time(),
            "price": fill_price,
        }

        key = self._position_key(hypothesis_id, symbol)
        position = {"key": key, "opened_at": signal["timestamp"],
                    "side": side, "entry_price": signal["price"]}
        if self.take_profit_pct is not None:
            position["take_profit_pct"] = self.take_profit_pct
            position["stop_loss_pct"] = self.stop_loss_pct
        if self.take_profit_roe is not None:
            position["take_profit_roe"] = self.take_profit_roe
        if self.stop_loss_roe is not None:
            position["stop_loss_roe"] = self.stop_loss_roe
        position["leverage"] = self.leverage
        self.open_positions[key] = position
        self._append_state(self.positions_path, position)

        count = self.paper_trade_counts.get(key, 0) + 1
        self.paper_trade_counts[key] = count
        self._append_state(self.paper_trades_path, {"key": key, "count": count})

        self._maybe_deliver_feedback(best, symbol)
        fam = self._family_of(hypothesis_id)
        self._maybe_deliver_family_feedback(symbol, family=fam)
        
        # Publish Entry Event (Architect Pub/Sub Enhancement)
        bus.publish("trade_opened", symbol=symbol, hypothesis_id=hypothesis_id, side=side)

        logger.info(
            "[entry] %s %s (hyp=%s, expectancy=%.4f, umbral=%.4f, "
            "score=%.3f, learn=%s%s)",
            side.upper(), symbol, hypothesis_id, signal["expectancy"],
            self.min_expectancy, signal["scientific_score"],
            bool(self.learn_mode), "/EXPLORACION" if self.learn_mode else "")
        return signal

    def run_cycle(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """Decide for all configured symbols."""
        return {symbol: self.decide(symbol) for symbol in self.symbols}
