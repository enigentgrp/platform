# Overview

This is an algorithmic trading platform for stocks and stock options built with Streamlit for the web interface and SQLAlchemy for database management. The platform supports multiple users with role-based permissions, integrates with multiple brokers (RobinHood and Alpaca), and provides automated trading capabilities based on technical indicators. The system focuses on S&P 500 stocks with actively traded options and uses momentum-based trading strategies for both call and put options.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (August 2025)

## Navigation System Improvements
- Removed duplicate upper navigation caused by Streamlit's automatic pages/ directory detection
- Moved page files from pages/ to app_pages/ directory to prevent automatic navigation
- Implemented clean sidebar navigation with radio buttons instead of selectbox
- Fixed all deprecated styling warnings (applymap → map) across all pages

## Database and Technical Fixes
- Switched from PostgreSQL to SQLite for better stability and reduced connection issues
- Added comprehensive sample data with 10 major stocks (AAPL, MSFT, TSLA, etc.) including realistic prices
- Fixed options trading interface errors by handling null price values properly
- Implemented manual technical indicator calculations to replace ta-lib dependency issues
- Set all sample stocks with has_options=True and priority=1 for testing

## Application Status
- All navigation issues resolved - only sidebar navigation remains
- Options trading interface functional with proper error handling
- Database initialization includes admin user (admin/admin123) and sample market data
- All deprecation warnings eliminated from the codebase

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