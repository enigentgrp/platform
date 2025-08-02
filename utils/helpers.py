import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from database.models import TransactionLog

def format_currency(amount: float) -> str:
    """Format amount as currency string"""
    return f"${amount:,.2f}"

def format_percentage(value: float) -> str:
    """Format value as percentage string"""
    return f"{value:.2f}%"

def calculate_portfolio_value(positions: List[Dict], market_data: Dict) -> float:
    """Calculate total portfolio value"""
    total_value = 0.0
    
    for position in positions:
        symbol = position['symbol']
        quantity = position['quantity']
        
        if symbol in market_data:
            current_price = market_data[symbol]['price']
            position_value = quantity * current_price
            total_value += position_value
    
    return total_value

def calculate_position_size(available_cash: float, stock_price: float, 
                          max_position_percent: float) -> int:
    """Calculate optimal position size"""
    max_position_value = available_cash * (max_position_percent / 100)
    quantity = int(max_position_value / stock_price)
    return max(0, quantity)

def calculate_risk_metrics(returns: List[float]) -> Dict:
    """Calculate risk metrics for a series of returns"""
    if not returns:
        return {}
    
    returns_array = np.array(returns)
    
    return {
        'total_return': np.sum(returns_array),
        'average_return': np.mean(returns_array),
        'volatility': np.std(returns_array),
        'sharpe_ratio': np.mean(returns_array) / np.std(returns_array) if np.std(returns_array) != 0 else 0,
        'max_drawdown': calculate_max_drawdown(returns_array),
        'win_rate': len([r for r in returns if r > 0]) / len(returns) * 100
    }

def calculate_max_drawdown(returns: np.array) -> float:
    """Calculate maximum drawdown"""
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    return np.min(drawdown)

def calculate_lifo_pnl(transactions: List[TransactionLog], current_price: float) -> Dict:
    """Calculate P&L using LIFO (Last In, First Out) method"""
    buys = []
    sells = []
    
    # Separate buy and sell transactions
    for transaction in transactions:
        if transaction.side == 'buy':
            buys.append(transaction)
        else:
            sells.append(transaction)
    
    # Sort transactions by date
    buys.sort(key=lambda x: x.transaction_date, reverse=True)  # LIFO - most recent first
    sells.sort(key=lambda x: x.transaction_date)
    
    realized_pnl = 0.0
    unrealized_pnl = 0.0
    remaining_quantity = 0
    remaining_cost_basis = 0
    
    # Process sells against buys using LIFO
    remaining_buys = buys.copy()
    
    for sell in sells:
        sell_quantity = sell.quantity
        sell_proceeds = sell_quantity * sell.price
        sell_cost_basis = 0
        
        # Match against most recent buys (LIFO)
        while sell_quantity > 0 and remaining_buys:
            buy = remaining_buys[0]
            
            if buy.quantity <= sell_quantity:
                # Use entire buy position
                sell_cost_basis += buy.quantity * buy.price
                sell_quantity -= buy.quantity
                remaining_buys.pop(0)
            else:
                # Partial use of buy position
                sell_cost_basis += sell_quantity * buy.price
                buy.quantity -= sell_quantity
                sell_quantity = 0
        
        # Calculate realized P&L for this sell
        realized_pnl += sell_proceeds - sell_cost_basis
    
    # Calculate unrealized P&L from remaining positions
    for buy in remaining_buys:
        remaining_quantity += buy.quantity
        remaining_cost_basis += buy.quantity * buy.price
    
    if remaining_quantity > 0:
        current_value = remaining_quantity * current_price
        unrealized_pnl = current_value - remaining_cost_basis
    
    return {
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized_pnl,
        'total_pnl': realized_pnl + unrealized_pnl,
        'remaining_quantity': remaining_quantity,
        'avg_cost_basis': remaining_cost_basis / remaining_quantity if remaining_quantity > 0 else 0
    }

def calculate_option_metrics(option_positions: List[Dict], current_prices: Dict) -> Dict:
    """Calculate metrics specific to options positions"""
    total_premium_paid = 0
    total_current_value = 0
    expiring_soon = 0
    
    for position in option_positions:
        symbol = position['symbol']
        quantity = position['quantity']
        premium_paid = position.get('avg_price', 0) * quantity
        
        total_premium_paid += premium_paid
        
        # Estimate current value (simplified)
        if symbol in current_prices:
            estimated_value = premium_paid * 1.1  # Simplified estimation
            total_current_value += estimated_value
        
        # Check if expiring soon (within 7 days)
        if position.get('expiration_date'):
            expiry = position['expiration_date']
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, '%Y-%m-%d')
            
            if expiry <= datetime.now() + timedelta(days=7):
                expiring_soon += 1
    
    return {
        'total_premium_paid': total_premium_paid,
        'total_current_value': total_current_value,
        'unrealized_pnl': total_current_value - total_premium_paid,
        'expiring_soon_count': expiring_soon
    }

def calculate_sector_allocation(positions: List[Dict], stock_sectors: Dict) -> Dict:
    """Calculate portfolio allocation by sector"""
    sector_values = {}
    total_value = 0
    
    for position in positions:
        symbol = position['symbol']
        value = position.get('market_value', 0)
        sector = stock_sectors.get(symbol, 'Unknown')
        
        if sector not in sector_values:
            sector_values[sector] = 0
        
        sector_values[sector] += value
        total_value += value
    
    # Convert to percentages
    sector_percentages = {}
    for sector, value in sector_values.items():
        sector_percentages[sector] = (value / total_value * 100) if total_value > 0 else 0
    
    return sector_percentages

def validate_trading_hours() -> bool:
    """Check if current time is within trading hours (9:30 AM - 4:00 PM ET)"""
    now = datetime.now()
    
    # Convert to ET (simplified - doesn't account for DST)
    # In production, would use proper timezone handling
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    return market_open <= now <= market_close

def calculate_day_trade_count(transactions: List[TransactionLog], account_type: str = 'margin') -> int:
    """Calculate number of day trades in the past 5 business days"""
    if account_type == 'cash':
        return 0  # Cash accounts don't have day trade restrictions
    
    # Get transactions from last 5 business days
    cutoff_date = datetime.now() - timedelta(days=7)  # Simplified
    recent_transactions = [t for t in transactions if t.transaction_date >= cutoff_date]
    
    # Group by symbol and date
    daily_trades = {}
    for transaction in recent_transactions:
        date_key = transaction.transaction_date.date()
        symbol = transaction.symbol
        
        if date_key not in daily_trades:
            daily_trades[date_key] = {}
        if symbol not in daily_trades[date_key]:
            daily_trades[date_key][symbol] = {'buys': 0, 'sells': 0}
        
        if transaction.side == 'buy':
            daily_trades[date_key][symbol]['buys'] += 1
        else:
            daily_trades[date_key][symbol]['sells'] += 1
    
    # Count day trades (buy and sell of same symbol on same day)
    day_trade_count = 0
    for date, symbols in daily_trades.items():
        for symbol, trades in symbols.items():
            day_trade_count += min(trades['buys'], trades['sells'])
    
    return day_trade_count

def generate_trade_signal(technical_data: Dict, price_data: List[float]) -> str:
    """Generate trading signal based on technical indicators"""
    signals = []
    
    # RSI signals
    rsi = technical_data.get('rsi', 50)
    if rsi > 70:
        signals.append('sell')
    elif rsi < 30:
        signals.append('buy')
    
    # Stochastic signals
    stoch_k = technical_data.get('stoch_k', 50)
    stoch_d = technical_data.get('stoch_d', 50)
    if stoch_k > 80 and stoch_d > 80:
        signals.append('sell')
    elif stoch_k < 20 and stoch_d < 20:
        signals.append('buy')
    
    # CCI signals
    cci = technical_data.get('cci', 0)
    if cci > 100:
        signals.append('sell')
    elif cci < -100:
        signals.append('buy')
    
    # Price momentum
    if len(price_data) >= 3:
        recent_trend = 'up' if all(price_data[i] >= price_data[i-1] for i in range(-2, 0)) else 'down'
        if recent_trend == 'up':
            signals.append('buy')
        else:
            signals.append('sell')
    
    # Determine overall signal
    buy_signals = signals.count('buy')
    sell_signals = signals.count('sell')
    
    if buy_signals > sell_signals:
        return 'buy'
    elif sell_signals > buy_signals:
        return 'sell'
    else:
        return 'hold'
