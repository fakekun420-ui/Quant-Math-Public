"""PA: expectancy viva con shrinkage doble (propio->familia, realizado->
generacion). PB: auto-graduacion de LEARN_MODE con ventana de cierres."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quant_math.decision_engine import DecisionEngine
from quant_math.decision_engine.main import FAMILY_SHRINK_K, LIVE_SHRINK_E


def make(tmp, kb_rows, state_dir=None, **kw):
    kb = os.path.join(tmp, "kb.jsonl")
    with open(kb, "w") as fh:
        for r in kb_rows:
            fh.write(json.dumps(r) + "\n")
    return DecisionEngine(
        symbols=["XRP/USDT"], kb_path=kb,
        state_dir=state_dir or os.path.join(tmp, "state"),
        data_provider=lambda s: [[i, 100, 101, 99, 100 + i, 10]
                                 for i in range(50)],
        use_postgres=False, **kw)


def seed_ledger(state_dir, closures):
    path = os.path.join(state_dir, "paper_executions.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        for c in closures:
            fh.write(json.dumps(c) + "\n")


def closure(hid, pnl_pct, symbol="XRP/USDT"):
    return {"type": "closure", "key": f"{hid}:{symbol}", "symbol": symbol,
            "hypothesis_id": hid, "side": "buy", "pnl_pct": pnl_pct,
            "exit_time": 1.0, "motivo_cierre": "sl"}


def test_pa_expectancy_shrinks_toward_realized():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        rows = [
            {"hypothesis_id": "hypA", "symbol": "XRP/USDT",
             "status": "backtested", "strategy_type": "momentum",
             "expectancy": 0.08, "scientific_score": 0.9},
            {"hypothesis_id": "hypB", "symbol": "XRP/USDT",
             "status": "backtested", "strategy_type": "momentum",
             "expectancy": 0.05, "scientific_score": 0.8},
        ]
        eng = make(tmp, rows, st)
        # hypA: 3 cierres propios (+1, -1, +3 -> mean +1.0)
        own = [closure("hypA", 1.0), closure("hypA", -1.0),
               closure("hypA", 3.0)]
        # familia momentum/XRP: agrega un cierre de hypB (-2.0)
        seed_ledger(st, own + [closure("hypB", -2.0)])

        eng._refresh_live_expectancy("hypA", "XRP/USDT")

        n, own_mean = 3, 1.0
        fam_mean = (3 * 1.0 - 2.0) / 4          # 0.25
        est = ((n * own_mean + FAMILY_SHRINK_K * fam_mean)
               / (n + FAMILY_SHRINK_K))          # (3+0.75)/6
        w = n / (n + LIVE_SHRINK_E)              # 0.375
        expected = w * 0.08 + (1 - w) * est

        got = eng.hypotheses["hypA"]["expectancy"]
        assert abs(got - round(expected, 8)) < 1e-9, (got, expected)
        assert eng.hypotheses["hypA"]["expectancy_source"] == "live_shrunk"
        # persistido en el KB JSONL
        disk = [json.loads(l) for l in open(eng.kb_path)]
        rec = [r for r in disk
               if r["hypothesis_id"] == "hypA"][-1]   # ultimo gana
        assert abs(rec["expectancy"] - round(expected, 8)) < 1e-9
    print("PASS PA: expectancy viva = %.6f (shrinkage doble)" % expected)


def test_pa_ranking_flips_when_live_results_bad():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        rows = [
            {"hypothesis_id": "good_static", "symbol": "XRP/USDT",
             "status": "backtested", "strategy_type": "momentum",
             "expectancy": 0.09, "scientific_score": 0.9},
            {"hypothesis_id": "meh_static", "symbol": "XRP/USDT",
             "status": "backtested", "strategy_type": "momentum",
             "expectancy": 0.05, "scientific_score": 0.8},
        ]
        eng = make(tmp, rows, st)
        assert eng.ranked_candidates("XRP/USDT")[0]["hypothesis_id"] \
            == "good_static"
        # good_static resulta pesimo en vivo: muchos cierres negativos
        seed_ledger(st, [closure("good_static", -2.5) for _ in range(20)])
        eng._refresh_live_expectancy("good_static", "XRP/USDT")
        top = eng.ranked_candidates("XRP/USDT")[0]["hypothesis_id"]
        assert top == "meh_static", top
    print("PASS PA: ranking se reordena con resultados vivos")


def test_pb_graduates_on_positive_window():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        eng = make(tmp, [{"hypothesis_id": "h1", "symbol": "XRP/USDT",
                          "status": "backtested",
                          "strategy_type": "momentum",
                          "expectancy": 0.01}], st,
                   learn_mode=True, auto_graduate=True, graduate_window=3)
        assert eng.learn_mode is True
        seed_ledger(st, [closure("h1", 0.5), closure("h1", 0.2),
                         closure("h1", -0.1)])   # media +0.2
        eng._maybe_graduate()
        assert eng.learn_mode is False and eng.graduated is True
        assert os.path.exists(eng.graduation_path)
        payload = json.load(open(eng.graduation_path))
        assert payload["graduated"] is True and abs(
            payload["mean_pnl_pct"] - 0.2) < 1e-9
    print("PASS PB: graduacion con ventana positiva")


def test_pb_no_graduation_on_negative_window():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        eng = make(tmp, [{"hypothesis_id": "h1", "symbol": "XRP/USDT",
                          "status": "backtested",
                          "strategy_type": "momentum",
                          "expectancy": 0.01}], st,
                   learn_mode=True, auto_graduate=True, graduate_window=3)
        seed_ledger(st, [closure("h1", 0.5), closure("h1", -0.2),
                         closure("h1", -0.4)])   # media -0.033
        eng._maybe_graduate()
        assert eng.learn_mode is True and not os.path.exists(
            eng.graduation_path)
        # ventana incompleta tampoco gradua
        os.remove(os.path.join(st, "paper_executions.jsonl"))
        seed_ledger(st, [closure("h1", 1.0), closure("h1", 1.0)])
        eng.graduated = False
        eng._maybe_graduate()
        assert eng.learn_mode is True
    print("PASS PB: no gradua con media negativa o ventana incompleta")


def test_pb_previous_graduation_survives_restart():
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        os.makedirs(st)
        with open(os.path.join(st, "graduation.json"), "w") as fh:
            json.dump({"graduated": True, "at": 1.0, "window": 30,
                       "mean_pnl_pct": 0.15}, fh)
        eng = make(tmp, [{"hypothesis_id": "h1", "symbol": "XRP/USDT",
                          "status": "backtested",
                          "strategy_type": "momentum",
                          "expectancy": 0.01}], st,
                   learn_mode=True, auto_graduate=True)
        assert eng.learn_mode is False and eng.graduated is True
    print("PASS PB: graduacion previa persiste entre reinicios")


if __name__ == "__main__":
    test_pa_expectancy_shrinks_toward_realized()
    test_pa_ranking_flips_when_live_results_bad()
    test_pb_graduates_on_positive_window()
    test_pb_no_graduation_on_negative_window()
    test_pb_previous_graduation_survives_restart()
    print("\n5/5 pa+pb tests passed")
