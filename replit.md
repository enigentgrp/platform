# Overview

This is an algorithmic trading platform for stocks and stock options built with Streamlit for the web interface and SQLAlchemy for database management. The platform supports multiple users with role-based permissions, integrates with multiple brokers (RobinHood and Alpaca), and provides automated trading capabilities based on technical indicators. The system focuses on S&P 500 stocks with actively traded options and uses momentum-based trading strategies for both call and put options.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (August 2025)

## Streamlined Application (Latest - August 2025)
- **Completely Streamlined Interface**: Removed all extra features not in original requirements
- **Core Navigation Only**: Trading, Orders, Positions (admin gets Settings and Database access)
- **Simplified Authentication**: Basic login with role-based access (admin/trader/viewer roles preserved)
- **Focus on Requirements**: Strictly following original document specifications
- **Removed Features**: AI Assistant, complex dashboards, unnecessary visualizations, and bloated interfaces
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