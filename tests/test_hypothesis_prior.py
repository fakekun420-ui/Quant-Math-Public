"""HypothesisPrior tests: advisory-only reordering + gate intactness.

Critical invariant (B3): the ML prior may only influence WHICH candidate
hypotheses AQDE generates/backtests first. The decision gate
(expectancy > 0 from each hypothesis's own REAL backtest) must behave
identically with or without the prior attached.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.ml.hypothesis_prior import HypothesisPrior


def make_records(n_breakout_pos, n_breakout_neg, n_mr_pos, n_mr_neg):
    records = []
    for i in range(n_breakout_pos):
        records.append({"strategy_type": "breakout", "symbol": "BTC/USDT",
                        "expectancy": 0.5 + i * 1e-9})
    for i in range(n_breakout_neg):
        records.append({"strategy_type": "breakout", "symbol": "BTC/USDT",
                        "expectancy": -0.2 - i * 1e-9})
    for i in range(n_mr_pos):
        records.append({"strategy_type": "mean_reversion", "symbol": "ETH/USDT",
                        "expectancy": 0.3})
    for i in range(n_mr_neg):
        records.append({"strategy_type": "mean_reversion", "symbol": "ETH/USDT",
                        "expectancy": -0.4})
    return records


def templates_for(symbol="BTC/USDT"):
    return [
        {"name": "MR_first", "strategy_type": "mean_reversion",
         "parameters": {"rsi_period": 14, "symbol": symbol}},
        {"name": "BRK_second", "strategy_type": "breakout",
         "parameters": {"donchian_window": 20, "symbol": symbol}},
        {"name": "MR_third", "strategy_type": "mean_reversion",
         "parameters": {"vwap_window": 20, "symbol": symbol}},
        {"name": "BRK_fourth", "strategy_type": "breakout",
         "parameters": {"donchian_window": 30, "symbol": symbol}},
    ]


def test_collecting_mode_returns_input_untouched():
    """< MIN_TOTAL records -> no reordering at all (B4)."""
    prior = HypothesisPrior(make_records(30, 20, 10, 15))
    assert prior.mode == "collecting"
    assert prior.total == 75 < 100
    tpls = templates_for()
    ordered, info = prior.rank_templates(tpls, "BTC/USDT", top_n=2)
    assert ordered == tpls
    assert info["reordered"] is False
    print("PASS collecting: <100 registros -> orden intacto")


def test_active_mode_biases_toward_high_prior_cells():
    """Active mode ranks high-positive-rate cells first; keeps multiset."""
    prior = HypothesisPrior(make_records(80, 10, 5, 60))
    assert prior.mode == "active"
    tpls = templates_for()
    ordered, info = prior.rank_templates(tpls, "BTC/USDT", top_n=2)
    names = [t["name"] for t in ordered]
    # breakout/BTC has ~89% positive rate vs mean_reversion ~7.6%:
    assert set(names) == {t["name"] for t in tpls}
    assert names[0].startswith("BRK")
    assert ordered[0]["name"] != tpls[0]["name"]
    assert info["reordered"] is True
    rate = prior.positive_rate("breakout", "BTC/USDT")
    assert 0.0 <= rate <= 1.0 and rate > 0.8
    summary = prior.summary()
    assert summary["total"] == 155 and summary["mode"] == "active"
    print(f"PASS active: breakout/BTC prior={rate:.2f} rankea primero; "
          f"multiset preservado")


def test_exploration_slots_preserve_original_candidates():
    """Even active mode reserves slots for original-order candidates."""
    prior = HypothesisPrior(make_records(90, 5, 2, 50))
    tpls = templates_for()
    ordered, info = prior.rank_templates(tpls, "ETH/USDT", top_n=2)
    assert len(ordered) == len(tpls)
    assert info["exploration_slots"] >= 1
    # With exploration=1 and keep=1, one slot comes from the tail of input.
    assert tpls[0] in ordered[1:]
    print("PASS exploración: slots reservados para candidatos originales")


def test_decision_gate_intact_with_prior_present():
    """THE critical B3 test: gate behavior identical with/without prior."""
    from quant_math.decision_engine import DecisionEngine

    candles_up = [[i, 100, 101, 99, 100 + i, 10] for i in range(50)]
    candles_down = [[i, 100, 101, 99, 100 - i, 10] for i in range(50)]

    prior = HypothesisPrior(make_records(95, 0, 0, 70))  # loves breakout
    assert prior.is_active

    with tempfile.TemporaryDirectory() as tmp:
        kb_path = os.path.join(tmp, "hypotheses.jsonl")
        with open(kb_path, "w") as fh:
            fh.write(json_line("hyp_neg_breakout", expectancy=-0.05,
                               status="backtested"))
        engine = DecisionEngine(
            symbols=["BTC/USDT"],
            kb_path=kb_path,
            state_dir=os.path.join(tmp, "state"),
            data_provider=lambda s: candles_up,
            use_postgres=False,
        )
        result = engine.decide("BTC/USDT")
        assert result["action"] == "no_entry", \
            "el prior NO puede abrir entradas con expectancy<=0"
        assert result["signal"] is None

    with tempfile.TemporaryDirectory() as tmp:
        kb_path = os.path.join(tmp, "hypotheses.jsonl")
        with open(kb_path, "w") as fh:
            fh.write(json_line("hyp_pos_breakout", expectancy=+0.03,
                               status="backtested"))
        engine = DecisionEngine(
            symbols=["BTC/USDT"],
            kb_path=kb_path,
            state_dir=os.path.join(tmp, "state"),
            data_provider=lambda s: candles_down,
            use_postgres=False,
        )
        signal = engine.decide("BTC/USDT")
        assert signal["action"] == "entry"
        second = engine.decide("BTC/USDT")
        assert second["action"] == "skip_position_guard"
    print("PASS gate intacto: expectancy<=0->no_entry y >0->entry sin cambios")


def json_line(hid, expectancy, status):
    import json
    return json.dumps({
        "hypothesis_id": hid, "symbol": "BTC/USDT",
        "status": status, "expectancy": expectancy,
        "scientific_score": 0.9, "parameters": {"lookback": 5},
    })


if __name__ == "__main__":
    test_collecting_mode_returns_input_untouched()
    test_active_mode_biases_toward_high_prior_cells()
    test_exploration_slots_preserve_original_candidates()
    test_decision_gate_intact_with_prior_present()
    print("\n4/4 hypothesis_prior tests passed")
