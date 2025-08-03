import streamlit as st
import time
from datetime import datetime
from services.broker_apis import BrokerManager

def display_animated_broker_status():
    """Display animated broker connection status widget"""
    
    # Initialize broker manager
    if 'broker_manager' not in st.session_state:
        st.session_state.broker_manager = BrokerManager()
    
    broker_manager = st.session_state.broker_manager
    
    # Get broker info
    active_broker = broker_manager.get_active_broker_name()
    
    # Create container for the widget
    status_container = st.container()
    
    with status_container:
        # CSS for animations and styling
        st.markdown("""
        <style>
        .broker-status-widget {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 20px;
            margin: 10px 0;
            color: white;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            position: relative;
            overflow: hidden;
        }
        
        .broker-status-widget::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 2s infinite;
        }
        
        @keyframes shimmer {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        
        .connection-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        .connected {
            background-color: #4CAF50;
            box-shadow: 0 0 10px #4CAF50;
        }
        
        .connecting {
            background-color: #FF9800;
            box-shadow: 0 0 10px #FF9800;
        }
        
        .disconnected {
            background-color: #F44336;
            box-shadow: 0 0 10px #F44336;
        }
        
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(1.2); }
            100% { opacity: 1; transform: scale(1); }
        }
        
        .broker-name {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .broker-details {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .status-metrics {
            display: flex;
            justify-content: space-between;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        
        .metric-item {
            text-align: center;
            flex: 1;
            min-width: 100px;
        }
        
        .metric-value {
            font-size: 16px;
            font-weight: bold;
            color: #FFD700;
        }
        
        .metric-label {
            font-size: 12px;
            opacity: 0.8;
        }
        
        .refresh-button {
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 20px;
            color: white;
            padding: 8px 16px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            float: right;
            margin-top: -10px;
        }
        
        .refresh-button:hover {
            background: rgba(255,255,255,0.3);
            transform: scale(1.05);
        }
        
        .last-updated {
            font-size: 10px;
            opacity: 0.7;
            margin-top: 10px;
            text-align: right;
        }
        
        .live-indicator {
            display: inline-block;
            background: #FF6B6B;
            color: white;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: bold;
            margin-left: 10px;
            animation: livePulse 1.5s infinite;
        }
        
        @keyframes livePulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.1); }
            100% { opacity: 1; transform: scale(1); }
        }
        
        .auto-refresh-badge {
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(255,255,255,0.2);
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Test connection
        try:
            account_info = broker_manager.get_account_info()
            is_connected = 'error' not in account_info
            
            if is_connected:
                status_class = "connected"
                status_text = "Connected"
                status_icon = "🟢"
            else:
                status_class = "disconnected"
                status_text = "Disconnected"
                status_icon = "🔴"
                
        except Exception:
            status_class = "disconnected"
            status_text = "Connection Error"
            status_icon = "🔴"
            account_info = {}
            is_connected = False
        
        # Format broker name for display
        broker_display_names = {
            'alpaca_paper': 'Alpaca Paper Trading',
            'alpaca_live': 'Alpaca Live Trading',
            'tradier_paper': 'Tradier Sandbox',
            'tradier_live': 'Tradier Live',
            'robinhood': 'Robinhood'
        }
        
        broker_display = broker_display_names.get(active_broker, active_broker.title())
        
        # Create the widget HTML
        widget_html = f"""
        <div class="broker-status-widget">
            <div class="auto-refresh-badge">LIVE</div>
            <div class="broker-name">
                <span class="connection-indicator {status_class}"></span>
                {status_icon} {broker_display}
                <span class="live-indicator">LIVE</span>
            </div>
            <div class="broker-details">
                Status: {status_text} | Mode: {'Paper' if 'paper' in active_broker else 'Live'} Trading
            </div>
        """
        
        if is_connected:
            portfolio_value = account_info.get('portfolio_value', 0)
            cash = account_info.get('cash', 0)
            buying_power = account_info.get('buying_power', 0)
            day_trades = account_info.get('day_trade_count', 0)
            
            widget_html += f"""
            <div class="status-metrics">
                <div class="metric-item">
                    <div class="metric-value">${portfolio_value:,.0f}</div>
                    <div class="metric-label">Portfolio</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">${cash:,.0f}</div>
                    <div class="metric-label">Cash</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">${buying_power:,.0f}</div>
                    <div class="metric-label">Buying Power</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{day_trades}/3</div>
                    <div class="metric-label">Day Trades</div>
                </div>
            </div>
            """
        
        current_time = datetime.now().strftime("%H:%M:%S")
        widget_html += f"""
            <div class="last-updated">Last updated: {current_time}</div>
        </div>
        """
        
        # Display the widget
        st.markdown(widget_html, unsafe_allow_html=True)
        
        # Refresh button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 Refresh Status", key="refresh_broker_status"):
                # Force refresh broker manager
                if 'broker_manager' in st.session_state:
                    st.session_state.broker_manager.reload_configuration()
                st.rerun()
        
        return is_connected, account_info

def display_mini_broker_status():
    """Display a compact version of the broker status widget"""
    
    if 'broker_manager' not in st.session_state:
        st.session_state.broker_manager = BrokerManager()
    
    broker_manager = st.session_state.broker_manager
    active_broker = broker_manager.get_active_broker_name()
    
    try:
        account_info = broker_manager.get_account_info()
        is_connected = 'error' not in account_info
        status_icon = "🟢" if is_connected else "🔴"
        status_text = "Connected" if is_connected else "Disconnected"
    except Exception:
        status_icon = "🔴"
        status_text = "Error"
        is_connected = False
    
    # Compact status display
    broker_display_names = {
        'alpaca_paper': 'Alpaca Paper',
        'alpaca_live': 'Alpaca Live',
        'tradier_paper': 'Tradier Sandbox',
        'tradier_live': 'Tradier Live',
        'robinhood': 'Robinhood'
    }
    
    broker_display = broker_display_names.get(active_broker, active_broker)
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(45deg, #667eea, #764ba2);
        border-radius: 10px;
        padding: 10px;
        color: white;
        text-align: center;
        margin: 5px 0;
        font-size: 14px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    ">
        {status_icon} {broker_display} - {status_text}
    </div>
    """, unsafe_allow_html=True)
    
    return is_connected

def display_connection_health_chart():
    """Display a connection health monitoring chart"""
    
    # Store connection history in session state
    if 'connection_history' not in st.session_state:
        st.session_state.connection_history = []
    
    if 'broker_manager' not in st.session_state:
        st.session_state.broker_manager = BrokerManager()
    
    broker_manager = st.session_state.broker_manager
    
    # Test connection
    try:
        account_info = broker_manager.get_account_info()
        is_connected = 'error' not in account_info
        response_time = 0.1  # Mock response time
    except Exception:
        is_connected = False
        response_time = None
    
    # Add to history
    current_time = datetime.now()
    st.session_state.connection_history.append({
        'timestamp': current_time,
        'connected': is_connected,
        'response_time': response_time
    })
    
    # Keep only last 20 data points
    if len(st.session_state.connection_history) > 20:
        st.session_state.connection_history = st.session_state.connection_history[-20:]
    
    # Create chart if we have data
    if len(st.session_state.connection_history) >= 2:
        import plotly.graph_objects as go
        
        timestamps = [h['timestamp'] for h in st.session_state.connection_history]
        connected_status = [1 if h['connected'] else 0 for h in st.session_state.connection_history]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=connected_status,
            mode='lines+markers',
            name='Connection Status',
            line=dict(color='green', width=3),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 0, 0.2)'
        ))
        
        fig.update_layout(
            title="Broker Connection Health",
            xaxis_title="Time",
            yaxis_title="Status",
            yaxis=dict(tickmode='array', tickvals=[0, 1], ticktext=['Disconnected', 'Connected']),
            height=200,
            margin=dict(l=0, r=0, t=30, b=0),
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)