from datetime import datetime
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field


class BBO(BaseModel):
    """Best Bid and Offer model."""
    symbol: str
    bid_price: Optional[float] = None
    bid_quantity: Optional[float] = None
    ask_price: Optional[float] = None
    ask_quantity: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrderBookUpdate(BaseModel):
    """Order book update model for L2 data."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    symbol: str
    asks: List[Tuple[float, float]] = []  # List of [price, quantity] pairs
    bids: List[Tuple[float, float]] = []  # List of [price, quantity] pairs
