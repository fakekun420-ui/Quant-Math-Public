# El plan de Leonardo a números — y por qué 100× no lo sostiene

> Estimación del 2026-09-30 con los números reales de Bybit (comisión taker
> 0,06% por lado leída del API, slippage 0,05% por lado del motor, MMR 0,33%
> del primer tramo). **No es una promesa de rentabilidad**: es la aritmética
> de su plan tal como lo describió.

## El plan, tal como lo describe

5 USDT de capital, ×100, 5-10% del capital por operación (lo que permita
meter el mínimo de 5 USDT de nocional después del apalancamiento), TP 2:1.
«Se ganan centavos, pero si hacemos muchas operaciones se gana al final por
el riesgo beneficio.»

## Lo que funciona de ese plan

- El margen cumple el mínimo de Bybit: con 5% son 0,25 USDT de margen y
  25 USDT de nocional; con 10%, 0,50 y 50. Muy por encima del mínimo de 5.
- **El SL se alcanza antes que la liquidación**: a 100× la liquidación está
  a 0,67% de precio y el SL de 25% ROE está a 0,25%. Hay holgura.
- La ratio 2:1 es buena: con SL a la mitad del TP, hace falta un 33,3% de
  aciertos para indiferencia **si no costara operar**.

## El problema: el coste se come el objetivo

El coste de ida y vuelta es 0,22% del nocional. A 100×, el TP de 50% ROE son
**0,50% de precio**: el coste se come el **44% del objetivo**.

| | por operación | % de tus 5 USDT |
|---|---|---|
| Ganando (50% ROE) | **+0,07 USDT** | +1,40% |
| Perdiendo (25% ROE) | **−0,12 USDT** | −2,35% |
| **Winrate de indiferencia** | **62,7%** | |

Sin coste sería 33,3%. Con el coste real son **62,7%**, porque cada operación
pierde casi 4,7% de tu capital si se equivoca y gana 1,4% si acierta.

El winrate medido en el research es **39,68%** (fuera de muestra, n=814).

## La corrección que importa: el apalancamiento

**El apalancamiento no se cancela en esta aritmética, y bajarlo es la
palanza.** El coste es % del nocional y es fijo; el objetivo en ROE se
convierte a precio dividiendo por el apalancamiento. O sea que **bajar el
apalancamiento agranda el objetivo respecto a un coste que no cambia**.

| Apalancamiento | TP en % de precio | El coste es… | Indiferencia |
|---|---|---|---|
| 100× | 0,50% | el 44% del objetivo | **62,7%** |
| 50× | 1,00% | el 22% | 48,0% |
| 30× | 1,67% | el 13% | 42,1% |
| **20×** | **2,50%** | **el 9%** | **39,2%** |

**A 20×, con el mismo TP 50% ROE / SL 25% ROE, la indiferencia cae a 39,2%:
por debajo de tu 39,68% medido.** Y el mínimo de Bybit sigue cumpliéndose:
5% de 5 USDT a 20× son 5 USDT de nocional, justo el mínimo; 10% son 10.

## AVISO IMPORTANTE: esto es un margen de 0,5 puntos

39,2% exigidos contra 39,68% medidos son **0,5 puntos porcentuales de
margen**. Eso está dentro del ruido de la muestra. No es un edge robusto:
es un empate técnico.

Además, el winrate **depende del tamaño del objetivo**, y el 39,68% se midió
con cruces de medias a 1 h, no con un objetivo de 2,5% de precio. Un objetivo
mayor tiene **menos** probabilidad de alcanzarse, así que el winrate real con
esos parámetros sería **menor** que 39,68%. Sustituir el 39,68% en la tabla es
una primera aproximación optimista, no un resultado.

## Qué haría falta de verdad

1. **Bajar a 20× o menos** y empezar por ahí, con SL a 1,25% de precio, que
   está 3,7× por dentro de la liquidación. El 100× no lo sostiene con coste real.
2. **Órdenes maker en lugar de taker**: baja el coste de 0,22% a 0,12%, y la
   indiferencia a 30× cae de 42,1% a 38,1%.
3. **No muchas operaciones como multiplicador.** La tesis de «muchas operaciones»
   funciona con una aritmética donde la operación vale positiva; aquí cada
   operación vale −1,4% de capital cuando acierta mal. Más operaciones es más
  速度 de perder.

## Lo que NO se ha medido

- El winrate real con objetivo de 2,5% de precio (solo se ha medido el de
  cruces de medias a 1 h).
- El efecto del funding en mantenimiento a 100×.
- La comisión concreta de la cuenta de Leonardo (depende del nivel VIP; se usó
  la tarifa estándar leída del API).
