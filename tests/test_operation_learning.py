"""SIS no supervisado + LEARN_MODE: clustering, recomendaciones, rachas,
cutoff de integracion y gate desactivado temporalmente."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.ml import feature_store as fs
from quant_math.ml.regime_learning import OperationLearningLoop


def write_ledger(state_dir, rows):
    path = os.path.join(state_dir, "paper_executions.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        for exit_time, sym, fam, pnl_pct, vol, fu in rows:
            hid = f"hyp_{sym.split('/')[0]}_{fam}_{int(exit_time)}"
            rec = {"type": "closure", "key": f"{hid}:{sym}",
                   "hypothesis_id": hid, "symbol": sym, "side": "buy",
                   "entry_price": 100, "exit_price": 100 * (1 + pnl_pct/100),
                   "quantity": 1.0, "pnl": pnl_pct, "pnl_pct": pnl_pct,
                   "entry_time": exit_time - 60, "exit_time": exit_time,
                   "motivo_cierre": "tp" if pnl_pct > 0 else "sl"}
            with open(os.path.join(state_dir, "kb_tmp"), "w") as _:
                pass
            kb_path = os.path.join(state_dir, "kb.jsonl")
            kb = {"hypothesis_id": hid, "symbol": sym,
                  "strategy_type": fam,
                  "parameters": {"donchian_window": 20,
                                 "_regime": {"vol_pct": vol,
                                             "forecast_up": bool(fu)}}}
            if not os.path.exists(kb_path):
                with open(kb_path, "w") as k:
                    k.write(json.dumps(kb) + "\n")
            else:
                cur = [json.loads(l) for l in open(kb_path)]
                if not any(x["hypothesis_id"] == hid for x in cur):
                    with open(kb_path, "a") as k:
                        k.write(json.dumps(kb) + "\n")
            fh.write(json.dumps(rec) + "\n")


def synth_rows():
    rows = []
    t = 1787500000
    for i in range(25):   # grupo ganador: vol alta + breakout
        rows.append((t + i * 120, "BTC/USDT", "breakout", 3.0 + i * .1, 85, True))
    for i in range(25):   # grupo perdedor: vol baja + mean_reversion
        rows.append((t + 5000 + i * 120, "ETH/USDT", "mean_reversion",
                     -2.0 - i * .1, 10, False))
    return rows


def build(tmp, extra=None):
    state = os.path.join(tmp, "state")
    os.makedirs(state, exist_ok=True)
    rows = synth_rows() + (extra or [])
    write_ledger(state, rows)
    loop = OperationLearningLoop(
        *_load_kb_and_args(state))
    return loop


def _load_kb_and_args(state):
    kb_path = os.path.join(state, "kb.jsonl")
    records = {}
    if os.path.exists(kb_path):
        with open(kb_path) as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    records[r["hypothesis_id"]] = r
    ledger = os.path.join(state, "paper_executions.jsonl")
    from quant_math.ml.feature_store import build_trade_dataset
    # reconstruir loop manual con dataset builder estandar
    loop = OperationLearningLoop.__new__(OperationLearningLoop)
    loop._fit(records, ledger, state)
    loop.kb_records = records
    return (records, ledger, state)


def test_collecting_mode_under_threshold():
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "state")
        os.makedirs(state)
        rows = [(1787500000 + i * 100, "BTC/USDT", "breakout", 1.0, 80, True)
                for i in range(5)]
        write_ledger(state, rows)
        records, ledger, st = _load_kb_and_args(state)[0], \
            os.path.join(state, "paper_executions.jsonl"), state
        loop = OperationLearningLoop(records, ledger, st)
        assert loop.mode == "collecting"
        assert loop.rank_families("BTC/USDT", {"vol_pct": 80}) == []
        assert loop.should_explore() is False
    print("PASS collecting: <30 ops -> sin efecto, sin crash")


def test_clusters_and_recommendation():
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "state")
        os.makedirs(state)
        rows = synth_rows()
        write_ledger(state, rows)
        records, ledger, st = _load_kb_and_args(state)[0], \
            os.path.join(state, "paper_executions.jsonl"), state
        loop = OperationLearningLoop(records, ledger, st)
        assert loop.mode == "active"
        assert len(loop.rows) == 50
        assert loop.cluster_stats, "sin clusters"
        best = max(loop.cluster_stats, key=lambda c: c["mean_pnl_pct"])
        assert best["mean_pnl_pct"] > 0
        fams = loop.rank_families("BTC/USDT",
                                  {"vol_pct": 85, "forecast_up": True})
        assert fams and fams[0] in ("breakout", "momentum"), fams
        print(f"PASS clusters/regimenes: {len(loop.cluster_stats)} clusters; "
              f"recomendada para BTC/vol-alta -> {fams[0]}")


def test_streak_triggers_explore():
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "state")
        os.makedirs(state)
        base = synth_rows()[:30]
        losses = [(1787510000 + i * 100, "SOL/USDT", "breakout",
                   -1.5 - i * .2, 40, False) for i in range(6)]
        write_ledger(state, base + losses)
        records, ledger, st = _load_kb_and_args(state)[0], \
            os.path.join(state, "paper_executions.jsonl"), state
        loop = OperationLearningLoop(records, ledger, st)
        assert loop.should_explore() is True
        print("PASS racha: 6 perdidas consecutivas -> exploracion")


def test_integration_cutoff_excludes_old_ops():
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "state")
        os.makedirs(state)
        rows = synth_rows()
        write_ledger(state, rows)
        cutoff = 1787500000 + 1500   # excluye los primeros cierres ganadores
        fs.set_integration_cutoff(state, cutoff)
        records, ledger, st = _load_kb_and_args(state)[0], \
            os.path.join(state, "paper_executions.jsonl"), state
        ds = fs.build_trade_dataset(records, ledger, state)
        pnls = [r["pnl_pct"] for r in ds]
        assert len(ds) < 50, f"cutoff no filtro nada ({len(ds)}/50)"
        assert 3.0 not in pnls, "el primer cierre (pre-cutoff) sigue en el dataset"
        assert any(p < 0 for p in pnls), "los post-cutoff deben seguir"
    print("PASS cutoff: pre-integracion excluido del dataset de aprendizaje")


def _kb(state):
    kb_path = os.path.join(state, "kb.jsonl")
    records = {}
    if os.path.exists(kb_path):
        with open(kb_path) as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    records[r["hypothesis_id"]] = r
    return (records,)


def test_learn_mode_gate_toggle(monkeypatch):
    from quant_math.decision_engine import DecisionEngine

    def make(learn):
        with tempfile.TemporaryDirectory() as tmp:
            kb = os.path.join(tmp, "kb.jsonl")
            with open(kb, "w") as fh:
                fh.write(json.dumps({"hypothesis_id": "hyp_neg",
                                     "symbol": "BTC/USDT",
                                     "status": "backtested",
                                     "expectancy": -0.05,
                                     "scientific_score": 0.9}))
            eng = DecisionEngine(
                symbols=["BTC/USDT"], kb_path=kb,
                state_dir=os.path.join(tmp, "st"),
                data_provider=lambda s: [[i, 100, 101, 99, 100+i, 10]
                                         for i in range(50)],
                use_postgres=False, learn_mode=learn)
            res = eng.decide("BTC/USDT")
            eng.close_position("hyp_neg", "BTC/USDT", motivo="manual",
                               exit_price=100)
            return res["action"], res.get("signal") is None

    monkeypatch.delenv("QUANTMATH_LEARN_MODE", raising=False)
    action_off, no_sig = make(False)
    assert (action_off, no_sig) == ("no_entry", True)
    action_on, _ = make(True)
    assert action_on == "entry"
    print(f"PASS LEARN_MODE: off->no_entry | on->entry (operando a perdida "
          f"para aprender)")


if __name__ == "__main__":
    test_collecting_mode_under_threshold()
    test_clusters_and_recommendation()
    test_streak_triggers_explore()
    test_integration_cutoff_excludes_old_ops()

    class M: 
        def __init__(self, v): self.v = v
        def setenv(self, *a): pass
        def delenv(self, *a, **k): pass
    test_learn_mode_gate_toggle(M(1))
    print("\n5/5 operation learning tests passed")
