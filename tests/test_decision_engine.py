"""Decision Engine behavior tests: abstention (no_entry) and operation (entry)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.decision_engine import DecisionEngine


def make_engine(tmp, hypotheses, candles):
    kb_path = os.path.join(tmp, "hypotheses.jsonl")
    with open(kb_path, "w", encoding="utf-8") as fh:
        for hyp in hypotheses:
            fh.write(hyp + "\n")
    return DecisionEngine(
        symbols=["BTC/USDT"],
        kb_path=kb_path,
        state_dir=os.path.join(tmp, "state"),
        min_paper_trades=3,
        data_provider=lambda symbol: candles,
    )


def test_abstention_all_nonpositive_expectancy():
    """All hypotheses with expectancy <= 0 -> no_entry, zero signals."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(
            tmp,
            [
                '{"hypothesis_id": "hyp_neg", "symbol": "BTC/USDT", "status": "validated",'
                ' "expectancy": -0.02, "scientific_score": 0.9}',
                '{"hypothesis_id": "hyp_zero", "symbol": "BTC/USDT", "status": "failed",'
                ' "expectancy": 0.0, "scientific_score": 0.95}',
            ],
            [[i, 100, 101, 99, 100.5, 10] for i in range(50)],
        )
        result = engine.decide("BTC/USDT")

        assert result is not None
        assert result["action"] == "no_entry"
        assert result["signal"] is None
        assert result["reason"] == "sin hipótesis de expectativa positiva disponible"
        assert len(engine.open_positions) == 0
    print("PASS abstention: expectancy<=0 -> no_entry, cero señales")


def test_operation_positive_expectancy_generates_signal():
    """One hypothesis with expectancy > 0 -> entry signal generated."""
    with tempfile.TemporaryDirectory() as tmp:
        candles = [[i, 100, 102, 99, 100 + i, 10] for i in range(50)]
        engine = make_engine(
            tmp,
            [
                '{"hypothesis_id": "hyp_pos", "symbol": "BTC/USDT", "status": "backtested",'
                ' "expectancy": 0.03, "scientific_score": 0.8, "parameters": {"lookback": 5}}',
                '{"hypothesis_id": "hyp_neg", "symbol": "BTC/USDT", "status": "failed",'
                ' "expectancy": -0.01, "scientific_score": 0.7}',
            ],
            candles,
        )
        signal = engine.decide("BTC/USDT")

        assert signal is not None
        assert signal["action"] == "entry"
        assert signal["side"] in ("buy", "sell")
        assert signal["hypothesis_id"] == "hyp_pos"
        assert signal["side"] == "buy"  # closes suben -> momentum positivo

        # Position guard: second cycle must NOT re-enter same hypothesis+symbol
        second = engine.decide("BTC/USDT")
        assert second["action"] == "skip_position_guard"
        assert second["signal"] is None
        assert len(engine.open_positions) == 1
    print("PASS operation: expectancy>0 -> señal generada; position guard activo")


def test_failed_status_still_queryable_and_best_selection_ordering():
    """Low scientific_score degrades to failed but stays queryable; ordering by expectancy."""
    with tempfile.TemporaryDirectory() as tmp:
        candles = [[i, 100, 102, 99, 100 - i, 10] for i in range(50)]
        engine = make_engine(
            tmp,
            [
                '{"hypothesis_id": "hyp_failed_low_score", "symbol": "BTC/USDT",'
                ' "status": "failed", "expectancy": 0.05, "scientific_score": 0.4,'
                ' "parameters": {"lookback": 5}}',
                '{"hypothésis_id": "ignored"}',
                '{"hypothesis_id": "hyp_draft", "symbol": "BTC/USDT",'
                ' "status": "draft", "expectancy": 0.99}',
            ],
            candles,
        )
        best = engine.select_best_hypothesis("BTC/USDT")
        # draft excluded even with higher expectancy; failed included
        assert best["hypothesis_id"] == "hyp_failed_low_score"

        signal = engine.decide("BTC/USDT")
        assert signal["action"] == "entry"
        assert signal["side"] == "sell"  # closes bajan -> momentum negativo
    print("PASS statuses: failed consultable, draft excluido, dirección sell")


def run_all():
    test_abstention_all_nonpositive_expectancy()
    test_operation_positive_expectancy_generates_signal()
    test_failed_status_still_queryable_and_best_selection_ordering()
    print("\n3/3 decision engine tests passed")


if __name__ == "__main__":
    run_all()
