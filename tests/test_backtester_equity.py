"""Contabilidad del backtester: el capital final tiene que cubrir exactamente
los trades que las demas metricas cuentan.

Bug (F3, 2026-09-29): el bloque que cierra las posiciones vivas al final del
backtest registraba el Trade pero NO movia el capital, mientras el margen
seguia descontado de la cuenta. O sea: los trades abiertos al final contaban
en n_trades, en win_rate y en profit_factor, pero su PnL no contaba en
final_capital. El retorno media una poblacion distinta de la que mide el resto
de metricas, y salia destruido: ema_crossover pasaba de +1,3526% (480 velas) a
-40,3567% (300 velas) con la misma estrategia y el mismo capital.

Por que importa mas alla del numero: quant_math/orchestrator.py calcula
expectancy = total_return_pct / n_trades, y esa metrica es la que ordena la
puerta de entrada. Con el bug, la puerta se ordenaba por el margen de una
posicion que nadie cerro, no por el resultado de los trades.

Invariante que queda como contrato contable:

    final_capital - initial_capital == sum(t.pnl for t in trades)

Se cumple con el bloque de cierre final moviendo el capital, y es lo que
verifican estos tests.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtesting.backtester import Backtester


CAP = 10_000.0
TOL = 1e-6


def _spot(**kw):
    """Backtester sin comisiones, sin slippage y a apalancamiento 1.

    Asi la aritmetica es cerrada y el PnL esperado se puede comprobar a mano:
    comprar qty a P y cerrar a Q da exactamente qty * (Q - P).
    """
    params = dict(initial_capital=CAP, commission_rate=0.0,
                  min_commission=0.0, slippage_pct=0.0, leverage=1.0)
    params.update(kw)
    return Backtester(**params)


def _plan_strategy(plan, n):
    """plan: dict simbolo -> {indice_vela: (side, qty)}; el resto son holds."""
    def strategy(_data):
        orders = []
        for i in range(n):
            for sym, sched in plan.items():
                if i in sched:
                    side, qty = sched[i]
                    orders.append({"symbol": sym, "side": side,
                                   "quantity": qty})
                    break
            else:
                orders.append({"symbol": next(iter(plan)), "side": "hold",
                               "quantity": 0})
        return orders
    return strategy


def _reconciles(res, initial=CAP):
    """El contrato contable: el capital movido ES la suma del PnL de los trades."""
    moved = res.final_capital - initial
    booked = sum(t.pnl for t in res.trades)
    assert res.num_trades == len(res.trades)
    assert abs(moved - booked) < TOL, (
        "el capital se movio %.6f pero los trades suman %.6f "
        "(poblaciones distintas: %d trades)"
        % (moved, booked, res.num_trades))


# --------------------------------------------------------------------------
# 1. Test de ENTRADA: una posicion abierta al final mueve el capital
# --------------------------------------------------------------------------
def test_open_position_pnl_counts_in_final_capital():
    """Bug: comprar y no vender nunca devolvia el margen y perdia el PnL."""
    prices = {"AAA": np.array([100.0, 102.0, 105.0, 110.0])}
    n = len(prices["AAA"])
    plan = {"AAA": {0: ("buy", 1.0)}}      # compra, nunca vende

    res = _spot().run_backtest(_plan_strategy(plan, n), prices)

    assert res.num_trades == 1, "el trade final debe registrarse"
    assert res.trades[0].exit_price == pytest.approx(110.0)
    assert res.trades[0].pnl == pytest.approx(10.0)
    # 10.000 + 1 unidad * (110 - 100)
    assert res.final_capital == pytest.approx(CAP + 10.0)
    assert res.total_return_pct == pytest.approx(0.1)   # +10%, no -100%
    _reconciles(res)


# --------------------------------------------------------------------------
# 2. Coherencia del retorno con la poblacion de trades
# --------------------------------------------------------------------------
def test_return_population_matches_trade_population():
    """Varias operaciones cerradas y una viva: el retorno no puede ignorar la viva."""
    rng = np.random.RandomState(7)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0006, 0.012, 240)))
    prices = {"AAA": closes}
    n = len(closes)

    # Round-trips en las velas 5, 20, 60, 120; la ultima queda abierta.
    plan = {"AAA": {5: ("buy", 1.0), 20: ("sell", 1.0),
                    60: ("buy", 1.0), 120: ("sell", 1.0),
                    180: ("buy", 1.0)}}
    res = _spot().run_backtest(_plan_strategy(plan, n), prices)

    assert res.num_trades == 3   # 2 cerradas + 1 viva al final
    _reconciles(res)
    # signo del retorno = signo del PnL realizado
    if sum(t.pnl for t in res.trades) > 0:
        assert res.total_return > 0
    else:
        assert res.total_return < 0


# --------------------------------------------------------------------------
# 3. Multi-simbolo: el PnL pendiente se suma UNA vez por posicion
# --------------------------------------------------------------------------
def test_multi_symbol_pending_pnl_counted_once():
    """Dos simbolos vivos al final: ni se ignoran ni se duplican."""
    prices = {
        "AAA": np.array([100.0, 101.0, 102.0, 103.0]),
        "BBB": np.array([50.0, 51.0, 52.0, 53.0]),
    }
    n = 4
    # AAA entra en la vela 0; BBB en la vela 1. Ninguna cierra.
    plan = {"AAA": {0: ("buy", 1.0)}, "BBB": {1: ("buy", 1.0)}}

    def strategy(_data):
        sides = [("AAA", "buy", 1.0), ("BBB", "buy", 1.0),
                 ("AAA", "hold", 0), ("AAA", "hold", 0)]
        return [{"symbol": s, "side": sd, "quantity": q} for s, sd, q in sides]

    res = _spot().run_backtest(strategy, prices)

    assert res.num_trades == 2
    assert {t.symbol for t in res.trades} == {"AAA", "BBB"}
    by_sym = {t.symbol: t.pnl for t in res.trades}
    assert by_sym["AAA"] == pytest.approx(103.0 - 100.0)   # +3
    assert by_sym["BBB"] == pytest.approx(53.0 - 51.0)     # +2
    # 10.000 + 3 + 2 = 10.005. Sumado dos veces serian 10.010.
    assert res.final_capital == pytest.approx(CAP + 5.0)
    _reconciles(res)


# --------------------------------------------------------------------------
# 4. La curva de equity termina en el capital final
# --------------------------------------------------------------------------
def test_equity_curve_ends_at_final_capital():
    """El punto extra de la curva es el que fija final_capital (= ultimo)."""
    prices = {"AAA": np.array([100.0, 101.0, 102.0, 110.0])}
    n = 4
    plan = {"AAA": {0: ("buy", 1.0)}}
    res = _spot().run_backtest(_plan_strategy(plan, n), prices)

    assert res.equity_curve[-1][1] == pytest.approx(res.final_capital)
    # una vela por punto, mas el inicial, mas el punto de liquidacion final
    assert len(res.equity_curve) == n + 2
    assert res.equity_curve[0][1] == pytest.approx(CAP)


def test_no_open_position_leaves_curve_untouched():
    """Sin posiciones vivas no se anade punto: las metricas de riesgo no cambian."""
    prices = {"AAA": np.array([100.0, 101.0, 102.0, 103.0])}
    n = 4
    plan = {"AAA": {0: ("buy", 1.0), 1: ("sell", 1.0)}}
    res = _spot().run_backtest(_plan_strategy(plan, n), prices)

    assert res.num_trades == 1
    assert len(res.equity_curve) == n + 1
    _reconciles(res)


# --------------------------------------------------------------------------
# 5. Apalancamiento, funding y liquidacion: mismo contrato
# --------------------------------------------------------------------------
def test_reconciles_with_leverage_and_funding():
    """Con apalancamiento y funding el PnL sigue siendo la variacion del capital."""
    rng = np.random.RandomState(11)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, 300)))
    prices = {"AAA": closes}
    n = len(closes)
    plan = {"AAA": {10: ("buy", 1.0), 50: ("sell", 1.0),
                    100: ("buy", 1.0), 140: ("sell", 1.0),
                    200: ("buy", 1.0)}}
    bt = Backtester(initial_capital=CAP, commission_rate=0.0006,
                    leverage=3.0, funding_rate_8h=0.0001, timeframe="1h")
    res = bt.run_backtest(_plan_strategy(plan, n), prices)
    assert res.num_trades == 3   # 2 cerradas + 1 viva al final
    _reconciles(res)


def test_liquidation_on_final_bar_is_charged_to_capital():
    """Liquidacion en la ultima vela: el margen perdido sale de la cuenta."""
    prices = {"AAA": np.array([100.0, 100.0, 99.0, 20.0])}
    n = 4
    plan = {"AAA": {0: ("buy", 1.0)}}       # nunca cierra antes del crash
    bt = Backtester(initial_capital=CAP, commission_rate=0.001,
                    leverage=2.0, funding_rate_8h=0.0001, timeframe="1h")
    res = bt.run_backtest(_plan_strategy(plan, n), prices)

    assert res.num_trades == 1
    assert res.trades[0].liquidated is True
    assert res.num_liquidations == 1
    _reconciles(res)
    # la liquidacion no puede "crear" capital
    assert res.final_capital < CAP


# --------------------------------------------------------------------------
# 6. La prueba de sensibilidad que destapo el bug
# --------------------------------------------------------------------------
def test_truncated_series_keeps_return_coherent():
    """Misma estrategia, serie recortada: el retorno no puede hundirse.

    Con el bug, la serie recortada acababa con posicion viva y reportaba
    -40% havingiendo la version larga +1,35%.
    """
    rng = np.random.RandomState(3)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.010, 400)))

    def run(sub):
        prices = {"AAA": sub}
        n = len(sub)
        # alterna cada 25 velas y deja la ultima compra abierta
        plan = {"AAA": {i: ("buy" if i % 50 == 0 else "sell", 1.0)
                        for i in range(0, n - 25, 25)}}
        return _spot().run_backtest(_plan_strategy(plan, n), prices)

    full = run(closes)
    cut = run(closes[:300])

    _reconciles(full)
    _reconciles(cut)
    # ninguna de las dos versiones puede hundirse por una posicion sin cerrar
    assert full.total_return_pct > -5.0, full.total_return_pct
    assert cut.total_return_pct > -5.0, cut.total_return_pct
    # y el signo del retorno tiene que ser el del PnL de los trades
    assert np.sign(full.total_return) == np.sign(
        sum(t.pnl for t in full.trades))
    assert np.sign(cut.total_return) == np.sign(
        sum(t.pnl for t in cut.trades))


# --------------------------------------------------------------------------
# 7. El signo que consume la puerta de entrada
# --------------------------------------------------------------------------
def test_expectancy_sign_follows_trade_pnl():
    """orchestrator: expectancy = total_return_pct / n_trades.

    Con el bug, una estrategia con 1 trade, 100% de aciertos y +1.868 USD
    reportaba -40,4840% y por tanto expectancy negativa. La metrica que
    ordena la puerta tiene que tener el signo de los trades.
    """
    prices = {"AAA": np.array([100.0, 130.0, 160.0, 190.0])}
    n = 4
    plan = {"AAA": {0: ("buy", 10.0)}}      # 1 trade ganador, sigue abierto
    res = _spot().run_backtest(_plan_strategy(plan, n), prices)

    assert res.num_trades == 1
    assert res.win_rate == pytest.approx(100.0)
    assert res.trades[0].pnl > 0
    expectancy = res.total_return_pct / res.num_trades
    assert expectancy > 0, (
        "expectancy %.4f con win_rate 100%% y pnl %.2f" % (expectancy,
                                                            res.trades[0].pnl))


if __name__ == "__main__":
    for fn in (test_open_position_pnl_counts_in_final_capital,
               test_return_population_matches_trade_population,
               test_multi_symbol_pending_pnl_counted_once,
               test_equity_curve_ends_at_final_capital,
               test_no_open_position_leaves_curve_untouched,
               test_reconciles_with_leverage_and_funding,
               test_liquidation_on_final_bar_is_charged_to_capital,
               test_truncated_series_keeps_return_coherent,
               test_expectancy_sign_follows_trade_pnl):
        fn()
        print("PASS", fn.__name__)
    print("\n9/9 tests de contabilidad del backtester")
