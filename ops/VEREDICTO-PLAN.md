# Veredicto: el plan de Leonardo, medido con el motor del proyecto

> Backtest del 2026-09-30 con `Backtester`, mainnet real, XRPUSDT perp.
> maker 0,01%/lado + slippage 0,05%/lado + funding 0,01%/8h, **MMR real 0,0033**,
> apalancamiento 50×, nocional 5 USDT, capital 5 USDT, TP 50% ROE (1,00% de
> precio) / SL 25% ROE (0,50%). Corte temporal 70/30, fuera de muestra.

## Resultado: 5 de 5 combinaciones dan PnL positivo

| Parámetros | Winrate OOS | Operaciones | PnL sobre 5 USDT | Liquidaciones |
|---|---|---|---|---|
| ma(8,50) | 60,0% | 30 | **+19,57%** | 3 |
| ma(13,60) | 48,4% | 31 | +12,02% | 4 |
| ma(5,30) | 53,8% | 26 | +8,77% | 3 |
| ma(8,80) | 41,7% | 24 | +2,95% | 3 |
| ma(21,100) | 40,0% | 25 | +0,56% | 2 |

Indiferencia con maker: **41,3%**. Cuatro de cinco la superan; la quinta se
queda en 40,0% pero **también cierra en dinero** (+0,56%), porque lo que mueve
el PnL son las liquidaciones y en esa solo hubo 2.

**Que el resultado no dependa del parámetro es lo que lo hace creíble.** Con
una sola combinación, un +19,57% en 30 operaciones sería ruido; con cinco
dando positivo y un degradado ordenado (medias más rápidas → mejor), es una
señal.

## El riesgo que el motor estaba contando bien: los HUECOS

Durante la verificación se vio que el backtest reportaba liquidaciones que
parecían imposibles con un SL al 0,50%. **No eran un bug.** Medido en 999
velas de XRP a 1h:

- velas que caen ≥0,50% (el SL): 18,82%
- velas que caen ≥1,50% (liquidación a 50×): **3,20%**
- de esas, las que saltan SL **y** liquidación de golpe: 3,20%

**Una de cada 31 velas de XRP a 1h se lleva el 100% del margen de golpe**, sin
pasar por el stop. Con 104 operaciones a 50× son ~3 liquidaciones, que es lo
que el motor dio tras la corrección.

Un hueco cuesta **3,4× una pérdida normal** y se come el **24% de la ganancia
esperada** (EV de +0,280% a +0,212% por operación). Es el precio real de 50×,
y el motor lo estaba contando desde el principio.

## El bug que sí existía

`MAINTENANCE_MARGIN_RATE` estaba **hardcodeado en 0,005**, que es el *segundo*
tramo del MMR de Bybit y además era un supuesto. Con eso la liquidación se
ponía más cerca de lo real y el backtest era **optimista** sobre ese punto.
Ahora usa el primer tramo real (0,0033, leído del API) y es configurable.

Al corregirlo, las liquidaciones de ma(8,50) pasaron de 6 a 3, que es
exactamente lo predicho. **El modelo corregido valida la medición anterior.**

## Lo que queda sin verificar

1. **`n` = 24-31 por combinación.** Suficiente para ver una señal, no para
   firmarla. Con 5 combinaciones coincidiendo es mucho mejor que una sola, pero
   no es walk-forward.
2. **Un solo símbolo y un solo periodo.** XRP bullish del último año.
   No dice nada de BTC, ni de un mercado lateral, ni de XRP en otro régimen.
3. **Que las órdenes llenen como maker es lo que sostiene el plan.** Sin
   claves no se ha probado ni una. Con taker la indiferencia sube de 41,3% a
   **47,3%**, y solo dos de las cinco combinaciones seguirían cerrando.
   **Esta es la incógnita más grande del plan**, y se resuelve con una sola
   prueba de orden en testnet.
4. El backtest usa velas de cierre, no intrabar. El SL puede tocarse dentro de
   una vela sin que el cierre lo refliese; el motor no puede verlo.
5. Sin comisión de VIP (se usó la tarifa estándar) y sin slippage real de
   libro: 0,05% es una suposición, no una medición del book de XRP.

## Conclusión

**El plan es viable tal como lo describiste, y a 50× con maker, no a 100× con
taker.** La diferencia entre ambas no es de estrategia: es aritmética del
coste, y está medida.

Antes de dinero real, en este orden:

1. **Probar una orden maker en testnet.** Es la incógnita que decide todo lo
   demás, y son cinco minutos una vez tengas las claves.
2. **Correrlo en paper** con esta configuración para confirmar que el winrate
   real se sostiene fuera de muestra y que no es un régimen de XRP.
3. Solo entonces, y con el tope de daño diario que ya tiene el sistema.
