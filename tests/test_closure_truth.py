"""
UN CIERRE QUE NO OCURRIO NO SE ESCRIBE COMO SI HUBIERA OCURRIDO (2026-10-01)

Este es el bug de raiz de que el ledger acabara con CUATRO filas de
cierre —con PnL de signo CONTRARIO— para una sola operacion fisica.

La cadena, en `decision_engine.close_position`:

  1. el exchange rechaza el cierre
  2. el codigo restaura la posicion como ABIERTA
  3. y aun asi escribia la fila de cierre en el ledger
  4. el siguiente ciclo ve la posicion otra vez; si el precio toca el
     otro extremo, vuelve a fallar el cierre y escribe OTRA fila

Medido sobre los datos reales de una corrida: 31 filas de cierre para 9
operaciones fisicas, y el PnL que enseNaba el panel era +4,73 cuando el
ledger real era +0,20. **Veintinueve veces mas.** Y de ahi salen el
equity, el drawdown, el tope diario y el Kelly: todos decidiendo sobre
un numero que se multiplicaba por si mismo.

Los dos arreglos van juntos, y por eso hay tests de los dos:

  - `close_position` no escribe un cierre si el cierre en vivo fallo
    (origen: no se fabrica la fila)
  - `_ledger_pnl` deduplica por `(key, entry_time, quantity)` (red de
    seguridad: aunque el fichero ya tenga duplicados, no los cuenta dos
    veces)

Cada test tiene que FALLAR contra el codigo viejo.
"""

import json
import os
import tempfile

import pytest

from quant_math.decision_engine import DecisionEngine
from quant_math.orchestrator import Orchestrator, OrchestratorConfig


# ---------------------------------------------------------------------------
# 1) EL ORIGEN: si el cierre en vivo falla, no hay cierre
# ---------------------------------------------------------------------------

def _motor_con_hojo(closer, tmp_path):
    """DecisionEngine REAL (no un __new__ a mano).

    Montarlo con `__new__` obliga a adivinar cada atributo que toca el
    metodo, y falla uno por uno: `mode`, `slippage_pct`, ... El motor de
    verdad se construye aqui y solo se le cambia el hook de cierre, que
    es justo lo que se quiere probar. Un doble construido a mano
    verifica el doble, no el codigo.
    """
    import pandas as pd
    idx = pd.date_range("2026-01-01", periods=120, freq="h", tz="UTC")
    velas = pd.DataFrame({
        "open": [100.0] * 120, "high": [100.5] * 120,
        "low": [99.5] * 120, "close": [100.0] * 120,
        "volume": [1.0] * 120}, index=idx)
    e = DecisionEngine(
        symbols=["BTC/USDT"], kb_path=str(tmp_path / "kb.jsonl"),
        state_dir=str(tmp_path), min_paper_trades=1, use_postgres=False,
        data_provider=lambda s: velas)
    e.ledger_path = str(tmp_path / "ledger.jsonl")
    e.live_close_hook = closer
    e._refresh_live_expectancy = lambda *a, **k: None
    e._maybe_graduate = lambda *a, **k: None
    return e


def _pos(e):
    key = e._position_key("h1", "BTC/USDT")
    e.open_positions[key] = {
        "key": key, "symbol": "BTC/USDT", "side": "buy",
        "entry_price": 100.0, "quantity": 1.0, "notional_usd": 100.0,
        "opened_at": 1000.0, "opened_at_ts": 1000.0, "hypothesis_id": "h1"}
    return key


def test_un_cierre_que_falla_no_se_escribe_como_cierre(tmp_path):
    """El caso real: Bybit rechaza el cierre y el exchange no lo ejecuta.

    Con el codigo viejo se escribia igual, con su `pnl`. El ledger luego decia que la operacion habia cerrado cuando en el exchange
    seguía abierta, y al ciclo siguiente se escribia OTRO cierre.
    """
    ledger = tmp_path / "ledger.jsonl"
    e = _motor_con_hojo(lambda *a, **k: {"ok": False,
                                          "error": "markets not loaded"},
                        tmp_path)
    e.ledger_path = str(ledger)
    _pos(e)

    r = e.close_position("h1", "BTC/USDT", "tp", 101.0)

    filas = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    cierres = [f for f in filas if f.get("type") == "closure"]

    assert r is None, (
        "si el exchange no ejecuto el cierre, `close_position` no puede "
        "devolver un cierre: no hay cierre")
    assert not cierres, (
        f"un cierre que el exchange NO ejecuto se escribio igual: "
        f"{cierres}. El ledger miente sobre el estado del exchange")
    intentos = [f for f in filas if f.get("type") == "close_attempt_failed"]
    assert len(intentos) == 1, (
        "el intento fallido tiene que quedar registrado: es lo que permite "
        "a la reconciliacion saber que hay algo abierto que recoger")
    assert intentos[0].get("error"), "el intento fallido dice por que fallo"


def test_la_posicion_sigue_abierta_cuando_el_cierre_falla(tmp_path):
    """Si no se cerro en el exchange, la posicion sigue viva. Punto.

    Es lo que hace que el ciclo siguiente vuelva a intentarlo. Con el
    codigo viejo el cierre se escribia Y la posicion se restauraba: las
    dos cosas a la vez, que es la contradiccion.
    """
    e = _motor_con_hojo(lambda *a, **k: {"ok": False, "error": "boom"},
                        tmp_path)
    key = _pos(e)

    e.close_position("h1", "BTC/USDT", "tp", 101.0)

    assert key in e.open_positions, (
        "el cierre fallo en el exchange, luego la posicion sigue abierta")


def test_un_cierre_que_si_ocurrio_se_escribe_normal(tmp_path):
    """El camino bueno: el exchange lo ejecuto y el cierre se escribe.

    Sin esto el arreglo seria "no escribir nunca nada", que tampoco es
    una respuesta: el ledger tiene que seguir siendo la verdad.
    """
    e = _motor_con_hojo(lambda *a, **k: {"ok": True, "order_id": "X1"},
                        tmp_path)
    _pos(e)

    r = e.close_position("h1", "BTC/USDT", "tp", 101.0)

    assert r is not None and r.get("type") == "closure"
    filas = [json.loads(l) for l in
             open(e.ledger_path, encoding="utf-8").read().splitlines()
             if l.strip()]
    assert sum(1 for f in filas if f.get("type") == "closure") == 1


# ---------------------------------------------------------------------------
# 2) LA RED DE SEGURIDAD: _ledger_pnl deduplica
# ---------------------------------------------------------------------------

def test_el_pnl_no_cuenta_dos_veces_la_misma_operacion(tmp_path):
    """Un ledger CON duplicados, como el que hubo de verdad.

    La identidad de una operacion fisica es
    `(key, entry_time, quantity)`. `key` solo NO basta: Bybit fusiona por
    simbolo y varias operaciones seguidas de la misma hipotesis
    comparten clave.
    """
    state = tmp_path / "state"
    state.mkdir()
    ledger = state / "paper_executions.jsonl"
    filas = []
    for pnl, motivo in ((-0.5054, "sl"), (0.2842, "tp"), (0.2842, "tp"),
                        (-0.2433, "cerrada_en_el_exchange_tp_sl")):
        filas.append({
            "type": "closure", "key": "h1:BTC/USDT", "symbol": "BTC/USDT",
            "hypothesis_id": "h1", "side": "sell", "entry_price": 1.4918,
            "exit_price": 1.4706, "quantity": 13.403927350713762,
            "pnl": pnl, "entry_time": 1000.0, "exit_time": 2000.0,
            "motivo_cierre": motivo})
    filas.append({
        "type": "closure", "key": "h2:BTC/USDT", "symbol": "BTC/USDT",
        "hypothesis_id": "h2", "side": "buy", "entry_price": 100.0,
        "exit_price": 101.0, "quantity": 1.0, "pnl": 1.0,
        "entry_time": 3000.0, "exit_time": 3100.0, "motivo_cierre": "tp"})
    ledger.write_text("\n".join(json.dumps(f) for f in filas) + "\n",
                      encoding="utf-8")

    cfg = OrchestratorConfig(
        symbols=["BTC/USDT"], timeframe="1m", lookback_days=3,
        min_paper_trades=1, hypotheses_per_cycle=3,
        kb_path=str(tmp_path / "kb.jsonl"), state_dir=str(state),
        initial_capital=5.0, entry_pct=0.05, take_profit_pct=0.01,
        leverage=50, mode="classic", dry_run=True)
    o = Orchestrator.__new__(Orchestrator)
    o.config = cfg

    _, total = o._ledger_pnl()

    bruta = sum(f["pnl"] for f in filas)      # +0,8195
    # La definitiva de h1 es la ULTIMA (-0,2433) + la de h2 (+1,0).
    esperado = -0.2433 + 1.0

    assert abs(total - bruta) > 1e-6, (
        "este test NO esta probando nada si la deduplicacion esta "
        "inactiva: el total tiene que diferir de la suma bruta")
    assert total == pytest.approx(esperado, abs=1e-6), (
        f"con deduplicacion el total es {total:+.6f} y deberia ser "
        f"{esperado:+.6f}: se cuenta la ultima fila de cada operacion")
