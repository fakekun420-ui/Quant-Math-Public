"""
Knowledge base used by `QuantMathAdapter` (and therefore by the
`ResearchManager` that creates hypotheses).

Was a pure in-memory stub: `store_hypothesis()` appended to a list and
nothing ever touched the disk. MEDIDO el 2026-09-30 con the system
running: the generated hypotheses never reached the JSONL that the engine
reads, so `ml-prior` reported `registros=0` on every startup and
`generadas=0` on every cycle. The system kept regenerating the same
candidates, discarding them as duplicates and never learning anything.

It was ALSO a slow leak: a list that grows 2-3 hypotheses per cycle, for
as long as the process lives, never freed.

This version persists to the SAME JSONL file the engine uses, and keeps
only an index in memory (ids, not whole records) so the search interface
keeps working without holding every hypothesis in RAM.

The public interface is unchanged on purpose: `QuantMathAdapter` and
`ResearchManager` import `HypothesisKnowledgeBase` from here and must keep
working as-is.
"""

import json
import os
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class SearchCriteria:
    """Criterios de busqueda (mismo contrato que antes)."""
    strategy_type: Optional[str] = None
    status: Optional[str] = None
    min_win_rate: Optional[float] = None
    min_sharpe_ratio: Optional[float] = None


class HypothesisKnowledgeBase:
    """Base de hipotesis persistente en JSONL, con indice en memoria.

    `storage_path` se acepta como ruta de FICHERO (lo que le pasa el
    orquestador: `config.kb_path`). Si por lo que sea llega un
    directorio, se le anade `hypotheses.jsonl` para no escribir un
    fichero dentro de un directorio por error.
    """

    #: Un solo cerrojo por fichero. El motor corre en un hilo y el CLI en
    #: otro, y dos escrituras a la vez en JSONL se corrompen.
    _locks: Dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    #: Tope del indice en memoria. Es un indice (id -> resumen), no los
    #: registros enteros: 50.000 son unos pocos MB. Sin tope, un proceso
    #: de dias acumularia el historique entero en RAM.
    MAX_INDEX = 50_000

    def __init__(self, storage_path: str = "autonomous_research/data/hypotheses"):
        self.storage_path = storage_path
        self._path = self._resolve_path(storage_path)
        #: indice id -> resumen (NO el registro entero)
        self._index: Dict[str, Dict[str, Any]] = {}
        #: numero total, para poder recortar el indice sin perder la cuenta
        self._total = 0
        self._lock = self._lock_for(self._path)
        self._load_index()
        print(f"[HypothesisKnowledgeBase] JSONL persistente kb={self._path} "
              f"({self._total} hipotesis)")

    # ------------------------------------------------------------------
    # infrastructure
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_path(path: str) -> str:
        """Normaliza a un fichero JSONL.

        Si `path` es un directorio existente, se le anade el nombre por
        defecto: escribir un fichero de hipotesis dentro de un directorio
        por error es facil y silencioso.
        """
        ruta = str(path)
        if os.path.isdir(ruta):
            return os.path.join(ruta, "hypotheses.jsonl")
        if ruta.endswith(("/", os.sep)):
            return os.path.join(ruta, "hypotheses.jsonl")
        if not ruta.endswith(".jsonl"):
            return ruta + ".jsonl"
        return ruta

    @classmethod
    def _lock_for(cls, path: str) -> threading.Lock:
        with cls._locks_guard:
            if path not in cls._locks:
                cls._locks[path] = threading.Lock()
            return cls._locks[path]

    def _load_index(self) -> None:
        """Lee el fichero una vez al arrancar y se queda con el indice."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    hid = rec.get("hypothesis_id")
                    if not hid:
                        continue
                    self._index[hid] = {
                        "hypothesis_id": hid,
                        "symbol": rec.get("symbol"),
                        "status": rec.get("status"),
                        "strategy_type": rec.get("strategy_type"),
                        "expectancy": rec.get("expectancy"),
                        "scientific_score": rec.get("scientific_score"),
                    }
                    self._total += 1
        except OSError:
            # No se puede leer: se sigue vacio, pero se DICE. Un indice
            # vacio sin aviso hace que el sistema regenerate en bucle
            # creyendo que ya lo ha probado todo.
            print(f"[HypothesisKnowledgeBase] AVISO: no se pudo leer "
                  f"{self._path}; se empieza con el indice vacio")

    # ------------------------------------------------------------------
    # interfaz publica
    # ------------------------------------------------------------------
    @property
    def kb_path(self) -> str:
        """Ruta real del JSONL (la que lee el motor)."""
        return self._path

    @property
    def hypotheses(self) -> List[Any]:
        """Lista de ids, en orden de aparicion.

        Antes era una lista de objetos. Ahora devuelve los ids para no
        sostener todo el historico en RAM; quien necesite los registros
        usa `load_records()`.
        """
        return list(self._index.keys())

    def load_records(self) -> List[Dict[str, Any]]:
        """Todos los registros, LEIDOS DE DISCO en este momento."""
        out: List[Dict[str, Any]] = []
        if not os.path.exists(self._path):
            return out
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return out
        return out

    def store_hypothesis(self, hypothesis) -> str:
        """ESCRIBE en el JSONL. Antes solo append a una lista en RAM."""
        hid = getattr(hypothesis, "hypothesis_id", None)
        if not hid:
            hid = f"hyp_{len(self._index) + 1:04d}"
        rec = hypothesis.to_dict() if hasattr(hypothesis, "to_dict") else dict(
            hypothesis) if isinstance(hypothesis, dict) else {
                "hypothesis_id": hid}
        rec["hypothesis_id"] = hid
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False,
                                        default=str) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
        except OSError as exc:
            # Si no se puede guardar, NO se finge que se guardo: la
            # hipotesis se perderia y el sistema no tendria memoria de
            # haberla probado nunca.
            print(f"[HypothesisKnowledgeBase] ERROR al guardar {hid} en "
                  f"{self._path}: {exc}. La hipotesis NO quedara guardada.")
            raise
        self._index[hid] = {
            "hypothesis_id": hid,
            "symbol": rec.get("symbol"),
            "status": rec.get("status"),
            "strategy_type": rec.get("strategy_type"),
            "expectancy": rec.get("expectancy"),
            "scientific_score": rec.get("scientific_score"),
        }
        self._total += 1
        self._recortar_indice()
        return hid

    def _recortar_indice(self) -> None:
        """Si el indice pasa del tope, se avisa.

        No se recortan datos: el JSONL es la fuente de verdad y se puede
        releer. Lo que se acota es lo que vive en RAM.
        """
        if len(self._index) <= self.MAX_INDEX:
            return
        exceso = len(self._index) - self.MAX_INDEX
        for hid in list(self._index)[:exceso]:
            self._index.pop(hid, None)
        print(f"[HypothesisKnowledgeBase] indice recortado a "
              f"{self.MAX_INDEX} en RAM; el JSONL sigue con todo "
              f"({self._total} hipótesis)")

    def retrieve_hypothesis(self, hypothesis_id: str):
        """Busca en DISCO, no en memoria."""
        for rec in self.load_records():
            if rec.get("hypothesis_id") == hypothesis_id:
                return rec
        return None

    def search_hypotheses(self, criteria: Any) -> List[Dict[str, Any]]:
        st = getattr(criteria, "strategy_type", None) or (
            criteria.get("strategy_type") if isinstance(criteria, dict) else None)
        status = getattr(criteria, "status", None) or (
            criteria.get("status") if isinstance(criteria, dict) else None)
        out = []
        for rec in self.load_records():
            if st and rec.get("strategy_type") != st:
                continue
            if status and rec.get("status") != status:
                continue
            out.append(rec)
        return out

    def search_hypotheses_by_text(self, query: str,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        q = (query or "").lower()
        out = [r for r in self.load_records()
               if q in json.dumps(r, default=str).lower()]
        return out[:limit]

    def search_similar_hypotheses(self, description: str,
                                  threshold: float = 0.7) -> List[Dict[str, Any]]:
        q = (description or "").lower()
        return [r for r in self.load_records()
                if q and q in str(r.get("description", "")).lower()]

    def search_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        return [r for r in self.load_records() if r.get("symbol") == symbol]

    def update_hypothesis(self, hypothesis_id: str,
                          updates: Dict[str, Any]) -> bool:
        """Reescribe el fichero. Es lo unico correcto: el JSONL es
        append-only por historial, pero una hipotesis que cambia de estado
        (`backtested` -> `failed`) tiene que reflectirse."""
        with self._lock:
            records = self.load_records()
            cambiada = False
            for rec in records:
                if rec.get("hypothesis_id") == hypothesis_id:
                    rec.update(updates)
                    cambiada = True
            if not cambiada:
                return False
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(rec, ensure_ascii=False,
                                        default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path)
        self._index.pop(hypothesis_id, None)
        self._index[hypothesis_id] = {
            "hypothesis_id": hypothesis_id,
            "symbol": updates.get("symbol"),
            "status": updates.get("status"),
        }
        return True

    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        with self._lock:
            records = [r for r in self.load_records()
                       if r.get("hypothesis_id") != hypothesis_id]
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(rec, ensure_ascii=False,
                                        default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path)
        self._index.pop(hypothesis_id, None)
        return True

    def get_statistics(self) -> Dict[str, Any]:
        records = self.load_records()
        by_status: Dict[str, int] = {}
        for r in records:
            k = str(r.get("status") or "unknown")
            by_status[k] = by_status.get(k, 0) + 1
        return {"total": len(records), "by_status": by_status,
                "path": self._path}

    def get_hypothesis_timeline(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        return [r for r in self.load_records()
                if r.get("hypothesis_id") == hypothesis_id]

    def export_hypotheses(self, output_path: str) -> Dict[str, Any]:
        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with self._lock:
                with open(output_path, "w", encoding="utf-8") as fh:
                    for rec in self.load_records():
                        fh.write(json.dumps(rec, ensure_ascii=False,
                                            default=str) + "\n")
            return {"ok": True, "path": output_path}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def import_hypotheses(self, input_path: str) -> int:
        if not os.path.exists(input_path):
            return 0
        n = 0
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as fh:
                with open(input_path, "r", encoding="utf-8") as src:
                    for line in src:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        fh.write(json.dumps(rec, ensure_ascii=False,
                                            default=str) + "\n")
                        hid = rec.get("hypothesis_id")
                        if hid:
                            self._index[hid] = {
                                "hypothesis_id": hid,
                                "symbol": rec.get("symbol"),
                                "status": rec.get("status"),
                            }
                            self._total += 1
                        n += 1
        return n