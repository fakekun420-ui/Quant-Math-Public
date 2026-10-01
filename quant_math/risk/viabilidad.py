"""Si una combinacion (simbolo, apalancamiento, temporalidad) puede ganar.

POR QUE EXISTE ESTE MODULO
-------------------------
Un backtest devuelve un numero de expectativa, y ese numero parece una
propiedad de la estrategia. No lo es: por debajo de certain valores es una
propiedad de la ARITMETICA del mercado, y no de lo que haga el sistema. Un
sistema puede tener la estrategia mas elaborate del mundo y perder dinero
igualmente si el coste de ida y vuelta es mayor que el movimiento que
persigue.

Hay DOS condiciones, y las dos tienen que cumplirse:

1. TECHO POSITIVO. A un horizonte h, el factor de captura necesario es
   `coste_ida_y_vuelta / movimiento_medio`. Si es >= 1.00, la estrategia
   tendria que capturar MAS del 100% del movimiento para solo cubrir el
   coste: imposible, y el techo de expectativa es negativo antes de
   escribir una sola linea de logica.

2. STOP COLOCABLE. El stop tiene que estar mas lejos que el ruido de la
   vela (si no, lo barre el azar, no la senal) y mas cerca que la
   liquidacion (si no, el exchange lo rechaza o la posicion se liquida
   antes). Si no existe ningun stop que cumpla las dos, la combinacion no
   existe operativamente, por muy buena que sea la estrategia.

Se mide con el p90 del rango de la vela, no con la mediana: el stop tiene
que sobrevivir al 90% de las velas, porque un 10% de barridosBESTMargen
convierten cada operacion en una moneda deFiche y el coste se va en
comisiones de salida.

MEDIDO el 2026-10-01 con velas reales de mainnet (1000 por simbolo y
temporalidad), contra MMR medido por simbolo (`mmr_table`). Resultado que
motivo el modulo:

    TAKER (coste 0,1268%)          MAKER (coste 0,0268%)
      25x  4/4 simbolos viables     25x  4/4 simbolos viables
      50x  4/4 simbolos viables     50x  4/4 simbolos viables
     100x  1/4 simbolos viables    100x  2/4 simbolos viables
     125x  0/4 simbolos viables    125x  1/4 simbolos viables

A 100x, XRP y SOL NO tienen ninguna temporalidad viable: el 90% de sus
velas es mas ancho que su distancia de liquidacion. No es que la estrategia
sea mala; es que el stop no tiene sitio donde ponerlo.

POR QUE NO SE USA PARA RECOMENDAR PARAMETROS
-------------------------------------------
Este modulo no dice "usa 50x". Dice "a 100x, XRP no tiene combinacion
viable". Elegir apalancamiento y temporalidad es del operador. Lo que hace
este modulo es que el sistema NO ACEPTE una combinacion aritmeticamente
imposible sin decirlo, en vez de operar meses para descubrirlo.

CACHE EN DISCO
--------------
Las estadisticas de mercado cambian despacio y descargar 1000 velas por
simbolo y temporalidad en cada ciclo es caro. Se cachean por
`(simbolo, temporalidad)` con una caducidad de `CADUCIDAD_HORAS`. Si no se
puede medir, NO se inventa el numero: se devuelve `medido=False` y quien
llame decide que hacer, porque un modulo que dice "no lo se" es preferible
a uno que devuelve un valor inventado que parece una medicion.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

#: Cuantas velas se descargan por simbolo y temporalidad.
VELAS_POR_MEDIDA = 1000

#: Caducidad de la cache de mercado, en horas.
CADUCIDAD_HORAS = 24.0

#: Percentil del rango de vela que el stop tiene que superar. 90 y no la
#: mediana porque el stop sobrevive a la vela tipica, no a la tipica de
#: entre las mas anchas.
PERCENTIL_RANGO = 90.0

#: Por debajo de este factor de captura el techo es positivo. A 1.00
#: exacto el coste iguala al movimiento y la expectativa es 0.
FACTOR_MAXIMO = 1.0

_CACHE_DIR = os.environ.get(
    "QUANTMATH_VIABILIDAD_CACHE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "runtime", "viabilidad.json"),
)


def _norm_tf(tf: str) -> str:
    """ccxt usa '5m', pero la config puede traer '5min' o '5MIN'."""
    t = str(tf).strip().lower()
    return {"5min": "5m", "15min": "15m", "1h": "1h", "60m": "1h",
            "1min": "1m", "3min": "3m", "4h": "4h"}.get(t, t)


def _split_symbol(simbolo: str) -> Tuple[str, str]:
    """'BTC/USDT:USDT' -> ('BTCUSDT', 'USDT')."""
    s = str(simbolo).strip().split(":", 1)[0]
    if "/" in s:
        base, quote = s.split("/", 1)
        return f"{base}{quote}".upper(), quote.upper()
    return s.upper(), "USDT"


def _cache_path() -> str:
    return _CACHE_DIR


def _leer_cache() -> Dict[str, Any]:
    try:
        with open(_cache_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _escribir_cache(cache: Dict[str, Any]) -> None:
    """Escritura atomica (`.tmp` + rename), que es lo que pide el entorno."""
    ruta = _cache_path()
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        tmp = ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, ruta)
    except OSError as exc:
        # Una cache que no se puede escribir NO puede tumbar el sistema:
        # lo unico que se pierde es la persistencia, no la decision.
        logger.warning("[viabilidad] no se pudo escribir la cache: %s", exc)


def medir_mercado(simbolo: str, temporalidad: str,
                  velas: int = VELAS_POR_MEDIDA) -> Optional[Dict[str, float]]:
    """Descarga velas reales y devuelve movimiento medio y p90 del rango.

    Devuelve None si no se pudo medir. No devuelve un valor por defecto:
    inventar el numero de un mercado que no se pudo leer es exactamente el
    fallo que este modulo existe para evitar.
    """
    sym, _quote = _split_symbol(simbolo)
    ccxt_sym = f"{sym[:-4]}/USDT:USDT" if sym.endswith("USDT") else simbolo
    tf = _norm_tf(temporalidad)
    try:
        import numpy as np
        from data_acquisition.data_sources.exchanges import ExchangeAPI
    except Exception as exc:                      # pragma: no cover
        logger.warning("[viabilidad] no se pudo importar el cliente: %s", exc)
        return None
    try:
        # MEDIDO el 2026-10-01: `ExchangeAPI("bybit")` sin argumentos crea el
        # cliente de datos con `sandbox=True` (lo decide `data_sandbox()`, que
        # mira el entorno, no el argumento `sandbox`). Sus velas de 5m de BTC
        # tienen un p90 de rango del 1,22% frente al 0,29% de mainnet, y el
        # cierre se va hasta un 0,60%: medir sobre testnet da una viabilidad
        # que no es la real. Por eso el venue se pasa EXPLICITO.
        #
        # Ademas se verifica que el cliente no quedo en testnet. Es la misma
        # trampa que ya mordio antes en otro sitio (el feed publico se
        # llevaba las claves y las velas): un feed correcto no se supone, se
        # comprueba.
        api = ExchangeAPI("bybit", data_venue="mainnet")
        cliente = api.data_client
        if bool(getattr(cliente, "sandbox", False)):
            logger.warning("[viabilidad] el cliente de datos quedo en SANDBOX: "
                           "las velas no son de mainnet y la medicion se "
                           "descarta")
            return None
        filas = cliente.fetch_ohlcv(ccxt_sym, tf, limit=velas)
    except Exception as exc:
        logger.warning("[viabilidad] %s %s no se pudo medir: %s",
                       simbolo, tf, exc)
        return None
    if not filas or len(filas) < 50:
        logger.warning("[viabilidad] %s %s: solo %s velas, no se puede medir",
                       simbolo, tf, len(filas or []))
        return None
    try:
        cierre = np.array([float(r[4]) for r in filas], dtype=float)
        maximo = np.array([float(r[2]) for r in filas], dtype=float)
        minimo = np.array([float(r[3]) for r in filas], dtype=float)
        if not np.all(cierre > 0):
            return None
        movimiento = np.abs(np.diff(cierre) / cierre[:-1]) * 100.0
        rango = (maximo - minimo) / cierre * 100.0
        if movimiento.size == 0 or float(movimiento.mean()) <= 0:
            return None
        return {
            "movimiento_medio_pct": float(movimiento.mean()),
            "rango_p90_pct": float(np.percentile(rango, PERCENTIL_RANGO)),
            "velas": int(len(filas)),
        }
    except Exception as exc:                      # pragma: no cover
        logger.warning("[viabilidad] %s %s: calculo fallo: %s",
                       simbolo, tf, exc)
        return None


def obtener_mercado(simbolo: str, temporalidad: str,
                    refrescar: bool = False) -> Optional[Dict[str, Any]]:
    """Medicion del mercado, con cache en disco de 24 h."""
    sym, _ = _split_symbol(simbolo)
    clave = f"{sym}@{_norm_tf(temporalidad)}"
    cache = _leer_cache()
    entrada = cache.get(clave)
    ahora = time.time()
    if (not refrescar and isinstance(entrada, dict)
            and ahora - float(entrada.get("ts", 0)) < CADUCIDAD_HORAS * 3600):
        datos = dict(entrada.get("datos") or {})
        datos["origen"] = "cache"
        return datos
    datos = medir_mercado(simbolo, temporalidad)
    if datos is None:
        return None
    cache[clave] = {"ts": ahora, "datos": datos}
    _escribir_cache(cache)
    salida = dict(datos)
    salida["origen"] = "medido"
    return salida


def distancia_liquidacion_pct(simbolo: str, apalancamiento: int) -> Optional[float]:
    """Distancia a la liquidacion en % de precio, con MMR real del simbolo.

    Con nocional N y margen M = N/L, la posicion se liquida cuando la
    perdida del nocional llega al margen menos el mantenimiento:

        M - N*x <= mmr*N   =>   x >= 1/L - mmr

    El MMR sale de `mmr_table`, que lo lee de la tabla publica de Bybit o,
    si el simbolo no esta, del valor medido en su posicion real.
    """
    if apalancamiento < 1:
        return None
    try:
        from quant_math.risk.mmr_table import mmr_for_symbol
        mmr, _origen = mmr_for_symbol(simbolo, apalancamiento)
    except Exception as exc:                      # pragma: no cover
        logger.warning("[viabilidad] no se pudo leer el MMR: %s", exc)
        return None
    return (1.0 / float(apalancamiento) - float(mmr)) * 100.0


def viabilidad(simbolo: str, apalancamiento: int, temporalidad: str,
               coste_pct: float) -> Dict[str, Any]:
    """Veredicto de viabilidad de UNA combinacion concreta.

    `coste_pct` es el coste de ida y vuelta EN PORCENTAJE DEL NOCIONAL, tal
    como lo miden las pruebas del proyecto: 0,1268 con taker y 0,0268 con
    maker, MEDIDOS, no tomados de la web.

    El dict devuelto lleva SIEMPRE `viable` y `motivo`. Cuando no se pudo
    medir, `viable` es None y el motivo lo dice: se prefiero no saber a
    saber un numero falso.
    """
    veredicto: Dict[str, Any] = {
        "simbolo": simbolo,
        "apalancamiento": int(apalancamiento),
        "temporalidad": _norm_tf(temporalidad),
        "coste_pct": float(coste_pct),
        "viable": None,
        "motivo": None,
    }

    mercado = obtener_mercado(simbolo, temporalidad)
    liq = distancia_liquidacion_pct(simbolo, apalancamiento)
    if mercado is None or liq is None or liq <= 0:
        veredicto["motivo"] = (
            "no_se_pudo_medir: sin velas o sin MMR para este simbolo")
        return veredicto

    movimiento = float(mercado["movimiento_medio_pct"])
    rango_p90 = float(mercado["rango_p90_pct"])
    factor = float(coste_pct) / movimiento
    veredicto.update({
        "movimiento_medio_pct": movimiento,
        "rango_p90_pct": rango_p90,
        "distancia_liquidacion_pct": liq,
        "factor_captura_requerido": factor,
        "mercado_origen": mercado.get("origen"),
    })

    if factor >= FACTOR_MAXIMO:
        veredicto["viable"] = False
        veredicto["motivo"] = (
            f"techo_negativo: el coste de ida y vuelta ({coste_pct:.4f}%) es "
            f"{factor:.2f}x el movimiento medio de la vela de "
            f"{_norm_tf(temporalidad)} ({movimiento:.4f}%). Habria que "
            f"capturar mas del 100% del movimiento para solo cubrir el "
            f"coste: ninguna estrategia gana aqui.")
        return veredicto

    if rango_p90 >= liq:
        veredicto["viable"] = False
        veredicto["motivo"] = (
            f"stop_imposible: el 90% de las velas de "
            f"{_norm_tf(temporalidad)} tiene un rango de {rango_p90:.4f}% y la "
            f"liquidacion a {apalancamiento}x esta a {liq:.4f}%. No hay stop "
            f"que no lo barra el ruido y que ademas se pueda colocar.")
        return veredicto

    veredicto["viable"] = True
    veredicto["motivo"] = (
        f"viable: techo positivo (factor {factor:.2f}x) y el stop cabe entre "
        f"el p90 de la vela ({rango_p90:.4f}%) y la liquidacion "
        f"({liq:.4f}%). Margen de stop disponible: "
        f"{liq - rango_p90:.4f}% de precio.")
    return veredicto


def conjunto_viable(apalancamiento: int, coste_pct: float,
                    simbolos, temporalidades=("5m", "15m", "1h"),
                    ) -> Dict[str, Any]:
    """Que simbolos y que temporalidades sobreviven a un apalancamiento dado.

    Devuelve ademas `sin_medir` a parte: si un simbolo no se pudo medir, no
    se cuenta como inviable sino como desconocido, porque son cosas distintas
    y confundirlas seria el mismo error que este modulo denuncia.
    """
    filas = []
    sin_medir = []
    for simbolo in simbolos:
        for tf in temporalidades:
            v = viabilidad(simbolo, apalancamiento, tf, coste_pct)
            if v["viable"] is None:
                sin_medir.append({"simbolo": simbolo,
                                  "temporalidad": v["temporalidad"]})
                continue
            filas.append(v)
    viables = [f for f in filas if f["viable"]]
    por_simbolo = {}
    # Se recorre la lista ORIGINAL de simbolos, no solo los que pasaron a
    # `filas`. Un simbolo cuyas temporalidades fallaron todas al medirse no
    # llega a `filas` y se perderia del recuento, con lo cual un simbolo
    # DESCONOCIDO se contaria como si no existiera. Eso es el mismo error
    # que este modulo denuncia (tratar lo no medido como lo medido), invertido.
    for simbolo in simbolos:
        tf_ok = sorted({f["temporalidad"] for f in viables
                        if f["simbolo"] == simbolo})
        if tf_ok:
            por_simbolo[simbolo] = tf_ok
        elif any(s["simbolo"] == simbolo for s in sin_medir):
            por_simbolo[simbolo] = ["NO MEDIDO"]
        else:
            por_simbolo[simbolo] = ["NINGUNA"]
    return {
        "apalancamiento": int(apalancamiento),
        "coste_pct": float(coste_pct),
        "simbolos_con_combinacion_viable": sum(
            1 for v in por_simbolo.values()
            if v not in (["NINGUNA"], ["NO MEDIDO"])),
        "simbolos_totales": len(por_simbolo),
        "por_simbolo": por_simbolo,
        "sin_medir": sin_medir,
        "detalle": filas,
    }