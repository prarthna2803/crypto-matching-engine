import pytest
from datetime import datetime

from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.core.matching_engine import MatchingEngine


def test_stop_loss_order():
    """Test stop-loss order behavior."""
    engine = MatchingEngine()
    
    # Add a limit buy order to create some liquidity
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    engine.process_order(buy_order)
    
    # Create a stop-loss sell order
    stop_loss_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=0.5,
        stop_price=49000.0  # Trigger when price falls to or below 49000
    )
    
    # Process the stop-loss order
    trades, updated_order = engine.process_order(stop_loss_order)
    
    # Check that the order is pending trigger
    assert updated_order.status == OrderStatus.PENDING_TRIGGER
    assert len(trades) == 0
    
    # Create a market sell order to drive the price down
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.SELL,
        quantity=1.0
    )
    
    # Process the market sell order
    trades, _ = engine.process_order(sell_order)
    
    # Check that a trade was executed at 50000
    assert len(trades) == 1
    assert trades[0].price == 50000.0
    
    # The stop-loss order should still be pending as the price hasn't gone below the trigger
    stop_loss_order_updated = engine.get_order(stop_loss_order.order_id)
    assert stop_loss_order_updated.status == OrderStatus.PENDING_TRIGGER
    
    # Add another limit buy order at a lower price
    buy_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=48000.0
    )
    engine.process_order(buy_order2)
    
    # Create another market sell order to drive the price below the stop price
    sell_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.SELL,
        quantity=0.5
    )
    
    # Process the market sell order
    trades, _ = engine.process_order(sell_order2)
    
    # Check that a trade was executed at 48000
    assert len(trades) == 1
    assert trades[0].price == 48000.0
    
    # The stop-loss order should now be triggered and executed
    stop_loss_order_final = engine.get_order(stop_loss_order.order_id)
    assert stop_loss_order_final.status == OrderStatus.FILLED
    assert stop_loss_order_final.filled_quantity == 0.5


def test_stop_limit_order():
    """Test stop-limit order behavior."""
    engine = MatchingEngine()
    
    # Add a limit buy order to create some liquidity
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=1.0,
        price=50000.0
    )
    engine.process_order(buy_order)
    
    # Create a stop-limit buy order
    stop_limit_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.STOP_LIMIT,
        side=OrderSide.BUY,
        quantity=0.5,
        stop_price=51000.0,  # Trigger when price rises to or above 51000
        limit_price=51500.0   # But don't buy above 51500
    )
    
    # Process the stop-limit order
    trades, updated_order = engine.process_order(stop_limit_order)
    
    # Check that the order is pending trigger
    assert updated_order.status == OrderStatus.PENDING_TRIGGER
    assert len(trades) == 0
    
    # Create a limit sell order at a higher price
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=51200.0
    )
    
    # Process the limit sell order
    engine.process_order(sell_order)
    
    # Create a market buy order to drive the price up
    buy_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=0.5
    )
    
    # Process the market buy order
    trades, _ = engine.process_order(buy_order2)
    
    # Check that a trade was executed at 51200
    assert len(trades) == 1
    assert trades[0].price == 51200.0
    
    # The stop-limit order should now be triggered and converted to a limit order
    stop_limit_order_final = engine.get_order(stop_limit_order.order_id)
    
    # It should be filled against the remaining sell order
    assert stop_limit_order_final.status == OrderStatus.FILLED
    assert stop_limit_order_final.filled_quantity == 0.5
    assert stop_limit_order_final.price == 51500.0  # The limit price


def test_take_profit_order():
    """Test take-profit order behavior."""
    engine = MatchingEngine()
    
    # Add a limit sell order to create some liquidity
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=50000.0
    )
    engine.process_order(sell_order)
    
    # Create a take-profit buy order
    take_profit_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.TAKE_PROFIT,
        side=OrderSide.BUY,
        quantity=0.5,
        stop_price=49000.0  # Trigger when price falls to or below 49000
    )
    
    # Process the take-profit order
    trades, updated_order = engine.process_order(take_profit_order)
    
    # Check that the order is pending trigger
    assert updated_order.status == OrderStatus.PENDING_TRIGGER
    assert len(trades) == 0
    
    # Create a limit sell order at a lower price
    sell_order2 = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=48000.0
    )
    
    # Process the limit sell order
    engine.process_order(sell_order2)
    
    # Create a market buy order to match against the lower sell order
    buy_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=0.5
    )
    
    # Process the market buy order
    trades, _ = engine.process_order(buy_order)
    
    # Check that a trade was executed at 48000
    assert len(trades) == 1
    assert trades[0].price == 48000.0
    
    # The take-profit order should now be triggered and executed
    take_profit_order_final = engine.get_order(take_profit_order.order_id)
    assert take_profit_order_final.status == OrderStatus.FILLED
    assert take_profit_order_final.filled_quantity == 0.5


def test_cancel_pending_trigger_order():
    """Test canceling a pending trigger order."""
    engine = MatchingEngine()
    
    # Create a stop-loss order
    stop_loss_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=1.0,
        stop_price=49000.0
    )
    
    # Process the stop-loss order
    engine.process_order(stop_loss_order)
    
    # Check that the order is pending trigger
    order = engine.get_order(stop_loss_order.order_id)
    assert order.status == OrderStatus.PENDING_TRIGGER
    
    # Cancel the order
    canceled_order = engine.cancel_order(stop_loss_order.order_id)
    
    # Check that the order was canceled
    assert canceled_order is not None
    assert canceled_order.status == OrderStatus.CANCELED
    
    # Check that the order is no longer in the pending trigger orders
    assert stop_loss_order.order_id not in [o.order_id for o in engine.pending_trigger_orders.get("BTC-USDT", [])]
