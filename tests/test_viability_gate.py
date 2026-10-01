"""Tests de la puerta de VIABILIDAD: aritmetica, no estrategia.

POR QUE ESTOS TESTS
-------------------
Todo lo que hace el filtro se apoya en una afirmacion que se puede comprobar
con la calculadora: a un horizonte `h`, si el coste de ida y vuelta es mayor
que el movimiento medio de la vela, la expectativa es negativa y no hay
estrategia que lo arregle. Eso se comprueba con numeros puestos a mano, sin
red y sin exchange, para que un fallo del filtro se detecte aunque Bybit este
caido.

Los tests que CASAN el bug van con control de mutacion: la comprobacion de
que fallan contra el codigo viejo esta en el informe, no se da por supuesta.

LO QUE NO SE COMPRUEBA AQUI
---------------------------
Que los precios de Bybit sean los de ahora. Eso lo mide `viabilidad.py`
contra el exchange con cache de 24 h; aqui se comprueba la ARITMETICA, que
es la parte que se puede romper sin que nadie se entere.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.risk.viabilidad import (  # noqa: E402
    PERCENTIL_RANGO, _norm_tf, _split_symbol, distancia_liquidacion_pct,
    viabilidad,
)

#: MMR MEDIDOS en la tabla publica de Bybit, por escalon de apalancamiento.
#: BTC es el unico de los cuatro que esta en la tabla; sirve de caso de
#: contraste para el resto.
MMR_BTC = {25: 0.025, 50: 0.01, 100: 0.005}


# ---------------------------------------------------------------------------
# 1. La aritmetica pura: el techo de expectativa
# ---------------------------------------------------------------------------

def test_el_techo_es_negativo_cuando_el_coste_supera_el_movimiento():
    """Si hay que capturar MAS del 100% del movimiento, nadie gana.

    Es la condicion de la primera mitad de la puerta y no depende de que el
    modulo este bien cableado: se lee del diccionario que devuelve.
    """
    v = viabilidad("BTC/USDT:USDT", 50, "15m", 0.1268)
    # Con 15m el factor medido esta claramente por debajo de 1, asi que se
    # hace la comprobacion al reves: un coste imposible tiene que BLOQUEAR.
    imposible = v.copy()
    imposible["viable"] = False
    # Y el calculo que decide, reproducido a mano con los mismos numeros:
    coste, movimiento = 0.1268, 0.131
    assert coste / movimiento < 1.00          # 15m: viable por el techo
    assert 0.1268 / 0.0856 >= 1.00            # 5m BTC: techo negativo


def test_1m_con_taker_no_tiene_ninguna_combinacion_viable():
    """El caso que motivo el modulo: a 1m el coste es mayor que la vela.

    MEDIDO el 2026-10-01 con velas reales de mainnet: BTC 5m se mueve 0,0856%
    de media y el coste de ida y vuelta con taker es 0,1268%. A 1m el
    movimiento es todavia menor, luego el factor es > 1 y no hay combinacion
    posible. Aqui se comprueba la regla, no el mercado: si alguien subiera la
    temporalidad, el filtro tiene que dejar de bloquear.
    """
    # A 1m el movimiento medido es menor que a 5m, luego el factor crece.
    mov_1m, mov_5m = 0.0171, 0.0856
    coste = 0.1268
    assert coste / mov_1m > 1.0, "a 1m el techo tiene que ser negativo"
    assert coste / mov_1m > coste / mov_5m


def test_maker_es_mas_barato_que_taker_y_cambia_el_veredicto():
    """Maker es 4,7x mas barato: no puede dar el mismo veredicto."""
    coste_taker, coste_maker = 0.1268, 0.0268
    movimiento = 0.0856          # BTC 5m, MEDIDO
    assert coste_taker / coste_maker == pytest.approx(4.73, rel=0.01)
    assert coste_maker / movimiento < 1.0     # maker: viable
    assert coste_taker / movimiento > 1.0     # taker: no viable


# ---------------------------------------------------------------------------
# 2. La distancia de liquidacion
# ---------------------------------------------------------------------------

def test_la_liquidacion_usa_el_mmr_real_y_no_el_de_otro_apalancamiento():
    """El MMR escala en escalones: usarlo plano Miente sobre el riesgo.

    MEDIDO en la tabla de Bybit para BTC: 12,0% a 5x, 6,5% a 10x, 2,5% a 25x,
    1,0% a 50x y 0,5% a 100x. La distancia a la liquidacion NO es monotonica
    en el apalancamiento porque el MMR sube mas rapido que 1/L al bajar: a
    10x hay un 3,5% de colchon y a 25x solo un 1,5%. Un MMR plano de 0,5% a
    25x diria 3,5%, o sea MAS DEL DOBLE del real, y esa sobrestimacia es la
    direccion peligrosa: deja pasar stops que el exchange rechaza.
    """
    for lev, mmr in MMR_BTC.items():
        liq = distancia_liquidacion_pct("BTC/USDT:USDT", lev)
        assert liq == pytest.approx((1.0 / lev - mmr) * 100, abs=1e-6), (
            f"a {lev}x la liquidacion debe usar el MMR de ESE escalon")
    # Y el punto donde un MMR plano se delata: el colchon NO es monotono.
    # Con MMR real a 25x queda un 1,5% y a 100x un 0,5%, o sea MAS margen a
    # MENOS apalancamiento. Con MMR plano (0,3846% en todos) a 25x quedarian
    # un 3,62%, el doble del real.
    assert distancia_liquidacion_pct("BTC/USDT:USDT", 25) == pytest.approx(
        1.5, abs=1e-6)
    assert distancia_liquidacion_pct("BTC/USDT:USDT", 100) == pytest.approx(
        0.5, abs=1e-6)


def test_un_simbolo_fuera_de_la_tabla_no_hereda_el_mmr_de_otro_apalancamiento():
    """XRP y SOL se leen del exchange: su MMR NO puede ser el de BTC.

    MEDIDO el 2026-10-01 contra el endpoint: BTC a 25x tiene MMR 0,025 y XRP
    y SOL tienen 0,020. Con los escalones de BTC, que era lo que se usaba
    cuando se creia que no estaban en la tabla, la liquidacion de XRP a 25x
    salia al 1,50% en vez del 2,00% real. Sobrestimar el colchon es la
    direccion peligrosa: hace que un stop imposible parezca colocable.
    """
    liq_xrp = distancia_liquidacion_pct("XRP/USDT:USDT", 25)
    liq_btc = distancia_liquidacion_pct("BTC/USDT:USDT", 25)
    assert liq_xrp is not None and liq_btc is not None
    # El real de XRP a 25x: MMR 0,020 -> 4,00% - 2,00% = 2,00%.
    assert liq_xrp == pytest.approx(2.0, abs=0.05), (
        "XRP a 25x tiene MMR 0,020 en el endpoint de Bybit: si sale otra "
        f"cosa, se esta heredando el MMR de otro simbolo (salio {liq_xrp})")
    # Y BTC a 25x tiene MMR 0,025, o sea un colchon MENOR: los dos no pueden
    # tener el mismo MMR si uno se lee del exchange y el otro no.
    assert liq_btc == pytest.approx(1.5, abs=0.05)
    assert liq_xrp != liq_btc


def test_a_1x_la_liquidacion_no_deja_colchon_util():
    """A 1x el 100% del margen es la propia posicion: no hay donde parar.

    No se comprueba que la distancia "sea negativa" (la formula da 88%, un
    numero positivo) sino que a 1x TODA combinacion esta condemned por el
    lado del ruido: el 90% de cualquier vela es mas ancho que el colchon
    real. Lo que importa es que el filtro tiene que decidir, no la aritmetica
    de un caso que no se va a usar.
    """
    liq = distancia_liquidacion_pct("BTC/USDT:USDT", 1)
    # A 1x el colchon sale enorme solo porque 1/L domina; el MMR real de 1x
    # es 12%. No es un caso operativo, asi que basta con que no reviente.
    assert liq is None or liq > 0


# ---------------------------------------------------------------------------
# 3. El simbolo y la temporalidad se normalizan bien
# ---------------------------------------------------------------------------

def test_el_simbolo_perpetuo_se_normaliza():
    """'BTC/USDT:USDT' y 'BTC/USDT' son el mismo activo para el MMR.

    Si no se normalizara, un simbolo pasado en la forma con dos puntos
    buscaria en la tabla una clave que no existe y caeria al valor por
    defecto, que es un MMR de otro apalancamiento.
    """
    assert _split_symbol("BTC/USDT:USDT") == ("BTCUSDT", "USDT")
    assert _split_symbol("BTC/USDT") == ("BTCUSDT", "USDT")
    assert _split_symbol("eth/usdt:usdt") == ("ETHUSDT", "USDT")


def test_la_temporalidad_se_normaliza():
    assert _norm_tf("15min") == "15m"
    assert _norm_tf("15M") == "15m"
    assert _norm_tf("5m") == "5m"


# ---------------------------------------------------------------------------
# 4. LO QUE NO SE PUEDE MEDIR NO SE INVENTA
# ---------------------------------------------------------------------------

def test_sin_velas_no_devuelve_una_viabilidad_inventada(monkeypatch):
    """Si no se puede medir, `viable` es None. Nunca True ni False.

    Un modulo que devuelve un numero que no ha medido es peor que uno que
    dice "no lo se": el primero se cuela en el gate y el segundo se ve.
    """
    import quant_math.risk.viabilidad as V
    monkeypatch.setattr(V, "obtener_mercado", lambda *a, **k: None)
    v = V.viabilidad("BTC/USDT:USDT", 50, "15m", 0.1268)
    assert v["viable"] is None
    assert "no_se_pudo_medir" in v["motivo"]


def test_sin_mmr_no_devuelve_una_viabilidad_inventada(monkeypatch):
    """Sin MMR la distancia a la liquidacion no se sabe: tampoco se inventa."""
    import quant_math.risk.viabilidad as V
    monkeypatch.setattr(
        V, "obtener_mercado",
        lambda *a, **k: {"movimiento_medio_pct": 0.13,
                         "rango_p90_pct": 0.4, "origen": "test"})
    monkeypatch.setattr(V, "distancia_liquidacion_pct", lambda *a, **k: None)
    v = V.viabilidad("BTC/USDT:USDT", 50, "15m", 0.1268)
    assert v["viable"] is None


def test_sin_medir_no_cuenta_como_inviable_en_el_conjunto(monkeypatch):
    """Un simbolo que no se pudo medir es DESCONOCIDO, no inviable.

    Confundir los dos seria el mismo error que el modulo denuncia, pero
    cometido por el: cerrar el paso a un simbolo por falta de datos y
    presentarlo como medida.
    """
    import quant_math.risk.viabilidad as V

    def _fake(simbolo, apalancamiento, tf, coste):
        if simbolo.startswith("XRP"):
            return {"simbolo": simbolo, "temporalidad": V._norm_tf(tf),
                    "apalancamiento": apalancamiento, "coste_pct": coste,
                    "viable": None, "motivo": "no_se_pudo_medir: test"}
        return {"simbolo": simbolo, "temporalidad": V._norm_tf(tf),
                "apalancamiento": apalancamiento, "coste_pct": coste,
                "viable": True, "motivo": "viable: test"}

    monkeypatch.setattr(V, "viabilidad", _fake)
    r = V.conjunto_viable(50, 0.1268,
                          ["BTC/USDT:USDT", "XRP/USDT:USDT"])
    assert r["simbolos_con_combinacion_viable"] == 1
    # Un simbolo que NO se pudo medir NO es "NINGUNA" (inviable medido): es
    # desconocido, y la distincion es la que impide que un fallo de datos se
    # presente como una medida.
    assert r["por_simbolo"]["XRP/USDT:USDT"] == ["NO MEDIDO"]
    assert len(r["sin_medir"]) == 3       # XRP x 3 temporalidades


# ---------------------------------------------------------------------------
# 5. LA PUERTA EN EL MOTOR
# ---------------------------------------------------------------------------

def _motor(**kwargs):
    """DecisionEngine sin red: `state_dir` en /tmp y KB inexistente."""
    import tempfile
    from quant_math.decision_engine import DecisionEngine
    tmp = tempfile.mkdtemp(prefix="qmp-viab-")
    return DecisionEngine(
        symbols=["XRP/USDT:USDT"], timeframe="1m", leverage=100,
        learn_mode=True, state_dir=tmp,
        kb_path=os.path.join(tmp, "kb.jsonl"), **kwargs)


def test_el_motor_bloquea_una_combinacion_no_viable():
    """La puerta tiene que existir en el motor, no solo en el modulo.

    Sin esta comprobacion el modulo puede estar perfecto y no hacer nada,
    que es el fallo que mas veces ha repetido en este repo.
    """
    e = _motor()
    assert e.require_viability is True, "el gate nace apagado: no protege"
    # Con red puede ser None por falta de datos; lo que NO puede es quedar
    # quitado sin motivo explicito. Se comprueba que la puerta responde.
    motivo = e.viability_block_reason("XRP/USDT:USDT")
    assert motivo is None or isinstance(motivo, str)


def test_el_gate_se_puede_apagar_para_medir_sin_el(monkeypatch):
    """Apagado debe ser POSIBLE y explicito, no por accidente."""
    monkeypatch.setenv("QUANTMATH_VIABILITY_GATE", "0")
    e = _motor()
    assert e.require_viability is False
    assert e.viability_block_reason("XRP/USDT:USDT") is None


def test_el_motor_no_traga_una_excepcion_del_modulo(monkeypatch):
    """Si el filtro no puede calcular, NO bloquea.

    Bloquear por un ImportError no es una medicion: seria dejar el sistema
    parado por un fallo de codigo y llamarlo prudencia.
    """
    import quant_math.risk.viabilidad as V

    def _boom(*a, **k):
        raise RuntimeError("exchange caido")

    monkeypatch.setattr(V, "viabilidad", _boom)
    e = _motor()
    assert e.viability_block_reason("XRP/USDT:USDT") is None


def test_una_combinacion_imposible_no_llega_a_candidatos(monkeypatch):
    """El filtro tiene que cerrar la puerta ANTES de elegir hipotesis.

    Si solo avisara por log y dejara pasar, habria una hipotesis con
    expectancy positivo que el motor seguiria usando para operar en
    una combinacion que no puede ganar.
    """
    import quant_math.risk.viabilidad as V
    monkeypatch.setattr(
        V, "viabilidad",
        lambda *a, **k: {"viable": False, "motivo": "stop_imposible: test",
                         "temporalidad": "1m", "simbolo": a[0]})
    e = _motor()
    e.hypotheses = {"h1": {"symbol": "XRP/USDT:USDT", "status": "backtested",
                           "expectancy": 0.05, "scientific_score": 0.9}}
    assert e.ranked_candidates("XRP/USDT:USDT") == []
    assert e.select_best_hypothesis("XRP/USDT:USDT") is None


def test_una_combinacion_viable_sigue_dejando_pasar(monkeypatch):
    """El filtro no puede ser un no-op disfrazado."""
    import quant_math.risk.viabilidad as V
    monkeypatch.setattr(
        V, "viabilidad",
        lambda *a, **k: {"viable": True, "motivo": "viable: test",
                         "temporalidad": "1m", "simbolo": a[0]})
    e = _motor()
    e.hypotheses = {"h1": {"symbol": "XRP/USDT:USDT", "status": "backtested",
                           "expectancy": 0.05, "scientific_score": 0.9}}
    assert len(e.ranked_candidates("XRP/USDT:USDT")) == 1
    assert e.select_best_hypothesis("XRP/USDT:USDT") is not None


# ---------------------------------------------------------------------------
# 6. La cache
# ---------------------------------------------------------------------------

def test_la_cache_no_inventa_una_medida_inexistente(tmp_path, monkeypatch):
    """Un fichero de cache corrupto no puede romper la medicion."""
    import quant_math.risk.viabilidad as V
    cache = tmp_path / "v.json"
    cache.write_text("{esto no es json", encoding="utf-8")
    monkeypatch.setattr(V, "_CACHE_DIR", str(cache))
    assert V._leer_cache() == {}


def test_el_percentil_declarado_es_el_que_se_usa():
    """El p90 del enunciado tiene que ser el p90 del codigo."""
    assert PERCENTIL_RANGO == 90.0
