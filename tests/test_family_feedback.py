"""Opcion B: feedback agregado por FAMILIA x SIMBOLO.

Las keys rotan (cada una con 1 operacion) pero la familia acumula -> el
feedback se entrega al cruzar multiplos del umbral, sin tocar el contrato
por-key ni el gate.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quant_math.decision_engine import DecisionEngine


def make(tmp, candles, tp=0.02, learn=True):
    return DecisionEngine(
        symbols=["XRP/USDT"],
        kb_path=os.path.join(tmp, "kb.jsonl"),
        state_dir=os.path.join(tmp, "state"),
        data_provider=lambda s: candles,
        use_postgres=False,
        take_profit_pct=tp,
        learn_mode=learn,
    )


def seed_hyp(tmp, hid, family_str="mean_reversion", expectancy=0.05):
    kb = os.path.join(tmp, "kb.jsonl")
    with open(kb, "a") as fh:
        fh.write(json.dumps({"hypothesis_id": hid, "symbol": "XRP/USDT",
                             "status": "backtested",
                             "strategy_type": family_str,
                             "expectancy": expectancy,
                             "scientific_score": 0.9,
                             "parameters": {"lookback": 5}}) + "\n")


def flat(price):
    return [[i, price, price, price, price, 10] for i in range(50)]


def test_family_feedback_fires_despite_key_rotation():
    """3 cierres de la MISMA familia (keys rotando o no): la familia llega a
    3 ops -> feedback agregado entregado al KB."""
    with tempfile.TemporaryDirectory() as tmp:
        seed_hyp(tmp, "famX")                       # sembrar ANTES del engine
        eng = make(tmp, flat(1.50))
        for i, price in enumerate((1.54, 1.55, 1.56)):
            sig = eng.decide("XRP/USDT")
            assert sig["action"] == "entry", (i, sig)
            c = eng.close_position("famX", "XRP/USDT", motivo="sl",
                                   exit_price=price)
            assert c["motivo_cierre"] == "sl"

        assert len(eng._family_ops("mean_reversion", "XRP/USDT")) == 3
        delivered = eng._maybe_deliver_family_feedback(
            "XRP/USDT", family="mean_reversion")
        assert delivered and delivered[0][0] == "mean_reversion"
        assert delivered[0][1] == 3

        with open(os.path.join(tmp, "kb.jsonl")) as fh:
            recs = [json.loads(l) for l in fh]
        marked = [r for r in recs
                  if r.get("feedback_family") == "mean_reversion"]
        assert len(marked) >= 1
        for r in marked:
            assert r["feedback_family_ops"] == 3
            assert r["feedback_family_wins"] == 0
            assert r["feedback_family_mean_pnl_pct"] <= 0
        print(f"PASS familia: 3 ops acumuladas pese a rotacion "
              f"(mean={marked[0]['feedback_family_mean_pnl_pct']:.3f}%)")


def test_bucket_multiple_delivers_again():
    """n=3 entrega; n=6 vuelve a entregar (bucket 2)."""
    with tempfile.TemporaryDirectory() as tmp:
        seed_hyp(tmp, "famY")
        eng = make(tmp, flat(1.50))
        for i, price in enumerate((1.54, 1.55, 1.56, 1.57, 1.58, 1.59)):
            eng.decide("XRP/USDT")
            eng.close_position("famY", "XRP/USDT", motivo="sl",
                               exit_price=price)
            if i == 2:
                d1 = eng._maybe_deliver_family_feedback(
                    "XRP/USDT", family="mean_reversion")
                assert d1 and d1[0][1] == 3
        d2 = eng._maybe_deliver_family_feedback("XRP/USDT",
                                                family="mean_reversion")
        assert d2 and d2[0][1] == 6
        print("PASS buckets: entrega en n=3 y nuevamente en n=6")


def test_per_key_contract_untouched():
    """El contrato original por-key (min=3) NO cambia: con 1 op no entrega."""
    with tempfile.TemporaryDirectory() as tmp:
        eng = make(tmp, flat(1.50))
        seed_hyp(tmp, "solo1")
        eng.decide("XRP/USDT")
        eng._maybe_deliver_feedback({"hypothesis_id": "solo1",
                                     "expectancy": -0.02}, "XRP/USDT")
        with open(os.path.join(tmp, "kb.jsonl")) as fh:
            rec = [json.loads(l) for l in fh][0]
        assert rec.get("feedback_paper_trades") is None
    print("PASS contrato por-key intacto: 1 op < min_paper_trades(3)")


if __name__ == "__main__":
    test_family_feedback_fires_despite_key_rotation()
    test_per_key_contract_untouched()
    test_bucket_multiple_delivers_again()
    print("\n3/3 family feedback tests passed")
