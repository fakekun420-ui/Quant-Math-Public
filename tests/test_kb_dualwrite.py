"""Bugfix post-graduacion: (1) dual-write PG+JSONL siempre en _save_hypothesis,
(2) carga inicial con PG mandando sobre el espejo JSONL."""
import json, os, sys, tempfile, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quant_math.decision_engine import DecisionEngine


class FakeKBPersistence:
    """Stub del adapter PG: graba saves y devuelve universo fijo."""
    saved = []

    def __init__(self, kb_path):
        FakeKBPersistence.saved = []
        self.kb_path = kb_path

    def save(self, record):
        FakeKBPersistence.saved.append(record)

    @staticmethod
    def load_all():
        return {
            "hyp_pg_top": {"hypothesis_id": "hyp_pg_top",
                            "symbol": "XRP/USDT", "status": "failed",
                            "strategy_type": "momentum",
                            "expectancy": 0.302,
                            "live_expectancy_updated_at": 99.0},
            "hyp_solo_pg": {"hypothesis_id": "hyp_solo_pg",
                             "symbol": "XRP/USDT", "status": "backtested",
                             "strategy_type": "momentum",
                             "expectancy": -0.02},
        }


def _install_fake_pg_module():
    mod = types.ModuleType(
        "quant_math.autonomous_research.adapters.postgres_kb")
    mod.KBPersistence = FakeKBPersistence
    sys.modules[mod.__name__] = mod


def _make(tmp, rows, use_postgres):
    kb = os.path.join(tmp, "kb.jsonl")
    with open(kb, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return DecisionEngine(
        symbols=["XRP/USDT"], kb_path=kb,
        state_dir=os.path.join(tmp, "state"),
        data_provider=lambda s: [[i, 100, 101, 99, 100 + i, 10]
                                 for i in range(50)],
        use_postgres=use_postgres), kb


def test_dual_write_writes_jsonl_even_with_storage():
    with tempfile.TemporaryDirectory() as tmp:
        eng, kb = _make(tmp, [{"hypothesis_id": "h0", "symbol": "XRP/USDT",
                               "status": "backtested",
                               "expectancy": 0.01}], use_postgres=False)
        eng.storage = FakeKBPersistence(tmp)
        rec = {"hypothesis_id": "h0", "symbol": "XRP/USDT",
               "status": "backtested", "expectancy": 0.42}
        before = sum(1 for _ in open(kb))
        eng._save_hypothesis(rec)
        after = sum(1 for _ in open(kb))
        assert len(FakeKBPersistence.saved) == 1      # fue a PG
        assert after == before + 1                    # Y al espejo jsonl
    print("PASS dual-write: PG y JSONL reciben el update")


def test_storage_boot_uses_full_pg_universe():
    """Con storage disponible, el arranque carga TODO el universo de PG
    (_load_jsonl delega en storage.load_all); sin PG caeria al espejo,
    por eso el dual-write mantiene el espejo completo."""
    modname = "quant_math.autonomous_research.adapters.postgres_kb"
    _install_fake_pg_module()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [{"hypothesis_id": "viejo_espejo", "symbol": "XRP/USDT",
                     "status": "backtested", "expectancy": 0.05}]
            eng, _ = _make(tmp, rows, use_postgres=True)
            assert eng.storage is not None
            top = eng.ranked_candidates("XRP/USDT")[0]["hypothesis_id"]
            assert top == "hyp_pg_top", top          # exp 0.302 manda
            assert eng.hypotheses["hyp_pg_top"]["expectancy"] == 0.302
            assert "hyp_solo_pg" in eng.hypotheses
    finally:
        sys.modules.pop(modname, None)
    print("PASS arranque con PG: universo completo de load_all")


if __name__ == "__main__":
    test_dual_write_writes_jsonl_even_with_storage()
    test_startup_loads_pg_over_mirror()
    print("\n2/2 kb dual-write tests passed")
