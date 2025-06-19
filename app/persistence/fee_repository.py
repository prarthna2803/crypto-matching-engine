"""
Repository for fee schedule persistence operations.
"""
import sqlite3
import logging
from typing import List, Optional, Dict, Any, Tuple

from app.models.fee import FeeSchedule
from app.persistence.database import Database

# Configure logging
logger = logging.getLogger(__name__)

class FeeRepository:
    """Repository for fee schedule persistence operations."""
    
    def __init__(self, database: Database):
        """Initialize with database connection."""
        self.db = database
    
    def save_fee_schedule(self, fee_schedule: FeeSchedule) -> None:
        """Save a fee schedule to the database."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO fee_schedules (
                symbol, maker_rate, taker_rate
            ) VALUES (?, ?, ?)
            ''', (
                fee_schedule.symbol,
                fee_schedule.maker_rate,
                fee_schedule.taker_rate
            ))
            
            conn.commit()
            logger.debug(f"Fee schedule saved for symbol: {fee_schedule.symbol}")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error saving fee schedule for {fee_schedule.symbol}: {e}")
            raise
    
    def get_fee_schedule(self, symbol: str) -> Optional[FeeSchedule]:
        """Get a fee schedule by symbol."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM fee_schedules WHERE symbol = ?', (symbol,))
            row = cursor.fetchone()
            
            if row:
                return FeeSchedule(
                    symbol=row['symbol'],
                    maker_rate=row['maker_rate'],
                    taker_rate=row['taker_rate']
                )
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting fee schedule for {symbol}: {e}")
            raise
    
    def get_all_fee_schedules(self) -> List[FeeSchedule]:
        """Get all fee schedules."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM fee_schedules')
            rows = cursor.fetchall()
            
            return [
                FeeSchedule(
                    symbol=row['symbol'],
                    maker_rate=row['maker_rate'],
                    taker_rate=row['taker_rate']
                )
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"Error getting all fee schedules: {e}")
            raise
    
    def save_default_fee_rates(self, maker_rate: float, taker_rate: float) -> None:
        """Save default fee rates."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            UPDATE default_fee_rates
            SET maker_rate = ?, taker_rate = ?
            WHERE id = 1
            ''', (maker_rate, taker_rate))
            
            conn.commit()
            logger.debug(f"Default fee rates saved: maker={maker_rate}, taker={taker_rate}")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error saving default fee rates: {e}")
            raise
    
    def get_default_fee_rates(self) -> Tuple[float, float]:
        """Get default fee rates."""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT maker_rate, taker_rate FROM default_fee_rates WHERE id = 1')
            row = cursor.fetchone()
            
            if row:
                return row['maker_rate'], row['taker_rate']
            return 0.001, 0.002  # Default values if not found
        except sqlite3.Error as e:
            logger.error(f"Error getting default fee rates: {e}")
            raise
