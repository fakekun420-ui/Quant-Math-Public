"""Tests para la exclusion de hipotesis sin trades (n_trades == 0 o None) y cuarentena."""

import os
import json
import tempfile
import pytest

from quant_math.decision_engine import DecisionEngine
from quant_math.autonomous_research.adapters.postgres_kb import JSONLKnowledgeBase


def test_decision_engine_rejects_zero_or_none_trades_to_quarantine():
    """Verifica que DecisionEngine.register_hypothesis no escribe en la KB operativa si n_trades <= 0 o None,
    sino que lo manda al archivo de cuarentena."""
    with tempfile.TemporaryDirectory() as tmp:
        kb_path = os.path.join(tmp, "runtime", "hypotheses.jsonl")
        state_dir = os.path.join(tmp, "runtime", "state")
        os.makedirs(os.path.dirname(kb_path), exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

        engine = DecisionEngine(
            symbols=["BTC/USDT"],
            kb_path=kb_path,
            state_dir=state_dir,
            data_provider=lambda s: [],
        )

        # 1. Hipotesis valida con n_trades > 0
        valid_hyp = {
            "hypothesis_id": "hyp_valid_1",
            "symbol": "BTC/USDT",
            "status": "validated",
            "n_trades": 15,
            "expectancy": 0.05,
            "scientific_score": 0.8,
        }
        engine.register_hypothesis(valid_hyp)

        # 2. Hipotesis con n_trades == 0
        zero_hyp = {
            "hypothesis_id": "hyp_zero_trades",
            "symbol": "BTC/USDT",
            "status": "failed",
            "n_trades": 0,
            "expectancy": 0.0,
            "scientific_score": 0.1,
        }
        engine.register_hypothesis(zero_hyp)

        # 3. Hipotesis con n_trades None / ausente
        none_hyp = {
            "hypothesis_id": "hyp_none_trades",
            "symbol": "BTC/USDT",
            "status": "backtested",
        }
        engine.register_hypothesis(none_hyp)

        # Comprobar KB operativa
        with open(kb_path, "r", encoding="utf-8") as f:
            kb_lines = [json.loads(line) for line in f if line.strip()]

        kb_ids = set(r["hypothesis_id"] for r in kb_lines)
        assert "hyp_valid_1" in kb_ids
        assert "hyp_zero_trades" not in kb_ids
        assert "hyp_none_trades" not in kb_ids
        assert len(kb_ids) == 1

        # Comprobar cuarentena (hypotheses_rejects.jsonl)
        rejects_path = os.path.join(tmp, "runtime", "hypotheses_rejects.jsonl")
        assert os.path.exists(rejects_path)
        with open(rejects_path, "r", encoding="utf-8") as f:
            reject_lines = [json.loads(line) for line in f if line.strip()]

        reject_ids = [r["hypothesis_id"] for r in reject_lines]
        assert "hyp_zero_trades" in reject_ids
        assert "hyp_none_trades" in reject_ids
        assert "hyp_valid_1" not in reject_ids
        assert len(reject_lines) == 2
        for r in reject_lines:
            assert r["quarantine_reason"] == "no_trades"
            assert "quarantined_at" in r


def test_quarantine_idempotence():
    """Verifica que registrar la misma hipotesis rechazada varias veces no duplica entradas en cuarentena."""
    with tempfile.TemporaryDirectory() as tmp:
        kb_path = os.path.join(tmp, "runtime", "hypotheses.jsonl")
        state_dir = os.path.join(tmp, "runtime", "state")
        os.makedirs(os.path.dirname(kb_path), exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

        engine = DecisionEngine(
            symbols=["BTC/USDT"],
            kb_path=kb_path,
            state_dir=state_dir,
            data_provider=lambda s: [],
        )

        zero_hyp = {
            "hypothesis_id": "hyp_repeat_zero",
            "symbol": "BTC/USDT",
            "status": "failed",
            "n_trades": 0,
        }

        # Registrar 3 veces
        engine.register_hypothesis(zero_hyp)
        engine.register_hypothesis(zero_hyp)
        engine.register_hypothesis(zero_hyp)

        rejects_path = os.path.join(tmp, "runtime", "hypotheses_rejects.jsonl")
        with open(rejects_path, "r", encoding="utf-8") as f:
            reject_lines = [json.loads(line) for line in f if line.strip()]

        assert len(reject_lines) == 1
        assert reject_lines[0]["hypothesis_id"] == "hyp_repeat_zero"


def test_postgres_kb_adapter_rejects_and_quarantine():
    """Verifica que JSONLKnowledgeBase (postgres_kb adapter) tambien filtra y envia a cuarentena."""
    with tempfile.TemporaryDirectory() as tmp:
        kb_path = os.path.join(tmp, "runtime", "hypotheses.jsonl")
        os.makedirs(os.path.dirname(kb_path), exist_ok=True)

        kb = JSONLKnowledgeBase(jsonl_path=kb_path)

        # Registro sin n_trades
        kb.register_hypothesis({"hypothesis_id": "hyp_stub_no_trades", "status": "draft"})
        # Registro con n_trades > 0
        kb.register_hypothesis({"hypothesis_id": "hyp_stub_ok", "n_trades": 10, "status": "validated"})

        records = kb.load_records()
        assert "hyp_stub_ok" in records
        assert "hyp_stub_no_trades" not in records

        rejects_path = os.path.join(tmp, "runtime", "hypotheses_rejects.jsonl")
        assert os.path.exists(rejects_path)
        with open(rejects_path, "r", encoding="utf-8") as f:
            reject_lines = [json.loads(line) for line in f if line.strip()]

        assert len(reject_lines) == 1
        assert reject_lines[0]["hypothesis_id"] == "hyp_stub_no_trades"
