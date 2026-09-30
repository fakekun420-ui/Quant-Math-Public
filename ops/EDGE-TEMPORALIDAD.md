# El edge existe, pero es más fino que el coste de ejecutarlo

> Medición propia del 2026-09-30, con velas reales de **mainnet** (BTCUSDT,
> ETHUSDT, XRPUSDT), corte temporal 70/30 sin solape. Sin costes de comisión.
> **Este documento NO promete rentabilidad.** Dice qué se midió, con qué n, y
> qué queda sin medir.

## El resultado que cambia la decisión

La pregunta «¿tenemos edge?» tiene dos respuestas distintas según si se mire
antes o después de pagar por operar:

| | BTC | ETH | XRP |
|---|---|---|---|
| **Bruto** (fuera de muestra) | +0,016% | +0,032% | +0,029% |
| **Coste** ida y vuelta | 0,100% | 0,100% | 0,100% |
| **Neto a 1 h** | **−0,084%** | **−0,068%** | **−0,071%** |

**Sí hay señal: 35 de 36 combinaciones salieron positivas fuera de muestra**
(12 combinaciones de parámetros × 3 símbolos). El problema es de magnitud: el
edge bruto por operación es de 0,01–0,07% y el coste de entrada y salida es de
**0,10% por operación**.

Eso explica por qué la auditoría del 2026-09-29 medió `expectancy_test =
−0,1914%`: no era un espejismo, era un edge real más fino que el coste.

## La palanca: la temporalidad, no las estrategias

El coste es **por operación**, así que lo que hace falta no es una estrategia
mejor sino **que cada operación mueva más**. Medido a tres temporalidades,
fuera de muestra:

| Temporalidad | BTC | ETH | XRP |
|---|---|---|---|
| 1 h | −0,084% | −0,068% | −0,071% |
| **4 h** | **+0,005%** | **+0,131%** | **+0,089%** |
| 1 d | −0,259% | −0,341% | +0,210% |

**En 4 h el edge sobrevive al coste en los tres símbolos.** El movimiento medio
por operación pasa de 0,02–0,03% (1 h) a 0,10–0,23% (4 h), y eso es lo que
cruza el umbral de 0,10%.

El sistema venía configurado en **1 h**, que es exactamente la temporalidad donde
el edge no llega. Esa es la palanca concreta, y es una decisión de producto:
`timeframe` en `OrchestratorConfig`.

## Selectividad: probada y NO ayuda

Cuanto más selectiva es la entrada, menos operaciones y peor el resultado neto:

| Umbral de entrada | BTC neto | ETH neto | n (BTC) |
|---|---|---|---|
| 0,000 | −0,098% | −0,075% | 133 |
| 0,003 | −0,081% | −0,071% | 67 |
| 0,010 | −0,090% | −0,090% | 36 |

Reducir las operaciones a la cuarta parte **empeoró** el neto. No es un problema
de demasiadas operaciones: es que el movimiento medio por operación no crece
con la selectividad.

## Qué NO se ha medido

Esto es una medición, no una garantía:

1. **Un solo corte 70/30, no walk-forward.** Con `n` de 100–143 por celda, un
   cambio de régimen puede mover el resultado.
2. **Sin commission de exchange.** El coste medido es solo el slippage del motor
   (`2 × 0,0005`). La comisión real de Bybit (0,05% taker por lado) **empeoraría**
   el neto, y no está modelada en paper.
3. **Sin el SL/TP del sistema.** Son cruces de medias sin stop: el motor real
   corta a 25% ROE y eso cambia el resultado.
4. **Solo tendencia.** No se han probado familias con señal direccional.
5. **n pequeño.** Por debajo de ~100 operaciones la diferencia entre +0,005% y
   −0,005% no significa nada.

## Conclusión accionable

No hay un «arreglar el edge»: hay **configurarlo donde el edge existe**. La
medida concreta es operar en **4 h** en vez de 1 h, y validar eso con
walk-forward antes de creérselo. Antes de mainnet, el orden sensato es:

1. Cambiar el timeframe a 4 h y repetir esta medición con walk-forward.
2. Modelar comisión de exchange (0,05% taker, 0,02% maker por lado) en el
   gate: si el edge no lo aguanta, no es edge.
3. Solo entonces, live en testnet, con las claves que aún no existen.

Mientras tanto el sistema está **en paper y explorando**, que es lo correcto:
no cuesta dinero y sigueacousticamente acumulando cierres para el SIS.

## ACTUALIZADO 2026-09-30: la comisión real cambia el veredicto

Lo de arriba está **desactualizado** y hay que leerlo con esta corrección encima.
La comisión de Bybit estaba ausente: el gate contaba solo slippage (0,10% por
ida y vuelta) cuando el real es **0,22% con taker**.

Leída del API el 2026-09-30 (`load_markets()['BTC/USDT:USDT']`):
`taker = 0,0006` (0,06% por lado) y `maker = 0,0001` (0,01% por lado).

Y Leonardo opera a **1 m**, no a 1 h. Medido a cuatro temporalidades, BTCUSDT,
fuera de muestra, 70/30, con las medias ajustadas a cada escala:

| Temporalidad | Bruto | taker (0,22%) | maker (0,12%) |
|---|---|---|---|
| **1 m** | −0,0009% | −0,2209% | −0,1209% |
| 5 m | +0,0027% | −0,2173% | −0,1173% |
| 15 m | −0,0056% | −0,2256% | −0,1256% |
| 1 h | +0,0161% | −0,2039% | −0,1039% |
| 4 h | +0,1052% | −0,1148% | −0,0148% |

**Ninguna temporalidad gana con taker. Con maker, la mejor (4 h) queda en
−0,0148%.** El edge no cubre el coste de operar.

### Qué cambia de la conclusión

1. A 1 m **no hay ni edge bruto**: es −0,0009%, que es cero. El movimiento
   por operación es cien veces más pequeño que el coste. Cruces de medias a
   1 m no pueden funcionar, y no es cuestión de afinar parámetros.
2. La temporalidad sigue siendo la palanca correcta *en dirección*, porque el
   coste es por operación y cada vela debe mover más (0,001% a 1 m frente a
   0,105% a 4 h), pero **subir a 4 h no basta**: se acerca al coste, no lo
   supera.
3. La conclusión de abajo («poner 4 h y repetir con walk-forward») queda
   **desaconsejada con los números reales**: repetirla seguiría dando negativo.
   Lo que hace falta es una estrategia cuyo movimiento medio por operación
   supere 0,22%, no elegir mejor entre las que ya se han medido.
4. Se ha añadido `QUANTMATH_COST_FLOOR_GATE` para que, cuando se opere, el
   gate compare el expectancy contra el **coste real** y no contra cero. Con
   el gate así, ninguna de las estrategias medidas de arriba sería aceptable:
   eso es exactamente lo que tiene que hacer.
