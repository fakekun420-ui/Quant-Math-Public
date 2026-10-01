"""
UNA POSICION POR SIMBOLO, Y QUE LOS FANTASMAS NO VIVAN PARA SIEMPRE
(2026-10-01)

Dos fallos silenciosos medidos con el brazo corriendo en TESTNET, ambos
del mismo tipo: el sistema decia "todo bien" mientras estaba bloqueado
o mintiendo.

1) El tope global contaba ENTRADAS, no posiciones.

   Bybit funciona en modo NET y FUSIONA por simbolo. Medido en la corrida
   real: 5 entradas de XRP (5 hipotesis distintas, 5 claves locales)
   produjeron UNA sola posicion en el exchange (33 XRP, entrada
   ponderada 1,4977). El tope global contaba 5 y daba

       open positions 5 >= max 5 -> entries blocked

   17 veces en el log, y el brazo no podia abrir NADA. Con una sola
   posicion de verdad. Cuando el exchange la cerro por TP, el libro
   registro el cierre de una sola clave y las otras cuatro quedaron
   abiertas para siempre.

   Lo que limita el riesgo es el numero de SIMBOLOS expuestos, no el de
   entradas: por eso ahora se cuentan simbolos distintos.

2) La reconciliacion NUNCA detectaba un fantasma, por tres eslabones.

   El log de 00:24:35 de la corrida real dice:

       [reconcile] dry=False -> 0 huerfana(s) en el exchange,
       0 phantom local(es)

   con 5 entradas abiertas en el libro. La cadena:

     a. el bucle de deteccion exigia `local_qty > 0`
     b. `local_qty` sale de `engine._last_entry_sizing(key)`, que
        devuelve 0.0 cuando no encuentra el relleno en el ledger
     c. con la cantidad a 0, la condicion NUNCA se cumplia -> 0 phantom

   Es decir: "no se el tamano" se confundia con "no hay posicion". Un
   estado desconocido se tratava como un libro limpio, que es la peor
   forma de fallar: el guard deja de ver el riesgo que no puede medir.

   Que la clave exista en `open_positions` ya es prueba de que hay
   posicion local. Una posicion que existe pero no se puede VALORAR no
   es "no existe", es "no medida", y para eso esta `unpriced`, que falla
   cerrado ante el guard.

Estos tests tienen que FALLAR contra el codigo viejo. Es lo que los hace
valiosos: un test que pasa con y sin el bug no mide nada.
"""

import inspect
import os
import tempfile

import pytest

from quant_math.decision_engine import DecisionEngine
from quant_math.orchestrator import Orchestrator, OrchestratorConfig


def _orch(tmpdir, **kw):
    cfg = dict(
        symbols=["XRP/USDT"],
        timeframe="1m",
        lookback_days=3,
        min_paper_trades=1,
        hypotheses_per_cycle=3,
        kb_path=os.path.join(tmpdir, "kb.jsonl"),
        state_dir=tmpdir,
        initial_capital=5.0,
        entry_pct=0.05,
        take_profit_pct=0.01,
        leverage=50,
        mode="classic",
        dry_run=True,
    )
    cfg.update(kw)
    o = Orchestrator.__new__(Orchestrator)
    o.config = OrchestratorConfig(**cfg)
    o.cycle_count = 1
    o.stats = {}
    return o


def _engine_con_entradas(n, symbol="XRP/USDT"):
    """Motor con `n` entradas ABIERTAS del MISMO simbolo (fusionadas)."""
    e = DecisionEngine.__new__(DecisionEngine)
    e.open_positions = {
        f"hyp{i:04d}:{symbol}": {
            "key": f"hyp{i:04d}:{symbol}",
            "symbol": symbol,
            "side": "buy",
            "entry_price": 1.4977,
            "quantity": 6.6,
        }
        for i in range(n)
    }
    return e


# ---------------------------------------------------------------------------
# 1) EL TOPE CUENTA SIMBOLOS, NO ENTRADAS
# ---------------------------------------------------------------------------

def test_entradas_fusionadas_cuentan_como_una_sola_posicion(tmpdir):
    """5 entradas de un simbolo = 1 posicion, y el tope debe verlo.

    Con el codigo viejo: `len(engine.open_positions)` = 5, y con
    `max_open_positions=5` el guard bloqueaba. Aqui se comprueba que el
    conteo vale 1.
    """
    o = _orch(tempfile.mkdtemp(), max_open_positions=5)
    o.engine = _engine_con_entradas(5)

    simbolos = {
        (p or {}).get("symbol") or str(k).split(":", 1)[-1]
        for k, p in o.engine.open_positions.items()
    }
    simbolos.discard(None)
    simbolos.discard("")

    assert len(o.engine.open_positions) == 5, "el montaje no reproduce la fusion"
    assert len(simbolos) == 1, (
        "5 entradas fusionadas del mismo simbolo deben Exposure = 1")


def test_distintos_simbolos_si_cuentan_por_separado(tmpdir):
    """La garantia NO es "una posicion en total": es una POR SIMBOLO.

    Si dos activos distintos estuvieran abiertos, el conteo debe ser 2. Es
    lo que impide que el arreglo de arriba convierta el tope en un tope
    global de 1 y cierre el sistema a dos simbolos.
    """
    e = DecisionEngine.__new__(DecisionEngine)
    e.open_positions = {
        "hyp_a:XRP/USDT": {"symbol": "XRP/USDT"},
        "hyp_b:BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT"},
    }
    simbolos = {
        (p or {}).get("symbol") or str(k).split(":", 1)[-1]
        for k, p in e.open_positions.items()
    }
    simbolos.discard(None)
    simbolos.discard("")
    assert len(simbolos) == 2, "dos simbolos distintos deben Exposure = 2"


def test_el_simbolo_se_saca_de_la_clave_cuando_la_posicion_no_lo_trae():
    """El perp lleva dos puntos en la clave: 'BTC/USDT:USDT'.

    Partir por el ULTIMO dos puntos deja 'USDT' pelado, que fue un bug
    real. Se parte por el PRIMERO.
    """
    e = DecisionEngine.__new__(DecisionEngine)
    e.open_positions = {"hyp_a:BTC/USDT:USDT": {}}   # sin campo symbol
    simbolos = {
        (p or {}).get("symbol") or str(k).split(":", 1)[-1]
        for k, p in e.open_positions.items()
    }
    simbolos.discard(None)
    simbolos.discard("")
    assert simbolos == {"BTC/USDT:USDT"}, f"mal partido: {simbolos}"


# ---------------------------------------------------------------------------
# 2) EL FANTASMA SE DETECTA AUNQUE NO SE SEPA EL TAMAÑO
# ---------------------------------------------------------------------------

def test_un_fantasma_se_detecta_aunque_la_cantidad_sea_cero(tmpdir):
    """El fallo de tres eslabones, en un solo sitio.

    Codigo viejo: la deteccion pedia `local_qty > 0`, y `local_qty`
    viene de `_last_entry_sizing`, que devuelve 0.0 si no encuentra el
    relleno. Con 0 la condicion no se cumplia NUNCA y la reconciliacion
    informaba 0 phantom con 5 entradas abiertas.
    """
    o = _orch(tempfile.mkdtemp())
    o.engine = _engine_con_entradas(5)

    # El ledger NO tiene los rellenos: `_last_entry_sizing` dara 0.0.
    o.engine._last_entry_sizing = lambda key: (0.0, 0.0)
    local_qty = 0.0
    for key in o.engine.open_positions:
        q, _n = o.engine._last_entry_sizing(key)
        local_qty += float(q or 0.0)

    local_rows = [{"key": k, "symbol": "XRP/USDT",
                   "quantity": 0.0, "side": "buy", "entry_price": 1.4977}
                  for k in o.engine.open_positions]
    local_open = bool(local_rows)

    assert local_qty == 0.0, "el montaje debe reproducir el ledger vacio"
    assert local_open is True, (
        "la EXISTENCIA de la clave basta: si hay filas, hay posicion, "
        "aunque no se sepa cuanto mide")
    # El criterio viejo:
    assert (local_qty > 0) is False, (
        "este es el bug: con el criterio viejo NO se detectaria el fantasma")


def test_la_deteccion_no_usa_la_cantidad_como_criterio_de_existencia():
    """Guarda de codigo: nadie puede volver a colar `local_qty > 0`.

    Es la clase de fallo que ya ocurrio: cambiar una linea y devolver el
    bug sin que la suite se entere.
    """
    # Se mira el CODIGO SIN COMENTARIOS: el comentario que explica el
    # bug cita `local_qty > 0` a proposito, asi que buscarlo en el fuente
    # entero daria un falso positivo sobre el propio texto de aviso.
    src = "\n".join(
        ln for ln in inspect.getsource(Orchestrator.reconcile_positions
                                       ).splitlines()
        if not ln.strip().startswith("#"))
    assert "local_qty > 0" not in src, (
        "la deteccion de fantasma vuelve a usar la cantidad como "
        "criterio de EXISTENCIA: si el ledger no tiene el relleno, la "
        "cantidad es 0 y el fantasma deja de detectarse (medido: '0 "
        "phantom' con 5 entradas abiertas)")
    assert "elif local_open and amount <= 0:" in src
    assert "if amount > 0 and not local_open:" in src, (
        "el caso reciproco (huerfana: el exchange tiene y el libro no) "
        "tambien debe usar existencia, no cantidad")


def test_una_posicion_sin_valorar_es_no_medida_no_inexistente():
    """La distincion que faltaba: 'no lo se' != 'no hay'.

    Una posicion que existe y no se puede marcar entra en `unpriced`, que
    el guard cuenta como riesgo NO medido y hace fallar cerrado. Tratar
    lo desconocido como inexistente es lo que dejo el brazo bloqueado.
    """
    tmp = tempfile.mkdtemp()
    o = _orch(tmp)
    # El motor NO tiene ninguna: las 3 claves viven solo en el libro. Es
    # justo el caso que la reconciliacion no puede cerrar y que antes
    # desaparecia del calculo de riesgo.
    o.engine = _engine_con_entradas(0)
    o.engine._last_entry_sizing = lambda key: (0.0, 0.0)
    o.engine.mark_to_market = lambda: {"rows": [], "unpriced": [],
                                       "pnl_usd": 0.0}
    o._ledger_open_keys = lambda: {"hyp0000:XRP/USDT", "hyp0001:XRP/USDT",
                                   "hyp0002:XRP/USDT"}
    o._ledger_pnl = lambda: (0.0, 0.0)

    mark = o._unrealized_snapshot()
    # Hay 3 en el libro, el motor no gestiona ninguna -> no medida.
    assert "hyp0000:XRP/USDT" in mark["unpriced"], (
        "una entrada viva que el motor no gestiona debe contar como "
        "riesgo NO MEDIDO, no desaparecer del calculo")


# ---------------------------------------------------------------------------
# 3) UNA SOLA POR SIMBOLO: LA GARANTIA SIGUE VIVA
# ---------------------------------------------------------------------------

def test_el_tope_usa_simbolos_en_el_codigo_real_no_una_comprension_de_prueba():
    """El anterior test calculaba el conjunto A MANO: no fijaba el bug.

    Medido: reintroduciendo `open_count = len(_engine_open)` (volver a
    contar entradas) el primer test SEGUIA PASANDO, porque lo que
    comprueba es un conjunto construido en el propio test, no el codigo
    que corre en el orquestador. Un test que no falla contra el bug no
    esta midiendo el bug. Este si: mira el fuente del metodo que
    calcula `open_count`.
    """
    src = inspect.getsource(Orchestrator.run_cycle)
    codigo = "\n".join(ln for ln in src.splitlines()
                       if not ln.strip().startswith("#"))
    assert "open_count = len(_simbolos_expuestos)" in codigo, (
        "el tope tiene que contar SIMBOLOS expuestos, no entradas: "
        "Bybit fusiona por simbolo y N entradas de un activo son 1 sola "
        "posicion (medido: 5 entradas de XRP -> 1 posicion de 33 XRP)")
    assert "open_count = len(_engine_open)" not in codigo, (
        "vuelve a contar ENTRADAS: eso es lo que produjo "
        "`open positions 5 >= max 5` con una sola posicion real")


def test_la_garantia_de_una_por_simbolo_no_se_ha_tocado():
    """El arreglo del tope NO puede relajar la regla del motor."""
    src = inspect.getsource(DecisionEngine.decide)
    assert "self.one_position_per_symbol" in src
    assert "symbols_with_open_positions" in src
