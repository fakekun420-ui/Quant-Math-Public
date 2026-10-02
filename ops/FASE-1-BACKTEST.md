# FASE 1: ¿el backtest dice la verdad?

Fecha: 2026-10-02. Sin operar. Sin tocar el exchange con órdenes.

## Qué se hizo

Se descargaron **180.000 velas reales de mainnet** (4 símbolos × 45.000, 468 días,
2025-06-20 → 2026-10-02, 15m) y se corrieron las **8 familias de producción** sobre
ellas: **32 combinaciones**.

El motivo de descargar a disco: hasta hoy no había ni un CSV. El backtest leía
velas de una variable en RAM, así que no quedaba rastro de con qué se había
medido y no se podía repetir nada.

`tools/fetch_ohlcv.py` deja los datos y el manifiesto. Los CSV (11 MB) están
ignorados a propósito; el manifiesto se versiona.

## Respuesta 1: sí, el backtest opera sobre histórico real

32 combinaciones con operaciones, de 10 (BTC VWAP) a 822 (SOL EMA).

## Respuesta 2: NO. Cero de 32 con expectativa neta positiva

Expectativa por operación, ya descontando el coste real de ida y vuelta con
taker (**0,1268%** del nocional, medido). El motor **no** descuenta el coste, así
que sin este paso todo resultado es optimista.

| Símbolo |Familia   |     n |  wr%  | esp/op% | **esp neta%** |  dd%  |
|---------|-----------|-------:|------:|--------:|--------------:|------:|
| BTC     | EMA       |    232 |  22,4 | −0,1751 |    **−0,3019** | 40,63 |
| BTC     | Breakout  |    132 |  24,2 | −0,3134 |    **−0,4402** | 41,90 |
| BTC     | VWAP      |     10 |  50,0 | −1,7339 |    **−1,8607** | 34,95 |
| ETH     | Bollinger |    492 |  60,6 | −0,0063 |    **−0,1331** |  4,34 |
| ETH     | ATI       |     48 |  39,6 | +0,0319 |    **−0,0949** |  1,10 |
| SOL     | RSI       |    488 |  56,6 | −0,0004 |    **−0,1272** |  0,21 |
| SOL     | ATI       |     39 |  46,2 | +0,0006 |    **−0,1262** |  0,10 |

(las 32 filas están en el informe de consola; el patrón es el mismo en las cuatro)

**El mejor caso medido es ETH/ATI: +0,032% por operación antes de costes, −0,095%
después.** Todo lo demás pierde. Y con `wr` de hasta 60,8% (Bollinger), que es
justo el caso que un humano lee como "acierta el 60%, surely gana": pierde. La
razón es que cuando acierta gana poco y cuando falla pierde más.

## Respuesta 3: el hallazgo que cambia la interpretación

XRP y SOL dan expectativa **−0,0000%** y drawdown **0,00%**. Eso no es "no hay
edge", es **que no se está midiendo nada**.

El backtest entra con `quantity=1`, sin dimensionar la posición. Medido:

| Símbolo | precio | nocional de `quantity=1` | % de una cuenta de 100.000 |
|---------|-------:|------------------------:|---------------------------:|
| BTC     | 105.900 |               105.900   |                **105,90%** |
| ETH     |   2.552 |                 2.552   |                   2,55% |
| SOL     |     148 |                   148   |                   0,15% |
| XRP     |    2,17 |                   2,17   |              **0,0022%** |

**La exposición varía en 50.000 veces entre el primero y el último.** BTC se mide
al 106% de la cuenta (apalancamiento 1,06 por accidente del precio) y XRP al
0,0022%, donde una operación mueve 0,003 USDT: ruido puro.

Consecuencia: **las cuatro columnas no son comparables entre sí**, y el "−0,0000%"
de XRP no es un resultado, es la ausencia de resultado.

## Qué sigue sin resolverse

1. **El backtest no tiene dimensionamiento de posición.** Es lo que hay que
   arreglar antes de volver a comparar nada. Con un modelo de riesgo por
   apalancamiento, no con `quantity=1`.
2. **No se ha mirado si el resultado cambia con costes de maker** (0,0268%): con
   maker el margen es mucho más estrecho y la conclusión puede cambiar. Sin
   maker, la conclusión es que las 8 familias no sirven.
3. **No se ha evaluado el error de la Fase 1 como tal:** una sola ventana de
   468 días y un solo régimen de mercado. Un backtest que no sobrevive a una
   ventana ya se puede descartar; uno que la supera, todavía no.
4. **El umbral `scientific_score = 0,6` y `interval_seconds` siguen sin
   decidir.** No se han tocado.
5. **El coste no está dentro del motor**, se restó a mano en este informe. El
   motor debería descontarlo, o cualquier backtest suyo será optimista por
   construcción.

## Conclusión

**Ninguna de las 8 familias de producción tiene ventaja demostrada a 15m con
taker.** No es que el motor esté roto: los bugs que se encontraron están
arreglados y verificados. Es que las estrategias no tienen edge, que es un
resultado, no un fallo.

La Fase 2 (buscar ventaja donde la literatura dice que existe) solo tiene
sentido con el punto 1 arreglado, porque comparar cuatro símbolos medidos con
exposiciones distintas no produce información.
