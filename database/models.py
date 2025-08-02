from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.database import Base

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

class EnvironmentVariable(Base):
    """Global environment variables table"""
    __tablename__ = 'environment_variables'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class BrokerageInfo(Base):
    """Brokerage information and credentials"""
    __tablename__ = 'brokerage_info'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    api_url = Column(String(255))
    api_key = Column(String(255))
    api_secret = Column(String(255))
    trading_fees = Column(Float, default=0.0)
    day_trade_limit = Column(Integer, default=3)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
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
    """Stock demographics and information"""
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Float)
    priority = Column(Integer, default=0, index=True)  # Priority ranking
    has_options = Column(Boolean, default=False)
    last_price = Column(Float)
    change_percent = Column(Float)
    volume = Column(Integer)
    avg_volume = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    price_history = relationship("StockPriceHistory", back_populates="stock")
    priority_prices = relationship("PriorityCurrentPrice", back_populates="stock")

class StockPriceHistory(Base):
    """Historical stock price data with technical indicators"""
    __tablename__ = 'stock_price_history'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    
    # Technical Indicators
    sma_20 = Column(Float)  # 20-day Simple Moving Average
    std_20 = Column(Float)  # 20-day Standard Deviation
    
    # Wilder's DMI indicators
    adx = Column(Float)  # Average Directional Index
    di_plus = Column(Float)  # Positive Directional Indicator
    di_minus = Column(Float)  # Negative Directional Indicator
    
    # Pivot Points
    pivot_point = Column(Float)
    resistance_1 = Column(Float)
    resistance_2 = Column(Float)
    support_1 = Column(Float)
    support_2 = Column(Float)
    
    # Commodity Channel Index
    cci = Column(Float)
    
    # Stochastic Oscillator
    stoch_k = Column(Float)
    stoch_d = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="price_history")
    
    # Indexes
    __table_args__ = (
        Index('idx_stock_date', 'stock_id', 'date'),
    )

class PriorityCurrentPrice(Base):
    """Real-time price tracking for priority stocks"""
    __tablename__ = 'priority_current_price'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    open_price = Column(Float)
    current_price = Column(Float, nullable=False)
    percent_change = Column(Float)
    volume = Column(Integer)
    
    # Relationships
    stock = relationship("Stock", back_populates="priority_prices")
    
    # Indexes
    __table_args__ = (
        Index('idx_stock_datetime', 'stock_id', 'datetime'),
    )

class PriorityArchivePrice(Base):
    """Archive table for historical priority price data"""
    __tablename__ = 'priority_archive_price'
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=False)
    open_price = Column(Float)
    current_price = Column(Float, nullable=False)
    percent_change = Column(Float)
    volume = Column(Integer)
    archived_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_archive_stock_datetime', 'stock_id', 'datetime'),
    )

class Order(Base):
    """Trading orders table"""
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    order_type = Column(String(20), nullable=False)  # market, limit, stop
    side = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Integer, nullable=False)
    price = Column(Float)  # limit price
    stop_price = Column(Float)  # stop price
    status = Column(String(20), default='pending')  # pending, filled, cancelled, rejected
    broker_order_id = Column(String(100))
    
    # Order details
    asset_type = Column(String(20), default='stock')  # stock, option
    option_type = Column(String(10))  # call, put (for options)
    strike_price = Column(Float)  # for options
    expiration_date = Column(DateTime(timezone=True))  # for options
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    filled_at = Column(DateTime(timezone=True))
    
    # Relationships
    account = relationship("Account")
    transactions = relationship("TransactionLog", back_populates="order")

class TransactionLog(Base):
    """Transaction log for executed trades"""
    __tablename__ = 'transaction_log'
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    
    # P&L Calculation (LIFO)
    cost_basis = Column(Float)
    realized_pnl = Column(Float)
    
    # Transaction details
    asset_type = Column(String(20), default='stock')
    option_type = Column(String(10))
    strike_price = Column(Float)
    expiration_date = Column(DateTime(timezone=True))
    
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="transactions")
    account = relationship("Account")
    
    # Indexes
    __table_args__ = (
        Index('idx_symbol_executed', 'symbol', 'executed_at'),
    )
