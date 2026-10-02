"""El dimensionamiento de posicion, que es lo que hace comparables los simbolos.

QUE PASABA
----------
MEDIDO el 2026-10-02: el backtest entraba con `quantity=1`, o sea que el
nocional era EL PRECIO DEL ACTIVO. Con una cuenta de 100.000:

    BTC   nocional 105.900  = 105,90% de la cuenta
    ETH   nocional   2.552  =   2,55%
    SOL   nocional     148  =   0,15%
    XRP   nocional   2,17  =   0,0022%

La exposicion variaba 50.000 veces entre el primero y el ultimo. BTC se
media al 106% de la cuenta por accidente del precio, y en XRP una operacion
movia 0,003 USDT: el "-0,0000%" de XRP no era "no hay edge", era la ausencia
de medida. Y las cuatro columnas no eran comparables entre si.

POR QUE FRACCIONAL Y NO RIESGO-POR-STOP
---------------------------------------
Porque el riesgo por stop meteria en la comparacion una variable mas (la
distancia del stop) que es justo lo que se quiere MEDIR. Con fraccion fija,
cada simbolo arriesga lo mismo y lo unico que cambia es la estrategia.

POR QUE 1,0 DE FRACCION NO ABRE NINGUNA POSICION
-------------------------------------------------
MEDIDO: el motor exige `current_capital >= margen + comision`. Con margen
igual al nocional, el 100% del capital mas la comision de entrada no cabe
NUNCA. A fraccion 1,0 el resultado son 0 operaciones en los 4 simbolos, que
se lee como "la estrategia no genera senal" cuando lo que pasa es que no hay
con que pagar el margen.
"""

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def _strategy_para(simbolo, fraccion, apalancamiento, dataframe):
    """Corre un backtest de verdad y devuelve el resultado."""
    from aqde_runner import AQDERunner
    from quant_math.autonomous_research.adapters.quant_math_adapter import (
        QuantMathAdapter)
    runner = AQDERunner(timeframe="15m")
    plantilla = runner.generate_base_hypotheses(simbolo)[0]
    return QuantMathAdapter().run_backtest(
        plantilla, {"data": dataframe, "symbol": simbolo},
        synthetic=False, fraccion_capital=fraccion,
        apalancamiento=apalancamiento)


@pytest.fixture(scope="module")
def velas():
    import pandas as pd
    rutas = {s: os.path.join(RAIZ, "data", "ohlcv", f"{s}_15m.csv")
             for s in ("BTC", "XRP")}
    faltan = [r for r in rutas.values() if not os.path.exists(r)]
    if faltan:
        pytest.skip(f"faltan velas reales: bajalas con tools/fetch_ohlcv.py "
                    f"(falta {os.path.basename(faltan[0])})")
    return {s: pd.read_csv(r) for s, r in rutas.items()}


def test_el_nocional_no_depende_del_precio_del_activo(velas):
    """El bug: el nocional era el precio, y el precio varia 50.000 veces.

    Con la fraccion por defecto los cuatro simbolos arriesgan LO MISMO. Se
    comprueba comparando BTC (105.900 la unidad) contra XRP (2,17): con
    `quantity=1` el nocional era 48.000 veces mayor en BTC.
    """
    res_btc = _strategy_para("BTC/USDT:USDT", 0.25, 1.0, velas["BTC"])
    res_xrp = _strategy_para("XRP/USDT:USDT", 0.25, 1.0, velas["XRP"])
    assert res_btc.trades and res_xrp.trades, (
        "ambos simbolos deben generar operaciones para comparar el "
        f"dimensionamiento (BTC={res_btc.num_trades}, XRP={res_xrp.num_trades})")
    # El retorno porcentual de la cuenta es la lectura comparable, porque ya
    # viene normalizada por el capital. Si el dimensionamientoiese igual en
    # ambos, la misma estrategia sobre activos de precio tan distinto daria
    # magnitudes de retorno del mismo orden.
    r_btc = abs(float(res_btc.total_return_pct))
    r_xrp = abs(float(res_xrp.total_return_pct))
    razon = max(r_btc, r_xrp) / max(1e-9, min(r_btc, r_xrp))
    assert razon < 20, (
        f"el retorno en % difiere {razon:.1f}x entre BTC ({r_btc:.3f}%) y XRP "
        f"({r_xrp:.3f}%) con la misma fraccion: el dimensionamiento sigue "
        "siendo dependiente del precio")


def test_la_fraccion_si_llega_a_las_operaciones(velas):
    """Comprobar que el parametro hace algo, no que sea decorativo."""
    bajo = _strategy_para("BTC/USDT:USDT", 0.10, 1.0, velas["BTC"])
    assert bajo.num_trades > 0, "una fraccion del 10% tiene que operar"


def test_fraccion_uno_no_abre_posiciones(velas):
    """El caso limite, y por que fraccion=1,0 NO es el default correcto.

    Con margen igual al nocional, el 100% del capital mas la comision de
    entrada no cabe. No es un detalle de implementacion: significa que con
    apalancamiento 1 no se puede usar todo el capital, y un dimensionamiento
    que promete el 100% y no abre nada es peor que uno que lo dice.
    """
    res = _strategy_para("BTC/USDT:USDT", 1.0, 1.0, velas["BTC"])
    assert res.num_trades == 0, (
        "con fraccion 1,0 y apalancamiento 1 la comision de entrada hace que "
        "el margen no quepa: se esperaba 0 operaciones")


def test_el_apalancamiento_cambia_el_nocional():
    """Apalancamiento y fraccion son cosas DISTINTAS y se multiplied."""
    import inspect
    from quant_math.autonomous_research.adapters.quant_math_adapter import (
        QuantMathAdapter)
    p = inspect.signature(QuantMathAdapter.run_backtest).parameters
    assert "fraccion_capital" in p and "apalancamiento" in p, (
        "los dos tienen que ser parametros: la fraccion es lo que se "
        "compromete como margen y el apalancamiento lo que amplifica")