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

---

## Decisiones de CONEXION (2026-10-01, encargo D2/ML) — los doce, uno a uno

Se aplico el orden del module-level sobre cada modulo: **muestra -> replay sobre el
ledger -> quien manda contra los frenos vivos -> solo entonces conexion con estado
explicito**. Nada se conecto "porque existe".

Suite: **400 tests antes -> 424 despues** (14 nuevos en
`tests/test_var_sharpe_conectados.py`; los 10 restantes son de otro agente que trabajo
en paralelo). Los 14 nuevos se comprobaron contra el estado ANTERIOR extrayendo HEAD
con `git archive` a `/tmp/qm_old` (sin tocar el working tree): **14 failed** alli,
**14 passed** aqui.

Nota: el `tests/MODULOS-MUERTOS-RIESGO.md` que menciona el encargo **no existe** en
disco; solo esta la copia de `ops/`.

### La muestra, medida hoy (el paso 1)

| Dato | Valor medido |
|---|---|
| Filas de cierre en `runtime/state_classic-xrp` | 14 |
| Posiciones unicas tras deduplicar | **9** (5 ganadoras, 4 perdedoras) |
| Cierres en el resto de `runtime/state_*` | **0** |
| Cierres por hipotesis (dedup) | hyp_0cd7e23b=6, hyp_62558bf3=1, hyp_dc24c22b=1, hyp_14a2983d=1 |
| Equity marcado / pico | 8.1998 / 10.8641 USD |
| Drawdown actual | **24.52% > 20% -> DailyGuard BLOQUEA entradas ya mismo** (`runtime_stats.json.risk_halt`) |
| Piso de la casa | 20 cierres -> **9 < 20: hoy NO se calcula ninguno de estos numeros** |

### El replay (el paso 2), con los 9 cierres reales

Serie en fraccion de la cuenta por cierre (media -0.00828, desviacion 0.02869, peor
cierre -7.42% de la cuenta):

| Numero | Valor con N=9 |
|---|---|
| VaR-95 | 5.5469% de la cuenta por cierre |
| ES-95 (tras el arreglo de abajo) | 6.7456% |
| VaR-99 / ES-99 | 7.5020% / 8.4741% |
| Sharpe por operacion (sin anualizar) | -0.2886 |
| Sortino por operacion (sin anualizar) | -0.2739 |
| Sharpe si se anualizara a 252 (el default del modulo) | **-4.5822** -> horizonte inventado |
| Leave-one-out del VaR-95 (quitar UN cierre) | **0.0256 .. 0.0596**, rango 3.40 pp = **61% del valor** |

Dos conclusiones que son las que fijan el diseno:

1. **El leave-one-out es el replay.** Con N=9, quitar una sola operacion mueve el VaR-95
   en un 61%. Cualquier umbral de freno por cola se estaria decidiendo sobre eso, asi que
   **no se define ningun umbral**: los estados son informativos y no vetan.
2. **BUG encontrado antes de conectar `var.py`**: `ExpectedShortfall` parametrico
   devolvia **0.0 SIEMPRE** — la formula tenia el signo de la dispersion cambiado
   (`-(mu + sigma*phi/alpha)` en vez de `-(mu - sigma*phi/alpha)`) y el
   `max(0.0, ...)` anulaba el resultado. Medido: `ES(0,1,0.95)` = 0.0 en vez de 2.0627,
   y el ES de la serie real del ledger = 0.0. O sea: el modulo afirmaba "no hay perdida
   en la cola del 5%". Se arreglo ANTES de conectarlo (prueba de que existia antes:
   `git show HEAD:quant_math/risk/var.py` cargado aparte devuelve 0.0). Con la formula
   correcta se cumple la invarianza `ES >= VaR` en todos los niveles, y esa invarianza
   quedo como test.

### CONECTADOS (2 modulos, con su estado hoy)

| Modulo | Como se conecta | Estado HOY (N=9) | Por que |
|---|---|---|---|
| `quant_math/risk/var.py` (`ValueAtRisk` + `ExpectedShortfall`) | `RiskManager._tail_risk_assessment`, llamado por `check_position_size(pnl_series=...)` | `var_status="insuficiente"` + nota con 9 y el piso 20; `var_95_frac/es_95_frac/var_99_frac/es_99_frac = None` | Es el freno por cola que el documento pedia, pero sin umbral (el replay no lo sustenta) y con dos pisos declarados: 20 para el 95% (piso de la casa) y 100 para el 99% (un cuantil al 99% se apoya en 1 obs. de cada 100) |
| `quant_math/expectation/sharpe_metrics.py` (`SharpeMetrics`) | `RiskManager._quality_assessment`, llamado por el mismo `check_position_size` | `sharpe_status="insuficiente"`; `sharpe`/`sortino` = None | Delega la formula en el modulo (antes reimplementada en la practica por nadie). Dos decisiones medicidas: **NO anualiza** (`periods_per_year=1`, la serie es por cierre) y **NO llama a `check_sharpe_threshold`** (el umbral 1.0 es un default sin evidencia) |

Dos cambios de apoyo, ambos necesarios para que la conexion no mienta:

* `ExpectedShortfall._parametric_es` arreglado (signo). Sin esto, conectar ES hubiera
  sido conectar un 0.0 que dice que no hay cola.
* El orquestador ahora mide la serie UNA vez (`_ledger_closures`, unico parseo del
  libro) y la pasa entera: `wr/aw/al/n` salen de ahi (Kelly) y
  `_ledger_pnl_series()` la da a VaR/ES/Sharpe. Dos parseos distintos del mismo libro
  serian dos fuentes de verdad para la misma muestra.

**Unidad y horizonte, declarados en cada nota** (sin esto dos calculos del mismo nombre
no son comparables): *fraccion de la cuenta por cierre, horizonte = 1 cierre, NO diario,
parametrico normal*. El motivo por el que no se uso `pnl_pct` (retorno sobre nocional) ni
el `ReturnCalculator` esta en el apartado 5 de abajo.

**Que NO hacen:** no aprueban, no recortan, no rechazan. `approved`, `reasons` y
`approved_size` son identicos con y sin serie (hay test que lo candado). Es estado medido,
no un freno.

### NO CONECTADOS, uno a uno

1. **`expectation/statistical_tests.py`** — NO TOCADO, encargo reservado para la fase de
   validacion (para no chocar). Se anota que hoy solo se importa desde
   `expectation/__init__.py` y nadie lo invoca.
2. **`monte_carlo/simulator.py`** — NO TOCADO, tambien reservado.
3. **`risk/stop_loss.py`** — **NO se conecta. Manda `roe_targets.build_roe_plan`.**
   Datos: `StopLoss` calcula el stop en % del precio de entrada y **no sabe nada de
   apalancamiento ni de liquidacion** (su `default_pct` es 0.02); en el ledger real de
   50x la liquidacion esta a **1.67%** del precio (`liquidation_price_distance=0.0167`)
   y el SL vivo esta en **0.5%** (`stop_loss_pct=0.005`). El stop por defecto de
   `StopLoss` (2%) caeria **mas alla de la liquidacion**, es decir una orden
   inalcanzable, y quien tendria que arreglarlo es exactamente el clamp medido de
   `max_sl_price_distance` que ya funciona. Conectarlo duplicaria la regla sin que la
   copia conozca la restriccion. La instancia `self.stop_loss` queda tal cual esta.
4. **`expectation/drawdown_analyzer.py`** — **NO se conecta. Manda
   `circuit_breaker.DailyGuard`.** Dos motivos medidos: (a) el guard YA esta cortando
   ahora mismo (24.52% > 20%, `risk_halt` en `runtime_stats.json`), y dos guardas con el
   mismo umbral no anaden seguridad, anaden dos formas de discrepar; (b) **no hay serie
   de equity que analizar**: `daily_pnl.json` guarda UN snapshot que se sobrescribe cada
   dia, y no existe ningun historial de equity en `runtime/state_*`. Lo unico que se
   podria construir es un drawdown de la *secuencia de cierres*, que es otra metrica con
   el MISMO NOMBRE y sin freno que gobernar. Si se quiere conectar, lo primero es decidir
   (dato) que serie diaria de equity se persiste; hasta entonces, documentado y sin tocar.
5. **`expectation/return_calculator.py`** — **NO se conecta: su unidad no sirve para
   estos datos.** `calculate_returns` hace `pnl_USD / entry_price`, que solo es un
   retorno si la cantidad es 1. En el ledger real: `0.054 / 1.499 = 3.61%` frente al
   **0.54%** real de esa operacion — un factor 6.67, que es justo la cantidad. Se
   decidio en su lugar la unidad explicita (fraccion de la cuenta por cierre) en vez de
   importar una conversion incorrecta. Si algun dia se arregla `calculate_returns` para
   dividir por el nocional (`entry_price * quantity`), ahi si tiene sentido que alimente
   a VaR y Sharpe.
6. **`risk/portfolio_risk.py`** — **NO se conecta: no hay matriz que calcular.**
   Necesita dos o mas series de retorno por estrategia; medido hoy: la hipotesis con mas
   datos tiene **6 cierres** (y las otras tres, 1 cada una), frente al piso de 20. Sin
   dos series que lleguen al piso no hay correlacion que estimar, y una matriz de 1x1 no
   es riesgo de cartera. Ademas hoy solo importa desde `risk/examples.py` (un ejemplo).
7. **`RiskManager.calculate_risk_metrics()` y `stress_test_strategy()`** (los metodos
   huerfanos por los que pasan VaR/ES) — **siguen huerfanos, a proposito.** Medido:
   `grep -rn "StrategyResult("` solo devuelve los dos `__str__` de `core/types.py` y
   `autonomous_research/interfaces.py`: **nadie construye un `StrategyResult` en todo el
   repo**, asi que conectarlos exigiria fabricar el objeto de entrada. VaR/ES se
   conectaron por la via que si tiene datos medidos: la serie de cierres del ledger.
8. **`data_processing/*` (4 ficheros, 1.167 lineas en la raiz del repo)** — **herramientas
   REALES sin usar; NO sobran, y NO se conectan aqui.** Contenido: `DataCleaner`
   (huecos/outliers), `Normalizer` (MinMax/Standard/Robust, scikit-learn), 
   `TimeSeriesResampler` (resample + retornos) y `StructuralBreakDetector` (ADF +
   roturas de regimen, statsmodels). Importan bien con las dependencias instaladas y son
   exactamente el tipo de pieza que necesita el pipeline de features que viene. Lo que
   falta no es codigo sino decision: **nadie los invoca** (unico "referencia" del repo: un
   comentario del docstring de `data_acquisition/data_sources/forex.py` linea 15 que dice
   *"`DataCleaner` ffill handles them`"*, que es **FALSO hoy** — no lo llama nadie, los
   huecos de fin de semana de forex no se rellenan con eso). Borrarlos perderia capacidad
   real; conectarlos hoy seria decidir a ciegas que serie limpia que. **Veredicto: se
   quedan, sin conectar; dos seguimientos** — (a) arreglar el comentario de forex o
   cablear el `ffill` de verdad (datos), (b) testearlos antes de que los use nadie
   (estan con 0 tests).
9. **`pca_analysis/*` (4 ficheros, 704 lineas + `__init__`)** — **TEST-ONLY pero NO es
   codigo muerto que sobra: se queda, sin conectar.** Tiene **21 tests**
   (`tests/test_pca_analysis.py`) que pasan y es la unica implementacion de PCA del repo
   (PCA por SVD en numpy, descomposicion de retornos, shrinkage de covarianza, factores
   de riesgo). Borrarlo se lleva por delante 21 tests y la capacidad. Por que no se
   conecta: exige una matriz de retornos multi-activo, y hoy cada run opera **un solo
   simbolo** con 9 cierres — alimentarlo seria darle una matriz de 1 fila. Alcanzables
   solo desde los tests y desde el listado `modules` de `quant_math/__main__.py`, sin
   ninguna ruta de produccion.
10. **`risk/position_sizing.py` / instancia `RiskManager.position_sizer`** — no estaba en
    la lista de doce pero consta en la tabla de arriba como "muerto AQUI": el MODULO ya
    esta vivo por otra ruta (`_apply_margin_cap` llama `sizing.PositionSizer.calculate`
    para el tope de riesgo por operacion). Lo que sobra es la instancia duplicada
    `self.position_sizer` dentro de `RiskManager`. No se toca: esta fuera del alcance de
    este encargo y borrarla no cambia ningun comportamiento.

### Los numeros: que se puede calcular HOY y que no

**Se puede (y ya esta):**

* Kelly: `kelly_status` con n=9 medido (estado `insuficiente`, como estaba).
* Estado de VaR/ES y Sharpe/Sortino en cada check, con la muestra y el piso a la vista.
* Con **9 cierres**: solo el ESTADO `insuficiente` + la nota. Ningun numero.
* El replay de arriba (VaR-95 5.55%, ES-95 6.75%, Sharpe -0.29/op), **para diagnostico,
  no para decidir**: son los numeros que justifican por que no se frena con ellos.

**No se puede (y se dice):**

* VaR/ES-95 y Sharpe/Sortino: hacen falta **20 cierres** (faltan 11).
* VaR/ES-99: hacen falta **100 cierres** (faltan 91).
* Cualquier medida **por hipotesis**: la mejor tiene 6 (faltan 14).
* Sharpe anualizado: no existe horizonte diario en la serie (es por cierre), asi que
  **nunca** se va a anualizar esta serie con 252.
* Drawdown analizado por `DrawdownAnalyzer`: no hay serie de equity persistida.
* Riesgo de cartera/correlaciones: no hay dos series.

### Como se prueba

`tests/test_var_sharpe_conectados.py`, 14 tests, todos offline:

* el ES en cero (bug) y la invarianza `ES >= VaR`;
* `sin_datos` / `datos_invalidos` / `insuficiente` / `ok_95` / `ok` con sus notas;
* delegacion real en `ValueAtRisk`, `ExpectedShortfall` y `SharpeMetrics`
  (los valores del registro se comparan contra el modulo);
* el candado: mismos `approved`/`approved_size`/`reasons` con y sin serie;
* cableado del orquestador (serie medida, deduplicada, ultima marca) y ruta completa
  orquestador -> RiskManager -> estado grabado en `risk_checks`.

**Siguiente paso cuando haya muestra** (no lo decide este modulo): con >= 20 cierres,
replay del VaR/ES sobre las entradas ya cerradas y decidir si alguno pasa a freno con
umbral medido; hasta entonces, ninguno de los dos estados tiene permiso para vetar.
