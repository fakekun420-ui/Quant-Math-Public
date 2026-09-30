"""
Politica del gate de decision (expectancy>0) y de sus umbrales.

Por que existe este modulo
---------------------------
El motor (`DecisionEngine`) tenia el default del gate en APAGADO, pero los
dos launchers lo encendian sin preguntar::

    quant_math_bg.py:119        os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")
    quant_math/cli/main.py:307  os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")

`setdefault` gana siempre que la variable no exista, y por la puerta real
(unico camino de produccion) nunca existia: el gate `expectancy > 0` NUNCA
estaba cerrado. Medido en el run real (F3, 2026-09-29): 5 de 5 operaciones
ejecutadas con expectancy NEGATIVA (-0.16431, -0.95096, -0.16439,
-0.16443, -0.95096).

Aqui la decision tiene UN solo sitio y deja rastro:

1. `resolve_learn_mode()` decide si la exploracion esta activa y de donde
   sale la decision (argumento explicito > variable de entorno > default).
2. El default es GATE CERRADO: solo opera `expectancy > min_expectancy`.
3. Abrir la exploracion es una ACCION EXPLICITA del operador y cada
   resolucion se anade a `<state_dir>/learn_mode_audit.jsonl`.
4. La auto-graduacion existente (PE in `DecisionEngine._maybe_graduate`)
   sigue siendo la via de cierre: aqui solo se registra.

Sobre el umbral: un umbral NO es un numero inventado. Por debajo del coste
de ejecucion el edge no existe, pero el coste depende del nocional
desplegado y ese solo lo conoce el backtest, no el gate. Ver
`COST_MODEL_NOTE` y el bloque de recalibracion del informe de la
correccion no3 (2026-09-29).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Variable de entorno del interruptor de exploracion. Unica via admitida
#: para abrir el gate desde fuera del proceso (ademas del argumento
#: explicito y de la config del orquestador).
LEARN_MODE_ENV = "QUANTMATH_LEARN_MODE"

#: Fichero de auditoria (append-only, una linea por resolucion).
GATE_AUDIT_FILENAME = "learn_mode_audit.jsonl"

#: Umbral MINIMO de expectancy, en la misma unidad que produce
#: `orchestrator._result_to_kb_record`: % de capital por trade
#: (`total_return_pct / n_trades`).
#: 0.0 = solo el signo, que es exactamente lo que hacia el codigo antes.
#: Se deja parametrizado porque el valor correcto depende de la
#: validacion OOS, que NO es de este departamento.
MIN_EXPECTANCY_ENV = "QUANTMATH_MIN_EXPECTANCY"
DEFAULT_MIN_EXPECTANCY: float = 0.0

#: Suelo opcional de `scientific_score`. OJO: hoy el umbral de 0.6 que
#: degrada a `failed` NO filtra nada, porque `failed` esta en
#: QUERYABLE_STATUSES y por tanto sigue operable. Este parametro es la
#: forma explicita de cerrar ese agujero si el operador lo quiere.
MIN_SCIENTIFIC_SCORE_ENV = "QUANTMATH_MIN_SCIENTIFIC_SCORE"
DEFAULT_MIN_SCIENTIFIC_SCORE: float = 0.0

#: Modelo de coste que usa el motor de paper (VERIFICADO en el codigo):
#: `DecisionEngine.slippage_pct` = 0.0005 por LADO (entrada y salida),
#: aplicado con `_slip()`. La comision del exchange NO se modela en el
#: motor de paper; el backtester si la usa (0.001 por lado).
#: 2 x 0.0005 = 0.001 = 0.10% del nocional por ida y vuelta.
COST_MODEL_NOTE = (
    "paper: 2 x slippage_pct = 0.10% del nocional por round trip "
    "(comision del exchange NO modelada en paper)"
)

_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")


def env_flag(name: str) -> Tuple[bool, bool]:
    """(valor, estaba_definida) leyendo una variable tipo flag.

    Solo '1'/'true'/'yes'/'on' activan. Un valor irreconocible (p.ej.
    'maybe') se trata como APAGADO y se avisa: un flag mal escrito nunca
    debe abrir el gate por sorpresa.
    """
    raw = os.environ.get(name)
    if raw is None:
        return False, False
    val = raw.strip().lower()
    if val in _TRUTHY:
        return True, True
    if val in _FALSY:
        return False, True
    logger.warning("[gate] %s=%r no es un booleano; se trata como APAGADO "
                   "(gate cerrado)", name, raw)
    return False, True


def env_float(name: str, default: float) -> float:
    """Lee un umbral del entorno; valor ilegible -> default + aviso."""
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("[gate] %s=%r ilegible; se usa el default %s",
                       name, raw, default)
        return float(default)


def audit_path(state_dir: str) -> str:
    return os.path.join(state_dir, GATE_AUDIT_FILENAME)


def append_gate_audit(state_dir: str, record: Dict[str, Any]) -> str:
    """Anade una linea al rastro del gate. NUNCA lanza.

    Devuelve la ruta escrita, o '' si no se pudo. Un fallo de escritura
    no puede tumbar el ciclo: se avisa y se sigue (el estado en memoria
    manda; el rastro es para poder afirmar despues en que modo se opero).
    """
    if not state_dir:
        return ""
    path = audit_path(state_dir)
    try:
        os.makedirs(state_dir, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False,
                                default=str) + "\n")
        return path
    except OSError as exc:
        logger.warning("[gate] no se pudo escribir el rastro %s: %s",
                       path, exc.__class__.__name__)
        return ""


def gate_audit_records(state_dir: str) -> List[Dict[str, Any]]:
    """Lee el rastro del gate. Devuelve [] si no hay o no se puede leer."""
    path = audit_path(state_dir)
    out: List[Dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def resolve_learn_mode(explicit: Optional[bool] = None,
                       state_dir: Optional[str] = None,
                       event: str = "startup",
                       ) -> Tuple[bool, str]:
    """Resuelve el estado de la exploracion. Devuelve (learn_mode, origen).

    Precedencia (de mas fuerte a mas debil):
      1. `explicit` (argumento de `DecisionEngine` / config del orquestador)
      2. variable de entorno `QUANTMATH_LEARN_MODE`
      3. default: GATE CERRADO

    Cada resolucion deja una linea en `<state_dir>/learn_mode_audit.jsonl`
    con el valor, el origen y el PID: sin eso, 'estaba en exploracion' no
    se puede ni afirmar ni desmentir despues.
    """
    env_value, env_set = env_flag(LEARN_MODE_ENV)
    if explicit is not None:
        learn = bool(explicit)
        source = "explicit"
    elif env_set:
        learn = env_value
        source = "env"
    else:
        learn = False
        source = "default"
    append_gate_audit(state_dir or "", {
        "ts": time.time(),
        "event": event,
        "learn_mode": learn,
        "source": source,
        "env_set": env_set,
        "env_value": os.environ.get(LEARN_MODE_ENV),
        "pid": os.getpid(),
    })
    return learn, source


def resolve_gate_thresholds(explicit_min_expectancy: Optional[float] = None,
                            explicit_min_score: Optional[float] = None,
                            ) -> Tuple[float, float]:
    """(min_expectancy, min_scientific_score) efectivos del gate.

    `DEFAULT_MIN_EXPECTANCY = 0.0` conserva exactamente la semantica
    anterior (`expectancy > 0`). Subirlo exige un numero justificado.
    """
    min_exp = (float(explicit_min_expectancy)
               if explicit_min_expectancy is not None
               else env_float(MIN_EXPECTANCY_ENV, DEFAULT_MIN_EXPECTANCY))
    min_score = (float(explicit_min_score)
                 if explicit_min_score is not None
                 else env_float(MIN_SCIENTIFIC_SCORE_ENV,
                                DEFAULT_MIN_SCIENTIFIC_SCORE))
    return min_exp, min_score


def round_trip_cost_pct(slippage_pct: float) -> float:
    """Coste de ida y vuelta en % del nocional segun el motor de paper.

    2 x slippage por lado. Es el suelo que el edge debe superar para que
    operar tenga sentido; se expone como diagnostico, no como umbral
    (ver el docstring del modulo).
    """
    return 2.0 * abs(float(slippage_pct or 0.0)) * 100.0
