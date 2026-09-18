"""
Algorithmic Trading System

This module provides algorithmic trading capabilities including:
- Execution algorithms (TWAP, VWAP, POV, Arrivals)
- Smart order routing
- Risk management for algo execution
- Performance monitoring
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from order_management import Order, OrderManager, SlippageModel, ExecutionReport


@dataclass
class AlgoExecution:
    """Result of algorithmic execution."""
    algo_id: str
    symbol: str
    side: str
    total_volume: int
    executed_volume: int
    avg_price: float
    slippage: float
    completion_status: str
    execution_time: float
    trades: List[ExecutionReport]


class TWAP:
    """
    Time-Weighted Average Price (TWAP)

    Splits order into equal time chunks for smooth execution.
    """

    def __init__(self, time_chunks: int = 10, execution_delay: float = 1.0,
                 total_quantity: float = None, time_horizon: int = None):
        """
        Initialize TWAP algorithm.

        Two modes:

        Order-based (legacy):
            time_chunks : int
            execution_delay : float

        Data-driven simulation:
            total_quantity : float - Total quantity to execute
            time_horizon : int - Execution horizon in seconds
        """
        self.time_chunks = time_chunks
        self.execution_delay = execution_delay
        self.total_quantity = total_quantity
        self.time_horizon = time_horizon

    def execute(self, order=None, order_manager: "OrderManager" = None,
                market_price: float = None, price_data=None,
                current_price: float = None, **kwargs):
        """
        Execute using TWAP.

        Order-based mode: execute(order, order_manager, market_price) -> AlgoExecution
        Data-driven mode: execute(price_data=..., current_price=...) -> list of slices
        """
        if price_data is not None or isinstance(order, np.ndarray) or (
                order is not None and not hasattr(order, 'quantity')):
            # Data-driven simulation mode
            prices = np.asarray(price_data if price_data is not None else order,
                                dtype=float)
            n_slices = max(1, min(len(prices), int((self.time_horizon or 3600) // 60)))
            slice_qty = self.total_quantity / n_slices
            ref_price = current_price if current_price is not None else prices[0]
            slices = []
            for i in range(n_slices):
                px = prices[min(i * max(1, len(prices) // n_slices), len(prices) - 1)]
                slices.append({
                    "slice": i + 1,
                    "symbol": kwargs.get("symbol", "UNKNOWN"),
                    "quantity": slice_qty,
                    "price": float(px),
                    "deviation_pct": (px - ref_price) / ref_price * 100,
                })
            return slices

        chunk_size = order.quantity // self.time_chunks
        executed_volume = 0
        total_slippage = 0
        trades = []

        for i in range(self.time_chunks):
            # Create chunk order
            chunk = order_manager.create_order(
                symbol=order.symbol,
                side=order.side,
                quantity=chunk_size,
                order_type='market'
            )

            # Execute chunk
            report = order_manager.match_order(chunk, market_price)
            trades.append(report)
            executed_volume += report.filled_quantity
            total_slippage += report.slippage

        # Calculate statistics
        avg_price = np.mean([t.avg_price for t in trades])
        slippage = np.mean([t.slippage for t in trades])

        execution = AlgoExecution(
            algo_id=f"TWAP-{len(order_manager.orders)-1:06d}",
            symbol=order.symbol,
            side=order.side,
            total_volume=order.quantity,
            executed_volume=executed_volume,
            avg_price=avg_price,
            slippage=slippage,
            completion_status='completed' if executed_volume == order.quantity else 'partial',
            execution_time=market_price,  # Simplified time
            trades=trades
        )

        return execution


class VWAP:
    """
    Volume-Weighted Average Price (VWAP)

    Splits order based on expected market volume profile.
    """

    def __init__(self, execution_time: int = 60, interval: int = 1,
                 total_quantity: float = None, time_horizon: int = None):
        """
        Initialize VWAP algorithm.

        Two modes:

        Order-based (legacy):
            execution_time : int - Total execution time in minutes
            interval : int - Execution interval in minutes

        Data-driven simulation:
            total_quantity : float - Total quantity to execute
            time_horizon : int - Execution horizon in seconds
        """
        self.execution_time = execution_time
        self.interval = interval
        if execution_time and interval:
            self.time_points = np.linspace(0, execution_time, max(1, int(execution_time / interval)))
        else:
            self.time_points = None
        self.total_quantity = total_quantity
        self.time_horizon = time_horizon

    def execute(self, order=None, order_manager: "OrderManager" = None,
                market_price: float = None,
                market_vol_profile: List[float] = None,
                price_data=None, volume_data=None,
                current_price: float = None, **kwargs):
        """
        Execute using VWAP.

        Order-based mode: execute(order, order_manager, market_price) -> AlgoExecution
        Data-driven mode: execute(price_data=..., volume_data=..., current_price=...) -> list of slices
        """
        if price_data is not None or isinstance(order, np.ndarray) or (
                order is not None and not hasattr(order, 'quantity')):
            prices = np.asarray(price_data if price_data is not None else order,
                                dtype=float)
            volumes = np.asarray(
                volume_data if volume_data is not None else market_vol_profile,
                dtype=float)
            n_slices = max(1, min(len(prices), int((self.time_horizon or 3600) // 60)))
            ref_price = current_price if current_price is not None else prices[0]
            weights = volumes / volumes.sum() if volumes.sum() > 0 else np.full(len(prices), 1 / len(prices))
            slices = []
            for i in range(n_slices):
                idx = min(i * max(1, len(prices) // n_slices), len(prices) - 1)
                px = prices[idx]
                qty = self.total_quantity * weights[idx] * n_slices
                slices.append({
                    "slice": i + 1,
                    "symbol": kwargs.get("symbol", "UNKNOWN"),
                    "quantity": float(qty),
                    "price": float(px),
                    "deviation_pct": (px - ref_price) / ref_price * 100,
                })
            return slices

        return self._execute_order_based(order, order_manager, market_price, market_vol_profile)

    def _execute_order_based(self, order: Order, order_manager: OrderManager,
                             market_price: float,
                             market_vol_profile: List[float] = None) -> AlgoExecution:
        """
        Execute order using VWAP.

        Parameters
        ----------
        order : Order
            Order to execute
        order_manager : OrderManager
            Order manager instance
        market_price : float
            Current market price
        market_vol_profile : list, optional
            Expected market volume at each time point

        Returns
        -------
        execution : AlgoExecution
            Execution results
        """
        if market_vol_profile is None:
            market_vol_profile = [1.0] * len(self.time_points)

        # Execute chunks based on volume profile
        total_volume = sum(market_vol_profile)
        chunk_sizes = [int(order.quantity * vol / total_volume) for vol in market_vol_profile]

        executed_volume = 0
        total_slippage = 0
        trades = []

        for i, chunk_size in enumerate(chunk_sizes):
            if chunk_size > 0:
                chunk = order_manager.create_order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=chunk_size,
                    order_type='market'
                )

                report = order_manager.match_order(chunk, market_price)
                trades.append(report)
                executed_volume += report.filled_quantity
                total_slippage += report.slippage

        # Calculate statistics
        avg_price = np.mean([t.avg_price for t in trades])
        slippage = np.mean([t.slippage for t in trades])

        execution = AlgoExecution(
            algo_id=f"VWAP-{len(order_manager.orders)-1:06d}",
            symbol=order.symbol,
            side=order.side,
            total_volume=order.quantity,
            executed_volume=executed_volume,
            avg_price=avg_price,
            slippage=slippage,
            completion_status='completed' if executed_volume == order.quantity else 'partial',
            execution_time=market_price,  # Simplified time
            trades=trades
        )

        return execution


class POV:
    """
    Percentage of Volume (POV)

    Splits order based on available market volume percentage.
    """

    def __init__(self, volume_pct: float = 0.2, max_slippage: float = 0.01,
                 total_quantity: float = None, participation_rate: float = None):
        """
        Initialize POV algorithm.

        Two modes:

        Order-based (legacy):
            volume_pct : float - Target volume as percentage (0-1)
            max_slippage : float

        Data-driven simulation:
            total_quantity : float
            participation_rate : float - Fraction of market volume per slice
        """
        self.volume_pct = volume_pct
        self.max_slippage = max_slippage
        self.total_quantity = total_quantity
        self.participation_rate = participation_rate if participation_rate is not None else volume_pct

    def execute(self, order=None, order_manager: "OrderManager" = None,
                market_price: float = None, available_volume: float = None,
                price_data=None, volume_data=None,
                current_price: float = None, **kwargs):
        """
        Execute using POV.

        Order-based mode: execute(order, order_manager, market_price, available_volume) -> AlgoExecution
        Data-driven mode: execute(price_data=..., volume_data=..., current_price=...) -> list of slices
        """
        if price_data is not None or isinstance(order, np.ndarray) or (
                order is not None and not hasattr(order, 'quantity')):
            prices = np.asarray(price_data if price_data is not None else order,
                                dtype=float)
            volumes = np.asarray(
                volume_data if volume_data is not None else available_volume,
                dtype=float)
            ref_price = current_price if current_price is not None else prices[0]
            remaining = self.total_quantity
            slices = []
            i = 0
            while remaining > 1e-12 and i < len(prices):
                market_vol = volumes[i] if len(volumes) else 100.0
                qty = min(remaining, market_vol * self.participation_rate)
                px = prices[i]
                slices.append({
                    "slice": i + 1,
                    "symbol": kwargs.get("symbol", "UNKNOWN"),
                    "quantity": float(qty),
                    "price": float(px),
                    "deviation_pct": (px - ref_price) / ref_price * 100,
                })
                remaining -= qty
                i += 1
            return slices

        return self._execute_order_based(order, order_manager, market_price, available_volume)

    def _execute_order_based(self, order: Order, order_manager: OrderManager,
                             market_price: float, available_volume: float) -> AlgoExecution:
        """
        Execute order using POV.

        Parameters
        ----------
        order : Order
            Order to execute
        order_manager : OrderManager
            Order manager instance
        market_price : float
            Current market price
        available_volume : float
            Available market volume

        Returns
        -------
        execution : AlgoExecution
            Execution results
        """
        chunk_size = max(1, int(order.quantity * self.volume_pct / available_volume))

        executed_volume = 0
        total_slippage = 0
        trades = []

        # Execute until order filled or max slippage reached
        while executed_volume < order.quantity:
            remaining = order.quantity - executed_volume
            current_chunk_size = min(chunk_size, remaining)

            chunk = order_manager.create_order(
                symbol=order.symbol,
                side=order.side,
                quantity=current_chunk_size,
                order_type='market'
            )

            report = order_manager.match_order(chunk, market_price)
            trades.append(report)
            executed_volume += report.filled_quantity
            total_slippage += report.slippage

            if executed_volume >= order.quantity:
                break

        # Calculate statistics
        avg_price = np.mean([t.avg_price for t in trades])
        slippage = np.mean([t.slippage for t in trades])

        completion_status = 'completed' if executed_volume == order.quantity else 'partial'

        execution = AlgoExecution(
            algo_id=f"POV-{len(order_manager.orders)-1:06d}",
            symbol=order.symbol,
            side=order.side,
            total_volume=order.quantity,
            executed_volume=executed_volume,
            avg_price=avg_price,
            slippage=slippage,
            completion_status=completion_status,
            execution_time=market_price,
            trades=trades
        )

        return execution


class AlgoTradingSystem:
    """
    Algorithmic Trading System

    Main orchestrator for algorithmic trading strategies.
    """

    def __init__(self, order_manager: OrderManager = None):
        """
        Initialize algo trading system.

        Parameters
        ----------
        order_manager : OrderManager, optional
            Order manager instance (created on demand if omitted)
        """
        self.order_manager = order_manager
        self.algos = {
            'twap': TWAP(),
            'vwap': VWAP(),
            'pov': POV()
        }

    def execute_order(self, symbol: str, side: str, quantity: int,
                      algo_type: str = 'vwap', **kwargs) -> Optional[AlgoExecution]:
        """
        Execute order using specified algorithm.

        Parameters
        ----------
        symbol : str
            Trading symbol
        side : str
            'buy' or 'sell'
        quantity : int
            Order quantity
        algo_type : str
            Algorithm type ('twap', 'vwap', 'pov')
        **kwargs : dict
            Algorithm-specific parameters

        Returns
        -------
        execution : AlgoExecution or None
            Execution results
        """
        if algo_type not in self.algos:
            print(f"Warning: Algorithm {algo_type} not found, using default VWAP")
            algo_type = 'vwap'

        algo = self.algos[algo_type]

        # Create market order
        order = self.order_manager.create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type='market'
        )

        # Execute using algorithm
        if algo_type == 'twap':
            execution = algo.execute(order, self.order_manager, kwargs.get('market_price', 150.0))
        elif algo_type == 'vwap':
            execution = algo.execute(order, self.order_manager, kwargs.get('market_price', 150.0),
                                   kwargs.get('market_vol_profile'))
        elif algo_type == 'pov':
            execution = algo.execute(order, self.order_manager, kwargs.get('market_price', 150.0),
                                   kwargs.get('available_volume', 10000.0))
        else:
            execution = None

        return execution

    def get_performance_metrics(self, execution: AlgoExecution) -> Dict[str, float]:
        """
        Calculate performance metrics for algorithmic execution.

        Parameters
        ----------
        execution : AlgoExecution
            Execution results

        Returns
        -------
        metrics : dict
            Performance metrics
        """
        metrics = {
            'total_slippage_pct': execution.slippage,
            'completion_rate': execution.executed_volume / execution.total_volume * 100,
            'avg_price': execution.avg_price,
            'avg_trade_size': np.mean([t.filled_quantity for t in execution.trades]),
            'num_trades': len(execution.trades),
            'total_volume_executed': execution.executed_volume
        }

        return metrics

    def compare_algos(self, symbol: str, side: str, quantity: int,
                     market_prices: List[float]) -> Dict[str, Dict[str, float]]:
        """
        Compare different algorithms on same order.

        Parameters
        ----------
        symbol : str
            Trading symbol
        side : str
            'buy' or 'sell'
        quantity : int
            Order quantity
        market_prices : list
            List of market prices for comparison

        Returns
        -------
        results : dict
            Algorithm comparison results
        """
        results = {}

        for algo_type in ['twap', 'vwap', 'pov']:
            avg_price = np.mean(market_prices)
            execution = self.execute_order(symbol, side, quantity, algo_type,
                                         market_price=avg_price)

            if execution:
                results[algo_type] = self.get_performance_metrics(execution)

        return results
