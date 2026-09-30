"""Tests del contrato generador <-> ejecutor.

POR QUE ESTE FICHERO EXISTE (medido 2026-09-28)
------------------------------------------------
Habia un test, `test_generates_executable_templates`, que afirmaba que el generador solo
emite tres estrategias: donchian_breakout, rsi_reversion y macd. Fallaba desde que el
generador crecio a SEIS (anadio energy_burst, range_pressure y scalp_burst) y nadie
actualizo el test. El codigo estaba bien; el test estaba caducado.

Ese test viejo era el UNICO que vigilaba este contrato, y era debilisimo por dos motivos:

  1. Tenia los nombres de estrategia ESCRITOS A MANO, asi que se rompe cada vez que el
     generador crece. Un contrato que se rompe solo no es un contrato.
  2. NO cubria la mitad del problema. La sustituccion silenciosa —una estrategia
     desconocida se backtestea como un `ema_crossover` desnudo, produciendo PnL FALSO que
     entra en el aprendizaje— no hacia fallar NADA. El test pasaba mientras el sistema
     moria por dentro.

Aqui se arregla las dos cosas: los nombres vienen del REGISTRO (una sola fuente de verdad,
la del propio ejecutor), y hay tests que comprueban la sustituccion silenciosa, que es el
defecto real.
"""
import inspect
import re

import pytest

from model_based_generator import generate_model_hypotheses

from quant_math.autonomous_research.adapters.quant_math_adapter import (
    IMPLEMENTED_STRATEGIES,
    QuantMathAdapter,
    UnknownStrategyError,
    is_implemented,
)


# ---------------------------------------------------------------- generador
def test_short_series_returns_empty():
    assert generate_model_hypotheses("BTC/USDT", [100.0] * 20) == []
    print("PASS serie corta: sin candidatos, sin crash")


# ---------------------------------------------------------------- el registro miente?
def test_registry_matches_dispatcher_chain():
    """El registro y la cadena `elif stype ==` del dispatcher no pueden separarse.

    Si alguien anade una estrategia a la cadena y no al registro (o al reves), esto falla.
    Es el test que hace que el registro sea una fuente de verdad y no una lista de deseos.
    """
    src = inspect.getsource(QuantMathAdapter)
    cadena = set(re.findall(r"elif stype == '([a-z_]+)'", src))
    cadena.add("ema_crossover")  # la rama explicita que sustituyo al else silencioso
    assert cadena == set(IMPLEMENTED_STRATEGIES), (
        f"registro y dispatcher no coinciden.\n"
        f"  en el registro sin implementacion: {sorted(set(IMPLEMENTED_STRATEGIES) - cadena)}\n"
        f"  implementada sin registrar      : {sorted(cadena - set(IMPLEMENTED_STRATEGIES))}"
    )
    print(f"PASS registro == dispatcher ({len(cadena)} estrategias)")


def test_hybrid_trend_reversion_is_not_implemented():
    """El defecto concreto que se arranco: esta estrategia se emitia y no se ejecutaba.

    `aqde_runner.py:400` la produce por mutacion cruzada. Caia en el `else` final y se
    backtesteaba como un ema_crossover DESNUDO: PnL falso que el sistema metia en su
    aprendizaje. Este test falla si alguien la vuelve a registrar sin implementarla.
    """
    assert not is_implemented("hybrid_trend_reversion"), (
        "hybrid_trend_reversion no puede estar en el registro: no existe en la cadena del "
        "dispatcher. Si se implemento, anadela a la cadena ANTES que al registro."
    )
    print("PASS hybrid_trend_reversion sigue sin estar implementada (y por tanto sin emitirse)")


# ---------------------------------------------------------------- el defecto real
def test_unknown_strategy_raises_instead_of_substituting_ema():
    """El fallo que este parche arregla: la SUSTITUCION SILENCIOSA.

    Antes, una estrategia desconocida caia en el `else` y devolvia las senales de un
    ema_crossover sin parametros. El backtest "tenia exito" con numeros que no eran de la
    estrategia pedida, y esos numeros entraban en el aprendizaje.

    Ahora tiene que FALLAR. Un backtest que no se hizo no puede parecerse a uno que si.
    """
    import pandas as pd

    closes = [100 + i * 0.1 for i in range(300)]
    df = pd.DataFrame({"close": closes, "high": closes, "low": closes, "open": closes,
                       "volume": [1.0] * 300})

    class _Hy:
        parameters = {"strategy_type": "estrategia_que_no_existe_xyz", "symbol": "BTC/USDT"}

    adapter = QuantMathAdapter()
    with pytest.raises(UnknownStrategyError):
        adapter.run_backtest(_Hy(), data={"data": df, "symbol": "BTC/USDT"})

    print("PASS estrategia desconocida -> error, no un ema_crossover disfrazado")


def test_known_strategy_still_runs():
    """Contracara del anterior: lo que SI esta implementado tiene que seguir funcionando."""
    import pandas as pd

    closes = [100 + i * 0.1 for i in range(300)]
    df = pd.DataFrame({"close": closes, "high": closes, "low": closes, "open": closes,
                       "volume": [1.0] * 300})

    class _Hy:
        parameters = {"strategy_type": "energy_burst", "symbol": "BTC/USDT",
                      "burst_window": 20, "burst_z": 1.5}

    adapter = QuantMathAdapter()
    result = adapter.run_backtest(_Hy(), data={"data": df, "symbol": "BTC/USDT"})
    assert result is not None
    print("PASS estrategia implementada -> se ejecuta")


def test_hardcoded_params_are_now_read_from_hypothesis():
    """energy_burst/range_pressure/scalp_burst tenian sus parametros fijos en el codigo.

    Eso hacia que la optimizacion del generador sobre ellas fuera codigo MUERTO en la ruta
    del orquestador. Aqui se comprueba que un parametro absurdo ENTRIA en el calculo: si
    alguien vuelve a hardcodearlo, la senal dejaria de depender de el y este test falla.
    """
    src = inspect.getsource(QuantMathAdapter)
    assert "w = 20\n" not in src, "energy_burst vuelve a tener w fijo"
    assert "zthr = 1.5" not in src, "energy_burst vuelve a tener zthr fijo"
    assert "hi, lo = 0.85, 0.15" not in src, "range_pressure vuelve a tener hi/lo fijos"
    assert "ema_f_w, ema_s_w = 8, 21" not in src, "scalp_burst vuelve a tener las EMAs fijas"
    assert "params.get('burst_window'" in src, "energy_burst no lee burst_window"
    assert "params.get('range_hi'" in src, "range_pressure no lee range_hi"
    assert "params.get('scalp_ema_fast'" in src, "scalp_burst no lee scalp_ema_fast"
    print("PASS los 3 leen sus parametros de la hipotesis")
