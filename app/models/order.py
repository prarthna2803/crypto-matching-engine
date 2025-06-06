from enum import Enum
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"  
    FOK = "fok"  
    STOP_LOSS = "stop_loss"  
    STOP_LIMIT = "stop_limit"  
    TAKE_PROFIT = "take_profit" 


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    PENDING_TRIGGER = "pending_trigger"  # for stop/take-profit orders waiting for trigger


class Order(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: float
    price: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: OrderStatus = OrderStatus.OPEN
    filled_quantity: float = 0
    remaining_quantity: float = None
    stop_price: Optional[float] = None  # truigger price for stop orders
    limit_price: Optional[float] = None  # limkit price for stop-limit orders

    def __init__(self, **data):
        super().__init__(**data)
        if self.remaining_quantity is None:
            self.remaining_quantity = self.quantity
            
        # setting initial status for stop and take-profit orders
        if self.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT]:
            self.status = OrderStatus.PENDING_TRIGGER

    def is_marketable(self, best_price: float) -> bool:
        """Check if the order is marketable against the given best price."""
        if self.order_type == OrderType.MARKET:
            return True
        if self.side == OrderSide.BUY:
            return self.price >= best_price if best_price else False
        else:  # SELL
            return self.price <= best_price if best_price else False

    def update_on_fill(self, fill_qty: float) -> None:
        """Update order after a fill."""
        self.filled_quantity += fill_qty
        self.remaining_quantity -= fill_qty
        
        if self.remaining_quantity <= 0:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
            
    def is_triggered(self, last_price: float) -> bool:
        """
        Check if a stop or take-profit order is triggered by the last trade price.
        
        For stop orders:
        - Buy stop: Triggers when price rises to or above stop price
        - Sell stop: Triggers when price falls to or below stop price
        
        For take-profit orders:
        - Buy take-profit: Triggers when price falls to or below take-profit price
        - Sell take-profit: Triggers when price rises to or above take-profit price
        """
        if self.status != OrderStatus.PENDING_TRIGGER:
            return False
            
        if self.order_type == OrderType.STOP_LOSS or self.order_type == OrderType.STOP_LIMIT:
            if self.side == OrderSide.BUY:
                return last_price >= self.stop_price
            else:  # SELL
                return last_price <= self.stop_price
                
        elif self.order_type == OrderType.TAKE_PROFIT:
            if self.side == OrderSide.BUY:
                return last_price <= self.stop_price  # f0r buy, take profit when price falls
            else:  # SELL
                return last_price >= self.stop_price  # for sell, take profit when price rises
                
        return False


class OrderBookEntry(BaseModel):
    """Represents an entry in the order book."""
    price: float
    orders: List[Order] = Field(default_factory=list)
    total_quantity: float = 0

    def add_order(self, order: Order) -> None:
        """Add an order to this price level."""
        self.orders.append(order)
        self.total_quantity += order.remaining_quantity

    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove an order from this price level."""
        for i, order in enumerate(self.orders):
            if order.order_id == order_id:
                removed_order = self.orders.pop(i)
                self.total_quantity -= removed_order.remaining_quantity
                return removed_order
        return None

    def update_quantity(self) -> None:
        """Recalculate the total quantity at this price level."""
        self.total_quantity = sum(order.remaining_quantity for order in self.orders)


class OrderSubmission(BaseModel):
    """Model for order submission API."""
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None  #
    limit_price: Optional[float] = None  


class OrderResponse(BaseModel):
    """Response model for order submission."""
    order_id: str
    status: str
    message: str = ""
