import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from database.database import get_session
from database.models import (
    Stock, PriorityCurrentPrice, Order, TransactionLog, 
    Account, EnvironmentVariable
)
from services.broker_apis import BrokerManager
from services.technical_indicators import TechnicalIndicators
from utils.helpers import calculate_position_size, calculate_lifo_pnl

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingEngine:
    """Main algorithmic trading engine"""
    
    def __init__(self):
        self.broker_manager = BrokerManager()
        self.is_running = False
        self.trading_mode = 'paper'  # paper or live
        self.max_position_size_percent = 5.0
        self.price_update_interval = 30  # seconds
        self.momentum_periods = 3
        self.position_size_percent = 2.0
        
        # Load configuration from environment variables
        self._load_configuration()
        
        # Authenticate with brokers
        self.broker_manager.authenticate_all()
    
    def _load_configuration(self):
        """Load configuration from environment variables table"""
        session = get_session()
        try:
            env_vars = session.query(EnvironmentVariable).all()
            for var in env_vars:
                if var.key == 'TRADING_MODE':
                    self.trading_mode = var.value
                elif var.key == 'MAX_POSITION_SIZE_PERCENT':
                    self.max_position_size_percent = float(var.value)
                elif var.key == 'PRICE_UPDATE_INTERVAL':
                    self.price_update_interval = int(var.value)
                elif var.key == 'ACTIVE_BROKER':
                    self.broker_manager.set_active_broker(var.value)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
        finally:
            session.close()
    
    def start_trading(self):
        """Start the trading engine"""
        if self.is_running:
            logger.warning("Trading engine is already running")
            return
        
        self.is_running = True
        logger.info(f"Starting trading engine in {self.trading_mode} mode")
        
        # Start the main trading loop in a separate thread
        import threading
        self.trading_thread = threading.Thread(target=self._run_trading_loop, daemon=True)
        self.trading_thread.start()
    
    def stop_trading(self):
        """Stop the trading engine"""
        self.is_running = False
        logger.info("Trading engine stopped")
        
        # Wait for trading thread to finish
        if hasattr(self, 'trading_thread') and self.trading_thread.is_alive():
            self.trading_thread.join(timeout=5.0)
    
    def _run_trading_loop(self):
        """Run the trading loop in a thread"""
        import asyncio
        import time
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._trading_loop())
        finally:
            loop.close()
    
    async def _trading_loop(self):
        """Main trading loop"""
        while self.is_running:
            try:
                await self._execute_trading_cycle()
                await asyncio.sleep(self.price_update_interval)
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _execute_trading_cycle(self):
        """Execute one trading cycle"""
        from datetime import datetime
        cycle_time = datetime.now().strftime("%H:%M:%S")
        logger.info(f"🔄 Starting trading cycle at {cycle_time}...")
        
        # Update session state for UI feedback
        import streamlit as st
        if 'last_activity' in st.session_state:
            st.session_state.last_activity = f"Cycle started at {cycle_time}"
        
        # 1. Update priority stock prices
        logger.info("📡 Fetching latest market data...")
        await self._update_priority_prices()
        
        # 2. Evaluate trading opportunities  
        logger.info("🔍 Analyzing trading opportunities...")
        await self._evaluate_trading_opportunities()
        
        # 3. Monitor existing positions
        logger.info("👁️ Monitoring existing positions...")
        await self._monitor_positions()
        
        # 4. Execute risk management
        logger.info("⚖️ Executing risk management...")
        await self._execute_risk_management()
        
        complete_time = datetime.now().strftime("%H:%M:%S")
        logger.info(f"✅ Trading cycle completed at {complete_time}")
        
        # Update completion time for UI
        if 'last_activity' in st.session_state:
            st.session_state.last_activity = f"Completed at {complete_time}"
    
    async def _update_priority_prices(self):
        """Update current prices for priority stocks"""
        session = get_session()
        try:
            # Get priority stocks
            priority_stocks = session.query(Stock).filter(Stock.priority > 0).all()
            
            if not priority_stocks:
                logger.info("⚠️ No priority stocks found - engine will monitor S&P 500 stocks")
                return
            
            symbols = [stock.symbol for stock in priority_stocks]
            logger.info(f"🎯 Monitoring {len(symbols)} priority stocks: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}")
            
            market_data = self.broker_manager.get_market_data(symbols)
            updated_count = 0
            
            for stock in priority_stocks:
                if stock.symbol in market_data:
                    data = market_data[stock.symbol]
                    
                    # Update stock price
                    stock.last_price = data['price']
                    stock.change_percent = data['change_percent']
                    
                    # Add to priority current price table
                    priority_price = PriorityCurrentPrice(
                        stock_id=stock.id,
                        symbol=stock.symbol,
                        datetime=datetime.utcnow(),
                        current_price=data['price'],
                        percent_change_from_previous=data['change_percent'],
                        volume=data.get('volume', 0)
                    )
                    session.add(priority_price)
                    updated_count += 1
                    
            session.commit()
            logger.info(f"📊 Updated prices for {updated_count} stocks successfully")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating priority prices: {e}")
        finally:
            session.close()
    
    async def _evaluate_trading_opportunities(self):
        """Evaluate stocks for trading opportunities"""
        session = get_session()
        try:
            priority_stocks = session.query(Stock).filter(Stock.priority > 0).all()
            
            for stock in priority_stocks:
                await self._evaluate_stock_for_trading(stock, session)
        
        except Exception as e:
            logger.error(f"Error evaluating trading opportunities: {e}")
        finally:
            session.close()
    
    async def _evaluate_stock_for_trading(self, stock: Stock, session):
        """Evaluate individual stock for trading opportunity"""
        try:
            # Get recent price data for momentum analysis
            recent_prices = session.query(PriorityCurrentPrice)\
                .filter(PriorityCurrentPrice.stock_id == stock.id)\
                .order_by(PriorityCurrentPrice.datetime.desc())\
                .limit(self.momentum_periods + 1).all()
            
            if len(recent_prices) < self.momentum_periods + 1:
                return
            
            # Check if order already exists for this stock
            existing_order = session.query(Order)\
                .filter(Order.symbol == stock.symbol)\
                .filter(Order.status == 'pending').first()
            
            if existing_order:
                return  # Skip if order already exists
            
            # Analyze price momentum
            prices = [p.current_price for p in reversed(recent_prices)]
            momentum = TechnicalIndicators.detect_price_momentum(prices, self.momentum_periods)
            
            # Calculate recent volatility
            price_changes = [TechnicalIndicators.calculate_price_change_percentage(
                prices[i], prices[i-1]) for i in range(1, len(prices))]
            
            avg_change = np.mean([abs(change) for change in price_changes])
            
            # Determine if conditions are met for trading
            if self._should_place_trade(momentum, price_changes, avg_change):
                await self._place_algorithmic_trade(stock, momentum, session)
        
        except Exception as e:
            logger.error(f"Error evaluating stock {stock.symbol}: {e}")
    
    def _should_place_trade(self, momentum: str, price_changes: List[float], avg_change: float) -> bool:
        """Determine if trading conditions are met"""
        # Check for consistent momentum
        if momentum == 'sideways':
            return False
        
        # Check if all periods moved in same direction
        if momentum == 'up':
            consistent_direction = all(change > 0 for change in price_changes)
        else:
            consistent_direction = all(change < 0 for change in price_changes)
        
        # Check if average change is significant (configurable threshold)
        significant_movement = avg_change > 1.0  # 1% threshold
        
        return consistent_direction and significant_movement
    
    async def _place_algorithmic_trade(self, stock: Stock, momentum: str, session):
        """Place algorithmic trade based on analysis"""
        try:
            # Get account information
            account_info = self.broker_manager.get_account_info()
            available_cash = account_info.get('cash', 0)
            
            if available_cash < 1000:  # Minimum cash requirement
                logger.warning(f"Insufficient cash for trading: ${available_cash}")
                return
            
            # Calculate position size
            position_value = available_cash * (self.position_size_percent / 100)
            current_price = stock.last_price or 100.0
            quantity = int(position_value / current_price)
            
            if quantity == 0:
                return
            
            # Determine if we should trade options or stock
            if self._should_trade_options(stock, momentum):
                await self._place_options_trade(stock, momentum, quantity, session)
            else:
                await self._place_stock_trade(stock, momentum, quantity, session)
        
        except Exception as e:
            logger.error(f"Error placing algorithmic trade for {stock.symbol}: {e}")
    
    def _should_trade_options(self, stock: Stock, momentum: str) -> bool:
        """Determine if we should trade options instead of stock"""
        # Trade options if stock has options and momentum is strong
        if not stock.has_options:
            return False
        
        # Check if conditions favor options trading
        # (this would include analysis of major indices, volatility, etc.)
        return True  # Simplified for now
    
    async def _place_options_trade(self, stock: Stock, momentum: str, quantity: int, session):
        """Place options trade"""
        try:
            # Determine option type based on momentum
            option_type = 'call' if momentum == 'up' else 'put'
            
            # Calculate strike price (simplified - would use more sophisticated logic)
            current_price = stock.last_price
            if option_type == 'call':
                strike_price = current_price * 1.05  # 5% OTM call
            else:
                strike_price = current_price * 0.95  # 5% OTM put
            
            # Set expiration date (simplified - would use more sophisticated logic)
            expiration_date = datetime.now() + timedelta(days=30)
            
            # Create order record
            order = Order(
                account_id=1,  # Default account
                symbol=stock.symbol,
                order_type='market',
                side='buy',
                quantity=quantity,
                asset_type='option',
                option_type=option_type,
                strike_price=strike_price,
                expiration_date=expiration_date,
                status='pending'
            )
            session.add(order)
            session.commit()
            
            # Place order with broker (in paper trading mode, this is simulated)
            if self.trading_mode == 'paper':
                await self._simulate_option_execution(order, session)
            else:
                # Would place real order with broker
                logger.info(f"Would place live options order: {option_type} {stock.symbol}")
        
        except Exception as e:
            logger.error(f"Error placing options trade: {e}")
            session.rollback()
    
    async def _place_stock_trade(self, stock: Stock, momentum: str, quantity: int, session):
        """Place stock trade"""
        try:
            side = 'buy' if momentum == 'up' else 'sell'
            
            # Create order record
            order = Order(
                account_id=1,
                symbol=stock.symbol,
                order_type='market',
                side=side,
                quantity=quantity,
                asset_type='stock',
                status='pending'
            )
            session.add(order)
            session.commit()
            
            # Place order with broker
            if self.trading_mode == 'paper':
                await self._simulate_stock_execution(order, session)
            else:
                broker_response = self.broker_manager.place_order(
                    stock.symbol, side, quantity, 'market'
                )
                order.broker_order_id = broker_response.get('id')
                session.commit()
        
        except Exception as e:
            logger.error(f"Error placing stock trade: {e}")
            session.rollback()
    
    async def _simulate_option_execution(self, order: Order, session):
        """Simulate option execution for paper trading"""
        try:
            # Simulate option pricing (simplified)
            option_price = 2.50  # Would use Black-Scholes or similar
            
            # Mark order as filled
            order.status = 'filled'
            order.filled_at = datetime.utcnow()
            
            # Create transaction log
            transaction = TransactionLog(
                order_id=order.id,
                user_id=order.user_id,
                account_id=order.account_id,
                stock_id=order.stock_id,
                symbol=order.symbol,
                transaction_type=order.action,
                quantity=order.quantity,
                price_per_share=option_price,
                total_amount=option_price * order.quantity,
                fees=order.estimated_fees or 0.0,
                transaction_date=datetime.utcnow()
            )
            session.add(transaction)
            session.commit()
            
            logger.info(f"Simulated option execution: {order.action} {order.quantity} {order.option_type} {order.symbol} @ ${option_price}")
        
        except Exception as e:
            logger.error(f"Error simulating option execution: {e}")
            session.rollback()
    
    async def _simulate_stock_execution(self, order: Order, session):
        """Simulate stock execution for paper trading"""
        try:
            # Use current market price
            stock = session.query(Stock).filter(Stock.symbol == order.symbol).first()
            execution_price = stock.last_price or 100.0
            
            # Mark order as filled
            order.status = 'filled'
            order.filled_at = datetime.utcnow()
            
            # Create transaction log
            transaction = TransactionLog(
                order_id=order.id,
                user_id=order.user_id,
                account_id=order.account_id,
                stock_id=order.stock_id,
                symbol=order.symbol,
                transaction_type=order.action,
                quantity=order.quantity,
                price_per_share=execution_price,
                total_amount=execution_price * order.quantity,
                fees=order.estimated_fees or 0.0,
                transaction_date=datetime.utcnow()
            )
            session.add(transaction)
            session.commit()
            
            logger.info(f"Simulated stock execution: {order.action} {order.quantity} {order.symbol} @ ${execution_price}")
        
        except Exception as e:
            logger.error(f"Error simulating stock execution: {e}")
            session.rollback()
    
    async def _monitor_positions(self):
        """Monitor existing positions for exit signals"""
        session = get_session()
        try:
            # Get open positions from transaction log
            open_positions = self._get_open_positions(session)
            
            for position in open_positions:
                await self._evaluate_position_exit(position, session)
        
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")
        finally:
            session.close()
    
    def _get_open_positions(self, session) -> List[Dict]:
        """Get currently open positions"""
        # Query transaction log to determine open positions
        transactions = session.query(TransactionLog).order_by(TransactionLog.transaction_date).all()
        
        positions = {}
        for transaction in transactions:
            key = f"{transaction.symbol}_{transaction.asset_type}"
            if transaction.option_type:
                key += f"_{transaction.option_type}_{transaction.strike_price}_{transaction.expiration_date}"
            
            if key not in positions:
                positions[key] = {
                    'symbol': transaction.symbol,
                    'asset_type': transaction.asset_type,
                    'option_type': transaction.option_type,
                    'strike_price': transaction.strike_price,
                    'expiration_date': transaction.expiration_date,
                    'quantity': 0,
                    'avg_price': 0,
                    'transactions': []
                }
            
            position = positions[key]
            position['transactions'].append(transaction)
            
            if transaction.side == 'buy':
                position['quantity'] += transaction.quantity
            else:
                position['quantity'] -= transaction.quantity
        
        # Return only positions with non-zero quantity
        return [pos for pos in positions.values() if pos['quantity'] != 0]
    
    async def _evaluate_position_exit(self, position: Dict, session):
        """Evaluate if position should be closed"""
        try:
            symbol = position['symbol']
            
            # Get current price
            current_price = self._get_current_price(symbol, position['asset_type'])
            
            # Get recent price history for momentum analysis
            recent_prices = session.query(PriorityCurrentPrice)\
                .filter(PriorityCurrentPrice.stock_id == 
                       session.query(Stock).filter(Stock.symbol == symbol).first().id)\
                .order_by(PriorityCurrentPrice.datetime.desc())\
                .limit(5).all()
            
            if len(recent_prices) < 3:
                return
            
            prices = [p.current_price for p in reversed(recent_prices)]
            
            # Check for exit signals
            if self._should_exit_position(position, prices, current_price):
                await self._close_position(position, session)
        
        except Exception as e:
            logger.error(f"Error evaluating position exit for {position['symbol']}: {e}")
    
    def _get_current_price(self, symbol: str, asset_type: str) -> float:
        """Get current price for symbol"""
        market_data = self.broker_manager.get_market_data([symbol])
        if symbol in market_data:
            return market_data[symbol]['price']
        return 100.0  # Fallback price
    
    def _should_exit_position(self, position: Dict, recent_prices: List[float], current_price: float) -> bool:
        """Determine if position should be exited"""
        # Check for momentum slowdown or reversal
        if len(recent_prices) < 3:
            return False
        
        # Calculate recent changes
        changes = [recent_prices[i] - recent_prices[i-1] for i in range(1, len(recent_prices))]
        
        # Check if momentum is slowing down
        if len(changes) >= 2:
            if position['asset_type'] == 'option':
                # For options, exit more aggressively
                if abs(changes[-1]) < abs(changes[-2]) * 0.5:  # Momentum slowing
                    return True
                
                # Check for reversal
                if (changes[-2] > 0 and changes[-1] < 0) or (changes[-2] < 0 and changes[-1] > 0):
                    return True
        
        return False
    
    async def _close_position(self, position: Dict, session):
        """Close an existing position"""
        try:
            symbol = position['symbol']
            quantity = abs(position['quantity'])
            side = 'sell' if position['quantity'] > 0 else 'buy'
            
            # Create closing order
            order = Order(
                account_id=1,
                symbol=symbol,
                order_type='market',
                side=side,
                quantity=quantity,
                asset_type=position['asset_type'],
                option_type=position['option_type'],
                strike_price=position['strike_price'],
                expiration_date=position['expiration_date'],
                status='pending'
            )
            session.add(order)
            session.commit()
            
            # Execute closing order
            if self.trading_mode == 'paper':
                if position['asset_type'] == 'option':
                    await self._simulate_option_execution(order, session)
                else:
                    await self._simulate_stock_execution(order, session)
            
            logger.info(f"Closed position: {side} {quantity} {symbol}")
        
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            session.rollback()
    
    async def _execute_risk_management(self):
        """Execute risk management rules"""
        try:
            # Check overall portfolio risk
            account_info = self.broker_manager.get_account_info()
            portfolio_value = account_info.get('portfolio_value', 0)
            
            # Implement stop-loss logic, position sizing limits, etc.
            # This would include more sophisticated risk management
            
            logger.debug("Risk management check completed")
        
        except Exception as e:
            logger.error(f"Error in risk management: {e}")
