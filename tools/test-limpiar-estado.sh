#!/usr/bin/env bash
# Test of the verification primitives used by runtime/limpiar-estado.sh.
# A guard that is only declared protects nothing, so this exercises the real
# functions with positive and negative controls.
set -uo pipefail

SRC="/sdcard/projects/Quant-Math-Public/tools/limpiar-estado.sh"
FAILS=0

# Source the real script: it returns right after the constants when sourced,
# so the functions under test are the actual ones and not a rebuilt copy.
# shellcheck disable=SC1090
source "$SRC"

check() {  # check <description> <expected true|false> <actual>
  if [ "$2" = "$3" ]; then
    printf "  OK    %-58s -> %s\n" "$1" "$3"
  else
    printf "  FALLA %-58s -> %s (se esperaba %s)\n" "$1" "$3" "$2"
    FAILS=$((FAILS+1))
  fi
}

R=/sdcard/projects/Quant-Math-Public/runtime
# Los datos de prueba se toman de la CUARENTENA, no de `runtime/`: la
# limpieza ya se aplico y en `runtime/` ya no hay nada. Un test que apunta a
# los ficheros que su propia prueba acaba de mover no mide el codigo, mide que
# el test esta roto: por eso se leen de donde los datos siguen existiendo.
Q=/sdcard/projects/_quarantine/qmp-limpieza-2026-10-01
A="$Q/01-kb-hypotheses/hypotheses_rejects.jsonl"
B="$Q/01-kb-hypotheses/hypotheses_classic-xrp.jsonl"
DIR_A="$Q/03-estado-sesion-activa/state_classic-xrp"
DIR_B="$Q/04-estados-otros/testnet-arm"
if [ ! -s "$A" ] || [ ! -s "$B" ] || [ ! -d "$DIR_A" ]; then
  echo "FALTAN los datos de prueba en la cuarentena ($A / $DIR_A)."
  echo "Sin ellos este test no puede afirmar nada: sale 2, no 0."
  exit 2
fi

echo "=== control positivo: un fichero consigo mismo SI es el mismo ==="
same_tree "$A" "$A" && r=true || r=false
check "same_tree(A, A)" true "$r"

echo "=== control negativo: dos ficheros distintos NO son el mismo ==="
same_tree "$A" "$B" && r=true || r=false
check "same_tree(A, B)" false "$r"

echo "=== control negativo: manifiesto vacio NO puede pasar como identico ==="
# a genuinely empty directory, so the manifest really is empty
rm -rf /tmp/qmp_empty && mkdir -p /tmp/qmp_empty
same_tree /tmp/qmp_empty /tmp/qmp_empty && r=true || r=false
check "same_tree(directorio vacio, si mismo)" false "$r"
rm -rf /tmp/qmp_empty

echo "=== un directorio de verdad: consigo mismo si, consigo mismo truncado no ==="
same_tree "$DIR_A" "$DIR_A" && r=true || r=false
check "same_tree(state_classic-xrp, si mismo)" true "$r"
same_tree "$DIR_A" "$DIR_B" && r=true || r=false
check "same_tree(xrp, testnet-arm)" false "$r"

echo "=== TRUNCADO REAL: se parte una copia y el detector tiene que verlo ==="
rm -rf /tmp/qmp_t && mkdir -p /tmp/qmp_t/a /tmp/qmp_t/b
cp "$A" /tmp/qmp_t/a/f.jsonl
cp "$A" /tmp/qmp_t/b/f.jsonl
same_tree /tmp/qmp_t/a /tmp/qmp_t/b && r=true || r=false
check "copia integra vs copia integra" true "$r"
# truncate the copy the way FUSE does, keeping the name
head -c 100 "$A" > /tmp/qmp_t/b/f.jsonl
same_tree /tmp/qmp_t/a /tmp/qmp_t/b && r=true || r=false
check "copia integra vs copia TRUNCADA" false "$r"
# and one byte short
cp "$A" /tmp/qmp_t/b/f.jsonl
truncate -s $(( $(wc -c < /tmp/qmp_t/b/f.jsonl) - 1 )) /tmp/qmp_t/b/f.jsonl
same_tree /tmp/qmp_t/a /tmp/qmp_t/b && r=true || r=false
check "copia integra vs copia a 1 byte menos" false "$r"

echo "=== bytes_of / nfiles_of sobre datos reales ==="
check "bytes_of(hypotheses_rejects.jsonl)" 106812 "$(bytes_of "$A")"
check "nfiles_of(state_classic-xrp)" 9 "$(nfiles_of "$DIR_A")"

echo "=== control POSITIVO del fallo que se corrigio: rutas distintas, mismo contenido ==="
# Se eligio el destino por ruta, asi que origen y copia NUNCA comparten
# nombre de ruta. Si `tree_sha` imprimiera "digest  ruta" en vez del digest
# solo, `same_tree` entre dos ficheros identicos en rutas distintas daria
# falso, y el script se negaria a mover ficheros ya copiados bien. Este test
# falla contra esa version, que es exactamente lo que hacia.
rm -rf /tmp/qmp_r && mkdir -p /tmp/qmp_r/origen /tmp/qmp_r/copia
cp "$A" /tmp/qmp_r/origen/hypotheses.jsonl
cp "$A" /tmp/qmp_r/copia/hypotheses.jsonl
same_tree /tmp/qmp_r/origen/hypotheses.jsonl /tmp/qmp_r/copia/hypotheses.jsonl && r=true || r=false
check "mismo fichero, RUTAS DISTINTAS" true "$r"
rm -rf /tmp/qmp_r

echo "=== dos ficheros VACIOS si son iguales (un KB de 0 b es un hecho) ==="
rm -rf /tmp/qmp_z && mkdir -p /tmp/qmp_z
: > /tmp/qmp_z/a; : > /tmp/qmp_z/b
same_tree /tmp/qmp_z/a /tmp/qmp_z/b && r=true || r=false
check "vacio vs vacio" true "$r"
rm -rf /tmp/qmp_z

echo "=== control negativo: vacio vs con contenido NO puede pasar ==="
rm -rf /tmp/qmp_z && mkdir -p /tmp/qmp_z
: > /tmp/qmp_z/a; printf 'datos' > /tmp/qmp_z/b
same_tree /tmp/qmp_z/a /tmp/qmp_z/b && r=true || r=false
check "vacio vs con contenido" false "$r"
rm -rf /tmp/qmp_z

rm -rf /tmp/qmp_t
echo
echo "fallos: $FAILS"
[ "$FAILS" = 0 ] || exit 2
echo "todas las comprobaciones pasan"
exit 0
