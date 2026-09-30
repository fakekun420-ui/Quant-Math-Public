# F3 · Ejecucion end-to-end y validacion fuera de muestra

**Fecha:** 2026-09-29 · **Departamento:** D2 (Kaenor · Quant Researcher) · **Modo:** medicion pura, cero cambios de codigo/config
**Alcance:** ejecucion real, OOS, SIS, coste de slippage. **WebUI fuera de alcance** (decision de Leonardo).

> Regla de esta fase: *prueba valida = comando ejecutado + salida pegada*. No vale «el fichero existe» ni «lo dice el README».
> Todo lo de abajo va marcado **[V]** verificado con ejecucion o **[I]** inferido. Donde no se, se dice.

---

## 0. Veredicto

**El sistema corre end-to-end y produce datos. Lo que no se sostiene es que sus senales tengan edge.**

Las cuatro preguntas del encargo, respondidas:

| # | Pregunta | Respuesta | Estado |
|---|---|---|---|
| A | iCorre de verdad? | **Si.** Delta medido: KB +6 filas, ledger paper +5, positions +5, ultima fila parseable, 84-lineas de traza con timestamps por etapa | **[V]** |
| B | iLas senales son ruido? | **`expectancy_test = -0,1914%` (n=814, winrate 39,68%).** La expectancy que el sistema produce es `expectancy_train = +0,4041%` (n=1630, wr 34,87%) | **[V]** |
| C | iEl SIS aprende? | **No se ha activado nunca.** 0 fit, 0 closures, 24 filas en `collecting` (MIN_ROWS=30). El orden temporal es correcto (sin look-ahead) y el KMeans no alimenta ninguna decision | **[V]** |
| D | iCoste del slippage? | **-0,05 pp por operacion**, independiente del winrate. Con el winrate de train (34,87%) el coste **vuelve negativo el signo**: bruta +0,0461% -> neta **-0,0039%** | **[V]** |

**Frase literal exigida: `expectancy_test <= 0`.** Ocurre, con muestra suficiente (n=814 > 30). **Hallazgo de riesgo maximo.**

### Hallazgos H1-H8 (todos con evidencia ejecutada)

| ID | Hallazgo | Evidencia | Gravedad |
|---|---|---|---|
| **H1** | La metrica `expectancy` del sistema esta **rota**: el backtester cierra posiciones al final sin devolver el margen, y luego divide ese margen perdido entre el numero de trades. Con 1 solo trade ganado da `ret_pct = -40,4840%` | `backtesting/backtester.py:817-819` + `:866-867` | **MAXIMA** |
| **H2** | `trades=0` **no es un fallo global**: el adapter emite `quantity: 1` y el backtester exige `capital >= qty*fill/leverage`. Afecta solo a activos con precio unitario > 10.000 USD (BTC si, ETH no) | `quant_math_adapter.py:629,632` + `backtester.py:753-755` + `aqde_runner.py:687` | ALTA |
| **H3** | **El gate de riesgo esta DESACTIVADO por la puerta real.** `decision_engine/main.py:42` pone el default en `0`; `quant_math_bg.py:119` hace `setdefault(..., "1")`. En el run real: **5 de 5 operaciones con expectancy negativa** | A/B medido: `LEARN_MODE=0` -> 0 senales; `=1` -> 1 senal, 1 ledger | **MAXIMA** |
| **H4** | `expectancy` de la familia sobrevive OOS solo en `mean_reversion`. `momentum`/`breakout` no | 13 estrategias, 70/30, ETH 1h Bybit | ALTA |
| **H5** | El slippage se come el edge: el winrate de equilibrio sube de **33,33%** (bruto) a **35,00%** (con costes) y el train real esta en **34,87%**, por debajo | `main.py:939` (entrada) + `:357` (salida); los 2 call sites **se cancelan**, coste efectivo 0,05 pp y no 0,10 | ALTA (medida, y **corrige la lectura de F1**) |
| **H6** | El SIS es **decorativo**: KMeans corre, pero su salida no llega a ninguna decision de entrada/salida | `orchestrator.py:341` -> `rank_families` solo lee `regime_table` | MEDIA |
| **H7** | Fuga de etiqueta **presente pero con influencia medida ~0**: `pnl_pct` es la columna 2 del vector; separacion de clusters 0,0560 con y sin ella, ARI -0,0008 | `feature_store.py:109-112` | BAJA (medida, no asumida) |
| **H8** | La puerta que documenta F1 (`PYTHONPATH=/tmp/qmp-libs`) **rompe el KMeans del SIS**: numpy 2.5.3 contra sklearn compilado contra numpy 1.x | `regime_learning.py:80-84` (except silencioso) | MEDIA (es una trampa de reproduccion) |

**Baseline de tests: 162 collected, `1 failed, 161 passed`.** Sin desvío respecto a la línea base. El unico fallo es `tests/test_scientific_features.py::test_spectral_cycle_detection` (`assert None is not None`) y **es preexistente**, no lo causo esta fase.

---

## 1. A - iCorre de verdad end-to-end? **Si.** [V]

### 1.1 BLOCKED-KEY (limite explicito, no simulado)

El encargo prohibe simular claves. Se comprobo antes de nada:

```
BYBIT_API_KEY len=0
BYBIT_API_SECRET len=0
```

**`BLOCKED-KEY`: sin claves de Bybit.** Consecuencia medida y no simulada: el sistema corre **en modo paper con datos publicos reales** (klines de Bybit, sin ordenes privadas). La garantia alcanzable es exactamente esa: *funciona en paper con datos publicos*. **No se puede afirmar nada sobre la colocacion de ordenes reales ni sobre fills reales** - ver §8.

### 1.2 Delta de lineas JSONL: antes y despues

```
--- counts_before ---
ANTES 0 .../e2e/kb.jsonl (no existe)
ANTES 0 .../e2e/state/paper_executions.jsonl (no existe)
ANTES 0 .../e2e/state/positions.json (no existe)
--- hora inicio: 02:46:09.156
--- ahora ---
kb.jsonl=6
state/paper_executions.jsonl=5
state/positions.jsonl=5
state/paper_trades.jsonl=5
```

| Artefacto | Antes | Despues | Delta |
|---|---|---|---|
| `hypotheses.jsonl` (KB) | 0 (no existia) | 6 | **+6** |
| `paper_executions.jsonl` (ledger) | 0 (no existia) | 5 | **+5** |
| `positions.jsonl` | 0 (no existia) | 5 | **+5** |
| `paper_trades.jsonl` | 0 (no existia) | 5 | **+5** |

**Criterio `delta >= 1`: cumplido en los cuatro artefactos.** Y no basta con que el proceso salga 0: la ultima fila del ledger **parsea y es coherente**:

```json
{"mode":"paper","key":"hyp_4b6838c7:ETH/USDT","symbol":"ETH/USDT","side":"sell",
 "quantity":0.0018781682938334193,"entry_price":2662.16825,"notional_usd":5.0,
 "take_profit_price":2608.924885,"hypothesis_id":"hyp_4b6838c7",
 "expectancy":-0.9509594294117638,"timestamp":1790650253.72,"cycle":5}
```

### 1.3 Traza por etapa (timestamps reales)

`runtime/f3/trace/trace.log` (84 lineas, `runtime/f3/f3_trace.py` envuelve `sys.stdout` con reloj de pared; el proyecto no se toco). Extracto del ciclo 1 completo y del arranque del 2:

```
   1.290s | [HypothesisKnowledgeBase] Initialized with storage path: .../runtime/f3/trace
   1.309s | [QuantMathAdapter] Initialized with bybit exchange
   1.319s | ORCHESTRATOR CYCLE 1 (modo=classic, datos=REALES/bybit)
   1.323s |   [ml-prior] modo=collecting registros=4 rate_global=0.1667 reordenado=False
   1.325s |   [sis] modo=collecting ops=0 (recolectando)
  19.664s |   [model-gen] +2 hipotesis cientificas para ETH/USDT
  19.664s |   Created hypothesis: hyp_d86d1d52 (MARIMA_MACD_8_21_ETHUSDT)
  38.866s |   Data fetched: 1080 candles
  38.866s |   [ResearchManager] Running backtest for hyp_d86d1d52
  38.895s |   [ResearchManager] Backtest complete: trades=34 wr=17.65% ret=-5.81% sharpe=0.55
  38.909s |   [ResearchManager] Backtest complete: trades=29 wr=20.69% ret=-4.85% sharpe=0.51
  38.909s |   [hyp] hyp_d86d1d52 MARIMA_MACD_8_21_ETHUSDT expectancy=-0.17074 score=0.11 status=failed
  38.921s |   [decision] ETH/USDT: NO_ENTRY (sin hipotesis de expectativa positiva disponible)
  38.921s | [cycle 1] generadas=2 senales=0 no_entry=1 skip_pos=0
  39.923s | ORCHESTRATOR CYCLE 2 (modo=classic, datos=REALES/bybit)
  41.284s |   [ResearchManager] Backtest complete: trades=37 wr=21.62% ret=-7.56% sharpe=0.59
  41.304s | [cycle 2] generadas=2 senales=0 no_entry=1 skip_pos=0
```

Cadena **AQDE -> Orchestrator -> DecisionEngine -> ledger -> SIS**, etapa por etapa, con reloj:

| Etapa | Fichero | Evidencia en traza | Tiempo |
|---|---|---|---|
| AQDE init | `quant_math_adapter.py:104` | `[QuantMathAdapter] Initialized with bybit exchange` | 1,31 s |
| KB init | `orchestrator.py:542+` | `[HypothesisKnowledgeBase] Initialized with storage path` | 1,29 s |
| SIS (prior) | `regime_learning.py:165+` | `[ml-prior] modo=collecting registros=4` / `[sis] modo=collecting ops=0` | 1,32 s |
| Generacion hipotesis | `orchestrator.py:927+` | `[model-gen] +2 hipotesis` + 7 `Created hypothesis` | 1,3 -> 19,7 s |
| Datos (AQDE) | `aqde_runner.py:125-157` | `Data fetched: 1080 candles` | 38,9 s |
| Backtest | `backtester.py:686-900` | `Backtest complete: trades=34 wr=17.65% ret=-5.81%` | 38,87 -> 38,90 s |
| KB record | `orchestrator.py:542-600` | `[hyp] ... expectancy=-0.17074 status=failed` | 38,91 s |
| DecisionEngine | `decision_engine/main.py:872-930` | `[decision] ETH/USDT: NO_ENTRY` | 38,92 s |
| Ledger | `orchestrator.py:689-780` | `paper_executions.jsonl` +5 filas | 38,9 s -> |
| SIS cierre | `orchestrator.py:995-999` | `[sis] modo=collecting` (nunca llega a `active`, ver §6) | fin de ciclo |

### 1.4 El run largo (5 ciclos, 6 en total)

`runtime/f3/e2e/qm.log`, 6 ciclos, ~5 min, 1 simbolo:

```
[cycle 1] generadas=1 senales=1 no_entry=1 skip_pos=0
[cycle 2] generadas=1 senales=1 no_entry=1 skip_pos=0
[cycle 3] generadas=1 senales=1 no_entry=1 skip_pos=0
[cycle 4] generadas=1 senales=1 no_entry=1 skip_pos=0
[cycle 5] generadas=1 senales=1 no_entry=1 skip_pos=0
[cycle 6] generadas=1 senales=0 no_entry=2 skip_pos=0
```

**5 entradas ejecitadas de verdad (paper) y 5 NO_ENTRY de BTC.** El ciclo 6 cierra: ya hay posicion ETH abierta, el motor pasa a `no_entry=2`.

### 1.5 Limpieza del estado de runtime

- Proceso parado al terminar: `ps -ef | grep -c '[q]uant_math_bg'` -> **0**. [V]
- Todo el scratch en `runtime/f3/`, y `runtime/` esta en `.gitignore:10` (`git check-ignore -v runtime/f3` -> `.gitignore:10:runtime/`). [V]
- `git status --short` **identico** al de entrada: los dos `M` (`quant_math_adapter.py`, `test_model_based_generator.py`) ya estaban **antes** de empezar; los `??` son `.hub/ .ponytail.md AGENTS.md ops/ tests/test_generator_contract.py`. **Cero cambios de codigo/config.** [V]

---

## 2. H2 - Por que `trades=0` (correccion a F1) [V]

F1 concluyo que «el backtester no produce senales, siempre `trades=0`». **Eso es cierto solo para BTC y falso como regla general.** La causa esta medida:

```
quant_math_adapter.py:629,632   ->  "quantity": 1.0   (el adapter SIEMPRE emite 1 unidad)
backtester.py:753-755           ->  exige  capital >= qty * fill / leverage
aqde_runner.py:687              ->  initial_capital: 10000.0
```

Es decir: el adapter pide **1 BTC**, que a 83.066 USD necesita 83.066 USD de margen y solo hay 10.000 -> **0 trades**. Se comprobaron las dos ramas con el mismo camino de codigo:

| Activo | Precio | Backtester con 10.000 USD | Backtester con 200.000 USD |
|---|---|---|---|
| BTC/USDT | 83.066 | **0 trades** | **8 trades** |
| ETH/USDT | 2.662 | 29-37 trades | 29-37 trades |

**Alcance real del bug: solo activos con precio unitario > 10.000 USD.** BTC cae; ETH no. En el log del run:

```
[ResearchManager] Backtest complete: trades=0 wr=0.00% ret=0.00% ...
[skip] hyp_c640170c sin resultado de backtest utilizable
[decision] BTC/USDT: NO_ENTRY (sin hipotesis de expectativa positiva disponible)
```

**Consecuencia medible: el sistema opera un solo simbolo de los dos que mira.** Es la mitad del «universo» del bot, no el todo.

---

## 3. H1 - La metrica `expectancy` del sistema esta rota (MAXIMA) [V]

Este es el hallazgo que **contamina toda metrica que el sistema emite**, y es la razon por la que el encargo pedia reportar dos expectancy.

`backtesting/backtester.py:817-819` cierra las posiciones que siguen abiertas al final del backtest en modo *record only*, **sin devolver el margen a `self.capital`**. Luego `:866-867` calcula:

```
ret_pct = 100*(final_capital - initial_capital)/initial_capital
```

Efecto: el margen de la ultima posicion abierta se cuenta como perdida, y ese descuadre se divide despues entre el numero de trades en `orchestrator.py:561` (`expectancy = total_return_pct / n_trades`). Salida real (`runtime/f3/f3_equity_bug.py`):

```
velas=478 capital=200000 comision=0.001

estrategia          n   suma_pnl_trades  capital_final    ret_pct  ret_pct_teorico   descuadre  winrate
----------------------------------------------------------------------------------------------
ema_crossover       8           2705.17      202705.17     1.3526         101.3526        0.00    25.00
ati_trend           1           1868.63      119032.06   -40.4840         100.9343   -82836.57   100.00
breakout            6           5096.29      205096.29     2.5481         102.5481        0.00    50.00
bb_reversion        5           1475.05      118638.48   -40.6808         100.7375   -82836.57    60.00
energy_burst       16           1325.14      201325.14     0.6626         100.6626       -0.00    37.50
```

**`ati_trend`: 1 trade, winrate 100,00%, PnL realizado +1.868,63 -> el sistema reporta `-40,4840%`.** Un backtest perfecto reportado como catastrophe. El descuadre es una constante ≈ **82.836,57** (el margen de 1 BTC a 83k con apalancamiento), no un error de calculo de PnL.

Prueba controlada — **la misma estrategia, la misma serie, solo recortada**, para descartar varianza de muestreo:

```
velas= 478  n= 8  suma_pnl=  2705.17  ret_pct=   1.3526%  dif=      0.00
velas= 300  n= 5  suma_pnl=  5097.82  ret_pct= -40.3567%  dif= -85811.30
velas= 250  n= 4  suma_pnl=  1642.47  ret_pct= -39.9520%  dif= -81546.37
velas= 200  n= 4  suma_pnl= -3287.05  ret_pct= -39.9520%  dif= -76616.86
velas= 150  n= 3  suma_pnl= -3458.40  ret_pct=  -1.7292%  dif=      0.00
```

`ema_crossover` pasa de **+1,3526%** a **-40,3567%** cambiando 178 velas. **No es sensibilidad a la muestra: es el mismo bug dependiendo de si el backtest termina con posicion abierta.** Cuando termina cerrado, el descuadre es 0 y el numero cuadra.

**Consecuencia para la auditoria:** toda metrica de «expectancy» que salga de la caja esta contaminada. Este informe reporta las dos cifras:
- `SISTEMA` = `total_return_pct / n_trades`, la que produce el codigo.
- `CORRECTA` = `PnL realizado / capital / n`, calculada aqui, sin tocar el proyecto.

---

## 4. H3 - El gate de riesgo esta DESACTIVADO (MAXIMA) [V]

`quant_math/decision_engine/main.py:41-42` define el default **apagado**; los dos launchers lo encienden:

```
quant_math/decision_engine/main.py:42  os.environ.get("QUANTMATH_LEARN_MODE", "0") == "1"   # default: APAGADO
quant_math_bg.py:119                   os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")   # launcher: ENCENDIDO
quant_math/cli/main.py:307             os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")   # launcher: ENCENDIDO
```

El gate esta en `decision_engine/main.py:884-886`. A/B medido con el camino de codigo real, misma serie, misma estrategia:

| `QUANTMATH_LEARN_MODE` | senales emitidas | filas en ledger |
|---|---|---|
| `0` (gate activo) | **0** | **0** |
| `1` (por la puerta real) | **1** | **1** (`hyp_83f05f4a:ETH/USDT sell exp=-0.17113`) |

### 4.1 Alcance: 5 de 5 operaciones con expectancy negativa

Del run real de 6 ciclos (§1.4), las 5 operaciones ejecutadas:

| Ciclo | Hipotesis | expectancy | wr | ret del backtest |
|---|---|---|---|---|
| 1 | `hyp_d39c0fed` MLowVol_RSI | **-0,16431** | 20,69% | -4,76% |
| 2 | `hyp_84346fac` MARIMA_MACD_8_21 | **-0,95096** | 17,65% | -32,33% |
| 3 | `hyp_3cc9d819` MLowVol_RSI_RSI12 | **-0,16439** | 20,69% | -4,77% |
| 4 | `hyp_54eb7229` MLowVol_RSI | **-0,16443** | 20,69% | -4,77% |
| 5 | `hyp_4b6838c7` MARIMA_MACD_8_21 | **-0,95096** | 17,65% | -32,33% |

**5/5 (100%) con expectancy negativa. 0/5 positivas.** El sistema abrio operaciones que su propio diseno dice que no debe abrir, y lo hizo las 5 veces que pudo.

**Matiz honesto (I → medido):** el ledger real son 0,005 USD por operacion (notional 5 USD, §7.3), o sea que el dano financiero de este handicap concreto es ~0,025 USD. **El hallazgo no es el perdida: es que el unico control de riesgo del sistema esta desactivado en produccion.** Si alguien sube el notional, el gate no esta ahi para frenarlo. Tamano de muestra: n=5, insuficiente para afirmar «el 100% de las operaciones es malo» como estadistica; **suficiente para afirmar que el gate no frena nada**, que es lo que se midio.

---

## 5. B - Validacion fuera de muestra: **las senales no sobreviven** [V]

### 5.1 Protocolo

Corte temporal puro, **sin solape**, paginando el exchange a mano porque el adapter solo saca 477 velas (`quant_math_adapter.py:152-153`):

```
### ETH/USDT  1h  540d  velas=12960  train=[0:9072]  test=[9072:12960]  solape=0
### train 2025-04-07 04:00 -> 2026-04-20 03:00   test 2026-04-20 04:00 -> 2026-09-29 03:00
### precio train 1632.61->2284.32  test 2272.80->2660.90  capital=10000
```

Las 13 estrategias de `IMPLEMENTED_STRATEGIES` (`quant_math_adapter.py:53-67`), cada una por separado, y agregado. `runtime/f3/f3_oos_final.py`, salida cruda `runtime/f3/oos_cap10k.txt`.

### 5.2 RESULTADO PRINCIPAL (capital 10.000 = el que usa el sistema, `aqde_runner.py:687`)

```
=== AGREGADO, 13 estrategias implementadas ===
  train  ops=1630 estrategias_con_senal=13  winrate_medio= 34.87%  expectancy_SISTEMA=  +0.3526%  expectancy_CORRECTA=  +0.4041%  %positivas=46.2%
         suff para inferencia (n>=30 por conjunto): SI
  test   ops=814  estrategias_con_senal=13  winrate_medio= 39.68%  expectancy_SISTEMA=  -0.4896%  expectancy_CORRECTA=  -0.1914%  %positivas=30.8%
         suff para inferencia (n>=30 por conjunto): SI
```

| Conjunto | n ops | wr | `expectancy_SISTEMA` | `expectancy_CORRECTA` | % estrategias + | n suficiente? |
|---|---|---|---|---|---|---|
| **train** [0:9072] | **1630** | 34,87% | **+0,3526%** | **+0,4041%** | 46,2% | si |
| **test** [9072:12960] | **814** | 39,68% | **-0,4896%** | **-0,1914%** | 30,8% | **si** |

> ### **`expectancy_test <= 0`.**
>
> **-0,1914% por operacion en 814 operaciones fuera de muestra. `n=814 >> 30`: la muestra es suficiente.** No es ruido de muestra pequena. El train es positivo y el test es negativo: es exactamente el patron de un **edge que se agota o no existe**, y el winrate *sube* (34,87% -> 39,68%) mientras la expectativa *baja*, o sea que las perdidas: cuando gana son mas grandes que cuando pierde.
>
> La metrica que emite el sistema (`SISTEMA`, -0,4896%) **amplifica el problema ~2,6x**. Con H1 corregido, la magnitud real sigue siendo negativa.

### 5.3 Detalle por estrategia (expectancy correcta por trade, %)

| Estrategia | Familia | train n | train exp | **test n** | **test exp** | Sobrevive OOS? |
|---|---|---|---|---|---|---|
| `vwap_reversion` | mean_rev | 253 | +2,8408% | 47 | **+1,0106%** | **SI** |
| `rsi_reversion` | mean_rev | 164 | +1,6068% | 63 | **+0,0891%** | SI (margen) |
| `stochastic_reversion` | mean_rev | 95 | +2,1585% | 43 | **+0,3436%** | **SI** |
| `bb_reversion` | mean_rev | 114 | +2,7711% | 42 | **+0,3373%** | **SI** |
| `ema_crossover` | momentum | 81 | -0,9817% | 81 | -0,3813% | no |
| `range_pressure` | breakout | 275 | +4,8547% | 101 | -0,4236% | no |
| `scalp_burst` | momentum | 80 | -0,9956% | 86 | -0,3953% | no |
| `breakout` | breakout | 47 | -1,6892% | 65 | -0,4195% | no |
| `energy_burst` | breakout | 365 | +3,3846% | 121 | -0,4170% | no |
| `ati_trend` | momentum | 29 | -2,8012% | 23 | -0,6350% | no |
| `macd` | momentum | 50 | -1,5875% | 55 | -0,4915% | no |
| `donchian_breakout` | breakout | 30 | -2,6209% | 44 | -0,4993% | no |
| `dual_ema` | momentum | 47 | -1,6889% | 43 | -0,6057% | no |

**H4: la unica familia que sobrevive OOS es `mean_reversion`, y de forma consistente (4/4).** `momentum` y `breakout` no sobreviven ninguna (0/9), y tres de ellas (`range_pressure`, `energy_burst`, `bb_reversion` train) son las de mejor resultado en train — **el ranking en train es anti-informativo**: las que mejor se ven entrenando son justo las que peor se comportan fuera.

Es el dato accionable de esta fase: **4 de 13 estrategias tienen edge OOS medido; las otras 9 se pueden eliminar hoy sin perder nada.** Y el sistema actual **no distingue entre unas y otras** — su gate (§4) no filtra por este criterio.

### 5.4 Sensibilidad al capital: el train ni siquiera es estable [V]

Mismo protocolo, mismo instante, **solo cambia `initial_capital`**:

| Capital | train n | train wr | **train exp CORRECTA** | test n | **test exp CORRECTA** |
|---|---|---|---|---|---|
| **10.000** (el del sistema) | 1630 | 34,87% | **+0,4041%** | 814 | **-0,1914%** |
| **100.000** | 2280 | 34,49% | **-0,0261%** | 814 | **-0,0191%** |

**El train pasa de +0,4041% a -0,0261% multiplicando el capital por 10.** Un edge real no cambia de signo con el dimensionamiento. Lo que se observa es el perfil de comision/slippage sobre un notional distinto, no alfa. **Esto degrada la lectura de §5.2: el +0,40% de train no es un edge, es un artefacto de capital.** La conclusion de §5.2 se mantiene y se **refuerza**: en ninguna capitalizacion el test es positivo.

### 5.5 Límite de exchange medido (por que el OOS principal es Bybit) [V]

Mismo script, exchange por defecto del adapter (Binance, `quant_math_adapter.py:104`):

```
### train 2026-09-09 06:00 -> 2026-09-23 03:00   test 2026-09-23 04:00 -> 2026-09-29 03:00
  train  ops=45   wr= 69.02%  expectancy_SISTEMA=  -8.1621%  expectancy_CORRECTA=  +0.5423%
  test   ops=25   wr= 17.95%  expectancy_SISTEMA=  -7.6597%  expectancy_CORRECTA=  -0.1932%
         suff para inferencia (n>=30 por conjunto): NO  <-- n insuficiente
```

**Solo 477 velas / 20 dias**, frente a 12.960 de Bybit. Binance **ignora `since` y `limit`** en esta ruta: el paginado no avanza. Consecuencias medidas:

| | Binance (default) | Bybit (inyectado) |
|---|---|---|
| Velas en 540 dias | **477** (20 dias) | **12.960** (540 dias) |
| `since` respetado | **no** | si |
| `limit` respetado | **no** | si |
| n test | 25 -> **insuficiente** | 814 -> suficiente |

**El OOS sobre Binance NO es valido: n_test=25 < 30.** Por eso el resultado que manda es el de Bybit. Corolario operativo: **el backtester y el motor de decision estan viendo historiales distintos** (el backtester pagina bien, el motor de decision se queda con las 100-1000 velas del exchange), asi que la hipotesis que evalua y la que ejecuta no son la misma.

### 5.6 Variante «fiel al runtime»

El runtime real solo trae 1.000 velas 1h por ciclo. Con 20 dias (`Binance`, §5.5) sale **n_test=25: insuficiente**, y por tanto **no se puede concluir nada con la fiel reproduccion del runtime**. Se reporta el numero por completitud, no como evidencia: train +0,5423% (n=45) / test -0,1932% (n=25).

---

## 6. C - El SIS (aprendizaje): **nunca se ha activado, y no alimenta ninguna decision** [V]

### 6.1 Estado real: `collecting` permanente

`regime_learning.py:66-70` — el umbral de activacion:

```python
def _fit(self, kb_records, ledger_path, state_dir):
    self.rows = fs.build_trade_dataset(kb_records, ledger_path, state_dir)
    if len(self.rows) < MIN_ROWS:
        self.mode = "collecting"
        ...
        return
```

`MIN_ROWS = 30` (`regime_learning.py:29`). Estado tras el run real y tras toda la instrumentacion de esta fase:

| Medida | Valor |
|---|---|
| Registros en KB tras 6 ciclos | 6 |
| Filas del dataset de trades | **24** |
| `MIN_ROWS` | 30 |
| Veces que se ejecuto `_fit` con datos suficientes | **0** |
| Veces que se alcanzo `mode == "active"` | **0** |
| Cierres de posicion registrados | **0** |
| Lineas con `mode=active` en cualquier log | **0** |

En todas las trazas de esta auditoria, sin excepcion:

```
[sis] modo=collecting ops=0 (recolectando)
[ml-prior] modo=collecting registros=4 rate_global=0.1667 reordenado=False
```

**Respuesta directa: el SIS no aprende, porque nunca ha-ddquirido los 30 datos que necesita.** Y el dataset no crece con el paso del tiempo del jeito que haria falta: `build_trade_dataset` (`feature_store.py:64-94`) necesita **cierres** (trade cerrado con `pnl`), no entradas. Como §4.1 muestra, el sistema abre posiciones y **ninguna se cierra**: `exits=0` en los 6 ciclos.

### 6.2 Orden de llamadas: **correcto, sin look-ahead** [V]

Esta era la pregunta: un `fit` sobre todo el dataset y luego `predict` sobre el pasado seria data leakage y haria el backtest una ficcion. **Codigo real, no inferido:**

```
orchestrator.py:340   from quant_math.ml.regime_learning import load_loop
orchestrator.py:341   loop = load_loop(self.config.kb_path, self.config.state_dir)
orchestrator.py:349   fams = loop.rank_families(symbol, regime)
                       ^^^ dentro de la GENERACION de hipotesis del ciclo

orchestrator.py:993   exit_future = pool.submit(self.engine.check_exits_all)
                       ^^^ DESPUES de publicar en KB y antes de decide()
```

Es decir: el SIS se carga y se consulta **al principio del ciclo** para ordenar familias, y los cierres se incorporating **al final del mismo ciclo**. Un ciclo solo puede usar cierres de ciclos anteriores.

**Veredicto: NO hay look-ahead temporal en el SIS. El orden es correcto.** Esto es un punto a favor del diseno, y conviene decirlo porque era la hipotesis mas grave y queda descartada.

### 6.3 Fuga de etiqueta: presente en el codigo, influencia medida ~0 [V]

La etiqueta **esta dentro del vector de features**. `feature_store.py:109-112`:

```
Columnas de encode_row (feature_store.py:109-112):
   [0]family [1]motivo [2]pnl_pct <-- ETIQUETA [3]p_window [4]vol_pct
   [5]forecast_up [6]cycle_len [7]k_slope [8]k_noise
```

Se midio si eso **realmente** separa los clusters, entrenando con y sin la columna (`runtime/f3/f3_leak.py`, salida `leak_run.txt`):

```
Dataset experimento: n=60  X(60, 9)

  CON pnl_pct en features (lo que hace el sistema) separacion_winrate_entre_clusters=0.0560  ARI(pnl>0, cluster)=-0.0008
  SIN la columna pnl_pct                           separacion_winrate_entre_clusters=0.0560  ARI(pnl>0, cluster)=-0.0008
```

**Idéntico byte a byte con y sin la etiqueta.** La fuga **existe en el diseño** (`pnl_pct` alimenta su propio clustering) pero **su influencia medida es cero** en este experimento. ARI -0,0008: el cluster no tiene mas informacion sobre el resultado que el azar.

> **Correccion a F1:** los clusters con `win_rate` 0.0 / 1.0 que reporto F1 **no son data leakage**. Son un artefacto de muestra: con 40 filas y 2-4 clusters, KMeans parte los datos casi siempre en dos grupos y las|winrate de cada grupo sale 0 o 1 por construccion. Aqui, con n=60 y 20 semillas, el ARI medido es ~0.

> **Lo que si es cierto:** si en el futuro el dataset creciera y la separacion fuera real, tener la etiqueta dentro del vector haria que el cluster fuera trivialmente separable y el `regime_table` worthless. **Es una bomba de relojeria, no un fallo activo hoy.** La correction es trivial (sacar la columna antes de `fit`), pero **esta fase no arregla nada**.

### 6.4 El KMeans no alimenta ninguna decision (H6) [V]

Comprobado leyendo el codigo, no inferido. Salida de `f3_leak.py`:

```
¿rank_families/should_explore leen self.labels (los clusters)? NO -> el KMeans no alimenta NINGUNA decision
   rank_families/should_explore usan: ['regime_table']
```

| Consumidor | Que lee | Usa `self.labels`? |
|---|---|---|
| `rank_families` (`regime_learning.py:123-146`) | solo `self.regime_table` (agregados por familia/regimen) | **NO** |
| `should_explore` (`:158-162`) | solo `self.rows` via `_consecutive_losses` (`:148-156`) | **NO** |
| `summary()` (`:117-122`) | `cluster_stats` | si, pero **solo para imprimir/loguear** |
| `_fit` (`:87-107`) | escribe `cluster_stats` y `regime_table` | — |

Es decir: **`regime_table` se construye con agregados simples de winrate/mean_pnl (`pnl_pct` sobre las filas), no con los clusters.** El KMeans produce `labels` y `cluster_stats`, y `cluster_stats` solo se consume en `summary()`, que solo imprime. **El modelo no entrenado es el que se usa; el entrenado se guarda y se enseña.**

Comentario del propio codigo, que lo dice en `orchestrator.py:337-338`:

```python
# SIS no supervisado: refuerza familias con exito historico en el
# regimen actual; nunca altera el gate.
```

**Eso es exacto y es el problema:** el SIS, aun funcionando, no puede abrir ni cerrar nada. Un componente que por construccion no puede cambiar una decision no puede «aprender» en el sentido que el proyecto necesita.

### 6.5 Trampa de reproduccion: `PYTHONPATH=/tmp/qmp-libs` ROMPE el KMeans [V]

**F1 recomienda en su §6 usar `PYTHONPATH=/tmp/qmp-libs`. Hacerlo desactiva el KMeans en silencio.**

`/tmp/qmp-libs` trae **numpy 2.5.3**; el sklearn del sistema esta compilado contra numpy 1.x. Al entrar, `_fit` revienta y la excepcion se traga:

```
regime_learning.py:79   try:
regime_learning.py:80       from sklearn.cluster import KMeans
regime_learning.py:83   except Exception as exc:
regime_learning.py:84       logger.warning("[SIS] clustering no disponible (%s); solo tablas agregadas", exc)
regime_learning.py:85       self.labels = None
```

`ValueError: numpy.dtype size changed` -> `logger.warning` -> `self.labels = None` -> el sistema sigue funcionando **sin clusters, sin error visible, sin exit != 0**. Quien reproduzca el entorno de F1 medirá un SIS que «no hace clustering» y atribuirá el motivo al diseno.

**Entorno real del sistema (el que hay que usar para medir):** `numpy 1.26.4`, `pandas 2.1.4`, `scikit-learn 1.4.1`, `/usr/bin/python3` (3.12.3). `.venv/` del proyecto esta **vacio**. Instalaciones extra: `pip3 install --target=/tmp/qmp-libs <pkg>` **solo para `arch`/`psycopg2`**, nunca para numpy/scikit.

### 6.6 Limite de graphify (metodo)

`graphify path "AQDERunner" "DecisionEngine"` -> `No directed path found` (el grafo AST no ve flujo de datos). `graphify query` en espanol tecnico no devuelve los nodos de sizing. **Para esta fase `grep` y `sed` sobre el codigo real fueron la herramienta principal y la que si resolvio** (orden de llamadas, gate, slippage, umbral SIS). Queda registrado como limite del indice, no del metodo.

---

## 7. D - Coste del slippage: **corrijo la premisa del encargo** [V]

El encargo (y el informe de F1) afirma que *«el slippage se come el edge: 0,05% por lado aplicado DOS veces, F1 midio +1,949% en vez de +2% y -1,0495% en vez de -1%»*. **Los numeros de F1 son correctos; la interpretacion no.** Hay dos call sites, pero **se cancelan entre si**.

### 7.1 Los dos call sites, leidos del codigo

```
main.py:939   fill_price = self._slip(float(candles[-1]["close"]), side, True)    # ENTRADA
main.py:955   signal = { ... "price": fill_price }
orchestrator.py:756  price = float(signal["price"])
orchestrator.py:756  quantity = notional / price
orchestrator.py:757  tp_price = price * (1 + take_profit_pct)     # <-- sobre el precio YA slidado
main.py:357    exit_px = self._slip(exit_px, side, entering=False)               # SALIDA
```

El TP/SL se define **sobre el precio de entrada despues del slippage**, y la cantidad se normaliza por ese mismo precio. Efecto: el `_slip` de entrada **entra y sale multiplicando y se anula**. El modelo cerrado es:

```
pnl_pct = (1 + retorno_bruto) * (1 - S) - 1        # S = 0,05%
```

Ejecutado (`runtime/f3/f3_slip3.py`), con los precios reales de la ruta:

```
== RUTA REAL DEL CODIGO (2 call sites de _slip) ==
  LONG Take-Profit +2%   P=100.00 ent=100.05000 qty=0.999500 objetivo=102.05100 fill_salida=101.99997  PnL%=+1.949000%
  LONG Stop-Loss  -1%   P=100.00 ent=100.05000 qty=0.999500 objetivo= 99.04950 fill_salida= 98.99998  PnL%=-1.049500%

   TP  (1+0,02)*(1-0,0005) - 1 = +1.949000%
   SL  (1-0,01)*(1-0,0005) - 1 = -1.049500%
```

**Coincide exactamente con lo que midio F1 (+1,9490% / -1,0495%).** La conclusion correcta es: **el coste efectivo es de 0,05 pp por round-trip, no 0,10 pp.** El «doblar» no ocurre porque la entrada es una renormalizacion, no un coste adicional. Esto **reduce** la gravedad del hallazgo respecto a lo que se suponia — y es exactamente el tipo de cosa que hace falta medir en vez de dar por buena una lectura.

### 7.2 Impacto acumulado con los winrates reales del OOS

```
conjunto        wr      bruta   con coste  delta pp   %ventaja  equilibrio
--------------------------------------------------------------------------
train       34.87%   +0.0461%    -0.0039%  -0.0500    -108.5%      35.00%
test        39.68%   +0.1904%    +0.1403%  -0.0501     -26.3%      35.00%
```

| Conjunto | wr | expectancy bruta | con coste | delta | ventaja consumida |
|---|---|---|---|---|---|
| train (n=1630) | 34,87% | +0,0461% | **-0,0039%** | -0,0500 pp | **-108,5%** |
| test (n=814) | 39,68% | +0,1904% | +0,1403% | -0,0501 pp | -26,3% |

**El coste es de -0,05 pp por operacion, independiente del winrate.** Y con el train medido **el slippage es suficiente para invertir el signo**: la ventaja bruta de +0,0461% pasa a **-0,0039%**. Se consume el 108,5% de la ventaja. Esto no es un detalle fino: **significa que en train no hay edge ni con costes.**

### 7.3 El winrate de equilibrio con costes es 35,00%

```
winrate de EQUILIBRIO: bruto 33.33%  ->  con coste 35.00%  (+1.67 pp)
  train 34.87% < 35.00% -> el train YA esta por debajo del equilibrio de costes
```

Con TP/SL 2:1 el equilibrio bruto es 33,33%. Al pagar el slippage sube a **35,00%**. **El winrate real de train es 34,87%: 0,13 pp por debajo de donde el sistema tiene que estar para no perder dinero.** Por eso §5.2 da negativo.

### 7.4 Coste absoluto en el ledger paper

Notional real de las ejecuciones medidas: **5,0 USD** (capital x `entry_pct` 0,05, sin apalancamiento). El ledger del run contiene `notional_usd: 5.0`.

| Operaciones | Slippage arrastrado en el round-trip |
|---|---|
| 5 (el run real completo) | **0,025 USD** |
| 100 | 0,500 USD |
| 1.000 | 5,000 USD |

**El dano en euros del slippage con el dimensionamiento actual es irrelevante (2,5 centavos en 5 operaciones).** El problema no es el coste: es que el dimensionamiento es tan pequeno que **ningun resultado de este bot es medible en euros**, ni a favor ni en contra. Quien lea «el slippage se come el edge» debe entenderse como: se come el edge *porcentual*, y el porcentaje es justo lo que se usa para decidir (gate, ranking, SIS).

---

## 8. NO VERIFICADO (lo que esta fase no puede afirmar)

Lo que **no** se comprobó, sin adornos. Cada punto con el motivo:

| # | No verificado | Por que |
|---|---|---|
| 1 | **Colocacion de ordenes reales y fills reales** | `BLOCKED-KEY`: `BYBIT_API_KEY len=0`, `BYBIT_API_SECRET len=0`. Todo lo medido es **paper**. Un fill real tiene latencia, rellenos parciales y commission de taker distinta: el ledger `notional_usd: 5.0` **no es un fill**, es una formule. |
| 2 | **PnL realizado en euros** | Ninguna posicion se cerro en 6 ciclos (`exits=0`). No hay ni un solo cierre real medido. Todo el PnL es de backtest. |
| 3 | **Comportamiento en otros pares** | Solo ETH (y BTC marginalmente). La Conclusion OOS es **de ETH 1h**; no se ha medido si se sostiene en BTC, ni en 15m/4h, ni enotros pares. |
| 4 | **Si el OOS se sostiene mas alla de test** | Un unico corte 70/30 sobre 18 meses. **No es un walk-forward de varios pliegues.** Con 13 estrategias y 3 periodos habria que corregir por multiplicidad: los +0,0891% de `rsi_reversion` en test probablemente no sobreviven a la penalizacion. **No se ha medido.** |
| 5 | **La expectativa de §5.2 en 100.000 USD contradice la de 10.000** | El train cambia de signo al cambiar el capital (§5.4). **No se ha investigado por que**, y por eso la magnitud +0,4041% **no se debe tomar como estimacion de edge**. Solo el signo negativo del test es robusto. |
| 6 | **Que hace el sistema en periodos largos** | 6 ciclos = ~5 minutos de reloj. Nada mas. No hay medida de degradacion, deriva ni memoria. |
| 7 | **El WebUI** | Fuera de alcance por decision de Leonardo. No mirado. |
| 8 | **Si el train del OOS es representativo** | El train cubre 2025-04 -> 2026-04 con ETH de 1.632 a 2.284. **Es un tramo de mercado, no un regimen.** El test (2.272->2.660) es un tramo distinto con tendencia. Un solo par y un solo regime no permite afirmar generalidad. |
| 9 | **Causa raiz del `Trades: 0` en BTC** | Se midio **el mecanismo** (margen insuficiente, `backtester.py:753-755` con `quantity:1`). **No se midio si el exchange es la unica fuente** del historial, ni si hay mas activos afectados aparte de BTC. |
| 10 | **El impacto de la fuga de etiqueta a escala** | Medido ~0 con n=60 sinteticos. Con el dataset real (24 filas) **no se ha medido**, porque el SIS nunca llega a `fit`. Es una bomba de relojeria (§6.3), no un fallo probado. |

**La limitacion que mas pesa:** el encargo pedia «iesto funciona?». **Si**: funciona, end-to-end, con datos reales, y produce un ledger coherente. **Lo que no se sostiene es que sirva para algo**: el unico criterio que el sistema usa para decidir (expectancy) esta roto (§3), y cuando se arregla, da negativo fuera de muestra (§5). |

---

## 9. Reversibilidad y estado final

Esta fase **no cambio ni una linea de codigo ni de configuracion**. Es reversible por construccion: no hay nada que revertir.

| Comprobacion | Resultado |
|---|---|
| `git status --short` al entrar | `M quant_math/autonomous_research/adapters/quant_math_adapter.py`, `M tests/test_model_based_generator.py`, `?? .hub/ ?? .ponytail.md ?? AGENTS.md ?? ops/ ?? tests/test_generator_contract.py` |
| `git status --short` al salir | **identico** (los 2 `M` ya estaban antes de empezar) |
| Baseline de tests | 162 collected -> **`1 failed, 161 passed`**. El fallo es `tests/test_scientific_features.py::test_spectral_cycle_detection`, **preexistente** |
| Procesos lanzados por esta fase | todos parados: `ps -ef \| grep -c '[q]uant_math_bg'` -> **0** |
| Estado de runtime creado | solo en `runtime/f3/`, y `runtime/` esta en `.gitignore:10` (verificado con `git check-ignore -v`) |
| Ficheros de esta fase | scripts y salidas en `runtime/f3/`; este informe en `ops/AUDITORIA-CONTEXTO/03-ejecucion-oos.md` |

### Lo que queda por decidir (no es mio: es del D2 Lead / de Leonardo)

1. **H1 antes que nada.** Con `expectancy` rota, cualquier decision que el sistema tome hoy se apoya en una cifra que puede ser `+1,35%` o `-40%` para la misma estrategia. Mientras eso siga, las otras correcciones son premature.
2. **¿4 de 13 estrategias, o ninguno?** §5.3 muestra que `mean_reversion` (4/4) sobrevive OOS y `momentum`/`breakout` no (0/9). Se puede acelerar mucho desactivando 9 estrategias. **No lo he hecho: es medicion pura, y apagar estrategias es una decision de producto.**
3. **Encender el gate.** §4: con `LEARN_MODE=0` el sistema no abre nada con expectancy negativa. Es un interruptor ya existente. Con lo medido aqui, activarlo parece la decision de menor riesgo y mayor impacto. **Tambien es una decision, no una medicion: no lo he tocado.**
4. **Lo unico inequivoco: hoy no hay edge.** `expectancy_test = -0,1914%` con n=814. No es un problema de afinacion del motor: es que la señal no vale. O se reconstruye la hipotesis de alpha sobre `mean_reversion`, o el proyecto se para.
