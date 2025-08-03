import streamlit as st
import threading
import time
from datetime import datetime
from services.trading_engine import TradingEngine
from database.database import get_session
from database.models import EnvironmentVariable, Order, TransactionLog
from utils.auth import check_permission

def show_trading_engine_control():
    """Trading Engine Control Panel"""
    
    # Check authentication
    if not st.session_state.get('authenticated', False):
        st.error("🚫 Please log in to access this page.")
        return
    
    user = st.session_state.user
    
    # Only admin and trader roles can control the trading engine
    if not check_permission(user, 'trader'):
        st.error("🚫 Access denied. Trading engine control requires trader privileges or higher.")
        return
    
    st.title("🤖 Automated Trading Engine Control")
    
    # Initialize trading engine in session state
    if 'trading_engine' not in st.session_state:
        st.session_state.trading_engine = None
        st.session_state.engine_status = "Stopped"
    
    # Current status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_color = "🟢" if st.session_state.engine_status == "Running" else "🔴"
        st.metric("Engine Status", f"{status_color} {st.session_state.engine_status}")
    
    with col2:
        session = get_session()
        try:
            trading_mode = session.query(EnvironmentVariable).filter(
                EnvironmentVariable.key == 'TRADING_MODE'
            ).first()
            mode = trading_mode.value if trading_mode else 'paper'
            st.metric("Trading Mode", mode.title())
        finally:
            session.close()
    
    with col3:
        # Count recent orders
        session = get_session()
        try:
            recent_orders = session.query(Order).filter(
                Order.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
            ).count()
            st.metric("Orders Today", recent_orders)
        finally:
            session.close()
    
    st.markdown("---")
    
    # What is the Trading Engine?
    with st.expander("ℹ️ What is the Trading Engine?", expanded=False):
        st.markdown("""
        **The Trading Engine is the "brain" of your algorithmic trading system that:**
        
        **🔄 Continuously Monitors:**
        - Stock prices every 30 seconds (configurable)
        - Technical indicators (moving averages, momentum)
        - Your existing positions and cash balance
        
        **🎯 Makes Trading Decisions:**
        - Identifies stocks with strong momentum (priority stocks)
        - Places buy orders when prices are trending up
        - Places sell orders when momentum slows or reverses
        - Buys call options when stocks are rising strongly
        - Buys put options when stocks are falling strongly
        
        **⚡ Executes Automatically:**
        - Sends orders to your broker (Alpaca, RobinHood, etc.)
        - Manages position sizes (uses only 2-5% of your cash per trade)
        - Respects day trading limits
        - Calculates gains/losses and updates your account balance
        
        **🛡️ Risk Management:**
        - Never risks more than set percentage of your account
        - Follows your broker's day trading rules
        - Uses offsetting options to lock in gains when needed
        - Stops trading if there are connection issues
        """)
    
    # Engine Controls
    st.subheader("🎮 Engine Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Start Trading Engine", disabled=(st.session_state.engine_status == "Running")):
            try:
                st.session_state.trading_engine = TradingEngine()
                st.session_state.trading_engine.start_trading()
                st.session_state.engine_status = "Running"
                st.success("✅ Trading engine started successfully!")
                st.info("The engine is now monitoring markets and will place trades automatically based on your algorithms.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to start trading engine: {e}")
    
    with col2:
        if st.button("⏹️ Stop Trading Engine", disabled=(st.session_state.engine_status == "Stopped")):
            try:
                if st.session_state.trading_engine:
                    st.session_state.trading_engine.stop_trading()
                    st.session_state.trading_engine = None
                st.session_state.engine_status = "Stopped"
                st.success("✅ Trading engine stopped successfully!")
                st.info("All automated trading has been halted. Manual trading is still available.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to stop trading engine: {e}")
    
    with col3:
        if st.button("🔄 Restart Engine"):
            try:
                # Stop first
                if st.session_state.trading_engine:
                    st.session_state.trading_engine.stop_trading()
                    time.sleep(2)
                
                # Start fresh
                st.session_state.trading_engine = TradingEngine()
                st.session_state.trading_engine.start_trading()
                st.session_state.engine_status = "Running"
                st.success("✅ Trading engine restarted successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to restart trading engine: {e}")
    
    st.markdown("---")
    
    # Engine Configuration
    st.subheader("⚙️ Engine Configuration")
    
    session = get_session()
    try:
        # Get current configuration
        config_vars = session.query(EnvironmentVariable).filter(
            EnvironmentVariable.key.in_([
                'PRICE_UPDATE_INTERVAL',
                'MAX_POSITION_SIZE_PERCENT', 
                'PRIORITY_EVALUATION_PERIODS',
                'TECHNICAL_ANALYSIS_PERIODS'
            ])
        ).all()
        
        config_dict = {var.key: var.value for var in config_vars}
        
        col1, col2 = st.columns(2)
        
        with col1:
            price_interval = st.number_input(
                "Price Update Interval (seconds)",
                min_value=10,
                max_value=300,
                value=int(config_dict.get('PRICE_UPDATE_INTERVAL', 30)),
                help="How often the engine checks stock prices"
            )
            
            max_position = st.number_input(
                "Max Position Size (%)",
                min_value=1.0,
                max_value=10.0,
                value=float(config_dict.get('MAX_POSITION_SIZE_PERCENT', 5.0)),
                help="Maximum percentage of account to use per trade"
            )
        
        with col2:
            eval_periods = st.number_input(
                "Evaluation Periods",
                min_value=2,
                max_value=10,
                value=int(config_dict.get('PRIORITY_EVALUATION_PERIODS', 3)),
                help="Number of price periods to analyze for momentum"
            )
            
            ta_periods = st.number_input(
                "Technical Analysis Periods",
                min_value=10,
                max_value=50,
                value=int(config_dict.get('TECHNICAL_ANALYSIS_PERIODS', 20)),
                help="Moving average period for technical analysis"
            )
        
        if st.button("💾 Save Configuration"):
            # Update configuration
            updates = {
                'PRICE_UPDATE_INTERVAL': str(price_interval),
                'MAX_POSITION_SIZE_PERCENT': str(max_position),
                'PRIORITY_EVALUATION_PERIODS': str(eval_periods),
                'TECHNICAL_ANALYSIS_PERIODS': str(ta_periods)
            }
            
            for key, value in updates.items():
                env_var = session.query(EnvironmentVariable).filter(
                    EnvironmentVariable.key == key
                ).first()
                
                if env_var:
                    env_var.value = value
                else:
                    env_var = EnvironmentVariable(key=key, value=value)
                    session.add(env_var)
            
            session.commit()
            st.success("✅ Configuration saved! Restart the engine to apply changes.")
    
    finally:
        session.close()
    
    # Recent Activity
    st.subheader("📊 Recent Trading Activity")
    
    session = get_session()
    try:
        # Recent orders
        recent_orders = session.query(Order).order_by(Order.created_at.desc()).limit(10).all()
        
        if recent_orders:
            order_data = []
            for order in recent_orders:
                order_data.append({
                    'Time': order.created_at.strftime('%H:%M:%S'),
                    'Symbol': order.symbol,
                    'Action': order.action.title(),
                    'Quantity': order.quantity,
                    'Price': f"${order.limit_price:.2f}" if order.limit_price else "Market",
                    'Status': order.status.title()
                })
            
            st.dataframe(order_data, use_container_width=True)
        else:
            st.info("No recent orders. Start the trading engine to begin automated trading.")
    
    finally:
        session.close()
    
    # Warning messages
    if st.session_state.engine_status == "Running":
        st.warning("⚠️ **IMPORTANT:** The trading engine is actively placing real trades. Monitor your account regularly.")
    
    if user.role == 'admin':
        st.info("👨‍💼 **Admin Note:** You can view all system logs and trading activity in the Database Admin section.")