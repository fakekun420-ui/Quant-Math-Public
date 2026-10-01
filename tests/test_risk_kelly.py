"""Tests que cazan el bug del Kelly silencioso en RiskManager (2026-10-01).

El bug: `_calculate_kelly_position_size` estaba reimplementada a mano en
`risk_manager.py` con defaults (wr=0.5, aw=1.0, al=1.0) que daban
exactamente `f = 0.5 - 0.5/1.0 = 0.0`, y ese 0.0 silencioso desactivaba
el aviso de Kelly (`kelly_size > 0`) pareciendo una medida. Medido antes
de arreglarlo: **0 tests del repo mencionaban "kelly"** (`grep -rni kelly
tests/ | wc -l` == 0), asi que borrar el modulo entero no rompia nada.

Dos pruebas de vida del arreglo:
  1. `kelly_size` no puede salir 0.0 (ni None) sin que el registro diga
     explicitamente por que y a que metodo declarado se cae.
  2. La formula a mano ya no existe: el calculo delega en el modulo
     canonico `quant_math.risk.sizing.KellyCriterion`.

Offline y deterministas: nada de red, nada de runtime/ reales.
"""
import ast
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.orchestrator import Orchestrator, OrchestratorConfig
from quant_math.risk.risk_manager import RiskManager
from quant_math.risk.sizing import KellyCriterion

RISK_MANAGER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "quant_math", "risk", "risk_manager.py")


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
            "exit_time": exit_, "motivo_cierre": "tp" if pnl > 0 else "sl"}


# ---------------------------------------------------------------------------
# 1. Un cero (o un None) sin explicacion es exactamente el bug
# ---------------------------------------------------------------------------

def test_kelly_sin_datos_no_es_cero_silencioso():
    """Sin win_rate medido NO hay numero: ni 0.0 ni nada parecido."""
    rm = RiskManager()
    chk = rm.check_position_size("h1", 10.0, 1000.0)

    # Antes: 0.0 sin mas. Ahora: None + estado que lo dice.
    assert chk["kelly_size"] is None, "kelly sin datos no puede ser 0.0"
    assert chk["kelly_status"] == "sin_datos"
    # y el registro dice ademas a que metodo DECLARADO se cae el sizing
    assert "max_position_size_pct" in chk["kelly_note"]
    assert "win_rate" in chk["kelly_note"]
    # el aviso no puede existir si no hay tamano que comparar
    assert chk["kelly_advisory"] is None
    # la aprobacion no se toca: esto es informativo, no un veto
    assert chk["approved"] is True
    assert chk["max_position"] == pytest.approx(200.0)


def test_ningun_camino_saca_un_cero_sin_declararlo():
    """Tabla de caminos: un kelly_size == 0.0 SOLO puede venir de
    "no_viable" (el Kelly medido dijo no apostar), y todo lo que no
    calcula devuelve None con su estado. Si algun dia vuelve a salir un
    0.0 por default, este test revienta."""
    rm = RiskManager()
    caminos = [
        ("sin_datos", dict()),
        ("insuficiente", dict(win_rate=0.8, avg_win=1.0, avg_loss=1.0,
                              n_closures=3)),
        ("datos_invalidos", dict(win_rate=1.5, avg_win=1.0, avg_loss=1.0,
                                 n_closures=50)),
        ("no_viable", dict(win_rate=0.3, avg_win=1.0, avg_loss=1.0,
                           n_closures=50)),
        ("ok", dict(win_rate=0.8, avg_win=1.0, avg_loss=1.0, n_closures=50)),
    ]
    for esperado, kwargs in caminos:
        chk = rm.check_position_size("h1", 10.0, 1000.0, **kwargs)
        assert chk["kelly_status"] == esperado, (
            f"camino {esperado}: salio {chk['kelly_status']}")
        size = chk["kelly_size"]
        if size == 0.0:
            assert esperado == "no_viable", (
                "kelly_size=0.0 sin que el registro declare que el Kelly "
                "medido no compensa: eso es el bug silencioso")
        if size is None:
            # todo None viene con nota que nombra el metodo declarado
            assert "max_position_size_pct" in chk["kelly_note"], (
                f"estado {esperado} sin declarar el metodo de repuesto")
        assert isinstance(chk["kelly_note"], str) and chk["kelly_note"]


def test_kelly_medido_ok_da_el_tamano_del_modulo():
    """Con datos medidos, el tamano es EL del modulo canonico aplicado a
    la fraccion de Kelly configurada (0.3 por defecto)."""
    rm = RiskManager()
    wr, aw, al, n = 0.8, 0.256176, 0.304833, 25  # medido en runtime/ 2026-10-01
    chk = rm.check_position_size("h1", 10.0, 8.5835,
                                 win_rate=wr, avg_win=aw, avg_loss=al,
                                 n_closures=n)
    esperado = KellyCriterion.calculate(wr, aw, al)
    assert chk["kelly_status"] == "ok"
    assert chk["kelly_size"] == pytest.approx(
        8.5835 * min(1.0, esperado * rm.kelly_fraction))
    assert chk["kelly_fraction_applied"] == pytest.approx(
        min(1.0, esperado * 0.3))
    assert "0.5620" in chk["kelly_note"] or "0.56" in chk["kelly_note"]


# ---------------------------------------------------------------------------
# 2. La formula a mano ya no existe: delega en el modulo
# ---------------------------------------------------------------------------

def test_la_formula_a_mano_ya_no_existe_en_el_fuente():
    """AST, no texto: se busca el IDENTIFICADOR `win_loss_ratio` en el
    arbol del codigo (la formula reimplementada lo usaba como divisor).
    Un texto dentro de un docstring no cuenta: lo que no puede volver es
    el calculo, no la memoria historica de como era."""
    with open(RISK_MANAGER_SRC, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    identificadores = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
    assert "win_loss_ratio" not in identificadores, (
        "la formula a mano (`f = wr - (1-wr)/win_loss_ratio`) sigue viva "
        "en el codigo: hay DOS fuentes de verdad para el Kelly")
    # y el punto unico de calculo es el del modulo
    with open(RISK_MANAGER_SRC, encoding="utf-8") as fh:
        src = fh.read()
    assert "self.kelly.calculate(" in src


def test_delega_en_el_modulo_y_no_recalcula_a_mando():
    """Prueba funcional de delegacion: si el modulo devuelve un valor
    marcado, el registro le sigue. Si siguiera reimplementando la formula
    a mano, el marcador no tendria efecto y aqui fallaria."""
    rm = RiskManager()
    rm.kelly.calculate = lambda *a, **k: 0.123456
    chk = rm.check_position_size("h1", 10.0, 1000.0,
                                 win_rate=0.6, avg_win=2.0, avg_loss=1.0,
                                 n_closures=50)
    assert chk["kelly_size"] == pytest.approx(
        1000.0 * 0.123456 * rm.kelly_fraction)


def test_formula_a_mano_y_modulo_daban_lo_mismo_pero_solo_una_queda():
    """Registro de la diagnostico: la reimplementacion a mano era
    ALGEBRAICAMENTE identica al modulo en el dominio normal
    (`p - (1-p)/(aw/al) == (p*aw - (1-p)*al)/aw`), asi que el bug no era
    un resultado distinto: era la DUPLICACION (dos fuentes de verdad) y
    los defaults que daban 0.0. Se comprueba la equivalencia para que
    conste, y que hoy el valor sale del modulo."""
    for wr, aw, al in [(0.6, 2.0, 1.0), (0.8, 0.256176, 0.304833),
                       (0.5, 1.0, 1.0), (0.55, 1.2, 0.9)]:
        b = aw / al
        a_mano = wr - (1 - wr) / b
        modulo = KellyCriterion.calculate(wr, aw, al)
        assert a_mano == pytest.approx(modulo), (wr, aw, al)
    # en el dominio normal coincidian; el problema eran los defaults:
    assert KellyCriterion.calculate(0.5, 1.0, 1.0) == 0.0


# ---------------------------------------------------------------------------
# 3. El aviso de Kelly NO puede entrar en `reasons` (dimensionamiento vivo)
# ---------------------------------------------------------------------------

def test_aviso_de_kelly_no_puede_romper_el_corte_de_margen():
    """Invariante del orquestador: si `approved` es False y TODOS los
    motivos son "exceeds max", el orquestador RECORTA el margen; si hay
    cualquier otro motivo, RECHAZA la entrada. Con Kelly medido su
    fraccion (<= 0.17 medido, frente a max_position_pct=0.20) se activa
    SIEMPRE que se supera el tope, asi que un aviso de Kelly dentro de
    `reasons` convertiria cada recorte en un rechazo cerrado. Este test
    es el candado: el motivo de Kelly vive en `kelly_advisory`, nunca en
    `reasons`."""
    rm = RiskManager()  # max_position_size_pct=0.2
    chk = rm.check_position_size("h1", 300.0, 1000.0,
                                 win_rate=0.8, avg_win=1.0, avg_loss=1.0,
                                 n_closures=50)
    # Kelly medido > 0 y pedido (300) > Kelly, y ademas pedido > tope
    assert chk["kelly_size"] is not None and chk["kelly_size"] > 0
    assert chk["requested_size"] > chk["kelly_size"]
    assert chk["approved"] is False
    assert chk["kelly_advisory"], "el aviso tiene que existir (aparte)"
    # El candado en si:
    assert all("exceeds max" in r for r in chk["reasons"]), (
        "motivo no-recorte en reasons: el orquestador rechazaria en vez "
        f"de recortar -> {chk['reasons']}")


def test_kelly_no_puede_ser_motivo_de_rechazo():
    """Ningun estado del Kelly pone approved=False: es informativo."""
    rm = RiskManager()
    for kwargs in ({}, dict(win_rate=0.8, avg_win=1.0, avg_loss=1.0,
                            n_closures=3),
                   dict(win_rate=0.3, avg_win=1.0, avg_loss=1.0,
                        n_closures=50)):
        chk = rm.check_position_size("h1", 10.0, 1000.0, **kwargs)
        assert chk["approved"] is True, kwargs
        assert not any("Kelly" in r for r in chk["reasons"]), kwargs


# ---------------------------------------------------------------------------
# 4. La medida del ledger: deduplica y el piso lo aplica RiskManager
# ---------------------------------------------------------------------------

def test_ledger_kelly_stats_cuenta_posiciones_no_filas():
    """El ledger real repite filas de UNA misma posicion (misma
    entrada/cantidad, hasta con pnl de signo opuesto entre marcas). Sin
    deduplicar el win_rate sale inflado. Aqui: 3 marcas de UNA posicion
    (la ultima gana) + 1 posicion perdedora = 2 cierres, no 4 filas."""
    with tempfile.TemporaryDirectory() as tmp:
        _ledger(os.path.join(tmp, "paper_executions.jsonl"), [
            _cierre("h1:XRP/USDT", 1000.0, 1100.0, 0.10),
            _cierre("h1:XRP/USDT", 1000.0, 1200.0, -0.10),
            _cierre("h1:XRP/USDT", 1000.0, 1300.0, 0.20),   # ultima marca
            _cierre("h2:ETH/USDT", 2000.0, 2100.0, -0.30),
            # una fila que no es cierre no cuenta
            {"type": "entry", "key": "h3:BTC/USDT", "entry_price": 1.0},
        ])
        o = _orch(_cfg(tmp))
        wr, aw, al, n = o._ledger_kelly_stats()
        assert n == 2, "cuentan POSICIONES unicas, no filas del ledger"
        assert wr == pytest.approx(0.5)
        assert aw == pytest.approx(0.20)   # gana la ultima marca
        assert al == pytest.approx(0.30)


def test_ledger_kelly_stats_sin_libro_no_lanza():
    """Un ledger ausente es 'sin datos', no una excepcion: esta llamada
    vive dentro del try que falla CERRADO y rechazaria la entrada."""
    with tempfile.TemporaryDirectory() as tmp:
        o = _orch(_cfg(tmp))
        assert o._ledger_kelly_stats() == (None, None, None, 0)


def test_piso_de_muestra_bloquea_el_kelly_de_muestra_chica():
    """9 cierres medidos (el numero real del ledger de
    state_classic-xrp el 2026-10-01) no llegan al piso: el registro lo
    dice con el numero en la mano en vez de devolver un Kelly de ruido."""
    rm = RiskManager()
    chk = rm.check_position_size(
        "h1", 10.0, 8.5835,
        win_rate=0.5556, avg_win=0.254208, avg_loss=0.254700,
        n_closures=9)
    assert chk["kelly_size"] is None
    assert chk["kelly_status"] == "insuficiente"
    assert "9 cierres" in chk["kelly_note"]
    assert "20" in chk["kelly_note"]  # el piso, para que se pueda juzgar


# ---------------------------------------------------------------------------
# 5. El orquestador pasa LO MEDIDO al check (y solo eso)
# ---------------------------------------------------------------------------

def test_orchestrator_pasa_al_check_lo_que_mide_el_ledger():
    """Cableado: `_apply_margin_cap` tiene que mandar win_rate/avg/n
    medidos del ledger al RiskManager. Se espia el metodo para leer los
    argumentos reales (el resultado del check no importa aqui)."""
    from quant_math.risk import risk_manager as rm_mod

    with tempfile.TemporaryDirectory() as tmp:
        filas = []
        for i in range(20):   # 20 posiciones ganadoras distintas
            filas.append(_cierre(f"h{i}:BTC/USDT", 1000.0 + i,
                                 1100.0 + i, 0.10, qty=float(i + 1)))
        for i in range(5):    # 5 perdedoras
            filas.append(_cierre(f"l{i}:BTC/USDT", 2000.0 + i,
                                 2100.0 + i, -0.05, qty=float(i + 1)))
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
            assert salio > 0.0  # con check aprobado, el nocional sigue
        finally:
            rm_mod.RiskManager.check_position_size = original

        assert capturado.get("n_closures") == 25, capturado
        assert capturado.get("win_rate") == pytest.approx(20 / 25)
        assert capturado.get("avg_win") == pytest.approx(0.10)
        assert capturado.get("avg_loss") == pytest.approx(0.05)


def test_orchestrator_sin_ledger_pasa_nones_declarados():
    """Sin libro de cierres, los argumentos vienen en None: el
    RiskManager es quien dice 'sin_datos' con su nota. Un default
    inventado (wr=0.5) aqui seria el bug con otra cara."""
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
            o._apply_margin_cap(1000.0, 10, "h1", sl_distance=0.025)
        finally:
            rm_mod.RiskManager.check_position_size = original

        assert capturado.get("win_rate") is None
        assert capturado.get("avg_win") is None
        assert capturado.get("avg_loss") is None
        assert capturado.get("n_closures") == 0
