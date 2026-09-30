"""P1: cuando el mejor candidato tiene posicion abierta, decide() cae al
siguiente mejor libre en lugar de quedarse en skip."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quant_math.decision_engine import DecisionEngine


def make(tmp, kb_rows, candles):
    kb = os.path.join(tmp, "kb.jsonl")
    with open(kb, "w") as fh:
        for r in kb_rows:
            fh.write(json.dumps(r) + "\n")
    return DecisionEngine(
        symbols=["XRP/USDT"], kb_path=kb,
        state_dir=os.path.join(tmp, "state"),
        data_provider=lambda s: candles, use_postgres=False)


def up():
    return [[i, 100, 101, 99, 100 + i, 10] for i in range(50)]


def test_fallback_to_next_best_when_best_open():
    """MEDIDO el 2026-09-30: este test codificaba el BUG.

    Abria una segunda posicion del MISMO simbolo con otra hipotesis. Pero
    Bybit funciona en modo NET: dos ordenes en la misma direccion sobre el
    mismo activo se FUSIONAN en una sola posicion con entrada ponderada. El
    sistema se quedaba con 5 posiciones locales (5 hipotesis) y el
    exchange con 1 (33 XRP). Al cerrar de golpe el TP quedaron 5
    fantasmas, el brazo se bloqueo con `open positions 5 >= max 5` y el SIS
    no aprendio de ningun cierre.

    Aqui se abre para un simbolo LIBRE, que es donde el fallback tiene
    sentido, y en el test siguiente se comprueba que el simbolo ocupado se
    respeta.
    """
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {"hypothesis_id": "best_open", "symbol": "XRP/USDT",
             "status": "backtested", "expectancy": 0.09,
             "scientific_score": 0.9},
            {"hypothesis_id": "second_free", "symbol": "BTC/USDT",
             "status": "backtested", "expectancy": 0.05,
             "scientific_score": 0.8},
        ]
        eng = make(tmp, rows, up())
        eng.open_positions["best_open:XRP/USDT"] = {
            "key": "best_open:XRP/USDT", "opened_at": 1.0,
            "side": "buy", "entry_price": 100.0}

        res = eng.decide("BTC/USDT")
        assert res["action"] == "entry", res
        assert res["hypothesis_id"] == "second_free"
        assert res["expectancy"] == 0.05


def test_no_se_abre_una_segunda_posicion_del_mismo_simbolo():
    """El fallo que produjo 5 locales contra 1 en el exchange.

    Otra hipotesis con MEJOR esperanza no puede meter una segunda
    posicion en un simbolo que ya esta ocupado: el exchange la fusionaria
    y el estado local quedaria desfasado.
    """
    with tempfile.TemporaryDirectory() as tmp:
        rows = [
            {"hypothesis_id": "h_best", "symbol": "XRP/USDT",
             "status": "backtested", "expectancy": 0.20,
             "scientific_score": 0.9},
            {"hypothesis_id": "h_otra", "symbol": "XRP/USDT",
             "status": "backtested", "expectancy": 0.15,
             "scientific_score": 0.8},
        ]
        eng = make(tmp, rows, up())
        # YA HAY UNA POSICION de XRP, de OTRA hipotesis
        eng.open_positions["h_otra:XRP/USDT"] = {
            "key": "h_otra:XRP/USDT", "opened_at": 1.0,
            "symbol": "XRP/USDT", "side": "buy", "entry_price": 100.0}

        res = eng.decide("XRP/USDT")
        assert res["action"] != "entry", (
            "ha abierto una segunda posicion del mismo simbolo: el exchange "
            "la fusionaria y el estado local quedaria desfasado")
        assert eng.symbols_with_open_positions() == {"XRP/USDT"}
    print("PASS fallback: una posicion por simbolo, el exchange fusiona")


def test_skip_contract_when_all_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"hypothesis_id": "only_one", "symbol": "XRP/USDT",
                 "status": "backtested", "expectancy": 0.05,
                 "scientific_score": 0.9}]
        eng = make(tmp, rows, up())
        eng.open_positions["only_one:XRP/USDT"] = {
            "key": "only_one:XRP/USDT", "opened_at": 1.0,
            "side": "buy", "entry_price": 100.0}
        res = eng.decide("XRP/USDT")
        assert res["action"] == "skip_position_guard"
        assert res["hypothesis_id"] == "only_one"
    print("PASS contrato: unico candidato bloqueado -> skip_position_guard")


if __name__ == "__main__":
    test_fallback_to_next_best_when_best_open()
    test_skip_contract_when_all_blocked()
    print("\n2/2 p1 fallback tests passed")
