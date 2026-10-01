"""Tests para la auditoria, deduplicacion e idempotencia del ledger permanente.

Verifica:
1. Deteccion y prevencion de cierres duplicados con signos opuestos para una misma posicion.
2. Idempotencia del saneador de ejecuciones (sanitize_paper_executions).
3. Preservacion de entradas intactas y archivo de cierres obsoletos en cuarentena.
"""

import json
import os
import shutil
import tempfile
import pytest

from quant_math.decision_engine.sanitize_ledger import sanitize_paper_executions


def test_sanitize_ledger_deduplication_and_quarantine():
    """Verifica que el saneador deduplica cierres repetidos y preserva el ultimo."""
    tmp_dir = tempfile.mkdtemp()
    try:
        ledger_file = os.path.join(tmp_dir, "paper_executions.jsonl")
        quarantine_file = os.path.join(tmp_dir, "rejects.jsonl")

        # Simulamos la situacion exacta del incidente:
        # 1 entrada + 3 cierres con signos opuestos para hyp_0cd7e23b
        records = [
            {
                "type": "entry",
                "key": "hyp_0cd7e23b:XRP/USDT",
                "symbol": "XRP/USDT",
                "entry_price": 1.49,
                "quantity": 13.4,
                "timestamp": 1000.0,
            },
            # Cierre 1: SL (-0.50) con live_close fallido
            {
                "type": "closure",
                "key": "hyp_0cd7e23b:XRP/USDT",
                "symbol": "XRP/USDT",
                "entry_time": 1000.0,
                "quantity": 13.4,
                "pnl": -0.5054,
                "motivo_cierre": "sl",
                "exit_time": 1050.0,
                "live_close": {"ok": False, "error": "bybit markets not loaded"},
            },
            # Cierre 2: TP (+0.28) con live_close fallido
            {
                "type": "closure",
                "key": "hyp_0cd7e23b:XRP/USDT",
                "symbol": "XRP/USDT",
                "entry_time": 1000.0,
                "quantity": 13.4,
                "pnl": +0.2842,
                "motivo_cierre": "tp",
                "exit_time": 1100.0,
                "live_close": {"ok": False, "error": "bybit markets not loaded"},
            },
            # Cierre 3: Cierre externo definitivo (-0.24)
            {
                "type": "closure",
                "key": "hyp_0cd7e23b:XRP/USDT",
                "symbol": "XRP/USDT",
                "entry_time": 1000.0,
                "quantity": 13.4,
                "pnl": -0.2433,
                "motivo_cierre": "cerrada_en_el_exchange_tp_sl",
                "exit_time": 1200.0,
                "cierre_externo": True,
            },
        ]

        with open(ledger_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        # Primera ejecucion del saneador
        res1 = sanitize_paper_executions(ledger_file, quarantine_path=quarantine_file)
        assert res1["status"] == "sanitized"
        assert res1["modified"] is True
        assert res1["kept_entries"] == 1
        assert res1["kept_closures"] == 1
        assert res1["quarantined_now"] == 2
        assert res1["realized_pnl"] == -0.2433

        # Verificar contenido del ledger limpio
        with open(ledger_file, "r", encoding="utf-8") as f:
            clean_lines = [json.loads(l) for l in f if l.strip()]
        assert len(clean_lines) == 2
        assert clean_lines[0]["type"] == "entry"
        assert clean_lines[1]["type"] == "closure"
        assert clean_lines[1]["pnl"] == -0.2433
        assert clean_lines[1]["motivo_cierre"] == "cerrada_en_el_exchange_tp_sl"

        # Verificar cuarentena
        assert os.path.exists(quarantine_file)
        with open(quarantine_file, "r", encoding="utf-8") as f:
            q_lines = [json.loads(l) for l in f if l.strip()]
        assert len(q_lines) == 2
        assert q_lines[0]["pnl"] == -0.5054
        assert q_lines[1]["pnl"] == +0.2842

        # Segunda ejecucion: IDEMPOTENCIA ESTRICTA
        res2 = sanitize_paper_executions(ledger_file, quarantine_path=quarantine_file)
        assert res2["status"] == "already_clean"
        assert res2["modified"] is False
        assert res2["quarantined_now"] == 0
        assert res2["kept_closures"] == 1
        assert res2["realized_pnl"] == -0.2433

        # Verificar que el fichero de cuarentena no cambio de tamano
        with open(quarantine_file, "r", encoding="utf-8") as f:
            q_lines_after = [json.loads(l) for l in f if l.strip()]
        assert len(q_lines_after) == 2

    finally:
        shutil.rmtree(tmp_dir)


def test_fail_if_duplicate_closures_with_opposite_sign():
    """Test de guard: falla si en un ledger coexisten cierres de signo opuesto para la misma operacion."""
    tmp_dir = tempfile.mkdtemp()
    try:
        ledger_file = os.path.join(tmp_dir, "paper_executions.jsonl")
        records = [
            {
                "type": "closure",
                "key": "hyp_0cd7e23b:XRP/USDT",
                "entry_time": 1000.0,
                "quantity": 13.4,
                "pnl": -0.50,
            },
            {
                "type": "closure",
                "key": "hyp_0cd7e23b:XRP/USDT",
                "entry_time": 1000.0,
                "quantity": 13.4,
                "pnl": +0.28,
            },
        ]
        with open(ledger_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        # Funcion de validacion de integridad del ledger
        def check_no_opposite_closures(path: str):
            groups = {}
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("type") == "closure" or "motivo_cierre" in rec:
                        k = (rec.get("key"), rec.get("entry_time"), rec.get("quantity"))
                        groups.setdefault(k, []).append(float(rec.get("pnl", 0.0) or 0.0))
            for k, pnls in groups.items():
                has_pos = any(p > 0 for p in pnls)
                has_neg = any(p < 0 for p in pnls)
                if has_pos and has_neg:
                    raise AssertionError(f"Posicion {k} tiene cierres con signos opuestos: {pnls}")

        # Sin sanear debe fallar
        with pytest.raises(AssertionError, match="signos opuestos"):
            check_no_opposite_closures(ledger_file)

        # Despues de sanear, ya no tiene signos opuestos y pasa
        sanitize_paper_executions(ledger_file)
        check_no_opposite_closures(ledger_file)

    finally:
        shutil.rmtree(tmp_dir)
