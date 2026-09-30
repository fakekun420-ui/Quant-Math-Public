"""Vocabulario canonico de familias de estrategia — UNA sola fuente de verdad.

Correccion 4 (2026-09-29). El bucle de aprendizaje se cortaba aqui por un
motivo silencioso: el vocabulario estaba escrito TRES veces y las dos mitades
del bucle usaban copias distintas:

* consumidor (`hypothesis_prior.family_of`) canonicaba y minusculizaba;
* productor (`regime_learning.family_of`) devolvia la cadena CRAUDA si no
  encontraba la familia por subcadena;
* `decision_engine._family_of` (feedback por familia) hacia un cuarto mapeo.

Resultado: con un `strategy_type` en hoja (``vwap_reversion``) o en forma de
enum (``StrategyType.MEAN_REVERSION`` / ``MEAN_REVERSION``) el SIS emitia una
clave que el consumidor NUNCA buscaba — ``family_prior.get("mean_reversion")``
sobre ``{"vwap_reversion": ...}`` -> ``None`` -> ``w = 0.0`` —, o sea que el
aprendizaje no entraba en la generacion ni un punto (cable decorativo).

Aqui vive el vocabulario UNA vez. Si anades una familia o una hoja se anade
una sola vez y las tres piezas quedan sincronizadas por construccion: ninguna
puede desincronizarse porque no hay segunda copia que comparar.

El mapeo hoja -> familia NO se inventa: se ha extraido del registro de
plantillas que ya existia en el codigo — `aqde_runner.generate_base_hypotheses`
y `generate_adaptive_hypotheses` (cada plantilla declara su `StrategyType`) y
`model_based_generator` (las hojas energy_burst/range_pressure/scalp_burst son
`StrategyType.CUSTOM`).
"""

from __future__ import annotations

from typing import Any, Dict

#: Familias canonicas = los valores de `StrategyType` con los que se rankea.
FAMILIES = ("breakout", "mean_reversion", "momentum", "trend_following")

#: Indice estable por familia (feature_store.encode_row).
FAMILY_INDEX: Dict[str, int] = {f: i for i, f in enumerate(FAMILIES)}

#: Hoja (`parameters.strategy_type`) -> familia canonica.
#: Origen: registro de plantillas de aqde_runner y model_based_generator.
LEAF_FAMILY: Dict[str, str] = {
    # --- aqde_runner.generate_base_hypotheses (plantilla -> StrategyType)
    "ema_crossover": "trend_following",
    "dual_ema": "trend_following",
    "ati_trend": "trend_following",
    "rsi_reversion": "mean_reversion",
    "bb_reversion": "mean_reversion",
    "vwap_reversion": "mean_reversion",
    "macd": "momentum",
    "breakout": "breakout",
    "donchian_breakout": "breakout",
    # --- hojas implementadas sin plantilla fija (IMPLEMENTED_STRATEGIES).
    # Por nombre: es una reversion sobre el estocastico.
    "stochastic_reversion": "mean_reversion",
    # --- mutaciones/hibridos y model-gen: StrategyType.CUSTOM
    "hybrid_trend_reversion": "custom",
    "energy_burst": "custom",
    "range_pressure": "custom",
    "scalp_burst": "custom",
}


def _raw(strategy_type: Any) -> str:
    """Cadena normalizada SIN canonicar: minusculas y ultimo tramo.

    Acepta las tres formas que llegan de verdad:
      * Enum           -> `StrategyType.MEAN_REVERSION` -> `mean_reversion`
      * cadena de enum -> `StrategyType.MEAN_REVERSION` -> `mean_reversion`
      * hoja canonica  -> `vwap_reversion` / `momentum`
    Un mapping (fila del dataset o plantilla) se resuelve por su clave
    `strategy_type`, de modo que `family_of(fila)` y `family_of(tipo)` son la
    MISMA funcion: no hay dos firmas que puedan desincronizarse.
    """
    if isinstance(strategy_type, dict) or (
            hasattr(strategy_type, "get")
            and not isinstance(strategy_type, (str, bytes))):
        try:
            strategy_type = strategy_type.get("strategy_type", "")
        except Exception:
            pass
    st = getattr(strategy_type, "value", strategy_type)
    st = "" if st is None else str(st)
    return st.strip().split(".")[-1].strip().lower()


def family_of(strategy_type: Any) -> str:
    """strategy_type -> familia canonica (o la cadena si no pertenece a una).

    Unica implementacion: la usan el SIS (`regime_learning`), el prior del KB
    (`hypothesis_prior`), el feedback por familia (`decision_engine`) y el
    encoding de clustering (`feature_store`). `?` = sin familia, la misma
    convolucion de "no lo se" que `vol_bucket(None)`.
    """
    st = _raw(strategy_type)
    if not st:
        return "?"
    if st in FAMILIES:
        return st
    leaf = LEAF_FAMILY.get(st)
    if leaf:
        return leaf
    for fam in FAMILIES:   # conserva el subcadenaje previo (donchian_breakout)
        if fam in st:
            return fam
    return st


def family_index(strategy_type: Any) -> int:
    """Indice de la familia canonica para encoding; -1 si no es de las cuatro."""
    return FAMILY_INDEX.get(family_of(strategy_type), -1)
