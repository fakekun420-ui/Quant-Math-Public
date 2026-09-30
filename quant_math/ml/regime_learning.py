"""Aprendizaje NO supervisado sobre operaciones cerradas.

OperationLearningLoop:
  - Clustering (KMeans) del dataset de operaciones para descubrir
    estructura sin etiquetas humanas (SOLO con n >= MIN_ROWS; ver mas abajo).
  - Tabla (regimen de mercado x familia) con tasa de exito por grupo,
    construida post-hoc contra pnl_pct y ENCOGIDA hacia la media global
    (empirical-Bayes, misma constante SHRINK_K que hypothesis_prior).
  - rank_families(): familias priorizadas para el simbolo/regimen actual.
  - family_prior(): el mismo numero en la forma que consume
    `HypothesisPrior`, para que el aprendizaje entre en la generacion.
  - hostile_families(): regimen hostil a la familia activa (pausa advisory).
  - should_explore(): detector de rachas que dispararafagas de exploracion.

Dos umbrales, no uno (correccion 4, 2026-09-29)
-----------------------------------------------
Antes habia UN numero, `MIN_ROWS = 30`, y gobernaba TODO: sin el, ni la
tabla ni los clusters existian. Se separan dos cosas porque degradan de
forma distinta:

* `MIN_ROWS_ACTIVE` (default 10, `QUANTMATH_SIS_MIN_ROWS_ACTIVE`) activa
  la TABLA regimen x familia. Es una linea de diseno, no una medida: con
  10 cierres hay como mucho DOS celdas de `MIN_CELL` (5) llenas, y por
  debajo la tabla ni siquiera puede emitir un veredicto de familia.
* `MIN_ROWS` / `QUANTMATH_SIS_MIN_ROWS` (default 30) gobierna SOLO el
  KMeans; su ausencia degrada en silencio a "solo tablas agregadas", que
  ya era el comportamiento previo.

LA EVIDENCIA ANTERIOR ESTABA ROTA. El docstring citaba
`runtime/f3/d2/calibra.py` como "VERIFICADO" y ese script NO existe en
disco (2026-09-29, find por *calibra* -> vacio), asi que ni las medianas
de duracion ni la simulacion de encogimiento eran comprobables. Se
sustituyen por tres scripts versionados en `tools/`:

1. `tools/calibrate_min_rows_kmeans.py` - por que MIN_ROWS es 30 y no 24
   (tabla mas abajo).
2. `tools/calibrate_hold_days.py` - dias hasta tocar SL/TP sobre
   `data/*_historical_4y.csv` (entrada al cierre, toque por high/low,
   horizonte 365 dias, peor caso si SL y TP caen en la misma barra):
   mediana hasta el SL 24 dias (BTC), 12 (ETH), 11 (XRP), 8 (DOGE); hasta
   el TP 32/20/17/15. El 1.7-2.5% de las entradas no toca ninguno en un
   anio y queda CENSURADO, fuera de la mediana. "Un cierre cuesta
   semanas" se mantiene; las cifras viejas (47/56/48/36 y 68-128) NO se
   reproducen y quedan retiradas.
3. `tools/calibrate_shrink_error.py` - RMSE del win-rate encogido
   (SHRINK_K=5) contra la tasa verdadera con p~Beta(2,2), 20000
   simulaciones: 0.172 con 3 cierres por familia, 0.131 con 8, por debajo
   de 0.10 recien a partir de 17. La afirmacion vieja ("se estanca en
   ~0.10 desde 3 cierres") NO se reproduce bajo estos supuestos y se
   retira. Es simulacion con supuestos, NO medicion del ledger real.

Por que MIN_ROWS = 30 y no 24 (medido, 2026-09-29)
---------------------------------------------------
`tools/calibrate_min_rows_kmeans.py`: mismo pipeline que `_fit`, dos
poblaciones sinteticas (NULA: contexto y pnl iid, todo separamiento es
falso; ESTRUCTURADA: dos grupos con win-rate 0.65 y 0.35, efecto
verdadero delta_WR=0.30), R=300 repeticiones por punto y DOS corrientes
de semilla. El veredicto usa el PEOR caso de las dos corrientes: un
umbral que cambia de semilla no es un umbral. Criterio: falsos
positivos del filtro <=1%, potencia >=95%, clusters residuales <=5%, y
que el cluster bueno se identifique en >=90% de las corridas.

   n | nulo: pasa sil>=0.25 | residuales | estruct: ordena bien
  15 | 2.0%                 | 6.7%       | 89.0%
  20 | 0.7%                 | 1.7%       | 84.7%
  24 | 0.3%                 | 1.0%       | 88.3%
  30 | 0.3%                 | 0.3%       | 91.7%   <- CUMPLE
  40 | 0.0%                 | 0.0%       | 96.3%   <- CUMPLE

El menor n que cumple todo es 30: con 24 filas el cluster bueno sale mal
en el 11.7% de las corridas (88.3% < 90%). Se descarta tambien la razon
que daba el docstring viejo ("con n<30 el win_rate por cluster sale 0 o
1 por construccion"): medido, los clusters residuales son 6.7% con n=15,
1.7% con n=20 y 0.3% con n=30, no "por construccion".

POR QUE NO UN FILTRO DE SILUETA (medido y descartado, 2026-09-29)
-------------------------------------------------------------------
La idea inicial era filtrar con la silueta (¿se separan los grupos en el
espacio de features?). Falla por una razon conceptual y otra empirica:

  * Conceptual: la estructura en el espacio de features NO implica
    estructura en el win-rate, que es lo que el `cluster_stats` imprime.
  * Empirica: la distribucion de la silueta nula depende de CUANTAS
    columnas varian. Con 7 columnas iid da p50=0.157-0.163 y el corte
    0.25 deja pasar solo el 0.3% (pasa25(nulo) de la tabla de arriba);
    con la forma real del ledger (solo tres columnas varian: familia
    categorica, vol_pct continuo y forecast_up binario) el nulo da
    p50=0.340-0.347 y el corte deja pasar el 99.7-100%. Es decir, con la
    forma de los datos REALES el filtro no filtra nada. Medido con
    `tools/calibrate_min_rows_kmeans.py` (versionado), secciones
    "Filtro de permutacion" y "Silueta nula con la FORMA del ledger".

Filtro que SI controla el error (`cluster_pvalue`, `CLUSTER_ALPHA`)
-------------------------------------------------------------------
Test de permutacion sobre el win-rate: ¿podria esta diferencia de
win-rate entre clusters aparecer si el pnl no tuviera relacion con el
cluster? Se fija la etiqueta de cluster y se permuta el pnl
`CLUSTER_PERM` veces (semilla fija -> determinista); si la diferencia
observada no es rara bajo esa permutacion, no hay cluster que mostrar.

  * Controla POR CONSTRUCCION la tasa que importa: el falso positivo es
    la probabilidad de rechazar la permutacion nula, es decir
    `CLUSTER_ALPHA` (0.05), y vale con cualquier forma de dato.
  * Mismo razonamiento que el resto de la casa: no se afirma "hay
    estructura" por un umbral calibrado a mano sobre un escenario
    sintetico, sino con un p-valor cuya tasa de error es la que se
    declara.
  * Un dataset rechazado deja `cluster_ready = False`: la misma
    degradacion que pocos datos ("solo tablas agregadas"). La TABLA
    regimen x familia no se toca.
  * Medido con `tools/calibrate_min_rows_kmeans.py` (R=300, 2
    corrientes, mismo escenario que la tabla de MIN_ROWS):

       n   falso positivo (nulo)   potencia delta=0.30   potencia delta=0.60
      24            4.0%                  23.7%                 75.7%
      30            3.0%                  23.0%                 87.3%
      40            4.0%                  32.7%                 99.0%

    El falso positivo queda en ~alpha por construccion (3-4% con
    alpha=0.05; con R=300 la resolucion es 1/300=0.33pp). La POTENCIA
    con un efecto de delta_WR=0.30 es BAJA (23-33%) y aqui se declara en
    vez de esconderla: con 30 cierres el filtro casi nunca demuestra un
    efecto moderado, asi que su valor no es descubrir clusters buenos
    sino NO presentar como hallazgo una diferencia que el azar produce.

Nada de esto toca el gate de decision: solo sesga el orden de generacion.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from quant_math.ml import feature_store as fs
from quant_math.ml.families import FAMILIES, family_of

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        logger.warning("[SIS] %s ilegible; se usa %s", name, default)
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        logger.warning("[SIS] %s ilegible; se usa %s", name, default)
        return default


#: Umbral del KMeans (antes gobernaba TODO el modulo; ahora solo clustering).
MIN_ROWS = _env_int("QUANTMATH_SIS_MIN_ROWS", 30)
#: Tasa de falso positivo admitida al dar por bueno un cluster: es la
#: probabilidad de que la diferencia de win-rate entre clusters salga
#: igual de grande con el pnl PERMITADO respecto a las etiquetas. Ver el
#: docstring del modulo (filtro por permutacion, no por silueta).
CLUSTER_ALPHA = _env_float("QUANTMATH_SIS_CLUSTER_ALPHA", 0.05)
#: Repeticiones del test de permutacion (200 -> p minimo 1/201 = 0.005).
CLUSTER_PERM = _env_int("QUANTMATH_SIS_CLUSTER_PERM", 200)
#: Umbral de activacion de la tabla regimen x familia.
MIN_ROWS_ACTIVE = _env_int("QUANTMATH_SIS_MIN_ROWS_ACTIVE", 10)
#: Cierres minimos en UNA celda (regimen, familia) para que su win-rate
#: cruro se use sin encoger y para poder declarar regimen hostil.
MIN_CELL = _env_int("QUANTMATH_SIS_MIN_CELL", 5)
#: Constante de encogimiento (misma que hypothesis_prior.SHRINK_K).
SHRINK_K = _env_float("QUANTMATH_SIS_SHRINK_K", 5.0)
#: Win-rate encogido por debajo del cual una familia se declara en regimen
#: hostil en el regimen actual. 0.5 = break-even: con coste de ejecucion
#: (0,10% round trip, ver gate_policy.COST_MODEL_NOTE) por debajo de 0.5 la
#: familia pierde dinero, luego es la linea que separa "ventana que la
#: favorece" de "ventana que la castiga".
HOSTILE_WIN_RATE = _env_float("QUANTMATH_SIS_HOSTILE_WIN_RATE", 0.5)

STREAK_LOSS_LIMIT = 5
HAS_OPERATION_LEARNING = True

#: Columnas de `encode_row` que son LA ETIQUETA (resultado de la operacion).
#: Estar dentro del vector de clustering hace que el cluster sea
#: trivialmente separable y la tabla, inutil. F3 lo llamó "bomba de
#: relojeria" (2026-09-29); aqui se desactiva: KMeans ve solo contexto.
_LABEL_COLS = (1, 2)   # motivo, pnl_pct


def vol_bucket(vol_pct: Optional[float]) -> str:
    if vol_pct is None:
        return "?"
    if vol_pct >= 70:
        return "high"
    if vol_pct <= 30:
        return "low"
    return "mid"


# El vocabulario vive UNA vez en `quant_math/ml/families.py` y es el MISMO
# que consume `hypothesis_prior`: `family_of` acepta la fila entera o el
# tipo suelto, canonica hojas (`vwap_reversion` -> `mean_reversion`) y formas
# de enum (`StrategyType.MEAN_REVERSION` -> `mean_reversion`). Antes esta
# funcion devolvia la cadena cruda si no casaba por subcadena, y las claves
# que salian de `family_prior()` no existian en el `.get()` del consumidor:
# el aprendizaje no llegaba a la generacion (correccion 4).


def _forecast_str(v: Any) -> str:
    """Prevision ausente = "?" = "no lo se", igual que vol_bucket(None).

    Sin esto la clave salia "...|None" y NUNCA casaba con "True"/"False":
    un regimen sin prevision no desempataba nada, devolvia {} y el SIS
    callaba en silencio aunque tuviera 100 cierres.
    """
    return "?" if v is None else str(v)


def regime_key(symbol: str, regime: Optional[Dict[str, Any]]) -> str:
    """Clave normalizada del regimen vigente para un simbolo."""
    reg = regime or {}
    return (f"{symbol}|{vol_bucket(reg.get('vol_pct'))}|"
            f"{_forecast_str(reg.get('forecast_up'))}")


def _same_regime(a: str, b: str) -> bool:
    """Dos claves de regimen casan si el campo desconocido (?) no decide.

    `?` significa "no lo se" (sin volatilidad medida / sin prevision):
    casar contra cualquier valor, igual que hacia `rank_families` antes.
    """
    sa, sb = a.split("|"), b.split("|")
    if len(sa) != 3 or len(sb) != 3:
        return False
    if sa[0] != sb[0]:
        return False
    for i in (1, 2):
        if sa[i] == "?" or sb[i] == "?":
            continue
        if i == 1 and sa[i] != sb[i]:
            return False
        if i == 2 and _norm_bool(sa[i]) != _norm_bool(sb[i]):
            return False
    return True


def _norm_bool(v: str) -> Optional[bool]:
    if v in ("1.0", "1", "True", "true"):
        return True
    if v in ("0.0", "0", "False", "false"):
        return False
    return None


def _cluster_pvalue(labels: np.ndarray, pnls: np.ndarray) -> float:
    """p-valor de la diferencia de win-rate entre clusters (permutacion).

    H0: el win-rate no depende del cluster. Se fija `labels` y se
    permuta `pnls` `CLUSTER_PERM` veces con semilla FIJA (determinismo:
    el mismo dataset da siempre el mismo p-valor, que exigen los tests).

    Devuelve (1 + nº de permutaciones con diferencia >= observada) /
    (1 + nº de permutaciones), el p-valor tipico de una permutacion.
    Con k<2 (un solo cluster) no hay diferencia que testar -> 1.0.
    """
    k = int(labels.max()) + 1 if len(labels) else 0
    if k < 2:
        return 1.0
    wins = (pnls > 0).astype(float)

    def sep(w):
        by_c = [w[labels == c].mean() for c in range(k) if (labels == c).any()]
        return (max(by_c) - min(by_c)) if len(by_c) >= 2 else 0.0

    obs = sep(wins)
    if obs <= 0.0:
        return 1.0
    rng = np.random.default_rng(0)
    ge = 0
    for _ in range(CLUSTER_PERM):
        if sep(rng.permutation(wins)) >= obs:
            ge += 1
    return (ge + 1.0) / (CLUSTER_PERM + 1.0)


class OperationLearningLoop:
    """Refit barato por ciclo: KMeans + tablas agregadas encogidas."""

    def __init__(self, kb_records: Dict[str, Dict[str, Any]],
                 ledger_path: str, state_dir: str):
        self.mode = "collecting"
        self.rows: List[Dict[str, Any]] = []
        self.labels: Optional[np.ndarray] = None
        self.cluster_ready = False
        self.cluster_stats: List[Dict[str, Any]] = []
        self.cluster_pvalue = None
        self.regime_table: Dict[Tuple[str, str], Dict[str, float]] = {}
        self.global_stats: Dict[str, float] = {"n": 0, "win_rate": 0.5,
                                               "mean_pnl_pct": 0.0}
        self._fit(kb_records, ledger_path, state_dir)

    # ------------------------------------------------------------------

    def _fit(self, kb_records, ledger_path, state_dir):
        self.rows = fs.build_trade_dataset(kb_records, ledger_path, state_dir)
        n = len(self.rows)
        if n < MIN_ROWS_ACTIVE:
            self.mode = "collecting"
            logger.info("[SIS] recolectando: %d/%d cierres "
                        "(KMeans a partir de %d)", n, MIN_ROWS_ACTIVE,
                        MIN_ROWS)
            return

        pnls = np.array([float(r.get("pnl_pct") or 0.0)
                         for r in self.rows], dtype=float)
        self.global_stats = {
            "n": n,
            "win_rate": float((pnls > 0).mean()),
            "mean_pnl_pct": float(np.nanmean(pnls)),
        }

        # --- clustering SOLO con contexto (sin la etiqueta) y solo con n suficiente
        self.cluster_ready = n >= MIN_ROWS
        self.labels = None
        self.cluster_stats = []
        self.cluster_pvalue = None
        if self.cluster_ready:
            X = np.array(fs.encode_dataset(self.rows), dtype=float)
            Xc = np.delete(X, _LABEL_COLS, axis=1)
            ok_cluster = False
            try:
                from sklearn.cluster import KMeans
                from sklearn.preprocessing import StandardScaler
                k = max(2, min(4, n // 25))
                Xs = StandardScaler().fit_transform(Xc)
                km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(Xs)
                # El KMeans devuelve grupos SIEMPRE (parte los datos en k
                # aunque no haya nada que partir), asi que lo que se
                # testa NO es si hay grupos sino si el win-rate depende
                # de ellos. Sin ese test, en n=30 el 12.0% de los datasets
                # sin estructura mostraba una diferencia de win-rate entre
                # clusters >= 0.30, del tamano del efecto real que se
                # quiere detectar (medido: tools/calibrate_min_rows_kmeans.py).
                pval = _cluster_pvalue(km.labels_, pnls)
                self.cluster_pvalue = pval
                if pval > CLUSTER_ALPHA:
                    logger.info("[SIS] %d cierres: clusters sin significacion "
                                "(p=%.3f > %.2f): la diferencia de win-rate "
                                "entre grupos cabe en el ruido; clusters "
                                "descartados, solo tablas agregadas",
                                n, pval, CLUSTER_ALPHA)
                else:
                    self.labels = km.labels_
                    ok_cluster = True
            except Exception as exc:
                logger.warning("[SIS] clustering no disponible (%s); "
                               "solo tablas agregadas", exc)
                self.labels = None
            self.cluster_ready = ok_cluster
            if ok_cluster:
                for cid in range(int(self.labels.max()) + 1):
                    idx = np.where(self.labels == cid)[0]
                    if not len(idx):
                        continue
                    p = pnls[idx]
                    self.cluster_stats.append({
                        "cluster": int(cid), "n": int(len(idx)),
                        "win_rate": float((p > 0).mean()),
                        "mean_pnl_pct": float(np.nanmean(p)),
                    })
        else:
            logger.info("[SIS] %d cierres: tablas activas, KMeans "
                        "diferido hasta %d (con menos, los clusters son un "
                        "artefacto de muestra)", n, MIN_ROWS)

        # --- tabla regimen x familia, con encogimiento
        table: Dict[Tuple[str, str], List[float]] = {}
        for r in self.rows:
            key = (f"{r.get('symbol')}|{vol_bucket(r.get('vol_pct'))}|"
                   f"{_forecast_str(r.get('forecast_up'))}", family_of(r))
            table.setdefault(key, []).append(float(r.get("pnl_pct") or 0.0))
        g_wr = self.global_stats["win_rate"]
        g_mu = self.global_stats["mean_pnl_pct"]
        self.regime_table = {}
        for key, v in table.items():
            n_cell = len(v)
            wins = sum(1 for p in v if p > 0)
            raw_wr = wins / n_cell
            raw_mu = sum(v) / n_cell
            self.regime_table[key] = {
                "n": n_cell,
                "win_rate": raw_wr,
                "mean_pnl_pct": raw_mu,
                # encogimiento: (n*raw + K*global)/(n+K). Con n=1 la celda
                # vale casi el global; con n grande, su valor crudo.
                "shrunk_win_rate": (wins + SHRINK_K * g_wr) / (n_cell + SHRINK_K),
                "shrunk_mean_pnl_pct": (sum(v) + SHRINK_K * g_mu)
                                       / (n_cell + SHRINK_K),
            }
        self.mode = "active"

    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        top_clusters = sorted(self.cluster_stats,
                              key=lambda c: -c["mean_pnl_pct"])[:3]
        return {"mode": self.mode, "rows": len(self.rows),
                "clusters": top_clusters,
                "cluster_ready": self.cluster_ready,
                "cluster_pvalue": self.cluster_pvalue,
                "min_rows_active": MIN_ROWS_ACTIVE,
                "min_rows_cluster": MIN_ROWS}

    def family_regime_stats(self, symbol: str,
                            regime: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """Agregado por familia en el regimen vigente, encogido.

        Es la superficie que consumen `rank_families`, `hostile_families`
        y `family_prior`: una sola fuente, sin duplicar la aritmetica.
        """
        if self.mode != "active" or not self.regime_table:
            return {}
        target = regime_key(symbol, regime)
        out: Dict[str, Dict[str, float]] = {}
        for (key, fam), s in self.regime_table.items():
            if not _same_regime(key, target):
                continue
            acc = out.setdefault(fam, {"n": 0, "wins": 0,
                                       "pnl_sum": 0.0})
            acc["n"] += s["n"]
            acc["wins"] += s["win_rate"] * s["n"]
            acc["pnl_sum"] += s["mean_pnl_pct"] * s["n"]
        g_wr = self.global_stats.get("win_rate", 0.5)
        g_mu = self.global_stats.get("mean_pnl_pct", 0.0)
        res: Dict[str, Dict[str, float]] = {}
        for fam, a in out.items():
            n = int(a["n"])
            wins = a["wins"]
            res[fam] = {
                "n": n,
                "win_rate": (wins / n) if n else 0.0,
                "mean_pnl_pct": (a["pnl_sum"] / n) if n else 0.0,
                "shrunk_win_rate": (wins + SHRINK_K * g_wr) / (n + SHRINK_K),
                "shrunk_mean_pnl_pct": (a["pnl_sum"] + SHRINK_K * g_mu)
                                        / (n + SHRINK_K),
            }
        return res

    def hostile_families(self, symbol: str,
                         regime: Optional[Dict[str, Any]]) -> List[str]:
        """Familias en REGIMEN HOSTIL: la ventana actual las castiga.

        Criterio EXPLICITO, no heuristico — las tres condiciones:

          1. hay al menos `MIN_CELL` cierres de esa familia en ese
             simbolo y ese regimen (sin evidencia no hay veredicto);
          2. su win-rate encogido < `HOSTILE_WIN_RATE` (0.5 = break-even
             antes del coste de ejecucion);
          3. el modo esta `active`.

        Con una sola falla la familia NO es hostil (fail-open a proposito:
        declarar hostil sin datos cerraria la puerta a una familia solo
        porque nadie la ha probado aun).

        LIMITE HONESTO: con el ledger real de 2026-09-29 esta funcion
        devuelve siempre [] porque no hay NI UN cierre en vivo. Esta
        implementada y testeada con datos sinteticos; NO validada sobre
        evidencia real todavia.
        """
        if self.mode != "active":
            return []
        stats = self.family_regime_stats(symbol, regime)
        return sorted(f for f, s in stats.items()
                      if s["n"] >= MIN_CELL
                      and s["shrunk_win_rate"] < HOSTILE_WIN_RATE)

    def family_prior(self, symbol: str,
                     regime: Optional[Dict[str, Any]]) -> Dict[str, Tuple[float, int]]:
        """{(familia): (win_rate_encogido, n)} para `HypothesisPrior`.

        Devuelve {} en `collecting`, asi que el consumidor no nota la
        diferencia hasta que hay evidencia suficiente.
        """
        if self.mode != "active":
            return {}
        return {f: (s["shrunk_win_rate"], int(s["n"]))
                for f, s in self.family_regime_stats(symbol, regime).items()}

    def rank_families(self, symbol: str,
                      regime: Optional[Dict[str, Any]]) -> List[str]:
        """Familias ordenadas por exito historico en el regimen actual.

        Orden por win-rate ENCOGIDO (no por el cruro: con 1 cierre ganador
        el cruro dice 1.00 y con 1 perdedor 0.00, que es ruido puro).
        Las familias en regimen hostil se mueven AL FINAL: se pausan, no se
        excluyen — el generador tiene slots de exploracion y dejarlas fuera
        del todo cerraria el bucle de aprendizaje.
        """
        stats = self.family_regime_stats(symbol, regime)
        if not stats:
            return []
        hostile = set(self.hostile_families(symbol, regime))
        ranked = sorted(stats.items(),
                        key=lambda kv: (-kv[1]["shrunk_win_rate"],
                                        -kv[1]["n"], kv[0]))
        ok = [f for f, _ in ranked if f not in hostile]
        bad = [f for f, _ in ranked if f in hostile]
        families = list(ok)
        for fallback in ("breakout", "momentum", "mean_reversion"):
            if fallback not in families and fallback not in hostile:
                families.append(fallback)
        # La hostil se BAJA al final SIEMPRE, tambien por detras de una
        # familia sin evidencia. Con la version anterior, si en la ventana
        # solo habia evidencia de UNA familia y esa era la hostil, salia
        # primera igualmente: la pausa no se notaba en el orden (medido,
        # runtime/f3/d2/demo_lazo.py, 2026-09-29).
        families += [f for f in bad if f not in families]
        return families

    def _consecutive_losses(self) -> int:
        n = 0
        for r in reversed(sorted(
                self.rows, key=lambda x: float(x.get("duration_s") or 0))):
            if float(r.get("pnl_pct") or 0) <= 0:
                n += 1
            else:
                break
        return n

    def should_explore(self) -> bool:
        """Rafaga de exploracion si la racha de perdidas es larga."""
        if self.mode != "active":
            return False
        return self._consecutive_losses() >= STREAK_LOSS_LIMIT


def load_loop(kb_path: str, state_dir: str) -> OperationLearningLoop:
    """Construye el loop desde las fuentes durables (PG->JSONL fallback)."""
    records: Dict[str, Dict[str, Any]] = {}
    try:
        from quant_math.autonomous_research.adapters.postgres_kb import (
            KBPersistence)
        records = KBPersistence(kb_path).load_all()
    except Exception as exc:
        logger.warning("[SIS] carga KB fallo (%s); intento JSONL puro",
                       exc.__class__.__name__)
        if os.path.exists(kb_path):
            with open(kb_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    hid = rec.get("hypothesis_id")
                    if hid:
                        existing = records.get(hid)
                        if existing:
                            existing.update(rec)
                        else:
                            records[hid] = rec
    ledger = os.path.join(state_dir, "paper_executions.jsonl")
    return OperationLearningLoop(records, ledger, state_dir)
