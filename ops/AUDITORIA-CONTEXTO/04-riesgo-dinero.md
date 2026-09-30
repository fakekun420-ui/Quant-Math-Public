# F4 — Cuánto puede perder Leonardo, con números

**Fecha:** 2026-09-29 · **Cargo:** `kaenor-risk-analyst` (D2) · **Fase:** F4 (riesgo de dinero)
**Método:** todo **VERIFICADO** lleva comando ejecutado + salida. **INFERIDO** = deducido de código leído.
Reproducir: `cd /sdcard/projects/Quant-Math-Public`. Python `/usr/bin/python3`.
Scratch y scripts: `Kaenor/ops/scratch-f4/`. **Cero cambios en el repo.**

---

## TL;DR — los 6 números

| # | Número | Dónde |
|---|--------|-------|
| 1 | **R:R = 0,50** (SL/TP), fijo para cualquier TP | `decision_engine/main.py:333` |
| 2 | **WR* = 33,33%** sin coste · **36,67%** con el coste medido | este informe A2/A3 |
| 3 | WR medido por F3 = **34,87%** → **1,80 pp por debajo** del WR* | A3 |
| 4 | **n real de operaciones cerradas = 0.** No hay drawdown ni racha que medir | A4 |
| 5 | Burst real: SL a **−2,00 USD = −200% del margen**, liquidado antes a **−4,5%** | B2/B3 |
| 6 | **No existe ninguna orden de cierre al exchange.** 1 solo `create_order`, de apertura | B1 |

---

## A. La matemática del riesgo, calculada

### A1. R:R que sale del código — VERIFICADO

```sh
$ /usr/bin/python3 Kaenor/ops/scratch-f4/f4_math.py    # sección A1
=== A1. R:R que sale del CODIGO (decision_engine/main.py:330-335) ===
  take_profit_pct=0.02   -> stop_loss_pct=0.01     -> R:R(SL/TP)=0.5000
  take_profit_pct=0.004  -> stop_loss_pct=0.002    -> R:R(SL/TP)=0.5000
  take_profit_pct=0.008  -> stop_loss_pct=0.004    -> R:R(SL/TP)=0.5000
  take_profit_pct=0.05   -> stop_loss_pct=0.025    -> R:R(SL/TP)=0.5000
  take_profit_pct=0.5    -> stop_loss_pct=0.25     -> R:R(SL/TP)=0.5000
```

**R:R = 0,5000 exacto** en los cinco TP. Es una propiedad, no un parámetro:
`decision_engine/main.py:331-335` — *"SL obligatorio 2:1 — siempre `take_profit_pct / 2.0`, **sin excepcion**"*.
El sistema **arriesga la mitad de lo que gana**. Es un R:R favorable.

### A2. El winrate de break-even NO es 66,7% — corrige el encargo

El encargo fijaba 66,7%. **Ese número corresponde a R:R = 2 (perder el doble de lo que se
gana), que es lo contrario de lo que hace el código.** Con el R:R medido en A1:

```sh
  === A2. Winrate de BREAK-EVEN que exige ese R:R ===
  formula: WR* = SL/(TP+SL) = R:R/(1+R:R)
  TP=0.02   SL=0.01   R:R=0.50 -> WR* = 33.33%
  TP=0.004  SL=0.002  R:R=0.50 -> WR* = 33.33%
  TP=0.008  SL=0.004  R:R=0.50 -> WR* = 33.33%
  TP=0.05   SL=0.025  R:R=0.50 -> WR* = 33.33%
```

**WR* = 33,33%.** El 66,7% habría sido el umbral de un sistema que arriesga 2× lo que gana.
Consecuencia práctica: la exigencia es **más fácil** de lo que parecía, y aun así el sistema
no la cumple con costes (A3).

### A3. Con el coste medido, el WR* sube y el WR medido queda por debajo

Coste verificado en el código, no citado: `decision_engine/main.py:104-118` fija
`slippage_pct = 0.0005` (classic, 0,05%) y `burst_slippage_pct = 0.0003` (burst, 0,03%),
**por lado**, y `_slip` (:585-592) lo aplica **en contra** en los dos extremos: entrada
`entering=True` (:939) y salida `entering=False` (:357). **Ida y vuelta = 2 lados.**

```sh
  === A3. Coste (F3: 0.05 pp por lado) -> WR* efectivo ===
  TP=0.02   WR* sin coste= 33.33%   WR* con coste= 36.67%   delta=+3.33 pp
  TP=0.004  WR* sin coste= 33.33%   WR* con coste= 50.00%   delta=+16.67 pp
  TP=0.008  WR* sin coste= 33.33%   WR* con coste= 41.67%   delta=+8.33 pp
```

| | WR* | WR medido (F3, n=1630) | Veredicto |
|---|---|---|---|
| classic (TP 2%, coste 0,10%) | **36,67%** | **34,87%** | **1,80 pp por debajo** |
| burst TP 0,4% (coste 0,06%) | **50,00%** | **34,87%** | **15,13 pp por debajo** |

**Dato honesto:** con n=1630, 1,80 pp de diferencia **no es concluyente por sí solo**
(la diferencia no está lejos del ruido de muestreo). Lo que sí apunta al mismo lado, y es
independiente, es el signo OOS que midió F3 (**−0,1914%**). **Mi conclusión: el sistema no
tiene edge demostrado, y su exigencia real de acierto es del 36,67%, no del 33,33%.**

> Corrección al encargo: F3 Mimi/consigna decía «0,05 pp por trade». Lo verificado es
> **0,05 pp por lado → 0,10 pp por operación completa** (y 0,06 en burst). El coste se duplica.

### A4. Curva de equity, drawdown, n de operaciones y peor racha

```sh
$ /usr/bin/python3 Kaenor/ops/scratch-f4/f4_ledger.py
### runtime/state_burst/paper_executions.jsonl     entradas=41  cierres=0
### runtime/state_classic-xrp-2x100/...            entradas=5   cierres=0
### runtime/f3/e2e/state/...                       entradas=5   cierres=0
### runtime/f1-scratch/sis/...                    entradas=0   cierres=40   <-- ver abajo
```

**El único ledger con cierres es inyectado, no medido. Prueba:**

```sh
$ /usr/bin/python3 -c "..."   # sobre runtime/f1-scratch/sis/paper_executions.jsonl
  n_registros           = 40
  entry_price distintos= 1 -> {80000}
  hypothesis_ids        = ['h00', 'h01', 'h02', 'h03', 'h04'] ... (h00..h39, correlativos)
  quantity distintas   = {0.001}
```

Un solo precio, quantity constante, hipótesis correlativas `h00..h39`: es la inyección de
F1, no mercado. **Sus 57,5% de winrate y su −209% de «drawdown» son artefactos.** No los uso.

| Métrica pedida | Valor real | Por qué |
|---|---|---|
| Curva de equity | **no existe** | 0 cierres en todos los ledgers reales |
| Max drawdown | **no calculable** | requiere la curva |
| Nº de operaciones (cerradas) | **n = 0** | 41+5+5 entradas, 0 cierres |
| Peor racha perdedora | **no calculable** | requiere la curva |

**No es «n<30, insuficiente». Es n=0: no hay ni una sola operación cerrada en todo el historial
del sistema.** No se puede afirmar nada sobre el comportamiento de la cola de pérdidas porque
la cola nunca se ha observado. En un sistema cuyo SL está a −200% del margen (B3), la cola es
exactamente lo que más importa.

Lo que sí es real y medible del run de burst (`runtime/state_burst/`):

```sh
$ /usr/bin/python3 Kaenor/ops/scratch-f4/f4_burst.py
  entradas=41  posiciones_vivas_en_positions.jsonl=41
  TP implicito: min=20.0000%  max=20.0000%
  SL implicito (TP/2): min=10.0000%
  notional_usd=[20.0]  margin_usd=[1.0]  leverage=[20]
  ventana: 2026-09-03 19:47 -> 2026-09-04 01:41 UTC  (5.89 h, 442 ciclos)
  expectancy CONTAMINADO registrado: min=0.809174  max=4.405441  medio=3.598255 (positivo 41/41)
```

**41 posiciones simultáneas y ninguna cerrada**, con `max_open_positions=5` configurado, y
los 41 expectancies que justificabanabrirlas salen **positivos** de la métrica rota (punto 1
del encargo). Ese es el caso de estudio: el sistema abrió 41 posiciones creyendo que ganaba.

> Salvedad de honestidad: **no achieved** que el guard de 5 no actuara en ese run. El run no dejó
> `daily_pnl.json` (los otros 7 state_dir sí), y su `runtime_stats.json` lleva claves que el
> `OrchestratorConfig` actual no tiene (`stop_loss_pct`, `mode:"paper"`): **es un harness anterior**.
> Probado el guard actual (B5): **funciona**. Lo que no puedo afirmar es que hubiera parado ese run.

---

## B. Qué pasa si mañana rellenan las claves y apuntan a mainnet

### B1. El gate existe y falla seguro — pero solo hay un flag, y no hay salida

```sh
$ grep -rn 'QUANTMATH_ALLOW_MAINNET' --include=*.py . | grep -v '/tests/'
./quant_math/cli/main.py:964      if os.environ.get("QUANTMATH_ALLOW_MAINNET") != "1":
./quant_math/orchestrator.py:118  "QUANTMATH_ALLOW_MAINNET") != "1":
```

**VERIFICADO, a favor del sistema:** mainnet está bloqueado por diseño
(`orchestrator.py:105-122`): exige `api_keys_present()` **y** `QUANTMATH_ALLOW_MAINNET=1`.
`testnet: bool = True` es el default (`orchestrator.py:78`). Los datos de mercado **siempre**
son reales; `dry_run` solo controla la ejecución (`orchestrator.py:13`).

**Tres|Matices que lo debilitan:**

1. **La doble confirmación es del TUI, no del motor.** `cli/main.py:970-975` pide 2 confirmaciones,
   pero la puerta real es `quant_math_bg.py` con un JSON por argv (`cli/main.py:304,323`). Un JSON
   con `dry_run:false, testnet:false` + la variable de entorno **entra igual**: el motor no sabe
   que hubo un wizard. **El control real es 1 flag de entorno, no 2 confirmaciones.**
2. **Dos defaults opuestos para `BYBIT_TESTNET` en el mismo fichero.**
   `exchanges.py:35` → default `"true"` (falla seguro). `exchanges.py:74` → default `""`, y `""`
   no está en `("1","true","yes")` → `env_testnet=False` → **no fuerza `sandbox`**.
   Con la variable ausente o mal escrita, `ExchangeAPI` no sella el modo.
3. **El modo de margen se fija en `try/except` que continúa** (`orchestrator.py:803-808`):
   `set_margin_mode(...,"isolated")` y `set_leverage(...)` — si fallan, el log dice *«continúo»*
   y la orden **se manda igual**. Si el isolated no se aplicó, la posición queda en **cross**:
   la liquidación deja de afectar al margen de la posición y pasa a afectar **a toda la cuenta**.

**Y el hallazgo que domina todos los demás:**

```sh
$ grep -rn 'create_order\|place_order\|reduceOnly' --include=*.py . | grep -v '/tests/'
./quant_math/orchestrator.py:810:   order = api.create_order(signal["symbol"], side, qty, order_type="market")
./data_acquisition/data_sources/exchanges.py:265:  def create_order(...)   # definicion
./order_management/order_management.py:169:  def create_order(...)   # modulo no conectado
```

**Un único call site de `create_order` en todo el código de producción, y es de apertura.**
No hay `reduceOnly`, ni orden de cierre, ni `cancel_order` en la cadena real.
`close_position` (`decision_engine/main.py:340-380`) **solo escribe una línea JSONL**; lo llama
`_check_exits` (:460-492) cuando el precio cruza TP o SL.

> **En mainnet el sistema abre posiciones reales y no tiene ninguna ruta de código que las cierre.**
> El SL/TP que el libro registra no es una orden en el exchange: es una línea en un fichero.
> Un SL en un exchange es un orden condicional que el servidor ejecuta aunque tu proceso esté muerto.
> Aquí no existe ese orden. **Este es el riesgo número 1 de la lista.**

### B2. El SL de burst es inalcanzable: la liquidación va antes

Perfil **medido del run real** (`runtime/state_burst/`, no del README):
`notional 20,00 · margin 1,00 · leverage 20 · TP 20% · SL 10%`.

```sh
$ /usr/bin/python3 Kaenor/ops/scratch-f4/f4_b.py    # sección B1
  notional=20.0  lev=20x  margin=1.00  SL=TP/2=10%
  SL dispara a -10%  ->  perdida = 20.0*0.10 = 2.00 USD = 200% del margen
  MMR 0.50% -> liquidacion cuando la perdida=1.00-0.1000=0.9000 USD = -4.50% de precio
      SL en -10.00%  ->  *** INALCANZABLE: la liquidacion va ANTES *** (factor 2.22x)
  MMR 0.35% -> -4.65%  -> factor 2.15x   |   MMR 0.75% -> -4.25%  -> factor 2.35x
  el margen entero se consume a -5.00% (sin MMR)
```

A 20×, el margen entero se agota en un movimiento adverso del **5%**. **El SL está al 10%:**
va **2,15–2,35× más lejos de donde el dinero se acaba.** No es que el SL sea amplio: es que
**es código muerto en la práctica**. Y no es un detalle de burst — es la misma aritmética que
`ops/DECISIONES-ROI.md` ya le dice a Leonardo para 100× («un movimiento adverso de ~1% liquida»),
con el número que corresponde a la config que el repo realmente ejecutó.

### B3. Pérdida por operación, con el WR medido (34,87%)

| Perfil | nocional | SL | pérdida al SL | % del margen | liquid. | E[trade] |
|---|---|---|---|---|---|---|
| classic lev 3 (F1: 100×0,05×3) | 15,00 | 1,00% | **−0,1500 USD** | 3% | −33,33% | −0,0081 USD |
| classic lev 1 (F1: 100×0,05×1) | 5,00 | 1,00% | **−0,0500 USD** | 1% | −100% | −0,0027 USD |
| **burst lev 20 (REAL)** | **20,00** | **10,00%** | **−2,0000 USD** | **200%** | **−4,5%** | — |

En classic el SL es alcanzable y la pérdida por trade es de céntimos. **El daño de este
sistema está concentrado en burst**, y burst es el modo que el propio wizard ofrece como
«Wizard Burst Scalping» con apalancamiento configurable (`cli/main.py:719-728`).

Con 5 posiciones simultáneas (el tope del guard) yendo todas a SL: **−10,00 USD**, la cuenta
entera de 50,00 que trae el propio run de burst. Probabilidad de 5 pérdidas seguidas con
WR 34,87%: **11,719%** — uno de cada nueve dias.

### B4. El guard de riesgo es ciego a la pérdida que aún no ha ocurrido

```sh
$ grep -n 'equity = ' quant_math/orchestrator.py
1007:  equity = self.config.initial_capital + realized_total
```

`_ledger_pnl` (`orchestrator.py:660-687`) **solo suma registros con `"motivo_cierre"`**. El equity
del guard es capital inicial **+ PnL realizado**. La pérdida de las posiciones abiertas **no
entra**. Ejecutado:

```sh
$ /usr/bin/python3 Kaenor/ops/scratch-f4/f4_b.py    # sección B4
  5 pos burst abiertas yendo a SL: perdida NO realizada=10.00 USD (20% de la cuenta)
     equity que VE el guard = initial_capital+realized = 50.00 (sin cierres, realized=0)
     drawdown que VE el guard = 0.00%  (limite 20%)  ->  *** PERMITE ***   perdida real = 20%
```

**Puedes tener el 20% de la cuenta a un SL y el guard ve 0,00% de drawdown y dice PERMITE.**
Los tres topes (`max_daily_loss_usd` 2,50 · `drawdown_limit` 20% · `max_open_positions` 5) son
controles de **apertura**, nunca de cierre: **no pueden limitar una pérdida que ya está abierta.**

### B5. El guard sí funciona (probado) — para que conste a favor

```sh
$ /usr/bin/python3 Kaenor/ops/scratch-f4/f4_guard.py
  sano                          open_count=0  -> PERMITE
  4 abiertas                    open_count=4  -> PERMITE
  5 abiertas (=max)             open_count=5  -> BLOQUEA  open positions 5 >= max 5 — entries blocked
  41 abiertas (caso REAL)       open_count=41 -> BLOQUEA  open positions 41 >= max 5 — entries blocked
  perdida diaria -2.60          open_count=0  -> BLOQUEA  daily loss -2.60 <= -2.50
  equity 30 vs peak 50          open_count=0  -> BLOQUEA  drawdown 40.00% > 20%
```

La lógica de `circuit_breaker.py:98-121` es correcta y está conectada (`orchestrator.py:1009`).
**Lo que falla no es el guard: es que mide la variable equivocada (B4) y que el único `create_order`
es de apertura (B1).**

---

## C. ¿Existe algún tope de riesgo por operación?

**Respuesta corta: no. En ningún sitio. En USD, no.**

```sh
$ grep -rniE 'max_risk_per_trade|risk_per_trade|max_loss_per_trade|max_risk_usd|risk_limit_usd|max_notional|max_order_notional' --include=*.py . | grep -v '/tests/'
./quant_math/risk/sizing.py:110:    def calculate(portfolio_value, risk_per_trade, stop_loss_distance) -> float:
./webui/.../routes.py:290,360                                "risk_per_trade": 2.0     (WebUI, fuera de alcance)
```

1. **`order_management/` NO está en la ruta viva.** Está en la **raíz** del repo, no en
   `quant_math/`, y solo lo importan `backtesting/backtester.py:17` y un adaptador con
   `try/except` (`quant_math_adapter.py:31`). La ruta viva usa `ExchangeAPI.create_order`
   (`exchanges.py:265`). Su `create_order` (`order_management.py:169`) **no tiene ningún tope**:
   construye un objeto `Order` y lo devuelve.
2. **Existe un módulo de dimensionamiento por riesgo y no lo usa nadie.**
   `quant_math/risk/sizing.py:110` (`PositionSizer.calculate` con `risk_per_trade`) tiene
   **0 referencias** desde orchestrator / decision_engine / bg. Lo mismo:
   ```sh
     ValueAtRisk       -> 0 referencias
     ExpectedShortfall -> 0 referencias
     PositionSizer     -> 0 referencias
     KellyCriterion    -> 0 referencias
     portfolio_risk    -> 0 referencias
   ```
   **VaR, ES, stress testing y Kelly están escritos, probados y desconectados del dinero.**
3. **Lo único que limita es un tope de margen, y falla abierto.**
   `risk_manager.py:93` → `max_position = account_value * max_position_size_pct`; el orquestador
   lo llama **con el margen**, no con el nocional (`orchestrator.py:707`:
   `margin_used = notional / max(1, lev_used)`), y envuelto en `try/except` que **devuelve el
   nocional sin capar** si algo peta (`orchestrator.py:712-714`, log *«sin cap»*). Ejecutado:
   ```sh
   $ /usr/bin/python3 Kaenor/ops/scratch-f4/f4_c.py
     burst real 1*20        notional=  20.0 lev=20 margen= 1.00 -> approved=True  nocional sale= 20.0 USD = 0.40x la cuenta (50)
     burst al tope de margen notional= 200.0 lev=20 margen=10.00 -> approved=True  nocional sale=200.0 USD = 4.00x la cuenta (50)
     nocional 1000 @lev20   notional=1000.0 lev=20 margen=50.00 -> approved=False approved_size=0.00
   ```
   **El tope permite 200,00 USD de nocional sobre una cuenta de 50,00 (4,00×) y lo aprueba.**
   Y dice nada del −2,00 USD que puede costar esa posición.

**Un hallazgo de este bloque es alto y no figuraba en el encargo:** el tope de riesgo por
operación no falta por descuido de un parámetro — **falta porque la librería que lo implementa
existe, está probada, y no está conectada a la ruta que mueve dinero.**

---

## Contraste exigido: `ops/DECISIONES-ROI.md` vs el código

| Afirmación del doc | Veredicto | Evidencia |
|---|---|---|
| §2.1 «TP y SL **no son fijos**: son inputs del wizard (`take_profit_roe`, `stop_loss_roe`)» | **FALSO** | `grep -rn 'take_profit_roe\|stop_loss_roe' --include=*.py .` → **0 ocurrencias**. El código tiene un solo `take_profit_pct` y un SL derivado por propiedad, «sin excepción» (`main.py:331-335`) |
| §2.2 «Las comisiones entran en el expectancy» | **PARCIAL, y por eso es peor** | En el backtester **sí**: `_fee` (`backtester.py:656`), entrada `:755`, salida `:771`. En el ledger paper y en la ruta viva **no**: 0 coincidencias de `commission`/`fee` en `decision_engine` y `orchestrator` |
| «con 100× un movimiento adverso de ~1% liquida» | **VERDADERO** | Aritmética correcta; aplicada a la config real del repo (20×) es el 5% → mata el SL (B2) |

**Gana el código, y el doc describe un sistema que no existe.** El doc tiene razón en el
razonamiento de liquidación y en que las comisiones deben entrar; el código no lo implementa.
Peor: la comisión **se descuenta en el backtester** (el numerador del expectancy) pero **no en
el libro** donde se registrarían las operaciones de paper y de live. O sea: el mismo número se
produce con costes y se consume sin ellos.

### Hallazgo adicional — dos poblaciones distintas en la métrica que decide

```sh
$ grep -n 'num_trades=len(trades)\|win_rate = PerformanceMetrics.win_rate(trades)' backtesting/backtester.py
876:  win_rate = PerformanceMetrics.win_rate(trades)     # trades = TODOS (:857 añade los no cerrados)
889:  num_trades=len(trades)                            # TODOS
$ grep -n 'expectancy = ' quant_math/orchestrator.py
564:  expectancy = total_return_pct / n_trades if n_trades > 0 else 0.0
```

`win_rate` se calcula sobre **todos** los trades; `expectancy` divide el retorno de
**`equity_curve[-1]`** (solo los cerrados, punto 1 del encargo) entre **`len(trades)`** (todos).
`scientific_score` (`orchestrator.py:563-567`) **mezcla las dos poblaciones**: `win_rate/100` de
una y `total_return_pct` de la otra. **El ranking que decide qué se opera se construye sobre
dos conjuntos de operaciones que no coinciden.** Esto no estaba en el encargo.

---

## D. Posición de riesgo ordenada

| # | Riesgo | Evidencia | A quién afecta |
|---|---|---|---|
| **1** | **Mainnet abre posiciones y no tiene ruta de cierre.** 1 solo `create_order`, de apertura | `orchestrator.py:810`; `close_position` `main.py:340-380` solo escribe JSONL; `_check_exits` `:460-492`; grep sin `reduceOnly` | Leonardo, **total**. La posición queda abierta sin SL en el exchange; la pérdida sigue corriendo cuando el proceso muere |
| **2** | **El SL de burst no se puede ejecutar**: está al 10%, la liquidación llega al 4,25–4,65% | `f4_b.py` B1 (MMR 0,35/0,5/0,75%); config real `state_burst` lev 20 / SL 10% | Leonardo, **2,00 USD por posición = 200% del margen**; −10,00 USD con 5 |
| **3** | **El guard mide solo PnL realizado**: con 20% de la cuenta a SL ve 0,00% de dd y permite | `orchestrator.py:1007` `equity = initial_capital + realized_total`; `_ledger_pnl` `:674` solo `motivo_cierre`; `f4_b.py` B4 | Leonardo. Los 3 topes no limitan pérdida abierta, solo aperturas |
| **4** | **No hay tope de riesgo por operación en USD**; el único tope es de margen y falla abierto | `f4_c.py`; `risk_manager.py:93`; `orchestrator.py:707,712-714`; `sizing.py:110` con 0 refs | Leonardo. Permite 200,00 de nocional sobre 50,00 de cuenta (4,00×) |
| **5** | **El expectancy que ordena está roto por población inconsistente**, además de la contaminación ya conocida | `backtester.py:861,876,889`; `orchestrator.py:564,563-567` | Leonardo y el ranking: se opera lo que la métrica recomienda, que no es lo que se midió |
| **6** | **El modo de margen y el apalancamiento se fijan en `try/except` que continúa** → posible **cross** | `orchestrator.py:803-808` (*«continúo»*) | Leonardo. En cross la liquidación afecta a **toda** la cuenta, no a la posición |
| **7** | **La doble confirmación es del TUI; el motor solo mira 1 flag de entorno** | `cli/main.py:970-975` vs `orchestrator.py:105-122`; puerta real `quant_math_bg.py` (JSON argv) | Leonardo. Un JSON con `testnet:false` + `QUANTMATH_ALLOW_MAINNET=1` entra sin wizard |
| **8** | **`BYBIT_TESTNET` con dos defaults opuestos en el mismo fichero** | `exchanges.py:35` (`"true"`) vs `:74` (`""` → False → no fuerza `sandbox`) | Leonardo. Variable ausente o mal escrita → sin sello de sandbox |
| **9** | **n real de operaciones cerradas = 0.** La cola de pérdidas nunca se ha observado, y en burst la cola es −200% del margen | `f4_ledger.py`; el único ledger con cierres es inyectado (1 precio, qty fija, h00..h39) | Leonardo. No hay base para afirmar nada sobre el riesgo de cola |
| **10** | **La librería de riesgo (VaR, ES, Kelly, PositionSizer, stress) está desconectada**: 0 referencias desde la ruta de dinero | `f4_ledger.py`/grep: `ValueAtRisk`, `ExpectedShortfall`, `PositionSizer`, `KellyCriterion`, `portfolio_risk` → 0 | Leonardo + el equipo. Existe la defensa y no está conectada |
| **11** | **La comisión se cobra en el backtester y no en el libro** | `backtester.py:656,755,771` vs 0 en `decision_engine`/`orchestrator` | Leonardo. El expectancy se produce con costes y se consume sin ellos |
| **12** | `order_management/` (raíz, con modelo de comisiones y slippage) **no está en la ruta viva** | grep: solo `backtesting/backtester.py:17` y `quant_math_adapter.py:31` (try/except) | Leonardo. La ruta real no pasa por el módulo de gestión de órdenes |

### Lo que NO verifiqué (y no afirmo)

- **No simulé una sesión de mainnet.** Sin claves, y con la instrucción de no tocar nada.
  Todo B2/B3 es aritmética sobre la config **medida** del run real, no una ejecución contra Bybit.
- **No verifiqué las MMR ni las tablas de liquidación vigentes de Bybit** para BTC/USDT a 20×.
  Las tres cifras (0,35% / 0,50% / 0,75%) son un barrido, no una consulta a la API. La conclusión
  es robusta a las tres: el factor está entre 2,15× y 2,35×.
- **No probé que el guard actual hubiera parado el run de 41 posiciones** de `state_burst`.
  Probé el guard aislado (funciona) y verifiqué que aquel run vino de otro harness (sin
  `daily_pnl.json`, claves de config inexistentes hoy). La relación causal queda **INFERIDA**.
- **No comprobé la cola de liquidaciones del backtester** (`_liq_price_long`, `num_liquidations`):
  el backtester tiene su propio modelo de liquidación que no contrasté contra Bybit.
- **No medí el spread real ni la profundidad** del libro en Bybit testnet. El 0,05 pp de F3 es
  un parámetro del código, no una medición de mercado.
- **WebUI no auditado**, por decisión de Leonardo. En C lo cito solo como *configuración*
  (`routes.py:290` declara `risk_per_trade: 2.0`) sin entrar en su funcionamiento.
- **No verifiqué si existe algún proceso externo** (cron, watchdog) que cierre posiciones.
  `grep` de `create_order` en el repo no lo encontraría si estuviera fuera del repo.

---

*Fin de F4. Ningún cambio en `Quant-Math-Public`: los scripts de medición están en
`Kaenor/ops/scratch-f4/` y solo leen.*
