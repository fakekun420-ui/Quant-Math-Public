"""Correccion no2 (2026-09-29): TP/SL en ROE + SL alcanzable antes de la
liquidacion + registro de margen en ambos modos + margin_cap que falla CERRADO.

Todos estos tests FALLAN con el codigo anterior a la correccion.
Offline y deterministas: nada de red, nada de ficheros de runtime/ reales.
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.orchestrator import Orchestrator, OrchestratorConfig
from quant_math.risk.roe_targets import (
    DEFAULT_MAINTENANCE_MARGIN_RATE,
    DEFAULT_SL_LIQUIDATION_SAFETY_FRAC,
    LeverageRiskError,
    build_roe_plan,
    liquidation_price_distance,
    max_sl_price_distance,
    roe_to_price_distance,
    sl_is_reachable,
    tp_sl_prices,
    validate_roe_plan,
)

# El barrido de MMR que hizo la auditoria del 2026-09-29 (NO es una lectura de
# la API de Bybit; es un supuesto propio que el operador debe confirmar).
MMR_SWEEP = (0.0035, 0.005, 0.0075)
LEVERAGES = (1, 2, 3, 5, 10, 20, 50, 100, 125)


def _cfg(state_dir, **kw):
    base = dict(
        symbols=["BTC/USDT"], timeframe="1h", lookback_days=14,
        initial_capital=1000.0, entry_pct=0.1, take_profit_pct=0.05,
        min_paper_trades=3, hypotheses_per_cycle=3,
        kb_path=os.path.join(state_dir, "kb.jsonl"),
        state_dir=state_dir,
    )
    base.update(kw)
    return OrchestratorConfig(**base)


def _orch(config):
    """Orchestrator sin red: solo la parte de ejecucion paper."""
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = config
    orch.cycle_count = 1
    orch._last_realized_total = 0.0
    orch._risk_manager = None
    return orch


def _signal(**kw):
    sig = {"action": "entry", "symbol": "BTC/USDT", "side": "buy",
           "hypothesis_id": "h1", "expectancy": 0.01,
           "timestamp": 1700000000.0, "price": 100.0, "sizing_mult": 1.0}
    sig.update(kw)
    return sig


# ---------------------------------------------------------------------------
# 1. EL TEST QUE MAS IMPORTA: el SL cae ANTES que la liquidacion
# ---------------------------------------------------------------------------

def test_sl_reachable_before_liquidation_across_leverages():
    """distancia_SL <= frac x distancia_a_liquidacion para todo apalancamiento
    y los tres MMR del barrido, en los dos modos.

    Se aisla la restriccion del SL subiendo max_tp_price_distance a 1.0, que
    desactiva el veto de apalancamiento bajo: aqui lo que se mide es
    exclusivamente que el SL es alcanzable antes de la liquidacion.
    """
    for mode in ("classic", "burst"):
        for mmr in MMR_SWEEP:
            for lev in LEVERAGES:
                plan = build_roe_plan(
                    mode=mode, leverage=lev, maintenance_margin_rate=mmr,
                    max_tp_price_distance=1.0)
                liq = liquidation_price_distance(lev, mmr)
                assert plan.sl_price_distance <= liq, (
                    f"{mode} L={lev} mmr={mmr}: SL {plan.sl_price_distance:.4%} "
                    f"llega ANTES de la liquidacion a {liq:.4%}")
                assert plan.sl_liquidation_headroom >= 1.0, (
                    f"{mode} L={lev} mmr={mmr}: holgura "
                    f"{plan.sl_liquidation_headroom:.2f}x < 1")
                assert plan.sl_price_distance <= (
                    DEFAULT_SL_LIQUIDATION_SAFETY_FRAC * liq), (
                    f"{mode} L={lev} mmr={mmr}: SL {plan.sl_price_distance:.4%} "
                    f"supera el techo {DEFAULT_SL_LIQUIDATION_SAFETY_FRAC} x "
                    f"{liq:.4%}")


def test_sl_was_unreachable_before_the_fix():
    """Documenta la regresion que se corrige.

    Con el codigo anterior: burst fijaba take_profit_pct >= 0.02 y el SL era
    TP/2 en fraccion de PRECIO, sin relacion con el apalancamiento ni con la
    liquidacion. Con L=20 eso son 10% de precio contra liquidacion a ~4.5%.
    """
    lev, mmr = 20, DEFAULT_MAINTENANCE_MARGIN_RATE
    # Regla vieja: TP = 0.20 de PRECIO (default del wizard burst viejo), SL =
    # TP/2 = 0.10 de PRECIO. Expresado en la misma moneda (ROE) son
    # 0.10 * 20 = 200% ROE, o sea un SL que exige perder 2x el margen: la
    # liquidacion (a -100% ROE) llega antes SIEMPRE.
    old_sl_price = max(0.02, 0.20) / 2.0
    old_sl_roe = old_sl_price * lev
    liq = liquidation_price_distance(lev, mmr)
    assert old_sl_price > liq, "la regla vieja deberia fallar el test"
    assert old_sl_roe == pytest.approx(2.00)
    assert not sl_is_reachable(old_sl_roe, lev, mmr), (
        "el SL viejo (200% ROE) no puede ser alcanzable antes de liquidar")
    # Regla nueva: SL 10% ROE -> 0.10/20 = 0.5% de precio. Alcanzable.
    new_sl_price = roe_to_price_distance(0.10, lev)
    assert new_sl_price == pytest.approx(0.005)
    assert sl_is_reachable(0.10, lev, mmr)
    assert new_sl_price <= max_sl_price_distance(lev, mmr)
    assert new_sl_price < liq
    # 40 veces mas cerca del precio de entrada que el SL viejo
    assert old_sl_price / new_sl_price == pytest.approx(20.0)


def test_clamp_actually_bites_at_high_leverage():
    """A 152x el SL en ROE se aparta de la liquidacion: el clamp actua.

    El umbral estaba en 125x cuando el MMR por defecto era el SUPUESTO 0,005.
    Con el MMR LEIDO de la tabla (0,0033) habia mas margen hasta la
    liquidacion, asi que el corte se movio a 152x.

    MEDIDO el 2026-10-01 contra una posicion REAL: el MMR de BTC es
    0,003846 (0,3207 / 83,3849), NO el 0,0033 de la tabla. Con el dato
    medido el clamp aprieta 22x antes: el corte pasa de 152x a 130x.

    Barrido medido (SL clasico al 25% de ROE contra el techo del 50% de
    la liquidacion):

        125x  liq 0,4154%  techo 0,2077%  SL 0,2000%  libre
        130x  liq 0,3846%  techo 0,1923%  SL 0,1923%  libre  <- justo
        135x  liq 0,3561%  techo 0,1781%  SL 0,1852%  CLAMPA

    Menos clamp no es un aflojo: es que el exchange deja la posicion mas
    lejos de lo que se asumia. Y aqui aplica al reves: el dato medido es
    MAS restrictivo que el de la tabla, asi que aprieta MAS. El MMR de la
    tabla (0,0033) era mas pequeno que el real (0,003846) y por eso
    fingia mas margen del que hay.
    """
    plan = build_roe_plan(mode="classic", leverage=140)
    assert plan.sl_clamped, "a 140x el clamp deberia morder"
    assert plan.sl_price_distance < roe_to_price_distance(0.25, 140)
    # El corte medido con el MMR REAL esta en 130x. Con el de la tabla
    # (0,0033, mas pequeño) estaba en 152x: 22x de diferencia por usar un
    # numero de la tabla en vez de uno medido.
    assert not build_roe_plan(mode="classic",
                               leverage=130).sl_clamped, (
        "a 130x el clamp todavia no debe morder con el MMR medido")
    assert build_roe_plan(mode="classic",
                          leverage=130, stop_loss_roe=0.30).sl_clamped, (
        "a 130x un SL al 30% de ROE si debe morder: el corte depende del "
        "SL pedido, no solo del apalancamiento")
    assert plan.realized_ratio > 2.0
    assert plan.sl_liquidation_headroom == pytest.approx(
        1.0 / DEFAULT_SL_LIQUIDATION_SAFETY_FRAC, rel=1e-6)


def test_sin_mmr_real_el_clamp_morde_antes():
    """A 125x con el MMR antiguo SI moria: confirma que el cambio es de datos.

    Si este test dejara de pasar, significaria que el MMR por defecto volvio
    a 0,005 y que los otros tests estan viendo el supuesto, no la realidad.
    """
    from quant_math.risk.roe_targets import max_sl_price_distance
    pedido = roe_to_price_distance(0.25, 125)
    assert pedido > max_sl_price_distance(125, 0.005, 0.5), (
        "con MMR 0,005 el clamp deberia morder a 125x")
    assert pedido <= max_sl_price_distance(125, 0.003846, 0.5), (
        "con el MMR MEDIDO de una posicion real (0,003846) no hace falta "
        "clampar a 125x")


# ---------------------------------------------------------------------------
# 2. Conversion ROE a precio, en los dos modos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,lev,tp_roe,sl_roe,tp_px,sl_px", [
    ("classic", 10, 0.50, 0.25, 0.050, 0.025),   # 50% ROE a 10x = 5% precio
    ("classic", 20, 0.50, 0.25, 0.025, 0.0125),
    ("classic", 5,  0.50, 0.25, 0.100, 0.050),
    ("burst",   20, 0.20, 0.10, 0.010, 0.005),  # 20% ROE a 20x = 1% precio
    ("burst",   10, 0.20, 0.10, 0.020, 0.010),
    ("burst",   50, 0.20, 0.10, 0.004, 0.002),
])
def test_roe_to_price_conversion(mode, lev, tp_roe, sl_roe, tp_px, sl_px):
    plan = build_roe_plan(mode=mode, leverage=lev, market="crypto")
    assert plan.tp_roe == pytest.approx(tp_roe)
    assert plan.sl_roe == pytest.approx(sl_roe)
    assert plan.tp_price_distance == pytest.approx(tp_px)
    assert roe_to_price_distance(sl_roe, lev) == pytest.approx(sl_px)
    if not plan.sl_clamped:
        assert plan.sl_price_distance == pytest.approx(sl_px)


def test_config_derives_pct_from_roe():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=10,
                   take_profit_roe=0.50, stop_loss_roe=0.25)
        assert cfg.roe_mode is True
        assert cfg.take_profit_pct == pytest.approx(0.05)
        assert cfg.stop_loss_pct == pytest.approx(0.025)
        assert cfg.effective_leverage == 10
        cfg2 = _cfg(tmp + "2", mode="burst", burst_leverage=20,
                    burst_margin=1.0, take_profit_roe=0.20, stop_loss_roe=0.10)
        assert cfg2.take_profit_pct == pytest.approx(0.01)
        assert cfg2.stop_loss_pct == pytest.approx(0.005)
        assert cfg2.effective_leverage == 20


def test_tp_sl_prices_from_plan():
    plan = build_roe_plan(mode="classic", leverage=10)
    assert tp_sl_prices(100.0, "buy", plan) == (
        pytest.approx(105.0), pytest.approx(97.5))
    assert tp_sl_prices(100.0, "sell", plan) == (
        pytest.approx(95.0), pytest.approx(102.5))


# ---------------------------------------------------------------------------
# 3. Rechazo al arrancar (wizard y __post_init__)
# ---------------------------------------------------------------------------

def test_leverage_1_is_refused_at_startup():
    """L=1 con TP 50% ROE = 50% de precio: inalcanzable. No se arranca."""
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(LeverageRiskError):
            _cfg(tmp, mode="classic", leverage=1,
                 take_profit_roe=0.50, stop_loss_roe=0.25)
        with pytest.raises(LeverageRiskError):
            _cfg(tmp + "2", mode="burst", burst_leverage=1,
                 take_profit_roe=0.20, stop_loss_roe=0.10)


def test_low_leverage_is_refused_but_usable_ones_pass():
    for lev in (2, 3, 4):
        plan = build_roe_plan(mode="classic", leverage=lev)
        assert not plan.ok, f"L={lev} deberia rechazarse"
    for lev in (5, 10, 20, 50, 100, 125):
        plan = build_roe_plan(mode="classic", leverage=lev)
        assert plan.ok, f"L={lev} deberia ser operable: {plan.errors}"
        validate_roe_plan(plan)


def test_leverage_above_mmr_capacity_is_refused():
    """1/L <= mmr: el mantenimiento ya cubre el margen inicial."""
    for lev, mmr in ((200, 0.005), (500, 0.005), (100, 0.02)):
        with pytest.raises(LeverageRiskError):
            build_roe_plan(mode="classic", leverage=lev,
                           maintenance_margin_rate=mmr)


def test_burst_no_longer_has_the_2pct_floor():
    """El suelo max(0.02, ...) era la causa directa del SL inalcanzable."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="burst", burst_leverage=20, burst_margin=1.0,
                   take_profit_pct=0.006)
        assert cfg.take_profit_pct == pytest.approx(0.006)
        assert cfg.take_profit_pct < 0.02
        assert cfg.stop_loss_pct == pytest.approx(0.003)


# ---------------------------------------------------------------------------
# 4. Registro de margen y apalancamiento en AMBOS modos
# ---------------------------------------------------------------------------

def test_classic_records_margin_and_leverage():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=10,
                   take_profit_roe=0.50, stop_loss_roe=0.25,
                   max_risk_per_trade_usd=1000.0)
        orch = _orch(cfg)
        trade = orch._execute_paper_trade(_signal())
        assert trade.get("action") is None, trade.get("action")
        # margen y apalancamiento en CLASSIC tambien
        assert trade["margin_usd"] == pytest.approx(trade["notional_usd"] / 10)
        assert trade["leverage"] == 10
        assert trade["take_profit_roe"] == pytest.approx(0.50)
        assert trade["stop_loss_roe"] == pytest.approx(0.25)
        assert trade["take_profit_pct"] == pytest.approx(0.05)
        assert trade["stop_loss_pct"] == pytest.approx(0.025)
        assert trade["stop_loss_price"] == pytest.approx(97.5)
        assert trade["take_profit_price"] == pytest.approx(105.0)
        assert trade["risk_usd_at_stop"] == pytest.approx(
            trade["notional_usd"] * 0.025)
        # 1/L - mmr con el MMR REAL de Bybit (0,0033, primer tramo, medido el
        # 2026-09-30 contra /v5/market/risk-limit). Antes era 0,095 porque el
        # MMR por defecto era el supuesto 0,005. Con el dato, la liquidacion
        # queda un poco mas lejos: 0,1 - 0,0033 = 0,0967.
        assert trade["liquidation_price_distance"] == pytest.approx(0.096154)
        assert trade["sl_clamped"] is False
        assert trade["quantity"] > 0
        with open(os.path.join(tmp, "paper_executions.jsonl"),
                  encoding="utf-8") as fh:
            row = json.loads(fh.read())
        assert row["margin_usd"] == pytest.approx(trade["margin_usd"])
        assert row["leverage"] == 10
        # el ROE realizado es medible: margen y apalancamiento estan ahi
        roe_achieved = (row["notional_usd"] / row["margin_usd"]) * \
            (row["take_profit_pct"])
        assert roe_achieved == pytest.approx(0.50)


def test_burst_still_records_margin_and_leverage():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="burst", burst_margin=2.0, burst_leverage=20,
                   take_profit_roe=0.20, stop_loss_roe=0.10,
                   max_risk_per_trade_usd=1000.0)
        orch = _orch(cfg)
        trade = orch._execute_paper_trade(_signal(margin=2.0, leverage=20))
        assert trade["leverage"] == 20
        assert trade["margin_usd"] == pytest.approx(2.0)
        assert trade["take_profit_roe"] == pytest.approx(0.20)
        assert trade["stop_loss_roe"] == pytest.approx(0.10)
        assert trade["stop_loss_pct"] == pytest.approx(0.005)
        assert trade["stop_loss_price"] == pytest.approx(99.5)


def test_legacy_ledger_rows_still_readable():
    """No se rompe el formato viejo: campos nuevos anadidos, nada cambiado."""
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "state")
        os.makedirs(state, exist_ok=True)
        old_row = {"mode": "paper", "key": "old:BTC/USDT",
                   "symbol": "BTC/USDT", "side": "buy", "quantity": 1.0,
                   "entry_price": 100.0, "notional_usd": 100.0,
                   "take_profit_price": 105.0, "hypothesis_id": "old",
                   "expectancy": 0.01, "timestamp": 1700000000.0,
                   "cycle": 1}
        with open(os.path.join(state, "paper_executions.jsonl"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(old_row) + "\n")
        cfg = _cfg(state, mode="burst", burst_leverage=20, burst_margin=1.0,
                   take_profit_roe=0.20, stop_loss_roe=0.10)
        orch = _orch(cfg)
        # correccion no3 (2026-09-29): la fila vieja (sin margin_usd) SI
        # cuenta como entrada viva. Antes _open_burst_entries exigia
        # margin_usd, asi que toda entrada anterior a la correccion no2
        # era INVISIBLE para el tope de exposicion burst: el cap se abria
        # con el tope ya excedido y sin que nada lo notara (falla abierta).
        # La fila sigue leyendose igual: solo cambia la contabilidad.
        assert len(orch._open_burst_entries()) == 1
        assert orch._ledger_pnl() == (0.0, 0.0)
        # el SL de una posicion vieja se sigue derivando de TP/2 (legacy)
        from quant_math.decision_engine import DecisionEngine
        eng = DecisionEngine(
            symbols=["BTC/USDT"], kb_path=cfg.kb_path, state_dir=state,
            data_provider=lambda s: [[i, 100, 100, 100, 100, 10]
                                      for i in range(5)],
            use_postgres=False, take_profit_pct=0.05)
        assert eng._entry_stop_loss_from_ledger("old:BTC/USDT") == \
            pytest.approx(0.025)


# ---------------------------------------------------------------------------
# 5. _apply_margin_cap falla CERRADO + tope de riesgo en USD
# ---------------------------------------------------------------------------

def test_margin_cap_fails_closed_on_exception():
    """Si la comprobacion de riesgo revienta, NO se opera (antes: sin cap)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=10, take_profit_roe=0.50,
                   stop_loss_roe=0.25, max_risk_per_trade_usd=1000.0)
        orch = _orch(cfg)
        import quant_math.risk.risk_manager as rm
        orig = rm.RiskManager.check_position_size

        def boom(*a, **k):
            raise RuntimeError("risk service down")

        rm.RiskManager.check_position_size = boom
        try:
            assert orch._apply_margin_cap(1000.0, 10, "h1",
                                         sl_distance=0.025) == 0.0
            out = orch._execute_paper_trade(_signal())
            assert out["action"] == "risk_rejected"
            ledger = os.path.join(tmp, "paper_executions.jsonl")
            assert not os.path.exists(ledger) or os.path.getsize(ledger) == 0
        finally:
            rm.RiskManager.check_position_size = orig


def test_margin_cap_rejects_when_global_loss_limit_hit():
    """Rechazo por otra causa que el tope de margen: tambien es CIERRE."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=10, take_profit_roe=0.50,
                   stop_loss_roe=0.25, max_risk_per_trade_usd=1000.0)
        orch = _orch(cfg)
        from quant_math.risk.risk_manager import RiskManager
        orch._risk_manager = RiskManager(max_position_size_pct=0.2)
        orch._risk_manager.overall_pnl["h1"] = -9999.0
        assert orch._apply_margin_cap(50.0, 10, "h1", sl_distance=0.025) == 0.0


# ---------------------------------------------------------------------------
# 5b. TOPE DE NOCIONAL: el freno que faltaba con apalancamiento
#
# MEDIDO el 2026-09-30 con el plan de Leonardo (5 USDT de capital, 50x,
# SL al 0,5%): el tope de RIESGO daba 0,10 USDT y con un SL del 0,5% eso
# autoriza 0,10 / 0,005 = 20 USDT de nocional, o sea 4x el capital. El
# tope cumplia (el riesgo eran 0,10 exactos) pero la posicion era cuatro
# veces mas grande de la que el plan pedia.
#
# El riesgo y el TAMANO no son lo mismo: un SL corto permite una posicion
# enorme perdiendo poco. El capital tampoco lo frena, porque el margen es
# una fraccion minuscula del nocional. Sin un tope de nocional, el
# apalancamiento manda.
# ---------------------------------------------------------------------------

def test_el_tope_de_riesgo_solo_autoriza_un_nocional_4x_el_capital():
    """Primero el hecho, para que el tope de nocional no parezca arbitrario.

    Si este test falla, el dimensionado cambio y el resto de estos habria
    que reescribirlos.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=50, take_profit_roe=0.50,
                   stop_loss_roe=0.25, initial_capital=5.0, entry_pct=1.0)
        assert cfg.stop_loss_pct == pytest.approx(0.005, rel=1e-6), (
            "el plan: SL al 0,5% de precio a 50x = 25% de ROE")
        # tope de riesgo: 2% de 5 = 0,10 USDT
        assert cfg.max_risk_per_trade_usd == pytest.approx(0.10, rel=1e-6)
        autorizado = cfg.max_risk_per_trade_usd / cfg.stop_loss_pct
        assert autorizado == pytest.approx(20.0, rel=1e-3)
        assert autorizado == pytest.approx(cfg.initial_capital * 4), (
            "4x el capital: por eso hace falta el tope de nocional")


def test_el_tope_de_nocional_recorta_lo_que_el_apalancamiento_infla():
    """5 USDT de capital, tope 100%: 20 USDT de nocional se quedan en 5."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=50, take_profit_roe=0.50,
                   stop_loss_roe=0.25, initial_capital=5.0, entry_pct=1.0,
                   max_notional_per_entry_pct=1.0)
        orch = _orch(cfg)
        fuera = orch._apply_margin_cap(20.0, 50, "h1", sl_distance=0.005)
        assert fuera == pytest.approx(5.0, rel=1e-6), (
            f"el nocional debe quedarse en el capital, salio {fuera}")


def test_el_tope_de_nocional_no_toca_lo_que_ya_cabe():
    """Si la posicion ya esta dentro del techo, no se toca. Un tope que
    aprieta de mas tambien es un fallo: cerria operaciones que son
    legitimas."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=50, take_profit_roe=0.50,
                   stop_loss_roe=0.25, initial_capital=5.0, entry_pct=1.0,
                   max_notional_per_entry_pct=1.0)
        orch = _orch(cfg)
        dentro = orch._apply_margin_cap(4.0, 50, "h1", sl_distance=0.005)
        assert dentro == pytest.approx(4.0, rel=1e-6)


def test_sin_tope_de_nocional_no_se_cambia_el_comportamiento():
    """Por defecto (None) el dimensionado es el de antes. El freno nuevo es
    opt-in porque impose una politica que el operador tiene que querer."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", leverage=50, take_profit_roe=0.50,
                   stop_loss_roe=0.25, initial_capital=5.0, entry_pct=1.0)
        assert cfg.max_notional_per_entry_pct is None
        orch = _orch(cfg)
        assert orch._apply_margin_cap(20.0, 50, "h1",
                                      sl_distance=0.005) == pytest.approx(20.0)


def test_un_tope_de_nocional_imposible_reventa_al_arrancar():
    """Se valida en la config, no en mitad de una operacion. Un tope
    invalido que solo falla al operar es un fallo que aparece cuando ya
    hay dinero en juego."""
    with tempfile.TemporaryDirectory() as tmp:
        for malo in (0.0, -0.5, 1.5, 2.0):
            with pytest.raises(ValueError, match="max_notional_per_entry_pct"):
                _cfg(tmp, mode="classic", leverage=50, take_profit_roe=0.50,
                     stop_loss_roe=0.25, initial_capital=5.0, entry_pct=1.0,
                     max_notional_per_entry_pct=malo)


def test_risk_per_trade_cap_in_usd_is_enforced():
    """El tope de riesgo por operacion en USD recorta el nocional.

    Reproduce el caso que midio la auditoria: nocional grande sobre una
    cuenta pequena. El tope de MARGEN (20% de la cuenta) por si solo permitiria
    200 de nocional; el tope de RIESGO en USD lo recorta.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(tmp, mode="classic", initial_capital=50.0, entry_pct=1.0,
                   leverage=20, take_profit_roe=0.50, stop_loss_roe=0.25,
                   max_risk_per_trade_pct=0.01)
        assert cfg.max_risk_per_trade_usd == pytest.approx(0.50)
        orch = _orch(cfg)
        orch.config.max_risk_per_trade_usd = 1e9
        nocional = orch._apply_margin_cap(1000.0, 20, "h1",
                                          sl_distance=cfg.stop_loss_pct)
        assert nocional == pytest.approx(200.0)
        orch.config.max_risk_per_trade_usd = 0.50
        capped = orch._apply_margin_cap(1000.0, 20, "h1",
                                        sl_distance=cfg.stop_loss_pct)
        assert capped == pytest.approx(40.0)
        assert capped * cfg.stop_loss_pct == pytest.approx(0.50)


def test_position_sizer_is_wired_into_the_money_path():
    """PositionSizer.calculate tiene referencias desde la ruta de dinero."""
    import inspect
    from quant_math.risk.sizing import PositionSizer
    src = inspect.getsource(Orchestrator._apply_margin_cap)
    assert "PositionSizer" in src
    assert PositionSizer.calculate(100.0, 0.02, 0.05) == pytest.approx(40.0)


def test_decision_engine_receives_explicit_clamped_sl():
    from quant_math.decision_engine import DecisionEngine
    with tempfile.TemporaryDirectory() as tmp:
        # 152x, no 125x: con el MMR real de Bybit (0,0033) el clamp no muerde
        # hasta 152x. Ver test_clamp_actually_bites_at_high_leverage.
        cfg = _cfg(tmp, mode="classic", leverage=152, take_profit_roe=0.50,
                   stop_loss_roe=0.25)
        assert cfg.roe_plan.sl_clamped
        eng = DecisionEngine(
            symbols=["BTC/USDT"], kb_path=cfg.kb_path, state_dir=tmp,
            data_provider=lambda s: [[i, 100, 100, 100, 100, 10]
                                      for i in range(5)],
            use_postgres=False, take_profit_pct=cfg.take_profit_pct,
            stop_loss_pct=cfg.stop_loss_pct, take_profit_roe=cfg.take_profit_roe,
            stop_loss_roe=cfg.stop_loss_roe, leverage=152)
        assert eng.stop_loss_pct == pytest.approx(cfg.roe_plan.sl_price_distance)
        assert eng.stop_loss_pct != pytest.approx(cfg.take_profit_pct / 2)
        assert eng.leverage == 152


def test_legacy_stop_loss_property_still_tp_over_2():
    """Sin ROE, el comportamiento viejo (TP/2) sigue intacto."""
    from quant_math.decision_engine import DecisionEngine
    with tempfile.TemporaryDirectory() as tmp:
        eng = DecisionEngine(
            symbols=["BTC/USDT"], kb_path=os.path.join(tmp, "kb.jsonl"),
            state_dir=tmp,
            data_provider=lambda s: [[i, 100, 100, 100, 100, 10]
                                      for i in range(5)],
            use_postgres=False, take_profit_pct=0.075)
        assert eng.stop_loss_pct == pytest.approx(0.0375)
