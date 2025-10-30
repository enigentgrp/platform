"""
Database Administration page to showcase the comprehensive database structure
and test database functionality as per exact specifications.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database.database import get_session
from database.models import (
    GlobalEnvVar, Account, Stock, PriceHistory,
    PriorityStock, Order, Trade, User
)
from services.database_service import DatabaseService

def render_database_admin_page():
    """Database Administration interface"""
    
    st.title("🗄️ Database Administration")
    st.markdown("*Comprehensive database management and testing interface*")
    
    # Authentication check
    if 'user' not in st.session_state or not st.session_state.user or st.session_state.user_role != 'admin':
        st.error("🚫 Access denied. Admin privileges required.")
        return
    
    session = get_session()
    db_service = DatabaseService(session)
    
    # Create tabs for different database operations
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Database Overview", 
        "⚙️ Environment Variables", 
        "🏦 Brokerages & Accounts",
        "📈 Stock Management",
        "🔄 Priority System"
    ])
    
    with tab1:
        render_database_overview(session, db_service)
    
    with tab2:
        render_environment_variables(session)
    
    with tab3:
        render_brokerages_accounts(session)
    
    with tab4:
        render_stock_management(session)
    
    with tab5:
        render_priority_system(session, db_service)
    
    session.close()

def render_database_overview(session, db_service):
    """Database overview and statistics"""
    
    st.subheader("📊 Database Statistics")
    
    # Get comprehensive stats
    stats = db_service.get_database_stats()
    
    # Create metrics display
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Environment Variables", stats['environment_variables'])
        st.metric("Total Stocks", stats['stocks_total'])
    
    with col2:
        st.metric("Priority Stocks", stats['stocks_priority_1'])
        st.metric("Sector ETFs", stats['stocks_sector_etf'])
    
    with col3:
        st.metric("Current Price Records", stats['priority_current_prices'])
        st.metric("Archive Price Records", stats['priority_archive_prices'])
    
    with col4:
        st.metric("Total Orders", stats['orders_total'])
        st.metric("Pending Orders", stats['orders_pending'])
    
    st.divider()
    
    # Tables overview
    st.subheader("📋 Table Structure Overview")
    
    table_info = [
        {"Table": "environment_variables", "Purpose": "Global trading configuration parameters", "Key Features": "Trading mode, broker settings, risk parameters"},
        {"Table": "brokerage_info", "Purpose": "Broker credentials and fee structures", "Key Features": "RobinHood, Alpaca support with trading fees"},
        {"Table": "accounts", "Purpose": "Individual trading accounts per brokerage", "Key Features": "Balance tracking, account types"},
        {"Table": "stocks", "Purpose": "S&P 500 stocks + sector ETFs with priority system", "Key Features": "Priority ranking (0=normal, 1=priority, 9=ETF)"},
        {"Table": "stock_price_history", "Purpose": "90-day historical data with technical indicators", "Key Features": "ADX, DMI, pivot points, Bollinger bands, CCI"},
        {"Table": "priority_current_price", "Purpose": "Real-time tracking for priority stocks", "Key Features": "Updated every X seconds, bid/ask spreads"},
        {"Table": "priority_archive_price", "Purpose": "Daily archive of priority price data", "Key Features": "Moved daily, purged after X days"},
        {"Table": "orders", "Purpose": "Complete order lifecycle tracking", "Key Features": "Stocks + options, LIFO calculations"},
        {"Table": "transaction_log", "Purpose": "LIFO gain/loss tracking", "Key Features": "Tax reporting, wash sale detection"}
    ]
    
    st.dataframe(pd.DataFrame(table_info), use_container_width=True)

def render_environment_variables(session):
    """Environment variables management"""
    
    st.subheader("⚙️ Environment Variables")
    
    # Display current variables
    env_vars = session.query(GlobalEnvVar).order_by(GlobalEnvVar.name).all()
    
    if env_vars:
        # Create DataFrame for display
        env_data = []
        for var in env_vars:
            env_data.append({
                "Name": var.name,
                "Value": var.value,
                "Type": var.value_type,
                "Description": (var.description[:50] + "..." if var.description and len(var.description) > 50 else (var.description or "N/A"))
            })
        
        df = pd.DataFrame(env_data)
        st.dataframe(df, use_container_width=True, height=400)
        
        st.divider()
        
        # Key environment variables for trading
        st.subheader("🔧 Key Trading Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trading_mode = next((v.value for v in env_vars if v.name == "TRADING_MODE"), "paper")
            active_broker = next((v.value for v in env_vars if v.name == "ACTIVE_BROKER"), "alpaca")
            
            st.info(f"**Trading Mode:** {trading_mode}")
            st.info(f"**Active Broker:** {active_broker}")
        
        with col2:
            price_interval = next((v.value for v in env_vars if v.name == "PRICE_UPDATE_INTERVAL"), "30")
            max_position = next((v.value for v in env_vars if v.name == "MAX_POSITION_SIZE_PERCENT"), "5")
            
            st.info(f"**Price Update Interval:** {price_interval} seconds")
            st.info(f"**Max Position Size:** {max_position}%")

def render_brokerages_accounts(session):
    """Account management"""
    
    st.subheader("💳 Trading Accounts")
    
    # Display accounts
    accounts = session.query(Account).all()
    
    if accounts:
        account_data = []
        for account in accounts:
            account_data.append({
                "User": account.user.username if account.user else "N/A",
                "Broker Platform": account.broker_platform or "N/A",
                "Account Number": account.broker_account_id or "N/A",
                "Active": "✓" if account.is_active else "✗"
            })
        
        st.dataframe(pd.DataFrame(account_data), use_container_width=True)
    else:
        st.info("No trading accounts configured yet.")

def render_stock_management(session):
    """Stock management interface"""
    
    st.subheader("📈 Stock Management")
    
    # Stock summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_stocks = session.query(Stock).count()
        st.metric("Total Stocks", total_stocks)
    
    with col2:
        priority_flagged = session.query(PriorityStock).count()
        st.metric("Priority Flagged", priority_flagged)
    
    with col3:
        active_stocks = session.query(Stock).filter(Stock.is_active == True).count()
        st.metric("Active Stocks", active_stocks)
    
    st.divider()
    
    st.info("📋 **Stock Universe**: Stocks with market segment categorization")
    
    # Display all stocks
    stocks = session.query(Stock).order_by(Stock.symbol).all()
    
    if stocks:
        stock_data = []
        for stock in stocks:
            # Check if stock is priority flagged
            priority_record = session.query(PriorityStock).filter(PriorityStock.stock_id == stock.id).first()
            
            stock_data.append({
                "Symbol": stock.symbol,
                "Name": stock.name,
                "Market Segment": stock.market_segment.name if stock.market_segment else "N/A",
                "Priority Score": f"{priority_record.score:.2f}" if priority_record else "0.00",
                "Active": "✓" if stock.is_active else "✗"
            })
        
        st.dataframe(pd.DataFrame(stock_data), use_container_width=True, height=400)
    else:
        st.info("No stocks found in database.")

def render_priority_system(session, db_service):
    """Priority system management and testing"""
    
    st.subheader("🔄 Priority System Management")
    
    # Priority system operations
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Update Stock Priorities", help="Recalculate priorities based on 20-day MA and volatility"):
            with st.spinner("Updating stock priorities..."):
                try:
                    updated_count = db_service.update_stock_priorities()
                    st.success(f"✅ Updated priorities for {updated_count} stocks")
                except Exception as e:
                    st.error(f"❌ Error updating priorities: {e}")
        
        if st.button("📊 Update Priority Prices", help="Add current price records for priority stocks"):
            with st.spinner("Updating priority prices..."):
                try:
                    updated_count = db_service.update_priority_current_prices()
                    st.success(f"✅ Updated {updated_count} priority price records")
                except Exception as e:
                    st.error(f"❌ Error updating prices: {e}")
    
    with col2:
        if st.button("📦 Archive Old Prices", help="Move yesterday's prices to archive"):
            with st.spinner("Archiving old prices..."):
                try:
                    archived_count = db_service.archive_priority_prices()
                    st.success(f"✅ Archived {archived_count} price records")
                except Exception as e:
                    st.error(f"❌ Error archiving: {e}")
        
        if st.button("🗑️ Purge Old Archives", help="Remove archive data older than retention period"):
            with st.spinner("Purging old archives..."):
                try:
                    purged_count = db_service.purge_old_archive_data()
                    st.success(f"✅ Purged {purged_count} old archive records")
                except Exception as e:
                    st.error(f"❌ Error purging: {e}")
    
    st.divider()
    
    # Trading opportunities analysis
    st.subheader("🎯 Trading Opportunities")
    
    if st.button("🔍 Evaluate Trading Opportunities"):
        with st.spinner("Analyzing trading opportunities..."):
            try:
                opportunities = db_service.evaluate_trading_opportunities()
                
                if opportunities:
                    opp_data = []
                    for opp in opportunities:
                        opp_data.append({
                            "Symbol": opp['symbol'],
                            "Action": opp['action'].upper(),
                            "Current Price": f"${opp['current_price']:.2f}",
                            "Momentum": f"{opp['momentum']:.2f}%",
                            "Confidence": f"{opp['confidence']:.1f}%"
                        })
                    
                    st.dataframe(pd.DataFrame(opp_data), use_container_width=True)
                else:
                    st.info("No trading opportunities found at this time.")
                    
            except Exception as e:
                st.error(f"❌ Error evaluating opportunities: {e}")
    
    # Recent priority stocks
    st.divider()
    st.subheader("📈 Priority Stock Rankings")
    
    priority_stocks = session.query(PriorityStock).order_by(
        PriorityStock.score.desc()
    ).limit(20).all()
    
    if priority_stocks:
        priority_data = []
        for ps in priority_stocks:
            stock = ps.stock
            priority_data.append({
                "Symbol": stock.symbol if stock else "N/A",
                "Name": stock.name if stock else "N/A",
                "Score": f"{ps.score:.2f}" if ps.score else "0",
                "Flagged At": ps.flagged_at.strftime("%Y-%m-%d %H:%M:%S") if ps.flagged_at else "N/A",
                "Reason": ps.reason[:50] if ps.reason else "N/A"
            })
        
        st.dataframe(pd.DataFrame(priority_data), use_container_width=True, height=300)
    else:
        st.info("No priority stocks flagged yet.")

if __name__ == "__main__":
    render_database_admin_page()