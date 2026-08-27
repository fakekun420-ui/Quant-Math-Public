# Graph Report - Quant-Math-Public  (2026-08-27)

## Corpus Check
- 209 files · ~134,232 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3100 nodes · 4923 edges · 172 communities (163 shown, 9 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 151 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Risk Management
- Backtesting & Data
- Knowledge Base
- Core Protocols
- Backtester Engine
- Backtest Protocols
- Algo Trading System
- ML Feature Store
- Regime Detection
- Web Frontend
- Execution Engine
- Risk Adapters
- VaR & Risk Models
- Database Storage
- Volatility Clustering
- ML Quant Features
- WebUI Backend
- Order Management
- Research Interfaces
- Statistical Models
- Paper Trading
- Cycle Orchestration
- Data Sources
- Model Generator
- Test Suite
- Burst Scalping
- SIS Learning
- Decision Engine
- State Management
- Monitor Dashboard
- Portfolio Optimizer
- Arbitrage Engine
- Walk-Forward Validation
- Event System
- Signal Processing
- CLI Interface
- Market Microstructure
- Network Analysis
- Optimization Engine
- Backtest Runner
- Trading Strategies
- ML Training Pipeline
- Data Normalizer
- Pattern Recognition
- Portfolio Metrics
- Adaptive System
- Historical Data
- Exchange Adapter
- Performance Analytics
- Strategy Optimizer
- Module 50
- Module 51
- Module 52
- Module 53
- Module 54
- Module 55
- Module 56
- Module 57
- Module 58
- Module 59
- Module 60
- Module 61
- Module 62
- Module 63
- Module 64
- Module 65
- Module 66
- Module 67
- Module 68
- Module 69
- Module 70
- Module 71
- Module 72
- Module 73
- Module 74
- Module 75
- Module 76
- Module 77
- Module 78
- Module 79
- Module 80
- Module 81
- Module 82
- Module 83
- Module 84
- Module 85
- Module 86
- Module 87
- Module 88
- Module 89
- Module 90
- Module 91
- Module 92
- Module 93
- Module 94
- Module 95
- Module 96
- Module 97
- Module 98
- Module 99
- Module 100
- Module 101
- Module 102
- Module 103
- Module 104
- Module 105
- Module 106
- Module 107
- Module 108
- Module 109
- Module 110
- Module 111
- Module 112
- Module 113
- Module 114
- Module 115
- Module 116
- Module 117
- Module 118
- Module 119
- Module 120
- Module 121
- Module 122
- Module 123
- Module 124
- Module 125
- Module 126
- Module 127
- Module 128
- Module 129
- Module 130
- Module 131
- Module 132
- Module 133
- Module 134
- Module 135
- Module 136
- Module 137
- Module 139
- Module 141
- Module 142
- Module 143
- Module 144
- Module 145
- Module 146
- Module 147
- Module 148
- Module 149
- Module 150
- Module 151
- Module 152
- Module 153
- Module 154
- Module 163
- Module 164

## God Nodes (most connected - your core abstractions)
1. `DecisionEngine` - 65 edges
2. `QuantMathAdapter` - 51 edges
3. `run_full_e2e_test()` - 39 edges
4. `RuntimeState` - 38 edges
5. `AQDERunner` - 36 edges
6. `OrchestratorConfig` - 32 edges
7. `OrderManager` - 31 edges
8. `Orchestrator` - 30 edges
9. `JSONLKnowledgeBase` - 28 edges
10. `BurstStateTracker` - 27 edges

## Surprising Connections (you probably didn't know these)
- `AlgoExecution` --uses--> `ExecutionReport`  [INFERRED]
  algo_trading/algo_trading.py → order_management/order_management.py
- `VWAP` --uses--> `Order`  [INFERRED]
  algo_trading/algo_trading.py → order_management/order_management.py
- `POV` --uses--> `Order`  [INFERRED]
  algo_trading/algo_trading.py → order_management/order_management.py
- `AQDERunner` --uses--> `ExchangeAPI`  [INFERRED]
  aqde_runner.py → data_acquisition/data_sources/exchanges.py
- `Orchestrator` --uses--> `AQDERunner`  [INFERRED]
  quant_math/orchestrator.py → aqde_runner.py

## Import Cycles
- None detected.

## Communities (172 total, 9 thin omitted)

### Community 0 - "Risk Management"
Cohesion: 0.04
Nodes (55): Risk Management Module This module provides comprehensive risk measurement and…, example_expected_shortfall(), example_portfolio_risk(), example_risk_budgeting(), example_stress_testing(), example_var_calculation(), main(), Example: Portfolio risk analysis. (+47 more)

### Community 1 - "Backtesting & Data"
Cohesion: 0.04
Nodes (60): Walk-Forward Validation Engine Implements walk-forward analysis for robust…, WalkForwardValidator, DataStore(), Factory: returns the SQLite-backed store when called with db_path, otherwise…, DataCleaner, Data Cleaning Module Handles missing values, outliers, and structural breaks, Data cleaning utilities for time series data, Normalizer (+52 more)

### Community 2 - "Knowledge Base"
Cohesion: 0.05
Nodes (39): JSONLKnowledgeBase, KBPersistence, Any, JSONL-backed Knowledge Base with atomic upsert and indexed search. Drop-in…, Atomic upsert: load → merge → save., Load all records (uses cache if available)., Atomic update: load → merge → save., Atomic delete: load → remove → save. (+31 more)

### Community 3 - "Core Protocols"
Cohesion: 0.07
Nodes (43): Quant-Math Core Package Shared domain types and protocols for the Quant-Math…, Auditor, BacktestEngine, DataProvider, MonteCarloEngine, Protocol, Quant-Math Core Protocols Hexagonal architecture ports that separate the domain…, Port for statistical validation of hypotheses. Adapters implement this to… (+35 more)

### Community 4 - "Backtester Engine"
Cohesion: 0.06
Nodes (34): BacktestResult, PerformanceMetrics, ndarray, Backtesting & Evaluation Module This module provides backtesting and…, Run walk-forward validation. Parameters ---------- strategy_func : callable…, Represents a single trade., Grid search optimization on training data., Run backtest with specific parameters. (+26 more)

### Community 5 - "Backtest Protocols"
Cohesion: 0.04
Nodes (29): KnowledgeBase, Any, datetime, Hypothesis, Search hypotheses using text matching, Find similar hypotheses using semantic search, Update an existing hypothesis, Get statistics about stored hypotheses (+21 more)

### Community 6 - "Algo Trading System"
Cohesion: 0.07
Nodes (34): AlgoExecution, AlgoTradingSystem, POV, Order, Algorithmic Trading System This module provides algorithmic trading…, Volume-Weighted Average Price (VWAP) Splits order based on expected market…, Initialize VWAP algorithm. Two modes: Order-based (legacy): execution_time :…, Execute using VWAP. Order-based mode: execute(order, order_manager,… (+26 more)

### Community 7 - "ML Feature Store"
Cohesion: 0.07
Nodes (36): build_trade_dataset(), encode_dataset(), encode_row(), Any, Feature store del aprendizaje no supervisado. Une el libro permanente de…, Una fila por cierre post-cutoff, enriquecida con KB + _regime., Vector fijo para clustering; None -> -1., read_closures() (+28 more)

### Community 8 - "Regime Detection"
Cohesion: 0.06
Nodes (32): Regime Detection Module This module provides tools for detecting and analyzing…, example_clustering(), example_hmm(), main(), Example: Hidden Markov Model regime detection., Example: Regime clustering., HiddenMarkovModel, ndarray (+24 more)

### Community 9 - "Web Frontend"
Cohesion: 0.05
Nodes (43): axios, chart.js, chartjs-adapter-date-fns, d3, date-fns, eslint, eslint-config-prettier, eslint-plugin-prettier (+35 more)

### Community 10 - "Execution Engine"
Cohesion: 0.07
Nodes (30): Backtester, Backtesting Engine Executes strategy backtests and calculates performance…, Initialize backtester. Parameters ---------- initial_capital : float Initial…, Order, OrderType, Enum, Initialize order. Parameters: ----------- symbol : str Trading symbol side :…, Validate order parameters. Returns: -------- bool True if valid (+22 more)

### Community 11 - "Risk Adapters"
Cohesion: 0.07
Nodes (24): Any, RiskManager, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Implementation of RiskManager port. Provides risk management functionality…, Check if drawdown is within acceptable limits. Args: hypothesis_id: Hypothesis…, Check if Sharpe ratio meets threshold. Args: sharpe_ratio: Sharpe ratio to…, Check if Sortino ratio meets threshold. Args: sortino_ratio: Sortino ratio to… (+16 more)

### Community 12 - "VaR & Risk Models"
Cohesion: 0.07
Nodes (25): Initialize the risk management engine. Args: max_position_size_pct: Maximum…, calculate_var(), expected_shortfall(), ExpectedShortfall, ndarray, Value at Risk (VaR) and Expected Shortfall (ES) Module Pure numpy…, Value at Risk calculator. VaR is the maximum expected loss over a given time…, Calculate VaR from return series. Args: returns: Array of returns confidence:… (+17 more)

### Community 13 - "Database Storage"
Cohesion: 0.06
Nodes (24): _PostgreSQLDataStore, Any, DataFrame, PostgreSQL Database Connector Provides data storage and retrieval with metadata…, Query data from database Args: query: SQL query string params: Query parameters…, Get schema information for a table Args: table: Table name Returns: List of…, Check data quality for a table Args: table: Table name columns: Specific…, Remove data older than specified threshold Args: table: Table name… (+16 more)

### Community 14 - "Volatility Clustering"
Cohesion: 0.07
Nodes (22): EWMAVolatility, GARCHModel, ndarray, Volatility Clustering Analysis This module provides methods to detect and…, Detect volatility clusters using rolling volatility. Parameters ----------…, Test for ARCH effects (autoregressive conditional heteroskedasticity). The…, Check if ARCH effects are present (indicating volatility clustering).…, Calculate the ratio of high volatility variance to low volatility variance.… (+14 more)

### Community 15 - "ML Quant Features"
Cohesion: 0.07
Nodes (24): FeatureEngineer, MLPortfolioOptimizer, MLPortfolioResult, ndarray, Machine Learning for Quant Module This module provides machine learning tools…, Add cross-asset features (e.g., spread, correlation). Parameters ----------…, Get feature importance from trained model. Parameters ---------- model : Any…, Machine Learning Portfolio Optimizer Uses ML-based constraints and risk models. (+16 more)

### Community 16 - "WebUI Backend"
Cohesion: 0.07
Nodes (26): AsyncSession, FastAPI, get_db(), init_db(), Database Module for WebUI Backend, Initialize database tables., Get database session., WebSocket (+18 more)

### Community 17 - "Order Management"
Cohesion: 0.10
Nodes (26): ExecutionReport, ExecutionStrategy, Order, OrderBook, Order Management Module This module provides order management and execution…, Helper to set last_price after execution., Create a new order. Parameters ---------- symbol : str Trading symbol side :…, Represents a trading order. (+18 more)

### Community 18 - "Research Interfaces"
Cohesion: 0.07
Nodes (23): Auditor, BacktestEngine, Any, Protocol, Port for statistical validation of hypotheses. Adapters implement this to…, Calculate win rate from trade history, Test statistical significance of strategy performance. Returns p-value or…, Calculate Sharpe ratio (+15 more)

### Community 19 - "Statistical Models"
Cohesion: 0.07
Nodes (25): ARCHModel, ARIMAModel, ARIMAResult, GARCHModel, Any, ndarray, Statistical Models for Probabilistic Forecasting This module provides time…, Generate probabilistic predictions with confidence intervals. Parameters… (+17 more)

### Community 20 - "Paper Trading"
Cohesion: 0.07
Nodes (22): AgentRegistry, Registry for managing specialized research agents. Maintains a registry of…, Clear all message history, Initialize the agent registry, Unregister an agent. Args: agent_id: ID of agent to unregister Returns: True if…, Any, Hypothesis, MonteCarloResult (+14 more)

### Community 21 - "Cycle Orchestration"
Cohesion: 0.08
Nodes (23): Risk Management Module Exports, kelly_fraction(), KellyCriterion, Kelly Criterion Module Kelly criterion position sizing for optimal bet sizing., Kelly criterion position sizing., Calculate full Kelly fraction. Parameters: ----------- win_rate : float Win…, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction. (+15 more)

### Community 22 - "Data Sources"
Cohesion: 0.10
Nodes (25): build_prior_from_kb(), HypothesisPrior, _norm_type(), Any, Hypothesis generation prior learned from historical backtest outcomes. Learns…, Shrunk estimate of P(expectancy>0); fully explainable formula., Reorder candidate templates by prior, preserving exploration slots. Returns…, Load every historical record (PG first, JSONL fallback) and fit. (+17 more)

### Community 23 - "Model Generator"
Cohesion: 0.11
Nodes (24): Agent Registry for managing specialized research agents. The registry maintains…, Enum, Research Manager - Main Orchestrator for AQDE. The Research Manager coordinates…, Phases of the research workflow, ResearchPhase, Autonomous Quant Discovery Engine (AQDE) A modular system for autonomous…, AgentMessage, MonteCarloEngine (+16 more)

### Community 24 - "Test Suite"
Cohesion: 0.07
Nodes (19): ExchangeAPI, get_available_exchanges(), Any, DataFrame, CCXT Exchange Integration Provides unified interface to multiple cryptocurrency…, Fetch order book data Args: symbol: Trading pair limit: Number of depth levels…, Fetch current ticker information Args: symbol: Trading pair Returns: Ticker…, Fetch recent trades Args: symbol: Trading pair limit: Number of recent trades… (+11 more)

### Community 25 - "Burst Scalping"
Cohesion: 0.09
Nodes (18): ElbowMethod, ndarray, Unsupervised Regime Clustering This module provides unsupervised learning…, Fit DBSCAN and predict labels. Parameters ---------- returns : np.ndarray…, Get cluster centroids (in original feature space). Returns ------- centroids :…, Get statistics for each cluster. Parameters ---------- returns : np.ndarray…, Unsupervised clustering of market regimes. This module uses K-Means and DBSCAN…, Calculate silhouette score for clustering quality. Parameters ----------… (+10 more)

### Community 26 - "SIS Learning"
Cohesion: 0.09
Nodes (12): Tracks background orchestrator processes (supports simultaneous classic+burst)., PostgreSQL eliminado — siempre retorna False., PostgreSQL VM eliminado — KB opera en modo JSONL puro., PostgreSQL VM eliminado — no hay nada que detener., Return list of modes with live processes., Detect orphan orchestrator processes from PID files., Stop a specific mode's orchestrator., Legacy: stop all processes. (+4 more)

### Community 27 - "Decision Engine"
Cohesion: 0.09
Nodes (18): ndarray, Feature Extraction for Regime Detection This module provides feature extraction…, Extract volume-based features., Extract price-based features., Extract volatility-based features., Extract features for market regime detection. Features are based on statistical…, Extract autocorrelation features., Extract higher moments of returns distribution. (+10 more)

### Community 28 - "State Management"
Cohesion: 0.07
Nodes (18): PositionSizer, Calculate position size based on portfolio value and risk per trade.…, Calculate fixed fractional position size. Parameters: -----------…, Position sizing calculator based on risk management., Calculate Kelly fraction. Parameters: ----------- win_rate : float Win rate…, Calculate optimal stop loss distance. Parameters: ----------- entry_price :…, Calculate stop loss as percentage of entry price., Calculate stop loss price. (+10 more)

### Community 29 - "Monitor Dashboard"
Cohesion: 0.09
Nodes (14): main(), _orchestrator_process_main(), Child process: run the orchestrator loop with all output to quant_math.log., Orchestrator, Continuous generation -> decision -> feedback loop., Generate N hypotheses across configured symbols and backtest them., Generate + backtest hypotheses for a single symbol (thread-safe)., Convert an AQDE backtest result into a KB JSONL record. (+6 more)

### Community 30 - "Portfolio Optimizer"
Cohesion: 0.09
Nodes (17): Any, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Check if drawdown is within acceptable limits. Args: hypothesis_id: Hypothesis…, Unified Risk Manager implementing the RiskManager protocol. Consolidates…, Check if Sharpe ratio meets threshold. Args: sharpe_ratio: Sharpe ratio to…, Check if Sortino ratio meets threshold. Args: sortino_ratio: Sortino ratio to…, Check if Calmar ratio meets threshold. Args: calmar_ratio: Calmar ratio to… (+9 more)

### Community 31 - "Arbitrage Engine"
Cohesion: 0.08
Nodes (16): AdaptiveSizer, Calculate adaptive position size. Supports two modes: Risk-based mode (keyword…, Calculate position size based on recent trade performance. Parameters:…, Adaptive position sizing based on market conditions., Calculate position size based on market regime. Parameters: ----------- regime…, KellyCriterion, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction. (+8 more)

### Community 32 - "Walk-Forward Validation"
Cohesion: 0.10
Nodes (15): AQDERunner, main(), Run Monte Carlo simulations for hypotheses, Prune unbounded data structures to prevent memory growth., Analyze performance of hypotheses for a symbol, Save iteration results to file, Fuerza re-descarga en el siguiente acceso (inicio de ciclo nuevo)., Datos de mercado para backtesting con cache intra-ciclo: si (symbol, timeframe,… (+7 more)

### Community 33 - "Event System"
Cohesion: 0.08
Nodes (17): ndarray, Statistical Tests for Market Regime Detection This module provides statistical…, Runs test for random sequence analysis. The runs test checks whether a sequence…, Perform runs test on return series. Parameters ---------- returns : np.ndarray…, Z-score based regime detection. The Z-score measures how many standard…, Check if the test result is statistically significant., Variance ratio test for mean reversion. The variance ratio test compares the…, Perform variance ratio test. Parameters ---------- returns : np.ndarray Daily… (+9 more)

### Community 34 - "Signal Processing"
Cohesion: 0.12
Nodes (18): Principal Component Analysis (PCA) This module provides tools for…, compute_pca(), pca_denoising(), PCAAnalyzer, PCAResult, ndarray, PCA Analysis Module Provides Principal Component Analysis implementation for…, Transform data to PCA space. Parameters ---------- X : np.ndarray Data to… (+10 more)

### Community 35 - "CLI Interface"
Cohesion: 0.09
Nodes (21): Drawdown Analyzer Module Calculates drawdown metrics for risk assessment., Expectation Calculation Module (Module 8) Statistical significance testing and…, Return Calculator Module Calculates various return metrics for trading…, Sharpe Metrics Module Calculates Sharpe, Sortino, Calmar and other risk-…, bootstrap_confidence_interval(), bootstrap_p_value(), jarque_bera_test(), one_sample_ttest() (+13 more)

### Community 36 - "Market Microstructure"
Cohesion: 0.08
Nodes (23): aqde, aqdePhaseClass, aqdeStatusClass, calculateProgress(), currentPhase, evaluationProgress, evolutionProgress, evolvedCount (+15 more)

### Community 37 - "Network Analysis"
Cohesion: 0.09
Nodes (21): aqde, aqdePhaseClass, aqdeProgress, aqdeStatusClass, events, health, hypotheses, pipelineStages (+13 more)

### Community 38 - "Optimization Engine"
Cohesion: 0.10
Nodes (13): ndarray, Compute the entire efficient frontier. Parameters ---------- n_points : int…, Find portfolio with maximum Sharpe ratio. Returns ------- weights : np.ndarray…, Find portfolio with minimum variance. Returns ------- weights : np.ndarray…, Initialize Black-Litterman model. Two modes: Legacy mode: expected_returns :…, Optimize portfolio with views. Legacy mode: views is a dict {asset_index:…, Initialize risk parity optimizer. Parameters ---------- returns : np.ndarray…, Optimize risk parity portfolio. Parameters ---------- target_risk : float,… (+5 more)

### Community 39 - "Backtest Runner"
Cohesion: 0.11
Nodes (12): HypothesisKnowledgeBase, Any, Get timeline of hypothesis development, Export all hypotheses to a file, Import hypotheses from a file, Stub implementation of HypothesisKnowledgeBase for integration testing., Retrieve hypothesis by ID, Search hypotheses based on criteria (+4 more)

### Community 40 - "Trading Strategies"
Cohesion: 0.11
Nodes (12): Decision Engine: expectancy-gated trade decision loop over AQDE hypotheses., DecisionEngine, _learn_mode_default(), Trading Decision Engine. Selects the best hypothesis per symbol from the JSONL-…, SL obligatorio 2:1 — siempre take_profit_pct / 2, sin excepcion., SL vigente EN el momento de la entrada para key, derivado del take_profit_price…, Umbrales TP/SL de la posicion. Prioridad: los guardados al abrir la posicion ->…, Expectancy-gated decision loop. For each configured symbol: 1. Pick best… (+4 more)

### Community 41 - "ML Training Pipeline"
Cohesion: 0.12
Nodes (16): design_and_apply_emd(), EmpiricalModeAnalysis, EmpiricalModeDecomposition, ndarray, Empirical Mode Decomposition Module Implements Empirical Mode Decomposition…, Interpolate between extrema using spline interpolation. Parameters ----------…, Sifting process to extract one IMF from signal. Parameters ---------- signal :…, Decompose signal into IMFs and residue. Parameters ---------- signal : array-… (+8 more)

### Community 42 - "Data Normalizer"
Cohesion: 0.09
Nodes (13): Any, datetime, Extract technical features for a specific date. Args: symbol: Trading symbol…, Get data quality metrics. Returns completeness, accuracy, and freshness metrics., Search hypotheses using text matching, Find similar hypotheses using semantic search, Update an existing hypothesis in persistent storage. Args: hypothesis_id: ID of…, Get statistics about stored hypotheses from persistent storage (+5 more)

### Community 43 - "Pattern Recognition"
Cohesion: 0.12
Nodes (14): callable, ndarray, Collection of statistical tests for strategy validation., Paired t-test (dependent samples). Args: sample1: First sample sample2: Second…, Jarque-Bera test for normality. Args: sample: Sample data Returns: Tuple of (JB…, Calculate t-statistic for one-sample t-test., Shapiro-Wilk test for normality (approximation). Args: sample: Sample data (max…, Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:… (+6 more)

### Community 44 - "Portfolio Metrics"
Cohesion: 0.14
Nodes (14): BurstStateTracker, Maneja cooldown, max entries, y streak de burst., make_engine(), Tests for Plan V2 Phase B3: BurstStateTracker + cooldown + trend filter., test_cooldown_remaining(), test_stats_dict(), test_tracker_can_enter_initially(), test_tracker_closure_stats() (+6 more)

### Community 45 - "Adaptive System"
Cohesion: 0.15
Nodes (13): PeriodogramAnalyzer, ndarray, Detect seasonality in the data. Parameters ---------- data : np.ndarray Time…, Periodogram analyzer. This class performs periodogram analysis to identify…, Compute spectral flatness. Parameters ---------- data : np.ndarray Time series…, Compute spectral kurtosis. Parameters ---------- data : np.ndarray Time series…, Compute auto-correlation of power spectrum. Parameters ---------- data :…, Plot periodogram. Parameters ---------- data : np.ndarray Time series data… (+5 more)

### Community 46 - "Historical Data"
Cohesion: 0.14
Nodes (13): PowerSpectralDensity, ndarray, Compute spectral centroid. Parameters ---------- data : np.ndarray Time series…, Compute spectral bandwidth. Parameters ---------- data : np.ndarray Time series…, Compute spectral rolloff. Parameters ---------- data : np.ndarray Time series…, Power Spectral Density (PSD) analyzer. This class computes PSD using Welch's…, Compute spectral flux between two signals. Parameters ---------- data1 :…, Detect 1/f noise characteristics. Parameters ---------- data : np.ndarray Time… (+5 more)

### Community 47 - "Exchange Adapter"
Cohesion: 0.08
Nodes (24): get_active_strategies(), get_autonomous_status(), get_backtest_hypotheses(), get_config_values(), get_events(), get_monitoring_flow(), get_monitoring_hypotheses(), get_monitoring_simulations() (+16 more)

### Community 48 - "Performance Analytics"
Cohesion: 0.12
Nodes (13): useApi(), useAutonomousApi(), useBacktestApi(), useConfigApi(), useDashboardApi(), useMonitoringApi(), useTradingApi(), useEquityChart() (+5 more)

### Community 49 - "Strategy Optimizer"
Cohesion: 0.16
Nodes (22): _ask_mode(), _count_open_positions(), _dispatch(), _get_current_price(), _get_exchange(), _learning_panel_data(), main(), monitor_loop() (+14 more)

### Community 50 - "Module 50"
Cohesion: 0.10
Nodes (12): Agent, AgentRegistry, AgentMessage, Port for agent communication and coordination. Abstract base for specialized…, Execute a specific task, Send/receive a message, Get list of agent capabilities, Register this agent with the registry (+4 more)

### Community 51 - "Module 51"
Cohesion: 0.14
Nodes (15): DenoisingKalmanFilter, design_and_apply_kalman_filter(), KalmanFilter, ndarray, Kalman Filter Module Implements Kalman filtering for state estimation and noise…, Predict state estimate forward. Parameters ---------- u : ndarray, optional…, Update state estimate with measurement. Parameters ---------- z : float or…, Apply Kalman filter to sequence of measurements. Parameters ----------… (+7 more)

### Community 52 - "Module 52"
Cohesion: 0.15
Nodes (14): ContinuousWaveletTransform, cwt(), callable, ndarray, Continuous Wavelet Transform (CWT) This module provides Continuous Wavelet…, Compute energy spectrum from CWT. Parameters ---------- data : np.ndarray Time…, Detect transient events in the time series. Parameters ---------- data :…, Plot CWT coefficients. Parameters ---------- data : np.ndarray Time series data… (+6 more)

### Community 53 - "Module 53"
Cohesion: 0.09
Nodes (12): QuantMathAdapter, Get list of available trading symbols, Store hypothesis in persistent knowledge base. Args: hypothesis: Hypothesis to…, Retrieve hypothesis by ID from persistent storage, Delete a hypothesis from persistent storage, Import hypotheses from a file, Adapter for integrating AQDE with existing quant-math modules. Implements all…, Calculate win rate from trade history (+4 more)

### Community 54 - "Module 54"
Cohesion: 0.15
Nodes (13): compute_fft(), FastFourierTransform, ndarray, Fast Fourier Transform (FFT) This module provides Fast Fourier Transform…, Find dominant frequency in the data. Parameters ---------- data : np.ndarray…, Fast Fourier Transform (FFT) analyzer. This class performs FFT analysis on time…, Compute FFT spectrum (magnitude squared). Parameters ---------- data :…, Detect presence of seasonality in the data. Parameters ---------- data :… (+5 more)

### Community 55 - "Module 55"
Cohesion: 0.14
Nodes (12): callable, ndarray, Shapiro-Wilk test for normality. Args: sample: Sample data (max 5000…, Collection of statistical tests for strategy validation., Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:…, Bootstrap confidence interval. Args: sample: Sample data statistic: Function to…, One-sample t-test. Args: sample: Sample data popmean: Population mean to test…, Test if strategy returns are significantly different from benchmark. Args:… (+4 more)

### Community 56 - "Module 56"
Cohesion: 0.10
Nodes (11): MonteCarloResult, StrategyResult, Test statistical significance of strategy performance. Returns p-value or…, Calculate Calmar ratio, Use bootstrap resampling to estimate significance. Returns bootstrap p-value., Run backtest on a hypothesis. Args: hypothesis: Hypothesis to test data: Market…, Run Monte Carlo simulation on strategy results, Calculate Value at Risk (+3 more)

### Community 57 - "Module 57"
Cohesion: 0.10
Nodes (15): areaPath, chartRef, colorMap, fillColor, hoverIndex, linePath, maxVal, minVal (+7 more)

### Community 58 - "Module 58"
Cohesion: 0.14
Nodes (17): useTradingStore, allConfirmed, apiConfig, closePosition(), confirmations, disableTrading(), emergencyStop(), enableTrading() (+9 more)

### Community 59 - "Module 59"
Cohesion: 0.16
Nodes (17): command, group, option, backtest(), cli(), discover(), export(), init_kb() (+9 more)

### Community 60 - "Module 60"
Cohesion: 0.15
Nodes (11): ndarray, Calculate Information Ratio (active return / tracking error). Args: returns:…, Calculate risk-adjusted performance metrics., Calculate Treynor ratio (excess return / beta). Args: returns: Strategy returns…, Calculate Omega ratio (probability-weighted gains / losses). Args: returns:…, Calculate all risk-adjusted metrics. Returns: Dictionary with all metrics, Calculate Sharpe ratio. Args: returns: Array of returns risk_free_rate: Risk-…, Calculate Sortino ratio (uses downside deviation). Args: returns: Array of… (+3 more)

### Community 61 - "Module 61"
Cohesion: 0.12
Nodes (16): activeHypotheses, activity, availableSymbols, config, iteration, maxIterations, phase, progress (+8 more)

### Community 62 - "Module 62"
Cohesion: 0.12
Nodes (10): Agent, AgentMessage, Any, Send a message to a specific agent. Args: sender: Sending agent receiver_id:…, Get message history. Args: agent_id: Filter by sender/receiver ID (optional)…, Get registry statistics. Returns: Dictionary with statistics about registered…, Get list of all registered agents with details. Returns: List of agent…, Register a new agent. Args: agent: Agent instance to register Returns: Agent ID… (+2 more)

### Community 63 - "Module 63"
Cohesion: 0.12
Nodes (10): Hypothesis, KnowledgeBase, Port for hypothesis knowledge management. Adapters implement this to store,…, Store a hypothesis and return its ID, Retrieve a hypothesis by ID, Search hypotheses based on criteria. Criteria can include: - strategy_type -…, Update an existing hypothesis, Get statistics about stored hypotheses (+2 more)

### Community 64 - "Module 64"
Cohesion: 0.13
Nodes (9): _burst_read_paper_trades(), _read_closures(), Tests for burst history and burst monitor separation (v1.2.1)., Test that AQDERunner prunes unbounded data structures., TestBurstConstants, TestBurstReadPaperTrades, TestMemoryPruning, TestReadClosures (+1 more)

### Community 65 - "Module 65"
Cohesion: 0.17
Nodes (7): Any, Register/overwrite a hypothesis record in the JSONL KB., Todos los candidatos consultables ordenados por (expectancy DESC,…, Best hypothesis for symbol by (expectancy DESC, scientific_score DESC)., Direction from momentum on real closes (lookback from params)., Run one decision cycle for a symbol., Decide for all configured symbols.

### Community 66 - "Module 66"
Cohesion: 0.16
Nodes (11): DrawdownAnalyzer, Any, ndarray, Calculate average drawdown duration., Calculate maximum drawdown duration., Calculate Ulcer Index (root mean square of drawdowns). Ulcer Index =…, Analyze drawdowns from equity curve or returns., Calculate drawdown series and metrics from equity curve. Args: equity_curve:… (+3 more)

### Community 67 - "Module 67"
Cohesion: 0.18
Nodes (10): HarmonicComponentAnalyzer, ndarray, Reconstruct signal from top harmonics. Parameters ---------- data : np.ndarray…, Harmonic component analyzer. This class identifies and analyzes harmonic…, Compute ratio between harmonic components. Parameters ---------- data :…, Analyze periodicity in the data. Parameters ---------- data : np.ndarray Time…, Plot harmonic components. Parameters ---------- data : np.ndarray Time series…, Plot frequency spectrum highlighting harmonics. Parameters ---------- data :… (+2 more)

### Community 68 - "Module 68"
Cohesion: 0.11
Nodes (14): areaPath, colorMap, fillColor, hoverPoint, linePath, maxVal, minVal, points (+6 more)

### Community 69 - "Module 69"
Cohesion: 0.11
Nodes (15): filteredHypotheses, flow, hypFilter, hypotheses, hypothesisStatuses, loading, simulationGroups, simulations (+7 more)

### Community 70 - "Module 70"
Cohesion: 0.18
Nodes (13): generate_model_hypotheses(), Generador de hipotesis basado en modelos cientificos (ARIMA/GARCH). Conecta los…, Devuelve plantillas compatibles con create_hypotheses_for_symbol. Regla…, Tests for Plan V2 Phase B2: scalp_burst strategy + generation., _sine_closes(), test_burst_mode_prioritizes_scalp_burst(), test_scalp_burst_in_model_generator(), test_scalp_burst_parameters() (+5 more)

### Community 71 - "Module 71"
Cohesion: 0.12
Nodes (16): put, API Routes for Quant-Math WebUI, # TODO: Connect to actual AQDE state, # TODO: Connect to actual paper trading engine, # TODO: Connect to hypothesis database, # TODO: Connect to event store, # TODO: Connect to actual strategy manager, # TODO: Load from actual config store (+8 more)

### Community 72 - "Module 72"
Cohesion: 0.21
Nodes (9): Any, Stop loss calculator with multiple methods. Supports: - Fixed percentage - ATR-…, Chandelier exit stop loss., Volatility-adjusted stop loss., Calculate multiple stop loss levels. Args: entry_price: Entry price side:…, Initialize stop loss calculator. Args: default_method: Default stop loss method…, Calculate stop loss price. Args: entry_price: Entry price side: 'long' or…, Fixed percentage stop loss. (+1 more)

### Community 73 - "Module 73"
Cohesion: 0.16
Nodes (11): BandPassFilter, design_and_apply_band_pass(), ndarray, Band-Pass Filter Module Implements band-pass filters to retain only specific…, Apply band-pass filter to input data. Parameters ---------- data : array-like…, Apply filter in real-time with phase delay (for online applications).…, Compute frequency response of the band-pass filter. Returns ------- w : ndarray…, Analyze signal power in passband vs stopbands. Parameters ----------… (+3 more)

### Community 74 - "Module 74"
Cohesion: 0.16
Nodes (11): design_and_apply_high_pass(), HighPassFilter, ndarray, High-Pass Filter Module Implements high-pass filters to remove low-frequency…, Apply filter using zero-pole-gain representation (more stable for long data).…, Compute frequency response of the filter. Returns ------- w : ndarray Angular…, Analyze signal bandwidth before and after filtering. Parameters ----------…, Convenience function to design and apply high-pass filter in one step.… (+3 more)

### Community 75 - "Module 75"
Cohesion: 0.17
Nodes (15): closeDropdown(), containerRef, emit, filteredOptions, focused, handleClickOutside(), handleKeydown(), hoveredIndex (+7 more)

### Community 76 - "Module 76"
Cohesion: 0.16
Nodes (14): useConfigStore, config, loadConfig(), loading, resetConfig(), saveConfig(), saving, sections (+6 more)

### Community 77 - "Module 77"
Cohesion: 0.12
Nodes (12): backtestStore, configStore, configValues, effectiveConfig, error, form, hypotheses, loadingDetail (+4 more)

### Community 78 - "Module 78"
Cohesion: 0.17
Nodes (9): DataFrame, ndarray, Cap outliers to specified bounds Args: df: DataFrame column: Column to cap…, Detect and count duplicate rows Args: df: Input DataFrame Returns: DataFrame…, Remove duplicate rows Args: df: Input DataFrame subset: Columns to check for…, Perform comprehensive data quality check Args: df: Input DataFrame Returns:…, Perform complete data cleaning pipeline Args: df: Input DataFrame…, Handle missing values in DataFrame Args: df: Input DataFrame method: 'ffill',… (+1 more)

### Community 79 - "Module 79"
Cohesion: 0.13
Nodes (9): DataFrame, Series, Calculate returns from price data Args: df: Input DataFrame with price column…, Calculate volatility Args: df: Input DataFrame with price column price_col:…, Shift data by specified periods Args: df: Input DataFrame cols: Columns to…, Create time-based features Args: df: Input DataFrame timestamp_col: Timestamp…, Resample to specific frequency Args: df: Input DataFrame target_freq: Target…, Resample time series data Args: df: Input DataFrame with timestamp column… (+1 more)

### Community 80 - "Module 80"
Cohesion: 0.22
Nodes (10): DataFrame, Series, Detect regime changes in time series Args: df: Input DataFrame col: Column to…, Detect structural breaks in time series data, Test stationarity of time series Args: df: Input DataFrame col: Column to test…, Detect changes in trend using linear regression Args: df: Input DataFrame col:…, Comprehensive structural break analysis Args: df: Input DataFrame col: Column…, Chow test for structural break at specified point Args: df: Input DataFrame… (+2 more)

### Community 81 - "Module 81"
Cohesion: 0.12
Nodes (15): bootstrap_confidence_interval(), bootstrap_p_value(), one_sample_ttest(), paired_ttest(), Statistical Tests Module Statistical significance testing for trading strategy…, Convenience function for one-sample t-test., Convenience function for two-sample t-test., Convenience function for paired t-test. (+7 more)

### Community 82 - "Module 82"
Cohesion: 0.17
Nodes (14): analyze_series(), _dominant_cycle(), Ciclo dominante en velas via FFT del paquete spectral_analysis existente (sin…, ARIMA(1,1,0): signo del forecast; GARCH(1,1): percentil de la volatilidad…, kalman_features(), kalman_level(), ndarray, Filtro de Kalman escalar (modelo de nivel constante) en numpy puro. Feature de… (+6 more)

### Community 83 - "Module 83"
Cohesion: 0.17
Nodes (10): Any, ndarray, Calculate various return metrics from trade history or price series., Calculate returns from trade history. Args: trades: List of trade dictionaries…, Calculate cumulative return from returns series., Calculate annualized return., Calculate geometric mean of returns., Calculate arithmetic mean of returns. (+2 more)

### Community 84 - "Module 84"
Cohesion: 0.22
Nodes (15): example_fft_analysis(), example_harmonic_analysis(), example_periodogram_analysis(), example_psd_analysis(), example_wavelet_analysis(), generate_sample_data(), main(), ndarray (+7 more)

### Community 85 - "Module 85"
Cohesion: 0.14
Nodes (8): ExchangeManager, Register an exchange. Parameters: ----------- name : str Exchange name api_key…, Set the active exchange. Parameters: ----------- name : str Exchange name…, Get the active exchange configuration., Manage multiple cryptocurrency exchanges., Place an order. Parameters: ----------- symbol : str Trading symbol (e.g.,…, Initialize exchange manager., Cancel an order. Parameters: ----------- order_id : str Order ID Returns:…

### Community 86 - "Module 86"
Cohesion: 0.13
Nodes (15): post, close_position(), disable_trading(), emergency_stop(), enable_trading(), Save configuration values., Stop autonomous mode., Enable real trading with Bybit. (+7 more)

### Community 87 - "Module 87"
Cohesion: 0.19
Nodes (10): design_and_apply_wavelet_denoise(), ndarray, Wavelet Decomposition Module Implements wavelet-based denoising and signal…, Denoise signal using wavelet thresholding. Parameters ---------- signal :…, Get multi-resolution analysis information. Parameters ---------- signal :…, Convenience function to denoise signal in one step. Parameters ----------…, Wavelet-based denoising and signal decomposition. This class implements wavelet…, Initialize wavelet denoiser. Parameters ---------- wavelet : str, optional… (+2 more)

### Community 88 - "Module 88"
Cohesion: 0.14
Nodes (10): isDark, navItems, route, router, store, wsStatus, app, pinia (+2 more)

### Community 89 - "Module 89"
Cohesion: 0.19
Nodes (8): DataFrame, ndarray, Generate synthetic OHLCV data for dry-run / testing. Uses a random walk with…, Calculate Stochastic %K and %D indicators, Calculate Volume Weighted Average Price, Calculate Donchian channels (upper and lower), Calculate Average True Range, Run backtest using quant-math backtester. Args: hypothesis: Hypothesis dict…

### Community 90 - "Module 90"
Cohesion: 0.22
Nodes (12): OrchestratorConfig, Explicit configuration. Required fields have NO hidden defaults., Tests for Plan V2 Phase C1: burst infrastructure., test_burst_notional_calculation(), test_mode_burst_clamps_leverage(), test_mode_burst_clamps_margin(), test_mode_burst_clamps_tp(), test_mode_burst_forces_interval() (+4 more)

### Community 91 - "Module 91"
Cohesion: 0.20
Nodes (13): example_band_pass_filter(), example_emd(), example_high_pass_filter(), example_kalman_filter(), example_wavelet_denoising(), generate_test_signal(), Signal Processing Module Example Usage This module demonstrates how to use the…, Example: Band-pass filtering to isolate specific frequency bands. (+5 more)

### Community 92 - "Module 92"
Cohesion: 0.27
Nodes (13): closure(), make(), O1 graduacion endurecida · O2 slippage · O6 vol-target sizing · O7 familias…, media +0.05 pero sd alta -> IC90_lb<0: NO gradua, IC90 ok pero una sola familia: NO gradua (min_families=2 default), media>0, IC90_lb>0 y >=2 familias -> gradua con campos nuevos, seed(), test_o1_family_diversity_required() (+5 more)

### Community 93 - "Module 93"
Cohesion: 0.32
Nodes (13): flat_candles(), make(), Riesgo + persistencia de posiciones: SL 2:1 obligatorio, cierres TP/SL en el…, Deja en el estado una posicion abierta como si viniera de sesion previa., SL = TP/2 exacto para cualquier TP configurado., Posicion abierta -> 'reinicio' -> se recupera, guarda y sigue monitoreando., read_ledger(), rising_candles() (+5 more)

### Community 94 - "Module 94"
Cohesion: 0.14
Nodes (9): activeCount, avgSharpe, selectedStrategy, statusLabels, stopStrategy(), store, strategies, totalPnL (+1 more)

### Community 95 - "Module 95"
Cohesion: 0.25
Nodes (10): useWebSocket(), clearTimers(), connect(), disconnect(), scheduleReconnect(), send(), useAutonomousStore, useBacktestStore (+2 more)

### Community 96 - "Module 96"
Cohesion: 0.17
Nodes (13): BaseModel, AutonomousConfig, BacktestRequest, BacktestResponse, ConfigSection, Event, get_config_sections(), Hypothesis (+5 more)

### Community 97 - "Module 97"
Cohesion: 0.23
Nodes (7): DataFrame, Standardize multiple columns Args: df: Input DataFrame method: 'zscore',…, Normalize all numerical columns Args: df: Input DataFrame method: Normalization…, Inverse transform normalized data Args: df_norm: Normalized DataFrame scaler:…, Min-Max normalization Args: df: Input DataFrame feature_range: Desired range…, Z-score normalization (standardization) Args: df: Input DataFrame columns:…, Robust scaling (using median and IQR) Args: df: Input DataFrame columns:…

### Community 98 - "Module 98"
Cohesion: 0.18
Nodes (6): Cierres de UNA hipotesis+simbolo segun el libro permanente., PA: expectancy viva con shrinkage bayesiano doble. 1) est = (n*media_propia +…, O1/PB: desactiva LEARN_MODE cuando la ventana movil de cierres es…, Cierres del simbolo en el libro (todas las familias)., Operaciones cerradas de la familia+simbolo segun el libro permanente (fuente…, Entrega feedback AGREGADO por familia cuando las operaciones de esa familia…

### Community 99 - "Module 99"
Cohesion: 0.17
Nodes (10): format, formatTime(), emit, formatDate(), formatDateTime(), props, statusLabels, formatTime() (+2 more)

### Community 100 - "Module 100"
Cohesion: 0.23
Nodes (12): autonomousLoading, emit, emitAutonomous(), emitBacktest(), emitRealTrading(), emitRestart(), emitStart(), emitStop() (+4 more)

### Community 101 - "Module 101"
Cohesion: 0.18
Nodes (7): Calculate Sharpe ratio. Parameters: ----------- returns : List[float] Period…, Calculate Sortino ratio (downside deviation). Parameters: ----------- returns :…, Calculate Sharpe ratio and related metrics., Calculate information ratio. Parameters: ----------- returns : List[float]…, SharpeMetrics, jarque_bera_test(), Convenience function for Jarque-Bera test.

### Community 102 - "Module 102"
Cohesion: 0.17
Nodes (7): Risk Manager Implementation. Implements the RiskManager port for risk…, Port for risk management checks. Adapters implement this to ensure hypotheses…, Check if position size meets risk criteria. Returns OK or failure reasons., Check if drawdown is within acceptable limits, Check if Sharpe ratio meets threshold, Check if Sortino ratio meets threshold, RiskManager

### Community 103 - "Module 103"
Cohesion: 0.23
Nodes (8): FakeKBPersistence, _install_fake_pg_module(), _make(), Bugfix post-graduacion: (1) dual-write PG+JSONL siempre en _save_hypothesis,…, Con storage disponible, el arranque carga TODO el universo de PG (_load_jsonl…, Stub del adapter PG: graba saves y devuelve universo fijo., test_dual_write_writes_jsonl_even_with_storage(), test_storage_boot_uses_full_pg_universe()

### Community 104 - "Module 104"
Cohesion: 0.18
Nodes (6): Calculate simple returns from price series. Parameters: ----------- prices :…, Calculate log returns from price series. Parameters: ----------- prices :…, Calculate annualized return. Parameters: ----------- returns : List[float]…, Calculate various return metrics., Calculate cumulative return from price series. Parameters: ----------- prices :…, ReturnCalculator

### Community 105 - "Module 105"
Cohesion: 0.18
Nodes (6): DrawdownAnalyzer, Calculate drawdowns from price series. Parameters: ----------- prices :…, Calculate maximum drawdown. Parameters: ----------- drawdowns : List[float]…, Calculate average drawdown. Parameters: ----------- drawdowns : List[float]…, Analyze drawdowns from price series., Calculate drawdown duration (time from peak to valley). Parameters: -----------…

### Community 106 - "Module 106"
Cohesion: 0.20
Nodes (7): DataProvider, datetime, Port for data access in AQDE. Adapters implement this to provide market data,…, Fetch market data for a given symbol and date range. Args: symbol: Trading…, Extract features for a specific date/time. Features can include technical…, Get list of available trading symbols, Get data quality metrics for a symbol. Returns completeness, accuracy, and…

### Community 107 - "Module 107"
Cohesion: 0.35
Nodes (10): flat(), make(), Opcion B: feedback agregado por FAMILIA x SIMBOLO. Las keys rotan (cada una con…, 3 cierres de la MISMA familia (keys rotando o no): la familia llega a 3 ops ->…, n=3 entrega; n=6 vuelve a entregar (bucket 2)., El contrato original por-key (min=3) NO cambia: con 1 op no entrega., seed_hyp(), test_bucket_multiple_delivers_again() (+2 more)

### Community 108 - "Module 108"
Cohesion: 0.42
Nodes (10): closure(), make(), PA: expectancy viva con shrinkage doble (propio->familia, realizado->…, O1: requiere media>0, IC90_lb>0 y >=2 familias en la ventana., seed_ledger(), test_pa_expectancy_shrinks_toward_realized(), test_pa_ranking_flips_when_live_results_bad(), test_pb_graduates_on_positive_window() (+2 more)

### Community 109 - "Module 109"
Cohesion: 0.24
Nodes (6): _read_paper_trades(), Test that the two-pass scan correctly identifies open entries., Entries that appear BEFORE their closure records should not be counted as open., Some entries open, some closed — only open ones should count., TestReadPaperTrades, TestTwoPassMonitorFix

### Community 110 - "Module 110"
Cohesion: 0.27
Nodes (9): list_modules(), main(), QUANT-MATH Main Entry Point Unified CLI entry point for the QUANT-MATH…, List available modules with descriptions., Main CLI entry point., Run integration tests., Show framework information., run_tests() (+1 more)

### Community 111 - "Module 111"
Cohesion: 0.33
Nodes (9): make_engine(), Decision Engine behavior tests: abstention (no_entry) and operation (entry)., All hypotheses with expectancy <= 0 -> no_entry, zero signals., One hypothesis with expectancy > 0 -> entry signal generated., Low scientific_score degrades to failed but stays queryable; ordering by…, run_all(), test_abstention_all_nonpositive_expectancy(), test_failed_status_still_queryable_and_best_selection_ordering() (+1 more)

### Community 112 - "Module 112"
Cohesion: 0.25
Nodes (5): Any, Generate base hypothesis configurations for a symbol, Generate new hypotheses based on performance feedback - ENHANCED, Closes recientes REALES para los modelos; cache por ciclo., Create and register hypotheses for a symbol

### Community 113 - "Module 113"
Cohesion: 0.22
Nodes (5): Agent, Port for agent communication and coordination. Abstract base for specialized…, Send/receive a message, Get list of agent capabilities, Register this agent with the registry

### Community 114 - "Module 114"
Cohesion: 0.22
Nodes (7): _BurstState, Quant-Math Orchestrator. Connects the full discovery -> decision -> feedback…, Estado persistente de la ráfaga burst., Adaptatividad del generador: rotacion por ciclo + feedback real. Verifica que…, test_dedupe_filters_duplicates_across_cycles(), test_exploration_rotates(), test_feedback_enables_mutations()

### Community 115 - "Module 115"
Cohesion: 0.33
Nodes (3): HiddenMarkovModel, ndarray, test_regime_detection()

### Community 116 - "Module 116"
Cohesion: 0.31
Nodes (3): ndarray, test_var(), ValueAtRisk

### Community 117 - "Module 117"
Cohesion: 0.33
Nodes (8): make_engine(), OrchestratorConfig_for_test(), Tests for Plan V2 Phase B4+C2: burst slippage + exposure cap., test_burst_env_var(), test_burst_slippage_tighter(), test_burst_trade_record_has_margin(), test_classic_slippage_unchanged(), test_exposure_cap_blocks_entry()

### Community 118 - "Module 118"
Cohesion: 0.22
Nodes (8): Tests for Plan V2 Phase B5: burst monitor panel., Verify that burst_stats dict has all fields needed by the monitor., Verify burst mode uses different graduation params., test_burst_mode_in_orchestrator_stats(), test_burst_panel_rows(), test_burst_stats_in_stats_dict(), test_burst_stats_zero_state(), test_graduation_burst_different_window()

### Community 119 - "Module 119"
Cohesion: 0.22
Nodes (8): autonomousStore, currentStore, dashboardStore, monitoringStore, route, routeStoreMap, statusClass, statusText

### Community 120 - "Module 120"
Cohesion: 0.36
Nodes (7): main(), Example: Risk factor model., Example: Feature engineering., Example: ML-based portfolio optimization., test_factor_model(), test_feature_engineering(), test_ml_portfolio()

### Community 121 - "Module 121"
Cohesion: 0.36
Nodes (7): main(), Example: Risk Parity Portfolio., Example: Efficient Frontier., Example: Black-Litterman Model., test_black_litterman(), test_efficient_frontier(), test_risk_parity()

### Community 122 - "Module 122"
Cohesion: 0.25
Nodes (5): Adapters for AQDE - Implementation of hexagonal architecture ports. These…, Stub module for HypothesisKnowledgeBase to fix imports., Search criteria for hypothesis search, SearchCriteria, Search hypotheses based on criteria. Args: criteria: Search criteria dictionary…

### Community 123 - "Module 123"
Cohesion: 0.32
Nodes (8): ask_float(), ask_int(), burst_wizard(), fetch_top_volume_assets(), Interactive configuration wizard. Returns cfg dict or None if cancelled., Interactive burst-scalping configuration wizard., Top-N USDT pairs by quoteVolume, stablecoin bases excluded., wizard()

### Community 124 - "Module 124"
Cohesion: 0.25
Nodes (5): _DetachedProcess, _detect_active_modes(), Wrapper for a subprocess.Popen that provides mp.Process-like interface., Detect running modes from PID files (for re-entrant CLI)., Check if the process is still running via PID file + os.kill.

### Community 125 - "Module 125"
Cohesion: 0.25
Nodes (4): Reescribe positions.jsonl con las posiciones vivas (atomico)., Cierra una posicion: la quita del estado vivo y la registra en el libro de…, Cantidad/notional de la ultima entrada abierta para key segun el libro…, O2: precio adverso por slippage. Comprar entra caro y sale barato (al cerrar…

### Community 126 - "Module 126"
Cohesion: 0.25
Nodes (4): Harmonic Component Analysis This module provides harmonic component analysis…, Spectral Analysis This module provides frequency domain analysis techniques…, Periodogram Analysis This module provides periodogram-based frequency analysis…, Power Spectral Density (PSD) This module provides Power Spectral Density…

### Community 127 - "Module 127"
Cohesion: 0.36
Nodes (7): make_engine(), Tests for Plan V2 Phase B1: burst sizing (margin × leverage)., test_burst_sizing_different_params(), test_burst_sizing_notional(), test_burst_tp_range(), test_burst_trade_record_fields(), test_classic_mode_no_burst_params()

### Community 128 - "Module 128"
Cohesion: 0.29
Nodes (6): BacktestEngine, KnowledgeBase, MonteCarloEngine, RiskManager, Initialize the Research Manager. Args: knowledge_base: Port for hypothesis…, StatisticalValidator

### Community 129 - "Module 129"
Cohesion: 0.33
Nodes (3): Check if a specific mode's orchestrator is alive., Legacy stats for single-mode. Returns stats of first running mode, or classic., Legacy: return config of first running or last started mode.

### Community 130 - "Module 130"
Cohesion: 0.33
Nodes (5): BaseSettings, Config, Quant-Math WebUI Backend Configuration, Application settings loaded from environment variables., Settings

### Community 131 - "Module 131"
Cohesion: 0.33
Nodes (5): _burst_count_open_positions(), burst_monitor_loop(), Live burst monitor; ESC returns to menu without stopping anything., render_burst_monitor(), TestBurstCountOpenPositions

### Community 132 - "Module 132"
Cohesion: 0.60
Nodes (5): make(), P1: cuando el mejor candidato tiene posicion abierta, decide() cae al siguiente…, test_fallback_to_next_best_when_best_open(), test_skip_contract_when_all_blocked(), up()

### Community 133 - "Module 133"
Cohesion: 0.47
Nodes (5): emit, handleChange(), handleInput(), props, showPassword

### Community 134 - "Module 134"
Cohesion: 0.40
Nodes (3): Series, Calculate RSI indicator, Calculate multiple EMA windows

### Community 135 - "Module 135"
Cohesion: 0.40
Nodes (3): ArchitecturalViolationTracker, Tracks if any module accesses code outside quant_math/**, Check if an import violates architectural boundaries

### Community 137 - "Module 137"
Cohesion: 0.50
Nodes (3): CryptoSymbol, Fetch top N symbols by volume from Bybit, Represents a crypto trading pair with metadata

### Community 139 - "Module 139"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 141 - "Module 141"
Cohesion: 0.50
Nodes (3): props, sizeClass, variantClass

### Community 143 - "Module 143"
Cohesion: 0.50
Nodes (3): formattedValue, props, valueColor

### Community 144 - "Module 144"
Cohesion: 0.67
Nodes (3): emit, props, selectItem()

### Community 145 - "Module 145"
Cohesion: 0.50
Nodes (3): statusClass, statusText, store

### Community 148 - "Module 148"
Cohesion: 0.67
Nodes (3): AQDEStatus, get_aqde_status(), Get AQDE autonomous mode status.

### Community 149 - "Module 149"
Cohesion: 0.67
Nodes (3): get_health(), HealthResponse, Get system health metrics.

### Community 150 - "Module 150"
Cohesion: 0.67
Nodes (3): get_trading_metrics(), Get paper trading metrics., TradingMetrics

### Community 151 - "Module 151"
Cohesion: 0.67
Nodes (3): websocket, WebSocket endpoint for real-time updates., websocket_endpoint()

## Knowledge Gaps
- **209 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `quant-math`, `quant-math-webui`, `Config` (+204 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DecisionEngine` connect `Trading Strategies` to `Knowledge Base`, `Module 132`, `ML Feature Store`, `Data Sources`, `Test Suite`, `Monitor Dashboard`, `Portfolio Metrics`, `Module 65`, `Module 92`, `Module 93`, `Module 98`, `Module 103`, `Module 107`, `Module 108`, `Module 111`, `Module 114`, `Module 117`, `Module 125`, `Module 127`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `FastFourierTransform` connect `Module 54` to `Module 82`, `Module 126`, `Module 84`, `Module 70`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `StrategyType` connect `Model Generator` to `Backtesting & Data`, `Module 70`, `Module 114`, `Module 82`, `Module 90`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `DecisionEngine` (e.g. with `ExchangeAPI` and `KBPersistence`) actually correct?**
  _`DecisionEngine` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `QuantMathAdapter` (e.g. with `ExchangeAPI` and `OrderManager`) actually correct?**
  _`QuantMathAdapter` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `run_full_e2e_test()` (e.g. with `StrategyType` and `ExpectedShortfall`) actually correct?**
  _`run_full_e2e_test()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `AQDERunner` (e.g. with `ExchangeAPI` and `Orchestrator`) actually correct?**
  _`AQDERunner` has 4 INFERRED edges - model-reasoned connections that need verification._