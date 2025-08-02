"""
Database initialization script with exact specifications from requirements.
Populates tables with:
1. Environment variables for trading configuration
2. Sector ETFs with priority=9  
3. Sample brokerage info for RobinHood and Alpaca
4. Sample accounts and users
5. S&P 500 stocks with actively traded options
"""

import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker
from database.database import engine, Base
from database.models import (
    User, EnvironmentVariable, BrokerageInfo, Account, Stock,
    StockPriceHistory, PriorityCurrentPrice, Order, TransactionLog
)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_environment_variables(session):
    """Initialize global environment variables for trading configuration"""
    env_vars = [
        # Core trading configuration
        ("TRADING_MODE", "paper", "Trading mode: paper or live", "string", True),
        ("ACTIVE_BROKER", "Alpaca", "Currently active broker", "string", True),
        ("ACTIVE_ACCOUNT", "1", "ID of active trading account", "integer", True),
        
        # Price monitoring configuration
        ("PRICE_UPDATE_INTERVAL", "30", "Seconds between priority price updates", "integer", False),
        ("ARCHIVE_RETENTION_DAYS", "30", "Days to keep priority archive data", "integer", False),
        
        # Priority calculation parameters
        ("PRIORITY_PERCENTAGE_TARGET", "2.5", "% threshold for priority calculation", "float", False),
        ("PRIORITY_EVALUATION_PERIODS", "3", "Periods for priority evaluation logic", "integer", False),
        
        # Risk management
        ("MAX_POSITION_SIZE", "1000", "Maximum position size per trade", "integer", False),
        ("MAX_DAILY_TRADES", "10", "Maximum number of trades per day", "integer", False),
        ("STOP_LOSS_PERCENTAGE", "5.0", "Default stop loss percentage", "float", False),
        ("TAKE_PROFIT_PERCENTAGE", "10.0", "Default take profit percentage", "float", False),
        
        # Technical indicators
        ("ADX_THRESHOLD", "25", "ADX threshold for trend strength", "integer", False),
        ("RSI_OVERSOLD", "30", "RSI oversold threshold", "integer", False),
        ("RSI_OVERBOUGHT", "70", "RSI overbought threshold", "integer", False),
        ("MACD_FAST_PERIOD", "12", "MACD fast EMA period", "integer", False),
        ("MACD_SLOW_PERIOD", "26", "MACD slow EMA period", "integer", False),
        ("MACD_SIGNAL_PERIOD", "9", "MACD signal line period", "integer", False),
        
        # Market hours
        ("MARKET_OPEN_HOUR", "9", "Market open hour (EST)", "integer", True),
        ("MARKET_OPEN_MINUTE", "30", "Market open minute", "integer", True),
        ("MARKET_CLOSE_HOUR", "16", "Market close hour (EST)", "integer", True),
        ("MARKET_CLOSE_MINUTE", "0", "Market close minute", "integer", True),
    ]
    
    for key, value, description, var_type, is_system in env_vars:
        existing = session.query(EnvironmentVariable).filter(EnvironmentVariable.key == key).first()
        if not existing:
            env_var = EnvironmentVariable(
                key=key,
                value=value,
                description=description,
                variable_type=var_type,
                is_system=is_system
            )
            session.add(env_var)
    
    print("✓ Environment variables initialized")

def init_sector_etfs(session):
    """Initialize sector ETFs with priority=9 as specified"""
    sector_etfs = [
        ("XLE", "Energy Select Sector SPDR Fund", "Energy"),
        ("XLB", "Materials Select Sector SPDR Fund", "Materials"),
        ("XLI", "Industrial Select Sector SPDR Fund", "Industrials"),
        ("XLY", "Consumer Discretionary Select Sector SPDR Fund", "Consumer Discretionary"),
        ("XLP", "Consumer Staples Select Sector SPDR Fund", "Consumer Staples"),
        ("XLV", "Health Care Select Sector SPDR Fund", "Healthcare"),
        ("XLF", "Financial Select Sector SPDR Fund", "Financials"),
        ("XLK", "Technology Select Sector SPDR Fund", "Information Technology"),
        ("XLC", "Communication Services Select Sector SPDR Fund", "Communication Services"),
        ("XLU", "Utilities Select Sector SPDR Fund", "Utilities"),
        ("XLRE", "Real Estate Select Sector SPDR Fund", "Real Estate")
    ]
    
    for symbol, name, sector in sector_etfs:
        existing = session.query(Stock).filter(Stock.symbol == symbol).first()
        if not existing:
            stock = Stock(
                symbol=symbol,
                name=name,
                sector=sector,
                industry="ETF",
                market_cap=0,  # ETFs don't have market cap
                priority=9,  # Sector ETFs always have priority 9
                has_options=True,
                is_sp500=False,
                is_sector_etf=True,
                last_price=50.00,  # Sample price
                change_percent=0.0
            )
            session.add(stock)
    
    print("✓ Sector ETFs initialized with priority=9")

def init_brokerages(session):
    """Initialize brokerage information for RobinHood and Alpaca"""
    brokerages = [
        {
            "name": "Alpaca",
            "api_url": "https://paper-api.alpaca.markets",
            "trading_fees_per_share": 0.0,
            "trading_fees_per_contract": 0.65,
            "day_trade_limit": 3,
            "max_day_trade_buying_power": 25000.0,
            "supports_options": True,
            "supports_crypto": True,
            "is_active": True
        },
        {
            "name": "RobinHood",
            "api_url": "https://robinhood.com/api",
            "trading_fees_per_share": 0.0,
            "trading_fees_per_contract": 0.0,
            "day_trade_limit": 3,
            "max_day_trade_buying_power": 25000.0,
            "supports_options": True,
            "supports_crypto": True,
            "is_active": False
        }
    ]
    
    for broker_data in brokerages:
        existing = session.query(BrokerageInfo).filter(BrokerageInfo.name == broker_data["name"]).first()
        if not existing:
            broker = BrokerageInfo(**broker_data)
            session.add(broker)
    
    print("✓ Brokerage information initialized")

def init_accounts(session):
    """Initialize sample trading accounts"""
    # Get Alpaca brokerage
    alpaca = session.query(BrokerageInfo).filter(BrokerageInfo.name == "Alpaca").first()
    robinhood = session.query(BrokerageInfo).filter(BrokerageInfo.name == "RobinHood").first()
    
    accounts_data = [
        {
            "brokerage_id": alpaca.id if alpaca else 1,
            "account_name": "Paper Trading Account",
            "account_type": "margin",
            "total_balance": 100000.0,
            "cash_balance": 50000.0,
            "is_active": True
        },
        {
            "brokerage_id": robinhood.id if robinhood else 2,
            "account_name": "Demo Account",
            "account_type": "cash",
            "total_balance": 25000.0,
            "cash_balance": 25000.0,
            "is_active": False
        }
    ]
    
    for account_data in accounts_data:
        existing = session.query(Account).filter(
            Account.brokerage_id == account_data["brokerage_id"],
            Account.account_name == account_data["account_name"]
        ).first()
        if not existing:
            account = Account(**account_data)
            session.add(account)
    
    print("✓ Trading accounts initialized")

def init_sample_sp500_stocks(session):
    """Initialize sample S&P 500 stocks with actively traded options"""
    # Major S&P 500 stocks with high options activity
    sp500_stocks = [
        ("AAPL", "Apple Inc.", "Information Technology", "Consumer Electronics", 3000000000000),
        ("MSFT", "Microsoft Corporation", "Information Technology", "Software", 2800000000000),
        ("GOOGL", "Alphabet Inc.", "Communication Services", "Internet Content & Information", 1700000000000),
        ("AMZN", "Amazon.com Inc.", "Consumer Discretionary", "Internet & Direct Marketing Retail", 1500000000000),
        ("TSLA", "Tesla Inc.", "Consumer Discretionary", "Automobiles", 800000000000),
        ("NVDA", "NVIDIA Corporation", "Information Technology", "Semiconductors", 2200000000000),
        ("META", "Meta Platforms Inc.", "Communication Services", "Interactive Media & Services", 900000000000),
        ("JPM", "JPMorgan Chase & Co.", "Financials", "Banks", 500000000000),
        ("V", "Visa Inc.", "Information Technology", "Data Processing & Outsourced Services", 450000000000),
        ("JNJ", "Johnson & Johnson", "Healthcare", "Pharmaceuticals", 400000000000),
        ("WMT", "Walmart Inc.", "Consumer Staples", "Hypermarkets & Super Centers", 420000000000),
        ("PG", "Procter & Gamble Co.", "Consumer Staples", "Household Products", 380000000000),
        ("UNH", "UnitedHealth Group Inc.", "Healthcare", "Managed Health Care", 480000000000),
        ("HD", "Home Depot Inc.", "Consumer Discretionary", "Home Improvement Retail", 350000000000),
        ("MA", "Mastercard Inc.", "Information Technology", "Data Processing & Outsourced Services", 360000000000),
        ("DIS", "Walt Disney Co.", "Communication Services", "Movies & Entertainment", 200000000000),
        ("NFLX", "Netflix Inc.", "Communication Services", "Movies & Entertainment", 180000000000),
        ("BAC", "Bank of America Corp.", "Financials", "Banks", 320000000000),
        ("XOM", "Exxon Mobil Corporation", "Energy", "Integrated Oil & Gas", 280000000000),
        ("KO", "Coca-Cola Co.", "Consumer Staples", "Soft Drinks", 260000000000)
    ]
    
    import random
    
    for symbol, name, sector, industry, market_cap in sp500_stocks:
        existing = session.query(Stock).filter(Stock.symbol == symbol).first()
        if not existing:
            # Generate realistic sample price and change
            base_price = random.uniform(50, 400)
            change_pct = random.uniform(-3.0, 3.0)
            
            stock = Stock(
                symbol=symbol,
                name=name,
                sector=sector,
                industry=industry,
                market_cap=market_cap,
                priority=1,  # Set all to priority 1 for testing
                has_options=True,
                is_sp500=True,
                is_sector_etf=False,
                last_price=round(base_price, 2),
                change_percent=round(change_pct, 2),
                volume=random.randint(1000000, 50000000),
                avg_volume=random.randint(500000, 25000000)
            )
            session.add(stock)
    
    print("✓ S&P 500 stocks with options initialized")

def init_users(session):
    """Initialize admin and sample users"""
    users_data = [
        {
            "username": "admin",
            "email": "admin@trading.local",
            "password": "admin123",
            "role": "admin"
        },
        {
            "username": "trader1",
            "email": "trader1@trading.local", 
            "password": "trader123",
            "role": "trader"
        },
        {
            "username": "viewer1",
            "email": "viewer1@trading.local",
            "password": "viewer123", 
            "role": "viewer"
        }
    ]
    
    for user_data in users_data:
        existing = session.query(User).filter(User.username == user_data["username"]).first()
        if not existing:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=hash_password(user_data["password"]),
                role=user_data["role"],
                is_active=True
            )
            session.add(user)
    
    print("✓ Users initialized")

def init_database():
    """Initialize entire database with exact specifications"""
    print("🔄 Initializing database with exact specifications...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")
    
    # Create session
    session = SessionLocal()
    
    try:
        # Initialize all data
        init_environment_variables(session)
        init_sector_etfs(session)
        init_brokerages(session)
        init_accounts(session)
        init_sample_sp500_stocks(session)
        init_users(session)
        
        # Commit all changes
        session.commit()
        print("✅ Database initialization completed successfully!")
        
        # Print summary
        print("\n📊 Database Summary:")
        print(f"   • Environment Variables: {session.query(EnvironmentVariable).count()}")
        print(f"   • Brokerages: {session.query(BrokerageInfo).count()}")
        print(f"   • Accounts: {session.query(Account).count()}")
        print(f"   • Stocks (Total): {session.query(Stock).count()}")
        print(f"   • Sector ETFs (Priority=9): {session.query(Stock).filter(Stock.priority == 9).count()}")
        print(f"   • S&P 500 Stocks (Priority=1): {session.query(Stock).filter(Stock.priority == 1).count()}")
        print(f"   • Users: {session.query(User).count()}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error initializing database: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    init_database()