"""El coste tiene que estar dentro del motor, y no puede contarse dos veces.

LOS TRES ERRORES QUE ESTE FICHERO CIERRA
----------------------------------------
1. `slippage_pct = 0.0` y `funding_rate_8h = 0.0` por defecto. MEDIDO el
   2026-10-02: el adaptador construia el motor sin pasar ninguno de los dos,
   de modo que TODOS los backtests del proyecto asumian ejecucion perfecta y
   mantenimiento gratis. No era un error de cuentas: era un supuesto
   favorable que no estaba escrito en ninguna parte.

2. El "0,1268% de taker" que se venia usando en toda la sesion es SOLO la
   comision. Con el spread medido el coste real ida y vuelta es 0,5538%, o
   sea que se estaba descontando menos de un cuarto de lo que cuesta
   realmente.

3. Restar el coste A MANO sobre un motor que ya lo descuenta. MEDIDO: el
   motor descuenta 0,2001% por operacion, que reconcilia con sus 0,001 por
   lado. Restando 0,1268% encima se contaba dos veces.

QUE COMPRUEBA CADA TEST
-----------------------
- Que la aritmetica del modelo es la que dice (comision x 2 + slippage x 2).
- Que el modelo lleva FECHA y exchange: un numero de coste sin fecha no es un
  dato, y el dia que Bybit cambie sus comisiones el valor sera historia.
- Que el descuento del motor por operacion es su coste, y no el doble.
- Que la ruta de produccion no usa ejecucion perfecta.
- Que el funding escala con las horas de permanence, que es lo que lo
  distingue del resto del coste: la comision va por relleno y el funding por
  tiempo.
"""

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def test_la_aritmetica_del_modelo_de_coste():
    from backtesting import ModeloCoste
    m = ModeloCoste(comision_por_lado=0.000634, deslizamiento_por_llenado=0.0)
    # Ida y vuelta son DOS rellenos, y por eso se multiplica por 2. Un modelo
    # que cobrara una sola vez estaria infraestimando el coste a la mitad.
    assert abs(m.ida_y_vuelta_pct() - 0.1268) < 1e-6, m.ida_y_vuelta_pct()
    con_spread = ModeloCoste(comision_por_lado=0.000634,
                             deslizamiento_por_llenado=0.002135)
    assert abs(con_spread.ida_y_vuelta_pct() - 0.5538) < 1e-3, con_spread.ida_y_vuelta_pct()


def test_el_coste_lleva_fecha_y_exchange():
    """Un numero de coste sin fecha parece tan preciso como uno al dia."""
    from backtesting import COSTE_TAKER, COSTE_MAKER
    for m in (COSTE_TAKER, COSTE_MAKER):
        assert m.medido_el, "el modelo de coste tiene que decir cuando se midio"
        assert m.exchange, "las comisiones cambian por exchange y por par"
        assert len(m.medido_el) == 10 and m.medido_el[4] == "-", m.medido_el


def test_el_funding_escala_con_las_horas_y_el_resto_no():
    """El funding es el unico componente que depende del TIEMPO.

    La comision va por relleno y el deslizamiento tambien, asi que una
    operacion que se mantiene el doble paga lo mismo de esos dos y el doble
    de funding. Si el funding no escalara, mantener una posicion abierta seria
    gratis, que es justo el supuesto que se acaba de quitar.
    """
    from backtesting import COSTE_TAKER
    corto = COSTE_TAKER.coste_por_operacion_pct(horas_mantenido=8.0)
    largo = COSTE_TAKER.coste_por_operacion_pct(horas_mantenido=80.0)
    fijo = COSTE_TAKER.ida_y_vuelta_pct()
    # 10x mas tiempo = 10x mas cobros de funding, y el resto igual.
    assert abs(largo - fijo - (corto - fijo) * 10.0) < 1e-6
    assert largo > corto > fijo


def test_el_coste_de_la_ruta_de_produccion_no_es_cero():
    """El adaptador tiene que pasar un coste MEDIDO, no el de por defecto.

    Este es el test que cierra el error nº1. Se lee el fuente del adaptador
    porque lo que hay que comprobar es que pase los parametros, no que el
    motor los soporte: un motor que sabe cobrar y un adaptador que no se lo
    pide dan el mismo numero en el test, y el numero es el que falla.
    """
    import inspect
    from quant_math.autonomous_research.adapters.quant_math_adapter import (
        QuantMathAdapter)
    src = inspect.getsource(QuantMathAdapter.run_backtest)
    for nombre in ("commission_rate=coste", "slippage_pct=coste",
                   "funding_rate_8h=coste"):
        assert nombre in src, (
            f"el adaptador no pasa {nombre}: entonces el motor usa su valor "
            f"por defecto y el backtest asume el coste que no se le pasa")
    assert "ModeloCoste" not in src or "COSTE_TAKER" in src, (
        "el valor por defecto del adaptador tiene que ser el modelo medido")


@pytest.mark.parametrize("comision", [0.001, 0.000634])
def test_el_motor_descuenta_su_coste_y_no_el_doble(comision):
    """El descuento del motor tiene que ser UN coste, y solo UNO.

    MEDIDO el 2026-10-02: el motor descuenta 0,2001% por operacion con sus
    0,001 por lado. Alguien que desconfie del motor tendria el reflejo de
    restar el coste otra vez "por si acaso", y ahi es donde el coste se
    contaria dos veces. Este test dice cual es la cifra del motor, para que la
    segunda resta no tenga a donde esconderse.

    POR QUE SE COMPARA CONTRA `entry_price`/`exit_price` Y NO CONTRA LA SERIE
    ------------------------------------------------------------------------
    Porque los rellenos ya llevan el deslizamiento dentro (`_adverse_fill`):
    la compra paga mas y la venta recibe menos. Lo que queda fuera de los
    rellenos, y lo que se ve al comparar con ellos, es exactamente la
    comision de los dos lados. Reconstruir el retorno desde la serie en vez de
    desde los rellenos METE el deslizamiento dentro de la medicion y lo
    compararia dos veces, que es el mismo error con otro disfraz.
    """
    import numpy as np
    from backtesting import Backtester
    simbolo = "X/USDT:USDT"
    precios = np.linspace(100.0, 120.0, 600)
    estado = {"dentro": False}

    def entrada_salida(_data):
        if not estado["dentro"]:
            estado["dentro"] = True
            return [{"symbol": simbolo, "side": "buy", "quantity": 1.0}]
        estado["dentro"] = False
        return [{"symbol": simbolo, "side": "sell", "quantity": 1.0}]

    bt = Backtester(initial_capital=100000.0, commission_rate=comision,
                    slippage_pct=0.0, funding_rate_8h=0.0, leverage=1.0)
    res = bt.run_backtest(entrada_salida, {simbolo: precios},
                          initial_capital=100000.0)
    assert res.trades, "la serie de prueba debe producir operaciones"

    for x in res.trades:
        if x.liquidated:
            continue                     # la liquidacion cierra a otro precio
        bruto = (x.exit_price - x.entry_price) / x.entry_price * 100.0
        descuento = bruto - float(x.pnl_pct)
        # MEDIDO al escribir este test: la comision de salida se cobra sobre
        # el nocional YA SUBIDO, no sobre el de entrada. Con la rampa de
        # 100 a 120 eso da 0,1395% y no 0,1268%, y durante un rato la
        # respuesta fue "el motor cobra de mas" cuando el motor estaba bien y
        # la referencia era ingenua.
        esperado = comision * 100.0 * (1.0 + x.exit_price / x.entry_price)
        assert abs(descuento - esperado) < 0.005, (
            f"el motor desconto {descuento:.4f}% y su comision por lado es "
            f"{comision}, o sea {esperado:.4f}% para ESTA operacion. Si el "
            f"descuento va al doble, el coste se esta contando dos veces; si "
            f"va a cero, no se esta contando ninguna")


def test_el_deslizamiento_esta_dentro_del_precio_de_entrada():
    """Con deslizamiento, el relleno se aleja del precio de la serie.

    Si esto no se cumpliera, el deslizamiento estaria decorativo: el motor
    aceptaria un numero de coste que no cambia nada del resultado.
    """
    import numpy as np
    from backtesting import Backtester
    simbolo = "X/USDT:USDT"
    precios = np.full(50, 100.0)
    estado = {"dentro": False}

    def entrar(_data):
        if not estado["dentro"]:
            estado["dentro"] = True
            return [{"symbol": simbolo, "side": "buy", "quantity": 1.0}]
        estado["dentro"] = False
        return [{"symbol": simbolo, "side": "sell", "quantity": 1.0}]

    limpio = Backtester(initial_capital=100000.0, commission_rate=0.0,
                        slippage_pct=0.0, leverage=1.0).run_backtest(
        entrar, {simbolo: precios}, initial_capital=100000.0)
    estado["dentro"] = False
    con_slip = Backtester(initial_capital=100000.0, commission_rate=0.0,
                          slippage_pct=0.002135, leverage=1.0).run_backtest(
        entrar, {simbolo: precios}, initial_capital=100000.0)
    assert limpio.trades and con_slip.trades
    assert con_slip.trades[0].entry_price > limpio.trades[0].entry_price, (
        "comprar con deslizamiento tiene que rellenar por ENCIMA del precio de "
        "la serie; si no, el deslizamiento no hace nada")
