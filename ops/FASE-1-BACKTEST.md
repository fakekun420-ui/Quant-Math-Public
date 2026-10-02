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

---

# FASE 1b: dimensionamiento de posición

## El bug

El backtest entraba con `quantity=1`, o sea que **el nocional era el precio del
activo**. Con una cuenta de 100.000:

| Símbolo | Nocional de `quantity=1` | % de la cuenta |
|---|---:|---:|
| BTC | 105.900 | 105,90% |
| ETH | 2.552 | 2,55% |
| SOL | 148 | 0,15% |
| XRP | 2,17 | 0,0022% |

50.000 veces de diferencia. BTC se medía al 106% de la cuenta por accidente del
precio, y en XRP una operación movía 0,003 USDT.

## El arreglo

Nocional = **fracción fija del capital × apalancamiento**, y la cantidad de cada
barra = nocional / precio de esa barra.

Fraccional y **no** riesgo-por-stop a propósito: el riesgo por stop metería en la
comparación una variable más —la distancia del stop— que es justo lo que se
quiere medir. Con fracción fija, cada símbolo arriesga lo mismo y lo único que
cambia es la estrategia.

## Un hallazgo del propio motor

Con fracción 1,0 y apalancamiento 1 el backtest **no abre ninguna posición**:
0 operaciones en los 4 símbolos. El motor exige `capital >= margen + comisión`, y
con margen igual al nocional, el 100% del capital más la comisión de entrada no
cabe nunca. Se lee como "la estrategia no genera señal" cuando lo que pasa es que
no hay con qué pagar el margen.

Además, **más exposición produce menos operaciones**, porque la cuenta muere
antes. Medido en BTC a 50×: fracción 0,95 → 1 operación y 78.732 restantes;
fracción 0,10 → 112 operaciones y 8.470. Eso es expectativa negativa acting sobre
el capital, y con dimensionamiento la consequence es visible en el número de
operaciones, no escondida en un porcentaje.

## Resultado con exposición comparable (25% del capital)

**3 de 32 con expectativa neta positiva, y ninguno con significación.**

| Símbolo | Familia | n | wr% | esp% | **esp neta%** | dd% | **IC95 inf.** |
|---|---|---:|---:|---:|---:|---:|---:|
| ETH | ATI | 48 | 39,6 | +0,3308 | **+0,2040** | 7,41 | **−275,31** |
| SOL | ATI | 39 | 46,2 | +0,2530 | **+0,1262** | 14,34 | **−439,13** |
| XRP | ATI | 37 | 32,4 | +0,1601 | **+0,0333** | 16,38 | **−836,01** |
| ETH | Bollinger | 492 | 60,6 | −0,0458 | −0,1726 | 32,57 | −94,54 |
| XRP | RSI | 474 | 55,5 | −0,0851 | −0,2119 | 43,18 | −136,44 |
| SOL | RSI | 488 | 56,6 | −0,0707 | −0,1975 | 38,66 | −120,66 |

Las tres positivas son **ATI**, y solo en los tres símbolos con más de 36
operaciones. Pero sus intervalos de confianza contienen el cero con holgura:
**ninguna es distinguible de una moneda al azar.**

El resto sigue perdiendo, y hay combinaciones con **60,6% de aciertos que
pierden**: cuando acierta gana poco y cuando falla pierde más.

## Conclusión de la Fase 1

1. **Ninguna de las 8 familias tiene ventaja demostrada a 15m con taker.**
2. ATI es la única con señal positiva consistente en 3 símbolos, y no alcanza
   significación con n=37–48.
3. Para que ATI fuera concluyente harían falta del orden de **n=200 por
   símbolo** al nivel de significación actual, o sea ~1.500 operaciones más.

## Siguiente paso natural

No es buscar más indicadores: es **probar ATI con exponente real** (más
operaciones) y con costes de maker, que son 4,7× más baratos y reduces el
margen de error. Con maker, un −0,13% neto pasa a −0,03%: el filtro de
significancia cambiaría.

---

# FASE 1c: ATI sobre 1.249 días, y dos errores míos al medirlo

## Qué se amplió

480.000 velas (1.249 días, del **2023-05-01**). El histórico nuevo es la subida
de 2023 y el ciclo del halving de 2024, o sea **un régimen de mercado distinto**
al de los 468 días iniciales.

## Resultado bruto: 8/8 tramos con expectativa neta positiva

Con taker y con maker, en los cuatro símbolos y en los dos cortes
(2025-01-01). Eso, sobre el papel, es señal consistente.

## Error mío nº1: la línea base estaba medida en otra escala

Comparé ATI con "comprar y esperar 40 barras" y salió 8/8 a favor de ATI.

**Los 40 barras los inventé yo.** Medido, ATI mantiene la posición una mediana
de **383 a 820 velas**, o sea **4 a 8,5 días**, no 10 horas. Comparé una
línea base de 10 horas contra una estrategia de 8 días. Esa comparación no
significa nada y **queda anulada**.

## Error mío nº2: "el backtester mira al futuro" — falso

La mejor operación de ATI sobre SOL 2023-2024 daba **+177,85%**, y el mejor
movimiento real de 40 barras de ese tramo era **+31,62%**: 5,62×, imposible.
Conclusión inmediata: el motor se inventa retornos.

**Era falso, y por el mismo error.** Con el horizonte correcto (medido: 820
velas) el máximo real del tramo es +70,38%, y un movimiento de +177% en 820
velas **sí ocurre** en SOL durante el squeeze de 2023.

Comprobado operación por operación, cada `pnl_pct` contra el retorno real de
**su propio** tramo de entrada a salida leído del CSV:

```
Operaciones comprobadas:               418
Operaciones que exceden el retorno real:  0
```

**El motor no se inventa nada y la Fase 1 no está contaminada.** Queda
fijado como test en `tests/test_backtester_no_inventa_retornos.py`.

## Lo que sí queda en pie: la ventaja son unas 3 operaciones

| Tramo | con todo | sin la mejor | **sin las 3 mejores** | las 3 mejores |
|---|---:|---:|---:|---|
| BTC 2023-2024 | +1,7092 | +0,9064 | **−0,2433** | +51,61 · +36,24 · +34,81 |
| BTC 2025-2026 | +0,1880 | −0,1504 | **−0,6560** | +19,94 · +14,88 · +13,39 |
| ETH 2023-2024 | +0,8957 | +0,4758 | **−0,3110** | +26,22 · +25,79 · +21,04 |
| ETH 2025-2026 | +0,1892 | −0,3682 | **−1,3273** | +36,55 · +33,10 · +26,85 |
| XRP 2023-2024 | +2,8221 | −1,1146 | **−2,8170** | +152,54 · +32,17 · +27,14 |
| XRP 2025-2026 | +0,7092 | −0,4835 | **−1,9818** | +55,70 · +37,71 · +27,50 |
| SOL 2023-2024 | +9,1087 | +3,6696 | +0,5186 | +177,85 · +53,62 · +45,35 |
| SOL 2025-2026 | +1,7728 | +1,2072 | +0,0615 | +30,18 · +29,72 · +27,95 |

(esperanza neta con taker, en % por operación)

**En 6 de 8 tramos la ventaja desaparece al quitar las 3 mejores operaciones.**
Sobre 418 operaciones totales, unas 24 sostienen el resultado. Los tres
supervivientes (los dos de SOL) quedan en +0,52% y +0,06%: indistinguibles del
cero, y ya con elIntervalo de confianza abierto.

## Veredicto de la Fase 1c

1. **El motor es correcto.** Verificado por invariante sobre 418 operaciones.
2. **ATI no tiene ventaja demostrada.** Su expectativa media es real pero la
   sostienen unas 3 operaciones por tramo; ninguna variante pasa el filtro de
   significancia (0 de 8 con IC95 entero por encima de cero, con taker y con
   maker).
3. **Más histórico no arregla esto**: de 468 a 1.249 días el número de
   operaciones fue de ~30-48 a 32-66 por tramo, y el intervalo siguió
   incluyendo el cero con holgura.

## Nota sobre el test del invariante

La primera versión del test **pasaba con el bug presente**, y no por casualidad:
trataba `entry_time` como marca de tiempo cuando son índice de barra, así que
el guard de rango se comía todas las operaciones y no comparaba nada. Un test
que no compara nada pasa siempre.

Mutación usada para comprobarlo: `pnl_pct × 1,5`. Con el test vacío daba
`2 passed`; con el test arreglado da `1 failed`. Por eso el control de
mutación es obligatorio y no opcional.

---

# FASE 1d: auditoría del modelo de coste

## Qué se auditó y qué salió

El modelo de coste del backtester, porque toda la Fase 1 restsó el coste "a
mano" y eso-printa que el motor no lo hacía.

## Error 1: el motor SÍ cobra, y yo lo desconté otra vez

**Medido**: el motor descuenta **−0,2001%** por operación, que reconcilia con
sus `commission_rate=0.001` por lado (0,2% ida y vuelta).

Escribí en el informe que "el motor NO descuenta el coste: se sigue restando a
mano". **Eso era falso** y came de no abrir el fichero antes de afirmarlo. Al
restar 0,1268% encima, el coste se contó dos veces: 0,2% dentro + 0,1268%
fuera. Todos los "neta%" de las fases anteriores eran **pesimos de más**.

## Error 2: el 0,1268% es solo la comisión — falta el 77% del coste

| Componente | Medido | Origen |
|---|---:|---|
| Comisión taker ida y vuelta | 0,1268% | medido |
| **Spread (deslizamiento)** | **0,4270%** | medido (ask 1,591 vs last 1,5248 en XRP) |
| **Subtotal real** | **0,5538%** | |
| Funding (ATI mantiene 3–8,5 días) | +0,24% | medido, 12–25 cobros por operación |
| **Total para ATI** | **0,79%** | |

**Se ha estado descontando menos de un cuarto de lo que cuesta operar
realmente.** El "0,1268%" es comisión pura.

## Los dos defaults que mentían

```python
slippage_pct    = 0.0    #  ejecución perfecta
funding_rate_8h = 0.0    #  mantener abierto es gratis
```

Y el adaptador no pasaba ninguno de los dos. **Todos los backtests del
proyecto asumían ejecución perfecta y mantenimiento gratuito**, sin que
estuviera escrito en ninguna parte. Un supuesto favorable que no se dice
nunca es el que más caro sale.

El funding en particular no era conservador sino **falso**: se midió
negativo (los largos pagaban) de febrero a abril de 2026.

## El arreglo

`ModeloCoste` con los tres componentes medidos, **con fecha y exchange**, y
`timeframe` pasando también al constructor (antes solo llegaba a
`run_backtest`, así que el funding se habría calculado a temporalidad 1h
equivale a 4 veces lo que toca).

## El efecto sobre el veredicto

Con el coste real, sobre ATI:

| Tramo | neta antes (0,1268%) | **neta real (0,79%)** | **sin las 3 mejores** |
|---|---:|---:|---:|
| BTC 2025-2026 | +0,3880 | **−0,1515** | −0,9955 |
| ETH 2025-2026 | +0,3892 | **−0,1296** | −1,6462 |
| SOL 2025-2026 | +1,9730 | +1,4025 | **−0,3087** |
| XRP 2025-2026 | +0,9094 | +0,3586 | **−2,3324** |

```
Tramos con expectativa NETA positiva:                    6 de 8
Tramos con expectativa neta positiva SIN LAS 3 MEJORES:   1 de 8
```

**El coste correcto no crea el problema: lo revela.** Con 0,1268% parecía que
6 de 8 tramos eran rentables. Con el coste real son 6 de 8, pero **al quitar
las 3 mejores operaciones solo queda 1**, y ese (+0,0353%) es indistinguible
del cero.

## Dos cosas que parecían bugs y no lo eran

1. **La reconciliación fallaba en SOL (3 de 4).** Al mirar una operación
   suelta: la diferencia es de 0,02 puntos sobre un coste de 0,7%, y crece en
   las operaciones ganadoras porque el nocional crece al salir. El motor
   descuenta correctamente; mi comparación usaba la mediana de horas contra
   la media de un coste que se cobra por operación.

2. **El motor "cobra de más" (0,1395% en vez de 0,1268%).** La comisión de
   salida se cobra sobre el nocional **ya subido**: al vender a 120 en vez de
   a 100 se paga un 20% más. El motor estaba bien y la referencia era
   ingenua.

## Verificación

- **499 tests verdes** (492 + 7 nuevos).
- **Control de mutación triple**, los tres cazados:
  - quitar el deslizamiento de la ruta de producción → 1 fallo
  - quitar el funding de la ruta de producción → 1 fallo
  - comisión ×2 en el motor → 2 fallos
- `graphify update .` hecho. Sin CJK.

## Lo que queda abierto

- El **spread de 0,427%** se midió en XRP en un momento concreto. BTC y ETH
  tienen spreads más ajustados, así que aplicar 0,427% a los cuatro es
  conservador de más. **Falta medir el spread de cada símbolo.**
- El funding de 0,01%/8h es un valor medio. **Falta la serie real** de funding
  para el periodo backtesteado: en un tramo de funding negativo el coste real
  es mucho mayor.
- `ModeloCoste` es un número único. Las comisiones de Bybit **varían por par**
  (BTC y XRP no tienen las mismas), así que un solo valor no puede ser
  correcto para los cuatro símbolos.
