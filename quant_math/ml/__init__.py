"""ML utilities for Quant-Math hypothesis generation (advisory only).

The models in this package never touch the expectancy decision gate.
"""

from quant_math.ml.hypothesis_prior import HypothesisPrior, build_prior_from_kb

__all__ = ["HypothesisPrior", "build_prior_from_kb"]
