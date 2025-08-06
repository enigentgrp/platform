import streamlit as st
import pandas as pd
from database.database import get_session
from database.models import User, EnvironmentVariable, Order, TransactionLog, Stock

# Page configuration
st.set_page_config(
    page_title="Foundation",
    page_icon="✝️",
    layout="wide"
)

# Custom CSS for Jesus background and pretty buttons
st.markdown("""
<style>
/* Main background with Jesus image */
.main {
    background-image: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), 
                      url('https://images.unsplash.com/photo-1578662996442-48f60103fc96?q=80&w=1974&auto=format&fit=crop&ixlib=rb-4.0.3');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}

/* Beautiful buttons */
.stButton > button {
    background: linear-gradient(45deg, #ff6b35, #f7931e);
    color: white !important;
    border: none;
    border-radius: 25px;
    padding: 0.5rem 2rem;
    font-weight: bold;
    font-size: 1rem;
    box-shadow: 0 4px 15px rgba(255, 107, 53, 0.4);
    transition: all 0.3s ease;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.stButton > button:hover {
    background: linear-gradient(45deg, #f7931e, #ff6b35);
    box-shadow: 0 6px 20px rgba(255, 107, 53, 0.6);
    transform: translateY(-2px);
}

.stButton > button:active {
    transform: translateY(0px);
    box-shadow: 0 2px 10px rgba(255, 107, 53, 0.8);
}

/* Form submit buttons */
.stFormSubmitButton > button {
    background: linear-gradient(45deg, #28a745, #20c997) !important;
    color: white !important;
    border: none !important;
    border-radius: 25px !important;
    padding: 0.75rem 3rem !important;
    font-weight: bold !important;
    font-size: 1.1rem !important;
    box-shadow: 0 4px 15px rgba(40, 167, 69, 0.4) !important;
    transition: all 0.3s ease !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
}

.stFormSubmitButton > button:hover {
    background: linear-gradient(45deg, #20c997, #28a745) !important;
    box-shadow: 0 6px 20px rgba(40, 167, 69, 0.6) !important;
    transform: translateY(-2px) !important;
}

/* Sidebar styling */
.css-1d391kg {
    background: linear-gradient(180deg, #1f1f2e, #16213e);
    border-right: 2px solid #ff6b35;
}

/* Title styling */
h1 {
    color: #fafafa !important;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
    font-family: 'serif' !important;
    text-align: center;
    margin-bottom: 2rem;
}

/* Cards and containers */
.stMetric {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border-radius: 15px;
    padding: 1rem;
    border: 1px solid rgba(255, 107, 53, 0.3);
}

/* Input fields */
.stTextInput > div > div > input {
    background: rgba(255, 255, 255, 0.1);
    border: 2px solid #ff6b35;
    border-radius: 10px;
    color: white !important;
}

.stSelectbox > div > div > select {
    background: rgba(255, 255, 255, 0.1);
    border: 2px solid #ff6b35;
    border-radius: 10px;
    color: white !important;
}

/* Success/error messages */
.stSuccess {
    background: rgba(40, 167, 69, 0.2);
    border: 1px solid #28a745;
    border-radius: 10px;
}

.stError {
    background: rgba(220, 53, 69, 0.2);
    border: 1px solid #dc3545;
    border-radius: 10px;
}

.stWarning {
    background: rgba(255, 193, 7, 0.2);
    border: 1px solid #ffc107;
    border-radius: 10px;
}

.stInfo {
    background: rgba(255, 107, 53, 0.2);
    border: 1px solid #ff6b35;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'engine_status' not in st.session_state:
        st.session_state.engine_status = 'Stopped'

def authenticate_user(username, password):
    """Authenticate user against database"""
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if user and user.check_password(password):
            return user
        return None
    finally:
        session.close()

def show_login_page():
    """Simple login form"""
    st.title("✝️ Foundation - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            user = authenticate_user(username, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")

def show_trading_interface():
    """Core trading interface per requirements"""
    st.title("💹 Algorithmic Trading System")
    
    # Trading engine controls
    col1, col2 = st.columns(2)
    
    with col1:
        engine_status = st.session_state.get('engine_status', 'Stopped')
        if engine_status == "Running":
            st.success("🤖 Trading Engine: RUNNING")
            if st.button("⏹️ Stop Engine"):
                if st.session_state.get('trading_engine'):
                    st.session_state.trading_engine.stop_trading()
                    st.session_state.trading_engine = None
                st.session_state.engine_status = "Stopped"
                st.rerun()
        else:
            st.warning("🤖 Trading Engine: STOPPED")
            if st.button("▶️ Start Engine"):
                from services.trading_engine import TradingEngine
                st.session_state.trading_engine = TradingEngine()
                st.session_state.trading_engine.start_trading()
                st.session_state.engine_status = "Running"
                st.rerun()
    
    with col2:
        # Trading mode from environment variables
        session = get_session()
        try:
            mode_var = session.query(EnvironmentVariable).filter(
                EnvironmentVariable.key == 'TRADING_MODE'
            ).first()
            current_mode = mode_var.value if mode_var else 'paper'
            st.info(f"Mode: {current_mode.upper()}")
        finally:
            session.close()
    
    # Priority stocks (per requirements - stocks with priority > 0)
    st.subheader("🎯 Priority Stocks (Algorithm Targets)")
    
    session = get_session()
    try:
        priority_stocks = session.query(Stock).filter(Stock.priority > 0).order_by(Stock.priority.desc()).all()
        
        if priority_stocks:
            stock_data = []
            for stock in priority_stocks:
                stock_data.append({
                    "Symbol": stock.symbol,
                    "Priority": stock.priority,
                    "Last Price": f"${stock.last_price:.2f}" if stock.last_price else "N/A",
                    "Change %": f"{stock.change_percent:.2f}%" if stock.change_percent else "N/A",
                    "Has Options": "Yes" if stock.has_options else "No",
                    "Sector": stock.sector
                })
            
            df = pd.DataFrame(stock_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No priority stocks. Engine will identify trading opportunities automatically.")
    finally:
        session.close()

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
    """Display positions and transaction log with LIFO gain/loss"""
    st.title("💼 Positions & Transaction Log")
    
    session = get_session()
    try:
        # Get live positions from active broker
        from services.broker_apis import BrokerManager
        
        # Use cached broker manager or create new one
        if 'broker_manager' not in st.session_state:
            st.session_state.broker_manager = BrokerManager()
        
        broker_manager = st.session_state.broker_manager
        broker_manager.authenticate_all()
        
        # Show live broker positions
        st.subheader("Live Broker Positions")
        
        try:
            live_positions = broker_manager.get_positions()
            account_info = broker_manager.get_account_info()
            
            # Display account summary
            if account_info and not account_info.get('error'):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cash Balance", f"${account_info.get('cash', 0):,.2f}")
                with col2:
                    st.metric("Portfolio Value", f"${account_info.get('portfolio_value', 0):,.2f}")
                with col3:
                    st.metric("Buying Power", f"${account_info.get('buying_power', 0):,.2f}")
            
            if live_positions:
                pos_data = []
                for pos in live_positions:
                    pos_data.append({
                        "Symbol": pos['symbol'],
                        "Quantity": pos['quantity'],
                        "Market Value": f"${pos.get('market_value', 0):,.2f}",
                        "Cost Basis": f"${pos.get('cost_basis', 0):,.2f}",
                        "Unrealized P&L": f"${pos.get('unrealized_pnl', 0):,.2f}",
                        "Side": pos.get('side', 'long').title()
                    })
                
                df = pd.DataFrame(pos_data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No live positions found in your broker account.")
                
        except Exception as e:
            st.error(f"Error fetching live positions: {e}")
            st.info("Showing positions from transaction log instead...")
            
            # Fallback: Calculate positions from transaction log
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
            
            # Show database positions
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
                st.info("No positions found.")
        
        # Transaction log with LIFO gain/loss calculations
        st.subheader("Transaction Log (LIFO Gain/Loss)")
        
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
                    "LIFO P&L": f"${transaction.gain_loss:.2f}" if transaction.gain_loss else "N/A"
                })
            
            df = pd.DataFrame(trans_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No transactions found.")
            
    finally:
        session.close()

def show_settings_page():
    """Environment variables configuration per requirements"""
    user = st.session_state.user
    
    if user.role == 'admin':
        st.title("⚙️ Settings - Environment Variables")
    else:
        st.title("⚙️ Trading Settings")
    
    session = get_session()
    try:
        # Get current environment variables
        env_vars = {var.key: var.value for var in session.query(EnvironmentVariable).all()}
        
        st.subheader("Trading Configuration")
        
        # Show current broker status
        from services.broker_apis import BrokerManager
        if 'broker_manager' not in st.session_state:
            st.session_state.broker_manager = BrokerManager()
        
        current_broker = st.session_state.broker_manager.get_active_broker_name()
        st.info(f"🔄 **Current Active Broker**: {current_broker.replace('_', ' ').title()}")
        
        # Broker and trading mode - available to traders and admins
        col1, col2 = st.columns(2)
        
        with col1:
            # Broker selection
            active_broker = st.selectbox(
                "Active Broker",
                ["alpaca", "robinhood"],
                index=0 if env_vars.get('ACTIVE_BROKER', 'alpaca') == 'alpaca' else 1,
                help="Switch between different broker platforms for trading"
            )
            
            trading_mode = st.selectbox(
                "Trading Mode (Paper/Live)",
                ["paper", "live"],
                index=0 if env_vars.get('TRADING_MODE', 'paper') == 'paper' else 1,
                help="Paper trading uses simulated money, Live trading uses real money"
            )
        
        # Advanced settings - admin only
        if user.role == 'admin':
            with col2:
                price_interval = st.number_input(
                    "Price Update Interval (seconds)",
                    min_value=5,
                    max_value=300,
                    value=int(env_vars.get('PRICE_UPDATE_INTERVAL', '30'))
                )
                
            col3, col4 = st.columns(2)
            with col3:
                max_position = st.number_input(
                    "Max Position Size (%)",
                    min_value=1.0,
                    max_value=25.0,
                    value=float(env_vars.get('MAX_POSITION_SIZE_PERCENT', '5.0')),
                    step=0.5
                )
                
            with col4:
                archive_days = st.number_input(
                    "Archive Retention (days)",
                    min_value=7,
                    max_value=365,
                    value=int(env_vars.get('ARCHIVE_RETENTION_DAYS', '30'))
                )
        
        if st.button("Save Settings"):
            # Update environment variables based on user role
            if user.role == 'admin':
                # Admin can change all settings
                updates = [
                    ('ACTIVE_BROKER', active_broker),
                    ('TRADING_MODE', trading_mode),
                    ('PRICE_UPDATE_INTERVAL', str(price_interval)),
                    ('MAX_POSITION_SIZE_PERCENT', str(max_position)),
                    ('ARCHIVE_RETENTION_DAYS', str(archive_days))
                ]
            else:
                # Traders can only change broker and trading mode
                updates = [
                    ('ACTIVE_BROKER', active_broker),
                    ('TRADING_MODE', trading_mode)
                ]
            
            for key, value in updates:
                env_var = session.query(EnvironmentVariable).filter(EnvironmentVariable.key == key).first()
                if env_var:
                    env_var.value = value
                else:
                    env_var = EnvironmentVariable(key=key, value=value)
                    session.add(env_var)
            
            session.commit()
            
            # Immediately update the broker manager
            try:
                if 'broker_manager' in st.session_state:
                    st.session_state.broker_manager.reload_configuration()
                else:
                    st.session_state.broker_manager = BrokerManager()
                
                # Test the new broker connection
                new_broker = st.session_state.broker_manager.get_active_broker_name()
                st.success(f"✅ Settings updated! Switched to {new_broker.replace('_', ' ').title()}")
                
                # Show connection test
                with st.spinner("Testing new broker connection..."):
                    try:
                        account_info = st.session_state.broker_manager.get_account_info()
                        if account_info and not account_info.get('error'):
                            st.success(f"✅ Connection successful! Cash: ${account_info.get('cash', 0):,.2f}")
                        else:
                            st.warning("⚠️ Connection test failed - check broker credentials")
                    except Exception as conn_error:
                        st.warning(f"⚠️ Connection test error: {conn_error}")
                        
            except Exception as e:
                st.error(f"❌ Error switching broker: {e}")
            
            st.rerun()
    
    finally:
        session.close()

def sidebar_navigation():
    """Streamlined navigation per requirements"""
    st.sidebar.title("✝️ Foundation")
    
    if st.session_state.authenticated:
        user = st.session_state.user
        st.sidebar.write(f"👤 {user.username} ({user.role})")
        
        # Show engine status
        engine_status = st.session_state.get('engine_status', 'Stopped')
        if engine_status == "Running":
            st.sidebar.success("🤖 Engine: RUNNING")
        else:
            st.sidebar.warning("🤖 Engine: STOPPED")
        
        # Core navigation per original requirements
        pages = {
            "Trading": "💹",
            "Orders": "📋", 
            "Positions": "💼"
        }
        
        # Trader and Admin pages
        if user.role in ['admin', 'trader']:
            pages["Settings"] = "⚙️"
            
        # Admin-only pages  
        if user.role == 'admin':
            pages["Database"] = "🗄️"
        
        selected_page = st.sidebar.radio(
            "Navigation",
            list(pages.keys()),
            format_func=lambda x: f"{pages[x]} {x}"
        )
        
        # Logout
        if st.sidebar.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.trading_engine = None
            st.rerun()
        
        return selected_page
    
    return None

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
    initialize_session_state()
    
    if not st.session_state.authenticated:
        show_login_page()
        return
    
    # Show sidebar and load selected page
    selected_page = sidebar_navigation()
    if selected_page:
        load_page_content(selected_page)

if __name__ == "__main__":
    main()