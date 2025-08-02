import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlite3

# Database configuration - Force SQLite for stability
DATABASE_URL = "sqlite:///trading_platform.db"

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 20
        },
        poolclass=StaticPool,
        echo=False
    )
    
    # Enable WAL mode for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
else:
    engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_session():
    """Get database session"""
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise

def init_database():
    """Initialize database and create tables"""
    from database.models import (
        User, EnvironmentVariable, BrokerageInfo, Account, 
        Stock, StockPriceHistory, PriorityCurrentPrice, 
        PriorityArchivePrice, Order, TransactionLog
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Initialize default data
    session = get_session()
    try:
        # Create default admin user if not exists
        admin_user = session.query(User).filter(User.username == 'admin').first()
        if not admin_user:
            from utils.auth import hash_password
            admin_user = User(
                username='admin',
                email='admin@trading.com',
                password_hash=hash_password('admin123'),
                role='admin',
                is_active=True
            )
            session.add(admin_user)
        
        # Create default environment variables
        default_env_vars = {
            'TRADING_MODE': 'paper',  # paper or live
            'ACTIVE_BROKER': 'alpaca',
            'PRICE_UPDATE_INTERVAL': '30',  # seconds
            'ARCHIVE_RETENTION_DAYS': '30',
            'MAX_POSITION_SIZE_PERCENT': '5',
            'RISK_MANAGEMENT_ENABLED': 'true',
            'TECHNICAL_ANALYSIS_PERIODS': '14'
        }
        
        for key, value in default_env_vars.items():
            existing = session.query(EnvironmentVariable).filter(
                EnvironmentVariable.key == key
            ).first()
            if not existing:
                env_var = EnvironmentVariable(
                    key=key,
                    value=value,
                    description=f'Default {key.lower().replace("_", " ")}'
                )
                session.add(env_var)
        
        # Create default brokerage info
        brokers = [
            {
                'name': 'Alpaca',
                'api_url': 'https://paper-api.alpaca.markets',
                'trading_fees': 0.0,
                'day_trade_limit': 3,
                'is_active': True
            },
            {
                'name': 'Robinhood',
                'api_url': 'https://robinhood.com/api',
                'trading_fees': 0.0,
                'day_trade_limit': 3,
                'is_active': False
            }
        ]
        
        for broker_data in brokers:
            existing = session.query(BrokerageInfo).filter(
                BrokerageInfo.name == broker_data['name']
            ).first()
            if not existing:
                broker = BrokerageInfo(**broker_data)
                session.add(broker)
        
        # Initialize S&P 500 stocks with sample data
        sample_stocks = [
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology', 'industry': 'Consumer Electronics', 'market_cap': 3000000000000},
            {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology', 'industry': 'Software', 'market_cap': 2800000000000},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Communication Services', 'industry': 'Internet Services', 'market_cap': 1800000000000},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'sector': 'Consumer Discretionary', 'industry': 'E-commerce', 'market_cap': 1600000000000},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'sector': 'Consumer Discretionary', 'industry': 'Electric Vehicles', 'market_cap': 800000000000},
            {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'sector': 'Communication Services', 'industry': 'Social Media', 'market_cap': 900000000000},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'Technology', 'industry': 'Semiconductors', 'market_cap': 2200000000000},
            {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'sector': 'Financials', 'industry': 'Banking', 'market_cap': 500000000000},
            {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'sector': 'Healthcare', 'industry': 'Pharmaceuticals', 'market_cap': 450000000000},
            {'symbol': 'V', 'name': 'Visa Inc.', 'sector': 'Financials', 'industry': 'Payment Processing', 'market_cap': 520000000000}
        ]
        
        for stock_data in sample_stocks:
            existing = session.query(Stock).filter(Stock.symbol == stock_data['symbol']).first()
            if not existing:
                stock = Stock(**stock_data, priority=0, has_options=True)
                session.add(stock)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
