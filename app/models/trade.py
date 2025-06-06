from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class Trade(BaseModel):
    """Model representing a trade execution."""
    trade_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    symbol: str
    price: float
    quantity: float
    aggressor_side: str  # "buy" or "sell"
    maker_order_id: str
    taker_order_id: str
    maker_fee: float = 0.0  # Fee paid by the maker
    taker_fee: float = 0.0  # Fee paid by the taker
    maker_fee_rate: float = 0.0  # Fee rate applied to maker
    taker_fee_rate: float = 0.0  # Fee rate applied to taker
