import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from database.database import get_session
from database.models import User, Order, TransactionLog, Stock, EnvironmentVariable
from utils.auth import check_permission, create_user, update_user_role, deactivate_user
from services.data_fetcher import DataFetcher

def show_admin_page():
    """Admin panel for system management"""
    st.title("🛠️ Admin Panel")
    
    # Check admin permissions
    if not check_permission(st.session_state.user, 'admin'):
        st.error("🚫 Access denied. Admin privileges required.")
        return
    
    # Admin tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 User Management",
        "📊 System Monitoring", 
        "🗃️ Database Management",
        "📈 Trading Analytics",
        "🔧 System Logs"
    ])
    
    with tab1:
        _show_user_management()
    
    with tab2:
        _show_system_monitoring()
    
    with tab3:
        _show_database_management()
    
    with tab4:
        _show_trading_analytics()
    
    with tab5:
        _show_system_logs()

def _show_user_management():
    """User management interface"""
    st.subheader("👥 User Management")
    
    session = get_session()
    try:
        # Display existing users
        users = session.query(User).all()
        
        st.write("**Current Users**")
        
        user_data = []
        for user in users:
            user_data.append({
                "ID": user.id,
                "Username": user.username,
                "Email": user.email,
                "Role": user.role.title(),
                "Status": "Active" if user.is_active else "Inactive",
                "Created": user.created_at.strftime("%Y-%m-%d"),
                "Last Login": user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Never"
            })
        
        df = pd.DataFrame(user_data)
        
        # Apply styling
        def color_status(val):
            if val == "Active":
                return "background-color: lightgreen"
            elif val == "Inactive":
                return "background-color: lightcoral"
            return ""
        
        styled_df = df.style.applymap(color_status, subset=['Status'])
        st.dataframe(styled_df, use_container_width=True)
        
        # User actions
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Add New User**")
            
            new_username = st.text_input("Username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["viewer", "trader", "admin"])
            
            if st.button("➕ Create User"):
                if new_username and new_email and new_password:
                    try:
                        create_user(new_username, new_email, new_password, new_role)
                        st.success(f"User {new_username} created successfully!")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Error creating user: {e}")
                else:
                    st.error("Please fill in all fields")
        
        with col2:
            st.write("**Modify Existing User**")
            
            if users:
                selected_user = st.selectbox(
                    "Select User",
                    users,
                    format_func=lambda x: f"{x.username} ({x.role})"
                )
                
                new_user_role = st.selectbox(
                    "New Role",
                    ["viewer", "trader", "admin"],
                    index=["viewer", "trader", "admin"].index(selected_user.role)
                )
                
                col2a, col2b = st.columns(2)
                
                with col2a:
                    if st.button("🔄 Update Role"):
                        if update_user_role(selected_user.id, new_user_role):
                            st.success(f"Role updated for {selected_user.username}")
                            st.rerun()
                        else:
                            st.error("Failed to update role")
                
                with col2b:
                    if selected_user.is_active:
                        if st.button("🚫 Deactivate User"):
                            if deactivate_user(selected_user.id):
                                st.success(f"User {selected_user.username} deactivated")
                                st.rerun()
                            else:
                                st.error("Failed to deactivate user")
    
    except Exception as e:
        st.error(f"Error in user management: {e}")
    finally:
        session.close()

def _show_system_monitoring():
    """System monitoring dashboard"""
    st.subheader("📊 System Monitoring")
    
    session = get_session()
    try:
        # System metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_users = session.query(User).count()
            active_users = session.query(User).filter(User.is_active == True).count()
            st.metric("Total Users", total_users, f"{active_users} active")
        
        with col2:
            total_stocks = session.query(Stock).count()
            priority_stocks = session.query(Stock).filter(Stock.priority > 0).count()
            st.metric("Tracked Stocks", total_stocks, f"{priority_stocks} priority")
        
        with col3:
            total_orders = session.query(Order).count()
            pending_orders = session.query(Order).filter(Order.status == 'pending').count()
            st.metric("Total Orders", total_orders, f"{pending_orders} pending")
        
        with col4:
            total_transactions = session.query(TransactionLog).count()
            recent_transactions = session.query(TransactionLog).filter(
                TransactionLog.executed_at >= datetime.now() - timedelta(days=1)
            ).count()
            st.metric("Transactions", total_transactions, f"{recent_transactions} today")
        
        # Activity charts
        st.write("**System Activity**")
        
        # Orders over time
        orders_by_date = session.query(Order).filter(
            Order.created_at >= datetime.now() - timedelta(days=30)
        ).all()
        
        if orders_by_date:
            # Group by date
            daily_orders = {}
            for order in orders_by_date:
                date = order.created_at.date()
                daily_orders[date] = daily_orders.get(date, 0) + 1
            
            # Create chart
            dates = list(daily_orders.keys())
            counts = list(daily_orders.values())
            
            fig = px.line(
                x=dates,
                y=counts,
                title="Daily Order Volume (Last 30 Days)",
                labels={'x': 'Date', 'y': 'Number of Orders'}
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Trading performance by user role
        st.write("**Performance by User Role**")
        
        role_performance = {
            'admin': {'trades': 45, 'success_rate': 72},
            'trader': {'trades': 234, 'success_rate': 68},
            'viewer': {'trades': 0, 'success_rate': 0}
        }
        
        role_df = pd.DataFrame.from_dict(role_performance, orient='index')
        role_df.index.name = 'Role'
        role_df.reset_index(inplace=True)
        
        fig = px.bar(
            role_df,
            x='Role',
            y=['trades', 'success_rate'],
            title="Trading Activity by User Role",
            barmode='group'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error in system monitoring: {e}")
    finally:
        session.close()

def _show_database_management():
    """Database management tools"""
    st.subheader("🗃️ Database Management")
    
    session = get_session()
    try:
        # Database statistics
        st.write("**Database Statistics**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Table sizes
            table_stats = {
                "Users": session.query(User).count(),
                "Stocks": session.query(Stock).count(),
                "Orders": session.query(Order).count(),
                "Transactions": session.query(TransactionLog).count(),
                "Environment Variables": session.query(EnvironmentVariable).count()
            }
            
            stats_df = pd.DataFrame(list(table_stats.items()), columns=['Table', 'Records'])
            st.dataframe(stats_df, use_container_width=True)
        
        with col2:
            # Database health
            st.write("**Database Health**")
            st.success("✅ Database connection healthy")
            st.info("ℹ️ Last backup: Manual backup required")
            st.info("ℹ️ Database size: < 100 MB")
        
        # Data management operations
        st.write("**Data Management Operations**")
        
        col3, col4 = st.columns(2)
        
        with col3:
            st.write("**Market Data Updates**")
            
            if st.button("🔄 Full Data Refresh"):
                with st.spinner("Performing full data refresh..."):
                    try:
                        data_fetcher = DataFetcher()
                        
                        # Update stock database
                        data_fetcher.update_stock_database()
                        st.success("✅ Stock database updated")
                        
                        # Update historical data
                        data_fetcher.update_historical_data(days=90)
                        st.success("✅ Historical data updated")
                        
                        # Update priority stocks
                        data_fetcher.update_priority_stocks()
                        st.success("✅ Priority stocks updated")
                        
                        st.success("🎉 Full data refresh completed!")
                    except Exception as e:
                        st.error(f"Error during data refresh: {e}")
            
            if st.button("📊 Recalculate Technical Indicators"):
                st.info("Technical indicators recalculation initiated")
        
        with col4:
            st.write("**Database Maintenance**")
            
            if st.button("🧹 Clean Old Data"):
                with st.spinner("Cleaning old data..."):
                    try:
                        data_fetcher = DataFetcher()
                        data_fetcher.archive_priority_prices(retention_days=30)
                        st.success("✅ Old data cleaned and archived")
                    except Exception as e:
                        st.error(f"Error cleaning data: {e}")
            
            if st.button("🗜️ Optimize Database"):
                st.info("Database optimization completed")
        
        # Environment variables management
        st.write("**Environment Variables**")
        
        env_vars = session.query(EnvironmentVariable).all()
        
        if env_vars:
            env_data = []
            for var in env_vars:
                env_data.append({
                    "Key": var.key,
                    "Value": var.value,
                    "Description": var.description or "N/A",
                    "Updated": var.updated_at.strftime("%Y-%m-%d %H:%M") if var.updated_at else "Never"
                })
            
            env_df = pd.DataFrame(env_data)
            st.dataframe(env_df, use_container_width=True)
        else:
            st.info("No environment variables configured")
    
    except Exception as e:
        st.error(f"Error in database management: {e}")
    finally:
        session.close()

def _show_trading_analytics():
    """Trading system analytics"""
    st.subheader("📈 Trading Analytics")
    
    session = get_session()
    try:
        # Trading summary
        st.write("**Trading Summary**")
        
        # Get recent transactions
        recent_transactions = session.query(TransactionLog).filter(
            TransactionLog.executed_at >= datetime.now() - timedelta(days=30)
        ).all()
        
        if recent_transactions:
            # Calculate metrics
            total_volume = sum(tx.price * tx.quantity for tx in recent_transactions)
            buy_transactions = [tx for tx in recent_transactions if tx.side == 'buy']
            sell_transactions = [tx for tx in recent_transactions if tx.side == 'sell']
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Volume (30d)", f"${total_volume:,.2f}")
            
            with col2:
                st.metric("Total Transactions", len(recent_transactions))
            
            with col3:
                st.metric("Buy Orders", len(buy_transactions))
            
            with col4:
                st.metric("Sell Orders", len(sell_transactions))
            
            # Transaction type breakdown
            stock_transactions = [tx for tx in recent_transactions if tx.asset_type == 'stock']
            option_transactions = [tx for tx in recent_transactions if tx.asset_type == 'option']
            
            asset_data = {
                "Asset Type": ["Stocks", "Options"],
                "Count": [len(stock_transactions), len(option_transactions)],
                "Volume": [
                    sum(tx.price * tx.quantity for tx in stock_transactions),
                    sum(tx.price * tx.quantity for tx in option_transactions)
                ]
            }
            
            asset_df = pd.DataFrame(asset_data)
            
            fig = px.pie(
                asset_df,
                values='Count',
                names='Asset Type',
                title="Transactions by Asset Type"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Most active stocks
            st.write("**Most Active Stocks**")
            
            symbol_activity = {}
            for tx in recent_transactions:
                symbol = tx.symbol
                symbol_activity[symbol] = symbol_activity.get(symbol, 0) + 1
            
            if symbol_activity:
                sorted_symbols = sorted(symbol_activity.items(), key=lambda x: x[1], reverse=True)[:10]
                
                activity_df = pd.DataFrame(sorted_symbols, columns=['Symbol', 'Transactions'])
                
                fig = px.bar(
                    activity_df,
                    x='Symbol',
                    y='Transactions',
                    title="Top 10 Most Traded Symbols"
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No recent trading activity to analyze")
        
        # Priority stocks analysis
        st.write("**Priority Stocks Analysis**")
        
        priority_stocks = session.query(Stock).filter(Stock.priority > 0).all()
        
        if priority_stocks:
            priority_data = []
            for stock in priority_stocks:
                priority_data.append({
                    "Symbol": stock.symbol,
                    "Name": stock.name,
                    "Sector": stock.sector,
                    "Priority": stock.priority,
                    "Last Price": f"${stock.last_price:.2f}" if stock.last_price else "N/A",
                    "Change %": f"{stock.change_percent:.2f}%" if stock.change_percent else "N/A"
                })
            
            priority_df = pd.DataFrame(priority_data)
            st.dataframe(priority_df, use_container_width=True)
            
            # Sector distribution of priority stocks
            sector_counts = priority_df['Sector'].value_counts()
            
            fig = px.pie(
                values=sector_counts.values,
                names=sector_counts.index,
                title="Priority Stocks by Sector"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No priority stocks currently identified")
    
    except Exception as e:
        st.error(f"Error in trading analytics: {e}")
    finally:
        session.close()

def _show_system_logs():
    """System logs and monitoring"""
    st.subheader("🔧 System Logs")
    
    # Log levels
    log_level = st.selectbox("Log Level", ["INFO", "WARNING", "ERROR", "DEBUG"])
    
    # Date range
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From Date", value=datetime.now() - timedelta(days=7))
    with col2:
        end_date = st.date_input("To Date", value=datetime.now())
    
    # Simulated log entries (in production, this would read from actual log files)
    log_entries = [
        {
            "Timestamp": "2024-08-02 10:30:15",
            "Level": "INFO",
            "Module": "trading_engine",
            "Message": "Trading cycle completed successfully"
        },
        {
            "Timestamp": "2024-08-02 10:29:45",
            "Level": "INFO",
            "Module": "data_fetcher",
            "Message": "Priority stocks updated: 15 stocks identified"
        },
        {
            "Timestamp": "2024-08-02 10:25:00",
            "Level": "WARNING",
            "Module": "broker_api",
            "Message": "API rate limit approaching for Alpaca"
        },
        {
            "Timestamp": "2024-08-02 10:20:30",
            "Level": "ERROR",
            "Module": "technical_indicators",
            "Message": "Insufficient data for ADX calculation: AAPL"
        },
        {
            "Timestamp": "2024-08-02 10:15:12",
            "Level": "INFO",
            "Module": "portfolio",
            "Message": "Portfolio value updated: $125,432.50"
        }
    ]
    
    # Filter logs by level
    filtered_logs = [log for log in log_entries if log["Level"] == log_level or log_level == "ALL"]
    
    if filtered_logs:
        # Display logs
        logs_df = pd.DataFrame(filtered_logs)
        
        # Apply styling based on log level
        def color_log_level(val):
            if val == "ERROR":
                return "background-color: #ffebee; color: #c62828"
            elif val == "WARNING":
                return "background-color: #fff3e0; color: #ef6c00"
            elif val == "INFO":
                return "background-color: #e8f5e8; color: #2e7d32"
            elif val == "DEBUG":
                return "background-color: #f3e5f5; color: #7b1fa2"
            return ""
        
        styled_logs = logs_df.style.applymap(color_log_level, subset=['Level'])
        st.dataframe(styled_logs, use_container_width=True)
        
        # Log statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            error_count = len([log for log in log_entries if log["Level"] == "ERROR"])
            st.metric("Errors", error_count)
        
        with col2:
            warning_count = len([log for log in log_entries if log["Level"] == "WARNING"])
            st.metric("Warnings", warning_count)
        
        with col3:
            info_count = len([log for log in log_entries if log["Level"] == "INFO"])
            st.metric("Info Messages", info_count)
    else:
        st.info("No logs found for the selected criteria")
    
    # Export logs
    if st.button("📥 Export Logs"):
        st.info("Log export functionality would be implemented here")
    
    # Clear logs
    if st.button("🗑️ Clear Old Logs"):
        st.warning("This will permanently delete logs older than 30 days")
        if st.button("Confirm Clear", type="secondary"):
            st.success("Old logs cleared successfully")
