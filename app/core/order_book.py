from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
from sortedcontainers import SortedDict

from app.models.order import Order, OrderType, OrderSide, OrderStatus, OrderBookEntry
from app.models.trade import Trade
from app.models.market_data import BBO, OrderBookUpdate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OrderBook:
    """
    Implements a price-time priority order book for a single trading pair.
    Uses sorted dictionaries for efficient price level access.
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        # SortedDict with reverse=True for bids (highest price first)
        self.bids = SortedDict(lambda x: -x)
        # SortedDict with default sorting for asks (lowest price first)
        self.asks = SortedDict()
        # Dictionary to quickly lookup orders by ID
        self.orders_by_id = {}
        # Current BBO
        self.bbo = BBO(symbol=symbol)
        # Trade history
        self.trades = []
        
        logger.info(f"Order book initialized for {symbol}")
    
    def _can_fully_fill(self, order: Order) -> bool:
        """
        Check if an order can be fully filled against the current book.
        Used for FOK orders to determine if they should be executed or canceled.
        """
        opposite_book = self.asks if order.side == OrderSide.BUY else self.bids
        remaining = order.quantity
        
        # Iterate through price levels
        for price in list(opposite_book.keys()):
            # For limit orders, check if the price is still acceptable
            if order.order_type == OrderType.LIMIT:
                if (order.side == OrderSide.BUY and price > order.price) or \
                   (order.side == OrderSide.SELL and price < order.price):
                    break
            
            # Add available quantity at this price level
            remaining -= opposite_book[price].total_quantity
            
            # If we can fill the order, return True
            if remaining <= 0:
                return True
        
        # If we get here, we can't fully fill the order
        return False
    
    def add_order(self, order: Order) -> Tuple[List[Trade], Order]:
        """
        Add a new order to the book. For marketable orders, this will trigger matching.
        Returns a list of trades executed and the updated order.
        """
        logger.info(f"Adding order: {order.order_id} - {order.side} {order.order_type} {order.quantity} @ {order.price}")
        
        # Validate order
        if order.order_type == OrderType.LIMIT and order.price is None:
            order.status = OrderStatus.REJECTED
            return [], order
        
        # For market orders, we need a valid opposite side
        if order.order_type == OrderType.MARKET:
            opposite_book = self.asks if order.side == OrderSide.BUY else self.bids
            if not opposite_book:
                order.status = OrderStatus.REJECTED
                return [], order
        
        # Check if the order is marketable
        trades = []
        
        if self._is_marketable(order):
            # For FOK orders, check if they can be fully filled
            if order.order_type == OrderType.FOK:
                if not self._can_fully_fill(order):
                    order.status = OrderStatus.CANCELED
                    return [], order
            
            # Process marketable order
            trades = self._match_order(order)
            
            # Handle special order types
            if order.order_type == OrderType.IOC and order.remaining_quantity > 0:
                # Cancel any unfilled portion for IOC orders
                order.status = OrderStatus.CANCELED if order.filled_quantity == 0 else OrderStatus.PARTIALLY_FILLED
                order.remaining_quantity = 0
        
        # Add any remaining quantity to the book for limit orders
        if order.remaining_quantity > 0 and order.order_type == OrderType.LIMIT:
            self._add_to_book(order)
            self.orders_by_id[order.order_id] = order
        
        # Update BBO
        self._update_bbo()
        
        return trades, order
    
    def cancel_order(self, order_id: str) -> Optional[Order]:
        """
        Cancel an order by ID.
        Returns the canceled order or None if not found.
        """
        if order_id not in self.orders_by_id:
            return None
        
        order = self.orders_by_id[order_id]
        
        # Remove from price level
        book = self.bids if order.side == OrderSide.BUY else self.asks
        if order.price in book:
            entry = book[order.price]
            entry.remove_order(order_id)
            
            # Remove price level if empty
            if not entry.orders:
                del book[order.price]
        
        # Remove from ID lookup
        del self.orders_by_id[order_id]
        
        # Update order status
        order.status = OrderStatus.CANCELED
        
        # Update BBO
        self._update_bbo()
        
        logger.info(f"Canceled order: {order_id}")
        return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self.orders_by_id.get(order_id)
    
    def get_bbo(self) -> BBO:
        """Get the current Best Bid and Offer."""
        return self.bbo
    
    def get_order_book_snapshot(self, depth: int = 10) -> OrderBookUpdate:
        """
        Get a snapshot of the order book up to the specified depth.
        Returns an OrderBookUpdate with bids and asks as [price, quantity] pairs.
        """
        bids = []
        asks = []
        
        # Get top bids (already sorted by price in descending order)
        for price, entry in self.bids.items():
            bids.append((price, entry.total_quantity))
            if len(bids) >= depth:
                break
        
        # Get top asks (already sorted by price in ascending order)
        for price, entry in self.asks.items():
            asks.append((price, entry.total_quantity))
            if len(asks) >= depth:
                break
        
        return OrderBookUpdate(
            timestamp=datetime.utcnow(),
            symbol=self.symbol,
            bids=bids,
            asks=asks
        )
    
    def _is_marketable(self, order: Order) -> bool:
        """Check if an order is immediately marketable against the current book."""
        if order.order_type == OrderType.MARKET:
            return True
            
        opposite_book = self.asks if order.side == OrderSide.BUY else self.bids
        
        if not opposite_book:
            return False
            
        best_price = next(iter(opposite_book))
        
        if order.side == OrderSide.BUY:
            return order.price >= best_price
        else:  # SELL
            return order.price <= best_price
    
    def _match_order(self, order: Order) -> List[Trade]:
        """
        Match a marketable order against the book.
        Returns a list of trades executed.
        """
        trades = []
        opposite_book = self.asks if order.side == OrderSide.BUY else self.bids
        
        # For FOK orders, we need to check if the entire order can be filled
        if order.order_type == OrderType.FOK:
            # Check if the order can be fully filled
            can_fill = self._can_fully_fill(order)
            if not can_fill:
                return []
        
        # Continue matching until the order is filled or no more matches
        while order.remaining_quantity > 0 and opposite_book:
            # Get the best price level
            best_price = next(iter(opposite_book))
            price_level = opposite_book[best_price]
            
            # For limit orders, check if the price is still acceptable
            if order.order_type == OrderType.LIMIT:
                if (order.side == OrderSide.BUY and best_price > order.price) or \
                   (order.side == OrderSide.SELL and best_price < order.price):
                    break
            
            # Match against orders at this price level (FIFO)
            i = 0
            while i < len(price_level.orders) and order.remaining_quantity > 0:
                resting_order = price_level.orders[i]
                
                # Calculate fill quantity
                fill_qty = min(order.remaining_quantity, resting_order.remaining_quantity)
                
                # Update both orders
                order.update_on_fill(fill_qty)
                resting_order.update_on_fill(fill_qty)
                
                # Create trade record
                trade = Trade(
                    symbol=self.symbol,
                    price=best_price,
                    quantity=fill_qty,
                    aggressor_side=order.side.value,
                    maker_order_id=resting_order.order_id,
                    taker_order_id=order.order_id
                )
                trades.append(trade)
                self.trades.append(trade)
                
                logger.info(f"Trade executed: {trade.trade_id} - {fill_qty} @ {best_price}")
                
                # If resting order is filled, remove it
                if resting_order.status == OrderStatus.FILLED:
                    price_level.orders.pop(i)
                    del self.orders_by_id[resting_order.order_id]
                else:
                    i += 1
                
                # Update total quantity at this price level
                price_level.update_quantity()
            
            # If price level is empty, remove it
            if not price_level.orders:
                del opposite_book[best_price]
            
            # For FOK orders, we need to check if the entire order can be filled
            if order.order_type == OrderType.FOK and order.filled_quantity < order.quantity:
                # We'll handle this in the calling function
                break
        
        return trades
    
    def _add_to_book(self, order: Order) -> None:
        """Add a non-marketable order to the book."""
        book = self.bids if order.side == OrderSide.BUY else self.asks
        
        if order.price not in book:
            book[order.price] = OrderBookEntry(price=order.price)
        
        book[order.price].add_order(order)
        logger.info(f"Order added to book: {order.order_id} at price {order.price}")
    
    def _update_bbo(self) -> None:
        """Update the Best Bid and Offer."""
        # Update best bid
        if self.bids:
            best_bid_price = next(iter(self.bids))
            best_bid_qty = self.bids[best_bid_price].total_quantity
            self.bbo.bid_price = best_bid_price
            self.bbo.bid_quantity = best_bid_qty
        else:
            self.bbo.bid_price = None
            self.bbo.bid_quantity = None
        
        # Update best ask
        if self.asks:
            best_ask_price = next(iter(self.asks))
            best_ask_qty = self.asks[best_ask_price].total_quantity
            self.bbo.ask_price = best_ask_price
            self.bbo.ask_quantity = best_ask_qty
        else:
            self.bbo.ask_price = None
            self.bbo.ask_quantity = None
        
        self.bbo.timestamp = datetime.utcnow()
        
        logger.debug(f"BBO updated: Bid {self.bbo.bid_price}@{self.bbo.bid_quantity}, Ask {self.bbo.ask_price}@{self.bbo.ask_quantity}")
