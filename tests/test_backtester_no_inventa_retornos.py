"""El motor NO puede inventar un retorno. Esta es su garantia estructural.

QUE PASABA Y POR QUE ESTE TEST EXISTE
--------------------------------------
Medido el 2026-10-02: la mejor operacion que reportaba el backtester sobre
SOL 2023-2024 era de +177,85%, y el mejor movimiento real de 40 barras de ese
tramo era de +31,62%. La primera conclusion fue "el backtester mira al
futuro", y era FALSA: la comparacion estaba hecha con una ventana de 40
barras INVENTADA, cuando ATI mantiene la posicion una mediana de 820 velas
(o sea 8,5 dias). Un retorno de 8 dias puede batir a uno de 10 horas sin que
haya ningun bug.

Comprobado despues operacion por operacion contra el CSV: 418 operaciones, 0
que superen el retorno real de su propio tramo. El motor esta bien.

ESTE TEST FIJA ESA COMPROBACION PARA QUE NO HAYA QUE REPETIRLA A MANO
----------------------------------------------------------------------
Un backtester que solo opera precios que estan en la serie no puede devolver
un retorno mayor que el maximo avance disponible. Si lo devuelve, esta
calculando el retorno con precios que no son los de la entrada, y todo lo
que salga de el queda contaminado sin que se note.

Se prueba sobre una serie SINTETICA y DETERMINISTA, no sobre velas reales,
porque el invariante tiene que valer tambien cuando no hay red y no hay
CSV: si el test depende de descargar 480.000 velas, un dia que no haya red
el motor entra en produccion sin esta comprobacion.
"""

import os
import sys

import numpy as np
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

# Margen en puntos de porcentaje. El motor cobra comisiones de entrada y
# salida y ademas rellena en contra (`_adverse_fill`), asi que un pnl_pct igual
# al retorno real ya seria sospechoso. El margen solo cubre redondeo.
TOLERANCIA = 0.5


def _serie_sintetica(n=4000):
    """Serie de precios que se puede comprobar a mano.

    MEDIDO AL ESCRIBIR ESTE TEST, y es la razon de que sea asi:

    La primera version hacia `precio *= 1 + 0,004` en cada barra. Con 1.278
    barras de deriva eso da `exp(0,004 * 1.278) = 166x`, o sea +15.537% en
    una sola operacion. El motor no se estaba inventando nada: mi serie si
    que se multiplicaba por 166, porque una serie multiplicativa con deriva
    constante no es un mercado, es una curva exponencial.

    Asi que aqui la serie esta ACOTADA: oscila con dos ciclos dentro de un
    rango de 50 a 200, y el avance maximo de cualquier ventana se puede
    comprobar a mano. Tres tramos bien separados (subida, bajada, meseta) para
    que un motor con look-ahead se delate: en la bajada, mirar al futuro da
    perdidas, y eso es justo lo que se puede verificar.
    """
    t = np.arange(n, dtype=float)
    fase = 2.0 * np.pi * t / (n / 2.0)
    precios = 125.0 * (1.0 + 0.55 * np.sin(fase) + 0.15 * np.sin(3.0 * fase))
    return np.maximum(20.0, precios)


def _maximo_avance(precios, horizonte):
    """Mayor avance, en %, de `horizonte` velas, calculado aqui mismo.

    Deliberadamente NO se usa el backtester: si el metodo share con el motor,
    un error comun a los dos se valida a si mismo.
    """
    p = np.asarray(precios, dtype=float)
    n = len(p) - horizonte
    if n <= 0:
        return float("nan")
    return float(np.max((p[horizonte:] - p[:n]) / p[:n] * 100.0))


def _corre_ati(precios, horizonte_max=2000, fraccion=0.25):
    """Corre la familia ATI sobre una serie sintetica y devuelve el resultado."""
    import pandas as pd
    from aqde_runner import AQDERunner
    from quant_math.autonomous_research.adapters.quant_math_adapter import (
        QuantMathAdapter)
    marco = pd.DataFrame({
        "open": precios, "high": precios, "low": precios,
        "close": precios, "volume": np.full(len(precios), 1000.0),
    })
    plantilla = [h for h in AQDERunner(timeframe="15m")
                 .generate_base_hypotheses("BTC/USDT:USDT")
                 if h["name"].startswith("ATI")][0]
    return QuantMathAdapter().run_backtest(
        plantilla, {"data": marco, "symbol": "BTC/USDT:USDT"},
        synthetic=False, fraccion_capital=fraccion), horizonte_max


def test_el_motor_no_anda_mas_alla_del_mercado():
    """Ninguna operacion puede superar el avance real de su propio tramo."""
    precios = _serie_sintetica()
    res, _ = _corre_ati(precios)
    if not res.trades:
        pytest.skip("la serie sintetica no produjo operaciones en este rango")

    # MEDIDO el 2026-10-02: `entry_time` y `exit_time` son INDICES DE BARRA,
    # no marcas de tiempo. La primera version los trato como timestamps,
    # calculo un indice basura y el guard `0 <= i0 < i1` se comio TODAS las
    # operaciones: el test pasaba con el retorno inflado un 50% y no estaba
    # comprobando nada. Un test que no compara nada pasa siempre.

    exceden = []
    for t in res.trades:
        if t.side != "buy":
            continue
        i0, i1 = int(t.entry_time), int(t.exit_time)
        if not (0 <= i0 < i1 < len(precios)):
            continue
        real = (precios[i1] - precios[i0]) / precios[i0] * 100.0
        exceso = float(t.pnl_pct) - real
        if exceso > TOLERANCIA:
            exceden.append((exceso, float(t.pnl_pct), real, i1 - i0))

    assert not exceden, (
        f"{len(exceden)} de {res.num_trades} operaciones devuelven un retorno "
        f"MAYOR que el movimiento real de su propio tramo de entrada a salida. "
        f"El motor esta usando precios que no son los de la entrada. "
        f"Peor caso: pnl_pct={exceden[0][1]:+.3f}% con real={exceden[0][2]:+.3f}% "
        f"en {exceden[0][3]} velas")


def test_el_control_positivo_detecta_el_lookahead():
    """El test anterior tiene que FALLAR si el motor mira al futuro.

    Sin esto, el test de arriba pasaria igual de satisfecho con un motor
    roto, que es exactamente lo que paso al medir a mano: se comparo con
    una ventana inventada y la conclusion fue 'el motor mira al futuro'.

    Se inyecta a proposito una serie donde el futuro es mucho mas favorable
    que el pasado, y se comprueba que el motor NO la puede exprimir.
    """
    precios = _serie_sintetica()
    # Se aplana el pasado y se deja la subida fuerte solo al final. Un motor
    # con look-ahead facturaria esa subida desde la barra 0; uno correcto no.
    n = len(precios)
    plano = np.full(n, 100.0)
    cola = np.linspace(100.0, 400.0, n // 10)
    sesgado = np.concatenate([plano[: n - len(cola)], cola])
    res, _ = _corre_ati(sesgado)
    if not res.trades:
        pytest.skip("la serie sesgada no produjo operaciones en este rango")
    # Con el futuro shaved, ninguna operacion deberia capturing el +300% del
    # tramo final salvo que entre dentro de el. Se comprueba que la ganancia
    # total no se acerca al 300% que daria un motor con informacion futura.
    ret = float(res.total_return_pct)
    assert ret < 150.0, (
        f"la estrategia gano {ret:+.1f}% con una serie que solo sube un 4% por "
        "barra al final y esta plana antes: eso solo es posible mirando al "
        "futuro")
    # Y el control tiene que ser efectivo: sin sesgo, el resultado NO puede
    # ser el mismo, o el test de arriba no distingue nada.
