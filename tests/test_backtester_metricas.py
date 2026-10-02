"""Los dos bugs del backtester que devuelven numeros que mienten.

QUE PASABA
----------
Los dos se encontraron el 2026-10-01.backtestando las 8 familias de
produccion sobre 1.000 velas REALES de mainnet a 15m, en vez de leer el
codigo. Ninguno de los dos habria salido leyendo el modulo: los dos
devuelven un numero con aspecto de numero.

1. `max_drawdown` devolvia 0.0 SIEMPRE, no "casi siempre". El drawdown se
   calcula como `(precio - maximo_acumulado) / maximo_acumulado * 100`, y
   por construccion el maximo acumulado es >= cada precio, luego TODOS los
   drawdowns son <= 0. Consecuencia logica: `np.max` de una serie no positiva
   es el mas cercano a cero. Una curva de equity que cae un 20% y se
   recupera reportaba 0% de caida.

2. `sharpe_ratio` restaba el riesgo sin riesgo (0,02 = un 2% ANUAL) de una
   media de retorno que ya venia multiplicada por 252. Dos unidades
   distintas restandose: el termino se anulaba.

POR QUE ES PELIGROSO
--------------------
El motor ordena por expectativa, pero el score cientifico (el pondero 0,5
del compuesto) se alimenta del backtest, y ahi entran Sharpe y drawdown. Un
drawdown que siempre vale 0 hace que el motor de riesgo no vea ninguna
perdida: exactamente cuando tiene que verla.
"""

import numpy as np
import pytest

from backtesting.backtester import PerformanceMetrics


# ---------------------------------------------------------------------------
# 1. max_drawdown
# ---------------------------------------------------------------------------

def test_un_drawdown_del_20_por_ciento_no_puede_ser_cero():
    """La demostracion minima. 100 -> 80 es una caida del 20%."""
    precios = [100.0, 95.0, 90.0, 85.0, 80.0, 85.0, 90.0]
    dd = PerformanceMetrics.max_drawdown(precios)
    assert dd == pytest.approx(20.0), (
        f"la serie cae de 100 a 80: el maximo drawdown es 20%, y el motor "
        f"devolvio {dd}")


def test_una_curva_que_sube_no_tiene_drawdown():
    """Control positivo: una equity que solo sube tiene dd = 0. Legitimo."""
    precios = [100.0, 101.0, 103.0, 106.0, 110.0]
    assert PerformanceMetrics.max_drawdown(precios) == pytest.approx(0.0)


def test_el_drawdown_se_recibe_en_positivo():
    """Se reporta como magnitud de perdida, no como numero negativo.

    Motivo: se compara contra umbrales (`max_drawdown > 20`) y contra el
    `DailyGuard`, que comparan con `>`. Un -20 no dispararia un `> 20` y el
    freno no se activaria nunca.
    """
    precios = [100.0, 80.0, 100.0]
    assert PerformanceMetrics.max_drawdown(precios) > 0


def test_caida_y_recuperacion_parcial():
    """Caso que aparece en una curva real: baja, sube, no vuelve a maximo."""
    precios = [100.0, 70.0, 85.0, 90.0, 60.0, 95.0]
    # El peor tramo es 100 -> 70 (30%) y 90 -> 60 (33,3% desde su maximo).
    dd = PerformanceMetrics.max_drawdown(precios)
    esperado = abs(min(0.0, (60.0 - 100.0) / 100.0 * 100))
    assert dd == pytest.approx(esperado, abs=1e-6)
    assert dd > 0


def test_serie_vacia_o_de_un_punto():
    """No debe reventar, y no debe inventar una perdida."""
    assert PerformanceMetrics.max_drawdown([]) == 0.0
    assert PerformanceMetrics.max_drawdown([100.0]) == 0.0


# ---------------------------------------------------------------------------
# 2. sharpe_ratio
# ---------------------------------------------------------------------------

def test_el_riesgo_sin_riesgo_tiene_la_misma_unidad_que_la_media():
    """El término de riesgo libre tiene que RESTAR de verdad, y restar bien.

    Serie construida para que el signo DISCRIMINE el bug, no solo para que
    "parezca rara". Media por periodo de +0,0000397, que anualizada son
    +0,010: por debajo del riesgo sin riesgo anual de 0,02.

        con el término correcto:  (0,010 - 0,02) / sigma  -> NEGATIVO
        con el término ausente:    0,010 / sigma          -> POSITIVO

    La primera version de este test usaba `rng.normal(0, 0,01)` y fallaba
    para distinguir: la media salia negativa sola (-0,0013) y el Sharpe era
    negativo con y sin el bug. Un test que pasa con el defecto puesto no
    protege del defecto: hay que elegir el caso donde el signo FLIPEA.
    """
    n = 250
    media_anual_objetivo = 0.010
    media_periodo = media_anual_objetivo / 252.0
    # Alternancia +-: mantiene el sigma acotado y hace la serie determinista.
    returns = np.array([media_periodo * (1 if i % 2 == 0 else -1)
                        for i in range(n)]) + media_periodo
    media_anual_real = returns.mean() * 252
    assert media_anual_real < 0.02, (
        "la serie tiene que tener media anualizada por debajo del riesgo sin "
        f"riesgo, o el test no discrimina (real: {media_anual_real})")
    s = PerformanceMetrics.sharpe_ratio(returns)
    assert s < 0, (
        f"gana {media_anual_real:.4f} al ano contra un riesgo sin riesgo del "
        f"2% anual: el Sharpe tiene que ser NEGATIVO, y sale {s:.4f}. Con "
        "0,0 el termino desaparece")


def test_una_serie_plana_no_da_sharpe_infinito():
    """Desviación cero: 0, no una división por cero."""
    returns = np.zeros(50)
    assert PerformanceMetrics.sharpe_ratio(returns) == 0.0


def test_mas_volatilidad_mismo_rendimiento_es_peor_sharpe():
    """El Sharpe tiene que PENALIZAR la volatilidad.

    Control de comportamiento: dos series con la misma media y distinto
    ruido. Si el motor no penaliza, el Sharpe no sirve para rankear.
    """
    rng = np.random.default_rng(11)
    media = 0.001
    tranquilo = rng.normal(media, 0.002, size=500)
    ruidoso = rng.normal(media, 0.05, size=500)
    s_tranquilo = PerformanceMetrics.sharpe_ratio(tranquilo)
    s_ruidoso = PerformanceMetrics.sharpe_ratio(ruidoso)
    assert s_tranquilo > s_ruidoso, (
        f"la serie tranquila ({s_tranquilo:.3f}) tiene que puntuar mas que "
        f"la ruidosa ({s_ruidoso:.3f})")


# ---------------------------------------------------------------------------
# 3. Lo que de verdad paso en la medicion
# ---------------------------------------------------------------------------

def test_una_estrategia_perdedora_no_puede_salir_con_drawdown_cero():
    """La condicion que hizo visible el bug: perder dinero, no tener dd.

    Antes del arreglo, un backtest con 20 operaciones perdedoras y -5,92% de
    retorno devolvia `max_drawdown = 0.0`. Este test no necesita la
    estrategia: basta la serie de equity que produce.
    """
    equity = [100_000.0]
    for pnl in (-198.72, -217.59, -815.81, -240.0, -310.0, -120.0):
        equity.append(equity[-1] + pnl)
    equity = list(reversed(equity))  # la serie va de mal a peor
    equity[-1] = 94_079.22            # cierre real medido
    dd = PerformanceMetrics.max_drawdown(equity)
    assert dd > 5.0, (
        f"la equity cae de 100.000 a 94.079: el drawdown es de ~6% y el "
        f"motor devolvio {dd}")


# ---------------------------------------------------------------------------
# 4. La anualizacion depende de la temporalidad
# ---------------------------------------------------------------------------

def test_las_temporalidades_tienen_una_anualizacion_distinta():
    """Un año tiene 35.040 velas de 15m, no 252.

    MEDIDO el 2026-10-01: el numero de periodos al año estaba FIJO en 252
    sin importar la temporalidad. Un backtest de 15m se annualizaba como si
    cada vela fuera un dia de mercado, o sea 139 veces de error en el
    numerador de la media y 11,8 en el de la desviacion.
    """
    ppa = PerformanceMetrics.periodos_por_anio
    assert ppa("15m") == 35_040
    assert ppa("1h") == 8_760
    assert ppa("1d") == 365
    assert ppa("5m") == 105_120
    # 365,25 dias al año * 96 velas de 15m al dia.
    assert ppa("15m") == pytest.approx(365.25 * 24 * 4, rel=0.001)


def test_temporalidad_desconocida_cae_a_diaria_y_no_alla():
    """Si no se sabe la temporalidad, se DECLARA la diaria. No se inventa."""
    assert PerformanceMetrics.periodos_por_anio(None) == 365
    assert PerformanceMetrics.periodos_por_anio("no-existe") == 365
    assert PerformanceMetrics.periodos_por_anio("") == 365


def test_la_misma_serie_da_un_sharpe_distinto_segun_la_temporalidad():
    """El caso que hace visible el bug: la MISMA serie, dos anualizaciones.

    Con el 252 fijo, una serie de 15m y la misma serie tratada como diaria
    darian el mismo numero. Tiene que depender de la temporalidad.
    """
    rng = np.random.default_rng(3)
    returns = rng.normal(0.0002, 0.002, size=400)
    s_15m = PerformanceMetrics.sharpe_ratio(returns, periods_per_year=35_040)
    s_diario = PerformanceMetrics.sharpe_ratio(returns, periods_per_year=365)
    assert s_15m != s_diario, (
        "el Sharpe no puede ser el mismo para 15m y para diario: eso es "
        "exactamente lo que pasaba con el 252 fijo")
    # Con la misma media y sigma, el Sharpe crece con sqrt(P).
    assert s_15m > s_diario, "mas velas al año, mas periodos que promediar"


def test_el_riesgo_sin_riesgo_se_escala_al_periodo():
    """El termino tiene que restar en la MISMA unidad que la media.

    Con media por periodo positiva pero menor que el riesgo sin riesgo
    repartido, el Sharpe tiene que salir NEGATIVO. Si se restara el 2%
    anual entero a una media de 15m, saldria absurdamente negativo; si no se
    restara nada, positivo.
    """
    media_anual = 0.05            # la estrategia gana 5% al año
    ppa = 35_040
    media_periodo = media_anual / ppa
    # Serie con media EXACTAMENTE `media_periodo`: una componente constante
    # mas un ruido de suma cero. La primera version alternaba +x/-x, que tiene
    # media CERO, y por eso el Sharpe salia negativo y el test fallaba por su
    # cuenta y no por la del motor.
    ruido = np.array([0.001 * (1 if i % 2 == 0 else -1) for i in range(2000)])
    returns = media_periodo + ruido
    assert returns.mean() == pytest.approx(media_periodo, rel=1e-9)
    s = PerformanceMetrics.sharpe_ratio(returns, periods_per_year=ppa)
    # Gana 5% contra 2% sin riesgo: tiene que ser positivo pero no enorme.
    assert s > 0, f"gana {media_anual:.0%} contra 2% sin riesgo: positivo. Sale {s}"
    # Y no puede ser desproporcionado: con P=35040, sqrt(P)=187, asi que un
    # Sharpe "razonable" esta en el orden de unidades a decenas. Un 1e5
    # significaria que el riesgo sin riesgo se esta restando sin escalar.
    assert abs(s) < 1_000, f"Sharpe desproporcionado ({s}): el riesgo sin riesgo no se escalo"


def test_run_backtest_acepta_la_temporalidad():
    """El parametro tiene que existir y llegar a las metricas."""
    import inspect
    sig = inspect.signature(__import__("backtesting").Backtester.run_backtest)
    assert "timeframe" in sig.parameters, (
        "run_backtest no acepta temporalidad: entonces el Sharpe se "
        "anualiza siempre como diario")


def test_run_backtest_usa_la_temporalidad_que_le_pasan():
    """TEST DE EXTREMO A EXTREMO del 252 fijo.

    Los tests anteriores llamaban a `sharpe_ratio` directamente, asi que
    esquivaban `run_backtest`, que es donde estaba el `_ppa = 252`. Al
    reintroducir ese 252 la suite SEGUIA PASANDO: 14 de 14. Este test pasa
    por `run_backtest`, que es el camino real, y por eso lo caza.
    """
    from backtesting import Backtester

    precios = 100.0 * np.cumprod(1 + np.concatenate([
        np.full(200, 0.0005), np.full(200, -0.0005)]))

    def estrategia(_data):
        return ([{'symbol': 'X', 'side': 'buy', 'quantity': 1}]
                + [{'symbol': 'X', 'side': 'hold', 'quantity': 0}] * (len(precios) - 2)
                + [{'symbol': 'X', 'side': 'sell', 'quantity': 1}])

    bt = Backtester(initial_capital=10_000.0)
    r_15m = bt.run_backtest(estrategia, {'X': precios}, timeframe="15m")
    r_1d = bt.run_backtest(estrategia, {'X': precios}, timeframe="1d")
    assert r_15m.sharpe_ratio != r_1d.sharpe_ratio, (
        f"la MISMA serie da el mismo Sharpe a 15m y a diario "
        f"({r_15m.sharpe_ratio:.4f}): la temporalidad no llega a las metricas")
    assert r_15m.sharpe_ratio > r_1d.sharpe_ratio, (
        "con la misma media y sigma, mas periodos al año da un Sharpe mayor")

