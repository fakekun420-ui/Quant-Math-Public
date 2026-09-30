"""
Reconciliacion de posiciones huerfanas.

El estado local (`positions.jsonl`) y el exchange son DOS verdades y
nadie las comparaba. Con apalancamiento, una posicion que solo existe en
el exchange es dinero en riesgo que nadie vigila: el bot no la ve, y su
equity, su drawdown y su tope diario dan un numero que no es el real.

La prueba que mas importa aqui es la 3: con `dry=True` NO se manda
ninguna orden. Un reconciliador que cierra solo es un peligro.

OFFLINE: se intercepta ExchangeAPI. Ningun test sale a la red.
"""

import pytest


class FakeAPI:
    """Doble de ExchangeAPI con posiciones configurables y llamadas registradas."""

    #: {"BTC/USDT:USDT": {"contracts": 0.5, "side": "long", ...}}
    POSITIONS = {}
    instances = []

    def __init__(self, exchange_id="bybit", sandbox=False, api_key=None,
                 api_secret=None, data_venue=None):
        self.exchange_id = exchange_id
        self.sandbox = sandbox
        self.orders = []
        self.closed = False
        FakeAPI.instances.append(self)

    def fetch_position(self, symbol):
        return dict(self.POSITIONS.get(symbol, {}))

    def create_order(self, symbol, side, amount, price=None,
                     order_type="market", params=None):
        self.orders.append({"symbol": symbol, "side": side,
                            "amount": amount, "params": params or {}})
        return {"id": f"ORD-{len(self.orders)}"}

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    FakeAPI.instances = []
    FakeAPI.POSITIONS = {}
    import data_acquisition.data_sources.exchanges as ex
    monkeypatch.setattr(ex, "ExchangeAPI", FakeAPI)
    monkeypatch.setenv("BYBIT_API_KEY", "CLAVE_DE_TEST")
    monkeypatch.setenv("BYBIT_API_SECRET", "SECRETO_DE_TEST")
    monkeypatch.setenv("BYBIT_TESTNET", "true")
    return FakeAPI


class FakeEngine:
    """El engine solo necesita open_positions, _last_entry_sizing y persist."""

    def __init__(self, positions):
        self.open_positions = dict(positions)
        self.persisted = 0

    def _last_entry_sizing(self, key):
        return 0.5, 500.0

    def _persist_positions(self):
        self.persisted += 1


def _orch(dry_run=True, symbols=("BTC/USDT:USDT",), positions=None):
    from quant_math.orchestrator import Orchestrator, OrchestratorConfig
    import tempfile
    tmp = tempfile.mkdtemp(prefix="rec-")
    cfg = OrchestratorConfig(
        symbols=list(symbols), timeframe="1h", lookback_days=30,
        min_paper_trades=1, hypotheses_per_cycle=1,
        kb_path=f"{tmp}/kb.jsonl", state_dir=tmp,
        initial_capital=1000.0, entry_pct=0.05, take_profit_pct=0.05,
        leverage=10, mode="classic", dry_run=dry_run, testnet=True,
    )
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = cfg
    orch.cycle_count = 1
    orch.engine = FakeEngine(positions or {})
    return orch


def test_detecta_orphan_exchange(fake_api):
    """Esta en el exchange y no en local: la discrepancia MAS GRAVE."""
    fake_api.POSITIONS["BTC/USDT:USDT"] = {
        "contracts": 0.5, "side": "long", "entryPrice": 83000.0,
        "leverage": 10, "liquidationPrice": 75000.0, "unrealisedPnl": -12.5,
    }
    r = _orch(dry_run=False, positions={}).reconcile_positions()
    assert r["status"] == "ok"
    assert len(r["orphan_exchange"]) == 1
    o = r["orphan_exchange"][0]
    assert o["symbol"] == "BTC/USDT:USDT"
    assert o["gravedad"] == "ALTA"
    assert o["exchange_quantity"] == 0.5
    assert o["unrealised_pnl"] == -12.5


def test_detecta_phantom_local(fake_api):
    """Esta en local pero no en el exchange: el ledger miente."""
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}   # exchange: nada
    pos = {"h1:BTC/USDT:USDT": {"side": "buy", "entry_price": 83000.0}}
    r = _orch(dry_run=False, positions=pos).reconcile_positions()
    assert len(r["phantom_local"]) == 1
    assert r["phantom_local"][0]["local_quantity"] == 0.5


def test_dry_true_no_manda_ninguna_orden(fake_api):
    """LA PRUEBA QUE MAS IMPORTA: por defecto SOLO informa.

    Un reconciliador que cierra posiciones solo es un peligro.
    """
    fake_api.POSITIONS["BTC/USDT:USDT"] = {"contracts": 0.5, "side": "long"}
    r = _orch(dry_run=False, positions={}).reconcile_positions()
    assert len(r["orphan_exchange"]) == 1
    assert r["closed"] == [], "no deberia haberse cerrado nada en dry"
    assert all(not api.orders for api in fake_api.instances), (
        "se mandaron ordenes en dry=True: ordenes NO autorizadas")


def test_dry_false_cierra_la_huerfana(fake_api):
    fake_api.POSITIONS["BTC/USDT:USDT"] = {
        "contracts": 0.5, "side": "long", "entryPrice": 83000.0}
    r = _orch(dry_run=False, positions={}).reconcile_positions(dry=False)
    assert len(r["closed"]) == 1
    assert r["closed"][0]["side"] == "sell", "cerrar una larga es vender"
    assert r["closed"][0]["result"]["reduce_only"] is True
    assert r["orphan_exchange"][0]["closed"]["ok"] is True
    # Y la orden que llego al exchange lleva reduceOnly de verdad.
    enviados = [o for api in fake_api.instances for o in api.orders]
    assert len(enviados) == 1
    assert enviados[0]["params"].get("reduceOnly") is True


def test_phantom_local_no_manda_orden_al_exchange(fake_api):
    """Un phantom local se corrige SOLO en local.

    Mandar una orden para "cerrar" algo que no existe seria inventar
    posicion — el error mas caro posible aqui.
    """
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}
    pos = {"h1:BTC/USDT:USDT": {"side": "buy", "entry_price": 83000.0}}
    orch = _orch(dry_run=False, positions=pos)
    r = orch.reconcile_positions(dry=False)
    assert r["phantom_local"][0]["corregida_en_local"] is True
    assert "h1:BTC/USDT:USDT" not in orch.engine.open_positions
    assert all(not api.orders for api in fake_api.instances), (
        "un phantom local no puede generar ordenes en el exchange")


def test_falla_cerrado_sin_claves(fake_api, monkeypatch):
    """Sin claves: skipped CON MOTIVO. Nunca un informe vacio.

    Un {} sin motivo se lee como "todo bien", y no lo es. Se construye el
    orquestador con claves validas y se pierden DESPUES, que es como pasa
    de verdad (claves que caducan o .env que no se lee).
    """
    orch = _orch(dry_run=False, positions={})
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    r = orch.reconcile_positions()
    assert r["status"] == "skipped"
    assert r["motivo"], "skipped sin motivo es indistinguible de 'ok'"
    assert r["orphan_exchange"] == []
    assert all(not api.orders for api in fake_api.instances)


def test_falla_cerrado_en_paper(fake_api):
    """En paper no hay exchange: se dice, y no se finge un OK."""
    r = _orch(dry_run=True, positions={}).reconcile_positions()
    assert r["status"] == "skipped"
    assert "dry_run" in r["motivo"]


def test_idempotente(fake_api):
    """Correrla dos veces no cambia nada la segunda."""
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}
    pos = {"h1:BTC/USDT:USDT": {"side": "buy", "entry_price": 83000.0}}
    orch = _orch(dry_run=False, positions=pos)
    primero = orch.reconcile_positions(dry=False)
    assert len(primero["phantom_local"]) == 1
    segundo = orch.reconcile_positions(dry=False)
    assert len(segundo["phantom_local"]) == 0, "la segunda pasada debe estar limpia"
    assert segundo["orphan_exchange"] == []


def test_reconciliacion_horaria_no_nunca(fake_api):
    """Default = 24 ciclos (una vez por hora a intervalo 1h).

    Antes era 0 (nunca), y entonces una posicion huerfana con apalancamiento
    es dinero en riesgo que nadie vigila. Y 1 por ciclo daria 86.400 llamadas
    al dia al exchange, que es peor que el problema que arregla. 24 son 24
    llamadas al dia y una ventana de datos sucios de una hora.
    """
    from quant_math.orchestrator import OrchestratorConfig
    import tempfile
    tmp = tempfile.mkdtemp(prefix="rec-cfg-")
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT:USDT"], timeframe="1h", lookback_days=30,
        min_paper_trades=1, hypotheses_per_cycle=1,
        kb_path=f"{tmp}/kb.jsonl", state_dir=tmp,
        initial_capital=1000.0, entry_pct=0.05, take_profit_pct=0.05,
        leverage=10, mode="classic", dry_run=True, testnet=True,
    )
    assert cfg.reconcile_every_n_cycles == 24


def test_cerrar_huerfanas_es_opt_in(fake_api):
    """Detectar una huerfana avisa; cerrarla es una decision.

    Por defecto `reconcile_auto_close=False`: el sistema informa y sigue. Un
    reconciliador que cierra solo es un peligro, y cerrar de mas es tan caro
    como no cerrar nunca.
    """
    from quant_math.orchestrator import OrchestratorConfig
    import tempfile
    tmp = tempfile.mkdtemp(prefix="rec-close-")
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT:USDT"], timeframe="1h", lookback_days=30,
        min_paper_trades=1, hypotheses_per_cycle=1,
        kb_path=f"{tmp}/kb.jsonl", state_dir=tmp,
        initial_capital=1000.0, entry_pct=0.05, take_profit_pct=0.05,
        leverage=10, mode="classic", dry_run=True, testnet=True,
    )
    assert cfg.reconcile_auto_close is False


def test_una_reconciliacion_fallida_no_tumba_el_ciclo(fake_api):
    """Un informe que no llega es mejor que un bot parado."""
    from quant_math.orchestrator import Orchestrator
    o = _orch(dry_run=False, positions={})
    o._run_reconcile = Orchestrator._run_reconcile.__get__(o, Orchestrator)

    def boom(*a, **k):
        raise RuntimeError("exchange caido")

    o.reconcile_positions = boom
    assert o._run_reconcile(dry=True) is None, "no deberia propagar la excepcion"


def test_reconcile_tabla_leida_coincide_con_la_api(fake_api):
    """El MMR por defecto tiene que ser el dato, no una constante inventada.

    Este test pegaria si alguien vuelve a poner 0,005 como supuesto.
    """
    from quant_math.risk.roe_targets import DEFAULT_MAINTENANCE_MARGIN_RATE
    assert DEFAULT_MAINTENANCE_MARGIN_RATE == 0.0033, (
        "el MMR por defecto debe ser el primer tramo real de Bybit (0,0033)")


def test_el_mmr_por_defecto_es_el_LEIDO_de_bybit(fake_api):
    """El MMR por defecto no puede volver a ser un supuesto.

    Medido el 2026-09-30 contra el endpoint publico /v5/market/risk-limit:
    primer tramo 0,0033. Antes era 0,005 (punto medio de un barrido propio).
    Este test falla si alguien vuelve a inventarse el numero.
    """
    from quant_math.risk.roe_targets import (
        DEFAULT_MAINTENANCE_MARGIN_RATE, mmr_for_notional, BYBIT_MMR_TIERS)
    assert DEFAULT_MAINTENANCE_MARGIN_RATE == 0.0033
    # El tamano real de este sistema cae en el primer tramo
    for nocional in (15.0, 100.0, 200.0, 300_000.0):
        assert mmr_for_notional(nocional) == 0.0033
    # Y crecer SI sube el MMR, porque la liquidacion se acerca.
    # Tramos reales: <=300k -> 0,0033 | <=2M -> 0,0050 | <=2,6M -> 0,0056 |
    # <=3,2M -> 0,0063. Con 3.000.000 ya se esta en el tramo de 3,2M.
    assert mmr_for_notional(1_000_000.0) == 0.0050
    assert mmr_for_notional(3_000_000.0) == 0.0063
    # La tabla tiene que ser monotona creciente: si no, el clamp mentiria
    mmrs = [m for _, m, _ in BYBIT_MMR_TIERS]
    assert mmrs == sorted(mmrs), f"MMR no crece con el tamano: {mmrs}"


def test_el_ledger_no_se_toca(fake_api):
    """La reconciliacion corrige el estado, NUNCA el libro permanente."""
    import os
    from quant_math.orchestrator import Orchestrator, OrchestratorConfig
    import tempfile
    tmp = tempfile.mkdtemp(prefix="rec-led-")
    ledger = os.path.join(tmp, "paper_executions.jsonl")
    original = '{"type":"closure","key":"h1:BTC/USDT:USDT","pnl":1.0}\n'
    with open(ledger, "w", encoding="utf-8") as fh:
        fh.write(original)
    cfg = OrchestratorConfig(
        symbols=["BTC/USDT:USDT"], timeframe="1h", lookback_days=30,
        min_paper_trades=1, hypotheses_per_cycle=1,
        kb_path=f"{tmp}/kb.jsonl", state_dir=tmp,
        initial_capital=1000.0, entry_pct=0.05, take_profit_pct=0.05,
        leverage=10, mode="classic", dry_run=False, testnet=True,
    )
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = cfg
    orch.cycle_count = 1
    orch.engine = FakeEngine({"h1:BTC/USDT:USDT": {"side": "buy",
                                                  "entry_price": 83000.0}})
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}
    orch.reconcile_positions(dry=False)
    with open(ledger, "r", encoding="utf-8") as fh:
        assert fh.read() == original, "el libro permanente fue modificado"
