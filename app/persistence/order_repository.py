"""
Repository for order persistence operations.
"""
import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.persistence.database import Database

# Configure logging
logger = logging.getLogger(__name__)

class OrderRepository:
    """Repository for order persistence operations."""
    
    def __init__(self, database: Database):
        """Initialize with database connection."""
        self.db = database
    
    def save_order(self, order: Order) -> None:
        """Save an order to the database."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO orders (
                order_id, symbol, order_type, side, quantity, price, stop_price, limit_price,
                timestamp, status, filled_quantity, remaining_quantity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order.order_id,
                order.symbol,
                order.order_type.value,
                order.side.value,
                order.quantity,
                order.price,
                order.stop_price,
                order.limit_price,
                order.timestamp.isoformat(),
                order.status.value,
                order.filled_quantity,
                order.remaining_quantity
            ))
            
            conn.commit()
            logger.debug(f"Order saved: {order.order_id}")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error saving order {order.order_id}: {e}")
            raise
    
    def save_orders(self, orders: List[Order]) -> None:
        """Save multiple orders to the database."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            for order in orders:
                cursor.execute('''
                INSERT OR REPLACE INTO orders (
                    order_id, symbol, order_type, side, quantity, price, stop_price, limit_price,
                    timestamp, status, filled_quantity, remaining_quantity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order.order_id,
                    order.symbol,
                    order.order_type.value,
                    order.side.value,
                    order.quantity,
                    order.price,
                    order.stop_price,
                    order.limit_price,
                    order.timestamp.isoformat(),
                    order.status.value,
                    order.filled_quantity,
                    order.remaining_quantity
                ))
            
            conn.commit()
            logger.debug(f"Saved {len(orders)} orders")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error saving orders: {e}")
            raise
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_order(row)
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting order {order_id}: {e}")
            raise
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all orders for a symbol."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM orders WHERE symbol = ?', (symbol,))
            rows = cursor.fetchall()
            
            return [self._row_to_order(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting orders for symbol {symbol}: {e}")
            raise
    
    def get_open_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all open orders for a symbol."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT * FROM orders 
            WHERE symbol = ? AND (status = ? OR status = ?)
            ''', (symbol, OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value))
            rows = cursor.fetchall()
            
            return [self._row_to_order(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting open orders for symbol {symbol}: {e}")
            raise
    
    def get_pending_trigger_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all pending trigger orders for a symbol."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT * FROM orders 
            WHERE symbol = ? AND status = ?
            ''', (symbol, OrderStatus.PENDING_TRIGGER.value))
            rows = cursor.fetchall()
            
            return [self._row_to_order(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting pending trigger orders for symbol {symbol}: {e}")
            raise
    
    def delete_order(self, order_id: str) -> None:
        """Delete an order from the database."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM orders WHERE order_id = ?', (order_id,))
            conn.commit()
            logger.debug(f"Order deleted: {order_id}")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error deleting order {order_id}: {e}")
            raise
    
    def _row_to_order(self, row: sqlite3.Row) -> Order:
        """Convert a database row to an Order object."""
        return Order(
            order_id=row['order_id'],
            symbol=row['symbol'],
            order_type=OrderType(row['order_type']),
            side=OrderSide(row['side']),
            quantity=row['quantity'],
            price=row['price'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            status=OrderStatus(row['status']),
            filled_quantity=row['filled_quantity'],
            remaining_quantity=row['remaining_quantity'],
            stop_price=row['stop_price'],
            limit_price=row['limit_price']
        )
