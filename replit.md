# Overview

This is Foundation - an algorithmic trading platform for stocks and stock options built with Streamlit for the web interface and SQLAlchemy for database management. The platform supports multiple users with role-based permissions, integrates with multiple brokers (RobinHood and Alpaca), and provides automated trading capabilities based on technical indicators. The system focuses on S&P 500 stocks with actively traded options and uses momentum-based trading strategies for both call and put options.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (August 2025)

## Foundation Platform Updates (Latest - August 2025)
- **Rebranded to Foundation**: Changed platform name with Jesus background and beautiful button styling
- **Enhanced Visual Design**: Custom CSS with gradient buttons, holy theme, and spiritual aesthetics
- **Completely Streamlined Interface**: Removed all extra features not in original requirements
- **Core Navigation Only**: Trading, Orders, Positions (admin gets Settings and Database access)
- **Simplified Authentication**: Basic login with role-based access (admin/trader/viewer roles preserved)
- **Focus on Requirements**: Strictly following original document specifications
- **Trader Broker Access**: Traders can now switch broker platforms in Settings page
- **Core Functionality Preserved**: All algorithmic trading logic, database tables, broker APIs remain intact
- **Clean Code**: Streamlined app.py with only essential functions matching requirements

## Essential Features Maintained
- **Trading Engine**: Start/stop controls for algorithmic trading system
- **Priority Stocks**: Display stocks with priority > 0 as specified in requirements  
- **Orders Table**: Complete order history with asset type, quantities, bid/ask, timestamps
- **Transaction Log**: LIFO gain/loss calculations as specified
- **Environment Variables**: Core trading configuration (paper/live mode, intervals, position sizing)
- **Database Access**: Admin users can access database management interface
- **Multi-broker Support**: RobinHood and Alpaca API integration preserved
- **Broker Switching**: Traders can switch broker platforms in Settings (admins get full config access)

## AI-Powered Features (Removed)
- AI Assistant feature removed per user request

## Application Status (Fully Operational)
- ✅ Authentication system working with proper credentials and role-based access control
- ✅ Three-tier user system: Admin (full access), Trader (trading enabled), Viewer (read-only)
- ✅ All major pages functional with appropriate permission checks
- ✅ Database Admin accessible to admin users with comprehensive interface
- ✅ Trading page properly blocked for viewer accounts with clear access denial messages
- ✅ Portfolio page shows read-only mode for viewers while maintaining full functionality for traders
- ✅ Settings page dynamically adjusts tabs based on user role permissions
- ✅ Options trading calculations fixed for decimal/float compatibility
- ✅ Broker configuration supporting both stock and options trading fees
- ✅ Complete database structure with priority system and technical indicators
- ✅ Performance analysis and transaction history working correctly

# Database Schema & Entity Relationship Diagram

## Entity Overview (9 Core Entities)

The database follows a carefully designed Entity Relationship model with 9 core entities:

| Entity | Table Name | Type | Description |
|--------|------------|------|-------------|
| 1. Global Environment Variables | `environment_variables` | Configuration | System-wide configs like market hours, trading mode |
| 2. Brokerage Info | `brokerage_info` | Static Reference | Broker metadata (Alpaca, Robinhood, etc.) |
| 3. Accounts | `accounts` | User/Trading | Individual brokerage accounts per user |
| 4. Stock Demographics | `stocks` | Reference Data | Company details, sector, market cap |
| 5. Stock Price History | `stock_price_history` | Time-series | Historical OHLCV data with technical indicators |
| 6. Priority Archive Price | `priority_archive_price` | Derived | Archived analytics snapshots for priority stocks |
| 7. Priority Current Price | `priority_current_price` | Live Data | Real-time computed metrics per priority stock |
| 8. Orders | `orders` | Trading | Buy/sell requests placed by accounts |
| 9. Transaction Log | `transaction_log` | Audit/Record | Execution details with LIFO gain/loss |

## Entity Relationship Map

```
GlobalEnv (environment_variables)
  ↓ (used globally by all entities)

BrokerageInfo (brokerage_info) ──1:N── Accounts (accounts)
                                          │
                                          ├──1:N── Orders (orders) ──1:N── Transactions (transaction_log)
                                          │           │                        │
                                          └──1:N──────┘                        │
                                                      │                        │
                                                      ↓                        ↓
                                          Stock (stocks) ──────────────────────┘
                                              │
                                              ├──1:N── PriceHistory (stock_price_history)
                                              ├──1:N── PriorityArchive (priority_archive_price)
                                              └──1:1── PriorityCurrent (priority_current_price)
```

## Detailed Relationships

### Primary Relationships

1. **BrokerageInfo → Accounts** (1:Many)
   - One broker can have many user accounts
   - Foreign Key: `accounts.brokerage_id` → `brokerage_info.id`
   - Cascade: RESTRICT (cannot delete broker if accounts exist)

2. **Accounts → Orders** (1:Many)
   - Each account places many orders
   - Foreign Key: `orders.account_id` → `accounts.id`
   - Cascade: RESTRICT (cannot delete account with existing orders)

3. **Orders → TransactionLog** (1:Many)
   - Each order results in one or more transactions
   - Foreign Key: `transaction_log.order_id` → `orders.id`
   - Cascade: CASCADE (deleting order removes its transactions)

4. **Accounts → TransactionLog** (1:Many)
   - Transactions are logged under the account
   - Foreign Key: `transaction_log.account_id` → `accounts.id`
   - Cascade: RESTRICT (cannot delete account with transaction history)

### Stock-Related Relationships

5. **Stock → StockPriceHistory** (1:Many)
   - Each stock has many daily price records
   - Foreign Key: `stock_price_history.stock_id` → `stocks.id`
   - Cascade: CASCADE (deleting stock removes its history)

6. **Stock → PriorityArchivePrice** (1:Many)
   - Each stock can have archived analytics
   - Foreign Key: `priority_archive_price.stock_id` → `stocks.id`
   - Cascade: CASCADE (deleting stock removes archives)

7. **Stock → PriorityCurrentPrice** (1:1)
   - One current "priority" value per stock
   - Foreign Key: `priority_current_price.stock_id` → `stocks.id`
   - Cascade: CASCADE (deleting stock removes current price)

### Trading Relationships

8. **Orders → Stock** (Many:1)
   - Each order targets one stock
   - Foreign Key: `orders.stock_id` → `stocks.id`
   - Cascade: RESTRICT (cannot delete stock with open orders)

9. **TransactionLog → Stock** (Many:1)
   - Each trade involves one stock
   - Foreign Key: `transaction_log.stock_id` → `stocks.id`
   - Cascade: RESTRICT (cannot delete stock with transaction history)

10. **Users → Orders** (1:Many)
    - Each user creates many orders
    - Foreign Key: `orders.user_id` → `users.id`
    - Cascade: RESTRICT

11. **Users → TransactionLog** (1:Many)
    - Each user has transaction history
    - Foreign Key: `transaction_log.user_id` → `users.id`
    - Cascade: RESTRICT

## Database Schema Flow

1. **System Level**: GlobalEnv defines system-wide configurations
2. **Broker Level**: BrokerageInfo contains broker details and credentials
3. **Account Level**: Accounts belong to brokers and users
4. **Trading Level**: Orders originate from accounts targeting stocks
5. **Execution Level**: Transactions record actual trade executions
6. **Analytics Level**: Stock data feeds price history and priority calculations

## Key Design Principles

- **Data Integrity**: Foreign keys with appropriate cascade behaviors ensure referential integrity
- **Performance**: Composite indexes on frequently queried fields (symbol + date, user + symbol)
- **Audit Trail**: Transaction log preserves complete trading history with LIFO calculations
- **Flexibility**: Priority system allows dynamic stock monitoring without schema changes
- **Scalability**: Separate tables for current vs archived priority data optimizes queries

# System Architecture

## Frontend Architecture
- **Streamlit Web Interface**: Multi-page application with role-based access control
- **Page Structure**: Organized into dedicated modules (dashboard, trading, portfolio, admin, settings)

- **Real-time Updates**: Live price monitoring and trading dashboard with auto-refresh capabilities
- **Responsive Design**: Wide layout with expandable sidebar for navigation

## Backend Architecture
- **SQLAlchemy ORM**: Database abstraction layer with declarative models
- **Modular Services**: Separated concerns into distinct service layers (data fetching, trading engine, technical indicators)
- **Broker Abstraction**: Generic broker API interface with specific implementations for different brokers
- **Authentication System**: Role-based user management with hashed passwords and session management

## Data Storage Solutions
- **Primary Database**: SQLite with WAL mode for concurrent access
- **Database Models**: Comprehensive schema including users, environment variables, brokerage info, accounts, stocks, price history, orders, and transaction logs
- **Price Data Management**: Dual-table approach with current prices and archived historical data
- **Configuration Storage**: Environment variables stored in database for runtime configuration

## Authentication and Authorization
- **User Roles**: Three-tier system (admin, trader, viewer) with hierarchical permissions
- **Password Security**: SHA-256 hashing with salt for secure password storage
- **Session Management**: Streamlit session state for user authentication persistence
- **Permission Checks**: Role-based access control for different application features

## Trading Engine Architecture
- **Algorithmic Strategy**: Momentum-based trading using directional price movements
- **Technical Indicators**: TA-Lib integration for ADX, DMI, moving averages, and pivot points
- **Risk Management**: Position sizing based on account balance and configurable risk parameters
- **Order Management**: Complete order lifecycle tracking with LIFO gain/loss calculations

# External Dependencies

## Broker APIs
- **Alpaca Trading API**: Primary broker integration for live and paper trading
- **RobinHood API**: Secondary broker support with modular implementation
- **Yahoo Finance (yfinance)**: Market data fetching for S&P 500 stocks and price history

## Market Data Sources
- **Wikipedia S&P 500 List**: Automated fetching of current S&P 500 constituents
- **Real-time Price Feeds**: Broker APIs for live price data and order execution
- **Options Data**: Broker-provided options chain data for tradeable options identification

## Technical Analysis
- **TA-Lib**: Technical analysis library for indicators (ADX, DMI, SMA, standard deviation)
- **NumPy/Pandas**: Data manipulation and numerical calculations for trading algorithms
- **Plotly**: Interactive charting for price analysis and portfolio visualization

## Infrastructure
- **SQLAlchemy**: Database ORM with SQLite backend (configurable for PostgreSQL)
- **Streamlit**: Web application framework with built-in session management
- **AsyncIO**: Asynchronous operations for concurrent price monitoring and trading execution
- **Threading**: Background processes for continuous market monitoring

## Development and Deployment
- **Environment Configuration**: Database-stored configuration variables for runtime flexibility
- **Logging**: Structured logging for trading operations and system monitoring
- **Error Handling**: Comprehensive exception handling for broker API failures and market disruptions