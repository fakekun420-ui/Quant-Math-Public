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

import json
import os

import pytest


class FakeAPI:
    """Doble de ExchangeAPI con posiciones configurables y llamadas registradas."""

    #: {"BTC/USDT:USDT": {"contracts": 0.5, "side": "long", ...}}
    POSITIONS = {}
    #: rellenos que el exchange devolveria en fetch_my_trades
    TRADES = []
    instances = []

    def __init__(self, exchange_id="bybit", sandbox=False, api_key=None,
                 api_secret=None, data_venue=None):
        self.exchange_id = exchange_id
        self.sandbox = sandbox
        self.orders = []
        self.closed = False
        # `exchange` es el cliente ccxt: el resolver de cierres fantasma
        # lee los rellenos por ahi (`fetch_my_trades`), que es de donde sale
        # el precio REAL de salida y no de una estimacion.
        self.exchange = self
        FakeAPI.instances.append(self)

    def fetch_my_trades(self, symbol, limit=50):
        return list(FakeAPI.TRADES)

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
        #: cierres que se le pidieron registrar. Con el doble NO se escribe
        #: nada en un libro: para comprobar que el cierre llega al libro hace
        #: falta el motor de verdad (ver `_orch(motor_real=True)`).
        self.cierres_registrados = []

    def _last_entry_sizing(self, key):
        return 0.5, 500.0

    def _persist_positions(self):
        self.persisted += 1

    def record_external_closure(self, hypothesis_id, symbol, exit_price,
                                motivo=None, opened_at=None, extra=None):
        self.cierres_registrados.append(
            {"hypothesis_id": hypothesis_id, "symbol": symbol,
             "exit_price": exit_price, "motivo": motivo,
             "opened_at": opened_at, "extra": extra})
        self.open_positions.pop(f"{hypothesis_id}:{symbol}", None)
        return {"type": "closure", "symbol": symbol,
                "exit_price": exit_price}


def _orch(dry_run=True, symbols=("BTC/USDT:USDT",), positions=None,
          motor_real=False):
    """Orquestador minimo.

    `motor_real=True` monta el DecisionEngine de verdad, para los tests que
    necesitan comprobar que un cierre LLEGA AL LIBRO. Con el doble eso no
    se puede ver, y un test que verifica un doble no verifica nada.
    """
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
    if motor_real:
        from quant_math.decision_engine import DecisionEngine
        eng = DecisionEngine(symbols=list(symbols), kb_path=f"{tmp}/kb.jsonl",
                             state_dir=tmp, min_paper_trades=1,
                             use_postgres=False,
                             data_provider=lambda s: _velas(83000.0))
        eng.open_positions = dict(positions or {})
        orch.engine = eng
    else:
        orch.engine = FakeEngine(positions or {})
    return orch


def _velas(precio, n=120):
    """Serie plana. Solo hace falta que el motor tenga precio para marcar."""
    import pandas as pd
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({
        "open": [precio] * n, "high": [precio * 1.001] * n,
        "low": [precio * 0.999] * n, "close": [precio] * n,
        "volume": [1.0] * n}, index=idx)


def _abrir_en_libro(orch, key, symbol, side, entry_price, qty):
    """Escribe la ENTRADA en el libro, que es de donde el motor saca el
    tamano para calcular el PnL del cierre. Sin ella, el PnL caeria en el
    fallback de 1.0 y no estariamos midiendo nada."""
    os.makedirs(orch.config.state_dir, exist_ok=True)
    rec = {"type": "entry", "key": key, "symbol": symbol, "side": side,
           "hypothesis_id": key.split(":", 1)[0], "entry_price": entry_price,
           "quantity": qty, "notional_usd": qty * entry_price}
    with open(orch.engine.ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


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
    """Un phantom local NO genera ordenes, pero se busca su cierre REAL.

    Mandar una orden para "cerrar" algo que no existe seria inventar
    posicion, el error mas caro posible aqui. Pero tampoco basta con
    borrarlo: si no se busca el cierre en el exchange, el cierre se pierde
    y el SIS no aprende de el, que es justo para lo que esta el SIS.

    En este test el exchange NO devuelve ningun relleno, asi que no se
    puede saber el precio y NO se inventa: se retira del estado vivo y se
    deja constancia de que el cierre se perdio.
    """
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}
    fake_api.TRADES = []
    pos = {"h1:BTC/USDT:USDT": {"side": "buy", "entry_price": 83000.0}}
    orch = _orch(dry_run=False, positions=pos)
    r = orch.reconcile_positions(dry=False)

    ph = r["phantom_local"][0]
    assert ph["registrada_como_cierre"] is False, "sin precio real, sin cierre"
    assert ph["cierre_perdido"], "y no se puede tapar que se perdio"
    assert "h1:BTC/USDT:USDT" not in orch.engine.open_positions
    assert all(not api.orders for api in fake_api.instances), (
        "un phantom local no puede generar ordenes en el exchange")


def test_phantom_con_cierre_real_se_registra_para_que_el_sis_aprenda(fake_api,
                                                                       tmp_path):
    """EL CASO QUE SE MIDIO el 2026-09-30: el exchange cerro y nadie se
    entero.

    El TP/SL del exchange ejecuto el cierre; el motor no lo decidio, asi
    que `close_position` nunca corrio y el libro no recibio nada. Con
    `max_open_positions=1` el brazo quedaba muerto con un RISK-HALT
    eterno, y el SIS sin cierres que aprender.

    Aqui se comprueba que con el relleno real disponible, el cierre entra
    al libro con la MISMA forma que cualquier otro.
    """
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}
    abierto = 1_700_000_000_000.0          # ms de la apertura
    fake_api.TRADES = [
        # Un relleno de salida ANTERIOR a la apertura: NO es el nuestro.
        {"side": "sell", "price": 1.0, "timestamp": abierto - 60_000,
         "fee": {"cost": 0.0}},
        # El nuestro: cierre real, 1% por encima de la entrada.
        {"side": "sell", "price": 83000.0 * 1.01, "timestamp": abierto + 5_000,
         "fee": {"cost": 0.42}},
    ]
    pos = {"h1:BTC/USDT:USDT": {
        "side": "buy", "entry_price": 83000.0,
        "opened_at": abierto / 1000.0}}
    orch = _orch(dry_run=False, positions=pos, motor_real=True)
    _abrir_en_libro(orch, "h1:BTC/USDT:USDT", "BTC/USDT:USDT", "buy",
                    83000.0, 0.5)
    r = orch.reconcile_positions(dry=False)

    ph = r["phantom_local"][0]
    assert ph["registrada_como_cierre"] is True
    assert ph["cierre_real"]["ok"] is True
    assert ph["cierre_real"]["exit_price"] == pytest.approx(83000.0 * 1.01)
    assert "h1:BTC/USDT:USDT" not in orch.engine.open_positions
    assert all(not api.orders for api in fake_api.instances), (
        "el exchange ya lo cerro: no se manda ninguna orden")

    # Y lo importante: el cierre esta en el libro, para que el SIS lo vea.
    with open(orch.engine.ledger_path, encoding="utf-8") as fh:
        filas = [json.loads(l) for l in fh if l.strip()]
    cierres = [f for f in filas if f.get("type") == "closure"]
    assert cierres, "el cierre tiene que estar en el libro"
    c = cierres[-1]
    assert c["cierre_externo"] is True, "hay que poder distinguirlo"
    assert c["exit_price"] == pytest.approx(83000.0 * 1.01)
    assert c["entry_price"] == pytest.approx(83000.0)
    # +1% de precio en largo, 0,5 de cantidad: +415 USDT. Si saliera
    # negativo o cero, se habria resuelto mal el lado o el tamano.
    assert c["pnl"] == pytest.approx(415.0, rel=1e-3), f"pnl: {c['pnl']}"
    assert c["quantity"] == pytest.approx(0.5)
    # Y el precio de salida es el REAL, sin slippage por encima: el
    # relleno ya ocurrio, aplicarle el adverso otra vez seria cobrar dos
    # veces por lo mismo.
    assert c["exit_price"] == pytest.approx(83000.0 * 1.01)


def test_sin_precio_real_no_se_inventa_un_pnl(fake_api):
    """Lo que NO se hace: fabricar un cierre con el precio de entrada.

    Poner el precio de entrada daria un PnL de cero y parece inocente, pero
    es un numero que no ocurrio. El SIS aprenderia de un cierre que no
    existio, que es el "operar con datos falsos" que no se permite.
    """
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}
    abierto = 1_700_000_000_000.0
    # Solo hay una COMPRA posterior: no hay ninguna salida que la cierre.
    fake_api.TRADES = [
        {"side": "buy", "price": 83000.0, "timestamp": abierto + 1_000,
         "fee": {"cost": 0.1}},
    ]
    pos = {"h1:BTC/USDT:USDT": {
        "side": "buy", "entry_price": 83000.0,
        "opened_at": abierto / 1000.0}}
    orch = _orch(dry_run=False, positions=pos)
    r = orch.reconcile_positions(dry=False)

    ph = r["phantom_local"][0]
    assert ph["registrada_como_cierre"] is False
    ledger = os.path.join(orch.config.state_dir, "paper_executions.jsonl")
    escrito = os.path.exists(ledger) and os.path.getsize(ledger) > 0
    if escrito:
        with open(ledger, encoding="utf-8") as fh:
            filas = [json.loads(l) for l in fh if l.strip()]
        assert not [f for f in filas if f.get("type") == "closure"], (
            "no debe haber ningun cierre sin precio real")


def test_reconciliar_dos_veces_no_escribe_dos_cierres(fake_api):
    """Idempotente: la segunda pasada no duplica el cierre.

    Si duplicara, el SIS aprenderia el mismo cierre dos veces y contaria
    operaciones que ocurrieron una sola vez.
    """
    fake_api.POSITIONS["BTC/USDT:USDT"] = {}
    abierto = 1_700_000_000_000.0
    fake_api.TRADES = [
        {"side": "sell", "price": 83000.0 * 1.01, "timestamp": abierto + 5_000,
         "fee": {"cost": 0.42}},
    ]
    pos = {"h1:BTC/USDT:USDT": {
        "side": "buy", "entry_price": 83000.0,
        "opened_at": abierto / 1000.0}}
    orch = _orch(dry_run=False, positions=pos, motor_real=True)
    _abrir_en_libro(orch, "h1:BTC/USDT:USDT", "BTC/USDT:USDT", "buy",
                    83000.0, 0.5)

    orch.reconcile_positions(dry=False)
    with open(orch.engine.ledger_path, encoding="utf-8") as fh:
        n1 = len([l for l in fh if l.strip() and json.loads(l).get("type")
                  == "closure"])
    assert n1 == 1

    r2 = orch.reconcile_positions(dry=False)
    assert not r2["phantom_local"], "la posicion ya no esta: no hay phantom"
    with open(orch.engine.ledger_path, encoding="utf-8") as fh:
        n2 = len([l for l in fh if l.strip() and json.loads(l).get("type")
                  == "closure"])
    assert n2 == n1, "no se puede escribir el mismo cierre dos veces"


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
