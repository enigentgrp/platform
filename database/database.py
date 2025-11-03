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
        User, Role, Permission, RolePermission, GlobalEnvVar,
        MarketSegment, Stock, Account
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Initialize default data
    session = get_session()
    try:
        # Create default roles
        roles_data = [
            ('admin', 'Administrator with full access'),
            ('trader', 'Trader with trading permissions'),
            ('viewer', 'View-only access')
        ]
        
        roles = {}
        for role_name, role_desc in roles_data:
            existing_role = session.query(Role).filter(Role.name == role_name).first()
            if not existing_role:
                role = Role(name=role_name)
                session.add(role)
                session.flush()
                roles[role_name] = role
            else:
                roles[role_name] = existing_role
        
        session.commit()
        
        # Create default admin user if not exists
        admin_user = session.query(User).filter(User.username == 'admin').first()
        if not admin_user:
            from utils.auth import hash_password
            admin_role = session.query(Role).filter(Role.name == 'admin').first()
            admin_user = User(
                username='admin',
                email='admin@foundation.com',
                password_hash=hash_password('admin123'),
                role_id=admin_role.id if admin_role else None
            )
            session.add(admin_user)
        
        # Create default environment variables per trading algorithm requirements
        default_env_vars = [
            # Core trading settings
            ('TRADING_MODE', 'paper', 'str', 'Trading mode: paper or live'),
            ('BROKER_PLATFORM', 'robinhood', 'str', 'Primary broker: robinhood or alpaca'),
            ('DAY_TRADING_ENABLED', 'true', 'bool', 'Enable day trading strategies'),
            
            # Price monitoring
            ('PRICE_CHECK_INTERVAL', '5', 'int', 'Seconds between price checks during trading hours'),
            ('CONSECUTIVE_PERIODS', '3', 'int', 'Number of consecutive periods for trend confirmation'),
            ('PRICE_UPDATE_INTERVAL', '30', 'int', 'Seconds between price updates (legacy)'),
            
            # Cash allocation for options
            ('CASH_INVEST_OPTION_PCT', '10', 'pct', 'Max % of cash to invest in options per trade'),
            ('OPTION_PCT_BUY', '5', 'pct', 'Max % of available options to buy'),
            ('CASH_INVEST_STOCK_PCT', '15', 'pct', 'Max % of cash to invest in stocks per trade'),
            ('STOCK_PCT_SELL', '50', 'pct', 'Percentage of stock position to sell on signal'),
            
            # Risk management
            ('MOMENTUM_DECR_PCT', '25', 'pct', 'Momentum decrease % to trigger profit lock'),
            ('LOSS_PCT_LIMIT', '50', 'pct', 'Max % loss of earlier profit before exit'),
            ('MAX_POSITION_SIZE_PERCENT', '5', 'pct', 'Maximum single position size'),
            ('RISK_MANAGEMENT_ENABLED', 'true', 'bool', 'Enable risk management'),
            
            # End of day
            ('EOD_LIMIT', '15', 'int', 'Minutes before market close to exit day trades'),
            
            # Options criteria
            ('MIN_OPTIONS_VOL', '1000', 'int', 'Minimum daily volume for tradeable options'),
            ('OPT_STRIKE_PRICE_PCT_TARGET', '5', 'pct', 'Target % above/below current price for strike'),
            
            # Technical analysis
            ('TECHNICAL_ANALYSIS_PERIODS', '14', 'int', 'Periods for RSI and CCI calculations'),
            ('MOVING_AVERAGE_PERIOD', '21', 'int', 'Period for simple moving average'),
            ('BOLLINGER_BAND_SD', '2', 'int', 'Standard deviations for Bollinger Bands'),
            ('PRIORITY_SD_THRESHOLD', '1', 'int', 'SD threshold for priority stock flagging'),
        ]
        
        for name, value, value_type, description in default_env_vars:
            existing = session.query(GlobalEnvVar).filter(GlobalEnvVar.name == name).first()
            if not existing:
                env_var = GlobalEnvVar(
                    name=name,
                    value=value,
                    value_type=value_type,
                    description=description
                )
                session.add(env_var)
        
        # Create default market segments (including sector ETFs per trading algorithm spec)
        segments_data = [
            ('sp500', 'S&P 500'),
            ('technology', 'Technology Sector'),
            ('healthcare', 'Healthcare Sector'),
            ('financials', 'Financial Sector'),
            ('energy', 'Energy Sector'),
            ('materials', 'Materials Sector'),
            ('industrials', 'Industrials Sector'),
            ('consumer_discretionary', 'Consumer Discretionary'),
            ('consumer_staples', 'Consumer Staples'),
            ('communication', 'Communication Services'),
            ('utilities', 'Utilities Sector'),
            ('real_estate', 'Real Estate Sector'),
        ]
        
        segments = {}
        for slug, name in segments_data:
            existing = session.query(MarketSegment).filter(MarketSegment.slug == slug).first()
            if not existing:
                segment = MarketSegment(slug=slug, name=name)
                session.add(segment)
                session.flush()
                segments[slug] = segment
            else:
                segments[slug] = existing
        
        # Initialize sector ETFs (per trading algorithm spec - always monitored with priority 9)
        sector_etfs = [
            {'symbol': 'XLE', 'name': 'Energy Select Sector SPDR Fund', 'segment': 'energy'},
            {'symbol': 'XLB', 'name': 'Materials Select Sector SPDR Fund', 'segment': 'materials'},
            {'symbol': 'XLI', 'name': 'Industrial Select Sector SPDR Fund', 'segment': 'industrials'},
            {'symbol': 'XLY', 'name': 'Consumer Discretionary Select Sector SPDR Fund', 'segment': 'consumer_discretionary'},
            {'symbol': 'XLP', 'name': 'Consumer Staples Select Sector SPDR Fund', 'segment': 'consumer_staples'},
            {'symbol': 'XLV', 'name': 'Health Care Select Sector SPDR Fund', 'segment': 'healthcare'},
            {'symbol': 'XLF', 'name': 'Financial Select Sector SPDR Fund', 'segment': 'financials'},
            {'symbol': 'XLK', 'name': 'Technology Select Sector SPDR Fund', 'segment': 'technology'},
            {'symbol': 'XLC', 'name': 'Communication Services Select Sector SPDR Fund', 'segment': 'communication'},
            {'symbol': 'XLU', 'name': 'Utilities Select Sector SPDR Fund', 'segment': 'utilities'},
            {'symbol': 'XLRE', 'name': 'Real Estate Select Sector SPDR Fund', 'segment': 'real_estate'},
        ]
        
        # Initialize sample S&P 500 stocks with actively traded options
        sample_stocks = [
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'shares_outstanding': 15000000000, 'segment': 'technology'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'shares_outstanding': 7500000000, 'segment': 'technology'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'shares_outstanding': 6000000000, 'segment': 'technology'},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'shares_outstanding': 10000000000, 'segment': 'technology'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'shares_outstanding': 3000000000, 'segment': 'technology'},
            {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'shares_outstanding': 2500000000, 'segment': 'technology'},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'shares_outstanding': 2500000000, 'segment': 'technology'},
            {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'shares_outstanding': 3000000000, 'segment': 'financials'},
            {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'shares_outstanding': 2500000000, 'segment': 'healthcare'},
            {'symbol': 'V', 'name': 'Visa Inc.', 'shares_outstanding': 2000000000, 'segment': 'financials'}
        ]
        
        # Combine ETFs and stocks for insertion
        all_stocks = sector_etfs + sample_stocks
        
        for stock_data in all_stocks:
            existing = session.query(Stock).filter(Stock.symbol == stock_data['symbol']).first()
            if not existing:
                segment_slug = stock_data.pop('segment')
                segment = segments.get(segment_slug)
                stock = Stock(
                    **stock_data,
                    market_segment_id=segment.id if segment else None,
                    is_active=True
                )
                session.add(stock)
        
        session.commit()
        print("✅ Database initialized successfully with new schema")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error initializing database: {e}")
        raise e
    finally:
        session.close()
