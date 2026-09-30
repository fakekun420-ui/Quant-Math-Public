"""Hypothesis generation prior learned from historical backtest outcomes.

Learns P(expectancy > 0 | strategy_type, symbol) from REAL historical records
(PostgreSQL KB with automatic JSONL fallback) using an explainable
shrinkage estimator:

    rate(cell)  = (positives_cell + K * global_rate) / (n_cell + K)

The prior ONLY reorders candidate hypotheses before AQDE's top-N selection
(advisory bias). It NEVER touches the decision gate: entry still requires
each hypothesis's own real backtested expectancy > 0.

Activation policy (anti-data-starvation):
    total records >= MIN_TOTAL  -> mode "active"   (ranking applied)
    otherwise                   -> mode "collecting" (input returned untouched)

SIS coupling (correccion 4, 2026-09-29)
---------------------------------------
`family_prior` inyecta el aprendizaje NO supervisado del SIS
(`OperationLearningLoop.family_prior`) en la puntuacion de cada plantilla:

    score = (1 - w) * positive_rate(tipo, simbolo) + w * wr_familia(regimen)
    w     = n_familia / (n_familia + PRIOR_K)

Es decir: con 0 cierres de esa familia w=0 y el prior se comporta EXACTAMENTE
que antes (los tests de B3 siguen valiendo); con evidencia, la familia que
esta funcionando EN EL REGIMEN ACTUAL pesa mas en que se genera despues.
Sigue siendo advisory: no abre ni cierra operaciones.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from quant_math.ml import families

logger = logging.getLogger(__name__)

MIN_TOTAL = int(os.environ.get("QUANTMATH_ML_MIN_RECORDS", "100"))
MIN_CELL = 8
SHRINK_K = 5.0
#: Peso maximo del prior de familia del SIS. Igual que SHRINK_K: con
#: n=5 cierres w=0,50; con n=15, w=0,75. La constante es la misma que la
#: del SIS para que las dos mitades del bucle midan "evidencia" igual.
PRIOR_K = 5.0

# Vocabulario UNICO de familias (quant_math/ml/families.py). Antes estaba
# escrito aqui y otra vez en `regime_learning`, con semanticas distintas: el
# SIS emitia claves hoja y este modulo buscaba canonicas -> `.get()` daba
# `None` -> w=0.0 y el aprendizaje no entraba en NADA (correccion 4).
# Re-exportado para no romper los llamantes que importan de aqui.
FAMILIES = families.FAMILIES
family_of = families.family_of


def _norm_type(strategy_type: Any) -> str:
    """Clave de CELDA (tipo, simbolo). NO canonicar: es el granulo del KB."""
    return str(getattr(strategy_type, "value", strategy_type) or "unknown")


class HypothesisPrior:
    """Explainable positive-expectancy prior over (strategy_type, symbol)."""

    def __init__(self, records: Iterable[Dict[str, Any]],
                 family_prior: Optional[Dict[str, Tuple[float, int]]] = None):
        #: {(familia): (win_rate_encogido, n)} del SIS en el regimen actual.
        #: Vacio por defecto -> el prior se comporta como antes de existir.
        self.family_prior: Dict[str, Tuple[float, int]] = dict(family_prior or {})
        self.total = 0
        self.positives = 0
        cells: Dict[Tuple[str, str], List[float]] = {}
        types: Dict[str, List[float]] = {}
        for rec in records:
            exp = rec.get("expectancy")
            st = _norm_type(rec.get("strategy_type"))
            sym = str(rec.get("symbol") or "unknown")
            try:
                exp_f = float(exp)
            except (TypeError, ValueError):
                continue
            pos = 1.0 if exp_f > 0 else 0.0
            self.total += 1
            self.positives += pos
            cells.setdefault((st, sym), []).append(exp_f)
            types.setdefault(st, []).append(exp_f)

        self.global_rate = (self.positives + 1.0) / (self.total + 2.0) \
            if self.total else 0.5
        self._cell_stats = {
            key: (sum(1.0 for e in vals if e > 0), len(vals))
            for key, vals in cells.items()
        }
        self._type_stats = {
            t: (sum(1.0 for e in vals if e > 0), len(vals))
            for t, vals in types.items()
        }
        self.mode = "active" if self.total >= MIN_TOTAL else "collecting"

    # ------------------------------------------------------------------

    @classmethod
    def from_records(cls, records: Iterable[Dict[str, Any]],
                     family_prior: Optional[Dict[str, Tuple[float, int]]] = None
                     ) -> "HypothesisPrior":
        return cls(records, family_prior=family_prior)

    # ------------------------------------------------------------------

    def family_weight(self, strategy_type: Any) -> float:
        """w con la que la evidencia del SIS entra en el score de `stype`.

        0.0 si el SIS no tiene evidencia de esa familia -> score identico al
        anterior. Con n cierres, w = n / (n + PRIOR_K).
        """
        hit = self.family_prior.get(family_of(strategy_type))
        if not hit:
            return 0.0
        _wr, n = hit
        try:
            n = float(n)
        except (TypeError, ValueError):
            return 0.0
        if n <= 0:
            return 0.0
        return n / (n + PRIOR_K)

    def score(self, strategy_type: Any, symbol: str) -> float:
        """Puntuacion con la que se rankea una plantilla.

        Base: positive_rate(tipo, simbolo) del KB. Si el SIS tiene evidencia
        de la familia en el regimen vigente, se mezcla con su win-rate
        encogido. NUNCA sale del rango [0, 1] porque ambas fases lo estan.
        """
        base = self.positive_rate(strategy_type, symbol)
        w = self.family_weight(strategy_type)
        if w <= 0.0:
            return base
        hit = self.family_prior.get(family_of(strategy_type))
        return (1.0 - w) * base + w * float(hit[0])

    @property
    def is_active(self) -> bool:
        return self.mode == "active"

    def beta_posterior(self, strategy_type: Any, symbol: str,
                       ci_level: float = 0.10) -> Tuple[float, float, float]:
        """Posterior Beta(a,b) de la celda (formalizacion bayesiana).

        Devuelve (mean, ci_lo, ci_hi) al nivel 1-alpha usando scipy.stats
        cuando esta disponible; celdas finas heredan el shrinkage del prior
        global como en positive_rate()."""
        st = _norm_type(strategy_type)
        n_pos, n = self._cell_stats.get((st, symbol), (0.0, 0))
        rate = self.positive_rate(st, symbol)
        if n < MIN_CELL:
            return rate, 0.0, 1.0          # sin datos suficientes: CI maxima
        a = alpha_pos = n_pos * rate / max(rate, 1e-9) if False else None
        # posterior Beta con conteos reales + prior uniforme
        a = 1.0 + n_pos
        b = 1.0 + (n - n_pos)
        try:
            from scipy import stats as sps
            lo = float(sps.beta.ppf(ci_level / 2, a, b))
            hi = float(sps.beta.ppf(1 - ci_level / 2, a, b))
            mean = float(sps.beta.mean(a, b))
            return mean, lo, hi
        except Exception:
            return rate, max(0.0, rate - 0.15), min(1.0, rate + 0.15)

    def positive_rate(self, strategy_type: Any, symbol: str) -> float:
        """Shrunk estimate of P(expectancy>0); fully explainable formula."""
        st = _norm_type(strategy_type)
        n_pos, n = self._cell_stats.get((st, symbol), (0.0, 0))
        cell_rate = (n_pos + SHRINK_K * self.global_rate) / (n + SHRINK_K)
        if n >= MIN_CELL:
            return cell_rate
        # Thin cells lean further on the strategy-type-level statistic.
        t_pos, t_n = self._type_stats.get(st, (0.0, 0))
        type_rate = (t_pos + SHRINK_K * self.global_rate) / (t_n + SHRINK_K)
        w = n / float(n + MIN_CELL) if (n + MIN_CELL) else 0.0
        return w * cell_rate + (1.0 - w) * type_rate

    def rank_templates(
        self,
        templates: List[Dict[str, Any]],
        symbol: str,
        top_n: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Reorder candidate templates by prior, preserving exploration slots.

        Returns (ordered_templates, info). In collecting mode returns the
        input order untouched. Even in active mode, E = max(1, top_n // 4)
        slots are reserved for templates as originally ordered so AQDE keeps
        exploring beyond the prior's favourites.
        """
        info = {"mode": self.mode, "total": self.total,
                "global_rate": round(self.global_rate, 4), "reordered": False,
                "family_prior": {f: (round(w, 3), n)
                                 for f, (w, n) in self.family_prior.items()},
                "family_prior_max_w": round(
                    max([self.family_weight(t.get("strategy_type"))
                         for t in templates], default=0.0), 3)}
        if not self.is_active or not templates:
            return templates, info

        scored = [
            (self.score(t.get("strategy_type"),
                        (t.get("parameters") or {}).get("symbol")
                        if isinstance((t.get("parameters") or {}).get("symbol"), str)
                        else symbol), i)
            for i, t in enumerate(templates)
        ]
        exploration = max(1, top_n // 4)
        keep = max(0, min(top_n - exploration, len(templates)))

        ranked = sorted(range(len(templates)),
                        key=lambda i: (-scored[i][0], i))
        biased_idx = ranked[:keep]
        tail_idx = [i for i in range(len(templates)) if i not in set(biased_idx)]
        ordered = [templates[i] for i in biased_idx] + \
            [templates[i] for i in tail_idx]
        info.update({"reordered": ordered[0] is not templates[0],
                     "exploration_slots": len(tail_idx)})
        return ordered, info

    def summary(self) -> Dict[str, Any]:
        top_cells = sorted(
            (((st, sym), p / n) for (st, sym), (p, n) in
             self._cell_stats.items() if n),
            key=lambda kv: -kv[1])[:5]
        cells_out = []
        for (st, sym), r in top_cells:
            mean, lo, hi = self.beta_posterior(st, sym)
            cells_out.append({"strategy_type": st, "symbol": sym,
                              "positive_rate": round(r, 3),
                              "ci90": [round(lo, 3), round(hi, 3)]})
        return {
            "mode": self.mode,
            "total": self.total,
            "global_positive_rate": round(self.global_rate, 4),
            "top_cells": cells_out,
        }


def _score_of(template: Dict[str, Any], symbol: str,
              prior: HypothesisPrior) -> float:
    """Score de una plantilla: base del KB mezclada con el SIS si lo hay."""
    st = template.get("strategy_type")
    params = template.get("parameters", {}) or {}
    inner_sym = params.get("symbol", symbol)
    return prior.score(st, inner_sym if isinstance(inner_sym, str)
                       else symbol)


def build_prior_from_kb(kb_path: str,
                        dsn: Optional[str] = None,
                        family_prior: Optional[Dict[str, Tuple[float, int]]] = None
                        ) -> HypothesisPrior:
    """Load every historical record (PG first, JSONL fallback) and fit.

    `family_prior` = salida de `OperationLearningLoop.family_prior()` (SIS).
    """
    from quant_math.autonomous_research.adapters.postgres_kb import (
        JSONLKnowledgeBase,
    )
    kb = JSONLKnowledgeBase(jsonl_path=kb_path)
    return HypothesisPrior.from_records(kb.load_records().values(),
                                        family_prior=family_prior)
