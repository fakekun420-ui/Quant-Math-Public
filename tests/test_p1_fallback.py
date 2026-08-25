"""P1: cuando el mejor candidato tiene posicion abierta, decide() cae al
siguiente mejor libre en lugar de quedarse en skip."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quant_math.decision_engine import DecisionEngine


def make(tmp, kb_rows, candles):
    kb = os.path.join(tmp, "kb.jsonl")
    with open(kb, "w") as fh:
        for r in kb_rows:
            fh.write(json.dumps(r) + "\n")
    return DecisionEngine(
        symbols=["XRP/USDT"], kb_path=kb,
        state_dir=os.path.join(tmp, "state"),
        data_provider=lambda s: candles, use_postgres=False)


def up():
    return [[i, 100, 101, 99, 100 + i, 10] for i in range(50)]


def test_fallback_to_next_best_when_best_open():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {"hypothesis_id": "best_open", "symbol": "XRP/USDT",
             "status": "backtested", "expectancy": 0.09,
             "scientific_score": 0.9},
            {"hypothesis_id": "second_free", "symbol": "XRP/USDT",
             "status": "backtested", "expectancy": 0.05,
             "scientific_score": 0.8},
        ]
        eng = make(tmp, rows, up())
        eng.open_positions["best_open:XRP/USDT"] = {
            "key": "best_open:XRP/USDT", "opened_at": 1.0,
            "side": "buy", "entry_price": 100.0}

        res = eng.decide("XRP/USDT")
        assert res["action"] == "entry", res
        assert res["hypothesis_id"] == "second_free"
        assert res["expectancy"] == 0.05
        assert eng.has_open_position("second_free", "XRP/USDT")
    print("PASS fallback: best abierto -> entra el segundo mejor")


def test_skip_contract_when_all_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "only_one", "symbol": "XRP/USDT",
                 "status": "backtested", "expectancy": 0.05,
                 "scientific_score": 0.9}]
        eng = make(tmp, rows, up())
        eng.open_positions["only_one:XRP/USDT"] = {
            "key": "only_one:XRP/USDT", "opened_at": 1.0,
            "side": "buy", "entry_price": 100.0}
        res = eng.decide("XRP/USDT")
        assert res["action"] == "skip_position_guard"
        assert res["hypothesis_id"] == "only_one"
    print("PASS contrato: unico candidato bloqueado -> skip_position_guard")


if __name__ == "__main__":
    test_fallback_to_next_best_when_best_open()
    test_skip_contract_when_all_blocked()
    print("\n2/2 p1 fallback tests passed")
