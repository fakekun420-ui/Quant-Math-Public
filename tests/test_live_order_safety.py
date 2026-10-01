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
import os
import tempfile

import pytest


class FakeAPI:
    """Doble de ExchangeAPI: registra las ordenes y devuelve ok."""

    instances = []

    # Palancas del doble, a nivel de CLASE y NO en __init__. Motivo: el
    # motor crea su propia instancia dentro de _execute_live_order, asi que
    # un test solo puede fijar la palanca ANTES de que exista esa
    # instancia. Si estuvieran en __init__, el atributo de instancia
    # taparia al de clase y el test creeria haber configurado algo que en
    # realidad no/configuro. (Medido: por eso los 4 tests fallaban con
    # "10 == 5".)
    #: si es str, set_leverage() lanza ese error
    leverage_error = None
    #: apalancamiento que el exchange DEVUELVE al releer la posicion
    leverage_real = 10
    #: margen disponible que declara la cuenta (None = no se sabe)
    margin_available = 100000.0
    #: modo de margen REAL que devuelve el exchange. Por defecto "isolated",
    #: que es lo que el motor pide y lo unico aceptable: en CRUCE la
    #: perdida de una posicion la paga toda la cuenta.
    margin_mode_real = "isolated"
    #: si es str, set_margin_mode() lanza ese error (con su motivo dentro)
    margin_mode_error = None
    #: precio del libro del venue de EJECUCION. `_live_order` lo relee antes
    #: de calcular el TP/SL: con el precio rancio de la senal el SL caia del
    #: lado equivocado y Bybit rechazaba la orden entera.
    book_price = 100.0
    #: si es str, fetch_order_book() lanza ese error
    book_error = None

    def __init__(self, exchange_id="bybit", sandbox=False, api_key=None,
                 api_secret=None, data_venue=None):
        self.exchange_id = exchange_id
        self.sandbox = sandbox
        self.orders = []
        self.margin_mode = None
        self.leverage = None
        FakeAPI.instances.append(self)

    def set_margin_mode(self, symbol, mode, params=None):
        if self.margin_mode_error:
            raise RuntimeError(self.margin_mode_error)
        self.margin_mode = (symbol, mode)

    def set_leverage(self, symbol, leverage, params=None):
        if self.leverage_error:
            raise RuntimeError(self.leverage_error)
        self.leverage = (symbol, leverage)

    def fetch_ticker(self, symbol, params=None):
        if FakeAPI.book_error:
            raise RuntimeError(FakeAPI.book_error)
        return {"last": FakeAPI.book_price, "bid": FakeAPI.book_price * 0.9999,
                "ask": FakeAPI.book_price * 1.0001}

    def read_back_leverage(self, symbol):
        return self.leverage_real

    def read_back_stops(self, symbol):
        """SL/TP que el exchange DECLARA tener.

        MEDIDO el 2026-10-01: el SL se mandaba en la orden y se daba por
        puesto sin comprobarlo. Una posicion quedo desprotegida y se
        liquido al 127,2% del margen con el SL pedido al 27,5%. Ahora se
        lee, y este doble devuelve lo que el pedido guardo, para poder
        comparar.

        `stops_real = None` simula un exchange que NO expone los stops
        (o una llamada que falla): el orquestador tiene que fallar
        cerrado y cerrar la posicion, no darla por buena.
        """
        if FakeAPI.stops_real is None:
            return {"stopLoss": None, "takeProfit": None,
                    "stopLoss_triggerBy": None, "takeProfit_triggerBy": None}
        return dict(FakeAPI.stops_real)

    def fetch_order_book(self, symbol, limit=5):
        """Libro del venue de EJECUCION (lo usa la comprobacion de rango)."""
        if FakeAPI.book_error:
            raise RuntimeError(FakeAPI.book_error)
        mid = FakeAPI.book_price
        return {"asks": [[mid * 1.0001, 10.0]], "bids": [[mid * 0.9999, 10.0]]}

    @property
    def exchange(self):
        """El motor relee el ULTIMO PRECIO del venue de ejecucion: Bybit
        valida el TP/SL contra `LastPrice`, no contra el libro."""
        return self

    def load_markets(self, reload=False, params=None):
        if FakeAPI.load_markets_error:
            raise RuntimeError(FakeAPI.load_markets_error)
        FakeAPI.load_markets_calls += 1
        return {}

    def read_back_margin_mode(self, symbol):
        return self.margin_mode_real

    def available_margin(self):
        return self.margin_available

    def create_order(self, symbol, side, amount, price=None,
                     order_type="market", params=None):
        self.orders.append({
            "symbol": symbol, "side": side, "amount": amount,
            "order_type": order_type, "params": params or {},
        })
        # Un exchange que ACEPTA la orden guarda lo que se le pidio. Se
        # registra aqui para que `read_back_stops` tenga algo que devolver:
        # es lo que hace que la comprobacion post-entrada sea real en vez
        # de un adorno. `FakeAPI.stops_drop` simula al exchange que se
        # come el SL sin avisar, que es el fallo que hay que cazar.
        if FakeAPI.stops_drop:
            FakeAPI.stops_real = {"stopLoss": None, "takeProfit": None,
                                  "stopLoss_triggerBy": None,
                                  "takeProfit_triggerBy": None}
        elif isinstance(params, dict) and params.get("stopLoss"):
            FakeAPI.stops_real = {
                "stopLoss": (params.get("stopLoss") or {}).get("triggerPrice"),
                "takeProfit": (params.get("takeProfit") or {}).get("triggerPrice"),
                "stopLoss_triggerBy": (params.get("stopLoss") or {}).get("triggerBy"),
                "takeProfit_triggerBy": (params.get("takeProfit") or {}).get("triggerBy"),
            }
        # El relleno de un marketable sale en el libro, no en el medio.
        _fill = FakeAPI.book_price
        return {"id": f"ORD-{len(self.orders)}", "amount": amount,
                "average": _fill, "price": _fill}

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    FakeAPI.instances = []
    # Las palancas son de clase: hay que devolverlas a su valor bueno entre
    # tests o cada uno hereda lo que dejo el anterior.
    FakeAPI.leverage_error = None
    FakeAPI.leverage_real = 10
    FakeAPI.margin_available = 100000.0
    FakeAPI.margin_mode_real = "isolated"
    FakeAPI.margin_mode_error = None
    # Por defecto el doble NO sabe de stops (como un exchange que no los
    # expone). Cada test que SI espera una operacion viva tiene que
    # declararlos en su `create_order`, que es donde se sabe lo que se
    # pidio. Asi el contrato queda explicito: no se da por buena ninguna
    # proteccion que no se pueda leer.
    FakeAPI.stops_real = None
    FakeAPI.stops_drop = False
    FakeAPI.load_markets_error = None
    FakeAPI.load_markets_calls = 0
    FakeAPI.book_price = 100.0
    FakeAPI.book_error = None
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
    # El TP/SL se calcula desde el ASK (100 x 1,0001 = 100,01), no desde el
    # medio ni desde el precio rancio de la senal: en una compra se paga el
    # ask, y Bybit valida `base_price` contra el mismo lado. Con el medio,
    # el SL quedaria por ENCIMA del precio de ejecucion y el exchange
    # rechazaria la orden (medido el 2026-09-30: 10001).
    entrada = api.book_price
    assert params["stopLoss"]["triggerPrice"] == pytest.approx(entrada * 0.95)
    assert params["takeProfit"]["triggerPrice"] == pytest.approx(entrada * 1.05)
    # Y lo que Bybit exige: el SL por DEBAJO y el TP por ARRIBA de la
    # entrada. Si esto se rompe, la orden no llega a mandarse nunca.
    assert params["stopLoss"]["triggerPrice"] < entrada
    assert params["takeProfit"]["triggerPrice"] > entrada


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


# ---------------------------------------------------------------------------
# La clave de posicion y el simbolo PERPETUAL (2026-09-30)
# ---------------------------------------------------------------------------

def test_la_clave_de_posicion_no_parte_mal_el_simbolo_perp():
    """La clave es "hipotesis_id:symbol" y el simbolo perp lleva dos puntos.

    Con rsplit(":", 1) se parte por el ULTIMO y sale "USDT" pelado. Se vio
    en el run real del 2026-09-30: "bybit does not have market symbol USDT",
    y las salidas de los perps no se podian comprobar. Este test es el que
    faltaba y por eso el bug llego a produccion.
    """
    key = "hyp_ae287e64:BTC/USDT:USDT"
    assert key.rsplit(":", 1)[-1] == "USDT", "el bug: sale el ticker solo"
    assert key.split(":", 1)[-1] == "BTC/USDT:USDT", "el arreglo"


def test_check_exits_ve_los_simbolos_perp_completos():
    """check_exits_all() tiene que devolver 'BTC/USDT:USDT', no 'USDT'."""
    from quant_math.decision_engine.main import DecisionEngine
    import tempfile
    tmp = tempfile.mkdtemp(prefix="perp-")
    e = DecisionEngine(symbols=["BTC/USDT:USDT"], kb_path=f"{tmp}/kb.jsonl",
                       state_dir=tmp, take_profit_pct=0.05)
    e.open_positions["hyp_1:BTC/USDT:USDT"] = {
        "side": "buy", "entry_price": 100.0, "quantity": 1.0}
    e.open_positions["hyp_2:ETH/USDT:USDT"] = {
        "side": "buy", "entry_price": 200.0, "quantity": 1.0}

    vistos = []
    e._check_exits = lambda sym: vistos.append(sym) or []
    e.check_exits_all()

    assert sorted(vistos) == ["BTC/USDT:USDT", "ETH/USDT:USDT"], (
        f"los simbolos perp deben llegar completos, llegaron {vistos}")


def test_reconcile_tambien_parte_por_el_primer_dos_puntos():
    """La reconciliacion copio el patron roto; ahora queda fijado."""
    from quant_math.orchestrator import Orchestrator
    from quant_math.autonomous_research.adapters.quant_math_adapter import (
        QuantMathAdapter)
    key = "hyp_x:BTC/USDT:USDT"
    assert key.split(":", 1)[-1] == "BTC/USDT:USDT"


# ---------------------------------------------------------------------------
# APALANCAMIENTO (2026-09-30)
#
# Un apalancamiento que no es el pedido cambia el riesgo por completo: la
# liquidacion cae mas lejos, el SL puede quedar inalcanzable y la posicion
# real es mas grande de la que se cree. Es la misma cosa que operar con
# datos falsos, y por eso NO se deja pasar en silencio.
#
# Que `set_leverage` no lance NO demuestra nada: Bybit puede aceptar la
# llamada y abrir la posicion a otro. La garantia es releer la posicion.
# ---------------------------------------------------------------------------

#: Clase REAL de ExchangeAPI, capturada aqui en la IMPORTACION del modulo.
#: El fixture `fake_api` la sustituye por el doble, asi que pedirla dentro
#: de un test devolveria el doble y no lo que se quiere comprobar. Es la
#: misma clase que el motor importa en vivo, por eso el test es valido.
REAL_EXCHANGE_API = None
try:
    from data_acquisition.data_sources.exchanges import (
        ExchangeAPI as REAL_EXCHANGE_API)
except Exception:                       # pragma: no cover
    REAL_EXCHANGE_API = None


def _orch_lev(fake_api, leverage_real, lev_pedido=10, **cfg_over):
    from quant_math.orchestrator import Orchestrator
    o = _orch(leverage=lev_pedido, **cfg_over)
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    orch.cycle_count = 1
    # se prepara el doble ANTES de que _execute_live_order lo cree: el
    # constructor de ExchangeAPI se monkeypatchea a FakeAPI y el motor crea
    # su propia instancia dentro, asi que se parchea la clase.
    FakeAPI.leverage_real = leverage_real
    signal = {"symbol": "BTC/USDT:USDT", "side": "buy", "price": 100.0,
              "hypothesis_id": "h1", "expectancy": 0.01,
              "timestamp": 1790000000000}
    return orch, signal


def test_si_el_apalancamiento_no_coincide_no_se_acepta_la_operacion(fake_api):
    """El exchange devuelve 5x cuando se pidieron 50x: se CIERRA."""
    orch, signal = _orch_lev(fake_api, leverage_real=5, lev_pedido=50)
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 50, 1.0)

    assert trade["action"] == "live_failed", "no debio aceptar la operacion"
    assert trade["leverage_requested"] == 50
    assert trade["leverage_actual"] == 5
    assert "apalancamiento" in trade["reason"].lower()

    api = fake_api.instances[-1]
    # primera orden = la entrada, segunda = el cierre con reduceOnly
    assert len(api.orders) == 2, "deberia haber abierto y cerrado"
    assert api.orders[1]["params"].get("reduceOnly") is True, \
        "el cierreAutomatico tiene que ser reduceOnly, si no abre una INVERSA"
    assert api.orders[1]["side"] == "sell", "cerrar una larga es vender"


def test_un_apalancamiento_ilegible_tambien_cierra(fake_api):
    """Si el exchange NO dice cual es el apalancamiento, no se fia.

    None no es "todo bien": es no saber, y con dinero real no saber como
    estas apalancado no es una situacion aceptable.
    """
    orch, signal = _orch_lev(fake_api, leverage_real=None, lev_pedido=50)
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 50, 1.0)

    assert trade["action"] == "live_failed"
    assert trade["leverage_actual"] is None
    assert trade["auto_closed"]["ok"] is True
    assert "ilegible" in trade["error"]


def test_si_el_apalancamiento_coincide_la_operacion_pasa(fake_api):
    """El camino bueno: 10 pedido, 10 real, se opera con normalidad."""
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10)
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade.get("action") != "live_failed", trade.get("error")
    assert trade["leverage"] == 10
    assert trade["margin_usd"] == pytest.approx(1.0)
    api = fake_api.instances[-1]
    assert len(api.orders) == 1, "con el apalancamiento correcto no se cierra"
    assert "stopLoss" in api.orders[0]["params"], "y sigue yendo protejida"


def test_margen_insuficiente_no_llega_a_la_orden(fake_api):
    """Mejor rechazar por nuestra cuenta que tocar la orden a medias."""
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10)
    FakeAPI.margin_available = 0.5      # hace falta 10 de margen
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 10.0)

    assert trade["action"] == "live_failed"
    assert trade["margin_needed"] == pytest.approx(10.0)
    assert trade["margin_available"] == pytest.approx(0.5)
    assert fake_api.instances[-1].orders == [], "no debio mandarse ninguna orden"


def test_un_margen_desconocido_no_impide_operar(fake_api):
    """Si no se sabe el margen, se opera: el exchange es el que rechaza.

    Esto es al reves que el apalancamiento y a proposito. Con el
    apalancamiento, no saber significa que la posicion puede ser 5x mas
    grande de lo que se cree, y eso no se descubre cuando ya esta abierta.
    Con el margen, el exchange no deja abrir sin fondos, y ser conservador
    sin saber dejaria el bot parado sin motivo.
    """
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10)
    FakeAPI.margin_available = None
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 10.0)

    assert trade.get("action") != "live_failed", trade.get("error")
    assert len(fake_api.instances[-1].orders) == 1


def test_set_leverage_trata_el_ya_puesto_como_correcto(fake_api):
    """Bybit NO es idempotente: con el apalancamiento ya puesto devuelve
    110043 "leverage not modified" y ccxt lo lanza como BadRequest.

    Semanticamente dice lo contrario de un fallo: CONFIRMA que ya es el
    pedido. Si se tratara como error, la segunda entrada en adelante se
    rechazaria siempre y el bot dejaria de operar.
    """
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    assert ExchangeAPI is not REAL_EXCHANGE_API, \
        "el fixture deberia haber sustituido la clase por el doble"
    assert REAL_EXCHANGE_API is not None, "no se pudo capturar la clase real"

    class _Client:
        def __init__(self, err):
            self.err = err
            self.calls = 0

        def set_leverage(self, lev, sym, params=None):
            self.calls += 1
            raise self.err

    api = object.__new__(REAL_EXCHANGE_API)
    api._require_auth = lambda: None
    api._to_swap_symbol = lambda s: s

    # 110043: se trata como exito
    api.exchange = _Client(Exception(
        'bybit {"retCode":110043,"retMsg":"leverage not modified"}'))
    r = api.set_leverage("XRP/USDT:USDT", 50)
    assert r.get("already_set") is True, "110043 debe contar como 'ya estaba'"
    assert api.exchange.calls == 1

    # cualquier otro error: se propaga
    api.exchange = _Client(Exception('retCode 110001 order does not exist'))
    with pytest.raises(Exception):
        api.set_leverage("XRP/USDT:USDT", 50)


# ---------------------------------------------------------------------------
# MODO DE MARGEN (2026-09-30)
#
# MEDIDO: la cuenta estaba en `tradeMode=0` (CRUCE) en BTC, XRP y ETH, y
# el motor abria igual: `set_margin_mode` fallaba, se escribia un warning
# y se seguia. En cruce la perdida de una posicion la paga TODA la
# cuenta, no solo el margen de esa posicion: con 5 USDT de capital, la
# diferencia entre "perdi 0,10" y "perdi los 5" es este ajuste.
# ---------------------------------------------------------------------------


def test_en_margen_cruce_se_cierra_la_operacion(fake_api):
    """Se pidio isolated y la posicion esta en CRUCE: se cierra.

    El interruptor se pone a True A PROPOSITO aqui: desde el 2026-09-30 el
    defecto es False porque la cuenta de testnet es unificada y el aislado
    no existe. Este test comprueba que el FRENO FUNCIONA cuando se exige,
    no que se exija siempre.
    """
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10,
                             require_isolated_margin=True)
    FakeAPI.margin_mode_real = "cross"
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade["action"] == "live_failed", "no debio aceptar la operacion"
    assert trade["margin_mode"] == "cross"
    assert "isolated" in trade["error"]
    assert "aislado" in trade["reason"]

    api = fake_api.instances[-1]
    assert len(api.orders) == 2, "debio abrir y cerrar"
    assert api.orders[1]["params"].get("reduceOnly") is True
    assert api.orders[1]["side"] == "sell"


def test_un_margen_ilegible_tambien_cierra(fake_api):
    """Si el exchange NO dice el modo de margen, no se opera.

    None no es "todo bien": es no saber, y en cruce unknowingly es perder
    mas de lo que dice el plan.
    """
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10,
                             require_isolated_margin=True)
    FakeAPI.margin_mode_real = None
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade["action"] == "live_failed"
    assert trade["margin_mode"] is None
    assert trade["auto_closed"]["ok"] is True
    assert "ilegible" in trade["error"]


def test_en_aislado_la_operacion_pasa(fake_api):
    """El camino bueno: isolated verificado, se opera con normalidad."""
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10)
    FakeAPI.margin_mode_real = "isolated"
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade.get("action") != "live_failed", trade.get("error")
    assert len(fake_api.instances[-1].orders) == 1, "no se cierra nada"
    assert "stopLoss" in fake_api.instances[-1].orders[0]["params"]


def test_si_el_islaado_es_imposible_el_motivo_llega_al_informe(fake_api):
    """MEDIDO el 2026-09-30: la cuenta testnet es una UNIFIED ACCOUNT y
    Bybit responde `100028 unified account is forbidden` al pedir aislado.

    O sea que en ESA cuenta no es que el sistema falle: es que el aislado
    NO EXISTE y no se va a conseguir reintentando. Por eso el motivo se
    guarda y se devuelve: un "operacion rechazada" sin causa es
    inaccionable, y el operador no puede arreglar lo que no se le explica.
    """
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10,
                             require_isolated_margin=True)
    FakeAPI.margin_mode_real = "cross"
    FakeAPI.margin_mode_error = (
        'bybit {"retCode":100028,"retMsg":"unified account is forbidden"}')
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade["action"] == "live_failed"
    assert "100028" in trade["margin_mode_origen"], (
        "el motivo real del exchange tiene que llegar al informe")
    assert "unified account" in trade["como_resolver"]
    assert "require_isolated_margin=False" in trade["como_resolver"], (
        "tiene que decir cual es la salida, no solo que fallo")


def test_con_require_isolated_false_se_opera_a_conciencia(fake_api):
    """Ponerlo a False es una DECISION, no un forget: entonces se abre y
    se avisa por el log de que la perdida la paga toda la cuenta."""
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10,
                             require_isolated_margin=False)
    FakeAPI.margin_mode_real = "cross"
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade.get("action") != "live_failed", trade.get("error")
    assert len(fake_api.instances[-1].orders) == 1, "se abre, no se cierra"
    assert "stopLoss" in fake_api.instances[-1].orders[0]["params"], (
        "y sigue yendo protejida aunque se acepte el cruce")


def test_el_sl_se_calcula_con_el_precio_FRESCO_del_exchange(fake_api):
    """EL BUG MEDIDO el 2026-09-30 con XRP en velas de 5 min.

    El TP/SL se calculaba con `signal["price"]`, que es el precio de
    INICIO DE CICLO: antes de generar hipotesis, hacer backtests y pasar
    el MLP por delante. Medido: XRP se mueve 0,217% de mediana por vela de
    5 min, y el SL a 100x esta a 0,25%. Con 2,2% de retraso el SL llegaba
    POR ENCIMA del precio de ejecucion y Bybit rechazaba la orden entera:

        StopLoss:157620000 set for Buy position should lower than
        base_price:154560000

    Aqui el precio de la senal es 100 y el del exchange 105: si se usara el
    viejo, el SL (95) estaria por debajo y la orden pasaria por casualidad.
    Con el fresco, el SL se recalcula sobre 105 y sigue siendo coherente.
    """
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10)
    FakeAPI.book_price = 105.0
    signal = dict(signal, price=100.0)          # el precio RANCI de la senal
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade.get("action") != "live_failed", trade.get("error")
    api = fake_api.instances[-1]
    params = api.orders[0]["params"]
    entrada_real = 105.0
    assert params["stopLoss"]["triggerPrice"] == pytest.approx(
        entrada_real * 0.95), "el SL se calculo con el precio rancio"
    assert params["stopLoss"]["triggerPrice"] < entrada_real, (
        "el SL tiene que quedar por DEBAJO del precio al que se compra")
    assert trade["entry_price"] == pytest.approx(entrada_real)


def test_sin_precio_fresco_no_se_manda_la_orden(fake_api):
    """Si no se puede leer el precio actual, NO se opera.

    Mandarla con el precio viejo es peor que no mandarla: el SL caeria del
    lado equivocado, Bybit rechazaria la orden, y en el mejor de los casos
    (que la aceptara) la proteccion estaria donde no toca.
    """
    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10)
    FakeAPI.book_error = "libro caido"
    trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade["action"] == "live_failed"
    assert "precio" in trade["reason"]
    assert trade["price_senal"] == 100.0, "se deja constancia del que se iba a usar"
    assert fake_api.instances[-1].orders == [], "no debio mandarse ninguna orden"


def test_por_defecto_se_opera_en_cruce_pero_se_avisa(fake_api, caplog):
    """DECISION DE LEONARDO, 2026-09-30: el defecto pasa a False.

    Motivo medido: la cuenta de testnet es una UNIFIED ACCOUNT y Bybit
    responde `100028 unified account is forbidden` al pedir aislado. El
    aislado NO EXISTE ahi, luego exigirlo por defecto dejaba el sistema sin
    operar nunca.

    Y no es relajar la garantia a la ligera: con nocional pequeno el riesgo
    esta acotado por el nocional, no por el modo de margen. Con 5 USDT y un
    SL al 0,5% se pierden 0,025 USDT; hasta la liquidacion, 0,083; y el
    peor caso absoluto son 5 USDT si el activo cae a cero.

    Lo que NO se negocia: se avisa. Si se opera en cruce, el log lo dice.
    """
    import logging
    from quant_math.orchestrator import OrchestratorConfig
    # el defecto de la config, sin pasar nada a mano
    with tempfile.TemporaryDirectory() as tmp:
        cfg = OrchestratorConfig(
            symbols=["BTC/USDT:USDT"], timeframe="1h", lookback_days=30,
            min_paper_trades=1, hypotheses_per_cycle=1,
            kb_path=f"{tmp}/kb.jsonl", state_dir=tmp, initial_capital=1000.0,
            entry_pct=0.05, take_profit_pct=0.05, leverage=10, mode="classic",
            dry_run=False, testnet=True)
        assert cfg.require_isolated_margin is False, (
            "el defecto debe permitir operar en una cuenta unificada")

    orch, signal = _orch_lev(fake_api, leverage_real=10, lev_pedido=10)
    FakeAPI.margin_mode_real = "cross"
    with caplog.at_level(logging.ERROR):
        trade = orch._execute_live_order(signal, 100.0, "buy", 100.0, 10, 1.0)

    assert trade.get("action") != "live_failed", trade.get("error")
    texto = caplog.text
    assert "CRUCE" in texto, "operar en cruce tiene que quedar en el log"
    assert "TODA la cuenta" in texto, "y decir exactamente que significa"


def test_una_entrada_que_el_exchange_rechaza_no_deja_posicion(fake_api):
    """EL BUG MEDIDO el 2026-09-30 con el brazo corriendo en testnet.

    `decide()` REGISTRA la posicion en `open_positions` antes de que se
    mande la orden. Cuando la orden se rechaza (apalancamiento que no
    cuadra, margen que no es aislado, margen insuficiente), la posicion se
    queda en el estado local sin haber existido jamas en el exchange.

    El log de aquella corrida decia `abiertas 1/5 | sin marcar 1` con 0
    posiciones en el exchange: el brazo contandose una posicion viva que
    no existia. Y como ademas no se registro la entrada, `_last_entry_sizing`
    caeria en su fallback y el PnL de un cierre posterior seria erroneo.
    """
    from quant_math.decision_engine import DecisionEngine
    import tempfile, json as _json
    tmp = tempfile.mkdtemp(prefix="abandon-")
    eng = DecisionEngine(symbols=["BTC/USDT:USDT"], kb_path=f"{tmp}/kb.jsonl",
                         state_dir=tmp, min_paper_trades=1, use_postgres=False,
                         data_provider=lambda s: None)
    key = eng._position_key("h1", "BTC/USDT:USDT")
    eng.open_positions[key] = {"symbol": "BTC/USDT:USDT", "side": "buy",
                               "entry_price": 100.0}
    eng.paper_trade_counts[key] = 1
    eng._persist_positions()

    from quant_math.orchestrator import Orchestrator
    o = _orch()
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    orch.cycle_count = 1
    orch.engine = eng

    signal = {"symbol": "BTC/USDT:USDT", "side": "buy", "price": 100.0,
              "hypothesis_id": "h1", "expectancy": 0.01,
              "timestamp": 1790000000000}
    orch._abandon_if_rejected(signal, {"action": "live_failed",
                                       "error": "margen cross"})

    assert key not in eng.open_positions, \
        "una entrada rechazada no puede quedar como posicion viva"
    assert eng.paper_trade_counts.get(key, 0) == 0, (
        "y tampoco puede contar como operacion: la hipotesis no se opero")
    with open(os.path.join(tmp, "paper_executions.jsonl"), "a",
              encoding="utf-8") as fh:
        fh.write("")           # toca el fichero vacio, a proposito
    with open(eng.paper_trades_path, encoding="utf-8") as fh:
        filas = [_json.loads(l) for l in fh if l.strip()]
    assert filas[-1]["count"] == 0, "el contador escrito tambien se corrige"


def test_una_entrada_que_si_se_abrió_no_se_retira(fake_api):
    """Lo contrario: si la orden SI salio, la posicion se queda. Un
    retraction que se~” fires con la misma logica dejaria al brazo sin
    posiciones y perderia el control del riesgo."""
    from quant_math.decision_engine import DecisionEngine
    import tempfile
    tmp = tempfile.mkdtemp(prefix="abandon2-")
    eng = DecisionEngine(symbols=["BTC/USDT:USDT"], kb_path=f"{tmp}/kb.jsonl",
                         state_dir=tmp, min_paper_trades=1, use_postgres=False,
                         data_provider=lambda s: None)
    key = eng._position_key("h1", "BTC/USDT:USDT")
    eng.open_positions[key] = {"symbol": "BTC/USDT:USDT", "side": "buy",
                               "entry_price": 100.0}

    from quant_math.orchestrator import Orchestrator
    o = _orch()
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = o
    orch.cycle_count = 1
    orch.engine = eng
    signal = {"symbol": "BTC/USDT:USDT", "side": "buy", "price": 100.0,
              "hypothesis_id": "h1", "expectancy": 0.01,
              "timestamp": 1790000000000}
    orch._abandon_if_rejected(signal, {"mode": "live-testnet",
                                       "leverage": 10})
    assert key in eng.open_positions, "una entrada abierta no se retira"


def test_el_wizard_devuelve_aislado_TAL_COMO_se_contesta(fake_api, monkeypatch):
    """EL BUG QUE SE LLEVO HORAS DE OPERACIONES (2026-09-30).

    `_ask_isolated` tenia un `not bool(...)` delante, o sea que devolvia lo
    CONTRARIO de lo que el operador elegia:

        contesta NO  ->  confirm()=False  ->  not False = True
        se guardaba require_isolated_margin=True  y el motor rechazaba
        TODAS las ordenes.

    Leonardo lo vio en pantalla ("No") y el sistema hizo lo contrario:
    cero entradas en horas, con el log lleno de "margen cross, se pidio
    isolated". Un bot que no opera parece un bot aprendiendo, y por eso el
    sintoma no senala a nadie al culpable.

    Se prueban LAS DOS respuestas. Un solo caso dejaria pasar la mitad de
    la inversion, que es justo el otro fallo posible.
    """
    import quant_math.cli.main as cli
    class _Respuesta:
        def __init__(self, valor):
            self.valor = valor

        def unsafe_ask(self):
            return self.valor

    def _confirmar(*_a, **_k):
        return _Respuesta(respuesta)

    class _Plan:
        sl_price_distance = 0.005
        liquidation_price_distance = 0.0167

    # --- contesto SI: quiero exigir aislado ---
    respuesta = True
    monkeypatch.setattr(cli.questionary, "confirm", _confirmar)
    assert cli._ask_isolated(5.0, _Plan()) is True, (
        "contestar SI tiene que guardar require_isolated_margin=True")

    # --- contesto NO: quiero operar en cruce ---
    respuesta = False
    assert cli._ask_isolated(5.0, _Plan()) is False, (
        "contestar NO tiene que guardar require_isolated_margin=False; "
        "invertirlo fue el bug que dejo el bot sin operar")


def test_el_wizard_de_nocional_tampoco_puede_invertir(fake_api, monkeypatch):
    """El mismo riesgo en la otra pregunta del wizard.

    `_ask_notional_cap` NO lleva confirmacion, se teclea el numero, asi que
    la inversion ahi seria otra cosa: que un valor valido se rechace o que
    uno invalido se acepte. Se comprueban los dos extremos.
    """
    import quant_math.cli.main as cli
    respuesta = {"v": "1.0"}

    class _Texto:
        def __init__(self, *_a, **_k):
            pass

        def unsafe_ask(self):
            return respuesta["v"]

    monkeypatch.setattr(cli.questionary, "text", _Texto)
    monkeypatch.setattr(cli.questionary, "confirm",
                        lambda *a, **k: type("R", (), {"unsafe_ask":
                                                       lambda s: True})())
    assert cli._ask_notional_cap(5.0, 50, 0.005) == pytest.approx(1.0)
    respuesta["v"] = "0.5"
    assert cli._ask_notional_cap(5.0, 50, 0.005) == pytest.approx(0.5)


def test_read_back_margin_mode_traduce_el_tradeMode_de_bybit():
    """Bybit V5 devuelve 0=cruce, 1=aislado. Que se traduzca bien importa:
    invertirlo abriria justo lo que se quiere impedir."""
    # OJO: se usa REAL_EXCHANGE_API, NO un import de ExchangeAPI aqui
    # dentro. El fixture `fake_api` sustituye esa clase por el doble, y un
    # import en el cuerpo del test traeria el doble: el metodo probado
    # seria el del doble y el test pasaria sin probar nada. (Ya paso una
    # vez en este mismo fichero con set_leverage.)
    assert REAL_EXCHANGE_API is not None

    class _Cliente:
        def __init__(self, filas):
            self.filas = filas
            self._require_auth = None

        def privateGetV5PositionList(self, params):
            return {"result": {"list": self.filas}}

    api = object.__new__(REAL_EXCHANGE_API)
    api._require_auth = lambda: None
    api._to_swap_symbol = lambda s: s

    for valor, esperado in ((1, "isolated"), (0, "cross")):
        api.exchange = _Cliente([{"tradeMode": valor}])
        assert api.read_back_margin_mode("BTCUSDT") == esperado, (
            f"tradeMode={valor} deberia ser {esperado}")

    # Sin dato o ilegible -> None, que es "NO SE SABE", no "aislado".
    for filas in ([], [{"otro": 1}], [{"tradeMode": "x"}]):
        api.exchange = _Cliente(filas)
        assert api.read_back_margin_mode("BTCUSDT") is None


def test_un_auto_cierre_que_no_puede_mandar_no_grita_alarma_falsa(fake_api):
    """EL FALLO QUE SALIO MEDIDO el 2026-09-30 contra testnet.

    Al intentar cerrar por segunda vez, Bybit responde `110017 current
    position is zero, cannot fix reduce-only order qty`. El codigo lo
    traducía por "HAY UNA POSICION VIVA SIN VERIFICAR", cuando en realidad
    NO quedaba ninguna: ya estaba cerrada.

    Una alarma falsa es tan dana como no dar ninguna, porque entrena a
    ignorar el log, que es justo lo que haria falta creerse el dia que SI
    hubiera una posicion sin cerrar.
    """
    from quant_math.orchestrator import Orchestrator
    orch = Orchestrator.__new__(Orchestrator)

    class _SinPosicion:
        """reduceOnly sobre una posicion que no existe: 110017."""
        def create_order(self, *a, **k):
            raise Exception('bybit {"retCode":110017,"retMsg":"current '
                            'position is zero, cannot fix reduce-only '
                            'order qty"}')

        def fetch_positions(self, symbols=None):
            return [{"contracts": 0.0}]

    r = orch._cerrar_si_no_verifica(_SinPosicion(), "BTC/USDT:USDT", "buy",
                                    1.0, "prueba")
    assert r["ok"] is True, "no hay posicion viva: no es un fallo"
    assert r.get("already_closed") is True
    assert r["posicion_sin_cerrar"] is False, \
        "gritar que queda viva una posicion que no existe"


def test_un_auto_cierre_que_falla_con_posicion_viva_sigue_gritando(fake_api):
    """La alarma VERDADERA se conserva: si queda posicion, se dice."""
    from quant_math.orchestrator import Orchestrator
    orch = Orchestrator.__new__(Orchestrator)

    class _NoCierra:
        def create_order(self, *a, **k):
            raise Exception('retCode 110001 order does not exist')

        def fetch_positions(self, symbols=None):
            return [{"contracts": 3.3, "side": "buy"}]

    r = orch._cerrar_si_no_verifica(_NoCierra(), "BTC/USDT:USDT", "buy",
                                    3.3, "prueba")
    assert r["ok"] is False
    assert r["posicion_sin_cerrar"] is True, "aqui SI queda posicion viva"


def test_si_no_se_puede_comprobar_no_se_inventa_la_veredicto(fake_api):
    """Sin poder preguntar al exchange: se dice que NO SE SABE.

    `None` es "desconocido", y se distingue de False a proposito. Ante la
    duda no se elige el veredicto que deja al operador tranquilo.
    """
    from quant_math.orchestrator import Orchestrator
    orch = Orchestrator.__new__(Orchestrator)

    class _NoSePuedeLeer:
        def create_order(self, *a, **k):
            raise Exception("fallo de red")

        def fetch_positions(self, symbols=None):
            raise Exception("fallo de red")

    r = orch._cerrar_si_no_verifica(_NoSePuedeLeer(), "BTC/USDT:USDT",
                                    "buy", 1.0, "prueba")
    assert r["posicion_sin_cerrar"] is None, "desconocido != cerrado"
    assert r["ok"] is False
    assert "aviso" in r


# ---------------------------------------------------------------------------
# EL SL SE COMPRUEBA, NO SE SUPONE (2026-10-01)
#
# MEDIDO con el brazo corriendo en testnet: una posicion quedo
# DESPROTEGIDA y se liquido al 127,2% del margen con el SL pedido al
# 27,5%. El sistema lo registro como `motivo=sl`: una etiqueta de
# proteccion para algo que nunca llego a ponerse.
#
# Estos tests son COMPORTAMIENTO, no codigo: montan el doble para que el
# exchange acepte la orden y luego se coma el SL, que es lo que hacia
# falta. Un test de codigo ("esta read_back_stops en el fuente") verifica
# que la comprobacion este escrita, no que haga algo.

def _orch_live(**cfg_over):
    """Orchestrator real (no doble) para llamar a `_execute_live_order`.

    Los tests de proteccion necesitan el ORQUESTADOR de verdad: el doble
    solo verifica como se construye la llamada, no que la comprobacion
    exista. Un test que verifica un doble no verifica nada.
    """
    from quant_math.orchestrator import Orchestrator
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = _orch(**cfg_over)
    orch.cycle_count = 1
    return orch


def _senal():
    return {"symbol": "BTC/USDT:USDT", "side": "buy", "price": 100.0,
            "hypothesis_id": "h1", "expectancy": 0.01,
            "timestamp": 1790000000000}


def test_si_el_exchange_se_traga_el_sl_la_posicion_se_cierra(fake_api):
    """El caso real: la orden entra, pero el exchange no pone el SL.

    Con el codigo viejo la operacion se daba por buena: el bot creia que
    tenia un SL al 27,5% cuando en realidad la posicion no tenia NADA, y
    el unico motivo por el que no se perdia mas era que la cuenta se
    liquidara antes. El SL era un numero en un diccionario local.
    """
    fake_api.stops_drop = True          # el exchange acepta y NO protege
    orch = _orch_live(dry_run=False)
    trade = orch._execute_live_order(_senal(), 100.0, "buy", 500.0, 10, 50.0)

    assert trade.get("action") == "live_failed", (
        "una posicion sin SL en el exchange NO puede darse por buena: "
        "tiene que cerrarse. Con el codigo viejo, trade['action'] era "
        "'entry' y el bot operaba sin proteccion ninguna")
    assert "SL" in str(trade.get("error", ""))
    assert trade.get("auto_closed") is not None, (
        "el cierre tiene que ocurrir, no solo anotarse como fallo: si no, "
        "la posicion se queda viva sin proteccion y sin nadie que la vigile")


def test_si_no_se_puede_leer_el_sl_tambien_se_cierra(fake_api):
    """Un None es 'no lo se', no 'esta bien'.

    Es la distincion que faltaba. Con el codigo viejo, no leer nada se
    confundia con que no hubiera nada que proteger.
    """
    # El exchange no DEJA leer los stops. Se simula con una excepcion, que
    # es como se manifiesta de verdad una llamada que falla por red: no
    # con un None. Poner `stops_real = None` NO servia, porque `create_order`
    # lo rellena con lo que se le pidio y a la hora de leer ya no era None.
    original = FakeAPI.read_back_stops

    def _no_se_puede_leer(self, symbol):
        raise RuntimeError("timeout leyendo la posicion")

    FakeAPI.read_back_stops = _no_se_puede_leer
    try:
        orch = _orch_live(dry_run=False)
        trade = orch._execute_live_order(_senal(), 100.0, "buy",
                                         500.0, 10, 50.0)
    finally:
        FakeAPI.read_back_stops = original

    assert trade.get("action") == "live_failed", (
        "no poder LEER la proteccion tiene que fallar cerrado: el riesgo "
        "de seguir operando sin saber si hay SL es mayor que el spread de "
        "cerrar y volver a abrir")


def test_si_el_sl_esta_presente_y_correcto_la_operacion_se_acepta(fake_api):
    """El camino bueno: el exchange pone el SL y se opera.

    Se comprueba para que el arreglo del SL no se convierta en 'no se
    opera nunca': cerrando de mas tampoco se gana.
    """
    orch = _orch_live(dry_run=False)
    trade = orch._execute_live_order(_senal(), 100.0, "buy", 500.0, 10, 50.0)

    assert trade.get("action") != "live_failed", (
        f"el exchange puso el SL correcto: la operacion tiene que "
        f"aceptarse, no cerrarse. Cerrar de mas tampoco se gana: {trade}")
    assert trade.get("exchange_order_id"), "no se registro la orden en vivo"
    enviados = [o for api in fake_api.instances for o in api.orders]
    params = enviados[0]["params"]
    entrada = fake_api.instances[-1].book_price
    assert params["stopLoss"]["triggerPrice"] == pytest.approx(entrada * 0.95), (
        "el SL se calcula sobre el ASK de entrada (el precio que se paga), "
        "no sobre el precio rancio de la senal: en una compra se paga el "
        "ask y Bybit valida base_price contra ese mismo lado")
    assert params["stopLoss"]["triggerBy"] == "MarkPrice", (
        "el SL tiene que dispararse por MarkPrice, que es la misma base "
        "que usa la liquidacion. Con LastPrice, un mark que se adelanta "
        "cruza la liquidacion ANTES de que el stop llegue a dispararse: "
        "medido, salida al 127,2% del margen con un SL pedido al 27,5%")


def test_un_sl_que_no_cuadra_tambien_cierra(fake_api):
    """No basta con que HAYA SL: tiene que ser el pedido.

    Un exchange que pone el SL en otro sitio (o con otro redondeo grande)
    deja la posicion expuesta igual. Aqui el exchange devuelve un SL
    deliberadamente equivocado.
    """
    orch = _orch_live(dry_run=False)

    # Intercepta la lectura: el exchange "pone" un SL que no es el pedido.
    original = FakeAPI.read_back_stops

    def _sl_malo(self, symbol):
        d = original(self, symbol)
        d["stopLoss"] = 99.0            # muy por debajo: no protege
        return d
    FakeAPI.read_back_stops = _sl_malo
    try:
        trade = orch._execute_live_order(_senal(), 100.0, "buy",
                                         500.0, 10, 50.0)
    finally:
        FakeAPI.read_back_stops = original

    assert trade.get("action") == "live_failed", (
        "un SL presente pero INCORRECTO deja la posicion expuesta: "
        "tiene queClosing la operacion")
    assert trade.get("stop_loss_real") == 99.0
