# models.py
# SQLAlchemy models for algorithmic trading app (SQLite / Postgres-compatible)
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean,
    DateTime, Date, Numeric, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from database.database import Base

# ------------- RBAC & Users -------------
class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    permissions = relationship("RolePermission", back_populates="role")
    users = relationship("User", back_populates="role")


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    role_permissions = relationship("RolePermission", back_populates="permission")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="role_permissions")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    role = relationship("Role", back_populates="users")
    accounts = relationship("Account", back_populates="user")


# ------------- Environment Variables & Market Segments -------------
class GlobalEnvVar(Base):
    __tablename__ = "global_env_vars"
    name = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    value_type = Column(String, nullable=False)  # 'int','float','pct','str','bool'
    description = Column(Text)


class MarketSegment(Base):
    __tablename__ = "market_segments"
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)

    stocks = relationship("Stock", back_populates="market_segment")
    env_vars = relationship("MarketSegmentEnvVar", back_populates="market_segment")


class MarketSegmentEnvVar(Base):
    __tablename__ = "market_segment_env_vars"
    market_segment_id = Column(Integer, ForeignKey("market_segments.id", ondelete="CASCADE"), primary_key=True)
    name = Column(String, primary_key=True)
    value = Column(String, nullable=False)

    market_segment = relationship("MarketSegment", back_populates="env_vars")


class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    market_segment_id = Column(Integer, ForeignKey("market_segments.id"))
    shares_outstanding = Column(BigInteger)
    is_active = Column(Boolean, default=True)

    market_segment = relationship("MarketSegment", back_populates="stocks")
    env_vars = relationship("StockEnvVar", back_populates="stock")
    price_history = relationship("PriceHistory", back_populates="stock")
    stochastic_history = relationship("StochasticHistory", back_populates="stock")
    options_chains = relationship("OptionsChain", back_populates="stock")
    positions = relationship("Position", back_populates="stock")
    priority_records = relationship("PriorityStock", back_populates="stock")


class StockEnvVar(Base):
    __tablename__ = "stock_env_vars"
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    name = Column(String, primary_key=True)
    value = Column(String, nullable=False)

    stock = relationship("Stock", back_populates="env_vars")


# ------------- Price & Derived History -------------
class PriceHistory(Base):
    __tablename__ = "price_history"
    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"))
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Numeric)
    high = Column(Numeric)
    low = Column(Numeric)
    close = Column(Numeric)
    volume = Column(BigInteger)

    stock = relationship("Stock", back_populates="price_history")

    __table_args__ = (
        Index('idx_price_stock_ts', 'stock_id', 'ts'),
    )


class StochasticHistory(Base):
    __tablename__ = "stochastic_history"
    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"))
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Moving averages and standard deviation
    sma_21 = Column(Numeric)
    sd_21 = Column(Numeric)
    
    # RSI and MACD
    rsi_14 = Column(Numeric)
    macd = Column(Numeric)
    macd_signal = Column(Numeric)
    
    # Stochastic Oscillator
    k_14 = Column(Numeric)  # %K
    d_3 = Column(Numeric)   # %D (3-period MA of %K)
    
    # Wilder's Directional Movement Indicators (DMI)
    adx = Column(Numeric)   # Average Directional Index
    di_plus = Column(Numeric)   # DI+
    di_minus = Column(Numeric)  # DI-
    
    # Commodity Channel Index
    cci_14 = Column(Numeric)
    
    # Bollinger Bands (20-day, 2 SD)
    bollinger_upper = Column(Numeric)
    bollinger_middle = Column(Numeric)  # Same as SMA_20
    bollinger_lower = Column(Numeric)
    
    # Pivot Points
    pivot_point = Column(Numeric)
    resistance_1 = Column(Numeric)
    support_1 = Column(Numeric)

    stock = relationship("Stock", back_populates="stochastic_history")

    __table_args__ = (
        Index('idx_stochastic_stock_ts', 'stock_id', 'ts'),
    )


# ------------- Options, Accounts, Positions, Orders, Trades -------------
class OptionsChain(Base):
    __tablename__ = "options_chain"
    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"))
    option_symbol = Column(String, nullable=False, index=True)
    strike = Column(Numeric, nullable=False)
    expiry = Column(Date, nullable=False)
    type = Column(String, nullable=False)  # 'CALL' or 'PUT'
    last_price = Column(Numeric)
    bid = Column(Numeric)
    ask = Column(Numeric)
    volume = Column(BigInteger)
    open_interest = Column(BigInteger)
    retrieved_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    stock = relationship("Stock", back_populates="options_chains")
    positions = relationship("Position", back_populates="option")
    orders = relationship("Order", back_populates="option")

    __table_args__ = (
        Index('idx_options_stock_expiry', 'stock_id', 'expiry'),
    )


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"))
    name = Column(String)
    
    # Broker integration
    broker_platform = Column(String)  # 'robinhood', 'alpaca', etc.
    broker_account_id = Column(String)  # External account ID
    broker_credentials_encrypted = Column(Text)  # Encrypted JSON with credentials
    
    # Account balances
    cash_balance = Column(Numeric, default=0)
    buying_power = Column(Numeric, default=0)
    total_balance = Column(Numeric, default=0)
    
    # Trading settings
    is_active = Column(Boolean, default=True)
    day_trade_enabled = Column(Boolean, default=False)
    min_balance_required = Column(Numeric, default=25000)  # For day trading
    transaction_fees = Column(Numeric, default=0)  # Per-trade fee
    
    # Account metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_synced_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="accounts")
    positions = relationship("Position", back_populates="account")
    orders = relationship("Order", back_populates="account")


class Position(Base):
    __tablename__ = "positions"
    id = Column(BigInteger, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"))
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="RESTRICT"), nullable=True)
    option_id = Column(BigInteger, ForeignKey("options_chain.id", ondelete="RESTRICT"), nullable=True)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(Numeric, nullable=False)
    side = Column(String, nullable=False)  # 'LONG' / 'SHORT'
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    account = relationship("Account", back_populates="positions")
    stock = relationship("Stock", back_populates="positions")
    option = relationship("OptionsChain", back_populates="positions")


class Order(Base):
    __tablename__ = "orders"
    id = Column(BigInteger, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"))
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="RESTRICT"), nullable=True)
    option_id = Column(BigInteger, ForeignKey("options_chain.id", ondelete="RESTRICT"), nullable=True)
    order_type = Column(String, nullable=False)  # 'MARKET','LIMIT'
    side = Column(String, nullable=False)  # 'BUY','SELL'
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric, nullable=True)
    status = Column(String, nullable=False, default="PENDING", index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    account = relationship("Account", back_populates="orders")
    stock = relationship("Stock")
    option = relationship("OptionsChain", back_populates="orders")
    trades = relationship("Trade", back_populates="order")


class Trade(Base):
    __tablename__ = "trades"
    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="SET NULL"))
    executed_price = Column(Numeric)
    executed_qty = Column(Integer)
    executed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("Order", back_populates="trades")


# ------------- Priority & Jobs & Change Log -------------
class PriorityStock(Base):
    __tablename__ = "priority_stocks"
    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"))
    reason = Column(Text)
    score = Column(Numeric)
    flagged_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    stock = relationship("Stock", back_populates="priority_records")


class NightlyJob(Base):
    __tablename__ = "nightly_jobs"
    id = Column(BigInteger, primary_key=True)
    job_date = Column(Date, nullable=False, index=True)
    status = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    notes = Column(Text)


class ChangeLog(Base):
    __tablename__ = "change_log"
    id = Column(BigInteger, primary_key=True)
    change_tag = Column(String, nullable=False, index=True)
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
