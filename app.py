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
        
        # Navigation menu based on user role
        pages = {
            "Dashboard": "📊",
            "Portfolio": "💼",
            "AI Assistant": "🤖"
        }
        
        # Add role-specific pages
        if user.role in ['trader', 'admin']:
            pages["Trading"] = "💹"
            pages["Trading Engine"] = "🤖"
            pages["Settings"] = "⚙️"
        elif user.role == 'viewer':
            # Viewers get limited settings (just profile)
            pages["Settings"] = "⚙️"
        
        # Add admin-only pages
        if user.role == 'admin':
            pages["Admin"] = "🛠️"
            pages["Database Admin"] = "🗄️"
        
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

def main_dashboard():
    st.title("📊 Trading Dashboard")
    
    # Initialize broker connection for real data
    from services.broker_apis import BrokerManager
    
    if 'broker_manager' not in st.session_state:
        st.session_state.broker_manager = BrokerManager()
    
    broker_manager = st.session_state.broker_manager
    
    # Get real account data
    account_info = broker_manager.get_account_info()
    positions = broker_manager.get_positions()
    
    # Quick stats with real data
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if 'error' not in account_info:
            portfolio_value = account_info.get('portfolio_value', 0)
            st.metric("Portfolio Value", f"${portfolio_value:,.2f}")
        else:
            st.metric("Portfolio Value", "Not Connected", "Check API")
    
    with col2:
        if 'error' not in account_info:
            cash = account_info.get('cash', 0)
            st.metric("Available Cash", f"${cash:,.2f}")
        else:
            st.metric("Available Cash", "Not Connected")
    
    with col3:
        st.metric("Active Positions", str(len(positions)))
    
    with col4:
        if 'error' not in account_info:
            day_trades = account_info.get('day_trade_count', 0)
            st.metric("Day Trades Used", str(day_trades))
        else:
            st.metric("Connection", "❌ Disconnected")
    
    # Live market overview
    st.subheader("📈 Live Market Overview")
    
    # Get real market data
    symbols = ['SPY', 'QQQ', 'DIA', 'VIX']
    market_data = broker_manager.get_market_data(symbols)
    
    if market_data:
        cols = st.columns(len(symbols))
        index_names = {'SPY': 'S&P 500 ETF', 'QQQ': 'NASDAQ ETF', 'DIA': 'DOW ETF', 'VIX': 'Volatility Index'}
        
        for i, symbol in enumerate(symbols):
            with cols[i]:
                if symbol in market_data:
                    data = market_data[symbol]
                    price = data.get('price', 0)
                    change_pct = data.get('change_percent', 0)
                    delta_color = "normal" if change_pct >= 0 else "inverse"
                    
                    st.metric(
                        index_names.get(symbol, symbol),
                        f"${price:.2f}",
                        f"{change_pct:+.2f}%",
                        delta_color=delta_color
                    )
                else:
                    st.metric(index_names.get(symbol, symbol), "Loading...")
    else:
        st.warning("Unable to fetch live market data. Check connection.")
    
    # Current positions
    st.subheader("📊 Current Positions")
    
    if positions:
        positions_df = pd.DataFrame(positions)
        # Format the dataframe for better display
        if not positions_df.empty:
            positions_df['market_value'] = positions_df['market_value'].apply(lambda x: f"${x:,.2f}")
            positions_df['cost_basis'] = positions_df['cost_basis'].apply(lambda x: f"${x:,.2f}")
            positions_df['unrealized_pnl'] = positions_df['unrealized_pnl'].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(positions_df, use_container_width=True)
    else:
        st.info("No current positions. Start trading to see your portfolio here.")
    
    # Priority stocks monitoring
    st.subheader("🎯 Priority Stocks")
    
    try:
        session = get_session()
        priority_stocks = session.query(Stock).filter(Stock.priority > 0).all()
        
        if priority_stocks:
            priority_data = []
            for stock in priority_stocks:
                priority_data.append({
                    "Symbol": stock.symbol,
                    "Name": stock.name,
                    "Sector": stock.sector,
                    "Priority": stock.priority,
                    "Last Price": f"${stock.last_price:.2f}" if stock.last_price is not None else "N/A",
                    "Change %": f"{stock.change_percent:.2f}%" if stock.change_percent is not None else "N/A"
                })
            
            df = pd.DataFrame(priority_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No priority stocks identified. Run market analysis to populate priority stocks.")
        
        session.close()
    except Exception as e:
        st.error(f"Error loading priority stocks: {str(e)}")
    
    # Trading engine status
    st.subheader("🤖 Trading Engine Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Get actual engine status from session state
        engine_status = st.session_state.get('engine_status', 'Stopped')
        if engine_status == "Running":
            st.success("✅ Trading Engine: RUNNING")
            st.info("Engine is actively monitoring markets and placing trades.")
        else:
            st.warning("⏸️ Trading Engine: STOPPED")
            st.info("No automated trading is occurring.")
        
        # Link to control page
        if st.button("🎮 Go to Engine Control"):
            # Force page refresh to sync status
            st.rerun()
    
    with col2:
        # Show current trading mode from database
        session = get_session()
        try:
            mode_var = session.query(EnvironmentVariable).filter(
                EnvironmentVariable.key == 'TRADING_MODE'
            ).first()
            current_mode = mode_var.value if mode_var else 'paper'
            st.info(f"🎯 Trading Mode: {current_mode.title()}")
            
            # Show recent engine activity
            if engine_status == "Running":
                st.metric("Engine Cycles", "Running continuously")
            else:
                st.metric("Engine Cycles", "0 (Stopped)")
        finally:
            session.close()

def load_page_content(page_name):
    """Dynamically load page content"""
    if page_name == "Dashboard":
        main_dashboard()
    elif page_name == "Trading":
        from app_pages.trading import show_trading_page
        show_trading_page()
    elif page_name == "Trading Engine":
        from app_pages.trading_engine_control import show_trading_engine_control
        show_trading_engine_control()
    elif page_name == "Portfolio":
        from app_pages.portfolio import show_portfolio_page
        show_portfolio_page()
    elif page_name == "AI Assistant":
        from app_pages.ai_assistant import show_ai_assistant_page
        show_ai_assistant_page()
    elif page_name == "Settings":
        from app_pages.settings import show_settings_page
        show_settings_page()
    elif page_name == "Admin":
        from app_pages.admin import show_admin_page
        show_admin_page()
    elif page_name == "Database Admin":
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
