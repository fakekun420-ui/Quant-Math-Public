"""Calibracion de MIN_ROWS (umbral del KMeans) y del filtro de silueta.

Versionada a proposito: quant_math/ml/regime_learning.py cita este
fichero como evidencia, y una cita a un script inexistente no es
evidencia (asi salio el bug de la cita a runtime/f3/d2/calibra.py,
2026-09-29, que aducia VERIFICADO un script que no estaba en disco).

Pregunta: con cuantas filas deja de ser artefacto el clustering, y hace
falta ademas filtrar la salida con la silueta?

Metodo (offline, sin red, semilla fija, R repeticiones x 2 corrientes de
semilla, para que un numero no dependa de UNA semilla):
  * Mismo pipeline que regime_learning._fit: contexto SIN las 2 columnas
    de etiqueta, StandardScaler y KMeans(n_clusters=max(2,min(4,n//25)),
    n_init=10, random_state=0).
  * Dos poblaciones:
      NULO     - contexto y pnl iid: TODO separamiento entre clusters es
                 falso.
      ESTRUCT. - dos grupos de contexto reales con win-rate 0.65 (grupo
                 bueno, etiqueta 0) y 0.35 (grupo malo, etiqueta 1):
                 efecto verdadero delta_WR = 0.30.
  * Medidas:
      fp30     - nulo: % de corridas en las que el separamiento de
                 win-rate entre clusters alcanza 0.30 (el efecto
                 verdadero). Es lo que cuesta NO filtrar.
      pasa25   - % de corridas que pasarian el filtro sil>=0.25: en el
                 nulo es tasa de falso positivo, en el estructurado es
                 potencia.
      orden    - estructurado: % de corridas en las que el cluster de
                 mayor PnL medio es mayoritariamente el grupo bueno.
      degen    - % de corridas con algun cluster de win-rate 0 o 1
                 (cluster residual de 1-2 filas; MIN_CELL=5).

CRITERIO (y el motivo de cada umbral):
  1) pasa25(nulo) <= 1.0%  - el filtro deja pasar como mucho 1 de cada
     100 datasets sin estructura. 1% es una decision a priori (un orden
     de magnitud por debajo del 5% convencional) y aqui se verifica.
  2) pasa25(estructurado) >= 95% - el filtro no descarta estructura real.
  3) degen(nulo) <= 5%     - sin clusters residuales de 1-2 filas.
  4) orden >= 90%          - el cluster bueno se identifica.
Y el veredicto de un n es "CUMPLE" solo si LO CUMPLEN LAS DOS
corrientes de semilla: un umbral que cambia de semilla no es un umbral.

Historia de la medicion (para no repetir el error):
  * El primer criterio probado, fp30 <= 5% sin filtro, es un
    estadistico de orden extremo y cruza segun la semilla: n=40 daba
    4.0% con R=200 y 6.2-8.0% con R=500 y otra corriente. Ese cruce no
    sostiene un numero.
  * El segundo, sil_max(nulo) < 0.25 (ningun nulo pasa jamas), tambien
    depende del maximo observado: 0.236 en una corriente y 0.276 en
    otra, ambas con n=30. Por eso el umbral es una TASA, no un maximo.
  * El docstring viejo decia que con n<30 el win_rate por cluster "sale
    0 o 1 por construccion": FALSO, medido (degen 6.4-9.0% con n=15,
    0.6% con n=20, 0.0-0.2% con n=24 y 0.0% con n=30).
  * Sin filtro, en n=30 el ruido imita el efecto verdadero en el 12.4%
    de los datasets: por eso el filtro no es opcional.

Uso:  /usr/bin/python3 tools/calibrate_min_rows_kmeans.py
(Sin dependencias nuevas: numpy y sklearn ya son del proyecto.)
"""
import os
import sys

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.getcwd())   # para importar quant_math al lanzarlo
from quant_math.ml.regime_learning import (  # noqa: E402
    CLUSTER_ALPHA, CLUSTER_PERM, _cluster_pvalue)

SEED = 20260929
R = 300
STREAMS = (0, 1000)      # dos corrientes de semilla
SIZES = [15, 20, 24, 30, 40]
SIL_MIN = 0.25
MAX_FP_PCT = 1.0         # tasa maxima de falso positivo del filtro
MIN_POT_PCT = 95.0       # potencia minima del filtro
MAX_DEGEN_PCT = 5.0      # clusters residuales de 1-2 filas
MIN_ORDEN_PCT = 90.0     # el cluster bueno se identifica
WR_BUENO, WR_MALO = 0.65, 0.35


def kmeans_n(x):
    """Misma formula que regime_learning._fit."""
    return max(2, min(4, x // 25))


def _contexto(rng, n):
    """Columnas de CONTEXTO (feature_store.encode_row sin la etiqueta).

    [0]=familia, [1]=p_window, [2]=vol_pct, [3]=forecast_up,
    [4]=cycle_len, [5]=k_slope, [6]=k_noise
    """
    return np.column_stack([
        rng.integers(0, 4, n), rng.choice([10, 14, 20, 26], n),
        rng.uniform(0, 100, n), rng.integers(0, 2, n),
        rng.uniform(10, 120, n), rng.normal(0, 0.1, n),
        rng.uniform(0, 1, n)])


def gen(n, structured, rng, wr_bueno=WR_BUENO, wr_malo=WR_MALO):
    """(X_contexto, pnl, etiqueta_real): 0 = grupo bueno, 1 = grupo malo."""
    X = _contexto(rng, n)
    if not structured:
        pnl = np.where(rng.random(n) < 0.5, 1.0, -1.0)
        return X, pnl, np.zeros(n, dtype=int)
    half = n // 2
    X[:half, 2] = rng.uniform(70, 100, half)
    X[:half, 3] = 1
    X[:half, 4] = rng.uniform(10, 40, half)
    X[half:, 2] = rng.uniform(0, 30, n - half)
    X[half:, 3] = 0
    X[half:, 4] = rng.uniform(60, 120, n - half)
    pnl = np.empty(n)
    pnl[:half] = np.where(rng.random(half) < wr_bueno, 1.0, -1.0)
    pnl[half:] = np.where(rng.random(n - half) < wr_malo, 1.0, -1.0)
    truth = np.zeros(n, dtype=int)
    truth[half:] = 1
    return X, pnl, truth


def run(n, structured, stream):
    rng = np.random.default_rng(SEED + stream + n * 11 + int(structured))
    k = kmeans_n(n)
    sils, seps, aris = [], [], []
    degen = ok = 0
    for _ in range(R):
        X, pnl, truth = gen(n, structured, rng)
        Xs = StandardScaler().fit_transform(X)
        lab = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Xs)
        wr = np.array([float((pnl[lab == c] > 0).mean()) for c in range(k)])
        seps.append(float(wr.max() - wr.min()))
        sils.append(float(silhouette_score(Xs, lab)))
        if bool((wr == 0.0).any() or (wr == 1.0).any()):
            degen += 1
        if structured:
            aris.append(float(adjusted_rand_score(truth, lab)))
            med = np.array([float(pnl[lab == c].mean()) for c in range(k)])
            if float((truth[lab == int(np.argmax(med))] == 0).mean()) >= 0.5:
                ok += 1
    s = np.array(sils)
    return {
        'n': n, 'k': k, 'stream': stream, 'reps': R,
        'sil_p50': round(float(np.percentile(s, 50)), 3),
        'pasa25_pct': round(100.0 * float((s >= SIL_MIN).mean()), 1),
        'sil_max': round(float(s.max()), 3),
        'sil_min': round(float(s.min()), 3),
        'fp30_pct': round(100.0 * float((np.array(seps) >= 0.30).mean()), 1),
        'degen_pct': round(100.0 * degen / R, 1),
        'orden_ok_pct': (round(100.0 * ok / R, 1) if structured else None),
        'ari_med': (round(float(np.median(aris)), 3) if structured else None),
    }


def cumple(nu, es):
    """Los cuatro umbrales (ver docstring). es=None en escenario nulo."""
    if nu['pasa25_pct'] > MAX_FP_PCT or nu['degen_pct'] > MAX_DEGEN_PCT:
        return False
    if es is None:
        return True
    return (es['pasa25_pct'] >= MIN_POT_PCT
            and es['orden_ok_pct'] >= MIN_ORDEN_PCT)


def x_producto(rng, n):
    """Contexto con la FORMA del ledger real: solo 3 columnas varian.

    familia categorica (0..3), vol_pct continuo y forecast_up binario;
    p_window/cycle_len/k_slope/k_noise constantes (escalan a 0). Mide
    como queda la silueta nula con esta forma, que es la que importa.
    """
    return np.column_stack([rng.integers(0, 4, n), np.full(n, 20.0),
                            rng.uniform(0, 100, n), rng.integers(0, 2, n),
                            np.full(n, 60.0), np.zeros(n), np.zeros(n)])


def gate_stats(n, scenario):
    """% de datasets en los que el filtro de permutacion deja el cluster.

    scenario: 'nulo' (nada que encontrar), 'delta30' (el efecto de la
    poblacion estructurada, 0.65 vs 0.35) o 'delta60' (efecto grande,
    0.80 vs 0.20). Se mide la potencia en los dos tamanos: un p-valor con
    30 muestras detecta mal un efecto de 0.30 y eso hay que decirlo.
    """
    if scenario == 'nulo':
        structured, wb, wm = False, WR_BUENO, WR_MALO
    elif scenario == 'delta60':
        structured, wb, wm = True, 0.80, 0.20
    else:
        structured, wb, wm = True, WR_BUENO, WR_MALO
    rng = np.random.default_rng(SEED + 777 + n * 3 + int(structured)
                                + (11 if scenario == 'delta60' else 0))
    k = kmeans_n(n)
    pasa = 0
    for _ in range(R):
        X, pnl, _truth = gen(n, structured, rng, wb, wm)
        Xs = StandardScaler().fit_transform(X)
        lab = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Xs)
        if _cluster_pvalue(lab, pnl) <= CLUSTER_ALPHA:
            pasa += 1
    return round(100.0 * pasa / R, 1)


def sil_forma_producto(n):
    """Silueta nula con la forma del ledger real (por que NO se usa)."""
    rng = np.random.default_rng(SEED + 555 + n)
    vals = []
    for _ in range(R):
        X = x_producto(rng, n)
        Xs = StandardScaler().fit_transform(X)
        lab = KMeans(n_clusters=2, n_init=10, random_state=0).fit_predict(Xs)
        vals.append(float(silhouette_score(Xs, lab)))
    v = np.array(vals)
    return (round(float(np.percentile(v, 50)), 3),
            round(100.0 * float((v >= 0.25).mean()), 1))


def main():
    print('R=%d por corriente, corrientes=%s, semilla base=%d, gate sil>=%.2f'
          % (R, list(STREAMS), SEED, SIL_MIN))
    print('%4s %2s | %-44s | %-52s | %s'
          % ('n', 'k', 'NULO  pasa25 fp30 degen sil_max',
             'ESTRUCT pasa25 orden ari sil_min', 'veredicto (2 corrientes)'))
    ok_ns = []
    for n in SIZES:
        pares = [(run(n, False, st), run(n, True, st)) for st in STREAMS]
        # peor caso entre corrientes: el umbral debe valer en las dos
        fp = max(p[0]['pasa25_pct'] for p in pares)
        dg = max(p[0]['degen_pct'] for p in pares)
        smx = max(p[0]['sil_max'] for p in pares)
        pot = min(p[1]['pasa25_pct'] for p in pares)
        ordn = min(p[1]['orden_ok_pct'] for p in pares)
        arim = min(p[1]['ari_med'] for p in pares)
        smn = min(p[1]['sil_min'] for p in pares)
        si = all(cumple(a, b) for a, b in pares)
        if si:
            ok_ns.append(n)
        print('%4d %2d | %10.1f %6.1f %6.1f %7.3f | %14.1f %7.1f %5.3f '
              '%8.3f | %s'
              % (n, pares[0][0]['k'], fp, max(p[0]['fp30_pct'] for p in pares),
                 dg, smx, pot, ordn, arim, smn,
                 'CUMPLE' if si else 'no'))
    print()
    print('criterio: pasa25(nulo)<=%.1f%% y pasa25(estr)>=%.0f%% y '
          'degen<=%.0f%% y orden>=%.0f%%, en LAS DOS corrientes'
          % (MAX_FP_PCT, MIN_POT_PCT, MAX_DEGEN_PCT, MIN_ORDEN_PCT))
    print('n que cumplen:', ok_ns)
    print('MIN_ROWS justificado =', min(ok_ns) if ok_ns else 'NINGUNO')

    print()
    print('Filtro de permutacion (alpha=%.2f, %d permutaciones): %% de '
          'datasets en los que SE DEJAN clusters'
          % (CLUSTER_ALPHA, CLUSTER_PERM))
    print('  %-6s %22s %24s %24s' % ('n', 'NULO (falso positivo)',
                                    'delta=0.30 (potencia)',
                                    'delta=0.60 (potencia)'))
    for n in (24, 30, 40):
        print('  n=%-4d %20.1f%% %24.1f%% %24.1f%%'
              % (n, gate_stats(n, 'nulo'), gate_stats(n, 'delta30'),
                 gate_stats(n, 'delta60')))
    print('  (el falso positivo del nulo es ~alpha por construccion: el '
          'p-valor controla la tasa, no un umbral calibrado a mano)')
    print()
    print('Silueta nula con la FORMA del ledger real (3 columnas varian) '
          '- por que NO se uso como filtro:')
    for n in (24, 30, 40):
        p50, p25 = sil_forma_producto(n)
        print('  n=%-4d sil_p50=%.3f  %%con sil>=0.25: %.1f%%  -> el corte '
              '0.25 no descartaria NADA' % (n, p50, p25))


if __name__ == '__main__':
    main()
