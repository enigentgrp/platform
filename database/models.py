from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index, SmallInteger, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.database import Base
import hashlib

class User(Base):
    """User table for authentication and role management"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='trader')  # admin, trader, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
    
    def check_password(self, password):
        """Check if provided password matches the stored hash"""
        try:
            # Handle both old and new password formats
            if ':' in self.password_hash:
                # New format with salt
                salt, hash_value = self.password_hash.split(':')
                return hashlib.sha256((password + salt).encode()).hexdigest() == hash_value
            else:
                # Old format for backward compatibility
                salted_password = f"{password}_trading_salt"
                password_hash = hashlib.sha256(salted_password.encode()).hexdigest()
                return self.password_hash == password_hash
        except Exception:
            return False

class EnvironmentVariable(Base):
    """Global environment variables for trading configuration"""
    __tablename__ = 'environment_variables'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text)
    variable_type = Column(String(50), default='string')  # string, integer, float, boolean
    is_system = Column(Boolean, default=False)  # System vs user configurable
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Add specific trading environment variables as per requirements
    # TRADING_MODE: paper/live
    # ACTIVE_BROKER: broker name
    # ACTIVE_ACCOUNT: account ID  
    # PRICE_UPDATE_INTERVAL: seconds for priority current price updates
    # ARCHIVE_RETENTION_DAYS: days to keep in priority archive
    # PRIORITY_PERCENTAGE_TARGET: % threshold for priority calculation
    # PRIORITY_EVALUATION_PERIODS: periods for evaluation

class BrokerageInfo(Base):
    """Brokerage information including login credentials, trading fees, day trade restrictions"""
    __tablename__ = 'brokerage_info'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)  # RobinHood, Alpaca, etc.
    api_url = Column(String(255), nullable=False)
    api_key = Column(String(255))  # Encrypted storage recommended
    api_secret = Column(String(255))  # Encrypted storage recommended
    username = Column(String(100))  # For brokers requiring username/password
    password_hash = Column(String(255))  # For brokers requiring username/password
    trading_fees_per_share = Column(Numeric(10, 4), default=0.0)
    trading_fees_per_contract = Column(Numeric(10, 4), default=0.0)
    day_trade_limit = Column(Integer, default=3)
    max_day_trade_buying_power = Column(Float)
    margin_requirements = Column(Text)  # JSON string for margin requirements
    is_active = Column(Boolean, default=True)
    supports_options = Column(Boolean, default=False)
    supports_crypto = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    accounts = relationship("Account", back_populates="brokerage")

class Account(Base):
    """Individual trading accounts at brokerages"""
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True, index=True)
    brokerage_id = Column(Integer, ForeignKey('brokerage_info.id'), nullable=False)
    account_name = Column(String(100), nullable=False)
    account_type = Column(String(50), nullable=False)  # cash, margin, ira
    total_balance = Column(Float, default=0.0)
    cash_balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    brokerage = relationship("BrokerageInfo", back_populates="accounts")

class Stock(Base):
    """Stock demographics - S&P 500 stocks with actively traded options + sector ETFs"""
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100), index=True)
    industry = Column(String(100))
    market_cap = Column(Float)
    priority = Column(SmallInteger, default=0, index=True)  # 0=normal, 1=priority, 9=sector ETF
    has_options = Column(Boolean, default=False, index=True)
    is_sp500 = Column(Boolean, default=False, index=True)
    is_sector_etf = Column(Boolean, default=False, index=True)
    last_price = Column(Numeric(10, 2))
    change_percent = Column(Numeric(8, 4))
    volume = Column(Integer)
    avg_volume = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    price_history = relationship("StockPriceHistory", back_populates="stock")
    priority_current_prices = relationship("PriorityCurrentPrice", back_populates="stock")
    priority_archive_prices = relationship("PriorityArchivePrice", back_populates="stock")
    orders = relationship("Order", back_populates="stock")

class StockPriceHistory(Base):
    """Stock price history with technical indicators - populated during off hours for past 90 days"""
    __tablename__ = 'stock_price_history'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    open_price = Column(Numeric(10, 2), nullable=False)
    high_price = Column(Numeric(10, 2), nullable=False)
    low_price = Column(Numeric(10, 2), nullable=False)
    close_price = Column(Numeric(10, 2), nullable=False)
    volume = Column(Integer)
    adjusted_close = Column(Numeric(10, 2))
    
    # Technical Indicators as per requirements
    # Wilder's Directional Movement Indicators
    adx = Column(Numeric(8, 4))  # Average Directional Index
    di_plus = Column(Numeric(8, 4))  # Directional Indicator +
    di_minus = Column(Numeric(8, 4))  # Directional Indicator -
    
    # Pivot Points
    pivot_point = Column(Numeric(10, 2))
    resistance_1 = Column(Numeric(10, 2))
    resistance_2 = Column(Numeric(10, 2))
    support_1 = Column(Numeric(10, 2))
    support_2 = Column(Numeric(10, 2))
    
    # 14-day Commodity Channel Index
    cci_14 = Column(Numeric(8, 4))
    
    # 20-day Bollinger Bands (2 standard deviations)
    bb_upper = Column(Numeric(10, 2))
    bb_middle = Column(Numeric(10, 2))  # 20-day SMA
    bb_lower = Column(Numeric(10, 2))
    bb_bandwidth = Column(Numeric(8, 4))
    
    # Additional common indicators
    sma_20 = Column(Numeric(10, 2))  # 20-day Simple Moving Average
    sma_50 = Column(Numeric(10, 2))  # 50-day Simple Moving Average
    ema_12 = Column(Numeric(10, 2))  # 12-day Exponential Moving Average
    ema_26 = Column(Numeric(10, 2))  # 26-day Exponential Moving Average
    rsi_14 = Column(Numeric(8, 4))   # 14-day Relative Strength Index
    macd = Column(Numeric(8, 4))     # MACD Line
    macd_signal = Column(Numeric(8, 4))  # MACD Signal Line
    macd_histogram = Column(Numeric(8, 4))  # MACD Histogram
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="price_history")
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_stock_date', 'stock_id', 'date'),
        Index('idx_symbol_date', 'symbol', 'date'),
    )

class PriorityCurrentPrice(Base):
    """Current price tracking for stocks with priority > 0, updated every X seconds"""
    __tablename__ = 'priority_current_price'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    price_at_open = Column(Numeric(10, 2))  # Price when market opened
    current_price = Column(Numeric(10, 2), nullable=False)
    percent_change_from_previous = Column(Numeric(8, 4))
    percent_change_from_open = Column(Numeric(8, 4))
    volume = Column(Integer)
    bid = Column(Numeric(10, 2))
    ask = Column(Numeric(10, 2))
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="priority_current_prices")
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_priority_symbol_datetime', 'symbol', 'datetime'),
        Index('idx_priority_stock_datetime', 'stock_id', 'datetime'),
    )

class PriorityArchivePrice(Base):
    """Archive for priority current prices, moved daily and purged after X days"""
    __tablename__ = 'priority_archive_price'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    price_at_open = Column(Numeric(10, 2))
    current_price = Column(Numeric(10, 2), nullable=False)
    percent_change_from_previous = Column(Numeric(8, 4))
    percent_change_from_open = Column(Numeric(8, 4))
    volume = Column(Integer)
    bid = Column(Numeric(10, 2))
    ask = Column(Numeric(10, 2))
    archived_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="priority_archive_prices")
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_archive_symbol_datetime', 'symbol', 'datetime'),
        Index('idx_archive_date', 'archived_date'),
    )

class Order(Base):
    """Orders table showing asset, action, quantity, bid, ask, limit, timedate, etc"""
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    
    # Order details
    order_type = Column(String(20), nullable=False)  # market, limit, stop, stop_limit
    action = Column(String(10), nullable=False, index=True)  # buy, sell, buy_to_open, sell_to_close
    asset_type = Column(String(20), default='stock')  # stock, option, crypto
    quantity = Column(Integer, nullable=False)
    
    # Pricing
    limit_price = Column(Numeric(10, 2))
    stop_price = Column(Numeric(10, 2))
    bid_price = Column(Numeric(10, 2))
    ask_price = Column(Numeric(10, 2))
    fill_price = Column(Numeric(10, 2))
    
    # Order status and timing
    status = Column(String(20), default='pending', index=True)  # pending, filled, cancelled, rejected
    time_in_force = Column(String(10), default='DAY')  # DAY, GTC, IOC, FOK
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    filled_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    
    # Broker information
    broker_order_id = Column(String(100), index=True)  # ID from broker system
    
    # Option-specific fields (nullable for stock orders)
    option_type = Column(String(10))  # call, put
    strike_price = Column(Numeric(10, 2))
    expiration_date = Column(DateTime(timezone=True))
    
    # Risk management
    estimated_fees = Column(Numeric(10, 4))
    actual_fees = Column(Numeric(10, 4))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    account = relationship("Account")
    stock = relationship("Stock", back_populates="orders")
    transactions = relationship("TransactionLog", back_populates="order")
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_order_user_symbol', 'user_id', 'symbol'),
        Index('idx_order_status_submitted', 'status', 'submitted_at'),
        Index('idx_order_symbol_action', 'symbol', 'action'),
    )

class TransactionLog(Base):
    """Transaction log showing order ID, asset, timedate, quantity, price, LIFO gain/loss"""
    __tablename__ = 'transaction_log'
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    
    # Transaction details
    symbol = Column(String(10), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)  # buy, sell, dividend, fee, etc.
    quantity = Column(Integer, nullable=False)
    price_per_share = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)  # quantity * price + fees
    fees = Column(Numeric(10, 4), default=0.0)
    
    # LIFO Gain/Loss calculation
    cost_basis = Column(Numeric(12, 2))  # Cost basis for sale transactions
    realized_gain_loss = Column(Numeric(12, 2))  # Gain/loss for completed transactions
    unrealized_gain_loss = Column(Numeric(12, 2))  # Current unrealized gain/loss
    
    # Timing
    transaction_date = Column(DateTime(timezone=True), nullable=False, index=True)
    settlement_date = Column(DateTime(timezone=True))
    
    # Broker information
    broker_transaction_id = Column(String(100), index=True)
    
    # Tax reporting
    wash_sale = Column(Boolean, default=False)
    short_term = Column(Boolean)  # True for short-term capital gains (<1 year)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="transactions")
    user = relationship("User")
    account = relationship("Account")
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_transaction_user_symbol', 'user_id', 'symbol'),
        Index('idx_transaction_date', 'transaction_date'),
        Index('idx_transaction_type_date', 'transaction_type', 'transaction_date'),
    )