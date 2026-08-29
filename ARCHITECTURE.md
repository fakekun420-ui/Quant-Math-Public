# QUANT-MATH Architecture — v1.4.0

> Fuente de verdad del pipeline en ejecución. El detalle histórico por
> módulo vive en `ARCHITECTURE_GUIDE.md`; el estado de implementación en
> `IMPLEMENTATION_STATUS.md`.

## Pipeline en ejecución

```
Bybit (OHLCV real, CCXT)
   │
   ▼
AQDERunner ──────────┐
│  · plantillas base │  model_based_generator.py
│  · mutaciones GA   │  ARIMA(1,1,0) + GARCH(1,1)
│  · rotación cíclica│  → candidatos ejecutables con contexto _regime
│  · cache intra-    │
│    ciclo OHLCV     │
└──┬─────────────────┘
   ▼
Orchestrator.run_cycle()
│  · dedupe por firma (refresh cada QUANTMATH_SIG_REFRESH_CYCLES=5)
│  · publish → Knowledge Base
│      JSONL con atomic upsert (sin dependencias externas)
│        ⇄ índice en memoria para búsqueda rápida
│  · HypothesisPrior (supervisado, advisory)
│  · SIS OperationLearningLoop (no supervisado, advisory)
│  · ráfagas de exploración por racha de pérdidas
▼
DecisionEngine.decide(symbol)
│  · select_best: expectancy DESC, score DESC
│  · LEARN_MODE puede bypassar el gate (solo paper)
│  · _check_exits(): SL = TP/2 (ratio 2:1 fijo), precio REAL por ciclo
▼
paper_executions.jsonl ── libro permanente append-only
│  cierres: motivo tp/sl/manual + pnl, pnl_pct, entry/exit_time
▼
Feedback
│  · por key: min_paper_trades=3 (contrato original intacto)
│  · por FAMILIA×SYMBOL: entrega en cada múltiplo del umbral
│    (feedback_family_ops/wins/mean_pnl_pct → registros del KB)
└──► AQDE mutations / prior / SIS (ciclo siguiente)
```

## Componentes

| Componente | Ubicación | Rol |
|---|---|---|
| CLI | `quant_math/cli/main.py` | Menú/wizard/monitor/historial; autoarranque VM PG; LEARN_MODE |
| Orchestrator | `quant_math/orchestrator.py` | Ciclos, dedupe+refresh, publicación KB, stats |
| Decision Engine | `quant_math/decision_engine/main.py` | Gate, TP/SL, posiciones, feedback key+familia |
| Knowledge Base | `quant_math/autonomous_research/adapters/postgres_kb.py` | JSONL con atomic upsert, índice en memoria, search by status/symbol/combined |
| Prior supervisado | `quant_math/ml/hypothesis_prior.py` | P(expectancy>0 \| tipo,símbolo) con shrinkage |
| SIS no supervisado | `quant_math/ml/regime_learning.py` | KMeans + tablas régimen×familia + rachas |
| Feature store | `quant_math/ml/feature_store.py` | Ledger↔KB→dataset con cutoff integración |
| Model generator | `model_based_generator.py` | ARIMA/GARCH → candidatos con `_regime` |
| Reset base | `tools/reset_learning_base.py` | Archiva KB, fija cutoff, limpia fantasmas |

## Garantías invariantes

1. **Gate**: ninguna capa ML abre operaciones; entry exige el expectancy del
   backtest real de cada hipótesis (bypass temporal solo vía LEARN_MODE).
2. **Datos**: 100% Bybit real. La ruta sintética es inalcanzable desde la CLI.
3. **Libro permanente**: append-only, nunca truncado; los resets archivan.
4. **Fallbacks**: cualquier fallo de infraestructura degrada a JSONL/skip,
   jamás detiene el sistema sin log explícito.
5. **Data-starvation safe**: todo aprendiz entra en modo *collecting* bajo su
   umbral mínimo de muestras.

## Ver más

- `README.md` — quickstart, flags de entorno, estructura real
- `IMPLEMENTATION_STATUS.md` — qué existe y qué está propuesto
- `ARCHITECTURE_GUIDE.md` — guía histórica profunda por módulo (v0.x)
