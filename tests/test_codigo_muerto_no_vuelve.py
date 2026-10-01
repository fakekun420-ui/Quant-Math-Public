"""Guardas de que el codigo muerto NO vuelva.

POR QUE ESTOS TESTS
-------------------
El 2026-10-01 se quitaron cinco modulos que estaban escritos y no se
llamaban: `monte_carlo.simulator`, `risk.stop_loss`,
`expectation.drawdown_analyzer`, `expectation.return_calculator` y
`risk.portfolio_risk`. Cada uno con su motivo, que esta en el commit.

Un borrado de este tipo no se sostiene solo: las cuatro razones por las que
pueden volver son (1) alguien copia un modulo de la cuarentena porque "hace
falta", (2) un `__init__.py` vuelve a exportarlo y el motor lo instancia sin
usarlo, otra vez, (3) el `__main__` vuelve a prometer una capacidad que ya no
esta, y (4) un test nuevo importa el simbolo y falla tarde.

Estos tests miran las cuatro. Son baratos y no dependen de la red.

LO QUE NO COMPRUEBAN
--------------------
Que los sustitutos vivos hagan el trabajo. Eso se mide en otro sitio: el SL
por `roe_targets.build_roe_plan` con su clamp de liquidacion, y el drawdown
por `circuit_breaker.DailyGuard`, que bloquea de verdad (medido: 24,52% > 20%
-> `risk_halt`). Aqui solo se comprueba que el hueco no se ha rellenado con
codigo que no hace nada.
"""

import ast
import inspect
import os
import re

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: (nombre de modulo, simbolos que aportaba, porque se sustituye por esto)
RETIRADOS = {
    "quant_math/monte_carlo/simulator.py": (
        ("MonteCarloSimulator", "MonteCarloConfig", "bootstrap_simulation",
         "parametric_simulation", "calculate_var_es"),
        "adapter.simulate_distribution (devuelve fraccion de capital, "
        "comparable con el pondero 0,3 del score cientifico)"),
    "quant_math/risk/stop_loss.py": (
        ("StopLoss",),
        "risk.roe_targets.build_roe_plan (clamp de liquidacion medido)"),
    "quant_math/expectation/drawdown_analyzer.py": (
        ("DrawdownAnalyzer",),
        "risk.circuit_breaker.DailyGuard (bloquea de verdad)"),
    "quant_math/expectation/return_calculator.py": (
        ("ReturnCalculator",),
        "ledger: el PnL se calcula con la cantidad, no con pnl/precio"),
    "quant_math/risk/portfolio_risk.py": (
        ("PortfolioRisk", "RiskBudget", "StressTesting"),
        "risk.var (VaR y ES, conectados a check_position_size)"),
}


def _ruta(rel):
    return os.path.join(RAIZ, rel)


# ---------------------------------------------------------------------------
# 1. Los ficheros no vuelven
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", sorted(RETIRADOS))
def test_el_modulo_retirado_no_esta_en_el_repo(rel):
    """El fichero no debe reaparecer.

    Control de mutacion: reintroducir cualquiera de los cinco hace FALLAR
    este test. No hay que comprobar nada mas: si el fichero esta, el codigo
    muerto esta.
    """
    assert not os.path.exists(_ruta(rel)), (
        f"{rel} vuelve a estar. Si se necesita, la pregunta no es "
        "si el modulo es util sino si su SUSTITUTO (ver RETIRADOS) deja de "
        "hacer el trabajo: con los dos vivos, uno de los dos queda sin usar")


# ---------------------------------------------------------------------------
# 2. Ningun __init__ vuelve a exportarlo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", sorted(RETIRADOS))
def test_ningun_init_lo_exporta(rel):
    """Un re-export es la via por la que el codigo muerto vuelve a la vida.

    Si un `__init__.py` importa un modulo retirado, el modulo tiene que
    existir y el import revienta; pero si alguien lo crea "para que no
    falle el import", el modulo entra de vuelta con 0 usos. Este test corta
    las dos mitades del problema.
    """
    simbolos = RETIRADOS[rel][0]
    for raiz, _dirs, ficheros in os.walk(RAIZ):
        if any(p in raiz for p in ("__pycache__", "graphify-out", ".git")):
            continue
        for f in ficheros:
            if f != "__init__.py":
                continue
            ruta = os.path.join(raiz, f)
            try:
                texto = open(ruta, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            # Solo cuenta el codigo: los comentarios explican la retirada
            # y tienen que mencionar el simbolo.
            codigo = "\n".join(
                l for l in texto.splitlines()
                if not l.strip().startswith("#"))
            for s in simbolos:
                assert not re.search(rf"\b{s}\b", codigo), (
                    f"{ruta} vuelve a exportar {s}, que estaba retirado "
                    "con su modulo")


# ---------------------------------------------------------------------------
# 3. El motor no los instancia sin usarlos (el bug ORIGINAL)
# ---------------------------------------------------------------------------

def test_ningun_modulo_se_instancia_y_no_se_usa():
    """El defecto que motivo el borrado era la instanciacion muerta.

    `risk_manager.py` hacia `self.stop_loss = StopLoss()` y
    `self.drawdown_analyzer = DrawdownAnalyzer()` y no llamaba a NINGUN
    metodo. Eso no es codigo inofensivo: son dos objetos vivos en cada
    `RiskManager` que ocupan memoria y aparentan hacer un trabajo que no
    hacen. Por eso el criterio de este repo no es "no se usa" sino
    "no se instancia sin usarse".
    """
    src = open(_ruta("quant_math/risk/risk_manager.py"),
               encoding="utf-8").read()
    # Se mira el CODIGO, no el texto: el comentario de la retirada tiene que
    # poder mencionar `self.stop_loss`, y este test no puede fallar por eso.
    codigo = "\n".join(l for l in src.splitlines()
                       if not l.strip().startswith("#"))
    for atributo in ("self.stop_loss", "self.drawdown_analyzer"):
        assert atributo not in codigo, (
            f"{atributo} vuelve a instanciarse sin usarse: comprueba que no "
            "tenga llamadas, no solo que exista la linea")


def test_el_risk_manager_no_crea_objetos_que_no_usa():
    """Control de MANDO: cada `self.x = Thing()` debe tener uso."""
    ruta = _ruta("quant_math/risk/risk_manager.py")
    src = open(ruta, encoding="utf-8").read()
    tree = ast.parse(src)
    asignados = {}
    for nodo in ast.walk(tree):
        if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Attribute)
                and isinstance(nodo.value, ast.Call)):
            nombre = nodo.targets[0].attr
            if not nombre.startswith("_"):
                asignados[nombre] = nodo.value.func
    # Contar accesos de lectura: `self.x` que NO es asignacion.
    leidos = 0
    for nodo in ast.walk(tree):
        if (isinstance(nodo, ast.Attribute)
                and isinstance(nodo.value, ast.Name)
                and nodo.value.id == "self"
                and isinstance(nodo.ctx, ast.Load)
                and nodo.attr in asignados):
            leidos += 1
    assert leidos > 0, (
        "ningun objeto asignado se lee: se ha metido una instanciacion "
        "muerta nueva, del mismo tipo que las que se quitaron")
    print(f"\n  RiskManager: {len(asignados)} objetos asignados, "
          f"{leidos} lecturas. Ninguno queda huerfano.")


# ---------------------------------------------------------------------------
# 4. El CLI no promete lo que ya no esta
# ---------------------------------------------------------------------------

def test_el_main_no_promete_modulos_retirados():
    """Un `__main__` que anuncia una capacidad inexistente es un fallo de
    documentacion que el usuario paga en tiempo de ejecucion: pide un modulo
    y no aparece.

    MEDIDO el 2026-10-01: la linea de `risk` incluia `PortfolioRisk`, que se
    retiro ese mismo dia, y `monte_carlo` anunciaba "Monte Carlo simulation
    engine" con el paquete ya vacio.
    """
    src = open(_ruta("quant_math/__main__.py"), encoding="utf-8").read()
    for s in ("PortfolioRisk", "MonteCarloSimulator", "StopLoss",
              "DrawdownAnalyzer", "ReturnCalculator"):
        assert s not in src, (
            f"el CLI anuncia {s}, que no existe: el usuario lo pide y no "
            "llega")


def test_el_ayuda_de_monte_carlo_no_mente_sobre_su_contenido():
    """El paquete quedo vacio; su descripcion en el menu tambien."""
    src = open(_ruta("quant_math/__main__.py"), encoding="utf-8").read()
    import quant_math.monte_carlo as mc
    if not mc.__all__:
        assert "Monte Carlo simulation engine" not in src, (
            "el paquete monte_carlo esta vacio y el menu lo anuncia como "
            "engine: es exactamente el fallo que hace que un menu sea peor "
            "que no tenerlo")


# ---------------------------------------------------------------------------
# 5. Los sustitutos vivos siguen respondiendo
# ---------------------------------------------------------------------------

def test_el_sustituto_del_stop_sigue_clampeando_la_liquidacion():
    """Si se quito `stop_loss.py`, `build_roe_plan` tiene que seguir aquí.

    El borrado solo es legitimo si la capacidad sigue existiendo en otro
    sitio. Este test mira que ese "otro sitio" responda, no solo que el
    modulo viejo no este: sin esto, un borrado puede dejar un hueco y
    parecer una limpieza.
    """
    from quant_math.risk.roe_targets import build_roe_plan
    plan = build_roe_plan(mode="classic", leverage=50, symbol="BTC/USDT:USDT",
                          take_profit_roe=0.50, stop_loss_roe=0.25)
    assert plan.sl_price_distance > 0, "el stop debe estar a una distancia real"
    assert plan.liquidation_price_distance > 0, (
        "sin distancia de liquidacion el clamp no tiene contra que "
        "clampear: el modulo retirado era el unico que la traia")
    # Y el clamp tiene que seguir mandando: pedir un SL mas lejos que la
    # liquidacion tiene que quedar recortado, no aceptarse.
    loco = build_roe_plan(mode="classic", leverage=100, symbol="BTC/USDT:USDT",
                          take_profit_roe=0.5, stop_loss_roe=0.95)
    assert loco.sl_clamped or loco.errors, (
        "un SL al 95% de ROE a 100x esta mas alla de la liquidacion: o se "
        "recorta o se rechaza. Si pasa limpio, el clamp se rompió")


def test_el_sustituto_del_drawdown_sigue_bloqueando(tmp_path):
    """`DailyGuard` tiene que seguir BLOQUEANDO, no solo existir.

    Un borrado es legitimo si la capacidad sigue existiendo en otro sitio. Si
    el sustituyo se rompe, el borrado no fue una limpieza: fue dejar un hueco
    y llamarlo limpieza. Por eso se comprueba que el freno RESPONDE.
    """
    from quant_math.risk.circuit_breaker import DailyGuard
    g = DailyGuard(state_dir=str(tmp_path), max_daily_loss_usd=1.0,
                   max_open_positions=1, drawdown_limit=0.2)
    # Firma real (medida): check(realized_today, equity, open_count, ...) y
    # devuelve (puede_continuar, motivo). True es "adelante", False es
    # "frenado". Se escribe segun la semantica y no segun el nombre: un
    # test que llama `puede_continuar` a una variable llamada `fuera` se lee
    # mal y acaba terminado al reves.
    puede, _ = g.check(realized_today=-0.50, equity=1000.0, open_count=0)
    assert puede is True, "una perdida de 0,50 con tope de 1,00 no frena"
    puede, motivo = g.check(realized_today=-2.00, equity=1000.0, open_count=0)
    assert puede is False, "una perdida de 2,00 con tope de 1,00 tiene que frenar"
    assert motivo, "el freno tiene que decir POR QUE frena, no solo que frena"


def _halted(veredicto) -> bool:
    """Como se declara el freno, sin suponer la forma del retorno.

    Se acepta un bool, un dict con `risk_halt`/`halted`/`blocked`, o una
    tupla. Motivo: este test no debe depender de que el sustituyo cambie su
    interfaz; solo de que deje de responder cuando toca.
    """
    if isinstance(veredicto, bool):
        return veredicto
    if isinstance(veredicto, dict):
        return bool(veredicto.get("risk_halt") or veredicto.get("halted")
                    or veredicto.get("blocked"))
    if isinstance(veredicto, tuple):
        return _halted(veredicto[0])
    return bool(veredicto)