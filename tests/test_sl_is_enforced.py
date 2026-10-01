"""
EL SL TIENE QUE EXISTIR EN EL EXCHANGE, Y LA RUTA DE CIERRE TIENE QUE
PODER CERRAR (2026-10-01)

Dos fallos medidos con el brazo corriendo en TESTNET, y los dos del
mismo tipo: el sistema decia que la posicion estaba protegida cuando
no lo estaba.

1) EL SL NO SE CUMPLIA

   Medido, entrada 1,4916, apalancamiento 50x:

       SL pedido        1,4996    (+0,536% precio =  26,8% ROE)
       liquidacion      1,5138    (+1,488% precio =  74,4% ROE)
       salida REAL      1,529552  (+2,544% precio = 127,2% ROE)  <-- MAS ALLA

   La salida real esta un 1,06% MAS ALLÁ de la liquidacion. Prediciendo
   con la cuenta: margen 0,40 x 1,272 = 0,5089 USDT, y el log dice
   `pnl=-0.5054`. Diferencia del 0,7%. NO fue un stop loss: fue una
   liquidacion, y el sistema la etiqueta `motivo=sl`, como si una
   proteccion que nadie puso se hubiera ejecutado.

   La causa: el SL se mandaba sin `triggerBy`. Bybit liquida por MARK
   price y pone el SL por LAST price si no se le dice otra cosa. Un mark
   que se adelanta cruza la liquidacion antes de tocar el SL.

   Y aunque se mandara bien, NADA lo comprobaba: se daba por puesto. El
   patron ya existia para el apalancamiento y el modo de margen (se
   comprueba y se cierra si no cuadra) y faltaba justo la pieza que mas
   duele: la proteccion.

2) `cierre fallo: bybit markets not loaded`

   Cuando la ruta de cierre se ejecutaba, el exchange respondia
   `markets not loaded`. El cierre local lo hacia el motor; este lo
   hace el exchange. Con los mercados sin cargar, el cierre no llegaba
   al exchange: la posicion se quedaba abierta sin que nadie la cerrara
   y el motor creia que la habia cerrado. Con el SL sin cumplirse, esa
   era la OTRA via de salida, y fallaba.

Estos tests tienen que FALLAR contra el codigo viejo. Un test que pasa
con y sin el bug no mide nada.
"""

import inspect
import os

import pytest

from quant_math.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# 1) EL SL SE MANDA SOBRE LA MISMA BASE QUE LA LIQUIDACION
# ---------------------------------------------------------------------------

def test_el_sl_se_manda_en_markprice_no_en_lastprice():
    """Bybit liquida por MarkPrice; si no se dice, el SL va por LastPrice.

    Es la diferencia entre un stop que corta y uno que la liquidacion se
    adelanta (medido: 127,2% del margen en vez de 26,8%).
    """
    src = inspect.getsource(Orchestrator._execute_live_order)
    assert '"triggerBy": "MarkPrice"' in src, (
        "el SL/TP tienen que dispararse por MarkPrice, la misma base que "
        "usa la liquidacion. Sin esto, Bybit los pone por LastPrice y un "
        "mark que se adelanta cruza la liquidacion ANTES de tocar el stop "
        "(medido: salida 1,529552 con liquidacion en 1,5138 y SL en "
        "1,4996)")

    # El atributo tiene que ir en AMBOS, no solo en el SL: un TP disparado
    # por una base distinta mide el recorrido de otra forma.
    assert src.count('"triggerBy": "MarkPrice"') >= 2, (
        "el TP tambien necesita triggerBy: MarkPrice; si solo lo lleva el "
        "SL, el TP se mide sobre una base y el SL sobre otra")


def test_la_comprobacion_de_proteccion_existe_y_falla_cerrado():
    """Se COMPRUEBA el SL en el exchange, no se supone puesto.

    Sin esto, mandar el SL y olvidar que el exchange puede no ponerlo es
    indistinguible de tenerlo: el sistema solo puedeimely que lo puso.
    """
    src = inspect.getsource(Orchestrator._execute_live_order)
    assert "read_back_stops" in src, (
        "no se lee lo que el exchange REALMENTE tiene: sin lectura no hay "
        "ninguna garantia de que el SL exista")
    assert "_cerrar_si_no_verifica" in src, (
        "si el SL no esta o no cuadra, la posicion se CIERRA. Fallar "
        "abierto aqui significa dejar una posicion sin proteccion en "
        "dinero real")
    # Fallar cerrado: que no poder LEER tambien cierre.
    assert "el exchange NO tiene SL puesto" in src, (
        "un None significa 'no se pudo comprobar', no 'esta todo bien'")


def test_la_comparacion_tolera_el_redondeo_del_tick():
    """Igualdad de float daria falsos negativos que SIEMPRE cierran.

    Bybit redondea al tick del simbolo (0,0001 en XRP, 0,01 en ETH). Si
    la comprobacion no tolera nada, una proteccion CORRECTA se declararia
    incorrecta y se cerraria la posicion. Fallar cerrado pero por error
    de redondeo tambien es un fallo.
    """
    src = inspect.getsource(Orchestrator._execute_live_order)
    assert "_tol" in src, (
        "la comparacion SL/TP necesita tolerancia de tick; comparar con "
        "igualdad de float cerraria posiciones bien protegidas")
    assert "abs(_sl_real - float(sl_px)) > _tol" in src


# ---------------------------------------------------------------------------
# 2) LA RUTA DE CIERRE TIENE QUE PODER CERRAR
# ---------------------------------------------------------------------------

def test_la_ruta_de_cierre_carga_los_mercados_antes_de_usarlos():
    """`bybit markets not loaded` al cerrar: el cierre no llega al exchange.

    El fallo medido no es un aviso: es que la posicion se queda abierta
    mientras el motor cree que la cerro. Con un SL que puede no
    ejecutarse, esa es la unica via de salida que queda, y falla.

    Se comprueba el ORDEN, no la presencia. Con la comprobacion simple
    ('esta load_markets en el metodo') este test PASABA con el bug ya
    reintroducido: el bloque se puede mover de sitio y seguir estando en
    el fuente. Y da igual donde este si va antes de `create_order`:
    ccxt necesita los mercados para CONSTRUIR la orden y revienta antes
    de enviarla.
    """
    src = inspect.getsource(Orchestrator._live_close_order)
    i_load = src.find("load_markets")
    i_order = src.find("create_order")
    assert i_load != -1, (
        "antes de mandar una orden al exchange hay que cargar los "
        "mercados: ccxt lanza 'markets not loaded' si no, y el cierre se "
        "queda SIN llegar (medido en el log: `[live] cierre fallo "
        "XRP/USDT sell: bybit markets not loaded`)")
    assert i_order != -1, "el cierre tiene que mandar la orden"
    assert i_load < i_order, (
        "load_markets tiene que ir ANTES de create_order: ccxt necesita "
        "los mercados para construir la orden, y revienta antes de "
        "enviarla si no estan")


def test_el_cierre_fallido_dice_que_no_se_ejecuto():
    """Un cierre que no ocurrio tiene que DECIRLO.

    Si devuelve algo indistinguible de un cierre bueno, el motor da la
    posicion por cerrada y sigue operando creyendo que esta viva en el
    exchange cuando ya no esta. Medido: la posicion se quedaba abierta y
    el sistema no avisaba.
    """
    src = inspect.getsource(Orchestrator._live_close_order)
    assert '"ok": False' in src, (
        "si no se pudieron cargar los mercados, el cierre tiene que "
        "devolver ok=False, no un ok con un id de orden: eso hace que un "
        "cierre que NO ocurrio parezca uno que si")
    assert "ejecutado" in src, (
        "el resultado lleva `ejecutado`, para distinguir 'se mando' de "
        "'no se mando'. Sin eso, quien lee no puede saber si la posicion "
        "sigue abierta en el exchange")


def test_el_cierre_manda_al_perp_no_al_spot():
    """`BTC/USDT` es SPOT y `BTC/USDT:USDT` es el PERP.

    MEDIDO el 2026-09-30: 34,6 USD de diferencia en BTC. MEDIDO el
    2026-10-01: la conversion estaba REIMPLEMENTADA a mano en el cierre
    y producia `SOL/USDT/USDT:USDT`, que el exchange rechaza con `does
    not have market symbol`; el cierre fallaba y la posicion se quedaba
    abierta. Eran ya TRES copias distintas de la misma regla en el
    fichero, y tres copias son tres formas de equivocarse.

    Ahora el cierre usa el metodo que ya existe en el cliente
    (`_to_swap_symbol`), que sabe hacerlo bien.
    """
    src = inspect.getsource(Orchestrator._live_close_order)
    assert "api._to_swap_symbol(symbol)" in src, (
        "el cierre tiene que usar la conversion del cliente, no una "
        "propia: la manual producia `SOL/USDT/USDT:USDT` y el exchange "
        "rechazaba el cierre con `does not have market symbol`, dejando "
        "la posicion abierta")
    codigo = "\n".join(ln for ln in src.splitlines()
                       if not ln.strip().startswith("#"))
    assert 'symbol + "/USDT:USDT"' not in codigo, (
        "vuelve la conversion manual al cierre: es la que se rompio")


def test_el_cierre_usa_reduce_only():
    """Un cierre en un symbolo equivocado abre la posicion al reves.

    Es la unica defensa que hay si un dia se cierra mal: `reduceOnly`
    hace que el exchange lo RECHACE en vez de ejecutar.
    """
    from quant_math.orchestrator import Orchestrator as O
    src = inspect.getsource(O)
    assert "reduceOnly" in src, (
        "todo cierre en vivo tiene que ir con reduceOnly: sin eso, un "
        "cierre mal dirigido abre una posicion al reves en vez de cerrar")
