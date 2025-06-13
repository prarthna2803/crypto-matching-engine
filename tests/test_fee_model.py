import pytest
from datetime import datetime

from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.models.fee import FeeModel, FeeSchedule
from app.core.matching_engine import MatchingEngine


def test_fee_model_initialization():
    """Test fee model initialization."""
    fee_model = FeeModel()
    
    # Check default rates
    assert fee_model.default_maker_rate == 0.001  # 0.1%
    assert fee_model.default_taker_rate == 0.002  # 0.2%
    
    # Check fee schedule creation
    fee_schedule = fee_model.get_fee_schedule("BTC-USDT")
    assert fee_schedule.symbol == "BTC-USDT"
    assert fee_schedule.maker_rate == 0.001
    assert fee_schedule.taker_rate == 0.002


def test_fee_calculation():
    """Test fee calculation."""
    fee_model = FeeModel()
    
    # Set custom fee schedule
    fee_model.set_fee_schedule("BTC-USDT", 0.002, 0.003)
    
    # Calculate fees
    maker_fee, taker_fee = fee_model.calculate_fees("BTC-USDT", 10000.0)
    
    # Check fee calculation
    assert maker_fee == 20.0  # 0.2% of 10000
    assert taker_fee == 30.0  # 0.3% of 10000


def test_fee_calculation_in_trades():
    """Test fee calculation in trades."""
    engine = MatchingEngine()
    
    # Set custom fee schedule
    engine.set_fee_schedule("BTC-USDT", 0.002, 0.003)
    
    # Add a limit sell order
    sell_order = Order(
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
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
    
    # Check fee calculation in the trade
    trade = trades[0]
    assert trade.price == 50000.0
    assert trade.quantity == 1.0
    assert trade.maker_fee_rate == 0.002
    assert trade.taker_fee_rate == 0.003
    assert trade.maker_fee == 100.0  # 0.2% of 50000
    assert trade.taker_fee == 150.0  # 0.3% of 50000


def test_default_fee_rates():
    """Test setting default fee rates."""
    engine = MatchingEngine()
    
    # Set default fee rates
    engine.set_default_fee_rates(0.003, 0.004)
    
    # Add a limit sell order for a new symbol
    sell_order = Order(
        symbol="ETH-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=1.0,
        price=3000.0
    )
    engine.process_order(sell_order)
    
    # Add a market buy order to generate a trade
    buy_order = Order(
        symbol="ETH-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=1.0
    )
    trades, _ = engine.process_order(buy_order)
    
    # Check that a trade was executed
    assert len(trades) == 1
    
    # Check fee calculation in the trade
    trade = trades[0]
    assert trade.price == 3000.0
    assert trade.quantity == 1.0
    assert trade.maker_fee_rate == 0.003
    assert trade.taker_fee_rate == 0.004
    assert trade.maker_fee == 9.0   # 0.3% of 3000
    assert trade.taker_fee == 12.0  # 0.4% of 3000
