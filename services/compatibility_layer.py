"""
Compatibility layer for bridging old Streamlit UI with new RBAC database schema.
Provides helper functions and DTOs that map new models to legacy data contracts.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database.models import (
    User, GlobalEnvVar, Stock, PriceHistory, StochasticHistory,
    PriorityStock, Order, Trade, Position, MarketSegment, Account
)


class LegacyStockView:
    """DTO that mimics the old Stock model structure"""
    def __init__(self, stock: Stock, latest_price: Optional[PriceHistory] = None, 
                 prev_price: Optional[PriceHistory] = None, priority_record: Optional[PriorityStock] = None):
        self.id = stock.id
        self.symbol = stock.symbol
        self.name = stock.name
        self.is_active = stock.is_active
        
        # Derived fields from new schema
        if latest_price:
            self.last_price = float(latest_price.close) if latest_price.close else 0.0
            if prev_price and prev_price.close and latest_price.close:
                self.change_percent = ((float(latest_price.close) - float(prev_price.close)) / float(prev_price.close)) * 100
            else:
                self.change_percent = 0.0
        else:
            self.last_price = 0.0
            self.change_percent = 0.0
        
        # Priority from PriorityStock table
        self.priority = int(priority_record.score) if priority_record and priority_record.score else 0
        
        # Market segment as sector
        self.sector = stock.market_segment.name if stock.market_segment else "Unknown"
        
        # Assume has_options based on whether we have options data
        self.has_options = True  # Default for now


class LegacyOrderView:
    """DTO that mimics the old Order model structure"""
    def __init__(self, order: Order, stock: Optional[Stock] = None):
        self.id = order.id
        self.symbol = stock.symbol if stock else "UNKNOWN"
        self.side = order.side
        self.asset_type = "option" if order.option_id else "stock"
        self.quantity = order.quantity
        self.order_type = order.order_type
        self.limit_price = float(order.price) if order.price else None
        self.status = order.status
        self.submitted_at = order.created_at
        self.filled_at = order.executed_at


class LegacyTradeView:
    """DTO that mimics the old TransactionLog model structure"""
    def __init__(self, trade: Trade, order: Optional[Order] = None, stock: Optional[Stock] = None):
        self.id = trade.id
        self.symbol = stock.symbol if stock else (order.stock.symbol if order and order.stock else "UNKNOWN")
        self.executed_price = float(trade.executed_price) if trade.executed_price else 0.0
        self.quantity = trade.executed_qty
        self.transaction_date = trade.executed_at
        self.side = order.side if order else "UNKNOWN"


class LegacyEnvVar:
    """DTO that mimics the old EnvironmentVariable model"""
    def __init__(self, env_var: GlobalEnvVar):
        self.key = env_var.name
        self.value = env_var.value
        self.description = env_var.description


def get_env_var(session: Session, key: str) -> Optional[LegacyEnvVar]:
    """Get environment variable by key (maps to name in new schema)"""
    env_var = session.query(GlobalEnvVar).filter(GlobalEnvVar.name == key).first()
    return LegacyEnvVar(env_var) if env_var else None


def get_all_env_vars(session: Session) -> List[LegacyEnvVar]:
    """Get all environment variables"""
    env_vars = session.query(GlobalEnvVar).all()
    return [LegacyEnvVar(ev) for ev in env_vars]


def set_env_var(session: Session, key: str, value: str, description: str = None) -> LegacyEnvVar:
    """Set environment variable"""
    env_var = session.query(GlobalEnvVar).filter(GlobalEnvVar.name == key).first()
    if env_var:
        env_var.value = value
        if description:
            env_var.description = description
    else:
        env_var = GlobalEnvVar(
            name=key,
            value=value,
            value_type='str',
            description=description or f'Custom variable {key}'
        )
        session.add(env_var)
    session.commit()
    return LegacyEnvVar(env_var)


def get_stock_with_price(session: Session, symbol: str) -> Optional[LegacyStockView]:
    """Get stock with latest price and priority data"""
    stock = session.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        return None
    
    # Get latest price
    latest_price = (session.query(PriceHistory)
                    .filter(PriceHistory.stock_id == stock.id)
                    .order_by(desc(PriceHistory.ts))
                    .first())
    
    # Get previous price for change calculation
    prev_price = None
    if latest_price:
        prev_price = (session.query(PriceHistory)
                      .filter(PriceHistory.stock_id == stock.id,
                              PriceHistory.ts < latest_price.ts)
                      .order_by(desc(PriceHistory.ts))
                      .first())
    
    # Get priority record
    priority = (session.query(PriorityStock)
                .filter(PriorityStock.stock_id == stock.id)
                .order_by(desc(PriorityStock.flagged_at))
                .first())
    
    return LegacyStockView(stock, latest_price, prev_price, priority)


def get_priority_stocks(session: Session) -> List[LegacyStockView]:
    """Get all stocks with priority > 0 (having PriorityStock records)"""
    # Get stocks that have priority records
    priority_records = (session.query(PriorityStock)
                        .order_by(desc(PriorityStock.score))
                        .all())
    
    stock_views = []
    for priority in priority_records:
        if priority.stock:
            # Get latest price
            latest_price = (session.query(PriceHistory)
                            .filter(PriceHistory.stock_id == priority.stock_id)
                            .order_by(desc(PriceHistory.ts))
                            .first())
            
            # Get previous price
            prev_price = None
            if latest_price:
                prev_price = (session.query(PriceHistory)
                              .filter(PriceHistory.stock_id == priority.stock_id,
                                      PriceHistory.ts < latest_price.ts)
                              .order_by(desc(PriceHistory.ts))
                              .first())
            
            stock_view = LegacyStockView(priority.stock, latest_price, prev_price, priority)
            stock_views.append(stock_view)
    
    return stock_views


def get_all_stocks_with_prices(session: Session, limit: int = 100) -> List[LegacyStockView]:
    """Get all stocks with latest prices"""
    stocks = session.query(Stock).filter(Stock.is_active == True).limit(limit).all()
    
    stock_views = []
    for stock in stocks:
        latest_price = (session.query(PriceHistory)
                        .filter(PriceHistory.stock_id == stock.id)
                        .order_by(desc(PriceHistory.ts))
                        .first())
        
        prev_price = None
        if latest_price:
            prev_price = (session.query(PriceHistory)
                          .filter(PriceHistory.stock_id == stock.id,
                                  PriceHistory.ts < latest_price.ts)
                          .order_by(desc(PriceHistory.ts))
                          .first())
        
        priority = (session.query(PriorityStock)
                    .filter(PriorityStock.stock_id == stock.id)
                    .order_by(desc(PriorityStock.flagged_at))
                    .first())
        
        stock_view = LegacyStockView(stock, latest_price, prev_price, priority)
        stock_views.append(stock_view)
    
    return stock_views


def get_all_orders(session: Session, limit: int = 100) -> List[LegacyOrderView]:
    """Get all orders with stock information"""
    orders = session.query(Order).order_by(desc(Order.created_at)).limit(limit).all()
    
    order_views = []
    for order in orders:
        stock = None
        if order.stock_id:
            stock = session.query(Stock).filter(Stock.id == order.stock_id).first()
        order_views.append(LegacyOrderView(order, stock))
    
    return order_views


def get_all_trades(session: Session, limit: int = 100) -> List[LegacyTradeView]:
    """Get all trades (transaction log)"""
    trades = session.query(Trade).order_by(desc(Trade.executed_at)).limit(limit).all()
    
    trade_views = []
    for trade in trades:
        order = session.query(Order).filter(Order.id == trade.order_id).first() if trade.order_id else None
        stock = None
        if order and order.stock_id:
            stock = session.query(Stock).filter(Stock.id == order.stock_id).first()
        trade_views.append(LegacyTradeView(trade, order, stock))
    
    return trade_views


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return session.query(User).filter(User.username == username).first()


def verify_user_password(user: User, password: str) -> bool:
    """Verify user password using the new hashing method"""
    if not user:
        return False
    
    import hashlib
    
    # Check if using new format (with salt)
    if ':' in user.password_hash:
        salt, hash_value = user.password_hash.split(':')
        computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return computed_hash == hash_value
    else:
        # Old format (legacy compatibility)
        salted = f"{password}_trading_salt"
        computed_hash = hashlib.sha256(salted.encode()).hexdigest()
        return computed_hash == user.password_hash


def get_user_role(user: User) -> str:
    """Get user role name"""
    if user.role:
        return user.role.name
    return "viewer"


def get_recent_priority_updates(session: Session, minutes: int = 5, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent priority stock updates for activity monitoring"""
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    
    recent_priorities = (session.query(PriorityStock)
                          .filter(PriorityStock.flagged_at >= cutoff)
                          .order_by(desc(PriorityStock.flagged_at))
                          .limit(limit)
                          .all())
    
    updates = []
    for priority in recent_priorities:
        if priority.stock:
            # Get latest price
            latest_price = (session.query(PriceHistory)
                            .filter(PriceHistory.stock_id == priority.stock_id)
                            .order_by(desc(PriceHistory.ts))
                            .first())
            
            prev_price = None
            if latest_price:
                prev_price = (session.query(PriceHistory)
                              .filter(PriceHistory.stock_id == priority.stock_id,
                                      PriceHistory.ts < latest_price.ts)
                              .order_by(desc(PriceHistory.ts))
                              .first())
            
            change_pct = 0.0
            if latest_price and prev_price and prev_price.close:
                change_pct = ((float(latest_price.close) - float(prev_price.close)) / float(prev_price.close)) * 100
            
            updates.append({
                "datetime": priority.flagged_at,
                "symbol": priority.stock.symbol,
                "current_price": float(latest_price.close) if latest_price and latest_price.close else 0.0,
                "percent_change_from_previous": change_pct,
                "volume": latest_price.volume if latest_price else None
            })
    
    return updates
