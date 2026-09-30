# AUDITORÍA DE CONTEXTO — Quant-Math-Public

> **Encargo de Leonardo, 2026-09-29:** auditoría completa sobre *qué es, qué hace y cómo
> funciona*, con garantía de que **funciona**.
>
> **Veredicto de la puerta de veto (`kaenor-reality-checker`): NO APTO PARA OPERAR CON DINERO REAL.**
> Las 7 afirmaciones reclamadas fueron CONFIRMADAS una a una contra el código. Ninguna refutada.
>
> **Precedente:** la auditoría del 2026-09-28 fue **DESCARTADA por el usuario** por limitaciones y
> errores de entorno. No se hereda, no se cita, no se contrasta. Esta es measurements nueva.

## Regla que gobierna todo lo que sigue

**Prueba válida = comando ejecutado + salida pegada.** Prohibido: «el fichero existe», «lo dice el
README», «el grafo lo muestra». Se distingue **VERIFICADO** (ejecutado) de **INFERIDO** (deducido).
Un «no lo sé» vale más que un relleno.

---

## 0. Línea base (medida antes de auditar nada)

Esto es lo primero que la auditoría del 28 no tenía, y la razón de que aquel trabajo no era
concluyente.

| Comprobación | Resultado | Cómo se midió |
|---|---|---|
| `.venv/` del proyecto | **VACÍO**, sin intérprete | `find .venv -maxdepth 2` |
| `psycopg2`, `arch` | **No instalados** (imports duros del código) | `python3 -c "import ..."` |
| Suite completa | **162 collected · 161 pasan · 1 falla** | `pytest tests/ -q` |
| Test rojo | `test_spectral_cycle_detection` → recibe `None` | ejecución aislada |
| Deps resueltas | `arch 8.0.0` + `psycopg2` en `/tmp/qmp-libs` | `pip3 install --target` (PEP 668 bloquea el sistema) |
| Credenciales | `BYBIT_API_KEY` y `BYBIT_API_SECRET` **VACÍAS**; `BYBIT_TESTNET=true` | lectura de `.env` (ignorado por git ✓) |
| Grafo | **2840 nodos, 5100 edges, STALE=no** | `graphify update` + test de desfase |

**El CLI arranca** (`import quant_math.cli.main` OK), pero **la puerta que documenta el README no
funciona**: es un TUI `questionary` (`quant_math/cli/main.py:1839`) que sin terminal muere con
`PermissionError` y no entiende `--help`. **La puerta real es `quant_math_bg.py`** (el TUI solo le
hace `Popen`, `main.py:323`).

---

## 1. QUÉ ES Y QUÉ HACE

Sistema de research cuantitativo autónomo en Python. Lee velas de **Bybit**, genera hipótesis
matemáticas, las backtestea, elige la mejor por un criterio de *expectancy*, y opera en **paper**
sobre un ledger propio. Un lazo de aprendizaje no supervisado (SIS/KMeans) debería realimentar las
prioridades de generación.

Flujo real (los 6 pasos verificados con `fichero:línea`):

```
Bybit OHLCV → AQDE Runner (plantillas + ARIMA/GARCH + mutaciones)   aqde_runner.py
            → Orchestrator publica en Knowledge Base JSONL          orchestrator.py
            → Decision Engine (ranking expectancy DESC + gate)      decision_engine/main.py
            → Ledger paper (paper_executions.jsonl)                 orchestrator.py
            → SIS / KMeans realimenta prioridades                   ml/regime_learning.py
```

---

## 2. QUÉ FUNCIONA ✅

| # | Qué | Evidencia |
|---|---|---|
| 1 | **El sistema corre end-to-end** | KB +6 líneas, ledger +5, positions +5, última fila parseable, 84 líneas de traza con timestamps por etapa |
| 2 | **No hay look-ahead en el SIS** | generación en `orchestrator.py:341` ANTES que cierres en `:993`. Orden temporal correcto |
| 3 | **TP/SL ratio 2:1 exacto** | `decision_engine/main.py:333`; medido en 5 TP distintos: `0,02→0,01` |
| 4 | **Sizing determinista y correcto** | classic 100×0,05×3=**15,00**; burst 10×20=**200,00**; vol-target ×2,0=**20,0**. Cuadra en 4/4 |
| 5 | **`.env` no está en git** | `.gitignore:19` |
| 6 | **El backtester opera en activos >10.000 USD** | BTC sí (29-37 trades), ETH no — el adapter emite `quantity:1` y el backtester exige margen |

---

## 3. QUÉ NO FUNCIONA ❌

### 3.1 EL HALLAZGO CENTRAL: el expectancy está mal calculado

Cadena verificada línea por línea:

- `quant_math/orchestrator.py:560` → `expectancy = total_return_pct / n_trades`
- `backtesting/backtester.py:861` → `final_capital = equity_curve[-1]`
- `equity_curve` **solo** se actualiza en `:816` y `:819`
- Los trades cerrados al final (`:823-858`) **nunca añaden su PnL al equity_curve**. El comentario en
  `:822` lo confiesa: *"record only — legacy behaviour keeps equity_curve cash-only"*

**Consecuencia: `total_return_pct` asume que el margen retenido se evaporó, y ese retorno destruido
se divide entre todos los trades.** Prueba de F3 con `ema_crossover`:

| Velas | Retorno reportado |
|---|---|
| 479 | **+1,3526%** |
| 300 (178 menos) | **−40,3567%** |

Un cambio de 178 velas mueve el retorno 41,7 pp. `ati_trend` con **1 trade, 100% aciertos, +1.868,63**
reporta **−40,4840%**.

> **Origen:** commit `580a4595` lo introdujo como decisión deliberada de compatibilidad «legacy». No
> es un descuido: es un compromiso que rompe el supuesto matemático aguas abajo. Agravante: los
> trades no cerrados **sí** entran en `n_trades` y en `win_rate` (población inconsistente entre
> métricas).

### 3.2 La puerta de `expectancy>0` está DESACTIVADA

```
quant_math/decision_engine/main.py:42   os.environ.get("QUANTMATH_LEARN_MODE","0")=="1"   # motor: APAGADO
quant_math_bg.py:119                     os.environ.setdefault("QUANTMATH_LEARN_MODE","1") # launcher: ENCENDIDO
quant_math/cli/main.py:307               os.environ.setdefault("QUANTMATH_LEARN_MODE","1") # launcher: ENCENDIDO
```

**Por la puerta real, el gate está apagado.** El sistema abre operaciones que su propio diseño
prohíbe. Confirmado en el log del proceso, no deducido.

### 3.3 La señal es ruido (fuera de muestra)

ETH 1h Bybit · 12.960 velas · corte 70/30 sin solape · 13 estrategias:

| Conjunto | n | expectancy | winrate |
|---|---|---|---|
| Train | 1630 | +0,4041% | 34,87% |
| **Test** | **814** | **−0,1914%** | 39,68% |

- Solo sobrevive OOS `mean_reversion` (**4/4**). `momentum`/`breakout` (**0/9**).
- **El ranking en train es anti-informativo**: las 3 mejores en train son las peores fuera.
  Ejemplo: `range_pressure` +4,85% train → −0,42% test.
- ⚠️ El +0,4041% **cambia de signo** al pasar de 10k a 100k de capital y no se investigó. **No
  debe tomarse como edge.** El único dato robusto es el **signo negativo** del test.

### 3.4 El aprendizaje nunca ha existido

24 filas acumuladas vs `MIN_ROWS=30` → `mode=collecting` para siempre. **0 fit, 0 `mode=active`,
0 cierres reales.** El lazo de aprendizaje es decorativo: nunca se ha ejecutado.

### 3.5 La suite de tests NO protege el dinero (medido por mutación)

| Mutación | Resultado de la suite | Lectura |
|---|---|---|
| **Corregir** el bug 3.1 (que `final_capital` incluya el PnL final) | **ROMPE** un test → `test_clusters_and_recommendation`: "sin clusters" | El test **codifica el bug** como comportamiento correcto |
| **Invertir el signo** del expectancy (ordenar al revés la puerta) | **Idéntica**: 2 failed, 160 passed | **Ningún test detecta el ranking invertido** |

- Al corregir la matemática, el expectancy pasa a negativo y el SIS deja de producir clusters
  (`cluster_stats == []`). **El "aprendizaje" que el sistema demuestra depende del bug.**
- Los tests comprueban el **signo** (`expectancy>0` → señal) pero **nunca el orden** del ranking.
- El test rojo (`test_spectral_cycle_detection`) recibe `None`; **no se ha dictaminado** si es
  expectativa irreal o código roto, ni si está en el camino de ejecución.

### 3.6 El guard de riesgo es ciego a las posiciones abiertas

`orchestrator.py:1007` → `equity = initial_capital + realized_total`, y `_ledger_pnl()` (`:665-685`)
solo itera registros con `"motivo_cierre"`. Con 5 posiciones abiertas en el SL:
**el guard ve 0,00% de drawdown y dice PERMITE.**

### 3.7 Sin tope de riesgo por operación en USD

`quant_math/risk/sizing.py:110` implementa el cálculo, con **0 referencias** desde la ruta de dinero
(solo `test_integration.py`). Igual que VaR, ES, Kelly y stress. Lo único que limita es un tope de
margen que **falla abierto** (`orchestrator.py:712-714`) y que, ejecutado, aprueba **200 USD de
nocional sobre una cuenta de 50**.

### 3.8 La matemática del riesgo está al límite

`R:R = 0,5` (`SL = tp_pct/2`) → **break-even = 33,33%** (riesgo 0,01 / premio 0,02).
WR medido 34,87% está **1,5 pp por encima**, pero el coste de **0,10 pp/trade** lo deja **por debajo**.
Además, con la config real del run burst (lev 20, nocional 20, margen 1, TP 20%, SL 10%): **el SL es
inalcanzable** — la liquidación llega 2,15–2,35× antes que el stop.

### 3.9 En mainnet no hay ruta de cierre

`orchestrator.py:810` hace `create_order` al abrir. Al cerrar solo se escribe una línea JSONL: el
TP/SL es **un fichero, no una orden condicional en el exchange**. No hay `reduceOnly`. **Las
posiciones quedarían huérfanas en Bybit.**

---

## 4. QUÉ NO SE HA MEDIDO ⚠️

| Hueco | Por qué |
|---|---|
| **Nada con dinero real** | `BLOCKED-KEY`: `.env` sin claves. Solo paper con datos públicos |
| **Walk-forward** | Un solo corte 70/30, un solo símbolo (ETH 1h), un solo régimen |
| **MMR vigentes de Bybit** | 0,35/0,50/0,75% es barrido propio, no lectura de API |
| **Causalidad del run de 41 posiciones** | El guard aislado funciona; que parara aquel run es **INFERIDO**, no probado |
| **Test rojo dictaminado** | No se supo si es expectativa irreal o código roto |
| **Fallo de `trades=0` en ETH** | Causa identificada (margen) pero no verificada de extremo a extremo |
| **WebUI** | Fuera de alcance por decisión de Leonardo |
| **F2 (integridad de datos)** | No se ejecutó como fase propia: cubierta dentro de F3 |

---

## 5. CORRECCIONES ORDENADAS POR RIESGO DE DINERO

> **NO SE ARREGLA NADA HASTA APROBACIÓN DE LEONARDO.** El repo está intacto: las mutaciones se
> hicieron en copias en `/tmp` y se borraron. `git status` idéntico antes y después.

| # | Riesgo | Evidencia | Dónde |
|---|---|---|---|
| **1** | **El expectancy está contaminado** → toda decisión de entrada rests sobre un número falso | `backtester.py:861` + `:822` | `ops/AUDITORIA-CONTEXTO-2026-09-29.md` §3.1 |
| **2** | **La puerta `expectancy>0` está apagada** en producción | `quant_math_bg.py:119` | §3.2 |
| **3** | **Señal con signo negativo fuera de muestra**, y el ranking en train es anti-informativo | n=814, −0,1914% | §3.3 |
| **4** | **En mainnet no hay cierre**: posiciones huérfanas en el exchange | `orchestrator.py:810` | §3.9 |
| **5** | **El guard no ve las posiciones abiertas**: 0% drawdown con 5 en SL | `orchestrator.py:1007` | §3.6 |
| **6** | **La suite no detecta el ranking invertido** | mutación de signo, suite idéntica | §3.5 |
| **7** | **Un test codifica el bug como correcto** | mutación de corrección rompe `test_operation_learning` | §3.5 |
| **8** | **Sin tope de riesgo por operación en USD**; el de margen falla abierto | `sizing.py:110`, 0 refs | §3.7 |
| **9** | **El SL de burst es inalcanzable** (liquidación 2,15–2,35× antes) | config medida de `runtime/state_burst` | §3.8 |
| **10** | **El slippage invierte el signo**: train +0,0461% → −0,0039% | F3 §D | §3.3 |
| **11** | **El SIS nunca se ha activado** (24 filas vs `MIN_ROWS=30`) | `ml/regime_learning.py:68-71` | §3.4 |
| **12** | **El backtester no opera en ETH** (`quantity:1` vs margen exigido) | BTC sí, ETH no | §2 |

### Orden de arreglo recomendado

1. **Arreglar el expectancy (#1)** y **encender la puerta (#2)** — sin esto, todo lo demás se mide sobre
   arena. Aviso: arreglar #1 **rompe un test** (#7) que hay que corregir de verdad, no silenciar.
2. **Cerrar el gap de #4 y #5** antes de cualquier/mainnet, aunque sea por descarte.
3. Solo después, límites (#8), R:R (#9) y tests que protejan la puerta (#6).
4. **El edge (#3) no es un bug: es una señal que no existe.** Aunque todo lo anterior se arregle,
   esto es lo que decide si el proyecto tiene futuro.

---

## 6. Veredicto

**El sistema es real, corre, y está bien estructurado.** El pipeline existe de punta a punta, la
traza es trazable, el SIS está bien ordenado y el sizing cuadra. Eso no es poco.

**Pero la puerta que decide qué se opera se apoya sobre una métrica mal calculada, y la puerta que
debería impedir operar está apagada.** Los dos fallos se compensan en apariencia: el expectancy
 sale inflado y el gate no lo vigila. El resultado es que el sistema **abre operaciones que su propio
diseño prohíbe, ordenadas por un número que cambia de signo con 178 velas.**

**NO APTO para dinero real.** No por falta de evidencia: la evidencia es concluyente en contra.
Además, **aunque los 12 hallazgos se arreglaran hoy, el edge sigue sin existir** (#3): la señal es
ruido fuera de muestra con muestra suficiente.

## 7. Ficheros de esta auditoría

| Fichero | Contenido |
|---|---|
| `ops/AUDITORIA-CONTEXTO/01-mapa-funcional.md` | Flujo real, 3 puntos de dinero, entrypoint probado |
| `ops/AUDITORIA-CONTEXTO/03-ejecucion-oos.md` | Ejecución end-to-end, OOS, leakage, coste del slippage |
| `ops/AUDITORIA-CONTEXTO/04-riesgo-dinero.md` | 12 riesgos ordenados, matemática del riesgo, escenario mainnet |
| `Kaenor/ops/bitacora/D2.md`, `D4.md` | Qué cambió, por qué, y **qué NO se verificó** |

**Autores:** `kaenor-software-architect` (F1) · `kaenor-quant-researcher` (F3) ·
`kaenor-risk-analyst` (F4) · Orquestador (línea base, F5/mutación, consolidación) ·
`kaenor-reality-checker` (veto) · `kaenor-product-manager` (diseño del plan).
