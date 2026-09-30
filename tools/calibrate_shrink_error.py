"""Error de la tasa de exito ENCOGIDA vs numero de cierres por familia.

Existe por lo mismo que calibrate_hold_days.py: el docstring de
regime_learning decia que el error "se estanca en ~0.10 a partir de ~3
cierres por familia y baja de 0.10 con ~8", citando un script
(runtime/f3/d2/calibra.py) que NO existe en disco. Aqui se recalcula y
se versiona.

Que se mide: el estimador encogido de regime_learning (SHRINK_K=5 hacia
la media global) contra la tasa VERDADERA de la familia, en un mundo
donde las tasas verdaderas se distribuyen como Beta(2,2) (media 0.5,
dispersion tipica ~0.22: familias ni todas iguales ni todas extremas).

  est = (victorias + SHRINK_K * 0.5) / (n + SHRINK_K)
  RMSE(est, p_verdadera) sobre 20000 familias simuladas.

Es una simulacion con supuestos (Beta(2,2), p global 0.5), NO una
medicion sobre datos reales: sirve para dimensionar el error, no para
afirmar que el ledger real tiene esa dispersion.

Uso: /usr/bin/python3 tools/calibrate_shrink_error.py
"""
import numpy as np

SEED = 20260929
K = 5.0            # SHRINK_K de regime_learning
SIMS = 20000
NS = list(range(1, 21))
OBJETIVO = 0.10


def main():
    rng = np.random.default_rng(SEED)
    p_true = rng.beta(2, 2, SIMS)
    print('semana: RMSE del win-rate encogido (K=%.0f, p~Beta(2,2), '
          '%d simulaciones)' % (K, SIMS))
    cruza = None
    for n in NS:
        vict = rng.binomial(n, p_true)
        est = (vict + K * 0.5) / (n + K)
        rmse = float(np.sqrt(((est - p_true) ** 2).mean()))
        marca = ''
        if cruza is None and rmse < OBJETIVO:
            cruza = n
            marca = '  <- primero por debajo de %.2f' % OBJETIVO
        print('  n=%2d cierres/familia  RMSE=%.4f%s' % (n, rmse, marca))
    print()
    print('primer n con RMSE < %.2f: %s' % (OBJETIVO, cruza))
    print('RMSE a n=3: ', end='')
    for n in (3, 8):
        vict = rng.binomial(n, p_true)
        est = (vict + K * 0.5) / (n + K)
        print('n=%d %.4f  ' % (n, float(np.sqrt(((est - p_true) ** 2).mean()))),
              end='')
    print()


if __name__ == '__main__':
    main()
