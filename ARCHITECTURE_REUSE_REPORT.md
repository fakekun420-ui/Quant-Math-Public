# Quant-Math Architecture Reuse Analysis Report

> ✅ **RE-VERIFICADO 2026-08-24 (v1.0.1): el hallazgo central SIGUE VIGENTE** —
> `webui/backend/webui/api/routes.py` continúa sirviendo datos mock sin
> importar `quant_math`. La integración real hoy ocurre vía la CLI
> (`quant_math/cli/main.py`) sobre el orchestrator; el WebUI permanece como
> interfaz secundaria pendiente de conectar. Análisis original abajo.

---

# Quant-Math Architecture Reuse Analysis Report

## Executive Summary

**Finding: The WebUI backend is NOT reusing existing quant-math modules.** The backend API routes (`webui/backend/webui/api/routes.py`) return mock/hardcoded data instead of connecting to the mature quant-math library. The `QuantMathAdapter` in `quant_math/autonomous_research/adapters/quant_math_adapter.py` exists and properly wraps quant-math components but is **not integrated** into the WebUI backend.

---

## Existing Quant-Math Modules (Ready for Reuse)

### 1. Backtesting Engine (`backtesting/backtester.py`)
| Component | Capabilities |
|-----------|-------------|
| `Backtester` | Run backtests with custom strategies, commission/slippage modeling, trade pairing, equity curves |
| `WalkForwardValidator` | Anchored/rolling walk-forward validation, parameter optimization, robustness scoring, parameter stability |
| `PerformanceMetrics` | Sharpe, Sortino, max drawdown, win rate, profit factor, total return |

### 2. Data Acquisition (`data_acquisition/data_sources/exchanges.py`)
| Component | Capabilities |
|-----------|-------------|
| `ExchangeAPI` | CCXT wrapper for Binance/Bybit/Coinbase/Kraken, OHLCV fetching, order book, ticker, balance, symbols |

### 3. Risk Management (`quant_math/risk/`)
| Module | Capabilities |
|--------|-------------|
| `kelly.py` | Kelly criterion position sizing |
| `position_sizing.py` | Fixed fractional, volatility-targeted, risk-based sizing |
| `stop_loss.py` | Fixed, ATR, trailing, percentage stops |
| `risk_manager.py` | Portfolio risk limits, drawdown controls |
| `var.py` | Value-at-Risk calculations |

### 4. Statistical Analysis (`quant_math/expectation/`)
| Module | Capabilities |
|--------|-------------|
| `statistical_tests.py` | Hypothesis testing, significance |
| `sharpe_metrics.py` | Sharpe/Sortino/Calmar ratios |
| `drawdown_analyzer.py` | Drawdown decomposition, recovery analysis |
| `return_calculator.py` | Return calculations |

### 5. Monte Carlo (`quant_math/monte_carlo/simulator.py`)
| Component | Capabilities |
|-----------|-------------|
| `MonteCarloSimulator` | Bootstrap resampling, parameter uncertainty, distribution analysis |

### 6. Autonomous Research (`quant_math/autonomous_research/`)
| Component | Capabilities |
|-----------|-------------|
| `QuantMathAdapter` | **Full adapter implementing AQDE ports**: DataProvider, KnowledgeBase, BacktestEngine, MonteCarloEngine, StatisticalValidator, RiskManager |
| `HypothesisKnowledgeBase` | Persistent hypothesis storage, search, similarity, timeline, export/import |
| `research_manager.py` | Autonomous research orchestration |
| `interfaces.py` | Formal port definitions (DataProvider, KnowledgeBase, BacktestEngine, etc.) |

---

## WebUI Backend Current State (NOT Reusing)

### `webui/backend/webui/api/routes.py` - Mock Endpoints

| Endpoint | Current Implementation | Should Use |
|----------|----------------------|------------|
| `GET /dashboard/health` | Hardcoded CPU/memory/disk | System metrics or health check |
| `GET /dashboard/aqde` | Returns `is_running: False` hardcoded | `QuantMathAdapter` + research_manager state |
| `GET /dashboard/trading` | Returns zero metrics | `ExchangeAPI` + paper trading engine |
| `GET /dashboard/hypotheses` | Returns `[]` | `HypothesisKnowledgeBase.search_hypotheses()` |
| `GET /dashboard/events` | Returns `{"events": []}` | Event store / WebSocket broadcasts |
| `GET /config/values` | Returns hardcoded defaults | Config file / database |
| `POST /config/values` | Returns `{"success": True}` | Persist to config |
| `GET /backtest/hypotheses` | Returns 3 mock hypotheses | `HypothesisKnowledgeBase` |
| `POST /backtest/run` | `asyncio.sleep(2)` + mock results | **`QuantMathAdapter.run_backtest()`** |
| `GET /autonomous/status` | Returns idle hardcoded | Research manager state |
| `POST /autonomous/start` | Returns success mock | **Research manager + QuantMathAdapter** |
| `GET /monitoring/*` | All return empty/mock | Real monitoring from research manager |
| `GET /trading/status` | Returns disabled hardcoded | ExchangeAPI + OrderManager |
| `POST /trading/enable` | Returns success mock | Validate keys, enable OrderManager |

---

## Frontend Stores (Correctly Designed for Real Backend)

The frontend Pinia stores in `webui/frontend/src/stores/` are well-designed and **would work correctly** once the backend is connected:

- `dashboard.js` - WebSocket + REST polling for real-time data
- `autonomous.js` - Full AQDE lifecycle management via WebSocket events
- `backtest.js` - Hypothesis selection + backtest execution
- `config.js` - Full config sections with validation
- `trading.js` - Real trading enable/disable, positions, risk limits
- `monitoring.js` - Pipeline monitoring across stages

---

## Integration Gap Analysis

### Missing Connections

```
┌─────────────────────────────────────────────────────────────────┐
│                        WEBUI BACKEND                            │
│  routes.py  ──►  MOCK DATA  (❌ NOT USING QUANT-MATH MODULES)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (SHOULD BE)
┌─────────────────────────────────────────────────────────────────┐
│                     QUANT-MATH ADAPTER                          │
│  QuantMathAdapter  ──►  Implements ALL AQDE Ports              │
│       │                                                        │
│       ├── DataProvider       ──► ExchangeAPI (CCXT)            │
│       ├── KnowledgeBase      ──► HypothesisKnowledgeBase       │
│       ├── BacktestEngine     ──► Backtester + WalkForward      │
│       ├── MonteCarloEngine   ──► MonteCarloSimulator           │
│       ├── StatisticalValidator ──► PerformanceMetrics          │
│       └── RiskManager        ──► risk/* modules                │
└─────────────────────────────────────────────────────────────────┘
```

### Required Changes

1. **Initialize `QuantMathAdapter` in `main.py` lifespan**
2. **Inject adapter into routes** via dependency injection
3. **Replace all mock returns** with actual adapter calls
4. **Connect WebSocket broadcasts** to research manager events
5. **Persist config** to file/database instead of hardcoded returns

---

## Recommended Integration Pattern

```python
# webui/main.py - Add to lifespan
from quant_math.autonomous_research.adapters.quant_math_adapter import QuantMathAdapter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize adapter with config
    adapter = QuantMathAdapter(
        exchange_id=settings.EXCHANGE_ID,
        knowledge_base_path=settings.KNOWLEDGE_BASE_PATH
    )
    app.state.adapter = adapter
    yield

# webui/api/routes.py - Use adapter
@router.post("/backtest/run")
async def run_backtest(request: BacktestRequest, adapter: QuantMathAdapter = Depends(get_adapter)):
    # Fetch real market data
    data = adapter.fetch_market_data(
        symbol=request.symbol,
        start_date=parse(request.start_date),
        end_date=parse(request.end_date),
        timeframe=request.timeframe
    )
    
    # Get hypothesis from knowledge base
    hypothesis = adapter.retrieve_hypothesis(request.hypothesis_id)
    
    # Run REAL backtest using quant-math engine
    result = adapter.run_backtest(hypothesis, data, request.initial_capital)
    
    return BacktestResponse(success=True, results=serialize(result))
```

---

## Conclusion

**The quant-math library is production-ready and comprehensive.** The WebUI frontend is well-architected. The **only missing piece** is connecting the backend routes to the `QuantMathAdapter` which already implements all required AQDE ports by wrapping the existing quant-math modules.

**Estimated effort to complete integration:** ~2-4 hours (replace mock endpoints with adapter calls, add dependency injection, connect WebSocket events).