from fastapi import FastAPI, HTTPException, Depends
from typing import List, Dict, Any, Optional

from app.core.matching_engine import MatchingEngine
from app.models.order import Order, OrderSubmission, OrderResponse, OrderType, OrderSide
from app.models.trade import Trade
from app.models.market_data import BBO, OrderBookUpdate

# Create FastAPI app
app = FastAPI(
    title="Cryptocurrency Matching Engine API",
    description="RESTful API for a high-performance cryptocurrency matching engine",
    version="1.0.0"
)

# Create matching engine instance
matching_engine = MatchingEngine()


# Dependency to get the matching engine
def get_matching_engine():
    return matching_engine


@app.post("/orders", response_model=OrderResponse)
async def create_order(
    order_submission: OrderSubmission,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Submit a new order to the matching engine.
    """
    # Validate price for limit orders
    if order_submission.order_type in [OrderType.LIMIT, OrderType.IOC, OrderType.FOK] and order_submission.price is None:
        raise HTTPException(status_code=400, detail="Price is required for limit orders")
    
    # Validate stop price for stop orders
    if order_submission.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT] and order_submission.stop_price is None:
        raise HTTPException(status_code=400, detail="Stop price is required for stop orders")
    
    # Validate limit price for stop-limit orders
    if order_submission.order_type == OrderType.STOP_LIMIT and order_submission.limit_price is None:
        raise HTTPException(status_code=400, detail="Limit price is required for stop-limit orders")
    
    # Create order object
    order = Order(
        symbol=order_submission.symbol,
        order_type=order_submission.order_type,
        side=order_submission.side,
        quantity=order_submission.quantity,
        price=order_submission.price,
        stop_price=order_submission.stop_price,
        limit_price=order_submission.limit_price
    )
    
    # Process the order
    trades, updated_order = engine.process_order(order)
    
    # Create response
    if updated_order.status == "rejected":
        return OrderResponse(
            order_id=updated_order.order_id,
            status="rejected",
            message="Order validation failed"
        )
    
    # Return success response
    message = f"Order processed successfully. Filled: {updated_order.filled_quantity}, Remaining: {updated_order.remaining_quantity}"
    if updated_order.status == "pending_trigger":
        message = f"Stop order accepted and waiting for trigger price: {updated_order.stop_price}"
    
    return OrderResponse(
        order_id=updated_order.order_id,
        status=updated_order.status,
        message=message
    )


@app.delete("/orders/{order_id}", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Cancel an existing order.
    """
    canceled_order = engine.cancel_order(order_id)
    
    if not canceled_order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return OrderResponse(
        order_id=canceled_order.order_id,
        status=canceled_order.status,
        message="Order canceled successfully"
    )


@app.get("/orders/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Get details of an existing order.
    """
    order = engine.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order


@app.get("/market-data/{symbol}/bbo", response_model=BBO)
async def get_bbo(
    symbol: str,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Get the current Best Bid and Offer (BBO) for a symbol.
    """
    bbo = engine.get_bbo(symbol)
    
    if not bbo:
        # If no BBO exists, create an empty one
        bbo = BBO(symbol=symbol)
    
    return bbo


@app.get("/market-data/{symbol}/order-book", response_model=OrderBookUpdate)
async def get_order_book(
    symbol: str,
    depth: int = 10,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Get the current order book for a symbol.
    """
    order_book = engine.get_order_book_snapshot(symbol, depth)
    
    if not order_book:
        # If no order book exists, create an empty one
        order_book = OrderBookUpdate(symbol=symbol)
    
    return order_book


@app.get("/market-data/{symbol}/trades", response_model=List[Trade])
async def get_trades(
    symbol: str,
    limit: int = 100,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Get recent trades for a symbol.
    """
    trades = engine.get_recent_trades(symbol, limit)
    return trades
@app.get("/fee-schedules/{symbol}", response_model=Dict[str, Any])
async def get_fee_schedule(
    symbol: str,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Get the fee schedule for a symbol.
    """
    return engine.get_fee_schedule(symbol)


@app.post("/fee-schedules/{symbol}", response_model=Dict[str, Any])
async def set_fee_schedule(
    symbol: str,
    maker_rate: float,
    taker_rate: float,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Set a custom fee schedule for a symbol.
    """
    if maker_rate < 0 or taker_rate < 0:
        raise HTTPException(status_code=400, detail="Fee rates cannot be negative")
    
    engine.set_fee_schedule(symbol, maker_rate, taker_rate)
    return engine.get_fee_schedule(symbol)


@app.post("/fee-schedules/default", response_model=Dict[str, Any])
async def set_default_fee_rates(
    maker_rate: float,
    taker_rate: float,
    engine: MatchingEngine = Depends(get_matching_engine)
):
    """
    Set the default fee rates.
    """
    if maker_rate < 0 or taker_rate < 0:
        raise HTTPException(status_code=400, detail="Fee rates cannot be negative")
    
    engine.set_default_fee_rates(maker_rate, taker_rate)
    return {"maker_rate": maker_rate, "taker_rate": taker_rate}
