# Cryptocurrency Matching Engine - Usage Guide

This guide provides step-by-step instructions on how to use the cryptocurrency matching engine application.

## Installation and Setup

1. Install the required dependencies:

```bash
python3 -m pip install -r requirements.txt
```

2. Run the application:

```bash
python3 -m app.main
```

The application will start and listen on port 8000 by default.

3. Database Configuration:

By default, the application uses a SQLite database named `trading_app.db` in the current directory. You can specify a different database path using the `DB_PATH` environment variable:

```bash
DB_PATH=/path/to/database.db python3 -m app.main
```

## Using the REST API

### Submitting Orders

#### Submit a Limit Order

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "order_type": "limit",
    "side": "buy",
    "quantity": 1.0,
    "price": 50000.0
  }'
```

Response:
```json
{
  "order_id": "b26a8784-b6b5-406c-b4d0-6c4b6e983871",
  "status": "open",
  "message": "Order processed successfully. Filled: 0, Remaining: 1.0"
}
```

#### Submit a Market Order

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "order_type": "market",
    "side": "sell",
    "quantity": 0.5
  }'
```

Response:
```json
{
  "order_id": "6bba28b7-be13-4d95-a5f0-2128d9e79a02",
  "status": "filled",
  "message": "Order processed successfully. Filled: 0.5, Remaining: 0.0"
}
```

#### Submit an IOC (Immediate-Or-Cancel) Order

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "order_type": "ioc",
    "side": "buy",
    "quantity": 1.0,
    "price": 50000.0
  }'
```

#### Submit a FOK (Fill-Or-Kill) Order

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "order_type": "fok",
    "side": "buy",
    "quantity": 1.0,
    "price": 50000.0
  }'
```

#### Submit a Stop-Loss Order

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "order_type": "stop_loss",
    "side": "sell",
    "quantity": 1.0,
    "stop_price": 49000.0
  }'
```

Response:
```json
{
  "order_id": "c7d9e123-f5a2-4b87-9c31-8e4f7a2d5b6e",
  "status": "pending_trigger",
  "message": "Stop order accepted and waiting for trigger price: 49000.0"
}
```

#### Submit a Stop-Limit Order

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "order_type": "stop_limit",
    "side": "buy",
    "quantity": 1.0,
    "stop_price": 51000.0,
    "limit_price": 51500.0
  }'
```

Response:
```json
{
  "order_id": "d8e0f234-g6b3-5c98-0d42-9f5g8b3e6c7f",
  "status": "pending_trigger",
  "message": "Stop order accepted and waiting for trigger price: 51000.0"
}
```

#### Submit a Take-Profit Order

```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "order_type": "take_profit",
    "side": "buy",
    "quantity": 1.0,
    "stop_price": 49000.0
  }'
```

Response:
```json
{
  "order_id": "e9f1g345-h7c4-6d09-1e53-0g6h9c4f7d8g",
  "status": "pending_trigger",
  "message": "Stop order accepted and waiting for trigger price: 49000.0"
}
```

### Canceling Orders

```bash
curl -X DELETE "http://localhost:8000/orders/{order_id}"
```

Replace `{order_id}` with the actual order ID returned when submitting the order.

### Getting Order Details

```bash
curl -X GET "http://localhost:8000/orders/{order_id}"
```

Replace `{order_id}` with the actual order ID.

### Getting Market Data

#### Get Best Bid and Offer (BBO)

```bash
curl -X GET "http://localhost:8000/market-data/BTC-USDT/bbo"
```

Response:
```json
{
  "symbol": "BTC-USDT",
  "bid_price": 50000.0,
  "bid_quantity": 0.5,
  "ask_price": null,
  "ask_quantity": null,
  "timestamp": "2025-06-10T15:47:47.725074"
}
```

#### Get Order Book

```bash
curl -X GET "http://localhost:8000/market-data/BTC-USDT/order-book"
```

Response:
```json
{
  "timestamp": "2025-06-10T15:48:03.755615",
  "symbol": "BTC-USDT",
  "asks": [],
  "bids": [[50000.0, 0.5]]
}
```

#### Get Recent Trades

```bash
curl -X GET "http://localhost:8000/market-data/BTC-USDT/trades"
```

Response:
```json
[
  {
    "trade_id": "ec3b9d64-95e1-4a7d-bb41-606204ba53cd",
    "timestamp": "2025-06-10T15:47:47.724969",
    "symbol": "BTC-USDT",
    "price": 50000.0,
    "quantity": 0.5,
    "aggressor_side": "sell",
    "maker_order_id": "b26a8784-b6b5-406c-b4d0-6c4b6e983871",
    "taker_order_id": "6bba28b7-be13-4d95-a5f0-2128d9e79a02",
    "maker_fee": 25.0,
    "taker_fee": 50.0,
    "maker_fee_rate": 0.001,
    "taker_fee_rate": 0.002
  }
]
```

## Using the WebSocket API

### Connecting to WebSocket Feeds

#### BBO Feed

```javascript
// Connect to the BBO feed
const bbosocket = new WebSocket('ws://localhost:8000/ws/bbo');

bbosocket.onopen = function(e) {
  // Subscribe to a symbol
  bbosocket.send(JSON.stringify({
    action: 'subscribe',
    symbol: 'BTC-USDT'
  }));
};

bbosocket.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('BBO Update:', data);
};
```

#### Order Book Feed

```javascript
// Connect to the order book feed
const orderBookSocket = new WebSocket('ws://localhost:8000/ws/order-book');

orderBookSocket.onopen = function(e) {
  // Subscribe to a symbol
  orderBookSocket.send(JSON.stringify({
    action: 'subscribe',
    symbol: 'BTC-USDT'
  }));
};

orderBookSocket.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Order Book Update:', data);
};
```

#### Trades Feed

```javascript
// Connect to the trades feed
const tradesSocket = new WebSocket('ws://localhost:8000/ws/trades');

tradesSocket.onopen = function(e) {
  // Subscribe to a symbol
  tradesSocket.send(JSON.stringify({
    action: 'subscribe',
    symbol: 'BTC-USDT'
  }));
};

tradesSocket.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Trade Update:', data);
};
```

### WebSocket Message Format

#### BBO Update

```json
{
  "type": "bbo",
  "data": {
    "symbol": "BTC-USDT",
    "bid_price": 50000.0,
    "bid_quantity": 1.0,
    "ask_price": 50100.0,
    "ask_quantity": 2.0,
    "timestamp": "2025-06-10T15:47:47.725074"
  }
}
```

#### Order Book Update

```json
{
  "type": "order_book",
  "data": {
    "timestamp": "2025-06-10T15:48:03.755615",
    "symbol": "BTC-USDT",
    "asks": [[50100.0, 2.0], [50200.0, 1.5]],
    "bids": [[50000.0, 1.0], [49900.0, 3.0]]
  }
}
```

#### Trade Update

```json
{
  "type": "trades",
  "data": [
    {
      "trade_id": "ec3b9d64-95e1-4a7d-bb41-606204ba53cd",
      "timestamp": "2025-06-10T15:47:47.724969",
      "symbol": "BTC-USDT",
      "price": 50000.0,
      "quantity": 0.5,
      "aggressor_side": "sell",
      "maker_order_id": "b26a8784-b6b5-406c-b4d0-6c4b6e983871",
      "taker_order_id": "6bba28b7-be13-4d95-a5f0-2128d9e79a02",
      "maker_fee": 25.0,
      "taker_fee": 50.0,
      "maker_fee_rate": 0.001,
      "taker_fee_rate": 0.002
    }
  ]
}
```

## Advanced Order Types

### Stop-Loss Orders

A stop-loss order is designed to limit an investor's loss on a position. It becomes a market order when the price reaches or falls below a specified stop price.

- For a sell stop-loss: Triggers when the price falls to or below the stop price
- For a buy stop-loss: Triggers when the price rises to or above the stop price

### Stop-Limit Orders

A stop-limit order combines the features of a stop order and a limit order. When the stop price is reached, the order becomes a limit order at the specified limit price.

- For a sell stop-limit: Triggers when the price falls to or below the stop price, then becomes a limit sell order at the limit price
- For a buy stop-limit: Triggers when the price rises to or above the stop price, then becomes a limit buy order at the limit price

### Take-Profit Orders

A take-profit order is designed to close a position when a specified profit target is reached. It becomes a market order when the price reaches the specified target.

- For a sell take-profit: Triggers when the price rises to or above the stop price
- For a buy take-profit: Triggers when the price falls to or below the stop price

## Persistence Layer

The application includes a SQLite-based persistence layer that automatically saves and recovers the system state.

### Automatic State Saving

The system state is automatically saved:

1. Every 60 seconds during normal operation
2. During graceful shutdowns (when you press Ctrl+C or send SIGINT/SIGTERM signals)

### Automatic State Recovery

When the application starts, it automatically:

1. Loads all open and partially filled orders
2. Reconstructs the order books with correct price-time priority
3. Restores pending trigger orders (stop-loss, stop-limit, take-profit)
4. Loads custom fee schedules
5. Recovers recent trade history

### Database Location

By default, the database is stored in a file named `trading_app.db` in the current directory. You can specify a different location using the `DB_PATH` environment variable:

```bash
DB_PATH=/path/to/database.db python3 -m app.main
```

### Database Schema

The database includes the following tables:

1. **orders**: Stores all orders with their properties
2. **trades**: Stores all executed trades with fee information
3. **fee_schedules**: Stores custom fee schedules for different trading pairs
4. **default_fee_rates**: Stores the default maker and taker fee rates

## Fee Model

The trading application implements a maker-taker fee model, where:

- **Makers** (who provide liquidity by placing limit orders) pay lower fees
- **Takers** (who remove liquidity by placing market orders) pay higher fees

### Default Fee Rates

By default, the system uses the following fee rates:
- Maker fee: 0.1% (0.001)
- Taker fee: 0.2% (0.002)

### Setting Custom Fee Schedules

You can set custom fee schedules for specific trading pairs:

```bash
curl -X POST "http://localhost:8000/fee-schedules/BTC-USDT?maker_rate=0.0005&taker_rate=0.001"
```

Response:
```json
{
  "symbol": "BTC-USDT",
  "maker_rate": 0.0005,
  "taker_rate": 0.001
}
```

### Setting Default Fee Rates

You can also change the default fee rates that apply to all trading pairs without a custom fee schedule:

```bash
curl -X POST "http://localhost:8000/fee-schedules/default?maker_rate=0.0008&taker_rate=0.0015"
```

Response:
```json
{
  "maker_rate": 0.0008,
  "taker_rate": 0.0015
}
```

### Getting Fee Schedules

To get the fee schedule for a specific trading pair:

```bash
curl -X GET "http://localhost:8000/fee-schedules/BTC-USDT"
```

Response:
```json
{
  "symbol": "BTC-USDT",
  "maker_rate": 0.0005,
  "taker_rate": 0.001
}
```

### Fee Information in Trade Reports

When trades are executed, fee information is included in the trade reports:

```json
{
  "trade_id": "ec3b9d64-95e1-4a7d-bb41-606204ba53cd",
  "timestamp": "2025-06-10T15:47:47.724969",
  "symbol": "BTC-USDT",
  "price": 50000.0,
  "quantity": 0.5,
  "aggressor_side": "sell",
  "maker_order_id": "b26a8784-b6b5-406c-b4d0-6c4b6e983871",
  "taker_order_id": "6bba28b7-be13-4d95-a5f0-2128d9e79a02",
  "maker_fee": 25.0,
  "taker_fee": 50.0,
  "maker_fee_rate": 0.001,
  "taker_fee_rate": 0.002
}
```

### Example Fee Calculation

Let's walk through an example of how fees are calculated:

1. A maker places a limit buy order for 1 BTC at $50,000
2. A taker places a market sell order for 1 BTC
3. The orders match and a trade is executed at $50,000
4. The trade value is $50,000 (price × quantity = $50,000 × 1)
5. With default fee rates:
   - Maker fee = $50,000 × 0.001 = $50
   - Taker fee = $50,000 × 0.002 = $100
6. The maker pays $50 in fees, and the taker pays $100 in fees

## Running Tests

To run the test suite:

```bash
python3 -m pytest
```

For more verbose output:

```bash
python3 -m pytest -v
```

To run tests for advanced order types specifically:

```bash
python3 -m pytest tests/test_advanced_orders.py -v
```

To run tests for the persistence layer:

```bash
python3 -m pytest tests/test_persistence.py -v
```

To run tests for the fee model:

```bash
python3 -m pytest tests/test_fee_model.py -v
```

## Stopping the Application

If you started the application in the foreground, press `Ctrl+C` to stop it. The application will save its state before shutting down.

If you started it in the background, find the process ID and send a SIGTERM signal:

```bash
ps aux | grep "python3 -m app.main"
kill <process_id>
```

This will trigger a graceful shutdown, saving the state before exiting.

def findNumberOfPowerGrid(arr, n):
    disc = [-1] * n
    low = [-1] * n
    parent_arr = [-1] * n
    ap = [False] * n
    time_val = [0]
    
    def dfs(u, parent_node):
        disc[u] = time_val[0]
        low[u] = time_val[0]
        time_val[0] += 1
        children = 0
        for v in range(n):
            if arr[u][v] == 1:
                if v == parent_node:
                    continue
                if disc[v] == -1:
                    parent_arr[v] = u
                    children += 1
                    dfs(v, u)
                    low[u] = min(low[u], low[v])
                    if parent_node is not None and low[v] >= disc[u]:
                        ap[u] = True
                else:
                    low[u] = min(low[u], disc[v])
        if parent_node is None and children >= 2:
            ap[u] = True
            
    for i in range(n):
        if disc[i] == -1:
            time_val[0] = 0
            dfs(i, None)
            
    return sum(1 for x in ap if x)