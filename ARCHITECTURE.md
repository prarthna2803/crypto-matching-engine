# Cryptocurrency Matching Engine - Architecture Documentation

## System Architecture

The cryptocurrency matching engine is designed as a high-performance trading system implementing REG NMS-inspired principles of price-time priority and internal order protection. The system consists of the following components:

### 1. Matching Engine Core

The core of the system is the matching engine, which:
- Processes incoming orders
- Maintains order books for different trading pairs
- Executes trades based on price-time priority
- Prevents internal trade-throughs
- Generates trade execution data
- Manages advanced order types (Stop-Loss, Stop-Limit, Take-Profit)

The matching engine is implemented in `app/core/matching_engine.py` and manages multiple order books, one for each trading pair.

### 2. Order Book

Each order book represents a single trading pair (e.g., BTC-USDT) and:
- Maintains separate books for bids and asks
- Organizes orders by price and time priority
- Calculates and updates the Best Bid and Offer (BBO)
- Matches incoming orders against resting orders

The order book is implemented in `app/core/order_book.py` and uses efficient data structures for order management.

### 3. REST API

The REST API provides endpoints for:
- Submitting new orders
- Canceling existing orders
- Retrieving order details
- Getting market data (BBO, order book, trades)

The REST API is implemented using FastAPI in `app/api/rest.py`.

### 4. WebSocket API

The WebSocket API provides real-time data streams for:
- BBO updates
- Order book updates
- Trade execution updates

The WebSocket API is implemented in `app/api/websocket.py` and uses FastAPI's WebSocket support.

## Data Structures

### 1. SortedDict for Price Levels

The system uses `SortedDict` from the `sortedcontainers` package to maintain price levels in the order book:
- Bids are sorted in descending order (highest price first)
- Asks are sorted in ascending order (lowest price first)

This provides:
- O(log n) insertion and deletion
- O(1) access to the best price level
- Efficient iteration through price levels in order

### 2. Order Lists at Each Price Level

At each price level, orders are stored in a list in time priority order (FIFO):
- New orders are appended to the end of the list
- When matching, orders are taken from the beginning of the list
- This ensures strict time priority within each price level

### 3. Order ID Lookup Dictionary

A dictionary maps order IDs to orders for O(1) access:
- Used for efficient order retrieval, cancellation, and modification
- Prevents the need to search through the order book to find an order

### 4. Pending Trigger Orders

A dictionary maps symbols to lists of pending trigger orders:
- Used for efficient management of stop and take-profit orders
- Orders are checked against each new trade price to determine if they should be triggered

## Matching Algorithm

The matching algorithm implements strict price-time priority:

1. When a new order arrives, the system checks if it's marketable against the opposite side of the book.
2. For marketable orders, the system matches at the best available price first.
3. At each price level, orders are matched in time priority (FIFO).
4. The system prevents internal trade-throughs by always matching at the best available price.
5. Special order types (IOC, FOK) have additional logic:
   - IOC: Execute immediately and cancel any unfilled portion
   - FOK: Execute entirely or cancel entirely

## Order Types

The system supports seven order types:

1. **Market Order**: Executes immediately at the best available price(s).
2. **Limit Order**: Executes at the specified price or better. Rests on the book if not immediately marketable.
3. **Immediate-Or-Cancel (IOC)**: Executes all or part of the order immediately and cancels any unfilled portion.
4. **Fill-Or-Kill (FOK)**: Executes the entire order immediately or cancels the entire order if it cannot be fully filled.
5. **Stop-Loss Order**: Becomes a market order when the price reaches the specified stop price.
6. **Stop-Limit Order**: Becomes a limit order when the price reaches the specified stop price.
7. **Take-Profit Order**: Executes when the price reaches a specified profit target.

### Advanced Order Types Implementation

#### Stop Orders
- Stop orders are stored in a separate data structure (`pending_trigger_orders`) and not in the order book
- After each trade, the system checks if any pending stop orders should be triggered
- When triggered, stop-loss orders become market orders, and stop-limit orders become limit orders

#### Take-Profit Orders
- Similar to stop orders, take-profit orders are stored in the `pending_trigger_orders` structure
- They are triggered when the price reaches the specified target
- When triggered, they become market orders

## API Specifications

### REST API

- `POST /orders`: Submit a new order
- `DELETE /orders/{order_id}`: Cancel an existing order
- `GET /orders/{order_id}`: Get details of an existing order
- `GET /market-data/{symbol}/bbo`: Get the current Best Bid and Offer
- `GET /market-data/{symbol}/order-book`: Get the current order book
- `GET /market-data/{symbol}/trades`: Get recent trades

### WebSocket API

- `/ws/bbo`: Stream real-time BBO updates
- `/ws/order-book`: Stream real-time order book updates
- `/ws/trades`: Stream real-time trade execution updates


## REG NMS-inspired Implementations

1. **Price-Time Priority**:
   - Better-priced orders matched first
   - At same price, earlier orders matched first

2. **Internal Order Protection**:
   - Prevents "internal trade-throughs"
   - Always matches at the best available price

3. **BBO Calculation and Dissemination**:
   - Maintains real-time Best Bid and Offer
   - Disseminates via REST and WebSocket APIs


**Persistence Layer**: SQLite-based storage for recovering state after crashes or restarts

### Database Schema
- **orders**: Stores all orders with their properties
- **trades**: Stores all executed trades with fee information
- **fee_schedules**: Stores custom fee schedules for different trading pairs
- **default_fee_rates**: Stores the default maker and taker fee rates

### Automatic State Management
- Saves state every 60 seconds
- Saves state during graceful shutdowns
- Recovers state automatically on startup


## Trade-off Decisions

### 1. In-Memory vs. Persistence

The system is designed as an in-memory matching engine for maximum performance. In a production environment, this would be complemented with:
- A persistence layer for order and trade history
- A recovery mechanism for system restarts
- A transaction log for audit purposes

### 2. Data Structure Choices

- **SortedDict**: Provides O(log n) insertion/deletion and O(1) access to the best price.
- **Lists for Time Priority**: Simple implementation that maintains FIFO order.
- **Dictionary for Order Lookup**: Provides O(1) access to any order by ID.

These choices balance performance with code simplicity and maintainability.

### 3. Concurrency Model

The current implementation is single-threaded for simplicity. In a production environment, a more sophisticated concurrency model would be needed:
- Thread-safe data structures
- Lock-free algorithms where possible
- Potential sharding by symbol

### 4. Error Handling and Validation

The system implements basic error handling and validation:
- Order parameter validation
- Rejection of invalid orders
- Proper error responses via the API

In a production system, more comprehensive error handling and validation would be needed.

### 5. Advanced Order Types Implementation

For advanced order types (Stop-Loss, Stop-Limit, Take-Profit):
- Orders are stored in memory and checked after each trade
- This approach is simple but may not scale well with a large number of pending trigger orders
- A more sophisticated implementation might use price-level-based triggers or a separate trigger service

## Performance Considerations

The system is designed for high performance:
- Efficient data structures for order book operations
- Minimal copying of data
- Optimized matching algorithm
- Asynchronous API endpoints

In a production environment, additional optimizations would be needed for handling high volumes of orders and market data dissemination.

## Fee Model

The system implements a maker-taker fee model, which is common in cryptocurrency exchanges:

### Fee Model Components

1. **FeeModel Class**: 
   - Central manager for fee schedules across different trading pairs
   - Maintains default fee rates and custom fee schedules by symbol
   - Provides methods for fee calculation and management

2. **FeeSchedule Class**:
   - Represents a fee schedule for a specific trading pair
   - Contains maker and taker fee rates
   - Provides methods to calculate fees based on trade value

### Fee Calculation Process

1. When a trade is executed, the system calculates the trade value (price × quantity)
2. The appropriate fee schedule is retrieved based on the trading pair
3. Maker and taker fees are calculated by multiplying the trade value by the respective fee rates
4. Fee information is added to the trade record

### Fee API Endpoints

The system provides API endpoints for fee management:
- `GET /fee-schedules/{symbol}`: Get the fee schedule for a symbol
- `POST /fee-schedules/{symbol}`: Set a custom fee schedule for a symbol
- `POST /fee-schedules/default`: Set the default fee rates

### Trade-off Decisions

1. **In-Memory Fee Model**:
   - The fee model is maintained in memory for simplicity and performance
   - In a production environment, fee schedules would be persisted to a database

2. **Simple Fee Structure**:
   - The current implementation uses fixed fee rates per trading pair
   - A more sophisticated implementation might include tiered fee structures based on trading volume or user VIP levels

3. **Fee Collection**:
   - The current implementation calculates fees but does not handle fee collection or account balance updates
   - In a production environment, this would be integrated with a balance management system