"""
Riesgo de liquidacion por HUECO (2026-09-30).

Que rompia
----------
`Backtester.MAINTENANCE_MARGIN_RATE` estaba HARDCODEADO en 0,005, que es el
SEGUNDO tramo del MMR real de Bybit y ademas era un supuesto. Con eso la
liquidacion se ponia MAS CERCA de lo real, o sea que el backtest era
OPTIMISTA: subestimaba el riesgo de liquidacion.

El MMR real se leyo del endpoint publico el 2026-09-30: primer tramo 0,0033.
Ahora es configurable y por defecto usa el real.

Lo que se discoverio al verificar
---------------------------------
Medido en XRP/USDT 1h, mainnet, 999 velas:

    velas que caen >= 0,50% (el SL)     188  = 18,82%
    velas que caen >= 1,50% (liquidacion a 50x) 32 =  3,20%
    de esas, las que saltan SL Y liquidacion de golpe: 32 = 3,20%

Es decir: **una de cada 31 velas de XRP a 1h se lleva el 100% del margen de
una posicion a 50x de golpe**, sin pasar por el stop. Por eso un backtest con
104 operaciones a 50x da ~3 liquidaciones: no es un bug del motor, es riesgo
real y el motor lo estaba contando bien.

Eso NO lo cambiaria el MMR (de 0,005 a 0,0033 solo mueve la liquidacion del
1,50% al 1,67%), pero si cambia el resto de la aritmetica y habia que
alinearlo con el dato.
"""

import numpy as np
import pytest

from backtesting.backtester import Backtester


def test_el_mmr_por_defecto_es_el_real_de_bybit():
    """0,0033 = primer tramo real. Antes 0,005, que era del segundo tramo."""
    assert Backtester.MAINTENANCE_MARGIN_RATE == 0.0033
    assert Backtester().maintenance_margin_rate == 0.0033


def test_el_mmr_es_configurable():
    bt = Backtester(leverage=50.0, maintenance_margin_rate=0.0056)
    assert bt.maintenance_margin_rate == 0.0056
    # Y el que se pasa manda, no el de la clase.
    assert bt._liq_price_long(100.0) == pytest.approx(100.0 * (1 - (0.02 - 0.0056)))


def test_la_liquidacion_mas_lejos_con_el_mmr_real():
    """Con el MMR real la liquidacion esta MAS lejos, no mas cerca.

    Bajarlo de 0,005 a 0,0033 aleja la liquidacion: el motor viejo era
    pesimista en este punto concreto, que es lo contrario de lo que se
    suponia al mirar el numero. Lo que era pesimista era la comision, que
    no se modelaba (ver el modulo del gate).
    """
    viejo = Backtester(leverage=50.0, maintenance_margin_rate=0.005)
    nuevo = Backtester(leverage=50.0)
    assert nuevo._liq_price_long(100.0) < viejo._liq_price_long(100.0)
    assert nuevo._liq_price_long(100.0) == pytest.approx(100.0 * (1 - (0.02 - 0.0033)))


def test_un_salto_que_salta_el_sl_cuenta_como_liquidacion():
    """El caso REAL que aparecia en el backtest de XRP a 50x.

    Una vela cae un 2% de golpe: se lleva el SL y la liquidacion. El motor
    tiene que contarla como liquidacion, porque se perdio todo el margen,
    no el SL.
    """
    px = np.array([100.0, 100.0, 98.0], dtype=float)
    bt = Backtester(leverage=50.0, timeframe="1h")
    liq = bt._liq_price_long(100.0)
    assert liq is not None and liq == pytest.approx(98.33)
    # la vela 98.0 esta por debajo de liquidacion -> toca
    assert bt._touched_liq(px, 0, 2, liq) is True
    # un recorrido que se queda en -0,4% NO toca liquidacion
    px_suave = np.array([100.0, 100.0, 99.6], dtype=float)
    assert bt._touched_liq(px_suave, 0, 2, liq) is False


def test_sin_apalancamiento_no_hay_liquidacion():
    bt = Backtester(leverage=1.0)
    assert bt._liq_price_long(100.0) is None
