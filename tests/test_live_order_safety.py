"""
Correccion 6 (2026-09-29) — la ruta de ordenes reales tiene que poder
cerrar lo que abre, y abrirse PROTEGIDA.

Que rompia:
- `create_order(...)` se mandaba DESNUDO, y los precios de TP/SL se
  calculaban despues, solo para guardarlos en el ledger. La proteccion
  vivia en un fichero local: si el proceso muriese, la posicion quedaba
  sin stop en el exchange.
- `close_position()` solo escribia una linea JSONL. No llegaba a mandar
  NADA al exchange, asi que en live la posicion se quitaba del estado
  local y se quedaba ABIERTA en Bybit.

Todo esto es OFFLINE: se intercepta ExchangeAPI y se comprueba COMO se
construyen las llamadas, que es justo donde estaba el fallo.
"""

import json

import pytest


class FakeAPI:
    """Doble de ExchangeAPI: registra las ordenes y devuelve ok."""

    instances = []

    def __init__(self, exchange_id="bybit", sandbox=False, api_key=None,
                 api_secret=None):
        self.exchange_id = exchange_id
        self.sandbox = sandbox
        self.orders = []
        self.margin_mode = None
        self.leverage = None
        FakeAPI.instances.append(self)

    def set_margin_mode(self, symbol, mode, params=None):
        self.margin_mode = (symbol, mode)

    def set_leverage(self, symbol, leverage, params=None):
        self.leverage = (symbol, leverage)

    def create_order(self, symbol, side, amount, price=None,
                     order_type="market", params=None):
        self.orders.append({
            "symbol": symbol, "side": side, "amount": amount,
            "order_type": order_type, "params": params or {},
        })
        return {"id": f"ORD-{len(self.orders)}", "amount": amount,
                "average": 100.0, "price": 100.0}

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    FakeAPI.instances = []
    import data_acquisition.data_sources.exchanges as ex
    monkeypatch.setattr(ex, "ExchangeAPI", FakeAPI)
    # Claves FICTICIAS solo para poder construir una config live: el bloqueo
    # de __post_init__ (que exige claves para dry_run=False) esta a proposito
    # y estos tests comprueban que sigue en pie. Ningun test sale a la red.
    monkeypatch.setenv("BYBIT_API_KEY", "CLAVE_DE_TEST")
    monkeypatch.setenv("BYBIT_API_SECRET", "SECRETO_DE_TEST")
    monkeypatch.setenv("BYBIT_TESTNET", "true")
    return FakeAPI


def _orch(**cfg_over):
    """Orchestrator minimo en dry_run=False, sin tocar disco de verdad."""
    from quant_math.orchestrator import OrchestratorConfig
    import tempfile
    tmp = tempfile.mkdtemp(prefix="b6-")
    cfg = {
        "symbols": ["BTC/USDT:USDT"], "timeframe": "1h", "lookback_days": 30,
        "min_paper_trades": 1, "hypotheses_per_cycle": 1,
        "kb_path": f"{tmp}/kb.jsonl", "state_dir": tmp,
        "initial_capital": 1000.0, "entry_pct": 0.05,
        "take_profit_pct": 0.05, "leverage": 10, "mode": "classic",
        "dry_run": False, "testnet": True,
    }
    cfg.update(cfg_over)
    return OrchestratorConfig(**cfg)


def test_la_entrada_lleva_sl_y_tp_al_exchange(fake_api):
    """LA PRUEBA QUE IMPORTA: la orden de apertura va PROTEGIDA.

    Antes salia sin nada y el SL solo vivia en el ledger local.
    """
    o = _orch()
    from quant_math.orchestrator import Orchestrator
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    orch.cycle_count = 1

    signal = {"symbol": "BTC/USDT:USDT", "side": "buy", "price": 100.0,
              "hypothesis_id": "h1", "expectancy": 0.01,
              "timestamp": 1790000000000}
    orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    api = fake_api.instances[-1]
    assert len(api.orders) == 1, "deberia haberse mandado una orden"
    params = api.orders[0]["params"]
    assert "stopLoss" in params, f"la entrada salio SIN stop: {params}"
    assert "takeProfit" in params, f"la entrada salio SIN TP: {params}"
    assert params["stopLoss"]["triggerPrice"] == pytest.approx(95.0)
    assert params["takeProfit"]["triggerPrice"] == pytest.approx(105.0)


def test_el_ledger_guarda_los_mismos_precios_que_mandó(fake_api):
    """Una sola verdad: lo que se registra es lo que se protecting."""
    from quant_math.orchestrator import Orchestrator
    o = _orch()
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    orch.cycle_count = 1
    signal = {"symbol": "BTC/USDT:USDT", "side": "buy", "price": 100.0,
              "hypothesis_id": "h1", "expectancy": 0.01,
              "timestamp": 1790000000000}
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    params = fake_api.instances[-1].orders[0]["params"]
    assert trade["stop_loss_price"] == pytest.approx(
        params["stopLoss"]["triggerPrice"])
    assert trade["take_profit_price"] == pytest.approx(
        params["takeProfit"]["triggerPrice"])


def test_el_cierre_live_manda_orden_reduce_only(fake_api):
    """Cerrar en live tiene que llegar al exchange, con el lado contrario
    y `reduceOnly` (que impide abrir una posicion INVERSA por error)."""
    from quant_math.orchestrator import Orchestrator
    o = _orch()
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o

    res = orch._live_close_order("BTC/USDT:USDT", "buy", 0.5)
    api = fake_api.instances[-1]
    assert len(api.orders) == 1, "el cierre no llego al exchange"
    assert api.orders[0]["side"] == "sell", "cerrar una larga es vender"
    assert api.orders[0]["params"].get("reduceOnly") is True
    assert res["ok"] is True


def test_cerrar_una_corta_compra(fake_api):
    from quant_math.orchestrator import Orchestrator
    o = _orch()
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    orch._live_close_order("BTC/USDT:USDT", "sell", 0.5)
    assert fake_api.instances[-1].orders[0]["side"] == "buy"


def test_en_paper_no_se_toca_la_red(fake_api):
    """El hook solo se instala en live: en paper no hay ni una llamada."""
    from quant_math.orchestrator import Orchestrator
    o = _orch(dry_run=True)
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    engine = orch._build_engine()
    assert getattr(engine, "live_close_hook", None) is None


def test_en_live_el_hook_esta_instalado(fake_api):
    from quant_math.orchestrator import Orchestrator
    o = _orch(dry_run=False)
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    engine = orch._build_engine()
    assert getattr(engine, "live_close_hook", None) is not None


def test_si_el_cierre_falla_la_posicion_no_se_borra(fake_api, monkeypatch):
    """Si la orden de cierre falla, la posicion sigue ABIERTA en local.

    Borrarla seria mentir: la verdad es que sigue abierta, y la
    reconciliacion necesita encontrarla.
    """
    from quant_math.decision_engine.main import DecisionEngine
    import tempfile
    tmp = tempfile.mkdtemp(prefix="b6close-")
    e = DecisionEngine(symbols=["BTC/USDT:USDT"], kb_path=f"{tmp}/kb.jsonl",
                       state_dir=tmp, take_profit_pct=0.05)

    key = e._position_key("h1", "BTC/USDT:USDT")
    e.open_positions[key] = {"entry_price": 100.0, "side": "buy",
                             "quantity": 1.0, "notional_usd": 100.0}

    def boom(*a, **k):
        raise RuntimeError("exchange caido")

    e.live_close_hook = boom
    e.close_position("h1", "BTC/USDT:USDT", motivo="sl", exit_price=95.0)
    assert key in e.open_positions, (
        "la posicion se borro localmente aunque el cierre fallo al exchange")


def test_el_cierre_exitoso_si_quita_la_posicion(fake_api):
    from quant_math.decision_engine.main import DecisionEngine
    import tempfile
    tmp = tempfile.mkdtemp(prefix="b6ok-")
    e = DecisionEngine(symbols=["BTC/USDT:USDT"], kb_path=f"{tmp}/kb.jsonl",
                       state_dir=tmp, take_profit_pct=0.05)
    key = e._position_key("h1", "BTC/USDT:USDT")
    e.open_positions[key] = {"entry_price": 100.0, "side": "buy",
                             "quantity": 1.0, "notional_usd": 100.0}
    e.live_close_hook = lambda *a, **k: {"ok": True, "order_id": "X"}
    closure = e.close_position("h1", "BTC/USDT:USDT", motivo="tp", exit_price=105.0)
    assert key not in e.open_positions, "una cerrada correcta se quita"
    assert closure["live_close"]["ok"] is True
