# Overview

Foundation is an algorithmic trading platform with a FastAPI REST backend and a Streamlit frontend. It features a sophisticated architecture with Role-Based Access Control (RBAC), market segments for stock categorization, and advanced stochastic indicators for technical analysis. The platform aims to provide comprehensive algorithmic trading capabilities, including automated buying and selling based on predefined strategies and multi-broker support.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

The system employs a dual-stack architecture:

## Frontend: Streamlit (Port 5000)
-   **Multi-page Application**: Provides a user interface for Dashboard, Orders, Positions, Settings, and Database Admin.
-   **Compatibility Layer**: Utilizes `services/compatibility_layer.py` to map new database models to legacy UI contracts, enabling a gradual migration.
-   **Role-Based Access**: UI restrictions based on user roles (Admin, Trader, Viewer).
-   **Design**: Custom CSS with gradient buttons and a spiritual theme.

## Backend: FastAPI (Port 8000)
-   **RESTful API**: Offers CRUD operations for all entities.
-   **JWT Authentication**: Secure token-based authentication.
-   **Role-Based Endpoints**: Access control for sensitive operations.
-   **Pydantic Validation**: Ensures data integrity for requests and responses.
-   **Auto-Documentation**: Swagger UI available at `/docs`.

## Data Flow
User interactions with the Streamlit UI are processed through a compatibility layer, interacting with database models. Direct API calls via FastAPI are validated by Pydantic schemas before interacting with the database.

## Database Schema
The database has a normalized, RBAC-based architecture with 17 core entities, including:
-   **RBAC & Users**: Roles, Permissions, RolePermission, Users.
-   **Configuration**: GlobalEnvVar, MarketSegment, MarketSegmentEnvVar, StockEnvVar.
-   **Market Data**: Stock, PriceHistory, StochasticHistory, OptionsChain, PriorityStock.
-   **Trading**: Account, Position, Order, Trade.
-   **Jobs & Logging**: NightlyJob, ChangeLog.

### Key Design Principles
-   **RBAC First**: Access control managed via role-permission relationships.
-   **Three-Level Configuration**: Global, Market Segment, and Stock-specific overrides for environment variables.
-   **Normalized Market Data**: Separate tables for prices, stochastics, and options.
-   **Trading Isolation**: Clear separation between orders (intent) and trades (execution).
-   **Audit Trail**: Comprehensive history maintained through trades and change logs.

## Trading Algorithm Enhancements
-   **Strategy Rules**: Buy on upward momentum, sell/buy on downward trends.
-   **Parameters**: All trading parameters are stored in the database for dynamic adjustment.
-   **Multi-Broker Support**: Integration with RobinHood (primary) and Alpaca (secondary).
-   **Technical Indicators**: Expanded set of indicators including Wilder's DMI, Commodity Channel Index, Bollinger Bands, and Pivot Points, alongside existing SMA, SD, RSI, MACD, Stochastic K/D.
-   **Account Model**: Enhanced to include broker platform, encrypted credentials, day trade settings, minimum balance, and transaction fees.
-   **Sector ETF Integration**: Monitoring of 11 sector ETFs for market segment analysis.
-   **Priority Stock Identification**: Logic to flag stocks exceeding 1 SD from the 21-day moving average, monitored frequently.

# External Dependencies

## Broker APIs
-   **Alpaca Trading API**: For live and paper trading.
-   **RobinHood API**: For secondary broker support.

## Market Data Sources
-   **Yahoo Finance (yfinance)**: For historical price data.
-   **Broker APIs**: For real-time quotes and options chains.

## Technical Analysis
-   **TA-Lib**: For technical indicators.
-   **NumPy/Pandas**: For data manipulation.
-   **Plotly**: For interactive charting.

## Backend Framework
-   **FastAPI**: Asynchronous Python API framework.
-   **Pydantic**: Data validation and serialization.
-   **PyJWT**: JSON Web Token authentication.
-   **Uvicorn**: ASGI server.

## Infrastructure
-   **SQLAlchemy**: Database ORM.
-   **Streamlit**: Web UI framework.
-   **SQLite**: Default database (PostgreSQL compatible).