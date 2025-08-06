import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import threading
import time

# Import custom modules
from database.database import init_database, get_session
from database.models import User, EnvironmentVariable, Stock, Account
from utils.auth import authenticate_user, get_current_user, check_permission
from services.data_fetcher import DataFetcher
from services.trading_engine import TradingEngine
from services.technical_indicators import TechnicalIndicators
from utils.helpers import format_currency, calculate_portfolio_value

# Initialize database
init_database()

# Configure page
st.set_page_config(
    page_title="Algorithmic Trading Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'trading_engine' not in st.session_state:
    st.session_state.trading_engine = None

def login_page():
    st.title("🔐 Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            user = authenticate_user(username, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def sidebar_navigation():
    st.sidebar.title("📈 Trading Platform")
    
    if st.session_state.authenticated:
        user = st.session_state.user
        st.sidebar.write(f"👤 Welcome, {user.username}")
        st.sidebar.write(f"🏷️ Role: {user.role}")
        
        # Show engine status in sidebar
        engine_status = st.session_state.get('engine_status', 'Stopped')
        if engine_status == "Running":
            st.sidebar.success("🤖 Engine: RUNNING")
        else:
            st.sidebar.warning("🤖 Engine: STOPPED")
        
        # Core navigation menu
        pages = {
            "Trading": "💹",
            "Orders": "📋", 
            "Positions": "💼"
        }
        
        # Add admin pages
        if user.role == 'admin':
            pages["Settings"] = "⚙️"
            pages["Database"] = "🗄️"
        
        selected_page = st.sidebar.radio(
            "Navigation",
            list(pages.keys()),
            format_func=lambda x: f"{pages[x]} {x}"
        )
        
        # Logout button
        if st.sidebar.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.trading_engine = None
            st.rerun()
        
        return selected_page
    
    return None

def show_orders_page():
    """Display orders table per requirements"""
    st.title("📋 Orders")
    
    session = get_session()
    try:
        orders = session.query(Order).order_by(Order.submitted_at.desc()).all()
        
        if orders:
            order_data = []
            for order in orders:
                order_data.append({
                    "Symbol": order.symbol,
                    "Action": order.side.title(),
                    "Asset": order.asset_type.title(),
                    "Quantity": order.quantity,
                    "Order Type": order.order_type.title(),
                    "Limit Price": f"${order.limit_price:.2f}" if order.limit_price else "N/A",
                    "Status": order.status.title(),
                    "Submitted": order.submitted_at.strftime("%Y-%m-%d %H:%M"),
                    "Filled": order.filled_at.strftime("%Y-%m-%d %H:%M") if order.filled_at else "N/A"
                })
            
            df = pd.DataFrame(order_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No orders found.")
    finally:
        session.close()

def show_positions_page():
    """Display current positions and transaction log"""
    st.title("💼 Positions & Transaction Log")
    
    # Current positions
    st.subheader("Current Positions")
    
    session = get_session()
    try:
        # Calculate positions from transaction log
        transactions = session.query(TransactionLog).order_by(TransactionLog.transaction_date).all()
        
        positions = {}
        for transaction in transactions:
            key = f"{transaction.symbol}_{transaction.asset_type}"
            if transaction.option_type:
                key += f"_{transaction.option_type}_{transaction.strike_price}"
            
            if key not in positions:
                positions[key] = {
                    'symbol': transaction.symbol,
                    'asset_type': transaction.asset_type,
                    'option_type': transaction.option_type,
                    'strike_price': transaction.strike_price,
                    'quantity': 0,
                    'avg_price': 0,
                    'total_cost': 0
                }
            
            pos = positions[key]
            if transaction.side == 'buy':
                pos['quantity'] += transaction.quantity
                pos['total_cost'] += transaction.price * transaction.quantity
            else:
                pos['quantity'] -= transaction.quantity
                pos['total_cost'] -= transaction.price * transaction.quantity
            
            if pos['quantity'] > 0:
                pos['avg_price'] = pos['total_cost'] / pos['quantity']
        
        # Filter non-zero positions
        active_positions = [pos for pos in positions.values() if pos['quantity'] != 0]
        
        if active_positions:
            pos_data = []
            for pos in active_positions:
                pos_data.append({
                    "Symbol": pos['symbol'],
                    "Asset": pos['asset_type'].title(),
                    "Type": pos['option_type'].title() if pos['option_type'] else "N/A",
                    "Strike": f"${pos['strike_price']:.2f}" if pos['strike_price'] else "N/A",
                    "Quantity": pos['quantity'],
                    "Avg Price": f"${pos['avg_price']:.2f}",
                    "Total Cost": f"${pos['total_cost']:.2f}"
                })
            
            df = pd.DataFrame(pos_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No current positions.")
        
        # Transaction log with LIFO gain/loss
        st.subheader("Transaction Log (LIFO)")
        
        recent_transactions = session.query(TransactionLog).order_by(TransactionLog.transaction_date.desc()).limit(50).all()
        
        if recent_transactions:
            trans_data = []
            for transaction in recent_transactions:
                trans_data.append({
                    "Date": transaction.transaction_date.strftime("%Y-%m-%d %H:%M"),
                    "Symbol": transaction.symbol,
                    "Side": transaction.side.title(),
                    "Asset": transaction.asset_type.title(),
                    "Quantity": transaction.quantity,
                    "Price": f"${transaction.price:.2f}",
                    "Total": f"${transaction.price * transaction.quantity:.2f}",
                    "P&L": f"${transaction.gain_loss:.2f}" if transaction.gain_loss else "N/A"
                })
            
            df = pd.DataFrame(trans_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No transactions found.")
            
    finally:
        session.close()

def show_settings_page():
    """Basic environment variables configuration"""
    st.title("⚙️ Settings")
    
    session = get_session()
    try:
        # Get environment variables
        env_vars = {var.key: var.value for var in session.query(EnvironmentVariable).all()}
        
        st.subheader("Trading Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trading_mode = st.selectbox(
                "Trading Mode",
                ["paper", "live"],
                index=0 if env_vars.get('TRADING_MODE', 'paper') == 'paper' else 1
            )
            
            price_interval = st.number_input(
                "Price Update Interval (seconds)",
                min_value=5,
                max_value=300,
                value=int(env_vars.get('PRICE_UPDATE_INTERVAL', '30'))
            )
        
        with col2:
            max_position = st.number_input(
                "Max Position Size (%)",
                min_value=1.0,
                max_value=25.0,
                value=float(env_vars.get('MAX_POSITION_SIZE_PERCENT', '5.0')),
                step=0.5
            )
            
            archive_days = st.number_input(
                "Archive Retention (days)",
                min_value=7,
                max_value=365,
                value=int(env_vars.get('ARCHIVE_RETENTION_DAYS', '30'))
            )
        
        if st.button("Save Settings"):
            # Update environment variables
            for key, value in [
                ('TRADING_MODE', trading_mode),
                ('PRICE_UPDATE_INTERVAL', str(price_interval)),
                ('MAX_POSITION_SIZE_PERCENT', str(max_position)),
                ('ARCHIVE_RETENTION_DAYS', str(archive_days))
            ]:
                env_var = session.query(EnvironmentVariable).filter(EnvironmentVariable.key == key).first()
                if env_var:
                    env_var.value = value
                else:
                    env_var = EnvironmentVariable(key=key, value=value)
                    session.add(env_var)
            
            session.commit()
            st.success("Settings saved!")
            st.rerun()
    
    finally:
        session.close()

# Remove old dashboard function - now using streamlined functions above


def load_page_content(page_name):
    """Load core trading functionality only"""
    if page_name == "Trading":
        show_trading_interface()
    elif page_name == "Orders":
        show_orders_page()
    elif page_name == "Positions":
        show_positions_page()
    elif page_name == "Settings":
        show_settings_page()
    elif page_name == "Database":
        from app_pages.database_admin import render_database_admin_page
        render_database_admin_page()

def main():
    """Main application entry point"""
    
    if not st.session_state.authenticated:
        login_page()
        return
    
    # Show sidebar navigation
    selected_page = sidebar_navigation()
    
    if selected_page:
        load_page_content(selected_page)
    
    # Background tasks status
    with st.sidebar:
        st.divider()
        st.subheader("🔄 Background Tasks")
        
        # Data fetcher status
        if st.button("🔄 Refresh Market Data"):
            with st.spinner("Fetching market data..."):
                try:
                    data_fetcher = DataFetcher()
                    data_fetcher.update_priority_stocks()
                    st.success("Market data updated!")
                except Exception as e:
                    st.error(f"Error updating data: {str(e)}")
        
        # Show last update time
        st.caption("Last update: 2 minutes ago")

if __name__ == "__main__":
    main()
