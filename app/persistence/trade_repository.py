"""
Repository for trade persistence operations.
"""
import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.trade import Trade
from app.persistence.database import Database

# Configure logging
logger = logging.getLogger(__name__)

class TradeRepository:
    """Repository for trade persistence operations."""
    
    def __init__(self, database: Database):
        """Initialize with database connection."""
        self.db = database
    
    def save_trade(self, trade: Trade) -> None:
        """Save a trade to the database."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO trades (
                trade_id, symbol, price, quantity, timestamp, aggressor_side,
                maker_order_id, taker_order_id, maker_fee, taker_fee,
                maker_fee_rate, taker_fee_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.trade_id,
                trade.symbol,
                trade.price,
                trade.quantity,
                trade.timestamp.isoformat(),
                trade.aggressor_side,
                trade.maker_order_id,
                trade.taker_order_id,
                trade.maker_fee,
                trade.taker_fee,
                trade.maker_fee_rate,
                trade.taker_fee_rate
            ))
            
            conn.commit()
            logger.debug(f"Trade saved: {trade.trade_id}")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error saving trade {trade.trade_id}: {e}")
            raise
    
    def save_trades(self, trades: List[Trade]) -> None:
        """Save multiple trades to the database."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            for trade in trades:
                cursor.execute('''
                INSERT OR REPLACE INTO trades (
                    trade_id, symbol, price, quantity, timestamp, aggressor_side,
                    maker_order_id, taker_order_id, maker_fee, taker_fee,
                    maker_fee_rate, taker_fee_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade.trade_id,
                    trade.symbol,
                    trade.price,
                    trade.quantity,
                    trade.timestamp.isoformat(),
                    trade.aggressor_side,
                    trade.maker_order_id,
                    trade.taker_order_id,
                    trade.maker_fee,
                    trade.taker_fee,
                    trade.maker_fee_rate,
                    trade.taker_fee_rate
                ))
            
            conn.commit()
            logger.debug(f"Saved {len(trades)} trades")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error saving trades: {e}")
            raise
    
    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get a trade by ID."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM trades WHERE trade_id = ?', (trade_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_trade(row)
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting trade {trade_id}: {e}")
            raise
    
    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades for a symbol."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT * FROM trades 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            ''', (symbol, limit))
            rows = cursor.fetchall()
            
            return [self._row_to_trade(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting trades for symbol {symbol}: {e}")
            raise
    
    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Convert a database row to a Trade object."""
        return Trade(
            trade_id=row['trade_id'],
            symbol=row['symbol'],
            price=row['price'],
            quantity=row['quantity'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            aggressor_side=row['aggressor_side'],
            maker_order_id=row['maker_order_id'],
            taker_order_id=row['taker_order_id'],
            maker_fee=row['maker_fee'],
            taker_fee=row['taker_fee'],
            maker_fee_rate=row['maker_fee_rate'],
            taker_fee_rate=row['taker_fee_rate']
        )
