"""
Order Management Module

This module provides order management and execution capabilities including:
- Order types (market, limit, stop)
- Slippage modeling
- Order book management
- Execution strategies
- Transaction costs
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
import warnings


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    order_type: str  # 'market', 'limit', 'stop'
    price: float = None  # For limit/stop orders
    stop_price: float = None  # For stop orders
    status: str = 'pending'  # 'pending', 'filled', 'partial', 'cancelled'
    filled_quantity: int = 0
    filled_price: float = None
    last_price: float = None  # Last known market price
    timestamp: float = field(default_factory=lambda: np.random.random())
    commission: float = 0.0


@dataclass
class OrderBook:
    """Represents a limit order book for a symbol."""
    symbol: str
    bids: List[Tuple[float, float]]  # (price, quantity)
    asks: List[Tuple[float, float]]
    last_price: float = None


@dataclass
class ExecutionReport:
    """Result of order execution."""
    order_id: str
    symbol: str
    filled_quantity: int
    avg_price: float
    commission: float
    slippage: float
    execution_time: float
    total_cost: float
    status: str


class SlippageModel:
    """
    Slippage Model

    Estimates slippage based on order size and market conditions.
    """

    @staticmethod
    def market_impact_model(volume: float, market_volume: float,
                           price_impact_coeff: float = 1e-5) -> float:
        """
        Estimate slippage based on relative order volume.

        Parameters
        ----------
        volume : float
            Order volume
        market_volume : float
            Total market volume
        price_impact_coeff : float
            Price impact coefficient

        Returns
        -------
        slippage : float
            Estimated slippage in percentage
        """
        if market_volume == 0:
            return 0.0

        rel_volume = volume / market_volume
        slippage = price_impact_coeff * rel_volume ** 2

        return slippage

    @staticmethod
    def realized_slippage(order, executed_price: float = None,
                          quantity: float = 0.0) -> float:
        """
        Calculate realized slippage.

        Two modes:

        Order mode (legacy):
            order : Order - Original order
            executed_price : float - Price at which order was executed

        Price mode (returns dollar cost):
            order : float - Expected/reference price
            executed_price : float - Actual execution price
            quantity : float - Executed quantity

        Returns
        -------
        slippage : float
            Realized slippage (percentage in order mode,
            dollar cost in price mode)
        """
        if isinstance(order, Order):
            if order.order_type == 'market':
                if order.last_price is None:
                    return 0.0
                slippage = (executed_price - order.last_price) / order.last_price * 100
                return slippage
            elif order.order_type in ['limit', 'stop']:
                if order.price is None:
                    return 0.0
                slippage = (executed_price - order.price) / order.price * 100
                return slippage
            else:
                return 0.0

        # Price mode: expected_price, executed_price, quantity -> dollar cost
        expected_price = order
        if not expected_price:
            return 0.0
        slippage_pct = (executed_price - expected_price) / expected_price
        return slippage_pct * expected_price * quantity

    @staticmethod
    def _update_last_price(order: Order, executed_price: float):
        """Helper to set last_price after execution."""
        if order.order_type == 'market':
            order.last_price = executed_price


class OrderManager:
    """
    Order Management System

    Handles order creation, management, and execution.
    """

    def __init__(self, commission_rate: float = 0.001,
                 min_commission: float = 1.0):
        """
        Initialize order manager.

        Parameters
        ----------
        commission_rate : float
        Commission rate (0.1% default)
        min_commission : float
        Minimum commission
        """
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.orders: Dict[str, Order] = {}
        self.order_id_counter = 0

    def create_order(self, symbol: str, side: str, quantity: int,
                     order_type: str = 'market', price: float = None,
                     stop_price: float = None) -> Order:
        """
        Create a new order.

        Parameters
        ----------
        symbol : str
            Trading symbol
        side : str
            'buy' or 'sell'
        quantity : int
            Order quantity
        order_type : str
            'market', 'limit', or 'stop'
        price : float, optional
            Limit price
        stop_price : float, optional
            Stop price

        Returns
        -------
        order : Order
            Created order
        """
        self.order_id_counter += 1
        order_id = f"ORD-{self.order_id_counter:06d}"

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            status='pending'
        )

        self.orders[order_id] = order
        return order

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Parameters
        ----------
        order_id : str
            Order ID to cancel

        Returns
        -------
        success : bool
            Whether cancellation was successful
        """
        if order_id not in self.orders:
            return False

        self.orders[order_id].status = 'cancelled'
        return True

    def match_order(self, order: Order, market_price: float,
                    volume_traded: int = None) -> ExecutionReport:
        """
        Execute an order against the market.

        Parameters
        ----------
        order : Order
            Order to execute
        market_price : float
            Current market price
        volume_traded : int, optional
            Specific volume to fill (for testing)

        Returns
        -------
        report : ExecutionReport
            Execution results
        """
        # Update order price
        order.last_price = market_price

        # Determine execution price based on order type
        if order.order_type == 'market':
            executed_price = market_price
        elif order.order_type == 'limit':
            if order.price is None:
                executed_price = market_price
            else:
                executed_price = order.price
        elif order.order_type == 'stop':
            if order.stop_price is None:
                executed_price = market_price
            else:
                executed_price = order.stop_price
        else:
            executed_price = market_price

        # Update last_price for market orders
        SlippageModel._update_last_price(order, executed_price)

        # Determine filled quantity
        if volume_traded is not None:
            filled_quantity = min(volume_traded, order.quantity)
        else:
            filled_quantity = order.quantity

        # Calculate slippage
        slippage = SlippageModel.realized_slippage(order, executed_price)

        # Calculate commission
        trade_value = filled_quantity * executed_price
        commission = max(self.min_commission,
                        trade_value * self.commission_rate)

        # Update order
        order.filled_quantity = filled_quantity
        order.filled_price = executed_price
        order.commission = commission
        order.status = 'filled' if filled_quantity == order.quantity else 'partial'

        # Create execution report
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            filled_quantity=filled_quantity,
            avg_price=executed_price,
            commission=commission,
            slippage=slippage,
            execution_time=order.timestamp,
            total_cost=trade_value + commission,
            status=order.status
        )

        return report

    def get_order_status(self, order_id: str) -> Optional[Order]:
        """
        Get order status.

        Parameters
        ----------
        order_id : str
            Order ID

        Returns
        -------
        order : Order or None
            Order details
        """
        return self.orders.get(order_id)


class ExecutionStrategy:
    """
    Execution Strategy

    Determines optimal execution timing and pacing.
    """

    @staticmethod
    def vwap_execution(order=None, order_book=None, total_volume: int = None,
                       num_chunks: int = 10, symbol: str = None,
                       total_quantity: float = None, time_horizon: int = None,
                       price_data=None) -> List[Order]:
        """
        Execute order using VWAP (Volume Weighted Average Price) strategy.

        Two call styles:

        Order-based (legacy):
            vwap_execution(order, order_book, total_volume, num_chunks)

        Data-driven:
            vwap_execution(symbol=..., total_quantity=...,
                           time_horizon=..., price_data=np.ndarray)
        """
        if isinstance(order, dict) or (symbol is not None and order is None):
            # Data-driven mode
            params = order if isinstance(order, dict) else {}
            sym = symbol or params.get("symbol", "UNKNOWN")
            qty = total_quantity if total_quantity is not None else params.get("total_quantity", 0.0)
            horizon = time_horizon if time_horizon is not None else params.get("time_horizon", 3600)
            prices = np.asarray(price_data if price_data is not None else params.get("price_data", []), dtype=float)
            n_chunks = max(1, min(num_chunks, int(horizon // 60) if horizon >= 60 else num_chunks))
            chunk_qty = qty / n_chunks
            chunks = []
            for i in range(n_chunks):
                px = prices[min(i * max(1, len(prices) // n_chunks), len(prices) - 1)] if len(prices) else None
                chunks.append(Order(
                    order_id=f"VWAP-{i:04d}",
                    symbol=sym,
                    side='buy',
                    quantity=chunk_qty,
                    order_type='market',
                    status='pending',
                    price=px
                ))
            return chunks

        if hasattr(order, 'quantity'):
            total_volume = order.quantity if total_volume is None else total_volume

        chunks = []
        chunk_size = total_volume // num_chunks

        for i in range(num_chunks):
            chunk = Order(
                order_id=f"VWAP-{i:04d}",
                symbol=order.symbol,
                side=order.side,
                quantity=chunk_size,
                order_type='market',
                status='pending'
            )
            chunks.append(chunk)

        return chunks

    @staticmethod
    def implementation_shortfall(order: Order, order_book: OrderBook,
                                 expected_price: float,
                                 execution_steps: List[float]) -> Dict[str, float]:
        """
        Calculate implementation shortfall.

        Parameters
        ----------
        order : Order
            Order details
        order_book : OrderBook
            Current market state
        expected_price : float
            Expected price
        execution_steps : List[float]
            Execution prices

        Returns
        -------
        shortfall : dict
            Implementation shortfall metrics
        """
        realized_price = np.mean(execution_steps)
        actual_cost = order.quantity * realized_price
        expected_cost = order.quantity * expected_price

        slippage = actual_cost - expected_cost
        slippage_pct = slippage / expected_cost * 100

        return {
            'realized_price': realized_price,
            'slippage': slippage,
            'slippage_pct': slippage_pct,
            'implementation_shortfall': slippage_pct
        }


class TransactionCostModel:
    """
    Transaction Cost Model

    Estimates transaction costs including commission and slippage.
    """

    def total_cost(order=None, executed_price: float = None,
                   market_vol: float = None, order_value: float = None,
                   slippage: float = 0.0, commission_rate: float = 0.001):
        """
        Calculate total transaction cost.

        Two modes:

        Order mode (legacy, returns tuple):
            order : Order - Order details
            executed_price : float - Execution price
            market_vol : float - Market volume

        Value mode (returns float):
            order_value : float - Notional value of the order
            slippage : float - Slippage cost in dollars
            commission_rate : float - Commission rate (min $1 applies)

        Returns
        -------
        total_cost : float / tuple
        commission : float
        slippage : float
        """
        if order_value is not None:
            # Value mode: single total cost in dollars
            commission = max(1.0, order_value * commission_rate)
            return commission + (slippage or 0.0)

        trade_value = order.quantity * executed_price
        slippage_pct = SlippageModel.realized_slippage(order, executed_price)
        slippage_cost = trade_value * slippage_pct / 100

        commission = max(1.0, trade_value * 0.001)

        total_cost = trade_value + commission + slippage_cost

        return total_cost, commission, slippage_cost
