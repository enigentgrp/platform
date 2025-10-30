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
        
        # Create default environment variables
        default_env_vars = [
            ('TRADING_MODE', 'paper', 'str', 'Trading mode: paper or live'),
            ('PRICE_UPDATE_INTERVAL', '30', 'int', 'Seconds between price updates'),
            ('MAX_POSITION_SIZE_PERCENT', '5', 'pct', 'Maximum position size as percentage'),
            ('RISK_MANAGEMENT_ENABLED', 'true', 'bool', 'Enable risk management'),
            ('TECHNICAL_ANALYSIS_PERIODS', '14', 'int', 'Periods for technical analysis'),
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
        
        # Create default market segments
        segments_data = [
            ('sp500', 'S&P 500'),
            ('technology', 'Technology Sector'),
            ('healthcare', 'Healthcare Sector'),
            ('financials', 'Financial Sector'),
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
        
        # Initialize sample stocks
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
        
        for stock_data in sample_stocks:
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
