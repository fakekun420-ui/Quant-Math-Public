# Graph Report - Quant-Math-Public  (2026-08-23)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2619 nodes · 4017 edges · 165 communities (152 shown, 13 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 82 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `02c3910a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 154
- Community 155
- Community 163
- Community 164

## God Nodes (most connected - your core abstractions)
1. `QuantMathAdapter` - 51 edges
2. `run_full_e2e_test()` - 39 edges
3. `OrderManager` - 31 edges
4. `RiskManager` - 25 edges
5. `RiskManagementEngine` - 24 edges
6. `DecisionEngine` - 23 edges
7. `ResearchManager` - 22 edges
8. `HypothesisKnowledgeBase` - 22 edges
9. `ExchangeAPI` - 21 edges
10. `AQDERunner` - 21 edges

## Surprising Connections (you probably didn't know these)
- `POV` --uses--> `Order`  [INFERRED]
  algo_trading/algo_trading.py → order_management/order_management.py
- `VWAP` --uses--> `Order`  [INFERRED]
  algo_trading/algo_trading.py → order_management/order_management.py
- `QuantMathAdapter` --uses--> `OrderManager`  [INFERRED]
  quant_math/autonomous_research/adapters/quant_math_adapter.py → order_management/order_management.py
- `run_full_e2e_test()` --uses--> `ValueAtRisk`  [INFERRED]
  test_full_system_e2e.py → risk_management/risk_management.py
- `run_full_e2e_test()` --uses--> `ExpectedShortfall`  [INFERRED]
  test_full_system_e2e.py → risk_management/risk_management.py

## Import Cycles
- None detected.

## Communities (165 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (32): Regime Detection Module This module provides tools for detecting and analyzing…, example_clustering(), example_hmm(), main(), Example: Hidden Markov Model regime detection., Example: Regime clustering., HiddenMarkovModel, ndarray (+24 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (33): AlgoExecution, AlgoTradingSystem, POV, Order, Algorithmic Trading System This module provides algorithmic trading…, Volume-Weighted Average Price (VWAP) Splits order based on expected market…, Result of algorithmic execution., Execute order using VWAP. Parameters ---------- order : Order Order to execute… (+25 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (29): BacktestEngine, KnowledgeBase, MonteCarloEngine, AgentRegistry, Registry for managing specialized research agents. Maintains a registry of…, Clear all message history, Initialize the agent registry, Unregister an agent. Args: agent_id: ID of agent to unregister Returns: True if… (+21 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (43): axios, chart.js, chartjs-adapter-date-fns, d3, date-fns, eslint, eslint-config-prettier, eslint-plugin-prettier (+35 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (24): Any, RiskManager, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Implementation of RiskManager port. Provides risk management functionality…, Check if drawdown is within acceptable limits. Args: hypothesis_id: Hypothesis…, Check if Sharpe ratio meets threshold. Args: sharpe_ratio: Sharpe ratio to…, Check if Sortino ratio meets threshold. Args: sortino_ratio: Sortino ratio to… (+16 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (24): _PostgreSQLDataStore, Any, DataFrame, PostgreSQL Database Connector Provides data storage and retrieval with metadata…, Query data from database Args: query: SQL query string params: Query parameters…, Get schema information for a table Args: table: Table name Returns: List of…, Check data quality for a table Args: table: Table name columns: Specific…, Remove data older than specified threshold Args: table: Table name… (+16 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (22): EWMAVolatility, GARCHModel, ndarray, Volatility Clustering Analysis This module provides methods to detect and…, Detect volatility clusters using rolling volatility. Parameters ----------…, Test for ARCH effects (autoregressive conditional heteroskedasticity). The…, Check if ARCH effects are present (indicating volatility clustering).…, Calculate the ratio of high volatility variance to low volatility variance.… (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (24): FeatureEngineer, MLPortfolioOptimizer, MLPortfolioResult, ndarray, Machine Learning for Quant Module This module provides machine learning tools…, Add cross-asset features (e.g., spread, correlation). Parameters ----------…, Get feature importance from trained model. Parameters ---------- model : Any…, Machine Learning Portfolio Optimizer Uses ML-based constraints and risk models. (+16 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (26): AsyncSession, FastAPI, get_db(), init_db(), Database Module for WebUI Backend, Initialize database tables., Get database session., WebSocket (+18 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (25): Monte Carlo Module Exports, bootstrap_simulation(), calculate_var_es(), MonteCarloSimulator, parametric_simulation(), Any, MonteCarloResult, ndarray (+17 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (25): Order, OrderType, Enum, Initialize order. Parameters: ----------- symbol : str Trading symbol side :…, Validate order parameters. Returns: -------- bool True if valid, Supported order types., OrderRouter, Order (+17 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (24): ARCHModel, ARIMAModel, ARIMAResult, GARCHModel, Any, ndarray, Statistical Models for Probabilistic Forecasting This module provides time…, Generate probabilistic predictions with confidence intervals. Parameters… (+16 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (20): ExchangeAPI, get_available_exchanges(), Any, DataFrame, CCXT Exchange Integration Provides unified interface to multiple cryptocurrency…, Fetch order book data Args: symbol: Trading pair limit: Number of depth levels…, Fetch current ticker information Args: symbol: Trading pair Returns: Ticker…, Fetch recent trades Args: symbol: Trading pair limit: Number of recent trades… (+12 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (27): Quant-Math Core Package Shared domain types and protocols for the Quant-Math…, BacktestEngine, MonteCarloEngine, Quant-Math Core Protocols Hexagonal architecture ports that separate the domain…, Port for backtesting hypotheses. Adapters implement this to execute backtests…, Port for Monte Carlo simulation. Adapters implement this to run Monte Carlo…, AgentMessage, Hypothesis (+19 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (11): KnowledgeBase, Hypothesis, Search hypotheses using text matching, Find similar hypotheses using semantic search, Get timeline of hypothesis development, Import hypotheses from a file, Optimize hypothesis parameters over a search space. Returns the best parameters…, Port for hypothesis knowledge management. Adapters implement this to store,… (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (18): Decision Engine: expectancy-gated trade decision loop over AQDE hypotheses., DecisionEngine, Any, Register/overwrite a hypothesis record in the JSONL KB., Best hypothesis for symbol by (expectancy DESC, scientific_score DESC)., Direction from momentum on real closes (lookback from params)., Run one decision cycle for a symbol., Expectancy-gated decision loop. For each configured symbol: 1. Pick best… (+10 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (18): ElbowMethod, ndarray, Unsupervised Regime Clustering This module provides unsupervised learning…, Fit DBSCAN and predict labels. Parameters ---------- returns : np.ndarray…, Get cluster centroids (in original feature space). Returns ------- centroids :…, Get statistics for each cluster. Parameters ---------- returns : np.ndarray…, Unsupervised clustering of market regimes. This module uses K-Means and DBSCAN…, Calculate silhouette score for clustering quality. Parameters ----------… (+10 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (23): Agent Registry for managing specialized research agents. The registry maintains…, Enum, Research Manager - Main Orchestrator for AQDE. The Research Manager coordinates…, Phases of the research workflow, ResearchPhase, Autonomous Quant Discovery Engine (AQDE) A modular system for autonomous…, AgentMessage, DataProvider (+15 more)

### Community 18 - "Community 18"
Cohesion: 0.09
Nodes (18): ndarray, Feature Extraction for Regime Detection This module provides feature extraction…, Extract volume-based features., Extract price-based features., Extract volatility-based features., Extract features for market regime detection. Features are based on statistical…, Extract autocorrelation features., Extract higher moments of returns distribution. (+10 more)

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (18): PositionSizer, Calculate position size based on portfolio value and risk per trade.…, Calculate fixed fractional position size. Parameters: -----------…, Position sizing calculator based on risk management., Calculate Kelly fraction. Parameters: ----------- win_rate : float Win rate…, Calculate optimal stop loss distance. Parameters: ----------- entry_price :…, Calculate stop loss as percentage of entry price., Calculate stop loss price. (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.08
Nodes (19): Auditor, BacktestEngine, Any, datetime, Protocol, Fetch market data for a given symbol and date range. Args: symbol: Trading…, Extract features for a specific date/time. Features can include technical…, Get data quality metrics for a symbol. Returns completeness, accuracy, and… (+11 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (17): Any, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Check if drawdown is within acceptable limits. Args: hypothesis_id: Hypothesis…, Unified Risk Manager implementing the RiskManager protocol. Consolidates…, Check if Sharpe ratio meets threshold. Args: sharpe_ratio: Sharpe ratio to…, Check if Sortino ratio meets threshold. Args: sortino_ratio: Sortino ratio to…, Check if Calmar ratio meets threshold. Args: calmar_ratio: Calmar ratio to… (+9 more)

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (18): Run backtests for all hypotheses of a symbol, PerformanceMetrics, ndarray, Represents a single trade., Performance Metrics Calculator Calculates various performance metrics for…, Calculate total return., Calculate total return percentage., Calculate Sharpe ratio. Parameters ---------- returns : np.ndarray Period… (+10 more)

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (19): ExecutionStrategy, Order, Helper to set last_price after execution., Create a new order. Parameters ---------- symbol : str Trading symbol side :…, Represents a trading order., Execute an order against the market. Parameters ---------- order : Order Order…, Get order status. Parameters ---------- order_id : str Order ID Returns -------…, Execution Strategy Determines optimal execution timing and pacing. (+11 more)

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (25): DataStore(), Factory: returns the SQLite-backed store when called with db_path, otherwise…, Transaction Cost Model Estimates transaction costs including commission and…, TransactionCostModel, Portfolio Construction module: Efficient Frontier, Black-Litterman, Risk Parity., BlackLitterman, EfficientFrontier, OptimizationResult (+17 more)

### Community 25 - "Community 25"
Cohesion: 0.08
Nodes (17): ndarray, Statistical Tests for Market Regime Detection This module provides statistical…, Runs test for random sequence analysis. The runs test checks whether a sequence…, Perform runs test on return series. Parameters ---------- returns : np.ndarray…, Z-score based regime detection. The Z-score measures how many standard…, Check if the test result is statistically significant., Variance ratio test for mean reversion. The variance ratio test compares the…, Perform variance ratio test. Parameters ---------- returns : np.ndarray Daily… (+9 more)

### Community 26 - "Community 26"
Cohesion: 0.12
Nodes (18): Principal Component Analysis (PCA) This module provides tools for…, compute_pca(), pca_denoising(), PCAAnalyzer, PCAResult, ndarray, PCA Analysis Module Provides Principal Component Analysis implementation for…, Transform data to PCA space. Parameters ---------- X : np.ndarray Data to… (+10 more)

### Community 27 - "Community 27"
Cohesion: 0.12
Nodes (14): AQDERunner, main(), Any, Print final summary of all iterations, Generate base hypothesis configurations for a symbol, Generate new hypotheses based on performance feedback - ENHANCED, Main runner for the Autonomous Quant Discovery Engine, Create and register hypotheses for a symbol (+6 more)

### Community 28 - "Community 28"
Cohesion: 0.08
Nodes (15): MonteCarloResult, StrategyResult, Port for statistical validation of hypotheses. Adapters implement this to…, Calculate win rate from trade history, Test statistical significance of strategy performance. Returns p-value or…, Calculate Sharpe ratio, Calculate Sortino ratio, Calculate Calmar ratio (+7 more)

### Community 29 - "Community 29"
Cohesion: 0.14
Nodes (14): PeriodogramAnalyzer, ndarray, Periodogram Analysis This module provides periodogram-based frequency analysis…, Detect seasonality in the data. Parameters ---------- data : np.ndarray Time…, Periodogram analyzer. This class performs periodogram analysis to identify…, Compute spectral flatness. Parameters ---------- data : np.ndarray Time series…, Compute spectral kurtosis. Parameters ---------- data : np.ndarray Time series…, Compute auto-correlation of power spectrum. Parameters ---------- data :… (+6 more)

### Community 30 - "Community 30"
Cohesion: 0.08
Nodes (23): aqde, aqdePhaseClass, aqdeStatusClass, calculateProgress(), currentPhase, evaluationProgress, evolutionProgress, evolvedCount (+15 more)

### Community 31 - "Community 31"
Cohesion: 0.09
Nodes (21): aqde, aqdePhaseClass, aqdeProgress, aqdeStatusClass, events, health, hypotheses, pipelineStages (+13 more)

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (13): ndarray, Compute the entire efficient frontier. Parameters ---------- n_points : int…, Find portfolio with maximum Sharpe ratio. Returns ------- weights : np.ndarray…, Find portfolio with minimum variance. Returns ------- weights : np.ndarray…, Initialize Black-Litterman model. Two modes: Legacy mode: expected_returns :…, Optimize portfolio with views. Legacy mode: views is a dict {asset_index:…, Initialize risk parity optimizer. Parameters ---------- returns : np.ndarray…, Optimize risk parity portfolio. Parameters ---------- target_risk : float,… (+5 more)

### Community 33 - "Community 33"
Cohesion: 0.11
Nodes (12): HypothesisKnowledgeBase, Any, Get timeline of hypothesis development, Export all hypotheses to a file, Import hypotheses from a file, Stub implementation of HypothesisKnowledgeBase for integration testing., Retrieve hypothesis by ID, Search hypotheses based on criteria (+4 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (13): Any, datetime, Extract technical features for a specific date. Args: symbol: Trading symbol…, Get data quality metrics. Returns completeness, accuracy, and freshness metrics., Search hypotheses using text matching, Find similar hypotheses using semantic search, Update an existing hypothesis in persistent storage. Args: hypothesis_id: ID of…, Get statistics about stored hypotheses from persistent storage (+5 more)

### Community 35 - "Community 35"
Cohesion: 0.09
Nodes (20): Drawdown Analyzer Module Calculates drawdown metrics for risk assessment., Expectation Calculation Module (Module 8) Statistical significance testing and…, Sharpe Metrics Module Calculates Sharpe, Sortino, Calmar and other risk-…, bootstrap_confidence_interval(), bootstrap_p_value(), jarque_bera_test(), one_sample_ttest(), paired_ttest() (+12 more)

### Community 36 - "Community 36"
Cohesion: 0.12
Nodes (14): callable, ndarray, Collection of statistical tests for strategy validation., Paired t-test (dependent samples). Args: sample1: First sample sample2: Second…, Jarque-Bera test for normality. Args: sample: Sample data Returns: Tuple of (JB…, Calculate t-statistic for one-sample t-test., Shapiro-Wilk test for normality (approximation). Args: sample: Sample data (max…, Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:… (+6 more)

### Community 37 - "Community 37"
Cohesion: 0.11
Nodes (15): Risk Management Module Exports, kelly_fraction(), KellyCriterion, Kelly Criterion Module Kelly criterion position sizing for optimal bet sizing., Kelly criterion position sizing., Calculate full Kelly fraction. Parameters: ----------- win_rate : float Win…, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction. (+7 more)

### Community 38 - "Community 38"
Cohesion: 0.14
Nodes (13): PowerSpectralDensity, ndarray, Compute spectral centroid. Parameters ---------- data : np.ndarray Time series…, Compute spectral bandwidth. Parameters ---------- data : np.ndarray Time series…, Compute spectral rolloff. Parameters ---------- data : np.ndarray Time series…, Power Spectral Density (PSD) analyzer. This class computes PSD using Welch's…, Compute spectral flux between two signals. Parameters ---------- data1 :…, Detect 1/f noise characteristics. Parameters ---------- data : np.ndarray Time… (+5 more)

### Community 39 - "Community 39"
Cohesion: 0.08
Nodes (24): get_active_strategies(), get_autonomous_status(), get_backtest_hypotheses(), get_events(), get_hypotheses(), get_monitoring_flow(), get_monitoring_hypotheses(), get_monitoring_simulations() (+16 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (13): useApi(), useAutonomousApi(), useBacktestApi(), useConfigApi(), useDashboardApi(), useMonitoringApi(), useTradingApi(), useEquityChart() (+5 more)

### Community 41 - "Community 41"
Cohesion: 0.14
Nodes (15): DenoisingKalmanFilter, design_and_apply_kalman_filter(), KalmanFilter, ndarray, Kalman Filter Module Implements Kalman filtering for state estimation and noise…, Predict state estimate forward. Parameters ---------- u : ndarray, optional…, Update state estimate with measurement. Parameters ---------- z : float or…, Apply Kalman filter to sequence of measurements. Parameters ----------… (+7 more)

### Community 42 - "Community 42"
Cohesion: 0.09
Nodes (12): QuantMathAdapter, Get list of available trading symbols, Store hypothesis in persistent knowledge base. Args: hypothesis: Hypothesis to…, Retrieve hypothesis by ID from persistent storage, Delete a hypothesis from persistent storage, Import hypotheses from a file, Adapter for integrating AQDE with existing quant-math modules. Implements all…, Calculate win rate from trade history (+4 more)

### Community 43 - "Community 43"
Cohesion: 0.15
Nodes (13): compute_fft(), FastFourierTransform, ndarray, Fast Fourier Transform (FFT) This module provides Fast Fourier Transform…, Find dominant frequency in the data. Parameters ---------- data : np.ndarray…, Fast Fourier Transform (FFT) analyzer. This class performs FFT analysis on time…, Compute FFT spectrum (magnitude squared). Parameters ---------- data :…, Detect presence of seasonality in the data. Parameters ---------- data :… (+5 more)

### Community 44 - "Community 44"
Cohesion: 0.13
Nodes (15): Backtester, BacktestResult, Backtesting & Evaluation Module This module provides backtesting and…, Result of backtesting., Calculate cumulative returns., Backtesting Engine Executes strategy backtests and calculates performance…, Initialize backtester. Parameters ---------- initial_capital : float Initial…, Result of walk-forward validation. (+7 more)

### Community 45 - "Community 45"
Cohesion: 0.15
Nodes (12): DataCleaner, DataFrame, ndarray, Data Cleaning Module Handles missing values, outliers, and structural breaks, Cap outliers to specified bounds Args: df: DataFrame column: Column to cap…, Data cleaning utilities for time series data, Detect and count duplicate rows Args: df: Input DataFrame Returns: DataFrame…, Remove duplicate rows Args: df: Input DataFrame subset: Columns to check for… (+4 more)

### Community 46 - "Community 46"
Cohesion: 0.11
Nodes (11): AdaptiveSizer, Calculate adaptive position size. Supports two modes: Risk-based mode (keyword…, Calculate position size based on recent trade performance. Parameters:…, Adaptive position sizing based on market conditions., Calculate position size based on market regime. Parameters: ----------- regime…, MeanVarianceOptimizer, ndarray, Optimize portfolio weights for minimum variance. Parameters: -----------… (+3 more)

### Community 47 - "Community 47"
Cohesion: 0.17
Nodes (17): ask_float(), ask_int(), _dispatch(), _get_current_price(), main(), monitor_loop(), Quant-Math interactive CLI. Menu: 1. Iniciar Quant-Math -> config wizard, then…, Interactive configuration wizard. Returns cfg dict or None if cancelled. (+9 more)

### Community 48 - "Community 48"
Cohesion: 0.12
Nodes (10): Agent, AgentRegistry, AgentMessage, Port for agent communication and coordination. Abstract base for specialized…, Send/receive a message, Get list of agent capabilities, Register this agent with the registry, Port for agent registry and communication. (+2 more)

### Community 49 - "Community 49"
Cohesion: 0.15
Nodes (11): ExpectedShortfall, ndarray, Calculate VaR from return series. Args: returns: Array of returns confidence:…, Calculate excess kurtosis., Expected Shortfall calculator. ES is the expected loss given that the loss…, Initialize ES calculator. Args: default_method: Default ES method…, Calculate Expected Shortfall. Args: mean_return: Mean return std_return:…, Parametric ES assuming normal distribution. (+3 more)

### Community 50 - "Community 50"
Cohesion: 0.14
Nodes (12): DataFrame, Series, Time Series Resampling Module Provides time series aggregation and resampling…, Calculate returns from price data Args: df: Input DataFrame with price column…, Calculate volatility Args: df: Input DataFrame with price column price_col:…, Time series resampling and aggregation utilities, Shift data by specified periods Args: df: Input DataFrame cols: Columns to…, Create time-based features Args: df: Input DataFrame timestamp_col: Timestamp… (+4 more)

### Community 51 - "Community 51"
Cohesion: 0.14
Nodes (12): callable, ndarray, Shapiro-Wilk test for normality. Args: sample: Sample data (max 5000…, Collection of statistical tests for strategy validation., Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:…, Bootstrap confidence interval. Args: sample: Sample data statistic: Function to…, One-sample t-test. Args: sample: Sample data popmean: Population mean to test…, Test if strategy returns are significantly different from benchmark. Args:… (+4 more)

### Community 52 - "Community 52"
Cohesion: 0.10
Nodes (15): areaPath, chartRef, colorMap, fillColor, hoverIndex, linePath, maxVal, minVal (+7 more)

### Community 53 - "Community 53"
Cohesion: 0.14
Nodes (17): useTradingStore, allConfirmed, apiConfig, closePosition(), confirmations, disableTrading(), emergencyStop(), enableTrading() (+9 more)

### Community 54 - "Community 54"
Cohesion: 0.16
Nodes (17): command, group, option, backtest(), cli(), discover(), export(), init_kb() (+9 more)

### Community 55 - "Community 55"
Cohesion: 0.15
Nodes (11): ndarray, Calculate Information Ratio (active return / tracking error). Args: returns:…, Calculate risk-adjusted performance metrics., Calculate Treynor ratio (excess return / beta). Args: returns: Strategy returns…, Calculate Omega ratio (probability-weighted gains / losses). Args: returns:…, Calculate all risk-adjusted metrics. Returns: Dictionary with all metrics, Calculate Sharpe ratio. Args: returns: Array of returns risk_free_rate: Risk-…, Calculate Sortino ratio (uses downside deviation). Args: returns: Array of… (+3 more)

### Community 56 - "Community 56"
Cohesion: 0.13
Nodes (12): calculate_var(), expected_shortfall(), Value at Risk (VaR) and Expected Shortfall (ES) Module Pure numpy…, Value at Risk calculator. VaR is the maximum expected loss over a given time…, Initialize VaR calculator. Args: default_method: Default VaR method…, Calculate Value at Risk using normal distribution (legacy API)., Calculate Expected Shortfall using normal distribution (legacy API)., Calculate Value at Risk. Args: mean_return: Mean return std_return: Standard… (+4 more)

### Community 57 - "Community 57"
Cohesion: 0.16
Nodes (12): design_and_apply_emd(), EmpiricalModeDecomposition, ndarray, Interpolate between extrema using spline interpolation. Parameters ----------…, Sifting process to extract one IMF from signal. Parameters ---------- signal :…, Decompose signal into IMFs and residue. Parameters ---------- signal : array-…, Perform Ensemble EMD (EEMD) for improved stability. Parameters ----------…, Initialize with signal for analysis. Parameters ---------- signal : array-like… (+4 more)

### Community 58 - "Community 58"
Cohesion: 0.18
Nodes (11): ContinuousWaveletTransform, callable, ndarray, Compute energy spectrum from CWT. Parameters ---------- data : np.ndarray Time…, Detect transient events in the time series. Parameters ---------- data :…, Continuous Wavelet Transform (CWT) analyzer. This class performs CWT analysis…, Plot CWT coefficients. Parameters ---------- data : np.ndarray Time series data…, Plot time-frequency heatmap with CWT coefficients. Parameters ---------- data :… (+3 more)

### Community 59 - "Community 59"
Cohesion: 0.12
Nodes (16): activeHypotheses, activity, availableSymbols, config, iteration, maxIterations, phase, progress (+8 more)

### Community 60 - "Community 60"
Cohesion: 0.12
Nodes (10): Agent, AgentMessage, Any, Send a message to a specific agent. Args: sender: Sending agent receiver_id:…, Get message history. Args: agent_id: Filter by sender/receiver ID (optional)…, Get registry statistics. Returns: Dictionary with statistics about registered…, Get list of all registered agents with details. Returns: List of agent…, Register a new agent. Args: agent: Agent instance to register Returns: Agent ID… (+2 more)

### Community 61 - "Community 61"
Cohesion: 0.18
Nodes (11): DataFrame, Series, Structural Break Detection Module Detects changes in data distribution and…, Detect regime changes in time series Args: df: Input DataFrame col: Column to…, Detect structural breaks in time series data, Test stationarity of time series Args: df: Input DataFrame col: Column to test…, Detect changes in trend using linear regression Args: df: Input DataFrame col:…, Comprehensive structural break analysis Args: df: Input DataFrame col: Column… (+3 more)

### Community 62 - "Community 62"
Cohesion: 0.13
Nodes (14): put, API Routes for Quant-Math WebUI, # TODO: Connect to actual AQDE state, # TODO: Connect to actual paper trading engine, # TODO: Connect to hypothesis database, # TODO: Connect to event store, # TODO: Connect to actual strategy manager, # TODO: Load from actual config store (+6 more)

### Community 63 - "Community 63"
Cohesion: 0.12
Nodes (10): Hypothesis, KnowledgeBase, Port for hypothesis knowledge management. Adapters implement this to store,…, Store a hypothesis and return its ID, Retrieve a hypothesis by ID, Search hypotheses based on criteria. Criteria can include: - strategy_type -…, Update an existing hypothesis, Get statistics about stored hypotheses (+2 more)

### Community 64 - "Community 64"
Cohesion: 0.16
Nodes (11): DrawdownAnalyzer, Any, ndarray, Calculate average drawdown duration., Calculate maximum drawdown duration., Calculate Ulcer Index (root mean square of drawdowns). Ulcer Index =…, Analyze drawdowns from equity curve or returns., Calculate drawdown series and metrics from equity curve. Args: equity_curve:… (+3 more)

### Community 65 - "Community 65"
Cohesion: 0.14
Nodes (11): Any, ndarray, Return Calculator Module Calculates various return metrics for trading…, Calculate various return metrics from trade history or price series., Calculate returns from trade history. Args: trades: List of trade dictionaries…, Calculate cumulative return from returns series., Calculate annualized return., Calculate geometric mean of returns. (+3 more)

### Community 66 - "Community 66"
Cohesion: 0.18
Nodes (7): Orchestrator, Generate N hypotheses across configured symbols and backtest them., Convert an AQDE backtest result into a KB JSONL record., Fill a paper trade at the signal price with configured sizing/TP., generate -> persist -> decide -> paper execute -> feedback., Continuous loop (Ctrl+C to stop)., Continuous generation -> decision -> feedback loop.

### Community 67 - "Community 67"
Cohesion: 0.18
Nodes (10): HarmonicComponentAnalyzer, ndarray, Reconstruct signal from top harmonics. Parameters ---------- data : np.ndarray…, Harmonic component analyzer. This class identifies and analyzes harmonic…, Compute ratio between harmonic components. Parameters ---------- data :…, Analyze periodicity in the data. Parameters ---------- data : np.ndarray Time…, Plot harmonic components. Parameters ---------- data : np.ndarray Time series…, Plot frequency spectrum highlighting harmonics. Parameters ---------- data :… (+2 more)

### Community 68 - "Community 68"
Cohesion: 0.11
Nodes (14): areaPath, colorMap, fillColor, hoverPoint, linePath, maxVal, minVal, points (+6 more)

### Community 69 - "Community 69"
Cohesion: 0.11
Nodes (15): filteredHypotheses, flow, hypFilter, hypotheses, hypothesisStatuses, loading, simulationGroups, simulations (+7 more)

### Community 70 - "Community 70"
Cohesion: 0.20
Nodes (10): Normalizer, DataFrame, Data Normalization Module Provides multiple normalization and scaling methods, Standardize multiple columns Args: df: Input DataFrame method: 'zscore',…, Data normalization and scaling utilities, Normalize all numerical columns Args: df: Input DataFrame method: Normalization…, Inverse transform normalized data Args: df_norm: Normalized DataFrame scaler:…, Min-Max normalization Args: df: Input DataFrame feature_range: Desired range… (+2 more)

### Community 71 - "Community 71"
Cohesion: 0.21
Nodes (9): Any, Stop loss calculator with multiple methods. Supports: - Fixed percentage - ATR-…, Chandelier exit stop loss., Volatility-adjusted stop loss., Calculate multiple stop loss levels. Args: entry_price: Entry price side:…, Initialize stop loss calculator. Args: default_method: Default stop loss method…, Calculate stop loss price. Args: entry_price: Entry price side: 'long' or…, Fixed percentage stop loss. (+1 more)

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (10): ndarray, Calculate both VaR and ES. Parameters ---------- returns : np.ndarray…, Initialize portfolio risk analyzer. Supports two modes: Returns mode (legacy):…, Derive the correlation matrix from a covariance matrix., Stress Testing and Scenario Analysis Tests portfolio performance under extreme…, Initialize stress tester. Parameters ---------- returns : np.ndarray, optional…, Generate historical scenarios (bootstrap). Parameters ---------- data :…, Generate industry standard stress scenarios. Typical stress scenarios: - Market… (+2 more)

### Community 73 - "Community 73"
Cohesion: 0.16
Nodes (11): BandPassFilter, design_and_apply_band_pass(), ndarray, Band-Pass Filter Module Implements band-pass filters to retain only specific…, Apply band-pass filter to input data. Parameters ---------- data : array-like…, Apply filter in real-time with phase delay (for online applications).…, Compute frequency response of the band-pass filter. Returns ------- w : ndarray…, Analyze signal power in passband vs stopbands. Parameters ----------… (+3 more)

### Community 74 - "Community 74"
Cohesion: 0.16
Nodes (11): design_and_apply_high_pass(), HighPassFilter, ndarray, High-Pass Filter Module Implements high-pass filters to remove low-frequency…, Apply filter using zero-pole-gain representation (more stable for long data).…, Compute frequency response of the filter. Returns ------- w : ndarray Angular…, Analyze signal bandwidth before and after filtering. Parameters ----------…, Convenience function to design and apply high-pass filter in one step.… (+3 more)

### Community 75 - "Community 75"
Cohesion: 0.17
Nodes (15): closeDropdown(), containerRef, emit, filteredOptions, focused, handleClickOutside(), handleKeydown(), hoveredIndex (+7 more)

### Community 76 - "Community 76"
Cohesion: 0.16
Nodes (14): useConfigStore, config, loadConfig(), loading, resetConfig(), saveConfig(), saving, sections (+6 more)

### Community 77 - "Community 77"
Cohesion: 0.12
Nodes (12): backtestStore, configStore, configValues, effectiveConfig, error, form, hypotheses, loadingDetail (+4 more)

### Community 78 - "Community 78"
Cohesion: 0.22
Nodes (15): example_fft_analysis(), example_harmonic_analysis(), example_periodogram_analysis(), example_psd_analysis(), example_wavelet_analysis(), generate_sample_data(), main(), ndarray (+7 more)

### Community 79 - "Community 79"
Cohesion: 0.19
Nodes (8): Run walk-forward validation. Parameters ---------- strategy_func : callable…, Grid search optimization on training data., Run backtest with specific parameters., Compute aggregate statistics., Compute robustness score (0-100)., Compute parameter stability across windows (0-100)., Walk-Forward Validation Engine Implements walk-forward analysis for robust…, WalkForwardValidator

### Community 80 - "Community 80"
Cohesion: 0.14
Nodes (8): ExchangeManager, Register an exchange. Parameters: ----------- name : str Exchange name api_key…, Set the active exchange. Parameters: ----------- name : str Exchange name…, Get the active exchange configuration., Manage multiple cryptocurrency exchanges., Place an order. Parameters: ----------- symbol : str Trading symbol (e.g.,…, Initialize exchange manager., Cancel an order. Parameters: ----------- order_id : str Order ID Returns:…

### Community 81 - "Community 81"
Cohesion: 0.13
Nodes (15): post, close_position(), disable_trading(), emergency_stop(), enable_trading(), Save configuration values., Stop autonomous mode., Enable real trading with Bybit. (+7 more)

### Community 82 - "Community 82"
Cohesion: 0.21
Nodes (9): PositionSizer, Any, Volatility targeting position sizing., Unified position sizing calculator. Supports multiple sizing algorithms: -…, ATR-based position sizing., Initialize position sizer. Args: default_method: Default sizing method…, Calculate position size based on method. Args: account_value: Total account…, Fixed fractional position sizing. (+1 more)

### Community 83 - "Community 83"
Cohesion: 0.14
Nodes (9): Any, Parametric VaR (assuming Student's t distribution). Parameters ----------…, Historical VaR (empirical method). Two call styles: Instance style:…, Calculate Conditional Tail Expectation (Expected Shortfall). Parameters…, Result of VaR calculation., Calculate concentration risk metrics. Returns ------- metrics : dict…, Parametric VaR (assuming normal distribution). Formula: VaR = mu - z_alpha *…, Monte Carlo stress testing. Parameters ---------- n_scenarios : int Number of… (+1 more)

### Community 84 - "Community 84"
Cohesion: 0.19
Nodes (10): design_and_apply_wavelet_denoise(), ndarray, Wavelet Decomposition Module Implements wavelet-based denoising and signal…, Denoise signal using wavelet thresholding. Parameters ---------- signal :…, Get multi-resolution analysis information. Parameters ---------- signal :…, Convenience function to denoise signal in one step. Parameters ----------…, Wavelet-based denoising and signal decomposition. This class implements wavelet…, Initialize wavelet denoiser. Parameters ---------- wavelet : str, optional… (+2 more)

### Community 85 - "Community 85"
Cohesion: 0.14
Nodes (10): isDark, navItems, route, router, store, wsStatus, app, pinia (+2 more)

### Community 86 - "Community 86"
Cohesion: 0.16
Nodes (13): bootstrap_confidence_interval(), jarque_bera_test(), one_sample_ttest(), paired_ttest(), Statistical Tests Module Statistical significance testing for trading strategy…, Convenience function for one-sample t-test., Convenience function for Jarque-Bera test., Convenience function for Shapiro-Wilk test. (+5 more)

### Community 87 - "Community 87"
Cohesion: 0.19
Nodes (8): DataFrame, ndarray, Generate synthetic OHLCV data for dry-run / testing. Uses a random walk with…, Calculate Stochastic %K and %D indicators, Calculate Volume Weighted Average Price, Calculate Donchian channels (upper and lower), Calculate Average True Range, Run backtest using quant-math backtester. Args: hypothesis: Hypothesis dict…

### Community 88 - "Community 88"
Cohesion: 0.14
Nodes (8): Port for risk management checks. Adapters implement this to ensure hypotheses…, Check if position size meets risk criteria. Returns OK or failure reasons., Check if drawdown is within acceptable limits, Check if Sharpe ratio meets threshold, Check if Sortino ratio meets threshold, Check if Calmar ratio meets threshold, Perform stress testing on strategy, RiskManager

### Community 89 - "Community 89"
Cohesion: 0.22
Nodes (13): example_expected_shortfall(), example_portfolio_risk(), example_risk_budgeting(), example_stress_testing(), example_var_calculation(), main(), Example: Portfolio risk analysis., Example: Risk budgeting and allocation. (+5 more)

### Community 90 - "Community 90"
Cohesion: 0.20
Nodes (13): example_band_pass_filter(), example_emd(), example_high_pass_filter(), example_kalman_filter(), example_wavelet_denoising(), generate_test_signal(), Signal Processing Module Example Usage This module demonstrates how to use the…, Example: Band-pass filtering to isolate specific frequency bands. (+5 more)

### Community 91 - "Community 91"
Cohesion: 0.14
Nodes (9): activeCount, avgSharpe, selectedStrategy, statusLabels, stopStrategy(), store, strategies, totalPnL (+1 more)

### Community 92 - "Community 92"
Cohesion: 0.25
Nodes (10): useWebSocket(), clearTimers(), connect(), disconnect(), scheduleReconnect(), send(), useAutonomousStore, useBacktestStore (+2 more)

### Community 93 - "Community 93"
Cohesion: 0.17
Nodes (13): BaseModel, AQDEStatus, BacktestRequest, BacktestResponse, Event, get_aqde_status(), get_trading_metrics(), Hypothesis (+5 more)

### Community 94 - "Community 94"
Cohesion: 0.17
Nodes (10): format, formatTime(), emit, formatDate(), formatDateTime(), props, statusLabels, formatTime() (+2 more)

### Community 95 - "Community 95"
Cohesion: 0.23
Nodes (12): autonomousLoading, emit, emitAutonomous(), emitBacktest(), emitRealTrading(), emitRestart(), emitStart(), emitStop() (+4 more)

### Community 96 - "Community 96"
Cohesion: 0.18
Nodes (7): Calculate Sharpe ratio. Parameters: ----------- returns : List[float] Period…, Calculate Sortino ratio (downside deviation). Parameters: ----------- returns :…, Calculate Sharpe ratio and related metrics., Calculate information ratio. Parameters: ----------- returns : List[float]…, SharpeMetrics, bootstrap_p_value(), Convenience function for bootstrap p-value.

### Community 97 - "Community 97"
Cohesion: 0.17
Nodes (7): Risk Manager Implementation. Implements the RiskManager port for risk…, Port for risk management checks. Adapters implement this to ensure hypotheses…, Check if position size meets risk criteria. Returns OK or failure reasons., Check if drawdown is within acceptable limits, Check if Sharpe ratio meets threshold, Check if Sortino ratio meets threshold, RiskManager

### Community 98 - "Community 98"
Cohesion: 0.17
Nodes (7): Port for statistical validation of hypotheses. Adapters implement this to…, Calculate win rate from trade history, Test statistical significance of strategy performance. Returns p-value or…, Calculate Sharpe ratio, Calculate Sortino ratio, Run Monte Carlo simulation on strategy performance. Uses bootstrapping or…, StatisticalValidator

### Community 99 - "Community 99"
Cohesion: 0.18
Nodes (7): Risk Management Module This module provides comprehensive risk measurement and…, Risk Management Module This module provides comprehensive risk measurement and…, Risk Budgeting and Allocation Allocates risk budgets across portfolio assets., Initialize risk budget allocator. Parameters ---------- target_var : float…, Allocate risk equally across assets. Parameters ---------- returns : np.ndarray…, Calculate optimal risk allocation using optimization. Parameters ----------…, RiskBudget

### Community 100 - "Community 100"
Cohesion: 0.20
Nodes (7): Calculate component VaR (marginal VaR). Parameters ---------- returns :…, Calculate diversification benefit. Benefit = (sum of individual VaR) -…, Calculate comprehensive portfolio risk metrics. Parameters ----------…, Value at Risk (VaR) Calculator Computes VaR at various confidence levels using…, Calculate marginal contributions to VaR. Parameters ---------- returns :…, Initialize VaR calculator. Parameters ---------- confidence_level : float…, ValueAtRisk

### Community 101 - "Community 101"
Cohesion: 0.18
Nodes (6): Calculate simple returns from price series. Parameters: ----------- prices :…, Calculate log returns from price series. Parameters: ----------- prices :…, Calculate annualized return. Parameters: ----------- returns : List[float]…, Calculate various return metrics., Calculate cumulative return from price series. Parameters: ----------- prices :…, ReturnCalculator

### Community 102 - "Community 102"
Cohesion: 0.18
Nodes (6): DrawdownAnalyzer, Calculate drawdowns from price series. Parameters: ----------- prices :…, Calculate maximum drawdown. Parameters: ----------- drawdowns : List[float]…, Calculate average drawdown. Parameters: ----------- drawdowns : List[float]…, Analyze drawdowns from price series., Calculate drawdown duration (time from peak to valley). Parameters: -----------…

### Community 103 - "Community 103"
Cohesion: 0.18
Nodes (7): Auditor, Protocol, Port for audit and compliance. Adapters implement this to track experiments,…, Log an experiment run with full details, Get experiment history for a hypothesis, Verify that an experiment can be reproduced, Get audit trail for a backtest. Includes data versioning, parameter logs,…

### Community 104 - "Community 104"
Cohesion: 0.20
Nodes (7): DataProvider, datetime, Port for data access in Quant-Math. Adapters implement this to provide market…, Fetch market data for a given symbol and date range. Args: symbol: Trading…, Extract features for a specific date/time. Features can include technical…, Get list of available trading symbols, Get data quality metrics for a symbol. Returns completeness, accuracy, and…

### Community 105 - "Community 105"
Cohesion: 0.27
Nodes (9): list_modules(), main(), QUANT-MATH Main Entry Point Unified CLI entry point for the QUANT-MATH…, List available modules with descriptions., Main CLI entry point., Run integration tests., Show framework information., run_tests() (+1 more)

### Community 106 - "Community 106"
Cohesion: 0.22
Nodes (6): ExpectedShortfall, Expected Shortfall (ES) Calculator Computes Expected Shortfall at various…, Initialize ES calculator. Parameters ---------- confidence_level : float…, Historical ES calculation. Two call styles: Instance style:…, Parametric ES (assuming normal distribution). Formula: ES = mu - sigma *…, Conditional Tail Expectation (ES) calculation. Parameters ---------- returns :…

### Community 107 - "Community 107"
Cohesion: 0.22
Nodes (5): Agent, Port for agent communication and coordination. Abstract base for specialized…, Send/receive a message, Get list of agent capabilities, Register this agent with the registry

### Community 108 - "Community 108"
Cohesion: 0.33
Nodes (3): HiddenMarkovModel, ndarray, test_regime_detection()

### Community 109 - "Community 109"
Cohesion: 0.31
Nodes (3): ndarray, test_var(), ValueAtRisk

### Community 110 - "Community 110"
Cohesion: 0.22
Nodes (8): autonomousStore, currentStore, dashboardStore, monitoringStore, route, routeStoreMap, statusClass, statusText

### Community 111 - "Community 111"
Cohesion: 0.36
Nodes (7): main(), Example: Risk factor model., Example: Feature engineering., Example: ML-based portfolio optimization., test_factor_model(), test_feature_engineering(), test_ml_portfolio()

### Community 112 - "Community 112"
Cohesion: 0.25
Nodes (5): KellyCriterion, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction., Kelly criterion position sizing., Calculate full Kelly fraction. Parameters: ----------- win_rate : float Win…

### Community 113 - "Community 113"
Cohesion: 0.36
Nodes (7): main(), Example: Risk Parity Portfolio., Example: Efficient Frontier., Example: Black-Litterman Model., test_black_litterman(), test_efficient_frontier(), test_risk_parity()

### Community 114 - "Community 114"
Cohesion: 0.25
Nodes (5): Adapters for AQDE - Implementation of hexagonal architecture ports. These…, Stub module for HypothesisKnowledgeBase to fix imports., Search criteria for hypothesis search, SearchCriteria, Search hypotheses based on criteria. Args: criteria: Search criteria dictionary…

### Community 115 - "Community 115"
Cohesion: 0.25
Nodes (5): MonteCarloEngine, Port for Monte Carlo simulation. Adapters implement this to run Monte Carlo…, Run Monte Carlo simulation on strategy results, Get confidence interval for a metric, Test robustness across multiple simulated scenarios. Returns distribution…

### Community 116 - "Community 116"
Cohesion: 0.25
Nodes (5): _orchestrator_process_main(), Child process: run the orchestrator loop with all output to quant_math.log., OrchestratorConfig, Quant-Math Orchestrator. Connects the full discovery -> decision -> feedback…, Explicit configuration. Required fields have NO hidden defaults.

### Community 117 - "Community 117"
Cohesion: 0.25
Nodes (4): Harmonic Component Analysis This module provides harmonic component analysis…, Spectral Analysis This module provides frequency domain analysis techniques…, Power Spectral Density (PSD) This module provides Power Spectral Density…, Continuous Wavelet Transform (CWT) This module provides Continuous Wavelet…

### Community 118 - "Community 118"
Cohesion: 0.33
Nodes (3): Execute order using specified algorithm. Parameters ---------- symbol : str…, Calculate performance metrics for algorithmic execution. Parameters ----------…, Compare different algorithms on same order. Parameters ---------- symbol : str…

### Community 119 - "Community 119"
Cohesion: 0.33
Nodes (5): BaseSettings, Config, Quant-Math WebUI Backend Configuration, Application settings loaded from environment variables., Settings

### Community 120 - "Community 120"
Cohesion: 0.33
Nodes (4): EmpiricalModeAnalysis, Empirical Mode Decomposition Module Implements Empirical Mode Decomposition…, Convenience class for empirical mode analysis. This class provides additional…, Get statistics for each IMF. Returns ------- stats : dict Dictionary containing…

### Community 121 - "Community 121"
Cohesion: 0.47
Nodes (5): emit, handleChange(), handleInput(), props, showPassword

### Community 122 - "Community 122"
Cohesion: 0.40
Nodes (3): Series, Calculate RSI indicator, Calculate multiple EMA windows

### Community 123 - "Community 123"
Cohesion: 0.40
Nodes (3): ArchitecturalViolationTracker, Tracks if any module accesses code outside quant_math/**, Check if an import violates architectural boundaries

### Community 125 - "Community 125"
Cohesion: 0.50
Nodes (3): CryptoSymbol, Represents a crypto trading pair with metadata, Fetch top N symbols by volume from Bybit

### Community 129 - "Community 129"
Cohesion: 0.50
Nodes (3): PortfolioRiskResult, Result of portfolio risk analysis., Dict-like access to result fields (e.g. 'var_95' -> total_var).

### Community 130 - "Community 130"
Cohesion: 0.50
Nodes (3): props, sizeClass, variantClass

### Community 132 - "Community 132"
Cohesion: 0.50
Nodes (3): formattedValue, props, valueColor

### Community 133 - "Community 133"
Cohesion: 0.67
Nodes (3): emit, props, selectItem()

### Community 134 - "Community 134"
Cohesion: 0.50
Nodes (3): statusClass, statusText, store

### Community 137 - "Community 137"
Cohesion: 0.12
Nodes (9): Any, Update an existing hypothesis, Get statistics about stored hypotheses, Export all hypotheses to a file, Get trade history for a hypothesis, Get all performance metrics for a hypothesis, Test robustness across multiple simulated scenarios. Returns distribution…, Execute a specific task (+1 more)

### Community 138 - "Community 138"
Cohesion: 0.67
Nodes (3): ConfigSection, get_config_sections(), Get available configuration sections.

### Community 139 - "Community 139"
Cohesion: 0.67
Nodes (3): websocket, WebSocket endpoint for real-time updates., websocket_endpoint()

### Community 163 - "Community 163"
Cohesion: 0.67
Nodes (3): AutonomousConfig, Start autonomous mode., start_autonomous()

### Community 164 - "Community 164"
Cohesion: 0.67
Nodes (3): get_health(), HealthResponse, Get system health metrics.

## Knowledge Gaps
- **207 isolated node(s):** `Config`, `autonomousStore`, `currentStore`, `dashboardStore`, `monitoringStore` (+202 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ResearchManager` connect `Community 2` to `Community 24`, `Community 17`, `Community 13`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `run_full_e2e_test()` connect `Community 24` to `Community 1`, `Community 2`, `Community 9`, `Community 10`, `Community 17`, `Community 22`, `Community 23`, `Community 42`, `Community 44`, `Community 45`, `Community 46`, `Community 50`, `Community 61`, `Community 70`, `Community 72`, `Community 79`, `Community 89`, `Community 100`, `Community 106`, `Community 123`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `QuantMathAdapter` connect `Community 42` to `Community 1`, `Community 2`, `Community 33`, `Community 34`, `Community 12`, `Community 17`, `Community 114`, `Community 22`, `Community 87`, `Community 54`, `Community 24`, `Community 122`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `QuantMathAdapter` (e.g. with `ExchangeAPI` and `OrderManager`) actually correct?**
  _`QuantMathAdapter` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `run_full_e2e_test()` (e.g. with `StrategyType` and `ExpectedShortfall`) actually correct?**
  _`run_full_e2e_test()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `OrderManager` (e.g. with `AlgoTradingSystem` and `POV`) actually correct?**
  _`OrderManager` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `RiskManager` (e.g. with `KellyCriterion` and `StrategyResult`) actually correct?**
  _`RiskManager` has 6 INFERRED edges - model-reasoned connections that need verification._