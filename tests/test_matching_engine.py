import pytest
from datetime import datetime

from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.core.matching_engine import MatchingEngine


def test_process_order():
    """Test processing an order through the matching engine."""
    engine = MatchingEngine()
    
    # Create a limit sell order
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50000.0
    )
    
    # Process the order
    trades, updated_sell_order = engine.process_order(sell_order)
    
    # Check that no trades were executed
    assert len(trades) == 0
    
    # Check that the order was added to the book
    assert updated_sell_order.status == OrderStatus.OPEN
    assert updated_sell_order.remaining_quantity == 1.0
    
    # Create a market buy order
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=0.5
    )
    
    # Process the order
    trades, updated_buy_order = engine.process_order(buy_order)
    
    # Check that a trade was executed
    assert len(trades) == 1
    assert trades[0].price == 50000.0
    assert trades[0].quantity == 0.5
    assert trades[0].aggressor_side == "buy"
    
    # Check that the buy order was filled
    assert updated_buy_order.status == OrderStatus.FILLED
    assert updated_buy_order.filled_quantity == 0.5
    assert updated_buy_order.remaining_quantity == 0
    
    # Check that the sell order was partially filled
    updated_sell_order = engine.get_order(sell_order.order_id)
    assert updated_sell_order is not None
    assert updated_sell_order.status == OrderStatus.PARTIALLY_FILLED
    assert updated_sell_order.filled_quantity == 0.5
    assert updated_sell_order.remaining_quantity == 0.5


def test_cancel_order():
    """Test canceling an order through the matching engine."""
    engine = MatchingEngine()
    
    # Create a limit buy order
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    
    # Process the order
    engine.process_order(buy_order)
    
    # Cancel the order
    canceled_order = engine.cancel_order(buy_order.order_id)
    
    # Check that the order was canceled
    assert canceled_order is not None
    assert canceled_order.status == OrderStatus.CANCELED
    
    # Check that the order is no longer active
    assert engine.get_order(buy_order.order_id).status == OrderStatus.CANCELED


def test_get_bbo():
    """Test getting the BBO through the matching engine."""
    engine = MatchingEngine()
    
    # Initially, there should be no BBO
    bbo = engine.get_bbo("BTC-USDT")
    assert bbo is None
    
    # Add a limit buy order
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    engine.process_order(buy_order)
    
    # Check the BBO
    bbo = engine.get_bbo("BTC-USDT")
    assert bbo is not None
    assert bbo.bid_price == 50000.0
    assert bbo.bid_quantity == 1.0
    assert bbo.ask_price is None
    assert bbo.ask_quantity is None
    
    # Add a limit sell order
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=2.0,
        price=50100.0
    )
    engine.process_order(sell_order)
    
    # Check the updated BBO
    bbo = engine.get_bbo("BTC-USDT")
    assert bbo is not None
    assert bbo.bid_price == 50000.0
    assert bbo.bid_quantity == 1.0
    assert bbo.ask_price == 50100.0
    assert bbo.ask_quantity == 2.0


def test_get_order_book_snapshot():
    """Test getting an order book snapshot through the matching engine."""
    engine = MatchingEngine()
    
    # Add some orders
    buy_order1 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    engine.process_order(buy_order1)
    
    buy_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=2.0,
        price=49900.0
    )
    engine.process_order(buy_order2)
    
    sell_order1 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.5,
        price=50100.0
    )
    engine.process_order(sell_order1)
    
    sell_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=2.5,
        price=50200.0
    )
    engine.process_order(sell_order2)
    
    # Get the order book snapshot
    snapshot = engine.get_order_book_snapshot("BTC-USDT")
    
    # Check the bids
    assert len(snapshot.bids) == 2
    assert snapshot.bids[0][0] == 50000.0  # Price
    assert snapshot.bids[0][1] == 1.0      # Quantity
    assert snapshot.bids[1][0] == 49900.0  # Price
    assert snapshot.bids[1][1] == 2.0      # Quantity
    
    # Check the asks
    assert len(snapshot.asks) == 2
    assert snapshot.asks[0][0] == 50100.0  # Price
    assert snapshot.asks[0][1] == 1.5      # Quantity
    assert snapshot.asks[1][0] == 50200.0  # Price
    assert snapshot.asks[1][1] == 2.5      # Quantity


def test_get_recent_trades():
    """Test getting recent trades through the matching engine."""
    engine = MatchingEngine()
    
    # Add a limit sell order
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=2.0,
        price=50000.0
    )
    engine.process_order(sell_order)
    
    # Add a market buy order to generate a trade
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=1.0
    )
    trades, _ = engine.process_order(buy_order)
    
    # Check that a trade was executed
    assert len(trades) == 1
    
    # Get recent trades
    recent_trades = engine.get_recent_trades("BTC-USDT")
    
    # Check that the trade is in the list
    assert len(recent_trades) == 1
    assert recent_trades[0].symbol == "BTC-USDT"
    assert recent_trades[0].price == 50000.0
    assert recent_trades[0].quantity == 1.0
    assert recent_trades[0].aggressor_side == "buy"
    assert recent_trades[0].maker_order_id == sell_order.order_id
    assert recent_trades[0].taker_order_id == buy_order.order_id
