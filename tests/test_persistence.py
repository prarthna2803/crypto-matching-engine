"""
Tests for the persistence layer.
"""
import os
import pytest
from datetime import datetime

from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.models.trade import Trade
from app.models.fee import FeeSchedule
from app.core.matching_engine import MatchingEngine
from app.persistence.database import Database
from app.persistence.order_repository import OrderRepository
from app.persistence.trade_repository import TradeRepository
from app.persistence.fee_repository import FeeRepository
from app.persistence.persistence_manager import PersistenceManager


@pytest.fixture
def test_db_path():
    """Fixture for test database path."""
    db_path = "test_trading_app.db"
    # Clean up any existing test database
    if os.path.exists(db_path):
        os.remove(db_path)
    yield db_path
    # Clean up after tests
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def database(test_db_path):
    """Fixture for database."""
    db = Database(test_db_path)
    yield db
    db.close()


@pytest.fixture
def order_repository(database):
    """Fixture for order repository."""
    return OrderRepository(database)


@pytest.fixture
def trade_repository(database):
    """Fixture for trade repository."""
    return TradeRepository(database)


@pytest.fixture
def fee_repository(database):
    """Fixture for fee repository."""
    return FeeRepository(database)


@pytest.fixture
def persistence_manager(test_db_path):
    """Fixture for persistence manager."""
    pm = PersistenceManager(test_db_path)
    yield pm
    pm.close()


def test_order_repository(order_repository):
    """Test order repository operations."""
    # Create a test order
    order = Order(
        order_id="test-order-1",
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    
    # Save the order
    order_repository.save_order(order)
    
    # Retrieve the order
    retrieved_order = order_repository.get_order("test-order-1")
    
    # Check that the retrieved order matches the original
    assert retrieved_order is not None
    assert retrieved_order.order_id == order.order_id
    assert retrieved_order.symbol == order.symbol
    assert retrieved_order.order_type == order.order_type
    assert retrieved_order.side == order.side
    assert retrieved_order.quantity == order.quantity
    assert retrieved_order.price == order.price
    assert retrieved_order.status == order.status
    
    # Update the order
    order.status = OrderStatus.PARTIALLY_FILLED
    order.filled_quantity = 0.5
    order.remaining_quantity = 0.5
    order_repository.save_order(order)
    
    # Retrieve the updated order
    updated_order = order_repository.get_order("test-order-1")
    assert updated_order.status == OrderStatus.PARTIALLY_FILLED
    assert updated_order.filled_quantity == 0.5
    assert updated_order.remaining_quantity == 0.5
    
    # Test get_orders_by_symbol
    orders = order_repository.get_orders_by_symbol("BTC-USDT")
    assert len(orders) == 1
    assert orders[0].order_id == "test-order-1"
    
    # Test get_open_orders_by_symbol
    open_orders = order_repository.get_open_orders_by_symbol("BTC-USDT")
    assert len(open_orders) == 1
    assert open_orders[0].order_id == "test-order-1"
    
    # Test delete_order
    order_repository.delete_order("test-order-1")
    assert order_repository.get_order("test-order-1") is None


def test_trade_repository(trade_repository):
    """Test trade repository operations."""
    # Create a test trade
    trade = Trade(
        trade_id="test-trade-1",
        symbol="BTC-USDT",
        price=50000.0,
        quantity=1.0,
        timestamp=datetime.utcnow(),
        aggressor_side="buy",
        maker_order_id="maker-order-1",
        taker_order_id="taker-order-1",
        maker_fee=50.0,
        taker_fee=100.0,
        maker_fee_rate=0.001,
        taker_fee_rate=0.002
    )
    
    # Save the trade
    trade_repository.save_trade(trade)
    
    # Retrieve the trade
    retrieved_trade = trade_repository.get_trade("test-trade-1")
    
    # Check that the retrieved trade matches the original
    assert retrieved_trade is not None
    assert retrieved_trade.trade_id == trade.trade_id
    assert retrieved_trade.symbol == trade.symbol
    assert retrieved_trade.price == trade.price
    assert retrieved_trade.quantity == trade.quantity
    assert retrieved_trade.aggressor_side == trade.aggressor_side
    assert retrieved_trade.maker_order_id == trade.maker_order_id
    assert retrieved_trade.taker_order_id == trade.taker_order_id
    assert retrieved_trade.maker_fee == trade.maker_fee
    assert retrieved_trade.taker_fee == trade.taker_fee
    assert retrieved_trade.maker_fee_rate == trade.maker_fee_rate
    assert retrieved_trade.taker_fee_rate == trade.taker_fee_rate
    
    # Test get_trades_by_symbol
    trades = trade_repository.get_trades_by_symbol("BTC-USDT")
    assert len(trades) == 1
    assert trades[0].trade_id == "test-trade-1"


def test_fee_repository(fee_repository):
    """Test fee repository operations."""
    # Create a test fee schedule
    fee_schedule = FeeSchedule(
        symbol="BTC-USDT",
        maker_rate=0.0005,
        taker_rate=0.001
    )
    
    # Save the fee schedule
    fee_repository.save_fee_schedule(fee_schedule)
    
    # Retrieve the fee schedule
    retrieved_fee_schedule = fee_repository.get_fee_schedule("BTC-USDT")
    
    # Check that the retrieved fee schedule matches the original
    assert retrieved_fee_schedule is not None
    assert retrieved_fee_schedule.symbol == fee_schedule.symbol
    assert retrieved_fee_schedule.maker_rate == fee_schedule.maker_rate
    assert retrieved_fee_schedule.taker_rate == fee_schedule.taker_rate
    
    # Test get_all_fee_schedules
    fee_schedules = fee_repository.get_all_fee_schedules()
    assert len(fee_schedules) == 1
    assert fee_schedules[0].symbol == "BTC-USDT"
    
    # Test save_default_fee_rates
    fee_repository.save_default_fee_rates(0.0003, 0.0006)
    
    # Test get_default_fee_rates
    maker_rate, taker_rate = fee_repository.get_default_fee_rates()
    assert maker_rate == 0.0003
    assert taker_rate == 0.0006


def test_persistence_manager(persistence_manager):
    """Test persistence manager operations."""
    # Create a matching engine
    engine = MatchingEngine()
    engine.persistence_manager = persistence_manager
    
    # Set custom fee schedule
    engine.set_fee_schedule("BTC-USDT", 0.0005, 0.001)
    
    # Add some orders
    buy_order = Order(
        order_id="test-buy-order",
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    engine.process_order(buy_order)
    
    sell_order = Order(
        order_id="test-sell-order",
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=0.5,
        price=50100.0
    )
    engine.process_order(sell_order)
    
    stop_order = Order(
        order_id="test-stop-order",
        symbol="BTC-USDT",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=0.5,
        stop_price=49000.0
    )
    engine.process_order(stop_order)
    
    # Save the engine state
    persistence_manager.save_engine_state(engine)
    
    # Create a new engine
    new_engine = MatchingEngine()
    new_engine.persistence_manager = persistence_manager
    
    # Load the engine state
    persistence_manager.load_engine_state(new_engine)
    
    # Check that the state was loaded correctly
    assert "BTC-USDT" in new_engine.order_books
    assert "test-buy-order" in new_engine.all_orders
    assert "test-sell-order" in new_engine.all_orders
    assert "test-stop-order" in new_engine.all_orders
    
    # Check that the fee schedule was loaded correctly
    fee_schedule = new_engine.fee_model.get_fee_schedule("BTC-USDT")
    assert fee_schedule.maker_rate == 0.0005
    assert fee_schedule.taker_rate == 0.001
    
    # Check that the pending trigger orders were loaded correctly
    assert "BTC-USDT" in new_engine.pending_trigger_orders
    assert len(new_engine.pending_trigger_orders["BTC-USDT"]) == 1
    assert new_engine.pending_trigger_orders["BTC-USDT"][0].order_id == "test-stop-order"
    
    # Check that the order book was loaded correctly
    order_book = new_engine.order_books["BTC-USDT"]
    assert len(order_book.bids) == 1
    assert len(order_book.asks) == 1
    assert next(iter(order_book.bids)) == 50000.0
    assert next(iter(order_book.asks)) == 50100.0
