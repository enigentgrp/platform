import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

from database.database import get_session
from database.models import Stock, Order, TransactionLog, Account
from services.data_fetcher import DataFetcher
from services.broker_apis import BrokerManager
from utils.helpers import format_currency, format_percentage, calculate_portfolio_value
from utils.broker_status_widget import display_animated_broker_status, display_connection_health_chart

def show_dashboard():
    st.title("📊 Trading Dashboard")
    
    # Animated broker status widget
    st.subheader("🔗 Broker Connection Status")
    is_connected, account_info = display_animated_broker_status()
    
    if not is_connected:
        st.warning("⚠️ Broker connection issues detected. Some features may be limited.")
        return
    
    # Connection health monitoring
    with st.expander("📈 Connection Health Monitor", expanded=False):
        display_connection_health_chart()
    
    # Initialize broker manager if not already done
    if 'broker_manager' not in st.session_state:
        st.session_state.broker_manager = BrokerManager()
    
    broker_manager = st.session_state.broker_manager
    
    # Get account information from active broker
    account_info = broker_manager.get_account_info()
    
    if 'error' not in account_info:
        # Portfolio overview section
        st.subheader("💼 Portfolio Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Portfolio Value", 
                f"${account_info.get('portfolio_value', 0):,.2f}",
                delta=f"${account_info.get('portfolio_value', 0) - account_info.get('cash', 0):,.2f}"
            )
        
        with col2:
            st.metric(
                "Cash Available", 
                f"${account_info.get('cash', 0):,.2f}"
            )
        
        with col3:
            st.metric(
                "Buying Power", 
                f"${account_info.get('buying_power', 0):,.2f}"
            )
        
        with col4:
            st.metric(
                "Day Trades Used", 
                account_info.get('day_trade_count', 0),
                delta="3 remaining" if account_info.get('day_trade_count', 0) < 3 else "Limit reached"
            )
    else:
        st.error(f"❌ Unable to connect to broker: {account_info.get('error', 'Unknown error')}")
    
    # Current positions section
    st.subheader("📈 Current Positions")
    
    positions = broker_manager.get_positions()
    if positions:
        position_data = []
        for position in positions:
            position_data.append({
                "Symbol": position.get('symbol', 'N/A'),
                "Quantity": position.get('qty', 0),
                "Market Value": f"${position.get('market_value', 0):,.2f}",
                "Cost Basis": f"${position.get('cost_basis', 0):,.2f}",
                "Unrealized P&L": f"${position.get('unrealized_pl', 0):,.2f}",
                "Unrealized P&L %": f"{position.get('unrealized_plpc', 0):.2f}%"
            })
        
        if position_data:
            df = pd.DataFrame(position_data)
            
            # Apply color styling to P&L columns
            def color_pnl(val):
                if isinstance(val, str) and '$' in val:
                    num_val = float(val.replace('$', '').replace(',', ''))
                    return 'color: green' if num_val >= 0 else 'color: red'
                elif isinstance(val, str) and '%' in val:
                    num_val = float(val.replace('%', ''))
                    return 'color: green' if num_val >= 0 else 'color: red'
                return ''
            
            styled_df = df.style.applymap(color_pnl, subset=['Unrealized P&L', 'Unrealized P&L %'])
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("No current positions")
    else:
        st.info("No positions found")
    
    # Market data section
    st.subheader("📊 Market Overview")
    
    # Get live market data for major ETFs
    market_symbols = ['SPY', 'QQQ', 'DIA', 'VIX']
    market_data = broker_manager.get_market_data(market_symbols)
    
    if market_data:
        cols = st.columns(len(market_symbols))
        for i, symbol in enumerate(market_symbols):
            if symbol in market_data:
                data = market_data[symbol]
                with cols[i]:
                    price = data.get('price', 0)
                    change_pct = data.get('change_percent', 0)
                    delta_color = "normal" if change_pct >= 0 else "inverse"
                    st.metric(
                        symbol,
                        f"${price:.2f}",
                        f"{change_pct:+.2f}%",
                        delta_color=delta_color
                    )
    
    # Trading activity chart
    st.subheader("📈 Recent Trading Activity")
    
    session = get_session()
    try:
        # Get recent transactions
        recent_transactions = session.query(TransactionLog)\
            .order_by(TransactionLog.transaction_date.desc())\
            .limit(50).all()
        
        if recent_transactions:
            # Create daily P&L chart
            daily_data = {}
            for transaction in recent_transactions:
                date_str = transaction.transaction_date.strftime('%Y-%m-%d')
                if date_str not in daily_data:
                    daily_data[date_str] = {'pnl': 0, 'volume': 0}
                
                pnl = (transaction.price * transaction.quantity) * (1 if transaction.side == 'sell' else -1)
                daily_data[date_str]['pnl'] += pnl
                daily_data[date_str]['volume'] += abs(transaction.price * transaction.quantity)
            
            if daily_data:
                df_chart = pd.DataFrame.from_dict(daily_data, orient='index')
                df_chart.index = pd.to_datetime(df_chart.index)
                df_chart = df_chart.sort_index()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_chart.index,
                    y=df_chart['pnl'].cumsum(),
                    mode='lines+markers',
                    name='Cumulative P&L',
                    line=dict(color='green')
                ))
                
                fig.update_layout(
                    title="Cumulative P&L Over Time",
                    xaxis_title="Date",
                    yaxis_title="P&L ($)",
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No recent trading activity")
    
    finally:
        session.close()
    
    # Quick actions
    st.subheader("⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Refresh Data"):
            # Clear broker manager cache to reload from database
            if 'broker_manager' in st.session_state:
                st.session_state.broker_manager.reload_configuration()
            st.rerun()
    
    with col2:
        if st.button("📊 Update Market Data"):
            with st.spinner("Updating market data..."):
                data_fetcher = DataFetcher()
                data_fetcher.update_priority_stocks()
                st.success("Market data updated!")
    
    with col3:
        if st.button("💹 Go to Trading"):
            st.switch_page("app_pages/trading.py")
    
    with col4:
        if st.button("⚙️ Settings"):
            st.switch_page("app_pages/settings.py")

if __name__ == "__main__":
    show_dashboard()