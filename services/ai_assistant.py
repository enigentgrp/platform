import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from database.database import get_session
from database.models import Stock, Order, Account, User
from services.technical_indicators import TechnicalIndicators
import random

class TradingAssistant:
    """AI-powered trading assistant that provides contextual advice"""
    
    def __init__(self):
        self.session = get_session()
        self.indicators = TechnicalIndicators()
        
    def analyze_market_sentiment(self) -> str:
        """Analyze current market sentiment based on available data"""
        try:
            stocks = self.session.query(Stock).filter(Stock.priority > 0).all()
            if not stocks:
                return "neutral"
                
            positive_moves = 0
            total_stocks = len(stocks)
            
            for stock in stocks:
                if stock.change_percent is not None and stock.change_percent > 0:
                    positive_moves += 1
                    
            sentiment_ratio = positive_moves / total_stocks if total_stocks > 0 else 0.5
            
            if sentiment_ratio > 0.6:
                return "bullish"
            elif sentiment_ratio < 0.4:
                return "bearish"
            else:
                return "neutral"
                
        except Exception:
            return "neutral"
    
    def get_portfolio_analysis(self, user_id: int) -> Dict[str, Any]:
        """Analyze user's portfolio and provide insights"""
        try:
            # Get user's orders/positions
            orders = self.session.query(Order).filter(
                Order.user_id == user_id,
                Order.status == 'filled'
            ).all()
            
            if not orders:
                return {
                    "total_positions": 0,
                    "portfolio_health": "No positions",
                    "risk_level": "low",
                    "suggestions": ["Start with paper trading to practice", "Consider diversified ETFs for beginners"]
                }
            
            # Calculate portfolio metrics
            total_value = sum(order.quantity * (order.fill_price or 0) for order in orders)
            position_count = len(set(order.symbol for order in orders))
            
            # Determine portfolio health
            if position_count < 3:
                portfolio_health = "Under-diversified"
                risk_level = "high"
            elif position_count > 10:
                portfolio_health = "Well-diversified"
                risk_level = "moderate"
            else:
                portfolio_health = "Moderately diversified"
                risk_level = "moderate"
            
            return {
                "total_positions": position_count,
                "portfolio_value": total_value,
                "portfolio_health": portfolio_health,
                "risk_level": risk_level,
                "recent_trades": len([o for o in orders if o.created_at is not None and 
                                    o.created_at > datetime.now() - timedelta(days=7)])
            }
            
        except Exception:
            return {
                "total_positions": 0,
                "portfolio_health": "Unable to analyze",
                "risk_level": "unknown",
                "suggestions": ["Check your account connection"]
            }
    
    def get_stock_recommendation(self, symbol: str) -> Dict[str, Any]:
        """Get recommendation for a specific stock"""
        try:
            stock = self.session.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                return {"recommendation": "unknown", "reason": "Stock not found in database"}
            
            # Simple recommendation logic based on change percent
            change = stock.change_percent if stock.change_percent is not None else 0
            price = stock.last_price if stock.last_price is not None else 0
            
            if change > 3:
                recommendation = "strong_buy"
                reason = f"{symbol} showing strong upward momentum (+{change:.1f}%)"
            elif change > 1:
                recommendation = "buy"
                reason = f"{symbol} has positive momentum (+{change:.1f}%)"
            elif change < -3:
                recommendation = "strong_sell"
                reason = f"{symbol} showing weakness ({change:.1f}%)"
            elif change < -1:
                recommendation = "sell"
                reason = f"{symbol} declining ({change:.1f}%)"
            else:
                recommendation = "hold"
                reason = f"{symbol} trading sideways ({change:.1f}%)"
            
            return {
                "recommendation": recommendation,
                "reason": reason,
                "current_price": price,
                "change_percent": change,
                "sector": stock.sector
            }
            
        except Exception as e:
            return {"recommendation": "unknown", "reason": f"Analysis error: {str(e)}"}
    
    def get_market_opportunities(self) -> List[Dict[str, Any]]:
        """Identify potential trading opportunities"""
        try:
            stocks = self.session.query(Stock).filter(
                Stock.priority > 0,
                Stock.last_price.isnot(None)
            ).all()
            
            opportunities = []
            
            for stock in stocks[:5]:  # Top 5 opportunities
                change = stock.change_percent if stock.change_percent is not None else 0
                
                # Look for momentum plays
                if abs(change) > 2:
                    opportunity_type = "momentum" if change > 0 else "reversal"
                    confidence = min(90, 60 + abs(change) * 5)
                    
                    opportunities.append({
                        "symbol": stock.symbol,
                        "name": stock.name,
                        "type": opportunity_type,
                        "reason": f"Strong {'upward' if change > 0 else 'downward'} movement ({change:.1f}%)",
                        "confidence": confidence,
                        "sector": stock.sector,
                        "price": stock.last_price
                    })
            
            return opportunities
            
        except Exception:
            return []
    
    def get_contextual_advice(self, user_id: int, context: str = "") -> Dict[str, Any]:
        """Provide contextual trading advice based on user situation"""
        market_sentiment = self.analyze_market_sentiment()
        portfolio = self.get_portfolio_analysis(user_id)
        opportunities = self.get_market_opportunities()
        
        # Generate contextual advice
        advice_parts = []
        
        # Market sentiment advice
        if market_sentiment == "bullish":
            advice_parts.append("Market sentiment is positive. Consider long positions in strong sectors.")
        elif market_sentiment == "bearish":
            advice_parts.append("Market showing weakness. Consider defensive positions or wait for better entry points.")
        else:
            advice_parts.append("Market is neutral. Focus on individual stock fundamentals.")
        
        # Portfolio-specific advice
        if portfolio["total_positions"] == 0:
            advice_parts.append("Start with small positions in blue-chip stocks to build experience.")
        elif portfolio["risk_level"] == "high":
            advice_parts.append("Consider diversifying across different sectors to reduce risk.")
        
        # Opportunity-based advice
        if opportunities:
            top_opportunity = opportunities[0]
            advice_parts.append(f"Watch {top_opportunity['symbol']} - showing {top_opportunity['type']} potential.")
        
        return {
            "market_sentiment": market_sentiment,
            "portfolio_analysis": portfolio,
            "opportunities": opportunities,
            "advice": " ".join(advice_parts),
            "risk_assessment": self._assess_current_risk(),
            "suggested_actions": self._get_suggested_actions(market_sentiment, portfolio)
        }
    
    def _assess_current_risk(self) -> str:
        """Assess current market risk level"""
        # Simple risk assessment based on market volatility indicators
        risk_factors = []
        
        try:
            stocks = self.session.query(Stock).filter(Stock.priority > 0).all()
            volatility_scores = []
            
            for stock in stocks:
                if stock.change_percent is not None:
                    volatility_scores.append(abs(stock.change_percent))
            
            if volatility_scores:
                avg_volatility = np.mean(volatility_scores)
                if avg_volatility > 3:
                    return "high"
                elif avg_volatility > 1.5:
                    return "moderate"
                else:
                    return "low"
                    
        except Exception:
            pass
            
        return "moderate"
    
    def _get_suggested_actions(self, sentiment: str, portfolio: Dict) -> List[str]:
        """Get specific action suggestions"""
        actions = []
        
        if sentiment == "bullish":
            actions.append("Consider increasing equity exposure")
            actions.append("Look for breakout patterns in tech stocks")
        elif sentiment == "bearish":
            actions.append("Review stop-loss levels")
            actions.append("Consider defensive sectors like utilities")
        
        if portfolio["total_positions"] < 3:
            actions.append("Diversify into at least 3-5 different stocks")
        
        if portfolio["risk_level"] == "high":
            actions.append("Reduce position sizes to manage risk")
        
        return actions
    
    def ask_question(self, question: str, user_id: int) -> str:
        """Process user questions and provide relevant answers"""
        question_lower = question.lower()
        
        # Portfolio questions
        if any(word in question_lower for word in ["portfolio", "positions", "holdings"]):
            portfolio = self.get_portfolio_analysis(user_id)
            return f"Your portfolio has {portfolio['total_positions']} positions with {portfolio['portfolio_health']} diversification. Risk level: {portfolio['risk_level']}."
        
        # Market questions
        elif any(word in question_lower for word in ["market", "sentiment", "outlook"]):
            sentiment = self.analyze_market_sentiment()
            return f"Current market sentiment appears {sentiment}. {self._get_sentiment_explanation(sentiment)}"
        
        # Stock-specific questions
        elif "should i buy" in question_lower or "should i sell" in question_lower:
            # Extract stock symbol if mentioned
            words = question_lower.split()
            stock_symbols = ["aapl", "msft", "googl", "amzn", "tsla", "meta", "nvda", "jpm", "jnj", "v"]
            mentioned_symbol = None
            
            for word in words:
                if word.upper() in [s.upper() for s in stock_symbols]:
                    mentioned_symbol = word.upper()
                    break
            
            if mentioned_symbol:
                rec = self.get_stock_recommendation(mentioned_symbol)
                return f"For {mentioned_symbol}: {rec['recommendation'].replace('_', ' ').title()}. {rec['reason']}"
            else:
                return "Please specify which stock you're asking about. I can analyze AAPL, MSFT, GOOGL, AMZN, TSLA, META, NVDA, JPM, JNJ, or V."
        
        # Risk questions
        elif any(word in question_lower for word in ["risk", "safe", "dangerous"]):
            risk = self._assess_current_risk()
            return f"Current market risk level is {risk}. {self._get_risk_explanation(risk)}"
        
        # General advice
        else:
            advice = self.get_contextual_advice(user_id)
            return advice["advice"]
    
    def _get_sentiment_explanation(self, sentiment: str) -> str:
        """Get explanation for market sentiment"""
        explanations = {
            "bullish": "Most stocks are showing positive movement. Good time for growth strategies.",
            "bearish": "Many stocks are declining. Consider defensive strategies or wait for better entries.",
            "neutral": "Mixed signals in the market. Focus on individual stock analysis."
        }
        return explanations.get(sentiment, "Market conditions are unclear.")
    
    def _get_risk_explanation(self, risk: str) -> str:
        """Get explanation for risk level"""
        explanations = {
            "high": "High volatility detected. Use smaller position sizes and tight stops.",
            "moderate": "Normal market conditions. Standard risk management applies.",
            "low": "Low volatility environment. Consider slightly larger positions if fundamentals support."
        }
        return explanations.get(risk, "Monitor risk levels closely.")