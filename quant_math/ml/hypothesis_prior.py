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
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_TOTAL = int(os.environ.get("QUANTMATH_ML_MIN_RECORDS", "100"))
MIN_CELL = 8
SHRINK_K = 5.0


def _norm_type(strategy_type: Any) -> str:
    return str(getattr(strategy_type, "value", strategy_type) or "unknown")


class HypothesisPrior:
    """Explainable positive-expectancy prior over (strategy_type, symbol)."""

    def __init__(self, records: Iterable[Dict[str, Any]]):
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
    def from_records(cls, records: Iterable[Dict[str, Any]]) -> "HypothesisPrior":
        return cls(records)

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
                "global_rate": round(self.global_rate, 4), "reordered": False}
        if not self.is_active or not templates:
            return templates, info

        scored = [
            (_score_of(t, symbol, self), i)
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
    st = template.get("strategy_type")
    params = template.get("parameters", {}) or {}
    inner_sym = params.get("symbol", symbol)
    return prior.positive_rate(st, inner_sym if isinstance(inner_sym, str)
                               else symbol)


def build_prior_from_kb(kb_path: str,
                        dsn: Optional[str] = None) -> HypothesisPrior:
    """Load every historical record (PG first, JSONL fallback) and fit."""
    from quant_math.autonomous_research.adapters.postgres_kb import (
        JSONLKnowledgeBase,
    )
    kb = JSONLKnowledgeBase(jsonl_path=kb_path)
    return HypothesisPrior.from_records(kb.load_records().values())
