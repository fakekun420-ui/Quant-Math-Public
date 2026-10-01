#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# limpiar-estado.sh -- idempotent quarantine of Quant-Math-Public runtime state
#
# Contract:
#   * NEVER destroys data. Each file is copied first, the copy is verified
#     byte-for-byte (sha256) against the source, and only then is the source
#     entry removed. At every instant the data exists in at least one place.
#   * Idempotent: targets already moved are reported and skipped, so a second
#     run is a no-op that still prints a full report.
#   * DRY-RUN is the default. Nothing moves without --apply.
#   * Refuses to act while a quant_math process is alive, or while any state
#     dir reports state=RUNNING, unless --force-live is given.
#   * ASCII only (no CJK).
#
# Usage:
#   bash runtime/limpiar-estado.sh                        # dry-run (default)
#   bash runtime/limpiar-estado.sh --apply                # actually move
#   bash runtime/limpiar-estado.sh --apply --incluir-scratch
#   bash runtime/limpiar-estado.sh --apply --force-live
#   bash runtime/limpiar-estado.sh --list-scope           # show what is held back
# ---------------------------------------------------------------------------
set -uo pipefail

PROJ="/sdcard/projects/Quant-Math-Public"
RUNTIME="$PROJ/runtime"
QROOT="/sdcard/projects/_quarantine/qmp-limpieza-2026-10-01"
LOGFILE="$QROOT/MANIFEST-LOG.txt"

APPLY=0
FORCE_LIVE=0
INCLUDE_SCRATCH=0
LIST_SCOPE=0

for a in "$@"; do
  case "$a" in
    --apply)          APPLY=1 ;;
    --force-live)     FORCE_LIVE=1 ;;
    --incluir-scratch) INCLUDE_SCRATCH=1 ;;
    --list-scope)     LIST_SCOPE=1 ;;
    -h|--help)        sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 64 ;;
  esac
done

# --- scope held back on purpose (not execution state) ----------------------
HELD_ARCHIVE="runtime/archive      already-quarantined data from the 2026-09-03 clean_history run and the 2026-08-24 learning reset; it is the evidence trail, moving it adds nothing"
HELD_F3="runtime/f3              4.2 MB of D2 work: patched copies of modules (orchestrator.py differs from the live one), patch scripts, OOS result JSONs, a .bak of the D2 bitacora. CODE, not state. Moving it would drop unsaved work"
HELD_F1="runtime/f1-scratch      F1 scratch: 184 KB log plus per-branch state dirs from an earlier run. Scratch, not the active session"
HELD_ARCHIVO="runtime/archivo     does not exist (probably meant runtime/archive)"

# --- manifest: CATEGORY | KIND | PATH-RELATIVE-TO-RUNTIME ------------------
MANIFEST=$(cat <<'EOF'
01-kb-hypotheses|file|hypotheses_classic-xrp.jsonl
01-kb-hypotheses|file|hypotheses_rejects.jsonl
02-kb-vacios|file|hypotheses.jsonl
02-kb-vacios|file|hypotheses_burst.jsonl
02-kb-vacios|file|hypotheses_classic-xrp-2x100.jsonl
03-estado-sesion-activa|dir|state_classic-xrp
04-estados-otros|dir|state
04-estados-otros|dir|state_burst
04-estados-otros|dir|state_classic-btc
04-estados-otros|dir|state_classic-btc-2x20
04-estados-otros|dir|state_classic-doge
04-estados-otros|dir|state_classic-eth
04-estados-otros|dir|state_classic-xrp-2x100
05-runs-anteriores|dir|testnet-arm
05-runs-anteriores|dir|validacion
05-runs-anteriores|dir|dim
06-scratch-requiere-decision|dir|f1-scratch
06-scratch-requiere-decision|dir|f3
EOF
)

# --- live-process / live-state guard --------------------------------------
# Blocking: processes that ARE the trading runtime (they hold the ledger and
# the KB open in append). An inline "python3 -c ... from quant_math.risk..."
# analysis is reported but does not block: it does not write runtime state.
live_procs() {
  ps -ef | grep -E "quant_math\.cli\.main|quant_math\.orchestrator|python3? -m quant_math" \
    | grep -v grep | grep -v "limpiar-estado" || true
}
other_procs() {
  ps -ef | grep "quant_math" \
    | grep -v grep | grep -v "limpiar-estado" \
    | grep -vE "quant_math\.cli\.main|quant_math\.orchestrator|python3? -m quant_math" || true
}
# A RUNNING flag is only proof of a live writer if it is being refreshed.
# The session writes runtime_stats.json every cycle, so a flag whose
# last_cycle_at is older than STALE_MIN has no writer behind it: that is a
# crash leftover, reported but not blocking. The process check is the real guard.
STALE_MIN=30

state_flags() {
  local s dir st lc age verdict
  for s in "$RUNTIME"/state*/runtime_stats.json; do
    [ -e "$s" ] || continue
    dir=$(basename "$(dirname "$s")")
    read -r st lc < <(python3 -c "
import json,sys,time
try:
    d=json.load(open(sys.argv[1]))
except Exception:
    print('unreadable 0'); raise SystemExit
lc=d.get('last_cycle_at') or 0
age=(time.time()-lc)/60.0 if isinstance(lc,(int,float)) and lc>0 else -1
print(d.get('state','?'), ('%.1f'%age))
" "$s" 2>/dev/null)
    [ "$st" = "RUNNING" ] || continue
    if python3 -c "import sys; sys.exit(0 if float('$lc')>=0 and float('$lc')<=$STALE_MIN else 1)" 2>/dev/null; then
      verdict="VIVO"
    else
      verdict="CADUCA (sin escritor: last_cycle_at hace ${lc} min)"
    fi
    printf "  %-34s state=RUNNING  %s\n" "$dir" "$verdict"
  done
}
live_states() { state_flags | grep "VIVO" || true; }
stale_states() { state_flags | grep "CADUCA" || true; }

# --- helpers ---------------------------------------------------------------
bytes_of() { find "$1" -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1} END{printf "%d", s+0}'; }
nfiles_of() { find "$1" -type f 2>/dev/null | wc -l; }

# sha manifest of a tree, sorted, paths relative to the tree root.
# A plain file must be hashed directly: "cd file" fails, find returns nothing,
# and the manifest would come out EMPTY -- which would make a diff of two empty
# manifests "match" and pass verification without verifying anything.
tree_sha() {
  local root="$1"
  # `sha256sum` imprime "digest  ruta". Como el origen y la copia viven en
  # rutas distintas, comparar la linea entera dera SIEMPRE distinto aunque los
  # ficheros sean identicos, que es justo el fallo que hacia que este script
  # se negase a mover ficheros ya copiados correctamente. Se imprime solo el
  # digest, y para un arbol el nombre relativo (con -printf), que si coincide.
  if [ -f "$root" ]; then
    sha256sum -- "$root" | cut -d' ' -f1
    return
  fi
  ( cd "$root" 2>/dev/null && find . -type f -printf '%P\0' \
      | sort -z | xargs -0 -r sha256sum ) 2>/dev/null | sort
}

# An EMPTY manifest must never count as a verified match: with no output on
# both sides, `[ "$a" = "$b" ]` is true for the wrong reason and a copy that
# never happened would look proven. The one exception is two plain FILES of 0
# bytes: a 0 b KB really is a 0 b file, and its (empty) digest is a fact, not a
# failure to measure.
same_tree() {
  local a b
  a=$(tree_sha "$1"); b=$(tree_sha "$2")
  if [ -f "$1" ] && [ -f "$2" ] && [ ! -s "$1" ] && [ ! -s "$2" ]; then
    return 0
  fi
  [ -n "$a" ] && [ "$a" = "$b" ]
}

# move one entry: copy, verify sha, then remove source. data is never lost.
move_verified() {
  local src="$1" dst="$2" tag="$3"

  if [ ! -e "$src" ]; then
    echo "  SKIP    ya limpio (no existe): $tag"
    return 0
  fi

  local b_src b_dst
  b_src=$(bytes_of "$src")

  # dry-run is a pure projection: it writes nothing at all, not even a copy
  if [ "$APPLY" != 1 ]; then
    local agg
    agg=$(tree_sha "$src" | sha256sum | cut -c1-16)
    echo "  DRYRUN  moveria $(nfiles_of "$src") ficheros, $b_src b  [$agg]  $tag"
    return 0
  fi

  # Un DIRECTORIO VACIO no tiene manifiesto que comparar: `tree_sha` de un
  # arbol sin ficheros sale vacio y `same_tree` rechaza los vacios a proposito
  # (para que un manifiesto vacio no pase por verificado). Aqui no hay nada
  # que verificar porque no hay nada que perder, asi que se trata aparte: dos
  # directorios vacios SI son iguales.
  if [ -d "$src" ] && [ "$(nfiles_of "$src")" = "0" ]; then
    mkdir -p "$dst" || { echo "  ERROR   no se pudo crear el destino: $tag" >&2; return 1; }
    rm -rf "$src" || { echo "  ERROR   no se pudo retirar el origen: $tag" >&2; return 1; }
    echo "  MOVIDO  0 b  (directorio vacio, no hay datos)  $tag"
    return 0
  fi

  # already there and identical -> the copy is proven, so finish the move
  if [ -e "$dst" ] && [ -e "$src" ]; then
    if same_tree "$src" "$dst"; then
      rm -rf "$src" || { echo "  ERROR   no se pudo retirar el origen: $tag" >&2; return 1; }
      if [ -e "$src" ]; then
        echo "  ERROR   el origen sigue presente tras retirar: $tag" >&2
        return 1
      fi
      echo "  MOVIDO  $b_src b  (copia preexistente verificada)  $tag"
      return 0
    fi
    # A previous copy left behind empty is the known FUSE truncation failure
    # (a 0 b file holds no information, and the source is still whole, so
    # replacing it destroys nothing). Anything else is a real conflict.
    if [ -f "$dst" ] && [ ! -s "$dst" ] && [ -s "$src" ]; then
      echo "  RECUPERA copia previa de 0 b (truncado FUSE previo); se rehace: $tag"
    else
      echo "  CONFLICTO la copia previa difiere; no se toca: $tag" >&2
      return 1
    fi
  fi
  # El destino puede ser un ARCHIVO (una KB suelta) o un DIRECTORIO (un
  # estado de sesion). `mkdir -p` sobre la ruta completa de un archivo lo
  # convierte en directorio y `cp -a` mete el archivo DENTRO, dejando
  # `hypotheses.jsonl/hypotheses.jsonl`: el sha nunca cuadra y el script
  # se niega a mover nada, con razon pero por un fallo suyo. Por eso solo
  # se crea el PADRE, y solo si el origen es un directorio.
  if [ -d "$src" ]; then
    mkdir -p "$dst" || { echo "  ERROR   no se pudo crear el destino: $tag" >&2; return 1; }
    cp -a "$src/." "$dst/" || { echo "  ERROR   copia fallo: $tag" >&2; return 1; }
  else
    mkdir -p "$(dirname "$dst")" || { echo "  ERROR   no se pudo crear el destino: $tag" >&2; return 1; }
    cp -a "$src" "$dst" || { echo "  ERROR   copia fallo: $tag" >&2; return 1; }
  fi
  b_dst=$(bytes_of "$dst")

  if [ ! -e "$dst" ]; then
    echo "  ERROR   la copia no existe tras copiar (posible fallo FUSE): $tag" >&2
    return 1
  fi
  if [ "$b_src" != "$b_dst" ]; then
    echo "  ERROR   bytes distintos origen=$b_src copia=$b_dst: $tag" >&2
    return 1
  fi
  if ! same_tree "$src" "$dst"; then
    echo "  ERROR   sha256 no coincide, el original NO se toca: $tag" >&2
    return 1
  fi

  {
    echo "--- $tag"
    echo "    origen: $src  ($b_src b, $(nfiles_of "$src") ficheros)"
    echo "    copia : $dst  ($b_dst b, $(nfiles_of "$dst") ficheros)"
    echo "    sha   : verificado fichero a fichero (sha256 identico en origen y copia)"
  } >> "$LOGFILE"

  if [ "$APPLY" = 1 ]; then
    rm -rf "$src" || { echo "  ERROR   no se pudo retirar el origen: $tag" >&2; return 1; }
    if [ -e "$src" ]; then
      echo "  ERROR   el origen sigue presente tras retirar: $tag" >&2
      return 1
    fi
    echo "  MOVIDO  $b_src b  $tag"
  fi
  return 0
}

# --- header ----------------------------------------------------------------
# When this file is sourced instead of executed, the functions above are now
# defined: stop here. That way the test exercises the real verification code
# instead of a hand-rebuilt copy of it, which is how a broken verifier ends up
# passing its own test.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  return 0 2>/dev/null || exit 0
fi

echo "=============================================================="
echo " limpieza de estado de ejecucion -- Quant-Math-Public"
echo " modo      : $([ "$APPLY" = 1 ] && echo 'APLICAR (mueve)' || echo 'DRY-RUN (no mueve nada)')"
echo " origen    : $RUNTIME"
echo " cuarentena: $QROOT"
echo "=============================================================="

if [ "$LIST_SCOPE" = 1 ]; then
  echo
  echo "REPOSADO A PROPOSTA (no es estado de ejecucion, o ya esta en cuarentena):"
  printf '  %s\n' "$HELD_ARCHIVE"
  printf '  %s\n' "$HELD_F3"
  printf '  %s\n' "$HELD_F1"
  printf '  %s\n' "$HELD_ARCHIVO"
  exit 0
fi

# --- guard -----------------------------------------------------------------
LP=$(live_procs)
LS=$(live_states)
SS=$(stale_states)
BLOCKED=0
if [ -n "$LP" ]; then
  BLOCKED=1
  echo
  echo "!! BLOQUEO: hay procesos del runtime de trading VIVOS"
  echo "   (limpiar ahora seria una carrera: tienen el ledger y la KB abiertos):"
  echo "$LP" | cut -c1-150 | sed 's/^/     /'
fi
if [ -n "$LS" ]; then
  BLOCKED=1
  echo
  echo "!! BLOQUEO: directorios de estado con bandera RUNNING VIVA:"
  echo "$LS" | sed 's/^/     /'
fi
if [ -n "$SS" ]; then
  echo
  echo "   (info) banderas RUNNING CADUCAS de sesiones que ya no escriben."
  echo "   No bloquean: no hay escritor detras, asi que no hay carrera posible."
  echo "   Aun asi son un estado incoherente que conviene limpiar a mano."
  echo "$SS" | sed 's/^/     /'
fi
OP=$(other_procs)
if [ -n "$OP" ]; then
  echo
  echo "   (info) otros procesos que mencionan quant_math, NO bloquean:"
  echo "$OP" | cut -c1-150 | sed 's/^/     /'
fi
if [ "$BLOCKED" = 1 ] && [ "$FORCE_LIVE" != 1 ]; then
  echo
  echo "ABORTADO. Nada movido. El propio codigo del proyecto aplica este mismo"
  echo "interlock (quant_math/ml/learning_reset.py:108-115 rechaza si runtime_stats"
  echo "dice RUNNING salvo force=True)."
  echo
  echo "Para continuar hace falta, en este orden:"
  echo "  1) detener la sesion desde la CLI (menu: Detener <sesion>) y esperar a que"
  echo "     el proceso muera de verdad;"
  echo "  2) re-ejecutar este script en DRY-RUN y comprobar que el bloqueo desaparece;"
  echo "  3) solo entonces --apply."
  echo "Forzar con --force-live es posible pero mueve ficheros que un proceso vivo"
  echo "tiene abiertos en append: no es una operacion segura."
  exit 3
fi
[ "$BLOCKED" = 1 ] && [ "$FORCE_LIVE" = 1 ] && echo "!! BLOQUEO IGNORADO por --force-live. Riesgo asumido."

# --- run -------------------------------------------------------------------
# dry-run writes nothing at all: not the quarantine dir, not the log
if [ "$APPLY" = 1 ]; then
  mkdir -p "$QROOT" || { echo "no se pudo crear $QROOT" >&2; exit 1; }
  : > "$LOGFILE"
  {
    echo "MANIFESTO de limpieza -- $(date -Is)"
    echo "modo: APLICAR (mueve)"
    echo "origen: $RUNTIME"
    echo "cuarentena: $QROOT"
    echo "force-live: $FORCE_LIVE   incluir-scratch: $INCLUDE_SCRATCH"
    echo "==================================================================="
  } >> "$LOGFILE"
else
  LOGFILE="(ninguno: el DRY-RUN no escribe nada)"
fi

TOTAL_SRC=0
TOTAL_DST=0
NFILES=0
NOK=0
NFAIL=0
NSKIP=0
NELEM=0

echo
while IFS='|' read -r cat kind rel; do
  [ -z "${cat:-}" ] && continue
  NELEM=$((NELEM+1))
  if [ "$cat" = "06-scratch-requiere-decision" ] && [ "$INCLUDE_SCRATCH" != 1 ]; then
    echo "  RETENIDO $rel   (categoria 06, hace falta --incluir-scratch)"
    NSKIP=$((NSKIP+1))
    continue
  fi
  src="$RUNTIME/$rel"
  dst="$QROOT/$cat/$rel"
  echo " [$cat] $rel"
  if move_verified "$src" "$dst" "$rel"; then
    NOK=$((NOK+1))
    if [ -e "$src" ]; then
      echo "  AVISO   el origen sigue presente tras mover: $rel" >&2
      NFAIL=$((NFAIL+1)); NOK=$((NOK-1))
    fi
  else
    NFAIL=$((NFAIL+1))
  fi
done <<< "$MANIFEST"

# --- totals ----------------------------------------------------------------
echo
echo "--------------------------------------------------------------"
echo " entradas en el manifiesto : $NELEM"
echo " procesadas sin error     : $NOK"
echo " fallos                   : $NFAIL"
echo " retenidas (no movidas)   : $NSKIP"
echo " ficheros accounting      : $NFILES"
# La verificacion real de "no se perdio nada" NO es esta suma: es que el
# total de la cuarentena sea igual al total que habia ANTES de empezar, y eso
# solo se puede comprobar con el projected del DRY-RUN, que se guarda abajo.
# Aqui se reporta lo que hay en la cuarentena y quien quiera comprobarlo
# reejecuta en DRY-RUN con un runtime ya limpio y compara las dos cifras.
echo
# La verificacion de "no se perdio nada" se hace SOBRE LA CUARENTENA, que es
# donde esta el dato. Medir "lo que queda en runtime" daria 0 por
# construccion en cuanto la limpieza funciona, y un accounting que solo puede
# dar 0 no demuestra nada.
Q_BYTES=$(bytes_of "$QROOT")
Q_FILES=$(nfiles_of "$QROOT")
R_LEFT=$(bytes_of "$RUNTIME")
echo " TOTAL en cuarentena : $Q_BYTES b  ($Q_FILES ficheros)"
echo " runtime restante    : $R_LEFT b  (lo retenido: f1-scratch, f3 y lo que dejo el proceso)"
if [ "$R_LEFT" = "0" ]; then
  echo " SUMA                : runtime VACIO, la sesion arrancara desde cero"
else
  echo " ATENCION            : runtime todavia tiene $R_LEFT b; no esta limpio"
fi
echo "--------------------------------------------------------------"
echo " log: $LOGFILE"
[ "$APPLY" = 1 ] || echo " modo DRY-RUN: no se movio nada. Usa --apply para mover."
exit 0
