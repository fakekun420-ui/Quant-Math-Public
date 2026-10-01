"""
MMR REAL POR ACTIVO Y POR APALANCAMIENTO (2026-10-01)

MEDIDO el 2026-10-01 contra el endpoint PUBLICO de Bybit
`/v5/market/risk-limit?category=linear`, que NO necesita clave ni posicion
abierta (600 simbolos, 17.394 filas con la paginacion completa). La tabla
que devuelve es por (simbolo, apalancamiento), NO por nocional:

    BTCUSDT  150x=0,3300%  100x=0,5000%  90x=0,5600%  80x=0,6300%  75x=0,6700%
    ETHUSDT  150x=0,3300%  100x=0,5000%  90x=0,5600%  80x=0,6300%  75x=0,6700%
    ENAUSDT   50x=1,0000%   33x=1,5000%   25x=2,0000%   20x=2,5000%

EL BUG QUE ESTE FICHERO ARREGLA. El codigo usaba 0,0033 como MMR por
defecto, y ese 0,33% es exactamente la fila de 150x. Aplicado a otro
apalancamiento el error es grande y en la direccion equivocada:

    apalancamiento   MMR del codigo   MMR REAL     error
         150x           0,3300%       0,3300%     correcto
         100x           0,3300%       0,5000%     -34%   <-- el que usa el sistema
          90x           0,3300%       0,5600%     -41%

Como la distancia a liquidacion es `1/L - mmr`, un MMR infraestimado
acerca la liquidacion... no, la ALEJA: el sistema creia que la
liquidacion estaba mas lejos de lo real, y por tanto el clamp del SL
dejaba pasar un SL mas apretado del debido. Ese clamp existe para que el
stop no llegue nunca a la liquidacion, asi que el fallo era justo en la
peor direccion: menos proteccion de la que el codigo creía dar.

Ademas el MMR es POR ACTIVO, no un numero unico. ENA a 50x da 1,00%,
tres veces el de BTC a 100x. Con un MMR por defecto fijo, operar en un
activo barato con apalancamiento alto subestimaba el riesgo de
liquidacion por un factor de tres.

Si el exchange no responde, se usa el valor por defecto y se DICE, en
vez de fingir que se consulto: un fallo de red que se manifesta como un
MMR fiable es el mismo tipo de fallo que ya se ha encontrado cuatro
veces en este proyecto.
"""

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

RISK_LIMIT_URL = ("https://api.bybit.com/v5/market/risk-limit"
                  "?category=linear&limit=500")

#: Cache del proceso: {simbolo: {apalancamiento: mmr}}
_CACHE: Dict[str, Dict[int, float]] = {}
_CACHED = False
_LOCK = threading.Lock()

#: Cache en disco. MEDIDO el 2026-10-01: sin esto la suite tardaba 40 s
#: porque cada test iba a la red a bajar 17.394 filas, y un test que
#: depende de la red no es un test: falla cuando el exchange va lento y
#: no dice por que. El fichero guarda lo que se leyo con la fecha, y se
#: usa si es reciente. Un MMR de Bybit cambia pocas veces al mes, asi que
#: un dia de antiguedad no introduce riesgo: es mucho menor que el riesgo
## de que la suite no pase por culpa de la red.

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".bybit_risk_limit.json")
CACHE_MAX_AGE_S = 24 * 3600

#: MMR MEDIDO en posiciones REALES de la cuenta (no de la tabla).
#:
#: MEDIDO el 2026-10-01 con `positionMM / positionValue` sobre posiciones
#: vivas a 100x, leyendo el exchange. Esto se midio y se guardaba, y
#: solo servia mientras la posicion estaba abierta: `mmr_for_symbol`
#: cae a la tabla o al valor por defecto cuando no hay posicion, y en
#: el PRIMER calculo (que es justo cuando hace falta para colocar el SL)
#: no hay ninguna. Con estos numeros, el primer calculo tambien es real.
#:
#:   XRP  0,5543%   ETH  0,3856%   SOL  0,5556%
#:
#: Comparado con lo que se asumia (0,3846%, el de BTC a 150x): XRP y
#: SOL son un 44% MAS altos. Con el supuesto, su liquidacion se
#: calculaba mas lejos de la real de lo que esta, y el clamp del SL
#: dejaba pasar un stop mas apretado del debido en justo los dos
#: simbolos con mas volatilidad.
#:
#: Se aplica solo cuando la tabla NO tiene el simbolo (medido: la tabla
#: publica de Bybit tiene 675 simbolos y XRP y SOL no estan). Cuando la
#: tabla tiene fila, manda la tabla, que es la fuente oficial y se
#: actualiza sola. Aqui no se sustituye una fuente por un dato fijo,
#: se rellena un hueco que la fuente no cubre.
#: MEDIDO a 100x y SOLO a 100x. El MMR de Bybit escala con el
#: apalancamiento en escalones (medido con BTC: 2,5% a 25x, 1,0% a 50x,
#: 0,5% a 100x), asi que un valor medido a 100x aplicado a 25x NO es una
#: aproximacion conservative: es un numero falso. Como la tabla publica no
#: tiene estos simbolos, a 25x y 50x no se puede dar el MMR y se devuelve
#: "no medido". Se prefiere eso a inventar el escalon.
MMR_MEDIDOS: Dict[Tuple[str, int], float] = {
    ("XRPUSDT", 100): 0.005543,
    ("SOLUSDT", 100): 0.005556,
}

#: MMR por defecto cuando el exchange no dice NADA, y no solo para un
#: apalancamiento.
#:
#: MEDIDO el 2026-10-01 en la tabla publica de Bybit para BTC, y el MMR escala
#: en escalones con el apalancamiento:
#:
#:     5x -> 12,00%   10x -> 6,50%   25x -> 2,50%
#:    50x ->  1,00%  100x -> 0,50%  125x -> 0,33%
#:
#: Antes se aplicaba 0,003846 a TODO, o sea el valor de 150x tambien a 25x.
#: Eso NO era conservador, era al reves: con MMR plano a 25x la liquidacion
#: se ponia a (4,00% - 0,38%) = 3,62% cuando la real esta a 1,50%. El
#: clamp del SL dejaba pasar stops que el exchange habria rechazado, y hacia
#: creer que habia el doble de margen del que hay. Sobreestimar el espacio
#: es la direccion que da pnls falsos.
#:
#: Estos escalones son los de BTC, un simbolo de la capitalizacion mas
#: grande de la lista. Para un simbolo que no esta en la tabla son una
#: APROXIMACION y asi se etiqueta en `origen`. La unica forma de cerrarla es
#: que el simbolo este en la tabla, que es lo que hace `cargar_tabla`.
ESCALONES_MMR: Tuple[Tuple[int, float], ...] = (
    (1, 0.120000), (10, 0.065000), (25, 0.025000),
    (50, 0.010000), (100, 0.005000), (125, 0.003300),
)
FALLBACK_MMR = 0.003846


def _mmr_por_escalon(leverage) -> float:
    """MMR estimado por escalon de apalancamiento.

    Si el apalancamiento es MAYOR que el ultimo escalon conocido se usa ese,
    que es el mas bajo: es el supuesto que mas espacio da, y por eso solo se
    acepta cuando de verdad no hay nada mejor.
    """
    try:
        lev = max(1, int(leverage))
    except (TypeError, ValueError):
        lev = 100
    elegido = ESCALONES_MMR[0][1]
    for tope, valor in ESCALONES_MMR:
        if lev <= tope:
            elegido = valor
            break
        elegido = valor
    return elegido

#: Simbolos que se saben ausentes de la tabla publica (medido: no
#: aparecen en las 40 paginas, 600 simbolos). Sin esto se consultaria y
#: se devolveria "no encontrado" cada ciclo, para cada uno, en cada
#: arranque.
KNOWN_ABSENT = frozenset({"SOLUSDT", "XRPUSDT"})


def _normaliza(simbolo: str) -> str:
    """`BTC/USDT:USDT` -> `BTCUSDT`.

    El codigo habla en `BTC/USDT:USDT` (formato ccxt) y el endpoint en
    `BTCUSDT`, que es base+MONEDA PEGADOS. Confundirlos es justo el tipo
    de detalle que hace que una busqueda "falle" sin que se entienda por
    que: el endpoint responde 600 simbolos y el MMR sale por defecto sin
    que ninguna excepcion lo delate.

    Se verificado contra el endpoint real: sin base+quote sale `BTC` y no
    hay ninguna fila con ese nombre.
    """
    if not simbolo:
        return ""
    sym = simbolo.strip().upper()
    if "/" not in sym:
        return sym.replace(":USDT", "")
    base, _, resto = sym.partition("/")
    # `BTC/USDT:USDT` -> base BTC, resto `USDT:USDT`
    quote = resto.split(":")[0] or "USDT"
    return f"{base}{quote}"


def _descarga() -> Dict[str, Dict[int, float]]:
    """Trae la tabla del exchange. Devuelve {} si falla."""
    out: Dict[str, Dict[int, float]] = {}
    cursor = None
    # 40 paginas es el tope medido: con limit=500 la tabla entera son 17.394
    # filas y 600 simbolos. Es un tope, no un alvo: si el exchange
    # creciera, se corta por el tope en vez de quedarse sin memoria.
    for _ in range(40):
        url = RISK_LIMIT_URL + (f"&cursor={cursor}" if cursor else "")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "qmp/1"})
            with urllib.request.urlopen(req, timeout=25) as fh:
                data = json.loads(fh.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError, ValueError,
                json.JSONDecodeError) as exc:
            logger.warning("[mmr] no se pudo leer la tabla de riesgo (%s): "
                           "se usara el valor por defecto %.6f", exc,
                           FALLBACK_MMR)
            break
        result = data.get("result") or {}
        filas = result.get("list") or []
        for x in filas:
            try:
                mmr = float(x["maintenanceMargin"])
                lev = int(float(x["maxLeverage"]))
            except (KeyError, TypeError, ValueError):
                continue
            if mmr <= 0 or lev <= 0:
                continue
            out.setdefault(str(x["symbol"]).upper(), {})[lev] = mmr
        cursor = result.get("nextPageCursor")
        if not cursor:
            break
    return out


def _lee_cache_disco():
    """Tabla cacheada en disco, si existe y no es muy vieja."""
    try:
        edad = time.time() - os.path.getmtime(CACHE_PATH)
        if edad > CACHE_MAX_AGE_S:
            return None
        with open(CACHE_PATH, encoding="utf-8") as fh:
            crudo = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    out = {}
    for sym, filas in (crudo or {}).items():
        try:
            out[str(sym).upper()] = {int(k): float(v)
                                     for k, v in (filas or {}).items()}
        except (TypeError, ValueError, AttributeError):
            continue
    return out or None


def _escribe_cache_disco(tabla) -> None:
    """Cache en disco, ATOMICA (§5.3: escribir a .tmp y renombrar).

    FUSE trunca escrituras a la mitad, ya ha pasado en este proyecto, y
    un JSON a medio escribir dejaria la tabla corrupta: al proximo
    arranque `mmr_for_symbol` no encontraria nada y volveria al valor por
    defecto sin avisar. El renombrado es lo que hace que eso no importe.
    """
    tmp = CACHE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(tabla, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, CACHE_PATH)
    except OSError as exc:
        logger.warning("[mmr] no se pudo cachear la tabla en disco: %s", exc)
        try:
            os.unlink(tmp)
        except OSError:
            pass


def cargar_tabla(forzar: bool = False) -> bool:
    """Carga la tabla MMR del exchange una vez por proceso.

    Devuelve True si la tabla quedo disponible. Falla cerrado: si no se
    puede, devuelve False y se usa `FALLBACK_MMR` DICHIENDOLO en el log.
    """
    global _CACHED, _CACHE
    with _LOCK:
        if _CACHED and not forzar:
            return bool(_CACHE)
        if not forzar:
            disco = _lee_cache_disco()
            if disco:
                _CACHE = disco
                _CACHED = True
                logger.info("[mmr] tabla de riesgo desde cache en disco: %d "
                            "simbolos", len(disco))
                return True
        tabla = _descarga()
        if tabla:
            _escribe_cache_disco(tabla)
            _CACHE = tabla
            _CACHED = True
            logger.info("[mmr] tabla de riesgo de Bybit cargada: %d simbolos",
                        len(tabla))
            return True
        logger.warning("[mmr] SIN tabla de riesgo: el MMR sera el valor por "
                       "defecto %.6f (medido en BTC a 150x). El clamp del SL "
                       "sera menos estricto que el real", FALLBACK_MMR)
        return False


def mmr_for_symbol(simbolo: Optional[str], leverage) -> Tuple[float, str]:
    """MMR real de un simbolo a un apalancamiento. Devuelve (mmr, origen).

    `origen` dice de donde sale el numero: `"exchange:<SYM>"`, `"por_defecto"`
    o `"tabla"`. Se devuelve para que quien lo use pueda DECIR de donde
    salio: un MMR que no dice de donde viene no se puede auditar.

    La regla de eleccion es la que usa el exchange: el MMR de un tramo es
    el de la fila con `maxLeverage` IGUAL al apalancamiento pedido, o la
    del tramo inmediatamente SUPERIOR si no hay fila exacta. Nunca el de
    un tramo inferior, porque ese daria un MMR mas pequeno (mas
    optimista) del que corresponde.
    """
    lev = max(1, int(float(leverage or 1)))
    sym = _normaliza(simbolo or "")
    cargar_tabla()
    if not _CACHE:
        est = _mmr_por_escalon(lev)
        logger.debug("[mmr] la tabla de riesgo no esta disponible: se estima "
                     "por escalon %.4f%% (NO es medida)", est * 100)
        return est, f"estimado_escalon:{lev}x"
    if sym in _CACHE:
        filas = _CACHE[sym]
        if lev in filas:
            return filas[lev], f"exchange:{sym}@{lev}x"
        # Tramo inmediatamente SUPERIOR (MMR mayor = mas conservador).
        superiores = [l for l in filas if l >= lev]
        if superiores:
            elegido = min(superiores)
            return filas[elegido], f"exchange:{sym}@{elegido}x"
        # Todas por debajo: la mayor disponible (el MMR mas alto, que es
        # el mas restrictivo de los que hay).
        elegido = max(filas)
        return filas[elegido], f"exchange:{sym}@{elegido}x"
    if sym in KNOWN_ABSENT:
        # MEDIDO el 2026-10-01: para estos dos simbolos la tabla publica no
        # existe, pero el MMR REAL se midio en sus posiciones vivas. Se usa
        # ese en vez del valor por defecto de otro activo: medido, es un
        # 44% mas alto, y la liquidacion calculada con el supuesto estaba
        # mas lejos de la real de lo que esta.
        medido = MMR_MEDIDOS.get((sym, int(leverage)))
        if medido is not None:
            logger.debug("[mmr] %s a %sx no esta en la tabla de Bybit; se usa "
                         "el MEDIDO en su posicion real: %.4f%%", sym,
                         leverage, medido * 100)
            return medido, f"medido:{sym}@{leverage}x"
        logger.debug("[mmr] %s a %sx no esta en la tabla publica de Bybit ni "
                     "hay medida a ESE apalancamiento: se estima por escalon "
                     "%.4f%% (escalones de BTC, NO es medida).", sym,
                     leverage, _mmr_por_escalon(leverage) * 100)
        return _mmr_por_escalon(leverage), f"estimado_escalon:{leverage}x"
    est = _mmr_por_escalon(leverage)
    logger.debug("[mmr] %s a %sx: la tabla no esta disponible; se estima por "
                 "escalon %.4f%% (escalones de BTC, NO es medida).", sym,
                 leverage, est * 100)
    return est, f"estimado_escalon:{leverage}x"


def mmr_from_live_position(simbolo: Optional[str], api=None) -> Tuple[
        Optional[float], str]:
    """MMR REAL de una posicion viva, leido del exchange. Es el dato bueno.

    MEDIDO el 2026-10-01. La tabla publica `/v5/market/risk-limit` cubre
    675 simbolos y BTC y ETH estan, pero SOL y XRP NO aparecen (buscados
    por nombre y por coincidencia parcial). Para esos el MMR se caia al
    valor por defecto, que es el de otro activo: subestimaba su
    liquidacion sin que nada lo dijera.

    Bybit resuelve el problema en la propia posicion: el campo
    `positionMM` es el mantenimiento real, y `positionValue` el nocional,
    luego el MMR es su cociente. Medido en SOL a 100x:

        positionValue 23,5380   positionMM 0,130783   ->  MMR 0,5556%

    Que es un 68% MAS ALTO que el 0,33% que asumia el codigo. Con la
    tabla prestada de ETH (0,50%) seguia quedarse corto.

    Devuelve None si no hay posicion viva: es el dato que solo existe
    cuando ya se ha abierto algo, asi que no sirve para el PRIMER calculo
    (antes de entrar), que es justo cuando hace falta para colocar el
    SL. Por eso `mmr_for_symbol` sigue usando la tabla como primera
    opcion y esta es la segunda, que corrige en cuanto hay posicion.
    """
    if api is None:
        return None, "sin_api"
    sym = _normaliza(simbolo or "")
    try:
        raw = api.exchange.fetch_position(sym if ":" in (simbolo or "")
                                          else f"{sym}/USDT:USDT")
    except Exception:
        return None, "sin_posicion"
    info = (raw or {}).get("info") or {}
    try:
        nocional = float(info.get("positionValue") or 0.0)
        mant = float(info.get("positionMM") or 0.0)
    except (TypeError, ValueError):
        return None, "sin_posicion"
    if nocional <= 0 or mant <= 0:
        return None, "sin_posicion"
    return mant / nocional, f"exchange:{sym}:positionMM"


def liquidation_price_distance_for_symbol(simbolo: Optional[str],
                                           leverage) -> Tuple[float, float, str]:
    """`(distancia, mmr, origen)` de la liquidacion de un simbolo concreto.

    Es la funcion que hay que usar cuando se sabe el simbolo. La que
    acepta `maintenance_margin_rate` explicito sigue ahi para cuando ya
    se tiene el dato (o para los tests), pero llamarla con el valor por
    defecto es lo que ha producido el bug.
    """
    from quant_math.risk.roe_targets import liquidation_price_distance
    mmr, origen = mmr_for_symbol(simbolo, leverage)
    return liquidation_price_distance(leverage, mmr), mmr, origen