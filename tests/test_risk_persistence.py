"""Riesgo + persistencia de posiciones: SL 2:1 obligatorio, cierres TP/SL en
el libro permanente (paper_executions.jsonl, append-only) y recuperación de
posiciones abiertas tras reinicio del decision_engine."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.decision_engine import DecisionEngine

TP = 0.02


def flat_candles(price):
    return [[i, price, price, price, price, 10] for i in range(50)]


def rising_candles():
    return [[i, 100, 102, 99, 100 + i, 10] for i in range(50)]


def make(tmp, candles, tp=TP):
    return DecisionEngine(
        symbols=["BTC/USDT"],
        kb_path=os.path.join(tmp, "hypotheses.jsonl"),
        state_dir=os.path.join(tmp, "state"),
        data_provider=lambda s: candles,
        use_postgres=False,
        take_profit_pct=tp,
    )


def seed_entry(tmp, entry_price=100.0, side="buy", qty=0.5):
    """Deja en el estado una posicion abierta como si viniera de sesion previa."""
    state = os.path.join(tmp, "state")
    os.makedirs(state, exist_ok=True)
    key = f"hyp_seed:BTC/USDT"
    with open(os.path.join(state, "positions.jsonl"), "a") as fh:
        fh.write(json.dumps({"key": key, "opened_at": 1700000000.0,
                             "side": side, "entry_price": entry_price}) + "\n")
    ledger = os.path.join(state, "paper_executions.jsonl")
    with open(ledger, "a") as fh:
        fh.write(json.dumps({
            "mode": "paper", "symbol": "BTC/USDT", "side": side,
            "quantity": qty, "entry_price": entry_price,
            "notional_usd": qty * entry_price,
            "take_profit_price": entry_price * (1 + TP),
            "hypothesis_id": "hyp_seed", "timestamp": 1700000000.0,
            "cycle": 1, "key": key,
        }) + "\n")
    return key


def read_ledger(tmp):
    path = os.path.join(tmp, "state", "paper_executions.jsonl")
    out = []
    with open(path) as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def test_sl_ratio_exact_2_to_1():
    """SL = TP/2 exacto para cualquier TP configurado."""
    for tp in (0.02, 0.05, 0.03, 0.075, 0.01, 0.2):
        with tempfile.TemporaryDirectory() as tmp:
            eng = make(tmp, rising_candles(), tp=tp)
            assert eng.take_profit_pct == tp
            assert eng.stop_loss_pct == tp / 2
    print("PASS ratio: stop_loss_pct == take_profit_pct/2 exacto "
          "(0.02->0.01, 0.05->0.025, 0.075->0.0375, ...)")


def test_recovery_position_survives_restart_and_monitors():
    """Posicion abierta -> 'reinicio' -> se recupera, guarda y sigue monitoreando."""
    with tempfile.TemporaryDirectory() as tmp:
        key = seed_entry(tmp, entry_price=100.0)
        # --- reinicio: nueva instancia lee el estado persistente ---
        eng = make(tmp, flat_candles(100.5))   # entre SL(99) y TP(102)
        assert eng.has_open_position("hyp_seed", "BTC/USDT")
        assert len(eng.open_positions) == 1

        # precio aun entre SL y TP -> no cierra, sigue abierta
        res = eng.decide("BTC/USDT")   # kb vacio -> no_entry tras check exits
        assert res["action"] in ("no_entry", "skip_position_guard")
        assert eng.has_open_position("hyp_seed", "BTC/USDT")
        assert all("motivo_cierre" not in r for r in read_ledger(tmp))
    print("PASS recovery: posicion recuperada del JSONL y monitoreada")


def test_sl_close_writes_permanent_ledger():
    """Precio cae al nivel del SL -> cierre con motivo='sl' en el libro."""
    with tempfile.TemporaryDirectory() as tmp:
        key = seed_entry(tmp, entry_price=100.0)
        eng = make(tmp, rising_candles())          # tp=0.02 -> sl=0.01
        sl_price = 100.0 * (1 - eng.stop_loss_pct)  # 99.0
        assert abs(sl_price - 99.0) < 1e-12

        # reinicio con precio EN el nivel del SL
        eng2 = make(tmp, flat_candles(round(sl_price, 6)))
        assert eng2.has_open_position("hyp_seed", "BTC/USDT")
        eng2.decide("BTC/USDT")

        closures = [r for r in read_ledger(tmp) if "motivo_cierre" in r]
        assert len(closures) == 1
        c = closures[0]
        assert c["motivo_cierre"] == "sl"
        assert c["symbol"] == "BTC/USDT"
        assert c["hypothesis_id"] == "hyp_seed"
        assert c["side"] == "buy"
        assert c["entry_price"] == 100.0
        assert abs(c["exit_price"] - sl_price) < 1e-9
        expected_pnl = 0.5 * (c["exit_price"] - 100.0)
        assert abs(c["pnl"] - expected_pnl) < 1e-9 and c["pnl"] < 0
        assert c["pnl_pct"] < 0
        assert c["entry_time"] == 1700000000.0 and c["exit_time"] > 0
        assert not eng2.has_open_position("hyp_seed", "BTC/USDT")

        pos_path = os.path.join(tmp, "state", "positions.jsonl")
        with open(pos_path) as pf:
            positions_left = pf.read().strip()
        assert positions_left == ""
    print(f"PASS SL: cerrada en exit={sl_price} motivo='sl', pnl={c['pnl']:.4f}, "
          f"posiciones.jsonl limpio")


def test_tp_close_and_ledger_append_only_across_sessions():
    """TP tambien cierra; el libro es append-only y nunca se resetea."""
    with tempfile.TemporaryDirectory() as tmp:
        key = seed_entry(tmp, entry_price=100.0)
        eng = make(tmp, rising_candles())
        tp_price = 100.0 * (1 + TP)

        eng2 = make(tmp, flat_candles(tp_price))    # reinicio al nivel del TP
        eng2.decide("BTC/USDT")
        eng3 = make(tmp, flat_candles(99999.0))     # otra 'sesion' despues
        n1 = len(read_ledger(tmp))
        eng3.decide("BTC/USDT")                     # no debe tocar el libro
        n2 = len(read_ledger(tmp))

        closures = [r for r in read_ledger(tmp) if "motivo_cierre" in r]
        assert len(closures) == 1 and closures[0]["motivo_cierre"] == "tp"
        assert closures[0]["exit_price"] == tp_price
        assert closures[0]["pnl"] > 0 and closures[0]["pnl_pct"] > 0
        assert n1 == n2
        # append-only: la entrada original sigue siendo la primera linea
        first = read_ledger(tmp)[0]
        assert "motivo_cierre" not in first and first["entry_price"] == 100.0
    print("PASS TP: motivo='tp', libro intacto entre sesiones (append-only)")


if __name__ == "__main__":
    test_sl_ratio_exact_2_to_1()
    test_recovery_position_survives_restart_and_monitors()
    test_sl_close_writes_permanent_ledger()
    test_tp_close_and_ledger_append_only_across_sessions()
    print("\n4/4 risk+persistence tests passed")
