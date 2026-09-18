# Order Types Module
from enum import Enum

class OrderType(Enum):
    """Supported order types."""
    MARKET = 'market'
    LIMIT = 'limit'
    STOP_LOSS = 'stop_loss'
    STOP_LOSS_LIMIT = 'stop_loss_limit'
    TAKE_PROFIT = 'take_profit'
    TAKE_PROFIT_LIMIT = 'take_profit_limit'
    TRAILING_STOP = 'trailing_stop'
    TRAILING_STOP_LIMIT = 'trailing_stop_limit'

class Order:
    """Base order class."""

    def __init__(self, symbol: str, side: str, order_type: OrderType,
                 amount: float, price: float = None, stop_price: float = None):
        """
        Initialize order.

        Parameters:
        -----------
        symbol : str
            Trading symbol
        side : str
            'buy' or 'sell'
        order_type : OrderType
            Order type
        amount : float
            Order amount
        price : float, optional
            Limit price
        stop_price : float, optional
            Stop price for stop orders
        """
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.amount = amount
        self.price = price
        self.stop_price = stop_price
        self.status = 'pending'

    def validate(self) -> bool:
        """
        Validate order parameters.

        Returns:
        --------
        bool
            True if valid
        """
        if self.side not in ['buy', 'sell']:
            return False

        if self.amount <= 0:
            return False

        if self.order_type == OrderType.LIMIT and self.price is None:
            return False

        if self.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT] and self.stop_price is None:
            return False

        return True
