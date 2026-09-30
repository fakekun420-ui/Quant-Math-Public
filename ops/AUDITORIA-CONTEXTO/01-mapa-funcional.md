# F1 — Mapa funcional de Quant-Math-Public (con criterio de demostración)

**Fecha:** 2026-09-29 · **Cargo:** `kaenor-software-architect` (D2) · **Fase:** F1 (bloqueante)
**Método:** toda afirmación marcada **VERIFICADO** tiene un comando ejecutado con su salida pegada.
**INFERIDO** = deducido de código leído, no ejecutado. **NO DEMOSTRADO** = no encontrado.

Reproducir todo: `cd /sdcard/projects/Quant-Math-Public`. Python: `/usr/bin/python3` (3.12.3).
Scratch de esta fase: `runtime/f1-scratch/` (gitignored; el repo quedó sin cambios).

---

## 0. Línea base

```sh
$ python3 -m pytest --collect-only -q 2>&1 | tail -3
    <Function test_spectral_cycle_detection>
    <Function test_bayes_ci_formal>
    <Function test_cross_symbol_validation>
========================= 162 tests collected in 1.75s =========================
```

**162 tests collected** → coincide con la línea base. No hay desvío. **VERIFICADO**

---

## 1. La puerta de entrada REAL

### 1.1 Imports de todos los entrypoints candidatos

```sh
$ cd /sdcard/projects/Quant-Math-Public
$ for M in aqde_runner quant_math.cli.main quant_math_bg model_based_generator; do
    echo "=== python3 -c 'import $M' ==="
    /usr/bin/python3 -c "import $M; print('OK', getattr($M,'__file__','?'))" 2>&1 | tail -4
  done
=== python3 -c 'import aqde_runner' ===
OK /sdcard/projects/Quant-Math-Public/aqde_runner.py
=== python3 -c 'import quant_math.cli.main' ===
OK /sdcard/projects/Quant-Math-Public/quant_math/cli/main.py
=== python3 -c 'import quant_math_bg' ===
OK /sdcard/projects/Quant-Math-Public/quant_math_bg.py
=== python3 -c 'import model_based_generator' ===
OK /sdcard/projects/Quant-Math-Public/model_based_generator.py
$ /usr/bin/python3 -c "import quant_math; print('OK', quant_math.__file__)"
OK /sdcard/projects/Quant-Math-Public/quant_math/__init__.py
```

Todos los módulos del README existen e importan. **VERIFICADO**

### 1.2 `python -m quant_math.cli.main` NO es ejecutable sin TTY

```sh
$ timeout 60 /usr/bin/python3 -m quant_math.cli.main < /dev/null 2>&1 | head -40
Warning: Input is not a terminal (fd=0).
...
  File "/sdcard/projects/Quant-Math-Public/quant_math/cli/main.py", line 2016, in <module>
    sys.exit(main())
  File "/sdcard/projects/Quant-Math-Public/quant_math/cli/main.py", line 1875, in main
    ).unsafe_ask()
  ...
PermissionError: [Errno 1] Operation not permitted
```

**El import funciona, pero el módulo no es un CLI: es un TUI `questionary`**
(`quant_math/cli/main.py:1839 def main()`, menú en `while True`, `:1875 questionary.select(...).unsafe_ask()`).
Sin terminal, revienta. **También ignora `--help`**: no hay argparse, `--help` se interpreta como
acción de menú.

> **Consecuencia para F3: `python -m quant_math.cli.main` NO sirve como entrypoint de ejecución
> end-to-end.** Es correcto como puerta de usuario (wizard) y es lo que documenta el README, pero no
> es automatizable. **VERIFICADO**

### 1.3 La cadena real de lanzamiento

| Tramo | Dónde | Qué hace |
|---|---|---|
| 1 | `quant_math/cli/main.py:1839 main()` | menú interactivo (wizard) |
| 2 | `quant_math/cli/main.py:304 RuntimeState.start` | `subprocess.Popen([sys.executable, "-u", launcher, config_json, mode], start_new_session=True)` (`:323`) |
| 3 | `quant_math_bg.py:22 main()` | **proceso real, desacoplado** → importa Orchestrator |
| 4 | `quant_math/orchestrator.py:1091 run_forever()` | bucle de ciclos |
| 5 | `quant_math/orchestrator.py:927 run_cycle()` | generate→publish→decide→execute→feedback |

`quant_math/cli/main.py:118` importa `Orchestrator` pero **solo lo usa como módulo**: el hijo lo ejecuta
`quant_math_bg.py:121-126`. El TUI no calcula nada.

### 1.4 ENTRYPOINT PARA F3 — probado

**`quant_math_bg.py` es la puerta real.** Lanzado como proceso, escribe PID file, log y corre ciclos:

```sh
$ cd /sdcard/projects/Quant-Math-Public
$ CFG=$(python3 -c "import json;print(json.dumps({
  'symbols':['BTC/USDT'],'timeframe':'1h','lookback_days':30,
  'initial_capital':100.0,'entry_pct':0.05,'take_profit_pct':0.02,
  'min_paper_trades':3,'hypotheses_per_cycle':1,
  'kb_path':'<DIR>/kb.jsonl','state_dir':'<DIR>/state',
  'interval_seconds':1,'dry_run':True,'mode':'classic','leverage':1,
  'log_path':'<DIR>/qm.log'}))")
$ timeout 240 python3 -u quant_math_bg.py "$CFG" classic &

$ cat <DIR>/state/orchestrator.pid
20622

$ head -40 <DIR>/qm.log
2026-09-29 02:31:08,597 [INFO] numexpr.utils: NumExpr defaulting to 8 threads.
[HypothesisKnowledgeBase] Initialized with storage path: autonomous_research/data/hypotheses
2026-09-29 02:31:09,273 [INFO] data_acquisition.data_sources.exchanges: Initialized bybit exchange connection
2026-09-29 02:31:09,273 [WARNING] quant_math.decision_engine.main: [LEARN MODE] gate expectancy>0 DESACTIVADO temporalmente
2026-09-29 02:31:09,273 [INFO] quant_math.decision_engine.main: [slippage] modelo activo: 0.050% por lado
2026-09-29 02:31:09,274 [INFO] quant_math.decision_engine.main: [graduacion] automatica armada: se desactivara LEARN_MODE con 30 cierres de media positiva
2026-09-29 02:31:09,274 [INFO] quant_math.decision_engine.main: [kb-storage] backend=jsonl (use_postgres=False)
============================================================
ORCHESTRATOR CYCLE 1 (modo=classic, datos=REALES/bybit)
============================================================
  [ml-prior] modo=collecting registros=0 rate_global=0.5 reordenado=False
2026-09-29 02:31:09,292 [INFO] quant_math.ml.regime_learning: [SIS] recolectando: 0/30 operaciones post-corte
[sis] modo=collecting ops=0 (recolectando)
2026-09-29 02:31:27,924 [INFO] data_acquisition.data_sources.exchanges: Fetched 300 candles for BTC/USDT
  [model-gen] +2 hipotesis cientificas para BTC/USDT
2026-09-29 02:31:45,345 [INFO] data_acquisition.data_sources.exchanges: Fetched 720 candles for BTC/USDT
  Data fetched: 720 candles
```

**Medición de ritmo:** con `interval_seconds=1`, el proceso llegó a **`[cycle 88]` en ~4 minutos**
antes de que lo matara el `timeout 240`. Un ciclo completo ≈ 2,7 s en un solo símbolo. **VERIFICADO**

> **`log_path` es obligatorio para F3.** Sin él, `quant_math_bg.py:72-74` manda toda la salida a
> `quant_math.log` en la raíz del proyecto (1.6 MB ya). Configurar `log_path` y `state_dir` en un
> directorio de scratch es lo que permite una ejecución reproducible y sin efectos colaterales.

> **OJO — el launcher enciende LEARN_MODE.** `quant_math_bg.py:119` y `quant_math/cli/main.py:307`
> hacen `os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")`, mientras que el default del engine es
> `"0"` (`quant_math/decision_engine/main.py:41-42`). **Por la puerta real, el gate `expectancy>0`
> está DESACTIVADO.** Verificado arriba en el log. **VERIFICADO** — implicacion en §3.

### 1.5 Alternativa para F3: un solo ciclo, salida a consola

`Orchestrator.run_forever(max_cycles=1)` existe (`quant_math/orchestrator.py:1091`) y es la vía más
barata de smoke-test. Ejecutado de verdad:

```sh
$ python3 -u -c "
from quant_math.orchestrator import Orchestrator, OrchestratorConfig
cfg = OrchestratorConfig(symbols=['BTC/USDT'], timeframe='1h', lookback_days=30,
  initial_capital=100.0, entry_pct=0.05, take_profit_pct=0.02,
  min_paper_trades=3, hypotheses_per_cycle=2,
  kb_path='<DIR>/kb.jsonl', state_dir='<DIR>/state', interval_seconds=1,
  dry_run=True, mode='classic', leverage=1)
Orchestrator(cfg).run_forever(max_cycles=1)"
```

Salida (recortada): 8 hipótesis creadas, `Data fetched: 720 candles`, 6 backtests
(`trades=0 wr=0.00% ret=0.00% sharpe=0.00`), luego
`[decision] BTC/USDT: NO_ENTRY (sin hipótesis de expectativa positiva disponible)` y
`[cycle 1] generadas=0 señales=0 no_entry=1 skip_pos=0`. **VERIFICADO**

---

## 2. El flujo de 6 pasos

| # | Paso | Implementación | `grep` que lo localiza | Estado |
|---|---|---|---|---|
| 1 | Bybit OHLCV | `ExchangeAPI.fetch_ohlcv` `data_acquisition/data_sources/exchanges.py:101`; fábrica `get_market_api` `data_acquisition/data_sources/forex.py:184`; consumo `DecisionEngine._data_provider` `quant_math/decision_engine/main.py:206` y `fetch_real_data` `:513` | `grep -n 'def fetch_ohlcv\|def get_market_api' data_acquisition/data_sources/*.py` | **VERIFICADO** |
| 2 | AQDE Runner (plantillas + ARIMA/GARCH + mutaciones) | `class AQDERunner` `aqde_runner.py:47`; plantillas `generate_base_hypotheses` `:220`; ARIMA/GARCH `model_based_generator.py:77,82` inyectado en `aqde_runner.py:636-649`; adaptativas/mutación `generate_adaptive_hypotheses` `:319`; backtest `run_backtest_for_symbol` `:667` | `grep -n 'class AQDERunner\|def generate_base_hypotheses\|def generate_adaptive_hypotheses' aqde_runner.py` | **VERIFICADO** |
| 3 | Orchestrator publica a KB JSONL | `_result_to_kb_record` `quant_math/orchestrator.py:542`; `_publish_to_kb` `:650` → `DecisionEngine.register_hypothesis` `quant_math/decision_engine/main.py:249` | `grep -n 'def _result_to_kb_record\|def _publish_to_kb' quant_math/orchestrator.py` | **VERIFICADO** |
| 4 | Decision Engine | `decide()` `quant_math/decision_engine/main.py:872`; ranking `ranked_candidates` `:256` / `select_best_hypothesis` `:270`; queryables `:26` | `grep -n 'def decide\|def ranked_candidates' quant_math/decision_engine/main.py` | **VERIFICADO** |
| 5 | Ejecuciones paper en ledger JSONL | `_execute_paper_trade` `quant_math/orchestrator.py:715` (escribe `:774`); cierres `DecisionEngine.close_position` `quant_math/decision_engine/main.py:340` (escribe `:374`) | `grep -rn 'paper_executions.jsonl' quant_math/ | grep -v test` | **VERIFICADO** |
| 6 | SIS unsupervised (KMeans) realimenta prioridades | `OperationLearningLoop._fit` `quant_math/ml/regime_learning.py:66`; `KMeans(...)` `:79`; `rank_families` `:123`; consumo en `Orchestrator._rank_hypotheses` `quant_math/orchestrator.py:340-370` | `grep -n 'KMeans(\|def load_loop\|def rank_families' quant_math/ml/regime_learning.py` | **VERIFICADO** |

### 2.1 Detalle por paso, con la salida que lo demuestra

**PASO 1 — Bybit OHLCV.** VERIFICADO con red real:
```
PASO1 Bybit OHLCV -> velas: 100 | ultima close: 83488.7 | ts: 1790647200000
```
Y en el log del orquestador: `Fetched 300 candles` / `Fetched 720 candles`. Datos **reales**, no
sintéticos (`OrchestratorConfig.dry_run` controla la ejecución, no los datos —
`quant_math/orchestrator.py:57-59`).

**PASO 2 — AQDE Runner.** VERIFICADO en el ciclo real:
```
  [model-gen] +2 hipotesis cientificas para BTC/USDT
[ResearchManager] Created hypothesis: MARIMA_MACD_13_34_BTCUSDT (hyp_99efe883)
[ResearchManager] Created hypothesis: MEnergy_Burst_1.5_BTCUSDT (hyp_a79bd93a)
[ResearchManager] Created hypothesis: Breakout_15_BTCUSDT_c1 (hyp_088c6c2b)
[ResearchManager] Created hypothesis: MACD_9_26_BTCUSDT_c1 (hyp_12ff6982)
[ResearchManager] Created hypothesis: RSIrev_14_BTCUSDT_c1 (hyp_65638a26)
[ResearchManager] Created hypothesis: BB_20_BTCUSDT_c1 (hyp_e248c0eb)
```
2 de las 6 vienen de ARIMA/GARCH (`model_based_generator`), 4 de plantillas.
Con `arch` disponible, el régimen GARCH se puebla de verdad:
```sh
$ PYTHONPATH=/tmp/qmp-libs python3 -c "...generate_model_hypotheses('BTC/USDT', closes, max_hypotheses=3)"
HAS_MODEL_BASED_GENERATOR= True  _HAS_GARCH= True
   MLowVol_RSI_BTCUSDT | StrategyType.MEAN_REVERSION | params={... '_regime': {'vol_pct': 1.0101, 'forecast_up': False, 'k_slope': np.float64(0.0), 'k_noise': np.float64(0.488526)}}
   MARIMA_MACD_13_34_BTCUSDT | StrategyType.MOMENTUM | params={... 'k_noise': np.float64(0.488526)}
   MEnergy_Burst_2.0_BTCUSDT | StrategyType.CUSTOM | params={... 'k_noise': np.float64(0.488526)}

$ python3 -c "import model_based_generator as m; print(m.HAS_MODEL_BASED_GENERATOR, m._HAS_GARCH)"
True  False        # sin PYTHONPATH: NO hay GARCH
```
**`arch` 8.0.0 y `psycopg2` SÍ están en `/tmp/qmp-libs`** (ambos importan OK con
`PYTHONPATH=/tmp/qmp-libs`). Sin ese `PYTHONPATH`, `model_based_generator._HAS_GARCH=False` y la
mitad del bloque "modelos científicos" del README no existe. **VERIFICADO**

**PASO 3 — publish a KB.** VERIFICADO, con la fórmula a la vista:
```
PASO3 record -> {'hypothesis_id': 'hyp_e22ffb69', 'status': 'failed', 'expectancy': 0.08,
                 'scientific_score': 0.3339, 'n_trades': 40}
   formula expectancy = total_return_pct/n_trades = 3.2 / 40 = 0.08
   fichero KB existe: True
   ranked_candidates: [('hyp_e22ffb69', 0.08)]
```
**Hallazgo de fórmula:** `expectancy = total_return_pct / n_trades`
(`quant_math/orchestrator.py:560-561`). No es una esperanza matemática por operación: es el retorno
total repartido. Y un `scientific_score` de 0,33 degrada el estado a `failed` (`:568-571`) **pero
`failed` sigue en `QUERYABLE_STATUSES`** (`quant_math/decision_engine/main.py:26`), así que un
resultado malo se puede operar. El gate de `expectancy>0` es el único filtro real.

**PASO 4 — Decision Engine.** VERIFICADO, las dos ramas:
```
# rama bloqueada (gate, ciclo real con learn_mode=0):
[decision] BTC/USDT: NO_ENTRY (sin hipótesis de expectativa positiva disponible)

# rama entrada (mismo código, expectativa 0.08 > 0):
PASO4 decide() -> {'action': 'entry', 'side': 'buy', 'price': 83528.5434,
                    'expectancy': 0.08, 'sizing_mult': 2.0}
```
El gate literal está en `quant_math/decision_engine/main.py:885-887`:
```python
exp_c = float(cand.get("expectancy", 0.0))
if exp_c <= 0 and not self.learn_mode:
    break                      # el resto tambien es <= 0
```

**PASO 5 — ledger paper.** VERIFICADO, contenido real del fichero:
```
{"mode": "paper", "key": "H1:BTC/USDT", "symbol": "BTC/USDT", "side": "buy",
 "quantity": 5.9888344171127355e-05, "entry_price": 83488.7, "notional_usd": 5.0,
 "take_profit_price": 85158.474, "hypothesis_id": "H1", "expectancy": 0.03, "cycle": 0}
{"type": "closure", ... "exit_price": 82612.4860935, "pnl": -0.052475, "pnl_pct": -1.0495, "motivo_cierre": "sl"}
{"type": "closure", ... "exit_price": 85115.894763,  "pnl":  0.09745,  "pnl_pct":  1.949,  "motivo_cierre": "tp"}
```

**PASO 6 — SIS / KMeans.** VERIFICADO (con 40 cierres y un `state_dir` que contenga
`paper_executions.jsonl`, nombre que `regime_learning.py:192` fija por código):
```
KB: 40 registros | paper_executions.jsonl: 40 cierres
modo SIS = active | filas = 40 | clusters KMeans = [0, 1]
cluster_stats = [{'cluster': 0, 'n': 17, 'win_rate': 0.0,  'mean_pnl_pct': -0.8065},
                 {'cluster': 1, 'n': 23, 'win_rate': 1.0,  'mean_pnl_pct':  1.0252}]
rank_families(BTC/USDT) = ['momentum', 'breakout', 'mean_reversion']
regime_table entradas = 2
```
Con pocas operaciones el SIS se queda en `collecting` y **no realimenta nada** (umbral
`MIN_ROWS = QUANTMATH_SIS_MIN_ROWS = 30`, `quant_math/ml/regime_learning.py:29`). El efecto sobre el
flujo es **advisory**: reordena candidatos en `Orchestrator._rank_hypotheses`
(`quant_math/orchestrator.py:355-364`), nunca toca el gate. VERIFICADO.

---

## 3. Los 3 PUNTOS DE DINERO

### P1 — Cálculo de entry / TP / SL

| Qué | Dónde | Fragmento real |
|---|---|---|
| TP en la entrada paper | `quant_math/orchestrator.py:752-753` | `tp_price = price * (1 + self.config.take_profit_pct) if side == "buy" else price * (1 - self.config.take_profit_pct)` |
| SL = TP/2 | `quant_math/decision_engine/main.py:330-335` | `@property` / `def stop_loss_pct` → `return self.take_profit_pct / 2.0` |
| Disparo de TP/SL | `quant_math/decision_engine/main.py:474-484` | `hit_sl = cur <= entry*(1-sl)` / `hit_tp = cur >= entry*(1+tp)` (espejo en `sell`) |
| PnL | `quant_math/decision_engine/main.py:358` | `pnl = qty * (exit_px - entry_price) * direction` |
| Slippage adverso | `quant_math/decision_engine/main.py:585-593` | `adverse_up = (side == "buy") == entering` → `price*(1+s)` |
| Prioridad de umbrales | `quant_math/decision_engine/main.py:437-457` | guardados al abrir → los del ledger → los de config (un cambio de config **no** mueve un SL vivo) |

**Medido (TP/SL exactos, `tp=0.02`):**
```
TP_pct= 0.02  SL_pct= 0.01
precio SL calculado = 82653.813  | precio TP calculado = 85158.474
cierre SL pnl= -0.052475 pct= -1.0495
cierre TP pnl=  0.09745  pct=  1.949
```
El SL es exactamente la mitad del TP en porcentaje (ratio 2:1, como promete el README). El PnL
realizado sale −1,0495% / +1,949% en vez de −1% / +2%: **el slippage del 0,05% por lado se aplica
dos veces** (fill de entrada y de salida) y se come ~0,1 puntos de round-trip. `exit_price` 82612.486
frente al teórico 82653.813 lo confirma. **VERIFICADO**

> El registro de **entrada** del ledger guarda `take_profit_price` pero **no** `stop_loss_pct`; el SL
> solo vive en el estado de posiciones (`positions.json`) y en el ledger de **cierres**. Si ese estado
> se pierde, `_position_exit_thresholds` cae al `stop_loss_pct` de configuración vigente, que puede ser
> otro. Mitigado por el fallback al ledger (`_entry_stop_loss_from_ledger`, `:411`).
> **INFERIDO — no lo ejecuté simulando pérdida de estado.**

### P2 — Dimensionamiento (sizing) y apalancamiento

`quant_math/orchestrator.py:715-748`:
```python
if self.config.mode == "burst":
    margin   = float(signal.get("margin", self.config.burst_margin))
    leverage = int(signal.get("leverage", self.config.burst_leverage))
    ...
    notional = margin * leverage            # L732
    lev_used = leverage
else:
    base_notional = (self.config.initial_capital * self.config.entry_pct
                     * float(signal.get("sizing_mult", 1.0)))   # L736
    notional = base_notional * self.config.leverage            # L738
    lev_used = max(1, self.config.leverage)
notional = self._apply_margin_cap(notional, lev_used, ...)      # L741
quantity  = notional / price                                   # L748
```

**Medido en los dos modos, con la aritmética a la vista** (`capital=100`, `entry_pct=0.05`/`0.10`,
`tp=0.02`, precio 83488,7):

| Modo | Fórmula | Valor medido | ¿Cuadra? |
|---|---|---|---|
| classic, `leverage=1`, `sizing_mult=1` | 100×0,05×1×1 | `notional=5.0` | ✅ exacto |
| classic, `leverage=3` | 100×0,05×1×3 | `notional=15.00` | ✅ exacto |
| classic, `sizing_mult=2.0` (vol-target) | 100×0,10×2,0×1 | `notional=20.0` | ✅ exacto |
| burst, `margin=10`, `burst_leverage=20` | 10×20 | `notional=200.00`, `margin_usd=10.0` | ✅ exacto |

Controles de riesgo alrededor (**INFERIDO** — leídos, no ejecutados):

| Control | Dónde | Comportamiento |
|---|---|---|
| Tope de margen por entrada | `_apply_margin_cap` `orchestrator.py:689` | `RiskManager.check_position_size`; **fail-open** con log si peta (`:713`) |
| Tope de exposición burst | `orchestrator.py:726-730` | `MAX_EXPOSURE_USD` sobre la suma de `margin_usd` abiertos |
| Apalancamiento máximo | `orchestrator.py:132-135` | clamp `1..500` en ambos modos |
| TP en burst | `orchestrator.py:131` | `take_profit_pct = max(0.02, min(0.50, ...))` |
| `max_position_pct` | `OrchestratorConfig:74` | 0,2 por defecto |
| Live bloqueado por diseño | `orchestrator.py:107-123` | `dry_run=False` exige API keys; mainnet exige `QUANTMATH_ALLOW_MAINNET=1` |

> **El exposure cap de burst mira `margin_usd`, no el modo.** En el registro classic no existe
> `margin_usd` (`orchestrator.py:769-774`), así que `_open_burst_entries` (`:623`) filtra
> `elif rec.get("margin_usd")` y **una entrada classic queda fuera del cálculo de exposición**.
> Solo afecta a burst, pero la aserción depende del campo, no del modo.
> **INFERIDO del código; no ejecutado con mezcla de modos.**

### P3 — Ejecución y ledger

| Qué | Dónde |
|---|---|
| Escritura de la entrada | `quant_math/orchestrator.py:773-777` — `open(state_dir/"paper_executions.jsonl", "a")` |
| Ruta del ledger | `quant_math/decision_engine/main.py:194` — `os.path.join(state_dir, "paper_executions.jsonl")` |
| Escritura del cierre | `quant_math/decision_engine/main.py:374` — `_append_state(self.ledger_path, closure)` |
| Lector de PnL para el circuit breaker | `Orchestrator._ledger_pnl` `quant_math/orchestrator.py:654` |
| Envío de orden real | `_execute_live_order` `quant_math/orchestrator.py:788` — solo si `not dry_run` (`:744`) |
| Publicación de eventos | `quant_math/decision_engine/event_bus.py` — `trade_opened` / `trade_closed` |

**Medido:**
```
ledger_pnl (hoy,total) = (0.044974999999999994, 0.044974999999999994)
```
`total = -0.052475 + 0.09745 = 0.044975` — el agregador lee bien las dos líneas de cierre.
**VERIFICADO**

Formato: **JSONL append-only**, un objeto por línea, dos tipos (`mode:"paper"` para entrada,
`type:"closure"` + `motivo_cierre` para salida). El comentario de `close_position:344` es explícito:
*"este archivo NUNCA se trunca ni se resetea"*. La reconciliación de posiciones abiertas
(`_open_burst_entries:623-648`) se hace reconstruyendo el estado a partir del ledger: una clave con
`motivo_cierre` se descarta; sin él y con `margin_usd` se cuenta como abierta. **El ledger es la fuente
de verdad, no el estado en memoria.** Eso es lo correcto.

---

## 4. Cómo se orienta con graphify (índice, NO prueba)

**El grafo está vivo y sirve, pero con límites honestos.**

```sh
$ graphify god-nodes .
God nodes (most connected):
  1. DecisionEngine - 68 edges
  2. QuantMathAdapter - 64 edges
  3. RuntimeState - 44 edges
  4. Orchestrator - 41 edges
  5. OrchestratorConfig - 38 edges
  6. AQDERunner - 37 edges
  7. ResearchManager - 34 edges
  8. JSONLKnowledgeBase - 33 edges
  9. ExchangeAPI - 32 edges
 10. run_full_e2e_test() - 32 edges

$ graphify explain DecisionEngine
Node: DecisionEngine
  ID:        quant_math_decision_engine_main_decisionengine
  Source:    quant_math/decision_engine/main.py L45
  Type:      code
  Community: DecisionEngine
  Degree:    68
Connections (68):
  <-- orchestrator.py [imports] [EXTRACTED] quant_math/orchestrator.py:L29
  --> .decide() [method] [EXTRACTED] quant_math/decision_engine/main.py:L872
  --> .close_position() [method] [EXTRACTED] quant_math/decision_engine/main.py:L340
  --> ._check_exits() [method] [EXTRACTED] quant_math/decision_engine/main.py:L460
  ...
```

`DecisionEngine` y `Orchestrator` son de verdad los dos polos del sistema: los dos god-nodes de más
grado son exactamente el motor de decisión y el orquestador. Confirma el mapa mental. **PERO**
`explain` no dice qué hace el código, solo dónde está; su valor real son los punteros de entrada a
`.close_position()` / `._check_exits()` / `._refresh_live_expectancy()`.

**Dos limitaciones medidas, no supuestas:**

1. `graphify path "AQDERunner" "DecisionEngine"` → **`No directed path found`**. La cadena real
   AQDE→Orchestrator→DecisionEngine **no existe como arista dirigida**; el acoplamiento es por
   *import* del orquestador y por construcción de objetos en runtime. El grafo de AST no ve el flujo
   de datos. **No uséis `path` para reconstruir el pipeline: mentirá.**
2. `graphify query "como se calcula el tamano de la posicion y el apalancamiento" --budget 2000`
   devolvió **25 nodos y ninguno era el código de sizing**; salieron `return_calculator.py`,
   `test_risk_persistence.py` y `ops/DECISIONES-ROI.md`. `query` es léxico y en español técnico no
   encuentra los símbolos. **Sirve para nombres, no para conceptos.**

**Lo que sí rindió:** `god-nodes` (dónde mirar primero) y `explain` (líneas exactas de los hubs).
En ambos casos lo que pasó después fue `grep`/`sed` sobre los ficheros que apuntaron.

**Aviso al resto de fases:** el grafo indexa `ops/DECISIONES-ROI.md` — *"Decisiones de Leonardo —
2026-09-28. TP/SL por ROI, apalancamiento y comisiones"*, con epígrafes *"TP y SL NO son fijos: se
preguntan en la encuesta del CLI"* y *"Las comisiones entran en el expectancy"*. **No lo he
verificado** y medirlo no es mi jurisdicción, pero el código que medí arriba (TP = `take_profit_pct`
fijo de config, SL = TP/2 fijo, expectancy **sin comisiones**) **no coincide con lo que ese documento
describe**. Alguien de D1/D4 debería cruzarlo antes de que cualquier cifra de rentabilidad sea firme.

---

## 5. Lo que NO verificado

| # | No verificado | Por qué |
|---|---|---|
| 1 | La ruta **live** (`_execute_live_order`, `orchestrator.py:788`) | Requiere API keys de Bybit testnet; `dry_run=True` en todo lo medido. Solo **leída**. |
| 2 | `_validate_live_access` (`orchestrator.py:889`) | Igual: sin keys nunca llega a ejecutarse. |
| 3 | Que el backtester produzca alguna vez `n_trades > 0` | En los ciclos reales medidos **siempre salió `trades=0`**, así que el expectancy real nunca se ejercita con datos de mercado. Mi rama de entrada (PASO 4) la forcé con un resultado de backtest artificial — **`decide()` y el sizing sí son reales; el `expectancy` no lo es.** |
| 4 | El comportamiento de `model_based_generator` cuando ARIMA falla dentro | `arch` funciona con `PYTHONPATH=/tmp/qmp-libs`; de la ruta sin `arch` solo comprobé `_HAS_GARCH=False`. |
| 5 | Modo `burst` en un `run_cycle` completo | Probado a nivel de sizing/ledger (`_execute_paper_trade` con `mode="burst"`), no un ciclo entero. |
| 6 | El grafo de graphify tras mis ejecuciones | No corrí `graphify update`; los nodos son los previos (coincidentes con la línea base que me dieron). |
| 7 | `.venv/` y el WebUI | Fuera de alcance por decisión de Leonardo. |
| 8 | Qué test rojo de los 162 | El recuento cuadra; identificarlo no era mi encargo. |
| 9 | `ops/AUDITORIA-QMP.md` y los 9 docs de `ops/` | Descartados por Leonardo. No los he citado ni usado como evidencia. |

---

## 6. Entregado a F3

```sh
cd /sdcard/projects/Quant-Math-Public
mkdir -p /sdcard/projects/Quant-Math-Public/runtime/f3
CFG=$(python3 -c "import json;print(json.dumps({
  'symbols':['BTC/USDT'],'timeframe':'1h','lookback_days':30,
  'initial_capital':100.0,'entry_pct':0.05,'take_profit_pct':0.02,
  'min_paper_trades':3,'hypotheses_per_cycle':2,
  'kb_path':'/sdcard/projects/Quant-Math-Public/runtime/f3/kb.jsonl',
  'state_dir':'/sdcard/projects/Quant-Math-Public/runtime/f3/state',
  'interval_seconds':60,'dry_run':True,'mode':'classic','leverage':1,
  'log_path':'/sdcard/projects/Quant-Math-Public/runtime/f3/qm.log'}))")

# LANZADOR REAL (equivalente a lo que hace el menu del TUI)
nohup python3 -u quant_math_bg.py "$CFG" classic &

# PARAR
kill $(cat /sdcard/projects/Quant-Math-Public/runtime/f3/state/orchestrator.pid)
```

- Si F3 quiere **un solo ciclo y salida por consola**, usar `Orchestrator(cfg).run_forever(max_cycles=1)`
  (§1.5) en vez del proceso.
- Añadir `PYTHONPATH=/tmp/qmp-libs` si se quiere la mitad GARCH de `model_based_generator`
  (y `psycopg2`, aunque el KB corre en JSONL: `use_postgres=False` por defecto, `orchestrator.py:60`).
- **Siempre** `log_path` y `state_dir` a un directorio de scratch: si no, la salida cae en
  `quant_math.log` de la raíz del proyecto.
- Duración de un ciclo, 1 símbolo: **≈2,7 s** con `interval_seconds=1`. Medido.

**Reversibilidad:** este informe no cambia código ni config. La única escritura en el proyecto es
`ops/AUDITORIA-CONTEXTO/01-mapa-funcional.md` (pedido) y datos de runtime bajo `runtime/f1-scratch/`
(gitignored). `git status` antes y después es idéntico. **Cheap de revertir.**
