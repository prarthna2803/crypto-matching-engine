# Cryptocurrency Matching Engine - Architecture Documentation

A high-throughput, low-latency cryptocurrency matching engine architecture built with **Python 3.10+**, **FastAPI**, **SortedContainers**, and **SQLite**. The system implements **REG NMS-inspired** principles of price-time priority, internal order protection (anti-trade-through), maker-taker fee structures, and real-time market data dissemination.

---

## Table of Contents
- [1. High-Level System Architecture](#1-high-level-system-architecture)
- [2. Component Breakdown](#2-component-breakdown)
- [3. Order Processing & Matching Flow](#3-order-processing--matching-flow)
- [4. Order Lifecycle & State Machine](#4-order-lifecycle--state-machine)
- [5. Advanced Order Trigger Workflow](#5-advanced-order-trigger-workflow)
- [6. In-Memory Data Structures & Complexity](#6-in-memory-data-structures--complexity)
- [7. Persistence Layer & Crash Recovery](#7-persistence-layer--crash-recovery)
- [8. Real-Time WebSocket Streaming Subsystem](#8-real-time-websocket-streaming-subsystem)
- [9. Performance & Concurrency Trade-Offs](#9-performance--concurrency-trade-offs)

---

## 1. High-Level System Architecture

The engine adopts a decoupled layered architecture separating **Network Ingestion (REST & WebSockets)**, **In-Memory Core Execution**, and **Asynchronous Persistence**.

```mermaid
flowchart TB
    subgraph Clients ["Client Applications & Trading Bots"]
        HTTP_Client["REST API Clients / Webhooks"]
        WS_Client["WebSocket Market Data Consumers"]
    end

    subgraph API_Layer ["API & Ingestion Layer (FastAPI)"]
        REST_Gateway["REST Controller\n(app/api/rest.py)"]
        WS_Gateway["WebSocket Controller\n(app/api/websocket.py)"]
        ConnManager["WebSocket Connection Manager\n(Topic Subscriptions)"]
    end

    subgraph Engine_Core ["Core Matching Engine (In-Memory)"]
        Engine["Matching Engine Coordinator\n(app/core/matching_engine.py)"]
        FeeEngine["Maker-Taker Fee Model\n(app/models/fee.py)"]
        TriggerManager["Pending Trigger Order Registry\n(Stop/Take-Profit)"]
        
        subgraph OrderBooks ["Symbol Order Books (e.g. BTC-USDT, ETH-USDT)"]
            OB["OrderBook Instance\n(app/core/order_book.py)"]
            Bids["Bids SortedDict\n(Desc Price -> FIFO Queue)"]
            Asks["Asks SortedDict\n(Asc Price -> FIFO Queue)"]
            Index["Order ID Lookup Map\n(O(1) Hash Map)"]
        end
    end

    subgraph Persistence ["Persistence & Durability Layer"]
        PManager["Persistence Manager\n(app/persistence/persistence_manager.py)"]
        DB[(SQLite Embedded DB\ntrading_app.db)]
        OrderRepo["Order Repository"]
        TradeRepo["Trade Repository"]
        FeeRepo["Fee Repository"]
    end

    %% Flow Connections
    HTTP_Client -->|Order Submissions & Queries| REST_Gateway
    WS_Client <-->|Subscribe & Stream Updates| WS_Gateway
    WS_Gateway --> ConnManager

    REST_Gateway -->|Submit / Cancel Orders| Engine
    Engine -->|Route to Symbol Book| OB
    OB --> Bids
    OB --> Asks
    OB --> Index

    Engine -->|Calculate Fees| FeeEngine
    Engine -->|Evaluate Trailing Triggers| TriggerManager
    TriggerManager -.->|Promote to Market/Limit| Engine

    Engine -->|Emit BBO, Depth & Trades| ConnManager
    ConnManager -->|Broadcast JSON Frames| WS_Client

    Engine -->|Sync State (Every 60s / Shutdown)| PManager
    PManager --> OrderRepo
    PManager --> TradeRepo
    PManager --> FeeRepo
    OrderRepo --> DB
    TradeRepo --> DB
    FeeRepo --> DB
```

---

## 2. Component Breakdown

| Component | Module Path | Primary Responsibility |
| :--- | :--- | :--- |
| **Matching Engine** | `app/core/matching_engine.py` | Central coordinator orchestrating order validation, symbol routing, trigger evaluation, fee calculation, and event broadcast. |
| **Order Book** | `app/core/order_book.py` | Manages bids/asks priority queues, executes matching loops, and maintains Best-Bid-Offer (BBO). |
| **Fee Model** | `app/models/fee.py` | Computes maker-taker fees with custom pair schedules and volume tier defaults. |
| **REST Gateway** | `app/api/rest.py` | FastAPI HTTP controllers for synchronous order lifecycle operations and market data queries. |
| **WebSocket Gateway** | `app/api/websocket.py` | Asynchronous pub-sub manager broadcasting BBO changes, L2 order book depth, and executed trade feeds. |
| **Persistence Manager** | `app/persistence/persistence_manager.py` | Snapshot engine persisting state to SQLite and restoring order books on crash/restart. |

---

## 3. Order Processing & Matching Flow

The sequence diagram below illustrates an incoming **Limit/Market Order** matched against resting liquidity, applying maker-taker fees, updating persistence, and streaming market data to subscribers:

```mermaid
sequenceDiagram
    autonumber
    actor Trader as Trader / API Client
    participant API as REST Controller
    participant Engine as Matching Engine
    participant Book as Symbol OrderBook
    participant Fee as Fee Engine
    participant Persist as Persistence Manager
    participant WS as WebSocket Manager
    actor Subs as WebSocket Subscribers

    Trader->>API: POST /orders (symbol, side, quantity, price, type)
    API->>Engine: process_order(Order)
    
    alt Stop / Take-Profit Order
        Engine->>Engine: register_trigger_order(order)
        Engine-->>API: Return Order (Status: PENDING_TRIGGER)
    else Market / Limit Order
        Engine->>Book: match_order(incoming_order)
        
        loop While incoming unfilled & opposite best price matches
            Book->>Book: Pop head of FIFO queue at best price level
            Book->>Book: Execute trade slice (fill_qty = min(resting, incoming))
            Book->>Fee: calculate_fees(symbol, trade_value, is_maker)
            Fee-->>Book: Return maker_fee & taker_fee
            Book->>Book: Record Trade & Update Order statuses
        end

        alt Remaining Unfilled Quantity > 0
            alt Order Type == LIMIT
                Book->>Book: Insert remainder into SortedDict price queue
            else Order Type == IOC or FOK
                Book->>Book: Cancel remainder / Void transaction
            end
        end

        Book-->>Engine: Return (list[Trade], updated_order)
        
        %% Post-matching actions
        par Async Persistence & Triggers
            Engine->>Engine: evaluate_pending_triggers(last_trade_price)
            Engine->>Persist: queue_for_persistence(trades, orders)
        and Real-time Dissemination
            Engine->>WS: broadcast_trade(trades)
            Engine->>WS: broadcast_bbo(symbol, new_bbo)
            Engine->>WS: broadcast_depth(symbol, l2_depth)
            WS-->>Subs: Push JSON Events
        end

        Engine-->>API: Return OrderResult
    end
    API-->>Trader: HTTP 201 Created (Order Details + Trades)
```

---

## 4. Order Lifecycle & State Machine

Each order transitions through well-defined lifecycle states ensuring deterministic execution and accounting.

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED: Order Received via API
    
    SUBMITTED --> REJECTED: Validation Failure (Invalid Price/Qty)
    SUBMITTED --> PENDING_TRIGGER: Stop-Loss / Take-Profit Order
    SUBMITTED --> MATCHING: Market / Limit / IOC / FOK Order

    PENDING_TRIGGER --> MATCHING: Price reaches trigger threshold
    PENDING_TRIGGER --> CANCELLED: Trader invokes DELETE /orders/{id}

    state MATCHING {
        [*] --> EVALUATE_OPPOSITE_BOOK
        EVALUATE_OPPOSITE_BOOK --> FULLY_MATCHED: Quantity fully consumed
        EVALUATE_OPPOSITE_BOOK --> PARTIALLY_MATCHED: Quantity partially consumed
        EVALUATE_OPPOSITE_BOOK --> UNMATCHED: No price overlap
    }

    FULLY_MATCHED --> FILLED: All quantity executed
    
    PARTIALLY_MATCHED --> PARTIALLY_FILLED: Limit Order (rest placed on book)
    PARTIALLY_MATCHED --> CANCELLED: IOC Order (unfilled portion cancelled)
    
    UNMATCHED --> OPEN: Limit Order placed on book
    UNMATCHED --> CANCELLED: IOC / FOK / Market Order with no liquidity

    OPEN --> PARTIALLY_FILLED: Subsequent incoming match
    OPEN --> CANCELLED: Trader invokes DELETE /orders/{id}
    
    PARTIALLY_FILLED --> FILLED: Remaining quantity executed
    PARTIALLY_FILLED --> CANCELLED: Trader cancels remainder

    FILLED --> [*]
    CANCELLED --> [*]
    REJECTED --> [*]
```

---

## 5. Advanced Order Trigger Workflow

Conditional orders (**Stop-Loss**, **Stop-Limit**, **Take-Profit**) reside in an indexed trigger pool outside the active order book to prevent book pollution until condition criteria are satisfied:

```mermaid
flowchart TD
    TradeOccurs["Trade Executed at Price P"] --> Broadcast["Update Last Traded Price"]
    Broadcast --> InspectTriggers{"Pending Triggers for Symbol?"}

    InspectTriggers -- No --> End[Continue Normal Processing]
    InspectTriggers -- Yes --> Loop[Iterate Registered Trigger Orders]

    Loop --> Condition{"Evaluate Trigger Condition"}
    
    Condition -- "Stop-Loss Buy: P >= StopPrice" --> Activate["Trigger Order"]
    Condition -- "Stop-Loss Sell: P <= StopPrice" --> Activate
    Condition -- "Take-Profit Buy: P <= StopPrice" --> Activate
    Condition -- "Take-Profit Sell: P >= StopPrice" --> Activate
    Condition -- Not Met --> KeepPending["Retain in Trigger Pool"]

    Activate --> Convert{"Order Type?"}
    Convert -- STOP_LOSS / TAKE_PROFIT --> PromoteMarket["Convert to MARKET Order"]
    Convert -- STOP_LIMIT --> PromoteLimit["Convert to LIMIT Order (at LimitPrice)"]

    PromoteMarket --> InjectEngine["Inject into Matching Engine Pipeline"]
    PromoteLimit --> InjectEngine
    InjectEngine --> RemoveTrigger["Remove from Pending Trigger Pool"]
```

---

## 6. In-Memory Data Structures & Complexity

To deliver microsecond-tier throughput, the engine combines **Sorted Containers** and **Hash Indices**:

```mermaid
classDiagram
    class OrderBook {
        +symbol: str
        +bids: SortedDict[float, deque[Order]]
        +asks: SortedDict[float, deque[Order]]
        +orders: dict[str, Order]
        +best_bid: Optional[float]
        +best_ask: Optional[float]
        +add_order(order: Order)
        +cancel_order(order_id: str)
        +match_order(order: Order)
        +get_bbo() BBO
        +get_depth(depth: int) L2Depth
    }

    class Order {
        +order_id: str
        +symbol: str
        +side: OrderSide
        +order_type: OrderType
        +price: Optional[float]
        +quantity: float
        +filled_quantity: float
        +status: OrderStatus
        +stop_price: Optional[float]
        +timestamp: datetime
    }

    class Trade {
        +trade_id: str
        +symbol: str
        +buyer_order_id: str
        +seller_order_id: str
        +price: float
        +quantity: float
        +maker_fee: float
        +taker_fee: float
        +timestamp: datetime
    }

    OrderBook "1" o-- "*" Order : indexed in
    OrderBook ..> Trade : produces
```

### Algorithmic Complexity Matrix

| Operation | Data Structure | Time Complexity | Notes |
| :--- | :--- | :---: | :--- |
| **Best Price Lookup (BBO)** | `SortedDict.keys()[-1]` (Bids) / `[0]` (Asks) | $\mathcal{O}(1)$ | Immediate top-of-book pointer |
| **Order Insertion (Resting)** | `SortedDict` + `collections.deque` | $\mathcal{O}(\log P)$ | $P$ = unique price levels, $\mathcal{O}(1)$ queue push |
| **Order Cancellation** | `dict` (ID lookup) + `deque.remove()` | $\mathcal{O}(1)$ avg | Direct hash lookup + pointer drop |
| **Time-Priority Execution** | `collections.deque.popleft()` | $\mathcal{O}(1)$ | Strict FIFO queue consumption |
| **Trigger Evaluation** | In-Memory Filter List | $\mathcal{O}(K)$ | $K$ = active pending conditional orders |

---

## 7. Persistence Layer & Crash Recovery

The engine uses a non-blocking asynchronous snapshotter backed by **SQLite (WAL Mode)** to ensure durability without penalizing the hot matching path.

```mermaid
erDiagram
    ORDERS {
        TEXT order_id PK
        TEXT symbol
        TEXT side
        TEXT order_type
        REAL price
        REAL quantity
        REAL filled_quantity
        TEXT status
        REAL stop_price
        REAL limit_price
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    TRADES {
        TEXT trade_id PK
        TEXT symbol
        TEXT buyer_order_id FK
        TEXT seller_order_id FK
        REAL price
        REAL quantity
        REAL maker_fee
        REAL taker_fee
        TIMESTAMP executed_at
    }

    FEE_SCHEDULES {
        TEXT symbol PK
        REAL maker_rate
        REAL taker_rate
        TIMESTAMP updated_at
    }

    DEFAULT_FEE_RATES {
        INTEGER id PK
        REAL maker_rate
        REAL taker_rate
        TIMESTAMP updated_at
    }

    ORDERS ||--o{ TRADES : "participates in"
    FEE_SCHEDULES ||--o{ TRADES : "governs fees"
```

### Crash Recovery Protocol
1. **Engine Startup**: `PersistenceManager.load_state()` initiates.
2. **Schema Validation**: SQLite table indices and WAL journaling are verified.
3. **Reconstruct Active Books**:
   - Query all `OPEN` and `PARTIALLY_FILLED` orders ordered by `created_at ASC`.
   - Re-insert into respective `OrderBook` instances (rebuilding identical FIFO priority without re-triggering matches).
4. **Restore Conditional Pool**: Re-populate `pending_trigger_orders` with active stops/take-profits.
5. **Fee Cache Invalidation**: Populate `FeeModel` with persisted symbol-specific fee schedules.

---

## 8. Real-Time WebSocket Streaming Subsystem

Market data is broadcast over low-latency WebSockets with granular channel subscriptions:

```mermaid
flowchart LR
    subgraph Publisher ["Matching Core"]
        E_BBO["BBO Update"]
        E_Depth["L2 Book Depth"]
        E_Trade["Trade Execution"]
    end

    subgraph Broker ["WebSocket Subsystem (FastAPI)"]
        WS_Router["WebSocket Connection Handler"]
        Ch_BBO[("Channel: /ws/bbo")]
        Ch_Depth[("Channel: /ws/order-book")]
        Ch_Trades[("Channel: /ws/trades")]
    end

    subgraph Subscribers ["Connected Client Sockets"]
        ClientA["Algorithmic Trading Bot"]
        ClientB["Web Dashboard / UI"]
        ClientC["Analytics & Risk Engine"]
    end

    E_BBO --> Ch_BBO
    E_Depth --> Ch_Depth
    E_Trade --> Ch_Trades

    Ch_BBO --> WS_Router
    Ch_Depth --> WS_Router
    Ch_Trades --> WS_Router

    WS_Router -->|JSON Stream| ClientA
    WS_Router -->|JSON Stream| ClientB
    WS_Router -->|JSON Stream| ClientC
```

---

## 9. Performance & Concurrency Trade-Offs

### 1. In-Memory Execution vs. Disk I/O
- **Decision**: Keep the primary matching path 100% in-memory with periodic (60s) or shutdown-triggered SQLite flushes.
- **Rationale**: Disk I/O during order matching introduces unpredictable latency spikes. In-memory execution guarantees sub-millisecond execution.

### 2. Single-Threaded Core vs. Lock Contention
- **Decision**: Execute order matching synchronously per symbol while delegating API transport to asynchronous FastAPI coroutines.
- **Rationale**: Eliminates synchronization locks and mutex contention over order books, avoiding race conditions and deadlocks.

### 3. Price-Time Priority vs. Pro-Rata
- **Decision**: Strict Price-Time (FIFO) allocation adhering to REG NMS principles.
- **Rationale**: Protects limit order providers, eliminates front-running, and guarantees mathematical fairness in execution ordering.