# Graph Report - Quant-Math-Public  (2026-08-25)

## Corpus Check
- 47 files · ~123,458 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3107 nodes · 4647 edges · 174 communities (157 shown, 17 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Risk Management Module
- Kelly y Riesgo Cuantitativo
- Criterios de Busqueda AQDE
- DataStore y Limpieza de Datos
- Generador ARIMA-GARCH y Prior ML
- Knowledge Base PostgreSQL
- Protocolos Core y Auditoria
- API de Persistencia de Experimentos
- SIS Feature Store
- Sistema de Algo Trading
- Motor de Backtesting
- Deteccion de Regimenes
- Pipeline de Investigacion AQDE
- Dependencias Frontend WebUI
- Puertos de Riesgo de Portafolio
- Capa de Base de Datos
- Order Management
- Clustering de Volatilidad
- Tipos de Ordenes de Ejecucion
- Ingenieria de Features ML
- Backend FastAPI Web
- Simulacion Monte Carlo
- CLI Interactiva
- Modelos Estadisticos ARCH
- Doc Vision Arquitectura Legacy
- Metodos de Clustering
- Extraccion de Features de Regimen
- Modulo Position Sizing
- Fuente de Datos Exchange
- Sizing Adaptativo
- Guia de Arquitectura
- Tests Estadisticos de Regimen
- Modulo PCA
- Registro Multi-Agente
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares
- Nodos Auxiliares

## God Nodes (most connected - your core abstractions)
1. `DecisionEngine` - 48 edges
2. `QuantMathAdapter` - 42 edges
3. `PostgreSQLKnowledgeBase` - 41 edges
4. `run_full_e2e_test()` - 39 edges
5. `OrderManager` - 29 edges
6. `AQDERunner` - 28 edges
7. `RiskManager` - 24 edges
8. `ExchangeAPI` - 24 edges
9. `RiskManagementEngine` - 23 edges
10. `Orchestrator` - 23 edges

## Surprising Connections (you probably didn't know these)
- `P1 Ranking Fallback (next-best candidate)` --conceptually_related_to--> `DecisionEngine`  [EXTRACTED]
  IMPLEMENTATION_STATUS.md → quant_math/decision_engine/main.py
- `PA Live Expectancy (Bayesian Shrinkage, [exp-refresh])` --conceptually_related_to--> `DecisionEngine`  [EXTRACTED]
  IMPLEMENTATION_STATUS.md → quant_math/decision_engine/main.py
- `PB Auto-Graduation of LEARN_MODE` --conceptually_related_to--> `DecisionEngine`  [EXTRACTED]
  IMPLEMENTATION_STATUS.md → quant_math/decision_engine/main.py
- `DecisionEngine` --implements--> `DecisionEngine.decide()`  [EXTRACTED]
  quant_math/decision_engine/main.py → ARCHITECTURE.md
- `ML Prior Bayesian IC90 (beta_posterior CI90)` --references--> `HypothesisPrior`  [EXTRACTED]
  IMPLEMENTATION_STATUS.md → quant_math/ml/hypothesis_prior.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Self-Improving Generate-Validate-Trade-Learn Cycle** — architecture_aqderunner, architecture_orchestrator_run_cycle, architecture_decision_engine_decide, architecture_paper_executions_ledger, architecture_sis_operation_learning_loop, architecture_family_feedback_buckets [EXTRACTED 0.90]
- **Decision-Engine Improvements (P1/PA/PB, commits 6414e71-d99d3cd)** — implementation_status_p1_ranking_fallback, implementation_status_pa_live_expectancy, implementation_status_pb_auto_graduation, implementation_status_graduation_json [EXTRACTED 0.90]
- **Pending WebUI-Core Integration Cluster** — architecture_reuse_report_webui_routes, architecture_guide_quantmathadapter, architecture_reuse_report_pinia_stores, webui_frontend_index_html_vueappshell [EXTRACTED 0.85]

## Communities (174 total, 17 thin omitted)

### Community 0 - "Risk Management Module"
Cohesion: 0.04
Nodes (55): Risk Management Module This module provides comprehensive risk measurement and…, example_expected_shortfall(), example_portfolio_risk(), example_risk_budgeting(), example_stress_testing(), example_var_calculation(), main(), Example: Portfolio risk analysis. (+47 more)

### Community 1 - "Kelly y Riesgo Cuantitativo"
Cohesion: 0.04
Nodes (46): Risk Management Module Exports, kelly_fraction(), KellyCriterion, Kelly Criterion Module Kelly criterion position sizing for optimal bet sizing., Kelly criterion position sizing., Calculate full Kelly fraction. Parameters: ----------- win_rate : float Win…, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction. (+38 more)

### Community 2 - "Criterios de Busqueda AQDE"
Cohesion: 0.04
Nodes (41): Search criteria for hypothesis search, SearchCriteria, Any, DataFrame, datetime, ndarray, Series, QuantMathAdapter (+33 more)

### Community 3 - "DataStore y Limpieza de Datos"
Cohesion: 0.04
Nodes (51): DataStore(), Factory: returns the SQLite-backed store when called with db_path, otherwise…, DataCleaner, Data Cleaning Module Handles missing values, outliers, and structural breaks, Data cleaning utilities for time series data, Normalizer, Data Normalization Module Provides multiple normalization and scaling methods, Data normalization and scaling utilities (+43 more)

### Community 4 - "Generador ARIMA-GARCH y Prior ML"
Cohesion: 0.06
Nodes (46): ML Prior Bayesian IC90 (beta_posterior CI90), analyze_series(), _dominant_cycle(), generate_model_hypotheses(), Generador de hipotesis basado en modelos cientificos (ARIMA/GARCH). Conecta los…, Ciclo dominante en velas via FFT del paquete spectral_analysis existente (sin…, ARIMA(1,1,0): signo del forecast; GARCH(1,1): percentil de la volatilidad…, Devuelve plantillas compatibles con create_hypotheses_for_symbol. Regla… (+38 more)

### Community 5 - "Knowledge Base PostgreSQL"
Cohesion: 0.07
Nodes (25): Exception, KBPersistence, PostgreSQLKnowledgeBase, _psycopg2(), Any, PostgreSQL-backed Knowledge Base with automatic JSONL fallback. Drop-in…, Bootstrap: if the PG table is empty but the JSONL mirror has records, import…, Return True if a healthy PG connection is present. (+17 more)

### Community 6 - "Protocolos Core y Auditoria"
Cohesion: 0.06
Nodes (43): Quant-Math Core Package Shared domain types and protocols for the Quant-Math…, Auditor, BacktestEngine, DataProvider, MonteCarloEngine, datetime, Protocol, Quant-Math Core Protocols Hexagonal architecture ports that separate the domain… (+35 more)

### Community 7 - "API de Persistencia de Experimentos"
Cohesion: 0.04
Nodes (28): KnowledgeBase, Any, Hypothesis, Search hypotheses using text matching, Find similar hypotheses using semantic search, Update an existing hypothesis, Get statistics about stored hypotheses, Get timeline of hypothesis development (+20 more)

### Community 8 - "SIS Feature Store"
Cohesion: 0.07
Nodes (35): build_trade_dataset(), encode_dataset(), encode_row(), Any, Feature store del aprendizaje no supervisado. Une el libro permanente de…, Una fila por cierre post-cutoff, enriquecida con KB + _regime., Vector fijo para clustering; None -> -1., read_closures() (+27 more)

### Community 9 - "Sistema de Algo Trading"
Cohesion: 0.08
Nodes (32): AlgoExecution, AlgoTradingSystem, POV, Order, Algorithmic Trading System This module provides algorithmic trading…, Volume-Weighted Average Price (VWAP) Splits order based on expected market…, Initialize VWAP algorithm. Two modes: Order-based (legacy): execution_time :…, Result of algorithmic execution. (+24 more)

### Community 10 - "Motor de Backtesting"
Cohesion: 0.08
Nodes (31): Run backtests for all hypotheses of a symbol, Backtester, BacktestResult, PerformanceMetrics, Backtesting & Evaluation Module This module provides backtesting and…, Represents a single trade., Performance Metrics Calculator Calculates various performance metrics for…, Result of backtesting. (+23 more)

### Community 11 - "Deteccion de Regimenes"
Cohesion: 0.06
Nodes (32): Regime Detection Module This module provides tools for detecting and analyzing…, example_clustering(), example_hmm(), main(), Example: Hidden Markov Model regime detection., Example: Regime clustering., HiddenMarkovModel, ndarray (+24 more)

### Community 12 - "Pipeline de Investigacion AQDE"
Cohesion: 0.05
Nodes (44): AQDERunner, Losing-Streak Exploration Bursts, Duplicate Adapter Consolidation Problem, AQDE 5-Phase Research Pipeline, QuantMathAdapter, Shared Port Protocols (DataProvider, KnowledgeBase, BacktestEngine, MonteCarloEngine, StatisticalValidator, RiskManager), Single Source of Truth Principle, Target Architecture: AQDE as Internal Module (v0.x Historical) (+36 more)

### Community 13 - "Dependencias Frontend WebUI"
Cohesion: 0.05
Nodes (43): axios, chart.js, chartjs-adapter-date-fns, d3, date-fns, eslint, eslint-config-prettier, eslint-plugin-prettier (+35 more)

### Community 14 - "Puertos de Riesgo de Portafolio"
Cohesion: 0.07
Nodes (24): Any, RiskManager, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Implementation of RiskManager port. Provides risk management functionality…, Check if drawdown is within acceptable limits. Args: hypothesis_id: Hypothesis…, Check if Sharpe ratio meets threshold. Args: sharpe_ratio: Sharpe ratio to…, Check if Sortino ratio meets threshold. Args: sortino_ratio: Sortino ratio to… (+16 more)

### Community 15 - "Capa de Base de Datos"
Cohesion: 0.06
Nodes (24): _PostgreSQLDataStore, Any, DataFrame, PostgreSQL Database Connector Provides data storage and retrieval with metadata…, Query data from database Args: query: SQL query string params: Query parameters…, Get schema information for a table Args: table: Table name Returns: List of…, Check data quality for a table Args: table: Table name columns: Specific…, Remove data older than specified threshold Args: table: Table name… (+16 more)

### Community 16 - "Order Management"
Cohesion: 0.09
Nodes (27): QUANT-MATH: Quantitative Trading Framework A modular research framework for…, ExecutionReport, ExecutionStrategy, Order, OrderBook, Order Management Module This module provides order management and execution…, Helper to set last_price after execution., Create a new order. Parameters ---------- symbol : str Trading symbol side :… (+19 more)

### Community 17 - "Clustering de Volatilidad"
Cohesion: 0.07
Nodes (22): EWMAVolatility, GARCHModel, ndarray, Volatility Clustering Analysis This module provides methods to detect and…, Detect volatility clusters using rolling volatility. Parameters ----------…, Test for ARCH effects (autoregressive conditional heteroskedasticity). The…, Check if ARCH effects are present (indicating volatility clustering).…, Calculate the ratio of high volatility variance to low volatility variance.… (+14 more)

### Community 18 - "Tipos de Ordenes de Ejecucion"
Cohesion: 0.08
Nodes (27): Order, OrderType, Enum, Initialize order. Parameters: ----------- symbol : str Trading symbol side :…, Validate order parameters. Returns: -------- bool True if valid, Supported order types., OrderRouter, Order (+19 more)

### Community 19 - "Ingenieria de Features ML"
Cohesion: 0.07
Nodes (24): FeatureEngineer, MLPortfolioOptimizer, MLPortfolioResult, ndarray, Machine Learning for Quant Module This module provides machine learning tools…, Add cross-asset features (e.g., spread, correlation). Parameters ----------…, Get feature importance from trained model. Parameters ---------- model : Any…, Machine Learning Portfolio Optimizer Uses ML-based constraints and risk models. (+16 more)

### Community 20 - "Backend FastAPI Web"
Cohesion: 0.07
Nodes (26): AsyncSession, FastAPI, get_db(), init_db(), Database Module for WebUI Backend, Initialize database tables., Get database session., WebSocket (+18 more)

### Community 21 - "Simulacion Monte Carlo"
Cohesion: 0.08
Nodes (25): Monte Carlo Module Exports, bootstrap_simulation(), calculate_var_es(), MonteCarloSimulator, parametric_simulation(), Any, MonteCarloResult, ndarray (+17 more)

### Community 22 - "CLI Interactiva"
Cohesion: 0.09
Nodes (27): ask_float(), ask_int(), _count_open_positions(), _dispatch(), _get_current_price(), main(), monitor_loop(), _orchestrator_process_main() (+19 more)

### Community 23 - "Modelos Estadisticos ARCH"
Cohesion: 0.08
Nodes (24): ARCHModel, ARIMAModel, ARIMAResult, GARCHModel, Any, ndarray, Statistical Models for Probabilistic Forecasting This module provides time…, Generate probabilistic predictions with confidence intervals. Parameters… (+16 more)

### Community 24 - "Doc Vision Arquitectura Legacy"
Cohesion: 0.06
Nodes (32): 10. Position Sizing Optimization, 11. Execution Engine, 12. Backtesting Engine, 13. Monte Carlo Simulation, 14. Continuous Optimization, 1. Data Acquisition Module, 1. Separation of Concerns, 2. Data Cleaning & Normalization (+24 more)

### Community 25 - "Metodos de Clustering"
Cohesion: 0.09
Nodes (18): ElbowMethod, ndarray, Unsupervised Regime Clustering This module provides unsupervised learning…, Fit DBSCAN and predict labels. Parameters ---------- returns : np.ndarray…, Get cluster centroids (in original feature space). Returns ------- centroids :…, Get statistics for each cluster. Parameters ---------- returns : np.ndarray…, Unsupervised clustering of market regimes. This module uses K-Means and DBSCAN…, Calculate silhouette score for clustering quality. Parameters ----------… (+10 more)

### Community 26 - "Extraccion de Features de Regimen"
Cohesion: 0.09
Nodes (18): ndarray, Feature Extraction for Regime Detection This module provides feature extraction…, Extract volume-based features., Extract price-based features., Extract volatility-based features., Extract features for market regime detection. Features are based on statistical…, Extract autocorrelation features., Extract higher moments of returns distribution. (+10 more)

### Community 27 - "Modulo Position Sizing"
Cohesion: 0.07
Nodes (18): PositionSizer, Calculate position size based on portfolio value and risk per trade.…, Calculate fixed fractional position size. Parameters: -----------…, Position sizing calculator based on risk management., Calculate Kelly fraction. Parameters: ----------- win_rate : float Win rate…, Calculate optimal stop loss distance. Parameters: ----------- entry_price :…, Calculate stop loss as percentage of entry price., Calculate stop loss price. (+10 more)

### Community 28 - "Fuente de Datos Exchange"
Cohesion: 0.07
Nodes (18): ExchangeAPI, get_available_exchanges(), Any, CCXT Exchange Integration Provides unified interface to multiple cryptocurrency…, Fetch order book data Args: symbol: Trading pair limit: Number of depth levels…, Fetch current ticker information Args: symbol: Trading pair Returns: Ticker…, Fetch recent trades Args: symbol: Trading pair limit: Number of recent trades…, CCXT-based exchange interface (+10 more)

### Community 29 - "Sizing Adaptativo"
Cohesion: 0.08
Nodes (16): AdaptiveSizer, Calculate adaptive position size. Supports two modes: Risk-based mode (keyword…, Calculate position size based on recent trade performance. Parameters:…, Adaptive position sizing based on market conditions., Calculate position size based on market regime. Parameters: ----------- regime…, KellyCriterion, Calculate discrete Kelly fraction (fractional Kelly)., Calculate growth-optimal fraction. (+8 more)

### Community 30 - "Guia de Arquitectura"
Cohesion: 0.07
Nodes (27): Action Plan (Implementation Steps), Appendix: File-by-File Mapping, AQDE → Quant-Math Core (Duplicates Eliminated), Backward Compatibility, Broken / Orphaned Files (Cleanup Required), Core Dependencies (Required — Always Installed), Current Problems Identified, Duplicate Implementations (Must Consolidate) (+19 more)

### Community 31 - "Tests Estadisticos de Regimen"
Cohesion: 0.08
Nodes (17): ndarray, Statistical Tests for Market Regime Detection This module provides statistical…, Runs test for random sequence analysis. The runs test checks whether a sequence…, Perform runs test on return series. Parameters ---------- returns : np.ndarray…, Z-score based regime detection. The Z-score measures how many standard…, Check if the test result is statistically significant., Variance ratio test for mean reversion. The variance ratio test compares the…, Perform variance ratio test. Parameters ---------- returns : np.ndarray Daily… (+9 more)

### Community 32 - "Modulo PCA"
Cohesion: 0.12
Nodes (18): Principal Component Analysis (PCA) This module provides tools for…, compute_pca(), pca_denoising(), PCAAnalyzer, PCAResult, ndarray, PCA Analysis Module Provides Principal Component Analysis implementation for…, Transform data to PCA space. Parameters ---------- X : np.ndarray Data to… (+10 more)

### Community 33 - "Registro Multi-Agente"
Cohesion: 0.10
Nodes (15): Agent, AgentRegistry, AgentMessage, Any, Send a message to a specific agent. Args: sender: Sending agent receiver_id:…, Get message history. Args: agent_id: Filter by sender/receiver ID (optional)…, Get registry statistics. Returns: Dictionary with statistics about registered…, Get list of all registered agents with details. Returns: List of agent… (+7 more)

### Community 34 - "Nodos Auxiliares"
Cohesion: 0.08
Nodes (23): aqde, aqdePhaseClass, aqdeStatusClass, calculateProgress(), currentPhase, evaluationProgress, evolutionProgress, evolvedCount (+15 more)

### Community 35 - "Nodos Auxiliares"
Cohesion: 0.09
Nodes (21): aqde, aqdePhaseClass, aqdeProgress, aqdeStatusClass, events, health, hypotheses, pipelineStages (+13 more)

### Community 36 - "Nodos Auxiliares"
Cohesion: 0.10
Nodes (13): ndarray, Compute the entire efficient frontier. Parameters ---------- n_points : int…, Find portfolio with maximum Sharpe ratio. Returns ------- weights : np.ndarray…, Find portfolio with minimum variance. Returns ------- weights : np.ndarray…, Initialize Black-Litterman model. Two modes: Legacy mode: expected_returns :…, Optimize portfolio with views. Legacy mode: views is a dict {asset_index:…, Initialize risk parity optimizer. Parameters ---------- returns : np.ndarray…, Optimize risk parity portfolio. Parameters ---------- target_risk : float,… (+5 more)

### Community 37 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (11): DecisionEngine, Reescribe positions.jsonl con las posiciones vivas (atomico)., SL obligatorio 2:1 — siempre take_profit_pct / 2, sin excepcion., Cierra una posicion: la quita del estado vivo y la registra en el libro de…, Cantidad/notional de la ultima entrada abierta para key segun el libro…, SL vigente EN el momento de la entrada para key, derivado del take_profit_price…, Umbrales TP/SL de la posicion. Prioridad: los guardados al abrir la posicion ->…, Comprueba precio actual vs entrada para cada posicion abierta del simbolo y… (+3 more)

### Community 38 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (16): design_and_apply_emd(), EmpiricalModeAnalysis, EmpiricalModeDecomposition, ndarray, Empirical Mode Decomposition Module Implements Empirical Mode Decomposition…, Interpolate between extrema using spline interpolation. Parameters ----------…, Sifting process to extract one IMF from signal. Parameters ---------- signal :…, Decompose signal into IMFs and residue. Parameters ---------- signal : array-… (+8 more)

### Community 39 - "Nodos Auxiliares"
Cohesion: 0.10
Nodes (13): Agent, AgentRegistry, AgentMessage, Port for agent communication and coordination. Abstract base for specialized…, Send/receive a message, Get list of agent capabilities, Register this agent with the registry, Port for agent registry and communication. (+5 more)

### Community 40 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (14): callable, ndarray, Collection of statistical tests for strategy validation., Paired t-test (dependent samples). Args: sample1: First sample sample2: Second…, Jarque-Bera test for normality. Args: sample: Sample data Returns: Tuple of (JB…, Calculate t-statistic for one-sample t-test., Shapiro-Wilk test for normality (approximation). Args: sample: Sample data (max…, Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:… (+6 more)

### Community 41 - "Nodos Auxiliares"
Cohesion: 0.15
Nodes (13): PeriodogramAnalyzer, ndarray, Detect seasonality in the data. Parameters ---------- data : np.ndarray Time…, Periodogram analyzer. This class performs periodogram analysis to identify…, Compute spectral flatness. Parameters ---------- data : np.ndarray Time series…, Compute spectral kurtosis. Parameters ---------- data : np.ndarray Time series…, Compute auto-correlation of power spectrum. Parameters ---------- data :…, Plot periodogram. Parameters ---------- data : np.ndarray Time series data… (+5 more)

### Community 42 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (13): PowerSpectralDensity, ndarray, Compute spectral centroid. Parameters ---------- data : np.ndarray Time series…, Compute spectral bandwidth. Parameters ---------- data : np.ndarray Time series…, Compute spectral rolloff. Parameters ---------- data : np.ndarray Time series…, Power Spectral Density (PSD) analyzer. This class computes PSD using Welch's…, Compute spectral flux between two signals. Parameters ---------- data1 :…, Detect 1/f noise characteristics. Parameters ---------- data : np.ndarray Time… (+5 more)

### Community 43 - "Nodos Auxiliares"
Cohesion: 0.08
Nodes (23): AQDE (autonomous-research) — Essential Files, AQDE — Missing Dependencies, AQDE — Optional / Standalone Scripts, AQDE — Orphaned / Unreferenced / Broken, AQDE `requirements_simplified.txt` (More current), AQDE `requirements.txt`, AQDE — Shared Files (Used by Both Systems), Architecture Overview (+15 more)

### Community 44 - "Nodos Auxiliares"
Cohesion: 0.08
Nodes (24): get_active_strategies(), get_autonomous_status(), get_backtest_hypotheses(), get_events(), get_hypotheses(), get_monitoring_flow(), get_monitoring_hypotheses(), get_monitoring_simulations() (+16 more)

### Community 45 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (13): useApi(), useAutonomousApi(), useBacktestApi(), useConfigApi(), useDashboardApi(), useMonitoringApi(), useTradingApi(), useEquityChart() (+5 more)

### Community 46 - "Nodos Auxiliares"
Cohesion: 0.15
Nodes (14): callable, ContinuousWaveletTransform, cwt(), ndarray, Continuous Wavelet Transform (CWT) This module provides Continuous Wavelet…, Compute energy spectrum from CWT. Parameters ---------- data : np.ndarray Time…, Detect transient events in the time series. Parameters ---------- data :…, Plot CWT coefficients. Parameters ---------- data : np.ndarray Time series data… (+6 more)

### Community 47 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (11): HypothesisKnowledgeBase, Any, Get timeline of hypothesis development, Export all hypotheses to a file, Import hypotheses from a file, Stub implementation of HypothesisKnowledgeBase for integration testing., Retrieve hypothesis by ID, Search hypotheses based on criteria (+3 more)

### Community 48 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (15): DenoisingKalmanFilter, design_and_apply_kalman_filter(), KalmanFilter, ndarray, Kalman Filter Module Implements Kalman filtering for state estimation and noise…, Predict state estimate forward. Parameters ---------- u : ndarray, optional…, Update state estimate with measurement. Parameters ---------- z : float or…, Apply Kalman filter to sequence of measurements. Parameters ----------… (+7 more)

### Community 49 - "Nodos Auxiliares"
Cohesion: 0.15
Nodes (13): compute_fft(), FastFourierTransform, ndarray, Fast Fourier Transform (FFT) This module provides Fast Fourier Transform…, Find dominant frequency in the data. Parameters ---------- data : np.ndarray…, Fast Fourier Transform (FFT) analyzer. This class performs FFT analysis on time…, Compute FFT spectrum (magnitude squared). Parameters ---------- data :…, Detect presence of seasonality in the data. Parameters ---------- data :… (+5 more)

### Community 50 - "Nodos Auxiliares"
Cohesion: 0.10
Nodes (20): Architecture, Citation, Core Principles, Disclaimer, Documentation, Getting Started, Key Methodologies, License (+12 more)

### Community 51 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (12): callable, ndarray, Shapiro-Wilk test for normality. Args: sample: Sample data (max 5000…, Collection of statistical tests for strategy validation., Bootstrap p-value for a given statistic. Args: sample: Sample data statistic:…, Bootstrap confidence interval. Args: sample: Sample data statistic: Function to…, One-sample t-test. Args: sample: Sample data popmean: Population mean to test…, Test if strategy returns are significantly different from benchmark. Args:… (+4 more)

### Community 52 - "Nodos Auxiliares"
Cohesion: 0.15
Nodes (8): Cross-Symbol Validation (winner family lift), Orchestrator, Generate N hypotheses across configured symbols and backtest them., Convert an AQDE backtest result into a KB JSONL record., Fill a paper trade at the signal price with configured sizing/TP., generate -> persist -> decide -> paper execute -> feedback., Continuous loop (Ctrl+C to stop)., Continuous generation -> decision -> feedback loop.

### Community 53 - "Nodos Auxiliares"
Cohesion: 0.10
Nodes (15): areaPath, chartRef, colorMap, fillColor, hoverIndex, linePath, maxVal, minVal (+7 more)

### Community 54 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (17): useTradingStore, allConfirmed, apiConfig, closePosition(), confirmations, disableTrading(), emergencyStop(), enableTrading() (+9 more)

### Community 55 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (9): Any, Save iteration results to file, Print final summary of all iterations, Generate base hypothesis configurations for a symbol, Generate new hypotheses based on performance feedback - ENHANCED, Closes recientes REALES para los modelos; cache por ciclo., Create and register hypotheses for a symbol, Run Monte Carlo simulations for hypotheses (+1 more)

### Community 56 - "Nodos Auxiliares"
Cohesion: 0.16
Nodes (17): command, group, option, backtest(), cli(), discover(), export(), init_kb() (+9 more)

### Community 57 - "Nodos Auxiliares"
Cohesion: 0.15
Nodes (11): ndarray, Calculate Information Ratio (active return / tracking error). Args: returns:…, Calculate risk-adjusted performance metrics., Calculate Treynor ratio (excess return / beta). Args: returns: Strategy returns…, Calculate Omega ratio (probability-weighted gains / losses). Args: returns:…, Calculate all risk-adjusted metrics. Returns: Dictionary with all metrics, Calculate Sharpe ratio. Args: returns: Array of returns risk_free_rate: Risk-…, Calculate Sortino ratio (uses downside deviation). Args: returns: Array of… (+3 more)

### Community 58 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (16): activeHypotheses, activity, availableSymbols, config, iteration, maxIterations, phase, progress (+8 more)

### Community 59 - "Nodos Auxiliares"
Cohesion: 0.11
Nodes (17): 1. Backtesting Engine (`backtesting/backtester.py`), 2. Data Acquisition (`data_acquisition/data_sources/exchanges.py`), 3. Risk Management (`quant_math/risk/`), 4. Statistical Analysis (`quant_math/expectation/`), 5. Monte Carlo (`quant_math/monte_carlo/simulator.py`), 6. Autonomous Research (`quant_math/autonomous_research/`), Conclusion, Executive Summary (+9 more)

### Community 60 - "Nodos Auxiliares"
Cohesion: 0.18
Nodes (11): DataFrame, Series, Structural Break Detection Module Detects changes in data distribution and…, Detect regime changes in time series Args: df: Input DataFrame col: Column to…, Detect structural breaks in time series data, Test stationarity of time series Args: df: Input DataFrame col: Column to test…, Detect changes in trend using linear regression Args: df: Input DataFrame col:…, Comprehensive structural break analysis Args: df: Input DataFrame col: Column… (+3 more)

### Community 61 - "Nodos Auxiliares"
Cohesion: 0.11
Nodes (17): 1. Expectation Module (`expectation/`), 2. Risk Module (`risk/`), 3. Optimization Module (`optimization/`), 4. Execution Module (`execution/`), 5. Backtesting Module (`backtesting/`), 6. Master Module (`__init__.py`), Backtesting, ✅ Completed Modules (+9 more)

### Community 62 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (17): put, get_trading_metrics(), API Routes for Quant-Math WebUI, # TODO: Connect to actual AQDE state, Get paper trading metrics., # TODO: Connect to actual paper trading engine, # TODO: Connect to hypothesis database, # TODO: Connect to event store (+9 more)

### Community 63 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (10): Hypothesis, KnowledgeBase, Port for hypothesis knowledge management. Adapters implement this to store,…, Store a hypothesis and return its ID, Retrieve a hypothesis by ID, Search hypotheses based on criteria. Criteria can include: - strategy_type -…, Update an existing hypothesis, Get statistics about stored hypotheses (+2 more)

### Community 64 - "Nodos Auxiliares"
Cohesion: 0.11
Nodes (10): MonteCarloResult, StrategyResult, Test statistical significance of strategy performance. Returns p-value or…, Calculate Calmar ratio, Use bootstrap resampling to estimate significance. Returns bootstrap p-value., Run Monte Carlo simulation on strategy results, Calculate Value at Risk, Calculate probability of loss (+2 more)

### Community 65 - "Nodos Auxiliares"
Cohesion: 0.16
Nodes (11): DrawdownAnalyzer, Any, ndarray, Calculate average drawdown duration., Calculate maximum drawdown duration., Calculate Ulcer Index (root mean square of drawdowns). Ulcer Index =…, Analyze drawdowns from equity curve or returns., Calculate drawdown series and metrics from equity curve. Args: equity_curve:… (+3 more)

### Community 66 - "Nodos Auxiliares"
Cohesion: 0.18
Nodes (10): HarmonicComponentAnalyzer, ndarray, Reconstruct signal from top harmonics. Parameters ---------- data : np.ndarray…, Harmonic component analyzer. This class identifies and analyzes harmonic…, Compute ratio between harmonic components. Parameters ---------- data :…, Analyze periodicity in the data. Parameters ---------- data : np.ndarray Time…, Plot harmonic components. Parameters ---------- data : np.ndarray Time series…, Plot frequency spectrum highlighting harmonics. Parameters ---------- data :… (+2 more)

### Community 67 - "Nodos Auxiliares"
Cohesion: 0.11
Nodes (14): areaPath, colorMap, fillColor, hoverPoint, linePath, maxVal, minVal, points (+6 more)

### Community 68 - "Nodos Auxiliares"
Cohesion: 0.11
Nodes (15): filteredHypotheses, flow, hypFilter, hypotheses, hypothesisStatuses, loading, simulationGroups, simulations (+7 more)

### Community 69 - "Nodos Auxiliares"
Cohesion: 0.16
Nodes (11): AQDERunner, CryptoSymbol, main(), Fuerza re-descarga en el siguiente acceso (inicio de ciclo nuevo)., Fetch top N symbols by volume from Bybit, Represents a crypto trading pair with metadata, Main runner for the Autonomous Quant Discovery Engine, Quant-Math Orchestrator. Connects the full discovery -> decision -> feedback… (+3 more)

### Community 70 - "Nodos Auxiliares"
Cohesion: 0.13
Nodes (17): DecisionEngine.decide(), Expectancy Gate Invariant (Sacred Gate), Family x Symbol Feedback Buckets, SL Overshoot Structural Slippage, LEARN_MODE Gate Bypass, paper_executions.jsonl Append-Only Ledger, SL = TP/2 Fixed 2:1 Risk Rule, runtime/state/graduation.json (+9 more)

### Community 71 - "Nodos Auxiliares"
Cohesion: 0.18
Nodes (7): Any, Register/overwrite a hypothesis record in the JSONL KB., Todos los candidatos consultables ordenados por (expectancy DESC,…, Best hypothesis for symbol by (expectancy DESC, scientific_score DESC)., Direction from momentum on real closes (lookback from params)., Run one decision cycle for a symbol., Decide for all configured symbols.

### Community 72 - "Nodos Auxiliares"
Cohesion: 0.21
Nodes (9): Any, Stop loss calculator with multiple methods. Supports: - Fixed percentage - ATR-…, Chandelier exit stop loss., Volatility-adjusted stop loss., Calculate multiple stop loss levels. Args: entry_price: Entry price side:…, Initialize stop loss calculator. Args: default_method: Default stop loss method…, Calculate stop loss price. Args: entry_price: Entry price side: 'long' or…, Fixed percentage stop loss. (+1 more)

### Community 73 - "Nodos Auxiliares"
Cohesion: 0.16
Nodes (11): BandPassFilter, design_and_apply_band_pass(), ndarray, Band-Pass Filter Module Implements band-pass filters to retain only specific…, Apply band-pass filter to input data. Parameters ---------- data : array-like…, Apply filter in real-time with phase delay (for online applications).…, Compute frequency response of the band-pass filter. Returns ------- w : ndarray…, Analyze signal power in passband vs stopbands. Parameters ----------… (+3 more)

### Community 74 - "Nodos Auxiliares"
Cohesion: 0.16
Nodes (11): design_and_apply_high_pass(), HighPassFilter, ndarray, High-Pass Filter Module Implements high-pass filters to remove low-frequency…, Apply filter using zero-pole-gain representation (more stable for long data).…, Compute frequency response of the filter. Returns ------- w : ndarray Angular…, Analyze signal bandwidth before and after filtering. Parameters ----------…, Convenience function to design and apply high-pass filter in one step.… (+3 more)

### Community 75 - "Nodos Auxiliares"
Cohesion: 0.17
Nodes (15): closeDropdown(), containerRef, emit, filteredOptions, focused, handleClickOutside(), handleKeydown(), hoveredIndex (+7 more)

### Community 76 - "Nodos Auxiliares"
Cohesion: 0.16
Nodes (14): useConfigStore, config, loadConfig(), loading, resetConfig(), saveConfig(), saving, sections (+6 more)

### Community 77 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (12): backtestStore, configStore, configValues, effectiveConfig, error, form, hypotheses, loadingDetail (+4 more)

### Community 78 - "Nodos Auxiliares"
Cohesion: 0.19
Nodes (9): ndarray, Run walk-forward validation. Parameters ---------- strategy_func : callable…, Grid search optimization on training data., Run backtest with specific parameters., Compute aggregate statistics., Compute robustness score (0-100)., Compute parameter stability across windows (0-100)., Walk-Forward Validation Engine Implements walk-forward analysis for robust… (+1 more)

### Community 79 - "Nodos Auxiliares"
Cohesion: 0.17
Nodes (9): DataFrame, ndarray, Cap outliers to specified bounds Args: df: DataFrame column: Column to cap…, Detect and count duplicate rows Args: df: Input DataFrame Returns: DataFrame…, Remove duplicate rows Args: df: Input DataFrame subset: Columns to check for…, Perform comprehensive data quality check Args: df: Input DataFrame Returns:…, Perform complete data cleaning pipeline Args: df: Input DataFrame…, Handle missing values in DataFrame Args: df: Input DataFrame method: 'ffill',… (+1 more)

### Community 80 - "Nodos Auxiliares"
Cohesion: 0.13
Nodes (9): DataFrame, Series, Calculate returns from price data Args: df: Input DataFrame with price column…, Calculate volatility Args: df: Input DataFrame with price column price_col:…, Shift data by specified periods Args: df: Input DataFrame cols: Columns to…, Create time-based features Args: df: Input DataFrame timestamp_col: Timestamp…, Resample to specific frequency Args: df: Input DataFrame target_freq: Target…, Resample time series data Args: df: Input DataFrame with timestamp column… (+1 more)

### Community 81 - "Nodos Auxiliares"
Cohesion: 0.12
Nodes (15): bootstrap_confidence_interval(), bootstrap_p_value(), one_sample_ttest(), paired_ttest(), Statistical Tests Module Statistical significance testing for trading strategy…, Convenience function for one-sample t-test., Convenience function for two-sample t-test., Convenience function for paired t-test. (+7 more)

### Community 82 - "Nodos Auxiliares"
Cohesion: 0.17
Nodes (10): Any, ndarray, Calculate various return metrics from trade history or price series., Calculate returns from trade history. Args: trades: List of trade dictionaries…, Calculate cumulative return from returns series., Calculate annualized return., Calculate geometric mean of returns., Calculate arithmetic mean of returns. (+2 more)

### Community 83 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (9): Any, StrategyResult, Calculate Kelly optimal position size. Args: hypothesis_id: Hypothesis ID…, Calculate comprehensive risk metrics for strategy. Args: result: StrategyResult…, Check correlation risk with other strategies. Args: hypothesis_id: Hypothesis…, Perform stress testing on strategy. Args: result: StrategyResult from backtest…, Apply stress scenario to strategy results, Get risk check history for a hypothesis (+1 more)

### Community 84 - "Nodos Auxiliares"
Cohesion: 0.22
Nodes (15): example_fft_analysis(), example_harmonic_analysis(), example_periodogram_analysis(), example_psd_analysis(), example_wavelet_analysis(), generate_sample_data(), main(), ndarray (+7 more)

### Community 85 - "Nodos Auxiliares"
Cohesion: 0.26
Nodes (15): flat_candles(), make(), Riesgo + persistencia de posiciones: SL 2:1 obligatorio, cierres TP/SL en el…, TP tambien cierra; el libro es append-only y nunca se resetea., Deja en el estado una posicion abierta como si viniera de sesion previa., SL = TP/2 exacto para cualquier TP configurado., Posicion abierta -> 'reinicio' -> se recupera, guarda y sigue monitoreando., Precio cae al nivel del SL -> cierre con motivo='sl' en el libro. (+7 more)

### Community 86 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (8): ExchangeManager, Register an exchange. Parameters: ----------- name : str Exchange name api_key…, Set the active exchange. Parameters: ----------- name : str Exchange name…, Get the active exchange configuration., Manage multiple cryptocurrency exchanges., Place an order. Parameters: ----------- symbol : str Trading symbol (e.g.,…, Initialize exchange manager., Cancel an order. Parameters: ----------- order_id : str Order ID Returns:…

### Community 87 - "Nodos Auxiliares"
Cohesion: 0.13
Nodes (15): post, close_position(), disable_trading(), emergency_stop(), enable_trading(), Save configuration values., Stop autonomous mode., Enable real trading with Bybit. (+7 more)

### Community 88 - "Nodos Auxiliares"
Cohesion: 0.21
Nodes (9): PositionSizer, Any, Volatility targeting position sizing., Unified position sizing calculator. Supports multiple sizing algorithms: -…, ATR-based position sizing., Initialize position sizer. Args: default_method: Default sizing method…, Calculate position size based on method. Args: account_value: Total account…, Fixed fractional position sizing. (+1 more)

### Community 89 - "Nodos Auxiliares"
Cohesion: 0.19
Nodes (10): design_and_apply_wavelet_denoise(), ndarray, Wavelet Decomposition Module Implements wavelet-based denoising and signal…, Denoise signal using wavelet thresholding. Parameters ---------- signal :…, Get multi-resolution analysis information. Parameters ---------- signal :…, Convenience function to denoise signal in one step. Parameters ----------…, Wavelet-based denoising and signal decomposition. This class implements wavelet…, Initialize wavelet denoiser. Parameters ---------- wavelet : str, optional… (+2 more)

### Community 90 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (10): isDark, navItems, route, router, store, wsStatus, app, pinia (+2 more)

### Community 91 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (8): Risk Manager Implementation. Implements the RiskManager port for risk…, MonteCarloResult, Result of Monte Carlo simulation. Provides statistical distribution of strategy…, Test statistical significance of strategy performance. Returns p-value or…, Run Monte Carlo simulation on strategy performance. Uses bootstrapping or…, Run Monte Carlo simulation on strategy results, Result of backtesting a hypothesis/strategy. Contains performance metrics and…, StrategyResult

### Community 92 - "Nodos Auxiliares"
Cohesion: 0.19
Nodes (11): Agent Registry for managing specialized research agents. The registry maintains…, AgentMessage, Enum, Core domain interfaces for AQDE. This module defines the hexagonal architecture…, Communication message between agents. Supports both synchronous and…, Type of trading strategy, Signal strength classification, Status of a hypothesis/strategy (+3 more)

### Community 93 - "Nodos Auxiliares"
Cohesion: 0.20
Nodes (13): example_band_pass_filter(), example_emd(), example_high_pass_filter(), example_kalman_filter(), example_wavelet_denoising(), generate_test_signal(), Signal Processing Module Example Usage This module demonstrates how to use the…, Example: Band-pass filtering to isolate specific frequency bands. (+5 more)

### Community 94 - "Nodos Auxiliares"
Cohesion: 0.14
Nodes (9): activeCount, avgSharpe, selectedStrategy, statusLabels, stopStrategy(), store, strategies, totalPnL (+1 more)

### Community 95 - "Nodos Auxiliares"
Cohesion: 0.25
Nodes (10): useWebSocket(), clearTimers(), connect(), disconnect(), scheduleReconnect(), send(), useAutonomousStore, useBacktestStore (+2 more)

### Community 96 - "Nodos Auxiliares"
Cohesion: 0.17
Nodes (13): BaseModel, AQDEStatus, AutonomousConfig, BacktestRequest, BacktestResponse, Event, get_aqde_status(), Hypothesis (+5 more)

### Community 97 - "Nodos Auxiliares"
Cohesion: 0.23
Nodes (7): DataFrame, Standardize multiple columns Args: df: Input DataFrame method: 'zscore',…, Normalize all numerical columns Args: df: Input DataFrame method: Normalization…, Inverse transform normalized data Args: df_norm: Normalized DataFrame scaler:…, Min-Max normalization Args: df: Input DataFrame feature_range: Desired range…, Z-score normalization (standardization) Args: df: Input DataFrame columns:…, Robust scaling (using median and IQR) Args: df: Input DataFrame columns:…

### Community 98 - "Nodos Auxiliares"
Cohesion: 0.19
Nodes (8): BacktestEngine, Any, Port for backtesting hypotheses. Adapters implement this to execute backtests…, Run backtest on a hypothesis. Args: hypothesis: Hypothesis to test data: Market…, Get trade history for a hypothesis, Get all performance metrics for a hypothesis, Optimize hypothesis parameters over a search space. Returns the best parameters…, Execute a specific task

### Community 99 - "Nodos Auxiliares"
Cohesion: 0.17
Nodes (10): format, formatTime(), emit, formatDate(), formatDateTime(), props, statusLabels, formatTime() (+2 more)

### Community 100 - "Nodos Auxiliares"
Cohesion: 0.23
Nodes (12): autonomousLoading, emit, emitAutonomous(), emitBacktest(), emitRealTrading(), emitRestart(), emitStart(), emitStop() (+4 more)

### Community 101 - "Nodos Auxiliares"
Cohesion: 0.18
Nodes (7): Calculate Sharpe ratio. Parameters: ----------- returns : List[float] Period…, Calculate Sortino ratio (downside deviation). Parameters: ----------- returns :…, Calculate Sharpe ratio and related metrics., Calculate information ratio. Parameters: ----------- returns : List[float]…, SharpeMetrics, jarque_bera_test(), Convenience function for Jarque-Bera test.

### Community 102 - "Nodos Auxiliares"
Cohesion: 0.17
Nodes (8): Drawdown Analyzer Module Calculates drawdown metrics for risk assessment., Expectation Calculation Module (Module 8) Statistical significance testing and…, Return Calculator Module Calculates various return metrics for trading…, Sharpe Metrics Module Calculates Sharpe, Sortino, Calmar and other risk-…, bootstrap_p_value(), jarque_bera_test(), Convenience function for Jarque-Bera test., Convenience function for bootstrap p-value.

### Community 103 - "Nodos Auxiliares"
Cohesion: 0.20
Nodes (11): bootstrap_confidence_interval(), one_sample_ttest(), paired_ttest(), Statistical Tests Module Statistical significance testing for trading strategy…, Convenience function for one-sample t-test., Convenience function for Shapiro-Wilk test., Convenience function for bootstrap confidence interval., Convenience function for strategy significance testing. (+3 more)

### Community 104 - "Nodos Auxiliares"
Cohesion: 0.18
Nodes (6): Calculate simple returns from price series. Parameters: ----------- prices :…, Calculate log returns from price series. Parameters: ----------- prices :…, Calculate annualized return. Parameters: ----------- returns : List[float]…, Calculate various return metrics., Calculate cumulative return from price series. Parameters: ----------- prices :…, ReturnCalculator

### Community 105 - "Nodos Auxiliares"
Cohesion: 0.18
Nodes (6): DrawdownAnalyzer, Calculate drawdowns from price series. Parameters: ----------- prices :…, Calculate maximum drawdown. Parameters: ----------- drawdowns : List[float]…, Calculate average drawdown. Parameters: ----------- drawdowns : List[float]…, Analyze drawdowns from price series., Calculate drawdown duration (time from peak to valley). Parameters: -----------…

### Community 106 - "Nodos Auxiliares"
Cohesion: 0.20
Nodes (7): DataProvider, datetime, Port for data access in AQDE. Adapters implement this to provide market data,…, Fetch market data for a given symbol and date range. Args: symbol: Trading…, Extract features for a specific date/time. Features can include technical…, Get list of available trading symbols, Get data quality metrics for a symbol. Returns completeness, accuracy, and…

### Community 107 - "Nodos Auxiliares"
Cohesion: 0.22
Nodes (5): Cierres de UNA hipotesis+simbolo segun el libro permanente., PA: expectancy viva con shrinkage bayesiano doble. 1) est = (n*media_propia +…, Cierres del simbolo en el libro (todas las familias)., Operaciones cerradas de la familia+simbolo segun el libro permanente (fuente…, Entrega feedback AGREGADO por familia cuando las operaciones de esa familia…

### Community 108 - "Nodos Auxiliares"
Cohesion: 0.35
Nodes (10): flat(), make(), Opcion B: feedback agregado por FAMILIA x SIMBOLO. Las keys rotan (cada una con…, 3 cierres de la MISMA familia (keys rotando o no): la familia llega a 3 ops ->…, n=3 entrega; n=6 vuelve a entregar (bucket 2)., El contrato original por-key (min=3) NO cambia: con 1 op no entrega., seed_hyp(), test_bucket_multiple_delivers_again() (+2 more)

### Community 109 - "Nodos Auxiliares"
Cohesion: 0.20
Nodes (6): Auditor, Port for audit and compliance. Adapters implement this to track experiments,…, Log an experiment run with full details, Get experiment history for a hypothesis, Verify that an experiment can be reproduced, Get audit trail for a backtest. Includes data versioning, parameter logs,…

### Community 110 - "Nodos Auxiliares"
Cohesion: 0.20
Nodes (6): Port for risk management checks. Adapters implement this to ensure hypotheses…, Check if position size meets risk criteria. Returns OK or failure reasons., Check if drawdown is within acceptable limits, Check if Sharpe ratio meets threshold, Check if Sortino ratio meets threshold, RiskManager

### Community 111 - "Nodos Auxiliares"
Cohesion: 0.27
Nodes (9): list_modules(), main(), QUANT-MATH Main Entry Point Unified CLI entry point for the QUANT-MATH…, List available modules with descriptions., Main CLI entry point., Run integration tests., Show framework information., run_tests() (+1 more)

### Community 112 - "Nodos Auxiliares"
Cohesion: 0.33
Nodes (9): make_engine(), Decision Engine behavior tests: abstention (no_entry) and operation (entry)., All hypotheses with expectancy <= 0 -> no_entry, zero signals., One hypothesis with expectancy > 0 -> entry signal generated., Low scientific_score degrades to failed but stays queryable; ordering by…, run_all(), test_abstention_all_nonpositive_expectancy(), test_failed_status_still_queryable_and_best_selection_ordering() (+1 more)

### Community 113 - "Nodos Auxiliares"
Cohesion: 0.49
Nodes (9): closure(), make(), PA: expectancy viva con shrinkage doble (propio->familia, realizado->…, seed_ledger(), test_pa_expectancy_shrinks_toward_realized(), test_pa_ranking_flips_when_live_results_bad(), test_pb_graduates_on_positive_window(), test_pb_no_graduation_on_negative_window() (+1 more)

### Community 114 - "Nodos Auxiliares"
Cohesion: 0.22
Nodes (5): Agent, Port for agent communication and coordination. Abstract base for specialized…, Send/receive a message, Get list of agent capabilities, Register this agent with the registry

### Community 115 - "Nodos Auxiliares"
Cohesion: 0.33
Nodes (3): HiddenMarkovModel, ndarray, test_regime_detection()

### Community 116 - "Nodos Auxiliares"
Cohesion: 0.31
Nodes (3): ndarray, test_var(), ValueAtRisk

### Community 117 - "Nodos Auxiliares"
Cohesion: 0.22
Nodes (8): autonomousStore, currentStore, dashboardStore, monitoringStore, route, routeStoreMap, statusClass, statusText

### Community 118 - "Nodos Auxiliares"
Cohesion: 0.25
Nodes (4): Datos de mercado para backtesting con cache intra-ciclo: si (symbol, timeframe,…, Run walk-forward validation on top hypotheses, Create a strategy function from a hypothesis, Get parameter grid for walk-forward optimization

### Community 119 - "Nodos Auxiliares"
Cohesion: 0.36
Nodes (7): main(), Example: Risk factor model., Example: Feature engineering., Example: ML-based portfolio optimization., test_factor_model(), test_feature_engineering(), test_ml_portfolio()

### Community 120 - "Nodos Auxiliares"
Cohesion: 0.36
Nodes (7): main(), Example: Risk Parity Portfolio., Example: Efficient Frontier., Example: Black-Litterman Model., test_black_litterman(), test_efficient_frontier(), test_risk_parity()

### Community 121 - "Nodos Auxiliares"
Cohesion: 0.25
Nodes (4): Adapters for AQDE - Implementation of hexagonal architecture ports. These…, Stub module for HypothesisKnowledgeBase to fix imports., Autonomous Quant Discovery Engine (AQDE) A modular system for autonomous…, QUANT-MATH: Quantitative Trading Framework A modular research framework for…

### Community 122 - "Nodos Auxiliares"
Cohesion: 0.25
Nodes (5): Port for statistical validation of hypotheses. Adapters implement this to…, Calculate win rate from trade history, Calculate Sharpe ratio, Calculate Sortino ratio, StatisticalValidator

### Community 123 - "Nodos Auxiliares"
Cohesion: 0.25
Nodes (4): Harmonic Component Analysis This module provides harmonic component analysis…, Spectral Analysis This module provides frequency domain analysis techniques…, Periodogram Analysis This module provides periodogram-based frequency analysis…, Power Spectral Density (PSD) This module provides Power Spectral Density…

### Community 124 - "Nodos Auxiliares"
Cohesion: 0.29
Nodes (6): BacktestEngine, KnowledgeBase, MonteCarloEngine, Initialize the Research Manager. Args: knowledge_base: Port for hypothesis…, RiskManager, StatisticalValidator

### Community 125 - "Nodos Auxiliares"
Cohesion: 0.33
Nodes (5): Enum, Research Manager - Main Orchestrator for AQDE. The Research Manager coordinates…, Phases of the research workflow, Set current research phase, ResearchPhase

### Community 126 - "Nodos Auxiliares"
Cohesion: 0.29
Nodes (5): MonteCarloEngine, Protocol, Port for Monte Carlo simulation. Adapters implement this to run Monte Carlo…, Get confidence interval for a metric, Test robustness across multiple simulated scenarios. Returns distribution…

### Community 127 - "Nodos Auxiliares"
Cohesion: 0.33
Nodes (5): BaseSettings, Config, Quant-Math WebUI Backend Configuration, Application settings loaded from environment variables., Settings

### Community 128 - "Nodos Auxiliares"
Cohesion: 0.33
Nodes (5): OrchestratorConfig, Explicit configuration. Required fields have NO hidden defaults., test_dedupe_filters_duplicates_across_cycles(), Familia ganadora en ETH -> backtested se eleva a validated para XRP; metricas…, test_cross_symbol_validation()

### Community 129 - "Nodos Auxiliares"
Cohesion: 0.60
Nodes (5): make(), P1: cuando el mejor candidato tiene posicion abierta, decide() cae al siguiente…, test_fallback_to_next_best_when_best_open(), test_skip_contract_when_all_blocked(), up()

### Community 130 - "Nodos Auxiliares"
Cohesion: 0.47
Nodes (5): emit, handleChange(), handleInput(), props, showPassword

### Community 131 - "Nodos Auxiliares"
Cohesion: 0.40
Nodes (3): Decision Engine: expectancy-gated trade decision loop over AQDE hypotheses., _learn_mode_default(), Trading Decision Engine. Selects the best hypothesis per symbol from the JSONL-…

### Community 134 - "Nodos Auxiliares"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 136 - "Nodos Auxiliares"
Cohesion: 0.50
Nodes (3): props, sizeClass, variantClass

### Community 138 - "Nodos Auxiliares"
Cohesion: 0.50
Nodes (3): formattedValue, props, valueColor

### Community 139 - "Nodos Auxiliares"
Cohesion: 0.67
Nodes (3): emit, props, selectItem()

### Community 140 - "Nodos Auxiliares"
Cohesion: 0.50
Nodes (3): statusClass, statusText, store

### Community 143 - "Nodos Auxiliares"
Cohesion: 0.67
Nodes (3): ConfigSection, get_config_sections(), Get available configuration sections.

### Community 144 - "Nodos Auxiliares"
Cohesion: 0.67
Nodes (3): get_health(), HealthResponse, Get system health metrics.

### Community 145 - "Nodos Auxiliares"
Cohesion: 0.67
Nodes (3): websocket, WebSocket endpoint for real-time updates., websocket_endpoint()

## Knowledge Gaps
- **348 isolated node(s):** `Config`, `AQDE (autonomous-research) — Essential Files`, `AQDE — Missing Dependencies`, `AQDE — Optional / Standalone Scripts`, `AQDE — Orphaned / Unreferenced / Broken` (+343 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExchangeAPI` connect `Fuente de Datos Exchange` to `Criterios de Busqueda AQDE`, `Nodos Auxiliares`, `DataStore y Limpieza de Datos`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Motor de Backtesting`, `Nodos Auxiliares`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `DecisionEngine` connect `Nodos Auxiliares` to `Nodos Auxiliares`, `Nodos Auxiliares`, `Generador ARIMA-GARCH y Prior ML`, `Knowledge Base PostgreSQL`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Fuente de Datos Exchange`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `ResearchManager` connect `DataStore y Limpieza de Datos` to `Nodos Auxiliares`, `Motor de Backtesting`, `Nodos Auxiliares`, `Nodos Auxiliares`, `Nodos Auxiliares`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `DecisionEngine` (e.g. with `ExchangeAPI` and `KBPersistence`) actually correct?**
  _`DecisionEngine` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `QuantMathAdapter` (e.g. with `ExchangeAPI` and `OrderManager`) actually correct?**
  _`QuantMathAdapter` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `run_full_e2e_test()` (e.g. with `StrategyType` and `ExpectedShortfall`) actually correct?**
  _`run_full_e2e_test()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `OrderManager` (e.g. with `AlgoTradingSystem` and `POV`) actually correct?**
  _`OrderManager` has 4 INFERRED edges - model-reasoned connections that need verification._