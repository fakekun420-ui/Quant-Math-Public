#!/usr/bin/env python3
"""
Standalone test for algo trading module
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from order_management import OrderManager, SlippageModel
from algo_trading import TWAP, VWAP, POV, AlgoTradingSystem, AlgoExecution


def test_twap():
    print("Testing TWAP Algorithm...")
    np.random.seed(42)

    om = OrderManager(commission_rate=0.001, min_commission=1.0)
    twap = TWAP(time_chunks=5, execution_delay=1.0)

    order = om.create_order("AAPL", "buy", 1000, order_type="market")
    market_price = 150.0

    execution = twap.execute(order, om, market_price)

    print(f"\n  Total volume: {execution.total_volume}")
    print(f"  Executed volume: {execution.executed_volume}")
    print(f"  Avg price: ${execution.avg_price:.2f}")
    print(f"  Slippage: {execution.slippage:.4f}%")
    print(f"  Completion: {execution.completion_status}")


def test_vwap():
    print("\n\nTesting VWAP Algorithm...")
    np.random.seed(42)

    om = OrderManager(commission_rate=0.001, min_commission=1.0)
    vwap = VWAP(execution_time=60, interval=1)

    order = om.create_order("MSFT", "buy", 500, order_type="market")
    market_price = 300.0
    market_vol_profile = [0.2, 0.3, 0.5, 0.4, 0.6, 0.8, 1.0]

    execution = vwap.execute(order, om, market_price, market_vol_profile)

    print(f"\n  Total volume: {execution.total_volume}")
    print(f"  Executed volume: {execution.executed_volume}")
    print(f"  Avg price: ${execution.avg_price:.2f}")
    print(f"  Slippage: {execution.slippage:.4f}%")
    print(f"  Trades: {len(execution.trades)}")


def test_pov():
    print("\n\nTesting POV Algorithm...")
    np.random.seed(42)

    om = OrderManager(commission_rate=0.001, min_commission=1.0)
    pov = POV(volume_pct=0.2, max_slippage=0.01)

    order = om.create_order("GOOGL", "buy", 200, order_type="market")
    market_price = 1500.0
    available_volume = 10000.0

    execution = pov.execute(order, om, market_price, available_volume)

    print(f"\n  Total volume: {execution.total_volume}")
    print(f"  Executed volume: {execution.executed_volume}")
    print(f"  Avg price: ${execution.avg_price:.2f}")
    print(f"  Slippage: {execution.slippage:.4f}%")
    print(f"  Completion: {execution.completion_status}")


def test_algo_system():
    print("\n\nTesting Algo Trading System...")
    np.random.seed(42)

    om = OrderManager(commission_rate=0.001, min_commission=1.0)
    system = AlgoTradingSystem(om)

    # Execute single order
    execution = system.execute_order("AAPL", "buy", 300, algo_type="vwap", market_price=150.0)
    metrics = system.get_performance_metrics(execution)

    print(f"\n  VWAP execution:")
    print(f"    Total slippage: {metrics['total_slippage_pct']:.4f}%")
    print(f"    Completion rate: {metrics['completion_rate']:.1f}%")
    print(f"    Avg price: ${metrics['avg_price']:.2f}")
    print(f"    Trades: {metrics['num_trades']}")

    # Compare algorithms
    print(f"\n  Algorithm comparison:")
    results = system.compare_algos("MSFT", "sell", 200, [298.0, 299.0, 298.5, 300.0, 299.5])
    for algo, metrics in results.items():
        print(f"    {algo.upper()}: slippage={metrics['total_slippage_pct']:.4f}%, completion={metrics['completion_rate']:.1f}%")


def test_multiple_orders():
    print("\n\nTesting Multiple Orders...")
    np.random.seed(42)

    om = OrderManager(commission_rate=0.001, min_commission=1.0)
    system = AlgoTradingSystem(om)

    # Execute multiple orders
    for algo_type in ['twap', 'vwap', 'pov']:
        execution = system.execute_order(
            symbol="AAPL",
            side="buy",
            quantity=200,
            algo_type=algo_type,
            market_price=150.0
        )
        metrics = system.get_performance_metrics(execution)
        print(f"\n  {algo_type.upper()} - {execution.algo_id}:")
        print(f"    Slippage: {metrics['total_slippage_pct']:.4f}%")
        print(f"    Trades: {metrics['num_trades']}")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH MODULE 13: Algo Trading System (Standalone Test)")
    print("="*70)

    test_twap()
    test_vwap()
    test_pov()
    test_algo_system()
    test_multiple_orders()

    print("\n" + "="*70)
    print("Standalone test completed!")
    print("="*70 + "\n")
