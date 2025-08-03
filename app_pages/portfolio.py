import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

from database.database import get_session
from database.models import Stock, Order, TransactionLog, Account, User
from services.broker_apis import BrokerManager
from utils.helpers import (
    format_currency, format_percentage, calculate_portfolio_value,
    calculate_lifo_pnl, calculate_option_metrics, calculate_sector_allocation,
    calculate_risk_metrics
)
from utils.auth import check_permission
from utils.broker_status_widget import display_mini_broker_status

def show_portfolio_page():
    """Portfolio overview and analysis page"""
    st.title("💼 Portfolio Management")
    
    # Check user permissions - viewers can see portfolio but not trade
    user = st.session_state.user
    is_viewer = user.role == 'viewer'
    
    if is_viewer:
        st.info("👁️ Viewing in read-only mode. Trading features are disabled for viewer accounts.")
    elif not check_permission(user, 'trader'):
        st.error("🚫 Access denied. Portfolio access requires trader privileges or higher.")
        return
    
    # Mini broker status
    is_connected = display_mini_broker_status()
    if not is_connected:
        st.warning("⚠️ Broker connection issues. Portfolio data may be limited.")
    
    # Portfolio overview metrics
    _show_portfolio_overview()
    
    # Current positions
    st.subheader("📊 Current Positions")
    _show_current_positions()
    
    # Performance analysis
    st.subheader("📈 Performance Analysis")
    _show_performance_analysis()
    
    # Risk metrics
    st.subheader("⚠️ Risk Analysis")
    _show_risk_analysis()
    
    # Transaction history
    st.subheader("📋 Transaction History")
    _show_transaction_history()

def _show_portfolio_overview():
    """Display portfolio overview metrics"""
    session = get_session()
    
    # Use centralized broker manager
    if 'broker_manager' not in st.session_state:
        st.session_state.broker_manager = BrokerManager()
    
    broker_manager = st.session_state.broker_manager
    
    # Display current broker info
    active_broker = broker_manager.get_active_broker_name()
    st.info(f"🎯 Data from: {active_broker}")
    
    try:
        # Get account information
        account_info = broker_manager.get_account_info()
        
        # Get current positions
        positions = broker_manager.get_positions()
        
        # Calculate metrics
        portfolio_value = account_info.get('portfolio_value', 0)
        cash_balance = account_info.get('cash', 0)
        day_pnl = 0  # Would calculate from daily changes
        total_pnl = 0  # Would calculate from cost basis
        
        # Display key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Portfolio Value",
                format_currency(portfolio_value),
                delta=format_currency(day_pnl)
            )
        
        with col2:
            st.metric(
                "Cash Balance",
                format_currency(cash_balance),
                delta=None
            )
        
        with col3:
            buying_power = account_info.get('buying_power', cash_balance)
            st.metric(
                "Buying Power",
                format_currency(buying_power),
                delta=None
            )
        
        with col4:
            num_positions = len(positions)
            st.metric(
                "Active Positions",
                str(num_positions),
                delta=None
            )
        
        # Portfolio allocation chart
        if positions:
            _show_portfolio_allocation(positions)
    
    except Exception as e:
        st.error(f"Error loading portfolio overview: {e}")
    finally:
        session.close()

def _show_portfolio_allocation(positions):
    """Show portfolio allocation pie chart"""
    if not positions:
        st.info("No positions to display")
        return
    
    # Prepare data for pie chart
    symbols = []
    values = []
    
    for position in positions:
        symbols.append(position['symbol'])
        values.append(abs(position['market_value']))
    
    # Create pie chart
    fig = px.pie(
        values=values,
        names=symbols,
        title="Portfolio Allocation by Position"
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def _show_current_positions():
    """Display current portfolio positions"""
    session = get_session()
    broker_manager = BrokerManager()
    
    try:
        # Get positions from broker
        positions = broker_manager.get_positions()
        
        if not positions:
            st.info("No current positions")
            return
        
        # Get current market data for P&L calculation
        symbols = [pos['symbol'] for pos in positions]
        market_data = broker_manager.get_market_data(symbols)
        
        # Prepare positions data
        position_data = []
        total_value = 0
        total_pnl = 0
        
        for position in positions:
            symbol = position['symbol']
            quantity = position['quantity']
            market_value = position['market_value']
            cost_basis = position['cost_basis']
            unrealized_pnl = position['unrealized_pnl']
            
            # Calculate percentage of portfolio
            portfolio_percent = 0  # Would calculate based on total portfolio value
            
            # Get current price
            current_price = market_data.get(symbol, {}).get('price', 0)
            
            position_data.append({
                "Symbol": symbol,
                "Quantity": quantity,
                "Current Price": format_currency(current_price),
                "Market Value": format_currency(market_value),
                "Cost Basis": format_currency(cost_basis),
                "Unrealized P&L": format_currency(unrealized_pnl),
                "% of Portfolio": format_percentage(portfolio_percent),
                "Side": position['side']
            })
            
            total_value += market_value
            total_pnl += unrealized_pnl
        
        # Display positions table
        df = pd.DataFrame(position_data)
        
        # Apply styling
        def color_pnl(val):
            if 'P&L' in val or val.startswith('$'):
                try:
                    amount = float(val.replace('$', '').replace(',', ''))
                    if amount > 0:
                        return 'color: green'
                    elif amount < 0:
                        return 'color: red'
                except:
                    pass
            return ''
        
        styled_df = df.style.map(color_pnl, subset=['Unrealized P&L'])
        st.dataframe(styled_df, use_container_width=True)
        
        # Summary metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Market Value", format_currency(total_value))
        with col2:
            st.metric("Total Unrealized P&L", format_currency(total_pnl))
    
    except Exception as e:
        st.error(f"Error loading positions: {e}")
    finally:
        session.close()

def _show_performance_analysis():
    """Show portfolio performance analysis"""
    session = get_session()
    
    try:
        # Get transaction history for performance calculation
        transactions = session.query(TransactionLog).order_by(TransactionLog.transaction_date).all()
        
        if not transactions:
            st.info("No transaction history available for performance analysis")
            return
        
        # Calculate daily returns (simplified)
        daily_returns = _calculate_daily_returns(transactions)
        
        if daily_returns:
            # Calculate performance metrics
            risk_metrics = calculate_risk_metrics(daily_returns)
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Return", format_percentage(risk_metrics.get('total_return', 0) * 100))
            
            with col2:
                st.metric("Average Daily Return", format_percentage(risk_metrics.get('average_return', 0) * 100))
            
            with col3:
                st.metric("Volatility", format_percentage(risk_metrics.get('volatility', 0) * 100))
            
            with col4:
                st.metric("Sharpe Ratio", f"{risk_metrics.get('sharpe_ratio', 0):.2f}")
            
            # Performance chart
            _show_performance_chart(daily_returns)
        else:
            st.info("Insufficient data for performance analysis")
    
    except Exception as e:
        st.error(f"Error in performance analysis: {e}")
    finally:
        session.close()

def _calculate_daily_returns(transactions):
    """Calculate daily returns from transaction history"""
    if not transactions:
        return []
    
    # Group transactions by date
    daily_pnl = {}
    
    for transaction in transactions:
        date = transaction.transaction_date.date()
        
        if date not in daily_pnl:
            daily_pnl[date] = 0
        
        # Simplified P&L calculation
        if transaction.side == 'sell':
            daily_pnl[date] += transaction.price * transaction.quantity
        else:
            daily_pnl[date] -= transaction.price * transaction.quantity
    
    # Convert to returns (simplified)
    returns = []
    portfolio_value = 100000  # Starting value assumption
    
    for date in sorted(daily_pnl.keys()):
        pnl = daily_pnl[date]
        daily_return = pnl / portfolio_value
        returns.append(daily_return)
        portfolio_value += pnl
    
    return returns

def _show_performance_chart(daily_returns):
    """Show performance chart"""
    if not daily_returns:
        return
    
    # Calculate cumulative returns
    cumulative_returns = []
    cumulative = 1
    
    for ret in daily_returns:
        cumulative *= (1 + ret)
        cumulative_returns.append((cumulative - 1) * 100)
    
    # Create chart
    dates = [datetime.now() - timedelta(days=len(daily_returns)-i-1) for i in range(len(daily_returns))]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=cumulative_returns,
        mode='lines',
        name='Cumulative Return',
        line=dict(color='blue', width=2)
    ))
    
    fig.update_layout(
        title="Portfolio Performance Over Time",
        xaxis_title="Date",
        yaxis_title="Cumulative Return (%)",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def _show_risk_analysis():
    """Show risk analysis metrics"""
    session = get_session()
    broker_manager = BrokerManager()
    
    try:
        # Get current positions
        positions = broker_manager.get_positions()
        
        if not positions:
            st.info("No positions for risk analysis")
            return
        
        # Calculate risk metrics
        total_exposure = sum(abs(pos['market_value']) for pos in positions)
        account_info = broker_manager.get_account_info()
        portfolio_value = account_info.get('portfolio_value', total_exposure)
        
        # Risk metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Concentration risk
            max_position = max((abs(pos['market_value']) for pos in positions), default=0)
            concentration = (max_position / portfolio_value * 100) if portfolio_value > 0 else 0
            st.metric("Largest Position", format_percentage(concentration))
            
            if concentration > 20:
                st.warning("⚠️ High concentration risk")
        
        with col2:
            # Leverage
            leverage = total_exposure / portfolio_value if portfolio_value > 0 else 0
            st.metric("Portfolio Leverage", f"{leverage:.2f}x")
            
            if leverage > 2:
                st.warning("⚠️ High leverage detected")
        
        with col3:
            # Day trading risk
            day_trade_count = account_info.get('day_trade_count', 0)
            st.metric("Day Trades (5 days)", str(day_trade_count))
            
            if day_trade_count >= 3:
                st.warning("⚠️ Approaching day trade limit")
        
        # Sector allocation
        _show_sector_risk_analysis(positions, session)
    
    except Exception as e:
        st.error(f"Error in risk analysis: {e}")
    finally:
        session.close()

def _show_sector_risk_analysis(positions, session):
    """Show sector allocation for risk analysis"""
    try:
        # Get sector information for positions
        symbols = [pos['symbol'] for pos in positions]
        stocks = session.query(Stock).filter(Stock.symbol.in_(symbols)).all()
        
        stock_sectors = {stock.symbol: stock.sector for stock in stocks}
        
        # Calculate sector allocation
        sector_allocation = calculate_sector_allocation(positions, stock_sectors)
        
        if sector_allocation:
            # Create sector allocation chart
            sectors = list(sector_allocation.keys())
            percentages = list(sector_allocation.values())
            
            fig = px.bar(
                x=sectors,
                y=percentages,
                title="Portfolio Allocation by Sector",
                labels={'x': 'Sector', 'y': 'Allocation (%)'}
            )
            
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            # Risk warnings
            max_sector_allocation = max(percentages) if percentages else 0
            if max_sector_allocation > 40:
                st.warning(f"⚠️ High sector concentration: {max_sector_allocation:.1f}% in one sector")
    
    except Exception as e:
        st.error(f"Error in sector risk analysis: {e}")

def _show_transaction_history():
    """Show transaction history with filtering"""
    session = get_session()
    
    try:
        # Date range filter
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            start_date = st.date_input("From Date", value=datetime.now() - timedelta(days=30))
        
        with col2:
            end_date = st.date_input("To Date", value=datetime.now())
        
        with col3:
            transaction_type = st.selectbox(
                "Transaction Type",
                ["All", "Stock", "Option", "Buy Only", "Sell Only"]
            )
        
        # Query transactions
        query = session.query(TransactionLog).filter(
            TransactionLog.transaction_date >= datetime.combine(start_date, datetime.min.time()),
            TransactionLog.transaction_date <= datetime.combine(end_date, datetime.max.time())
        )
        
        # Apply filters
        if transaction_type == "Stock":
            query = query.filter(TransactionLog.asset_type == 'stock')
        elif transaction_type == "Option":
            query = query.filter(TransactionLog.asset_type == 'option')
        elif transaction_type == "Buy Only":
            query = query.filter(TransactionLog.side == 'buy')
        elif transaction_type == "Sell Only":
            query = query.filter(TransactionLog.side == 'sell')
        
        transactions = query.order_by(TransactionLog.transaction_date.desc()).all()
        
        if transactions:
            # Prepare transaction data
            transaction_data = []
            
            for tx in transactions:
                asset_info = tx.symbol
                if tx.asset_type == 'option':
                    asset_info += f" {tx.option_type.upper()}" if tx.option_type else ""
                    if tx.strike_price:
                        asset_info += f" ${tx.strike_price}"
                    if tx.expiration_date:
                        asset_info += f" {tx.expiration_date.strftime('%m/%d/%y')}"
                
                transaction_data.append({
                    "Date": tx.transaction_date.strftime("%Y-%m-%d %H:%M"),
                    "Asset": asset_info,
                    "Side": tx.side.upper(),
                    "Quantity": tx.quantity,
                    "Price": format_currency(tx.price),
                    "Total": format_currency(tx.price * tx.quantity),
                    "P&L": format_currency(tx.realized_pnl) if tx.realized_pnl else "N/A"
                })
            
            # Display transactions
            df = pd.DataFrame(transaction_data)
            
            # Apply styling
            def color_side(val):
                if val == 'BUY':
                    return 'color: green'
                elif val == 'SELL':
                    return 'color: red'
                return ''
            
            def color_pnl(val):
                if val != "N/A" and val.startswith('$'):
                    try:
                        amount = float(val.replace('$', '').replace(',', ''))
                        if amount > 0:
                            return 'color: green'
                        elif amount < 0:
                            return 'color: red'
                    except:
                        pass
                return ''
            
            styled_df = df.style.map(color_side, subset=['Side'])\
                              .map(color_pnl, subset=['P&L'])
            
            st.dataframe(styled_df, use_container_width=True)
            
            # Summary statistics
            total_trades = len(transactions)
            buy_trades = len([tx for tx in transactions if tx.side == 'buy'])
            sell_trades = len([tx for tx in transactions if tx.side == 'sell'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Trades", str(total_trades))
            with col2:
                st.metric("Buy Trades", str(buy_trades))
            with col3:
                st.metric("Sell Trades", str(sell_trades))
        else:
            st.info("No transactions found for the selected criteria")
    
    except Exception as e:
        st.error(f"Error loading transaction history: {e}")
    finally:
        session.close()
