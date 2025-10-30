# Overview

This is Foundation - an algorithmic trading platform featuring a **FastAPI REST backend** and **Streamlit frontend**. The platform has been migrated from a simpler database structure to a sophisticated architecture with **RBAC (Role-Based Access Control)**, **market segments** for stock categorization, and **stochastic indicators** for advanced technical analysis.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (October 2025)

## Major Architecture Migration (Latest - October 30, 2025)

### Database Schema Replacement
- **Migrated from 9-entity model to sophisticated RBAC structure**
- **New Core Entities**: Roles, Permissions, RolePermission, MarketSegment, PriceHistory, StochasticHistory
- **Replaced Models**: 
  - `EnvironmentVariable` → `GlobalEnvVar` (with market segment and stock-level overrides)
  - `StockPriceHistory` → `PriceHistory`
  - `PriorityCurrentPrice` → `PriorityStock` (with scoring system)
  - `TransactionLog` → `Trade`
  - Removed `BrokerageInfo` (integrated into external broker APIs)
- **Created Compatibility Layer**: `services/compatibility_layer.py` bridges old Streamlit UI with new schema
- **FastAPI Backend**: Running on port 8000 with JWT authentication and comprehensive API endpoints

### Key Features Added
- **RBAC System**: Fine-grained permission control with role-permission mapping
- **Market Segments**: Stocks categorized by market (sp500, technology, healthcare, financials)
- **Stochastic Indicators**: Advanced technical analysis with SMA, SD, RSI, MACD, K, D calculations
- **Three-Level Environment Variables**: Global, market segment-specific, and stock-specific configuration
- **FastAPI REST API**: Complete backend API with authentication, orders, positions, and market data endpoints
- **Compatibility Layer**: Allows gradual migration of Streamlit pages to new schema

### Technical Implementation
- **Database Initialization**: Successfully seeded with roles, permissions, market segments, and sample stocks
- **Workflows**: Both Streamlit (port 5000) and FastAPI (port 8000) running concurrently
- **Authentication**: Updated to use new User model with improved password hashing
- **API Endpoints**: 
  - `/auth/login` - JWT authentication
  - `/users/me` - Current user info
  - `/env/global` - Global environment variables (admin only)
  - `/stocks` - Stock listing with market segments
  - `/stocks/{symbol}/price_history` - Historical price data
  - `/stocks/{symbol}/options` - Options chains
  - `/orders` - Order placement and history
  - `/positions` - Position tracking
  - `/priority` - Priority stock recommendations

# Database Schema & Entity Relationship Diagram

## New Architecture (October 2025)

### Entity Overview (17 Core Entities)

The database now follows a normalized RBAC-based architecture:

| Entity | Table Name | Type | Description |
|--------|------------|------|-------------|
| **RBAC & Users** |
| 1. Roles | `roles` | Access Control | User role definitions (admin, trader, viewer) |
| 2. Permissions | `permissions` | Access Control | Permission definitions |
| 3. RolePermission | `role_permissions` | Join Table | Maps roles to permissions |
| 4. Users | `users` | Authentication | User accounts with role assignments |
| **Configuration** |
| 5. GlobalEnvVar | `global_env_vars` | Config | System-wide configuration |
| 6. MarketSegment | `market_segments` | Classification | Market segments (sp500, sectors) |
| 7. MarketSegmentEnvVar | `market_segment_env_vars` | Config | Segment-specific overrides |
| 8. StockEnvVar | `stock_env_vars` | Config | Stock-specific overrides |
| **Market Data** |
| 9. Stock | `stocks` | Reference | Stock metadata with market segment |
| 10. PriceHistory | `price_history` | Time-series | OHLCV data |
| 11. StochasticHistory | `stochastic_history` | Time-series | Technical indicators (SMA, RSI, MACD, K, D) |
| 12. OptionsChain | `options_chain` | Derivatives | Options contracts |
| 13. PriorityStock | `priority_stocks` | Analysis | Flagged stocks with scores |
| **Trading** |
| 14. Account | `accounts` | Trading | User trading accounts |
| 15. Position | `positions` | Trading | Current holdings |
| 16. Order | `orders` | Trading | Buy/sell orders |
| 17. Trade | `trades` | Audit | Executed transactions |
| **Jobs & Logging** |
| 18. NightlyJob | `nightly_jobs` | Batch | Scheduled job tracking |
| 19. ChangeLog | `change_log` | Audit | System change history |

## Entity Relationship Map (New Architecture)

```
┌─────────────────── RBAC Layer ───────────────────┐
│                                                   │
│  Role ──1:N── RolePermission ──N:1── Permission  │
│    │                                              │
│    └──1:N── User                                 │
│                 │                                 │
└─────────────────┼─────────────────────────────────┘
                  │
┌─────────────────┼──── Configuration Layer ────────┐
│                 │                                  │
│  GlobalEnvVar   │                                  │
│                 │                                  │
│  MarketSegment ─┼─1:N── MarketSegmentEnvVar       │
│       │         │                                  │
└───────┼─────────┼──────────────────────────────────┘
        │         │
┌───────┼─────────┼──── Market Data Layer ──────────┐
│       │         │                                  │
│       └─1:N─ Stock ──1:N── StockEnvVar            │
│                 │                                  │
│                 ├──1:N── PriceHistory             │
│                 ├──1:N── StochasticHistory        │
│                 ├──1:N── OptionsChain             │
│                 └──1:N── PriorityStock            │
│                                                    │
└────────────────────────────────────────────────────┘
                     │
┌────────────────────┼──── Trading Layer ────────────┐
│                    │                                │
│  User ──1:N── Account ──1:N── Position            │
│                    │         (Stock/Option)        │
│                    │                                │
│                    └──1:N── Order                  │
│                              │                      │
│                              └──1:N── Trade        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Key Design Principles

1. **RBAC First**: All access control managed through role-permission relationships
2. **Three-Level Configuration**: Global → Market Segment → Stock-specific overrides
3. **Normalized Market Data**: Separate tables for prices, stochastics, and options
4. **Trading Isolation**: Clear separation between orders (intent) and trades (execution)
5. **Audit Trail**: Complete history via trades and change log
6. **Scalability**: Indexed time-series data optimized for performance

# System Architecture

## Dual-Stack Architecture

### Frontend: Streamlit (Port 5000)
- **Multi-page Application**: Dashboard, Orders, Positions, Settings, Database Admin
- **Compatibility Layer**: `services/compatibility_layer.py` provides DTOs that map new models to legacy UI contracts
- **Role-Based Access**: Admin, Trader, Viewer with appropriate UI restrictions
- **Real-time Updates**: Live price monitoring and engine status
- **Beautiful Design**: Custom CSS with gradient buttons and spiritual theme

### Backend: FastAPI (Port 8000)
- **RESTful API**: Complete CRUD operations for all entities
- **JWT Authentication**: Secure token-based authentication
- **Role-Based Endpoints**: Admin-only endpoints for configuration
- **Pydantic Validation**: Request/response schema validation
- **Auto-Documentation**: Swagger UI at `/docs`

## Data Flow

```
User → Streamlit UI → Compatibility Layer → Database Models → SQLite/PostgreSQL
                                                            ↓
User → FastAPI → Pydantic Schemas → Database Models → SQLite/PostgreSQL
```

## Compatibility Layer Strategy

The compatibility layer (`services/compatibility_layer.py`) enables gradual migration:

1. **Legacy DTOs**: `LegacyStockView`, `LegacyOrderView`, `LegacyTradeView`, `LegacyEnvVar`
2. **Helper Functions**: `get_priority_stocks()`, `get_all_orders()`, `get_all_trades()`
3. **Derived Fields**: Calculates `last_price`, `change_percent`, `priority` from new schema
4. **Authentication**: `verify_user_password()` compatible with new User model

This approach allows:
- Streamlit UI to continue working during migration
- Incremental page rewrites to use new models directly
- No loss of functionality during transition
- Maintainable codebase with clear separation of concerns

# External Dependencies

## Broker APIs
- **Alpaca Trading API**: Primary broker integration for live and paper trading
- **RobinHood API**: Secondary broker support (via external API calls)

## Market Data Sources
- **Yahoo Finance (yfinance)**: Historical price data
- **Broker APIs**: Real-time quotes and options chains

## Technical Analysis
- **TA-Lib**: Technical indicators (pending integration with StochasticHistory)
- **NumPy/Pandas**: Data manipulation
- **Plotly**: Interactive charting

## Backend Framework
- **FastAPI**: Modern async Python API framework
- **Pydantic**: Data validation and serialization
- **PyJWT**: JSON Web Token authentication
- **Uvicorn**: ASGI server

## Infrastructure
- **SQLAlchemy**: Database ORM
- **Streamlit**: Web UI framework
- **SQLite**: Default database (PostgreSQL compatible)

# Development Guidelines

## Working with the New Schema

### Adding New Features
1. Define models in `database/models.py`
2. Create Pydantic schemas in `api/main.py`
3. Add API endpoints in `api/main.py`
4. Update compatibility layer if Streamlit UI needs access
5. Test both FastAPI and Streamlit interfaces

### Database Changes
1. **NEVER** manually write SQL migrations
2. Modify models in `database/models.py`
3. Delete `trading_platform.db`
4. Run `python3 -c "from database.database import init_database; init_database()"`
5. Restart both workflows

### Authentication
- FastAPI uses JWT tokens via `/auth/login`
- Streamlit uses session state with `verify_user_password()`
- Passwords hashed with SHA-256 + salt

### Testing
- FastAPI: `curl http://localhost:8000/endpoint`
- Streamlit: Access via webview on port 5000
- Both workflows must be running concurrently

## API Development Best Practices

1. **Use Role Checks**: `require_role(user, ["admin"])` for protected endpoints
2. **Validate Input**: Use Pydantic models for all requests
3. **Return Proper Status Codes**: 200, 201, 400, 401, 403, 404, 500
4. **Document Endpoints**: Add clear docstrings and response models
5. **Handle Errors**: Use try/except with proper error responses

## Migration Progress

### ✅ Completed
- Database schema replacement
- FastAPI backend setup
- Compatibility layer implementation
- Core Streamlit pages updated (app.py)
- Authentication system updated
- Both workflows running successfully

### 🚧 Pending
- Update remaining app_pages/* to use new models directly
- Integrate stochastic indicators into trading engine
- Add options trading endpoints to FastAPI
- Update broker APIs to work with new Account model
- Create admin UI for role/permission management
- Migrate trading engine to use new PriorityStock scoring

### 📝 Future Enhancements
- WebSocket support for real-time updates
- Redis caching layer
- PostgreSQL migration for production
- GraphQL API option
- Mobile-responsive UI
- Advanced charting with stochastic overlays
