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
                        for i in range(n)])
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
