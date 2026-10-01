"""
Unified Risk Manager

Consolidated risk management implementation using Quant-Math core modules.
"""

import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from quant_math.core.types import StrategyResult
from quant_math.risk.position_sizing import PositionSizer
from quant_math.risk.stop_loss import StopLoss
from quant_math.risk.kelly import KellyCriterion
from quant_math.risk.var import ValueAtRisk, ExpectedShortfall
from quant_math.expectation import DrawdownAnalyzer, SharpeMetrics


class RiskManager:
    """
    Unified Risk Manager implementing the RiskManager protocol.

    Consolidates position sizing, drawdown monitoring, risk metrics,
    and stress testing using Quant-Math core modules.
    """

    # ------------------------------------------------------------------
    # Pisos de muestra para las estadisticas de la SERIE DE CIERRES
    # ------------------------------------------------------------------
    # Mismo numero que el Kelly y por la misma razon: por debajo de 20
    # observaciones una sola operacion mueve la estadistica mas de 5 pp
    # (1/N) y el numero deja de ser una medida. Toda serie que alimente
    # VaR/ES o Sharpe pasa por aqui ANTES de calcularse.
    MIN_CLOSURES_FOR_SAMPLE = 20

    # Compatibilidad: la politica de muestra empezo con el Kelly y el
    # nombre viejo sigue referenciado fuera de aqui. Un solo numero,
    # dos nombres: dos constantes con el mismo valor a mano son dos
    # constantes que acaban divergiendo.
    MIN_CLOSURES_FOR_KELLY = MIN_CLOSURES_FOR_SAMPLE

    # Piso aparte para el nivel 99%. Un cuantil al 99% se apoya en UNA
    # observacion de cada 100: con menos de 100 cierres no hay cola
    # empirica que medir y el numero sale entero del supuesto de
    # normalidad, no de los datos. Por eso VaR/ES-95 y VaR/ES-99 no se
    # activan juntos.
    MIN_CLOSURES_FOR_VAR99 = 100

    def __init__(
        self,
        max_position_size_pct: float = 0.2,
        max_daily_loss_pct: float = 0.05,
        max_overall_loss_pct: float = 0.15,
        kelly_fraction: float = 0.3,
        drawdown_limit: float = 0.2
    ):
        """
        Initialize the risk management engine.

        Args:
            max_position_size_pct: Maximum position size as % of capital (default: 20%)
            max_daily_loss_pct: Maximum daily loss as % of capital (default: 5%)
            max_overall_loss_pct: Maximum overall loss as % of capital (default: 15%)
            kelly_fraction: Fraction of Kelly criterion to use (default: 30%)
            drawdown_limit: Maximum acceptable drawdown (default: 20%)
        """
        self.max_position_size_pct = max_position_size_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_overall_loss_pct = max_overall_loss_pct
        self.kelly_fraction = kelly_fraction
        self.drawdown_limit = drawdown_limit

        # Initialize Quant-Math components
        self.position_sizer = PositionSizer()
        self.stop_loss = StopLoss()
        self.kelly = KellyCriterion()
        self.var_calculator = ValueAtRisk()
        self.es_calculator = ExpectedShortfall()
        self.drawdown_analyzer = DrawdownAnalyzer()
        self.sharpe_metrics = SharpeMetrics()

        # Risk monitoring state
        self.position_sizes: Dict[str, float] = {}
        self.daily_pnl: Dict[str, float] = {}
        self.overall_pnl: Dict[str, float] = {}
        self.risk_checks: Dict[str, List[Dict[str, Any]]] = {}
        self.risk_violations: Dict[str, List[str]] = {}

    def check_position_size(
        self,
        hypothesis_id: str,
        requested_size: float,
        account_value: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        n_closures: Optional[int] = None,
        pnl_series: Optional[List[float]] = None,
        **risk_params
    ) -> Dict[str, Any]:
        """
        Check if position size meets risk criteria.

        Args:
            hypothesis_id: Hypothesis ID
            requested_size: Requested position size (absolute value)
            account_value: Total account value
            win_rate: Win rate for Kelly calculation (optional)
            avg_win: Average win for Kelly calculation (optional)
            avg_loss: Average loss for Kelly calculation (optional)
            n_closures: Numero de cierres de los que salen esas medidas.
                Si viene y es menor que MIN_CLOSURES_FOR_KELLY, NO se
                calcula Kelly: una muestra chica lo mueve una sola
                operacion y el tamano resultante seria una invencion.
            pnl_series: PnL en USD de cada cierre DEDUPLICADO del ledger,
                en orden. Alimenta VaR/ES (cola) y Sharpe/Sortino
                (calidad). Si no viene, esos bloques se declaran
                `sin_datos` en vez de inventar un numero.
            **risk_params: Additional risk parameters

        Returns:
            Dictionary with risk check results. El registro incluye
            `kelly_status` + `kelly_note` (por que hay o no hay Kelly) y
            `kelly_advisory` (aviso si el pedido supera el Kelly medido),
            mas `var_status`/`var_note`/`var_*_frac` (VaR y Expected
            Shortfall de la cola por cierre) y
            `sharpe_status`/`sharpe_note`/`sharpe`/`sortino` (calidad de
            la serie). Ninguno de esos cuatro estados toca `approved` ni
            `reasons`: son ESTADO MEDIDO, no frenos (los frenos vivos son
            DailyGuard y los topes de margen/riesgo).
        """
        # Apply position limits
        max_position = account_value * self.max_position_size_pct

        # Kelly con la formula canonica del modulo y datos medidos, o con
        # un estado EXPLICITO de por que no lo hay. Antes esto devolia un
        # 0.0 silencioso con los defaults (wr=0.5, aw=1, al=1), y ese cero
        # desactivaba el aviso de Kelly sin que nadie supiera que no habia
        # medida que lo sustentara.
        kelly = self._kelly_assessment(
            account_value, win_rate, avg_win, avg_loss, n_closures
        )
        kelly_size = kelly["size"]  # float | None: nunca un 0 sin explicar

        # VaR/ES (cola del PnL) y Sharpe/Sortino (calidad de la serie),
        # calculados con los modulos canonicos `risk.var` y
        # `expectation.sharpe_metrics` sobre la MISMA serie de cierres que
        # alimenta el Kelly, y con el mismo piso de muestra. Los dos
        # devuelven ESTADO (`*_status`/`*_note`): si no hay datos o no hay
        # muestra suficiente lo dicen con el numero en la mano en vez de
        # entregar un VaR o un Sharpe de ruido.
        cola = self._tail_risk_assessment(pnl_series, account_value)
        calidad = self._quality_assessment(pnl_series, account_value)

        # Check constraints
        approved = True
        reasons = []
        actual_size = requested_size

        # Check maximum position size
        if requested_size > max_position:
            approved = False
            reasons.append(f"Position size {requested_size:.2f} exceeds max {max_position:.2f}")
            actual_size = min(requested_size, max_position)

        # Aviso de Kelly: supera el tamano recomendado, pero NO cambia la
        # aprobacion.
        #
        # Por que NO va en `reasons`: el orquestador lee `reasons` para
        # decidir entre RECORTAR el margen (si todo razon es "exceeds max")
        # y RECHAZAR la entrada (si hay cualquier otra razon). Con Kelly
        # medido su fraccion va SIEMPRE por debajo de max_position_pct
        # (0.03-0.17 medido frente a 0.20), asi que meter aqui el aviso
        # haria que cada tope de margen se convirtiera en un rechazo
        # cerrado: el dimensionamiento en vivo cambiaria sin medirse.
        # El aviso se expone aparte, en `kelly_advisory`.
        kelly_advisory = None
        if kelly_size is not None and kelly_size > 0 and requested_size > kelly_size:
            kelly_advisory = (f"Position size exceeds Kelly optimal "
                              f"(Kelly={kelly_size:.2f})")

        # Check overall loss limit
        current_loss = self.overall_pnl.get(hypothesis_id, 0.0)
        if current_loss < -account_value * self.max_overall_loss_pct:
            approved = False
            reasons.append(f"Overall loss {current_loss:.2f} exceeds limit")

        # Store position size
        self.position_sizes[hypothesis_id] = actual_size if approved else 0.0

        # Record risk check
        check_record = {
            "timestamp": datetime.now().isoformat(),
            "requested_size": requested_size,
            "approved_size": actual_size if approved else 0.0,
            "approved": approved,
            "reasons": reasons,
            "max_position": max_position,
            "kelly_size": kelly_size,
            "kelly_status": kelly["status"],
            "kelly_note": kelly["note"],
            "kelly_fraction_applied": kelly["fraction"],
            "kelly_advisory": kelly_advisory,
            # cola (VaR/ES) y calidad (Sharpe/Sortino): estado medido,
            # nunca un veto — ver `_tail_risk_assessment` y
            # `_quality_assessment`.
            **cola,
            **calidad,
            "account_value": account_value
        }

        if hypothesis_id not in self.risk_checks:
            self.risk_checks[hypothesis_id] = []
        self.risk_checks[hypothesis_id].append(check_record)

        if not approved:
            if hypothesis_id not in self.risk_violations:
                self.risk_violations[hypothesis_id] = []
            self.risk_violations[hypothesis_id].extend(reasons)

        return check_record

    # (el piso comun MIN_CLOSURES_FOR_SAMPLE, definido arriba: con N=20
    # una sola operacion mueve el win_rate 5 puntos porcentuales)

    def _kelly_assessment(
        self,
        account_value: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        n_closures: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Kelly con la formula CANONICA del modulo (`KellyCriterion.calculate`).

        Antes estaba reimplementada a mano en este mismo fichero
        (`f = wr - (1 - wr) / win_loss_ratio`, con defaults wr=0.5,
        aw=1.0, al=1.0 que daban exactamente 0.0), y ese 0.0 silencioso
        desactivaba el aviso de Kelly pareciendo una medida. Por eso el
        resultado ahora es un estado explicito:

          - "sin_datos"       -> size=None: faltan win_rate/avg_win/avg_loss
          - "insuficiente"    -> size=None: hay muestra pero < piso
          - "datos_invalidos" -> size=None: valores fuera de dominio
          - "no_viable"       -> size=0.0: el Kelly MEDIDO no compensa
          - "ok"              -> size=float: Kelly medido

        Un 0.0 numerico solo puede salir de "no_viable", que lo explica.
        Los cuatro estados no-"ok" declaran ademas en que metodo se cae
        el dimensionado (el tope declarado max_position_size_pct).

        Si `n_closures` no se informa, las estadisticas se dan por buenas:
        quien las pasa se responsabiliza de su muestra. El orquestador
        pasa siempre la n medido del ledger.
        """
        faltantes = [nombre for nombre, valor in
                     (("win_rate", win_rate), ("avg_win", avg_win),
                      ("avg_loss", avg_loss)) if valor is None]
        if faltantes:
            return {
                "status": "sin_datos",
                "size": None,
                "fraction": None,
                "note": (
                    f"sin {', '.join(faltantes)} medidos: NO se dimensiona "
                    "con Kelly. Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%} "
                    f"(= {account_value * self.max_position_size_pct:.2f} "
                    f"USD de margen sobre cuenta {account_value:.2f})"
                ),
            }

        if n_closures is not None and n_closures < self.MIN_CLOSURES_FOR_KELLY:
            return {
                "status": "insuficiente",
                "size": None,
                "fraction": None,
                "note": (
                    f"solo {n_closures} cierres medidos (piso "
                    f"{self.MIN_CLOSURES_FOR_KELLY}): una sola operacion "
                    "mueve el win_rate mas de "
                    f"{100.0 / max(1, int(n_closures)):.1f} pp. NO se "
                    "dimensiona con Kelly. Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%} "
                    f"(= {account_value * self.max_position_size_pct:.2f} "
                    "USD de margen)"
                ),
            }

        try:
            wr, aw, al = float(win_rate), float(avg_win), float(avg_loss)
            valido = (0.0 <= wr <= 1.0) and (aw > 0) and (al > 0)
        except (TypeError, ValueError):
            valido = False
        if not valido:
            return {
                "status": "datos_invalidos",
                "size": None,
                "fraction": None,
                "note": (
                    f"datos de Kelly fuera de dominio (win_rate={win_rate}, "
                    f"avg_win={avg_win}, avg_loss={avg_loss}): se ignora el "
                    "Kelly. Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%}"
                ),
            }

        # Unico punto de calculo, y es la formula canonica del modulo.
        # Antes estaba duplicada a mano aqui: dos fuentes de verdad para
        # la misma formula es como se acaba midiendo una cosa creyendo
        # que se mide la otra.
        full = float(self.kelly.calculate(wr, aw, al))

        if full <= 0.0:
            # El cero MEDIDO: con estos datos no compensa apostar. Se
            # declara para que sea distinguible de "no hay datos".
            n_txt = (f"{n_closures} cierres" if n_closures is not None
                     else "cierres no informados")
            return {
                "status": "no_viable",
                "size": 0.0,
                "fraction": 0.0,
                "note": (
                    f"Kelly medido = {full:.4f} <= 0 con win_rate={wr:.4f}, "
                    f"avg_win={aw:.6f}, avg_loss={al:.6f} ({n_txt}): no "
                    "compensa apostar (0.0 es una medida, no la ausencia de "
                    "ella). Manda el metodo declarado "
                    f"max_position_size_pct={self.max_position_size_pct:.0%}"
                ),
            }

        fraction = max(0.0, min(1.0, full * self.kelly_fraction))
        n_txt = (f"{n_closures} cierres" if n_closures is not None
                 else "cierres no informados")
        return {
            "status": "ok",
            "size": account_value * fraction,
            "fraction": fraction,
            "note": (
                f"Kelly medido = {full:.4f} x fraccion "
                f"{self.kelly_fraction} = {fraction:.4f} -> "
                f"{account_value * fraction:.2f} USD de margen "
                f"(win_rate={wr:.4f}, {n_txt})"
            ),
        }

    # ------------------------------------------------------------------
    # Cola (VaR/ES) y calidad (Sharpe/Sortino) de la serie de cierres
    # ------------------------------------------------------------------
    #: Unidad en la que se reporta TODO lo de este bloque: fraccion de la
    #: cuenta por cierre. Sin una unidad declarada, dos calculos con el
    #: mismo nombre no son comparables entre si ni con los frenos vivos
    #: (DailyGuard habla de % de capital, el tope de margen tambien).
    SERIE_UNIDAD = "fraccion de la cuenta por cierre"

    def _serie_cierres(
        self,
        pnl_series: Optional[List[float]],
        account_value: float,
    ) -> Tuple[str, Optional[np.ndarray], str]:
        """Serie de cierres normalizada a fraccion de la cuenta.

        Devuelve (estado, serie, nota). La serie es None salvo en "ok":
        el motivo de que no lo este va siempre en la nota, para que el
        registro pueda explicar por que no hay numero en vez de devolver
        un cero que parezca una medida (el mismo bug que tuvo el Kelly).

        Nunca lanza: esta llamada vive dentro del `try` de
        `_apply_margin_cap`, donde cualquier excepcion RECHAZA la entrada
        y un fallo de parseo del ledger no debe costar una operacion.
        """
        if not pnl_series:
            return ("sin_datos", None, (
                "sin serie de cierres: NO se calcula. Unidad que se "
                f"usaria: {self.SERIE_UNIDAD}; horizonte = 1 cierre, NO "
                "diario. El sistema sigue con sus frenos vivos "
                "(DailyGuard, tope de margen y tope de riesgo por "
                "operacion)."
            ))
        try:
            arr = np.array([float(x) for x in pnl_series], dtype=float)
            cuenta = float(account_value)
            validos = (arr.size > 0 and bool(np.isfinite(arr).all())
                       and np.isfinite(cuenta) and cuenta > 0)
        except (TypeError, ValueError, OverflowError):
            validos = False
        if not validos:
            return ("datos_invalidos", None, (
                f"serie de cierres o cuenta fuera de dominio (n="
                f"{len(pnl_series)}, cuenta={account_value}): NO se "
                "calcula en vez de calcular algo dudoso. Unidad que se "
                f"usaria: {self.SERIE_UNIDAD}."
            ))
        return ("ok", arr / cuenta, "")

    def _tail_risk_assessment(
        self,
        pnl_series: Optional[List[float]],
        account_value: float,
    ) -> Dict[str, Any]:
        """VaR y Expected Shortfall de la cola, CON estado explicito.

        Que mide: la perdida maxima esperada (VaR) y la perdida media mas
        alla de esa cola (ES) de UN cierre, en fraccion de la cuenta.
        Delega el calculo en los modulos canonicos
        `quant_math.risk.var.ValueAtRisk` / `ExpectedShortfall`
        (parametrico normal), que hasta el 2026-10-01 no tenian NINGUN
        llamador en produccion.

        Por que no veta: un freno por cola exige un umbral, y el umbral
        se decide con replay sobre el ledger — con la muestra actual
        (9 cierres) el replay deja el VaR-95 entre 0.026 y 0.060 de la
        cuenta segun que cierre se quita, asi que cualquier umbral seria
        una decision tomada sobre ruido. Mientras no haya muestra, esto es
        estado medido y nada mas: `approved` y `reasons` no se tocan.

        Por que dos pisos (20 y 100): ver `MIN_CLOSURES_FOR_SAMPLE` y
        `MIN_CLOSURES_FOR_VAR99`.
        """
        vacio = {"var_95_frac": None, "es_95_frac": None,
                 "var_99_frac": None, "es_99_frac": None}
        status, serie, motivo = self._serie_cierres(pnl_series, account_value)
        if serie is None:
            return {"var_status": status, "var_note": motivo, **vacio}

        n = int(serie.size)
        if n < self.MIN_CLOSURES_FOR_SAMPLE:
            return {
                "var_status": "insuficiente",
                "var_note": (
                    f"solo {n} cierres medidos (piso "
                    f"{self.MIN_CLOSURES_FOR_SAMPLE}): NO se calcula "
                    "VaR/ES. Con N tan chica una sola operacion mueve el "
                    "VaR-95 mas de un 50% (leave-one-out medido sobre el "
                    "ledger real: 0.026-0.060 de la cuenta con N=9), o sea "
                    "que el numero seria ruido. Unidad: "
                    f"{self.SERIE_UNIDAD}; horizonte = 1 cierre. Mandan "
                    "los frenos vivos."
                ),
                **vacio,
            }

        media = float(np.mean(serie))
        dstd = float(np.std(serie, ddof=1))
        var_95 = float(self.var_calculator.calculate(media, dstd, 0.95))
        es_95 = float(self.es_calculator.calculate(media, dstd, 0.95))
        var_99 = None
        es_99 = None
        if n >= self.MIN_CLOSURES_FOR_VAR99:
            var_99 = float(self.var_calculator.calculate(media, dstd, 0.99))
            es_99 = float(self.es_calculator.calculate(media, dstd, 0.99))
            nota_99 = (
                f"VaR-99={var_99:.4%} y ES-99={es_99:.4%} de la cuenta "
                f"medidos con {n} cierres (piso "
                f"{self.MIN_CLOSURES_FOR_VAR99})"
            )
            status = "ok"
        else:
            nota_99 = (
                f"VaR/ES-99 NO medidos: {n} cierres < piso "
                f"{self.MIN_CLOSURES_FOR_VAR99} (el nivel 99% se apoya en "
                "1 observacion de cada 100 y aqui no hay cola empirica "
                "que medir; saldria del supuesto de normalidad, no de los "
                "datos)"
            )
            status = "ok_95"
        return {
            "var_status": status,
            "var_note": (
                f"VaR-95={var_95:.4%} y ES-95={es_95:.4%} de la cuenta — "
                f"unidad: {self.SERIE_UNIDAD}; horizonte = 1 cierre, NO "
                f"diario; metodo parametrico normal sobre {n} cierres. "
                f"{nota_99}. Estado informativo: NO aprueba ni veta "
                "entradas."
            ),
            "var_95_frac": var_95,
            "es_95_frac": es_95,
            "var_99_frac": var_99,
            "es_99_frac": es_99,
        }

    def _quality_assessment(
        self,
        pnl_series: Optional[List[float]],
        account_value: float,
    ) -> Dict[str, Any]:
        """Sharpe y Sortino de la serie de cierres, CON estado explicito.

        Delega en `quant_math.expectation.sharpe_metrics.SharpeMetrics`,
        que hasta el 2026-10-01 solo se instanciaba en `__init__` y no
        tenia ni un llamador.

        Dos decisiones, ambas por medicion:

        1. **NO se anualiza.** La serie es por CIERRE, no diaria:
           `periods_per_year=1`. Anualizarla con 252 (el default del
           modulo) multiplicaria el Sharpe por sqrt(252)=15.9 sin que
           exista ningun horizonte diario detras: con la serie real del
           ledger, -0.29 saldria -4.58 pareciendo una estrategia
           desastrosa cuando solo se ha cambiado la unidad.
        2. **No se compara contra un umbral.** `check_sharpe_threshold`
           (umbral 1.0) sigue sin llamarse: 1.0 es un default sin
           evidencia de este negocio, y aplicarlo con n<20 seria vetar
           entradas con ruido. Cuando haya muestra, el umbral se decide
           con replay.
        """
        vacio = {"sharpe": None, "sortino": None}
        status, serie, motivo = self._serie_cierres(pnl_series, account_value)
        if serie is None:
            return {"sharpe_status": status, "sharpe_note": motivo, **vacio}

        n = int(serie.size)
        if n < self.MIN_CLOSURES_FOR_SAMPLE:
            return {
                "sharpe_status": "insuficiente",
                "sharpe_note": (
                    f"solo {n} cierres medidos (piso "
                    f"{self.MIN_CLOSURES_FOR_SAMPLE}): NO se calcula "
                    "Sharpe/Sortino. Con menos de 20 operaciones una sola "
                    "mueve la estadistica 1/N >= 5 pp, y ademas aqui NO "
                    "se anualiza: la serie es por cierre. Unidad: "
                    f"{self.SERIE_UNIDAD}."
                ),
                **vacio,
            }

        # periods_per_year=1 -> sin anualizar (la serie es por cierre).
        sharpe = float(SharpeMetrics.sharpe_ratio(serie, periods_per_year=1))
        sortino = float(SharpeMetrics.sortino_ratio(serie, periods_per_year=1))
        # `inf` es un caso de borde del modulo (sin perdidas, o
        # desviacion a la baja 0): se guarda None para que el registro
        # siga siendo JSON valido y el motivo quede en la nota, no un
        # Infinity que quien lea el registro no sabe interpretar.
        nota_borde = ""
        if not np.isfinite(sharpe) or not np.isfinite(sortino):
            nota_borde = (" (borde del modulo: sin perdidas o con "
                          "desviacion a la baja 0, el ratio no tiene "
                          "definicion finita)")
            sharpe = sharpe if np.isfinite(sharpe) else None
            sortino = sortino if np.isfinite(sortino) else None
        if float(np.std(serie, ddof=1)) == 0:
            nota_borde = (" (serie plana: std=0, el modulo devuelve 0.0 "
                          "por definicion, no por medida)")
        return {
            "sharpe_status": "ok",
            "sharpe_note": (
                f"Sharpe={sharpe if sharpe is None else round(sharpe, 4)} y "
                f"Sortino={sortino if sortino is None else round(sortino, 4)} "
                f"POR OPERACION y SIN anualizar (serie de {n} cierres, no "
                "diaria; delegado en SharpeMetrics con periods_per_year=1). "
                f"Unidad: {self.SERIE_UNIDAD}.{nota_borde} Estado "
                "informativo: NO aprueba ni veta entradas."
            ),
            "sharpe": sharpe,
            "sortino": sortino,
        }

    def check_drawdown_limit(
        self,
        hypothesis_id: str,
        current_drawdown: float,
        limit: Optional[float] = None
    ) -> bool:
        """
        Check if drawdown is within acceptable limits.

        Args:
            hypothesis_id: Hypothesis ID
            current_drawdown: Current drawdown (positive number)
            limit: Custom drawdown limit (uses default if None)

        Returns:
            True if drawdown is acceptable
        """
        limit = limit or self.drawdown_limit

        acceptable = current_drawdown <= limit

        if not acceptable:
            violation = f"Drawdown {current_drawdown:.2%} exceeds limit {limit:.2%}"
            if hypothesis_id not in self.risk_violations:
                self.risk_violations[hypothesis_id] = []
            self.risk_violations[hypothesis_id].append(violation)

        return acceptable

    def check_sharpe_threshold(
        self,
        sharpe_ratio: float,
        threshold: float = 1.0
    ) -> bool:
        """
        Check if Sharpe ratio meets threshold.

        Args:
            sharpe_ratio: Sharpe ratio to check
            threshold: Minimum acceptable Sharpe ratio

        Returns:
            True if Sharpe ratio meets threshold
        """
        return sharpe_ratio >= threshold

    def check_sortino_threshold(
        self,
        sortino_ratio: float,
        threshold: float = 1.0
    ) -> bool:
        """
        Check if Sortino ratio meets threshold.

        Args:
            sortino_ratio: Sortino ratio to check
            threshold: Minimum acceptable Sortino ratio

        Returns:
            True if Sortino ratio meets threshold
        """
        return sortino_ratio >= threshold

    def check_calmar_threshold(
        self,
        calmar_ratio: float,
        threshold: float = 0.5
    ) -> bool:
        """
        Check if Calmar ratio meets threshold.

        Args:
            calmar_ratio: Calmar ratio to check
            threshold: Minimum acceptable Calmar ratio

        Returns:
            True if Calmar ratio meets threshold
        """
        return calmar_ratio >= threshold

    def calculate_risk_metrics(
        self,
        result: StrategyResult
    ) -> Dict[str, float]:
        """
        Calculate comprehensive risk metrics for strategy.

        Args:
            result: StrategyResult from backtest

        Returns:
            Dictionary with risk metrics
        """
        metrics = {}

        # Basic metrics from result
        metrics["sharpe_ratio"] = result.sharpe_ratio
        metrics["sortino_ratio"] = result.sortino_ratio
        metrics["max_drawdown"] = result.max_drawdown
        metrics["win_rate"] = result.win_rate
        metrics["total_trades"] = result.total_trades
        metrics["profit_factor"] = result.profit_factor

        # VaR/ES using Quant-Math
        if result.trades and len(result.trades) > 0:
            # Extract returns from trades
            returns = []
            for trade in result.trades:
                if isinstance(trade, dict):
                    pnl = trade.get('pnl') or trade.get('PnL')
                    if pnl is not None:
                        returns.append(float(pnl))
                elif hasattr(trade, 'pnl'):
                    returns.append(float(trade.pnl))

            if returns:
                returns_arr = np.array(returns)
                metrics["var_95"] = float(self.var_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.95))
                metrics["var_99"] = float(self.var_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.99))
                metrics["expected_shortfall_95"] = float(self.es_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.95))
                metrics["expected_shortfall_99"] = float(self.es_calculator.calculate(
                    np.mean(returns_arr), np.std(returns_arr), 0.99))

        # Recovery factor
        if result.max_drawdown != 0:
            metrics["recovery_factor"] = abs(result.net_profit) / result.max_drawdown
        else:
            metrics["recovery_factor"] = float('inf')

        return metrics

    def check_correlation_risk(
        self,
        hypothesis_id: str,
        correlations: Dict[str, float],
        max_correlation: float = 0.7
    ) -> Dict[str, Any]:
        """
        Check correlation risk with other strategies.

        Args:
            hypothesis_id: Hypothesis ID
            correlations: Dictionary of correlation coefficients
            max_correlation: Maximum acceptable correlation

        Returns:
            Dictionary with correlation risk assessment
        """
        high_correlations = {}
        for other_id, correlation in correlations.items():
            if abs(correlation) > max_correlation:
                high_correlations[other_id] = correlation

        result = {
            "hypothesis_id": hypothesis_id,
            "max_correlation": max_correlation,
            "high_correlations": high_correlations,
            "has_high_correlation": len(high_correlations) > 0
        }

        if high_correlations:
            warning = f"High correlation detected with {len(high_correlations)} strategies"
            if hypothesis_id not in self.risk_violations:
                self.risk_violations[hypothesis_id] = []
            self.risk_violations[hypothesis_id].append(warning)

        return result

    def stress_test_strategy(
        self,
        result: StrategyResult,
        stress_scenarios: List[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Perform stress testing on strategy.

        Args:
            result: StrategyResult from backtest
            stress_scenarios: List of stress scenarios

        Returns:
            Dictionary with stress test results
        """
        if stress_scenarios is None:
            stress_scenarios = [
                {"name": "market_crash", "return_shock": -0.20},
                {"name": "volatility_spike", "volatility_multiplier": 3.0},
                {"name": "liquidity_crisis", "slippage_multiplier": 5.0}
            ]

        results = {}
        for scenario in stress_scenarios:
            scenario_name = scenario["name"]
            stressed_result = self._apply_stress_scenario(result, scenario)
            results[scenario_name] = stressed_result

        return results

    def _apply_stress_scenario(self, result: StrategyResult, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Apply stress scenario to strategy results"""
        stressed_metrics = {
            "original_total_return": result.total_return,
            "original_sharpe_ratio": result.sharpe_ratio,
            "original_max_drawdown": result.max_drawdown
        }

        if "return_shock" in scenario:
            shocked_return = result.total_return + scenario["return_shock"]
            stressed_metrics["stressed_total_return"] = shocked_return
            stressed_metrics["return_impact"] = scenario["return_shock"]

        if "volatility_multiplier" in scenario:
            stressed_sharpe = result.sharpe_ratio / scenario["volatility_multiplier"]
            stressed_metrics["stressed_sharpe_ratio"] = stressed_sharpe
            stressed_metrics["volatility_impact"] = scenario["volatility_multiplier"]

        if "slippage_multiplier" in scenario:
            # Approximate slippage impact on returns
            stressed_return = result.total_return * (1 - scenario["slippage_multiplier"] * 0.001)
            stressed_metrics["stressed_total_return"] = stressed_return
            stressed_metrics["slippage_impact"] = scenario["slippage_multiplier"]

        return stressed_metrics

    def get_risk_check_history(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Get risk check history for a hypothesis"""
        return self.risk_checks.get(hypothesis_id, [])

    def get_risk_violations(self, hypothesis_id: str) -> List[str]:
        """Get risk violations for a hypothesis"""
        return self.risk_violations.get(hypothesis_id, [])

    def clear_risk_data(self, hypothesis_id: str = None):
        """Clear risk data for a hypothesis or all hypotheses"""
        if hypothesis_id:
            self.position_sizes.pop(hypothesis_id, None)
            self.daily_pnl.pop(hypothesis_id, None)
            self.overall_pnl.pop(hypothesis_id, None)
            self.risk_checks.pop(hypothesis_id, None)
            self.risk_violations.pop(hypothesis_id, None)
        else:
            self.position_sizes.clear()
            self.daily_pnl.clear()
            self.overall_pnl.clear()
            self.risk_checks.clear()
            self.risk_violations.clear()


# Convenience function
def create_risk_manager(**kwargs) -> RiskManager:
    """Create a RiskManager with custom parameters."""
    return RiskManager(**kwargs)