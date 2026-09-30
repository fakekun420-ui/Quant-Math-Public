"""Model-based generator: flag activo, plantillas ejecutables, degradacion."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model_based_generator import (HAS_MODEL_BASED_GENERATOR,
                                   generate_model_hypotheses)


def test_flag_active_in_ubuntu_env():
    assert HAS_MODEL_BASED_GENERATOR is True
    print("PASS flag: HAS_MODEL_BASED_GENERATOR=True")


def test_generates_executable_templates():
    closes = list(100 + i * 0.1 + ((i % 7) * 0.05) for i in range(300))
    out = generate_model_hypotheses("BTC/USDT", closes, max_hypotheses=2)
    assert 1 <= len(out) <= 2
    # MEDIDO 2026-09-28: esta lista estaba escrita a mano con 3 nombres y el generador ya
    # emitia 6, asi que el test llevaba tiempo fallando sin que hubiera un defecto. Ahora la
    # lista valida es la del propio ejecutor (una sola fuente de verdad), de modo que esto no
    # se vuelve a quedar viejo. Los tests del contrato entero estan en test_generator_contract.py
    from quant_math.autonomous_research.adapters.quant_math_adapter import IMPLEMENTED_STRATEGIES
    valid = IMPLEMENTED_STRATEGIES
    for t in out:
        st = t["parameters"]["strategy_type"]
        assert st in valid, f"estrategia no ejecutable por backtester: {st}"
        assert t["parameters"]["symbol"] == "BTC/USDT"
        assert "description" in t and "name" in t
    print(f"PASS templates: {[t['name'] for t in out]}")


def test_short_series_returns_empty():
    assert generate_model_hypotheses("BTC/USDT", [100.0] * 20) == []
    print("PASS serie corta: sin candidatos, sin crash")
