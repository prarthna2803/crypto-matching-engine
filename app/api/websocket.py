import asyncio
import json
import logging
from typing import Dict, Set, List, Any
from fastapi import WebSocket, WebSocketDisconnect

from app.core.matching_engine import MatchingEngine
from app.models.market_data import BBO, OrderBookUpdate
from app.models.trade import Trade

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts market data.
    """
    
    def __init__(self, matching_engine: MatchingEngine):
        self.matching_engine = matching_engine
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "bbo": set(),
            "order_book": set(),
            "trades": set()
        }
        self.symbol_subscriptions: Dict[WebSocket, Set[str]] = {}
        self.running = False
        self.broadcast_task = None
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Connect a client to a specific channel."""
        await websocket.accept()
        
        if channel not in self.active_connections:
            await websocket.close(code=1003, reason=f"Invalid channel: {channel}")
            return False
        
        self.active_connections[channel].add(websocket)
        self.symbol_subscriptions[websocket] = set()
        
        logger.info(f"Client connected to {channel} channel")
        return True
    
    async def disconnect(self, websocket: WebSocket):
        """Disconnect a client from all channels."""
        for channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
        
        if websocket in self.symbol_subscriptions:
            del self.symbol_subscriptions[websocket]
        
        logger.info("Client disconnected")
    
    async def subscribe(self, websocket: WebSocket, symbol: str):
        """Subscribe a client to a specific symbol."""
        if websocket in self.symbol_subscriptions:
            self.symbol_subscriptions[websocket].add(symbol)
            await websocket.send_text(json.dumps({
                "type": "subscription",
                "status": "success",
                "symbol": symbol
            }))
            logger.info(f"Client subscribed to {symbol}")
        else:
            await websocket.send_text(json.dumps({
                "type": "subscription",
                "status": "error",
                "message": "Not connected to any channel"
            }))
    
    async def unsubscribe(self, websocket: WebSocket, symbol: str):
        """Unsubscribe a client from a specific symbol."""
        if websocket in self.symbol_subscriptions and symbol in self.symbol_subscriptions[websocket]:
            self.symbol_subscriptions[websocket].remove(symbol)
            await websocket.send_text(json.dumps({
                "type": "unsubscription",
                "status": "success",
                "symbol": symbol
            }))
            logger.info(f"Client unsubscribed from {symbol}")
    
    async def broadcast_bbo(self):
        """Broadcast BBO updates to subscribed clients."""
        if not self.active_connections["bbo"]:
            return
        
        # Get all symbols with active order books
        symbols = list(self.matching_engine.order_books.keys())
        
        for symbol in symbols:
            bbo = self.matching_engine.get_bbo(symbol)
            if not bbo:
                continue
            
            # Convert to dict for JSON serialization
            bbo_dict = bbo.dict()
            message = {
                "type": "bbo",
                "data": bbo_dict
            }
            
            # Send to all clients subscribed to this symbol
            for websocket in list(self.active_connections["bbo"]):
                if websocket in self.symbol_subscriptions and (
                    not self.symbol_subscriptions[websocket] or  # No subscriptions means all symbols
                    symbol in self.symbol_subscriptions[websocket]
                ):
                    try:
                        await websocket.send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"Error sending BBO update: {e}")
                        # Will be removed on next receive error
    
    async def broadcast_order_book(self):
        """Broadcast order book updates to subscribed clients."""
        if not self.active_connections["order_book"]:
            return
        
        # Get all symbols with active order books
        symbols = list(self.matching_engine.order_books.keys())
        
        for symbol in symbols:
            order_book = self.matching_engine.get_order_book_snapshot(symbol)
            if not order_book:
                continue
            
            # Convert to dict for JSON serialization
            order_book_dict = order_book.dict()
            message = {
                "type": "order_book",
                "data": order_book_dict
            }
            
            # Send to all clients subscribed to this symbol
            for websocket in list(self.active_connections["order_book"]):
                if websocket in self.symbol_subscriptions and (
                    not self.symbol_subscriptions[websocket] or  # No subscriptions means all symbols
                    symbol in self.symbol_subscriptions[websocket]
                ):
                    try:
                        await websocket.send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"Error sending order book update: {e}")
                        # Will be removed on next receive error
    
    async def broadcast_trades(self, trades: List[Trade], symbol: str):
        """Broadcast trade updates to subscribed clients."""
        if not self.active_connections["trades"] or not trades:
            return
        
        # Convert trades to dict for JSON serialization
        trades_dict = [trade.dict() for trade in trades]
        message = {
            "type": "trades",
            "data": trades_dict
        }
        
        # Send to all clients subscribed to this symbol
        for websocket in list(self.active_connections["trades"]):
            if websocket in self.symbol_subscriptions and (
                not self.symbol_subscriptions[websocket] or  # No subscriptions means all symbols
                symbol in self.symbol_subscriptions[websocket]
            ):
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending trade update: {e}")
                    # Will be removed on next receive error
    
    async def start_broadcasting(self):
        """Start the background broadcasting task."""
        if self.running:
            return
        
        self.running = True
        self.broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info("Started broadcasting market data")
    
    async def stop_broadcasting(self):
        """Stop the background broadcasting task."""
        if not self.running:
            return
        
        self.running = False
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass
            self.broadcast_task = None
        
        logger.info("Stopped broadcasting market data")
    
    async def _broadcast_loop(self):
        """Background task to periodically broadcast market data."""
        try:
            while self.running:
                await self.broadcast_bbo()
                await self.broadcast_order_book()
                await asyncio.sleep(1)  # Broadcast every second
        except asyncio.CancelledError:
            logger.info("Broadcast loop cancelled")
        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}")
            self.running = False


async def handle_websocket(
    websocket: WebSocket,
    channel: str,
    connection_manager: ConnectionManager
):
    """Handle a WebSocket connection for a specific channel."""
    connected = await connection_manager.connect(websocket, channel)
    
    if not connected:
        return
    
    try:
        # Start broadcasting if not already running
        if not connection_manager.running:
            await connection_manager.start_broadcasting()
        
        # Handle client messages
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if "action" in message:
                    if message["action"] == "subscribe" and "symbol" in message:
                        await connection_manager.subscribe(websocket, message["symbol"])
                    elif message["action"] == "unsubscribe" and "symbol" in message:
                        await connection_manager.unsubscribe(websocket, message["symbol"])
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Invalid action or missing symbol"
                        }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid message format"
                    }))
            
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
            
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Internal server error"
                }))
    
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await connection_manager.disconnect(websocket)
