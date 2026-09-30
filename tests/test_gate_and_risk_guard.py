"""Correccion no3 (2026-09-29): la puerta de decision y el guard de riesgo.

Cubre tres cosas que estaban rotas y medidas:

1. LA PUERTA. El gate expectancy>0 esta CERRADO por defecto. Antes el
   motor lo tenia en "0" pero los dos launchers lo encendian con
   os.environ.setdefault(LEARN_MODE_ENV, "1"), que gana siempre que la
   variable no exista, y por la puerta real nunca existia. Resultado
   medido (F3, 2026-09-29): 5 de 5 operaciones con expectancy NEGATIVA.

2. EL GUARD VEIA 0,00% DE DRAWDOWN con posiciones abiertas: el equity
   era initial_capital + realizado y el flotante no existia. Con 3
   posiciones en contra decia PERMITE.

3. EL TOPE DE DANO DIARIO miraba solo el realizado. Con el flotante,
   las losses abiertas no contaban y el dia se hundia sin parar.

Todo OFFLINE y DETERMINISTA: nada de red, nada de ficheros de runtime/
reales, precios fijados a mano. El unico reloj es time.time(), y para
el corte de medianoche UTC se usa utc_day_start_ts() en vez de una
fecha fija (asi la prueba no se pudre al cambiar de dia).
"""

import ast
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.decision_engine import DecisionEngine
from quant_math.orchestrator import Orchestrator, OrchestratorConfig
from quant_math.risk.circuit_breaker import (
    DEFAULT_MAX_DAILY_LOSS_PCT,
    DailyGuard,
    daily_loss_usd,
    utc_day_start_ts,
)
from quant_math.risk.gate_policy import (
    DEFAULT_MIN_EXPECTANCY,
    LEARN_MODE_ENV,
    MIN_EXPECTANCY_ENV,
    MIN_SCIENTIFIC_SCORE_ENV,
    gate_audit_records,
    resolve_learn_mode,
    round_trip_cost_pct,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMBOL = "BTC/USDT"
GATE_ENV_VARS = (LEARN_MODE_ENV, MIN_EXPECTANCY_ENV,
                 MIN_SCIENTIFIC_SCORE_ENV,
                 "QUANTMATH_SLIPPAGE_PCT", "QUANTMATH_BURST_SLIPPAGE_PCT")
#: Slippage adverso por LADO del motor de paper (VERIFICADO en
#: DecisionEngine.__init__). El cierre lo sufre una vez y el marcado a
#: mercado lo tiene que sufrir igual, o el flotante miente.
SLIP = 0.0005


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    """Ninguna prueba depende del entorno de quien la lanza.

    Sin esto, exportar QUANTMATH_LEARN_MODE=1 antes de pytest abriria
    el gate en todas las pruebas de este fichero.
    """
    for var in GATE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------

def _ohlc(last_close, n=50, start=100.0, step=1.0):
    """Velas OHLC deterministas cuyo ULTIMO cierre es exactamente
    last_close. Los intermedios son lineales y no importan: al
    marcado a mercado y a la traza de SL/TP solo les afecta el
    ultimo."""
    rows = [[float(i), start + 1.0, start + 2.0, start - 1.0,
             start + step * i, 10.0] for i in range(n)]
    rows[-1][4] = float(last_close)
    return rows


def _engine(tmp, hypotheses=(), candles=None, **kw):
    """DecisionEngine real, con KB y precios locales.

    candles es la MISMA funcion que usaria el cierre: aqui no se
    duplica el modelo de mercado.
    """
    kb = os.path.join(str(tmp), "kb.jsonl")
    with open(kb, "w", encoding="utf-8") as fh:
        for row in hypotheses:
            fh.write(json.dumps(row) + "\n")
    if candles is None:
        candles = _ohlc(149.0)
    state = os.path.join(str(tmp), "state")
    os.makedirs(state, exist_ok=True)
    return DecisionEngine(
        symbols=[SYMBOL], kb_path=kb, state_dir=state,
        min_paper_trades=3, use_postgres=False,
        data_provider=lambda symbol: candles, **kw)


class _SinRed:
    """Runner de AQDE sin red: lo unico que run_cycle le pide es
    invalidar la cache de mercado."""

    def invalidate_market_cache(self):
        pass


def _orchestrator(tmp, candles, *, capital=50.0, hypotheses=(),
                  max_daily_loss_pct=None, max_open_positions=5,
                  max_unpriced_positions=0, drawdown_limit=0.20,
                  learn_mode=None, monkeypatch=None, state_name="state"):
    """Orquestador REAL con la generacion troceada.

    Se sustituyen SOLO las dos piezas que hablarian con la red: el
    runner de AQDE y la generacion+backtest, porque aqui se prueba el
    camino de RIESGO. Todo lo que se decide en estas pruebas (cierres,
    marcado a mercado, guard, gate, libro) es codigo de produccion
    sin tocar.

    state_name: cada orquestador de la misma prueba necesita su propio
    state_dir, o el libro de uno se cuela en el equity del otro.
    """
    if monkeypatch is not None:
        monkeypatch.setattr(Orchestrator, "_build_runner",
                            lambda self: setattr(self, "runner", _SinRed()))
    cfg = OrchestratorConfig(
        symbols=[SYMBOL], timeframe="1h", lookback_days=7,
        initial_capital=capital, entry_pct=0.02, take_profit_pct=0.25,
        min_paper_trades=3, hypotheses_per_cycle=3,
        kb_path=os.path.join(str(tmp), "kb.jsonl"),
        state_dir=os.path.join(str(tmp), state_name),
        max_daily_loss_pct=max_daily_loss_pct,
        max_open_positions=max_open_positions,
        max_unpriced_positions=max_unpriced_positions,
        drawdown_limit=drawdown_limit,
        learn_mode=learn_mode,
    )
    o = Orchestrator(cfg)
    o.engine._data_provider = lambda symbol: candles
    o.engine.hypotheses = {}
    for row in hypotheses:
        o.engine.hypotheses[row["hypothesis_id"]] = dict(row)
    o._generate_and_backtest_symbol = lambda *a, **k: []
    return o


def _abrir(o, n=3, entry=100.0, notional=10.0, side="buy",
           take_profit_pct=0.25, stop_loss_pct=0.125, opened_at=None,
           con_margin=True, prefix="h"):
    """Abre n posiciones VIVAS de forma coherente libro<->motor.

    El libro lleva las filas de entrada que escribe
    _execute_paper_trade y el motor lleva open_positions. Las dos
    mitades tienen que cuadrar: si no, el orquestador las declara SIN
    MARCAR y el guard bloquea.
    """
    if opened_at is None:
        opened_at = time.time()
    path = os.path.join(o.config.state_dir, "paper_executions.jsonl")
    os.makedirs(o.config.state_dir, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for i in range(n):
            hid = prefix + str(i + 1)
            key = hid + ":" + SYMBOL
            row = {
                "mode": "paper", "key": key, "symbol": SYMBOL, "side": side,
                "quantity": notional / entry, "notional_usd": notional,
                "entry_price": entry, "timestamp": opened_at,
                "hypothesis_id": hid, "cycle": 0,
            }
            if con_margin:
                row["margin_usd"] = notional
                row["leverage"] = 1
            fh.write(json.dumps(row) + "\n")
            pos = {"key": key, "opened_at": opened_at, "side": side,
                   "entry_price": entry, "leverage": 1}
            if take_profit_pct is not None:
                pos["take_profit_pct"] = take_profit_pct
                pos["stop_loss_pct"] = stop_loss_pct
            o.engine.open_positions[key] = pos
    return o


def _cerrar_en_libro(o, key, pnl=-0.8, motivo="sl"):
    """Escribe una fila de CIERRE en el libro permanente."""
    path = os.path.join(o.config.state_dir, "paper_executions.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "key": key, "symbol": SYMBOL, "motivo_cierre": motivo,
            "pnl": pnl, "pnl_pct": -8.0, "exit_time": time.time(),
            "exit_price": 92.0}) + "\n")


# ======================================================================
# 1. LA PUERTA: gate CERRADO por defecto
# ======================================================================

def test_gate_cerrado_por_defecto_con_expectancy_negativa(tmp_path):
    """COMPORTAMIENTO 3: expectancy = -0.01 y gate cerrado -> NO opera.

    Es el caso del run real: hipotesis con expectativa negativa
    ejecutadas porque el launcher habia dejado la exploracion encendida
    sin que nadie la pidiera.
    """
    engine = _engine(tmp_path, [{
        "hypothesis_id": "h_neg", "symbol": SYMBOL, "status": "backtested",
        "expectancy": -0.01, "scientific_score": 0.8,
        "parameters": {"lookback": 5},
    }])
    assert engine.learn_mode is False
    assert engine.learn_mode_source == "default"
    out = engine.decide(SYMBOL)
    assert out["action"] == "no_entry", out
    assert out["signal"] is None
    assert engine.open_positions == {}
    assert engine.min_expectancy == DEFAULT_MIN_EXPECTANCY == 0.0


def test_gate_cerrado_sigue_dejando_operar_con_expectancy_positiva(tmp_path):
    """COMPORTAMIENTO 4: expectancy = +0.01 y gate cerrado -> SI opera.

    Cerrar el gate no es apagar el sistema: es quedarse con la parte
    del KB que dice que gana.
    """
    engine = _engine(tmp_path, [{
        "hypothesis_id": "h_pos", "symbol": SYMBOL, "status": "backtested",
        "expectancy": 0.01, "scientific_score": 0.8,
        "parameters": {"lookback": 5},
    }])
    assert engine.learn_mode is False
    out = engine.decide(SYMBOL)
    assert out["action"] == "entry", out
    assert out["hypothesis_id"] == "h_pos"
    assert out["gate_open"] is False
    assert out["learn_entry"] is False
    assert out["gate_min_expectancy"] == 0.0
    assert len(engine.open_positions) == 1


def test_exploracion_es_explicita_y_queda_marcada(tmp_path):
    """Con learn_mode=True explicito SI se opera, y se puede demostrar
    despues. "Estabamos en exploracion" tiene que ser afirmable con un
    fichero, no con la memoria de quien lanzo el proceso.
    """
    state = os.path.join(str(tmp_path), "state")
    engine = _engine(tmp_path, [{
        "hypothesis_id": "h_neg", "symbol": SYMBOL, "status": "backtested",
        "expectancy": -0.01, "scientific_score": 0.8,
        "parameters": {"lookback": 5},
    }], learn_mode=True)
    assert engine.learn_mode is True
    assert engine.learn_mode_source == "explicit"
    out = engine.decide(SYMBOL)
    assert out["action"] == "entry", out
    assert out["learn_entry"] is True      # entro por exploracion
    assert out["gate_open"] is True

    rows = gate_audit_records(state)
    assert rows, "no se escribio rastro del gate"
    first = rows[0]
    assert first["event"] == "startup"
    assert first["learn_mode"] is True
    assert first["source"] == "explicit"
    assert isinstance(first["pid"], int)


def test_entorno_abre_la_exploracion_pero_argumento_manda(tmp_path,
                                                          monkeypatch):
    """Precedencia: argumento explicito > entorno > default (cerrado)."""
    monkeypatch.setenv(LEARN_MODE_ENV, "1")
    learn, source = resolve_learn_mode(None, os.path.join(str(tmp_path), "s1"))
    assert learn is True and source == "env"
    learn, source = resolve_learn_mode(False,
                                       os.path.join(str(tmp_path), "s2"))
    assert learn is False and source == "explicit"
    # Un flag mal escrito NUNCA abre el gate por sorpresa.
    monkeypatch.setenv(LEARN_MODE_ENV, "maybe")
    learn, source = resolve_learn_mode(None,
                                       os.path.join(str(tmp_path), "s3"))
    assert learn is False and source == "env"


def test_el_rastro_del_gate_es_append_only(tmp_path):
    state = os.path.join(str(tmp_path), "state")
    for i in range(3):
        resolve_learn_mode(i % 2 == 0, state, event="n" + str(i))
    rows = gate_audit_records(state)
    assert len(rows) == 3
    assert [r["event"] for r in rows] == ["n0", "n1", "n2"]
    assert [r["learn_mode"] for r in rows] == [True, False, True]


def test_auto_graduacion_cierra_el_gate_y_deja_rastro(tmp_path):
    """La auto-graduacion (PB) SE RESPETA: cierra el gate sola y avisa.

    No se reescribe: se comprueba que, tras graduarse, el gate vuelve a
    cerrarse y que el cambio queda en learn_mode_audit.jsonl.
    """
    state = os.path.join(str(tmp_path), "state")
    engine = _engine(tmp_path, [
        {"hypothesis_id": "h1", "symbol": SYMBOL, "status": "backtested",
         "strategy_type": "momentum", "expectancy": 0.01,
         "scientific_score": 0.9},
        {"hypothesis_id": "h2", "symbol": SYMBOL, "status": "backtested",
         "strategy_type": "breakout", "expectancy": 0.01,
         "scientific_score": 0.9},
    ], learn_mode=True, auto_graduate=True, graduate_window=4)
    # 4 cierres positivos y de 2 familias: cumple el criterio O1.
    with open(engine.ledger_path, "a", encoding="utf-8") as fh:
        for hid, pct in (("h1", 0.5), ("h2", 0.3), ("h1", 0.2), ("h2", 0.0)):
            fh.write(json.dumps({
                "type": "closure", "key": hid + ":" + SYMBOL,
                "symbol": SYMBOL, "hypothesis_id": hid, "side": "buy",
                "pnl_pct": pct, "exit_time": 1.0,
                "motivo_cierre": "tp"}) + "\n")
    engine._maybe_graduate()
    assert engine.learn_mode is False and engine.graduated is True
    records = gate_audit_records(state)
    assert "auto_graduation" in [r["event"] for r in records]
    grad = [r for r in records if r["event"] == "auto_graduation"][0]
    assert grad["source"] == "auto_graduate" and grad["learn_mode"] is False
    # Con el gate cerrado, la hipotesis negativa ya no se opera. Se
    # vacia el KB porque el ranking es por expectancy DESC y las dos
    # positivas del graduation se learian por delante.
    engine.hypotheses = {
        "h3": {"hypothesis_id": "h3", "symbol": SYMBOL,
               "status": "backtested", "expectancy": -0.01,
               "scientific_score": 0.8, "parameters": {"lookback": 5}},
    }
    out = engine.decide(SYMBOL)
    assert out["action"] == "no_entry", out


# ======================================================================
# 2. LOS LAUNCHERS: la linea que apagaba el gate
# ======================================================================

def _setdefault_learn_mode_calls(path):
    """Llamadas REALES a os.environ.setdefault(LEARN_MODE_ENV, ...).

    Se parsea el AST, no el texto: asi un comentario que nombre la
    linea eliminada no hace pasar la prueba por alto, ni al reves la
    hace fallar.
    """
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute)
                and func.attr == "setdefault"):
            continue
        owner = func.value
        if not (isinstance(owner, ast.Attribute)
                and owner.attr == "environ"):
            continue
        args = [a.value for a in node.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if LEARN_MODE_ENV in args:
            found.append((node.lineno, args))
    return found


@pytest.mark.parametrize("relpath", ["quant_math_bg.py",
                                    "quant_math/cli/main.py"])
def test_los_launchers_no_pueden_encender_el_gate_solos(relpath):
    """REGRESION DEL BUG REAL: los dos launcheros hacian
    os.environ.setdefault(LEARN_MODE_ENV, "1"), que gana siempre que la
    variable no exista. Con la politica nueva abrir la exploracion es
    una ACCION del operador: un launcher no puede decidirlo en su
    nombre.
    """
    calls = _setdefault_learn_mode_calls(os.path.join(REPO, relpath))
    assert calls == [], (relpath + " enciende el gate por su cuenta: "
                         + str(calls))


def test_el_motor_tampoco_usa_setdefault_para_el_gate():
    """El motor aplica la politica; no se la fabrica a si mismo."""
    calls = _setdefault_learn_mode_calls(
        os.path.join(REPO, "quant_math/decision_engine/main.py"))
    assert calls == []


def test_el_wizard_pregunta_y_su_default_es_cerrado():
    """El wizard PREGUNTA, y el default de la pregunta es no explorar."""
    src = open(os.path.join(REPO, "quant_math/cli/main.py"),
               encoding="utf-8").read()
    tree = ast.parse(src)
    body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_ask_learn_mode":
            body = ast.get_source_segment(src, node)
            break
    assert body, "el wizard ya no pregunta por la exploracion"
    assert "default=False" in body, "el default del wizard no es CERRADO"
    # Las dos config del wizard (classic y burst) llevan la respuesta.
    assert src.count('"learn_mode": bool(learn_mode)') == 2


# ======================================================================
# 3. UMBRALES: parametrizados, y el default NO es un numero inventado
# ======================================================================

def _hyp(hid, exp, score=0.8):
    return {"hypothesis_id": hid, "symbol": SYMBOL, "status": "backtested",
            "expectancy": exp, "scientific_score": score,
            "parameters": {"lookback": 5}}


def test_el_umbral_de_expectancy_es_parametrizable(tmp_path):
    """Con min_expectancy=0.05 una hipotesis de 0.03 deja de ser
    operable. El default sigue siendo 0.0 (solo el signo), que es lo
    unico defendible sin validacion OOS."""
    rows = [_hyp("h", 0.03)]
    assert _engine(tmp_path, rows, min_expectancy=0.05
                   ).decide(SYMBOL)["action"] == "no_entry"
    assert _engine(tmp_path, rows, min_expectancy=0.01
                   ).decide(SYMBOL)["action"] == "entry"


def test_el_umbral_por_entorno_equivale_al_argumento(tmp_path, monkeypatch):
    monkeypatch.setenv(MIN_EXPECTANCY_ENV, "0.5")
    engine = _engine(tmp_path, [_hyp("h", 0.03)])
    assert engine.min_expectancy == 0.5
    assert engine.decide(SYMBOL)["action"] == "no_entry"
    # Un valor ilegible no para nada: avisa y usa el default.
    monkeypatch.setenv(MIN_EXPECTANCY_ENV, "mucho")
    assert _engine(tmp_path, [_hyp("h", 0.03)]).min_expectancy == 0.0


def test_el_suelo_de_score_por_defecto_no_filtra_nada(tmp_path):
    """Con el default 0.0 el suelo de score es INERTE: una hipotesis
    degradada a failed (score 0.4) sigue operable, como antes.

    Sube el suelo cuando quieras cerrar ese agujero; el filtro esta,
    pero no se aplica por sorpresa. Medido: 0 de 495 filas del KB
    tienen score 0, asi que el cambio de <= por > seria puro ruido.
    """
    rows = [_hyp("h_failed", 0.05, score=0.4)]
    assert _engine(tmp_path, rows).decide(SYMBOL)["action"] == "entry"
    assert _engine(tmp_path, rows, min_scientific_score=0.5
                   ).decide(SYMBOL)["action"] == "no_entry"
    assert _engine(tmp_path, rows, min_scientific_score=0.4
                   ).decide(SYMBOL)["action"] == "no_entry"


def test_el_suelo_de_score_es_operativo_por_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv(MIN_SCIENTIFIC_SCORE_ENV, "0.6")
    assert _engine(tmp_path, [_hyp("h", 0.05, score=0.4)]
                   ).decide(SYMBOL)["action"] == "no_entry"
    assert _engine(tmp_path, [_hyp("h", 0.05, score=0.8)]
                   ).decide(SYMBOL)["action"] == "entry"


def test_coste_de_ejecucion_es_diagnostico_y_no_umbral(tmp_path, monkeypatch):
    """El suelo de coste son 2 x slippage POR LADO, en % del nocional.

    NO es un umbral del gate: el gate vive en % de capital por trade
    (otra unidad) y solo el backtest conoce el nocional desplegado.
    Con los defaults de paper: 2 x 0,05% = 0,10% del nocional.
    """
    assert round_trip_cost_pct(SLIP) == pytest.approx(0.10)
    assert round_trip_cost_pct(0.0003) == pytest.approx(0.06)
    assert _engine(tmp_path, [_hyp("h", 0.05)]
                   ).cost_floor_pct == pytest.approx(0.10)
    monkeypatch.setenv("QUANTMATH_BURST_SLIPPAGE_PCT", "0.0003")
    assert _engine(tmp_path, [_hyp("h", 0.05)], mode="burst"
                   ).cost_floor_pct == pytest.approx(0.06)


# ======================================================================
# 4. EL GUARD: equity MARCADO (el 0,00% de drawdown)
# ======================================================================

#: 3 posiciones long de 10 USD de nocional abiertas a 100,00, con el
#: mercado en 92,00. Flotante por posicion = 0,1 x (92,00 x 0,9995 -
#: 100,00) = -0,8046. Total -2,4138 sobre un capital de 50,00.
PNL_POR_POS = 0.1 * (92.0 * (1 - SLIP) - 100.0)
PNL_3_POS = 3 * PNL_POR_POS
EQUITY_3_POS = 50.0 + PNL_3_POS
DD_3_POS = -PNL_3_POS / 50.0


def test_el_guard_no_ve_cero_drawdown_con_tres_posiciones_en_perdida(
        tmp_path, monkeypatch):
    """COMPORTAMIENTO 1: 3 posiciones abiertas en perdida, 0 cerradas.

    equity = 50,00 (capital) + 0,00 (realizado) + -2,4138 (flotante
    marcado a 92,00 con el slippage adverso de salida) = 47,5862.
    Con el pico de 50,00 del ciclo anterior el drawdown es 4,83%, no
    0,00%. Con el codigo anterior el equity era 50,00 y el guard decia
    PERMITE.
    """
    o = _orchestrator(tmp_path, _ohlc(92.0), monkeypatch=monkeypatch)
    _abrir(o, n=3, entry=100.0, notional=10.0)
    # Ciclo 1: sin posiciones, el pico se fija en el capital.
    o.guard.check(0.0, o.config.initial_capital, 0)
    o.run_cycle()

    st = o.stats
    assert st["realized_total"] == 0.0
    assert st["unrealized_total"] == pytest.approx(PNL_3_POS, abs=5e-4)
    assert st["equity"] == pytest.approx(EQUITY_3_POS, abs=5e-4)
    assert st["peak_equity"] == pytest.approx(50.0, abs=1e-6)
    assert st["drawdown_pct"] == pytest.approx(DD_3_POS, abs=1e-5)
    assert st["drawdown_pct"] != 0.0
    assert st["unpriced_positions"] == 0
    # El flotante de HOY es el de las tres: se abrieron hace un momento.
    assert st["unrealized_today"] == pytest.approx(st["unrealized_total"])


def test_el_flotante_entra_en_el_equity_que_ve_el_tope_de_riesgo(
        tmp_path, monkeypatch):
    """El sizing y el tope de margen ven el equity MARCADO. Con 3
    posiciones en contra el account tiene que HABER bajado, no crecer:
    antes el "account" era initial + realizado y parecia mas grande
    justo cuando mas falta era no anadir."""
    o = _orchestrator(tmp_path, _ohlc(92.0), monkeypatch=monkeypatch)
    _abrir(o, n=3, entry=100.0, notional=10.0)
    o.run_cycle()
    assert o._last_equity == pytest.approx(EQUITY_3_POS, abs=5e-4)
    assert o._last_equity < o.config.initial_capital
    # Y el tope de margen lo lee de ahi, no del capital nominal.
    o._risk_manager = None
    o._last_realized_total = 0.0
    notional = o._apply_margin_cap(
        1000.0, 1, "h1", sl_distance=o.config.stop_loss_pct)
    assert notional < 1000.0


def test_el_guard_falla_cerrado_si_no_puede_marcar(tmp_path, monkeypatch):
    """Sin precio NO hay PnL que calcular, y un PnL que no se puede
    calcular no se puede llamar cero: se declara y se bloquea."""
    o = _orchestrator(tmp_path, _ohlc(92.0), monkeypatch=monkeypatch)

    def _boom(symbol):
        raise RuntimeError("exchange caido")
    o.engine._data_provider = _boom
    _abrir(o, n=1, entry=100.0, notional=10.0)
    o.run_cycle()

    assert o.stats["unpriced_positions"] == 1
    assert o.stats["risk_halt"], "un riesgo no medido debe bloquear"
    assert "sin marcar" in o.stats["risk_halt"]
    # Y el flotante NO se ha inventado: 0 marcado, no -algo.
    assert o.stats["unrealized_total"] == 0.0
    assert o.stats["signals"] == 0


def test_entrada_viva_en_el_libro_que_el_motor_no_gestiona_se_declara(
        tmp_path, monkeypatch):
    """Reconciliacion libro<->motor: una entrada viva que el motor no
    tiene no la cierra nadie. Se cuenta como riesgo no medido."""
    o = _orchestrator(tmp_path, _ohlc(92.0), monkeypatch=monkeypatch)
    _abrir(o, n=1, entry=100.0, notional=10.0)
    o.engine.open_positions.clear()      # el motor "olvida" la posicion
    o.run_cycle()
    assert o.stats["open_positions"] == 0
    assert o.stats["unpriced_positions"] == 1
    assert o.stats["risk_halt"] is not None


# ======================================================================
# 5. EL TOPE DE DANO DIARIO (limita el DANO, no el numero de trades)
# ======================================================================

def test_tope_diario_suma_realizado_y_flotante_negativo(tmp_path):
    """COMPORTAMIENTO 2, version aritmetica.

    -1,20 realizado + -1,80 flotante = -3,00 <= -2,50 -> BLOQUEA.
    Antes solo se miraba el realizado: -1,20 no llegaba a -2,50 y el
    guard decia PERMITE con el dia ya en -3,00.
    """
    g = DailyGuard(str(tmp_path), max_daily_loss_usd=2.5)
    ok, reason = g.check(-1.20, 47.0, 3, unrealized_today=-1.80,
                         unrealized_total=-1.80)
    assert not ok
    assert "daily loss" in reason
    # El motivo lleva las CIFRAS, no un "se bloquea" de cuento.
    assert "-3.00" in reason and "-2.50" in reason
    assert "-1.20" in reason and "-1.80" in reason
    # Y deja claro que limita dano y no operaciones.
    assert "no de operaciones" in reason


def test_el_flotante_solo_resta_nunca_suma(tmp_path):
    """Una ganancia no realizada no paga deudas: el dano de hoy no se
    maquilla al alza. Realizado -1,00 con flotante +5,00 sigue siendo
    -1,00 de dano, no +4,00."""
    g = DailyGuard(str(tmp_path), max_daily_loss_usd=2.5)
    ok, _ = g.check(-1.00, 54.0, 2, unrealized_today=5.00,
                    unrealized_total=5.00)
    assert ok
    ok, reason = g.check(-2.60, 52.4, 2, unrealized_today=5.00)
    assert not ok and "daily loss" in reason


def test_el_tope_diario_bloquea_aunque_la_hipotesis_guste(
        tmp_path, monkeypatch):
    """COMPORTAMIENTO 2, extremo a extremo.

    Con el tope al 2% del capital ($1,00) y las 3 posiciones en contra
    (-$2,41 de flotante) el ciclo NO abre, aunque la hipotesis tenga
    expectancy +0,50. El motivo lleva las cifras.
    """
    o = _orchestrator(tmp_path, _ohlc(92.0), monkeypatch=monkeypatch,
                      capital=50.0, max_daily_loss_pct=0.02,
                      hypotheses=[_hyp("h_ok", 0.50)])
    _abrir(o, n=3, entry=100.0, notional=10.0)
    o.run_cycle()
    assert o.config.max_daily_loss_usd == pytest.approx(1.0)
    reason = o.stats["risk_halt"]
    assert reason and "daily loss" in reason
    assert "-2.41" in reason          # el flotante se ve en el motivo
    assert o.stats["signals"] == 0    # no se abrio nada
    assert o.stats["paper_trades_taken"] == 0
    assert len(o.engine.open_positions) == 3


def test_el_tope_diario_por_defecto_es_5_por_ciento_del_capital(
        tmp_path, monkeypatch):
    """5% es la mitad del peor dia posible con los topes del resto del
    sistema: riesgo/trade 2% x 5 posiciones simultaneas = 10%. El dia
    se para cuando ya se ha gastado la mitad de ese peor caso."""
    assert DEFAULT_MAX_DAILY_LOSS_PCT == 0.05
    assert daily_loss_usd(50.0, 0.05) == pytest.approx(2.5)
    assert daily_loss_usd(10_000.0, 0.05) == pytest.approx(500.0)
    o = _orchestrator(tmp_path, _ohlc(100.0), capital=10_000.0,
                      monkeypatch=monkeypatch)
    assert o.config.max_daily_loss_usd == pytest.approx(500.0)
    assert o.config.max_daily_loss_pct == 0.05
    # Si el operador pasa USD, manda el USD.
    o2 = _orchestrator(tmp_path, _ohlc(100.0), capital=10_000.0,
                       max_daily_loss_pct=0.01, monkeypatch=monkeypatch)
    o2.config.max_daily_loss_usd = 123.0
    assert o2.config.max_daily_loss_usd == 123.0


def test_un_tope_diario_que_no_limita_nada_avisa_con_numeros(
        tmp_path, monkeypatch, caplog):
    """Si el tope diario esta por ENCIMA del peor dia posible, el tope
    no esta limitando nada. No se rompe el arranque: se dice con
    numeros."""
    import logging
    with caplog.at_level(logging.WARNING, logger="quant_math.orchestrator"):
        o = _orchestrator(tmp_path, _ohlc(100.0), capital=1000.0,
                          max_daily_loss_pct=0.50, monkeypatch=monkeypatch)
    # 1000 x 50% = 500 de tope, pero el peor dia posible son
    # 1000 x 2% x 5 = 100. El tope solo muerde a partir de 500.
    assert o.config.max_daily_loss_usd == pytest.approx(500.0)
    assert any("no limita nada" in r.message for r in caplog.records)


def test_max_daily_loss_pct_ilegible_se_rechaza(tmp_path):
    with pytest.raises(ValueError):
        OrchestratorConfig(
            symbols=[SYMBOL], timeframe="1h", lookback_days=7,
            initial_capital=50.0, entry_pct=0.02, take_profit_pct=0.25,
            min_paper_trades=3, hypotheses_per_cycle=3,
            kb_path=str(tmp_path / "kb.jsonl"),
            state_dir=str(tmp_path / "state"), max_daily_loss_pct=1.5)


# ======================================================================
# 6. MARCADO A MERCADO: misma fuente de precio y mismos costes
# ======================================================================

def _pos_viva(engine, key, side="buy", entry=100.0, notional=10.0):
    """Una posicion en el motor Y su fila de entrada en el libro.

    Las dos mitades: sin fila de entrada no hay nocional, y sin nocional
    la posicion queda sin marcar.
    """
    engine.open_positions[key] = {
        "key": key, "opened_at": time.time(), "side": side,
        "entry_price": entry, "take_profit_pct": 0.25,
        "stop_loss_pct": 0.125, "leverage": 1}
    with open(engine.ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "key": key, "symbol": SYMBOL, "side": side,
            "entry_price": entry, "quantity": notional / entry,
            "notional_usd": notional, "timestamp": time.time()}) + "\n")
    return key


def test_el_marcado_reutiliza_el_precio_del_mismo_ciclo(tmp_path):
    """El marcado usa el MISMO ultimo cierre que la traza de SL/TP y no
    vuelve a bajar al exchange en el mismo ciclo."""
    calls = {"n": 0}

    def _provider(symbol):
        calls["n"] += 1
        return _ohlc(92.0)
    engine = _engine(tmp_path, [])
    engine._data_provider = _provider
    _pos_viva(engine, "h1:" + SYMBOL)

    assert engine._check_exits(SYMBOL) == []      # 92 no toca SL (87,5)
    assert calls["n"] == 1
    mark = engine.mark_to_market()                # reutiliza el precio
    assert calls["n"] == 1, "volvio a pedir el precio en el mismo ciclo"
    row = mark["rows"][0]
    # Mismo slippage ADVERSO de salida que sufre el cierre real: al
    # cerrar un long se vende, y se ejecuta peor.
    assert row["mark_price"] == pytest.approx(92.0 * (1 - SLIP))
    assert row["pnl_usd"] == pytest.approx(
        0.1 * (92.0 * (1 - SLIP) - 100.0))
    assert mark["pnl_usd"] == pytest.approx(-0.8046, abs=5e-4)
    assert mark["unpriced"] == []
    assert mark["open"] == 1


def test_el_marcado_es_el_espejo_en_una_posicion_cortista(tmp_path):
    """Signo coherente con el cierre: un short pierde cuando el precio
    SUBE. Cerrar un short es COMPRAR para cubrir, asi que el slippage
    va en contra al alza: el mark es 110 x (1 + s), no 110 x (1 - s).
    Es el MISMO _slip, no una segunda version del coste.
    """
    engine = _engine(tmp_path, [], candles=_ohlc(110.0))
    _pos_viva(engine, "h1:" + SYMBOL, side="sell")
    row = engine.mark_to_market()["rows"][0]
    assert row["mark_price"] == pytest.approx(110.0 * (1 + SLIP))
    assert row["pnl_usd"] == pytest.approx(
        0.1 * (110.0 * (1 + SLIP) - 100.0) * -1)
    assert row["pnl_usd"] < -1.0


def test_sin_tamano_en_el_libro_la_posicion_queda_sin_marcar(tmp_path):
    """Sin nocional no hay PnL que calcular. Se DECLARA; no se estima
    a cero, porque un cero aqui es un "no hay riesgo" falso."""
    engine = _engine(tmp_path, [], candles=_ohlc(92.0))
    key = "h1:" + SYMBOL
    engine.open_positions[key] = {
        "key": key, "opened_at": time.time(), "side": "buy",
        "entry_price": 100.0, "take_profit_pct": 0.25,
        "stop_loss_pct": 0.125}
    mark = engine.mark_to_market()
    assert mark["rows"] == []
    assert mark["unpriced"] == [key]
    assert mark["pnl_usd"] == 0.0


def test_el_precio_rancio_no_se_reutiliza(tmp_path):
    """La cache de precio tiene antiguedad maxima. Pasados 300 s se
    vuelve a pedir: una posicion de hace 10 min no se marca con un
    precio rancio."""
    engine = _engine(tmp_path, [], candles=_ohlc(92.0))
    _pos_viva(engine, "h1:" + SYMBOL)
    engine._close_cache[SYMBOL] = (time.time() - 10_000.0, 1.0)
    calls = {"n": 0}

    def _provider(symbol):
        calls["n"] += 1
        return _ohlc(92.0)
    engine._data_provider = _provider
    row = engine.mark_to_market()["rows"][0]
    assert calls["n"] == 1
    assert row["mark_price"] == pytest.approx(92.0 * (1 - SLIP))


def test_el_flotante_de_hoy_solo_cuenta_lo_abierto_desde_medianoche(
        tmp_path, monkeypatch):
    """Reparto: el drawdown ve TODO el flotante (incluida la posicion
    vieja que lleva dias sangrando); el tope del dia solo lo abierto
    desde las 00:00 UTC."""
    ayer = utc_day_start_ts() - 86_400.0
    o = _orchestrator(tmp_path, _ohlc(92.0), monkeypatch=monkeypatch)
    _abrir(o, n=1, entry=100.0, notional=10.0, opened_at=ayer,
           prefix="old")
    _abrir(o, n=2, entry=100.0, notional=10.0)   # las de hoy
    o.run_cycle()
    # El flotante TOTAL son las tres: -2,4138.
    assert o.stats["unrealized_total"] == pytest.approx(PNL_3_POS, abs=5e-4)
    # El de HOY son solo dos: la de ayer no es dano de hoy.
    assert o.stats["unrealized_today"] == pytest.approx(
        2 * PNL_POR_POS, abs=5e-4)
    assert o.stats["day_pnl"] == pytest.approx(
        min(0.0, o.stats["unrealized_today"]), abs=5e-4)
    # Y el equity SI ve la de ayer: para eso esta el flotante total.
    assert o.stats["equity"] == pytest.approx(EQUITY_3_POS, abs=5e-4)


# ======================================================================
# 7. BURST y posiciones simultaneas: los topes que fallaban abiertos
# ======================================================================

def test_una_entrada_sin_margin_usd_tambien_cuenta_para_el_tope(
        tmp_path, monkeypatch):
    """FALLA ABIERTA que se cierra: la fila de entrada solo contaba si
    traia margin_usd. Las entradas anteriores a la correccion no2 no lo
    traian, asi que el tope de exposicion burst no las contaba."""
    o = _orchestrator(tmp_path, _ohlc(100.0), monkeypatch=monkeypatch,
                      state_name="s1")
    path = os.path.join(o.config.state_dir, "paper_executions.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({          # fila "legacy": sin margin_usd
            "mode": "paper", "key": "legacy:" + SYMBOL, "symbol": SYMBOL,
            "side": "buy", "entry_price": 100.0, "quantity": 0.1,
            "notional_usd": 10.0, "timestamp": time.time(),
            "hypothesis_id": "legacy", "cycle": 0}) + "\n")
    assert len(o._open_burst_entries()) == 1

    o2 = _orchestrator(tmp_path, _ohlc(100.0), monkeypatch=monkeypatch,
                       state_name="s2")
    _abrir(o2, n=1, entry=100.0, notional=10.0)
    assert len(o2._open_burst_entries()) == 1     # con margen explicito

    o3 = _orchestrator(tmp_path, _ohlc(100.0), monkeypatch=monkeypatch,
                       state_name="s3")
    _abrir(o3, n=1, entry=100.0, notional=10.0)
    _cerrar_en_libro(o3, "h1:" + SYMBOL)
    assert o3._open_burst_entries() == []         # cerrada ya no cuenta


def test_el_tope_de_posiciones_simultaneas_lo_aplica_el_guard(
        tmp_path, monkeypatch):
    """max_open_positions tiene que existir de verdad, no solo en la
    config: con 5 vivas y tope 5 no se abre la sexta, y con 4 si."""
    o = _orchestrator(tmp_path, _ohlc(100.0), max_open_positions=5,
                      hypotheses=[_hyp("h_ok", 0.50)], monkeypatch=monkeypatch,
                      state_name="p5")
    _abrir(o, n=5, entry=100.0, notional=1.0)
    o.run_cycle()
    reason = o.stats["risk_halt"]
    assert reason and "open positions" in reason
    assert "5 >= max 5" in reason
    assert o.stats["signals"] == 0
    assert len(o.engine.open_positions) == 5

    o2 = _orchestrator(tmp_path, _ohlc(100.0), max_open_positions=5,
                       hypotheses=[_hyp("h_ok", 0.50)], monkeypatch=monkeypatch,
                       state_name="p4")
    _abrir(o2, n=4, entry=100.0, notional=1.0)
    o2.run_cycle()
    assert o2.stats["risk_halt"] is None
    assert o2.stats["signals"] == 1
    assert len(o2.engine.open_positions) == 5
    # Y la quinta queda en el libro con el rastro del gate.
    rows = [json.loads(l) for l in
            open(os.path.join(o2.config.state_dir,
                              "paper_executions.jsonl"))
            if l.strip()]
    assert any("h_ok" in json.dumps(r) for r in rows)


# ======================================================================
# 8. El libro deja rastro de si se operaba en exploracion
# ======================================================================

def test_la_entrada_de_exploracion_queda_marcada_en_el_libro(
        tmp_path, monkeypatch):
    """Sin esto, despues no se puede afirmar si una operacion se hizo
    con el gate cerrado o en exploracion. Y lo que no se puede
    afirmar, no se puede auditar."""
    o = _orchestrator(tmp_path, _ohlc(149.0), learn_mode=True,
                      hypotheses=[_hyp("h_neg", -0.01)],
                      monkeypatch=monkeypatch)
    assert o.engine.learn_mode is True
    o.run_cycle()
    assert o.stats["signals"] == 1
    rows = [json.loads(l) for l in
            open(os.path.join(o.config.state_dir,
                              "paper_executions.jsonl"))
            if l.strip()]
    entrada = [r for r in rows if "entry_price" in r][0]
    assert entrada["learn_entry"] is True
    assert entrada["gate_open"] is True
    assert entrada["gate_min_expectancy"] == 0.0
    assert entrada["cost_floor_pct"] == pytest.approx(0.10)
    # Y el rastro del gate, aparte, con el PID que lo decidio.
    audit = gate_audit_records(o.config.state_dir)
    assert audit and audit[0]["source"] == "explicit"


def test_la_entrada_con_el_gate_cerrado_no_lleva_rastro_de_exploracion(
        tmp_path, monkeypatch):
    o = _orchestrator(tmp_path, _ohlc(149.0),
                      hypotheses=[_hyp("h_pos", 0.50)],
                      monkeypatch=monkeypatch)
    assert o.engine.learn_mode is False
    o.run_cycle()
    assert o.stats["signals"] == 1
    rows = [json.loads(l) for l in
            open(os.path.join(o.config.state_dir,
                              "paper_executions.jsonl"))
            if l.strip()]
    entrada = [r for r in rows if "entry_price" in r][0]
    assert entrada["learn_entry"] is False
    assert entrada["gate_open"] is False
    audit = gate_audit_records(o.config.state_dir)
    assert audit and audit[0]["source"] == "default"


if __name__ == "__main__":
    import tempfile
    fails = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        code = fn.__code__
        if code.co_argcount and code.co_varnames[0] in ("tmp_path",
                                                        "monkeypatch"):
            print("SKIP " + name + " (necesita fixtures)")
            continue
        try:
            fn()
            print("PASS " + name)
        except AssertionError as exc:
            fails += 1
            print("FAIL " + name + ": " + str(exc)[:120])
    raise SystemExit(1 if fails else 0)
