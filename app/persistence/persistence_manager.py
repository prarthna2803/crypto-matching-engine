"""
Persistence manager for the cryptocurrency matching engine.
Coordinates persistence operations across repositories.
"""
import logging
from typing import Dict, List, Optional, Tuple

from app.models.order import Order
from app.models.trade import Trade
from app.models.fee import FeeSchedule, FeeModel
from app.core.matching_engine import MatchingEngine
from app.core.order_book import OrderBook
from app.persistence.database import Database
from app.persistence.order_repository import OrderRepository
from app.persistence.trade_repository import TradeRepository
from app.persistence.fee_repository import FeeRepository

# Configure logging
logger = logging.getLogger(__name__)

class PersistenceManager:
    """
    Manages persistence operations for the matching engine.
    Coordinates saving and loading of orders, trades, and fee schedules.
    """
    
    def __init__(self, db_path: str = "trading_app.db"):
        """Initialize the persistence manager."""
        self.database = Database(db_path)
        self.order_repository = OrderRepository(self.database)
        self.trade_repository = TradeRepository(self.database)
        self.fee_repository = FeeRepository(self.database)
        logger.info("Persistence manager initialized")
    
    def save_engine_state(self, engine: MatchingEngine) -> None:
        """
        Save the current state of the matching engine to the database.
        This includes all orders, trades, and fee schedules.
        """
        try:
            # Save all orders
            all_orders = list(engine.all_orders.values())
            self.order_repository.save_orders(all_orders)
            
            # Save all trades
            self.trade_repository.save_trades(engine.all_trades)
            
            # Save fee schedules
            for symbol, fee_schedule in engine.fee_model.fee_schedules.items():
                self.fee_repository.save_fee_schedule(fee_schedule)
            
            # Save default fee rates
            self.fee_repository.save_default_fee_rates(
                engine.fee_model.default_maker_rate,
                engine.fee_model.default_taker_rate
            )
            
            logger.info("Engine state saved to database")
        except Exception as e:
            logger.error(f"Error saving engine state: {e}")
            raise
    
    def load_engine_state(self, engine: MatchingEngine) -> None:
        """
        Load the matching engine state from the database.
        This includes all orders, trades, and fee schedules.
        """
        try:
            # Load fee schedules first
            default_maker_rate, default_taker_rate = self.fee_repository.get_default_fee_rates()
            engine.fee_model.set_default_rates(default_maker_rate, default_taker_rate)
            
            fee_schedules = self.fee_repository.get_all_fee_schedules()
            for fee_schedule in fee_schedules:
                engine.fee_model.fee_schedules[fee_schedule.symbol] = fee_schedule
            
            # Get all symbols from orders
            conn = self.database.connect()
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT symbol FROM orders')
            symbols = [row['symbol'] for row in cursor.fetchall()]
            
            # Process each symbol
            for symbol in symbols:
                # Get open orders for this symbol
                open_orders = self.order_repository.get_open_orders_by_symbol(symbol)
                
                # Get pending trigger orders for this symbol
                pending_trigger_orders = self.order_repository.get_pending_trigger_orders_by_symbol(symbol)
                
                # Create order book for this symbol
                order_book = engine.get_or_create_order_book(symbol)
                
                # Add open orders to the order book
                for order in open_orders:
                    engine.all_orders[order.order_id] = order
                    if order.order_type.value == "limit":
                        # Add to the book directly to avoid matching
                        order_book._add_to_book(order)
                        order_book.orders_by_id[order.order_id] = order
                
                # Add pending trigger orders
                if pending_trigger_orders:
                    if symbol not in engine.pending_trigger_orders:
                        engine.pending_trigger_orders[symbol] = []
                    
                    for order in pending_trigger_orders:
                        engine.all_orders[order.order_id] = order
                        engine.pending_trigger_orders[symbol].append(order)
                
                # Update BBO
                order_book._update_bbo()
            
            # Load recent trades
            for symbol in symbols:
                trades = self.trade_repository.get_trades_by_symbol(symbol, limit=1000)
                engine.all_trades.extend(trades)
                
                # Add trades to the order book's trade history
                if symbol in engine.order_books:
                    engine.order_books[symbol].trades.extend(trades)
            
            logger.info("Engine state loaded from database")
        except Exception as e:
            logger.error(f"Error loading engine state: {e}")
            raise
    
    def close(self) -> None:
        """Close the database connection."""
        self.database.close()
