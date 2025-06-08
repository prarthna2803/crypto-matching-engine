import pytest
from datetime import datetime

from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.core.order_book import OrderBook


def test_add_limit_order():
    """Test adding a limit order to the order book."""
    order_book = OrderBook("BTC-USDT")
    
    # Create a limit buy order
    order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    
    # Add the order to the book
    trades, updated_order = order_book.add_order(order)
    
    # Check that no trades were executed
    assert len(trades) == 0
    
    # Check that the order was added to the book
    assert updated_order.status == OrderStatus.OPEN
    assert updated_order.remaining_quantity == 1.0
    
    # Check that the BBO was updated
    bbo = order_book.get_bbo()
    assert bbo.bid_price == 50000.0
    assert bbo.bid_quantity == 1.0
    assert bbo.ask_price is None
    assert bbo.ask_quantity is None


def test_matching_market_order():
    """Test matching a market order against the book."""
    order_book = OrderBook("BTC-USDT")
    
    # Add a limit sell order to the book
    limit_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50000.0
    )
    trades, _ = order_book.add_order(limit_order)
    assert len(trades) == 0
    
    # Create a market buy order
    market_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=0.5
    )
    
    # Add the market order to the book
    trades, updated_order = order_book.add_order(market_order)
    
    # Check that a trade was executed
    assert len(trades) == 1
    assert trades[0].price == 50000.0
    assert trades[0].quantity == 0.5
    assert trades[0].aggressor_side == "buy"
    
    # Check that the market order was filled
    assert updated_order.status == OrderStatus.FILLED
    assert updated_order.filled_quantity == 0.5
    assert updated_order.remaining_quantity == 0
    
    # Check that the limit order was partially filled
    limit_order_id = limit_order.order_id
    updated_limit_order = order_book.get_order(limit_order_id)
    assert updated_limit_order is not None
    assert updated_limit_order.status == OrderStatus.PARTIALLY_FILLED
    assert updated_limit_order.filled_quantity == 0.5
    assert updated_limit_order.remaining_quantity == 0.5
    
    # Check that the BBO was updated
    bbo = order_book.get_bbo()
    assert bbo.bid_price is None
    assert bbo.bid_quantity is None
    assert bbo.ask_price == 50000.0
    assert bbo.ask_quantity == 0.5


def test_price_time_priority():
    """Test that orders are matched according to price-time priority."""
    order_book = OrderBook("BTC-USDT")
    
    # Add three limit sell orders at different prices
    sell_order1 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50000.0
    )
    trades, _ = order_book.add_order(sell_order1)
    assert len(trades) == 0
    
    sell_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50100.0
    )
    trades, _ = order_book.add_order(sell_order2)
    assert len(trades) == 0
    
    sell_order3 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50000.0  # Same price as sell_order1
    )
    trades, _ = order_book.add_order(sell_order3)
    assert len(trades) == 0
    
    # Create a market buy order that will match against the sell orders
    market_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=2.5
    )
    
    # Add the market order to the book
    trades, updated_order = order_book.add_order(market_order)
    
    # Check that trades were executed in price-time priority
    assert len(trades) == 3
    
    # First trade should be against sell_order1 (best price, first in time)
    assert trades[0].price == 50000.0
    assert trades[0].quantity == 1.0
    assert trades[0].maker_order_id == sell_order1.order_id
    
    # Second trade should be against sell_order3 (same price, second in time)
    assert trades[1].price == 50000.0
    assert trades[1].quantity == 1.0
    assert trades[1].maker_order_id == sell_order3.order_id
    
    # Third trade should be against sell_order2 (worst price)
    assert trades[2].price == 50100.0
    assert trades[2].quantity == 0.5
    assert trades[2].maker_order_id == sell_order2.order_id
    
    # Check that the market order was filled
    assert updated_order.status == OrderStatus.FILLED
    assert updated_order.filled_quantity == 2.5
    assert updated_order.remaining_quantity == 0
    
    # Check that sell_order1 and sell_order3 were fully filled and removed from the book
    assert order_book.get_order(sell_order1.order_id) is None
    assert order_book.get_order(sell_order3.order_id) is None
    
    # Check that sell_order2 was partially filled
    updated_sell_order2 = order_book.get_order(sell_order2.order_id)
    assert updated_sell_order2 is not None
    assert updated_sell_order2.status == OrderStatus.PARTIALLY_FILLED
    assert updated_sell_order2.filled_quantity == 0.5
    assert updated_sell_order2.remaining_quantity == 0.5


def test_ioc_order():
    """Test Immediate-Or-Cancel (IOC) order behavior."""
    order_book = OrderBook("BTC-USDT")
    
    # Add a limit sell order to the book
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50000.0
    )
    order_book.add_order(sell_order)
    
    # Create an IOC buy order that will partially match
    ioc_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.IOC,
        side=OrderSide.BUY,
        quantity=2.0,
        price=50000.0
    )
    
    # Add the IOC order to the book
    trades, updated_order = order_book.add_order(ioc_order)
    
    # Check that a trade was executed for the available quantity
    assert len(trades) == 1
    assert trades[0].price == 50000.0
    assert trades[0].quantity == 1.0
    
    # Check that the IOC order was partially filled and the rest was canceled
    assert updated_order.status == OrderStatus.PARTIALLY_FILLED
    assert updated_order.filled_quantity == 1.0
    assert updated_order.remaining_quantity == 0  # Remaining quantity is canceled
    
    # Check that the IOC order is not in the book
    assert order_book.get_order(ioc_order.order_id) is None


def test_fok_order_success():
    """Test Fill-Or-Kill (FOK) order that can be fully filled."""
    order_book = OrderBook("BTC-USDT")
    
    # Add limit sell orders to the book
    sell_order1 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50000.0
    )
    order_book.add_order(sell_order1)
    
    sell_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50100.0
    )
    order_book.add_order(sell_order2)
    
    # Create a FOK buy order that can be fully filled
    fok_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.FOK,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50100.0
    )
    
    # Add the FOK order to the book
    trades, updated_order = order_book.add_order(fok_order)
    
    # Check that a trade was executed
    assert len(trades) == 1
    assert trades[0].price == 50000.0  # Should match at the best price
    assert trades[0].quantity == 1.0
    
    # Check that the FOK order was fully filled
    assert updated_order.status == OrderStatus.FILLED
    assert updated_order.filled_quantity == 1.0
    assert updated_order.remaining_quantity == 0


def test_fok_order_failure():
    """Test Fill-Or-Kill (FOK) order that cannot be fully filled."""
    order_book = OrderBook("BTC-USDT")
    
    # Add a limit sell order to the book
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=0.5,
        price=50000.0
    )
    order_book.add_order(sell_order)
    
    # Create a FOK buy order that cannot be fully filled
    fok_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.FOK,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    
    # Add the FOK order to the book
    trades, updated_order = order_book.add_order(fok_order)
    
    # Check that no trades were executed
    assert len(trades) == 0
    
    # Check that the FOK order was canceled
    assert updated_order.status == OrderStatus.CANCELED
    assert updated_order.filled_quantity == 0
    assert updated_order.remaining_quantity == 1.0
    
    # Check that the FOK order is not in the book
    assert order_book.get_order(fok_order.order_id) is None
    
    # Check that the sell order is still in the book unchanged
    updated_sell_order = order_book.get_order(sell_order.order_id)
    assert updated_sell_order is not None
    assert updated_sell_order.status == OrderStatus.OPEN
    assert updated_sell_order.filled_quantity == 0
    assert updated_sell_order.remaining_quantity == 0.5


def test_cancel_order():
    """Test canceling an order."""
    order_book = OrderBook("BTC-USDT")
    
    # Add a limit buy order to the book
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    order_book.add_order(buy_order)
    
    # Cancel the order
    canceled_order = order_book.cancel_order(buy_order.order_id)
    
    # Check that the order was canceled
    assert canceled_order is not None
    assert canceled_order.status == OrderStatus.CANCELED
    
    # Check that the order is no longer in the book
    assert order_book.get_order(buy_order.order_id) is None
    
    # Check that the BBO was updated
    bbo = order_book.get_bbo()
    assert bbo.bid_price is None
    assert bbo.bid_quantity is None
