#!/usr/bin/env python3
"""
Standalone test for order management module
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from order_management import Order, OrderManager, ExecutionReport, SlippageModel, ExecutionStrategy, TransactionCostModel


def test_slippage():
    print("Testing Slippage Model...")
    np.random.seed(42)

    # Market impact
    slippage = SlippageModel.market_impact_model(1000, 10000, 1e-5)
    print(f"  Slippage for 1000 volume in 10000 market: {slippage:.4f}%")

    # Realized slippage (market order)
    order = Order(order_id="TEST-001", symbol="AAPL", side="buy",
                  quantity=100, order_type="market")
    executed_price = 150.0
    realized_slippage = SlippageModel.realized_slippage(order, executed_price)
    print(f"  Realized slippage: {realized_slippage:.4f}%")

    # Realized slippage (limit order)
    order.price = 149.0
    executed_price = 149.5
    realized_slippage = SlippageModel.realized_slippage(order, executed_price)
    print(f"  Realized slippage (limit): {realized_slippage:.4f}%")

    # Realized slippage (stop order)
    order.order_type = "stop"
    order.stop_price = 148.0
    executed_price = 148.5
    realized_slippage = SlippageModel.realized_slippage(order, executed_price)
    print(f"  Realized slippage (stop): {realized_slippage:.4f}%")


def test_order_manager():
    print("\n\nTesting Order Manager...")
    np.random.seed(42)

    om = OrderManager(commission_rate=0.001, min_commission=1.0)

    # Create orders
    order1 = om.create_order("AAPL", "buy", 100)
    order2 = om.create_order("MSFT", "sell", 50)
    order3 = om.create_order("GOOGL", "buy", 25, order_type="limit", price=1500.0)

    print(f"\n  Created {len(om.orders)} orders:")
    for oid, o in om.orders.items():
        print(f"    {o.order_id}: {o.symbol} {o.side} {o.quantity} @ {o.order_type}")

    # Execute orders
    report1 = om.match_order(order1, market_price=150.0)
    print(f"\n  Order {order1.order_id} executed:")
    print(f"    Filled: {report1.filled_quantity} @ {report1.avg_price:.2f}")
    print(f"    Commission: ${report1.commission:.2f}")
    print(f"    Slippage: {report1.slippage:.4f}%")
    print(f"    Total cost: ${report1.total_cost:.2f}")

    # Partial fill
    report2 = om.match_order(order2, market_price=300.0, volume_traded=25)
    print(f"\n  Order {order2.order_id} partially filled:")
    print(f"    Filled: {report2.filled_quantity} @ {report2.avg_price:.2f}")
    print(f"    Status: {report2.status}")

    # Cancel order
    success = om.cancel_order("TEST-001")
    print(f"\n  Cancelled order TEST-001: {success}")


def test_execution_strategy():
    print("\n\nTesting Execution Strategy...")
    np.random.seed(42)

    order = Order(order_id="STRAT-001", symbol="AAPL", side="buy",
                  quantity=1000, order_type="market")

    # VWAP execution
    chunks = ExecutionStrategy.vwap_execution(order, None, 1000, 5)
    print(f"\n  VWAP chunks for 1000 shares in 5 steps:")
    for i, chunk in enumerate(chunks):
        print(f"    Chunk {i+1}: {chunk.quantity} shares")

    # Implementation shortfall
    order_book = type('OB', (), {'last_price': 150.0})()
    execution_steps = [150.0, 150.1, 150.05, 150.02]
    shortfall = ExecutionStrategy.implementation_shortfall(
        order, order_book, 150.0, execution_steps
    )
    print(f"\n  Implementation shortfall:")
    print(f"    Realized price: ${shortfall['realized_price']:.2f}")
    print(f"    Slippage: {shortfall['slippage_pct']:.4f}%")


def test_transaction_cost():
    print("\n\nTesting Transaction Cost Model...")
    np.random.seed(42)

    order = Order(order_id="COST-001", symbol="AAPL", side="buy",
                  quantity=100, order_type="market")

    executed_price = 150.0
    market_vol = 1000000

    total_cost, commission, slippage = TransactionCostModel.total_cost(
        order, executed_price, market_vol
    )

    print(f"\n  Transaction cost for {order.quantity} @ ${executed_price:.2f}:")
    print(f"    Total cost: ${total_cost:.2f}")
    print(f"    Commission: ${commission:.2f}")
    print(f"    Slippage: ${slippage:.2f}")
    print(f"    Slippage %: {slippage / (order.quantity * executed_price) * 100:.4f}%")


if __name__ == "__main__":
    print("="*70)
    print("QUANT-MATH MODULE 12: Order Management (Standalone Test)")
    print("="*70)

    test_slippage()
    test_order_manager()
    test_execution_strategy()
    test_transaction_cost()

    print("\n" + "="*70)
    print("Standalone test completed!")
    print("="*70 + "\n")
