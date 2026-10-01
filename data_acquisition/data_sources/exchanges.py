"""
CCXT Exchange Integration
Provides unified interface to multiple cryptocurrency exchanges
"""

import os

try:
    import ccxt
except ImportError:
    ccxt = None  # type: ignore  # optional: solo live trading; synthetic/forex-Yahoo sigue ok
from typing import List, Dict, Any, Optional
import time
from datetime import datetime
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Load .env if present (Bybit keys for future live trading)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def api_keys_present() -> bool:
    """True if both BYBIT_API_KEY and BYBIT_API_SECRET are set (env or .env)."""
    return bool(os.getenv("BYBIT_API_KEY") and os.getenv("BYBIT_API_SECRET"))


# DOS EJES DISTINTOS, NO CONFUNDIR (correccion 5, 2026-09-29)
# ------------------------------------------------------------------
# 1. DOMINIO DE DATOS -> de donde salen las VELAS (publico, sin claves)
# 2. VENUE DE ORDENES -> donde acaban las ordenes (privado, con claves)
#
# Antes un solo flag (`sandbox`) gobernaba los dos, y como `.env` trae
# BYBIT_TESTNET=true el sistema leia velas del TESTNET: precios que no son
# los del mercado. Medido el 2026-09-29, BTCUSDT ultimo cierre:
#   mainnet 83.465,6   testnet 83.532,6   -> 67 USD de diferencia.
# Decision de Leonardo 2026-09-29: los datos son del mercado real.
# El venue de ordenes NO cambia de default: sigue siendo testnet-seguro.
def is_testnet() -> bool:
    """VENUE DE ORDENES: True salvo que BYBIT_TESTNET se ponga a false.

    Esto NO dice nada de de donde salen los velas — para eso, `data_sandbox()`.
    Se mantiene el default True a proposito: es lo que evita operar en real
    por accidente. No lo cambies sin revisar el bloqueo de mainnet.
    """
    return os.getenv("BYBIT_TESTNET", "true").lower() not in ("0", "false", "no")


def data_sandbox() -> bool:
    """DOMINIO DE DATOS: si las VELAS salen del sandbox (testnet).

    OJO: esto es un override MANUAL. El valor normal lo decide el venue de
    ordenes, dentro de `ExchangeAPI.__init__` (testnet -> testnet, mainnet
    -> mainnet), porque un TP/SL calculado sobre el precio de un mercado no
    vale en otro: medido el 2026-09-30, XRP cotiza a 1,501 en mainnet y a
    1,5735 en testnet, y Bybit rechaza el TP si queda por debajo del precio
    de ejecucion.

    Este override existe para el caso raro de querer datos de testnet con
    ordenes en mainnet, o al reves. Ponerlo a mano es raro: por defecto los
    datos siguen a donde se ejecuta.
    """
    return os.getenv("BYBIT_DATA_SANDBOX", "").lower() in ("1", "true", "yes")


class ExchangeAPI:
    """
    CCXT-based exchange interface
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sandbox: bool = False,
        data_venue: Optional[str] = None
    ):
        """
        Initialize exchange connection

        Args:
            exchange_id: Exchange identifier (e.g., 'binance', 'bybit')
                or 'synthetic' for offline/simulated mode
            api_key: API key (optional)
            api_secret: API secret (optional)
            sandbox: Use testnet/sandbox environment
            data_venue: de donde salen los DATOS ("mainnet"|"testnet"|None).
                None = siguen al venue de ordenes. "mainnet" es lo que
                tiene que pasar el motor en PAPER: alli no se manda ninguna
                orden, luego no hay venue de ejecucion al que atenerse, y lo
                que se quiere es el mercado de verdad.
        """
        self.exchange = None
        self.exchange_id = exchange_id

        if exchange_id == 'synthetic':
            # Offline / simulated mode: no real exchange connection.
            # Data must be provided via generate_synthetic_data().
            logger.info("Initialized synthetic (offline) exchange mode")
            return

        if ccxt is None:
            raise ImportError("ccxt no instalado — solo modo 'synthetic' disponible offline. Instalar ccxt para live trading.")
        exchange_class = getattr(ccxt, exchange_id)

        # Auto-load from .env if not passed explicitly (for future live trading)
        if api_key is None:
            api_key = os.getenv("BYBIT_API_KEY") or None
        if api_secret is None:
            api_secret = os.getenv("BYBIT_API_SECRET") or None
        env_testnet = os.getenv("BYBIT_TESTNET", "").lower() in ("1", "true", "yes")
        if env_testnet:
            # SOLO el venue de ordenes. Los datos no se ven afectados: antes
            # este bloque metia las velas en el sandbox y por eso el research
            # corria contra precios del testnet (correccion 5).
            sandbox = True

        base_config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # USDT perpetuals (Futures)
            }
        }

        # 1) Venue de ORDENES: privado, respeta `sandbox` (testnet por
        #    defecto). Es el unico que lleva claves.
        order_config = dict(base_config)
        if api_key:
            order_config['apiKey'] = api_key
        if api_secret:
            order_config['secret'] = api_secret
        if sandbox:
            order_config['sandbox'] = True
        # 2) DOMINIO DE DATOS: los datos SIGUEN al lugar donde se ejecuta,
        #    porque un TP/SL calculado sobre el precio de un mercado no
        #    vale en otro.
        #
        #    Medido el 2026-09-30: XRP cotiza a 1,501 en mainnet y a 1,5735
        #    en testnet, un 4,83% de diferencia. Con los datos en mainnet y
        #    las ordenes en testnet, el TP/SL calculado sobre el feed quedaba
        #    POR DEBAJO del precio de ejecucion y Bybit rechazaba la orden:
        #    "TakeProfit 1,5180 should be higher than base_price 1,5756".
        #
        #    Precedencia (gana la primera que aplique):
        #      1) BYBIT_DATA_VENUE        — override manual del operador
        #      2) data_venue (argumento)  — lo dice quien llama (el motor
        #                                      pone "mainnet" en paper)
        #      3) el venue de ORDENES     — testnet con testnet, mainnet
        #                                      con mainnet
        #
        #    El caso 3 es el que obliga a distinguir PAPER de LIVE. En
        #    paper no hay venue de ejecucion porque no se manda nada, y
        #    aprender contra precios de testnet seria aprender sobre datos
        #    falsos. Por eso el motor pasa data_venue="mainnet" en paper.
        _env_venue = str(os.getenv("BYBIT_DATA_VENUE", "")).strip().lower()
        _arg_venue = str(data_venue or "").strip().lower()
        if _env_venue:
            self.data_venue = _env_venue
        elif data_sandbox():
            # BYBIT_DATA_SANDBOX=1 sigue siendo un override valido: es la
            # forma corta de pedir datos de testnet y, de hecho, la que ya
            # se usaba. Se mantiene para no romper a quien la use.
            self.data_venue = "testnet"
        elif _arg_venue:
            self.data_venue = _arg_venue
        else:
            self.data_venue = "testnet" if sandbox else "mainnet"
        if self.data_venue not in ("testnet", "mainnet"):
            self.data_venue = "mainnet"
        self.exchange = exchange_class(order_config)

        # 3) Cliente de DATOS: publico, SIN claves. Sigue al venue de
        #    ordenes salvo que se fuerce con BYBIT_DATA_VENUE. Son dos
        #    clientes y no uno porque en ccxt `sandbox` afecta a velas Y a
        #    ordenes a la vez: con un solo objeto no se puede leer el
        #    mercado real y mandar a testnet.
        self._data_exchange = None
        self._data_sandbox = (self.data_venue == "testnet")
        # El sandbox REAL del venue de ordenes, ya con el env aplicado. Se
        # guarda aparte porque `is_testnet()` y este valor no siempre
        # coinciden (el primero asume True por defecto), y comparar contra
        # el equivocado hacia que el atajo de abajo reutilizara el cliente
        # equivocado.
        self._order_sandbox = bool(sandbox)

        logger.info(
            "Initialized %s exchange connection (ordenes: %s | datos: %s)",
            exchange_id,
            "testnet" if sandbox else "mainnet",
            "testnet" if self._data_sandbox else "mainnet",
        )

    @property
    def data_client(self):
        """Cliente de mercado (velas, libro, ticker). NUNCA lleva ordenes.

        Se construye laxo para no abrir una segunda conexion si nadie pide
        datos.

        NUNCA se reutiliza el cliente de ordenes, ni siquiera cuando los dos
       estan en el mismo venue. Antes si se hacia, cuando `_data_sandbox`
        coincidia con el del exchange, y era inocuo porque el de datos
        siempre iba a mainnet y el de ordenes a testnet. Desde el
        2026-09-30 los dos pueden ser testnet a la vez, y el atajo devolvia
        el cliente CON CLAVES: el feed de mercado, que deberia ser publico,
        pasaba a llevar credenciales. Ahorrar una conexion no compra nada
        frente a romper esa garantia.
        """
        if self._data_exchange is None:
            cfg = {
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'},
            }
            if self._data_sandbox:
                cfg['sandbox'] = True
            self._data_exchange = getattr(ccxt, self.exchange_id)(cfg)
        return self._data_exchange

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        since: Optional[int] = None,
        limit: int = 1000
    ) -> List[List]:
        """
        Fetch OHLCV (candlestick) data

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            since: Timestamp in milliseconds
            limit: Number of candles to fetch

        Returns:
            List of [timestamp, open, high, low, close, volume] lists
        """
        symbol = self._to_data_symbol(symbol)
        # Reintentos con backoff: un timeout transitorio de una pagina no
        # debe abortar el ciclo completo del orchestrator (F1).
        last_err = None
        for attempt in range(1, 4):
            try:
                ohlcv = self.data_client.fetch_ohlcv(
                    symbol,
                    timeframe,
                    since=since,
                    limit=limit
                )
                logger.info(f"Fetched {len(ohlcv)} candles for {symbol}")
                return ohlcv
            except Exception as e:
                last_err = e
                if attempt < 3:
                    wait_s = 2 ** attempt
                    logger.warning(
                        f"OHLCV intento {attempt}/3 fallo ({e}); reintento "
                        f"en {wait_s}s")
                    time.sleep(wait_s)
        logger.error(f"Failed to fetch OHLCV tras 3 intentos: {last_err}")
        raise last_err

    def fetch_order_book(
        self,
        symbol: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Fetch order book data

        Args:
            symbol: Trading pair
            limit: Number of depth levels

        Returns:
            Order book as dictionary
        """
        try:
            order_book = self.data_client.fetch_order_book(symbol, limit)
            return order_book

        except Exception as e:
            logger.error(f"Failed to fetch order book: {e}")
            raise

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker information

        Args:
            symbol: Trading pair

        Returns:
            Ticker data dictionary
        """
        try:
            ticker = self.data_client.fetch_ticker(symbol)
            return ticker

        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            raise

    def fetch_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Fetch recent trades

        Args:
            symbol: Trading pair
            limit: Number of recent trades

        Returns:
            List of trade dictionaries
        """
        try:
            trades = self.data_client.fetch_trades(symbol, limit=limit)
            return trades

        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            raise

    def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance

        Returns:
            Balance information dictionary
        """
        try:
            balance = self.exchange.fetch_balance()
            return balance

        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise

    # ------------------------------------------------------------------
    # Live trading (Fase 2-4: Bybit USDT perpetuals). All methods require
    # API keys (.env BYBIT_API_KEY/SECRET) and raise RuntimeError otherwise.
    # Nothing here is called while dry_run=True.
    # ------------------------------------------------------------------

    def _require_auth(self) -> None:
        if self.exchange is None:
            raise RuntimeError("exchange not initialized")
        if not self.exchange.apiKey or not self.exchange.secret:
            raise RuntimeError(
                "live trading needs BYBIT_API_KEY and BYBIT_API_SECRET in .env"
            )

    @staticmethod
    def _to_swap_symbol(symbol: str) -> str:
        """BTC/USDT -> BTC/USDT:USDT for Bybit perpetuals."""
        if ":" not in symbol and symbol.endswith("/USDT"):
            return symbol + ":USDT"
        return symbol

    def _to_data_symbol(self, symbol: str) -> str:
        """Normaliza el simbolo de la RUTA DE DATOS al mercado correcto.

        Medido el 2026-09-29: `BTC/USDT` y `BTC/USDT:USDT` son dos mercados
        distintos en ccxt — el primero SPOT (83.601,4) y el segundo el
        PERPETUAL (83.559,1). El sistema entero es de perps (apalancamiento,
        funding, liquidacion) y el wizard ofrecia `BTC/USDT` por defecto, asi
        que se leian velas de spot creyendo que eran del perp. Los dos precios
        son plausibles, asi que el fallo era SILENCIOSO.

        No se fuerza el sufijo a ciegas: solo se corrige si el simbolo tal
        cual resuelve a spot Y existe su equivalente perpetual. Un par de spot
        de verdad (BTC/USDC) o un par de forex se queda como esta.
        """
        if self._data_exchange is None and self._data_sandbox == self._order_sandbox:
            # Puede que aun no haya cliente de datos construido.
            try:
                self.data_client
            except Exception as exc:  # pragma: no cover - sin red
                logger.warning("[datos] no se pudo normalizar %s: %s", symbol, exc)
                return symbol
        markets = getattr(self.data_client, "markets", None)
        if not markets:
            # ccxt no tiene los mercados hasta que se piden. Se cargan una
            # vez (ccxt los cachea) y de ahi en adelante es una lookup.
            try:
                self.data_client.load_markets()
                markets = getattr(self.data_client, "markets", None)
            except Exception as exc:  # pragma: no cover - sin red
                logger.warning("[datos] no se pudieron cargar los mercados: %s", exc)
                return symbol
        if not markets:
            return symbol
        actual = markets.get(symbol)
        if actual is None or actual.get("type") != "spot":
            return symbol
        swap = self._to_swap_symbol(symbol)
        if swap == symbol or markets.get(swap) is None:
            # Es un spot de verdad: no hay perpetual equivalente. Se deja
            # como esta, pero se dice, porque un spot con apalancamiento no
            # tiene sentido en este sistema.
            logger.warning(
                "[datos] %s es SPOT y no tiene perpetual equivalente: se "
                "mide spot. Con apalancamiento eso no es lo que se operaria.",
                symbol)
            return symbol
        logger.info(
            "[datos] %s -> %s (perp): el simbolo sin sufijo es SPOT y el "
            "sistema opera perps", symbol, swap)
        return swap

    def set_sandbox_mode(self, enabled: bool = True) -> None:
        """Venue de ORDENES: Bybit Testnet (sandbox) o Mainnet.

        No toca el cliente de datos a proposito: conmutar el sandbox de
        mercado seria devolver el research al testnet sin que nadie lo pidiera
        (el bug que corrigio la separacion). Para leer velas de testnet hay
        que arrancar con BYBIT_DATA_SANDBOX=1.
        """
        self.exchange.set_sandbox_mode(enabled)
        logger.info("sandbox mode (ordenes): %s", enabled)

    def set_leverage(self, symbol: str, leverage: int,
                     params: Optional[Dict] = None) -> Any:
        """Set leverage for a perpetual symbol.

        IDEMPOTENTE A PROPOSITO, y hace falta. Medido el 2026-09-30:
        `set_leverage(50)` con la cuenta ya en 50 devuelve
        `retCode 110043 "leverage not modified"` y ccxt lo lanza como
        `BadRequest`. Semanticamente ese error dice lo CONTRARIO de un
        fallo: confirma que el apalancamiento ya es el pedido. Si se
        tratara como fallo, la segunda entrada en adelante se rechazaria
        siempre y el bot no operaria nunca mas.

        La garantia real de que el apalancamiento es el pedido la da
        `read_back_leverage()` DESPUES de abrir, no esta llamada: poner el
        valor y que el exchange lo acepte no prueba que la posicion se
        abriera con el.
        """
        self._require_auth()
        swap = self._to_swap_symbol(symbol)
        try:
            result = self.exchange.set_leverage(int(leverage), swap,
                                                 params or {})
        except Exception as exc:
            texto = str(exc)
            if "110043" in texto or "leverage not modified" in texto.lower():
                logger.info("set leverage %sx en %s: ya estaba asi "
                            "(Bybit 110043), se da por correcto",
                            leverage, swap)
                return {"retCode": 0, "retMsg": "leverage not modified "
                                                "(ya era el pedido)",
                        "already_set": True}
            raise
        logger.info("set leverage %sx on %s", leverage, swap)
        return result

    def fetch_positions(self, symbols: Optional[List[str]] = None
                        ) -> List[Dict[str, Any]]:
        """Posiciones del VENUE DE ORDENES (testnet si `sandbox`).

        Se leen del cliente de ordenes y NO del de datos a proposito: en
        testnet son mercados distintos (medido: XRP 1,501 en mainnet y
        1,5735 en testnet), y lo que importa para una posicion viva es el
        precio y la liquidacion del sitio donde se ejecuta.
        """
        self._require_auth()
        swaps = [self._to_swap_symbol(s) for s in symbols] if symbols else None
        return list(self.exchange.fetch_positions(swaps) or [])

    def read_back_stops(self, symbol: str) -> Dict[str, Optional[float]]:
        """SL y TP REALES de la posicion abierta, leidos del exchange.

        MEDIDO el 2026-10-01: el SL se mandaba en la orden de entrada y
        se daba por puesto. No lo estaba. Una posicion quedo DESPROTEGIDA
        en el exchange y se liquido al 127,2% del margen cuando el SL
        pedia 27,5%: el sistema lo etiquetaba `motivo=sl` aunque nadie
        lo habia ejecutado.

        Por eso esto lee lo que el exchange TENIA, en vez de fiarse de
        lo que le pedimos. Igual que `read_back_leverage`: que devuelva
        None significa "no se pudo comprobar", nunca "esta todo bien".
        Quien llama tiene que fallar cerrado.

        El `triggerBy` tambien se lee, porque no es decorativo:
        Bybit liquida por MarkPrice y pone el SL por LastPrice si no se
        le dice otra cosa, de modo que un mark que se adelanta cruza la
        liquidacion antes de tocar el SL.
        """
        out: Dict[str, Optional[float]] = {"stopLoss": None,
                                           "takeProfit": None,
                                           "stopLoss_triggerBy": None,
                                           "takeProfit_triggerBy": None}
        self._require_auth()
        swap = self._to_swap_symbol(symbol)
        for pos in self.fetch_positions([swap]):
            if not pos.get("contracts"):
                continue
            info = pos.get("info") or {}
            for destino, clave in (("stopLoss", "stopLoss"),
                                   ("takeProfit", "takeProfit")):
                nodo = info.get(clave)
                # MEDIDO el 2026-10-01 contra el exchange: Bybit v5
                # devuelve el precio como CADENA plana
                #   "stopLoss": "2690.63"
                # y no como diccionario. Este lector solo miraba la forma
                # de diccionario, devolvia None, y el guardia post-entrada
                # cerraba posiciones que SI estaban protegidas. Es decir:
                # fallo cerrado pero en la direccion que hace que el sistema
                # no pueda operar nunca. Un guardia que siempre dice "no"
                # es tan inservible como uno que nunca lo dice.
                #
                # Se aceptan las dos formas porque no son inventadas: la
                # plana es la medida hoy en Bybit, y la de diccionario con
                # `triggerBy` aparece en otras respuestas (y es la unica que
                # trae el tipo de disparador).
                if isinstance(nodo, str):
                    try:
                        if nodo.strip() and float(nodo) > 0:
                            out[destino] = float(nodo)
                    except (TypeError, ValueError):
                        pass
                elif isinstance(nodo, dict):
                    precio = nodo.get("stopLossPrice" if destino == "stopLoss"
                                      else "takeProfitPrice")
                    if precio in (None, "", "0", 0):
                        precio = nodo.get("triggerPrice")
                    try:
                        if precio not in (None, "", "0", 0):
                            out[destino] = float(precio)
                    except (TypeError, ValueError):
                        pass
                    tb = nodo.get("triggerBy")
                    if tb:
                        out[f"{destino}_triggerBy"] = str(tb)
            return out
        return out

    def read_back_leverage(self, symbol: str) -> Optional[float]:
        """Apalancamiento REAL de la posicion abierta, leido del exchange.

        Devuelve None si no hay posicion, si el exchange no lo expone, o si
        no se puede leer. None NO es "todo bien": quien llama tiene que
        tratar un None como desconfianza, no como ausencia de problema.
        """
        self._require_auth()
        swap = self._to_swap_symbol(symbol)
        for pos in self.fetch_positions([swap]):
            if not pos.get("contracts"):
                continue
            for campo in ("leverage", "info"):
                val = pos.get(campo)
                if campo == "info" and isinstance(val, dict):
                    val = val.get("leverage")
                try:
                    if val is not None:
                        return float(val)
                except (TypeError, ValueError):
                    continue
        return None

    def read_back_margin_mode(self, symbol: str) -> Optional[str]:
        """Modo de margen REAL de la posicion, leido del exchange.

        Devuelve "isolated", "cross" o None si no se pudo saber. None NO es
        "aislado": quien llama tiene que tratar un None como desconfianza.

        Por que importa mas de lo que parece: en modo CRUCE la perdida de
        una posicion la paga TODA la cuenta, no solo el margen de esa
        posicion. Con 5 USDT de capital, la diferencia entre "perdi 0,10"
        y "perdi los 5" es el modo de margen. Medido el 2026-09-30: la
        cuenta estaba en `tradeMode=0` (cruce) en BTC, XRP y ETH.
        """
        self._require_auth()
        swap = self._to_swap_symbol(symbol)
        # OJO: los endpoints PRIVADOS de Bybit V5 no aceptan el formato de
        # ccxt. Hay que pasar `BTCUSDT`, no `BTC/USDT:USDT`.
        #
        # Y el truco NO es "quitar barras y dos puntos": `BTC/USDT:USDT`
        # se quedaria en `BTCUSDTUSDT`, que tampoco existe. Hay que
        # quitar el sufijo del PERPETUAL (`:USDT`) y despues las barras.
        #
        # Medido el 2026-09-30: con el simbolo mal formado este metodo
        # devolvia SIEMPRE None, o sea que la verificacion PARECIA
        # funcionar cuando en realidad no leia nada. Un chequeo que siempre
        # responde "no se" es peor que no tenerlo, porque aparenta que ha
        # pasado cuando solo ha fallado en silencio.
        crudo = swap.split(":", 1)[0].replace("/", "").upper()
        try:
            resp = self.exchange.privateGetV5PositionList(
                {"category": "linear", "symbol": crudo, "limit": 1})
        except Exception as exc:
            logger.warning("[margin_mode] no se pudo leer: %s", exc)
            return None
        filas = (resp.get("result") or {}).get("list") or []
        if not filas:
            return None
        modo = filas[0].get("tradeMode")
        if modo is None:
            return None
        try:
            modo = int(modo)
        except (TypeError, ValueError):
            return None
        # Bybit V5: 0 = cross, 1 = isolated.
        return "isolated" if modo == 1 else "cross"

    def available_margin(self) -> Optional[float]:
        """MARGEN DISPONIBLE de la cuenta, en la moneda de margen.

        None si el exchange no lo expone. Permite rechazar la entrada por
        falta de fondos ANTES de mandar la orden, en vez de que el exchange
        la rechace (o peor, que la ejecute parcialmente).
        """
        self._require_auth()
        try:
            raw = self.exchange.fetch_balance()
        except Exception as exc:
            logger.warning("[margin] fetch_balance fallo: %s", exc)
            return None
        lista = (raw.get("info") or {}).get("result", {}).get("list", [])
        if not isinstance(lista, list) or not lista:
            return None

        def _num(item: Dict[str, Any], clave: str) -> Optional[float]:
            try:
                if item.get(clave) is not None:
                    return float(item[clave])
            except (TypeError, ValueError):
                return None
            return None

        # Camino corto: si el exchange publica el disponible, se usa tal cual.
        for item in lista:
            v = _num(item, "totalAvailableBalance")
            if v is not None:
                return v
        # Camino largo: disponible = equity - margen usado - margen de
        # ordenes. OJO: `totalOrderMargin` NO es el disponible, es lo
        # inmovilizado por ordenes vivas; sumarlo sin restarlo seria
        # justo el error que hace creerse que hay dinero que no hay.
        for item in lista:
            equity = _num(item, "totalEquity")
            if equity is None:
                continue
            usado = _num(item, "totalUsedMargin") or 0.0
            en_ordenes = _num(item, "totalOrderMargin") or 0.0
            return equity - usado - en_ordenes
        return None

    def set_margin_mode(self, symbol: str, mode: str = "isolated",
                        params: Optional[Dict] = None) -> Any:
        """Set margin mode ('isolated' or 'cross') for a perpetual symbol."""
        self._require_auth()
        if mode not in ("isolated", "cross"):
            raise ValueError("margin mode must be 'isolated' or 'cross'")
        swap = self._to_swap_symbol(symbol)
        result = self.exchange.set_margin_mode(mode, swap, params or {})
        logger.info("set margin mode %s on %s", mode, swap)
        return result

    def cantidad_minima(self, symbol: str) -> Dict[str, Any]:
        """Minimo que el exchange IMPONE para este simbolo. Leido de el.

        MEDIDO el 2026-10-01 contra los mercados de Bybit:

            BTC/USDT:USDT   min_amount 0,001   min_cost 5 USDT
            ETH/USDT:USDT   min_amount 0,01    min_cost 5 USDT
            XRP/USDT:USDT   min_amount 0,1     min_cost 5 USDT
            SOL/USDT:USDT   min_amount 0,1     min_cost 5 USDT

        El minimo DIFIERE por simbolo porque el coste por unidad cambia:
        0,001 BTC son ~83 USDT y 0,001 ETH son ~2,7 USDT, que el exchange
        no acepta. Un minimo global es un numero que no significa nada,
        y usarlo como si lo significara produce ordenes RECHAZADAS.

        El `precision` tambien viene por aqui, porque es lo que decide si
        una cantidad es representable: si el minimo es 0,001 y la
        precision admite 3 decimales, 0,001 es justo lo mas pequeno que se
        puede mandar.
        """
        swap = self._to_swap_symbol(symbol)
        out = {"min_amount": None, "min_cost": None, "precision": None,
               "swap": swap}
        try:
            mercado = (self.exchange.markets.get(swap)
                       or self.exchange.market(swap))
        except Exception:
            return out
        if not mercado:
            return out
        lim = mercado.get("limits") or {}
        out["min_amount"] = ((lim.get("amount") or {}).get("min"))
        out["min_cost"] = ((lim.get("cost") or {}).get("min"))
        out["precision"] = (mercado.get("precision") or {}).get("amount")
        return out

    def ajusta_a_minimo(self, symbol: str, cantidad: float,
                        precio: Optional[float] = None) -> float:
        """Cantidad redondeada ARRIBA al minimo del exchange.

        Por que ARRIBA y no abajo: una cantidad por debajo del minimo se
        RECHAZA entera (`amount of ETH/USDT:USDT must be greater than
        minimum amount`), y ahi no se abre nada. Redondear hacia arriba
        es lo unico que hace que la orden sea aceptable.

        Ojo al coste: subir al minimo puede elevar la posicion por encima
        de lo que se pedia. Cuando el minimo de coste (5 USDT) manda mas
        que la cantidad, el minimo a respetar es el que de verdad
        sostiene el exchange, y se devuelve ese. Quien llama tiene que
        volver a comprobar el riesgo con la cantidad devuelta: subir la
        cantidad para que la orden pase y no mirar el riesgo que eso
        genera seria cambiar el riesgo en silencio.
        """
        swap = self._to_swap_symbol(symbol)
        try:
            mercado = (self.exchange.markets.get(swap)
                       or self.exchange.market(swap))
        except Exception:
            mercado = None
        if not mercado:
            return cantidad
        lim = mercado.get("limits") or {}
        min_amount = (lim.get("amount") or {}).get("min")
        min_cost = (lim.get("cost") or {}).get("min")
        cantidad = float(cantidad)
        if min_amount:
            cantidad = max(cantidad, float(min_amount))
        if min_cost and precio:
            min_por_coste = float(min_cost) / float(precio)
            cantidad = max(cantidad, min_por_coste)
        prec = (mercado.get("precision") or {}).get("amount")
        if prec is not None:
            try:
                cantidad = float(self.exchange.amount_to_precision(
                    swap, cantidad))
            except Exception:
                pass
        return cantidad

    def create_order(self, symbol: str, side: str, amount: float,
                     price: Optional[float] = None,
                     order_type: str = "market",
                     params: Optional[Dict] = None) -> Dict[str, Any]:
        """Place a live order. Returns the ccxt order dict."""
        self._require_auth()
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        swap = self._to_swap_symbol(symbol)
        amount = float(self.exchange.amount_to_precision(swap, amount))
        if price is not None:
            price = float(self.exchange.price_to_precision(swap, price))
        order = self.exchange.create_order(swap, order_type, side,
                                           amount, price, params or {})
        logger.info("live order %s %s %s @ %s -> id=%s",
                    side, amount, swap, price, order.get("id"))
        return order

    def cancel_order(self, order_id: str, symbol: str) -> Any:
        self._require_auth()
        return self.exchange.cancel_order(order_id, self._to_swap_symbol(symbol))

    def fetch_position(self, symbol: str) -> Dict[str, Any]:
        self._require_auth()
        positions = self.exchange.fetch_positions([self._to_swap_symbol(symbol)])
        return positions[0] if positions else {}

    def get_available_symbols(self) -> List[str]:
        """
        Get list of available trading symbols

        Returns:
            List of trading pairs
        """
        try:
            markets = self.data_client.load_markets()
            symbols = list(markets.keys())
            return symbols

        except Exception as e:
            logger.error(f"Failed to get available symbols: {e}")
            raise

    def ohlcv_to_dataframe(
        self,
        ohlcv: List[List],
        timeframe: str = '1h'
    ) -> pd.DataFrame:
        """
        Convert OHLCV list to DataFrame

        Args:
            ohlcv: OHLCV data
            timeframe: Timeframe label

        Returns:
            DataFrame with OHLCV data
        """
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['timeframe'] = timeframe

        return df

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get trading pair information

        Args:
            symbol: Trading pair

        Returns:
            Symbol info dictionary
        """
        try:
            markets = self.data_client.load_markets()
            return markets.get(symbol)

        except Exception as e:
            logger.error(f"Failed to get symbol info: {e}")
            return None

    def check_rate_limit(self):
        """Check and enforce rate limits"""
        return self.exchange.checkRateLimit()

    def close(self):
        """Close exchange connection"""
        self.exchange.close()
        logger.info("Exchange connection closed")


def get_available_exchanges() -> List[str]:
    """
    Get list of available exchanges

    Returns:
        List of exchange names
    """
    exchanges = getattr(ccxt, "exchanges", []) if ccxt else []
    return exchanges


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example usage
    exchange = ExchangeAPI(
        exchange_id='bybit',
        sandbox=False
    )

    # Fetch OHLCV data
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=100)
    print(f"Fetched {len(ohlcv)} candles")

    # Convert to DataFrame
    df = exchange.ohlcv_to_dataframe(ohlcv)
    print(df.head())

    # Get ticker
    ticker = exchange.fetch_ticker('BTC/USDT')
    print(f"Current price: {ticker['last']}")

    exchange.close()
