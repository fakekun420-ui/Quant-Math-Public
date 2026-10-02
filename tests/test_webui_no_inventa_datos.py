"""El panel no puede fabricar metricas sin decirlo.

POR QUE
------
MEDIDO el 2026-10-01: `webui/backend/webui/api/routes.py` tiene 29 endpoints,
13 con `# TODO` y 26 con numeros escritos a mano, sin ningun flag de mock.
`/dashboard/active-strategies` devolvia dos estrategias INVENTADAS con
`sharpe: 1.85`, `win_rate: 58.5`, `total_trades: 42` y posiciones con
precios de entrada.

Para quien mira el panel, eso es indistinguible de una medicion. Y en este
proyecto la confusion entre "medido" y "parece medido" ya ha costado una
sesion entera: la KB se lleno de 621 hipotesis sobre una premisa que
resulto falsa.

LO QUE ESTE TEST PROTEGE
------------------------
Que un endpoint con numeros inventados no pueda devolverlos SIN declarar que
son de ejemplo. Un `# TODO` en el codigo no protege: se lee cuando se escribe
el endpoint, no cuando se mira el panel, que es cuando importa.

Como estos endpoints son `async def` que dependen de FastAPI, no se ejecutan
aqui: se comprueba el CODIGO, que es donde el numero inventado nace. Un test
que solo contara `return marcar_mock(` no serviria de nada, porque Bastaria
con que un endpoint tenga el wrapping y otro no.
"""

import ast
import os
import re

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTES = os.path.join(
    RAIZ, "webui", "backend", "webui", "api", "routes.py")

#: Metricas de rendimiento que un panel muestra. Si un endpoint las inventa,
#: tienen que ir marcadas como mock.
METRICAS = (
    "sharpe", "sortino", "win_rate", "total_trades", "profit_factor",
    "max_drawdown", "equity_curve", "pnl", "unrealized_pnl", "expectancy",
    "scientific_score", "current_drawdown", "exposure", "avg_trade",
)


def _arbol():
    with open(ROUTES, encoding="utf-8") as fh:
        return ast.parse(fh.read()), fh


def _src():
    with open(ROUTES, encoding="utf-8") as fh:
        return fh.read()


def test_el_fichero_existe_y_parsea():
    """Si el backend no arranca, todos los tests de este modulo mienten."""
    tree, _fh = _arbol()
    assert tree is not None


def test_existe_una_declaracion_de_mock():
    """Sin el aviso, marcar no sirve de nada.

    Un `data_source: "mock"` sin texto que explique que significa deja al
    usuario descifrando una palabra inglesa.
    """
    src = _src()
    assert "AVISO_DATOS_MOCK" in src, (
        "no hay aviso que explique que los datos son inventados")
    assert "Datos de EJEMPLO" in src or "Datos de ejemplo" in src, (
        "el aviso tiene que decir en claro que no son medidas")


def test_active_strategies_va_marcado():
    """El endpoint concreto que se midio: Sharpe 1,85 y 42 operaciones.

    Tiene su propio test y no depende del recuento generico, porque es el
    caso que se encontrou mirando. La busqueda va por la FUNCION, no por un
    recorte de texto: la primera version cortaba el fichero con `index("def ")`
    y se rompia en cuanto habia otra funcion despues.
    """
    tree = ast.parse(_src())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.AsyncFunctionDef)
               and n.name == "get_active_strategies"), None)
    assert fn is not None, "el endpoint active-strategies ya no existe"
    assert any(isinstance(c, ast.Name) and c.id == "marcar_mock"
               for c in ast.walk(fn)), (
        "/dashboard/active-strategies devuelve estrategias inventadas "
        "(sharpe 1,85, 42 trades) y no declara que son de ejemplo")


def test_ningun_endpoint_inventa_metricas_sin_marcar():
    """El fallo de FORMA: cualquier endpoint con VALORES de metricas, marcado.

    Se recorre el AST y se miran los `return` de cada funcion de endpoint.
    Si un return asigna un valor numerico a una metrica y la funcion no llama
    a `marcar_mock`, el numero sale al panel sin aviso.

    Se excluyen los endpoints que nombran una metrica pero no le dan valor:
    `get_config_sections` declara el ESQUEMA (`{"key": "sharpe",
    "label": "Sharpe Ratio"}`) y un formulario de configuracion tiene que
    poder mencionar el Sharpe sin estar inventando una medida. La primera
    version de este test los marcaba a ellos y era un falso positivo: un
    nombre de campo no es un dato.
    """
    src = _src()
    tree = ast.parse(src)
    metricas = set(METRICAS)
    fallos = []
    for nodo in ast.walk(tree):
        if not isinstance(nodo, ast.AsyncFunctionDef):
            continue
        llama_mock = any(
            isinstance(c, ast.Name) and c.id == "marcar_mock"
            for c in ast.walk(nodo))
        for sub in ast.walk(nodo):
            if not isinstance(sub, ast.Return) or sub.value is None:
                continue
            # Un endpoint puede declarar el origen DENTRO del propio
            # modelo, en vez de llamar a `marcar_mock`. Se acepta si pone
            # `data_source`, que es la misma marca por otra via.
            declara_origen = any(
                isinstance(k, ast.keyword) and k.arg == "data_source"
                for k in ast.walk(sub.value))
            for asig in ast.walk(sub.value):
                # Solo las ASIGNACIONES: "sharpe": 1.85 inventa, pero
                # {"key": "sharpe"} solo describe.
                if not isinstance(asig, ast.keyword):
                    continue
                if not (isinstance(asig.arg, str)
                        and asig.arg in metricas):
                    continue
                if llama_mock or declara_origen:
                    continue
                fallos.append(f"{nodo.name}({asig.arg})")
    assert not fallos, (
        f"estos endpoints devuelven VALORES de metricas de rendimiento SIN "
        f"declarar que son de ejemplo: {sorted(set(fallos))}. O se conectan "
        "al motor, o se envuelven en marcar_mock()")


def test_un_endpoint_nuevo_no_puede_olvidar_la_marca():
    """Control de la REGRESION, mirando la forma del todo.

    Si alguien anade un endpoint con `"sharpe": 2.0` y no llama a
    `marcar_mock`, el test anterior lo caza. Este verifica que ese test
    realmente tiene teeth: comprueba que existe al menos un endpoint marcado
    y que el helper se aplica de verdad, para que "0 fallos" no signifique
    "el test no mira nada".
    """
    src = _src()
    assert "return marcar_mock(" in src, (
        "ningun endpoint usa marcar_mock: o no hay stubs, o el helper existe "
        "pero nadie lo aplica")
    # Y el helper tiene que modificar de verdad, no devolver lo mismo.
    tree = ast.parse(src)
    helper = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)
                   and n.name == "marcar_mock"), None)
    assert helper is not None, "el helper marcar_mock no esta"
    claves = {c.value for n in ast.walk(helper)
              for c in ast.walk(n)
              if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    assert "data_source" in claves, (
        "marcar_mock tiene que anadir data_source, o no marca nada")
    assert "aviso" in claves, (
        "marcar_mock tiene que anadir el aviso, o el marca no se entiende")


def test_los_datos_falsos_no_se_presentan_como_medidos():
    """Que el panel no llame "running" a una estrategia que no existe.

    MEDIDO: el endpoint servia `"status": "running"` con 42 operaciones. Un
    panel que dice "running" es una afirmacion sobre el sistema, y esa
    afirmacion se puede comprobar. Es el mismo criterio que se aplico al MMR
    y a las fases de validacion: lo que no se ha medido no se afirma.
    """
    src = _src()
    # "running" puede seguir apareciendo, pero solo dentro de algo marcado.
    for m in re.finditer(r'"status":\s*"(\w+)"', src):
        contexto = src[max(0, m.start() - 4000):m.start()]
        if "marcar_mock(" in contexto:
            continue
        pytest.fail(
            f'"status": "{m.group(1)}" aparece fuera de un bloque marcado como '
            "mock: es una afirmacion sobre el sistema sin respaldo")
