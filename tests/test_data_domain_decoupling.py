"""
Correccion 5 (2026-09-29) — el dominio de DATOS y el venue de ORDENES son
dos ejes y no pueden volver a confundirse.

Que rompia: un unico flag (`sandbox`) gobernaba los dos. Como `.env` trae
`BYBIT_TESTNET=true`, el research leia velas del TESTNET —precios que no son
los del mercado— durante 182 ciclos. Medido: BTCUSDT ultimo cierre mainnet
83.465,6 vs testnet 83.532,6.

Estos tests son OFFLINE: no tocan la red. Interceptan ccxt y comprueban COMO
se construyen los dos clientes, que es justo donde estaba el error.
"""

import os

import pytest


@pytest.fixture
def fake_ccxt(monkeypatch):
    """Sustituye ccxt por un doble que registra la config con la que se creo."""
    created = []

    class FakeExchange:
        def __init__(self, config):
            self.config = dict(config)
            self.sandbox = bool(config.get("sandbox"))
            self.apiKey = config.get("apiKey")
            self.secret = config.get("secret")
            self.markets = None  # ccxt lo deja a None hasta load_markets()
            created.append(self)

        # ccxt llama a load_markets() en cuanto toca markets
        def load_markets(self):
            return {"BTC/USDT:USDT": {}}

        def set_sandbox_mode(self, enabled):
            self.sandbox = bool(enabled)

        # Catálogo de mercados, como ccxt: se rellena con load_markets().
        # Deliberadamente empieza VACIO para reproducir el caso real, donde
        # `markets` es None hasta que se carga y un normalizador que lo
        # asumiera poblado no detectaria nada.
        MARKETS = {
            "BTC/USDT": {"type": "spot"},
            "BTC/USDT:USDT": {"type": "swap"},
            "ETH/USDT": {"type": "spot"},
            "ETH/USDT:USDT": {"type": "swap"},
            "BTC/USDC": {"type": "spot"},  # spot sin perpetual equivalente
        }

        def load_markets(self):
            self.markets = dict(self.MARKETS)
            return self.markets

    class FakeCcxt:
        bybit = FakeExchange

    from data_acquisition.data_sources import exchanges
    monkeypatch.setattr(exchanges, "ccxt", FakeCcxt)
    return created


@pytest.fixture
def clean_env(monkeypatch):
    """Deja el entorno sin los dos flags, para partir de una base conocida."""
    monkeypatch.delenv("BYBIT_TESTNET", raising=False)
    monkeypatch.delenv("BYBIT_DATA_SANDBOX", raising=False)
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)


def test_bybit_testnet_no_arrastra_las_velas_al_testnet(fake_ccxt, clean_env, monkeypatch):
    """EL BUG: BYBIT_TESTNET decidia tambien de donde salian los velas.

    Con el codigo viejo, sandbox=True acaparaba el unico cliente y las velas
    iban a testnet. Ahora solo mueve el venue de ordenes.
    """
    monkeypatch.setenv("BYBIT_TESTNET", "true")

    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")

    assert api.exchange.sandbox is True, "las ordenes deben seguir yendo a testnet"
    assert api.data_client.sandbox is False, (
        "las velas deben ir al mercado real aunque las ordenes vayan a testnet"
    )


def test_datos_mainnet_por_defecto(fake_ccxt, clean_env):
    """Sin ningun flag, los datos son del mercado real (decision de Leonardo)."""
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    assert api.data_client.sandbox is False


def test_data_sandbox_es_explicito(fake_ccxt, clean_env, monkeypatch):
    """Leer velas de testnet se tiene que pedir a proposito."""
    monkeypatch.setenv("BYBIT_DATA_SANDBOX", "1")
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    assert api.data_client.sandbox is True


def test_el_default_de_ordenes_sigue_siendo_seguro(fake_ccxt, clean_env):
    """is_testnet() NO se toca: es lo que evita operar en real por error.

    Cambiar el default de DATOS no puede relajar el de ORDENES.
    """
    from data_acquisition.data_sources.exchanges import is_testnet
    assert is_testnet() is True


def test_set_sandbox_mode_no_arrastra_los_datos(fake_ccxt, clean_env):
    """Conmutar el sandbox de ordenes no devuelve el research al testnet.

    Es el segundo camino por el que el bug volvia: si algo llamaba a
    set_sandbox_mode(True), las velas se iban a testnet sin pedirlo.
    """
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    before = api.data_client
    api.set_sandbox_mode(True)
    assert api.data_client is before, "el cliente de datos no debe cambiar"


def test_el_cliente_publico_no_lleva_claves(fake_ccxt, clean_env, monkeypatch):
    """Las velas son publicas: el cliente de datos no arrastra credenciales."""
    monkeypatch.setenv("BYBIT_TESTNET", "true")
    monkeypatch.setenv("BYBIT_API_KEY", "CLAVE_FICTICIA")
    monkeypatch.setenv("BYBIT_API_SECRET", "SECRETO_FICTICIO")

    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    assert api.exchange.apiKey == "CLAVE_FICTICIA", "las ordenes si necesitan claves"
    assert api.data_client.apiKey is None, "el feed de mercado no lleva claves"


# ------------------------------------------------------------------
# Simbolo de datos: spot vs perpetual
# ------------------------------------------------------------------
# Medido el 2026-09-29 en mainnet: `BTC/USDT` y `BTC/USDT:USDT` son dos
# mercados DISTINTOS para ccxt (spot 83.601,4 / perp 83.559,1). El sistema
# entero es de perps (apalancamiento, funding, liquidacion) y el wizard
# ofrecia `BTC/USDT` por defecto, asi que se leian velas de SPOT creyendo
# que eran del perp. Los dos precios son plausibles: el fallo era silencioso.


def test_simbolo_sin_sufijo_se_normaliza_al_perpetual(fake_ccxt, clean_env):
    """`BTC/USDT` es SPOT: la ruta de datos debe pedir el PERPETUAL."""
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    assert api._to_data_symbol("BTC/USDT") == "BTC/USDT:USDT"


def test_simbolo_ya_canonico_no_se_toca(fake_ccxt, clean_env):
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    assert api._to_data_symbol("BTC/USDT:USDT") == "BTC/USDT:USDT"


def test_un_spot_sin_perpetual_se_deja_como_esta(fake_ccxt, clean_env):
    """`BTC/USDC` no tiene perpetual: no hay que inventar un sufijo.

    Se deja como spot, pero el codigo avisa por log: con apalancamiento
    medir un spot no es lo que se operaria.
    """
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    assert api._to_data_symbol("BTC/USDC") == "BTC/USDC"


def test_el_normalizador_carga_los_mercados_si_faltan(fake_ccxt, clean_env):
    """ccxt deja `markets` a None hasta load_markets(): hay que cargarlos.

    Si el normalizador asumiera el catalogo poblado, en el arranque real
    no detectaria ningun spot y devolveria el simbolo sin tocar.
    """
    from data_acquisition.data_sources.exchanges import ExchangeAPI
    api = ExchangeAPI("bybit")
    assert api.data_client.markets is None, "precondicion: el catalogo arranca vacio"
    assert api._to_data_symbol("ETH/USDT") == "ETH/USDT:USDT"
