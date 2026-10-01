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

#: SUELO DE COSTE REAL como umbral del gate (correccion 2026-09-30).
#:
#: Ponerlo a 1 hace que el gate_compare `expectancy` CONTRA el coste real de
#: operar, en vez de contra cero. Es distinto de `min_expectancy` a proposito:
#: `min_expectancy` esta en % de CAPITAL por operacion, y este suelo esta en
#: % del NOCIONAL; por eso no se mezclan.
#:
#: Por que importa: con taker, operar cuesta 0,22% del nocional ida y vuelta.
#: Una hipotesis con expectancy de +0,10% es "positiva" para `min_expectancy`
#: y aun asi pierde dinero al pagar por entrar y salir. Medido el 2026-09-30:
#: el mejor edge bruto fuera de muestra fue +0,1052% (4h), que con taker queda
#: en -0,1148%. Sin este suelo, el gate llama "buena" a una estrategia que
#: pierde dinero.
#:
#: Por defecto 0 (desactivado) porque el gate esta en modo exploracion y
#: explores se con universo abierto. Para operar de verdad hay que ponerlo a
#: 1, o a un valor propio si el backtest conoce mejor el coste.
COST_FLOOR_GATE_ENV = "QUANTMATH_COST_FLOOR_GATE"
DEFAULT_COST_FLOOR_GATE: float = 0.0

#: Suelo opcional de `scientific_score`. OJO: hoy el umbral de 0.6 que
#: degrada a `failed` NO filtra nada, porque `failed` esta en
#: QUERYABLE_STATUSES y por tanto sigue operable. Este parametro es la
#: forma explicita de cerrar ese agujero si el operador lo quiere.
MIN_SCIENTIFIC_SCORE_ENV = "QUANTMATH_MIN_SCIENTIFIC_SCORE"
DEFAULT_MIN_SCIENTIFIC_SCORE: float = 0.0

# ---------------------------------------------------------------------------
# GATE CIENTIFICO (2026-10-01) — las tres fases, por fin, en el camino real
# ---------------------------------------------------------------------------
#
# Que es esto
# -----------
# El pipeline de validacion estaba entero y DESCONECTADO: `run_validation`,
# `run_monte_carlo` y `score_hypothesis` solo se llamaban desde
# `AQDERunner.run()`, que solo se ejecuta con `python aqde_runner.py`. El
# motor de produccion (`quant_math_bg.py` -> `orchestrator.run_forever`) nunca
# entra ahi. Consecuencia medida: la formula
# `scientific_score = 0,2*validacion + 0,5*backtest + 0,3*monte_carlo` NO se
# habia ejecutado jamas sobre una hipotesis real, y `orchestrator.
# _result_to_kb_record` se inventaba un 0,098 porque `hyp.scientific_score`
# valia 0,0.
#
# Con las tres fases conectadas, el registro de la KB lleva ya el veredicto.
# Este modulo es la POLITICA de como ese veredicto se convierte en operable,
# y vive aqui (no en el motor, no en el orquestador) para que las tres cosas
# que lo leen no puedan discrepar entre si.
#
# POR QUE el gate cientifico NO lo salta `learn_mode`
# ---------------------------------------------------
# `learn_mode` salta el gate de expectancy y el de `scientific_score`, y eso
# es coherente: es una decision de EXPLORAR con expectativa negativa. Pero
# aqui no se trata de tolerancia al riesgo, sino de una AFIRMACION sobre los
# datos: si no hay operaciones suficientes, no se ha medido nada, y ninguna
# hipotesis no medida puede afirmar que es operable. `learn_mode` esta ENCENDIDO
# por defecto en los dos lanzadores de produccion (`quant_math_bg.py:119` y
# `quant_math/cli/main.py:307`), asi que honrarlo como bypass dejaria este
# gate como un no-op en produccion. Decision: el gate cientifico SIEMPRE
# aplica.
#
# El umbral de operaciones
# ------------------------
# Sin un minimo, un CI95% sobre 7 operaciones sale con la misma autoridad
# que uno sobre 400. MEDIDO sobre las ejecuciones REALES del libro
# (runtime/state_classic-xrp/paper_executions.jsonl, 14 cierres) con bootstrap
# parametrico sobre los PnL reales:
#
#     n=  7   CI95 de la media/trade = [-0,1329, +0,4297]  ancho 0,5626
#     n= 30   CI95 de la media/trade = [+0,0875, +0,3509]  ancho 0,2635
#     n=188   CI95 de la media/trade = [+0,1292, +0,2416]  ancho 0,1124
#
# A n=7 el intervalo es 3,8 veces la propia estimacion y CONTIENE el cero: no
# dice nada. A n>=30 ya es 1,2 veces la estimacion y excluye el cero. 30 es
# tambien el punto en que el semiplano del IC al 95% deja de depender de la
# aproximacion (t_29 = 2,045 frente a t_3 = 3,182). Por debajo de 30 la fase
# NO CONCLUYE y la hipotesis se marca como tal: no se devuelve el numero.
MIN_TRADES_CONCLUSION_ENV = "QUANTMATH_MIN_TRADES_CONCLUSION"
DEFAULT_MIN_TRADES_CONCLUSION: int = 30

#: Alfa del test de significancia (una cola: interesa el PnL POR ENCIMA de 0,
#: no que sea distinto de 0). 0,05 es el habitual y no es un numero inventado
#: aqui: lo que cambia respecto a antes no es el alfa sino que antes NO habia
#: ningun test.
SIGNIFICANCE_ALPHA_ENV = "QUANTMATH_SIGNIFICANCE_ALPHA"
DEFAULT_SIGNIFICANCE_ALPHA: float = 0.05

#: Interruptor del gate cientifico. Apagado = el registro se sigue publicando
#: con su veredicto pero la decision engine no lo filtra (para poder comparar
#: antes/despues sin tocar el exchange).
REQUIRE_SCIENTIFIC_ENV = "QUANTMATH_REQUIRE_SCIENTIFIC_VALIDATION"
DEFAULT_REQUIRE_SCIENTIFIC: bool = True

#: Las filas de la KB publicadas ANTES de que existiera el pipeline no tienen
#: veredicto. Son la mayoria (medido el 2026-10-01: 674 de 766 filas de
#: runtime/hypotheses_classic-xrp.jsonl). Con esto APAGADO se les conserva la
#: semantica anterior en vez de borrar el universo de golpe; cada una recibe
#: veredicto en cuanto su firma se re-backtestea
#: (`QUANTMATH_SIG_REFRESH_CYCLES`, 5 por defecto), asi que la migracion es
#: gradual y sola. ENCENDIDO es el modo estricto: lo que no se ha medido no
#: opera.
STRICT_SCIENTIFIC_LEGACY_ENV = "QUANTMATH_STRICT_SCIENTIFIC_LEGACY"
DEFAULT_STRICT_SCIENTIFIC_LEGACY: bool = False

#: Nombres de los campos del veredicto. Declarados AQUI para que el
#: orquestador (que los escribe) y el motor (que los lee) no puedan separarse.
FIELD_SCIENTIFICALLY_VALIDATED = "scientifically_validated"
FIELD_SCIENTIFIC_REASONS = "scientific_reasons"
FIELD_PVALUE = "statistical_significance"
FIELD_PVALUE_ALPHA = "statistical_significance_alpha"
FIELD_MC_CONCLUSIVE = "monte_carlo_conclusive"
FIELD_MC_MEAN = "monte_carlo_mean"
FIELD_MC_LOWER = "monte_carlo_lower_bound"
FIELD_MC_UPPER = "monte_carlo_upper_bound"
FIELD_MIN_TRADES = "min_trades_conclusion"
FIELD_VALIDATION_SCORE = "validation_score"

#: COMISION REAL de Bybit (LEIDA el 2026-09-30 del endpoint publico de
#: mercados, campo `taker`/`maker` del mercado, NO una cifra de wiki):
#:
#:     ex.load_markets()['BTC/USDT:USDT']['taker'] = 0.0006   (0,06% por lado)
#:     ex.load_markets()['BTC/USDT:USDT']['maker'] = 0.0001   (0,01% por lado)
#:
#: MEDIDO ADEMAS en las ejecuciones, que es el dato que manda: el 2026-09-30
#: se abrieron y cerraron 4 posiciones reales en TESTNET y las 4 cobraron
#: exactamente 0,0550% por lado, no 0,06%:
#:
#:     fee 0,00272305 / (1,5003 x 3,3 = 4,95099) = 0,0550%
#:     fee 0,00272359 / (1,5006 x 3,3 = 4,95198) = 0,0550%
#:     fee 0,00272741 / (1,5027 x 3,3 = 4,95891) = 0,0550%
#:     fee 0,00272704 / (1,5025 x 3,3 = 4,95825) = 0,0550%
#:
#: O sea que lo que anuncia el mercado se pasa por 9,1%. Se deja 0,0006 a
#: proposito, por dos razones: es CONSERVADOR (cargar de mas no abre puertas
#: que deberian estar cerradas) y, sobre todo, es un dato de TESTNET. En
#: MAINNET no se ha medido ninguna ejecucion, y cambiar el numero por otro
#: de testnet seria explicar un coste de mainnet con una medida de testnet.
#: Cuando se mida en mainnet, se cambia aqui y se dice.
#:
#: Antes este modulo accountable SOLO del slippage y decia explicitamente que
#: la comision no se modelaba. Eso hacia que el gate creyera que operar
#: cuesta 0,10% cuando en realidad cuesta **0,22% con taker**: se
#: inflaba la ventaja un 2,2x. Y el edge medido es de 0,01-0,10% por
#: operacion, o sea que la diferencia decidia si habia negocio o no.
TAKER_FEE: float = 0.0006
MAKER_FEE: float = 0.0001

#: Slippage del motor de paper = LA MITAD DEL SPREAD REAL de Bybit.
#:
#: MEDIDO el 2026-09-30, 40 muestras por simbolo en el libro:
#:
#:     XRP/USDT:USDT  min 0,0067%  mediana 0,0100%  max 0,0200%
#:     BTC/USDT:USDT  min 0,0001%  mediana 0,0002%  max 0,0006%
#:     ETH/USDT:USDT  min 0,0004%  mediana 0,0006%  max 0,0019%
#:
#: DOS COSAS QUE ESTO DICE Y QUE NO DEBEN OLVIDARSE:
#:
#: 1) EL SPREAD VARIA MUCHO CON EL SIMBOLO: el de XRP es 50x mas ancho que
#:    el de BTC. Una sola constante para todos es incorrecta por
#: construccion. Aqui se deja la de XRP porque es el simbolo del plan, y
#: porque entre las tres es la MAS CARA: asi el modelo no es optimista
#:    para nadie.
#:
#: 2) 0,0034% es el MINIMO de XRP, no su mediana. Con la mediana real
#:    (0,0100%, o sea 0,0050% por lado) el coste a mercado de XRP es
#:    0,1300% y no el 0,1268% que declara este modulo. La diferencia es
#:    pequena, pero el numero de este comentario es el mejor caso, no el
#:    tipico.
#:
#: Antes valia 0,0005, que era un SUPUESTO de un barrido propio y salio
#: 15 veces mas caro que la realidad. Con el, el gate creia que operar
#: costaba 0,10% cuando entrar A MERCADO cuesta 0,127%: el motor era
#: optimista para quien opera a mercado, que es el fallo en la direccion
#: contraria a la que protege.
DEFAULT_SLIPPAGE_PCT: float = 0.000034

COST_MODEL_NOTE = (
    "round trip = 2 x (slippage + comision). Con taker: "
    "2 x (0,05% + 0,06%) = 0,22% del nocional. Con maker: "
    "2 x (0,05% + 0,01%) = 0,12%. Comisiones leidas del API de Bybit el "
    "2026-09-30; el slippage es el del motor de paper."
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


def resolve_scientific_policy(
        explicit_require: Optional[bool] = None,
        explicit_strict_legacy: Optional[bool] = None,
) -> Dict[str, Any]:
    """Politica del gate cientifico resuelta y DECLARADA.

    Devuelve el umbral de operaciones, el alfa, y los dos interruptores, para
    que quien llame no tenga que repetir las reglas ni inventar defaults.
    """
    if explicit_require is None:
        require, was_set = env_flag(REQUIRE_SCIENTIFIC_ENV)
        if not was_set:
            # `env_flag` devuelve False cuando la variable NO existe, y el
            # default declarado aqui es True. Sin este matiz el gate se
            # encontraria apagado en cualquier despliegue que no exporte la
            # variable, o sea el caso normal: un default silencioso.
            require = DEFAULT_REQUIRE_SCIENTIFIC
    else:
        require = bool(explicit_require)
    if explicit_strict_legacy is None:
        strict, was_set = env_flag(STRICT_SCIENTIFIC_LEGACY_ENV)
        if not was_set:
            strict = DEFAULT_STRICT_SCIENTIFIC_LEGACY
    else:
        strict = bool(explicit_strict_legacy)
    min_trades = int(env_float(MIN_TRADES_CONCLUSION_ENV,
                               DEFAULT_MIN_TRADES_CONCLUSION))
    if min_trades < 2:
        # Un t-test necesita al menos 2 observaciones para tener grados de
        # libertad; un umbral de 1 seria un umbral que no dice nada.
        logger.warning("[gate] %s=%s es <2; se usa 2",
                       MIN_TRADES_CONCLUSION_ENV, min_trades)
        min_trades = 2
    alpha = env_float(SIGNIFICANCE_ALPHA_ENV, DEFAULT_SIGNIFICANCE_ALPHA)
    if not 0.0 < alpha < 1.0:
        logger.warning("[gate] %s=%s no es un alfa; se usa %s",
                       SIGNIFICANCE_ALPHA_ENV, alpha, DEFAULT_SIGNIFICANCE_ALPHA)
        alpha = DEFAULT_SIGNIFICANCE_ALPHA
    return {
        "require": require,
        "strict_legacy": strict,
        "min_trades": min_trades,
        "alpha": alpha,
    }


def scientific_block_reason(record: Dict[str, Any],
                            strict_legacy: bool = False) -> Optional[str]:
    """Motivo por el que un registro NO es operable cientificamente, o None.

    UNA sola definicion de "operable" para las tres cosas que la consultan
    (`ranked_candidates`, `select_best_hypothesis` y el gate de `decide`): si
    cada una decidiera por su cuenta, el motor podria Promote una hipotesis
    que el panel no muestra o al reves, y eso ya ha pasado con otros filtros.

    Devuelve None cuando la hipotesis es operable a efectos cientificos.
    """
    if not isinstance(record, dict):
        return "registro no es un dict"
    if FIELD_SCIENTIFICALLY_VALIDATED not in record:
        # Fila anterior al pipeline: NO se ha medido, pero tampoco se afirma
        # que sea mala. Con `strict_legacy` se cierra el paso.
        return ("sin_pipeline" if strict_legacy else None)
    if record.get(FIELD_SCIENTIFICALLY_VALIDATED):
        return None
    reasons = record.get(FIELD_SCIENTIFIC_REASONS) or []
    if isinstance(reasons, (list, tuple)):
        detalle = "; ".join(str(r) for r in reasons)
    else:
        detalle = str(reasons)
    return detalle or "no_validada_sin_motivo"


def round_trip_cost_pct(slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
                        taker: bool = True) -> float:
    """Coste REAL de ida y vuelta en % del nocional.

    `2 x (slippage + comision)`. Antes solo contaba el slippage, o sea
    0,10%, y el gate creia que eso era todo lo que costaba operar. Con la
    comision real de Bybit el taker son 0,22%: el gate estaba inflando la
    ventaja un 2,2x. Como el edge medido anda en 0,01-0,10% por operacion,
    esa diferencia decide si hay negocio o no.

    Se expone como diagnostico, no como umbral (ver el docstring del
    modulo): lo que decide es `min_expectancy`, no esta cifra.
    """
    slip = abs(float(slippage_pct or 0.0))
    fee = TAKER_FEE if taker else MAKER_FEE
    return 2.0 * (slip + fee) * 100.0


def break_even_expectancy_pct(taker: bool = True) -> float:
    """El expectancy minimo por operacion para no perder dinero.

    Es el suelo REAL, con comision incluida. Si un hypothesis esta por
    debajo, da igual que su expectancy sea positivo: al pagar por operar
    se pierde. Con taker son 0,22% por operacion.
    """
    return round_trip_cost_pct(DEFAULT_SLIPPAGE_PCT, taker=taker)
