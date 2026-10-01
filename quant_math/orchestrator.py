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
from quant_math.risk.circuit_breaker import (
    DEFAULT_MAX_DAILY_LOSS_PCT,
    DailyGuard,
    daily_loss_usd,
    utc_day_start_ts,
)
from quant_math.risk.roe_targets import (
    DEFAULT_MAINTENANCE_MARGIN_RATE,
    DEFAULT_MAX_RISK_PER_TRADE_PCT,
    DEFAULT_SL_LIQUIDATION_SAFETY_FRAC,
    build_roe_plan,
    tp_sl_prices,
    validate_roe_plan,
)

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
    market: str = "crypto"                  # "crypto" (ccxt) or "forex" (Yahoo)
    dry_run: bool = True                    # True=paper trading ONLY (no live path yet)
    use_postgres: bool = False               # KB storage: always JSONL (PG removed)
    mode: str = "classic"                   # "classic" or "burst"

    # Burst-mode specifics (only used when mode == "burst")
    burst_margin: float = 10.0              # USD margin per burst entry
    burst_leverage: int = 10                # leverage multiplier (1-20)

    # Classic-mode leverage (1 = no leverage)
    leverage: int = 1                       # leverage multiplier for classic mode

    # --- TP/SL por ROE (correccion no2, 2026-09-29) ----------------------
    # Fuente unica de verdad: quant_math/risk/roe_targets.py
    # Si se pasa take_profit_roe y/o stop_loss_roe, el plan se deriva SOLO del
    # apalancamiento (distancia_precio = roe / L) y take_profit_pct pasa a ser
    # un valor DERIVADO, reescrito en __post_init__. El SL se clampa para que
    # caiga siempre ANTES de la liquidacion, y si el plan no es operable el
    # arranque se RECHAZA (__post_init__ lanza). Si ambos son None se conserva
    # el modo legado por fraccion de precio (deprecated).
    take_profit_roe: Optional[float] = None   # ej. 0.50 = 50% del MARGEN
    stop_loss_roe: Optional[float] = None     # ej. 0.25 = 25% del MARGEN
    # SUPUESTO, no lectura de la API de Bybit (ver roe_targets). El operador
    # debe confirmarlo contra la documentacion vigente del exchange.
    maintenance_margin_rate: float = DEFAULT_MAINTENANCE_MARGIN_RATE
    # El SL en precio <= esta fraccion de la distancia a liquidacion.
    sl_liquidation_safety_frac: float = DEFAULT_SL_LIQUIDATION_SAFETY_FRAC
    # Tope de APALANCAMIENTO EFECTIVO por encima del cual el TP en ROE exigiria
    # mas recorrido de precio del admisible. None = segun mercado.
    max_tp_price_distance: Optional[float] = None
    # Tope de RIESGO por operacion, en USD. None -> initial_capital * pct.
    max_risk_per_trade_usd: Optional[float] = None
    max_risk_per_trade_pct: float = DEFAULT_MAX_RISK_PER_TRADE_PCT

    # Derivados por __post_init__ (no lospongas al construir)
    stop_loss_pct: Optional[float] = None
    effective_leverage: int = 1
    roe_mode: bool = False

    # --- Circuit breaker (Fase 1b) — enforced in run_cycle ------------
    # OJO CON EL NOMBRE (correccion no3, 2026-09-29): esto limita el DANO
    # POR DIA, no el numero de operaciones. El paper es ilimitado en
    # tiempo (decision de Leonardo): se opera toda la noche, pero si el
    # dia se vuelve negativo se DEJA DE ABRIR. `max_daily_loss_pct` es la
    # forma honesta de expresarlo (5% del capital); en USD se traduce
    # con el capital inicial. Si se pasan los dos, manda el USD.
    max_daily_loss_pct: Optional[float] = DEFAULT_MAX_DAILY_LOSS_PCT
    max_daily_loss_usd: Optional[float] = None
    max_open_positions: int = 5             # block entries at/above this count
    drawdown_limit: float = 0.2             # block entries past this drawdown
    max_position_pct: float = 0.2           # max margin per entry vs account
    # Techo de NOCIONAL por entrada, como fraccion del capital. Es el
    # freno que falta para que el apalancamiento no infle la posicion.
    #
    # MEDIDO el 2026-09-30 con el plan de Leonardo (5 USDT de capital, 50x,
    # SL al 0,5%): el tope de RIESGO por operacion daba 0,10 USDT (2% de
    # 5), y con un SL del 0,5% eso autoriza 0,10 / 0,005 = 20 USDT de
    # nocional. O sea 4x el capital. El tope de riesgo cumplia su trabajo
    # (el riesgo eran exactamente 0,10 USDT) pero la POSICION era cuatro
    # veces mas grande de la que el plan pedia.
    #
    # La razon: el riesgo y el tamano son cosas distintas, y con
    # apalancamiento dejan de ir juntas. Un SL muy corto permite una
    # posicion enorme con poco riesgo, y el capital no limita nada porque
    # el margen es una fraccion minuscula. Por eso hace falta un tope que
    # mire el NOCIONAL y no solo lo que se puede perder.
    #
    # None = sin tope (comportamiento anterior). Se recomienda fijarlo
    # siempre que se opere con apalancamiento.
    max_notional_per_entry_pct: Optional[float] = None
    # ¿Exigir margen AISLADO antes de operar?
    #
    # MEDIDO el 2026-09-30: la cuenta de testnet es una UNIFIED ACCOUNT y
    # Bybit responde `100028 unified account is forbidden` al pedir aislado.
    # El modo aislado NO EXISTE en esa cuenta y no se va a conseguir
    # reintentando. Con esto en True el motor se niega a abrir SIEMPRE, o
    # sea que el sistema no operaria nunca.
    #
    # Por eso el defecto es False y no True, y no es relajar la garantia sin
    # mas: con nocional PEQUEÑO el riesgo de cuenta esta acotado por el
    # propio nocional, no por el modo de margen. Medido con el plan de
    # Leonardo (5 USDT de nocional, 50x, SL al 0,5%):
    #
    #     perdida en el SL        5 x 0,5%  = 0,025 USDT
    #     hasta la liquidacion    5 x 1,67% = 0,083 USDT   (margen 0,10)
    #     peor caso absoluto      5 USDT     (si el activo cae a cero)
    #
    # O sea: en cruce, como muy tarde, se pierden los 5 USDT de nocional.
    # Con un nocional grande, en cambio, una sola posicion puede vaciar la
    # cuenta entera, y ahi el aislado si es imprescindible.
    #
    # El log sigue avisando en mayusculas cuando opera en cruce, y el
    # informe de la operacion lleva `margin_mode` para que se pueda ver.
    require_isolated_margin: bool = False
    # Cada cuantos ciclos se reconcilian las posiciones contra el exchange.
    # Por defecto TODAS LAS HORAS (24 ciclos a intervalo 1h = una vez por
    # hora), no 0. Con 0 no se comparaba nunca y una posicion huerfana con
    # apalancamiento es dinero en riesgo que nadie vigila; pero 1 por ciclo
    # daria 86.400 llamadas al dia al exchange, que es peor. A 24 el coste
    # es 24 llamadas al dia y la ventana de datos sucios es de una hora.
    reconcile_every_n_cycles: int = 24
    # Al detectar una huerfana en el exchange, cerrarla es una DECISION, no
    # una consecuencia de medir. Por defecto solo avisa y deja que un humano
    # (o el ciclo siguiente) decida. Poner True para cerrar automaticamente.
    reconcile_auto_close: bool = False
    # Una posicion por simbolo. Bybit funde las ordenes del mismo activo
    # (modo net): dos cortas sobre XRP se convierten en UNA sola posicion
    # con entrada ponderada. Si el motor guarda una posicion local por
    # hipotesis, el estado local acaba teniendo MAS posiciones que el
    # exchange, y al cerrar de golpe el TP quedan todas como fantasma.
    #
    # MEDIDO el 2026-09-30 con el brazo corriendo: 5 posiciones locales
    # (5 hipotesis) contra 1 en el exchange (33 XRP). Consecuencias: el
    # brazo quedo bloqueado con `open positions 5 >= max 5`, el PnL
    # flotante que se mostraba (+0,15) era FICTICIO porque la posicion ya
    # estaba cerrada, y los 5 cierres no entraron al libro, luego el SIS
    # no aprendio nada.
    #
    # False solo tiene sentido en modo HEDGE, donde el exchange SI admite
    # posiciones separadas en la misma direccion. En net no.
    one_position_per_symbol: bool = True
    # Posiciones vivas que pueden quedar SIN marcar (sin precio o sin
    # tamano en el libro) antes de bloquear entradas. 0 = falla cerrado.
    max_unpriced_positions: int = 0

    # --- Gate de decision (correccion no3) -----------------------------
    # None = lo que diga QUANTMATH_LEARN_MODE. El DEFAULT es gate CERRADO
    # (solo expectancy > min_expectancy). True abre la exploracion de
    # forma EXPLICITA y queda registrada en learn_mode_audit.jsonl.
    # EXPLORACION POR DEFECTO (decision de Leonardo, 2026-09-30).
    #
    # "Que no haya min_expectancy": el umbral de 0.0 solo servia para
    # cerrar por defecto un gate que, en paper, no cuesta nada abrir. Sin
    # umbral no hay nada que recalibrar y el sistema opera siempre, que es
    # lo que hace falta para que el SIS tenga material con el que aprender.
    #
    # El default es True y por eso `None` significa "lo que toque". Para
    # operar solo con expectativa positiva hay que pasar False
    # explicitamente, que queda registrado en learn_mode_audit.jsonl.
    #
    # OJO: esto solo es gratis en paper y en testnet. En MAINNET sigue
    # BLOQUEADO (ver __post_init__): abrir el gate ahi es perder dinero en
    # cada operacion, y el aprendizaje seria una donacion.
    learn_mode: Optional[bool] = True
    # % de capital por trade. 0.0 = solo el signo (semantica anterior).
    min_expectancy: Optional[float] = None
    min_scientific_score: Optional[float] = None

    # Live-trading path (Fase 2-4)
    shadow_live: bool = False               # log shadow_orders.jsonl intent
    testnet: bool = True                    # live orders only allowed on testnet

    def __post_init__(self):
        if not self.symbols:
            raise ValueError("symbols no puede estar vacío")
        if not 0 < self.entry_pct <= 1:
            raise ValueError(f"entry_pct debe estar en (0, 1], recibido {self.entry_pct}")
        if (self.max_notional_per_entry_pct is not None
                and not 0 < float(self.max_notional_per_entry_pct) <= 1):
            raise ValueError(
                "max_notional_per_entry_pct debe estar en (0, 1], recibido "
                f"{self.max_notional_per_entry_pct}")
        if self.take_profit_pct <= 0:
            raise ValueError(f"take_profit_pct debe ser > 0, recibido {self.take_profit_pct}")
        if self.min_paper_trades < 1:
            raise ValueError(f"min_paper_trades inválido: {self.min_paper_trades}")
        if self.hypotheses_per_cycle < 1:
            raise ValueError(f"hypotheses_per_cycle inválido: {self.hypotheses_per_cycle}")
        if self.mode not in ("classic", "burst"):
            raise ValueError(f"mode debe ser 'classic' o 'burst', recibido '{self.mode}'")
        self.market = (self.market or "crypto").lower()
        if self.market not in ("crypto", "forex"):
            raise ValueError(f"market debe ser 'crypto' o 'forex', recibido '{self.market}'")
        # Circuit-breaker sanity
        if self.max_daily_loss_usd is None:
            pct = (DEFAULT_MAX_DAILY_LOSS_PCT
                   if self.max_daily_loss_pct is None
                   else float(self.max_daily_loss_pct))
            if not 0 < pct <= 1:
                raise ValueError(
                    f"max_daily_loss_pct debe estar en (0, 1], recibido {pct}")
            self.max_daily_loss_usd = daily_loss_usd(
                float(self.initial_capital), pct)
            self.max_daily_loss_pct = pct
        else:
            self.max_daily_loss_usd = float(self.max_daily_loss_usd)
        if self.max_daily_loss_usd < 0:
            raise ValueError("max_daily_loss_usd debe ser >= 0")
        if self.max_unpriced_positions < 0:
            raise ValueError("max_unpriced_positions debe ser >= 0")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions debe ser >= 1")
        if not 0 < self.drawdown_limit <= 1:
            raise ValueError("drawdown_limit debe estar en (0, 1]")
        if not 0 < self.max_position_pct <= 1:
            raise ValueError("max_position_pct debe estar en (0, 1]")
        # EXPLORACION + DINERO REAL = PERDIDA GARANTIZADA.
        #
        # `learn_mode` abre el gate `expectancy > 0`, es decir: admite operar
        # con expectativa MATEMATICA NEGATIVA a proposito, para reunir datos con
        # los que el SIS aprenda. En paper no cuesta nada: por eso el paper
        # ilimitado en tiempo es la forma correcta de explorar.
        #
        # En MAINNET eso es cada trade perdiendo dinero, y el "aprendizaje"
        # seria en realidad una donacion. Por eso se BLOQUEA, y sin mando
        # trasero: no hay variable de entorno que lo esquive. Si hay que
        # explorar en vivo, se hace en TESTNET, que es dinero del exchange y
        # no tuyo.
        #
        # Medido antes de poner esto: no existia NINGUNA proteccion — ni aqui
        # ni en el motor, que ni siquiera recibe `dry_run`.
        if not self.dry_run and not self.testnet and self.learn_mode:
            raise ValueError(
                "learn_mode=True esta BLOQUEADO en mainnet por diseno: abre "
                "el gate expectancy>0 y opera con expectativa negativa a "
                "proposito, lo que es perdida garantizada con dinero real. "
                "Opciones: (a) explorar en paper, que es gratis y es donde el "
                "aprendizaje tiene sentido; (b) explorar en testnet "
                "(testnet=True, dry_run=False), que ejercita el circuito "
                "completo sin dinero propio; (c) si de verdad quieres aceptar "
                "la perdida en mainnet, deja learn_mode=False y baja "
                "min_expectancy, que si queda registrado en "
                "learn_mode_audit.jsonl y en cada entrada del ledger"
            )
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
        # Leverage constraints — dynamic per-asset max (BTC 150x crypto,
        # FX majors up to 500x). Wizard validates against the venue max
        # (Bybit per-asset / FX 500); here only lower bound + absolute 500.
        if self.mode == "burst":
            self.interval_seconds = min(self.interval_seconds, 15)
            self.burst_margin = max(1.0, self.burst_margin)
            self.burst_leverage = max(1, min(500, int(self.burst_leverage)))
            # SIN suelo artificial: el max(0.02, ...) que habia aqui era la
            # causa directa de que el SL fuera inalcanzable (medido en la
            # auditoria 2026-09-29). El tope superior se mantiene.
            self.take_profit_pct = min(0.50, self.take_profit_pct)
        self.leverage = max(1, min(500, int(self.leverage)))

        # --- TP/SL en ROE + validacion de alcanzabilidad ---------------
        # Ocurre AQUI, al arrancar, no en la ejecucion: es preferible
        # negarse a arrancar a arrancar con un SL inalcanzable.
        self.effective_leverage = (self.burst_leverage if self.mode == "burst"
                                    else self.leverage)
        self.roe_mode = (self.take_profit_roe is not None
                         or self.stop_loss_roe is not None)
        self.roe_plan = None
        if self.roe_mode:
            plan = build_roe_plan(
                mode=self.mode,
                leverage=self.effective_leverage,
                take_profit_roe=self.take_profit_roe,
                stop_loss_roe=self.stop_loss_roe,
                maintenance_margin_rate=self.maintenance_margin_rate,
                sl_liquidation_safety_frac=self.sl_liquidation_safety_frac,
                market=self.market,
                max_tp_price_distance=self.max_tp_price_distance,
            )
            for warn in plan.warnings:
                logger.warning("[roe] %s", warn)
            # Lanza si el plan no es operable -> el arranque se rechaza.
            validate_roe_plan(plan)
            self.roe_plan = plan
            self.take_profit_roe = plan.tp_roe
            self.stop_loss_roe = plan.sl_roe_requested
            self.take_profit_pct = plan.tp_price_distance
            self.stop_loss_pct = plan.sl_price_distance
            logger.info("[roe] %s", plan.describe())
        else:
            # Modo legado: TP/SL en fraccion de precio. Se conserva por
            # compatibilidad con llamantes que no pasan ROE (scripts de
            # research). El wizard SIEMPRE pasa ROE.
            self.stop_loss_pct = self.take_profit_pct / 2.0
            logger.warning(
                "[roe] modo LEGADO: take_profit_pct=%.4f es fraccion de "
                "PRECIO, no de ROE; el ROE sale por multiplicar por el "
                "apalancamiento. Pasa take_profit_roe/stop_loss_roe para "
                "razonar en ROE y tener SL validado contra la liquidacion.",
                self.take_profit_pct)
        if self.max_risk_per_trade_usd is None:
            self.max_risk_per_trade_usd = (
                float(self.initial_capital) * float(self.max_risk_per_trade_pct))
        # Coherencia de topes (correccion no3): el peor dia posible con
        # los topes abiertos es risk/trade x posiciones simultaneas. El
        # tope de dano diario tiene que estar por debajo de ese techo o
        # no esta limitando nada. Se avisa con numeros, no se falla.
        worst_day = (float(self.max_risk_per_trade_usd)
                     * float(self.max_open_positions))
        if worst_day > 0 and self.max_daily_loss_usd > worst_day:
            logger.warning(
                "[risk] tope diario $%.2f > peor dia posible $%.2f "
                "(riesgo/trade $%.2f x %d posiciones): el tope diario no "
                "limita nada mientras las %d posiciones esten abiertas",
                self.max_daily_loss_usd, worst_day,
                self.max_risk_per_trade_usd, self.max_open_positions,
                self.max_open_positions)
        logger.info(
            "[risk] topes: dano/dia $%.2f (%.1f%% de $%.2f), posiciones "
            "simultaneas <= %d, drawdown <= %.0f%%, riesgo/trade $%.2f",
            self.max_daily_loss_usd,
            100.0 * self.max_daily_loss_usd / max(1e-9, float(
                self.initial_capital)),
            float(self.initial_capital), self.max_open_positions,
            100.0 * self.drawdown_limit,
            float(self.max_risk_per_trade_usd))


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
        # Falla cerrado: sin precio no se puede medir el riesgo.
        self.guard.max_unpriced_positions = int(config.max_unpriced_positions)
        self._risk_manager = None  # lazy RiskManager (margin checks)
        self._last_realized_total = 0.0
        # Equity MARCADO (realizado + flotante). Es lo que ven el RiskManager
        # y el tope de riesgo por operacion; antes solo el realizado, asi
        # que con 5 posiciones en contra el sizing/account crecia solo.
        self._last_equity = float(config.initial_capital)
        self._last_unrealized = 0.0
        self._last_unrealized_today = 0.0
        self._last_unpriced = []
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
            "unrealized_today": 0.0,
            "unrealized_total": 0.0,
            "equity": float(config.initial_capital),
            "peak_equity": float(config.initial_capital),
            "drawdown_pct": 0.0,
            "day_pnl": 0.0,
            "open_positions": 0,
            "unpriced_positions": 0,
            "gate_open": bool(getattr(self.engine, "learn_mode", False)),
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
                               # MEDIDO el 2026-09-30: faltaban. El monitor
                               # hace `cfg = stats.get("config", {})` y luego
                               # `state_dir = cfg.get("state_dir",
                               # "runtime/state")`. Sin este campo caia en la
                               # ruta POR DEFECTO, que es una sesion VIEJA, y
                               # el monitor enseñaba 0 posiciones y 0 equity
                               # mientras el bot tenia 5 posiciones vivas.
                               # O sea: el panel moria exactamente cuando
                               # habia algo que mirar.
                               "state_dir": self.config.state_dir,
                               "session": getattr(self.config, "session", None),
                               # El monitor pide la clave `leverage` y sin
                               # esto no la encuentra: `effective_leverage`
                               # es el MISMO numero con otro nombre, y el
                               # panel lo descartaba en silencio. El
                               # apalancamiento es justo lo que el operador
                               # quiere ver, asi que se escribe con el
                               # nombre que el panel lee.
                               "leverage": self.config.leverage,
                               "symbols": self.config.symbols,
                               "initial_capital": self.config.initial_capital,
                               "entry_pct": self.config.entry_pct,
                               "timeframe": self.config.timeframe,
                               "take_profit_pct": self.config.take_profit_pct,
                               "stop_loss_pct": self.config.stop_loss_pct,
                               "take_profit_roe": self.config.take_profit_roe,
                               "stop_loss_roe": self.config.stop_loss_roe,
                               "roe_mode": self.config.roe_mode,
                               "effective_leverage": self.config.effective_leverage,
                               "maintenance_margin_rate": self.config.maintenance_margin_rate,
                               "max_risk_per_trade_usd": self.config.max_risk_per_trade_usd,
                               # correccion no3: topes y puerta de decision
                               "max_daily_loss_usd": self.config.max_daily_loss_usd,
                               "max_daily_loss_pct": self.config.max_daily_loss_pct,
                               "max_open_positions": self.config.max_open_positions,
                               "drawdown_limit": self.config.drawdown_limit,
                               "max_unpriced_positions": self.config.max_unpriced_positions,
                               "learn_mode": bool(getattr(self.engine,
                                                          "learn_mode", False)),
                               "learn_mode_source": getattr(
                                   self.engine, "learn_mode_source", None),
                               "min_expectancy": getattr(
                                   self.engine, "min_expectancy", None),
                               "min_scientific_score": getattr(
                                   self.engine, "min_scientific_score", None),
                               "cost_floor_pct": getattr(
                                   self.engine, "cost_floor_pct", None),
                               "roe_plan": (self.config.roe_plan.to_dict()
                                            if self.config.roe_plan else None),
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
            market=self.config.market,
            timeframe=self.config.timeframe,
            lookback_days=self.config.lookback_days,
            dry_run=self.config.dry_run,
            force_real_data=True,
            # MEDIDO el 2026-09-30: esto NO se pasaba. El AQDERunner se
            # quedaba con su defecto
            # "autonomous_research/data/hypotheses", mientras el motor
            # leia y escribia `config.kb_path`
            # (runtime/hypotheses_<sesion>.jsonl). Dos ficheros distintos,
            # y por eso lo que generaba el ResearchManager no llegaba
            # donde lo leía el motor: `registros=0` y `generadas=0` en
            # cada arranque, con el log limpio.
            # Aunque la base ahora PERSISTA, si no se le pasa la ruta
            # correcta persistirá en un fichero que nadie lee.
            knowledge_base_path=self.config.kb_path,
            hypothesis_ranker=self._rank_hypotheses,
        )

    @staticmethod
    def _family_sequence(templates: List[Dict]) -> List[str]:
        """Secuencia de familias de una lista de plantillas (para el rastro)."""
        from quant_math.ml.hypothesis_prior import family_of
        return [family_of(t.get("strategy_type")) for t in templates]

    def _current_regime(self, symbol: str,
                        templates: Optional[List[Dict]] = None) -> Optional[Dict]:
        """Regimen vigente de `symbol`, en orden de fiabilidad.

        1. el que trae una plantilla (el model-gen lo mide AHORA mismo);
        2. el `_regime` mas reciente del KB para ESE simbolo — la ultima
           ventana medida, con datos de ciclos anteriores (sin look-ahead);
        3. None: la clave de ventana pasa a ser `simbolo|?|?`, que casaria
           con TODAS las ventanas. Se degrada a "sin segmentacion" y el
           prior devuelve el agregado, sin forzar ninguna ventana.

        Antes solo existia (1), y como las plantillas base NO llevan
        `_regime` (solo las del model-gen), con el model-gen ausente el
        objetivo era siempre `simbolo|?|?` y el condicionamiento por ventana
        no se aplicaba nunca (correccion 4).
        """
        for t in templates or []:
            r = (t.get("parameters") or {}).get("_regime")
            if r:
                return r
        try:
            from quant_math.autonomous_research.adapters.postgres_kb import (
                JSONLKnowledgeBase)
            recs = JSONLKnowledgeBase(
                jsonl_path=self.config.kb_path).load_records()
        except Exception as exc:
            logger.debug("[sis] sin regimen del KB (%s)",
                         exc.__class__.__name__)
            return None
        best_ts, best = -1.0, None
        for rec in recs.values():
            if symbol and rec.get("symbol") != symbol:
                continue
            reg = (rec.get("parameters") or {}).get("_regime")
            if not reg:
                continue
            try:
                ts = float(rec.get("created_at") or rec.get("updated_at") or 0)
            except (TypeError, ValueError):
                ts = 0.0
            if ts >= best_ts:
                best_ts, best = ts, reg
        return best

    def _rank_hypotheses(self, templates: List[Dict], symbol: str) -> List[Dict]:
        """Advisory ML reordering of candidate hypotheses (gate untouched).

        Dos fuentes y un orden explicito (correccion 4):

          1. el SIS se consulta PRIMERO, porque su salida (prior de familia
             ponderado por el regimen vigente) alimenta al prior del KB;
          2. `HypothesisPrior.rank_templates` reordena con esa mezcla;
          3. `rank_families` reordena despues las FAMILIAS por el regimen.

        El orden temporal se mantiene sin look-ahead: aqui solo se LEE el
        libro de cierres de ciclos anteriores; `check_exits_all` escribe al
        final del ciclo (F3 2026-09-29, verificado).
        """
        # 0) regimen vigente: plantilla (model-gen) -> KB del simbolo -> None.
        regime = self._current_regime(symbol, templates)

        # 1) SIS
        loop = None
        fam_prior: Dict[str, tuple] = {}
        fams: List[str] = []
        try:
            from quant_math.ml.regime_learning import load_loop
            loop = load_loop(self.config.kb_path, self.config.state_dir)
            if loop.mode == "active":
                fam_prior = loop.family_prior(symbol, regime)
                fams = loop.rank_families(symbol, regime)
            self._explore_burst = (
                loop.should_explore() if loop.mode == "active" else False)
        except Exception as exc:
            logger.warning("[sis] fallo (%s); sin boost", exc)
            self._explore_burst = False

        before = self._family_sequence(templates)

        # 2) prior del KB, ya ponderado con el aprendizaje del SIS
        try:
            from quant_math.ml.hypothesis_prior import build_prior_from_kb
            top_n = self.config.hypotheses_per_cycle
            prior = build_prior_from_kb(self.config.kb_path,
                                        family_prior=fam_prior)
            ordered, info = prior.rank_templates(templates, symbol, top_n)
            print(f"  [ml-prior] modo={info['mode']} registros={info['total']} "
                  f"rate_global={info['global_rate']} "
                  f"reordenado={info['reordered']} "
                  f"sis_w={info.get('family_prior_max_w', 0.0)}")
        except Exception as exc:
            logger.warning("[ml-prior] fallo (%s); orden original", exc)
            ordered = templates

        # 3) regimen hostil: BAJA al final, nunca se excluye.
        #
        # Antes aqui se reordenaba por rank_families entero, y eso anulaba
        # la mezcla del paso 2: cuando solo una familia tenia evidencia en
        # la ventana, salia primera con o sin aprendizaje y el orden final
        # era IDENTICO al de antes del SIS (medido en
        # runtime/f3/d2/demo_lazo.py). El orden POSITIVO lo decide el
        # paso 2 (prior del KB ponderado con el win-rate de la ventana);
        # lo que el SIS puede vetar aqui es lo que esta en regimen hostil.
        hostiles: List[str] = []
        if loop is not None and loop.mode == "active":
            hostiles = loop.hostile_families(symbol, regime)
        if hostiles:
            hs = set(hostiles)
            def _fam(t):
                from quant_math.ml.hypothesis_prior import family_of
                return family_of(t.get("strategy_type"))
            ordered = ([t for t in ordered if _fam(t) not in hs]
                       + [t for t in ordered if _fam(t) in hs])

        after = self._family_sequence(ordered)
        if loop is None:
            print(f"[sis] modo=error ops=0 (recolectando)")
        elif loop.mode == "active":
            s = loop.summary()
            print(f"[sis] modo={s['mode']} ops={s['rows']} "
                  f"clusters={'si' if s['cluster_ready'] else 'no'} "
                  f"hostiles={loop.hostile_families(symbol, regime)} "
                  f"familias={fams[:3]} "
                  f"reordenado_advisory={before != after}")
            if before != after:
                print(f"[sis] orden_familias ANTES={before} "
                      f"DESPUES={after}")
        else:
            s = loop.summary()
            print(f"[sis] modo={s['mode']} ops={s['rows']} "
                  f"(recolectando; faltan "
                  f"{max(0, s['min_rows_active'] - s['rows'])} cierres)")
        return ordered

    def _build_engine(self) -> DecisionEngine:
        engine = DecisionEngine(
            symbols=self.config.symbols,
            kb_path=self.config.kb_path,
            state_dir=self.config.state_dir,
            exchange_id=self.config.exchange_id,
            market=self.config.market,
            timeframe=self.config.timeframe,
            min_paper_trades=self.config.min_paper_trades,
            use_postgres=self.config.use_postgres,
            take_profit_pct=self.config.take_profit_pct,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_roe=self.config.take_profit_roe,
            stop_loss_roe=self.config.stop_loss_roe,
            leverage=self.config.effective_leverage,
            mode=self.config.mode,
            burst_margin=self.config.burst_margin,
            burst_leverage=self.config.burst_leverage,
            # Gate: cerrado por defecto, y con umbral explicito.
            learn_mode=self.config.learn_mode,
            one_position_per_symbol=self.config.one_position_per_symbol,
            min_expectancy=self.config.min_expectancy,
            min_scientific_score=self.config.min_scientific_score,
        )
        # Solo en live se manda la orden de cierre al exchange. En paper el
        # hook queda a None y close_position no toca la red (correccion 6).
        if not self.config.dry_run:
            engine.live_close_hook = self._live_close_order
        return engine

    def _live_close_order(self, symbol: str, side: str, qty: float) -> Dict:
        """Cierra en el exchange la posicion que se cierra en local.

        `reduceOnly` es lo que impide que un cierre abra una posicion
        INVERSA por error: si la posicion ya no existe en el exchange, la
        orden se rechaza en vez de abrir otra cosa.

        MEDIDO el 2026-10-01: al cerrar fallaba con `bybit markets not
        loaded`. ccxt necesita los mercados cargados para construir la
        orden; sin ellos lanza antes de llegar al exchange. El resultado
        era que la posicion se quedaba ABIERTA mientras el motor la
        daba por cerrada, y sin avisar de nada: el cierre no habia
        ocurrido. Es especialmente grave aqui porque, con el SL sin
        cumplirse (ver la comprobacion post-entrada), esta era la otra
        via de salida.
        """
        from data_acquisition.data_sources.exchanges import ExchangeAPI
        api = self._exchange()
        try:
            swap = symbol if ":" in symbol else (
                symbol + "/USDT:USDT" if symbol.endswith("/USDT") else symbol)
            # Cargar los mercados ANTES de construir la orden. `load_markets`
            # es idempotente: si ya estan cargados no vuelve a pedir nada,
            # y si falla se dice POR QUE en vez de dejar que reviente
            # despues con un error que no nombra la causa.
            try:
                api.exchange.load_markets()  # el cliente ccxt crudo
            except Exception as exc:
                logger.error("[live] no se pudieron cargar los mercados "
                             "para cerrar %s: %s; el cierre NO se ha "
                             "ejecutado y la posicion sigue abierta",
                             symbol, exc)
                return {"ok": False, "error": f"mercados no cargados: {exc}",
                        "ejecutado": False, "symbol": symbol}
            # Al cerrar se compra para tapar una larga y se vende para tapar
            # una corta: el lado es el contrario al de la entrada.
            exit_side = "sell" if side == "buy" else "buy"
            order = api.create_order(swap, exit_side, abs(qty),
                                     order_type="market",
                                     params={"reduceOnly": True})
            return {"ok": True, "order_id": order.get("id"),
                    "exchange_order_id": order.get("id"),
                    "reduce_only": True, "side": exit_side,
                    "ejecutado": True}
        finally:
            try:
                api.close()
            except Exception:
                pass

    def _resolver_cierre_fantasma(self, api, symbol: str,
                                  local_rows: List[Dict[str, Any]]) -> Dict:
        """Busca en el exchange el cierre REAL de una posicion fantasma.

        "Fantasma" = el estado local la da por abierta y el exchange no la
        tiene. Casi siempre significa que el TP/SL que puso el exchange la
        cerro y el motor no se entero.

        Devuelve el relleno real, no una estimacion:
            {"ok": True, "exit_price": ..., "motivo": ..., "fuente": ...}

        Y si no lo encuentra, `ok=False` con el motivo. En ese caso NO se
        inventa el precio: quien llama decide que hacer con un cierre
        desconocido, que es cosa distinta de cerrar con un numero
        Mentira.
        """
        vacio = {"ok": False}
        if not local_rows:
            return dict(vacio, motivo_error="no hay posicion local")
        fila = local_rows[0]
        lado = str(fila.get("side") or "buy").lower()
        salida_esperada = "sell" if lado == "buy" else "buy"
        swap = symbol if ":" in symbol else (
            symbol + ":USDT" if symbol.endswith("/USDT") else symbol)
        try:
            trades = api.exchange.fetch_my_trades(swap, limit=50)
        except Exception as exc:
            return dict(vacio, motivo_error=
                        f"no se pudieron leer los rellenos del exchange: {exc}")
        if not trades:
            return dict(vacio, motivo_error="el exchange no devolvio rellenos")

        # El cierre tiene que ser POSTERIOR a la apertura local. Sin ese
        # filtro se cogeria un cierre de una operacion anterior, que es
        # justo el error de mirar donde no toca.
        abierto = None
        try:
            abierto = float(fila.get("opened_at") or 0) or None
        except (TypeError, ValueError):
            abierto = None
        base = abierto or 0.0

        candidatos = []
        for t in trades:
            try:
                when = float(t.get("timestamp") or t.get("datetime_ms") or 0)
                ms = (t.get("datetime") or "")
                if not when and isinstance(ms, str) and ms:
                    from datetime import datetime as _dt
                    when = _dt.strptime(
                        ms.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z"
                    ).timestamp()
                if when <= base:
                    continue
            except Exception:
                continue
            if str(t.get("side") or "").lower() != salida_esperada:
                continue
            try:
                precio = float(t.get("price"))
            except (TypeError, ValueError):
                continue
            if precio <= 0:
                continue
            candidatos.append((when, precio, t))
        if not candidatos:
            return dict(vacio, motivo_error=(
                "no hay ningun relleno de salida posterior a la apertura "
                f"(lado esperado: {salida_esperada})"))
        # El ULTIMO es el que cerro: si se cerro por partes, el ultimo
        # relleno es el que dejo la posicion en cero.
        when, precio, t = max(candidatos, key=lambda c: c[0])
        try:
            comision = float((t.get("fee") or {}).get("cost") or 0.0)
        except (TypeError, ValueError, AttributeError):
            comision = 0.0
        logger.info("[reconcile] cierre REAL de %s encontrado en el "
                    "exchange: %s a %.8g (comision %.8f)",
                    symbol, salida_esperada, precio, comision)
        return {"ok": True, "exit_price": precio, "exit_time": when,
                "opened_at": abierto, "fee": comision, "fuente":
                    f"exchange:fetch_my_trades ({salida_esperada} @ {precio})",
                "motivo": "cerrada_en_el_exchange_tp_sl"}

    def reconcile_positions(self, dry: bool = True) -> Dict:
        """Compara el estado LOCAL de posiciones contra el EXCHANGE.

        Son dos verdades y nadie las comparaba. Con apalancamiento, una
        posicion que solo existe en el exchange es dinero en riesgo que
        nadie vigila: el bot no la ve, y su equity, su drawdown y su tope
        diario dan un numero que no es el real.

        Clasifica cada discrepancia:
          - `orphan_exchange`: esta en el exchange y no en local. LA GRAVE.
          - `phantom_local`: esta en local y no en el exchange. El ledger
            miente sobre lo que se esta arriesgando.

        `dry=True` (por defecto) SOLO informa. Cerrar posiciones es una
        decision, no una consecuencia de medir: un reconciliador que manda
        ordenes por su cuenta seria un peligro. Con `dry=False` cierra solo
        las huerfanas y registra cada cierre; las `phantom_local` se corrigen
        unicamente en local y con rastro, porque mandar una orden para
        "cerrar" algo que no existe seria inventar posicion.

        Idempotente: correrla dos veces no cambia nada la segunda vez.
        """
        report: Dict[str, Any] = {
            "status": "ok", "dry": dry, "checked": [],
            "orphan_exchange": [], "phantom_local": [], "closed": [],
            "errors": [],
        }

        # Sin claves o en paper no se puede comparar: se dice, no se finge.
        if self.config.dry_run:
            report["status"] = "skipped"
            report["motivo"] = ("dry_run=True: no hay exchange contra el que "
                                "comparar (en paper la posicion vive solo en "
                                "local, y eso no es una discrepancia)")
            return report
        try:
            from data_acquisition.data_sources.exchanges import (
                ExchangeAPI, api_keys_present)
            if not api_keys_present():
                report["status"] = "skipped"
                report["motivo"] = ("sin BYBIT_API_KEY/BYBIT_API_SECRET: no se "
                                    "puede leer el exchange. Esto NO significa "
                                    "que no haya posiciones abiertas")
                return report
        except Exception as exc:
            report["status"] = "skipped"
            report["motivo"] = f"no se pudo comprobar las credenciales: {exc}"
            return report

        engine = getattr(self, "engine", None)
        local = dict(getattr(engine, "open_positions", {}) or {})

        # El simbolo no se guarda en la posicion: sale de la clave
        # "hipotesis_id:s simbolo". La cantidad sale del ledger de entradas.
        local_by_symbol: Dict[str, List[Dict[str, Any]]] = {}
        for key, pos in local.items():
            # Partir por el PRIMERO dos puntos: el simbolo perp los lleva
            # ("BTC/USDT:USDT"). Con rsplit salia "USDT" pelado, y las
            # posiciones de perps no se podian ni marcar ni cerrar.
            symbol = pos.get("symbol") or key.split(":", 1)[-1]
            qty = 0.0
            try:
                qty, _notional = engine._last_entry_sizing(key)
            except Exception:
                qty = 0.0
            local_by_symbol.setdefault(symbol, []).append({
                "key": key, "symbol": symbol, "side": pos.get("side", "buy"),
                "quantity": float(qty or 0.0),
                "entry_price": pos.get("entry_price"),
            })

        try:
            api = self._exchange()
        except Exception as exc:
            report["status"] = "error"
            report["motivo"] = f"no se pudo abrir el exchange: {exc}"
            return report

        try:
            symbols = sorted(set(local_by_symbol) | set(self.config.symbols))
            for symbol in symbols:
                report["checked"].append(symbol)
                try:
                    pos = api.fetch_position(symbol)
                except Exception as exc:
                    report["errors"].append({"symbol": symbol,
                                             "error": str(exc)})
                    continue
                amount = 0.0
                try:
                    amount = abs(float(pos.get("contracts") or 0.0))
                except (TypeError, ValueError):
                    amount = 0.0
                local_rows = local_by_symbol.get(symbol, [])
                local_qty = sum(r["quantity"] for r in local_rows)
                # MEDIDO el 2026-09-30: esto era un fallo SILENCIOSO de
                # tres eslabones, y por eso los fantasmas vivian para
                # siempre. La deteccion de phantom exigia
                # `local_qty > 0`, pero `local_qty` sale de
                # `engine._last_entry_sizing(key)`, que devuelve 0 cuando
                # no encuentra el relleno en el ledger. Con la cantidad a
                # 0, la condicion NUNCA se cumplia y la reconciliacion
                # informaba "0 phantom local(es)" con 5 entradas abiertas
                # en el libro. Medido: el log de 00:24:35 dice
                # `0 phantom` mientras el motor tenia 5 posiciones en
                # memoria.
                #
                # Que la clave exista en `open_positions` YA es prueba de
                # que hay posicion local: no hace falta que ademas se sepa
                # el tamano. Una posicion que existe pero no se puede
                # VALORAR no es "no existe", es "no medida", y para eso
                # esta `unpriced`, que falla cerrado ante el guard. Usar
                # la cantidad como criterio de EXISTENCIA confundia
                # "no lo se" con "no hay", y hacia que un estado
                # desconocido se tratara como si el libro estuviera limpio.
                local_open = bool(local_rows)

                if amount > 0 and not local_open:
                    # La grave: hay dinero en el exchange que nadie vigila.
                    orphan = {
                        "symbol": symbol,
                        "exchange_quantity": amount,
                        "exchange_side": pos.get("side"),
                        "entry_price": pos.get("entryPrice"),
                        "leverage": pos.get("leverage"),
                        "liquidation_price": pos.get("liquidationPrice"),
                        "unrealised_pnl": pos.get("unrealisedPnl"),
                        "gravedad": "ALTA",
                        "detalle": ("posicion en el exchange que el estado "
                                    "local no ve: su equity y su drawdown "
                                    "estan calculandose mal"),
                    }
                    report["orphan_exchange"].append(orphan)
                    if not dry and amount > 0:
                        side = str(pos.get("side") or "long").lower()
                        close_side = "sell" if side in ("long", "buy") else "buy"
                        try:
                            res = self._live_close_order(symbol, close_side,
                                                         amount)
                            orphan["closed"] = res
                            report["closed"].append(
                                {"symbol": symbol, "quantity": amount,
                                 "side": close_side, "result": res})
                            logger.warning(
                                "[reconcile] huerfana CERRADA %s qty=%.6f",
                                symbol, amount)
                        except Exception as exc:
                            orphan["close_error"] = str(exc)
                            report["errors"].append(
                                {"symbol": symbol, "close_error": str(exc)})
                            logger.error(
                                "[reconcile] no se pudo cerrar la huerfana "
                                "%s: %s", symbol, exc)
                elif local_open and amount <= 0:
                    phantom = {
                        "symbol": symbol,
                        "local_quantity": local_qty,
                        "local_keys": [r["key"] for r in local_rows],
                        "gravedad": "MEDIA",
                        "detalle": ("el estado local da por abierta una "
                                    "posicion que no esta en el exchange: el "
                                    "riesgo real es otro"),
                    }
                    report["phantom_local"].append(phantom)
                    # QUE NO SE APRENDA DE UN CIERRE QUE NO SE CONOCE
                    # (eleccion de Leonardo, 2026-09-30).
                    #
                    # Un cierre inventado (poner el precio de entrada, o un
                    # cero) poisonaria el aprendizaje: el SIS aprenderia de
                    # numeros que no son, que es lo unico que NO se permite.
                    # Asi que primero se busca el cierre REAL en el
                    # exchange.
                    if not dry and engine is not None:
                        cerrado = self._resolver_cierre_fantasma(
                            api, symbol, local_rows)
                        phantom["cierre_real"] = cerrado
                        if cerrado.get("ok") and cerrado.get("exit_price"):
                            # Con el cierre real: se registra COMO CIERRE,
                            # para que el SIS lo vea igual que cualquier
                            # otro, y la posicion desaparece del estado
                            # vivo.
                            #
                            # OJO: la condicion mira `exit_price`, que es lo
                            # que devuelve el resolver. Pedir `closure` aqui
                            # seria pedir el resultado de una llamada que aun
                            # no se ha hecho, y el camino bueno no se
                            # ejecutaria nunca (asiemnte salio: 3 tests
                            # en rojo por pedir lo que aun no existe).
                            for row in local_rows:
                                _cl = engine.record_external_closure(
                                    row["key"].split(":", 1)[0], symbol,
                                    cerrado["exit_price"],
                                    motivo=cerrado.get("motivo",
                                                       "cerrada_en_el_exchange"),
                                    opened_at=cerrado.get("opened_at"),
                                    extra={"exit_source":
                                           cerrado.get("fuente"),
                                           "exit_time_exchange":
                                           cerrado.get("exit_time")})
                                if _cl is not None:
                                    cerrado["closure"] = _cl
                            phantom["registrada_como_cierre"] = bool(
                                cerrado.get("closure"))
                            logger.warning(
                                "[reconcile] phantom %s REGISTRADA como "
                                "cierre real: salida=%s pnl=%s (fuente: %s). "
                                "El SIS ya puede aprender de ella.",
                                symbol, cerrado.get("exit_price"),
                                cerrado.get("closure", {}).get("pnl"),
                                cerrado.get("fuente"))
                        else:
                            # Sin precio real: NO se inventa. Se quita del
                            # estado vivo (si se deja, con
                            # max_open_positions=1 el brazo queda muerto)
                            # pero se deja constancia de que ese cierre se
                            # ha perdido, para que no se confunda con que
                            # no ocurrio.
                            for row in local_rows:
                                engine.open_positions.pop(row["key"], None)
                            phantom["registrada_como_cierre"] = False
                            phantom["cierre_perdido"] = (
                                cerrado.get("motivo_error")
                                or "no se pudo determinar el precio real de "
                                   "salida en el exchange")
                            logger.error(
                                "[reconcile] phantom %s: NO se pudo determinar "
                                "el precio real de salida (%s). Se retira del "
                                "estado vivo para no bloquear el brazo, pero "
                                "ese cierre NO entra al aprendizaje.",
                                symbol, cerrado.get("motivo_error"))
                        try:
                            engine._persist_positions()
                        except Exception as exc:
                            phantom["persist_error"] = str(exc)
        finally:
            try:
                api.close()
            except Exception:
                pass

        report["resumen"] = (
            f"{len(report['orphan_exchange'])} huerfana(s) en el exchange, "
            f"{len(report['phantom_local'])} phantom local(es), "
            f"{len(report['closed'])} cerrada(s), "
            f"{len(report['errors'])} error(es)")
        # El log deja rastro aunque nadie pida el informe.
        logger.info("[reconcile] dry=%s -> %s", dry, report["resumen"])
        return report

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
                    elif rec.get("entry_price") is not None:
                        # FALLA ABIERTA que se cierra aqui (correccion
                        # no3): antes la fila solo contaba si traia
                        # `margin_usd`. Las entradas anteriores a la
                        # correccion no2 no lo traian, asi que el tope de
                        # exposicion burst no las contaba y se abria
                        # con el tope excedido sin que nada lo notara.
                        # Ahora toda entrada viva cuenta; si no hay
                        # margen, cuenta 0 y se avisa, que es lo honesto.
                        entries.append(rec)
                        open_keys.add(key)
        except OSError:
            pass
        return [e for e in entries if e.get("key") in open_keys]

    def _ledger_open_keys(self) -> set:
        """Claves de entrada VIVAS segun el libro permanente.

        Recorre el libro una vez mas (es pequeño) para poder distinguir
        "hay 3 posiciones abiertas" de "el motor dice que hay 0". La
        divergencia entre ambos es un agujero de riesgo y por eso existe
        esta funcion y no solo `_open_burst_entries`.
        """
        open_keys = set()
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
                    key = rec.get("key") or (f"{rec.get('hypothesis_id')}:"
                                            f"{rec.get('symbol')}")
                    if "motivo_cierre" in rec:
                        open_keys.discard(key)
                    elif rec.get("entry_price") is not None:
                        open_keys.add(key)
        except OSError:
            return set()
        return open_keys

    def _unrealized_snapshot(self) -> Dict:
        """Marca a mercado las posiciones vivas y reparte el flotante.

        Reparto (correccion no3, 2026-09-29):
          - `total` -> TODO el flotante; entra en el equity y por tanto en
            el drawdown. Es la red que agarra las posiciones viejas que
            llevan dias sangrando y que el corte de medianoche no ve.
          - `today` -> solo las abiertas DESDE las 00:00 UTC. Es el dano
            de HOY, y lo que se compara con el tope diario.
        `unpriced` son las que NO se han podido marcar: se declaran, no
        se estiman a cero. El guard decide con ellas (falla cerrado).
        """
        day_start = utc_day_start_ts()
        engine_positions = getattr(self.engine, "open_positions", None) or {}
        mark = (self.engine.mark_to_market()
                if hasattr(self.engine, "mark_to_market") else {})
        rows = mark.get("rows") or []
        today = 0.0
        for row in rows:
            try:
                opened = float(row.get("opened_at") or 0.0)
            except (TypeError, ValueError):
                opened = 0.0
            if opened >= day_start:
                today += float(row.get("pnl_usd") or 0.0)
        unpriced = list(mark.get("unpriced") or [])
        # Reconciliacion libro <-> motor: una entrada viva que el motor
        # no gestiona no se puede marcar y no la cierra nadie.
        unmanaged = sorted(self._ledger_open_keys() - set(engine_positions))
        if unmanaged:
            logger.error(
                "[risk] %d entrada(s) viva(s) en el libro que el motor no "
                "gestiona: %s — se cuentan como riesgo NO medido",
                len(unmanaged), ", ".join(unmanaged))
            unpriced.extend(unmanaged)
        return {
            "total": float(mark.get("pnl_usd") or 0.0),
            "today": today,
            "rows": rows,
            "unpriced": unpriced,
            "open": len(engine_positions),
        }

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
                          hypothesis_id: str,
                          sl_distance: Optional[float] = None) -> float:
        """Fase 1b: tope de MARGEN por entrada + tope de RIESGO por operacion.

        FALLA CERRADO. Antes, ante cualquier excepcion, devolvia el nocional
        SIN capar (`logger.warning("sin cap")`): si la comprobacion de riesgo
        fallaba, se operaba sin limite. Ahora una excepcion devuelve 0.0 y
        `_execute_paper_trade` aborta sin escribir nada en el libro.

        El tope de margen se recalcula aqui a partir de `max_position` (la
        misma regla que usa RiskManager: account * max_position_pct) y NO a
        partir de `approved_size`, que vale 0.0 cuando el check NO aprueba —
        eso producia operaciones de nocional 0 en el libro en vez de una
        operacion recortada.

        `sl_distance` (distancia de precio del SL, ya clampada contra la
        liquidacion) activa el tope de riesgo en USD. Se calcula con
        `PositionSizer.calculate`, que es la formula canonica de sizing y hasta
        ahora tenia 0 referencias desde la ruta de dinero.
        """
        notional = float(notional)
        lev_used = max(1, int(lev_used))
        if notional <= 0:
            return 0.0
        try:
            from quant_math.risk.risk_manager import RiskManager
            if self._risk_manager is None:
                self._risk_manager = RiskManager(
                    max_position_size_pct=self.config.max_position_pct,
                    drawdown_limit=self.config.drawdown_limit,
                )
            margin_used = notional / lev_used
            # Equity MARCADO (realizado + flotante). Antes solo el
            # realizado: con posiciones abiertas en contra, el "account"
            # parecia mas grande justo cuando mas falta era no añadir.
            account = float(getattr(self, "_last_equity", 0.0) or 0.0)
            if account <= 0:
                account = (float(self.config.initial_capital)
                           + float(self._last_realized_total))
            if not (account > 0):
                raise ValueError(f"cuenta no positiva ({account}); no se opera")
            chk = self._risk_manager.check_position_size(
                hypothesis_id, margin_used, account)
            reasons = list(chk.get("reasons") or [])
            if not chk.get("approved"):
                # `max_position` es la MISMA regla que aplica RiskManager.
                max_margin = float(chk.get("max_position") or 0.0)
                only_size = bool(reasons) and all(
                    "exceeds max" in r for r in reasons)
                if not (only_size and max_margin > 0):
                    # Rechazo por otra causa (limite global de perdida,
                    # Kelly...). Fallar CERRADO: no se opera.
                    logger.error(
                        "[risk] entrada RECHAZADA para %s: %s",
                        hypothesis_id, "; ".join(reasons) or "sin detalle")
                    print(f"  [risk] RECHAZADA (cierre): {'; '.join(reasons)}")
                    return 0.0
                capped_margin = min(margin_used, max_margin)
                notional = capped_margin * lev_used
                print(f"  [risk] margin cap: notional ${notional + (capped_margin - margin_used) * lev_used:.2f} -> "
                      f"${notional:.2f} (margen ${margin_used:.2f} -> "
                      f"${capped_margin:.2f} <= ${max_margin:.2f})")
            # --- tope de RIESGO por operacion, en USD -------------------
            cap_usd = float(self.config.max_risk_per_trade_usd or 0.0)
            if sl_distance and sl_distance > 0 and cap_usd > 0:
                from quant_math.risk.sizing import PositionSizer
                max_notional = PositionSizer.calculate(
                    portfolio_value=account,
                    risk_per_trade=cap_usd / account,
                    stop_loss_distance=float(sl_distance),
                )
                if notional > max_notional:
                    risk_usd = notional * float(sl_distance)
                    notional = max_notional
                    print(f"  [risk] riesgo/trade: ${risk_usd:.2f} -> "
                          f"${cap_usd:.2f} tope ({self.config.max_risk_per_trade_pct:.1%} "
                          f"de ${account:.2f}); nocional ${max_notional:.2f}")
            # --- tope de NOCIONAL: el freno del apalancamiento ----------
            # Va AL FINAL, y a proposito: es el techo de verdad. Si se
            # pusiera antes, cualquier tope posterior podria dejar el
            # nocional por encima, y entonces este no seria un tope sino
            # una sugerencia.
            tope_pct = self.config.max_notional_per_entry_pct
            if tope_pct:
                max_notional_cap = account * float(tope_pct)
                if notional > max_notional_cap:
                    antes = notional
                    notional = max_notional_cap
                    logger.warning(
                        "[risk] NOCIONAL capado por max_notional_per_entry_"
                        "pct=%.2f%%: $%.2f -> $%.2f (margen $%.2f a %sx). "
                        "El tope de RIESGO autorizaba mas: riesgo y tamano "
                        "no son lo mismo con apalancamiento.",
                        float(tope_pct) * 100, antes, notional,
                        notional / max(1, lev_used), lev_used)
                    print(f"  [risk] nocional capado: ${antes:.2f} -> "
                          f"${notional:.2f} (techo {float(tope_pct):.0%} de "
                          f"${account:.2f})")
            return notional
        except Exception as exc:
            # CIERRE, no apertura. Si no se puede comprobar el riesgo,
            # no se opera: un tope que se desactiva solo no es un tope.
            logger.error("[risk] comprobacion de riesgo fallo (%s); CIERRE: "
                         "no se opera", exc)
            print(f"  [risk] CIERRE: comprobacion de riesgo fallo ({exc}); "
                  f"no se opera")
            return 0.0

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
        # Distancia de precio del SL YA VALIDADA contra la liquidacion
        # (clampeada en __post_init__). Es la que materializa el tope de
        # riesgo en USD y la que se registra en el libro.
        sl_distance = self.config.stop_loss_pct
        # Fase 1b: tope de margen + tope de riesgo por operacion.
        # FALLA CERRADO: puede devolver 0.0 y entonces no se opera.
        notional = self._apply_margin_cap(
            notional, lev_used, str(signal.get("hypothesis_id", "")),
            sl_distance=sl_distance)
        if notional <= 0:
            return {"action": "risk_rejected",
                    "symbol": signal.get("symbol"),
                    "hypothesis_id": signal.get("hypothesis_id")}
        # Margen real DESPUES del cap, en AMBOS modos: sin esto el ROE
        # realizado no es medible y el aprendizaje no se puede evaluar.
        margin = notional / max(1, lev_used)
        # Fase 3: live path (config guard guarantees testnet + keys,
        # or mainnet with QUANTMATH_ALLOW_MAINNET=1 — see __post_init__).
        if not self.config.dry_run:
            _t = self._execute_live_order(
                signal, price, side, notional, lev_used,
                margin if self.config.mode == "burst" else None)
            # Si la orden no llego a existir, `decide()` ya habia registrado
            # la posicion local y hay que retirarla. Sin esto el brazo cuenta
            # una posicion viva que no esta en el exchange.
            self._abandon_if_rejected(signal, _t)
            return _t
        quantity = notional / price
        plan = self.config.roe_plan
        if plan is not None:
            tp_price, sl_price = tp_sl_prices(price, side, plan)
        else:
            d = self.config.take_profit_pct
            tp_price = price * (1 + d) if side == "buy" else price * (1 - d)
            sl_price = price * (1 - d) if side == "buy" else price * (1 + d)

        # Ledger paper_executions.jsonl. Campos NUEVOS se AÑADEN; ninguno
        # antiguo se cambia ni se borra, para que las filas viejas sigan
        # leyendose igual.
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
            # --- desde la correccion no2: ROE y riesgo medibles ---
            "stop_loss_price": sl_price,
            "take_profit_pct": self.config.take_profit_pct,
            "stop_loss_pct": sl_distance,
            "take_profit_roe": self.config.take_profit_roe,
            "stop_loss_roe": (plan.sl_roe_requested if plan is not None
                              else None),
            "margin_usd": margin,          # ambos modos, no solo burst
            "leverage": lev_used,          # ambos modos, no solo burst
            "risk_usd_at_stop": (notional * sl_distance) if sl_distance else None,
            "liquidation_price_distance": (plan.liquidation_price_distance
                                           if plan is not None else None),
            "sl_clamped": bool(plan.sl_clamped) if plan is not None else False,
            # --- correccion no3: rastro del gate en el libro -----------
            # Sin esto no se puede afirmar despues si una operacion se
            # hizo con el gate cerrado o en exploracion.
            "learn_entry": bool(signal.get("learn_entry")),
            "gate_open": bool(signal.get("gate_open")),
            "gate_min_expectancy": signal.get("gate_min_expectancy"),
            "cost_floor_pct": signal.get("cost_floor_pct"),
        }
        trades_path = os.path.join(self.config.state_dir, "paper_executions.jsonl")
        os.makedirs(self.config.state_dir, exist_ok=True)
        with open(trades_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(trade, ensure_ascii=False) + "\n")

        logger.info("[paper_trade] %s %s qty=%.6f @ %.2f TP=%.2f SL=%.2f "
                    "margen=%.2f lev=%dx (hyp=%s)",
                    side.upper(), trade["symbol"], quantity, price, tp_price,
                    sl_price, margin, lev_used, trade["hypothesis_id"])
        # Fase 2: shadow live intent — what WOULD be sent to the exchange.
        # No API call; paper trading continues untouched.
        if self.config.shadow_live:
            self._log_shadow_order(trade, signal, price)
        return trade

    def _exchange(self):
        """Cliente de exchange con el DOMINIO DE DATOS bien puesto.

        Es un metodo y no cuatro `ExchangeAPI(...)` sueltos porque la regla
        tiene DOS ramas opuestas y basta con que una se olvide para que el
        sistema aprenda sobre el mercado equivocado:

        - PAPER: feed SIEMPRE de mainnet. No se manda ninguna orden, luego
          no hay venue de ejecucion al que atenerse, y aprender contra los
          precios de testnet seria aprender sobre datos FALSOS.
        - LIVE: los datos siguen al venue donde se ejecuta. Medido el
          2026-09-30: XRP cotiza a 1,501 en mainnet y a 1,5735 en testnet
          (4,83%), y con el feed equivocado Bybit rechaza el TP porque le
          queda por debajo del precio de ejecucion.
        """
        from data_acquisition.data_sources.exchanges import ExchangeAPI
        return ExchangeAPI(self.config.exchange_id,
                           sandbox=self.config.testnet,
                           data_venue="mainnet" if self.config.dry_run
                           else None)

    def _cerrar_si_no_verifica(self, api, symbol: str, side: str,
                               qty: float, motivo: str) -> Dict:
        """Cierra en el exchange una entrada que no se pudo verificar.

        Se usa cuando la posicion abre pero sus parametros no son los
        pedidos: apalancamiento que no cuadra, o ilegible. Es un caminho
        que deberia ser RARO, y por eso se registra como incidente y no como
        una operacion mas: si aparece, significa que el exchange cambio de
        reglas o que la cuenta tiene algo puesto a mano.

        `reduceOnly` es obligatorio: sin el, un cierre sobre una posicion
        que ya no existe abriria una INVERSA, que es peor que no hacer nada.
        """
        exit_side = "sell" if side == "buy" else "buy"
        try:
            swap = symbol if ":" in symbol else (
                symbol + ":USDT" if symbol.endswith("/USDT") else symbol)
            out = api.create_order(swap, exit_side, abs(qty),
                                   order_type="market",
                                   params={"reduceOnly": True})
            logger.error("[live] AUTO-CERRADA entrada no verificada (%s): "
                         "id=%s", motivo, out.get("id"))
            return {"ok": True, "order_id": out.get("id"), "motivo": motivo}
        except Exception as exc:
            # FALLO al cerrar. Antes de decir "vive una posicion sin
            # verificar" hay que PREGUNTARLE al exchange, porque el motivo
            # mas probable NO es ese: es que la posicion ya estaba cerrada
            # (medido el 2026-09-30: al intentar cerrar por segunda vez,
            # Bybit responde 110017 "current position is zero" y el log
            # gritaba que quedaba una posicion viva sin verificar, cuando
            # no quedaba ninguna).
            #
            # Una alarma falsa es tan dana como no dar ninguna: entrena a
            # ignorar el log, que es justo lo que haria falta creerse el
            # dia que SÍ hubiera una posicion sin cerrar.
            sigue = self._queda_posicion_viva(api, symbol)
            if sigue is None:
                logger.error("[live] el auto-cierre fallo (%s: %s) y ADEMAS "
                             "no se pudo comprobar si queda posicion: "
                             "COMPRUEBA LA CUENTA A MANO", motivo, exc)
                return {"ok": False, "error": str(exc), "motivo": motivo,
                        "posicion_sin_cerrar": None,
                        "aviso": "no se pudo verificar el estado"}
            if sigue:
                logger.error("[live] NO SE PUDO CERRAR la entrada no "
                             "verificada (%s): %s. HAY UNA POSICION VIVA "
                             "SIN VERIFICAR.", motivo, exc)
                return {"ok": False, "error": str(exc), "motivo": motivo,
                        "posicion_sin_cerrar": True}
            logger.warning("[live] el auto-cierre no pudo mandar la orden "
                           "(%s: %s), pero NO queda posicion abierta: ya "
                           "estaba cerrada. Motivo del cierre: %s",
                           motivo, str(exc)[:120], motivo)
            return {"ok": True, "already_closed": True, "error": str(exc),
                    "motivo": motivo, "posicion_sin_cerrar": False}

    def _queda_posicion_viva(self, api, symbol: str) -> Optional[bool]:
        """True si queda posicion, False si no, None si no se pudo saber."""
        try:
            swap = symbol if ":" in symbol else (
                symbol + ":USDT" if symbol.endswith("/USDT") else symbol)
            posiciones = api.fetch_positions([swap])
        except Exception as exc:
            logger.error("[live] no se pudo leer la posicion: %s", exc)
            return None
        try:
            return any(float(p.get("contracts") or 0) != 0
                       for p in posiciones)
        except (TypeError, ValueError) as exc:
            logger.error("[live] respuesta de posicion ilegible: %s", exc)
            return None

    def _abandon_if_rejected(self, signal: Dict, trade: Dict) -> None:
        """Si la orden NO llego a existir, la posicion local se retira.

        `decide()` registra la posicion en `open_positions` ANTES de que se
        mande la orden. Si la orden se rechaza, esa posicion se queda ahi
        sin haber existido nunca en el exchange, y el brazo acaba
        contando una posicion viva que no existe (MEDIDO el 2026-09-30 en
        testnet: exactamente eso, con `sin marcar 1` en el riesgo).

        Importante: no se registra ningun cierre. No hubo entrada, luego no
        hay PnL que anotar, y fabricar uno seria el dato falso que el
        resto del sistema evita a proposito.
        """
        if not isinstance(trade, dict):
            return
        if trade.get("action") != "live_failed":
            return
        engine = getattr(self, "engine", None)
        if engine is None:
            return
        quitter = getattr(engine, "abandon_entry", None)
        if quitter is None:
            return
        try:
            quitter(signal.get("hypothesis_id"), signal.get("symbol"),
                    motivo=str(trade.get("error") or "orden rechazada")[:120])
        except Exception as exc:                # pragma: no cover
            logger.error("[abandon] no se pudo retirar la entrada: %s", exc)

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
            api = self._exchange()
            # --- APALANCAMIENTO: se EXIGE, no se supone ---------------
            #
            # Antes: `set_leverage` fallaba, se escribia un warning y la
            # orden se mandaba igual. Medido el 2026-09-30: se pidio 50x y
            # la posicion se abrio a 10x. Un apalancamiento que no es el
            # pedido cambia por completo el riesgo: la liquidacion cae 4x
            # mas lejos, el SL puede quedar IRREACHABLE y la posicion real
            # es 5x mas grande de la que se cree. Es la misma cosa que
            # operar con datos falsos, y por eso aqui FALLA CERRADO.
            _modo_error = None
            try:
                api.set_margin_mode(signal["symbol"], "isolated")
            except Exception as exc:
                # El motivo se GUARDA, no se pierde en un warning: es lo
                # que permite decirle al operador que hacer. Medido el
                # 2026-09-30: `100028 unified account is forbidden`, o sea
                # que en una unified account el aislado no es una opcion y
                # no se va a conseguir reintentando.
                _modo_error = str(exc)[:200]
                logger.warning("[live] set_margin_mode fallo (%s); se "
                               "comprobara donde esta la posicion", exc)
            try:
                api.set_leverage(signal["symbol"], lev_used)
            except Exception as exc:
                logger.error("[live] set_leverage(%sx) fallo (%s): NO se "
                             "abre la posicion", lev_used, exc)
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed", "symbol": signal["symbol"],
                        "error": f"set_leverage {lev_used}x fallo: {exc}",
                        "leverage_requested": lev_used,
                        "leverage_actual": None,
                        "reason": "apalancamiento pedido no aplicable"}

            # Margen suficiente ANTES de mandar la orden: mejor un rechazo
            # propio y explicito que una orden que el exchange toca a medias.
            try:
                disp = api.available_margin()
            except Exception as exc:
                logger.warning("[live] no se pudo leer el margen: %s", exc)
                disp = None
            if disp is not None and margin is not None:
                if margin > disp * 1.001:
                    logger.error("[live] margen insuficiente: necesito %.2f y "
                                 "hay %.2f disponibles", margin, disp)
                    try:
                        api.close()
                    except Exception:
                        pass
                    return {"action": "live_failed",
                            "symbol": signal["symbol"],
                            "error": (f"margen insuficiente: necesito "
                                      f"{margin:.2f}, hay {disp:.2f}"),
                            "margin_needed": margin,
                            "margin_available": disp,
                            "reason": "margen insuficiente"}

            # --- PRECIO FRESCO antes de calcular TP/SL ----------------
            #
            # MEDIDO el 2026-09-30 con XRP en velas de 5 min: el precio se
            # mueve 0,217% de mediana por vela y 1,28% en el p90. El SL a
            # 100x esta a 0,25% de precio, o sea MAS PEQUEÑO que el
            # movimiento tipico de una vela. Con el precio del SIGNAL
            # (que es el de inicio de ciclo, antes de generar hipotesis y
            # hacer backtests) el SL llegaba del lado equivocado y Bybit
            # rechazaba la orden entera:
            #
            #   StopLoss:157620000 set for Buy position should lower than
            #   base_price:154560000
            #
            # Es decir, un 2,2% de retraso. Con un SL mas holgado tampoco
            # ayuda: mientras el precio se mueva mas que la distancia del
            # SL, la orden se cae.
            #
            # Se relee del VENUE DE EJECUCION (no del feed de datos).
            #
            # Y la referencia es el ULTIMO PRECIO, no el libro. MEDIDO el
            # 2026-09-30: el mejor ask de XRP estaba en 1,591 y el ultimo
            # precio en 1,5248, un 4,3% de diferencia, y Bybit rechazaba la
            # orden con
            #
            #     StopLoss:158300000 set for Buy position should lower than
            #     base_price:152480000??LastPrice
            #
            # O sea que Bybit valida el TP/SL contra `LastPrice`, no contra
            # el libro. Calcularlo sobre el ask manda el SL por ENCIMA de lo
            # que el exchange usa de referencia, y la orden entera se cae.
            # Por eso los niveles se calculan sobre el ultimo precio.
            precio_fresco = None
            try:
                # Con el simbolo SWAP, no con el que viene en la senal.
                # MEDIDO el 2026-09-30: `fetch_ticker("XRP/USDT")` devolvia
                # `last=1,579469` con `bid=1,5842` (el ultimo precio POR DEBAJO
                # del bid, imposible) y el perp `XRP/USDT:USDT` daba
                # 1,5697: son mercados distintos. Leer el ticker de SPOT
                # para decidir una posicion de PERPETUO es leer otro
                # mercado, y con el el SL se coloca donde no toca.
                _sym = signal["symbol"]
                _swap = _sym if ":" in _sym else (
                    _sym + ":USDT" if _sym.endswith("/USDT") else _sym)
                _tk = api.exchange.fetch_ticker(_swap)
                precio_fresco = float(_tk.get("last") or 0.0)
            except Exception as exc:
                logger.error("[live] no se pudo leer el ultimo precio de %s "
                             "(%s); NO se manda la orden con un precio rancio, "
                             "porque el SL caeria del lado equivocado",
                             signal.get("symbol"), exc)
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed",
                        "symbol": signal.get("symbol"),
                        "error": f"no se pudo leer el ultimo precio: {exc}",
                        "reason": "precio fresco ilegible",
                        "price_senal": price}
            if precio_fresco <= 0:
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed",
                        "symbol": signal.get("symbol"),
                        "error": f"ultimo precio invalido: {precio_fresco}",
                        "reason": "precio fresco invalido"}
            if abs(precio_fresco - price) / price > 0.002:
                logger.warning("[live] precio RANCIO: la senal llevaba %.4f y "
                               "el ultimo precio es %.4f (%+.2f%%); se usa el "
                               "fresco", price, precio_fresco,
                               (precio_fresco - price) / price * 100)
            price = precio_fresco
            qty = notional / price
            # Los precios de salida se calculan ANTES de mandar la orden
            # (correccion 6): antes se mandaba la entrada desnuda y el TP/SL
            # se calculaba despues, solo para guardarlo en el ledger. La
            # proteccion vivia unicamente en un fichero local: si el proceso
            # muriese, la posicion quedaba sin SL en el exchange.
            plan = self.config.roe_plan
            if plan is not None:
                tp_px, sl_px = tp_sl_prices(price, side, plan)
            else:
                d = self.config.take_profit_pct
                tp_px = price * (1 + d) if side == "buy" else price * (1 - d)
                sl_px = price * (1 - d) if side == "buy" else price * (1 + d)
            # El exchange guarda la orden de proteccion: aunque el bot se
            # caiga, el SL sigue puesta. Es lo que hace esto operable con
            # dinero real y no solo un papel con buena intencion.
            # MEDIDO el 2026-10-01: el SL se mandaba sin `triggerBy` y no
            # se cumplia. Bybit liquida por MARK price pero pone el SL por
            # LAST price si no se le dice otra cosa, asi que un mark que se
            # adelanta cruza la liquidacion antes de tocar el SL. Medido:
            # entrada 1,4916, SL pedido 1,4996 (26,8% ROE), liquidacion
            # 1,5138 (74,4%) y salida real 1,529552 (127,2%) — es decir,
            # se perdio mas del margen y el sistema lo etiqueto
            # `motivo=sl`. El SL va en MarkPrice para que ambas cosas
            # midan sobre lo mismo.
            order_params: Dict[str, Any] = {
                "stopLoss": {"triggerPrice": float(sl_px),
                             "triggerBy": "MarkPrice"},
                "takeProfit": {"triggerPrice": float(tp_px),
                               "triggerBy": "MarkPrice"},
            }
            order = api.create_order(signal["symbol"], side, qty,
                                     order_type="market", params=order_params)

            # --- COMPROBACION POST-ENTRADA ---------------------------
            # Que `set_leverage` no fallara NO demuestra que la posicion se
            # abriera al apalancamiento pedido: Bybit puede aceptar la
            # llamada y usar otro (medido: 50 pedido, 10 real). Se lee del
            # exchange y, si no coincide, se CIERRA. Preferimos perder el
            # spread de una entrada equivocada a quedarnos con una posicion
            # cuyo riesgo nadie ha medido.
            try:
                real = api.read_back_leverage(signal["symbol"])
            except Exception as exc:
                logger.warning("[live] no se pudo leer el apalancamiento "
                               "real: %s", exc)
                real = None
            if real is None:
                logger.error("[live] el exchange NO dice que apalancamiento "
                             "tiene la posicion; no se fia, se cierra")
                _cerrado = self._cerrar_si_no_verifica(
                    api, signal["symbol"], side, qty,
                    f"apalancamiento real ilegible (pedido {lev_used}x)")
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed",
                        "symbol": signal["symbol"],
                        "error": "apalancamiento real ilegible",
                        "leverage_requested": lev_used,
                        "leverage_actual": None,
                        "auto_closed": _cerrado,
                        "reason": "apalancamiento real no verificable"}
            if abs(real - lev_used) > 0.01:
                logger.error("[live] APALANCAMIENTO INCORRECTO: pedi %sx y la "
                             "posicion esta a %sx; se cierra",
                             lev_used, real)
                _cerrado = self._cerrar_si_no_verifica(
                    api, signal["symbol"], side, qty,
                    f"apalancamiento {real}x != pedido {lev_used}x")
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed",
                        "symbol": signal["symbol"],
                        "error": (f"apalancamiento incorrecto: pedido "
                                  f"{lev_used}x, real {real}x"),
                        "leverage_requested": lev_used,
                        "leverage_actual": real,
                        "auto_closed": _cerrado,
                        "reason": "apalancamiento distinto del pedido"}
            logger.info("[live] apalancamiento VERIFICADO en el exchange: "
                        "%sx (era lo pedido)", real)

            # --- EL SL Y EL TP TIENEN QUE ESTAR EN EL EXCHANGE ----------
            #
            # MEDIDO el 2026-10-01: esto NO se comprobaba. Se mandaba el SL
            # dentro de la orden de entrada y se daba por puesto, pero una
            # posicion acabo DESPROTEGIDA y se liquido al 127,2% del margen
            # con el SL pedido al 27,5%. El sistema lo registro como
            # `motivo=sl`: una etiqueta de proteccion para algo que no
            # llego a existir.
            #
            # El patron ya existe para el apalancamiento y el modo de
            # margen: se COMPRUEBA y se cierra si no cuadra. Aqui faltaba
            # la tercera pieza, y es la mas grave de las tres: sin SL en el
            # exchange, lo unico que protege es que el proceso siga vivo.
            #
            # Fallo cerrado: si no se puede LEER, no se fia. Preferimos
            # perder el spread de una entrada a quedarnos con una posicion
            # cuya proteccion nadie ha medido.
            try:
                _stops = api.read_back_stops(signal["symbol"])
            except Exception as exc:
                logger.warning("[live] no se pudieron leer los stops reales: "
                               "%s", exc)
                _stops = {}
            _sl_real = _stops.get("stopLoss") if isinstance(_stops, dict) else None
            _tp_real = (_stops.get("takeProfit")
                        if isinstance(_stops, dict) else None)
            # Tolerancia: el exchange redondea al tick del simbolo. Un tick
            # de XRP es 0,0001, que es 0,0067% a este precio: comparar
            # con igualdad de float daria falsos negativos que SIEMPRE
            # acabarian cerrando una posicion bien protegida.
            _tol = max(abs(float(price)) * 0.0005, 1e-9)
            _motivo = None
            if _sl_real is None:
                _motivo = "el exchange NO tiene SL puesto"
            elif abs(_sl_real - float(sl_px)) > _tol:
                _motivo = (f"SL real {_sl_real} != SL pedido {float(sl_px):.6f}")
            if _motivo is None and _tp_real is not None \
                    and abs(_tp_real - float(tp_px)) > _tol:
                _motivo = (f"TP real {_tp_real} != TP pedido {float(tp_px):.6f}")
            if _motivo:
                logger.error("[live] PROTECCION AUSENTE O INCORRECTA: %s; "
                             "se cierra la posicion", _motivo)
                _cerrado = self._cerrar_si_no_verifica(
                    api, signal["symbol"], side, qty, _motivo)
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed",
                        "symbol": signal["symbol"],
                        "error": _motivo,
                        "stop_loss_pedido": float(sl_px),
                        "stop_loss_real": _sl_real,
                        "take_profit_pedido": float(tp_px),
                        "take_profit_real": _tp_real,
                        "auto_closed": _cerrado,
                        "reason": "proteccion no verificable en el exchange"}
            logger.info("[live] SL/TP VERIFICADOS en el exchange: SL=%s TP=%s "
                        "(triggerBy SL=%s)", _sl_real, _tp_real,
                        _stops.get("stopLoss_triggerBy"))

            # --- MODO DE MARGEN: tambien se COMPRUEBA -----------------
            #
            # Antes: `set_margin_mode` fallaba, se escribia un warning y se
            # abria igual. Medido el 2026-09-30: la cuenta estaba en CRUCE
            # (tradeMode=0) en BTC, XRP y ETH.
            #
            # En cruce la perdida de una posicion la paga TODA la cuenta,
            # no solo el margen de esa posicion. Con 5 USDT de capital la
            # diferencia entre "perdi 0,10" y "perdi los 5" es exactamente
            # este ajuste. Es el mismo fallo que el apalancamiento: se
            # suponia en vez de comprobarse.
            try:
                modo = api.read_back_margin_mode(signal["symbol"])
            except Exception as exc:
                logger.warning("[live] no se pudo leer el modo de margen: %s",
                               exc)
                modo = None
            # El motivo del fallo del `set_margin_mode` se guarda para poder
            # explicarle al operador POR QUE no esta aislado, en vez de
            # dejarle un "operacion rechazada" sin causa accionable.
            if modo is not None and modo != "isolated" \
                    and not self.config.require_isolated_margin:
                logger.error(
                    "[live] MARGEN CRUCE y require_isolated_margin=False: "
                    "se opera A CONSCIENCIA. En cruce la perdida de esta "
                    "posicion la paga TODA la cuenta, no solo su margen. "
                    "Origen del aviso al ponerlo: %s", _modo_error or "?")
            if modo is not None and modo != "isolated" \
                    and self.config.require_isolated_margin:
                logger.error("[live] MARGEN CRUCE: se pidio isolated y la "
                             "posicion esta en %s; se cierra", modo)
                _cerrado = self._cerrar_si_no_verifica(
                    api, signal["symbol"], side, qty,
                    f"margen {modo} != isolated")
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed", "symbol": signal["symbol"],
                        "error": f"margen {modo}, se pidio isolated",
                        "margin_mode": modo,
                        "margin_mode_origen": _modo_error,
                        "auto_closed": _cerrado,
                        "reason": "margen no aislado",
                        "como_resolver": (
                            "Bybit no permite margen aislado en una unified "
                            "account (retCode 100028). O se crea una cuenta "
                            "CLASICA, o se pone require_isolated_margin=False "
                            "y se acepta que la perdida la paga toda la "
                            "cuenta.")}
            if modo is None and self.config.require_isolated_margin:
                logger.error("[live] el exchange NO dice el modo de margen; "
                             "no se fia, se cierra")
                _cerrado = self._cerrar_si_no_verifica(
                    api, signal["symbol"], side, qty,
                    "modo de margen ilegible")
                try:
                    api.close()
                except Exception:
                    pass
                return {"action": "live_failed", "symbol": signal["symbol"],
                        "error": "modo de margen ilegible",
                        "margin_mode": None, "auto_closed": _cerrado,
                        "reason": "modo de margen no verificable"}
            # Si se llega aqui: o es "isolated", o el operador puso
            # require_isolated_margin=False y ya se le aviso. Ojo: este
            # `if` con la lista de motivos tiene que ser el UNICO sitio
            # que decide. Hubo un duplicado que hacia que la rama blanda
            # ejecutase el log de "a conciencia" y acto seguido cerrara
            # igual, que es justo lo contrario de lo que significa.
            if modo == "isolated":
                logger.info("[live] modo de margen VERIFICADO: isolated "
                            "(en cruce la perdida la paga toda la cuenta)")

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
                "take_profit_price": price,  # reescrito justo despues con el plan
                "hypothesis_id": signal["hypothesis_id"],
                "expectancy": signal["expectancy"],
                "timestamp": signal["timestamp"],
                "cycle": self.cycle_count,
                "leverage": lev_used,
                "exchange_order_id": order.get("id"),
                "testnet": self.config.testnet,
                # correccion no3: mismo rastro del gate que en paper
                "learn_entry": bool(signal.get("learn_entry")),
                "gate_open": bool(signal.get("gate_open")),
                "gate_min_expectancy": signal.get("gate_min_expectancy"),
                "cost_floor_pct": signal.get("cost_floor_pct"),
            }
            # tp_px / sl_px ya estan calculados arriba, antes de la orden
            # (correccion 6). Se reusan tal cual: una sola verdad.
            trade["take_profit_price"] = tp_px
            trade["stop_loss_price"] = sl_px
            trade["take_profit_pct"] = self.config.take_profit_pct
            trade["stop_loss_pct"] = self.config.stop_loss_pct
            trade["take_profit_roe"] = self.config.take_profit_roe
            trade["stop_loss_roe"] = (plan.sl_roe_requested
                                       if plan is not None else None)
            trade["liquidation_price_distance"] = (
                plan.liquidation_price_distance if plan is not None else None)
            # Margen SIEMPRE, tambien en classic: sin el no hay ROE
            # realizado medible.
            trade["margin_usd"] = (notional / max(1, lev_used)
                                    if margin is None else margin)
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
                "timestamp": trade.get("timestamp"),
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
            api = self._exchange()
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
        # Flotante: lo que YA se ha perdido aunque no se haya cerrado
        # nada. Sin esto, con 5 posiciones abiertas en el SL el guard ve
        # 0,00% de drawdown y dice PERMITE (medido, F3 2026-09-29).
        mark = self._unrealized_snapshot()
        self._last_unrealized = mark["total"]
        self._last_unrealized_today = mark["today"]
        self._last_unpriced = mark["unpriced"]
        equity = (self.config.initial_capital + realized_total
                  + mark["total"])
        self._last_equity = equity
        # MEDIDO el 2026-09-30: se contaba el numero de ENTRADAS, no el de
        # posiciones reales. Bybit funciona en modo NET y FUSIONA por
        # simbolo: N entradas del mismo activo = 1 posicion en el
        # exchange. Medido con el brazo corriendo en testnet: 5 entradas
        # de XRP (5 hipotesis) -> 1 sola posicion de 33 XRP. El tope
        # global contaba 5, daba `open positions 5 >= max 5` y el brazo
        # quedaba BLOQUEADO sin poder operar nunca mas, cuando en
        # realidad solo habia 1 posicion y el exchange la habia cerrado.
        #
        # Lo que limita el riesgo de verdad es el numero de SIMBOLOS
        # expuestos, no el de entradas: por eso se cuentan simbolos
        # distintos. Con esto, 5 entradas fusionadas de un simbolo valen
        # 1, que es lo que el exchange tiene, y el tope global vuelve a
        # medir la exposicion real. La garantia de "una posicion por
        # simbolo" la da `one_position_per_symbol` en el motor
        # (`symbols_with_open_positions`), que ya impedia abrir una
        # segunda en el mismo activo.
        _engine_open = getattr(self.engine, "open_positions", {}) or {}
        _simbolos_expuestos = {
            (p or {}).get("symbol") or str(k).split(":", 1)[-1]
            for k, p in _engine_open.items()
        }
        _simbolos_expuestos.discard(None)
        _simbolos_expuestos.discard("")
        open_count = len(_simbolos_expuestos)
        risk_ok, risk_reason = self.guard.check(
            realized_today, equity, open_count,
            unrealized_today=mark["today"],
            unrealized_total=mark["total"],
            unpriced_positions=len(mark["unpriced"]))
        peak = float(self.guard.last.get("peak_equity") or equity)
        drawdown = ((peak - equity) / peak) if peak > 0 else 0.0
        day_pnl = realized_today + min(0.0, mark["today"])
        self.stats["risk_halt"] = risk_reason
        self.stats["realized_today"] = round(realized_today, 4)
        self.stats["realized_total"] = round(realized_total, 4)
        self.stats["unrealized_today"] = round(mark["today"], 4)
        self.stats["unrealized_total"] = round(mark["total"], 4)
        self.stats["equity"] = round(equity, 4)
        self.stats["peak_equity"] = round(peak, 4)
        self.stats["drawdown_pct"] = round(drawdown, 6)
        self.stats["day_pnl"] = round(day_pnl, 4)
        self.stats["open_positions"] = open_count
        self.stats["unpriced_positions"] = len(mark["unpriced"])
        self.stats["gate_open"] = bool(
            getattr(self.engine, "learn_mode", False))
        print(f"  [riesgo] equity ${equity:,.4f} = ${self.config.initial_capital:,.2f} "
              f"+ realizado ${realized_total:+,.4f} + flotante ${mark['total']:+,.4f} | "
              f"dia {day_pnl:+,.4f} de -${self.config.max_daily_loss_usd:,.2f} | "
              f"dd {drawdown:.2%} de {self.config.drawdown_limit:.0%} | "
              f"abiertas {open_count}/{self.config.max_open_positions} | "
              f"sin marcar {len(mark['unpriced'])} | "
              f"gate {'ABIERTO/exploracion' if self.stats['gate_open'] else 'cerrado'}")
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

    def _run_reconcile(self, dry: bool = True) -> Optional[Dict]:
        """Llama a `reconcile_positions` sin dejar que tumbe el ciclo.

        Una reconciliacion fallida no puede parar el bot: se registra y se
        sigue. Un informe que no llega es mejor que un bot parado.
        """
        try:
            report = self.reconcile_positions(dry=dry)
        except Exception as exc:
            logger.error("[reconcile] fallo (el ciclo sigue): %s", exc)
            return None
        if report.get("status") == "skipped":
            logger.info("[reconcile] omitida: %s", report.get("motivo"))
        return report

    def run_forever(self, max_cycles: Optional[int] = None):
        """Continuous loop (Ctrl+C to stop)."""
        cycles = 0
        # Reconciliacion periodica (correccion 6). DESACTIVADA por defecto a
        # proposito: cada llamada abre conexion con el exchange y consulta
        # posiciones. Con interval_seconds=3600 serian 86.400 llamadas al dia
        # para mirar lo mismo. Activar con reconcile_every_n_cycles>0.
        if self.config.reconcile_every_n_cycles > 0 and not self.config.dry_run:
            self._run_reconcile(dry=not self.config.reconcile_auto_close)
        while max_cycles is None or cycles < max_cycles:
            if self._stop_requested:
                break
            try:
                self.run_cycle()
            except Exception as exc:
                logger.exception("Cycle failed: %s", exc)
            cycles += 1
            every = self.config.reconcile_every_n_cycles
            if (every > 0 and cycles % every == 0
                    and not self.config.dry_run):
                self._run_reconcile(dry=not self.config.reconcile_auto_close)
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
