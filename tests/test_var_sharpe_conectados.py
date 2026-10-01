"""Pruebas de vida de la conexion de `var.py` y `sharpe_metrics.py` (2026-10-01).

Contexto: los doce modulos muertos del inventario. Estos dos SI se
conectan, y asi se decide (orden del module-level: muestra -> replay ->
quien manda -> conexion con estado explicito):

  * **Muestra**: 9 cierres deduplicados en el ledger vivo
    (state_classic-xrp; 14 filas de cierre, 9 posiciones unicas) frente a
    un piso de 20. Todo lo de este bloque tiene que decir "insuficiente"
    con el numero en la mano, no entregar un VaR o un Sharpe de ruido.
  * **Replay**: con N=9, dejar caer UN cierre movia el VaR-95 entre
    0.026 y 0.060 de la cuenta (leave-one-out). Por eso los estados son
    INFORMATIVOS: ni aprueban ni vetan.
  * **Quien manda**: DailyGuard (drawdown) y los topes de margen/riesgo
    siguen mandando; estos bloques no tocan `approved` ni `reasons`.
  * **Conexion**: `check_position_size(..., pnl_series=...)` y el
    orquestador pasa la serie medida del ledger.

Y un bug que hubo que arreglar ANTES de conectar: `ExpectedShortfall`
parametrico devolvia 0.0 siempre (signo cambiado en la formula + el
`max(0.0, ...)`), es decir decia que no hay perdida en la cola. El
primer test de este fichero es el candado.

Todos los tests fallaban contra el estado anterior (modulos sin
llamadores y ES en cero). Offline: nada de red ni de runtime/ reales.
"""
import json
import os
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.orchestrator import Orchestrator, OrchestratorConfig
from quant_math.risk.risk_manager import RiskManager
from quant_math.risk.var import ExpectedShortfall, ValueAtRisk
from quant_math.expectation.sharpe_metrics import SharpeMetrics

#: Serie REAL del ledger state_classic-xrp, 9 posiciones unicas
#: deduplicadas (medida el 2026-10-01). Se usa tal cual para no poder
#: aprobar un test con una muestra mejorada a proposito.
SERIE_REAL = [-0.6084, -0.2433, -0.1011, -0.0661, 0.0435,
              0.0541, 0.0569, 0.1172, 0.1360]
CUENTA_REAL = 8.1998


def _cfg(state_dir, **kw):
    base = dict(
        symbols=["BTC/USDT"], timeframe="1h", lookback_days=14,
        initial_capital=5.0, entry_pct=0.1, take_profit_pct=0.05,
        min_paper_trades=3, hypotheses_per_cycle=3,
        kb_path=os.path.join(state_dir, "kb.jsonl"),
        state_dir=state_dir,
    )
    base.update(kw)
    return OrchestratorConfig(**base)


def _orch(config):
    """Orchestrator minimo para llamar a metodos que solo leen config."""
    orch = Orchestrator.__new__(Orchestrator)
    orch.config = config
    orch.cycle_count = 1
    orch._last_realized_total = 0.0
    orch._last_equity = 0.0
    orch._risk_manager = None
    return orch


def _ledger(path, filas):
    with open(path, "w", encoding="utf-8") as fh:
        for fila in filas:
            fh.write(json.dumps(fila) + "\n")


def _cierre(key, entry, exit_, pnl, qty=1.0, symbol="BTC/USDT"):
    return {"type": "closure", "key": key, "hypothesis_id": key.split(":")[0],
            "symbol": symbol, "entry_price": 100.0, "exit_price": 100.0,
            "quantity": qty, "pnl": pnl, "entry_time": entry,
            "exit_time": exit_, "motivo_cierre": "tp" if pnl >= 0 else "sl"}


def _serie(n, semilla=0, media=-0.001, dstd=0.02, cuenta=1000.0):
    """n cierres sinteticos EN USD para una cuenta dada (fraccion ~dstd)."""
    r = np.random.RandomState(semilla)
    return list(r.normal(media * cuenta, dstd * cuenta, n))


# ---------------------------------------------------------------------------
# 1. El ES parametrico decia "no hay perdida en la cola": arreglado antes
#    de conectar
# ---------------------------------------------------------------------------

def test_es_parametrico_no_devuelve_cero():
    """Con mu=0, sigma=1, ES-95 = 2.06 (perdida media del 5% peor).
    Antes devolvia exactamente 0.0: `-(mu + sigma*phi/alpha)` era
    negativo y el `max(0.0, ...)` lo anulaba."""
    es = ExpectedShortfall().calculate(0.0, 1.0, 0.95)
    assert es == pytest.approx(2.0627, abs=1e-3)
    es99 = ExpectedShortfall().calculate(0.0, 1.0, 0.99)
    assert es99 == pytest.approx(2.6652, abs=1e-3)
    assert es99 > es


def test_es_es_mayor_o_igual_que_var_en_todos_los_niveles():
    """Invarianza obligatoria: la perdida MEDIA de la cola no puede ser
    menor que el umbral de la cola. Con el signo cambiado, ES era 0.0 y
    el invariante se rompia en todos los niveles."""
    var = ValueAtRisk()
    es = ExpectedShortfall()
    for conf in (0.90, 0.95, 0.99):
        assert es.calculate(0.0, 1.0, conf) >= var.calculate(0.0, 1.0, conf), conf
        # y con serie real, no solo con la normal canonica
        r = np.array(SERIE_REAL)
        assert (es.calculate_from_returns(r, conf)
                >= var.calculate_from_returns(r, conf)), conf


# ---------------------------------------------------------------------------
# 2. Sin serie: estado explicito, nunca un cero que parezca medida
# ---------------------------------------------------------------------------

def test_sin_serie_los_dos_bloques_se_declaran_sin_datos():
    rm = RiskManager()
    chk = rm.check_position_size("h1", 10.0, 1000.0)

    assert chk["var_status"] == "sin_datos"
    assert chk["sharpe_status"] == "sin_datos"
    # ningun numero sin datos (ni 0.0, que seria una medida falsa)
    assert chk["var_95_frac"] is None and chk["es_95_frac"] is None
    assert chk["var_99_frac"] is None and chk["es_99_frac"] is None
    assert chk["sharpe"] is None and chk["sortino"] is None
    # la nota declara la unidad y el horizonte: sin eso, dos calculos
    # con el mismo nombre no son comparables
    assert "fraccion de la cuenta" in chk["var_note"]
    assert "1 cierre" in chk["var_note"]
    assert "NO se calcula" in chk["sharpe_note"]
    # y no toca la aprobacion
    assert chk["approved"] is True


def test_serie_basura_no_lanza_y_no_veta():
    """Esta llamada vive dentro del `try` de `_apply_margin_cap`, donde
    una excepcion RECHAZA la entrada: una serie corrupta tiene que
    declararse invalida, no tirar la operacion."""
    rm = RiskManager()
    chk = rm.check_position_size("h1", 10.0, 1000.0,
                                 pnl_series=["x", None, np.nan])
    assert chk["var_status"] == "datos_invalidos"
    assert chk["sharpe_status"] == "datos_invalidos"
    assert chk["var_95_frac"] is None and chk["sharpe"] is None
    assert chk["approved"] is True
    assert chk["reasons"] == []


# ---------------------------------------------------------------------------
# 3. La muestra REAL: piso 20, y aqui hay 9
# ---------------------------------------------------------------------------

def test_con_la_muestra_real_del_ledger_todo_insuficiente():
    """Los 9 cierres de state_classic-xrp (medidos, sin tocar): por
    debajo del piso, asi que NINGUN numero sale. Un VaR o un Sharpe con
    N=9 seria ruido presentado como medida."""
    rm = RiskManager()
    # 1.00 USD de margen pedidos sobre la cuenta real (8.20): por debajo
    # del tope de 20%, asi que lo unico que puede cambiar la aprobacion
    # es el bloque de cola/calidad
    chk = rm.check_position_size("h1", 1.0, CUENTA_REAL,
                                 pnl_series=SERIE_REAL, n_closures=9)
    assert chk["var_status"] == "insuficiente"
    assert chk["sharpe_status"] == "insuficiente"
    assert chk["var_95_frac"] is None
    assert chk["es_95_frac"] is None
    assert chk["var_99_frac"] is None
    assert chk["sharpe"] is None and chk["sortino"] is None
    # el registro dice el numero de la muestra y el piso, para que se
    # pueda juzgar sin volver al ledger
    assert "9 cierres" in chk["var_note"]
    assert "20" in chk["var_note"]
    assert "9 cierres" in chk["sharpe_note"]
    assert "20" in chk["sharpe_note"]
    # e igual que el Kelly, no veta
    assert chk["approved"] is True
    assert chk["reasons"] == []


# ---------------------------------------------------------------------------
# 4. Con muestra suficiente: delega en los modulos canonicos
# ---------------------------------------------------------------------------

def test_con_muestra_suficiente_delega_en_var_es_y_sharpe():
    rm = RiskManager()
    cuenta = 1000.0
    serie = _serie(25)
    chk = rm.check_position_size("h1", 10.0, cuenta, pnl_series=serie)

    fracs = np.array(serie) / cuenta
    media = float(np.mean(fracs))
    dstd = float(np.std(fracs, ddof=1))
    esperado_var = ValueAtRisk().calculate(media, dstd, 0.95)
    esperado_es = ExpectedShortfall().calculate(media, dstd, 0.95)

    assert chk["var_status"] == "ok_95"       # 20 <= 25 < 100
    assert chk["var_95_frac"] == pytest.approx(esperado_var)
    assert chk["es_95_frac"] == pytest.approx(esperado_es)
    # la unidad de la nota es la del valor
    assert "fraccion de la cuenta" in chk["var_note"]
    assert "VaR-95=" in chk["var_note"]

    # Sharpe/Sortino delegados en SharpeMetrics, SIN anualizar
    assert chk["sharpe_status"] == "ok"
    assert chk["sharpe"] == pytest.approx(
        SharpeMetrics.sharpe_ratio(fracs, periods_per_year=1))
    assert chk["sortino"] == pytest.approx(
        SharpeMetrics.sortino_ratio(fracs, periods_per_year=1))


def test_var99_requiere_su_piso_de_100_y_se_declara():
    """Dos pisos, dos estados: el 95% se activa con 20 (piso de la
    casa) y el 99% con 100 (se apoya en 1 observacion de cada 100).
    Con 25 cierres sale ok_95 con el 99 declarado como NO medido."""
    rm = RiskManager()
    chk25 = rm.check_position_size("h1", 10.0, 1000.0, pnl_series=_serie(25))
    assert chk25["var_status"] == "ok_95"
    assert chk25["var_99_frac"] is None and chk25["es_99_frac"] is None
    assert "NO medidos" in chk25["var_note"]
    assert "100" in chk25["var_note"]

    chk100 = rm.check_position_size("h1", 10.0, 1000.0,
                                    pnl_series=_serie(100, semilla=7))
    assert chk100["var_status"] == "ok"
    assert chk100["var_99_frac"] is not None
    assert chk100["es_99_frac"] >= chk100["var_99_frac"]
    assert "VaR-99=" in chk100["var_note"]


def test_sharpe_no_se_anualiza_la_serie_es_por_cierre():
    """El modulo anualiza con 252 por DEFECTO. Nuestra serie es por
    cierre: anualizaria un horizonte que no existe (el Sharpe real de la
    serie del ledger pasa de -0.29 a -4.58 solo por cambiar la unidad)."""
    rm = RiskManager()
    serie = _serie(40, semilla=3)
    chk = rm.check_position_size("h1", 10.0, 1000.0, pnl_series=serie)
    fracs = np.array(serie) / 1000.0

    sin_anualizar = SharpeMetrics.sharpe_ratio(fracs, periods_per_year=1)
    anualizado = SharpeMetrics.sharpe_ratio(fracs, periods_per_year=252)
    assert chk["sharpe"] == pytest.approx(sin_anualizar)
    assert chk["sharpe"] != pytest.approx(anualizado)
    assert abs(chk["sharpe"]) < abs(anualizado)
    assert "SIN anualizar" in chk["sharpe_note"]
    assert "periods_per_year=1" in chk["sharpe_note"]


# ---------------------------------------------------------------------------
# 5. El candado: ninguno de estos estados aprueba, recorta o rechaza
# ---------------------------------------------------------------------------

def test_los_estados_nuevos_no_vetan_ni_recortan():
    """Muestra grande y colas horrorosas: el resultado del check tiene
    que ser IDENTICO con y sin serie. Si algun dia un VaR o un Sharpe
    pasa a vetar, este test es el que avisa de que el dimensionamiento
    vivo cambio sin medirse."""
    rm = RiskManager()
    peores = [-0.20] * 100          # 100 cierres perdiendo el 20% cada uno
    sin = rm.check_position_size("h1", 10.0, 1000.0)
    con = rm.check_position_size("h1", 10.0, 1000.0, pnl_series=peores)

    assert con["var_status"] == "ok" and con["sharpe_status"] == "ok"
    assert con["approved"] == sin["approved"] is True
    assert con["approved_size"] == sin["approved_size"] == 10.0
    assert con["reasons"] == sin["reasons"] == []
    assert not any("VaR" in r or "Sharpe" in r for r in con["reasons"])
    # el tamano tampoco cambia: la unica diferencia es el ESTADO
    assert con["max_position"] == sin["max_position"]


def test_estado_sin_datos_y_estado_ok_dan_el_mismo_nocional():
    """Mismo pedido, misma cuenta, con y sin serie medida."""
    rm = RiskManager()
    a = rm.check_position_size("h1", 50.0, 1000.0)
    b = rm.check_position_size("h1", 50.0, 1000.0, pnl_series=_serie(25))
    assert a["approved_size"] == b["approved_size"] == 50.0
    assert a["kelly_status"] == b["kelly_status"] == "sin_datos"
    assert a["var_status"] == "sin_datos" and b["var_status"] == "ok_95"


# ---------------------------------------------------------------------------
# 6. El orquestador pasa LA SERIE MEDIDA, no una inventada
# ---------------------------------------------------------------------------

def test_orchestrator_pasa_la_seria_del_ledger_al_check():
    from quant_math.risk import risk_manager as rm_mod

    with tempfile.TemporaryDirectory() as tmp:
        filas = []
        for i in range(20):
            filas.append(_cierre(f"h{i}:BTC/USDT", 1000.0 + i, 1100.0 + i,
                                 0.10, qty=float(i + 1)))
        for i in range(5):
            filas.append(_cierre(f"l{i}:BTC/USDT", 2000.0 + i, 2100.0 + i,
                                 -0.05, qty=float(i + 1)))
        # una re-marca de una posicion YA contada: la ultima marca gana
        filas.append(_cierre("h0:BTC/USDT", 1000.0, 1100.0, 0.30, qty=1.0))
        _ledger(os.path.join(tmp, "paper_executions.jsonl"), filas)

        capturado = {}

        def espia(self, hypothesis_id, requested_size, account_value, **kw):
            capturado.update(kw)
            return {"approved": True, "reasons": [], "max_position":
                    account_value * 0.2, "kelly_size": None,
                    "kelly_status": "sin_datos", "kelly_note": "",
                    "requested_size": requested_size,
                    "kelly_fraction_applied": None,
                    "kelly_advisory": None}

        original = rm_mod.RiskManager.check_position_size
        rm_mod.RiskManager.check_position_size = espia
        try:
            o = _orch(_cfg(tmp, max_position_pct=0.2,
                           max_notional_per_entry_pct=1.0))
            salio = o._apply_margin_cap(1000.0, 10, "h1", sl_distance=0.025)
            assert salio > 0.0
        finally:
            rm_mod.RiskManager.check_position_size = original

        serie = capturado.get("pnl_series")
        assert serie is not None, (
            "_apply_margin_cap no paso la serie de cierres: VaR/ES y "
            "Sharpe quedarian siempre en sin_datos")
        # 25 posiciones unicas (la re-marca de h0 no cuenta doble)
        assert len(serie) == 25, serie
        # la ultima marca de h0 es la que manda (0.30, no 0.10)
        assert serie.count(0.30) == 1 and serie.count(0.10) == 19
        assert sorted(serie).count(-0.05) == 5
        # y la n del Kelly sale del MISMO libro: las dos medidas cuadran
        assert capturado.get("n_closures") == 25


def test_ruta_completa_orquestador_riskmanager_estado_grabado():
    """Prueba de conexion de verdad (sin espiar): el orquestador mide la
    serie del ledger, RiskManager la evalua y el ESTADO queda grabado en
    el historial de checks — que es donde ya vive el del Kelly."""
    with tempfile.TemporaryDirectory() as tmp:
        # los 9 cierres del ledger real, escritos en un libro temporal
        _ledger(os.path.join(tmp, "paper_executions.jsonl"), [
            _cierre(f"h{i}:XRP/USDT", 1000.0 + i, 1100.0 + i, pnl,
                    qty=float(i + 1))
            for i, pnl in enumerate(SERIE_REAL)
        ])
        o = _orch(_cfg(tmp, max_position_pct=0.2,
                       max_notional_per_entry_pct=1.0))
        salio = o._apply_margin_cap(20.0, 10, "h1", sl_distance=0.025)
        assert salio > 0.0

        historial = o._risk_manager.get_risk_check_history("h1")
        assert len(historial) == 1
        chk = historial[0]
        # con los 9 cierres reales, los dos bloques estan en
        # "insuficiente" y sin numeros: asi funciona la conexion HOY
        assert chk["var_status"] == "insuficiente"
        assert chk["sharpe_status"] == "insuficiente"
        assert chk["var_95_frac"] is None and chk["sharpe"] is None
        # y la entrada salio igual que sin serie (no es un veto)
        assert salio == o._apply_margin_cap(20.0, 10, "h1",
                                            sl_distance=0.025)


def test_orchestrator_sin_libro_pasa_serie_vacia():
    """Sin ledger la serie viene vacia y el modulo declara sin_datos: el
    estado NO se inventa en el orquestador."""
    from quant_math.risk import risk_manager as rm_mod

    with tempfile.TemporaryDirectory() as tmp:
        capturado = {}

        def espia(self, hypothesis_id, requested_size, account_value, **kw):
            capturado.update(kw)
            return {"approved": True, "reasons": [], "max_position":
                    account_value * 0.2, "kelly_size": None,
                    "kelly_status": "sin_datos", "kelly_note": "",
                    "requested_size": requested_size,
                    "kelly_fraction_applied": None,
                    "kelly_advisory": None}

        original = rm_mod.RiskManager.check_position_size
        rm_mod.RiskManager.check_position_size = espia
        try:
            o = _orch(_cfg(tmp, max_position_pct=0.2,
                           max_notional_per_entry_pct=1.0))
            assert o._apply_margin_cap(1000.0, 10, "h1") > 0.0
        finally:
            rm_mod.RiskManager.check_position_size = original

        assert capturado.get("pnl_series") == []


def test_ledger_pnl_series_y_kelly_stats_miden_lo_mismo():
    """Las dos medidas salen del MISMO parseo (`_ledger_closures`): dos
    parseos distintos del libro son dos fuentes de verdad para la misma
    muestra."""
    with tempfile.TemporaryDirectory() as tmp:
        _ledger(os.path.join(tmp, "paper_executions.jsonl"), [
            _cierre("h1:XRP/USDT", 1000.0, 1100.0, 0.10),
            _cierre("h1:XRP/USDT", 1000.0, 1200.0, -0.10),
            _cierre("h1:XRP/USDT", 1000.0, 1300.0, 0.20),   # ultima marca
            _cierre("h2:ETH/USDT", 2000.0, 2100.0, -0.30),
            # un cierre PLANO entra en la serie (es una observacion
            # real de la cola) aunque el Kelly lo excluya
            _cierre("h3:BTC/USDT", 3000.0, 3100.0, 0.0),
            {"type": "entry", "key": "h4:BTC/USDT", "entry_price": 1.0},
        ])
        o = _orch(_cfg(tmp))
        serie = o._ledger_pnl_series()
        # h1 gana su ultima marca (0.20), h2 (-0.30) y el cierre plano
        # (0.0): la serie tiene TRES observaciones
        assert sorted(serie) == [-0.30, 0.0, 0.20]
        # el Kelly sigue excluyendo el cero a cero (no informa de
        # ventaja ni de desventaja): la muestra del Kelly es de 2, la
        # serie de cierres de 4
        wr, aw, al, n = o._ledger_kelly_stats()
        assert n == 2
        assert wr == pytest.approx(0.5)
        assert aw == pytest.approx(0.20)
        assert al == pytest.approx(0.30)
