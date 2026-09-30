"""
PERSISTENCIA DE LA BASE DE HIPOTESIS (2026-09-30)

El fallo que estos tests fijan: `HypothesisKnowledgeBase` era un STUB EN
MEMORIA. `store_hypothesis()` solo hacia

    self.hypotheses.append(hypothesis)

y NUNCA escribia en disco. Con el brazo corriendo eso significaba:

  - `ml-prior` reportaba `registros=0` en CADA arranque
  - `generadas=0` en CADA ciclo
  - el fichero `runtime/hypotheses_<sesion>.jsonl` no se creaba
  - la lista en RAM crecia 2-3 hipotesis por ciclo SIN LIMITE

Es decir: el sistema PARECIA funcionar (log limpio, "Created hypothesis"
en pantalla, cero errores) y en realidad no guardaba nada. Peor: lo
perdia todo al reiniciar, luego no podia aprender entre sesiones.

Ademas habia DOS almacenes distintos, y por eso a veces guardaba y a
veces no:

  - el motor (`DecisionEngine._kb`) pasaba el DIRECTORIO de `kb_path`, de
    modo que sus realimentaciones caian en `runtime/hypotheses.jsonl`
    (0 bytes) en vez de en el fichero de su sesion;
  - el ResearchManager recibia la ruta por defecto
    `autonomous_research/data/hypotheses`, no `config.kb_path`.

Los tres ya apuntan al mismo fichero, y estos tests son la red que lo
impide volver a romper.
"""

import json
import os
import tempfile

import pytest

from quant_math.autonomous_research.adapters.knowledge_manager_stub import (
    HypothesisKnowledgeBase,
)


class _Hip:
    """Hipotesis minima con la interfaz que espera `store_hypothesis`."""

    def __init__(self, hid, symbol="XRP/USDT", status="backtested",
                 expectancy=0.1):
        self.hypothesis_id = hid
        self.symbol = symbol
        self.status = status
        self.expectancy = expectancy

    def to_dict(self):
        return {"hypothesis_id": self.hypothesis_id, "symbol": self.symbol,
                "status": self.status, "expectancy": self.expectancy,
                "scientific_score": 0.5}


def _kb(tmpdir, name="kb.jsonl"):
    return HypothesisKnowledgeBase(storage_path=os.path.join(tmpdir, name))


# ---------------------------------------------------------------------------
# 1) ESCRIBE. Este es el test que falla contra el stub en memoria.
# ---------------------------------------------------------------------------

def test_store_hypothesis_escribe_en_disco(tmp_path):
    """`store_hypothesis()` tiene que CREAR el fichero y hacer que crezca.

    Con el stub en memoria no habia ninguna escritura, asi que el fichero
    no existia. Este es el test que distingue una base de una lista.
    """
    ruta = str(tmp_path / "kb.jsonl")
    kb = HypothesisKnowledgeBase(storage_path=ruta)
    assert not os.path.exists(ruta), "no deberia existir antes de guardar"

    kb.store_hypothesis(_Hip("h1"))

    assert os.path.exists(ruta), "store_hypothesis no creo el fichero"
    assert os.path.getsize(ruta) > 0, "el fichero quedo vacio"
    with open(ruta, encoding="utf-8") as fh:
        filas = [json.loads(l) for l in fh if l.strip()]
    assert len(filas) == 1
    assert filas[0]["hypothesis_id"] == "h1"
    assert filas[0]["symbol"] == "XRP/USDT"


# ---------------------------------------------------------------------------
# 2) SUPERVIVENCIA ENTRE PROCESOS. El bug de "no persistia" en estado puro.
# ---------------------------------------------------------------------------

def test_una_instancia_nueva_lee_lo_que_escribio_otra(tmp_path):
    """Lo que importa NO es que guarde, sino que sobreviva al reinicio.

    Una base que solo vive mientras el proceso dura parece que funciona
    y no sirve para nada: el aprendizaje se pierde en cada arranque.
    """
    ruta = str(tmp_path / "kb.jsonl")
    kb1 = HypothesisKnowledgeBase(storage_path=ruta)
    for i in range(3):
        kb1.store_hypothesis(_Hip(f"h{i}"))

    kb2 = HypothesisKnowledgeBase(storage_path=ruta)   # proceso "nuevo"

    assert kb2._total == 3, "la segunda instancia no vio lo que escribio la primera"
    assert sorted(kb2.hypotheses) == ["h0", "h1", "h2"]
    rec = kb2.retrieve_hypothesis("h1")
    assert rec is not None, "no encuentra una hipotesis que existe"
    assert rec["symbol"] == "XRP/USDT"


# ---------------------------------------------------------------------------
# 3) FALLO DE ESCRITURA: se dice, no se finge.
# ---------------------------------------------------------------------------

def test_si_no_se_puede_escribir_no_se_finge_que_se_guardo(tmp_path):
    """Un fallo de disco tiene que PROPAGARSE.

    Tragaselo es lo peor: el sistema sigue como si la hipotesis estuviera
    guardada, la usa para decidir, y al reiniciar resulta que nunca
    existio. Medido: con el stub, todos los fallos de disco eran
    invisibles.

    OJO con COMO se provoca el fallo: `chmod 0o500` no sirve porque las
    pruebas corren como ROOT, y root ignora los permisos de escritura. Un
    test que parece cubrir el caso y en realidad no lo cubre es peor que
    no tenerlo. Aqui se hace que el DIRECTORIO padre sea un FICHERO, que
    es un fallo que root tampoco puede esquivar.
    """
    fichero = tmp_path / "no_es_un_directorio"
    fichero.write_text("soy un fichero, no una carpeta", encoding="utf-8")
    # La KB quiere crear `no_es_un_directorio/hb.jsonl`; `makedirs` falla
    # porque hay un fichero donde deberia haber un directorio.
    kb = HypothesisKnowledgeBase(storage_path=str(fichero / "kb.jsonl"))
    with pytest.raises(OSError):
        kb.store_hypothesis(_Hip("h1"))


# ---------------------------------------------------------------------------
# 4) INDICE EN RAM ACOTADO, JSONL INTACTO
# ---------------------------------------------------------------------------

def test_el_indice_se_recorta_pero_el_jsonl_conserva_todo(tmp_path, monkeypatch):
    """La fuga lenta: la lista crecia sin limite en RAM.

    Con el tope bajo se comprueba rapido. Lo que importa es que recortar el
    indice NO borre datos: el JSONL es la fuente de verdad y el indice es
    solo lo que vive en memoria.
    """
    ruta = str(tmp_path / "kb.jsonl")
    kb = HypothesisKnowledgeBase(storage_path=ruta)
    monkeypatch.setattr(HypothesisKnowledgeBase, "MAX_INDEX", 10)

    for i in range(25):
        kb.store_hypothesis(_Hip(f"h{i:02d}"))

    assert len(kb._index) <= 10, "el indice en RAM no se acoto"
    with open(ruta, encoding="utf-8") as fh:
        filas = [l for l in fh if l.strip()]
    assert len(filas) == 25, f"se perdieron hipotesis: {len(filas)} de 25"
    # Y desde disco se siguen viendo todas:
    assert len(kb.load_records()) == 25


# ---------------------------------------------------------------------------
# 5) NORMALIZACION DE RUTA
# ---------------------------------------------------------------------------

def test_un_directorio_no_se_confunde_con_un_fichero(tmp_path):
    """Pasarle el DIRECTORIO es un error facil y silencioso.

    Es justo lo que hacia el motor: `os.path.dirname(kb_path)`. Como
    todas las sesiones comparten `runtime/`, el motor escribia sus
    realimentaciones en `runtime/hypotheses.jsonl` (0 bytes) en vez de en
    el fichero de su sesion.
    """
    sub = tmp_path / "runtime"
    sub.mkdir()
    kb = HypothesisKnowledgeBase(storage_path=str(sub))
    kb.store_hypothesis(_Hip("h1"))
    # Debe haber creado un fichero DENTRO, no haber escrito en el sitio
    # equivocado.
    assert kb.kb_path == os.path.join(str(sub), "hypotheses.jsonl")
    assert os.path.isfile(kb.kb_path)


def test_una_ruta_con_extension_se_respeta(tmp_path):
    """Si ya es un fichero, no se le cambia el nombre."""
    ruta = str(tmp_path / "mi_base.jsonl")
    kb = HypothesisKnowledgeBase(storage_path=ruta)
    assert kb.kb_path == ruta


# ---------------------------------------------------------------------------
# 6) TRES PUNTOS DE LA KB TIENEN QUE APUNTAR AL MISMO FICHERO
#
# Es el bug que hacia que el sistema "funcionara" guardando en un sitio y
# leyendo en otro. Un test de cada pieza no lo habria cazado.
# ---------------------------------------------------------------------------

def test_las_tres_rutas_de_la_kb_coinciden():
    """Orquestador, ResearchManager y motor, al mismo fichero.

    MEDIDO el 2026-09-30: el motor pasaba `os.path.dirname(kb_path)` y el
    ResearchManager se quedaba con su ruta por defecto. Dos almacenes, y
    por eso `registros=0` y `generadas=0` en cada arranque con el log
    limpio.
    """
    import inspect
    from quant_math.orchestrator import Orchestrator, OrchestratorConfig
    from quant_math.decision_engine import DecisionEngine

    src_orq = inspect.getsource(Orchestrator._build_runner)
    assert "knowledge_base_path=self.config.kb_path" in src_orq, (
        "el AQDERunner debe recibir config.kb_path; si no, guarda en su "
        "ruta por defecto y nadie lo lee")

    src_motor = inspect.getsource(DecisionEngine.__init__)
    # No vale pasar el directorio: `os.path.dirname` fue el bug.
    assert "storage_path=os.path.dirname(kb_path)" not in src_motor, (
        "el motor vuelve a pasar el DIRECTORIO: con varias sesiones eso "
        "vuelve a mandar las realimentaciones a hypotheses.jsonl (0 bytes)")
    assert "HypothesisKnowledgeBase(storage_path=kb_path)" in src_motor
