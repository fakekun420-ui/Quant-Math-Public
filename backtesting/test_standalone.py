#!/usr/bin/env python3
"""
Standalone test for backtesting module
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from backtesting import Backtester, PerformanceMetrics, BacktestResult, Trade


def test_metrics():
    print("Testing Performance Metrics...")
    np.random.seed(42)

    # Generate synthetic returns
    n = 252
    returns = np.random.normal(0.001, 0.02, n)

    # Sharpe ratio
    sharpe = PerformanceMetrics.sharpe_ratio(returns, risk_free_rate=0.02)
    print(f"  Sharpe ratio: {sharpe:.4f}")

    # Sortino ratio
    sortino = PerformanceMetrics.sortino_ratio(returns, risk_free_rate=0.02)
    print(f"  Sortino ratio: {sortino:.4f}")

    # Max drawdown
    prices = 100 * np.cumprod(1 + returns)
    max_dd = PerformanceMetrics.max_drawdown(prices)
    print(f"  Max drawdown: {max_dd:.2f}%")

    # Win rate
    trades = [
        Trade(trade_id="T1", symbol="AAPL", side="buy", quantity=100,
              entry_price=150, exit_price=155, pnl=500, pnl_pct=3.33,
              hold_duration=10, entry_time=0, exit_time=10, commission=15),
        Trade(trade_id="T2", symbol="MSFT", side="buy", quantity=50,
              entry_price=300, exit_price=295, pnl=-250, pnl_pct=-1.67,
              hold_duration=15, entry_time=11, exit_time=26, commission=10),
        Trade(trade_id="T3", symbol="GOOGL", side="buy", quantity=75,
              entry_price=1500, exit_price=1550, pnl=375, pnl_pct=3.33,
              hold_duration=5, entry_time=27, exit_time=32, commission=20)
    ]
    win_rate = PerformanceMetrics.win_rate(trades)
    print(f"  Win rate: {win_rate:.1f}%")

    # Profit factor
    profit_factor = PerformanceMetrics.profit_factor(trades)
    print(f"  Profit factor: {profit_factor:.2f}")


def test_backtester():
    print("\n\nTesting Backtester...")
    np.random.seed(42)

    # Generate synthetic price data
    n = 100
    n_assets = 3
    prices = {f"ASSET_{i}": 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n))) for i in range(n_assets)}

    # Define simple strategy
    def simple_strategy(data):
        """Buy on day 0, sell on day 10 for each asset."""
        orders = []
        for symbol in data:
            if np.random.random() > 0.5:
                orders.append({
                    'symbol': symbol,
                    'side': 'buy',
                    'quantity': 10
                })
        return orders

    # Run backtest
    backtester = Backtester(initial_capital=100000.0)
    result = backtester.run_backtest(simple_strategy, prices)

    # Print summary
    backtester.print_summary(result)

    print(f"  Equity curve length: {len(result.equity_curve)}")
    print(f"  Number of trades: {result.num_trades}")


def test_cumulative_returns():
    print("\n\nTesting Cumulative Returns...")
    np.random.seed(42)

    prices = [100, 102, 101, 105, 110, 108, 115, 120, 118, 125]

    cumulative = PerformanceMetrics.cumulative_returns(prices)
    print(f"  Initial price: ${prices[0]:.2f}")
    print(f"  Final price: ${prices[-1]:.2f}")
    print(f"  Cumulative return: {cumulative[-1] - 1:.2%}")
    print(f"  Number of points: {len(cumulative)}")


def test_equity_curve():
    print("\n\nTesting Equity Curve...")
    np.random.seed(42)

    initial_capital = 100000.0
    returns = np.random.normal(0.001, 0.02, 252)
    prices = 100 * np.cumprod(1 + returns)

    # Calculate equity curve
    equity = initial_capital
    equity_curve = [equity]

    for r in returns:
        equity *= (1 + r)
        equity_curve.append(equity)

    print(f"  Initial capital: ${initial_capital:,.2f}")
    print(f"  Final value: ${equity_curve[-1]:,.2f}")
    print(f"  Total return: {equity_curve[-1] / initial_capital - 1:.2%}")
    print(f"  Max drawdown: {PerformanceMetrics.max_drawdown(prices):.2f}%")
    print(f"  Sharpe ratio: {PerformanceMetrics.sharpe_ratio(returns):.4f}")


def test_multiple_strategies():
    print("\n\nTesting Multiple Strategies...")
    np.random.seed(42)

    n = 100
    prices = {f"ASSET_{i}": 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n))) for i in range(3)}

    backtester = Backtester(initial_capital=50000.0)

    # Strategy 1: Long only
    def strategy1(data):
        orders = [{'symbol': 'ASSET_0', 'side': 'buy', 'quantity': 10}]
        return orders

    # Strategy 2: Long and short
    def strategy2(data):
        orders = [
            {'symbol': 'ASSET_0', 'side': 'buy', 'quantity': 10},
            {'symbol': 'ASSET_1', 'side': 'sell', 'quantity': 5}
        ]
        return orders

    # Run both strategies
    result1 = backtester.run_backtest(strategy1, prices)
    result2 = backtester.run_backtest(strategy2, prices)

    print(f"\nStrategy 1 (Long Only):")
    print(f"  Final capital: ${result1.final_capital:,.2f}")
    print(f"  Total return: {result1.total_return_pct:.2f}%")
    print(f"  Trades: {result1.num_trades}")

    print(f"\nStrategy 2 (Long/Short):")
    print(f"  Final capital: ${result2.final_capital:,.2f}")
    print(f"  Total return: {result2.total_return_pct:.2f}%")
    print(f"  Trades: {result2.num_trades}")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH MODULE 14: Backtesting & Evaluation (Standalone Test)")
    print("="*70)

    test_metrics()
    test_cumulative_returns()
    test_equity_curve()
    test_backtester()
    test_multiple_strategies()

    print("\n" + "="*70)
    print("Standalone test completed!")
    print("="*70 + "\n")
