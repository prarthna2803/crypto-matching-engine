"""
Database module for the cryptocurrency matching engine.
Provides SQLite database connection and schema setup.
"""
import os
import sqlite3
import logging
from typing import Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Database:
    """SQLite database connection manager."""
    
    def __init__(self, db_path: str = "trading_app.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.create_tables()
        
    def connect(self) -> sqlite3.Connection:
        """Connect to the SQLite database."""
        if self.conn is None:
            try:
                self.conn = sqlite3.connect(self.db_path)
                self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                logger.info(f"Connected to database: {self.db_path}")
            except sqlite3.Error as e:
                logger.error(f"Error connecting to database: {e}")
                raise
        return self.conn
    
    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")
    
    def create_tables(self) -> None:
        """Create database tables if they don't exist."""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Create orders table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            order_type TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL,
            stop_price REAL,
            limit_price REAL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            filled_quantity REAL NOT NULL,
            remaining_quantity REAL NOT NULL
        )
        ''')
        
        # Create trades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            quantity REAL NOT NULL,
            timestamp TEXT NOT NULL,
            aggressor_side TEXT NOT NULL,
            maker_order_id TEXT NOT NULL,
            taker_order_id TEXT NOT NULL,
            maker_fee REAL NOT NULL,
            taker_fee REAL NOT NULL,
            maker_fee_rate REAL NOT NULL,
            taker_fee_rate REAL NOT NULL,
            FOREIGN KEY (maker_order_id) REFERENCES orders (order_id),
            FOREIGN KEY (taker_order_id) REFERENCES orders (order_id)
        )
        ''')
        
        # Create fee_schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fee_schedules (
            symbol TEXT PRIMARY KEY,
            maker_rate REAL NOT NULL,
            taker_rate REAL NOT NULL
        )
        ''')
        
        # Create default_fee_rates table (single row table)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS default_fee_rates (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            maker_rate REAL NOT NULL,
            taker_rate REAL NOT NULL
        )
        ''')
        
        # Insert default fee rates if not exists
        cursor.execute('''
        INSERT OR IGNORE INTO default_fee_rates (id, maker_rate, taker_rate)
        VALUES (1, 0.001, 0.002)
        ''')
        
        conn.commit()
        logger.info("Database tables created")
