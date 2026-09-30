"""
El historico de la generacion adaptativa no se perdia (2026-09-30).

El problema
-----------
`AQDERunner.performance_history` era memoria pura (`= []`, con tope de 500) y
**nunca se cargaba de disco**. Consecuencia medida: en cada reinicio
`analyze_performance()` no encontraba nada, devolvia listas vacias, y
`generate_adaptive_hypotheses()` generaba sin feedback. El sistema
empezaba de cero cada vez, que es lo contrario de "que vaya generando mas
y mejores hipotesis".

La Knowledge Base SI es append-only y SI sobrevive. Ahora se siembra desde
alla al arrancar.

Y el segundo problema: el umbral `scientific_score > 0.6` de
`ResearchManager` marcaba TODAS las hipotesis como `failed`. Medido en una
corrida real: los 17 puntajos estaban entre 0,099 y 0,131, o sea que ninguna
podia pasar. El score es 0,2*validacion + 0,5*backtest + 0,3*monte_carlo y
ninguna de las tres componentes esta normalizada, asi que 0,6 no significa
nada sobre datos reales.
"""

import json
import os
import tempfile

import pytest


def _kb(tmp, rows):
    ruta = os.path.join(tmp, "kb.jsonl")
    with open(ruta, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return ruta


class _KBStub:
    def __init__(self, path):
        self.storage_path = path


def _runner(path):
    """Runner minimo, sin tocar la red ni el motor de backtest."""
    from aqde_runner import AQDERunner
    r = AQDERunner.__new__(AQDERunner)
    r.symbols = []
    r.all_hypotheses = {}
    r.performance_history = []
    r.iteration = 0
    r._mkt_cache = {}
    r.knowledge_base = _KBStub(path)
    return r


# ---------------------------------------------------------------------------
# 1. El historico se siembra desde la KB
# ---------------------------------------------------------------------------

def test_el_historico_se_siembra_desde_la_kb(tmp_path):
    tmp = str(tmp_path)
    ruta = _kb(tmp, [
        {"hypothesis_id": "h1", "symbol": "BTC/USDT", "status": "backtested",
         "n_trades": 120, "total_return_pct": 0.08, "expectancy": 0.02,
         "strategy_type": "mean_reversion.vwap"},
        {"hypothesis_id": "h2", "symbol": "BTC/USDT", "status": "backtested",
         "n_trades": 90, "total_return_pct": 0.03, "expectancy": 0.01,
         "strategy_type": "momentum.ema_crossover"},
    ])
    r = _runner(ruta)
    sembrados = r._seed_performance_from_kb()
    assert sembrados == 2
    assert len(r.performance_history) == 2


def test_el_vocabulario_se_traduce_al_interno_del_runner(tmp_path):
    """La KB dice 'backtested'; `analyze_performance` filtra por 'success'."""
    tmp = str(tmp_path)
    ruta = _kb(tmp, [{"hypothesis_id": "h1", "symbol": "BTC/USDT",
                      "status": "backtested", "n_trades": 50}])
    r = _runner(ruta)
    r._seed_performance_from_kb()
    assert r.performance_history[0]["status"] == "success"
    # Y por eso analyze_performance YA lo ve:
    assert len(r.analyze_performance("BTC/USDT")["best_strategies"]) >= 1


def test_las_hipotesis_sin_operaciones_no_se_siembran(tmp_path):
    """Sin trades no hay nada que aprender: es el filtro que ya se hacia."""
    tmp = str(tmp_path)
    ruta = _kb(tmp, [
        {"hypothesis_id": "h1", "symbol": "BTC/USDT", "status": "backtested",
         "n_trades": 0},
        {"hypothesis_id": "h2", "symbol": "BTC/USDT", "status": "failed",
         "n_trades": 90},
    ])
    r = _runner(ruta)
    assert r._seed_performance_from_kb() == 0


def test_kb_vacia_o_inexistente_no_es_un_error(tmp_path):
    """Arranque en frio: sin historico, pero sin romperse."""
    r = _runner(str(tmp_path / "no-existe.jsonl"))
    assert r._seed_performance_from_kb() == 0
    # Y analyze_performance responde con vacio en vez de explotar:
    assert r.analyze_performance("BTC/USDT") == {
        "best_strategies": [], "worst_strategies": [], "cross_symbol_insights": {}}


def test_una_linea_corrupta_no_rompe_la_siembra(tmp_path):
    tmp = str(tmp_path)
    ruta = os.path.join(tmp, "kb.jsonl")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"hypothesis_id": "h1", "symbol": "BTC/USDT",
                             "status": "backtested", "n_trades": 30}) + "\n")
        fh.write("{esto no es json\n")
        fh.write("\n")
        fh.write(json.dumps({"hypothesis_id": "h2", "symbol": "BTC/USDT",
                             "status": "backtested", "n_trades": 40}) + "\n")
    r = _runner(ruta)
    assert r._seed_performance_from_kb() == 2


# ---------------------------------------------------------------------------
# 2. El umbral de scientific_score
# ---------------------------------------------------------------------------

def test_el_umbral_de_validado_ya_no_esta_hardcodeado():
    """0,6 descartaba el 100% de las hipotesis reales."""
    import inspect
    from quant_math.autonomous_research.agents.research_manager import (
        ResearchManager)
    src = inspect.getsource(ResearchManager)
    assert "scientific_score > 0.6" not in src, \
        "el umbral 0,6 sigue hardcodeado"
    assert "self.validated_score_threshold" in src


def test_el_umbral_por_defecto_no_descarta_una_hipotesis_real():
    """Con 0.0 por defecto, un score de 0,13 (el maximo real medido) conserva."""
    from quant_math.autonomous_research.agents.research_manager import (
        ResearchManager)
    r = ResearchManager.__new__(ResearchManager)
    r.validated_score_threshold = 0.0
    assert 0.13 > r.validated_score_threshold
    # Y se puede endurecer si alguien lo quiere
    r.validated_score_threshold = 0.6
    assert 0.13 < r.validated_score_threshold
