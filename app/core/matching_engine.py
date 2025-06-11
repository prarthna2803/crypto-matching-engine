from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.models.trade import Trade
from app.models.market_data import BBO, OrderBookUpdate
from app.models.fee import FeeModel
from app.core.order_book import OrderBook

# configuring logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Main matching engine that manages multiple order books for different trading pairs.
    """
    
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}
        self.all_orders: Dict[str, Order] = {}
        self.all_trades: List[Trade] = []
        self.pending_trigger_orders: Dict[str, List[Order]] = {}  # Symbol -> List of pending trigger orders
        self.fee_model = FeeModel()  # initializing the fee model
        self.persistence_manager = None  # will be set by main.py
        logger.info("Matching engine initialized")
    
    def get_or_create_order_book(self, symbol: str) -> OrderBook:
        """Get an existing order book or create a new one if it doesn't exist."""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]
    
    def process_order(self, order: Order) -> Tuple[List[Trade], Order]:
        """
        Process a new order.
        Returns a list of trades executed and the updated order.
        """
        # Validate order
        if not self._validate_order(order):
            order.status = OrderStatus.REJECTED
            return [], order
        
        # Get the appropriate order book
        order_book = self.get_or_create_order_book(order.symbol)
        
        # Handle stop and take-profit orders
        if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT]:
            # Store the order in pending triggers
            if order.symbol not in self.pending_trigger_orders:
                self.pending_trigger_orders[order.symbol] = []
            
            self.pending_trigger_orders[order.symbol].append(order)
            self.all_orders[order.order_id] = order
            
            logger.info(f"Added pending trigger order: {order.order_id} - {order.order_type} at {order.stop_price}")
            
            # saving state if persistence manager is available
            if self.persistence_manager:
                self.persistence_manager.order_repository.save_order(order)
                
            return [], order
        
        # Process regular order
        trades, updated_order = order_book.add_order(order)
        
        if updated_order.status != OrderStatus.REJECTED:
            self.all_orders[updated_order.order_id] = updated_order
            
            # save order if persistence manager is available
            if self.persistence_manager:
                self.persistence_manager.order_repository.save_order(updated_order)
        
        if trades:
            for trade in trades:
                trade_value = trade.price * trade.quantity
                fee_schedule = self.fee_model.get_fee_schedule(order.symbol)
                
                # calculate fees
                maker_fee = fee_schedule.calculate_maker_fee(trade_value)
                taker_fee = fee_schedule.calculate_taker_fee(trade_value)
                
                # adding fees to the trade
                trade.maker_fee = maker_fee
                trade.taker_fee = taker_fee
                trade.maker_fee_rate = fee_schedule.maker_rate
                trade.taker_fee_rate = fee_schedule.taker_rate
                
                logger.info(f"Fees calculated for trade {trade.trade_id}: maker={maker_fee}, taker={taker_fee}")
                
                # Save trade if persistence manager is available
                if self.persistence_manager:
                    self.persistence_manager.trade_repository.save_trade(trade)
            
            self.all_trades.extend(trades)
            # checking if any pending trigger orders should be activated
            self._check_triggers(order.symbol, trades[-1].price)
        
        return trades, updated_order
    
    def cancel_order(self, order_id: str) -> Optional[Order]:
        """
        Cancel an order by ID.
        Returns the canceled order or None if not found.
        """
        if order_id not in self.all_orders:
            return None
        
        order = self.all_orders[order_id]
        
        # check if it's a pending trigger order
        if order.status == OrderStatus.PENDING_TRIGGER:
            if order.symbol in self.pending_trigger_orders:
                # find and remove from pending trigger orders
                for i, pending_order in enumerate(self.pending_trigger_orders[order.symbol]):
                    if pending_order.order_id == order_id:
                        removed_order = self.pending_trigger_orders[order.symbol].pop(i)
                        removed_order.status = OrderStatus.CANCELED
                        self.all_orders[order_id] = removed_order
                        
                        # updating order in database if persistence manager is available
                        if self.persistence_manager:
                            self.persistence_manager.order_repository.save_order(removed_order)
                            
                        logger.info(f"Canceled pending trigger order: {order_id}")
                        return removed_order
            
            # If we get here, the order wasn't found in pending_trigger_orders
            return None
        
        # Handle regular orders
        if order.symbol not in self.order_books:
            return None
        
        order_book = self.order_books[order.symbol]
        canceled_order = order_book.cancel_order(order_id)
        
        if canceled_order:
            self.all_orders[order_id] = canceled_order
            
            # Update order in database if persistence manager is available
            if self.persistence_manager:
                self.persistence_manager.order_repository.save_order(canceled_order)
        
        return canceled_order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self.all_orders.get(order_id)
    
    def get_bbo(self, symbol: str) -> Optional[BBO]:
        """Get the current Best Bid and Offer for a symbol."""
        if symbol not in self.order_books:
            return None
        return self.order_books[symbol].get_bbo()
    
    def get_order_book_snapshot(self, symbol: str, depth: int = 10) -> Optional[OrderBookUpdate]:
        """Get a snapshot of the order book for a symbol."""
        if symbol not in self.order_books:
            return None
        return self.order_books[symbol].get_order_book_snapshot(depth)
    
    def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades for a symbol."""
        if symbol not in self.order_books:
            return []
        
        # Get trades from the order book, most recent first
        trades = self.order_books[symbol].trades
        return sorted(trades, key=lambda t: t.timestamp, reverse=True)[:limit]
    
    def _validate_order(self, order: Order) -> bool:
        """Validate an order."""
        # Check required fields
        if not order.symbol or not order.order_type or not order.side or order.quantity <= 0:
            logger.warning(f"Invalid order: missing required fields or invalid quantity")
            return False
        
        # Check price for limit orders
        if order.order_type in [OrderType.LIMIT, OrderType.IOC, OrderType.FOK] and (order.price is None or order.price <= 0):
            logger.warning(f"Invalid limit order: missing or invalid price")
            return False
            
        # Check stop price for stop orders
        if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT] and (order.stop_price is None or order.stop_price <= 0):
            logger.warning(f"Invalid stop order: missing or invalid stop price")
            return False
            
        # Check limit price for stop-limit orders
        if order.order_type == OrderType.STOP_LIMIT and (order.limit_price is None or order.limit_price <= 0):
            logger.warning(f"Invalid stop-limit order: missing or invalid limit price")
            return False
        
        return True
    
    def _check_triggers(self, symbol: str, last_price: float) -> None:
        """
        Check if any pending trigger orders should be activated based on the last trade price.
        """
        if symbol not in self.pending_trigger_orders or not self.pending_trigger_orders[symbol]:
            return
            
        # Get the order book
        order_book = self.get_or_create_order_book(symbol)
        
        # Check each pending trigger order
        triggered_orders = []
        remaining_orders = []
        
        for order in self.pending_trigger_orders[symbol]:
            if order.is_triggered(last_price):
                triggered_orders.append(order)
                logger.info(f"Triggered order: {order.order_id} - {order.order_type} at {order.stop_price}")
            else:
                remaining_orders.append(order)
                
        # Update the list of pending trigger orders
        self.pending_trigger_orders[symbol] = remaining_orders
        
        # Process each triggered order
        for order in triggered_orders:
            # Convert to appropriate order type
            if order.order_type == OrderType.STOP_LOSS:
                # Convert to market order
                order.order_type = OrderType.MARKET
                order.status = OrderStatus.OPEN
            elif order.order_type == OrderType.STOP_LIMIT:
                # Convert to limit order with the specified limit price
                order.order_type = OrderType.LIMIT
                order.price = order.limit_price
                order.status = OrderStatus.OPEN
            elif order.order_type == OrderType.TAKE_PROFIT:
                # Convert to market order
                order.order_type = OrderType.MARKET
                order.status = OrderStatus.OPEN
                
            # Process the converted order
            trades, updated_order = order_book.add_order(order)
            
            # Calculate and add fees to each trade
            for trade in trades:
                trade_value = trade.price * trade.quantity
                fee_schedule = self.fee_model.get_fee_schedule(order.symbol)
                
                # Calculate fees
                maker_fee = fee_schedule.calculate_maker_fee(trade_value)
                taker_fee = fee_schedule.calculate_taker_fee(trade_value)
                
                # Add fees to the trade
                trade.maker_fee = maker_fee
                trade.taker_fee = taker_fee
                trade.maker_fee_rate = fee_schedule.maker_rate
                trade.taker_fee_rate = fee_schedule.taker_rate
                
                logger.info(f"Fees calculated for trade {trade.trade_id}: maker={maker_fee}, taker={taker_fee}")
                
                # Save trade if persistence manager is available
                if self.persistence_manager:
                    self.persistence_manager.trade_repository.save_trade(trade)
            
            # Update the order in all_orders
            self.all_orders[order.order_id] = updated_order
            
            # Update order in database if persistence manager is available
            if self.persistence_manager:
                self.persistence_manager.order_repository.save_order(updated_order)
            
            # Add trades to the list
            if trades:
                self.all_trades.extend(trades)
    
    def set_fee_schedule(self, symbol: str, maker_rate: float, taker_rate: float) -> None:
        """Set a custom fee schedule for a symbol."""
        fee_schedule = self.fee_model.set_fee_schedule(symbol, maker_rate, taker_rate)
        logger.info(f"Fee schedule set for {symbol}: maker={maker_rate}, taker={taker_rate}")
        
        # Save fee schedule if persistence manager is available
        if self.persistence_manager:
            self.persistence_manager.fee_repository.save_fee_schedule(fee_schedule)
    
    def set_default_fee_rates(self, maker_rate: float, taker_rate: float) -> None:
        """Set the default fee rates."""
        self.fee_model.set_default_rates(maker_rate, taker_rate)
        logger.info(f"Default fee rates set: maker={maker_rate}, taker={taker_rate}")
        
        # Save default fee rates if persistence manager is available
        if self.persistence_manager:
            self.persistence_manager.fee_repository.save_default_fee_rates(maker_rate, taker_rate)
    
    def get_fee_schedule(self, symbol: str) -> dict:
        """Get the fee schedule for a symbol."""
        fee_schedule = self.fee_model.get_fee_schedule(symbol)
        return {
            "symbol": fee_schedule.symbol,
            "maker_rate": fee_schedule.maker_rate,
            "taker_rate": fee_schedule.taker_rate
        }
    
    def save_state(self) -> None:
        """Save the current state to the database."""
        if self.persistence_manager:
            self.persistence_manager.save_engine_state(self)
            logger.info("Engine state saved to database")
    
    def load_state(self) -> None:
        """Load the state from the database."""
        if self.persistence_manager:
            self.persistence_manager.load_engine_state(self)
            logger.info("Engine state loaded from database")
