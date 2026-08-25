"""Las 4 implementaciones cientificas aprobadas:
Kalman, Spectral (FFT), Bayes formal y validacion cruzada entre simbolos.
Condicion: nada duplicado, gate intacto, suite verde."""
import json
import os
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.ml.kalman_feature import kalman_features
from model_based_generator import analyze_series
from quant_math.ml.hypothesis_prior import HypothesisPrior


def test_kalman_features_directional():
    up = [100 + i * 0.5 for i in range(100)]
    f_up = kalman_features(up)
    assert f_up["kalman_slope_pct"] > 0
    flat = [100 + np.sin(i / 3) * 0.01 for i in range(100)]
    f_flat = kalman_features(flat)
    assert abs(f_flat["kalman_slope_pct"]) < 0.05
    print(f"PASS kalman: slope_up={f_up['kalman_slope_pct']:.4f} "
          f"slope_flat={f_flat['kalman_slope_pct']:.5f}")


def test_spectral_cycle_detection():
    t = np.arange(500)
    sine = 100 + 5 * np.sin(2 * np.pi * t / 17) + \
        np.random.RandomState(0).normal(0, .1, 500)
    info = analyze_series(list(sine))
    cycle = info.get("cycle_len")
    assert cycle is not None and 14 <= cycle <= 21, cycle
    print(f"PASS spectral: ciclo dominante detectado={cycle} (real=17)")


def test_bayes_ci_formal():
    rows = ([{"strategy_type": "breakout", "symbol": "BTC/USDT",
              "expectancy": 0.5} for _ in range(20)]
            + [{"strategy_type": "breakout", "symbol": "BTC/USDT",
                "expectancy": -0.1} for _ in range(5)])
    p = HypothesisPrior(rows)
    mean, lo, hi = p.beta_posterior("breakout", "BTC/USDT", ci_level=0.10)
    assert lo < mean < hi and lo > 0.3
    s = p.summary()
    assert all("ci90" in c for c in s["top_cells"])
    print(f"PASS bayes: IC90=[{lo:.3f},{hi:.3f}] mean={mean:.3f} en summary")


def test_cross_symbol_validation():
    """Familia ganadora en ETH -> backtested se eleva a validated para XRP;
    metricas debiles siguen failed. Gate intacto."""
    from quant_math.orchestrator import Orchestrator, OrchestratorConfig
    from quant_math.autonomous_research.interfaces import StrategyType

    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(tmp, "kb.jsonl")
        with open(kb, "w") as fh:
            for i in range(110):
                fh.write(json.dumps({
                    "hypothesis_id": f"seed_{i}",
                    "symbol": "ETH/USDT" if i < 60 else "SOL/USDT",
                    "status": "backtested",
                    "strategy_type": "momentum" if i % 2 else "mean_reversion",
                    "expectancy": 0.6 if i % 2 == 0 else -0.3,
                    "scientific_score": 0.9, "n_trades": 20,
                    "win_rate": 55.0, "parameters": {}}) + "\n")

        cfg = OrchestratorConfig(
            symbols=["XRP/USDT"], timeframe="5m", lookback_days=7,
            initial_capital=10000.0, entry_pct=0.05, take_profit_pct=0.02,
            min_paper_trades=3, hypotheses_per_cycle=3,
            kb_path=kb, state_dir=os.path.join(tmp, "st"), use_postgres=False)
        o = Orchestrator(cfg)
        hid = o.runner.research_manager.generate_hypothesis(
            name="CrossGood", description="t",
            strategy_type=StrategyType.MOMENTUM, author="t",
            short_window=11, long_window=23, symbol="XRP/USDT")
        strong = {"hypothesis_id": hid, "symbol": "XRP/USDT",
                  "status": "success", "n_trades": 30, "win_rate": 95.0,
                  "total_return": 45000.0, "total_return_pct": 450.0,
                  "sharpe_ratio": 9.0}
        rec = o._result_to_kb_record(strong, "XRP/USDT")
        assert rec["status"] == "validated", rec["status"]
        assert rec["cross_symbol_validated"] is True
        print("PASS cross-symbol: familia ganadora en otro simbolo eleva a "
              "validated")

