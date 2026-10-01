"""Pipeline de validacion en el CAMINO REAL (2026-10-01).

Por que existe este fichero: el pipeline estaba entero y DESCONNECTADO.
`run_validation`, `run_monte_carlo` y `score_hypothesis` solo se llamaban
desde `AQDERunner.run()`, que solo se ejecuta con `python aqde_runner.py`;
el motor de produccion (`quant_math_bg.py` -> `orchestrator.run_forever`)
nunca entra ahi. La formula
`0,2*validacion + 0,5*backtest + 0,3*monte_carlo` no se habia ejecutado
jamas sobre una hipotesis real.

Los tests de aqui no comprueban que las fases existan (existen desde antes):
comprueban que se EJECUTEN por el camino que sigue produccion, y que una
hipotesis sin medida suficiente no se vuelva operable.
"""
import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtesting.backtester import BacktestResult, Trade
from quant_math.autonomous_research.adapters.postgres_kb import (
    JSONLKnowledgeBase,
)
from quant_math.autonomous_research.interfaces import StrategyType
from quant_math.risk.gate_policy import (
    DEFAULT_MIN_TRADES_CONCLUSION,
    resolve_scientific_policy,
)


# ----------------------------------------------------------------------
# Piezas reales, no dobles, para que el test mida el codigo de produccion
# ----------------------------------------------------------------------

def _trades(pnls, symbol="XRP/USDT"):
    """`Trade` del backtester real (el que `BacktestResult` lleva)."""
    return [
        Trade(trade_id=f"t{i}", symbol=symbol, side="long", quantity=1,
              entry_price=100.0, exit_price=100.0 + pnl, pnl=float(pnl),
              pnl_pct=float(pnl) / 100.0, hold_duration=60.0,
              entry_time=1_700_000_000.0 + i * 60, exit_time=1_700_000_060.0 + i * 60,
              commission=0.0)
        for i, pnl in enumerate(pnls)
    ]


def _bt_result(pnls):
    """`BacktestResult` real, con el PnL POR OPERACION en `trades`."""
    pnls = np.asarray(pnls, dtype=float)
    wins = int((pnls > 0).sum())
    n = len(pnls)
    return BacktestResult(
        initial_capital=10000.0,
        final_capital=10000.0 + float(pnls.sum()),
        total_return=float(pnls.sum()),
        total_return_pct=float(pnls.sum()) / 100.0,
        sharpe_ratio=1.2, sortino_ratio=1.4, max_drawdown=0.05,
        annualized_volatility=0.2, num_trades=n,
        win_rate=(wins / n * 100.0) if n else 0.0,
        avg_win=float(pnls[pnls > 0].mean()) if wins else 0.0,
        avg_loss=float(pnls[pnls < 0].mean()) if (n - wins) else 0.0,
        profit_factor=1.5, trades=_trades(pnls),
        equity_curve=[(1_700_000_000.0 + i, 10000.0 + float(pnls[:i + 1].sum()))
                      for i in range(n)],
    )


def _pnls_sin_edge(n, seed=11):
    """Serie larga con edge NULO: +-1 se anula,win_rate 50%,PnL ~0."""
    rng = np.random.RandomState(seed)
    return list(rng.choice([-1.0, 1.0], size=n))


def _pnls_con_edge(n, gain=0.5, seed=3):
    """Serie larga con edge real: media positiva y desviacion parecida."""
    rng = np.random.RandomState(seed)
    return list(rng.normal(gain, 1.0, n))


def _manager(tmp, monte_carlo_engine=None, **kwargs):
    """ResearchManager con KB real y el motor de Monte Carlo REAL.

    El motor es el metodo del adapter (`simulate_distribution`), invocado sin
    construir el adapter entero para no abrir el exchange. Es el MISMO codigo
    que corre en produccion.
    """
    from quant_math.autonomous_research.agents.research_manager import (
        ResearchManager,
    )
    if monte_carlo_engine is None:
        from quant_math.autonomous_research.adapters.quant_math_adapter import (
            QuantMathAdapter,
        )
        monte_carlo_engine = QuantMathAdapter.__new__(QuantMathAdapter)

    class _NoBacktest:
        """Puerta que NO puede backtestear: si el pipeline lo tocara, falla."""
        def run_backtest(self, *a, **k):
            raise AssertionError(
                "el pipeline NO puede lanzar un backtest propio: se alimenta "
                "del que ya se ha hecho")

    class _Passthrough:
        def calculate_win_rate(self, trades):
            return 50.0

        def test_significance(self, *a, **k):
            return 1.0

    class _NoRisk:
        pass

    rm = ResearchManager(
        knowledge_base=JSONLKnowledgeBase(
            os.path.join(tmp, "aqde_kb.jsonl")),
        backtest_engine=_NoBacktest(),
        monte_carlo_engine=monte_carlo_engine,
        statistical_validator=_Passthrough(),
        risk_manager=_NoRisk(),
        **kwargs,
    )
    return rm


def _hyp(rm, name="H", **params):
    return rm.generate_hypothesis(
        name=name, description="t",
        strategy_type=StrategyType.CUSTOM, author="test",
        symbol="XRP/USDT", **params)


# ----------------------------------------------------------------------
# 1. Las tres fases se ejecutan por el camino REAL
# ----------------------------------------------------------------------

def test_score_hypothesis_is_called_on_the_real_path():
    """CAZA EL BUG: si `score_hypothesis` deja de correr en el camino real,
    este test falla. Antes del arreglo el score publicado era el 0,098 de
    reserva de `_result_to_kb_record` porque la fase nunca se ejecutaba."""
    from quant_math.orchestrator import Orchestrator, OrchestratorConfig

    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(tmp, "kb.jsonl")
        cfg = OrchestratorConfig(
            symbols=["XRP/USDT"], timeframe="5m", lookback_days=7,
            initial_capital=10000.0, entry_pct=0.05, take_profit_pct=0.02,
            min_paper_trades=3, hypotheses_per_cycle=1,
            kb_path=kb, state_dir=os.path.join(tmp, "st"), use_postgres=False)
        o = Orchestrator(cfg)
        rm = o.runner.research_manager

        # Espia: cuenta las llamadas a la fase de puntuacion.
        llamadas = []
        original = rm.score_hypothesis

        def espia(hid):
            llamadas.append(hid)
            return original(hid)
        rm.score_hypothesis = espia

        hid = _hyp(rm, name="Real")
        o.runner.all_hypotheses[hid] = rm.get_hypothesis(hid)
        pnls = _pnls_con_edge(200)

        def fake_create(symbol, iteration):
            return [hid]

        def fake_backtest(symbol, hypothesis_ids):
            # Se comporta como `run_backtest_for_symbol`: deja el resultado
            # en el manager, que es de donde beben las tres fases.
            rm.results[hid] = _bt_result(pnls)
            return [{"hypothesis_id": hid, "symbol": symbol,
                     "n_trades": len(pnls), "win_rate": 55.0,
                     "total_return": float(np.sum(pnls)),
                     "total_return_pct": float(np.sum(pnls)) / 100.0,
                     "sharpe_ratio": 1.2, "sortino_ratio": 1.4,
                     "max_drawdown": 0.05, "status": "success"}]

        o.runner.create_hypotheses_for_symbol = fake_create
        o.runner.run_backtest_for_symbol = fake_backtest

        records = o._generate_and_backtest_symbol(
            "XRP/USDT", 1, {}, 5, )

        assert llamadas == [hid], (
            "score_hypothesis NO se llamo en el camino real: el pipeline sigue "
            f"desconectado (llamadas={llamadas})")
        assert len(records) == 1, records
        rec = records[0]
        # El score publicado sale de la formula con los TRES componentes
        # reales, no del 0,098 de reserva que se ponia cuando
        # `hyp.scientific_score` valia 0,0 porque las fases no corrian.
        hyp = rm.get_hypothesis(hid)
        bt = rm._calculate_backtest_score(rm.results[hid])
        mc_mean = rm.monte_carlo_verdicts[hid]["mean"]
        esperado = (0.2 * hyp.validation_score + 0.5 * bt + 0.3 * mc_mean)
        assert rec["scientific_score"] == hyp.scientific_score
        assert abs(rec["scientific_score"] - esperado) < 1e-12, (
            rec["scientific_score"], esperado)
        assert rec["monte_carlo_mean"] == mc_mean
        assert rec["scientific_score"] > 0.098, rec["scientific_score"]
        # El veredicto viaja con el registro.
        assert rec["scientifically_validated"] is True, rec["scientific_reasons"]
        assert rec["statistical_significance"] is not None
        assert rec["monte_carlo_conclusive"] is True
        assert rec["min_trades_conclusion"] == DEFAULT_MIN_TRADES_CONCLUSION
        # `status` y "operable" ya NO son lo mismo, y por diseño: el corte del
        # 0,6 (congelado) deja el status en `failed`, pero `failed` esta en
        # QUERYABLE_STATUSES, luego el status nunca decidio operabilidad. Quien
        # decide es el veredicto de las tres fases.
        assert rec["status"] == "failed", rec["status"]
        assert rec["scientifically_validated"] is True
        print(f"PASS camino real: score={rec['scientific_score']:.4f} "
              f"p={rec['statistical_significance']:.5f} "
              f"status={rec['status']} operable={rec['scientifically_validated']}")


def test_pipeline_does_not_rerun_the_backtest():
    """El pipeline bebe del backtest YA hecho. Si algo lo re-ejecutara (que es
    lo que hacia `execute_workflow`, bajando datos otra vez y pisando
    `self.results`), el MC y el score serian de OTRO backtest."""
    from quant_math.autonomous_research.agents.research_manager import (
        ResearchManager,
    )
    with tempfile.TemporaryDirectory() as tmp:
        rm = _manager(tmp)
        hid = _hyp(rm)
        original = _bt_result(_pnls_con_edge(120))
        rm.results[hid] = original
        rm.run_validation(hid)   # la fase 1 antes del MC, como en el pipeline
        rm.evaluate_hypothesis(hid)
        assert rm.results[hid] is original, (
            "el pipeline cambio el resultado del backtest: el MC y el score "
            "no salieron del backtest que se uso")


# ----------------------------------------------------------------------
# 2. El umbral declarado se APLICA
# ----------------------------------------------------------------------

def test_monte_carlo_below_min_trades_does_not_conclude():
    """Con menos operaciones que el minimo declarado, el MC NO da numero."""
    with tempfile.TemporaryDirectory() as tmp:
        rm = _manager(tmp)
        hid = _hyp(rm)
        pnls = _pnls_con_edge(7)
        rm.results[hid] = _bt_result(pnls)
        rm.run_validation(hid)
        rm.run_statistical_validation(hid)
        mc = rm.run_monte_carlo(hid, n_iterations=200)

        veredicto = rm.monte_carlo_verdicts[hid]
        assert veredicto["conclusive"] is False
        assert veredicto["n_trades"] == 7
        assert veredicto["min_trades"] == DEFAULT_MIN_TRADES_CONCLUSION
        assert str(DEFAULT_MIN_TRADES_CONCLUSION) in veredicto["reason"]
        # El numero devuelto no se inventa: es la forma vacia.
        assert mc.mean == 0.0 and mc.lower_bound == 0.0
        assert getattr(mc, "inconclusive", False) is True
        # Y la significancia tampoco concluye con 7 operaciones.
        assert rm.statistical_results[hid]["conclusive"] is False
        print(f"PASS MC sin conclusion: n=7 < {DEFAULT_MIN_TRADES_CONCLUSION} "
              f"-> motivo={veredicto['reason']}")


def test_monte_carlo_concludes_above_min_trades_and_is_reproducible():
    """Por encima del minimo SI conclude, y da lo MISMO en dos llamadas.

    El determinismo importa: `simulate_distribution` usa el `np.random` global
    y el pipeline corre en paralelo por simbolo. Sin sembrar de forma
    derivada, el mismo backtest daria un CI distinto en cada ciclo.
    """
    with tempfile.TemporaryDirectory() as tmp:
        rm = _manager(tmp)
        hid = _hyp(rm)
        pnls = _pnls_con_edge(150, gain=0.6)
        rm.results[hid] = _bt_result(pnls)
        rm.run_validation(hid)
        mc1 = rm.run_monte_carlo(hid, n_iterations=500)
        mc2 = rm.run_monte_carlo(hid, n_iterations=500)
        veredicto = rm.monte_carlo_verdicts[hid]
        assert veredicto["conclusive"] is True
        assert veredicto["mean"] > 0.0
        assert mc1.mean == mc2.mean, (mc1.mean, mc2.mean)
        assert mc1.lower_bound == mc2.lower_bound
        print(f"PASS MC concluyente: n=150 mean={mc1.mean:.5f} "
              f"CI95=[{mc1.lower_bound:.5f},{mc1.upper_bound:.5f}] "
              f"reproducible={mc1.mean == mc2.mean}")


def test_inconclusive_monte_carlo_does_not_feed_the_score():
    """El pondero de Monte Carlo es 0,3*monte_carlo: si la fase no
    concluye, su contribucion es 0 y no su numero."""
    with tempfile.TemporaryDirectory() as tmp:
        rm = _manager(tmp)
        pnls = _pnls_con_edge(7, gain=3.0)   # edge enorme, pero n=7
        hid_corta = _hyp(rm, name="Corta")
        rm.results[hid_corta] = _bt_result(pnls)
        rm.run_validation(hid_corta)
        rm.run_statistical_validation(hid_corta)
        rm.run_monte_carlo(hid_corta, n_iterations=500)
        score_corta = rm.score_hypothesis(hid_corta)

        hid_larga = _hyp(rm, name="Larga")
        rm.results[hid_larga] = _bt_result(_pnls_con_edge(150, gain=0.6))
        rm.run_validation(hid_larga)
        rm.run_statistical_validation(hid_larga)
        rm.run_monte_carlo(hid_larga, n_iterations=500)
        score_larga = rm.score_hypothesis(hid_larga)

        assert score_corta["monte_carlo_score"] == 0.0
        assert score_corta["monte_carlo_conclusive"] is False
        esperado = (0.2 * score_corta["validation_score"]
                    + 0.5 * score_corta["backtest_score"])
        assert abs(score_corta["scientific_score"] - esperado) < 1e-12, (
            score_corta["scientific_score"], esperado)
        assert score_larga["monte_carlo_conclusive"] is True
        print(f"PASS score sin MC: score={score_corta['scientific_score']:.4f} "
              f"= 0,2*val + 0,5*bt (sin el 0,3*mc)")


# ----------------------------------------------------------------------
# 3. El comportamiento que se pedia: no concluyente NO es operable
# ----------------------------------------------------------------------

def test_many_trades_with_null_significance_is_not_operable():
    """200 operaciones, win_rate 50%, PnL esperado 0: NO es operable.

    Antes esto SI era operable con solo `expectancy > 0`, y el
    `scientific_score` era un 0,098 inventado que no significaba nada.
    """
    from quant_math.orchestrator import Orchestrator, OrchestratorConfig
    from quant_math.risk.gate_policy import (
        scientific_block_reason,
    )

    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(tmp, "kb.jsonl")
        cfg = OrchestratorConfig(
            symbols=["XRP/USDT"], timeframe="5m", lookback_days=7,
            initial_capital=10000.0, entry_pct=0.05, take_profit_pct=0.02,
            min_paper_trades=3, hypotheses_per_cycle=1,
            kb_path=kb, state_dir=os.path.join(tmp, "st"), use_postgres=False)
        o = Orchestrator(cfg)
        rm = o.runner.research_manager
        hid = _hyp(rm, name="SinEdge")
        o.runner.all_hypotheses[hid] = rm.get_hypothesis(hid)

        pnls = _pnls_sin_edge(200)
        assert abs(float(np.mean(pnls))) < 0.5, float(np.mean(pnls))
        rm.results[hid] = _bt_result(pnls)
        o.runner.create_hypotheses_for_symbol = lambda s, i: [hid]
        o.runner.run_backtest_for_symbol = lambda s, ids: [{
            "hypothesis_id": hid, "symbol": s, "n_trades": len(pnls),
            "win_rate": 50.0, "total_return": float(np.sum(pnls)),
            "total_return_pct": float(np.sum(pnls)) / 100.0,
            "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.1,
            "status": "success"}]

        records = o._generate_and_backtest_symbol("XRP/USDT", 1, {}, 5)
        rec = records[0]
        assert rec["n_trades"] == 200
        assert rec["monte_carlo_conclusive"] is True, rec  # hay operaciones de sobra
        # El p es alto: 200 operaciones no compran un edge que no existe.
        assert rec["statistical_significance"] > 0.05, rec
        assert rec["scientifically_validated"] is False
        assert any("significancia" in m for m in rec["scientific_reasons"]), rec

        # Y el motor NO la ofrece como candidata, ni aunque su expectancy
        # sea positiva (que es el caso, un pelo).
        engine = o.engine
        engine.hypotheses[hid] = dict(rec)
        antes = len(engine.ranked_candidates("XRP/USDT"))
        assert hid not in [h["hypothesis_id"]
                           for h in engine.ranked_candidates("XRP/USDT")]
        assert engine.select_best_hypothesis("XRP/USDT") is None
        assert antes == 0, antes
        # Motivo legible: no un "no" mudo.
        assert "significancia" in (
            scientific_block_reason(rec) or "no deberia llegar aqui")
        print(f"PASS sin significancia no opera: n=200 p="
              f"{rec['statistical_significance']:.4f} expectancy="
              f"{rec['expectancy']:+.5f} motivos={rec['scientific_reasons']}")


def test_positive_significance_is_operable():
    """El otro lado: con operaciones suficientes Y edge real, SÍ opera. Sin
    esto el gate seria un no-op y habria pasado desapercibido."""
    from quant_math.orchestrator import Orchestrator, OrchestratorConfig

    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(tmp, "kb.jsonl")
        cfg = OrchestratorConfig(
            symbols=["XRP/USDT"], timeframe="5m", lookback_days=7,
            initial_capital=10000.0, entry_pct=0.05, take_profit_pct=0.02,
            min_paper_trades=3, hypotheses_per_cycle=1,
            kb_path=kb, state_dir=os.path.join(tmp, "st"), use_postgres=False)
        o = Orchestrator(cfg)
        rm = o.runner.research_manager
        hid = _hyp(rm, name="ConEdge")
        o.runner.all_hypotheses[hid] = rm.get_hypothesis(hid)

        pnls = _pnls_con_edge(200, gain=0.8, seed=5)
        rm.results[hid] = _bt_result(pnls)
        o.runner.create_hypotheses_for_symbol = lambda s, i: [hid]
        o.runner.run_backtest_for_symbol = lambda s, ids: [{
            "hypothesis_id": hid, "symbol": s, "n_trades": len(pnls),
            "win_rate": 60.0, "total_return": float(np.sum(pnls)),
            "total_return_pct": float(np.sum(pnls)) / 100.0,
            "sharpe_ratio": 1.0, "sortino_ratio": 1.0, "max_drawdown": 0.1,
            "status": "success"}]

        rec = o._generate_and_backtest_symbol("XRP/USDT", 1, {}, 5)[0]
        assert rec["statistical_significance"] < 0.05, rec
        assert rec["scientifically_validated"] is True, rec["scientific_reasons"]
        engine = o.engine
        engine.hypotheses[hid] = dict(rec)
        assert engine.select_best_hypothesis("XRP/USDT") is not None
        print(f"PASS con significancia opera: p={rec['statistical_significance']:.6f} "
              f"score={rec['scientific_score']:.4f}")


def test_learn_mode_does_not_bypass_the_scientific_gate():
    """`learn_mode` salta el gate de expectancy, no el cientifico.

    MEDIDO: `quant_math_bg.py:119` y `quant_math/cli/main.py:307` ponen
    `QUANTMATH_LEARN_MODE=1` por defecto, o sea que en produccion learn_mode
    esta ENCENDIDO. Si el gate cientifico lo respetara, no filtraria nada en
    produccion y todo este trabajo habria sido un no-op.
    """
    from quant_math.decision_engine.main import DecisionEngine
    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(tmp, "kb.jsonl")
        with open(kb, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "hypothesis_id": "h_nula", "symbol": "XRP/USDT",
                "status": "backtested", "expectancy": -5.0,
                "scientific_score": 0.09, "n_trades": 200, "win_rate": 50.0,
                "scientifically_validated": False,
                "scientific_reasons": ["significancia: p=0.42>=0,05"],
                "parameters": {}}) + "\n")
            fh.write(json.dumps({
                "hypothesis_id": "h_buena", "symbol": "XRP/USDT",
                "status": "backtested", "expectancy": 0.5,
                "scientific_score": 0.7, "n_trades": 200, "win_rate": 60.0,
                "scientifically_validated": True, "scientific_reasons": [],
                "parameters": {}}) + "\n")
        eng = DecisionEngine(
            symbols=["XRP/USDT"], kb_path=kb, state_dir=tmp, use_postgres=False,
            learn_mode=True)
        assert eng.learn_mode is True
        ids = [h["hypothesis_id"] for h in eng.ranked_candidates("XRP/USDT")]
        assert ids == ["h_buena"], ids
        # Y con veredicto negativo sigue fuera, learn_mode o no.
        assert eng.scientifically_operable(
            {"hypothesis_id": "x", "scientifically_validated": False,
             "scientific_reasons": ["significancia: p=0,42"]})[0] is False
        assert eng.scientifically_operable(
            {"hypothesis_id": "y", "scientifically_validated": True})[0] is True
        print("PASS learn_mode no salta el gate cientifico: "
              f"candidatas={ids}")


def test_legacy_rows_are_not_silently_deleted_and_migrate():
    """Las filas publicadas ANTES del pipeline no tienen veredicto.

    Con `strict_legacy` apagado conservan la semantica anterior (borrarlas
    todas seria parar el motor de golpe); cada una recibe veredicto en cuanto
    su firma se re-backtestea. Con `strict_legacy` encendido cierran el paso.
    """
    from quant_math.risk.gate_policy import scientific_block_reason
    legacy = {"hypothesis_id": "old", "status": "backtested", "expectancy": 0.4}
    assert scientific_block_reason(legacy) is None
    assert scientific_block_reason(legacy, strict_legacy=True) == "sin_pipeline"
    policy = resolve_scientific_policy()
    assert policy["require"] is True, policy
    assert policy["min_trades"] == DEFAULT_MIN_TRADES_CONCLUSION
    print("PASS legado: sin veredicto conserva semantica; strict lo cierra")


def test_gate_switch_can_be_turned_off_to_compare():
    """El interruptor existe para poder comparar antes/despues sin tocar el
    exchange. Con el gate apagado, una hipotesis no validada sigue
    apareciendo en el ranking (que es justo el 'antes')."""
    from quant_math.decision_engine.main import DecisionEngine
    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(tmp, "kb.jsonl")
        rec = {"hypothesis_id": "h1", "symbol": "XRP/USDT",
               "status": "backtested", "expectancy": 0.5,
               "scientific_score": 0.09, "n_trades": 200, "win_rate": 50.0,
               "scientifically_validated": False,
               "scientific_reasons": ["significancia: p=0,42"],
               "parameters": {}}
        with open(kb, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        apagado = DecisionEngine(symbols=["XRP/USDT"], kb_path=kb,
                                 state_dir=tmp, use_postgres=False,
                                 require_scientific_validation=False)
        assert apagado.select_best_hypothesis("XRP/USDT") is not None
        encendido = DecisionEngine(symbols=["XRP/USDT"], kb_path=kb,
                                   state_dir=tmp, use_postgres=False,
                                   require_scientific_validation=True)
        assert encendido.select_best_hypothesis("XRP/USDT") is None
        print("PASS interruptor: apagado=1 candidata, encendido=0")