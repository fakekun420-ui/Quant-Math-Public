# Graph Report - Quant-Math-Public  (2026-08-25)

## Corpus Check
- 192 files · ~121,057 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2998 nodes · 4618 edges · 173 communities (161 shown, 12 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 95 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4ad8a203`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HiddenMarkovModel
- __init__.py
- ResearchManager
- dependencies
- RiskManagementEngine
- _PostgreSQLDataStore
- VolatilityClusteringAnalyzer
- ndarray
- WebSocketManager
- MonteCarloSimulator
- test_integration.py
- ARIMAModel
- ExchangeAPI
- quant_math/__init__.py
- Any
- .decide
- RegimeClustering
- autonomous_research/__init__.py
- RegimeFeatureExtractor
- risk/__init__.py
- Any
- Any
- Backtester
- Order
- test_full_system_e2e.py
- VarianceRatioTest
- PCAAnalyzer
- AQDERunner
- StrategyResult
- PeriodogramAnalyzer
- AQDELabPanel.vue
- DashboardView.vue
- ndarray
- HypothesisKnowledgeBase
- Any
- quant_math/expectation/__init__.py
- StatisticalTests
- RiskManager
- PowerSpectralDensity
- get
- useApi
- KalmanFilter
- QuantMathAdapter
- FastFourierTransform
- PostgreSQLKnowledgeBase
- DataCleaner
- KellyCriterion
- cli/main.py
- .communicate
- test_operation_learning.py
- TimeSeriesResampler
- StatisticalTests
- EquityChart.vue
- TradingView.vue
- autonomous_research/cli/__init__.py
- SharpeMetrics
- Module Breakdown
- EmpiricalModeDecomposition
- ContinuousWaveletTransform
- AutonomousView.vue
- AgentRegistry
- StructuralBreakDetector
- routes.py
- Hypothesis
- DrawdownAnalyzer
- ReturnCalculator
- Orchestrator
- HarmonicComponentAnalyzer
- MiniChart.vue
- MonitoringView.vue
- Normalizer
- StopLoss
- ndarray
- BandPassFilter
- HighPassFilter
- MultiSelect.vue
- ConfigView.vue
- BacktestView.vue
- spectral_analysis/__main__.py
- HypothesisPrior
- ExchangeManager
- post
- PositionSizer
- Any
- WaveletDenoiser
- App.vue
- expectation/statistical_tests.py
- .run_backtest
- Quant-Math + AQDE Consolidated Architecture Guide
- PortfolioRisk
- signal_processing/__main__.py
- ActiveStrategiesPanel.vue
- stores/index.js
- BaseModel
- format
- ControlButtons.vue
- expectation/__init__.py
- .check_sharpe_threshold
- aqde_runner.py
- risk_management.py
- ValueAtRisk
- ReturnCalculator
- DrawdownAnalyzer
- System Dependency Map — Quant-Math + AQDE Ecosystem
- DecisionEngine
- quant_math/__main__.py
- ExpectedShortfall
- QUANT-MATH: Professional Quantitative Trading Research System
- HiddenMarkovModel
- ValueAtRisk
- ConnectionStatus.vue
- ml_quant/__main__.py
- SQLiteDataStore
- portfolio_construction/__main__.py
- SearchCriteria
- Quant-Math Architecture Reuse Analysis Report
- RuntimeState
- spectral_analysis/__init__.py
- ✅ Completed Modules
- Settings
- test_risk_persistence.py
- ParameterField.vue
- ._calculate_emas
- ArchitecturalViolationTracker
- EquityCurveChart.vue
- .fetch_top_symbols
- .create_hypotheses_for_symbol
- PortfolioRiskResult
- Button.vue
- PnlDistributionChart.vue
- MetricCard.vue
- StageColumn.vue
- SystemStatusIndicator.vue
- graphify.js
- .get_params
- generate_model_hypotheses
- test_family_feedback.py
- websocket_endpoint
- simulator.py
- test_decision_engine.py
- quant_math/cli/__init__.py
- .__init__
- .fetch_balance
- .close_position
- quant-math
- quant-math-webui
- ._maybe_deliver_family_feedback
- get_health
- ResearchPhase
- opencode.json
- get_aqde_status
- get_trading_metrics
- .__init__
- .check_sortino_threshold
- get_hypotheses
- get_monitoring_strategies

## God Nodes (most connected - your core abstractions)
1. `QuantMathAdapter` - 51 edges
2. `DecisionEngine` - 44 edges
3. `PostgreSQLKnowledgeBase` - 41 edges
4. `run_full_e2e_test()` - 39 edges
5. `OrderManager` - 31 edges
6. `AQDERunner` - 28 edges
7. `RiskManager` - 25 edges
8. `ExchangeAPI` - 24 edges
9. `RiskManagementEngine` - 24 edges
10. `HypothesisKnowledgeBase` - 22 edges

## Surprising Connections (you probably didn't know these)
- `VWAP` --uses--> `Order`  [INFERRED]
  algo_trading/algo_trading.py → order_management/order_management.py
- `POV` --uses--> `Order`  [INFERRED]
  algo_trading/algo_trading.py → order_management/order_management.py
- `AQDERunner` --uses--> `ExchangeAPI`  [INFERRED]
  aqde_runner.py → data_acquisition/data_sources/exchanges.py
- `Orchestrator` --uses--> `AQDERunner`  [INFERRED]
  quant_math/orchestrator.py → aqde_runner.py
- `QuantMathAdapter` --uses--> `ExchangeAPI`  [INFERRED]
  quant_math/autonomous_research/adapters/quant_math_adapter.py → data_acquisition/data_sources/exchanges.py

## Import Cycles
- None detected.

## Communities (173 total, 12 thin omitted)

### Community 0 - "HiddenMarkovModel"
Cohesion: 0.06
Nodes (32): Regime Detection Module This module provides tools for detecting and analyzing…, example_clustering(), example_hmm(), main(), Example: Hidden Markov Model regime detection., Example: Regime clustering., HiddenMarkovModel, ndarray (+24 more)

### Community 1 - "__init__.py"
Cohesion: 0.07
Nodes (40): AlgoExecution, AlgoTradingSystem, POV, Order, Algorithmic Trading System This module provides algorithmic trading…, Volume-Weighted Average Price (VWAP) Splits order based on expected market…, Initialize VWAP algorithm. Two modes: Order-based (legacy): execution_time :…, Execute using VWAP. Order-based mode: execute(order, order_manager,… (+32 more)

### Community 2 - "ResearchManager"
Cohesion: 0.11
Nodes (16): Any, Hypothesis, MonteCarloResult, StrategyResult, Generate a new hypothesis. Args: hypothesis_id: Optional ID (auto-generated if…, Run scientific validation on a hypothesis. Checks logical consistency,…, Run Monte Carlo simulation on a hypothesis. Args: hypothesis_id: ID of…, Calculate comprehensive score for a hypothesis. Combines validation, backtest,… (+8 more)

### Community 3 - "dependencies"
Cohesion: 0.05
Nodes (43): axios, chart.js, chartjs-adapter-date-fns, d3, date-fns, eslint, eslint-config-prettier, eslint-plugin-prettier (+35 more)

### Community 4 - "RiskManagementEngine"
Cohesion: 0.07
Nodes (24): Any, RiskManager, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Implementation of RiskManager port. Provides risk management functionality…, Check if drawdown is within acceptable limits. Args: hypothesis_id: Hypothesis…, Check if Sharpe ratio meets threshold. Args: sharpe_ratio: Sharpe ratio to…, Check if Sortino ratio meets threshold. Args: sortino_ratio: Sortino ratio to… (+16 more)

### Community 5 - "_PostgreSQLDataStore"
Cohesion: 0.14
Nodes (13): _PostgreSQLDataStore, Any, DataFrame, Query data from database Args: query: SQL query string params: Query parameters…, Get schema information for a table Args: table: Table name Returns: List of…, Check data quality for a table Args: table: Table name columns: Specific…, Remove data older than specified threshold Args: table: Table name…, Close all connections in the pool (+5 more)

### Community 6 - "VolatilityClusteringAnalyzer"
Cohesion: 0.07
Nodes (22): EWMAVolatility, GARCHModel, ndarray, Volatility Clustering Analysis This module provides methods to detect and…, Detect volatility clusters using rolling volatility. Parameters ----------…, Test for ARCH effects (autoregressive conditional heteroskedasticity). The…, Check if ARCH effects are present (indicating volatility clustering).…, Calculate the ratio of high volatility variance to low volatility variance.… (+14 more)

### Community 7 - "ndarray"
Cohesion: 0.07
Nodes (24): FeatureEngineer, MLPortfolioOptimizer, MLPortfolioResult, ndarray, Machine Learning for Quant Module This module provides machine learning tools…, Add cross-asset features (e.g., spread, correlation). Parameters ----------…, Get feature importance from trained model. Parameters ---------- model : Any…, Machine Learning Portfolio Optimizer Uses ML-based constraints and risk models. (+16 more)

### Community 8 - "WebSocketManager"
Cohesion: 0.07
Nodes (26): AsyncSession, FastAPI, get_db(), init_db(), Database Module for WebUI Backend, Initialize database tables., Get database session., WebSocket (+18 more)

### Community 9 - "MonteCarloSimulator"
Cohesion: 0.11
Nodes (17): MonteCarloSimulator, Any, MonteCarloResult, ndarray, StrategyResult, Extract PnL values from trade records., Bootstrap simulation (non-parametric resampling)., Parametric simulation assuming normal distribution. (+9 more)

### Community 10 - "test_integration.py"
Cohesion: 0.08
Nodes (27): Order, OrderType, Enum, Initialize order. Parameters: ----------- symbol : str Trading symbol side :…, Validate order parameters. Returns: -------- bool True if valid, Supported order types., OrderRouter, Order (+19 more)

### Community 11 - "ARIMAModel"
Cohesion: 0.07
Nodes (25): ARCHModel, ARIMAModel, ARIMAResult, GARCHModel, Any, ndarray, Statistical Models for Probabilistic Forecasting This module provides time…, Generate probabilistic predictions with confidence intervals. Parameters… (+17 more)

### Community 12 - "ExchangeAPI"
Cohesion: 0.09
Nodes (14): ExchangeAPI, get_available_exchanges(), DataFrame, CCXT Exchange Integration Provides unified interface to multiple cryptocurrency…, Fetch recent trades Args: symbol: Trading pair limit: Number of recent trades…, CCXT-based exchange interface, Get list of available trading symbols Returns: List of trading pairs, Convert OHLCV list to DataFrame Args: ohlcv: OHLCV data timeframe: Timeframe… (+6 more)

### Community 13 - "quant_math/__init__.py"
Cohesion: 0.06
Nodes (49): Quant-Math Core Package Shared domain types and protocols for the Quant-Math…, Agent, AgentRegistry, Auditor, BacktestEngine, DataProvider, MonteCarloEngine, Protocol (+41 more)

### Community 14 - "Any"
Cohesion: 0.04
Nodes (32): KnowledgeBase, Any, datetime, Hypothesis, Search hypotheses using text matching, Find similar hypotheses using semantic search, Update an existing hypothesis, Get statistics about stored hypotheses (+24 more)

### Community 15 - ".decide"
Cohesion: 0.21
Nodes (6): Any, Register/overwrite a hypothesis record in the JSONL KB., Best hypothesis for symbol by (expectancy DESC, scientific_score DESC)., Direction from momentum on real closes (lookback from params)., Run one decision cycle for a symbol., Decide for all configured symbols.

### Community 16 - "RegimeClustering"
Cohesion: 0.09
Nodes (18): ElbowMethod, ndarray, Unsupervised Regime Clustering This module provides unsupervised learning…, Fit DBSCAN and predict labels. Parameters ---------- returns : np.ndarray…, Get cluster centroids (in original feature space). Returns ------- centroids :…, Get statistics for each cluster. Parameters ---------- returns : np.ndarray…, Unsupervised clustering of market regimes. This module uses K-Means and DBSCAN…, Calculate silhouette score for clustering quality. Parameters ----------… (+10 more)

### Community 17 - "autonomous_research/__init__.py"
Cohesion: 0.07
Nodes (35): Agent Registry for managing specialized research agents. The registry maintains…, Research Manager - Main Orchestrator for AQDE. The Research Manager coordinates…, Autonomous Quant Discovery Engine (AQDE) A modular system for autonomous…, Agent, AgentMessage, Auditor, BacktestEngine, DataProvider (+27 more)

### Community 18 - "RegimeFeatureExtractor"
Cohesion: 0.09
Nodes (18): ndarray, Feature Extraction for Regime Detection This module provides feature extraction…, Extract volume-based features., Extract price-based features., Extract volatility-based features., Extract features for market regime detection. Features are based on statistical…, Extract autocorrelation features., Extract higher moments of returns distribution. (+10 more)

### Community 19 - "risk/__init__.py"
Cohesion: 0.07
Nodes (18): PositionSizer, Calculate position size based on portfolio value and risk per trade.…, Calculate fixed fractional position size. Parameters: -----------…, Position sizing calculator based on risk management., Calculate Kelly fraction. Parameters: ----------- win_rate : float Win rate…, Calculate optimal stop loss distance. Parameters: ----------- entry_price :…, Calculate stop loss as percentage of entry price., Calculate stop loss price. (+10 more)

### Community 20 - "Any"
Cohesion: 0.07
Nodes (16): Any, datetime, Fetch market data for a given symbol and date range. Args: symbol: Trading…, Extract features for a specific date/time. Features can include technical…, Get data quality metrics for a symbol. Returns completeness, accuracy, and…, Calculate win rate from trade history, Calculate Sharpe ratio, Calculate Sortino ratio (+8 more)

### Community 21 - "Any"
Cohesion: 0.14
Nodes (9): Any, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Calculate comprehensive risk metrics for strategy. Args: result: StrategyResult…, Check correlation risk with other strategies. Args: hypothesis_id: Hypothesis…, Perform stress testing on strategy. Args: result: StrategyResult from backtest…, Apply stress scenario to strategy results, Get risk check history for a hypothesis (+1 more)

### Community 22 - "Backtester"
Cohesion: 0.06
Nodes (39): Backtester, BacktestResult, PerformanceMetrics, ndarray, Backtesting & Evaluation Module This module provides backtesting and…, Run walk-forward validation. Parameters ---------- strategy_func : callable…, Represents a single trade., Grid search optimization on training data. (+31 more)

### Community 23 - "Order"
Cohesion: 0.10
Nodes (19): ExecutionStrategy, Order, Helper to set last_price after execution., Create a new order. Parameters ---------- symbol : str Trading symbol side :…, Represents a trading order., Execute an order against the market. Parameters ---------- order : Order Order…, Get order status. Parameters ---------- order_id : str Order ID Returns -------…, Execution Strategy Determines optimal execution timing and pacing. (+11 more)

### Community 24 - "test_full_system_e2e.py"
Cohesion: 0.10
Nodes (25): DataStore(), Factory: returns the SQLite-backed store when called with db_path, otherwise…, Portfolio Construction module: Efficient Frontier, Black-Litterman, Risk Parity., BlackLitterman, EfficientFrontier, OptimizationResult, Portfolio Construction Module This module provides portfolio construction and…, Compute the entire efficient frontier. Parameters ---------- n_points : int… (+17 more)

### Community 25 - "VarianceRatioTest"
Cohesion: 0.08
Nodes (17): ndarray, Statistical Tests for Market Regime Detection This module provides statistical…, Runs test for random sequence analysis. The runs test checks whether a sequence…, Perform runs test on return series. Parameters ---------- returns : np.ndarray…, Z-score based regime detection. The Z-score measures how many standard…, Check if the test result is statistically significant., Variance ratio test for mean reversion. The variance ratio test compares the…, Perform variance ratio test. Parameters ---------- returns : np.ndarray Daily… (+9 more)

### Community 26 - "PCAAnalyzer"
Cohesion: 0.12
Nodes (18): Principal Component Analysis (PCA) This module provides tools for…, compute_pca(), pca_denoising(), PCAAnalyzer, PCAResult, ndarray, PCA Analysis Module Provides Principal Component Analysis implementation for…, Transform data to PCA space. Parameters ---------- X : np.ndarray Data to… (+10 more)

### Community 27 - "AQDERunner"
Cohesion: 0.09
Nodes (19): AQDERunner, main(), Save iteration results to file, Fuerza re-descarga en el siguiente acceso (inicio de ciclo nuevo)., Datos de mercado para backtesting con cache intra-ciclo: si (symbol, timeframe,…, Print final summary of all iterations, Main runner for the Autonomous Quant Discovery Engine, Run backtests for all hypotheses of a symbol (+11 more)

### Community 28 - "StrategyResult"
Cohesion: 0.11
Nodes (10): MonteCarloResult, StrategyResult, Test statistical significance of strategy performance. Returns p-value or…, Calculate Calmar ratio, Use bootstrap resampling to estimate significance. Returns bootstrap p-value., Run Monte Carlo simulation on strategy results, Calculate Value at Risk, Calculate probability of loss (+2 more)

### Community 29 - "PeriodogramAnalyzer"
Cohesion: 0.15
Nodes (13): PeriodogramAnalyzer, ndarray, Detect seasonality in the data. Parameters ---------- data : np.ndarray Time…, Periodogram analyzer. This class performs periodogram analysis to identify…, Compute spectral flatness. Parameters ---------- data : np.ndarray Time series…, Compute spectral kurtosis. Parameters ---------- data : np.ndarray Time series…, Compute auto-correlation of power spectrum. Parameters ---------- data :…, Plot periodogram. Parameters ---------- data : np.ndarray Time series data… (+5 more)

### Community 30 - "AQDELabPanel.vue"
Cohesion: 0.08
Nodes (23): aqde, aqdePhaseClass, aqdeStatusClass, calculateProgress(), currentPhase, evaluationProgress, evolutionProgress, evolvedCount (+15 more)

### Community 31 - "DashboardView.vue"
Cohesion: 0.09
Nodes (21): aqde, aqdePhaseClass, aqdeProgress, aqdeStatusClass, events, health, hypotheses, pipelineStages (+13 more)

### Community 32 - "ndarray"
Cohesion: 0.11
Nodes (11): ndarray, Find portfolio with maximum Sharpe ratio. Returns ------- weights : np.ndarray…, Find portfolio with minimum variance. Returns ------- weights : np.ndarray…, Initialize Black-Litterman model. Two modes: Legacy mode: expected_returns :…, Optimize portfolio with views. Legacy mode: views is a dict {asset_index:…, Initialize risk parity optimizer. Parameters ---------- returns : np.ndarray…, Optimize risk parity portfolio. Parameters ---------- target_risk : float,…, Equal risk contribution portfolio. (+3 more)

### Community 33 - "HypothesisKnowledgeBase"
Cohesion: 0.11
Nodes (12): HypothesisKnowledgeBase, Any, Stub module for HypothesisKnowledgeBase to fix imports., Get timeline of hypothesis development, Export all hypotheses to a file, Import hypotheses from a file, Stub implementation of HypothesisKnowledgeBase for integration testing., Retrieve hypothesis by ID (+4 more)

### Community 34 - "Any"
Cohesion: 0.09
Nodes (13): Any, datetime, Extract technical features for a specific date. Args: symbol: Trading symbol…, Get data quality metrics. Returns completeness, accuracy, and freshness metrics., Search hypotheses using text matching, Find similar hypotheses using semantic search, Update an existing hypothesis in persistent storage. Args: hypothesis_id: ID of…, Get statistics about stored hypotheses from persistent storage (+5 more)

### Community 35 - "quant_math/expectation/__init__.py"
Cohesion: 0.09
Nodes (21): Drawdown Analyzer Module Calculates drawdown metrics for risk assessment., Expectation Calculation Module (Module 8) Statistical significance testing and…, Return Calculator Module Calculates various return metrics for trading…, Sharpe Metrics Module Calculates Sharpe, Sortino, Calmar and other risk-…, bootstrap_confidence_interval(), bootstrap_p_value(), jarque_bera_test(), one_sample_ttest() (+13 more)

### Community 36 - "StatisticalTests"
Cohesion: 0.12
Nodes (14): callable, ndarray, Collection of statistical tests for strategy validation., Paired t-test (dependent samples). Args: sample1: First sample sample2: Second…, Jarque-Bera test for normality. Args: sample: Sample data Returns: Tuple of (JB…, Calculate t-statistic for one-sample t-test., Shapiro-Wilk test for normality (approximation). Args: sample: Sample data (max…, Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:… (+6 more)

### Community 37 - "RiskManager"
Cohesion: 0.04
Nodes (47): Risk Management Module Exports, kelly_fraction(), KellyCriterion, Kelly Criterion Module Kelly criterion position sizing for optimal bet sizing., Kelly criterion position sizing., Calculate full Kelly fraction. Parameters: ----------- win_rate : float Win…, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction. (+39 more)

### Community 38 - "PowerSpectralDensity"
Cohesion: 0.14
Nodes (13): PowerSpectralDensity, ndarray, Compute spectral centroid. Parameters ---------- data : np.ndarray Time series…, Compute spectral bandwidth. Parameters ---------- data : np.ndarray Time series…, Compute spectral rolloff. Parameters ---------- data : np.ndarray Time series…, Power Spectral Density (PSD) analyzer. This class computes PSD using Welch's…, Compute spectral flux between two signals. Parameters ---------- data1 :…, Detect 1/f noise characteristics. Parameters ---------- data : np.ndarray Time… (+5 more)

### Community 39 - "get"
Cohesion: 0.08
Nodes (24): get_active_strategies(), get_autonomous_status(), get_backtest_hypotheses(), get_config_values(), get_events(), get_monitoring_flow(), get_monitoring_hypotheses(), get_monitoring_simulations() (+16 more)

### Community 40 - "useApi"
Cohesion: 0.12
Nodes (13): useApi(), useAutonomousApi(), useBacktestApi(), useConfigApi(), useDashboardApi(), useMonitoringApi(), useTradingApi(), useEquityChart() (+5 more)

### Community 41 - "KalmanFilter"
Cohesion: 0.14
Nodes (15): DenoisingKalmanFilter, design_and_apply_kalman_filter(), KalmanFilter, ndarray, Kalman Filter Module Implements Kalman filtering for state estimation and noise…, Predict state estimate forward. Parameters ---------- u : ndarray, optional…, Update state estimate with measurement. Parameters ---------- z : float or…, Apply Kalman filter to sequence of measurements. Parameters ----------… (+7 more)

### Community 42 - "QuantMathAdapter"
Cohesion: 0.08
Nodes (14): QuantMathAdapter, Get list of available trading symbols, Store hypothesis in persistent knowledge base. Args: hypothesis: Hypothesis to…, Retrieve hypothesis by ID from persistent storage, Delete a hypothesis from persistent storage, Import hypotheses from a file, Adapter for integrating AQDE with existing quant-math modules. Implements all…, Calculate win rate from trade history (+6 more)

### Community 43 - "FastFourierTransform"
Cohesion: 0.15
Nodes (13): compute_fft(), FastFourierTransform, ndarray, Fast Fourier Transform (FFT) This module provides Fast Fourier Transform…, Find dominant frequency in the data. Parameters ---------- data : np.ndarray…, Fast Fourier Transform (FFT) analyzer. This class performs FFT analysis on time…, Compute FFT spectrum (magnitude squared). Parameters ---------- data :…, Detect presence of seasonality in the data. Parameters ---------- data :… (+5 more)

### Community 44 - "PostgreSQLKnowledgeBase"
Cohesion: 0.06
Nodes (32): Exception, KBPersistence, PostgreSQLKnowledgeBase, _psycopg2(), Any, PostgreSQL-backed Knowledge Base with automatic JSONL fallback. Drop-in…, Bootstrap: if the PG table is empty but the JSONL mirror has records, import…, Return True if a healthy PG connection is present. (+24 more)

### Community 45 - "DataCleaner"
Cohesion: 0.15
Nodes (12): DataCleaner, DataFrame, ndarray, Data Cleaning Module Handles missing values, outliers, and structural breaks, Cap outliers to specified bounds Args: df: DataFrame column: Column to cap…, Data cleaning utilities for time series data, Detect and count duplicate rows Args: df: Input DataFrame Returns: DataFrame…, Remove duplicate rows Args: df: Input DataFrame subset: Columns to check for… (+4 more)

### Community 46 - "KellyCriterion"
Cohesion: 0.08
Nodes (16): AdaptiveSizer, Calculate adaptive position size. Supports two modes: Risk-based mode (keyword…, Calculate position size based on recent trade performance. Parameters:…, Adaptive position sizing based on market conditions., Calculate position size based on market regime. Parameters: ----------- regime…, KellyCriterion, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction. (+8 more)

### Community 47 - "cli/main.py"
Cohesion: 0.18
Nodes (19): ask_float(), ask_int(), _count_open_positions(), _dispatch(), _get_current_price(), main(), monitor_loop(), Quant-Math interactive CLI. Menu: 1. Iniciar Quant-Math -> config wizard, then… (+11 more)

### Community 48 - ".communicate"
Cohesion: 0.29
Nodes (4): AgentMessage, Send/receive a message, Broadcast message to all agents, Send message to specific agent

### Community 49 - "test_operation_learning.py"
Cohesion: 0.09
Nodes (29): build_trade_dataset(), encode_dataset(), encode_row(), Any, Feature store del aprendizaje no supervisado. Une el libro permanente de…, Una fila por cierre post-cutoff, enriquecida con KB + _regime., Vector fijo para clustering; None -> -1., read_closures() (+21 more)

### Community 50 - "TimeSeriesResampler"
Cohesion: 0.14
Nodes (12): DataFrame, Series, Time Series Resampling Module Provides time series aggregation and resampling…, Calculate returns from price data Args: df: Input DataFrame with price column…, Calculate volatility Args: df: Input DataFrame with price column price_col:…, Time series resampling and aggregation utilities, Shift data by specified periods Args: df: Input DataFrame cols: Columns to…, Create time-based features Args: df: Input DataFrame timestamp_col: Timestamp… (+4 more)

### Community 51 - "StatisticalTests"
Cohesion: 0.14
Nodes (12): callable, ndarray, Shapiro-Wilk test for normality. Args: sample: Sample data (max 5000…, Collection of statistical tests for strategy validation., Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:…, Bootstrap confidence interval. Args: sample: Sample data statistic: Function to…, One-sample t-test. Args: sample: Sample data popmean: Population mean to test…, Test if strategy returns are significantly different from benchmark. Args:… (+4 more)

### Community 52 - "EquityChart.vue"
Cohesion: 0.10
Nodes (15): areaPath, chartRef, colorMap, fillColor, hoverIndex, linePath, maxVal, minVal (+7 more)

### Community 53 - "TradingView.vue"
Cohesion: 0.14
Nodes (17): useTradingStore, allConfirmed, apiConfig, closePosition(), confirmations, disableTrading(), emergencyStop(), enableTrading() (+9 more)

### Community 54 - "autonomous_research/cli/__init__.py"
Cohesion: 0.16
Nodes (17): command, group, option, backtest(), cli(), discover(), export(), init_kb() (+9 more)

### Community 55 - "SharpeMetrics"
Cohesion: 0.15
Nodes (11): ndarray, Calculate Information Ratio (active return / tracking error). Args: returns:…, Calculate risk-adjusted performance metrics., Calculate Treynor ratio (excess return / beta). Args: returns: Strategy returns…, Calculate Omega ratio (probability-weighted gains / losses). Args: returns:…, Calculate all risk-adjusted metrics. Returns: Dictionary with all metrics, Calculate Sharpe ratio. Args: returns: Array of returns risk_free_rate: Risk-…, Calculate Sortino ratio (uses downside deviation). Args: returns: Array of… (+3 more)

### Community 56 - "Module Breakdown"
Cohesion: 0.06
Nodes (32): 10. Position Sizing Optimization, 11. Execution Engine, 12. Backtesting Engine, 13. Monte Carlo Simulation, 14. Continuous Optimization, 1. Data Acquisition Module, 1. Separation of Concerns, 2. Data Cleaning & Normalization (+24 more)

### Community 57 - "EmpiricalModeDecomposition"
Cohesion: 0.12
Nodes (16): design_and_apply_emd(), EmpiricalModeAnalysis, EmpiricalModeDecomposition, ndarray, Empirical Mode Decomposition Module Implements Empirical Mode Decomposition…, Interpolate between extrema using spline interpolation. Parameters ----------…, Sifting process to extract one IMF from signal. Parameters ---------- signal :…, Decompose signal into IMFs and residue. Parameters ---------- signal : array-… (+8 more)

### Community 58 - "ContinuousWaveletTransform"
Cohesion: 0.18
Nodes (11): ContinuousWaveletTransform, callable, ndarray, Compute energy spectrum from CWT. Parameters ---------- data : np.ndarray Time…, Detect transient events in the time series. Parameters ---------- data :…, Continuous Wavelet Transform (CWT) analyzer. This class performs CWT analysis…, Plot CWT coefficients. Parameters ---------- data : np.ndarray Time series data…, Plot time-frequency heatmap with CWT coefficients. Parameters ---------- data :… (+3 more)

### Community 59 - "AutonomousView.vue"
Cohesion: 0.12
Nodes (16): activeHypotheses, activity, availableSymbols, config, iteration, maxIterations, phase, progress (+8 more)

### Community 60 - "AgentRegistry"
Cohesion: 0.10
Nodes (15): Agent, AgentRegistry, AgentMessage, Any, Send a message to a specific agent. Args: sender: Sending agent receiver_id:…, Get message history. Args: agent_id: Filter by sender/receiver ID (optional)…, Get registry statistics. Returns: Dictionary with statistics about registered…, Get list of all registered agents with details. Returns: List of agent… (+7 more)

### Community 61 - "StructuralBreakDetector"
Cohesion: 0.18
Nodes (11): DataFrame, Series, Structural Break Detection Module Detects changes in data distribution and…, Detect regime changes in time series Args: df: Input DataFrame col: Column to…, Detect structural breaks in time series data, Test stationarity of time series Args: df: Input DataFrame col: Column to test…, Detect changes in trend using linear regression Args: df: Input DataFrame col:…, Comprehensive structural break analysis Args: df: Input DataFrame col: Column… (+3 more)

### Community 62 - "routes.py"
Cohesion: 0.12
Nodes (16): put, API Routes for Quant-Math WebUI, # TODO: Connect to actual AQDE state, # TODO: Connect to actual paper trading engine, # TODO: Connect to hypothesis database, # TODO: Connect to event store, # TODO: Connect to actual strategy manager, # TODO: Load from actual config store (+8 more)

### Community 63 - "Hypothesis"
Cohesion: 0.10
Nodes (12): Hypothesis, KnowledgeBase, Port for hypothesis knowledge management. Adapters implement this to store,…, Store a hypothesis and return its ID, Retrieve a hypothesis by ID, Search hypotheses based on criteria. Criteria can include: - strategy_type -…, Update an existing hypothesis, Get statistics about stored hypotheses (+4 more)

### Community 64 - "DrawdownAnalyzer"
Cohesion: 0.16
Nodes (11): DrawdownAnalyzer, Any, ndarray, Calculate average drawdown duration., Calculate maximum drawdown duration., Calculate Ulcer Index (root mean square of drawdowns). Ulcer Index =…, Analyze drawdowns from equity curve or returns., Calculate drawdown series and metrics from equity curve. Args: equity_curve:… (+3 more)

### Community 65 - "ReturnCalculator"
Cohesion: 0.17
Nodes (10): Any, ndarray, Calculate various return metrics from trade history or price series., Calculate returns from trade history. Args: trades: List of trade dictionaries…, Calculate cumulative return from returns series., Calculate annualized return., Calculate geometric mean of returns., Calculate arithmetic mean of returns. (+2 more)

### Community 66 - "Orchestrator"
Cohesion: 0.14
Nodes (8): Orchestrator, Advisory ML reordering of candidate hypotheses (gate untouched)., Generate N hypotheses across configured symbols and backtest them., Convert an AQDE backtest result into a KB JSONL record., Fill a paper trade at the signal price with configured sizing/TP., generate -> persist -> decide -> paper execute -> feedback., Continuous loop (Ctrl+C to stop)., Continuous generation -> decision -> feedback loop.

### Community 67 - "HarmonicComponentAnalyzer"
Cohesion: 0.18
Nodes (10): HarmonicComponentAnalyzer, ndarray, Reconstruct signal from top harmonics. Parameters ---------- data : np.ndarray…, Harmonic component analyzer. This class identifies and analyzes harmonic…, Compute ratio between harmonic components. Parameters ---------- data :…, Analyze periodicity in the data. Parameters ---------- data : np.ndarray Time…, Plot harmonic components. Parameters ---------- data : np.ndarray Time series…, Plot frequency spectrum highlighting harmonics. Parameters ---------- data :… (+2 more)

### Community 68 - "MiniChart.vue"
Cohesion: 0.11
Nodes (14): areaPath, colorMap, fillColor, hoverPoint, linePath, maxVal, minVal, points (+6 more)

### Community 69 - "MonitoringView.vue"
Cohesion: 0.11
Nodes (15): filteredHypotheses, flow, hypFilter, hypotheses, hypothesisStatuses, loading, simulationGroups, simulations (+7 more)

### Community 70 - "Normalizer"
Cohesion: 0.20
Nodes (10): Normalizer, DataFrame, Data Normalization Module Provides multiple normalization and scaling methods, Standardize multiple columns Args: df: Input DataFrame method: 'zscore',…, Data normalization and scaling utilities, Normalize all numerical columns Args: df: Input DataFrame method: Normalization…, Inverse transform normalized data Args: df_norm: Normalized DataFrame scaler:…, Min-Max normalization Args: df: Input DataFrame feature_range: Desired range… (+2 more)

### Community 71 - "StopLoss"
Cohesion: 0.21
Nodes (9): Any, Stop loss calculator with multiple methods. Supports: - Fixed percentage - ATR-…, Chandelier exit stop loss., Volatility-adjusted stop loss., Calculate multiple stop loss levels. Args: entry_price: Entry price side:…, Initialize stop loss calculator. Args: default_method: Default stop loss method…, Calculate stop loss price. Args: entry_price: Entry price side: 'long' or…, Fixed percentage stop loss. (+1 more)

### Community 72 - "ndarray"
Cohesion: 0.15
Nodes (10): ndarray, Calculate both VaR and ES. Parameters ---------- returns : np.ndarray…, Initialize portfolio risk analyzer. Supports two modes: Returns mode (legacy):…, Derive the correlation matrix from a covariance matrix., Stress Testing and Scenario Analysis Tests portfolio performance under extreme…, Initialize stress tester. Parameters ---------- returns : np.ndarray, optional…, Generate historical scenarios (bootstrap). Parameters ---------- data :…, Generate industry standard stress scenarios. Typical stress scenarios: - Market… (+2 more)

### Community 73 - "BandPassFilter"
Cohesion: 0.16
Nodes (11): BandPassFilter, design_and_apply_band_pass(), ndarray, Band-Pass Filter Module Implements band-pass filters to retain only specific…, Apply band-pass filter to input data. Parameters ---------- data : array-like…, Apply filter in real-time with phase delay (for online applications).…, Compute frequency response of the band-pass filter. Returns ------- w : ndarray…, Analyze signal power in passband vs stopbands. Parameters ----------… (+3 more)

### Community 74 - "HighPassFilter"
Cohesion: 0.16
Nodes (11): design_and_apply_high_pass(), HighPassFilter, ndarray, High-Pass Filter Module Implements high-pass filters to remove low-frequency…, Apply filter using zero-pole-gain representation (more stable for long data).…, Compute frequency response of the filter. Returns ------- w : ndarray Angular…, Analyze signal bandwidth before and after filtering. Parameters ----------…, Convenience function to design and apply high-pass filter in one step.… (+3 more)

### Community 75 - "MultiSelect.vue"
Cohesion: 0.17
Nodes (15): closeDropdown(), containerRef, emit, filteredOptions, focused, handleClickOutside(), handleKeydown(), hoveredIndex (+7 more)

### Community 76 - "ConfigView.vue"
Cohesion: 0.16
Nodes (14): useConfigStore, config, loadConfig(), loading, resetConfig(), saveConfig(), saving, sections (+6 more)

### Community 77 - "BacktestView.vue"
Cohesion: 0.12
Nodes (12): backtestStore, configStore, configValues, effectiveConfig, error, form, hypotheses, loadingDetail (+4 more)

### Community 78 - "spectral_analysis/__main__.py"
Cohesion: 0.22
Nodes (15): example_fft_analysis(), example_harmonic_analysis(), example_periodogram_analysis(), example_psd_analysis(), example_wavelet_analysis(), generate_sample_data(), main(), ndarray (+7 more)

### Community 79 - "HypothesisPrior"
Cohesion: 0.12
Nodes (23): build_prior_from_kb(), HypothesisPrior, _norm_type(), Any, Hypothesis generation prior learned from historical backtest outcomes. Learns…, Load every historical record (PG first, JSONL fallback) and fit., Explainable positive-expectancy prior over (strategy_type, symbol)., Shrunk estimate of P(expectancy>0); fully explainable formula. (+15 more)

### Community 80 - "ExchangeManager"
Cohesion: 0.14
Nodes (8): ExchangeManager, Register an exchange. Parameters: ----------- name : str Exchange name api_key…, Set the active exchange. Parameters: ----------- name : str Exchange name…, Get the active exchange configuration., Manage multiple cryptocurrency exchanges., Place an order. Parameters: ----------- symbol : str Trading symbol (e.g.,…, Initialize exchange manager., Cancel an order. Parameters: ----------- order_id : str Order ID Returns:…

### Community 81 - "post"
Cohesion: 0.13
Nodes (15): post, close_position(), disable_trading(), emergency_stop(), enable_trading(), Save configuration values., Stop autonomous mode., Enable real trading with Bybit. (+7 more)

### Community 82 - "PositionSizer"
Cohesion: 0.21
Nodes (9): PositionSizer, Any, Volatility targeting position sizing., Unified position sizing calculator. Supports multiple sizing algorithms: -…, ATR-based position sizing., Initialize position sizer. Args: default_method: Default sizing method…, Calculate position size based on method. Args: account_value: Total account…, Fixed fractional position sizing. (+1 more)

### Community 83 - "Any"
Cohesion: 0.14
Nodes (9): Any, Parametric VaR (assuming Student's t distribution). Parameters ----------…, Historical VaR (empirical method). Two call styles: Instance style:…, Calculate Conditional Tail Expectation (Expected Shortfall). Parameters…, Result of VaR calculation., Calculate concentration risk metrics. Returns ------- metrics : dict…, Parametric VaR (assuming normal distribution). Formula: VaR = mu - z_alpha *…, Monte Carlo stress testing. Parameters ---------- n_scenarios : int Number of… (+1 more)

### Community 84 - "WaveletDenoiser"
Cohesion: 0.19
Nodes (10): design_and_apply_wavelet_denoise(), ndarray, Wavelet Decomposition Module Implements wavelet-based denoising and signal…, Denoise signal using wavelet thresholding. Parameters ---------- signal :…, Get multi-resolution analysis information. Parameters ---------- signal :…, Convenience function to denoise signal in one step. Parameters ----------…, Wavelet-based denoising and signal decomposition. This class implements wavelet…, Initialize wavelet denoiser. Parameters ---------- wavelet : str, optional… (+2 more)

### Community 85 - "App.vue"
Cohesion: 0.14
Nodes (10): isDark, navItems, route, router, store, wsStatus, app, pinia (+2 more)

### Community 86 - "expectation/statistical_tests.py"
Cohesion: 0.12
Nodes (15): bootstrap_confidence_interval(), bootstrap_p_value(), one_sample_ttest(), paired_ttest(), Statistical Tests Module Statistical significance testing for trading strategy…, Convenience function for one-sample t-test., Convenience function for two-sample t-test., Convenience function for paired t-test. (+7 more)

### Community 87 - ".run_backtest"
Cohesion: 0.19
Nodes (8): DataFrame, ndarray, Generate synthetic OHLCV data for dry-run / testing. Uses a random walk with…, Calculate Stochastic %K and %D indicators, Calculate Volume Weighted Average Price, Calculate Donchian channels (upper and lower), Calculate Average True Range, Run backtest using quant-math backtester. Args: hypothesis: Hypothesis dict…

### Community 88 - "Quant-Math + AQDE Consolidated Architecture Guide"
Cohesion: 0.07
Nodes (27): Action Plan (Implementation Steps), Appendix: File-by-File Mapping, AQDE → Quant-Math Core (Duplicates Eliminated), Backward Compatibility, Broken / Orphaned Files (Cleanup Required), Core Dependencies (Required — Always Installed), Current Problems Identified, Duplicate Implementations (Must Consolidate) (+19 more)

### Community 89 - "PortfolioRisk"
Cohesion: 0.22
Nodes (13): example_expected_shortfall(), example_portfolio_risk(), example_risk_budgeting(), example_stress_testing(), example_var_calculation(), main(), Example: Portfolio risk analysis., Example: Risk budgeting and allocation. (+5 more)

### Community 90 - "signal_processing/__main__.py"
Cohesion: 0.20
Nodes (13): example_band_pass_filter(), example_emd(), example_high_pass_filter(), example_kalman_filter(), example_wavelet_denoising(), generate_test_signal(), Signal Processing Module Example Usage This module demonstrates how to use the…, Example: Band-pass filtering to isolate specific frequency bands. (+5 more)

### Community 91 - "ActiveStrategiesPanel.vue"
Cohesion: 0.14
Nodes (9): activeCount, avgSharpe, selectedStrategy, statusLabels, stopStrategy(), store, strategies, totalPnL (+1 more)

### Community 92 - "stores/index.js"
Cohesion: 0.25
Nodes (10): useWebSocket(), clearTimers(), connect(), disconnect(), scheduleReconnect(), send(), useAutonomousStore, useBacktestStore (+2 more)

### Community 93 - "BaseModel"
Cohesion: 0.17
Nodes (13): BaseModel, AutonomousConfig, BacktestRequest, BacktestResponse, ConfigSection, Event, get_config_sections(), Hypothesis (+5 more)

### Community 94 - "format"
Cohesion: 0.17
Nodes (10): format, formatTime(), emit, formatDate(), formatDateTime(), props, statusLabels, formatTime() (+2 more)

### Community 95 - "ControlButtons.vue"
Cohesion: 0.23
Nodes (12): autonomousLoading, emit, emitAutonomous(), emitBacktest(), emitRealTrading(), emitRestart(), emitStart(), emitStop() (+4 more)

### Community 96 - "expectation/__init__.py"
Cohesion: 0.18
Nodes (7): Calculate Sharpe ratio. Parameters: ----------- returns : List[float] Period…, Calculate Sortino ratio (downside deviation). Parameters: ----------- returns :…, Calculate Sharpe ratio and related metrics., Calculate information ratio. Parameters: ----------- returns : List[float]…, SharpeMetrics, jarque_bera_test(), Convenience function for Jarque-Bera test.

### Community 98 - "aqde_runner.py"
Cohesion: 0.12
Nodes (9): Adapters for AQDE - Implementation of hexagonal architecture ports. These…, Risk Manager Implementation. Implements the RiskManager port for risk…, MonteCarloResult, Result of Monte Carlo simulation. Provides statistical distribution of strategy…, Test statistical significance of strategy performance. Returns p-value or…, Run Monte Carlo simulation on strategy performance. Uses bootstrapping or…, Run Monte Carlo simulation on strategy results, Result of backtesting a hypothesis/strategy. Contains performance metrics and… (+1 more)

### Community 99 - "risk_management.py"
Cohesion: 0.18
Nodes (7): Risk Management Module This module provides comprehensive risk measurement and…, Risk Management Module This module provides comprehensive risk measurement and…, Risk Budgeting and Allocation Allocates risk budgets across portfolio assets., Initialize risk budget allocator. Parameters ---------- target_var : float…, Allocate risk equally across assets. Parameters ---------- returns : np.ndarray…, Calculate optimal risk allocation using optimization. Parameters ----------…, RiskBudget

### Community 100 - "ValueAtRisk"
Cohesion: 0.20
Nodes (7): Calculate component VaR (marginal VaR). Parameters ---------- returns :…, Calculate diversification benefit. Benefit = (sum of individual VaR) -…, Calculate comprehensive portfolio risk metrics. Parameters ----------…, Value at Risk (VaR) Calculator Computes VaR at various confidence levels using…, Calculate marginal contributions to VaR. Parameters ---------- returns :…, Initialize VaR calculator. Parameters ---------- confidence_level : float…, ValueAtRisk

### Community 101 - "ReturnCalculator"
Cohesion: 0.18
Nodes (6): Calculate simple returns from price series. Parameters: ----------- prices :…, Calculate log returns from price series. Parameters: ----------- prices :…, Calculate annualized return. Parameters: ----------- returns : List[float]…, Calculate various return metrics., Calculate cumulative return from price series. Parameters: ----------- prices :…, ReturnCalculator

### Community 102 - "DrawdownAnalyzer"
Cohesion: 0.18
Nodes (6): DrawdownAnalyzer, Calculate drawdowns from price series. Parameters: ----------- prices :…, Calculate maximum drawdown. Parameters: ----------- drawdowns : List[float]…, Calculate average drawdown. Parameters: ----------- drawdowns : List[float]…, Analyze drawdowns from price series., Calculate drawdown duration (time from peak to valley). Parameters: -----------…

### Community 103 - "System Dependency Map — Quant-Math + AQDE Ecosystem"
Cohesion: 0.08
Nodes (23): AQDE (autonomous-research) — Essential Files, AQDE — Missing Dependencies, AQDE — Optional / Standalone Scripts, AQDE — Orphaned / Unreferenced / Broken, AQDE `requirements_simplified.txt` (More current), AQDE `requirements.txt`, AQDE — Shared Files (Used by Both Systems), Architecture Overview (+15 more)

### Community 104 - "DecisionEngine"
Cohesion: 0.13
Nodes (10): Decision Engine: expectancy-gated trade decision loop over AQDE hypotheses., DecisionEngine, _learn_mode_default(), Trading Decision Engine. Selects the best hypothesis per symbol from the JSONL-…, SL obligatorio 2:1 — siempre take_profit_pct / 2, sin excepcion., SL vigente EN el momento de la entrada para key, derivado del take_profit_price…, Umbrales TP/SL de la posicion. Prioridad: los guardados al abrir la posicion ->…, Comprueba precio actual vs entrada para cada posicion abierta del simbolo y… (+2 more)

### Community 105 - "quant_math/__main__.py"
Cohesion: 0.27
Nodes (9): list_modules(), main(), QUANT-MATH Main Entry Point Unified CLI entry point for the QUANT-MATH…, List available modules with descriptions., Main CLI entry point., Run integration tests., Show framework information., run_tests() (+1 more)

### Community 106 - "ExpectedShortfall"
Cohesion: 0.22
Nodes (6): ExpectedShortfall, Expected Shortfall (ES) Calculator Computes Expected Shortfall at various…, Initialize ES calculator. Parameters ---------- confidence_level : float…, Historical ES calculation. Two call styles: Instance style:…, Parametric ES (assuming normal distribution). Formula: ES = mu - sigma *…, Conditional Tail Expectation (ES) calculation. Parameters ---------- returns :…

### Community 107 - "QUANT-MATH: Professional Quantitative Trading Research System"
Cohesion: 0.10
Nodes (20): Architecture, Citation, Core Principles, Disclaimer, Documentation, Getting Started, Key Methodologies, License (+12 more)

### Community 108 - "HiddenMarkovModel"
Cohesion: 0.33
Nodes (3): HiddenMarkovModel, ndarray, test_regime_detection()

### Community 109 - "ValueAtRisk"
Cohesion: 0.31
Nodes (3): ndarray, test_var(), ValueAtRisk

### Community 110 - "ConnectionStatus.vue"
Cohesion: 0.22
Nodes (8): autonomousStore, currentStore, dashboardStore, monitoringStore, route, routeStoreMap, statusClass, statusText

### Community 111 - "ml_quant/__main__.py"
Cohesion: 0.36
Nodes (7): main(), Example: Risk factor model., Example: Feature engineering., Example: ML-based portfolio optimization., test_factor_model(), test_feature_engineering(), test_ml_portfolio()

### Community 112 - "SQLiteDataStore"
Cohesion: 0.11
Nodes (11): PostgreSQL Database Connector Provides data storage and retrieval with metadata…, DataFrame, SQLite-backed data store for local / mobile environments. Provides the same…, SQLite data store with DataFrame support., Initialize SQLite connection. Args: db_path: Path to the SQLite database file, Save a DataFrame to a table. Args: table_name: Target table name df: DataFrame…, Execute a SQL query and return the result as a DataFrame. Args: sql: SQL query…, Execute a raw SQL statement and commit. (+3 more)

### Community 113 - "portfolio_construction/__main__.py"
Cohesion: 0.36
Nodes (7): main(), Example: Risk Parity Portfolio., Example: Efficient Frontier., Example: Black-Litterman Model., test_black_litterman(), test_efficient_frontier(), test_risk_parity()

### Community 114 - "SearchCriteria"
Cohesion: 0.50
Nodes (3): Search criteria for hypothesis search, SearchCriteria, Search hypotheses based on criteria. Args: criteria: Search criteria dictionary…

### Community 115 - "Quant-Math Architecture Reuse Analysis Report"
Cohesion: 0.11
Nodes (17): 1. Backtesting Engine (`backtesting/backtester.py`), 2. Data Acquisition (`data_acquisition/data_sources/exchanges.py`), 3. Risk Management (`quant_math/risk/`), 4. Statistical Analysis (`quant_math/expectation/`), 5. Monte Carlo (`quant_math/monte_carlo/simulator.py`), 6. Autonomous Research (`quant_math/autonomous_research/`), Conclusion, Executive Summary (+9 more)

### Community 116 - "RuntimeState"
Cohesion: 0.15
Nodes (8): _orchestrator_process_main(), Tracks the background orchestrator process., Arranca la microVM de PostgreSQL si no responde; si falla, sigue con fallback a…, Apaga la microVM de PostgreSQL: 'quit' por el FIFO de control del driver; si el…, Aggressive escalating stop: SIGINT -> SIGTERM -> SIGKILL, <10s worst case., Best-effort: reflect STOPPED in runtime_stats.json., Child process: run the orchestrator loop with all output to quant_math.log., RuntimeState

### Community 117 - "spectral_analysis/__init__.py"
Cohesion: 0.20
Nodes (5): Harmonic Component Analysis This module provides harmonic component analysis…, Spectral Analysis This module provides frequency domain analysis techniques…, Periodogram Analysis This module provides periodogram-based frequency analysis…, Power Spectral Density (PSD) This module provides Power Spectral Density…, Continuous Wavelet Transform (CWT) This module provides Continuous Wavelet…

### Community 118 - "✅ Completed Modules"
Cohesion: 0.11
Nodes (17): 1. Expectation Module (`expectation/`), 2. Risk Module (`risk/`), 3. Optimization Module (`optimization/`), 4. Execution Module (`execution/`), 5. Backtesting Module (`backtesting/`), 6. Master Module (`__init__.py`), Backtesting, ✅ Completed Modules (+9 more)

### Community 119 - "Settings"
Cohesion: 0.33
Nodes (5): BaseSettings, Config, Quant-Math WebUI Backend Configuration, Application settings loaded from environment variables., Settings

### Community 120 - "test_risk_persistence.py"
Cohesion: 0.26
Nodes (15): flat_candles(), make(), Riesgo + persistencia de posiciones: SL 2:1 obligatorio, cierres TP/SL en el…, TP tambien cierra; el libro es append-only y nunca se resetea., Deja en el estado una posicion abierta como si viniera de sesion previa., SL = TP/2 exacto para cualquier TP configurado., Posicion abierta -> 'reinicio' -> se recupera, guarda y sigue monitoreando., Precio cae al nivel del SL -> cierre con motivo='sl' en el libro. (+7 more)

### Community 121 - "ParameterField.vue"
Cohesion: 0.47
Nodes (5): emit, handleChange(), handleInput(), props, showPassword

### Community 122 - "._calculate_emas"
Cohesion: 0.40
Nodes (3): Series, Calculate RSI indicator, Calculate multiple EMA windows

### Community 123 - "ArchitecturalViolationTracker"
Cohesion: 0.40
Nodes (3): ArchitecturalViolationTracker, Tracks if any module accesses code outside quant_math/**, Check if an import violates architectural boundaries

### Community 125 - ".fetch_top_symbols"
Cohesion: 0.50
Nodes (3): CryptoSymbol, Fetch top N symbols by volume from Bybit, Represents a crypto trading pair with metadata

### Community 128 - ".create_hypotheses_for_symbol"
Cohesion: 0.20
Nodes (6): Any, Generate base hypothesis configurations for a symbol, Generate new hypotheses based on performance feedback - ENHANCED, Closes recientes REALES para los modelos; cache por ciclo., Create and register hypotheses for a symbol, Analyze performance of hypotheses for a symbol

### Community 129 - "PortfolioRiskResult"
Cohesion: 0.50
Nodes (3): PortfolioRiskResult, Result of portfolio risk analysis., Dict-like access to result fields (e.g. 'var_95' -> total_var).

### Community 130 - "Button.vue"
Cohesion: 0.50
Nodes (3): props, sizeClass, variantClass

### Community 132 - "MetricCard.vue"
Cohesion: 0.50
Nodes (3): formattedValue, props, valueColor

### Community 133 - "StageColumn.vue"
Cohesion: 0.67
Nodes (3): emit, props, selectItem()

### Community 134 - "SystemStatusIndicator.vue"
Cohesion: 0.50
Nodes (3): statusClass, statusText, store

### Community 137 - "generate_model_hypotheses"
Cohesion: 0.25
Nodes (8): analyze_series(), generate_model_hypotheses(), Generador de hipotesis basado en modelos cientificos (ARIMA/GARCH). Conecta los…, ARIMA(1,1,0): signo del forecast; GARCH(1,1): percentil de la volatilidad…, Devuelve plantillas compatibles con create_hypotheses_for_symbol. Regla…, Model-based generator: flag activo, plantillas ejecutables, degradacion., test_generates_executable_templates(), test_short_series_returns_empty()

### Community 138 - "test_family_feedback.py"
Cohesion: 0.35
Nodes (10): flat(), make(), Opcion B: feedback agregado por FAMILIA x SIMBOLO. Las keys rotan (cada una con…, 3 cierres de la MISMA familia (keys rotando o no): la familia llega a 3 ops ->…, n=3 entrega; n=6 vuelve a entregar (bucket 2)., El contrato original por-key (min=3) NO cambia: con 1 op no entrega., seed_hyp(), test_bucket_multiple_delivers_again() (+2 more)

### Community 139 - "websocket_endpoint"
Cohesion: 0.67
Nodes (3): websocket, WebSocket endpoint for real-time updates., websocket_endpoint()

### Community 140 - "simulator.py"
Cohesion: 0.29
Nodes (8): Monte Carlo Module Exports, bootstrap_simulation(), calculate_var_es(), parametric_simulation(), Monte Carlo Simulation Engine Unified Monte Carlo simulation for backtest…, Bootstrap resampling of returns. Args: returns: Array of returns n_iterations:…, Parametric simulation assuming normal distribution. Args: returns: Array of…, Calculate VaR and Expected Shortfall. Args: returns: Array of returns…

### Community 141 - "test_decision_engine.py"
Cohesion: 0.33
Nodes (9): make_engine(), Decision Engine behavior tests: abstention (no_entry) and operation (entry)., All hypotheses with expectancy <= 0 -> no_entry, zero signals., One hypothesis with expectancy > 0 -> entry signal generated., Low scientific_score degrades to failed but stays queryable; ordering by…, run_all(), test_abstention_all_nonpositive_expectancy(), test_failed_status_still_queryable_and_best_selection_ordering() (+1 more)

### Community 143 - ".__init__"
Cohesion: 0.29
Nodes (6): BacktestEngine, KnowledgeBase, MonteCarloEngine, RiskManager, Initialize the Research Manager. Args: knowledge_base: Port for hypothesis…, StatisticalValidator

### Community 144 - ".fetch_balance"
Cohesion: 0.29
Nodes (4): Any, Fetch order book data Args: symbol: Trading pair limit: Number of depth levels…, Fetch current ticker information Args: symbol: Trading pair Returns: Ticker…, Fetch account balance Returns: Balance information dictionary

### Community 145 - ".close_position"
Cohesion: 0.29
Nodes (3): Reescribe positions.jsonl con las posiciones vivas (atomico)., Cierra una posicion: la quita del estado vivo y la registra en el libro de…, Cantidad/notional de la ultima entrada abierta para key segun el libro…

### Community 163 - "._maybe_deliver_family_feedback"
Cohesion: 0.33
Nodes (3): Cierres del simbolo en el libro (todas las familias)., Operaciones cerradas de la familia+simbolo segun el libro permanente (fuente…, Entrega feedback AGREGADO por familia cuando las operaciones de esa familia…

### Community 164 - "get_health"
Cohesion: 0.67
Nodes (3): get_health(), HealthResponse, Get system health metrics.

### Community 165 - "ResearchPhase"
Cohesion: 0.40
Nodes (4): Enum, Phases of the research workflow, Set current research phase, ResearchPhase

### Community 166 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 167 - "get_aqde_status"
Cohesion: 0.67
Nodes (3): AQDEStatus, get_aqde_status(), Get AQDE autonomous mode status.

### Community 168 - "get_trading_metrics"
Cohesion: 0.67
Nodes (3): get_trading_metrics(), Get paper trading metrics., TradingMetrics

## Knowledge Gaps
- **323 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `quant-math`, `quant-math-webui`, `Config` (+318 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExchangeAPI` connect `ExchangeAPI` to `.create_hypotheses_for_symbol`, `aqde_runner.py`, `DecisionEngine`, `QuantMathAdapter`, `.fetch_balance`, `Backtester`, `test_full_system_e2e.py`, `AQDERunner`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `DecisionEngine` connect `DecisionEngine` to `Orchestrator`, `._maybe_deliver_family_feedback`, `test_family_feedback.py`, `ExchangeAPI`, `PostgreSQLKnowledgeBase`, `test_decision_engine.py`, `.decide`, `HypothesisPrior`, `.close_position`, `test_operation_learning.py`, `test_risk_persistence.py`, `AQDERunner`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `ResearchManager` connect `ResearchManager` to `aqde_runner.py`, `ResearchPhase`, `quant_math/__init__.py`, `.__init__`, `autonomous_research/__init__.py`, `Backtester`, `test_full_system_e2e.py`, `AgentRegistry`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `QuantMathAdapter` (e.g. with `ExchangeAPI` and `OrderManager`) actually correct?**
  _`QuantMathAdapter` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DecisionEngine` (e.g. with `ExchangeAPI` and `KBPersistence`) actually correct?**
  _`DecisionEngine` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `run_full_e2e_test()` (e.g. with `StrategyType` and `ExpectedShortfall`) actually correct?**
  _`run_full_e2e_test()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `OrderManager` (e.g. with `AlgoTradingSystem` and `POV`) actually correct?**
  _`OrderManager` has 4 INFERRED edges - model-reasoned connections that need verification._