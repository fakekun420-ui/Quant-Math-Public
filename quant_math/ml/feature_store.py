"""Feature store del aprendizaje no supervisado.

Une el libro permanente de operaciones (paper_executions.jsonl, cierres con
motivo_cierre) con los registros de hipotesis del KB (parametros + contexto
de mercado _regime persistido por el model-gen), produciendo un dataset por
operacion listo para clustering.

Cutoff de integracion: si existe runtime/state/learning_meta.json con
"integration_ts", las operaciones ANTERIORES a ese timestamp se excluyen del
aprendizaje (la base no se contamina con datos pre-integracion). El libro en
si NUNCA se toca: sigue siendo el historial permanente visible.

Multi-libro (correccion 4, 2026-09-29)
--------------------------------------
El dataset se construia desde UN SOLO fichero, el del `state_dir` de la
sesion. Cada modo/simbolo tiene su propio `state_*`, asi que los cierres de
una sesion eran invisibles para la siguiente, y una limpieza de `runtime/`
dejaba el contador a cero. `ledger_globs()` amplia la lectura a los libros
hermanos `state*` y a los archivados por la limpieza, con desduplicacion
por (key, exit_time): la misma cuenta no se dos veces y ninguna se pierde.
Desactivable con QUANTMATH_SIS_LEDGERS=off.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

NUMERIC_PARAM_KEYS = ("donchian_window", "rsi_period", "bb_period",
                      "short_window", "atr_window")


def integration_cutoff(state_dir: str) -> Optional[float]:
    path = os.path.join(state_dir, "learning_meta.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return float(json.load(fh).get("integration_ts") or 0) or None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def set_integration_cutoff(state_dir: str, ts: float):
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "learning_meta.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"integration_ts": ts}, fh)


def read_closures(ledger_path: str,
                  since_ts: Optional[float] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(ledger_path):
        return out
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "motivo_cierre" not in rec:
                continue
            if since_ts and float(rec.get("exit_time") or 0) < since_ts:
                continue
            out.append(rec)
    return out


def ledger_globs(state_dir: str) -> List[str]:
    """Ficheros de libro que alimentan el aprendizaje de `state_dir`.

    Alcance, todo relativo a la carpeta del propio `state_dir`:

      1. el libro de la sesion (`state_dir/paper_executions.jsonl`);
      2. `../state*/paper_executions.jsonl` — los libros de los OTROS
         modos/simbolos: sus cierres tambien son evidencia;
      3. `../archive/*/paper_executions*.jsonl` y
         `../archive/*/state*__paper_executions.jsonl` — lo que la
         limpieza de `runtime/` movio a archivo en vez de destruirlo.

    Los patrones 2 y 3 se anaden solo si la carpeta se llama (o empieza por)
    `state`, de modo que un `state_dir` de test en un tmp aislado no arrastra
    nada. `QUANTMATH_SIS_LEDGERS=off` desactiva 2 y 3 (solo el libro propio).
    """
    own = os.path.join(state_dir, "paper_executions.jsonl")
    out = [own]
    flag = os.environ.get("QUANTMATH_SIS_LEDGERS", "").strip().lower()
    if flag in ("off", "0", "false", "no"):
        return out
    import glob as _glob
    base = os.path.basename(os.path.normpath(state_dir))
    if not base.startswith("state"):
        return out
    parent = os.path.dirname(os.path.normpath(state_dir)) or "."
    found = []
    found += _glob.glob(os.path.join(parent, "state*",
                                     "paper_executions.jsonl"))
    found += _glob.glob(os.path.join(parent, "archive", "*",
                                     "paper_executions*.jsonl"))
    found += _glob.glob(os.path.join(parent, "archive", "*",
                                     "*__paper_executions.jsonl"))
    for f in sorted(set(found)):
        if os.path.abspath(f) != os.path.abspath(own):
            out.append(f)
    return out


def read_all_closures(state_dir: str,
                      since_ts: Optional[float] = None) -> List[Dict[str, Any]]:
    """Cierres de TODOS los libros, desduplicados por (key, exit_time, motivo).

    La desduplicacion es obligatoria: un mismo cierre puede estar a la vez
    en el libro vivo y en un archivo de limpieza. Dos cierres distintos de
    la misma posicion no comparten `exit_time` porque `close_position` usa
    `time.time()` al escribir.
    """
    seen = set()
    out: List[Dict[str, Any]] = []
    for path in ledger_globs(state_dir):
        for rec in read_closures(path, since_ts):
            ident = (rec.get("key"), float(rec.get("exit_time") or 0.0),
                     rec.get("motivo_cierre"))
            if ident in seen:
                continue
            seen.add(ident)
            rec = dict(rec)
            rec["_ledger"] = path
            out.append(rec)
    out.sort(key=lambda r: float(r.get("exit_time") or 0.0))
    return out


def _kb_candidates(ledger_path: str) -> List[str]:
    """Ficheros de hipotesis que corresponden a ESTE libro.

    Convencion medida en runtime/ (2026-09-29, VERIFICADO con ls): el KB de
    un modo vive JUNTO al state_* que lo usa, no dentro de el:

        runtime/state                    -> runtime/hypotheses.jsonl
        runtime/state_burst              -> runtime/hypotheses_burst.jsonl
        runtime/state_classic-xrp-2x100  -> runtime/hypotheses_classic-xrp-2x100.jsonl
        runtime/archive/<limpieza>/      -> hypotheses*.jsonl al lado del libro copiado

    Sin esto los cierres leidos de un libro hermano llegan SIN
    strategy_type ni _regime: la tabla regimen x familia acumularia una
    celda de familia "" que no significa nada. Anade tambien kb.jsonl en la
    propia carpeta (scratch de F3 y tests).
    """
    import glob as _glob
    d = os.path.dirname(os.path.abspath(ledger_path))
    base = os.path.basename(os.path.normpath(d))
    parent = os.path.dirname(d) or "."
    out: List[str] = []
    if base.startswith("state"):
        out.append(os.path.join(parent,
                                "hypotheses%s.jsonl" % base[len("state"):]))
    out.append(os.path.join(d, "kb.jsonl"))
    out += _glob.glob(os.path.join(d, "hypotheses*.jsonl"))
    seen, uniq = set(), []
    for f in out:
        if f not in seen and os.path.exists(f):
            seen.add(f)
            uniq.append(f)
    return uniq


def _load_kb_file(path: str, cache: Dict[str, Dict[str, Any]]
                  ) -> Dict[str, Dict[str, Any]]:
    if path in cache:
        return cache[path]
    recs: Dict[str, Dict[str, Any]] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hid = rec.get("hypothesis_id")
                if hid:
                    recs[hid] = rec
    except OSError:
        pass
    cache[path] = recs
    return recs


def build_trade_dataset(kb_records: Dict[str, Dict[str, Any]],
                        ledger_path: str,
                        state_dir: str) -> List[Dict[str, Any]]:
    """Una fila por cierre post-cutoff, enriquecida con KB + _regime.

    `ledger_path` se conserva por compatibilidad con los llamantes y con los
    tests; la fuente real es `state_dir` (ver `ledger_globs`).
    """
    cutoff = integration_cutoff(state_dir)
    rows: List[Dict[str, Any]] = []
    closures = read_all_closures(state_dir, cutoff)
    if not closures and ledger_path:
        closures = read_closures(ledger_path, cutoff)
    kb_cache: Dict[str, Dict[str, Any]] = {}
    for c in closures:
        hid = c.get("hypothesis_id", "")
        h = kb_records.get(hid) or {}
        if not h:
            # cierre de un libro hermano: su hipotesis vive en OTRO KB
            for cand in _kb_candidates(c.get("_ledger") or ledger_path or ""):
                h = _load_kb_file(cand, kb_cache).get(hid) or {}
                if h:
                    break
        params = h.get("parameters") or {}
        regime = params.get("_regime") or {}
        p_num = next((float(params[k]) for k in NUMERIC_PARAM_KEYS
                      if k in params and params[k] is not None), None)
        fu = regime.get("forecast_up")
        st_raw = h.get("strategy_type")
        st = getattr(st_raw, "value", None) or str(st_raw or "")
        rows.append({
            # copia plana del regimen del KB. Antes solo existian las
            # columnas aplanadas (vol_pct/forecast_up/...) y la clave
            # `regime` NO estaba en la fila: `rows[i].get("regime")` daba
            # None con el KB bien poblado (correccion 4).
            "regime": dict(regime),
            "strategy_type": st.split(".")[-1],
            "symbol": c.get("symbol", ""),
            "motivo": c.get("motivo_cierre", ""),
            "pnl_pct": c.get("pnl_pct"),
            "duration_s": (float(c.get("exit_time") or 0)
                           - float(c.get("entry_time") or 0)),
            "p_window": p_num,
            "vol_pct": regime.get("vol_pct"),
            "forecast_up": (1.0 if fu else 0.0) if fu is not None else None,
            "cycle_len": regime.get("cycle_len"),
            "k_slope": regime.get("k_slope"),
            "k_noise": regime.get("k_noise"),
        })
    return rows


def encode_row(row: Dict[str, Any]) -> List[float]:
    """Vector fijo para clustering; None -> -1.

    La familia se canonica con el vocabulario UNICO (`families`): antes el
    indice se buscaba con un match EXACTO sobre la cadena cruda, asi que una
    hoja (`vwap_reversion`) o `MEAN_REVERSION` codificaba -1, es decir la
    mitad de las filas entraban como "familia desconocida".
    """
    from quant_math.ml.families import family_index
    fam = family_index(row.get("strategy_type"))
    mot = {"tp": 0, "sl": 1}.get(str(row.get("motivo")), 2)

    def num(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return -1.0
        return v
    return [fam, mot, num(row.get("pnl_pct")), num(row.get("p_window")),
            num(row.get("vol_pct")), num(row.get("forecast_up")),
            num(row.get("cycle_len")), num(row.get("k_slope")),
            num(row.get("k_noise"))]


def encode_dataset(rows: List[Dict[str, Any]]) -> List[List[float]]:
    return [encode_row(r) for r in rows]
