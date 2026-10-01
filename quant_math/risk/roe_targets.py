"""
TP/SL en ROE — fuente UNICA de verdad para objetivos y alcanzabilidad.

Por que existe este modulo
---------------------------
Antes de este modulo, `take_profit_pct` era una *fraccion de precio* y el ROE
salia "por casualidad" como `precio x apalancamiento`. Eso hacia imposible
razonar sobre el riesgo y producia el fallo medido en la auditoria (2026-09-29):
con el suelo duro `take_profit_pct = max(0.02, ...)` en modo burst, el SL nunca
podia bajar lo suficiente y la liquidacion llegaba antes.

Aqui el objetivo se declara en ROE (fraccion del MARGEN) y la distancia en
precio se deriva del apalancamiento en un solo sitio:

    distancia_precio = roe_objetivo / L

Decision de Leonardo (2026-09-29), targets fijos por modo:
    classic -> TP 50% ROE / SL 25% ROE   (ratio 2:1)
    burst   -> TP 20% ROE / SL 10% ROE   (ratio 2:1)

Liquidacion (margen aislado, perp lineal)
------------------------------------------
Con nocional N, margen M = N/L y tasa de mantenimiento `mmr` (fraccion del
nocional), la posicion se liquida cuando el margen libre cae por debajo del
requerimiento de mantenimiento:

    M - N*x <= mmr*N   =>   x >= 1/L - mmr

Es decir, la distancia de precio hasta la liquidacion es `1/L - mmr`.
VERIFICADO contra el rango publicado por la auditoria: con L=20 y mmr en
{0.35%, 0.50%, 0.75%} sale {4.65%, 4.50%, 4.25%} y el SL de entonces (10% de
precio) queda 2.15x-2.35x mas lejos — exactamente el "2,15-2,35x" del informe.

MMR REAL DE BYBIT (medido, no supuesto)
-----------------------------------------
El 2026-09-30 se consulto el endpoint PUBLICO de Bybit
`/v5/market/risk-limit?category=linear` (no hace falta API key) y se
consiguio la tabla REAL de mantenimiento, que es ESCALONADA por nocional y
no un numero unico. Primeros tramos, identicos para BTCUSDT y ETHUSDT:

    nocional <=   300.000 USD  ->  MMR 0,0033   (apalancamiento max 150x)
    nocional <= 2.000.000 USD  ->  MMR 0,0050   (100x)
    nocional <= 2.600.000 USD  ->  MMR 0,0056   (90x)
    ... 35 tramos en total

El supuesto anterior era 0,0050, que es el SEGUNDO tramo. Este sistema
opera con 15-200 USD de nocional, muy por debajo del primer umbral, asi
que la tabla le asigna 0,0033.

CORRECCION 2026-10-01, MEDIDA contra la cuenta REAL (no contra la tabla).
La tabla de arriba NO basta, y el comentario queetitleaba aquí.decía
justo lo contrario de lo cierto. Con dos capturas de una posicion real
de Leonardo, mismo tramo de nocional (15-200 USD):

    BTCUSDT   nocional 83,3849   mantenimiento 0,3207   ->  MMR 0,003846
    ENAUSDT   nocional 25,8883   mantenimiento 0,2728   ->  MMR 0,010538

Dos conclusiones, y las dos importan:

1) El valor por defecto era OPTIMISTA, no estricto. 0,0033 es MENOR que
   el 0,003846 real de BTC, luego la distancia a liquidacion que
   calculaba era DEMASIADO AMPLIA en 0,0546 puntos de precio (medido):
   1,6700% en vez de 1,6154% a 50x. El texto anterior afirmaba que
   ningun SL quedaba mas lejos de la liquidacion de lo que permitia el
   dato real. Falso: quedaba mas lejos de lo permitido.

2) EL MMR ES POR ACTIVO, NO SOLO POR NOCIONAL. BTC da 0,003846 y ENA
   0,010538 con nocionales EN EL MISMO TRAMO: ENA es 2,7 veces mayor.
   La tabla por nocional no captura esa dimension, y el valor por defecto
   se cambia a la MEDIDA de BTC (la mas restrictiva de las dos) en vez
   de al supuesto de la tabla.

Consecuencia honesta: para activos de MMR alto como ENA, un SL calculado
con el valor por defecto queda mas cerca de la liquidacion de lo que
deberia. Es un fallo del que hay que ser consciente, no un detalle: el
clamp del SL se apoya en esta cifra para decidir cuanto se puede acercar
el stop a la liquidacion.

Ojo al crecer: si el nocional sube de 300.000 USD el MMR sube y la
distancia a liquidacion se ACORTA, asi que el clamp se aprieta solo. Para
tamanos grandes hay que pasar el tramo que toque por configuracion
(`maintenance_margin_rate`), o llamar a `mmr_for_notional()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constantes de politica (las decisiones de Leonardo, en un solo sitio)
# ---------------------------------------------------------------------------

#: mode -> (take_profit_roe, stop_loss_roe). Ambos en fraccion de MARGEN.
MODE_ROE_TARGETS: Dict[str, Tuple[float, float]] = {
    "classic": (0.50, 0.25),   # TP 50% ROE / SL 25% ROE  (2:1)
    "burst": (0.20, 0.10),     # TP 20% ROE / SL 10% ROE  (2:1)
}

VALID_MODES: Tuple[str, ...] = tuple(MODE_ROE_TARGETS)

#: MMR LEIDO de Bybit el 2026-09-30 (endpoint publico /v5/market/risk-limit),
#: primer tramo, que es el que corresponde a un nocional de 15-200 USD.
#: Antes era 0.005, un SUPUESTO tomado del punto medio de un barrido propio.
DEFAULT_MAINTENANCE_MARGIN_RATE: float = 0.003846

#: Tabla REAL de maintenance margin de Bybit (2026-09-30), como
#: (nocional_maximo_usd, mmr, apalancamiento_maximo). Fuente: endpoint publico
#: `/v5/market/risk-limit?category=linear`. Identica para BTCUSDT y ETHUSDT.
#: El MMR SUBE con el tamano, o sea que la distancia a liquidacion se ACORTA
#: al crecer la posicion: por eso el clamp se aprieta solo y no hace falta
#: vigilarlo a mano. 35 tramos en la respuesta real; estos son los primeros.
BYBIT_MMR_TIERS: Tuple[Tuple[float, float, int], ...] = (
    (300_000.0, 0.0033, 150),
    (2_000_000.0, 0.0050, 100),
    (2_600_000.0, 0.0056, 90),
    (3_200_000.0, 0.0063, 80),
    (3_800_000.0, 0.0067, 75),
)

#: El SL en precio debe estar a lo sumo en esta FRACCION de la distancia a la
#: liquidacion. 0.5 = el SL dispara como muy tarde a mitad de camino hacia la
#: liquidacion, dejando espacio para slippage, funding y latencia.
DEFAULT_SL_LIQUIDATION_SAFETY_FRAC: float = 0.50

#: Movimiento de precio maximo admisible para un TP. Un TP que exige mas
#: recorrido del que el activo da en el timeframe de trabajo no se "persigue":
#: se toca el SL siempre. Es el aviso (y el veto al arranque) para
#: apalancamientos demasiado bajos — tipicamente L=1.
MAX_TP_PRICE_DISTANCE: Dict[str, float] = {
    "crypto": 0.10,   # 10% de precio
    "forex": 0.05,    # 5% de precio (FX se mueve menos)
}
DEFAULT_MAX_TP_PRICE_DISTANCE: float = 0.10

#: Tope de riesgo por operacion (fraccion de la cuenta). Se traduce a USD en
#: OrchestratorConfig y se materializa con PositionSizer.calculate().
DEFAULT_MAX_RISK_PER_TRADE_PCT: float = 0.02


class LeverageRiskError(ValueError):
    """Configuracion de apalancamiento/TP-SL que NO se puede operar.

    Se lanza en `validate_roe_plan()`, es decir al arrancar el wizard y en
    `OrchestratorConfig.__post_init__` — no en la ejecucion. Es preferible
    negarse a arrancar a arrancar con un SL inalcanzable.
    """


# ---------------------------------------------------------------------------
# Conversion ROE <-> precio  (aqui vive, y en ningun otro sitio)
# ---------------------------------------------------------------------------

def roe_targets_for_mode(mode: str) -> Tuple[float, float]:
    """(tp_roe, sl_roe) del modo. Lanza si el modo no existe."""
    m = (mode or "").strip().lower()
    if m not in MODE_ROE_TARGETS:
        raise LeverageRiskError(
            f"modo desconocido {mode!r}; validos: {', '.join(VALID_MODES)}")
    return MODE_ROE_TARGETS[m]


def normalize_leverage(leverage) -> int:
    """Apalancamiento efectivo, >= 1. Acepta float/int/str."""
    try:
        lev = int(float(leverage))
    except (TypeError, ValueError):
        raise LeverageRiskError(f"apalancamiento no numerico: {leverage!r}")
    return max(1, lev)


def roe_to_price_distance(roe: float, leverage) -> float:
    """Distancia en PRECIO que corresponde a un objetivo de ROE.

        distancia_precio = roe / L

    classic L=10 -> TP 50% ROE = 0.50/10 = 5% de precio.
    """
    lev = normalize_leverage(leverage)
    return abs(float(roe)) / lev


def price_distance_to_roe(distance: float, leverage) -> float:
    """Inversa: que ROE representa una distancia de precio dada."""
    return abs(float(distance)) * normalize_leverage(leverage)


def liquidation_price_distance(
    leverage,
    maintenance_margin_rate: float = DEFAULT_MAINTENANCE_MARGIN_RATE,
) -> float:
    """Distancia de precio (movimiento adverso) hasta la liquidacion.

    Margen aislado, perp lineal:  1/L - mmr.
    Lanza si el margen inicial ya no cubre el mantenimiento (L demasiado alto
    para el mmr dado): con mmr=0.5% no se puede abrir aislado a 200x porque el
    mantenimiento (0.5% del nocional) ya iguala el margen inicial (0.5%).
    """
    lev = normalize_leverage(leverage)
    mmr = float(maintenance_margin_rate)
    if not 0.0 < mmr < 1.0:
        raise LeverageRiskError(
            f"maintenance_margin_rate debe estar en (0, 1), recibido {mmr}")
    dist = 1.0 / lev - mmr
    if dist <= 0:
        raise LeverageRiskError(
            f"apalancamiento {lev}x incompatible con maintenance_margin_rate "
            f"{mmr:.4%}: el margen de mantenimiento ya supera al inicial "
            f"(1/{lev} = {1.0/lev:.4%}); la posicion se liquidaria en la entrada. "
            f"Baja el apalancamiento o sube el MMR real del exchange.")
    return dist


def mmr_for_notional(notional_usd: float) -> float:
    """MMR real de Bybit que corresponde a un nocional dado.

    El MMR es escalonado: con 15-200 USD (el tamano de este sistema) sale el
    primer tramo, 0,0033. Por encima de 300.000 USD sube y la distancia a
    liquidacion se ACORTA, asi que el clamp se aprieta solo. Se resuelve por
    config para no dejar un supuesto fijo que envejezca en silencio.
    """
    for ceiling, mmr, _max_lev in BYBIT_MMR_TIERS:
        if notional_usd <= ceiling:
            return mmr
    # Por encima del ultimo tramo conocido: se usa el MMR mas alto medido,
    # que es la direccion conservadora (mas MMR = mas cerca la liquidacion =
    # clamp mas estricto).
    return BYBIT_MMR_TIERS[-1][1]


def max_sl_price_distance(
    leverage,
    maintenance_margin_rate: float = DEFAULT_MAINTENANCE_MARGIN_RATE,
    safety_frac: float = DEFAULT_SL_LIQUIDATION_SAFETY_FRAC,
) -> float:
    """Techo del SL en precio: safety_frac x distancia a liquidacion."""
    frac = float(safety_frac)
    if not 0.0 < frac < 1.0:
        raise LeverageRiskError(
            f"sl_liquidation_safety_frac debe estar en (0, 1), recibido {frac}")
    return frac * liquidation_price_distance(leverage, maintenance_margin_rate)


def sl_is_reachable(
    sl_roe: float,
    leverage,
    maintenance_margin_rate: float = DEFAULT_MAINTENANCE_MARGIN_RATE,
    safety_frac: float = DEFAULT_SL_LIQUIDATION_SAFETY_FRAC,
) -> bool:
    """El SL en ROE cae ANTES que la liquidacion, con margen de seguridad."""
    d = roe_to_price_distance(sl_roe, leverage)
    return d <= max_sl_price_distance(leverage, maintenance_margin_rate, safety_frac)


# ---------------------------------------------------------------------------
# El plan
# ---------------------------------------------------------------------------

@dataclass
class RoePlan:
    """TP/SL de una configuracion, ya traducidos a precio y validados."""

    mode: str
    leverage: int
    tp_roe: float
    sl_roe: float
    tp_price_distance: float
    sl_price_distance: float
    sl_roe_requested: float
    liquidation_price_distance: float
    maintenance_margin_rate: float
    sl_liquidation_safety_frac: float
    max_tp_price_distance: float
    sl_clamped: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def realized_sl_roe(self) -> float:
        """ROE que realmente representa el SL tras el clamp."""
        return price_distance_to_roe(self.sl_price_distance, self.leverage)

    @property
    def realized_ratio(self) -> float:
        """TP_roe / SL_roe efectivo. 2.0 salvo que el clamp haya mordido."""
        return (self.tp_roe / self.realized_sl_roe
                if self.realized_sl_roe > 0 else float("inf"))

    @property
    def sl_liquidation_headroom(self) -> float:
        """Veces que el SL cabe en la distancia a liquidacion (>1 = sobra)."""
        liq = self.liquidation_price_distance
        return (liq / self.sl_price_distance) if self.sl_price_distance > 0 else float("inf")

    def to_dict(self) -> Dict[str, object]:
        d = dict(self.__dict__)
        d["ok"] = self.ok
        d["realized_sl_roe"] = self.realized_sl_roe
        d["realized_ratio"] = self.realized_ratio
        d["sl_liquidation_headroom"] = self.sl_liquidation_headroom
        return d

    def describe(self) -> str:
        return (
            f"modo={self.mode} L={self.leverage}x | "
            f"TP {self.tp_roe:+.0%} ROE = {self.tp_price_distance:.3%} precio | "
            f"SL {self.sl_roe:+.0%} ROE = {self.sl_price_distance:.3%} precio "
            f"{'[CLAMP]' if self.sl_clamped else ''} | "
            f"liquidacion a {self.liquidation_price_distance:.3%} precio "
            f"(mmr {self.maintenance_margin_rate:.3%}) | "
            f"holgura SL/liq {self.sl_liquidation_headroom:.2f}x"
        )


def build_roe_plan(
    mode: str,
    leverage,
    take_profit_roe: Optional[float] = None,
    stop_loss_roe: Optional[float] = None,
    maintenance_margin_rate: float = DEFAULT_MAINTENANCE_MARGIN_RATE,
    sl_liquidation_safety_frac: float = DEFAULT_SL_LIQUIDATION_SAFETY_FRAC,
    market: str = "crypto",
    max_tp_price_distance: Optional[float] = None,
) -> RoePlan:
    """Construye el plan ROE de un modo+apalancamiento.

    No lanza por problemas de *alcanzabilidad*: esos van en `plan.errors` /
    `plan.warnings`, para que el wizard pueda mostrarlos. Si lanza
    (LeverageRiskError), es que ni la matematica tiene sentido (mmr >= 1/L).
    """
    m = (mode or "").strip().lower()
    default_tp, default_sl = roe_targets_for_mode(m)
    lev = normalize_leverage(leverage)
    tp_roe = default_tp if take_profit_roe is None else abs(float(take_profit_roe))
    sl_roe_req = default_sl if stop_loss_roe is None else abs(float(stop_loss_roe))
    if tp_roe <= 0 or sl_roe_req <= 0:
        raise LeverageRiskError(
            f"objetivos ROE deben ser > 0 (tp={tp_roe}, sl={sl_roe_req})")

    liq = liquidation_price_distance(lev, maintenance_margin_rate)
    ceiling = max_sl_price_distance(lev, maintenance_margin_rate,
                                    sl_liquidation_safety_frac)
    max_dist = (MAX_TP_PRICE_DISTANCE.get((market or "crypto").lower(),
                                          DEFAULT_MAX_TP_PRICE_DISTANCE)
                if max_tp_price_distance is None
                else float(max_tp_price_distance))

    tp_dist = roe_to_price_distance(tp_roe, lev)
    sl_dist = roe_to_price_distance(sl_roe_req, lev)
    sl_clamped = False
    warnings: List[str] = []
    errors: List[str] = []

    # --- CLAMP: el SL en ROE nunca puede acercarse a la liquidacion -------
    if sl_dist > ceiling:
        sl_clamped = True
        warnings.append(
            f"SL clamped: {sl_roe_req:.2%} ROE = {sl_dist:.3%} de precio supera "
            f"el techo {sl_liquidation_safety_frac:.0%} x {liq:.3%} = "
            f"{ceiling:.3%}; se deja en {ceiling:.3%} de precio "
            f"({ceiling * lev:.2%} ROE). Motivo: apalancamiento alto para un SL "
            f"de {sl_roe_req:.0%} ROE — el SL habria llegado demasiado cerca de "
            f"la liquidacion. El ratio 2:1 es objetivo, la seguridad es ley.")
        sl_dist = ceiling

    # --- Aviso por apalancamiento demasiado bajo (caso L=1) --------------
    if tp_dist > max_dist:
        errors.append(
            f"TP {tp_roe:.0%} ROE con L={lev}x exige mover {tp_dist:.2%} del "
            f"precio, mas alla del maximo admisible ({max_dist:.2%} para "
            f"{market}). Con tan poco apalancamiento el TP no se alcanza en el "
            f"timeframe y la operacion se pierde entera en el SL. Sube el "
            f"apalancamiento (o baja el objetivo de ROE).")
    if sl_dist >= tp_dist:
        errors.append(
            f"SL ({sl_dist:.3%} de precio) >= TP ({tp_dist:.3%} de precio): "
            f"no hay configuracion coherente de TP/SL.")
    if not sl_is_reachable(sl_roe_req, lev, maintenance_margin_rate,
                            sl_liquidation_safety_frac) and not sl_clamped:
        errors.append(
            f"SL {sl_roe_req:.2%} ROE inalcanzable antes de la liquidacion "
            f"(liq a {liq:.3%}, techo {ceiling:.3%})")

    return RoePlan(
        mode=m,
        leverage=lev,
        tp_roe=tp_roe,
        sl_roe=sl_roe_req,
        tp_price_distance=tp_dist,
        sl_price_distance=sl_dist,
        sl_roe_requested=sl_roe_req,
        liquidation_price_distance=liq,
        maintenance_margin_rate=float(maintenance_margin_rate),
        sl_liquidation_safety_frac=float(sl_liquidation_safety_frac),
        max_tp_price_distance=max_dist,
        sl_clamped=sl_clamped,
        errors=errors,
        warnings=warnings,
    )


def validate_roe_plan(plan: RoePlan) -> RoePlan:
    """Lanza LeverageRiskError si el plan no se puede operar."""
    if not plan.ok:
        raise LeverageRiskError(
            f"configuracion de riesgo no operable ({plan.mode} "
            f"L={plan.leverage}x): " + " | ".join(plan.errors))
    return plan


def build_and_validate(*args, **kwargs) -> RoePlan:
    return validate_roe_plan(build_roe_plan(*args, **kwargs))


def tp_sl_prices(entry_price: float, side: str, plan: RoePlan) -> Tuple[float, float]:
    """(precio_tp, precio_sl) a partir del plan. Unico lugar que multiplica
    precio por (1 +- distancia)."""
    p = float(entry_price)
    d = 1.0 if str(side).lower() == "buy" else -1.0
    return (p * (1.0 + d * plan.tp_price_distance),
            p * (1.0 - d * plan.sl_price_distance))
