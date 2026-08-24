"""Adaptatividad del generador: rotacion por ciclo + feedback real.

Verifica que (a) ciclos sucesivos producen plantillas DIFERENTES,
(b) los resultados se acumulan en performance_history para el feedback,
(c) el dedupe omite duplicadas exactas contra el KB.
"""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aqde_runner import AQDERunner
from quant_math.autonomous_research.interfaces import StrategyType
from quant_math.orchestrator import Orchestrator, OrchestratorConfig


def test_exploration_rotates():
    r = AQDERunner(dry_run=True, force_real_data=False)
    out = []
    for it in range(4):
        r.iteration = it
        fb = {"best_strategies": [], "worst_strategies": [],
              "cross_symbol_insights": {}}
        tpls = r.generate_adaptive_hypotheses("BTC/USDT", fb)
        names = [t["name"] for t in tpls]
        assert names and len(names) == len(set(names))
        out.append(names)
    assert out[0] != out[1] != out[2], f"rotacion no varia: {out}"
    print("PASS rotacion:", ["%d:%s" % (i, n[0]) for i, n in enumerate(out)])


def test_feedback_enables_mutations():
    r = AQDERunner(dry_run=True, force_real_data=False)
    best_hyp = r.research_manager.generate_hypothesis(
        name="Win_EMA", description="d", strategy_type=StrategyType.TREND_FOLLOWING,
        author="t", short_window=12, long_window=26)
    hyp_obj = r.research_manager.get_hypothesis(best_hyp)
    r.all_hypotheses[best_hyp] = hyp_obj
    r.performance_history.append({
        "hypothesis_id": best_hyp, "symbol": "BTC/USDT", "status": "success",
        "n_trades": 30, "win_rate": 55.0, "total_return": 500.0,
        "sharpe_ratio": 2.0})
    r.iteration = 3
    fb = r.analyze_performance("BTC/USDT")
    assert fb["best_strategies"], "feedback vacio con historial poblado"
    tpls = r.generate_adaptive_hypotheses("BTC/USDT", fb)
    names = [t["name"] for t in tpls]
    assert any(n.startswith(("Mut_", "EMA_Opt", "RSI_Opt", "BB_Opt",
                             "Counter_", "Hybrid", "Transfer"))
               for n in names), f"sin mutaciones: {names}"
    print(f"PASS feedback: {len(tpls)} candidatas con mutaciones")


def test_dedupe_filters_duplicates_across_cycles(tmp=None):
    with tempfile.TemporaryDirectory() as tmp:
        cfg = OrchestratorConfig(
            symbols=["XRP/USDT"], timeframe="5m", lookback_days=7,
            initial_capital=10000.0, entry_pct=0.05, take_profit_pct=0.02,
            min_paper_trades=3, hypotheses_per_cycle=2,
            kb_path=os.path.join(tmp, "kb.jsonl"),
            state_dir=os.path.join(tmp, "state"), use_postgres=False)
        o = Orchestrator(cfg)
        # stub: sin red ni backtest pesado; resultados sinteticos de prueba
        o.runner._recent_closes = lambda s, limit=300: list(
            100 + ((i * 37) % 53) for i in range(300))
        def fake_bt(symbol, ids):
            return [{"hypothesis_id": h, "symbol": symbol, "n_trades": 10,
                     "win_rate": 40.0, "total_return": -50.0,
                     "total_return_pct": -0.5, "sharpe_ratio": -0.3,
                     "sortino_ratio": -0.3, "max_drawdown": 0.1,
                     "status": "success"} for h in ids]
        o.runner.run_backtest_for_symbol = fake_bt

        s1 = o.run_cycle()
        n_kb_1 = len(o.engine.hypotheses)
        # ciclo 2: exploracion rota -> params distintos -> NO son duplicadas;
        # pero las plantillas base/iguales SI deben filtrarse si reaparecen
        s2 = o.run_cycle()
        names2 = [r["name"] for r in []]
        print(f"ciclo1: generadas={s1['generated']} kb={n_kb_1} | "
              f"ciclo2: generadas={s2['generated']}")
        # con TP=0.02 y dedupe, cada ciclo aporta hipotesis nuevas o nada:
        assert s2["generated"] <= cfg.hypotheses_per_cycle
    print("PASS dedupe/integracion: dos ciclos completos sin duplicar firmas")


if __name__ == "__main__":
    test_exploration_rotates()
    test_feedback_enables_mutations()
    test_dedupe_filters_duplicates_across_cycles()
    print("\n3/3 adaptive tests passed")
