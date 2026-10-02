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

---

# FASE 1e: el coste por símbolo, y por periodo

## Tres modelos seguidos, tres veredictos distintos

| Medición del coste | Netas positivas | Sin las 3 mejores | Con significación |
|---|---:|---:|---:|
| Fase 1 — solo comisión 0,1268% (y contada dos veces) | 0 de 32 | — | 0 |
| Fase 1d — spread de **un tick** + funding medio | 6 de 8 | 1 de 8 | 0 |
| **Fase 1e — spread muestreado + funding real por periodo** | **8 de 8** | **2 de 8** | **0** |

**El veredicto cambiaba tres veces y ninguna vez por culpa de la estrategia.**
Cambiaba por el modelo de coste, es decir por mis propias mediciones. Tres
números que parecían el mismo concepto —"lo que cuesta operar"— y que en
realidad eran tres cosas distintas.

## El spread de 0,427% eran 65× lo que es

Salió de **un solo tick** de XRP (ask 1,591 contra bid 1,5842). Con 25
muestras por símbolo:

| Símbolo | Medido (mediana de 25) | vs 0,427% |
|---|---:|---:|
| BTC | 0,00012% | 4.270× |
| ETH | 0,00036% | 1.186× |
| XRP | 0,00649% | 65× |
| SOL | 0,00822% | 52× |

**El spread es despreciable frente a la comisión.** El modelo costaba 4× de más
por culpa de un tick.

Es el mismo error que el del "0,1268%": un número de una sola muestra parece
tan firme como uno de 25. Y lo cometí dos veces, en direcciones opuestas — la
primera took too little, la segunda too much.

## El funding real: 3.800 periodos por símbolo

Endpoint público `publicGetV5MarketFundingHistory`. **Tres caminos y solo uno
funciona**: el privado no existe en este build de ccxt, el v3 público da 404, y
el v5 `market/funding/history` responde. Además pagina con `endTime` y **no**
con `end` — con `end` devuelve siempre la misma página, que es el bucle
infinito que ya se cueló una vez en el paginador de velas.

| Símbolo | 2023-2024 | 2025-2026 | Negativos 2025-2026 |
|---|---:|---:|---:|
| BTC | 0,01002% | 0,00363% | 23,1% |
| ETH | 0,01009% | 0,00347% | 25,1% |
| XRP | 0,01253% | 0,00270% | 32,4% |
| SOL | 0,01079% | 0,00095% | 38,3% |

**El tramo reciente es entre 3 y 10 veces más barato**, así que el promedio de
los dos no representa a ninguno. Y el funding es **negativo entre el 10% y el
38% de los periodos**: un largo en tramo negativo recibe dinero. El signo
cambia el coste, no solo su magnitud.

## El coste real, por símbolo y periodo

Para una posición de 3 a 8 días (el horizonte medido de ATI):

| Símbolo | Periodo | Ida y vuelta | +3 días | +8 días |
|---|---|---:|---:|---:|
| BTC | 2023-2024 | 0,1270% | 0,2172% | 0,3675% |
| BTC | 2025-2026 | 0,1270% | 0,1597% | 0,2142% |
| ETH | 2025-2026 | 0,1275% | 0,1588% | 0,2108% |
| XRP | 2025-2026 | 0,1398% | 0,1641% | 0,2046% |
| SOL | 2025-2026 | 0,1432% | 0,1518% | 0,1660% |

## El número bueno de ATI

| Símbolo | Tramo | Bruta % | Coste % | **Neta %** | **IC95 inf.** | **Neta sin las 3** |
|---|---|---:|---:|---:|---:|---:|
| BTC | 2023-2024 | +2,0360 | 0,2470 | **+1,7890** | −0,7625 | −0,1635 |
| BTC | 2025-2026 | +0,5148 | 0,1679 | **+0,3469** | −0,9538 | −0,4971 |
| ETH | 2023-2024 | +1,2225 | 0,2565 | **+0,9660** | −0,9121 | −0,2407 |
| ETH | 2025-2026 | +0,5160 | 0,1594 | **+0,3566** | −1,9246 | −1,1599 |
| XRP | 2023-2024 | +3,1489 | 0,3516 | **+2,7973** | −5,5341 | −2,8418 |
| XRP | 2025-2026 | +1,0362 | 0,1732 | **+0,8630** | −2,6614 | −1,8280 |
| SOL | 2023-2024 | +9,4355 | 0,4197 | **+9,0158** | −3,0789 | **+0,4256** |
| SOL | 2025-2026 | +2,0998 | 0,1569 | **+1,9429** | −0,7678 | **+0,2317** |

```
Neta positiva:                   8 de 8
IC95 entero sobre cero:          0 de 8
Neta positiva sin las 3 mejores: 2 de 8   (los dos de SOL)
```

## Veredicto

1. **La expectativa media de ATI es real y positiva** en los ocho tramos, y es
   de 2 a 3 veces el coste. Eso ya no es un artefacto del coste mal medido.
2. **Ninguno de los ocho es estadísticamente distinguible de una moneda al
   azar.** El intervalo contiene el cero en los 8.
3. **Solo SOL sobrevive** a quitar las 3 mejores operaciones (+0,4256% y
   +0,2317%). Es la única pista que queda, y es una pista, no una ventaja.

Un punto positivo del proceso: **la conclusión se ha vuelto más pesimista tres
veces seguidas** al medir mejor, y eso es lo que debería pasar. Cuando afloja
el instrumento, la estrategia no mejora; aparece que el instrumento estaba
mintiendo.

## Verificación

- **503 tests verdes** (499 + 4 nuevos).
- **Control de mutación triple, los tres cazados**:
  - volver al spread de un tick → 2 fallos
  - promediar el funding entre los dos periodos → 1 fallo
  - quitar la conversión de unidades del spread → 1 fallo

## Sigue abierto

- El spread es una **foto de ahora**, no del periodo backtesteado, y no hay
  forma de reconstruirlo desde las velas (`high`/`low` son extremos del rango,
  no el precio de ejecución). Los números de 2023-2024 usan el spread de 2026.
- El funding está **integrado como la tasa de la mediana de horas**, no
  sumando los periodos reales que caen dentro de cada operación. Con un
  horizonte de 3 a 8 días y un cutoff cada 8 horas, son de 9 a 24 periodos:
  sumar los reales daría un número distinto.
- **No se ha medido el coste de pasar por el libro de profundidad.** Con
  notional de miles de USDT en XRP o SOL, el precio ejecutado no es el del
  primer nivel, y ahí el spread efectivo sube.
- Las **comisiones por par** no se han podido leer: el endpoint público de
  grupos de comisiones devuelve `retCode 10001`. Sigue usándose 0,000634 por
  lado para los cuatro, que es el valor taker estándar medido en BTC.

---

# FASE 1f: el deslizamiento de verdad, que no es el spread

## Qué se midió

Recorriendo el libro de órdenes nivel a nivel y calculando el precio medio
ponderado por volumen. Ese alejamiento respecto al mejor nivel **es** el
deslizamiento efectivo, y es lo que se paga de verdad.

## El deslizamiento no es un número: depende del nocional

Ida y vuelta, en %:

| Nocional | BTC | ETH | XRP | SOL |
|---:|---:|---:|---:|---:|
| 250 | sin medir | 0,0178 | 0,0000 | 0,0173 |
| 2.500 | sin medir | 0,0747 | 0,0000 | 0,0504 |
| 25.000 | sin medir | sin medir | 0,0092 | **0,1822** |
| 100.000 | sin medir | sin medir | 0,0294 | **0,4979** |

**En SOL va de 0,0173% a 0,4979%: 29 veces peor**, y a 25.000 USDT es
0,1822%, que es **11 veces** lo que decía el spread del primer nivel
(0,0164%).

El spread del primer nivel solo dice el precio al que se ejecuta una cantidad
**mínima**. Un nocional real se come niveles. Un modelo con un solo número de
spread subestima el coste de SOL entre 6 y 30 veces.

**Y el orden es el opuesto al que se supone:** BTC y ETH tienen el libro más
profundo y SOL el más fino. Quien parece barato de operar es el que se come el
libro.

## Tres errores midiendo esto

1. **Sumar los dos lados con signo.** En compra el deslizamiento es positivo y
   en venta negativo, así que sumarlos **los cancela** y deja un coste de
   cero. Es `compra + |venta|`.
2. **Contar niveles de tamaño cero.** Sin filtrarlos, en BTC salían 393
   niveles para 250 USDT — 0,64 USDT por nivel — y un deslizamiento del 0,10%,
   **860 veces** el spread del primer nivel. El libro más profundo del mundo
   aparecía como el más caro, al revés de lo real.
3. **Mi docstring mentía.** Decía que la función "lo dice" cuando un símbolo no
   tiene medición, y no lo dice: es pura y no tiene logger. Ahora existe
   `simbolo_medido()`, que sí responde.

## Lo que no se pudo medir, y se deja como hueco

**BTC y ETH por encima de unos miles de USDT.** `fetch_order_book(limit=1000)`
no devuelve profundidad suficiente para ellos: su liquidez está más allá de los
niveles que ese endpoint da. Los huecos se quedan huecos. El endpoint agregado
de Bybit daría la profundidad real y queda pendiente.

Un hueco declarado es información. Poner un número inventado ahí sería peor,
porque el hueco se ve y el número inventado no.

## Qué NO cambia

El coste con profundidad sigue por debajo de la expectativa de ATI: en SOL a
25.000 USDT el deslizamiento real es 0,1822% frente a una expectativa neta de
+1,94%. **No vuelca el veredicto, pero sí el dimensionamiento**: a 100.000 USDT
el mismo SOL cuesta 0,4979% solo en deslizamiento.

Y el hallazgo de fondo sigue igual, porque es sobre la forma de la
distribución y no sobre su nivel: **0 de 8 tramos con significación, y solo 2
de 8 sobreviven a quitar las 3 mejores operaciones.**

## Verificación

- **507 tests verdes** (503 + 4 nuevos).
- **Control de mutación triple, los tres cazados**:
  - usar el spread del primer nivel como si fuera el real → 4 fallos
  - devolver la fila más barata para un nocional sin medir → 3 fallos
  - `simbolo_medido()` diciendo "medido" cuando no lo está → 1 fallo

---

# FASE 1g: RETRACTACIÓN — la tabla de deslizamiento estaba mal

**Lo publicado en `f85507b9` era falso. Se retira aquí.**

## Qué se publicó

> «En SOL va de 0,0173% a 0,4979%: **29 veces peor**, y a 25.000 USDT es
> 0,1822%, que es **11 veces** lo que decía el spread del primer nivel.»

## Qué es verdad

| Nocional | BTC | ETH | XRP | SOL |
|---:|---:|---:|---:|---:|
| 250 | 0,00000% | 0,00000% | 0,00000% | 0,00000% |
| 2.500 | 0,00000% | 0,00000% | 0,00000% | 0,00000% |
| 25.000 | 0,00000% | 0,00000% | 0,01171% | 0,01504% |
| 100.000 | 0,00000% | 0,00342% | 0,03273% | 0,01438% |
| 500.000 | 0,00319% | 0,02516% | 0,09037% | 0,04629% |

**El número de SOL a 25.000 era 12 veces mayor de lo real.** Y BTC, que se
publicó como el libro más caro del mundo, tiene deslizamiento **cero** hasta
100.000 USDT: su primer nivel tiene 3,193 BTC (268.295 USDT medidos), así que
25.000 se ejecuta entero en el primer nivel.

## De dónde salió el error

**El tamaño de un nivel va en unidades del activo, y se estaba restando de un
presupuesto en USDT.** Con `t = min(q, rest)` un nocional de 250 USDT
consumía 250 BTC — unos 21 millones de dólares — y agotaba el libro entero.

La firma del error era que **el deslizamiento grows como el precio del
activo**: BTC, el más caro, salía como el más caro de operar. Eso estaba en la
tabla publicada y era la pista de que el recorrido estaba mal, y se leyó como
un hallazgo en vez de como una alarma.

**Y tres versiones seguidas de esta medición dieron tres números distintos,
los dos primeros por el mismo tipo de fallo: unidades mezcladas.** La primera
también se cancelaba al sumar los dos lados con signo, y contaba niveles de
tamaño cero.

## Qué pasa con el veredicto

**No lo cambia, y conviene decirlo claro.** El deslizamiento a 25.000 USDT es
de orden milésimas, la expectativa neta de ATI es de +0,35% a +1,94%, y el
coste total sigue dominado por la comisión (0,1270–0,1432%). La conclusión de
fondo sigue igual:

```
0 de 8 tramos con significación
2 de 8 sobreviven a quitar las 3 mejores operaciones (los dos de SOL)
```

Y la profundidad **sí importa para el dimensionamiento**, pero a partir de
100.000 USDT, no antes: a 500.000 el deslizamiento va de 0,003% en BTC a
0,090% en XRP, y **XRP pasa a ser el símbolo más caro, no SOL**.

## Una cosa que el test no puede exigir

La serie de deslizamiento **no es estrictamente monótona**: en SOL se midió
0,01504% a 25.000 y 0,01438% a 100.000. Cada nocional se midió en una toma
distinta del libro y el libro se mueve. El test comprueba la tendencia y la
magnitud, no la monotonia, y el motivo está escrito en el propio test: obligar
a que la serie suba a cada paso sería exigir algo que el dato no tiene.

## Verificación

- **508 tests verdes** (507 + 1 reformulado).
- **Control de mutación**: reintroducir el número retractado de SOL
  (0,18220) → 2 fallos.
- Los tres tests que fijaban la tabla anterior se han reescrito: afirmaban
  cosas que eran consecuencias del error, y un test que afirma una consecuencia
  del bug no mide el bug.

---

# FASE 1h: el bug que quedaba vivo en producción

## Lo que se encontró al mirar qué valor llevaba la constante

`COSTE_TAKER` seguía teniendo dentro el deslizamiento de **0,2135%** — el
número que se retractó en la fase anterior. Y el adaptador lo usaba como
**valor por defecto**.

**La ruta de producción estaba cobrando 4,4 veces de más** (0,5538% contra
0,1268% de comisión sola), y no lo decía en ninguna parte. Un backtest hecho
por el sistema llevaba tres fases usando un número que ya se sabía falso.

Esto no se detectó mirando los resultados: se detectó mirando **qué valor
llevaba la constante** que se acababa de corregir en otro sitio. Dos medidas
del mismo número, en sitios distintos, y el arreglo se aplicó a uno solo.

## Qué hace ahora la ruta de producción

Nada de constantes heredadas. El coste se **calcula**:

| Componente | De dónde sale |
|---|---|
| Comisión por lado | 0,000634 taker / 0,000134 maker |
| Deslizamiento de primer nivel | tabla medida **por símbolo** |
| Deslizamiento de profundidad | fila medida del **nocional**, si la hay |
| Funding | tasa del **régimen que le toca a los datos**, deducido de la fecha de la primera vela |

Que el régimen se **deduzca** de la vela y no se pase a mano es lo importante:
el funding de 2025-2026 es entre 3 y 10 veces más barato que el de 2023-2024,
así que un valor por defecto cobraba el régimen equivocado a la mitad de los
backtests.

## Efecto medido sobre ATI

Retorno de la cuenta por operación, ya con el coste dentro del motor:

| Símbolo | Tramo | **antes** | **ahora** | cambio |
|---|---|---:|---:|---:|
| BTC | 2023-2024 | +0,3695 | +0,4259 | +0,0565 |
| BTC | 2025-2026 | −0,0100 | +0,0819 | +0,0920 |
| ETH | 2025-2026 | −0,0097 | +0,0828 | +0,0926 |
| XRP | 2025-2026 | −0,1743 | −0,0860 | +0,0882 |
| SOL | 2023-2024 | +1,8216 | +1,7965 | **−0,0251** |
| SOL | 2025-2026 | +0,0054 | +0,1043 | +0,0989 |

```
Tramos con expectativa negativa antes:  3 de 8
Tramos con expectativa negativa ahora: 1 de 8
```

**El arreglo no es uniformemente favorable, y conviene decirlo.** SOL
2023-2024 empeora: se le saves 0,42% de deslizamiento inflado pero se le cobra
el funding que antes era cero, y en el régimen de 2023-2024 ese funding es de
0,01079% cada 8 horas sobre 8,5 días: 0,277%. Cobrar lo que no existía pesa
más que ahorrar lo que sobraba.

## Respaldo en investigación, 2026-10-02

Tres cosas confirmadas contra fuentes externas y **medidas** en los datos:

1. **Comisiones Bybit VIP 0 publicadas: taker 0,0550%, maker 0,0200%** por
   lado. Las medidas aquí dan 0,0634% y 0,0134%: la de taker es un 15% más
   alta que la publicada y la de maker más baja. Se usa la medida por ser la
   propia, y la diferencia queda anotada en el código en vez de escondida.
2. **El signo del funding es exactamente el que se asumía**: positivo →
   los largos pagan; negativo → los cortos pagan. Confirmado en la literatura,
   y coincide con la serie descargada, que sale negativa entre el 10% y el 38%
   de los periodos según símbolo y régimen.
3. **El funding se cobra en instantes discretos** (00:00, 08:00, 16:00 UTC), no
   prorrateado. Y **la periodicidad puede ser de 1 hora en otros pares**.
   Medido aquí: los cuatro liquidan a las 8 horas exactas, 3.800 de 3.800, sin
   una excepción. Queda comprobado y anotado como invariante.

## Verificación

- **512 tests verdes**.
- **Control de mutación triple, los tres cazados**:
  - volver a la constante retractada en el adaptador → 1 fallo
  - devolver el deslizamiento retractado al suelo → 1 fallo
  - period，`o por defecto en vez de deducido → 1 fallo

---

# FASE 1i: funding discreto, y el dead end de las comisiones por par

## El funding se cobra en instantes, no prorrateado

**Medido y confirmado por dos vías independientes:**

1. De los 3.800 periodos descargados por símbolo: intervalo de **8,00 horas
   exactas en los 3.800**, sin una excepción, siempre a las 00:00, 08:00 y 16:00
   UTC.
2. Del endpoint `instrumentsInfo`: `fundingInterval = 480` minutos = 8 horas
   en los cuatro pares.

Antes se prorrateaba: `tasa × horas / 8`. Eso mete cobros que en el exchange no
ocurren (12,15 horas no son un cobro y un doceavo) y **promedia un tramo donde
se paga con uno donde se recibe**. Con velas de 15 minutos, cada cobro cae en
una vela distinta — las barras 0, 32 y 64 de cada día — y con su tasa real.

## Efecto medido: el discreto es PEOR en 8 de 8

| Símbolo | Tramo | prorrateado | **discreto** | cambio |
|---|---|---:|---:|---:|
| BTC | 2023-2024 | +0,4259 | +0,4138 | −0,0121 |
| BTC | 2025-2026 | +0,0819 | +0,0804 | −0,0015 |
| ETH | 2023-2024 | +0,2261 | +0,2146 | −0,0115 |
| ETH | 2025-2026 | +0,0828 | +0,0769 | −0,0059 |
| XRP | 2025-2026 | −0,0860 | −0,0953 | −0,0093 |
| SOL | 2023-2024 | +1,7965 | +1,7742 | −0,0223 |

**El prorrateo cobraba de menos, en los ocho tramos.** El modelo correcto es
el que da peor resultado, que es lo único que hace creíble un modelo.

La magnitud es pequeña (0,001 a 0,022 puntos por operación) y **no cambia el
veredicto**.

## Un test que pasaba sin comprobar nada

El primer test del signo pasó a la primera. Motivo: **`run_backtest` no llama
a la estrategia barra a barra — le pide la lista completa de órdenes de una
vez.** La estrategia de prueba devolvía "comprar, luego vender" pensando que se
evaluaba en cada barra, así que la posición se cerraba en la barra 0 y la
ventana del cobro era de una sola barra. **La serie de −1% nunca caía dentro y
el test no comparaba nada.**

Rehecho con una posición explícita de 100 barras, y con una aserción que
comprueba que la ventana contiene el cobro antes de mirar el signo.

## Comisiones por par: dead end declarado

`publicGetV5MarketFeeGroupInfo` devuelve **`retCode 10001`** con las tres
variantes de parámetros probadas (`accountType=UNIFIED`, `SPOT`, y con
`category`). `instrumentsInfo` no lleva comisión.

Lo que queda son dos fuentes, y las dos están anotadas en el código:

- **Publicada de Bybit VIP 0**: taker 0,0550%, maker 0,0200% por lado.
- **Medida aquí**: 0,0634% taker y 0,0134% maker. La de taker es un **15% más
  alta** que la publicada.

Se usa la medida, por ser la propia, y **la diferencia queda escrita en vez de
escondida**. El hueco —que BTC y XRP pueden tener comisiones distintas— queda
documentado, no relleno.

## Lo que queda abierto, y es que no se puede cerrar

- **El spread histórico.** El exchange no lo publica y no sale de las velas:
  `high`/`low` son el rango, no el precio de ejecución. Los números de 2023 y
  2024 usan una foto de 2026-10-02.
- **La profundidad por encima de 500.000 USDT** solo está medida a una
  instantánea por símbolo.
- **La tasa real de cada cobro**, no la del régimen: el modelo usa la tasa media
  del periodo, no la serie. La serie está en disco y el motor ya sabe leerla;
  lo que no se ha hecho es alinear cada cobro de cada operación con su tasa, en
  vez de con la del régimen.

Ese último es el que queda más cerca y es el que más importa: con el funding
negativo entre el 10% y el 38% de los periodos, **qué tasa tocó a cada cobro**
cambia el resultado más que cualquier otro número del modelo.

## Verificación

- **517 tests verdes**.
- **Control de mutación, los dos cazados**:
  - invertir el signo del cobro → 1 fallo
  - prorratear en vez de sumar los cobros → 1 fallo

---

# FASE 1j: la cobertura de la serie, que era dinero gratis

## Lo que se encontró al verificar que la serie llegaba

La serie real **sí** estaba llegando: 1.918 cobros colocados sobre 1.917
esperados, y su media (0,00270%) cuadra con la del régimen. Eso estaba bien.

Lo que estaba mal era **qué pasa cuando la serie no cubre la ventana**:

```
cobros esperados en una ventana de 9 meses:  4.110
cobros con dato:                             1.606
cobros que se cobraban a CERO:               2.504
```

`cuotas_funding_por_barra` deja en cero los instantes sin dato, y como el
motor con serie presente cobra **la suma** de las cuotas, la parte sin
cobertura **se cobra a cero**. En un caso de prueba de 20 días: **37% del
funding del periodo, gratis y en silencio**.

Eso es **peor que el prorrateo** que arreglé en la fase anterior: allí al
menos había una aproximación declarada. Aquí no había nada — ni aproximación,
ni aviso, ni un cero que significara cero.

## El arreglo

`cuotas_funding_completas` rellena los cobros que faltan con la tasa media del
régimen y **devuelve cuántos ha rellenado**, para que quien llama lo diga. El
adaptador lo registra como `warning`.

Sin `tasa_periodo` **no rellena nada**: rellenar con una tasa inventada sería
cambiar un optimismo silencioso por otro. Lo que no se sabe no se rellena.

| | cobros | suma de cuotas |
|---|---:|---:|
| Sin rellenar | 20 de 63 | 0,002000 |
| Con rellenar | 63 de 63 | 0,003161 |

## El respaldo sin serie también cobra cobros completos

Sin serie, el motor prorrateaba: `tasa × horas / 8`. Ya se midió que con la
serie real el cobro discreto sale **más caro en los 8 de 8 tramos**, o sea que
prorratear **cobraba de menos**. El respaldo ahora cuenta cobros enteros
(`horas // 8`) y va por debajo del discreto solo en los tramos que caen justo
en un borde. Está declarado en el código.

## Un `timeframe` omitido hacía el funding 4× grande

Al escribir el test del respaldo, el motor contó 199 horas donde había 49,75:
no se le estaba pasando `timeframe`, así que usaba su valor por defecto de
**1h** con velas de 15m. **El funding salía cuatro veces grande.**

El adaptador ya lo pasa (por el bug que ya se corrigió), y ahora hay un test
que lo fija. Es la segunda vez que el mismo descuido aparece en dos sitios
distintos, y por eso tiene que estar en la firma, no en un valor por defecto
silencioso.

## Una mutación que no la cazó nadie

Reemplazar el adaptador por la variante **sin rellenar** daba
**521 passed**. El test de `cuotas_funding_completas` sí que fallaba — hay
que probarlo primero, no después de escribirlo. Añadido el test que comprueba
que **el adaptador llama a la versión que rellena**, y la mutación ahora da
1 fallo.

**Un código bien probado y un código sin usar son cosas distintas**, y solo la
segunda importa en producción.

## Verificación

- **522 tests verdes**.
- **Control de mutación, los tres cazados**:
  - no rellenar los huecos → 1 fallo
  - volver al prorrateo en el respaldo → 1 fallo
  - el adaptador usa la serie sin rellenar → 1 fallo

## Estado del modelo de coste

| Componente | Cómo está |
|---|---|
| Comisión | medida, con la publicada anotada al lado |
| Deslizamiento primer nivel | medido **por símbolo** |
| Deslizamiento de profundidad | medido **por nocional**, sin huecos |
| Funding | serie **real por cobro**, con huecos rellenados y contados |
| Suelo de comisión | sin deslizamiento ni funding, a propósito |

Lo que **no** se puede cerrar y está escrito en el código: el spread
histórico, que el exchange no publica y las velas no contienen.

---

# FASE 1k: revalidación de la KB antigua

## Lo primero: la KB actual no tiene nada que revalidar

`autonomous_research/data/hypotheses.jsonl` tiene **114 líneas y un solo
campo**: `hypothesis_id`. Los demás campos están a `None` en las 114. Son
cascarones.

El contenido real está en la cuarentena del 2026-10-01:
`qmp-limpieza-2026-10-01/01-kb-hypotheses/hypotheses_classic-xrp.jsonl`, con
**669 hipótesis con contenido** (y 940 en `hypotheses_rejects.jsonl`, de las
que solo 3 tienen contenido).

## El resultado, y es rotundo

```
hipotesis con contenido:               669
estados:                               669 failed
max_drawdown == 0.0 en                 669 de 669
sharpe fuera de [-3, +3] en            553 de 669
```

**Las 669 tenían el drawdown a cero.** No "muchas": *todas*. El bug era
universal, así que la parte de riesgo de su `scientific_score` valía
exactamente cero en cada una. Y el 83% tenía un sharpe fuera de cualquier
rango plausible.

Eso significa que **`scientific_score` nunca midió riesgo en ninguna
hipótesis**, y el umbral de 0,6 se aplicó sobre un número cuya parte de
riesgo era constante cero.

## Solo 3 de 13 combinaciones se pueden reconstruir

| | |
|---|---:|
| combinaciones (símbolo, estrategia) distintas | 13 |
| de las cuales el motor **sabe construir hoy** | **3** |

Las otras 10 apuntan a estrategias que el motor ya no tiene. Una hipótesis
sobre código que no existe no se revalida: **se tira y se vuelve a generar.**

## Las tres que sí, con el motor correcto

| Símbolo | Nombre | n antes | n ahora | esp antes | esp ahora | **dd antes** | **dd ahora** |
|---|---|---:|---:|---:|---:|---:|---:|
| ETH | Breakout_15 | 43 | 2.137 | **−22,91%** | −0,0131% | 0,0000 | **32,29%** |
| SOL | Breakout_15 | 72 | 205 | −0,4582% | −0,3654% | 0,0000 | **75,04%** |
| XRP | Breakout_15 | 78 | 240 | −0,0232% | −0,3123% | 0,0000 | **74,96%** |

- La expectativa de ETH era **−22,91% por operación**, una cifra imposible.
  Sale de la serie de 15 minutos completa sobre 2.137 operaciones.
- Los drawdowns reales son del **32% al 75%**. Los antiguos decían 0,0.
- Expectativa positiva: **0 antes, 0 ahora**.

## La conclusión

**Las 669 siguen siendo `failed`, y lo estarían igual.** El problema no eran
las métricas: eran las estrategias. Arreglar el motor no resucita ninguna
hipótesis, y decirlo es más útil que(이) responsabilidad: si alguien
reescribiera sus métricas y las hipotesis aparecieran como buenas, sería un
error.

Y hay un dato estructural que pesa más que el resultado: **10 de 13 familias
de hipótesis apuntan a código que ya no existe.** La mayor parte de la KB no
es un registro de estrategias buenas, es un registro de funciones borradas.
Revalidarla es trabajo perdido; lo que vale es **volver a generar desde cero**
sobre las 8 familias de producción, que ya están medidas en la Fase 1.

## Lo que queda por decidir

- **`scientific_score = 0,6`** se aplicó sobre un número con la parte de
  riesgo a cero constante. Sigue sin decidir, y ahora se sabe que el umbral
  no estaba midiendo lo que parecía.
- **Si la KB se limpia.** Las 114 líneas actuales son índices sin contenido y
  no sirven para nada. Las 669 están en cuarentena y no se han tocado.
