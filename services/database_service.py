"""
Database service for managing priority calculations, archiving, and database operations
as specified in the requirements.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database.models import (
    Stock, EnvironmentVariable, PriorityCurrentPrice, PriorityArchivePrice,
    StockPriceHistory, Order, TransactionLog
)
import numpy as np
from typing import List, Optional

class DatabaseService:
    """Service for managing database operations per specifications"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_environment_variable(self, key: str, default=None):
        """Get environment variable value with type conversion"""
        env_var = self.session.query(EnvironmentVariable).filter(
            EnvironmentVariable.key == key
        ).first()
        
        if not env_var:
            return default
            
        value = env_var.value
        var_type = env_var.variable_type
        
        try:
            if var_type == 'integer':
                return int(value)
            elif var_type == 'float':
                return float(value)
            elif var_type == 'boolean':
                return value.lower() in ('true', '1', 'yes', 'on')
            else:
                return value
        except (ValueError, AttributeError):
            return default
    
    def update_stock_priorities(self):
        """
        Update stock priorities based on specifications:
        - Set priority=1 if closing price is > 1 std dev above/below 20-day MA
        - And closing price is above/below MA by more than PRIORITY_PERCENTAGE_TARGET%
        - Set priority=0 for all others (except sector ETFs which stay at 9)
        """
        percentage_target = self.get_environment_variable('PRIORITY_PERCENTAGE_TARGET', 2.5)
        
        # Get all stocks except sector ETFs
        stocks = self.session.query(Stock).filter(Stock.priority != 9).all()
        
        for stock in stocks:
            # Get last 20 days of price history
            history = self.session.query(StockPriceHistory).filter(
                StockPriceHistory.stock_id == stock.id
            ).order_by(StockPriceHistory.date.desc()).limit(20).all()
            
            if len(history) >= 20:
                # Calculate 20-day moving average and standard deviation
                closes = [float(h.close_price) for h in reversed(history)]
                ma_20 = np.mean(closes)
                std_20 = np.std(closes)
                current_price = float(stock.last_price) if stock.last_price else closes[-1]
                
                # Check if price is > 1 std dev from MA
                upper_threshold = ma_20 + std_20
                lower_threshold = ma_20 - std_20
                
                # Check percentage change from MA
                pct_change_from_ma = abs((current_price - ma_20) / ma_20) * 100
                
                # Set priority based on conditions
                if ((current_price > upper_threshold or current_price < lower_threshold) and 
                    pct_change_from_ma > percentage_target):
                    stock.priority = 1
                else:
                    stock.priority = 0
            else:
                # Not enough history, set to 0
                stock.priority = 0
        
        self.session.commit()
        return len([s for s in stocks if s.priority == 1])
    
    def update_priority_current_prices(self):
        """
        Update priority current price table for stocks with priority > 0
        Record every X seconds as per environment variables
        """
        # Get all priority stocks
        priority_stocks = self.session.query(Stock).filter(Stock.priority > 0).all()
        current_time = datetime.now()
        
        updated_count = 0
        for stock in priority_stocks:
            # Get market open price for today
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Check if we have an open price for today
            open_record = self.session.query(PriorityCurrentPrice).filter(
                and_(
                    PriorityCurrentPrice.stock_id == stock.id,
                    PriorityCurrentPrice.datetime >= today_start
                )
            ).order_by(PriorityCurrentPrice.datetime.asc()).first()
            
            price_at_open = float(open_record.price_at_open) if open_record and open_record.price_at_open else float(stock.last_price or 0)
            current_price = float(stock.last_price or 0)
            
            # Get previous price for percent change calculation
            last_record = self.session.query(PriorityCurrentPrice).filter(
                PriorityCurrentPrice.stock_id == stock.id
            ).order_by(PriorityCurrentPrice.datetime.desc()).first()
            
            previous_price = float(last_record.current_price) if last_record else current_price
            
            # Calculate percent changes
            pct_change_from_previous = ((current_price - previous_price) / previous_price * 100) if previous_price > 0 else 0
            pct_change_from_open = ((current_price - price_at_open) / price_at_open * 100) if price_at_open > 0 else 0
            
            # Create new price record
            price_record = PriorityCurrentPrice(
                stock_id=stock.id,
                symbol=stock.symbol,
                datetime=current_time,
                price_at_open=price_at_open if not open_record else open_record.price_at_open,
                current_price=current_price,
                percent_change_from_previous=round(pct_change_from_previous, 4),
                percent_change_from_open=round(pct_change_from_open, 4),
                volume=stock.volume,
                bid=current_price * 0.999,  # Simulate bid/ask spread
                ask=current_price * 1.001
            )
            
            self.session.add(price_record)
            updated_count += 1
        
        self.session.commit()
        return updated_count
    
    def archive_priority_prices(self):
        """
        Move records from priority_current_price to priority_archive_price 
        at the end of each day
        """
        # Get yesterday's cutoff
        yesterday = datetime.now() - timedelta(days=1)
        cutoff = yesterday.replace(hour=23, minute=59, second=59)
        
        # Get records to archive
        records_to_archive = self.session.query(PriorityCurrentPrice).filter(
            PriorityCurrentPrice.datetime <= cutoff
        ).all()
        
        archived_count = 0
        for record in records_to_archive:
            # Create archive record
            archive_record = PriorityArchivePrice(
                stock_id=record.stock_id,
                symbol=record.symbol,
                datetime=record.datetime,
                price_at_open=record.price_at_open,
                current_price=record.current_price,
                percent_change_from_previous=record.percent_change_from_previous,
                percent_change_from_open=record.percent_change_from_open,
                volume=record.volume,
                bid=record.bid,
                ask=record.ask
            )
            
            self.session.add(archive_record)
            self.session.delete(record)
            archived_count += 1
        
        self.session.commit()
        return archived_count
    
    def purge_old_archive_data(self):
        """Purge archive data older than X days (from environment variables)"""
        retention_days = self.get_environment_variable('ARCHIVE_RETENTION_DAYS', 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        deleted_count = self.session.query(PriorityArchivePrice).filter(
            PriorityArchivePrice.archived_date < cutoff_date
        ).delete()
        
        self.session.commit()
        return deleted_count
    
    def evaluate_trading_opportunities(self):
        """
        Evaluate priority current price table for trading opportunities
        If no order exists for ticker and X periods meet criteria, trigger trading logic
        """
        evaluation_periods = self.get_environment_variable('PRIORITY_EVALUATION_PERIODS', 3)
        
        # Get all priority stocks
        priority_stocks = self.session.query(Stock).filter(Stock.priority > 0).all()
        opportunities = []
        
        for stock in priority_stocks:
            # Check if there's already an open order for this stock
            existing_order = self.session.query(Order).filter(
                and_(
                    Order.symbol == stock.symbol,
                    Order.status.in_(['pending', 'partially_filled'])
                )
            ).first()
            
            if not existing_order:
                # Get last X periods of price data
                recent_prices = self.session.query(PriorityCurrentPrice).filter(
                    PriorityCurrentPrice.stock_id == stock.id
                ).order_by(PriorityCurrentPrice.datetime.desc()).limit(evaluation_periods).all()
                
                if len(recent_prices) >= evaluation_periods:
                    # Analyze price movement for trading signals
                    prices = [float(p.current_price) for p in reversed(recent_prices)]
                    
                    # Simple momentum strategy
                    if len(prices) >= 2:
                        momentum = (prices[-1] - prices[0]) / prices[0] * 100
                        
                        # Generate buy/sell signals based on momentum
                        if momentum > 1.0:  # 1% positive momentum
                            opportunities.append({
                                'symbol': stock.symbol,
                                'action': 'buy',
                                'momentum': momentum,
                                'current_price': prices[-1],
                                'confidence': min(abs(momentum) * 10, 100)
                            })
                        elif momentum < -1.0:  # 1% negative momentum
                            opportunities.append({
                                'symbol': stock.symbol,
                                'action': 'sell',
                                'momentum': momentum,
                                'current_price': prices[-1],
                                'confidence': min(abs(momentum) * 10, 100)
                            })
        
        return opportunities
    
    def get_lifo_cost_basis(self, symbol: str, quantity: int) -> tuple:
        """
        Calculate LIFO cost basis for sale transactions
        Returns (cost_basis, realized_gain_loss)
        """
        # Get all buy transactions for this symbol, ordered by date desc (LIFO)
        buy_transactions = self.session.query(TransactionLog).filter(
            and_(
                TransactionLog.symbol == symbol,
                TransactionLog.transaction_type == 'buy'
            )
        ).order_by(TransactionLog.transaction_date.desc()).all()
        
        remaining_quantity = quantity
        total_cost_basis = 0.0
        
        for transaction in buy_transactions:
            if remaining_quantity <= 0:
                break
                
            available_shares = transaction.quantity
            shares_to_use = min(remaining_quantity, available_shares)
            
            cost_basis_portion = shares_to_use * float(transaction.price_per_share)
            total_cost_basis += cost_basis_portion
            
            remaining_quantity -= shares_to_use
        
        return total_cost_basis, 0.0  # Return 0 for realized_gain_loss, to be calculated by caller
    
    def get_database_stats(self):
        """Get comprehensive database statistics"""
        stats = {
            'environment_variables': self.session.query(EnvironmentVariable).count(),
            'stocks_total': self.session.query(Stock).count(),
            'stocks_priority_1': self.session.query(Stock).filter(Stock.priority == 1).count(),
            'stocks_sector_etf': self.session.query(Stock).filter(Stock.priority == 9).count(),
            'priority_current_prices': self.session.query(PriorityCurrentPrice).count(),
            'priority_archive_prices': self.session.query(PriorityArchivePrice).count(),
            'orders_total': self.session.query(Order).count(),
            'orders_pending': self.session.query(Order).filter(Order.status == 'pending').count(),
            'transactions_total': self.session.query(TransactionLog).count()
        }
        
        return stats