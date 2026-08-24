#!/usr/bin/env python3
"""
AQDE Runner - Autonomous Quant Discovery Engine with Bybit Integration

This script runs the complete AQDE pipeline:
1. Uses Bybit as the data provider
2. Fetches data for top 5 volume crypto pairs
3. Generates multiple hypotheses per pair
4. Backtests all hypotheses
5. Implements feedback loop to learn and generate new hypotheses
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add project root to path
sys.path.insert(0, '/data/data/com.termux/files/home/quant-math')

from quant_math.autonomous_research import (
    ResearchManager,
    AgentRegistry,
    QuantMathAdapter,
    HypothesisKnowledgeBase,
    Hypothesis,
    StrategyType,
    StrategyStatus,
)
from quant_math.autonomous_research.interfaces import StrategyResult, MonteCarloResult
from quant_math.autonomous_research.adapters.quant_math_adapter import HAS_QUANT_MATH
from backtesting import Backtester, WalkForwardValidator
import numpy as np


@dataclass
class CryptoSymbol:
    """Represents a crypto trading pair with metadata"""
    symbol: str
    volume: float
    rank: int


class AQDERunner:
    """Main runner for the Autonomous Quant Discovery Engine"""

    def __init__(
        self,
        exchange_id: str = "bybit",
        knowledge_base_path: str = "autonomous_research/data/hypotheses",
        top_n_symbols: int = 20,
        min_volume_usd: float = 1_000_000,
        timeframe: str = "1h",
        lookback_days: int = 365,
        hypotheses_per_symbol: int = 15,
        feedback_iterations: int = 10,
        dry_run: bool = False,
        force_real_data: bool = False,
        hypothesis_ranker=None
    ):
        self.exchange_id = exchange_id
        self.knowledge_base_path = knowledge_base_path
        self.top_n_symbols = top_n_symbols
        self.min_volume_usd = min_volume_usd
        self.timeframe = timeframe
        self.lookback_days = lookback_days
        self.hypotheses_per_symbol = hypotheses_per_symbol
        self.feedback_iterations = feedback_iterations
        # dry_run controls ONLY the execution mode convenience switches.
        # force_real_data=True keeps market data REAL even when dry_run=True
        # (used by the orchestrator: dry_run never means synthetic data).
        self.force_real_data = force_real_data
        self.dry_run = dry_run
        # Optional advisory callable(templates, symbol) -> reordered templates.
        # Applied BEFORE top-N selection; NEVER touches the decision gate.
        self.hypothesis_ranker = hypothesis_ranker

        # Initialize components
        self.adapter = QuantMathAdapter(
            exchange_id=exchange_id,
            knowledge_base_path=knowledge_base_path
        )
        self.knowledge_base = self.adapter.knowledge_base
        self.research_manager = ResearchManager(
            knowledge_base=self.knowledge_base,
            backtest_engine=self.adapter,
            monte_carlo_engine=self.adapter,
            statistical_validator=self.adapter,
            risk_manager=self.adapter,
            agent_registry=AgentRegistry()
        )

        # State
        self.symbols: List[CryptoSymbol] = []
        self.all_hypotheses: Dict[str, Hypothesis] = {}
        self.performance_history: List[Dict] = []
        self.iteration = 0
        # Cache INTRA-CICLO de datos de mercado: clave (symbol, timeframe,
        # lookback_days). El orchestrator la invalida al inicio de cada ciclo;
        # nunca persiste entre ciclos.
        self._mkt_cache: Dict[Any, Any] = {}

    def invalidate_market_cache(self):
        """Fuerza re-descarga en el siguiente acceso (inicio de ciclo nuevo)."""
        self._mkt_cache.clear()

    def get_or_fetch_market_data(self, symbol: str):
        """Datos de mercado para backtesting con cache intra-ciclo: si
        (symbol, timeframe, lookback_days) ya se descargo en este ciclo, se
        reutiliza para TODAS las hipotesis en lugar de repetir ~130 peticiones
        (caso 1m/90d)."""
        key = (symbol, self.timeframe, self.lookback_days)
        if key in self._mkt_cache:
            print(f"  [cache] {symbol} {self.timeframe}/{self.lookback_days}d "
                  f"reutilizado del ciclo actual")
            return self._mkt_cache[key]
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days)
        if self.dry_run and not self.force_real_data:
            market_data = self.adapter.generate_synthetic_data(
                symbol, n_candles=1000)
        else:
            market_data = self.adapter.fetch_market_data(
                symbol, start_date, end_date, self.timeframe)
        self._mkt_cache[key] = market_data
        return market_data

    def fetch_top_symbols(self) -> List[CryptoSymbol]:
        """Fetch top N symbols by volume from Bybit"""
        print(f"\n{'='*60}")
        print(f"Fetching top {self.top_n_symbols} symbols from {self.exchange_id}...")
        print(f"{'='*60}")

        if self.dry_run:
            # Return synthetic symbols for testing
            self.symbols = [
                CryptoSymbol("BTC/USDT", 455_000_000, 1),
                CryptoSymbol("ETH/USDT", 124_000_000, 2),
                CryptoSymbol("XRP/USDT", 20_000_000, 3),
                CryptoSymbol("AAVE/USDT", 19_600_000, 4),
                CryptoSymbol("SOL/USDT", 19_100_000, 5),
            ]
            print(f"\nTop {self.top_n_symbols} symbols by volume (DRY RUN):")
            for sym in self.symbols:
                print(f"  {sym.rank}. {sym.symbol}: ${sym.volume:,.0f}")
            return self.symbols

        import ccxt
        ex = ccxt.bybit({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
        markets = ex.load_markets()

        # Filter USDT pairs
        usdt_pairs = [s for s in markets if s.endswith('/USDT') and markets[s].get('active', True)]

        # Get tickers in batches
        top_pairs = []
        batch_size = 50
        for i in range(0, min(len(usdt_pairs), 200), batch_size):
            batch = usdt_pairs[i:i+batch_size]
            try:
                tickers = ex.fetch_tickers(batch)
                for s, t in tickers.items():
                    if 'quoteVolume' in t and t['quoteVolume'] and t['quoteVolume'] >= self.min_volume_usd:
                        top_pairs.append((s, t['quoteVolume']))
            except Exception as e:
                print(f"  Warning: Error fetching batch {i}: {e}")

        top_pairs.sort(key=lambda x: x[1], reverse=True)
        self.symbols = [
            CryptoSymbol(symbol=s, volume=v, rank=i+1)
            for i, (s, v) in enumerate(top_pairs[:self.top_n_symbols])
        ]

        print(f"\nTop {self.top_n_symbols} symbols by volume:")
        for sym in self.symbols:
            print(f"  {sym.rank}. {sym.symbol}: ${sym.volume:,.0f}")

        return self.symbols

    def generate_base_hypotheses(self, symbol: str) -> List[Dict[str, Any]]:
        """Generate base hypothesis configurations for a symbol"""
        hypotheses = []

        # Strategy templates for different market conditions
        strategy_templates = [
            {
                "name": f"EMA_Crossover_{symbol.replace('/', '')}",
                "description": f"EMA crossover strategy for {symbol}",
                "strategy_type": StrategyType.TREND_FOLLOWING,
                "parameters": {
                    "strategy_type": "ema_crossover",
                    "short_window": 12,
                    "long_window": 26,
                    "symbol": symbol,
                }
            },
            {
                "name": f"RSI_Reversion_{symbol.replace('/', '')}",
                "description": f"RSI mean reversion for {symbol}",
                "strategy_type": StrategyType.MEAN_REVERSION,
                "parameters": {
                    "strategy_type": "rsi_reversion",
                    "rsi_period": 14,
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "symbol": symbol,
                }
            },
            {
                "name": f"Bollinger_Bands_{symbol.replace('/', '')}",
                "description": f"Bollinger Bands reversion for {symbol}",
                "strategy_type": StrategyType.MEAN_REVERSION,
                "parameters": {
                    "strategy_type": "bb_reversion",
                    "bb_period": 20,
                    "bb_std": 2.0,
                    "symbol": symbol,
                }
            },
            {
                "name": f"Breakout_{symbol.replace('/', '')}",
                "description": f"Donchian breakout strategy for {symbol}",
                "strategy_type": StrategyType.BREAKOUT,
                "parameters": {
                    "strategy_type": "donchian_breakout",
                    "donchian_window": 20,
                    "symbol": symbol,
                }
            },
            {
                "name": f"Dual_EMA_Trend_{symbol.replace('/', '')}",
                "description": f"Triple EMA trend filter for {symbol}",
                "strategy_type": StrategyType.TREND_FOLLOWING,
                "parameters": {
                    "strategy_type": "dual_ema",
                    "dual_fast": 8,
                    "dual_mid": 21,
                    "dual_slow": 55,
                    "symbol": symbol,
                }
            },
            {
                "name": f"VWAP_Reversion_{symbol.replace('/', '')}",
                "description": f"VWAP mean reversion for {symbol}",
                "strategy_type": StrategyType.MEAN_REVERSION,
                "parameters": {
                    "strategy_type": "vwap_reversion",
                    "vwap_window": 20,
                    "vwap_threshold": 0.02,
                    "symbol": symbol,
                }
            },
            {
                "name": f"MACD_{symbol.replace('/', '')}",
                "description": f"MACD crossover strategy for {symbol}",
                "strategy_type": StrategyType.MOMENTUM,
                "parameters": {
                    "strategy_type": "macd",
                    "short_window": 12,
                    "long_window": 26,
                    "symbol": symbol,
                }
            },
            {
                "name": f"ATI_Trend_{symbol.replace('/', '')}",
                "description": f"ATR trend indicator for {symbol}",
                "strategy_type": StrategyType.TREND_FOLLOWING,
                "parameters": {
                    "strategy_type": "ati_trend",
                    "atr_window": 14,
                    "atr_factor": 3.0,
                    "symbol": symbol,
                }
            },
        ]

        return strategy_templates

    def generate_adaptive_hypotheses(self, symbol: str, feedback: Dict) -> List[Dict[str, Any]]:
        """Generate new hypotheses based on performance feedback - ENHANCED"""
        hypotheses = []

        # Analyze what worked
        best_strategies = feedback.get('best_strategies', [])
        worst_strategies = feedback.get('worst_strategies', [])
        cross_symbol_insights = feedback.get('cross_symbol_insights', {})

        # === 1. PARAMETER MUTATION (Genetic Algorithm style) ===
        for best in best_strategies[:3]:
            base_params = best.get('parameters', {})
            strategy_type = base_params.get('strategy_type', 'ema_crossover')

            # Mutation 1: Fine-tune parameters
            if 'short_window' in base_params:
                # Small perturbations for local search
                for delta in [-2, -1, 1, 2]:
                    hyp = {
                        "name": f"{best['name']}_Mut_{delta:+d}",
                        "description": f"Mutated {best['name']} (delta={delta:+d})",
                        "strategy_type": best['strategy_type'],
                        "parameters": {
                            **base_params,
                            "short_window": max(5, base_params.get('short_window', 12) + delta),
                            "long_window": max(10, base_params.get('long_window', 26) + delta * 2),
                        }
                    }
                    hypotheses.append(hyp)

            # Mutation 2: RSI parameter space exploration
            if 'rsi_period' in base_params:
                for rsi_p in [base_params.get('rsi_period', 14) + d for d in [-2, -1, 1, 2, 3]]:
                    for os, ob in [(25, 75), (30, 70), (20, 80), (35, 65)]:
                        hyp = {
                            "name": f"{best['name']}_RSI{rsi_p}_{os}{ob}",
                            "description": f"RSI variant of {best['name']}",
                            "strategy_type": best['strategy_type'],
                            "parameters": {
                                **base_params,
                                "rsi_period": max(7, min(30, rsi_p)),
                                "rsi_oversold": os,
                                "rsi_overbought": ob,
                            }
                        }
                        hypotheses.append(hyp)

            # Mutation 3: Bollinger Bands parameter space
            if 'bb_period' in base_params:
                for bb_p in [base_params.get('bb_period', 20) + d for d in [-5, -3, 3, 5]]:
                    for std in [1.5, 2.0, 2.5, 3.0]:
                        hyp = {
                            "name": f"{best['name']}_BB{bb_p}_Std{std}",
                            "description": f"BB variant of {best['name']}",
                            "strategy_type": best['strategy_type'],
                            "parameters": {
                                **base_params,
                                "bb_period": max(10, min(50, bb_p)),
                                "bb_std": std,
                            }
                        }
                        hypotheses.append(hyp)

        # === 2. STRATEGY CROSSOVER (Combine best features) ===
        if len(best_strategies) >= 2:
            for i, s1 in enumerate(best_strategies[:2]):
                for s2 in best_strategies[i+1:3]:
                    # Hybrid: trend + mean reversion
                    if s1['strategy_type'] != s2['strategy_type']:
                        hyp = {
                            "name": f"Hybrid_{s1['name'].split('_')[0]}_{s2['name'].split('_')[0]}",
                            "description": f"Hybrid of {s1['name']} + {s2['name']}",
                            "strategy_type": StrategyType.CUSTOM,
                            "parameters": {
                                "strategy_type": "hybrid_trend_reversion",
                                "trend_short": s1['parameters'].get('short_window', 12),
                                "trend_long": s1['parameters'].get('long_window', 26),
                                "rsi_period": s2['parameters'].get('rsi_period', 14),
                                "rsi_oversold": s2['parameters'].get('rsi_oversold', 30),
                                "rsi_overbought": s2['parameters'].get('rsi_overbought', 70),
                                "symbol": symbol,
                            }
                        }
                        hypotheses.append(hyp)

        # === 3. BAYESIAN-INSPIRED PARAMETER SAMPLING ===
        # Sample from promising regions based on performance
        if best_strategies:
            for best in best_strategies[:2]:
                base = best.get('parameters', {})
                strategy = base.get('strategy_type', 'ema_crossover')

                # Focused sampling around best performers
                if strategy == 'ema_crossover':
                    for sw in [8, 9, 10, 12, 13, 15, 18]:
                        for lw in [21, 24, 26, 30, 34, 40]:
                            if lw > sw:
                                hyp = {
                                    "name": f"EMA_Opt_{sw}_{lw}_{symbol.replace('/', '')}",
                                    "description": f"Optimized EMA {sw}/{lw} for {symbol}",
                                    "strategy_type": StrategyType.TREND_FOLLOWING,
                                    "parameters": {
                                        "strategy_type": "ema_crossover",
                                        "short_window": sw,
                                        "long_window": lw,
                                        "symbol": symbol,
                                    }
                                }
                                hypotheses.append(hyp)

                elif strategy == 'rsi_reversion':
                    for rp in [7, 9, 12, 14, 16, 20, 25]:
                        for os in [15, 20, 25, 30]:
                            for ob in [65, 70, 75, 80, 85]:
                                if os < ob:
                                    hyp = {
                                        "name": f"RSI_Opt_{rp}_{os}{ob}_{symbol.replace('/', '')}",
                                        "description": f"Optimized RSI {rp} {os}/{ob} for {symbol}",
                                        "strategy_type": StrategyType.MEAN_REVERSION,
                                        "parameters": {
                                            "strategy_type": "rsi_reversion",
                                            "rsi_period": rp,
                                            "rsi_oversold": os,
                                            "rsi_overbought": ob,
                                            "symbol": symbol,
                                        }
                                    }
                                    hypotheses.append(hyp)

                elif strategy == 'bb_reversion':
                    for bp in [10, 12, 15, 18, 20, 22, 25, 30]:
                        for std in [1.5, 1.8, 2.0, 2.2, 2.5, 3.0]:
                            hyp = {
                                "name": f"BB_Opt_{bp}_{std}_{symbol.replace('/', '')}",
                                "description": f"Optimized BB {bp} std{std} for {symbol}",
                                "strategy_type": StrategyType.MEAN_REVERSION,
                                "parameters": {
                                    "strategy_type": "bb_reversion",
                                    "bb_period": bp,
                                    "bb_std": std,
                                    "symbol": symbol,
                                }
                            }
                            hypotheses.append(hyp)

        # === 4. CROSS-SYMBOL TRANSFER LEARNING ===
        # Apply best strategies from other symbols to this symbol
        for other_symbol, insights in cross_symbol_insights.items():
            if other_symbol != symbol:
                for best_from_other in insights.get('best_strategies', [])[:2]:
                    base_params = best_from_other.get('parameters', {})
                    # Adapt to this symbol
                    adapted = {**base_params, 'symbol': symbol}
                    hyp = {
                        "name": f"Transfer_{best_from_other['name']}_{symbol.replace('/', '')}",
                        "description": f"Transferred from {other_symbol}: {best_from_other['name']}",
                        "strategy_type": best_from_other['strategy_type'],
                        "parameters": adapted
                    }
                    hypotheses.append(hyp)

        # === 5. OPPOSITE STRATEGIES FOR WORST PERFORMERS ===
        for worst in worst_strategies[:2]:
            if worst['strategy_type'] == StrategyType.TREND_FOLLOWING:
                # Try multiple mean reversion variants
                for rsi_p in [14, 16]:
                    for os, ob in [(20, 80), (25, 75), (30, 70)]:
                        hyp = {
                            "name": f"Counter_{worst['name']}_RSI{rsi_p}_{os}{ob}",
                            "description": f"Counter-trend RSI {rsi_p} {os}/{ob} vs {worst['name']}",
                            "strategy_type": StrategyType.MEAN_REVERSION,
                            "parameters": {
                                "strategy_type": "rsi_reversion",
                                "rsi_period": rsi_p,
                                "rsi_oversold": os,
                                "rsi_overbought": ob,
                                "symbol": symbol,
                            }
                        }
                        hypotheses.append(hyp)
                # VWAP reversion
                hyp = {
                    "name": f"Counter_{worst['name']}_VWAP",
                    "description": f"VWAP reversion vs {worst['name']}",
                    "strategy_type": StrategyType.MEAN_REVERSION,
                    "parameters": {
                        "strategy_type": "vwap_reversion",
                        "vwap_window": 20,
                        "vwap_threshold": 0.02,
                        "symbol": symbol,
                    }
                }
                hypotheses.append(hyp)
            elif worst['strategy_type'] == StrategyType.MEAN_REVERSION:
                # Try multiple trend following variants
                for sw, lw in [(8, 21), (9, 21), (10, 26), (12, 26), (15, 30)]:
                    hyp = {
                        "name": f"Counter_{worst['name']}_EMA{sw}_{lw}",
                        "description": f"EMA {sw}/{lw} trend vs {worst['name']}",
                        "strategy_type": StrategyType.TREND_FOLLOWING,
                        "parameters": {
                            "strategy_type": "ema_crossover",
                            "short_window": sw,
                            "long_window": lw,
                            "symbol": symbol,
                        }
                    }
                    hypotheses.append(hyp)
                # Dual EMA trend
                hyp = {
                    "name": f"Counter_{worst['name']}_DualEMA",
                    "description": f"Dual EMA trend vs {worst['name']}",
                    "strategy_type": StrategyType.TREND_FOLLOWING,
                    "parameters": {
                        "strategy_type": "dual_ema",
                        "dual_fast": 8,
                        "dual_mid": 21,
                        "dual_slow": 55,
                        "symbol": symbol,
                    }
                }
                hypotheses.append(hyp)

        # === 6. EXPLORACION CON ROTACION POR CICLO ===
        # Sin feedback suficiente, explora familias/parametros que ROTAN con
        # self.iteration en vez de repetir el mismo set fijo cada ciclo.
        it = int(getattr(self, "iteration", 0) or 0)
        sym = symbol.replace("/", "")

        dw_all = [10, 15, 20, 25, 30]
        dw = dw_all[it % len(dw_all)]
        hypotheses.append({
            "name": f"Breakout_{dw}_{sym}_c{it}",
            "description": f"Donchian breakout {dw} (exploracion ciclo {it})",
            "strategy_type": StrategyType.BREAKOUT,
            "parameters": {"strategy_type": "donchian_breakout",
                           "donchian_window": dw, "symbol": symbol},
        })

        macd_pairs = [(8, 21), (9, 26), (12, 30), (10, 28)]
        fs, ls = macd_pairs[it % len(macd_pairs)]
        hypotheses.append({
            "name": f"MACD_{fs}_{ls}_{sym}_c{it}",
            "description": f"MACD {fs}/{ls} (exploracion ciclo {it})",
            "strategy_type": StrategyType.MOMENTUM,
            "parameters": {"strategy_type": "macd", "short_window": fs,
                           "long_window": ls, "signal_window": 9,
                           "symbol": symbol},
        })

        if it % 2 == 1:   # ciclos impares: rotar tambien mean-reversion
            rsi_p = [14, 10, 18][(it // 2) % 3]
            hypotheses.append({
                "name": f"RSIrev_{rsi_p}_{sym}_c{it}",
                "description": f"RSI reversion p={rsi_p} (ciclo {it})",
                "strategy_type": StrategyType.MEAN_REVERSION,
                "parameters": {"strategy_type": "rsi_reversion",
                               "rsi_period": rsi_p, "rsi_oversold": 30,
                               "rsi_overbought": 70, "symbol": symbol},
            })
            bb_p = [20, 16, 24][(it // 2) % 3]
            hypotheses.append({
                "name": f"BB_{bb_p}_{sym}_c{it}",
                "description": f"Bollinger reversion p={bb_p} (ciclo {it})",
                "strategy_type": StrategyType.MEAN_REVERSION,
                "parameters": {"strategy_type": "bb_reversion",
                               "bb_period": bb_p, "bb_std": 2.0,
                               "symbol": symbol},
            })

        # Deduplicate by name
        seen = set()
        unique = []
        for h in hypotheses:
            if h['name'] not in seen:
                seen.add(h['name'])
                unique.append(h)

        return unique[:self.hypotheses_per_symbol * 2]  # Return more candidates, runner will select top N

    def _recent_closes(self, symbol, limit=300):
        """Closes recientes REALES para los modelos; cache por ciclo."""
        cached = getattr(self, "_closes_cache", None)
        now = time.time()
        if cached and cached[0] == symbol and now - cached[1] < 300:
            return cached[2]
        from data_acquisition.data_sources.exchanges import ExchangeAPI
        ex = ExchangeAPI(exchange_id=self.exchange_id)
        ohlcv = ex.fetch_ohlcv(symbol, self.timeframe, limit=limit)
        closes = [c[4] for c in (ohlcv or []) if c and c[4] is not None]
        self._closes_cache = (symbol, now, closes)
        return closes

    def create_hypotheses_for_symbol(self, symbol: str, iteration: int) -> List[str]:
        """Create and register hypotheses for a symbol"""
        hypothesis_ids = []

        if iteration == 0:
            templates = self.generate_base_hypotheses(symbol)
        else:
            # Get feedback from previous iteration
            feedback = self.analyze_performance(symbol)
            templates = self.generate_adaptive_hypotheses(symbol, feedback)

        if self.hypothesis_ranker is not None:
            try:
                templates = self.hypothesis_ranker(templates, symbol)
            except Exception as exc:
                print(f"  [ml-prior] ranker error ({exc}); orden original")

        # Generacion basada en modelos cientificos (ARIMA/GARCH) como fuente
        # ADICIONAL de candidatos; su ausencia nunca rompe el flujo.
        try:
            from model_based_generator import (HAS_MODEL_BASED_GENERATOR,
                                               generate_model_hypotheses)
            if HAS_MODEL_BASED_GENERATOR:
                closes = self._recent_closes(symbol)
                sci = generate_model_hypotheses(symbol, closes,
                                                max_hypotheses=2)
                if sci:
                    templates = sci + templates
                    print(f"  [model-gen] +{len(sci)} hipotesis cientificas "
                          f"para {symbol}")
        except Exception as exc:
            print(f"  [model-gen] no disponible ({type(exc).__name__}: {exc})")

        # Select top N hypotheses
        for i, template in enumerate(templates[:self.hypotheses_per_symbol]):
            hyp_id = self.research_manager.generate_hypothesis(
                name=template["name"],
                description=template["description"],
                strategy_type=template["strategy_type"],
                author="AQDE_Runner",
                **{k: v for k, v in template["parameters"].items() if k != "strategy_type"}
            )
            hypothesis_ids.append(hyp_id)
            self.all_hypotheses[hyp_id] = self.research_manager.get_hypothesis(hyp_id)
            print(f"  Created hypothesis: {hyp_id} ({template['name']})")

        return hypothesis_ids

    def run_backtest_for_symbol(self, symbol: str, hypothesis_ids: List[str]) -> List[Dict]:
        """Run backtests for all hypotheses of a symbol"""
        results = []

        # Fetch market data once
        market_data = self.get_or_fetch_market_data(symbol)

        print(f"  Data fetched: {market_data['count']} candles")

        for hyp_id in hypothesis_ids:
            print(f"\n  Backtesting {hyp_id}...")
            try:
                # Prepare backtest kwargs
                hyp = self.research_manager.get_hypothesis(hyp_id)
                backtest_kwargs = {
                    "data": market_data,
                    "initial_capital": 10000.0
                }

                result = self.research_manager.run_backtest(hyp_id, **backtest_kwargs)

                # Calculate metrics
                n_trades = getattr(result, "num_trades", 0) or getattr(result, "total_trades", 0)
                win_rate = getattr(result, "win_rate", 0)
                total_return = getattr(result, "total_return", 0)
                sharpe = getattr(result, "sharpe_ratio", 0)
                sortino = getattr(result, "sortino_ratio", 0)
                max_dd = getattr(result, "max_drawdown", 0)
                total_return_pct = getattr(result, "total_return_pct", 0)

                result_data = {
                    "hypothesis_id": hyp_id,
                    "symbol": symbol,
                    "n_trades": n_trades,
                    "win_rate": win_rate,
                    # PnL absoluto en USD (final - initial), NO porcentaje
                    "total_return": total_return,
                    # Cambio real de capital en % ((final-initial)/initial*100)
                    "total_return_pct": total_return_pct,
                    "sharpe_ratio": sharpe,
                    "sortino_ratio": sortino,
                    "max_drawdown": max_dd,
                    "status": "success" if n_trades > 0 else "no_trades"
                }
                results.append(result_data)

                print(f"    Trades: {n_trades}, Win Rate: {win_rate:.2f}%, Return: {total_return_pct:.2f}% (${total_return:,.2f}), Sharpe: {sharpe:.2f}")

            except Exception as e:
                print(f"    Error: {e}")
                results.append({
                    "hypothesis_id": hyp_id,
                    "symbol": symbol,
                    "status": "error",
                    "error": str(e)}
                )

        return results

    def run_walk_forward_validation(self, symbol: str, hypothesis_ids: List[str], min_robustness: float = 50.0) -> Dict:
        """Run walk-forward validation on top hypotheses"""
        if not HAS_QUANT_MATH:
            return {}
        
        print(f"\n  Running Walk-Forward Validation for {symbol}...")
        wfv_results = {}
        
        # Datos con cache intra-ciclo (misma descarga que el backtest)
        market_data = self.get_or_fetch_market_data(symbol)
        
        # Convert market data to format expected by WalkForwardValidator
        # market_data contains 'data' key with DataFrame
        price_data = {symbol: market_data['data']['close'].values}
        
        # Create backtester
        backtester = Backtester(initial_capital=10000.0)
        
        # Create walk-forward validator
        wfv = WalkForwardValidator(
            backtester=backtester,
            train_window=252,  # ~1 year for daily
            test_window=63,    # ~3 months for daily
            step_size=63,
            anchored=True
        )
        
        for hyp_id in hypothesis_ids[:5]:  # Top 5 per symbol
            hyp = self.research_manager.get_hypothesis(hyp_id)
            if not hyp:
                continue
                
            print(f"    WFV: {hyp.name}...")
            
            try:
                # Create strategy function from hypothesis
                strategy_func = self._create_strategy_from_hypothesis(hyp)
                
                # Define parameter grid based on strategy type
                param_grid = self._get_param_grid_for_hypothesis(hyp)
                
                # Run walk-forward validation
                wfv_result = wfv.validate(
                    strategy_func=strategy_func,
                    data=price_data,
                    param_grid=param_grid,
                    initial_capital=10000.0
                )
                
                wfv_results[hyp_id] = {
                    "hypothesis_id": hyp_id,
                    "symbol": symbol,
                    "robustness_score": wfv_result.robustness_score,
                    "parameter_stability": wfv_result.parameter_stability,
                    "is_stats": wfv_result.is_stats,
                    "oos_stats": wfv_result.oos_stats,
                    "windows": wfv_result.windows,
                    "passed": wfv_result.robustness_score >= min_robustness
                }
                
                print(f"      Robustness: {wfv_result.robustness_score:.1f}/100, "
                      f"Param Stability: {wfv_result.parameter_stability:.1f}/100, "
                      f"Passed: {wfv_result.robustness_score >= min_robustness}")
                
            except Exception as e:
                print(f"      WFV Error: {e}")
                wfv_results[hyp_id] = {
                    "hypothesis_id": hyp_id,
                    "symbol": symbol,
                    "error": str(e),
                    "passed": False
                }
        
        return wfv_results

    def _create_strategy_from_hypothesis(self, hyp):
        """Create a strategy function from a hypothesis"""
        params = hyp.parameters
        strategy_type = params.get('strategy_type', 'ema_crossover')
        
        def strategy(data, **kwargs):
            # Merge hypothesis params with any overrides
            all_params = {**params, **kwargs}
            
            # Get price data
            symbol = list(data.keys())[0]
            prices = data[symbol]
            
            # Generate signals based on strategy type
            orders = []
            if strategy_type == 'ema_crossover':
                short = all_params.get('short_window', 12)
                long = all_params.get('long_window', 26)
                # Simple EMA crossover logic
                ema_short = np.convolve(prices, np.ones(short)/short, mode='valid')
                ema_long = np.convolve(prices, np.ones(long)/long, mode='valid')
                min_len = min(len(ema_short), len(ema_long))
                for i in range(min_len):
                    if i == 0:
                        orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
                    elif ema_short[i] > ema_long[i] and ema_short[i-1] <= ema_long[i-1]:
                        orders.append({'symbol': symbol, 'side': 'buy', 'quantity': 1})
                    elif ema_short[i] < ema_long[i] and ema_short[i-1] >= ema_long[i-1]:
                        orders.append({'symbol': symbol, 'side': 'sell', 'quantity': 1})
                    else:
                        orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
                        
            elif strategy_type == 'rsi_reversion':
                rsi_period = all_params.get('rsi_period', 14)
                oversold = all_params.get('rsi_oversold', 30)
                overbought = all_params.get('rsi_overbought', 70)
                # Simple RSI logic
                orders = []
                for i in range(len(prices)):
                    if i < rsi_period:
                        orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
                    else:
                        gains = np.diff(prices[i-rsi_period:i+1])
                        gains = gains[gains > 0]
                        losses = -np.diff(prices[i-rsi_period:i+1])
                        losses = losses[losses > 0]
                        avg_gain = np.mean(gains) if len(gains) > 0 else 0
                        avg_loss = np.mean(losses) if len(losses) > 0 else 1
                        rs = avg_gain / avg_loss if avg_loss > 0 else 100
                        rsi = 100 - (100 / (1 + rs))
                        if rsi < oversold:
                            orders.append({'symbol': symbol, 'side': 'buy', 'quantity': 1})
                        elif rsi > overbought:
                            orders.append({'symbol': symbol, 'side': 'sell', 'quantity': 1})
                        else:
                            orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
                            
            elif strategy_type == 'bb_reversion':
                bb_period = all_params.get('bb_period', 20)
                bb_std = all_params.get('bb_std', 2.0)
                orders = []
                for i in range(len(prices)):
                    if i < bb_period:
                        orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
                    else:
                        window = prices[i-bb_period:i]
                        mean = np.mean(window)
                        std = np.std(window)
                        upper = mean + bb_std * std
                        lower = mean - bb_std * std
                        if prices[i] < lower:
                            orders.append({'symbol': symbol, 'side': 'buy', 'quantity': 1})
                        elif prices[i] > upper:
                            orders.append({'symbol': symbol, 'side': 'sell', 'quantity': 1})
                        else:
                            orders.append({'symbol': symbol, 'side': 'hold', 'quantity': 0})
            else:
                # Default: hold
                orders = [{'symbol': symbol, 'side': 'hold', 'quantity': 0} for _ in prices]
            
            return orders
        
        return strategy

    def _get_param_grid_for_hypothesis(self, hyp):
        """Get parameter grid for walk-forward optimization"""
        params = hyp.parameters
        strategy_type = params.get('strategy_type', 'ema_crossover')
        
        if strategy_type == 'ema_crossover':
            return {
                'short_window': [8, 10, 12, 15, 18, 20],
                'long_window': [21, 26, 30, 35, 40, 50]
            }
        elif strategy_type == 'rsi_reversion':
            return {
                'rsi_period': [7, 10, 14, 16, 20, 25],
                'rsi_oversold': [15, 20, 25, 30],
                'rsi_overbought': [65, 70, 75, 80]
            }
        elif strategy_type == 'bb_reversion':
            return {
                'bb_period': [10, 15, 20, 25, 30],
                'bb_std': [1.5, 1.8, 2.0, 2.5, 3.0]
            }
        elif strategy_type == 'donchian_breakout':
            return {
                'donchian_window': [10, 15, 20, 25, 30, 40]
            }
        elif strategy_type == 'dual_ema':
            return {
                'dual_fast': [5, 8, 10, 12],
                'dual_mid': [13, 21, 26, 30],
                'dual_slow': [34, 50, 55, 60]
            }
        elif strategy_type == 'vwap_reversion':
            return {
                'vwap_window': [10, 15, 20, 25, 30],
                'vwap_threshold': [0.01, 0.02, 0.03, 0.05]
            }
        elif strategy_type == 'macd':
            return {
                'short_window': [8, 12, 15],
                'long_window': [21, 26, 30],
                'signal_window': [7, 9, 12]
            }
        elif strategy_type == 'ati_trend':
            return {
                'atr_window': [10, 14, 20],
                'atr_factor': [2.0, 2.5, 3.0, 3.5]
            }
        else:
            return {}

    def run_monte_carlo_for_results(self, hypothesis_ids: List[str]):
        """Run Monte Carlo simulations for hypotheses"""
        print(f"\n  Running Monte Carlo simulations...")
        for hyp_id in hypothesis_ids:
            if hyp_id in self.research_manager.results:
                try:
                    mc_result = self.research_manager.run_monte_carlo(hyp_id, n_iterations=500)
                    print(f"    {hyp_id}: Mean={mc_result.mean:.2%}, 95% CI=[{mc_result.lower_bound:.2%}, {mc_result.upper_bound:.2%}]")
                except Exception as e:
                    print(f"    {hyp_id}: Error - {e}")

    def score_hypotheses(self, hypothesis_ids: List[str]):
        """Score all hypotheses"""
        print(f"\n  Scoring hypotheses...")
        for hyp_id in hypothesis_ids:
            try:
                score = self.research_manager.score_hypothesis(hyp_id)
                print(f"    {hyp_id}: Scientific Score = {score['scientific_score']:.2%}")
            except Exception as e:
                print(f"    {hyp_id}: Error - {e}")

    def analyze_performance(self, symbol: str) -> Dict:
        """Analyze performance of hypotheses for a symbol"""
        # Get all hypotheses for this symbol
        all_results = [r for r in self.performance_history if r.get('symbol') == symbol]
        if not all_results:
            return {"best_strategies": [], "worst_strategies": [], "cross_symbol_insights": {}}

        # Filter successful ones
        successful = [r for r in all_results if r.get('status') == 'success' and r.get('n_trades', 0) > 0]

        if not successful:
            return {"best_strategies": [], "worst_strategies": [], "cross_symbol_insights": {}}

        # Sort by scientific score (combination of return, sharpe, win rate)
        for r in successful:
            hyp = self.all_hypotheses.get(r['hypothesis_id'])
            if hyp and hasattr(hyp, 'scientific_score') and hyp.scientific_score:
                r['scientific_score'] = hyp.scientific_score
            else:
                # Compute proxy score
                wr = r.get('win_rate', 0) / 100 if r.get('win_rate', 0) > 1 else r.get('win_rate', 0)
                ret = r.get('total_return', 0)
                sh = r.get('sharpe_ratio', 0)
                r['scientific_score'] = max(0, min(1, 0.3*wr + 0.4*max(0, ret/2) + 0.3*max(0, sh/3)))

        successful.sort(key=lambda x: x.get('scientific_score', 0), reverse=True)

        best = successful[:3]
        worst = successful[-2:] if len(successful) >= 2 else []

        # Cross-symbol insights: best from other symbols
        cross_insights = {}
        for sym_obj in self.symbols:
            other = sym_obj.symbol
            if other != symbol:
                other_results = [r for r in self.performance_history if r.get('symbol') == other]
                other_successful = [r for r in other_results if r.get('status') == 'success' and r.get('n_trades', 0) > 0]
                if other_successful:
                    for r in other_successful:
                        hyp = self.all_hypotheses.get(r['hypothesis_id'])
                        if hyp and hasattr(hyp, 'scientific_score') and hyp.scientific_score:
                            r['scientific_score'] = hyp.scientific_score
                        else:
                            wr = r.get('win_rate', 0) / 100 if r.get('win_rate', 0) > 1 else r.get('win_rate', 0)
                            ret = r.get('total_return', 0)
                            sh = r.get('sharpe_ratio', 0)
                            r['scientific_score'] = max(0, min(1, 0.3*wr + 0.4*max(0, ret/2) + 0.3*max(0, sh/3)))
                    other_successful.sort(key=lambda x: x.get('scientific_score', 0), reverse=True)
                    cross_insights[other] = {
                        "best_strategies": [
                            {
                                "name": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'name': r['hypothesis_id']})).name,
                                "hypothesis_id": r['hypothesis_id'],
                                "strategy_type": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'strategy_type': StrategyType.CUSTOM})).strategy_type,
                                "parameters": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'parameters': {}})).parameters,
                                "score": r.get('scientific_score', 0)
                            }
                            for r in other_successful[:2]
                        ]
                    }

        return {
            "best_strategies": [
                {
                    "name": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'name': r['hypothesis_id']})).name,
                    "hypothesis_id": r['hypothesis_id'],
                    "strategy_type": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'strategy_type': StrategyType.CUSTOM})).strategy_type,
                    "parameters": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'parameters': {}})).parameters,
                    "score": r.get('scientific_score', 0)
                }
                for r in best
            ],
            "worst_strategies": [
                {
                    "name": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'name': r['hypothesis_id']})).name,
                    "hypothesis_id": r['hypothesis_id'],
                    "strategy_type": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'strategy_type': StrategyType.CUSTOM})).strategy_type,
                    "parameters": self.all_hypotheses.get(r['hypothesis_id'], type('obj', (), {'parameters': {}})).parameters,
                    "score": r.get('scientific_score', 0)
                }
                for r in worst
            ],
            "cross_symbol_insights": cross_insights
        }

    def save_iteration_results(self, iteration: int, results: Dict):
        """Save iteration results to file"""
        output = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "symbols": [asdict(s) for s in self.symbols],
            "results": results,
            "total_hypotheses": len(self.all_hypotheses)
        }

        filename = f"aqde_iteration_{iteration}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\n  Results saved to {filename}")
        return filename

    def run(self):
        """Main execution loop"""
        print(f"\n{'#'*60}")
        print(f"# AQDE RUNNER - Autonomous Quant Discovery Engine")
        print(f"# Exchange: {self.exchange_id}")
        print(f"# Symbols: {self.top_n_symbols}")
        print(f"# Hypotheses per symbol: {self.hypotheses_per_symbol}")
        print(f"# Feedback iterations: {self.feedback_iterations}")
        print(f"# Dry run: {self.dry_run}")
        print(f"{'#'*60}")

        # Step 1: Fetch top symbols
        self.fetch_top_symbols()

        if not self.symbols:
            print("No symbols found! Exiting.")
            return

        # Step 2: Run iterations with feedback loop
        all_iteration_results = {}

        for iteration in range(self.feedback_iterations + 1):
            self.iteration = iteration
            print(f"\n{'='*60}")
            print(f"ITERATION {iteration}/{self.feedback_iterations}")
            print(f"{'='*60}")

            iteration_results = {}

            for symbol_obj in self.symbols:
                symbol = symbol_obj.symbol
                print(f"\nProcessing {symbol}...")

                # Create hypotheses
                hypothesis_ids = self.create_hypotheses_for_symbol(symbol, iteration)

                # Run backtests
                backtest_results = self.run_backtest_for_symbol(symbol, hypothesis_ids)

                # Run Walk-Forward Validation on top hypotheses
                if HAS_QUANT_MATH and iteration > 0:
                    # Sort by performance and run WFV on top 5
                    successful = [r for r in backtest_results if r.get('status') == 'success' and r.get('n_trades', 0) > 0]
                    successful.sort(key=lambda x: x.get('sharpe_ratio', 0) + x.get('total_return', 0)/10, reverse=True)
                    top_hyp_ids = [r['hypothesis_id'] for r in successful[:5]]
                    wfv_results = self.run_walk_forward_validation(symbol, top_hyp_ids)
                    iteration_results[f"{symbol}_wfv"] = wfv_results

                # Run Monte Carlo
                if HAS_QUANT_MATH:
                    self.run_monte_carlo_for_results(hypothesis_ids)

                # Score hypotheses
                self.score_hypotheses(hypothesis_ids)

                # Store results
                iteration_results[symbol] = backtest_results
                self.performance_history.extend(backtest_results)

            all_iteration_results[f"iteration_{iteration}"] = iteration_results

            # Save iteration results
            self.save_iteration_results(iteration, iteration_results)

            # Analyze and prepare feedback for next iteration
            if iteration < self.feedback_iterations:
                print(f"\n{'='*60}")
                print(f"FEEDBACK ANALYSIS FOR ITERATION {iteration}")
                print(f"{'='*60}")

                for symbol_obj in self.symbols:
                    symbol = symbol_obj.symbol
                    feedback = self.analyze_performance(symbol)
                    print(f"\n{symbol} Feedback:")
                    print(f"  Best strategies: {len(feedback['best_strategies'])}")
                    for b in feedback['best_strategies']:
                        print(f"    - {b['name']} (score: {b['score']:.2%})")
                    print(f"  Worst strategies: {len(feedback['worst_strategies'])}")
                    for w in feedback['worst_strategies']:
                        print(f"    - {w['name']} (score: {w['score']:.2%})")

        # Final summary
        self.print_final_summary(all_iteration_results)

        return all_iteration_results

    def print_final_summary(self, all_results: Dict):
        """Print final summary of all iterations"""
        print(f"\n{'#'*60}")
        print(f"# FINAL SUMMARY")
        print(f"{'#'*60}")

        total_hypotheses = len(self.all_hypotheses)
        total_backtested = sum(
            len([r for r in results.values() if isinstance(r, list)])
            for results in all_results.values()
        )

        print(f"\nTotal Hypotheses Created: {total_hypotheses}")
        print(f"Total Backtests Run: {total_backtested}")
        print(f"Iterations Completed: {self.feedback_iterations + 1}")

        # Best overall hypotheses
        all_successful = [
            r for results in all_results.values()
            for symbol_results in results.values()
            for r in symbol_results
            if isinstance(r, dict) and r.get('status') == 'success' and r.get('n_trades', 0) > 0
        ]

        if all_successful:
            # Score them
            for r in all_successful:
                hyp = self.all_hypotheses.get(r['hypothesis_id'])
                if hyp and hasattr(hyp, 'scientific_score') and hyp.scientific_score:
                    r['final_score'] = hyp.scientific_score
                else:
                    wr = r.get('win_rate', 0) / 100 if r.get('win_rate', 0) > 1 else r.get('win_rate', 0)
                    ret = r.get('total_return', 0)
                    sh = r.get('sharpe_ratio', 0)
                    r['final_score'] = max(0, min(1, 0.3*wr + 0.4*max(0, ret/2) + 0.3*max(0, sh/3)))

            all_successful.sort(key=lambda x: x.get('final_score', 0), reverse=True)

            print(f"\nTop 10 Hypotheses Overall:")
            for i, r in enumerate(all_successful[:10], 1):
                hyp = self.all_hypotheses.get(r['hypothesis_id'])
                name = hyp.name if hyp else r['hypothesis_id']
                print(f"  {i}. {name} ({r['symbol']})")
                print(f"      Score: {r.get('final_score', 0):.2%}, Trades: {r['n_trades']}, "
                      f"Win%: {r['win_rate']:.1f}%, Return: {r.get('total_return_pct', 0):.2f}%, Sharpe: {r['sharpe_ratio']:.2f}")

        # Save final comprehensive results
        final_output = {
            "summary": {
                "total_hypotheses": total_hypotheses,
                "total_backtested": total_backtested,
                "iterations": self.feedback_iterations + 1,
                "symbols": [asdict(s) for s in self.symbols],
                "timestamp": datetime.now().isoformat()
            },
            "all_results": all_results,
            "top_hypotheses": all_successful[:20] if all_successful else []
        }

        filename = f"aqde_final_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(final_output, f, indent=2, default=str)

        print(f"\nFinal results saved to {filename}")

        # Export knowledge base
        export_file = f"hypotheses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.adapter.export_hypotheses(export_file)
        print(f"Knowledge base exported to {export_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AQDE Runner with Bybit Integration")
    parser.add_argument("--exchange", default="bybit", help="Exchange ID (default: bybit)")
    parser.add_argument("--symbols", type=int, default=20, help="Number of top volume symbols (default: 20)")
    parser.add_argument("--hypotheses", type=int, default=15, help="Hypotheses per symbol (default: 15)")
    parser.add_argument("--iterations", type=int, default=10, help="Feedback iterations (default: 10)")
    parser.add_argument("--lookback", type=int, default=365, help="Lookback days for data (default: 365)")
    parser.add_argument("--timeframe", default="1h", help="Timeframe (default: 1h)")
    parser.add_argument("--min-volume", type=float, default=1_000_000, help="Minimum volume USD (default: 1M)")
    parser.add_argument("--dry-run", action="store_true", help="Use synthetic data for testing")
    parser.add_argument("--kb-path", default="autonomous_research/data/hypotheses", help="Knowledge base path")

    args = parser.parse_args()

    runner = AQDERunner(
        exchange_id=args.exchange,
        knowledge_base_path=args.kb_path,
        top_n_symbols=args.symbols,
        min_volume_usd=args.min_volume,
        timeframe=args.timeframe,
        lookback_days=args.lookback,
        hypotheses_per_symbol=args.hypotheses,
        feedback_iterations=args.iterations,
        dry_run=args.dry_run
    )

    runner.run()


if __name__ == "__main__":
    main()