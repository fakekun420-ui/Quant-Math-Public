"""Dias hasta que se toca el SL o el TP con barras diarias.

Existe porque el docstring de regime_learning citaba un script
(runtime/f3/d2/calibra.py) que NO estaba en disco: las medianas de
"47/56/48/36 dias hasta el SL" eran NO VERIFICADAS. Este fichero las
vuelve a calcular y versiona, para que la cita apunte a algo que existe.

Convencion (la del propio docstring): SL a 25% ROE y TP a 50% ROE con
apalancamiento 2x -> 12.5% y 25% de movimiento de precio.

Metodo (offline, sobre data/*_historical_4y.csv, barras diarias):
  * Entrada al CIERRE de cada barra.
  * SL tocado si el low del dia posterior <= entrada * 0.875.
  * TP tocado si el high del dia posterior >= entrada * 1.25.
  * Si ambos se tocan en la misma barra, cuenta SL (peor caso).
  * Horizonte maximo 365 dias: lo que no llega es CENSURADO y se
    reporta aparte; las medianas solo se calculan sobre lo no censurado
    (decir "la mediana es 47 dias" sin decir que el resto no llega
    nunca seria otra mentira).

LIMITES HONESTOS: barras diarias, entradas que se solapan (no es un
backtest: es la duracion de UNA posicion). Sirve para responder "un
cierre cuesta semanas o sesiones?", no para estimar expectancy.

Uso: /usr/bin/python3 tools/calibrate_hold_days.py
"""
import csv
import statistics

SL = 0.875     # -12.5% de precio = 25% ROE a 2x
TP = 1.25      # +25% de precio   = 50% ROE a 2x
HORIZON = 365
FILES = ['btcusdt', 'ethusdt', 'xrpusdt', 'dogeusdt']


def medias(sym):
    path = 'data/' + sym + '_historical_4y.csv'
    with open(path, encoding='utf-8') as fh:
        rows = [r for r in csv.DictReader(fh) if r.get('close')]
    closes = [float(r['close']) for r in rows]
    highs = [float(r['high']) for r in rows]
    lows = [float(r['low']) for r in rows]
    n = len(closes)
    dias_sl, dias_tp, cens = [], [], 0
    for i in range(n - 1):
        e = closes[i]
        hit_sl = hit_tp = None
        for d in range(1, min(HORIZON, n - 1 - i) + 1):
            if lows[i + d] <= e * SL:
                hit_sl = d
            if highs[i + d] >= e * TP:
                hit_tp = d
            if hit_sl or hit_tp:
                break
        if hit_sl is None and hit_tp is None:
            cens += 1
        elif hit_sl is not None and (hit_tp is None or hit_sl <= hit_tp):
            dias_sl.append(hit_sl)
        else:
            dias_tp.append(hit_tp)
    return {
        'barras': n,
        'sl_n': len(dias_sl),
        'sl_med': statistics.median(dias_sl) if dias_sl else None,
        'tp_n': len(dias_tp),
        'tp_med': statistics.median(dias_tp) if dias_tp else None,
        'cens_pct': round(100.0 * cens / max(1, n - 1), 1),
    }


def main():
    print('%10s %6s | %7s %7s | %7s %7s | %s'
          % ('symbol', 'barras', 'sl_n', 'sl_med', 'tp_n', 'tp_med',
             'cens%'))
    for s in FILES:
        r = medias(s)
        print('%10s %6d | %7d %7s | %7d %7s | %s'
              % (s.replace('usdt', ''), r['barras'], r['sl_n'], r['sl_med'],
                 r['tp_n'], r['tp_med'], r['cens_pct']))
    print()
    print('SL = -12.5% precio (25% ROE a 2x), TP = +25% precio (50% ROE a 2x)')
    print('horizonte %d dias; mediana SOLO sobre lo no censurado' % HORIZON)


if __name__ == '__main__':
    main()
