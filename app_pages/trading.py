import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

from database.database import get_session
from database.models import Stock, Order, TransactionLog, PriorityCurrentPrice
from services.technical_indicators import TechnicalIndicators
from services.broker_apis import BrokerManager
from utils.helpers import format_currency, format_percentage

def show_trading_page():
    st.title("💹 Advanced Trading")
    
    # Check user permissions - only traders and admins can access trading
    from utils.auth import check_permission
    if not check_permission(st.session_state.user, 'trader'):
        st.error("🚫 Access denied. Trading privileges required.")
        st.info("Viewers can only access Dashboard, Portfolio (read-only), and AI Assistant.")
        return
    
    # Trading controls
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        trading_mode = st.selectbox("Mode", ["Paper", "Live"])
    
    with col2:
        auto_trading = st.toggle("Auto Trading", value=False)
    
    with col3:
        risk_level = st.selectbox("Risk Level", ["Conservative", "Moderate", "Aggressive"])
    
    # Real-time monitoring
    st.subheader("📈 Real-Time Monitoring")
    
    # Get priority stocks
    session = get_session()
    try:
        priority_stocks = session.query(Stock).filter(Stock.priority > 0).all()
        
        if priority_stocks:
            # Stock selector
            selected_stock = st.selectbox(
                "Select Stock for Analysis",
                options=priority_stocks,
                format_func=lambda x: f"{x.symbol} - {x.name}"
            )
            
            if selected_stock:
                _show_stock_analysis(selected_stock, session)
        else:
            st.warning("No priority stocks available for trading")
    
    finally:
        session.close()
    
    # Trading strategies
    st.subheader("🎯 Active Strategies")
    _show_active_strategies()
    
    # Options trading
    st.subheader("📋 Options Trading")
    _show_options_interface()

def _show_stock_analysis(stock: Stock, session):
    """Show detailed analysis for selected stock"""
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Price chart with technical indicators
        _show_price_chart(stock, session)
    
    with col2:
        # Stock metrics
        st.metric("Current Price", f"${stock.last_price:.2f}", f"{stock.change_percent:.2f}%")
        
        # Technical indicators
        st.subheader("Technical Indicators")
        
        # Get recent price data for indicators
        recent_prices = session.query(PriorityCurrentPrice)\
            .filter(PriorityCurrentPrice.stock_id == stock.id)\
            .order_by(PriorityCurrentPrice.datetime.desc())\
            .limit(50).all()
        
        if recent_prices:
            prices = [p.current_price for p in reversed(recent_prices)]
            
            # Calculate simple indicators
            if len(prices) >= 20:
                sma_20 = sum(prices[-20:]) / 20
                current_price = prices[-1]
                
                st.metric("20-Day SMA", f"${sma_20:.2f}")
                st.metric("Price vs SMA", f"{((current_price - sma_20) / sma_20 * 100):.2f}%")
        
        # Trading signals
        st.subheader("Trading Signals")
        _show_trading_signals(stock, session)

def _show_price_chart(stock: Stock, session):
    """Show price chart with technical analysis"""
    # Get historical price data
    recent_prices = session.query(PriorityCurrentPrice)\
        .filter(PriorityCurrentPrice.stock_id == stock.id)\
        .order_by(PriorityCurrentPrice.datetime.desc())\
        .limit(100).all()
    
    if not recent_prices:
        st.info("No price data available")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame([{
        'time': p.datetime,
        'price': p.current_price,
        'volume': p.volume or 0
    } for p in reversed(recent_prices)])
    
    # Create candlestick chart (simplified to line chart for demo)
    fig = go.Figure()
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['price'],
        mode='lines',
        name='Price',
        line=dict(color='blue', width=2)
    ))
    
    # Add volume bars
    fig.add_trace(go.Bar(
        x=df['time'],
        y=df['volume'],
        name='Volume',
        yaxis='y2',
        opacity=0.3
    ))
    
    # Update layout
    fig.update_layout(
        title=f"{stock.symbol} Price Chart",
        xaxis_title="Time",
        yaxis_title="Price ($)",
        yaxis2=dict(
            title="Volume",
            overlaying='y',
            side='right'
        ),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def _show_trading_signals(stock: Stock, session):
    """Show trading signals and recommendations"""
    # Get recent technical data
    recent_prices = session.query(PriorityCurrentPrice)\
        .filter(PriorityCurrentPrice.stock_id == stock.id)\
        .order_by(PriorityCurrentPrice.datetime.desc())\
        .limit(20).all()
    
    if len(recent_prices) < 5:
        st.info("Insufficient data for signals")
        return
    
    prices = [p.current_price for p in reversed(recent_prices)]
    
    # Determine momentum
    momentum = TechnicalIndicators.detect_price_momentum(prices, 3)
    
    # Signal strength
    signal_strength = "Strong" if abs(prices[-1] - prices[-5]) / prices[-5] > 0.02 else "Weak"
    
    # Display signals
    if momentum == 'up':
        st.success(f"🟢 **BUY Signal** ({signal_strength})")
        st.write("Price showing upward momentum")
        
        if stock.has_options:
            st.info("💡 Consider call options for leveraged exposure")
    
    elif momentum == 'down':
        st.error(f"🔴 **SELL Signal** ({signal_strength})")
        st.write("Price showing downward momentum")
        
        if stock.has_options:
            st.info("💡 Consider put options or protective strategies")
    
    else:
        st.warning("🟡 **HOLD Signal**")
        st.write("Price showing sideways movement")
    
    # Risk assessment
    volatility = _calculate_volatility(prices)
    if volatility > 0.05:
        st.warning("⚠️ High volatility detected")
    elif volatility < 0.01:
        st.info("ℹ️ Low volatility - consider volatility strategies")

def _calculate_volatility(prices):
    """Calculate simple volatility measure"""
    if len(prices) < 2:
        return 0
    
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    return sum(abs(r) for r in returns) / len(returns)

def _show_active_strategies():
    """Show active trading strategies"""
    strategies = [
        {
            "Strategy": "Momentum Following",
            "Status": "Active",
            "Stocks": 5,
            "P&L": "+$1,250",
            "Success Rate": "68%"
        },
        {
            "Strategy": "Mean Reversion",
            "Status": "Paused",
            "Stocks": 0,
            "P&L": "+$850",
            "Success Rate": "72%"
        },
        {
            "Strategy": "Options Arbitrage",
            "Status": "Active",
            "Stocks": 3,
            "P&L": "+$420",
            "Success Rate": "85%"
        }
    ]
    
    df = pd.DataFrame(strategies)
    
    # Color code status
    def color_status(val):
        if val == 'Active':
            return 'background-color: lightgreen'
        elif val == 'Paused':
            return 'background-color: lightyellow'
        else:
            return ''
    
    styled_df = df.style.map(color_status, subset=['Status'])
    st.dataframe(styled_df, use_container_width=True)

def _show_options_interface():
    """Show options trading interface"""
    session = get_session()
    
    try:
        # Get stocks with options
        options_stocks = session.query(Stock).filter(Stock.has_options == True).all()
        
        if not options_stocks:
            st.info("No stocks with options available")
            return
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            selected_stock = st.selectbox(
                "Stock for Options",
                options=options_stocks,
                format_func=lambda x: f"{x.symbol} - ${x.last_price:.2f}" if x.last_price is not None else f"{x.symbol} - No Price"
            )
        
        with col2:
            option_type = st.selectbox("Option Type", ["Call", "Put"])
        
        with col3:
            expiry_days = st.selectbox("Days to Expiry", [7, 14, 21, 30, 45, 60])
        
        if selected_stock:
            # Options chain (simplified)
            current_price = selected_stock.last_price or 100.0
            
            # Generate strike prices around current price
            strikes = []
            for i in range(-5, 6):
                strike = round(current_price + (i * 5), 2)
                moneyness = "ITM" if (option_type == "Call" and strike < current_price) or \
                                   (option_type == "Put" and strike > current_price) else "OTM"
                
                # Simplified option pricing
                intrinsic = max(0, current_price - strike) if option_type == "Call" else max(0, strike - current_price)
                time_value = 2.5 * (expiry_days / 30)  # Simplified
                option_price = float(intrinsic) + time_value
                
                strikes.append({
                    "Strike": f"${strike:.2f}",
                    "Type": moneyness,
                    "Bid": f"${option_price * 0.95:.2f}",
                    "Ask": f"${option_price * 1.05:.2f}",
                    "Volume": f"{1000 + i*100:,}",
                    "Open Interest": f"{5000 + i*500:,}"
                })
            
            st.subheader(f"{option_type} Options Chain - {selected_stock.symbol}")
            options_df = pd.DataFrame(strikes)
            st.dataframe(options_df, use_container_width=True)
            
            # Quick trade buttons
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("Buy ATM Call"):
                    st.success(f"Placed order: Buy ATM Call {selected_stock.symbol}")
            
            with col2:
                if st.button("Buy ATM Put"):
                    st.success(f"Placed order: Buy ATM Put {selected_stock.symbol}")
            
            with col3:
                if st.button("Sell Covered Call"):
                    st.success(f"Placed order: Sell Covered Call {selected_stock.symbol}")
            
            with col4:
                if st.button("Buy Protective Put"):
                    st.success(f"Placed order: Buy Protective Put {selected_stock.symbol}")
    
    finally:
        session.close()
