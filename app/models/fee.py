from typing import Dict, Optional
from pydantic import BaseModel


class FeeSchedule(BaseModel):
    """Model representing a fee schedule for a trading pair."""
    symbol: str
    maker_rate: float  # Fee rate for makers (e.g., 0.001 for 0.1%)
    taker_rate: float  # Fee rate for takers (e.g., 0.002 for 0.2%)
    
    def calculate_maker_fee(self, trade_value: float) -> float:
        """Calculate the fee for a maker."""
        return trade_value * self.maker_rate
    
    def calculate_taker_fee(self, trade_value: float) -> float:
        """Calculate the fee for a taker."""
        return trade_value * self.taker_rate


class FeeModel:
    """
    Fee model for the trading system.
    Manages fee schedules for different trading pairs.
    """
    
    def __init__(self):
        # Default fee rates
        self.default_maker_rate = 0.001  # 0.1%
        self.default_taker_rate = 0.002  # 0.2%
        
        # Fee schedules by symbol
        self.fee_schedules: Dict[str, FeeSchedule] = {}
    
    def get_fee_schedule(self, symbol: str) -> FeeSchedule:
        """
        Get the fee schedule for a symbol.
        If no specific schedule exists, create one with default rates.
        """
        if symbol not in self.fee_schedules:
            self.fee_schedules[symbol] = FeeSchedule(
                symbol=symbol,
                maker_rate=self.default_maker_rate,
                taker_rate=self.default_taker_rate
            )
        
        return self.fee_schedules[symbol]
    
    def set_fee_schedule(self, symbol: str, maker_rate: float, taker_rate: float) -> FeeSchedule:
        """Set a custom fee schedule for a symbol."""
        self.fee_schedules[symbol] = FeeSchedule(
            symbol=symbol,
            maker_rate=maker_rate,
            taker_rate=taker_rate
        )
        
        return self.fee_schedules[symbol]
    
    def set_default_rates(self, maker_rate: float, taker_rate: float) -> None:
        """Set the default fee rates."""
        self.default_maker_rate = maker_rate
        self.default_taker_rate = taker_rate
    
    def calculate_fees(self, symbol: str, trade_value: float) -> tuple:
        """
        Calculate maker and taker fees for a trade.
        Returns a tuple of (maker_fee, taker_fee).
        """
        fee_schedule = self.get_fee_schedule(symbol)
        maker_fee = fee_schedule.calculate_maker_fee(trade_value)
        taker_fee = fee_schedule.calculate_taker_fee(trade_value)
        
        return maker_fee, taker_fee
