# Modulos muertos de `RiskManager` — que se ganaria y que hay que medir antes de conectar

**Fecha:** 2026-10-01 · **Origen:** encargo de diagnostico y arreglo del Kelly silencioso.

`quant_math/risk/risk_manager.py` instancia siete objetos en sus lineas 52-58. Produccion solo
llama `check_position_size()` (desde `quant_math/orchestrator.py`, dentro de `_apply_margin_cap`).
De los siete, el unico que esa ruta necesitaba era el Kelly — estaba reimplementado a mano y
devolia 0.0 silencioso — y **ya esta conectado** al modulo canonico
(`quant_math.risk.sizing.KellyCriterion`) con estado explicito (`kelly_status`/`kelly_note`).
Este documento es la entrega pendiente: los otros seis.

## Inventario medido

Medida: `grep -c "self.<attr>" quant_math/risk/risk_manager.py` (ocurrencias = instanciacion +
usos).

| Objeto | Atributo | Linea | Usos en el fichero | Estado |
|---|---|---|---|---|
| `KellyCriterion` | `self.kelly` | 54 | 2 (instanciacion + `_kelly_assessment`) | **CONECTADO 2026-10-01** |
| `PositionSizer` | `self.position_sizer` | 52 | 1 (solo instanciacion) | muerto AQUI |
| `StopLoss` | `self.stop_loss` | 53 | 1 (solo instanciacion) | muerto |
| `ValueAtRisk` | `self.var_calculator` | 55 | 3 (solo dentro de `calculate_risk_metrics`) | huerfano |
| `ExpectedShortfall` | `self.es_calculator` | 56 | 3 (solo dentro de `calculate_risk_metrics`) | huerfano |
| `DrawdownAnalyzer` | `self.drawdown_analyzer` | 57 | 1 (solo instanciacion) | muerto |
| `SharpeMetrics` | `self.sharpe_metrics` | 58 | 1 (solo instanciacion) | muerto |

"**Huerfano**" significa que el metodo que los usa existe y es correcto, pero **nadie lo llama**:
`grep -rn "calculate_risk_metrics\|stress_test_strategy\|check_drawdown_limit\|check_sharpe_\
threshold\|check_sortino_threshold\|check_calmar_threshold\|check_correlation_risk" --include=*.py`
no devuelve ningun llamador en produccion (el unico `calculate_risk_metrics` que aparece es de
`risk/examples.py`, y es de OTRA clase: `PortfolioRisk`).

Copia adicional encontrada al diagnosticar: `quant_math/autonomous_research/adapters/risk_manager.py`
(`RiskManagementEngine`) reimplementa el MISMO Kelly a mano con placeholders fijos
(`win_rate = 0.5`, `win_loss_ratio = 2.0`, lineas 142-149) y **no se instancia en ninguna parte**
medida. `quant_math/autonomous_research/adapters/quant_math_adapter.py:761` tiene una tercera
variante (`kelly_fraction = 0.2` hardcodeado). No se tocan: estan en el camino de `autonomous_research`,
fuera de la ruta de dinero, y no hay evidencia de uso. Se anotan para no olvidarlos.

---

## 1. `PositionSizer` (`self.position_sizer`, linea 52)

**Que se gania:** que el tamano proponga un METODO (fixed_fractional, kelly, volatility_target,
atr_based) en vez de solo el techo porcentual `max_position_size_pct`. Hoy la decision de tamano
esta partida en dos sitios: el tope de margen/riesgo y el tope de nocional viven en
`_apply_margin_cap` (orquestador) y el unico uso de la clase es `PositionSizer.calculate` de
riesgo-por-operacion — `RiskManager` no decide tamano, solo veta.

**Que medir antes de conectar:**
1. **Replay del ledger real**: cuantos tamanos cambiarian entre metodos sobre las operaciones ya
   cerradas (nocional tipico hoy: 10-28 USD, margen 0.10-0.28 USD a 100x).
2. **Datos de entrada**: `calculate_size` exige `entry_price`/`stop_price`; al check hoy solo
   llega `sl_distance`. Confirmar que el precio de SL llega a tiempo de decidir.
3. **No duplicar el Kelly**: el metodo `"kelly"` del sizer usa `KellyCriterion` con su propia
   fraccion (0.5 por defecto) — definir cual fraccion manda (hoy `RiskManager.kelly_fraction`=0.3).
4. **walk-forward** fixed_fractional vs volatility_target con el cost floor real (0.1268%).

## 2. `StopLoss` (`self.stop_loss`, linea 53)

**Que se gania:** validar TP/SL dentro del propio check de tamano: un solo sitio que diga
"esta entrada es operable o no".

**Que medir antes de conectar:**
1. **Solape con `risk/roe_targets.build_roe_plan`**, que YA valida SL contra la liquidacion con
   clamp medido (el runtime lo declara en sus `warnings`: "la seguridad es ley"). Conectar
   `StopLoss` sin decidir quien manda duplica reglas y puede PISAR ese clamp: antes,
   replay de las dos reglas sobre el mismo plan y elegir.
2. **Replay**: cuantos checks cambiarian de aprobado a rechazado con el `StopLoss` activo.
3. Muestra: pares TP-SL por estrategia (aplicar el mismo piso de 20 del Kelly).

## 3. `ValueAtRisk` + `ExpectedShortfall` (`self.var_calculator`, `self.es_calculator`, 55-56)

**Que se gania:** frenar el tamano por COLA de riesgo del PnL (VaR/ES a 95/99%) ademas del techo
porcentual. El codigo ya existe y es el que usa `calculate_risk_metrics` (parametrico:
`calculate(media, std, conf)`), solo que nadie lo invoca.

**Que medir antes de conectar:**
1. **Muestra**: hoy hay 9 posiciones unicas en el ledger. VaR-99 parametrico con n=9 es ruido
   puro: harian falta del orden de 100+ cierres. Mismo criterio de piso que el Kelly, dicho con
   el numero.
2. **Supuesto de normalidad**: hoy se pasa (media, std) de pnl bruto. Testearlo de verdad
   (`expectation/statistical_tests.py` tiene las pruebas) antes de creerse un VaR parametrico.
3. **Horizonte y unidad**: VaR por operacion, diario o por ciclo; en % de cuenta o en USD.
   Sin eso, dos calculos del mismo nombre no son comparables.
4. **Replay**: cuantas entradas habria recortado/rechazado el freno por VaR/ES y que PnL
   habria evitado o perdido. Si no mejora el resultado, no se conecta.
5. **Dato de entrada**: `calculate_risk_metrics` exige `StrategyResult.trades`, que la ruta de
   produccion hoy NO construye — hay que decidir si se reconstruye del ledger o se mide aparte.

## 4. `DrawdownAnalyzer` (`self.drawdown_analyzer`, linea 57)

**Que se gania:** corte automatico por drawdown dentro del dimensionamiento (analizar la serie de
equity en vez de solo el umbral).

**Que medir antes de conectar:**
1. **DUPLICADO**: `risk/circuit_breaker.DailyGuard` YA corta por drawdown
   (`drawdown_limit=0.2` en runtime, `guard.drawdown_limit`). Definir quien manda; dos guardas
   con el mismo umbral no anaden seguridad, anaden dos formas de discrepar.
2. **Serie**: el runtime lleva 3 ciclos (`drawdown_pct=0.0` en todo el arranque). Hace falta
   historico de equity (`daily_pnl.json` diario) para que el analizador tenga algo que analizar.
3. **Replay**: en que drawdown habria cortado respecto al guard actual, con la misma serie.

## 5. `SharpeMetrics` (`self.sharpe_metrics`, linea 58)

**Que se gania:** filtrar entradas por calidad de estrategia calculando el Sharpe/Sortino con el
modulo, en vez del `check_sharpe_threshold` que hoy es `sharpe >= 1.0` sobre un escalar que nadie
pasa y que nadie llama.

**Que medir antes de conectar:**
1. **Muestra por estrategia**: n_trades en backtest llega a 99 pero en vivo cada hipotesis tiene
   1-5 operaciones. Un Sharpe con n<30 es ruido; definir ventana y frecuencia de recalculo.
2. **Umbral**: 1.0 es un default sin evidencia de este negocio — hay que graduarlo con el
   replay (cuantas entradas veta y que coste de oportunidad tiene).
3. **Ventana**: rolling o desde el inicio; con regimenes de mercado (el runtime ya separa
   sesiones) un Sharpe global puede esconder el regime actual.

## 6. Los checks escalares y el stress test (sin atributo propio)

`check_sharpe_threshold`, `check_sortino_threshold`, `check_calmar_threshold`,
`check_correlation_risk`, `check_drawdown_limit`, `stress_test_strategy` y
`calculate_risk_metrics` estan implementados y **0 llamadores en produccion** (medido). Lo que se
gania al conectarlos es superficie de control ya escrita; lo que hay que medir antes es
**exactamente quien los llama y con que datos**: hoy no hay quien pase un `StrategyResult` con
`trades` ni una matriz de correlaciones por ciclo, y un check que nadie invoca no protege nada
(leccion medida en Kaenor el 2026-09-28: una defensa definida y nunca invocada no hace nada).

---

## Regla de oro para conectar cualquiera de los seis

Ninguno se conecta "porque existe". El paso minimo, en este orden:

1. **Muestra**: aplicar el mismo piso que el Kelly (`MIN_CLOSURES_FOR_KELLY = 20` en
   `risk_manager.py`) a la serie que alimenta el modulo. Si no llega, el modulo dice
   `insuficiente` en vez de inventar.
2. **Replay** sobre el ledger real: cuantos decisiones cambiarian y con que impacto en PnL.
3. **Decidir quien manda** cuando el modulo nuevo choque con un freno ya vivo
   (`DailyGuard`, `roe_targets`, tope de nocional).
4. Solo entonces conectar, con el estado explicito (`*_status`/`*_note`) que ya usa el Kelly:
   si el modulo no puede responder, lo dice, y el tamano cae en un metodo declarado.

**El Kelly de referencia (conectado 2026-10-01):** con los datos reales de
`runtime/state_classic-xrp` (25 filas de cierre = 9 posiciones unicas tras deduplicar, ver
`_ledger_kelly_stats`) el estado es `insuficiente` (9 < 20) y el dimensionado cae en
`max_position_size_pct = 20%` (1.72 USD de margen sobre 8.58 USD de equity). Antes decia 0.0 y
nadie sabia que eso significaba "no habia medida".
