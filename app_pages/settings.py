import streamlit as st
import pandas as pd
from datetime import datetime

from database.database import get_session
from database.models import EnvironmentVariable, BrokerageInfo, Account, User
from utils.auth import check_permission, hash_password
from services.data_fetcher import DataFetcher
from utils.broker_status_widget import display_animated_broker_status

def show_settings_page():
    """Settings and configuration page"""
    st.title("⚙️ Settings & Configuration")
    
    # Check user permissions
    user = st.session_state.user
    is_admin = user.role == 'admin'
    is_trader = user.role == 'trader'
    is_viewer = user.role == 'viewer'
    
    # Settings tabs based on role
    if is_admin:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Trading Settings", 
            "🏦 Broker Configuration", 
            "💰 Account Settings",
            "🔧 System Settings",
            "👤 User Profile"
        ])
    elif is_trader:
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Trading Settings",
            "🏦 Broker Configuration",
            "💰 Account Settings", 
            "👤 User Profile"
        ])
    else:  # viewer
        tab1, tab2 = st.tabs(["💰 Account Settings", "👤 User Profile"])
        
        with tab1:
            _show_account_settings()
        with tab2:
            _show_user_profile()
        return
    
    # Admin tabs
    if is_admin:
        with tab1:
            _show_trading_settings()
        with tab2:
            _show_broker_configuration()
        with tab3:
            _show_account_settings()
        with tab4:
            _show_system_settings()
        with tab5:
            _show_user_profile()
    
    # Trader tabs
    elif is_trader:
        with tab1:
            _show_trading_settings()
        with tab2:
            _show_broker_configuration()
        with tab3:
            _show_account_settings()
        with tab4:
            _show_user_profile()

def _show_trading_settings():
    """Show trading configuration settings"""
    st.subheader("📊 Trading Configuration")
    
    session = get_session()
    try:
        # Get current environment variables
        env_vars = {var.key: var.value for var in session.query(EnvironmentVariable).all()}
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**General Trading Settings**")
            
            # Trading mode
            trading_mode = st.selectbox(
                "Trading Mode",
                ["paper", "live"],
                index=0 if env_vars.get('TRADING_MODE', 'paper') == 'paper' else 1
            )
            
            # Active broker
            active_broker = st.selectbox(
                "Active Broker",
                ["alpaca", "robinhood"],
                index=0 if env_vars.get('ACTIVE_BROKER', 'alpaca') == 'alpaca' else 1
            )
            
            # Price update interval
            price_interval = st.number_input(
                "Price Update Interval (seconds)",
                min_value=5,
                max_value=300,
                value=int(env_vars.get('PRICE_UPDATE_INTERVAL', '30'))
            )
        
        with col2:
            st.write("**Risk Management**")
            
            # Maximum position size
            max_position_size = st.number_input(
                "Max Position Size (%)",
                min_value=1.0,
                max_value=25.0,
                value=float(env_vars.get('MAX_POSITION_SIZE_PERCENT', '5.0')),
                step=0.5
            )
            
            # Risk management enabled
            risk_management = st.checkbox(
                "Enable Risk Management",
                value=env_vars.get('RISK_MANAGEMENT_ENABLED', 'true').lower() == 'true'
            )
            
            # Technical analysis periods
            ta_periods = st.number_input(
                "Technical Analysis Periods",
                min_value=5,
                max_value=50,
                value=int(env_vars.get('TECHNICAL_ANALYSIS_PERIODS', '14'))
            )
        
        st.write("**Data Management**")
        
        col3, col4 = st.columns(2)
        
        with col3:
            # Archive retention
            archive_days = st.number_input(
                "Archive Retention (days)",
                min_value=7,
                max_value=365,
                value=int(env_vars.get('ARCHIVE_RETENTION_DAYS', '30'))
            )
        
        with col4:
            # Auto-update settings
            auto_update = st.checkbox(
                "Auto-update Market Data",
                value=True
            )
        
        # Save button
        if st.button("💾 Save Trading Settings", type="primary"):
            _save_environment_variables(session, {
                'TRADING_MODE': trading_mode,
                'ACTIVE_BROKER': active_broker,
                'PRICE_UPDATE_INTERVAL': str(price_interval),
                'MAX_POSITION_SIZE_PERCENT': str(max_position_size),
                'RISK_MANAGEMENT_ENABLED': str(risk_management).lower(),
                'TECHNICAL_ANALYSIS_PERIODS': str(ta_periods),
                'ARCHIVE_RETENTION_DAYS': str(archive_days)
            })
            st.success("Trading settings saved successfully!")
            st.rerun()
    
    except Exception as e:
        st.error(f"Error loading trading settings: {e}")
    finally:
        session.close()

def _show_broker_configuration():
    """Show comprehensive broker API configuration"""
    st.subheader("🏦 Broker Configuration")
    
    session = get_session()
    try:
        # Get current configuration from environment variables
        trading_mode_var = session.query(EnvironmentVariable)\
            .filter(EnvironmentVariable.key == 'TRADING_MODE').first()
        paper_broker_var = session.query(EnvironmentVariable)\
            .filter(EnvironmentVariable.key == 'PAPER_TRADING_BROKER').first()
        live_broker_var = session.query(EnvironmentVariable)\
            .filter(EnvironmentVariable.key == 'LIVE_TRADING_BROKER').first()
        
        current_mode = trading_mode_var.value if trading_mode_var else 'paper'
        current_paper_broker = paper_broker_var.value if paper_broker_var else 'alpaca_paper'
        current_live_broker = live_broker_var.value if live_broker_var else 'robinhood'
        
        # Current active broker display
        active_broker = current_paper_broker if current_mode == 'paper' else current_live_broker
        st.success(f"🎯 **Currently Active:** {active_broker} ({'Paper Trading' if current_mode == 'paper' else 'Live Trading'})")
        
        # Trading mode selection
        st.write("**Trading Mode Configuration**")
        trading_mode = st.selectbox(
            "Trading Mode",
            ["paper", "live"],
            index=0 if current_mode == 'paper' else 1,
            help="Paper trading uses virtual money, Live trading uses real money",
            key="trading_mode_select"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Paper Trading Broker")
            paper_broker = st.selectbox(
                "Paper Trading Broker",
                ["alpaca_paper", "tradier_paper", "robinhood"],
                index=["alpaca_paper", "tradier_paper", "robinhood"].index(current_paper_broker) if current_paper_broker in ["alpaca_paper", "tradier_paper", "robinhood"] else 0,
                key="paper_broker_select"
            )
            
            # Show broker details
            broker_details = {
                'alpaca_paper': "✅ Alpaca Markets - Paper Trading\n• Free real market data\n• $100K virtual portfolio\n• Full API access",
                'tradier_paper': "⚙️ Tradier - Sandbox Environment\n• Developer friendly\n• Options trading focus\n• Mock implementation",
                'robinhood': "🚧 Robinhood - Mock Interface\n• Commission free design\n• Future implementation\n• Mock data only"
            }
            st.info(broker_details.get(paper_broker, ""))
        
        with col2:
            st.subheader("💰 Live Trading Broker")
            live_broker = st.selectbox(
                "Live Trading Broker",
                ["robinhood", "alpaca_live", "tradier_live"],
                index=["robinhood", "alpaca_live", "tradier_live"].index(current_live_broker) if current_live_broker in ["robinhood", "alpaca_live", "tradier_live"] else 0,
                key="live_broker_select"
            )
            
            # Show broker details
            live_details = {
                'robinhood': "🚧 Robinhood - Commission Free\n• $0 stock trades\n• $0 options contracts\n• Future implementation",
                'alpaca_live': "⚠️ Alpaca Markets - Live Trading\n• Real money trades\n• Professional API\n• Requires live API keys",
                'tradier_live': "💼 Tradier - Professional Platform\n• Advanced options trading\n• Institutional features\n• Future implementation"
            }
            st.info(live_details.get(live_broker, ""))
        
        # Save configuration button
        if st.button("💾 Save Broker Configuration", type="primary"):
            # Update or create environment variables
            def update_env_var(key: str, value: str):
                env_var = session.query(EnvironmentVariable)\
                    .filter(EnvironmentVariable.key == key).first()
                if env_var:
                    env_var.value = value
                else:
                    env_var = EnvironmentVariable(key=key, value=value)
                    session.add(env_var)
            
            update_env_var('TRADING_MODE', trading_mode)
            update_env_var('PAPER_TRADING_BROKER', paper_broker)
            update_env_var('LIVE_TRADING_BROKER', live_broker)
            
            session.commit()
            
            # Clear broker manager cache to force re-initialization across all pages
            if 'broker_manager' in st.session_state:
                del st.session_state['broker_manager']
            
            st.success("✅ Broker configuration saved! All pages updated.")
            st.info("🔄 Dashboard, Trading, and Portfolio pages will now use the new broker.")
            st.balloons()
            st.rerun()
        
        # Show current broker status with animated widget
        st.subheader("📊 Live Broker Connection Status")
        is_connected, account_info = display_animated_broker_status()
        
        if not is_connected:
            st.error("⚠️ Connection test failed. Please verify broker credentials and network connectivity.")
        
        # Trading fees configuration  
        st.subheader("💰 Trading Fees Configuration")
        broker_info = session.query(BrokerageInfo).first()
        
        if not broker_info:
            broker_info = BrokerageInfo(
                name="Default Broker",
                trading_fees_per_share=0.01,
                trading_fees_per_contract=0.65,
                api_endpoint="https://api.broker.com",
                is_active=True
            )
            session.add(broker_info)
            session.commit()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fees_per_share = st.number_input(
                "Trading Fees per Share ($)", 
                value=float(broker_info.trading_fees_per_share),
                min_value=0.0, 
                step=0.01,
                key="broker_fees_per_share"
            )
        
        with col2:
            fees_per_contract = st.number_input(
                "Trading Fees per Contract ($)", 
                value=float(broker_info.trading_fees_per_contract),
                min_value=0.0, 
                step=0.01,
                key="broker_fees_per_contract"
            )
        
        if st.button("💰 Save Trading Fees"):
            broker_info.trading_fees_per_share = fees_per_share
            broker_info.trading_fees_per_contract = fees_per_contract
            session.commit()
            st.success("Trading fees updated successfully!")
        
        with col6:
            if st.button("💾 Save Broker Configuration"):
                _save_broker_configuration(
                    session, broker_name, api_url, api_key, api_secret,
                    trading_fees_per_share, trading_fees_per_contract, day_trade_limit, is_active
                )
                st.success(f"Broker {broker_name} configuration saved!")
                st.rerun()
    
    except Exception as e:
        st.error(f"Error in broker configuration: {e}")
    finally:
        session.close()

def _show_account_settings():
    """Show account management settings"""
    st.subheader("💰 Account Settings")
    
    session = get_session()
    try:
        accounts = session.query(Account).all()
        
        # Display existing accounts
        st.write("**Trading Accounts**")
        
        if accounts:
            account_data = []
            for account in accounts:
                brokerage = session.query(BrokerageInfo).filter(
                    BrokerageInfo.id == account.brokerage_id
                ).first()
                
                account_data.append({
                    "Account Name": account.account_name,
                    "Brokerage": brokerage.name if brokerage else "Unknown",
                    "Type": account.account_type.title(),
                    "Total Balance": f"${account.total_balance:,.2f}",
                    "Cash Balance": f"${account.cash_balance:,.2f}",
                    "Status": "Active" if account.is_active else "Inactive"
                })
            
            df = pd.DataFrame(account_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No accounts configured")
        
        # Add new account form
        st.write("**Add New Account**")
        
        # Get available brokerages
        brokerages = session.query(BrokerageInfo).filter(BrokerageInfo.is_active == True).all()
        
        if brokerages:
            col1, col2 = st.columns(2)
            
            with col1:
                selected_brokerage = st.selectbox(
                    "Brokerage",
                    brokerages,
                    format_func=lambda x: x.name
                )
                
                account_name = st.text_input("Account Name")
            
            with col2:
                account_type = st.selectbox(
                    "Account Type",
                    ["cash", "margin", "ira"]
                )
                
                initial_balance = st.number_input(
                    "Initial Balance ($)",
                    min_value=0.0,
                    value=10000.0
                )
            
            if st.button("➕ Add Account"):
                if account_name:
                    _add_new_account(
                        session, selected_brokerage.id, account_name,
                        account_type, initial_balance
                    )
                    st.success(f"Account {account_name} added successfully!")
                    st.rerun()
                else:
                    st.error("Please enter an account name")
        else:
            st.warning("Please configure at least one brokerage first")
    
    except Exception as e:
        st.error(f"Error in account settings: {e}")
    finally:
        session.close()

def _show_system_settings():
    """Show system-wide settings"""
    st.subheader("🔧 System Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Data Management**")
        
        if st.button("🔄 Update Stock Database"):
            with st.spinner("Updating stock database..."):
                try:
                    data_fetcher = DataFetcher()
                    data_fetcher.update_stock_database()
                    st.success("Stock database updated!")
                except Exception as e:
                    st.error(f"Error updating stock database: {e}")
        
        if st.button("📊 Update Historical Data"):
            with st.spinner("Updating historical data..."):
                try:
                    data_fetcher = DataFetcher()
                    data_fetcher.update_historical_data(days=90)
                    st.success("Historical data updated!")
                except Exception as e:
                    st.error(f"Error updating historical data: {e}")
        
        if st.button("🎯 Update Priority Stocks"):
            with st.spinner("Analyzing priority stocks..."):
                try:
                    data_fetcher = DataFetcher()
                    data_fetcher.update_priority_stocks()
                    st.success("Priority stocks updated!")
                except Exception as e:
                    st.error(f"Error updating priority stocks: {e}")
    
    with col2:
        st.write("**Database Maintenance**")
        
        if st.button("🗄️ Archive Old Data"):
            with st.spinner("Archiving old data..."):
                try:
                    data_fetcher = DataFetcher()
                    data_fetcher.archive_priority_prices()
                    st.success("Old data archived!")
                except Exception as e:
                    st.error(f"Error archiving data: {e}")
        
        if st.button("🧹 Cleanup Database"):
            st.warning("Database cleanup will remove old records. This action cannot be undone.")
            if st.button("Confirm Cleanup", type="secondary"):
                st.info("Database cleanup feature not implemented in demo")
        
        st.write("**System Information**")
        st.info(f"Database: SQLite")
        st.info(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def _show_user_profile():
    """Show user profile and preferences"""
    st.subheader("👤 User Profile")
    
    user = st.session_state.user
    
    # User information
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Account Information**")
        st.info(f"Username: {user.username}")
        st.info(f"Email: {user.email}")
        st.info(f"Role: {user.role.title()}")
        st.info(f"Member Since: {user.created_at.strftime('%Y-%m-%d')}")
    
    with col2:
        st.write("**Update Profile**")
        
        new_email = st.text_input("New Email", value=user.email)
        
        if st.button("📧 Update Email"):
            if new_email != user.email:
                session = get_session()
                try:
                    user_record = session.query(User).filter(User.id == user.id).first()
                    if user_record:
                        user_record.email = new_email
                        session.commit()
                        st.success("Email updated successfully!")
                        st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"Error updating email: {e}")
                finally:
                    session.close()
    
    # Change password
    st.write("**Change Password**")
    
    col3, col4 = st.columns(2)
    
    with col3:
        current_password = st.text_input("Current Password", type="password")
    
    with col4:
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
    
    if st.button("🔐 Change Password"):
        if new_password != confirm_password:
            st.error("New passwords don't match")
        elif len(new_password) < 6:
            st.error("Password must be at least 6 characters")
        else:
            session = get_session()
            try:
                from utils.auth import verify_password
                user_record = session.query(User).filter(User.id == user.id).first()
                
                if user_record and verify_password(current_password, user_record.password_hash):
                    user_record.password_hash = hash_password(new_password)
                    session.commit()
                    st.success("Password changed successfully!")
                else:
                    st.error("Current password is incorrect")
            except Exception as e:
                session.rollback()
                st.error(f"Error changing password: {e}")
            finally:
                session.close()

def _save_environment_variables(session, variables):
    """Save environment variables to database"""
    try:
        for key, value in variables.items():
            env_var = session.query(EnvironmentVariable).filter(
                EnvironmentVariable.key == key
            ).first()
            
            if env_var:
                env_var.value = value
                env_var.updated_at = datetime.utcnow()
            else:
                env_var = EnvironmentVariable(
                    key=key,
                    value=value,
                    description=f"Auto-generated {key}"
                )
                session.add(env_var)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e

def _save_broker_configuration(session, name, api_url, api_key, api_secret, 
                             trading_fees_per_share, trading_fees_per_contract, day_trade_limit, is_active):
    """Save broker configuration"""
    try:
        broker = session.query(BrokerageInfo).filter(
            BrokerageInfo.name == name
        ).first()
        
        if broker:
            broker.api_url = api_url
            broker.trading_fees_per_share = trading_fees_per_share
            broker.trading_fees_per_contract = trading_fees_per_contract
            broker.day_trade_limit = day_trade_limit
            broker.is_active = is_active
            if api_key:
                broker.api_key = api_key
            if api_secret:
                broker.api_secret = api_secret
        else:
            broker = BrokerageInfo(
                name=name,
                api_url=api_url,
                api_key=api_key,
                api_secret=api_secret,
                trading_fees_per_share=trading_fees_per_share,
                trading_fees_per_contract=trading_fees_per_contract,
                day_trade_limit=day_trade_limit,
                is_active=is_active
            )
            session.add(broker)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e

def _add_new_account(session, brokerage_id, account_name, account_type, initial_balance):
    """Add new trading account"""
    try:
        account = Account(
            brokerage_id=brokerage_id,
            account_name=account_name,
            account_type=account_type,
            total_balance=initial_balance,
            cash_balance=initial_balance,
            is_active=True
        )
        session.add(account)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
