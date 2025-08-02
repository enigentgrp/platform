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
        
        # Navigation menu
        pages = {
            "Dashboard": "📊",
            "Trading": "💹",
            "Portfolio": "💼",
            "AI Assistant": "🤖",
            "Settings": "⚙️"
        }
        
        # Add admin page for admin users
        if user.role == 'admin':
            pages["Admin"] = "🛠️"
        
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
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Portfolio Value", "$125,432.50", "2.3%")
    
    with col2:
        st.metric("Daily P&L", "$1,234.56", "0.98%")
    
    with col3:
        st.metric("Active Positions", "12", "2")
    
    with col4:
        st.metric("Success Rate", "68.5%", "1.2%")
    
    # Market overview
    st.subheader("📈 Market Overview")
    
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
        if st.session_state.get('trading_engine_active', False):
            st.success("✅ Trading Engine: ACTIVE")
            if st.button("🛑 Stop Trading Engine"):
                st.session_state.trading_engine_active = False
                st.rerun()
        else:
            st.warning("⏸️ Trading Engine: STOPPED")
            if st.button("▶️ Start Trading Engine"):
                st.session_state.trading_engine_active = True
                st.rerun()
    
    with col2:
        trading_mode = st.selectbox("Trading Mode", ["Paper Trading", "Live Trading"])
        st.info(f"Current Mode: {trading_mode}")

def load_page_content(page_name):
    """Dynamically load page content"""
    if page_name == "Dashboard":
        main_dashboard()
    elif page_name == "Trading":
        from app_pages.trading import show_trading_page
        show_trading_page()
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
