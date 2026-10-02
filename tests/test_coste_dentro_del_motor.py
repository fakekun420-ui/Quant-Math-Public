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
    import backtesting.backtester as BT
    # Se usa `coste_para` y no `COSTE_TAKER`: el suelo de comision lleva el
    # funding a cero A PROPOSITO, porque un suelo no puede convertirse sin
    # querer en un coste. La serie que se quiere comprobar es la que lleva
    # funding, que es la que construye la ruta de produccion.
    m = BT.coste_para("BTC/USDT:USDT", periodo="2025-2026")
    corto = m.coste_por_operacion_pct(horas_mantenido=8.0)
    largo = m.coste_por_operacion_pct(horas_mantenido=80.0)
    fijo = m.ida_y_vuelta_pct()
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


# ---------------------------------------------------------------------------
# El coste POR SIMBOLO. MEDIDO el 2026-10-02.
# ---------------------------------------------------------------------------

def test_el_spread_medido_no_puede_venir_de_una_sola_foto():
    """Un spread de 0,427% salio de UN tick de XRP y era 65x lo medido.

    Es el mismo error que hizo que "0,1268%" se tomara por el coste entero: un
    numero de una sola muestra parece tan firme como uno de 25, y no lo es. Se
    fija la tabla medida para que nadie reintroduzca un numero de un tick sin
    dejar constancia de que lo es.
    """
    import backtesting.backtester as BT
    for simbolo, esperado in BT.SPREAD_POR_SIMBOLO_PCT.items():
        assert 0.0 <= esperado <= 0.05, (
            f"{simbolo}: un spread de {esperado}% es de un tick, no de una "
            f"medida. El medido con 25 muestras va del 0,00012% al 0,00822%")
    # Y el orden tiene que ser el del libro: BTC el mas profundo.
    assert (BT.SPREAD_POR_SIMBOLO_PCT["BTC"]
            < BT.SPREAD_POR_SIMBOLO_PCT["ETH"]
            < BT.SPREAD_POR_SIMBOLO_PCT["XRP"]
            < BT.SPREAD_POR_SIMBOLO_PCT["SOL"]), (
        "en Bybit el libro se ensancha de BTC a SOL; si el orden se invierte, "
        "alguno de los numeros esta cambiado de sitio")


def test_las_unidades_del_spread_no_se_confunden():
    """El medido es un PORCENTAJE y se usa como fraccion. Confundirlas pesa 100x.

    MEDIDO al escribir esto: la tabla guardaba 0,00649 en porcentaje y se
    usaba como fraccion, y el coste de XRP salia en 1,42% en vez de 0,14%. Una
    unidad mal puesta pesa mas que un valor mal puesto porque no se nota.
    """
    import backtesting.backtester as BT
    m = BT.coste_para("XRP/USDT:USDT", periodo="2025-2026")
    esperado_spread_pct = BT.SPREAD_POR_SIMBOLO_PCT["XRP"]
    assert abs(m.deslizamiento_por_llenado * 100.0 - esperado_spread_pct) < 1e-9, (
        f"el modelo usa {m.deslizamiento_por_llenado * 100:.5f}% y lo medido "
        f"es {esperado_spread_pct}%")
    # Y el total tiene que salir cerca de 0,14%, no cerca de 1,4%.
    assert 0.05 < m.ida_y_vuelta_pct() < 0.30, (
        f"el coste ida y vuelta de XRP sale en {m.ida_y_vuelta_pct():.4f}%, que "
        f"esta fuera de lo medido. Con un spread de 0,00649% y una comision "
        f"de 0,000634 por lado no puede pasar de 0,20%")


def test_el_funding_difiere_por_periodo_y_no_se_puede_pedir_uno_inventado():
    """El funding de 2025-2026 es entre 3 y 10 veces mas barato que el de
    2023-2024. Usar la media de los dos no representa a ninguno, asi que pedir
    un periodo sin medir tiene que FALLAR y no devolver un promedio."""
    import backtesting.backtester as BT
    for simbolo in BT.FUNDING_POR_SIMBOLO:
        a = BT.coste_para(f"{simbolo}/USDT:USDT", 8 * 24, periodo="2023-2024")
        b = BT.coste_para(f"{simbolo}/USDT:USDT", 8 * 24, periodo="2025-2026")
        assert a.coste_por_operacion_pct(192) > b.coste_por_operacion_pct(192), (
            f"{simbolo}: el tramo viejo tiene que costar MAS que el reciente; "
            f"si no, las dos filas estan cambiadas de sitio")
    with pytest.raises(ValueError, match="sin funding medido"):
        BT.coste_para("BTC/USDT:USDT", 8 * 24, periodo="1999-2000")


def test_el_spread_se_aplica_por_simbolo_y_no_a_todos_igual():
    """Un solo numero para los cuatro obliga a que uno pague el coste de otro.

    BTC tiene el libro 54 veces mas ajustado que SOL: 0,00012% contra 0,00822%.
    Con un numero unico se estaria cobrando a BTC el spread de SOL.
    """
    import backtesting.backtester as BT
    btc = BT.coste_para("BTC/USDT:USDT", periodo="2025-2026")
    sol = BT.coste_para("SOL/USDT:USDT", periodo="2025-2026")
    assert btc.ida_y_vuelta_pct() < sol.ida_y_vuelta_pct(), (
        "BTC no puede costar lo mismo que SOL: sus libros no se parecen")


# ---------------------------------------------------------------------------
# El deslizamiento EFFECTIVO, que no es el spread del primer nivel.
# MEDIDO el 2026-10-02 recorriendo el libro de ordenes.
# ---------------------------------------------------------------------------

def test_el_deslizamiento_crece_con_el_nocional():
    """A 25.000 USDT el deslizamiento es cero en BTC y ETH, y no lo es a 500.000.

    MEDIDO el 2026-10-02 recorriendo el libro de verdad. El resultado CONTRADICE
    lo que se publico antes en este repositorio, que decia que en SOL a 25.000
    el deslizamiento era 0,1822%. Venia de restar unidades del activo de un
    presupuesto en USDT, con lo que el resultado crecia con el PRECIO del
    activo y BTC aparecia como el mas caro de operar.

    Este test existe para que el error no vuelva por el otro lado: si alguien
    vuelve a mezclar unidades, el recorrido dara un slippage enorme y esto
    fallara.
    """
    import backtesting.backtester as BT
    for simbolo in ("BTC", "ETH", "XRP", "SOL"):
        notionales = [250.0, 2500.0, 25000.0, 100000.0, 500000.0]
        vals = [BT.slippage_para(f"{simbolo}/USDT:USDT", n) for n in notionales]
        # NO se exige monotonia ESTRICTA. Cada nocional se midio en una toma
        # distinta del libro y este se mueve, asi que en SOL se midio 0,01504%
        # a 25.000 y 0,01438% a 100.000. Exigir que la serie suba a cada paso
        # seria exigir algo que el dato no tiene, y un test que obliga a
        # deformar el dato para cumplirlo es peor que no tener el test.
        # Lo que si tiene que cumplirse es la TENDENCIA y la MAGNITUD.
        assert vals[-1] > vals[0], f"{simbolo}: {vals}"
        assert all(v < 0.5 for v in vals), (
            f"{simbolo}: un deslizamiento de {max(vals):.4f}% significa que se "
            f"estan mezclando unidades del activo con USDT, o que el recorrido "
            f"del libro se ha roto")
        assert vals[0] == 0.0, (
            f"{simbolo}: con 250 USDT tiene que entrar en el primer nivel, que "
            f"en BTC medido son 268.295 USDT")


def test_a_25k_el_deslizamiento_es_de_orden_milesimas():
    """El nocional del backtest (25% de 100.000) entra en el primer nivel."""
    import backtesting.backtester as BT
    for simbolo in ("BTC", "ETH", "XRP", "SOL"):
        v = BT.slippage_para(f"{simbolo}/USDT:USDT", 25000.0)
        assert v <= 0.02, (
            f"{simbolo} a 25.000 USDT da {v:.4f}%. Lo medido es 0% en BTC y "
            f"ETH y del orden de 0,012-0,015% en XRP y SOL.")


def test_la_profundidad_solo_empieza_a_importar_a_partir_de_100_000():
    """Con un nocional de backtest la profundidad no es el problema."""
    import backtesting.backtester as BT
    for simbolo in ("BTC", "ETH", "XRP", "SOL"):
        pequeno = BT.slippage_para(f"{simbolo}/USDT:USDT", 25000.0)
        grande = BT.slippage_para(f"{simbolo}/USDT:USDT", 500000.0)
        assert grande > pequeno, f"{simbolo}: {grande} vs {pequeno}"


def test_nunca_interpola_hacia_arriba():
    """Un nocional por encima de lo medido se queda con la fila mas cara."""
    import backtesting.backtester as BT
    ultima = BT.SLIPPAGE_POR_NOTIONAL["SOL"][500000.0]
    assert BT.slippage_para("SOL/USDT:USDT", 2000000.0) == ultima, (
        "pedir 2.000.000 USDT y devolver menos que lo medido a 500.000 seria "
        "optimista por construccion")


def test_una_fila_no_medida_no_se_confunde_con_cero():
    """Un simbolo fuera de la tabla devuelve 0.0 sin avisar, y por eso existe
    `simbolo_medido`: un 0 silencioso hace que un backtest parezca gratis."""
    import backtesting.backtester as BT
    assert not BT.simbolo_medido("DOGE/USDT:USDT", 25000.0), (
        "DOGE no tiene profundidad medida: preguntar tiene que decir que no se "
        "sabe, no devolver 0")
    assert BT.slippage_para("DOGE/USDT:USDT", 25000.0) == 0.0
    assert BT.simbolo_medido("SOL/USDT:USDT", 25000.0), "SOL si esta medido"


# ---------------------------------------------------------------------------
# El bug de PRODUCCION: el adaptador cobrando 4,4 veces de mas.
# MEDIDO y arreglado el 2026-10-02.
# ---------------------------------------------------------------------------

def test_el_suelo_de_comision_no_lleva_deslizamiento_ni_funding():
    """`COSTE_TAKER` es un SUELO, no un modelo de coste.

    MEDIDO el 2026-10-02: `COSTE_TAKER` llevaba dentro el deslizamiento de
    0,2135%, que despues se retracto por estar 65 veces medido, y el adaptador
    lo usaba como valor por defecto. La ruta de produccion cobraba 4,4 veces
    de mas. Que ahora no lleve nada mas es lo que evita que se repita.
    """
    from backtesting import COSTE_TAKER
    assert COSTE_TAKER.deslizamiento_por_llenado == 0.0, (
        "el suelo de comision lleva deslizamiento. Si lo lleva, es un modelo "
        "de coste disfrazado de suelo y vuelve a poder quedar retractado")
    assert COSTE_TAKER.funding_por_8h == 0.0, (
        "el suelo de comision lleva funding, y el funding depende del regimen")
    assert abs(COSTE_TAKER.ida_y_vuelta_pct() - 0.1268) < 1e-6


def test_el_adaptador_calcula_el_coste_y_no_hereda_una_constante():
    """El adaptador tiene que LLAMAR a las medidas, no usar un valor fijo.

    Se lee el fuente porque lo que hay que comprobar es que llame a
    `coste_para`: un motor que sabe cobrar y un adaptador que no le pide el
    coste dan el mismo numero en un test de resultado, y el numero es
    justamente el que falla.
    """
    import inspect
    from quant_math.autonomous_research.adapters.quant_math_adapter import (
        QuantMathAdapter)
    src = inspect.getsource(QuantMathAdapter.run_backtest)
    for llamada in ("coste_para(", "periodo_para(", "slippage_para("):
        assert llamada in src, (
            f"el adaptador no llama a {llamada}: entonces vuelve a usar un "
            f"coste fijo, y eso fue exactamente el bug")


def test_el_periodo_se_deduce_de_la_fecha_y_no_se_pide():
    """Que el regimen se deduzca de la vela es lo que evita el cobro equivocado.

    Si hubiera que pasar el periodo a mano, el valor por defecto seria el de un
    regimen cualquiera y la mitad de los backtest cobrarian el funding del
    tramo equivocado, que es entre 3 y 10 veces mas barato.
    """
    import backtesting.backtester as BT
    import pandas as pd
    assert BT.periodo_para(pd.Timestamp("2023-06-15", tz="UTC")) == "2023-2024"
    assert BT.periodo_para(pd.Timestamp("2025-06-15", tz="UTC")) == "2025-2026"
    assert BT.periodo_para(None) is None
    assert BT.periodo_para(pd.Timestamp("2022-06-15", tz="UTC")) is None, (
        "una fecha fuera de todo lo medido tiene que decir que no se sabe, no "
        "devolver un regimen por defecto")


def test_el_funding_liquida_cada_8_horas_y_no_cada_hora():
    """Los cuatro pares de este proyecto cobran cada 8 horas a las 0, 8 y 16.

    MEDIDO sobre las 3.800 descargas por simbolo: el intervalo es de 8 horas
    exactas en las 3.800, sin una sola excepcion. Se comprueba porque algunos
    pares de otros exchanges cobran cada hora, y con un modelo fijo de 8 horas
    un par de 1 hora estaria 8 veces mal.
    """
    import backtesting.backtester as BT
    assert BT.FUNDING_CADA_HORAS == 8
    assert BT.FUNDING_HORAS == (0, 8, 16)
