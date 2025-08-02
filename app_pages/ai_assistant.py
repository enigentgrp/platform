import streamlit as st
import pandas as pd
from datetime import datetime
from services.ai_assistant import TradingAssistant
from database.database import get_session
from database.models import Stock

def show_ai_assistant_page():
    """Show AI trading assistant page"""
    st.title("🤖 AI Trading Assistant")
    
    if not st.session_state.get('authenticated', False):
        st.error("Please log in to access the AI assistant")
        return
    
    user = st.session_state.user
    assistant = TradingAssistant()
    
    # Create tabs for different assistant features
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📊 Market Analysis", "🎯 Opportunities", "📈 Portfolio Insights"])
    
    with tab1:
        st.subheader("Chat with Your Trading Assistant")
        
        # Initialize chat history
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = [
                {"role": "assistant", "content": f"Hello {user.username}! I'm your AI trading assistant. Ask me about market conditions, stock recommendations, or portfolio advice."}
            ]
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask me anything about trading..."):
            # Add user message to chat history
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.write(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    response = assistant.ask_question(prompt, user.id)
                    st.write(response)
                    
                    # Add assistant response to chat history
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
        
        # Quick action buttons
        st.subheader("Quick Questions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Market Outlook"):
                response = assistant.ask_question("What's the current market sentiment?", user.id)
                st.session_state.chat_history.append({"role": "user", "content": "What's the current market sentiment?"})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
        
        with col2:
            if st.button("💼 Portfolio Review"):
                response = assistant.ask_question("How is my portfolio performing?", user.id)
                st.session_state.chat_history.append({"role": "user", "content": "How is my portfolio performing?"})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
        
        with col3:
            if st.button("⚠️ Risk Assessment"):
                response = assistant.ask_question("What's the current risk level?", user.id)
                st.session_state.chat_history.append({"role": "user", "content": "What's the current risk level?"})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
    
    with tab2:
        st.subheader("Real-time Market Analysis")
        
        # Get market sentiment
        sentiment = assistant.analyze_market_sentiment()
        
        # Display sentiment with color coding
        sentiment_colors = {
            "bullish": "🟢",
            "bearish": "🔴", 
            "neutral": "🟡"
        }
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Market Sentiment", 
                f"{sentiment_colors.get(sentiment, '⚪')} {sentiment.title()}",
                help="Overall market direction based on stock movements"
            )
        
        with col2:
            risk_level = assistant._assess_current_risk()
            risk_colors = {"high": "🔴", "moderate": "🟡", "low": "🟢"}
            st.metric(
                "Risk Level",
                f"{risk_colors.get(risk_level, '⚪')} {risk_level.title()}",
                help="Current market volatility assessment"
            )
        
        with col3:
            # Count active stocks
            session = get_session()
            active_stocks = session.query(Stock).filter(Stock.priority > 0).count()
            session.close()
            st.metric("Monitored Stocks", active_stocks, help="Stocks currently being tracked")
        
        # Market overview table
        st.subheader("Top Movers")
        
        try:
            session = get_session()
            stocks = session.query(Stock).filter(
                Stock.priority > 0,
                Stock.change_percent.isnot(None)
            ).order_by(Stock.change_percent.desc()).limit(10).all()
            
            if stocks:
                market_data = []
                for stock in stocks:
                    market_data.append({
                        "Symbol": stock.symbol,
                        "Name": stock.name,
                        "Price": f"${stock.last_price:.2f}" if stock.last_price else "N/A",
                        "Change %": f"{stock.change_percent:.2f}%" if stock.change_percent else "0.00%",
                        "Sector": stock.sector
                    })
                
                df = pd.DataFrame(market_data)
                
                # Color code the change column
                def color_change(val):
                    if "%" in str(val):
                        num = float(val.replace("%", ""))
                        if num > 0:
                            return "background-color: lightgreen"
                        elif num < 0:
                            return "background-color: lightcoral"
                    return ""
                
                styled_df = df.style.map(color_change, subset=['Change %'])
                st.dataframe(styled_df, use_container_width=True)
            else:
                st.info("No market data available")
            
            session.close()
        except Exception as e:
            st.error(f"Error loading market data: {str(e)}")
    
    with tab3:
        st.subheader("Trading Opportunities")
        
        opportunities = assistant.get_market_opportunities()
        
        if opportunities:
            for opp in opportunities:
                with st.container():
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.write(f"**{opp['symbol']}** - {opp['name']}")
                        st.caption(f"Sector: {opp['sector']}")
                    
                    with col2:
                        st.write(f"**{opp['type'].title()}** Play")
                        st.write(opp['reason'])
                    
                    with col3:
                        confidence_color = "🟢" if opp['confidence'] > 75 else "🟡" if opp['confidence'] > 60 else "🔴"
                        st.metric("Confidence", f"{confidence_color} {opp['confidence']:.0f}%")
                    
                    # Action buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Analyze {opp['symbol']}", key=f"analyze_{opp['symbol']}"):
                            rec = assistant.get_stock_recommendation(opp['symbol'])
                            st.info(f"**Recommendation**: {rec['recommendation'].replace('_', ' ').title()}\n\n**Reason**: {rec['reason']}")
                    
                    with col2:
                        if st.button(f"Add to Watchlist", key=f"watch_{opp['symbol']}"):
                            st.success(f"Added {opp['symbol']} to watchlist")
                    
                    st.divider()
        else:
            st.info("No specific opportunities identified at the moment. Market appears stable.")
    
    with tab4:
        st.subheader("Portfolio Insights & Recommendations")
        
        # Get comprehensive analysis
        analysis = assistant.get_contextual_advice(user.id)
        
        # Portfolio health overview
        portfolio = analysis['portfolio_analysis']
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Positions", portfolio.get('total_positions', 0))
        
        with col2:
            health = portfolio.get('portfolio_health', 'Unknown')
            health_color = "🟢" if "well" in health.lower() else "🟡" if "moderate" in health.lower() else "🔴"
            st.metric("Portfolio Health", f"{health_color} {health}")
        
        with col3:
            risk = portfolio.get('risk_level', 'unknown')
            risk_color = "🔴" if risk == "high" else "🟡" if risk == "moderate" else "🟢"
            st.metric("Risk Level", f"{risk_color} {risk.title()}")
        
        # AI Advice
        st.subheader("🎯 Personalized Advice")
        st.write(analysis['advice'])
        
        # Suggested Actions
        if analysis.get('suggested_actions'):
            st.subheader("📋 Recommended Actions")
            for action in analysis['suggested_actions']:
                st.write(f"• {action}")
        
        # Risk Assessment Details
        st.subheader("⚠️ Risk Analysis")
        risk_assessment = analysis['risk_assessment']
        
        if risk_assessment == "high":
            st.warning("⚠️ High risk environment detected. Consider reducing position sizes and implementing tighter stop-losses.")
        elif risk_assessment == "moderate":
            st.info("ℹ️ Moderate risk conditions. Normal risk management practices apply.")
        else:
            st.success("✅ Low risk environment. Consider slightly larger positions if fundamentals support it.")
        
        # Performance tracking placeholder
        st.subheader("📈 Performance Tracking")
        st.info("Portfolio performance tracking will be enhanced as you make more trades. The AI learns from your trading patterns to provide better recommendations.")
    
    # Sidebar with quick stats
    with st.sidebar:
        st.subheader("🤖 Assistant Status")
        st.success("AI Assistant Online")
        
        st.subheader("📊 Quick Stats")
        try:
            session = get_session()
            total_stocks = session.query(Stock).count()
            priority_stocks = session.query(Stock).filter(Stock.priority > 0).count()
            session.close()
            
            st.metric("Total Stocks", total_stocks)
            st.metric("Priority Stocks", priority_stocks)
            st.metric("Chat Messages", len(st.session_state.get('chat_history', [])))
        except Exception:
            st.info("Unable to load stats")
        
        # Clear chat button
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = [
                {"role": "assistant", "content": f"Hello {user.username}! I'm your AI trading assistant. Ask me about market conditions, stock recommendations, or portfolio advice."}
            ]
            st.rerun()