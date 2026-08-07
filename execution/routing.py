# Order Routing Module
from typing import List, Dict, Optional
from .order_types import Order, OrderType

class OrderRouter:
    """Route orders to appropriate execution venues."""

    def __init__(self):
        """Initialize order router."""
        self.exchanges = {}

    def register_exchange(self, name: str, priority: int = 0) -> None:
        """
        Register an exchange for order routing.

        Parameters:
        -----------
        name : str
            Exchange name
        priority : int
            Routing priority (higher = preferred)
        """
        self.exchanges[name] = {
            'priority': priority,
            'active': True
        }

    def route_order(self, order: Order) -> Dict:
        """
        Route an order to the best available exchange.

        Parameters:
        -----------
        order : Order
            Order to route

        Returns:
        --------
        Dict
            Routing result with order_id, exchange, and executed flag
        """
        # Find best exchange
        best_exchange = None
        best_priority = -1

        for name, exchange in self.exchanges.items():
            if exchange['active']:
                if exchange['priority'] > best_priority:
                    best_priority = exchange['priority']
                    best_exchange = name

        if best_exchange is None:
            return {'error': 'No active exchanges available'}

        # Generate order ID
        order_id = f"{best_exchange}_{order.symbol}_{order.order_type.name}"

        return {
            'order_id': order_id,
            'exchange': best_exchange,
            'symbol': order.symbol,
            'executed': True,
            'order': order
        }

    def get_execution_fees(self, exchange_name: str, order_type: OrderType, volume: float) -> float:
        """
        Estimate execution fees for an order.

        Parameters:
        -----------
        exchange_name : str
            Exchange name
        order_type : OrderType
            Order type
        volume : float
            Order volume

        Returns:
        --------
        float
            Estimated fee
        """
        # Placeholder fee structure
        fee_tiers = {
            'BTC/USDT': {'0-1': 0.001, '1-10': 0.0008, '10-100': 0.0006, '100+': 0.0004},
            'ETH/USDT': {'0-10': 0.001, '10-100': 0.0008, '100+': 0.0005}
        }

        # Normalize order type to symbol format
        symbol = f"{order_type.name}/{order_type.name}"
        fees = fee_tiers.get(symbol, {'100+': 0.001})

        # Find appropriate fee tier
        tier = '100+'
        if volume < 1:
            tier = '0-1'
        elif volume < 10:
            tier = '1-10'
        elif volume < 100:
            tier = '10-100'

        return volume * fees.get(tier, 0.001)

    def get_supported_exchanges(self) -> List[str]:
        """
        Get list of registered exchanges.

        Returns:
        --------
        List[str]
            Exchange names
        """
        return list(self.exchanges.keys())

    def get_active_exchanges(self) -> List[str]:
        """
        Get list of active exchanges.

        Returns:
        --------
        List[str]
            Active exchange names
        """
        return [name for name, exchange in self.exchanges.items() if exchange['active']]
