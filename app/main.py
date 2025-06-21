import os
import signal
import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from typing import List, Dict, Any, Optional

from app.core.matching_engine import MatchingEngine
from app.api.rest import app as rest_app
from app.api.websocket import handle_websocket, ConnectionManager
from app.persistence.persistence_manager import PersistenceManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='trading_app.log'
)
logger = logging.getLogger(__name__)

# Create the main FastAPI app
app = FastAPI(
    title="Cryptocurrency Trading App",
    description="High-performance cryptocurrency matching engine with RESTful and WebSocket APIs",
    version="1.0.0"
)

# Create matching engine instance
matching_engine = MatchingEngine()

# Create persistence manager
db_path = os.environ.get("DB_PATH", "trading_app.db")
persistence_manager = PersistenceManager(db_path)
matching_engine.persistence_manager = persistence_manager

# Load state from database
try:
    matching_engine.load_state()
    logger.info("Loaded state from database")
except Exception as e:
    logger.error(f"Error loading state from database: {e}")
    logger.info("Starting with empty state")

# Create WebSocket connection manager
connection_manager = ConnectionManager(matching_engine)

# Copy routes from the REST API
for route in rest_app.routes:
    app.routes.append(route)


@app.websocket("/ws/bbo")
async def websocket_bbo_endpoint(websocket: WebSocket):
    """WebSocket endpoint for BBO updates."""
    await handle_websocket(websocket, "bbo", connection_manager)


@app.websocket("/ws/order-book")
async def websocket_order_book_endpoint(websocket: WebSocket):
    """WebSocket endpoint for order book updates."""
    await handle_websocket(websocket, "order_book", connection_manager)


@app.websocket("/ws/trades")
async def websocket_trades_endpoint(websocket: WebSocket):
    """WebSocket endpoint for trade updates."""
    await handle_websocket(websocket, "trades", connection_manager)


# Dependency to get the matching engine
def get_matching_engine():
    return matching_engine


# Periodic state saving
async def save_state_periodically():
    """Save the engine state to the database periodically."""
    while True:
        try:
            await asyncio.sleep(60)  # Save every 60 seconds
            matching_engine.save_state()
            logger.info("Periodic state save completed")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error during periodic state save: {e}")


# Shutdown handler
def handle_shutdown(signal, frame):
    """Handle graceful shutdown."""
    logger.info("Shutdown signal received, saving state...")
    try:
        matching_engine.save_state()
        persistence_manager.close()
        logger.info("State saved, shutting down")
    except Exception as e:
        logger.error(f"Error saving state during shutdown: {e}")
    finally:
        # Exit with success status
        os._exit(0)


# Register shutdown handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    # Start the periodic state saving task
    app.state.save_task = asyncio.create_task(save_state_periodically())
    logger.info("Application started")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    # Cancel the periodic state saving task
    if hasattr(app.state, "save_task"):
        app.state.save_task.cancel()
        try:
            await app.state.save_task
        except asyncio.CancelledError:
            pass
    
    # Save state one last time
    try:
        matching_engine.save_state()
        persistence_manager.close()
        logger.info("Final state save completed")
    except Exception as e:
        logger.error(f"Error during final state save: {e}")
    
    logger.info("Application shutdown")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
