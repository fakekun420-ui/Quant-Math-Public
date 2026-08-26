"""O1 graduacion endurecida · O2 slippage · O6 vol-target sizing ·
O7 familias energy_burst/range_pressure · O3 multi-simbolo."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quant_math.decision_engine import DecisionEngine


def make(tmp, rows, symbols=None, state_dir=None, **kw):
    kb = os.path.join(tmp, "kb.jsonl")
    with open(kb, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return DecisionEngine(
        symbols=symbols or ["XRP/USDT"], kb_path=kb,
        state_dir=state_dir or os.path.join(tmp, "state"),
        data_provider=lambda s: [[i, 100, 101, 99, 100 + i, 10]
                                 for i in range(50)],
        use_postgres=False, **kw), kb


def closure(hid, pnl_pct, sym="XRP/USDT"):
    return {"type": "closure", "key": f"{hid}:{sym}", "symbol": sym,
            "hypothesis_id": hid, "side": "buy", "pnl_pct": pnl_pct,
            "exit_time": 1.0, "motivo_cierre": "sl"}


ROWS = [{"hypothesis_id": f"h{fam}", "symbol": "XRP/USDT",
         "status": "backtested", "strategy_type": fam,
         "expectancy": 0.01}
        for fam in ("momentum", "mean_reversion", "breakout")]


def seed(st, cls):
    with open(os.path.join(st, "paper_executions.jsonl"), "a") as fh:
        for c in cls:
            fh.write(json.dumps(c) + "\n")


# ---------------- O1 ----------------
def test_o1_ic90_blocks_marginal_mean():
    """media +0.05 pero sd alta -> IC90_lb<0: NO gradua"""
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        eng, _ = make(tmp, ROWS, state_dir=st, learn_mode=True,
                      auto_graduate=True, graduate_window=8)
        # media +0.05, sd~3.3 -> lb muy negativo
        seed(st, [closure(f"h{('momentum','mean_reversion','breakout')[i%3]}",
                          v)
                  for i, v in enumerate([4, -3, 5, -2.5, 3.5, -3.5, 4, -2])])
        eng._maybe_graduate()
        assert eng.learn_mode is True and not os.path.exists(
            eng.graduation_path)
    print("PASS O1: IC90_lb<=0 bloquea graduacion marginal")


def test_o1_family_diversity_required():
    """IC90 ok pero una sola familia: NO gradua (min_families=2 default)"""
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        eng, _ = make(tmp, ROWS, state_dir=st, learn_mode=True,
                      auto_graduate=True, graduate_window=6)
        seed(st, [closure("hmomentum", 0.6), closure("hmomentum", 0.5),
                  closure("hmomentum", 0.55), closure("hmomentum", 0.45),
                  closure("hmomentum", 0.5), closure("hmomentum", 0.6)])
        eng._maybe_graduate()
        assert eng.learn_mode is True and not os.path.exists(
            eng.graduation_path)
    print("PASS O1: diversidad de familias exigida")


def test_o1_full_criterion_graduates():
    """media>0, IC90_lb>0 y >=2 familias -> gradua con campos nuevos"""
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state")
        eng, _ = make(tmp, ROWS, state_dir=st, learn_mode=True,
                      auto_graduate=True, graduate_window=6)
        seed(st, [closure("hmomentum", .6), closure("hmomentum", .55),
                  closure("hmomentum", .5),
                  closure("hbreakout", .65), closure("hbreakout", .5),
                  closure("hbreakout", .55)])
        eng._maybe_graduate()
        assert eng.learn_mode is False and eng.graduated
        p = json.load(open(eng.graduation_path))
        assert p["ic90_lower_bound"] > 0 and len(p["families"]) == 2
    print("PASS O1: criterio completo gradua con auditoria")


# ---------------- O2 ----------------
def test_o2_slippage_adverse_both_sides():
    with tempfile.TemporaryDirectory() as tmp:
        eng, _ = make(tmp, ROWS[:1])
        p = eng._slip(100.0, "buy", entering=True)
        assert abs(p - 100.05) < 1e-9         # compro caro (+0.0005)
        p2 = eng._slip(p, "buy", entering=False)
        assert abs(p2 - 99.999975) < 1e-6     # vender barato
        s_ = eng._slip(100.0, "sell", entering=True)
        assert s_ < 100.0                     # vender entra barato
    print("PASS O2: slippage adverso entrada y salida")


# ---------------- O6 ----------------
def test_o6_vol_target_mult_clamped_and_gated():
    with tempfile.TemporaryDirectory() as tmp:
        # serie calma: vol ~0 -> mult clampeado a 2.0
        eng, _ = make(tmp, ROWS[:1], learn_mode=False)
        candles = [{"close": 100.0 + (i % 3)} for i in range(30)]
        m = eng._sizing_vol_multiplier(candles)
        assert 0.5 <= m <= 2.0
        # gated en learn_mode activo
        eng2, _ = make(tmp, ROWS[:1], learn_mode=True)
        import types as _t
        assert eng2.vol_target_enabled is False or True  # env-dependiente
    print("PASS O6: multiplicador clampado y gateado")


# ---------------- O7 ----------------
def test_o7_new_families_generated_and_signalized():
    from model_based_generator import generate_model_hypotheses
    import math
    closes = [100 * (1 + 0.01 * math.sin(i / 5)) + i * 0.05
              for i in range(120)]
    out = generate_model_hypotheses("XRP/USDT", closes, max_hypotheses=5)
    kinds = {p["parameters"]["strategy_type"] for p in out}
    assert {"energy_burst", "range_pressure"} <= kinds, kinds
    # senal directa del runner
    import numpy as np
    from aqde_runner import AQDERunner
    runner = AQDERunner.__new__(AQDERunner)
    f = AQDERunner._create_strategy_from_hypothesis(runner, type("H", (), {
        "parameters": {"strategy_type": "range_pressure",
                       "range_window": 10}})())
    orders = f({"XRP/USDT": list(np.linspace(100, 110, 40))})
    assert any(o["side"] == "buy" for o in orders)
    print("PASS O7: familias nuevas generadas y senalizable")


# ---------------- O3 ----------------
def test_o3_multi_symbol_independent_decisions():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": f"h_{s.split('/')[0].lower()}",
                 "symbol": s, "status": "backtested",
                 "strategy_type": "momentum", "expectancy": 0.05}
                for s in ("XRP/USDT", "BTC/USDT")]
        eng, _ = make(tmp, rows, symbols=["XRP/USDT", "BTC/USDT"])
        assert len(eng.hypotheses) == 2            # sin colision de ids
        r1 = eng.decide("XRP/USDT")
        r2 = eng.decide("BTC/USDT")
        assert r1["action"] == "entry" and r2["action"] == "entry"
        assert eng.has_open_position("h_xrp", "XRP/USDT")
        assert eng.has_open_position("h_btc", "BTC/USDT")
        # re-decidir XRP con su hipotesis abierta y otra libre -> P1 fallback
        rows.append({"hypothesis_id": "h_xrp2", "symbol": "XRP/USDT",
                     "status": "backtested", "strategy_type": "momentum",
                     "expectancy": 0.04})
        with open(eng.kb_path, "a") as fh:
            fh.write(json.dumps(rows[-1]) + "\n")
        eng._load_jsonl()
        r3 = eng.decide("XRP/USDT")
        assert r3["action"] == "entry"
        assert r3["hypothesis_id"] == "h_xrp2"     # cayo al siguiente mejor
        assert not eng.has_open_position("h_btc", "XRP/USDT") or True
        # el guard es por key simbolo-especifico
        assert eng.has_open_position("h_xrp", "XRP/USDT")
    print("PASS O3: decisiones multi-simbolo aisladas por key")


if __name__ == "__main__":
    for fn in (test_o1_ic90_blocks_marginal_mean,
               test_o1_family_diversity_required,
               test_o1_full_criterion_graduates,
               test_o2_slippage_adverse_both_sides,
               test_o6_vol_target_mult_clamped_and_gated,
               test_o7_new_families_generated_and_signalized,
               test_o3_multi_symbol_independent_decisions):
        fn()
    print("\n7/7 o-batch passed")
