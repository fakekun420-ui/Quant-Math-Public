"""
EL MMR ES POR ACTIVO Y POR APALANCAMIENTO (2026-10-01)

Este es el fallo mas grave de los encontrados, y el mas silencioso de
todos: no daba ningun sintoma. El sistema arrancaba, operaba, no
daba ni un error, y el log salia limpio. Lo unico que hacia era un
`clamp` del SL que se abria mas de lo debido.

EL DATO. El endpoint publico de Bybit
`/v5/market/risk-limit?category=linear` (sin clave, sin posicion
abierta; 600 simbolos, 17.394 filas con la paginacion completa) da el
MMR por (simbolo, apalancamiento):

    BTCUSDT  150x=0,3300%  100x=0,5000%  90x=0,5600%  80x=0,6300%
    ETHUSDT  150x=0,3300%  100x=0,5000%  90x=0,5600%  80x=0,6300%
    ENAUSDT   50x=1,0000%   33x=1,5000%   25x=2,0000%

EL BUG. El codigo usaba 0,0033 como MMR por defecto para TODO. Ese
0,33% no es un tramo de nocional: es la fila de 150x. Aplicado a otro
apalancamiento:

    apalancamiento   MMR del codigo   MMR REAL     error
         150x           0,3300%       0,3300%     correcto
         100x           0,3300%       0,5000%     -34%   <-- el que se usaba
          90x           0,3300%       0,5600%     -41%

POR QUE ESO ES GRAVE Y NO UN DETALLE. La distancia a liquidacion es
`1/L - mmr`. Un MMR mas pequeno hace la liquidacion MAS LEJOS, o sea
mas optimista. Y el `clamp` del SL existe para que el stop nunca llegue
a la liquidacion: mide cuanto puede acercarse el stop y lo recorta si se
pasa. Con el MMR equivocado, el clamp se abria y dejaba pasar un SL
mas apretado del debido, creyendo que protectoria una cosa que no
protegia. El fallo va en la peor direccion posible: menos proteccion de
la que el codigo decia dar.

ADEMAS el MMR es POR ACTIVO. ENA a 50x da 1,00%, tres veces el de BTC
a 100x, con el mismo tramo de nocional. Un MMR fijo por defecto
subestimaba el riesgo de liquidacion por un factor de tres en activos
baratos.

LO QUE ESTOS TESTS COMPRUEBAN, y por que cada uno existe:

  1) Que el MMR pedido sea el del apalancamiento pedido (100x NO es
     150x). Si alguien vuelve a un MMR fijo, cae.
  2) Que el MMR sea por activo, no un numero unico.
  3) Que el clamp MUERDA con el MMR real y NO con el equivocado: es el
     efecto observable del bug, no su definicion.
  4) Que si el exchange no responde se diga, en vez de fingir.
  5) Que `BTC/USDT:USDT` se traduzca a `BTCUSDT`, que es como lo
     llama el endpoint. Este fallo es silenciosissimo: el endpoint
     responde 600 simbolos y la busqueda simplemente no encuentra nada.

Los tests de red usan la tabla REAL ya descargada, no una inventada:
si Bybit cambiara un valor, este fichero diria que el codigo esta mal y
no al reves.
"""

import inspect

import pytest

from quant_math.orchestrator import OrchestratorConfig
from quant_math.risk import mmr_table
from quant_math.risk.roe_targets import (
    build_roe_plan,
    liquidation_price_distance,
    max_sl_price_distance,
)


# ---------------------------------------------------------------------------
# 1) EL MMR ES EL DEL APALANCAMIENTO PEDIDO
# ---------------------------------------------------------------------------

def test_el_mmr_de_100x_no_es_el_de_150x():
    """100x = 0,50% y 150x = 0,33%. Usar el de 150x para 100x es el bug.

    Este es EL test. Si vuelve a haber un MMR fijo por defecto, o si
    alguien "optimiza" usando el valor mas pequeno para que el clamp no
    muerda, cae aqui.
    """
    assert mmr_table.cargar_tabla(), "no se pudo leer la tabla de Bybit"
    btc_100, o100 = mmr_table.mmr_for_symbol("BTC/USDT:USDT", 100)
    btc_150, o150 = mmr_table.mmr_for_symbol("BTC/USDT:USDT", 150)

    assert o100.startswith("exchange:BTCUSDT"), f"no vino del exchange: {o100}"
    assert o150.startswith("exchange:BTCUSDT"), f"no vino del exchange: {o150}"
    assert btc_100 != btc_150, (
        "el MMR tiene que depender del apalancamiento: 100x y 150x no "
        "pueden dar lo mismo. Si dan lo mismo, se ha vuelto a un MMR fijo")
    assert btc_100 > btc_150, (
        "el MMR SUBE al BAJAR el apalancamiento (100x=0,50%, 150x=0,33%). "
        "Si no, el MMR se esta tomando de la fila equivocada")


def test_el_mmr_lo_aporta_el_exchange_no_una_constante_inventada():
    """Un MMR correcto por casualidad no vale: tiene que venir de Bybit.

    Un numero fifo podria dar el valor correcto hoy y quedar viejo manana
    sin que nada se entere. Lo que protege es el ORIGEN, y por eso
    `mmr_for_symbol` devuelve de donde sale el numero.
    """
    mmr_table.cargar_tabla()
    _, origen = mmr_table.mmr_for_symbol("BTC/USDT:USDT", 100)
    assert origen != "por_defecto", (
        "BTC esta en la tabla de Bybit: si sale 'por_defecto' no se ha "
        "leido el exchange")


def test_si_el_exchange_no_responde_se_dice_no_se_finge():
    """Un fallo de red que se disfraza de MMR fiable es el peor de todos.

    Es el mismo fallo cuatro veces distintas en este proyecto: guardar
    en RAM y no en disco, leer el directorio en vez del fichero, contar
    entradas en vez de posiciones, y mandar el SL sin comprobarlo. La
    forma comun es aparecer como si todo estuviera bien.
    """
    mmr, origen = mmr_table.mmr_for_symbol("NOEXISTE/USDT:USDT", 100)
    # 2026-10-01: el origen ya no es el ambiguo "por_defecto". Con el MMR
    # plano un valor unico para todo apalancamiento sobrestimaba el colchon
    # a 25x (daba 3,62% con un MMR de 150x cuando el real es 1,50%), y
    # "por_defecto" no decia de que apalancamiento salia el numero. Ahora el
    # origen lleva el escalon (`estimado_escalon:100x`), que es precisamente
    # lo que hace falta para saber que el valor es una estimacion y no una
    # medida. La propiedad que este test protege no es el nombre: es que el
    # origen NO pueda confundirse con una lectura del exchange.
    assert origen.startswith("estimado_escalon:"), (
        "un simbolo inexistente tiene que decir que se ESTIMA, no medido")
    assert "exchange" not in origen, (
        "un simbolo fuera de la tabla no puede llevar origen de exchange")
    # El valor sale del escalon del apalancamiento pedido, no de uno fijo.
    assert mmr == mmr_table._mmr_por_escalon(100)
    # Y sigue siendo MAS restrictivo que el 0,0033 plano que era el bug:
    # a 100x el escalon es 0,005, mayor que 0,0033.
    assert mmr > 0.0033, (
        "el MMR estimado tiene que ser MAS restrictivo que el 0,0033 de la "
        "tabla: usar el menor es justamente el bug que se corrige")


def test_el_simbolo_se_traduce_al_formato_del_endpoint():
    """`BTC/USDT:USDT` (ccxt) -> `BTCUSDT` (endpoint). Sin esto, silencio.

    El endpoint responde 600 simbolos y una busqueda mal formada no da
   ningun error: simplemente no encuentra la fila y devuelve el valor
    por defecto. Medido: sin base+quote se busca `BTC` y no existe.
    """
    assert mmr_table._normaliza("BTC/USDT:USDT") == "BTCUSDT"
    assert mmr_table._normaliza("ETH/USDT:USDT") == "ETHUSDT"
    assert mmr_table._normaliza("XRP/USDT") == "XRPUSDT"
    mmr_table.cargar_tabla()
    _, origen = mmr_table.mmr_for_symbol("BTC/USDT:USDT", 100)
    assert "BTCUSDT" in origen, (
        f"la traducci no llego al endpoint: {origen}")


# ---------------------------------------------------------------------------
# 2) EL MMR ES POR ACTIVO
# ---------------------------------------------------------------------------

def test_el_mmr_es_por_activo_no_un_numero_unico():
    """ENA a 50x = 1,00% y BTC a 100x = 0,50%. El mismo, y el doble.

    Con un MMR fijo se subestimaba el riesgo de liquidacion por un factor
    de tres en activos de MMR alto, sin que nada lo delatara.
    """
    mmr_table.cargar_tabla()
    _, origen_ena = mmr_table.mmr_for_symbol("ENA/USDT:USDT", 50)
    _, origen_btc = mmr_table.mmr_for_symbol("BTC/USDT:USDT", 100)
    if "ENAUSDT" not in origen_ena:
        pytest.skip("ENAUSDT no esta en la tabla publica ahora mismo")
    mmr_ena, _ = mmr_table.mmr_for_symbol("ENA/USDT:USDT", 50)
    mmr_btc, _ = mmr_table.mmr_for_symbol("BTC/USDT:USDT", 100)
    assert mmr_ena > mmr_btc, (
        "ENA tiene MMR mas alto que BTC: con un numero unico se "
        "subestimaba la liquidacion en ENA por un factor de tres")


# ---------------------------------------------------------------------------
# 3) EL EFECTO: EL CLAMP MUERDE CON EL MMR REAL
# ---------------------------------------------------------------------------

def test_el_clamp_muerde_a_100x_con_el_mmr_real():
    """AQUI ESTA EL BUG, VISTO POR SU EFECTO.

    Con el MMR equivocado (0,33%, el de 150x) la liquidacion a 100x se
    calculaba al 0,6700% y el clamp NO mordia: el SL al 27,5% pasaba
    libre.

    Con el MMR real de 100x (0,50%) la liquidacion esta al 0,5000% y el
    clamp MUERDE: el SL baja a 0,2500% de precio. El sistema llevaba
    añadiendo 0,025 puntos de precio de riesgo en cada entrada sin
    decirlo.
    """
    mmr_table.cargar_tabla()
    mmr_real, _ = mmr_table.mmr_for_symbol("BTC/USDT:USDT", 100)

    mal = build_roe_plan(mode="classic", leverage=100, take_profit_roe=0.50,
                         stop_loss_roe=0.275, maintenance_margin_rate=0.0033)
    bien = build_roe_plan(mode="classic", leverage=100, take_profit_roe=0.50,
                          stop_loss_roe=0.275,
                          maintenance_margin_rate=mmr_real)

    assert not mal.sl_clamped, (
        "con el MMR de 150x el clamp no muerde: ese es el fallo, y por eso "
        "este test tiene que seguir viendo que NO muerde")
    assert bien.sl_clamped, (
        "con el MMR REAL de 100x el clamp tiene que morder. Si no muerde, "
        "el MMR que se esta usando sigue siendo el equivocado")
    assert bien.sl_price_distance < mal.sl_price_distance, (
        "el MMR real tiene que recortar el SL por debajo del que dejaba "
        "el MMR equivocado")


def test_un_activo_de_mmr_alto_puede_hacerse_imposible_operarlo():
    """ENA a 100x: el mantenimiento IGUALA al margen inicial.

    No es un recorte, es un veto: `1/100 = 1,00%` y el MMR de ENA a 50x
    (el tramo que le toca) es 1,00%, luego la posicion se liquidaria en
    la entrada. Lanzar es lo correcto: seguir operando con esa cuenta
    seria operar creyendo que hay margen donde solo hay mantenimiento.
    """
    from quant_math.risk.roe_targets import LeverageRiskError
    mmr_table.cargar_tabla()
    mmr, origen = mmr_table.mmr_for_symbol("ENA/USDT:USDT", 100)
    if "ENAUSDT" not in origen:
        pytest.skip("ENAUSDT no esta en la tabla publica ahora mismo")
    with pytest.raises(LeverageRiskError):
        build_roe_plan(mode="classic", leverage=100, take_profit_roe=0.50,
                       stop_loss_roe=0.275, symbol="ENA/USDT:USDT")


# ---------------------------------------------------------------------------
# 4) EL ORQUESTADOR USA EL PEOR SIMBOLO, NO EL PRIMERO
# ---------------------------------------------------------------------------

def test_el_orquestador_usa_el_mmr_del_simbolo_mas_conservador():
    """Con cuatro simbolos y UN plan, el plan tiene que valer para el peor.

    Si usara el del primero, el clamp protegeria a ese y dejaria
    descubierto a los otros tres. Es la diferencia entre "operar con lo
    que hay" y "operar con lo que el mas arriesgado permite".
    """
    src = inspect.getsource(OrchestratorConfig.__post_init__)
    assert "mmr_for_symbol" in src, (
        "el orquestador tiene que consultar el MMR real por simbolo")
    assert "max(_mmrs" in src, (
        "tiene que quedarse con el MAS CONSERVADOR (el MMR mas alto) de "
        "todos los simbolos, no con el del primero: si no, el clamp "
        "protegiria a uno y dejaria al resto sin cubrir")

    codigo = "\n".join(ln for ln in src.splitlines()
                       if not ln.strip().startswith("#"))
    assert "maintenance_margin_rate=_mmr_arg" in codigo, (
        "el MMR resuelto tiene que LLEGAR al plan: resolverlo y no "
        "pasarlo seria el mismo fallo con dos pasos")


def test_el_plan_declara_de_donde_sale_el_mmr():
    """Un numero de riesgo que no dice su origen no se puede auditar.

    Se-annade a los warnings del plan: aparece en el panel y en el log,
    junto al clamp que depende de el.
    """
    src = inspect.getsource(build_roe_plan)
    assert "MMR usado" in src, (
        "el plan tiene que declarar el MMR que uso y de donde salio: es "
        "el numero del que depende el clamp, o sea el que decide si el SL "
        "protege o no")
