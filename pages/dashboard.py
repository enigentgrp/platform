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

def show_trading_page():
    st.title("💹 Trading Interface")
    
    # Trading mode selector
    col1, col2 = st.columns([1, 1])
    with col1:
        trading_mode = st.selectbox("Trading Mode", ["Paper Trading", "Live Trading"])
    
    with col2:
        auto_trading = st.checkbox("Enable Auto Trading", value=False)
    
    if trading_mode == "Live Trading":
        st.warning("⚠️ Live trading is enabled. Real money will be used!")
    
    # Priority stocks section
    st.subheader("🎯 Priority Stocks")
    
    session = get_session()
    try:
        priority_stocks = session.query(Stock).filter(Stock.priority > 0).all()
        
        if priority_stocks:
            # Create DataFrame for display
            stock_data = []
            for stock in priority_stocks:
                stock_data.append({
                    "Symbol": stock.symbol,
                    "Name": stock.name,
                    "Sector": stock.sector,
                    "Last Price": stock.last_price or 0,
                    "Change %": stock.change_percent or 0,
                    "Priority": stock.priority,
                    "Has Options": "✅" if stock.has_options else "❌"
                })
            
            df = pd.DataFrame(stock_data)
            
            # Apply styling to the dataframe
            def color_change(val):
                color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
                return f'color: {color}'
            
            styled_df = df.style.applymap(color_change, subset=['Change %'])
            st.dataframe(styled_df, use_container_width=True)
            
            # Stock selection for manual trading
            st.subheader("📋 Manual Trading")
            
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                selected_symbol = st.selectbox("Select Stock", [s.symbol for s in priority_stocks])
            
            with col2:
                trade_side = st.selectbox("Side", ["Buy", "Sell"])
            
            with col3:
                asset_type = st.selectbox("Asset Type", ["Stock", "Call Option", "Put Option"])
            
            with col4:
                quantity = st.number_input("Quantity", min_value=1, value=100)
            
            if asset_type in ["Call Option", "Put Option"]:
                col1, col2 = st.columns(2)
                with col1:
                    strike_price = st.number_input("Strike Price", min_value=0.01, value=100.0)
                with col2:
                    expiry_date = st.date_input("Expiry Date", value=datetime.now() + timedelta(days=30))
            
            if st.button("Place Order", type="primary"):
                if _place_manual_order(selected_symbol, trade_side, asset_type, quantity, trading_mode):
                    st.success(f"Order placed: {trade_side} {quantity} {selected_symbol}")
                    st.rerun()
                else:
                    st.error("Failed to place order")
        
        else:
            st.info("No priority stocks identified. Run market analysis to identify priority stocks.")
            
            if st.button("🔄 Run Market Analysis"):
                with st.spinner("Analyzing market data..."):
                    data_fetcher = DataFetcher()
                    data_fetcher.update_priority_stocks()
                    st.success("Market analysis completed!")
                    st.rerun()
    
    finally:
        session.close()
    
    # Recent orders section
    st.subheader("📄 Recent Orders")
    _show_recent_orders()
    
    # Market data section
    st.subheader("📊 Market Data")
    _show_market_data()

def _place_manual_order(symbol: str, side: str, asset_type: str, quantity: int, trading_mode: str) -> bool:
    """Place a manual trading order"""
    session = get_session()
    try:
        # Create order record
        order = Order(
            account_id=1,  # Default account
            symbol=symbol,
            order_type='market',
            side=side.lower(),
            quantity=quantity,
            asset_type='stock' if asset_type == 'Stock' else 'option',
            option_type=asset_type.split()[0].lower() if 'Option' in asset_type else None,
            status='pending'
        )
        
        session.add(order)
        session.commit()
        
        # For paper trading, immediately fill the order
        if trading_mode == "Paper Trading":
            order.status = 'filled'
            order.filled_at = datetime.utcnow()
            
            # Create transaction record
            stock = session.query(Stock).filter(Stock.symbol == symbol).first()
            price = stock.last_price if stock and stock.last_price else 100.0
            
            transaction = TransactionLog(
                order_id=order.id,
                account_id=order.account_id,
                symbol=symbol,
                side=side.lower(),
                quantity=quantity,
                price=price,
                asset_type=order.asset_type,
                option_type=order.option_type
            )
            session.add(transaction)
            session.commit()
        
        return True
    
    except Exception as e:
        session.rollback()
        st.error(f"Error placing order: {e}")
        return False
    finally:
        session.close()

def _show_recent_orders():
    """Display recent orders"""
    session = get_session()
    try:
        recent_orders = session.query(Order).order_by(Order.created_at.desc()).limit(10).all()
        
        if recent_orders:
            order_data = []
            for order in recent_orders:
                order_data.append({
                    "Time": order.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Symbol": order.symbol,
                    "Side": order.side.upper(),
                    "Type": order.asset_type.title(),
                    "Quantity": order.quantity,
                    "Status": order.status.title(),
                    "Price": f"${order.price:.2f}" if order.price else "Market"
                })
            
            df = pd.DataFrame(order_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No recent orders")
    
    finally:
        session.close()

def _show_market_data():
    """Display market overview data"""
    # Market indices (simulated data for demo)
    indices_data = {
        "Index": ["S&P 500", "NASDAQ", "DOW", "VIX"],
        "Value": [4520.45, 14230.50, 35180.25, 18.45],
        "Change": [45.20, 120.30, -25.80, 2.15],
        "Change %": [1.01, 0.85, -0.07, 13.20]
    }
    
    indices_df = pd.DataFrame(indices_data)
    
    # Apply color styling
    def color_change(val):
        color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
        return f'color: {color}'
    
    styled_indices = indices_df.style.applymap(color_change, subset=['Change', 'Change %'])
    st.dataframe(styled_indices, use_container_width=True)
    
    # Sector performance chart
    sector_data = {
        "Sector": ["Technology", "Healthcare", "Financials", "Energy", "Materials"],
        "Performance": [2.5, 1.8, -0.5, 3.2, 1.2]
    }
    
    fig = px.bar(
        sector_data, 
        x="Sector", 
        y="Performance",
        title="Sector Performance (%)",
        color="Performance",
        color_continuous_scale=['red', 'yellow', 'green']
    )
    
    st.plotly_chart(fig, use_container_width=True)
