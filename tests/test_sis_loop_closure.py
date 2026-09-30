"""Correccion 4 (2026-09-29): el lazo de autoaprendizaje cerrado.

Lo que cubre, y por que:

1. Multi-libro (`feature_store.ledger_globs`): antes el dataset leia UN
   fichero, el del `state_dir` de la sesion. Los cierres de las otras
   sesiones no contaban y una limpieza dejaba el contador a cero.
2. Dos umbrales: la tabla regimen x familia se activa con
   `MIN_ROWS_ACTIVE` (10) y el KMeans sigue exigiendo `MIN_ROWS` (30),
   porque degradan distinto. MIN_ROWS=30 esta MEDIDO (no elegido):
   ver tests de umbral mas abajo y tools/calibrate_min_rows_kmeans.py.
2b. Filtro de significacion de los clusters (permutacion, alpha): un
   dataset cuyo win-rate no dependa del grupo no produce clusters.
3. La etiqueta (pnl/motivo) ya no entra en el vector de clustering.
4. Regimen hostil: criterio explicito de 3 condiciones y fail-open.
5. El aprendizaje entra en la GENERACION via `HypothesisPrior.family_prior`
   y con prior vacio el orden es byte a byte el de antes (regresion B3).

Todos los tests son offline y deterministicos: ni red ni ficheros de
`runtime/` reales.
"""

import json
import os
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.core.types import StrategyType
from quant_math.ml import feature_store as fs
from quant_math.ml.families import FAMILIES, family_of
from quant_math.ml.hypothesis_prior import HypothesisPrior
from quant_math.ml.regime_learning import (
    CLUSTER_ALPHA,
    CLUSTER_PERM,
    MIN_CELL,
    MIN_ROWS,
    MIN_ROWS_ACTIVE,
    OperationLearningLoop,
    _cluster_pvalue,
)


# ------------------------------------------------------------------ helpers
def write_ledger(state_dir, rows):
    """rows: (exit_time, symbol, family, pnl_pct, vol, forecast_up)."""
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "paper_executions.jsonl")
    kb_path = os.path.join(state_dir, "kb.jsonl")
    with open(path, "a", encoding="utf-8") as fh, \
         open(kb_path, "a", encoding="utf-8") as kfh:
        for i, (exit_time, sym, fam, pnl_pct, vol, fu) in enumerate(rows):
            hid = f"hyp_{fam}_{sym.split('/')[0]}_{int(exit_time)}_{i}"
            kfh.write(json.dumps({
                "hypothesis_id": hid, "symbol": sym,
                "strategy_type": fam,
                "parameters": {"donchian_window": 20,
                               "_regime": {"vol_pct": vol,
                                           "forecast_up": bool(fu) if fu is not None else None}}},
                ensure_ascii=False) + "\n")
            fh.write(json.dumps({
                "type": "closure", "key": f"{hid}:{sym}",
                "hypothesis_id": hid, "symbol": sym, "side": "buy",
                "entry_price": 100,
                "exit_price": 100 * (1 + pnl_pct / 100),
                "quantity": 1.0, "pnl": pnl_pct, "pnl_pct": pnl_pct,
                "entry_time": exit_time - 60, "exit_time": exit_time,
                "motivo_cierre": "tp" if pnl_pct > 0 else "sl"},
                ensure_ascii=False) + "\n")


def load_kb(state_dir):
    kb_path = os.path.join(state_dir, "kb.jsonl")
    records = {}
    if os.path.exists(kb_path):
        with open(kb_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    records[r["hypothesis_id"]] = r
    return records


def build_loop(state_dir):
    return OperationLearningLoop(
        load_kb(state_dir),
        os.path.join(state_dir, "paper_executions.jsonl"),
        state_dir)


def make_rows(n, fam="breakout", sym="BTC/USDT", pnl=1.0, vol=80,
              fu=True, t0=1787500000):
    return [(t0 + i * 120, sym, fam, pnl if i % 2 else pnl, vol, fu)
            for i in range(n)]


# ------------------------------------------------- 1) multi-libro / durabilidad
def test_ledgers_from_sibling_state_dirs_are_agregated():
    """Los cierres de OTRAS sesiones cuentan: el dataset era particionado."""
    with tempfile.TemporaryDirectory() as tmp:
        a = os.path.join(tmp, "state_classic-xrp")
        b = os.path.join(tmp, "state_burst")
        write_ledger(a, make_rows(6, fam="breakout"))
        write_ledger(b, make_rows(6, fam="momentum", sym="ETH/USDT",
                                  pnl=-1.0, vol=20, fu=False))
        globs = fs.ledger_globs(a)
        assert len(globs) == 2, globs
        rows = fs.build_trade_dataset(load_kb(a),
                                      os.path.join(a, "paper_executions.jsonl"),
                                      a)
        assert len(rows) == 12, f"solo {len(rows)} de 12 cierres visibles"
        fams = {r["strategy_type"] for r in rows}
        assert fams == {"breakout", "momentum"}
    print("PASS multi-libro: los cierres de las 2 sesiones cuentan (12/12)")


def test_same_closure_in_archive_is_not_double_counted():
    """Un cierre archivado por la limpieza y a la vez vivo no cuenta dos veces."""
    with tempfile.TemporaryDirectory() as tmp:
        a = os.path.join(tmp, "state_classic-btc")
        rows = make_rows(4)
        write_ledger(a, rows)
        # la limpieza copia el libro al archivo y lo deja a cero...
        arch = os.path.join(tmp, "archive", "clean_20260903_124621")
        os.makedirs(arch, exist_ok=True)
        with open(os.path.join(a, "paper_executions.jsonl"),
                  encoding="utf-8") as fh:
            content = fh.read()
        with open(os.path.join(arch, "state__paper_executions.jsonl"),
                  "w", encoding="utf-8") as fh:
            fh.write(content)
        # ...y aqui volvemos a escribir el mismo cierre en el libro vivo
        # (misma key y mismo exit_time -> identico).
        n_live = fs.build_trade_dataset(load_kb(a),
                                        os.path.join(a, "paper_executions.jsonl"), a)
        assert len(n_live) == 4, len(n_live)
        with open(os.path.join(a, "paper_executions.jsonl"),
                  "a", encoding="utf-8") as fh:
            fh.write(content)
        n_dup = fs.build_trade_dataset(load_kb(a),
                                       os.path.join(a, "paper_executions.jsonl"), a)
        assert len(n_dup) == 4, f"dedup fallo: {len(n_dup)} != 4"
    print("PASS dedup: libro vivo + archivo = 4 cierres, no 8")


def test_ledger_globs_can_be_disabled(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        a = os.path.join(tmp, "state_classic-doge")
        b = os.path.join(tmp, "state_burst")
        write_ledger(a, make_rows(3))
        write_ledger(b, make_rows(3, sym="ETH/USDT"))
        monkeypatch.setenv("QUANTMATH_SIS_LEDGERS", "off")
        assert fs.ledger_globs(a) == [os.path.join(a, "paper_executions.jsonl")]
        monkeypatch.delenv("QUANTMATH_SIS_LEDGERS")
        assert len(fs.ledger_globs(a)) == 2
    print("PASS QUANTMATH_SIS_LEDGERS=off -> solo el libro propio")


# ------------------------------------------------- 2) dos umbrales, no uno
def test_activation_threshold_is_10_not_30():
    """10 cierres activan la TABLA; 30 siguen siendo el umbral del KMeans."""
    assert MIN_ROWS_ACTIVE == 10, MIN_ROWS_ACTIVE
    assert MIN_ROWS == 30, MIN_ROWS
    assert MIN_ROWS_ACTIVE < MIN_ROWS
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_burst")
        write_ledger(st, make_rows(MIN_ROWS_ACTIVE))
        loop = build_loop(st)
        assert loop.mode == "active", "10 cierres deberian activar la tabla"
        assert loop.cluster_ready is False, "el KMeans NO deberia correr aun"
        assert loop.cluster_stats == []
        assert loop.labels is None
        fams = loop.rank_families("BTC/USDT", {"vol_pct": 80})
        assert fams and fams[0] == "breakout"
    print(f"PASS umbral: {MIN_ROWS_ACTIVE} cierres -> tabla activa, KMeans "
          f"diferido hasta {MIN_ROWS}")


def test_cluster_runs_at_30_and_label_columns_are_out():
    """A partir de 30 corre el KMeans y la matriz NO lleva la etiqueta."""
    import sklearn.cluster as skc
    captured = {}

    # Se DELEGA en el KMeans real: con el filtro de silueta (SIL_MIN) un
    # KMeans falso de etiquetas alternas no tiene estructura y el propio
    # modulo lo rechazaria. La captura de la forma se mantiene.
    class _CapturingKMeans(skc.KMeans):
        def fit(self, X, y=None, sample_weight=None):
            captured["shape"] = X.shape
            return super().fit(X, y, sample_weight)

    original = skc.KMeans
    skc.KMeans = _CapturingKMeans
    try:
        with tempfile.TemporaryDirectory() as tmp:
            st = os.path.join(tmp, "state_burst")
            rows = make_rows(15, pnl=1.0) + make_rows(15, fam="mean_reversion",
                                                      sym="ETH/USDT", pnl=-1.0,
                                                      vol=15, fu=False,
                                                      t0=1787600000)
            write_ledger(st, rows)
            loop = build_loop(st)
            assert loop.mode == "active" and loop.cluster_ready
            assert "shape" in captured, "KMeans no se invoco"
            n_cols_total = len(__import__(
                "quant_math.ml.feature_store", fromlist=["encode_row"]
            ).encode_row(loop.rows[0]))
            assert captured["shape"][1] == n_cols_total - 2, (
                f"entran {captured['shape'][1]} columnas: la etiqueta "
                f"(pnl/motivo) sigue dentro del clustering")
            assert loop.cluster_stats
            assert loop.cluster_pvalue <= CLUSTER_ALPHA, (
                f"p={loop.cluster_pvalue} > {CLUSTER_ALPHA}: el grupo "
                f"bueno y el malo no deberian ser distinguibles del ruido")
    finally:
        skc.KMeans = original
    print(f"PASS clustering: {MIN_ROWS} cierres -> KMeans con "
          f"{captured['shape'][1]} columnas (2 de etiqueta fuera), "
          f"p={loop.cluster_pvalue:.4f}")


def test_cluster_gate_rejects_groups_that_do_not_predict_the_outcome():
    """Dos grupos de features limpios pero con el MISMO win-rate: sin cluster.

    Es justo el caso que el filtro tiene que rechazar: el KMeans separa
    perfectamente los dos contextos (silueta altisima), pero el win-rate
    es el mismo en los dos, asi que el `cluster_stats` que saldria del
    log diria dos cosas distintas de dos cosas iguales.
    """
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_burst")
        rows = []
        for i in range(MIN_ROWS):
            # mitad alta vol/forecast con 8 ganancias de 15...
            if i < MIN_ROWS // 2:
                rows.append((1787500000 + i * 120, "BTC/USDT", "breakout",
                             1.0 if i % 2 == 0 else -1.0, 80, True))
            # ...y mitad baja vol/forecast con 7 de 15: mismos grupos,
            # win-rate casi identico (0.533 vs 0.467).
            else:
                j = i - MIN_ROWS // 2
                rows.append((1787500000 + i * 120, "ETH/USDT", "momentum",
                             1.0 if j % 2 == 1 else -1.0, 10, False))
        write_ledger(st, rows)
        loop = build_loop(st)
        assert loop.mode == "active", "la TABLA debe seguir activa"
        assert loop.cluster_ready is False, (
            "dos grupos con el mismo win-rate no deben producir clusters")
        assert loop.labels is None
        assert loop.cluster_stats == []
        assert loop.cluster_pvalue is not None
        assert loop.cluster_pvalue > CLUSTER_ALPHA, loop.cluster_pvalue
        assert loop.summary()["cluster_ready"] is False
        # el filtro solo toca el clustering: la tabla sigue ordenando
        assert loop.rank_families("BTC/USDT", {"vol_pct": 80})
    print(f"PASS gate: p={loop.cluster_pvalue:.3f} > {CLUSTER_ALPHA} "
          f"-> sin clusters, tabla activa")


def test_cluster_pvalue_is_deterministic_and_honests_its_alpha():
    """Mismo dataset -> mismo p-valor (los tests exigen determinismo)."""
    rng = np.random.default_rng(7)
    labels = rng.integers(0, 2, 40)
    pnls = np.where(rng.random(40) < 0.5, 1.0, -1.0)
    a = _cluster_pvalue(labels, pnls)
    b = _cluster_pvalue(labels, pnls)
    assert a == b, f"no determinista: {a} != {b}"
    assert 0.0 < a <= 1.0, a
    # piso: con CLUSTER_PERM permutaciones el menor p posible es 1/(N+1)
    assert a >= 1.0 / (CLUSTER_PERM + 1.0) - 1e-12, a
    # sin estructura de win-rate (todo el mismo pnl) no hay diferencia
    assert _cluster_pvalue(labels, np.ones(40)) == 1.0
    print(f"PASS determinismo: p={a:.4f} >= 1/{CLUSTER_PERM + 1} "
          f"(alpha={CLUSTER_ALPHA})")


# ------------------------------------------------- 3) regimen: ventanas y hostilidad
def _hostile_fixture(tmp, n_momentum, n_breakout=6):
    st = os.path.join(tmp, "state_classic-xrp-2x100")
    rows = make_rows(n_breakout, fam="breakout", pnl=+1.0, vol=80, fu=True)
    rows += make_rows(n_momentum, fam="momentum", pnl=-1.0, vol=80, fu=True,
                      t0=1787600000)
    write_ledger(st, rows)
    return build_loop(st), st


def test_hostile_regime_demotes_but_never_excludes():
    with tempfile.TemporaryDirectory() as tmp:
        loop, st = _hostile_fixture(tmp, n_momentum=MIN_CELL + 1)
        assert loop.mode == "active"
        hostile = loop.hostile_families("BTC/USDT", {"vol_pct": 80,
                                                      "forecast_up": True})
        assert hostile == ["momentum"], hostile
        fams = loop.rank_families("BTC/USDT", {"vol_pct": 80,
                                               "forecast_up": True})
        assert fams.index("breakout") < fams.index("momentum"), fams
        # pausada, NO excluida: sigue en la lista (los slots de exploracion
        # la pueden volver a coger; sacarla del todo cerraria el bucle).
        assert "momentum" in fams
        # la familia hostil SÍ entra en el prior con su win-rate bajo,
        # para que la generacion la penalice, no la ignore.
        prior = loop.family_prior("BTC/USDT", {"vol_pct": 80,
                                               "forecast_up": True})
        assert prior["momentum"][0] < prior["breakout"][0]
    print("PASS regimen hostil: momentum (6/6 perdidas) al final, no fuera")


def test_hostile_fails_open_without_enough_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        loop, st = _hostile_fixture(tmp, n_momentum=MIN_CELL - 1)
        assert loop.mode == "active"
        # sin MIN_CELL cierres no hay veredicto: la familia NO se declara
        # hostil aunque sus unicas 4 operaciones sean perdedoras.
        hostile = loop.hostile_families("BTC/USDT", {"vol_pct": 80,
                                                      "forecast_up": True})
        assert hostile == [], hostile
        fams = loop.rank_families("BTC/USDT", {"vol_pct": 80,
                                               "forecast_up": True})
        assert "momentum" in fams
    print("PASS fail-open: <MIN_CELL cierres -> sin veredicto de hostilidad")


def test_regime_window_changes_the_family_order():
    """La misma familia gana en una ventana y pierde en otra -> cambia el orden."""
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_burst")
        # ventana de ALTA vol: breakout gana, mean_reversion pierde
        rows = make_rows(6, fam="breakout", pnl=+2.0, vol=85, fu=True)
        rows += make_rows(6, fam="mean_reversion", pnl=-2.0, vol=85, fu=True,
                          t0=1787600000)
        # ventana de BAJA vol: al reves
        rows += make_rows(6, fam="breakout", pnl=-2.0, vol=15, fu=False,
                          t0=1787700000)
        rows += make_rows(6, fam="mean_reversion", pnl=+2.0, vol=15, fu=False,
                          t0=1787800000)
        write_ledger(st, rows)
        loop = build_loop(st)
        assert loop.mode == "active"
        hi = loop.rank_families("BTC/USDT", {"vol_pct": 85, "forecast_up": True})
        lo = loop.rank_families("BTC/USDT", {"vol_pct": 15, "forecast_up": False})
        assert hi[0] == "breakout" and lo[0] == "mean_reversion", (hi, lo)
        # y el prior que llega a la generacion refleja la ventana
        p_hi = loop.family_prior("BTC/USDT", {"vol_pct": 85, "forecast_up": True})
        p_lo = loop.family_prior("BTC/USDT", {"vol_pct": 15, "forecast_up": False})
        assert p_hi["breakout"][0] > p_hi["mean_reversion"][0]
        assert p_lo["mean_reversion"][0] > p_lo["breakout"][0]
    print("PASS ventanas: orden de familias distinto en vol-alta vs vol-baja")


# ------------------------------- 4) el aprendizaje entra en la GENERACION
def _kb_records(n_pos, n_neg):
    """KB con tasa base ~igual para las dos familias (el SIS desempata)."""
    out = []
    for i in range(n_pos):
        out.append({"strategy_type": "breakout", "symbol": "BTC/USDT",
                    "expectancy": 0.4})
        out.append({"strategy_type": "mean_reversion", "symbol": "BTC/USDT",
                    "expectancy": 0.4})
    for i in range(n_neg):
        out.append({"strategy_type": "breakout", "symbol": "BTC/USDT",
                    "expectancy": -0.4})
        out.append({"strategy_type": "mean_reversion", "symbol": "BTC/USDT",
                    "expectancy": -0.4})
    return out


def _templates():
    return [
        {"name": "MR_1", "strategy_type": "mean_reversion",
         "parameters": {"rsi_period": 14, "symbol": "BTC/USDT"}},
        {"name": "BRK_2", "strategy_type": "breakout",
         "parameters": {"donchian_window": 20, "symbol": "BTC/USDT"}},
        {"name": "MR_3", "strategy_type": "mean_reversion",
         "parameters": {"bb_period": 20, "symbol": "BTC/USDT"}},
        {"name": "BRK_4", "strategy_type": "breakout",
         "parameters": {"donchian_window": 30, "symbol": "BTC/USDT"}},
    ]


def test_family_prior_changes_what_is_generated():
    """EL bucle: sin aprendizaje el orden es el original; con el, cambia."""
    # MIN_TOTAL=100: con 80 registros el prior del KB sigue en
    # "collecting" y rank_templates no reordena NUNCA, con o sin SIS.
    # 120 registros -> modo active, que es donde el cable puede notarse.
    recs = _kb_records(30, 30)   # base identica para las dos familias
    tpls = _templates()
    before, _ = HypothesisPrior(recs).rank_templates(list(tpls), "BTC/USDT", 4)
    assert [t["name"] for t in before] == [t["name"] for t in tpls]

    # el SIS ha medido: breakout gana en esta ventana, mean_reversion pierde
    learned = HypothesisPrior(
        recs, family_prior={"breakout": (0.90, 12),
                            "mean_reversion": (0.15, 12)})
    after, info = learned.rank_templates(list(tpls), "BTC/USDT", 4)
    assert [t["name"] for t in after] != [t["name"] for t in tpls], \
        "el aprendizaje no cambio NADA en la generacion"
    assert after[0]["strategy_type"] == "breakout"
    assert info["family_prior"] != {}
    assert info["family_prior_max_w"] > 0.5
    assert HypothesisPrior(recs).family_weight("breakout") == 0.0
    print(f"PASS bucle: orden ANTES={[t['name'] for t in before]} "
          f"DESPUES={[t['name'] for t in after]} (w={info['family_prior_max_w']})")


def test_empty_family_prior_is_a_noop():
    """Con el SIS en `collecting` el prior del KB se comporta EXACTAMENTE
    como antes de existir el acople (regresion B3)."""
    recs = _kb_records(55, 5)   # 120 -> prior del KB en modo active
    tpls = _templates()
    plain, i1 = HypothesisPrior(recs).rank_templates(list(tpls), "BTC/USDT", 2)
    wired, i2 = HypothesisPrior(recs, family_prior={}).rank_templates(
        list(tpls), "BTC/USDT", 2)
    assert [t["name"] for t in plain] == [t["name"] for t in wired]
    assert i1["reordered"] == i2["reordered"]
    assert i2["family_prior_max_w"] == 0.0
    print("PASS noop: prior de familia vacio -> mismo orden que antes")


def test_family_vocabulary_matches_between_sis_and_prior():
    """Cruce REAL: las claves que el SIS EMITE son las que el prior BUSCA.

    La version anterior de este test solo llamaba a `family_of()` con
    cadenas escritas a mano: verificaba la funcion, no el cable, y por eso
    no detecto que el SIS emitia claves hoja (`vwap_reversion`) o en
    mayusculas (`MEAN_REVERSION`) mientras el consumidor buscaba
    `mean_reversion`. Aqui se cruzan de verdad las DOS mitades:

      emitidas  = claves que sale de `OperationLearningLoop.family_prior`;
      buscadas  = `family_of(...)` sobre lo que una PLANTILLA puede llevar
                  (enum, cadena de enum o familia canonica).

    Toda clave emitida tiene que ser alcanzable por una busqueda: si no,
    el `.get()` del consumidor devuelve `None` y w=0.
    """
    # formas en las que el KB puede traer strategy_type en produccion
    formas_sis = ["mean_reversion", "StrategyType.MEAN_REVERSION",
                  "MEAN_REVERSION", "vwap_reversion"]
    # formas que una plantilla lleva (aqde_runner: enum; tests: cadena)
    plantillas = ["mean_reversion", StrategyType.MEAN_REVERSION,
                  "StrategyType.MEAN_REVERSION", "donchian_breakout"]
    buscadas = {family_of(p) for p in plantillas}
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_forms")
        rows = []
        for j, forma in enumerate(formas_sis):
            rows += make_rows(6, fam=forma, pnl=+1.0, vol=80, fu=True,
                              t0=1787500000 + j * 100000)
        write_ledger(st, rows)
        loop = build_loop(st)
        assert loop.mode == "active", loop.mode
        emitted = loop.family_prior("BTC/USDT",
                                    {"vol_pct": 80, "forecast_up": True})
        assert emitted, "el SIS no emitio prior"
        fuera = sorted(set(emitted) - buscadas)
        assert not fuera, (
            "claves EMITIDAS que el consumidor NUNCA busca: %s "
            "(emitidas=%s, buscadas=%s)" % (fuera, sorted(emitted),
                                             sorted(buscadas)))
        # y al reves: cada clave emitida pondera una plantilla de esa familia
        prior = HypothesisPrior([], family_prior=emitted)
        for p in plantillas[:-1]:          # las formas de mean_reversion
            assert prior.family_weight(p) > 0.0, (p, emitted)
    assert family_of("donchian_breakout") == "breakout"
    print("PASS vocabulario cruce: emitidas=%s buscadas=%s" %
          (sorted(emitted), sorted(buscadas)))


def test_collecting_loop_supplies_empty_prior():
    """Un SIS en `collecting` no puede inyectar nada (y no debe)."""
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_burst")
        write_ledger(st, make_rows(MIN_ROWS_ACTIVE - 1))
        loop = build_loop(st)
        assert loop.mode == "collecting"
        assert loop.family_prior("BTC/USDT", {"vol_pct": 80}) == {}
        assert loop.rank_families("BTC/USDT", {"vol_pct": 80}) == []
        assert loop.hostile_families("BTC/USDT", {"vol_pct": 80}) == []
        assert loop.should_explore() is False
    print("PASS collecting: sin evidencia -> sin prior, sin orden, sin veto")


NL = chr(10)

# ---------------- 5) dos defectos medidos en la demo (correccion 4b)
def test_hostile_demotion_is_visible_even_with_one_family():
    """La pausa de una familia hostil tiene que notarse en el orden.

    Medido en runtime/f3/d2/demo_lazo.py: si en la ventana solo hay
    evidencia de UNA familia y esa es la hostil, la version anterior la
    dejaba PRIMERA (estaba la unica en la tabla y los fallbacks la
    repetian), o sea que la pausa no existia.
    """
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_only_momentum")
        write_ledger(st, make_rows(10, fam="momentum", pnl=-1.0))
        loop = build_loop(st)
        assert loop.mode == "active"
        reg = {"vol_pct": 80, "forecast_up": True}
        assert loop.hostile_families("BTC/USDT", reg) == ["momentum"],             "momentum con 10 perdidas deberia ser hostil"
        fams = loop.rank_families("BTC/USDT", reg)
        assert fams[-1] == "momentum", fams
        assert "momentum" in fams, "pausada, NO excluida"
        assert fams.index("momentum") > fams.index("breakout")
    print("PASS pausa visible: la familia hostil unica queda ULTIMA, no primera")


def _write_kb(path, st_pos, st_tot, mr_pos, mr_tot, symbol="BTC/USDT"):
    """KB sintetico: controla positive_rate por familia (SIS y prior del KB)."""
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(st_tot):
            fh.write(json.dumps({"hypothesis_id": "kb_m%d" % i,
                                 "strategy_type": "momentum", "symbol": symbol,
                                 "expectancy": 0.4 if i < st_pos else -0.4})
                     + NL)
        for i in range(mr_tot):
            fh.write(json.dumps({"hypothesis_id": "kb_r%d" % i,
                                 "strategy_type": "mean_reversion",
                                 "symbol": symbol,
                                 "expectancy": 0.4 if i < mr_pos else -0.4})
                     + NL)


def _orch(kb_path, state_dir):
    from types import SimpleNamespace
    from quant_math.orchestrator import Orchestrator
    o = Orchestrator.__new__(Orchestrator)
    o.config = SimpleNamespace(kb_path=kb_path, state_dir=state_dir,
                               hypotheses_per_cycle=6)
    o._explore_burst = False
    return o


def _templates4():
    return [
        {"name": "MR_1", "strategy_type": "mean_reversion",
         "parameters": {"rsi_period": 14, "symbol": "BTC/USDT"}},
        {"name": "BRK_1", "strategy_type": "momentum",
         "parameters": {"short_window": 12, "symbol": "BTC/USDT"}},
        {"name": "MR_2", "strategy_type": "mean_reversion",
         "parameters": {"bb_period": 20, "symbol": "BTC/USDT"}},
        {"name": "BRK_2", "strategy_type": "momentum",
         "parameters": {"short_window": 26, "symbol": "BTC/USDT"}},
    ]


def test_rank_hypotheses_changes_with_the_learned_loop():
    """EL LAZO CERRADO en el codigo de produccion.

    0 cierres -> SIS collecting -> el orden es el del prior del KB;
    20 cierres ganadores -> SIS active -> momentum pasa primero.
    Se ejecuta el _rank_hypotheses REAL (no una copia).
    """
    with tempfile.TemporaryDirectory() as tmp:
        empty = os.path.join(tmp, "a", "state_empty")
        sis = os.path.join(tmp, "b", "state_sis")
        kb = os.path.join(tmp, "hypotheses.jsonl")
        _write_kb(kb, 50, 100, 50, 100)          # base IGUAL para las dos
        write_ledger(sis, [(1787500000 + i * 60, "BTC/USDT", "momentum",
                            1.0, 80, True) for i in range(20)])   # 20/20

        o1 = _orch(kb, empty)
        before = [t["name"] for t in o1._rank_hypotheses(_templates4(),
                                                         "BTC/USDT")]
        o2 = _orch(kb, sis)
        after = [t["name"] for t in o2._rank_hypotheses(_templates4(),
                                                        "BTC/USDT")]
        assert before != after, ("el aprendizaje no cambio la generacion: "
                                 "%s" % before)
        assert before[0] == "MR_1", before
        assert after[0] == "BRK_1", after
    print("PASS lazo cerrado: ANTES=%s DESPUES=%s" % (before, after))


def test_family_step_does_not_undo_the_kb_prior_mix():
    """Regresion del defecto medido en la demo (fix D).

    El KB dice que mean_reversion es mejor (0.88 vs 0.12); el SIS mide a
    momentum en la ventana con un win-rate mediocre (0.55) que le pone
    PRIMERO en rank_families. El paso 3 anterior reordenaba por esa lista
    y anulaba la mezcla del paso 2: momentum volvia a salir primero y el
    orden final era el mismo que sin aprendizaje. Ahora el paso 3 solo
    aplica el veto hostil.
    """
    with tempfile.TemporaryDirectory() as tmp:
        empty = os.path.join(tmp, "a", "state_empty")
        sis = os.path.join(tmp, "b", "state_sis")
        kb = os.path.join(tmp, "hypotheses.jsonl")
        _write_kb(kb, 10, 100, 90, 100)          # base: MR 0.88 / MOM 0.12
        rows = [(1787500000 + i * 60, "BTC/USDT", "momentum",
                 1.0 if i < 11 else -1.0, 80, True) for i in range(20)]
        write_ledger(sis, rows)                  # wr = 11/20 = 0.55

        o1 = _orch(kb, empty)
        before = [t["strategy_type"] for t in
                  o1._rank_hypotheses(_templates4(), "BTC/USDT")]
        o2 = _orch(kb, sis)
        after = [t["strategy_type"] for t in
                 o2._rank_hypotheses(_templates4(), "BTC/USDT")]
        assert after[0] == "mean_reversion", (
            "el paso 3 anulo la mezcla del paso 2: %s" % after)
        assert before == after, (before, after)
    print("PASS sin anulacion: el veto hostil no borra la mezcla del KB")


# --------------- 7) LA PRUEBA QUE DECIDE: el prior CAMBIA el score y el rank

def _base_igual(n_pos=60, n_neg=60, symbol="BTC/USDT"):
    """KB del prior con el MISMO positive_rate para momentum y mean_reversion.

    Si la base es igual, cualquier diferencia de score posterior viene del
    aprendizaje del SIS y no del KB (aislamos la variable).
    """
    out = []
    for _ in range(n_pos):
        out.append({"strategy_type": "mean_reversion", "symbol": symbol,
                    "expectancy": 0.4})
        out.append({"strategy_type": "momentum", "symbol": symbol,
                    "expectancy": 0.4})
    for _ in range(n_neg):
        out.append({"strategy_type": "mean_reversion", "symbol": symbol,
                    "expectancy": -0.4})
        out.append({"strategy_type": "momentum", "symbol": symbol,
                    "expectancy": -0.4})
    return out


def _tpl_mom_first():
    """Plantillas a favor de momentum: si nadie las reordena, ganan ellas."""
    return [
        {"name": "MOM_1", "strategy_type": "momentum",
         "parameters": {"short_window": 12, "symbol": "BTC/USDT"}},
        {"name": "MOM_2", "strategy_type": "momentum",
         "parameters": {"short_window": 26, "symbol": "BTC/USDT"}},
        {"name": "MR_1", "strategy_type": "mean_reversion",
         "parameters": {"rsi_period": 14, "symbol": "BTC/USDT"}},
        {"name": "MR_2", "strategy_type": "mean_reversion",
         "parameters": {"bb_period": 20, "symbol": "BTC/USDT"}},
    ]


def test_sis_prior_changes_the_score_and_the_rank():
    """EL LAZO CERRADO: 24 cierres, dos familias, win-rate distinto.

    Reproduccion del corte medido por el Orquestador: el KB del SIS trae
    las HOJAS (`vwap_reversion` -> mean_reversion con 8/12 = 67%, `macd` ->
    momentum con 4/12 = 33%) mientras el consumidor busca la familia
    canonica. Si las claves no casan, `family_weight` devuelve 0.0 y el
    score de las DOS familias es identico con o sin aprendizaje.
    """
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_sis")
        t0 = 1787500000
        rows = [(t0 + i * 60, "BTC/USDT", "vwap_reversion",
                 1.0 if i < 8 else -1.0, 80, True) for i in range(12)]
        rows += [(t0 + 200000 + i * 60, "BTC/USDT", "macd",
                  1.0 if i < 4 else -1.0, 80, True) for i in range(12)]
        write_ledger(st, rows)
        loop = build_loop(st)
        assert loop.mode == "active" and len(loop.rows) == 24, loop.mode
        reg = {"vol_pct": 80, "forecast_up": True}
        fam = loop.family_prior("BTC/USDT", reg)
        assert fam, "el SIS no emitio prior con 24 cierres"
        for k in fam:
            assert k in FAMILIES, (
                "clave NO canonica emitida por el SIS: %r -> el consumidor "
                "la buscara como familia canonica y no existira" % (k,))

        recs = _base_igual()
        base = HypothesisPrior(recs)                       # sin SIS
        con = HypothesisPrior(recs, family_prior=fam)      # con el SIS

        antes = (base.score("mean_reversion", "BTC/USDT"),
                 base.score("momentum", "BTC/USDT"))
        despues = (con.score("mean_reversion", "BTC/USDT"),
                   con.score("momentum", "BTC/USDT"))
        print("\n  score ANTES  (sin SIS): mean_reversion=%.4f momentum=%.4f"
              % antes)
        print("  score DESPUES (con SIS): mean_reversion=%.4f momentum=%.4f"
              % despues)
        print("  family_prior emitido: %s  w(MR)=%.3f w(MOM)=%.3f"
              % ({k: (round(v[0], 3), v[1]) for k, v in fam.items()},
                 con.family_weight("mean_reversion"),
                 con.family_weight("momentum")))

        # 1) el peso del SIS deja de ser cero
        assert con.family_weight("mean_reversion") > 0.0, (
            "w=0: el aprendizaje del SIS no llega al prior")
        assert base.family_weight("mean_reversion") == 0.0
        # 2) el score DE VERDAD se mueve, en el sentido medido por el SIS
        assert despues[0] > antes[0] + 1e-9, (antes, despues)
        assert despues[1] < antes[1] - 1e-9, (antes, despues)
        # 3) y el RANK de las plantillas cambia
        b_ord, _ = base.rank_templates(list(_tpl_mom_first()), "BTC/USDT", 4)
        c_ord, info = con.rank_templates(list(_tpl_mom_first()), "BTC/USDT", 4)
        print("  rank ANTES  = %s" % [t["name"] for t in b_ord])
        print("  rank DESPUES= %s (w_max=%.3f)"
              % ([t["name"] for t in c_ord], info["family_prior_max_w"]))
        assert [t["name"] for t in b_ord] == ["MOM_1", "MOM_2", "MR_1", "MR_2"]
        assert [t["name"] for t in c_ord] == ["MR_1", "MR_2", "MOM_1", "MOM_2"], \
            "el aprendizaje no cambio el orden de generacion"
        # 4) la misma conclusion por el camino de PRODUCCION (_rank_hypotheses)
        kb = os.path.join(tmp, "hypotheses.jsonl")
        _write_kb(kb, 60, 120, 60, 120)
        o = _orch(kb, st)
        e2e = [t["name"] for t in o._rank_hypotheses(list(_tpl_mom_first()),
                                                      "BTC/USDT")]
        print("  _rank_hypotheses PRODUCCION = %s" % e2e)
        assert e2e[0] == "MR_1", e2e
    print("PASS lazo: ANTES score MR=%.4f/MOM=%.4f -> DESPUES MR=%.4f/MOM=%.4f"
          % (antes + despues))


# ---------------------------------- 8) el regimen llega entero al dataset

def test_row_carries_the_regime_from_the_kb():
    """Recorrido KB -> fila: la clave `regime` existia SOLO en el KB.

    `build_trade_dataset` aplanaba el `_regime` a vol_pct/forecast_up/... y
    no dejaba la clave `regime` en la fila, asi que cualquier inspeccion
    (`rows[i].get("regime")`) daba None aunque el KB estuviera bien poblado.
    """
    with tempfile.TemporaryDirectory() as tmp:
        st = os.path.join(tmp, "state_burst")
        write_ledger(st, make_rows(6, vol=85, fu=True))
        rows = fs.build_trade_dataset(load_kb(st),
                                      os.path.join(st, "paper_executions.jsonl"),
                                      st)
        assert rows, "sin filas"
        for r in rows:
            reg = r.get("regime")
            assert isinstance(reg, dict) and reg, (
                "la fila NO trae el regimen del KB: %s" % sorted(r))
            assert reg.get("vol_pct") == 85, reg
            assert reg.get("forecast_up") is True, reg
        # las columnas aplanadas siguen ahi (son las que usa la tabla)
        assert rows[0]["vol_pct"] == 85 and rows[0]["forecast_up"] == 1.0
    print("PASS regimen en fila: KB._regime -> rows[i].regime poblado")


def _write_kb_regime(path, regime, n_pos=60, n_tot=120, symbol="BTC/USDT"):
    """KB con `_regime` en parameters (lo que el model-gen persiste)."""
    with open(path, "w", encoding="utf-8") as fh:
        for fam in ("mean_reversion", "momentum"):
            for i in range(n_tot):
                fh.write(json.dumps({
                    "hypothesis_id": "kb_%s_%d" % (fam, i),
                    "strategy_type": fam, "symbol": symbol,
                    "created_at": 1787500000.0 + i,
                    "expectancy": 0.4 if i < n_pos else -0.4,
                    "parameters": {"symbol": symbol, "_regime": regime}}) + NL)


def test_regimen_vigente_se_recupera_del_kb_si_las_plantillas_no_lo_traen():
    """Sin `_regime` en las plantillas el objetivo era `simbolo|?|?`, que
    casa con TODAS las ventanas: la condicionamiento por ventana no se
    aplicaba y el prior devolvia el agregado de todas ellas.
    """
    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(tmp, "hypotheses.jsonl")
        alta = {"vol_pct": 85, "forecast_up": True, "cycle_len": 20,
                "k_slope": 0.1, "k_noise": 0.4}
        _write_kb_regime(kb, alta)
        o = _orch(kb, os.path.join(tmp, "state_x"))
        # (a) plantillas SIN _regime -> se recupera la ultima ventana del KB
        reg = o._current_regime("BTC/USDT", _templates4())
        assert isinstance(reg, dict) and reg.get("vol_pct") == 85, reg
        # (b) si una plantilla trae _regime, manda ESA (es la vigente)
        tpl_con = [{"name": "MG", "strategy_type": "momentum",
                    "parameters": {"_regime": {"vol_pct": 15,
                                                "forecast_up": False}}}]
        assert o._current_regime("BTC/USDT", tpl_con).get("vol_pct") == 15
        # (c) otro simbolo: no hay regimen -> None (sin forzar)
        assert o._current_regime("ETH/USDT", _templates4()) is None
    print("PASS regimen: plantilla -> KB del simbolo -> None")


def _tpl_mr_first():
    """Plantillas a favor de mean_reversion: sin impulso del SIS van primeras."""
    return [
        {"name": "MR_1", "strategy_type": "mean_reversion",
         "parameters": {"rsi_period": 14, "symbol": "BTC/USDT"}},
        {"name": "MR_2", "strategy_type": "mean_reversion",
         "parameters": {"bb_period": 20, "symbol": "BTC/USDT"}},
        {"name": "MOM_1", "strategy_type": "momentum",
         "parameters": {"short_window": 12, "symbol": "BTC/USDT"}},
        {"name": "MOM_2", "strategy_type": "momentum",
         "parameters": {"short_window": 26, "symbol": "BTC/USDT"}},
    ]


def test_regimen_vigente_hace_discriminar_por_ventana():
    """El end-to-end: momentum gana en la ventana ALTA y pierde en la BAJA.

    Con el regimen vigente = ventana ALTA (la del KB), el prior tiene que
    impulsar a momentum POR DELANTE de mean_reversion; sin regimen (antes)
    el objetivo casaba con las dos ventanas, el win-rate agregado salia
    0.50 y el orden era el de entrada (empate -> orden estable).
    """
    with tempfile.TemporaryDirectory() as tmp:
        sis = os.path.join(tmp, "state_sis")
        kb = os.path.join(tmp, "hypotheses.jsonl")
        rows = make_rows(10, fam="momentum", pnl=+1.0, vol=85, fu=True)
        rows += make_rows(10, fam="momentum", pnl=-1.0, vol=15, fu=False,
                          t0=1787600000)
        write_ledger(sis, rows)
        _write_kb_regime(kb, {"vol_pct": 85, "forecast_up": True,
                              "cycle_len": 20, "k_slope": 0.1,
                              "k_noise": 0.4})
        o = _orch(kb, sis)
        orden = [t["strategy_type"] for t in
                 o._rank_hypotheses(list(_tpl_mr_first()), "BTC/USDT")]
        print("  orden con regimen vigente (ventana ALTA) = %s" % orden)
        assert orden[0] == "momentum", (
            "la ventana vigente no discrimino: %s" % orden)
    print("PASS ventana: el regimen vigente decide que familia sube")
