"""
Backtesting & Evaluation Module

This module provides backtesting and performance evaluation capabilities including:
- Backtesting engine
- Walk-forward validation
- Performance metrics (Sharpe, Sortino, drawdown, etc.)
- Portfolio performance tracking
- Trade analysis
- Risk-adjusted returns
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from order_management import OrderManager, ExecutionReport


@dataclass(frozen=True)
class ModeloCoste:
    """Lo que cuesta una operacion ida y vuelta, MEDIDO en el exchange.

    POR QUE ESTA CLASE Y NO TRES PARAMETROS SUELTOS
    ----------------------------------------------
    MEDIDO el 2026-10-02: el motor se construia con los valores por defecto,
    que son `slippage_pct=0.0` y `funding_rate_8h=0.0`. Eso significa que
    TODOS los backtests del proyecto asumian ejecucion perfecta y funding
    gratis, sin decirlo en ninguna parte. Un backtest cuyo modelo de coste se
    calla no se puede auditar, y aqui el silencio iba en la direccion
    favorable: hacia una expectativa mejor que la real.

    Reagruparlos en un objeto con nombre hace que el coste se pueda leer, pasar
    por parametro y comparar, en vez de estar repartido en defaults que nadie
    mira.

    LOS TRES COMPONENTES
    --------------------
    comision_por_lado      La cobra el exchange en cada relleno. Se descuenta
                           en entrada y en salida, o sea que ida y vuelta es
                           el doble.
    deslizamiento_por_llenado
                           Media bid/ask pagada de mas en cada relleno. Se
                           aplica en contra (`_adverse_fill`).
    funding_por_8h        Perpetuo: se paga cada 8 horas por mantener abierto.
                           Es el unico de los tres que depende de cuanto se
                           mantiene la posicion, no de cuantas operaciones se
                           hacen.

    DE DONDE SALEN LOS NUMEROS
    --------------------------
    Medidos contra Bybit el 2026-10-02, no copiados de la documentacion:
      * taker ida y vuelta 0,1268%  ->  0,000634 por lado
      * maker ida y vuelta 0,0268%  ->  0,000134 por lado
      * spread medido en XRP 0,427% (ask 1,591 contra last 1,5248), o sea
        0,2135% de deslizamiento adverse por relleno.
    Los tres vienen con la FECHA porque un exchange cambia sus comisiones y un
    numero sin fecha no es un dato, es un recuerdo.
    """

    comision_por_lado: float = 0.000634
    deslizamiento_por_llenado: float = 0.002135
    funding_por_8h: float = 0.0001
    #: Que se mido cada numero y cuando. Sin esto, un modelo de coste sin
    #: fecha parece tan preciso como uno al dia.
    medido_el: str = "2026-10-02"
    #: Que exchange se midio. Las comisiones cambian por par y por nivel de
    #: VIP: BTC no tiene las mismas que XRP.
    exchange: str = "bybit"

    def ida_y_vuelta_pct(self) -> float:
        """Coste de UNA operacion completa, en %, sin funding.

        El funding se deja fuera a proposito: depende de cuanto se mantiene
        la posicion, que es distinto en cada estrategia, y meterlo aqui
        haria que dos estrategias distintas se compararan con el mismo coste
        de mantenimiento sin serlo.
        """
        return (self.comision_por_lado * 2
                + self.deslizamiento_por_llenado * 2) * 100.0

    def coste_por_operacion_pct(self, horas_mantenido: float = 0.0) -> float:
        """Coste total de una operacion, en %, con el funding incluido."""
        base = self.ida_y_vuelta_pct()
        if horas_mantenido > 0.0:
            base += self.funding_por_8h * (horas_mantenido / 8.0) * 100.0
        return base


#: Suelo de COMISION, sin deslizamiento y sin funding. NO es un modelo de
#: coste: es lo que se paga en el mejor caso y sirve para comparar estrategias
#: entre si, porque todas pagan lo mismo.
#:
#: MEDIDO el 2026-10-02: `COSTE_TAKER` llevaba dentro el deslizamiento de
#: 0,2135% que despues se Retiro por RETRACTADO, y el adaptador lo usaba como
#: valor por defecto. O sea que la ruta de produccion estaba cobrando 4,4 veces
#: de mas, y solo se vio al mirar que valor llevaba la constante. Por eso
#: `COSTE_COMISION` no lleva ningun otro componente: un suelo no puede
#: convertirse sin querer en un coste.
#:
#: La comision es la de Bybit VIP 0 publicada (taker 0,0550% por lado) y la
#: MEDIDA contra el exchange (0,0634% por lado, que es un 15% mas alta). Se usa
#: la medida, por ser la propia, y la diferencia queda anotada aqui.
COSTE_TAKER = ModeloCoste(comision_por_lado=0.000634,
                           deslizamiento_por_llenado=0.0,
                           funding_por_8h=0.0)
COSTE_MAKER = ModeloCoste(comision_por_lado=0.000134,
                           deslizamiento_por_llenado=0.0,
                           funding_por_8h=0.0)
#: Alias con el nombre que dice lo que es. `COSTE_TAKER` se conserva por
#: compatibilidad, y este es el nombre que hay que usar.
COSTE_COMISION = COSTE_TAKER

#: COTES DE FUNDING. MEDIDO el 2026-10-02 sobre 3.800 periodos por simbolo:
#: los cuatro liquidan CADA 8 HORAS, sin excepcion, y siempre a las 00:00,
#: 08:00 y 16:00 UTC. Se comprueba porque algunos pares de otros exchanges
#: liquidan cada hora, y con un modelo de 8 horas un par de 1 hora estaria 8
#: veces mal.
FUNDING_HORAS = (0, 8, 16)
FUNDING_CADA_HORAS = 8


def periodo_para(ts) -> Optional[str]:
    """Que regimen de funding le toca a una fecha, o None si no hay ninguno.

    Se deduce de la FECHA DE LA VELA, no se pide. Antes habia que pasar el
    periodo a mano y quien no lo pasara se llevaba un coste de un regimen
    equivocado sin enterarse, que es la forma de error mas comun: un valor por
    defecto que nadie mira.
    """
    import datetime as _dt
    if ts is None:
        return None
    if hasattr(ts, "year"):
        anio = ts.year
    elif hasattr(ts, "timestamp"):
        anio = _dt.datetime.utcfromtimestamp(ts / 1000.0).year
    else:
        return None
    for nombre, (desde, hasta) in CORTE_PERIODO_FUNDING.items():
        if desde <= anio <= hasta:
            return nombre
    return None


#: De que año a que año cubre cada regimen medido. El corte de 2025-01-01 es
#: el mismo que usan los backtests, para que la comparacion sea entre las dos
#: cosas medidas con el mismo corte.
CORTE_PERIODO_FUNDING = {"2023-2024": (2023, 2024), "2025-2026": (2025, 2026)}

#: SPREAD POR SIMBOLO, MEDIDO. 25 muestras del libro de ordenes separadas
#: ~0,35 s el 2026-10-02, y se guarda la mediana y no un punto suelto.
#:
#: POR QUE ESTA TABLA Y NO UN NUMERO
#: ---------------------------------
#: MEDIDO el 2026-10-02: el modelo usaba 0,2135% de deslizamiento por relleno,
#: salido de UN tick de XRP (ask 1,591 contra bid 1,5842). Con 25 muestras por
#: simbolo, ese numero era 65 veces demasiado alto para XRP y 4.270 para BTC:
#:
#:     BTC  0,00012%      ETH  0,00036%
#:     XRP  0,00649%      SOL  0,00822%
#:
#: O sea que el spread es DESPRECIABLE frente a la comision, y el modelo lo
#: estaba CBARRO por un factor de 4 al calcular el coste total. Con estos
#: valores, el coste real ida y vuelta queda en 0,1270% a 0,1432% segun el
#: simbolo, y no en el 0,5538% que se venia usando.
#:
#: LO QUE NO SE PUEDE MEDIR, Y POR QUE NO SE INVENTA
#: -------------------------------------------------
#: El spread HISTORICO. El exchange no lo publica y no sale de las velas:
#: high/low son extremos del rango, no el precio al que se ejecutaba. Usar el
#: rango de la vela como spread seria inventarse un numero. Esto es una foto
#: de AHORA y por eso lleva fecha, y por eso hay una fila `medido_el` que
#: obliga a volver a mirarla antes de Nabi reutilizarla para un periodo viejo.
#: Los valores van en PORCENTAJE porque es como se midieron, y se convierten
#: a fraccion en `coste_para`. MEDIDO al escribirlo: la primera version los
#: guardaba en porcentaje y los usaba como fraccion, o sea que el spread
#: llegaba 100 veces grande y el coste de XRP salia en 1,42% en vez de 0,14%.
#: Es el mismo error que hizo que el "0,1268%" de la sesion pasara por coste
#: cuando era solo la comision: una unidad mal puesta pesa mas que un valor
#: mal puesto, porque no se nota.
SPREAD_POR_SIMBOLO_PCT = {
    "BTC": 0.00012,
    "ETH": 0.00036,
    "XRP": 0.00649,
    "SOL": 0.00822,
}

#: FUNDING POR SIMBOLO Y PERIODO, de la serie real de 3.800 periodos por
#: simbolo (2023-04-15 a 2026-10-02, endpoint publico
#: `publicGetV5MarketFundingHistory`). NO es un valor medio del periodo
#: entero: el funding de 2025-2026 es entre 3 y 10 veces mas barato que el de
#: 2023-2024, y usarlo como media subestima un tramo y sobreestima el otro.
#:
#:     simbolo  2023-2024   2025-2026   negativos 2025-2026
#:     BTC        0,01002%    0,00363%      23,1%
#:     ETH        0,01009%    0,00347%      25,1%
#:     XRP        0,01253%    0,00270%      32,4%
#:     SOL        0,01079%    0,00095%      38,3%
#:
#: Y el funding es NEGATIVO entre el 10% y el 38% de los periodos segun
#: simbolo y periodo, o sea que un largo en un tramo negativo RECIBE dinero y
#: uno largo en un tramo positivo lo PAGA. El signo cambia el coste, no solo
#: su magnitud.
#: SLIPPAGE EFECTIVO POR NOTIONAL, recorriendo el libro de ordenes.
#:
#: MEDIDO el 2026-10-02: 6 tomas por simbolo con `fetch_order_book(limit=500)`
#: y recorrido nivel a nivel. Es la ida y vuelta: se paga en la compra y se
#: cobra de menos en la venta, asi que los dos se SUMAN con valor absoluto.
#:
#:     nocional      BTC      ETH      XRP      SOL
#:         250    0,00000  0,00000  0,00000  0,00000
#:       2.500    0,00000  0,00000  0,00000  0,00000
#:      25.000    0,00000  0,00000  0,01171  0,01504
#:     100.000    0,00000  0,00342  0,03273  0,01438
#:     500.000    0,00319  0,02516  0,09037  0,04629
#:
#: LO QUE ESTO DICE, Y CORRIGE UNA AFIRMACION ANTERIOR
#: --------------------------------------------------
#: A 25.000 USDT, que es el nocional del backtest, el deslizamiento es CERO en
#: BTC y ETH y de 0,011-0,015% en XRP y SOL. El primer nivel de BTC tiene
#: 3,193 BTC (268.295 USDT medidos), o sea que un nocional de 25.000 se
#: ejecuta en el primer nivel.
#:
#: Se publico antes lo contrario: 0,1822% para SOL a 25.000, "11 veces el
#: spread del primer nivel". Era DOCE VECES MAYOR de lo real, y venia de un
#: error en el recorrido: el tamano de un nivel va en UNIDADES DEL ACTIVO y se
#: estaba restando de un presupuesto en USDT, con lo que un nocional de 250
#: USDT consumia 250 BTC y agotaba el libro entero. Con el recorrido mal, el
#: slippage grows como el PRECIO del activo: BTC (el activo mas caro)
#: aparecia como el mas caro de operar, que es al reves de lo real.
#:
#: LA LECCION QUE NO SE DEJA OLVIDAR
#: ---------------------------------
#: El recorrido del libro tiene UN concepto de unidades que hay que tener bien
#: a la primera. Tres versiones seguidas de esta medicion dieron tres numeros
#: distintos, y los dos primeros eranWrong por el mismo tipo de fallo: unidades
#: mezcladas. La primera tambien se cancelaba con signo y contaba niveles de
#: tamano cero.
#:
#: LO QUE SI DICE LA TABLA
#: -----------------------
#: La profundidad importa a partir de unos 100.000 USDT, no antes. A 500.000 el
#: deslizamiento va de 0,003% en BTC a 0,090% en XRP, y XRP pasa a ser el
#: simbolo mas caro, no SOL.
SLIPPAGE_POR_NOTIONAL = {
    "BTC": {250.0: 0.0, 2500.0: 0.0, 25000.0: 0.0, 100000.0: 0.0, 500000.0: 0.00319},
    "ETH": {250.0: 0.0, 2500.0: 0.0, 25000.0: 0.0, 100000.0: 0.00342, 500000.0: 0.02516},
    "XRP": {250.0: 0.0, 2500.0: 0.0, 25000.0: 0.01171, 100000.0: 0.03273, 500000.0: 0.09037},
    "SOL": {250.0: 0.0, 2500.0: 0.0, 25000.0: 0.01504, 100000.0: 0.01438, 500000.0: 0.04629},
}


def simbolo_medido(simbolo: str, nocional: float) -> bool:
    """Si hay una medicion de deslizamiento que cubra ese nocional.

    False significa que `slippage_para` devuelve 0.0 porque NO SE HA MEDIDO, y
    no porque el deslizamiento sea cero. Son cosas distintas y confundirlas
    hace que un backtest parezca gratis.
    """
    base = simbolo.split("/")[0].split(":")[0].upper()
    filas = SLIPPAGE_POR_NOTIONAL.get(base)
    return bool(filas) and any(n <= nocional for n in filas)


def slippage_para(simbolo: str, nocional: float) -> float:
    """Deslizamiento efectivo IDA Y VUELTA, en %, para ese nocional.

    Elige la fila medida mas cercana POR DEBAJO del nocional pedido, y nunca
    interpola hacia arriba: un nocional por encima de lo medido se queda con la
    ultima fila, que es la mas cara de las conocidas, y no con una
    interpolacion optimista.

    Los cuatro simbolos tienen la tabla completa, asi que `simbolo_medido`
    devuelve True para todos los nocionales medidos. Se mantiene la funcion
    porque un hueco debe poder preguntar, no porque hoy haya alguno.
    """
    base = simbolo.split("/")[0].split(":")[0].upper()
    filas = SLIPPAGE_POR_NOTIONAL.get(base)
    if not filas:
        return 0.0
    no_superan = [n for n in filas if n <= nocional]
    return filas[max(no_superan)] if no_superan else filas[min(filas)]


FUNDING_POR_SIMBOLO = {
    "BTC": {"2023-2024": 0.01002, "2025-2026": 0.00363},
    "ETH": {"2023-2024": 0.01009, "2025-2026": 0.00347},
    "XRP": {"2023-2024": 0.01253, "2025-2026": 0.00270},
    "SOL": {"2023-2024": 0.01079, "2025-2026": 0.00095},
}


def coste_para(simbolo: str, horas_mantenido: float = 0.0,
               periodo: Optional[str] = None,
               taker: bool = True) -> ModeloCoste:
    """El modelo de coste REAL de un simbolo, con sus numeros medidos.

    `periodo` es "2023-2024" o "2025-2026", y es OBLIGATORIO cuando se pide el
    funding: sin el se devolveria el promedio de los dos regimes, que es un
    numero que no corresponde a ningun tramo real.

    Se pasa el simbolo porque el spread y el funding varian por par: BTC tiene
    un libro 54 veces mas ajustado que SOL, y un solo numero para los cuatro
    obliga a que uno de los dos pague el coste del otro.
    """
    base = simbolo.split("/")[0].split(":")[0].upper()
    spread = SPREAD_POR_SIMBOLO_PCT.get(base, 0.2135) / 100.0
    modelo = ModeloCoste(
        comision_por_lado=0.000634 if taker else 0.000134,
        deslizamiento_por_llenado=spread,
        funding_por_8h=0.0,
    )
    if periodo:
        fila = FUNDING_POR_SIMBOLO.get(base, {})
        if periodo not in fila:
            raise ValueError(
                f"periodo {periodo!r} sin funding medido para {base}; hay "
                f"{sorted(fila)}. Sin ese dato no se puede costear: el "
                f"promedio de los dos regimes no representa a ninguno")
        modelo = ModeloCoste(
            comision_por_lado=modelo.comision_por_lado,
            deslizamiento_por_llenado=modelo.deslizamiento_por_llenado,
            funding_por_8h=fila[periodo] / 100.0)
    return modelo


@dataclass
class Trade:
    """Represents a single trade."""
    trade_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    hold_duration: float
    entry_time: float
    exit_time: float
    commission: float
    liquidated: bool = False       # True if closed by liquidation (leverage)
    funding_paid: float = 0.0      # total funding paid while holding


@dataclass
class BacktestResult:
    """Result of backtesting."""
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    annualized_volatility: float
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    trades: List[Trade]
    equity_curve: List[Tuple[float, float]]
    num_liquidations: int = 0
    total_funding_paid: float = 0.0


@dataclass
class WalkForwardResult:
    """Result of walk-forward validation."""
    windows: List[Dict[str, Any]]
    is_stats: Dict[str, float]
    oos_stats: Dict[str, float]
    robustness_score: float
    parameter_stability: float


class WalkForwardValidator:
    """
    Walk-Forward Validation Engine

    Implements walk-forward analysis for robust strategy validation:
    - Anchored/rolling window walk-forward
    - In-sample optimization, out-of-sample testing
    - Robustness scoring
    - Parameter stability analysis
    """

    def __init__(
        self,
        backtester: 'Backtester',
        train_window: int = 252,  # ~1 year for daily
        test_window: int = 63,    # ~3 months for daily
        step_size: int = 63,      # Step by 3 months
        anchored: bool = True,    # Anchored (expanding) vs rolling
        min_train_size: int = 100
    ):
        self.backtester = backtester
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size
        self.anchored = anchored
        self.min_train_size = min_train_size

    def validate(
        self,
        strategy_func: Callable,
        data: Dict[str, np.ndarray],
        param_grid: Optional[Dict[str, List]] = None,
        initial_capital: Optional[float] = None
    ) -> WalkForwardResult:
        """
        Run walk-forward validation.

        Parameters
        ----------
        strategy_func : callable
            Strategy function that takes data and params, returns orders
        data : dict
            Dictionary of {symbol: price_array}
        param_grid : dict, optional
            Parameter grid for optimization {param_name: [values]}
        initial_capital : float, optional
            Initial capital

        Returns
        -------
        result : WalkForwardResult
            Walk-forward validation results
        """
        if initial_capital is None:
            initial_capital = self.backtester.initial_capital

        # Get data length (assume all symbols same length)
        symbol = list(data.keys())[0]
        n_bars = len(data[symbol])

        windows = []
        is_returns = []
        oos_returns = []
        is_sharpes = []
        oos_sharpes = []
        best_params_per_window = []

        # Walk-forward loop
        start = 0
        window_idx = 0

        while start + self.train_window + self.test_window <= n_bars:
            train_end = start + self.train_window
            test_end = min(train_end + self.test_window, n_bars)

            if test_end - train_end < 10:
                break

            # Extract train/test slices
            train_data = {s: prices[start:train_end] for s, prices in data.items()}
            test_data = {s: prices[train_end:test_end] for s, prices in data.items()}

            # In-sample optimization (if param_grid provided)
            if param_grid:
                best_params, best_score = self._optimize_params(
                    strategy_func, train_data, param_grid, initial_capital
                )
            else:
                best_params = {}
                best_score = None

            best_params_per_window.append(best_params)

            # In-sample backtest with best params
            is_result = self._run_with_params(
                strategy_func, train_data, best_params, initial_capital
            )

            # Out-of-sample backtest with best params
            oos_result = self._run_with_params(
                strategy_func, test_data, best_params, initial_capital
            )

            # Collect metrics
            is_ret = is_result.total_return_pct
            oos_ret = oos_result.total_return_pct
            is_sharpe = is_result.sharpe_ratio
            oos_sharpe = oos_result.sharpe_ratio

            is_returns.append(is_ret)
            oos_returns.append(oos_ret)
            is_sharpes.append(is_sharpe)
            oos_sharpes.append(oos_sharpe)

            windows.append({
                'window': window_idx,
                'train_start': start,
                'train_end': train_end,
                'test_start': train_end,
                'test_end': test_end,
                'train_bars': train_end - start,
                'test_bars': test_end - train_end,
                'best_params': best_params,
                'is_return': is_ret,
                'oos_return': oos_ret,
                'is_sharpe': is_sharpe,
                'oos_sharpe': oos_sharpe,
                'is_trades': is_result.num_trades,
                'oos_trades': oos_result.num_trades,
                'is_win_rate': is_result.win_rate,
                'oos_win_rate': oos_result.win_rate,
            })

            window_idx += 1

            # Move window
            if self.anchored:
                # Anchored: expand training window
                start += self.step_size
                self.train_window += self.step_size
            else:
                # Rolling: fixed window size
                start += self.step_size

        # Calculate aggregate statistics
        is_stats = self._compute_stats(is_returns, is_sharpes, 'IS')
        oos_stats = self._compute_stats(oos_returns, oos_sharpes, 'OOS')

        # Robustness score
        robustness = self._compute_robustness(is_returns, oos_returns, is_sharpes, oos_sharpes)

        # Parameter stability
        param_stability = self._compute_param_stability(best_params_per_window)

        return WalkForwardResult(
            windows=windows,
            is_stats=is_stats,
            oos_stats=oos_stats,
            robustness_score=robustness,
            parameter_stability=param_stability
        )

    def _optimize_params(
        self,
        strategy_func: Callable,
        train_data: Dict[str, np.ndarray],
        param_grid: Dict[str, List],
        initial_capital: float
    ) -> Tuple[Dict, float]:
        """Grid search optimization on training data."""
        import itertools

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        best_score = -float('inf')
        best_params = {}

        for combo in itertools.product(*param_values):
            params = dict(zip(param_names, combo))

            try:
                result = self._run_with_params(
                    strategy_func, train_data, params, initial_capital
                )
                # Score: combination of return and sharpe
                score = result.total_return_pct * 0.5 + result.sharpe_ratio * 50 * 0.5
                if result.num_trades < 5:
                    score -= 100  # Penalty for too few trades

                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception:
                continue

        return best_params, best_score

    def _run_with_params(
        self,
        strategy_func: Callable,
        data: Dict[str, np.ndarray],
        params: Dict,
        initial_capital: float
    ) -> BacktestResult:
        """Run backtest with specific parameters."""

        def param_strategy(d):
            return strategy_func(d, **params)

        return self.backtester.run_backtest(param_strategy, data, initial_capital)

    def _compute_stats(self, returns: List[float], sharpes: List[float], prefix: str) -> Dict:
        """Compute aggregate statistics."""
        if not returns:
            return {f'{prefix}_mean_return': 0, f'{prefix}_mean_sharpe': 0,
                    f'{prefix}_std_return': 0, f'{prefix}_win_rate': 0,
                    f'{prefix}_profit_factor': 0, f'{prefix}_consistency': 0}

        returns_arr = np.array(returns)
        sharpes_arr = np.array(sharpes)

        # Profit factor
        gross_profit = np.sum(returns_arr[returns_arr > 0])
        gross_loss = abs(np.sum(returns_arr[returns_arr < 0]))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Consistency: percentage of positive windows
        consistency = np.mean(returns_arr > 0) * 100

        return {
            f'{prefix}_mean_return': float(np.mean(returns_arr)),
            f'{prefix}_median_return': float(np.median(returns_arr)),
            f'{prefix}_std_return': float(np.std(returns_arr)),
            f'{prefix}_mean_sharpe': float(np.mean(sharpes_arr)),
            f'{prefix}_median_sharpe': float(np.median(sharpes_arr)),
            f'{prefix}_win_rate': float(np.mean(returns_arr > 0) * 100),
            f'{prefix}_profit_factor': pf if pf != float('inf') else 999,
            f'{prefix}_consistency': consistency,
            f'{prefix}_best_window': float(np.max(returns_arr)),
            f'{prefix}_worst_window': float(np.min(returns_arr)),
        }

    def _compute_robustness(
        self,
        is_returns: List[float],
        oos_returns: List[float],
        is_sharpes: List[float],
        oos_sharpes: List[float]
    ) -> float:
        """Compute robustness score (0-100)."""
        if not is_returns or not oos_returns:
            return 0.0

        # Correlation between IS and OOS performance
        try:
            corr = np.corrcoef(is_returns, oos_returns)[0, 1]
            if np.isnan(corr):
                corr = 0
        except Exception:
            corr = 0

        # OOS consistency
        oos_consistency = np.mean(np.array(oos_returns) > 0)

        # OOS Sharpe quality
        oos_mean_sharpe = np.mean(oos_sharpes)
        oos_sharpe_quality = min(max(oos_mean_sharpe / 2.0, 0), 1)  # Normalize to 0-1

        # Degradation factor (IS vs OOS)
        is_mean = np.mean(is_returns)
        oos_mean = np.mean(oos_returns)
        if is_mean != 0:
            degradation = max(0, min(oos_mean / is_mean, 2))  # Cap at 2x
        else:
            degradation = 0

        # Combined robustness score
        robustness = (
            0.3 * max(0, corr) * 100 +      # IS-OOS correlation (0-100)
            0.3 * oos_consistency * 100 +   # OOS win rate (0-100)
            0.2 * oos_sharpe_quality * 100 + # OOS Sharpe quality (0-100)
            0.2 * degradation * 50          # Degradation factor (0-100)
        )

        return float(max(0, min(robustness, 100)))

    def _compute_param_stability(self, params_per_window: List[Dict]) -> float:
        """Compute parameter stability across windows (0-100)."""
        if len(params_per_window) < 2:
            return 100.0

        # Get all parameter names
        all_names = set()
        for p in params_per_window:
            all_names.update(p.keys())

        if not all_names:
            return 100.0

        stabilities = []
        for name in all_names:
            values = [p.get(name) for p in params_per_window if name in p]
            if len(values) < 2:
                stabilities.append(100)
                continue

            # Coefficient of variation
            mean_val = np.mean(values)
            if mean_val != 0:
                cv = np.std(values) / abs(mean_val)
                # Convert to stability (lower CV = higher stability)
                stability = max(0, 100 * (1 - min(cv, 1)))
            else:
                stability = 100 if np.std(values) == 0 else 0
            stabilities.append(stability)

        return float(np.mean(stabilities))


class PerformanceMetrics:
    # ... (rest of existing class)
    """
    Performance Metrics Calculator

    Calculates various performance metrics for trading strategies.
    """

    @staticmethod
    def total_return(initial: float, final: float) -> float:
        """Calculate total return."""
        return final - initial

    @staticmethod
    def total_return_pct(initial: float, final: float) -> float:
        """Calculate total return percentage."""
        return (final - initial) / initial * 100

    @staticmethod
    def cumulative_returns(prices: List[float]) -> List[float]:
        """Calculate cumulative returns."""
        returns = np.diff(prices) / prices[:-1]
        cumulative = 1.0
        cumulative_returns = [cumulative]

        for r in returns:
            cumulative *= (1 + r)
            cumulative_returns.append(cumulative)

        return np.array(cumulative_returns)

    #: Velas por año por temporalidad de Bybit. MEDIDO el 2026-10-01: el
    #: numero de barras al año es `365,25 dias * velas/dia`, y las velas por
    #: dia son 1440/horas. Un año tiene 35.040 barras de 15m, no 252.
    #:
    #: Se declara aqui y no se calcula con `sqrt(252)` porque el error de
    #: antes no era de precision: era de UNIDADES. Un Sharpe calculado con
    #: 252 sobre velas de 15m compara una media de 15 minutos contra una
    #: desviacion de un dia.
    PERIODOS_POR_ANIO = {
        "1m": 525_600, "3m": 175_200, "5m": 105_120, "15m": 35_040,
        "30m": 17_520, "1h": 8_760, "2h": 4_380, "4h": 2_190, "1d": 365,
    }

    @classmethod
    def periodos_por_anio(cls, timeframe: Optional[str]) -> int:
        """Velas al año de una temporalidad. `None` o desconocida -> diaria.

        Se cae a 365 y no a 252 a proposito: 252 son DIAS DE MERCADO sobre
        velas diarias, y cualquier otra temporalidad necesita velas. Con
        `None` el valor es una aproximacion declarada, no una medida, y el
        llamante puede ver cual es por el propio resultado.
        """
        if not timeframe:
            return cls.PERIODOS_POR_ANIO["1d"]
        return cls.PERIODOS_POR_ANIO.get(str(timeframe).strip().lower(),
                                        cls.PERIODOS_POR_ANIO["1d"])

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02,
                     period: str = 'daily',
                     periods_per_year: Optional[int] = None) -> float:
        """
        Calculate Sharpe ratio.

        Parameters
        ----------
        returns : np.ndarray
            Period returns
        risk_free_rate : float
            Risk-free rate (annualized)
        period : str
            Period type ('daily', 'weekly', 'monthly')

        Returns
        -------
        sharpe : float
            Sharpe ratio
        """
        if len(returns) == 0:
            return 0.0

        # CORREGIDO el 2026-10-01. Antes el numero de periodos al año estaba
        # FIJO en 252 sin importar la temporalidad, con lo que un backtest de
        # 15m se annualizaba como si cada vela fuera un dia. Y el riesgo sin
        # riesgo, que es ANUAL, se restaba de una media ya multiplicada.
        #
        # Ahora `periods_per_year` se puede pasar explicito (lo hace
        # `run_backtest` con la temporalidad real) y el riesgo sin riesgo se
        # escala al periodo ANTES de restar, que es la unica forma de que los
        # dos terminos sean de la misma unidad:
        #
        #     sharpe_anual = (media - rf_anual/P) * sqrt(P) / sigma
        #
        # Si se deja `period` y no `periods_per_year`, manda `period` (se
        # conserva el comportamiento historico para los llamantes viejos).
        if periods_per_year is None:
            if period == 'daily':
                periods_per_year = 252
            elif period == 'weekly':
                periods_per_year = 52
            else:
                periods_per_year = 12
        periods_per_year = max(1, int(periods_per_year))

        rf_periodo = risk_free_rate / periods_per_year
        media = np.mean(returns)
        sigma = np.std(returns)
        if sigma == 0:
            return 0.0
        sharpe = (media - rf_periodo) * np.sqrt(periods_per_year) / sigma

        return float(sharpe)

    @staticmethod
    def sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.02,
                      period: str = 'daily') -> float:
        """
        Calculate Sortino ratio.

        Parameters
        ----------
        returns : np.ndarray
            Period returns
        risk_free_rate : float
            Risk-free rate (annualized)
        period : str
            Period type

        Returns
        -------
        sortino : float
            Sortino ratio
        """
        if len(returns) == 0:
            return 0.0

        # Convert to annualized
        if period == 'daily':
            periods_per_year = 252
        elif period == 'weekly':
            periods_per_year = 52
        else:
            periods_per_year = 12

        mean_return = np.mean(returns) * periods_per_year
        downside_returns = returns[returns < 0]
        if downside_returns.size == 0:
            # sin periodos perdedores: riesgo a la baja indefinidamente bajo
            return float("inf") if returns.size else 0.0
        downside_std = np.std(downside_returns) * np.sqrt(periods_per_year)

        if not np.isfinite(downside_std) or downside_std == 0:
            return 0.0

        sortino = (mean_return - risk_free_rate) / downside_std

        return sortino

    @staticmethod
    def max_drawdown(prices: List[float]) -> float:
        """
        Calculate maximum drawdown.

        Parameters
        ----------
        prices : List[float]
            Price series

        Returns
        -------
        max_dd : float
            Maximum drawdown percentage
        """
        if len(prices) == 0:
            return 0.0

        prices_array = np.array(prices)
        cumulative = np.maximum.accumulate(prices_array)
        drawdowns = (prices_array - cumulative) / cumulative * 100
        # CORREGIDO el 2026-10-01. Aqui estaba `np.max(drawdowns)`, y eso
        # devolvia 0.0 SIEMPRE, no "casi siempre": por construccion
        # `prices <= maximo_acumulado`, luego todos los drawdowns son <= 0, y
        # el maximo de una serie no positiva es el MAS CERCANO a cero.
        # Demostrado: [100, 90, 80, 85, 90, 110] cae un 20% y devolvia 0,0.
        #
        # Un drawdown es una PERDIDA, asi que el peor es el mas negativo y se
        # reporta en positivo. Con `np.max` el motor de riesgo recibia "no he
        #endido ninguna perdida" en cada operacion perdedora que tuviera,
        # que es justo cuando tiene que verla.
        max_drawdown = abs(float(np.min(drawdowns)))

        return max_drawdown

    @staticmethod
    def win_rate(trades: List[Trade]) -> float:
        """
        Calculate win rate.

        Parameters
        ----------
        trades : List[Trade]
            Trade history

        Returns
        -------
        win_rate : float
            Win rate percentage
        """
        if len(trades) == 0:
            return 0.0

        wins = sum(1 for t in trades if t.pnl > 0)
        return wins / len(trades) * 100

    @staticmethod
    def profit_factor(trades: List[Trade]) -> float:
        """
        Calculate profit factor.

        Parameters
        ----------
        trades : List[Trade]
            Trade history

        Returns
        -------
        pf : float
            Profit factor
        """
        if len(trades) == 0:
            return 0.0

        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

        if gross_loss == 0:
            return float('inf')

        return gross_profit / gross_loss


class Backtester:
    """
    Backtesting Engine

    Executes strategy backtests and calculates performance metrics.
    """

    # Futures realism defaults (Bybit USDT perpetuals)
    DEFAULT_FUNDING_8H = 0.0001      # 0.01% per 8h funding interval
    DEFAULT_SLIPPAGE_PCT = 0.0001   # 1bp adverse fill
    #: MMR por defecto = 0,0033, LEIDO del endpoint publico de Bybit el
    #: 2026-09-30 (`/v5/market/risk-limit`, primer tramo, que es el que
    #: corresponde a un nocional pequeno). Antes estaba HARDCODEADO en 0,005,
    #: que era el segundo tramo y ademas un supuesto: eso ponia la
    #: liquidacion MAS CERCA de lo real, o sea que el backtest era
    #: OPTIMISTA y se:"-subestimaba" el riesgo de liquidacion.
    #: El MMR real es ESCALONADO por nocional; ver
    #: `quant_math.risk.roe_targets.BYBIT_MMR_TIERS` y `mmr_for_notional()`.
    MAINTENANCE_MARGIN_RATE = 0.0033  # primer tramo real de Bybit (2026-09-30)

    def __init__(self, initial_capital: float = 100000.0,
                 commission_rate: float = 0.001,
                 min_commission: float = 0.0,
                 slippage_pct: float = 0.0,
                 leverage: float = 1.0,
                 funding_rate_8h: float = 0.0,
                 timeframe: str = "1h",
                 maintenance_margin_rate: Optional[float] = None):
        """
        Initialize backtester.

        Parameters
        ----------
        initial_capital : float
            Initial capital
        commission_rate : float
            Commission rate
        min_commission : float
            Minimum commission
        slippage_pct : float
            Adverse slippage per fill as fraction (e.g. 0.0001 = 1bp).
            0.0 significa EJECUCION PERFECTA, y se conserva solo por
            compatibilidad con los tests que asertan aritmetica sobre
            precios desnudos. MEDIDO el
            2026-10-02: a spread real de 0,427% en XRP, asi que un backtest
            con 0,0 se esta atribuyendo una ejecucion que el exchange no
            concede. Para produccion usa `ModeloCoste`.
        leverage : float
            Position leverage. 1.0 = spot (legacy behaviour). >1 scales PnL,
            posts margin instead of full notional, and enables liquidation.
        funding_rate_8h : float
            Perpetual funding rate per 8h as fraction of notional
            (e.g. 0.0001 = 0.01%). 0.0 lo desactiva, y desactivarlo es
            asumir que mantener una posicion abierta es gratis. MEDIDO el
            2026-10-02: el
            funding fue NEGATIVO (los largos pagaban) de febrero a abril de
            2026, asi que ignorarlo no es conservador, es falso. Para
            produccion usa `ModeloCoste`.
        timeframe : str
            Candle timeframe ('1m','5m','15m','1h','4h','1d') used to convert
            bars held into hours for funding accrual.
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage_pct = max(0.0, float(slippage_pct))
        self.leverage = max(1.0, float(leverage))
        self.funding_rate_8h = float(funding_rate_8h)
        self.timeframe = timeframe
        # MMR configurable: el real de Bybit es escalonado por nocional y el
        # valor hardcodeado (0,005) era del segundo tramo. Con None se usa el
        # primer tramo real, que es el que corresponde a un nocional pequeno.
        self.maintenance_margin_rate = float(
            self.MAINTENANCE_MARGIN_RATE
            if maintenance_margin_rate is None else maintenance_margin_rate)

    # ------------------------------------------------------------------
    # Futures realism helpers
    # ------------------------------------------------------------------

    def _timeframe_hours(self) -> float:
        """Hours per candle for funding accrual."""
        tf = (self.timeframe or "1h").strip().lower()
        try:
            if tf.endswith("m"):
                return float(tf[:-1]) / 60.0
            if tf.endswith("h"):
                return float(tf[:-1])
            if tf.endswith("d"):
                return float(tf[:-1]) * 24.0
        except ValueError:
            pass
        return 1.0

    def _adverse_fill(self, price: float, side: str) -> float:
        """Adverse slippage fill: buy pays more, sell receives less."""
        if side == "buy":
            return price * (1.0 + self.slippage_pct)
        return price * (1.0 - self.slippage_pct)

    def _fee(self, notional: float) -> float:
        return max(self.min_commission, notional * self.commission_rate)

    def _funding_cost(self, notional: float, bars_held: int) -> float:
        """Funding paid for holding `bars_held` bars at current notional."""
        if self.funding_rate_8h == 0.0 or bars_held <= 0:
            return 0.0
        hours = bars_held * self._timeframe_hours()
        return notional * self.funding_rate_8h * (hours / 8.0)

    def _liq_price_long(self, entry_price: float) -> Optional[float]:
        """Liquidation price for a long at configured leverage (None if spot)."""
        if self.leverage <= 1.0:
            return None
        drop = 1.0 / self.leverage - self.maintenance_margin_rate
        if drop <= 0:
            return None
        return entry_price * (1.0 - drop)

    def _touched_liq(self, series: np.ndarray, entry_idx: int,
                     exit_idx: int, liq_price: Optional[float]) -> bool:
        """True if any bar low (close series proxy) touched liquidation."""
        if liq_price is None:
            return False
        lo = int(max(0, entry_idx))
        hi = int(min(len(series), exit_idx + 1))
        if hi <= lo:
            return False
        return bool(np.min(series[lo:hi]) <= liq_price)

    def run_backtest(self, strategy_func: Callable, data: Dict[str, np.ndarray],
                    initial_capital: Optional[float] = None,
                    timeframe: Optional[str] = None) -> BacktestResult:
        """
        Run backtest for a strategy.

        Parameters
        ----------
        strategy_func : callable
            Strategy function that takes data and returns orders
        data : dict
            Dictionary of {symbol: price_array}
        initial_capital : float, optional
            Initial capital

        Returns
        -------
        result : BacktestResult
            Backtest results
        """
        if initial_capital is None:
            initial_capital = self.initial_capital

        capital = initial_capital
        orders = strategy_func(data)
        trades = []
        # Mutable counters shared with fill logic below
        num_liquidations = [0]
        total_funding_paid = [0.0]

        # Simulate execution - only process non-hold orders
        executed_orders = []
        for i, order in enumerate(orders):
            if order['symbol'] in data and order['side'] != 'hold':
                price = data[order['symbol']][i]
                quantity = order['quantity']

                trade_value = quantity * price
                commission = max(self.min_commission, trade_value * self.commission_rate)

                executed_orders.append({
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'quantity': quantity,
                    'price': price,
                    'commission': commission,
                    'index': i
                })

        # Calculate equity curve
        equity_curve = [initial_capital]
        current_capital = initial_capital

        # Track positions for proper trade pairing
        open_positions = {}  # symbol -> {side, quantity, entry_price, entry_commission, entry_index}

        def equity_mtm(_precios):
            """EQUITY mark-to-market, para los PUNTOS INTERMEDIOS de la curva.

            MEDIDO el 2026-10-01: la curva guardaba `current_capital`, que es
            EFECTIVO. Al abrir una posicion se le descuenta el margen y no se
            acredita el valor de la posicion, luego con 100.000 de cuenta y
            86.000 de nocional la curva caia a ~10.000 y al cerrar volvia a
            ~94.000. En BTC 15m real alternaba

                10.164 -> 93.697 -> 9.713 -> 94.249

            que no es ninguna serie de equity. De ahi dos numeros falsos:

              * max_drawdown 90,3%: era el margen en custodia, no una perdida
              * sharpe_ratio +22,84 con la estrategia PERDIENDO 5.493 USDT:
                cada apertura y cierre metia y sacaba el nocional entero de
                la cuenta, y eso parecia rentabilidad

            Y el segundo no es cosmético: `sharpe_ratio` pesa 0,3 en el
            `scientific_score` (orchestrator.py:1497), y ese score decide si
            la hipotesis queda `backtested` o degrada a `failed`.

            LA FORMULA, y por que esa:

                equity = efectivo + margen + (precio - entrada) * cantidad

            El margen va porque el motor lo descuenta al abrir y lo devuelve
            al cerrar (`current_capital += margin + pnl`): esta EN CUSTODIA,
            no perdido. Sumar solo `(precio - entrada)` daria el doble de
            error, porque a la entrada esa diferencia es cero mientras la
            posicion vale su nocional entero.

            POR QUE SOLO LOS PUNTOS INTERMEDIOS. El ultimo punto de la curva
            NO usa esta funcion: sigue siendo el efectivo liquidado, y por
            eso `final_capital` reconcilia al centimo con la suma de los PnL
            cerrados, que es el contrato de
            `tests/test_backtester_equity.py`. Mark-to-market y liquidado son
            dos magnitudes distintas y cada metrica necesita la suya:

              * expectancy, ranking y gate  ->  liquidado (sin cambios aqui)
              * sharpe y max_drawdown       ->  mark-to-market (esta funcion)

            Un intento anterior aplico mark-to-market a TODO, incluido el
            punto final, y rompio tres tests: el capital final dejaba de
            cuadrar con los trades cerrados. Ese error es el queobliga a separar
            las dos curvas.
            """
            total = current_capital
            for _sym, pos in open_positions.items():
                _px = _precios.get(_sym)
                if _px is None:
                    _serie = data.get(_sym)
                    _px = (float(_serie[min(i, len(_serie) - 1)])
                           if _serie is not None else pos['entry_price'])
                _dir = 1 if pos['side'] == 'long' else -1
                total += (float(pos.get('margin', 0.0))
                          + _dir * (float(_px) - pos['entry_price'])
                          * pos['quantity'])
            return total


        for i, order in enumerate(orders):
            symbol = order['symbol']
            side = order['side']
            quantity = order['quantity']

            # Precio de mercado de CADA posicion viva, no solo de la que
            # toca en esta orden: el equity depende de todas a la vez.
            _precios = {}
            for _s in open_positions:
                _serie = data.get(_s)
                if _serie is not None and i < len(_serie):
                    _precios[_s] = float(_serie[i])


            if symbol not in data:
                equity_curve.append(equity_mtm(_precios))
                continue

            price = data[symbol][i]

            if side == 'buy' and quantity > 0:
                fill = self._adverse_fill(price, 'buy')
                margin = quantity * fill / self.leverage
                entry_fee = self._fee(quantity * fill)
                if current_capital >= margin + entry_fee:
                    current_capital -= (margin + entry_fee)
                    # Track open position
                    open_positions[symbol] = {
                        'side': 'long',
                        'quantity': quantity,
                        'entry_price': fill,
                        'margin': margin,
                        'entry_commission': entry_fee,
                        'entry_index': i
                    }
                equity_curve.append(equity_mtm(_precios))

            elif side == 'sell' and quantity > 0:
                fill = self._adverse_fill(price, 'sell')
                exit_fee = self._fee(quantity * fill)
                # Close position if exists (return margin + net PnL)
                if symbol in open_positions and open_positions[symbol]['side'] == 'long':
                    pos = open_positions[symbol]
                    margin = pos.get('margin', pos['quantity'] * pos['entry_price'])
                    bars_held = max(0, i - pos['entry_index'])
                    funding = self._funding_cost(pos['quantity'] * fill, bars_held)
                    total_funding_paid[0] += funding
                    liq = self._liq_price_long(pos['entry_price'])
                    liquidated = self._touched_liq(data[symbol], pos['entry_index'], i, liq)
                    if liquidated:
                        exit_px = liq if liq is not None else fill
                        exit_fee = self._fee(quantity * exit_px)
                        # Margin lost; only exit fee + funding leave the account
                        # (entry fee + margin were already deducted at entry)
                        current_capital -= (exit_fee + funding)
                        pnl = -margin - pos['entry_commission'] - exit_fee - funding
                        num_liquidations[0] += 1
                    else:
                        exit_px = fill
                        # Return margin + price PnL net of exit fee + funding
                        # (entry fee already deducted at entry)
                        current_capital += (margin + (fill - pos['entry_price'])
                                            * pos['quantity'] - exit_fee - funding)
                        pnl = ((fill - pos['entry_price']) * pos['quantity']
                               - pos['entry_commission'] - exit_fee - funding)
                    pnl_pct = pnl / margin * 100 if margin else 0.0
                    trade = Trade(
                        trade_id=f"TRD-{len(trades):06d}",
                        symbol=symbol,
                        side='buy',
                        quantity=pos['quantity'],
                        entry_price=pos['entry_price'],
                        exit_price=exit_px,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        hold_duration=float(bars_held),
                        entry_time=pos['entry_index'],
                        exit_time=i,
                        commission=pos['entry_commission'] + exit_fee,
                        liquidated=liquidated,
                        funding_paid=funding
                    )
                    trades.append(trade)
                    del open_positions[symbol]
                equity_curve.append(equity_mtm(_precios))

            else:  # hold
                equity_curve.append(equity_mtm(_precios))

        # Cerrar las posiciones vivas al precio de la ultima vela.
        # El PnL se suma al capital, no es solo registro: si el Trade
        # cuenta en n_trades y en win_rate, su PnL tiene que contar
        # tambien en final_capital. Si no, el retorno mide una
        # poblacion distinta de la que cuentan las metricas de trade.
        for symbol, pos in open_positions.items():
            fill = self._adverse_fill(data[symbol][-1], 'sell')
            commission = self._fee(pos['quantity'] * fill)
            margin = pos.get('margin', pos['quantity'] * pos['entry_price'])
            bars_held = max(0, len(orders) - 1 - pos['entry_index'])
            funding = self._funding_cost(pos['quantity'] * fill, bars_held)
            total_funding_paid[0] += funding
            liq = self._liq_price_long(pos['entry_price'])
            liquidated = self._touched_liq(data[symbol], pos['entry_index'],
                                           len(orders) - 1, liq)
            if liquidated:
                exit_px = liq if liq is not None else fill
                # El margen y la comision de entrada ya se descontaron
                # al abrir: de la cuenta solo salen salida y funding.
                current_capital -= (commission + funding)
                pnl = -margin - pos['entry_commission'] - commission - funding
                num_liquidations[0] += 1
            else:
                exit_px = fill
                # Se devuelve margen + PnL de precio - salida - funding
                # (la comision de entrada ya se desconto al abrir).
                current_capital += (margin + (fill - pos['entry_price'])
                                   * pos['quantity'] - commission - funding)
                pnl = ((fill - pos['entry_price']) * pos['quantity']
                       - pos['entry_commission'] - commission - funding)
            pnl_pct = pnl / margin * 100 if margin else 0.0
            trade = Trade(
                trade_id=f"TRD-{len(trades):06d}",
                symbol=symbol,
                side='buy',
                quantity=pos['quantity'],
                entry_price=pos['entry_price'],
                exit_price=exit_px,
                pnl=pnl,
                pnl_pct=pnl_pct,
                hold_duration=float(bars_held),
                entry_time=pos['entry_index'],
                exit_time=len(orders) - 1,
                commission=pos['entry_commission'] + commission,
                liquidated=liquidated,
                funding_paid=funding
            )
            trades.append(trade)

        # Punto final: LIQUIDADO, no mark-to-market. Y la diferencia es
        # deliberada.
        #
        # Los puntos intermedios usan `equity_mtm` (efectivo + margen en
        # custodia + no realizado) porque de ellos salen `sharpe_ratio` y
        # `max_drawdown`, que son magnitudes de RIESGO y necesitan el valor de
        # mercado en cada instante.
        #
        # Este ultimo punto NO usa mark-to-market, y es a proposito: de el
        # salen `final_capital` y `total_return_pct`, y esos tienen que
        # reconciliar con la suma de los PnL CERRADOS, que es el contrato de
        # `tests/test_backtester_equity.py`:
        #
        #     final_capital - initial == sum(pnl de los trades), al centimo
        #
        # Con mark-to-market aqui, una posicion que sigue abierta meteria su
        # no realizado y el capital final dejaria de cuadrar. Un intento
        # anterior aplico mark-to-market a toda la curva, incluido este punto,
        # y rompio tres tests por eso.
        #
        # O sea: mark-to-market para riesgo, liquidado para resultado. Son dos
        # preguntas distintas y por eso son dos curvas distintas.
        if open_positions:
            equity_curve.append(current_capital)

        # Calculate metrics
        final_capital = equity_curve[-1]
        total_return = PerformanceMetrics.total_return(initial_capital, final_capital)
        total_return_pct = PerformanceMetrics.total_return_pct(initial_capital, final_capital)

        # Create price series for metrics
        price_series = equity_curve

        returns = np.diff(price_series) / price_series[:-1] if len(price_series) > 1 else np.array([0.0])
        # MEDIDO el 2026-10-01: esto iba fijo en 252 velas al año, sin
        # mirar la temporalidad. Un backtest de 15m tiene 35.040 velas al
        # año, luego la volatilidad y el Sharpe salian calculados con un
        # 139x de error en el numerador y un 11,8x en el denominador.
        _ppa = PerformanceMetrics.periodos_por_anio(timeframe)
        annualized_vol = (np.std(returns) * np.sqrt(_ppa)
                          if len(returns) > 0 else 0.0)
        sharpe = PerformanceMetrics.sharpe_ratio(returns, periods_per_year=_ppa)
        sortino = PerformanceMetrics.sortino_ratio(returns)
        max_dd = PerformanceMetrics.max_drawdown(price_series)

        # Trade metrics
        win_rate = PerformanceMetrics.win_rate(trades)
        avg_win = np.mean([t.pnl for t in trades if t.pnl > 0]) if any(t.pnl > 0 for t in trades) else 0.0
        avg_loss = np.mean([t.pnl for t in trades if t.pnl < 0]) if any(t.pnl < 0 for t in trades) else 0.0
        pf = PerformanceMetrics.profit_factor(trades)

        result = BacktestResult(
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            annualized_volatility=annualized_vol,
            num_trades=len(trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=pf,
            trades=trades,
            equity_curve=list(zip(range(len(equity_curve)), equity_curve)),
            num_liquidations=num_liquidations[0],
            total_funding_paid=total_funding_paid[0]
        )

        return result

    def print_summary(self, result: BacktestResult):
        """Print backtest summary."""
        print("\n" + "="*70)
        print("BACKTEST SUMMARY")
        print("="*70)

        print(f"\nCapital:")
        print(f"  Initial: ${result.initial_capital:,.2f}")
        print(f"  Final: ${result.final_capital:,.2f}")
        print(f"  Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.2f}%)")

        print(f"\nPerformance Metrics:")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.4f}")
        print(f"  Sortino Ratio: {result.sortino_ratio:.4f}")
        print(f"  Max Drawdown: {result.max_drawdown:.2f}%")
        print(f"  Annualized Volatility: {result.annualized_volatility:.2f}%")

        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {result.num_trades}")
        print(f"  Win Rate: {result.win_rate:.2f}%")
        print(f"  Average Win: ${result.avg_win:.2f}")
        print(f"  Average Loss: ${result.avg_loss:.2f}")
        print(f"  Profit Factor: {result.profit_factor:.2f}")

        print("\n" + "="*70 + "\n")
