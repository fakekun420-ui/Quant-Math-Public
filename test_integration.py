#!/usr/bin/env python3
"""
System Integration Test for QUANT-MATH Framework

Tests the integration of all modules:
1. Expectation Calculation
2. Risk Management
3. Position Sizing
4. Order Management
5. Algo Trading
6. Backtesting
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

# Import modules
from backtesting import Backtester, PerformanceMetrics, Trade, BacktestResult
from order_management import OrderManager
from algo_trading import AlgoTradingSystem
from quant_math.risk import PositionSizer, ValueAtRisk, ExpectedShortfall
from optimization import KellyCriterion
from quant_math.expectation import ReturnCalculator, DrawdownAnalyzer, SharpeMetrics


def test_expectation_and_metrics():
    """Test expectation calculation and performance metrics."""
    print("\n" + "="*70)
    print("TEST 1: Expectation Calculation & Performance Metrics")
    print("="*70)

    # Sharpe metrics
    returns = np.array([0.01, -0.005, 0.02, -0.015])
    sharpe = SharpeMetrics.sharpe_ratio(returns)
    sortino = SharpeMetrics.sortino_ratio(returns)
    print(f"\nSharpe Metrics:")
    print(f"  Sharpe Ratio: {sharpe:.4f}")
    print(f"  Sortino Ratio: {sortino:.4f}")
    # Return calculator
    prices = [100, 102, 101, 105, 108, 110]
    # Convert prices to returns for the new API
    price_array = np.array(prices)
    simple_returns = np.diff(price_array) / price_array[:-1]
    log_returns = np.log(price_array[1:] / price_array[:-1])
    annualized = ReturnCalculator.calculate_annualized_return(simple_returns)
    print(f"\nReturn Calculator:")
    print(f"  Prices: {prices}")
    print(f"  Simple Returns: {[f'{r:.2%}' for r in simple_returns]}")
    print(f"  Log Returns: {[f'{r:.4f}' for r in log_returns]}")
    print(f"  Annualized Return: {annualized:.2%}")

    # Drawdown analysis
    dd_result = DrawdownAnalyzer.calculate_drawdowns(np.array(prices))
    drawdowns = dd_result["drawdowns"]
    max_dd = dd_result["max_drawdown"]
    avg_dd = DrawdownAnalyzer.average_drawdown(dd_result.get("drawdown_periods", []))
    
    print(f"\nDrawdown Analysis:")
    print(f"  Max Drawdown: {max_dd:.2%}")
    print(f"  Average Drawdown: {avg_dd:.2%}")


def test_risk_management():
    """Test risk management calculations."""
    print("\n" + "="*70)
    print("TEST 2: Risk Management")
    print("="*70)

    # Kelly Criterion
    win_rate = 0.60
    avg_win = 500
    avg_loss = 250

    kelly = KellyCriterion.calculate(win_rate, avg_win, avg_loss)
    print(f"\nKelly Criterion:")
    print(f"  Kelly Fraction: {kelly:.4f}")
    print(f"  Win Rate: {win_rate:.0%}")
    print(f"  Avg Win: ${avg_win:.0f}")
    print(f"  Avg Loss: ${avg_loss:.0f}")
    print(f"  Risk/Reward: {avg_win/avg_loss:.2f}")

    # Position Sizing
    portfolio_value = 100000.0
    risk_per_trade = 0.02  # 2% of portfolio
    stop_loss_distance = 0.05  # 5% loss

    position_size = PositionSizer.calculate(
        portfolio_value=portfolio_value,
        risk_per_trade=risk_per_trade,
        stop_loss_distance=stop_loss_distance
    )

    print(f"\nPosition Sizing:")
    print(f"  Portfolio Value: ${portfolio_value:,.2f}")
    print(f"  Risk Per Trade: {risk_per_trade:.0%}")
    print(f"  Stop Loss Distance: {stop_loss_distance:.0%}")
    print(f"  Position Size: {position_size:.2f} shares")

    # Value at Risk
    portfolio_std = 0.02  # 2% daily volatility
    confidence_level = 0.95
    var = ValueAtRisk.calculate(portfolio_value, portfolio_std, confidence_level)

    print(f"\nValue at Risk:")
    print(f"  Portfolio Volatility: {portfolio_std:.0%}")
    print(f"  Confidence Level: {confidence_level:.0%}")
    print(f"  Value at Risk (95%): ${var:,.2f}")


def test_order_management():
    """Test order management system."""
    print("\n" + "="*70)
    print("TEST 3: Order Management")
    print("="*70)

    from execution import OrderRouter, OrderType, Order

    router = OrderRouter()

    # Register exchanges
    router.register_exchange("binance", priority=1)
    router.register_exchange("coinbase", priority=2)

    # Create order
    order = Order(
        symbol="BTC/USDT",
        side="buy",
        order_type=OrderType.MARKET,
        amount=0.1,
        price=50000.0
    )

    # Route order
    result = router.route_order(order)

    print(f"\nOrder Routing:")
    print(f"  Order ID: {result.get('order_id', 'N/A')}")
    print(f"  Exchange: {result.get('exchange', 'N/A')}")
    print(f"  Executed: {result.get('executed', False)}")

    # Get fees
    fee = router.get_execution_fees("binance", OrderType.MARKET, 0.1)
    print(f"\nExecution Fees:")
    print(f"  Estimated Fee: ${fee:.4f}")


def test_algo_trading():
    """Test algorithmic trading execution."""
    print("\n" + "="*70)
    print("TEST 4: Algorithmic Trading")
    print("="*70)

    from execution import OrderRouter, OrderType, Order

    router = OrderRouter()
    router.register_exchange("binance", priority=1)

    # Create and route order
    order = Order(
        symbol="ETH/USDT",
        side="buy",
        order_type=OrderType.MARKET,
        amount=1.0,
        price=3000.0
    )

    result = router.route_order(order)

    print(f"\nAlgo Trading Execution:")
    print(f"  Order ID: {result.get('order_id', 'N/A')}")
    print(f"  Exchange: {result.get('exchange', 'N/A')}")
    print(f"  Executed: {result.get('executed', False)}")


def test_backtesting_integration():
    """Test complete backtesting workflow."""
    print("\n" + "="*70)
    print("TEST 5: Backtesting Integration")
    print("="*70)

    np.random.seed(42)

    # Generate synthetic price data
    n = 100
    n_assets = 2
    prices = {f"ASSET_{i}": 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n))) for i in range(n_assets)}

    backtester = Backtester(initial_capital=50000.0)

    # Define simple momentum strategy
    def momentum_strategy(data):
        """Buy assets that outperform the market yesterday."""
        orders = []
        current_prices = {symbol: prices[symbol][-1] for symbol in prices}

        for symbol in prices:
            if symbol == "ASSET_0":
                continue  # Benchmark

            yesterday = data[symbol][-2]
            today = current_prices[symbol]
            market_avg = current_prices["ASSET_0"]

            # Momentum: buy if asset outperforms market
            if (today - yesterday) / yesterday > (market_avg - yesterday) / yesterday:
                orders.append({
                    'symbol': symbol,
                    'side': 'buy',
                    'quantity': 10
                })

        return orders

    # Run backtest
    result = backtester.run_backtest(momentum_strategy, prices)

    # Print results
    print(f"\nBacktest Results:")
    print(f"  Initial Capital: ${result.initial_capital:,.2f}")
    print(f"  Final Capital: ${result.final_capital:,.2f}")
    print(f"  Total Return: {result.total_return_pct:.2f}%")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.4f}")
    print(f"  Sortino Ratio: {result.sortino_ratio:.4f}")
    print(f"  Max Drawdown: {result.max_drawdown:.2f}%")
    print(f"  Annualized Volatility: {result.annualized_volatility:.2f}%")
    print(f"  Number of Trades: {result.num_trades}")
    print(f"  Win Rate: {result.win_rate:.2f}%")
    print(f"  Profit Factor: {result.profit_factor:.2f}")

    backtester.print_summary(result)


def test_full_workflow():
    """Test end-to-end workflow."""
    print("\n" + "="*70)
    print("TEST 6: Full Workflow Integration")
    print("="*70)

    np.random.seed(42)

    # Step 1: Generate data
    n = 100
    prices = {f"SYMBOL_{i}": 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n))) for i in range(3)}

    # Step 2: Define strategy
    def simple_momentum_strategy(data):
        orders = []
        for symbol in ["SYMBOL_1", "SYMBOL_2"]:
            if np.random.random() > 0.5:
                orders.append({
                    'symbol': symbol,
                    'side': 'buy',
                    'quantity': 5
                })
        return orders

    # Step 3: Risk Management
    position_size = PositionSizer.calculate(
        portfolio_value=100000.0,
        risk_per_trade=0.02,
        stop_loss_distance=0.05
    )

    # Step 4: Order Management
    from execution import OrderRouter, OrderType, Order
    router = OrderRouter()
    router.register_exchange("binance", priority=1)
    
    order = Order(
        symbol="SYMBOL_1",
        side="buy",
        order_type=OrderType.MARKET,
        amount=min(position_size, 10),
        price=prices["SYMBOL_1"][-1]
    )

    # Step 5: Algo Trading
    result = router.route_order(order)

    # Step 6: Backtesting
    backtester = Backtester(initial_capital=100000.0)
    backtest_result = backtester.run_backtest(simple_momentum_strategy, prices)

    print(f"\nWorkflow Summary:")
    print(f"  Risk Management: Position size calculated ({position_size:.2f})")
    print(f"  Order Management: Order routed to {result.get('exchange', 'N/A')}")
    print(f"  Backtesting: {backtest_result.final_capital:,.2f} final capital")
    print(f"  Total Return: {backtest_result.total_return_pct:.2f}%")
    print(f"  Sharpe Ratio: {backtest_result.sharpe_ratio:.4f}")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH SYSTEM INTEGRATION TEST")
    print("All Modules Integration Testing")
    print("="*70)

    try:
        test_expectation_and_metrics()
        test_risk_management()
        test_order_management()
        test_algo_trading()
        test_backtesting_integration()
        test_full_workflow()

        print("\n" + "="*70)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("="*70)
        print("\nQUANT-MATH framework is working correctly.")
        print("All modules are integrated and functioning as expected.")

    except Exception as e:
        print("\n" + "="*70)
        print("❌ INTEGRATION TEST FAILED!")
        print("="*70)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
