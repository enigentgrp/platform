import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

from database.database import get_session
from database.models import Stock, StockPriceHistory, PriorityCurrentPrice, PriorityArchivePrice
from services.technical_indicators import TechnicalIndicators
from services.broker_apis import BrokerManager

logger = logging.getLogger(__name__)

class DataFetcher:
    """Handles fetching and updating stock market data"""
    
    def __init__(self):
        self.broker_manager = BrokerManager()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def fetch_sp500_symbols(self) -> List[str]:
        """Fetch S&P 500 symbols from a reliable source"""
        try:
            # Using a common approach to get S&P 500 symbols
            sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            tables = pd.read_html(sp500_url)
            sp500_df = tables[0]
            return sp500_df['Symbol'].tolist()
        except Exception as e:
            logger.error(f"Error fetching S&P 500 symbols: {e}")
            # Return a subset of known S&P 500 symbols as fallback
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'JNJ', 'V',
                'WMT', 'PG', 'UNH', 'HD', 'MA', 'BAC', 'DIS', 'ADBE', 'CRM', 'NFLX',
                'KO', 'PEP', 'TMO', 'COST', 'ABT', 'ACN', 'MRK', 'LIN', 'VZ', 'DHR'
            ]
    
    def update_stock_database(self):
        """Update stock database with S&P 500 stocks that have options"""
        session = get_session()
        try:
            sp500_symbols = self.fetch_sp500_symbols()
            
            for symbol in sp500_symbols:
                try:
                    # Check if stock already exists
                    existing_stock = session.query(Stock).filter(Stock.symbol == symbol).first()
                    
                    if not existing_stock:
                        # Fetch stock info
                        ticker = yf.Ticker(symbol)
                        info = ticker.info
                        
                        # Check if options are available
                        has_options = len(ticker.options) > 0 if hasattr(ticker, 'options') else False
                        
                        # Create new stock record
                        stock = Stock(
                            symbol=symbol,
                            name=info.get('longName', symbol),
                            sector=info.get('sector', 'Unknown'),
                            industry=info.get('industry', 'Unknown'),
                            market_cap=info.get('marketCap', 0),
                            has_options=has_options,
                            priority=0
                        )
                        session.add(stock)
                
                except Exception as e:
                    logger.error(f"Error processing stock {symbol}: {e}")
                    continue
            
            session.commit()
            logger.info(f"Updated stock database with {len(sp500_symbols)} symbols")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating stock database: {e}")
        finally:
            session.close()
    
    def update_historical_data(self, days: int = 90):
        """Update historical price data for all stocks"""
        session = get_session()
        try:
            stocks = session.query(Stock).all()
            start_date = datetime.now() - timedelta(days=days)
            
            for stock in stocks:
                try:
                    self._update_stock_historical_data(stock, start_date, session)
                except Exception as e:
                    logger.error(f"Error updating historical data for {stock.symbol}: {e}")
                    continue
            
            session.commit()
            logger.info(f"Updated historical data for {len(stocks)} stocks")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating historical data: {e}")
        finally:
            session.close()
    
    def _update_stock_historical_data(self, stock: Stock, start_date: datetime, session):
        """Update historical data for a single stock"""
        try:
            # Check if we already have recent data
            latest_data = session.query(StockPriceHistory)\
                .filter(StockPriceHistory.stock_id == stock.id)\
                .order_by(StockPriceHistory.date.desc()).first()
            
            if latest_data and latest_data.date.date() >= (datetime.now() - timedelta(days=1)).date():
                return  # Data is up to date
            
            # Fetch data from yfinance
            ticker = yf.Ticker(stock.symbol)
            hist = ticker.history(start=start_date, end=datetime.now())
            
            if hist.empty:
                return
            
            # Calculate technical indicators
            hist_with_indicators = TechnicalIndicators.calculate_all_indicators(hist.reset_index())
            
            # Update database
            for _, row in hist_with_indicators.iterrows():
                if pd.isna(row['Date']):
                    continue
                
                date = pd.to_datetime(row['Date']).to_pydatetime()
                
                # Check if record already exists
                existing = session.query(StockPriceHistory)\
                    .filter(StockPriceHistory.stock_id == stock.id)\
                    .filter(StockPriceHistory.date == date).first()
                
                if existing:
                    continue
                
                price_history = StockPriceHistory(
                    stock_id=stock.id,
                    date=date,
                    open_price=float(row['Open']),
                    high_price=float(row['High']),
                    low_price=float(row['Low']),
                    close_price=float(row['Close']),
                    volume=int(row['Volume']),
                    sma_20=float(row.get('SMA_20', 0)) if pd.notna(row.get('SMA_20')) else None,
                    std_20=float(row.get('STD_20', 0)) if pd.notna(row.get('STD_20')) else None,
                    adx=float(row.get('ADX', 0)) if pd.notna(row.get('ADX')) else None,
                    di_plus=float(row.get('DI_Plus', 0)) if pd.notna(row.get('DI_Plus')) else None,
                    di_minus=float(row.get('DI_Minus', 0)) if pd.notna(row.get('DI_Minus')) else None,
                    pivot_point=float(row.get('Pivot_Point', 0)) if pd.notna(row.get('Pivot_Point')) else None,
                    resistance_1=float(row.get('Resistance_1', 0)) if pd.notna(row.get('Resistance_1')) else None,
                    resistance_2=float(row.get('Resistance_2', 0)) if pd.notna(row.get('Resistance_2')) else None,
                    support_1=float(row.get('Support_1', 0)) if pd.notna(row.get('Support_1')) else None,
                    support_2=float(row.get('Support_2', 0)) if pd.notna(row.get('Support_2')) else None,
                    cci=float(row.get('CCI', 0)) if pd.notna(row.get('CCI')) else None,
                    stoch_k=float(row.get('Stoch_K', 0)) if pd.notna(row.get('Stoch_K')) else None,
                    stoch_d=float(row.get('Stoch_D', 0)) if pd.notna(row.get('Stoch_D')) else None
                )
                session.add(price_history)
        
        except Exception as e:
            logger.error(f"Error updating historical data for {stock.symbol}: {e}")
    
    def update_priority_stocks(self):
        """Update priority stock identification"""
        session = get_session()
        try:
            stocks = session.query(Stock).filter(Stock.has_options == True).all()
            
            for stock in stocks:
                try:
                    # Get recent historical data
                    recent_data = session.query(StockPriceHistory)\
                        .filter(StockPriceHistory.stock_id == stock.id)\
                        .order_by(StockPriceHistory.date.desc())\
                        .limit(30).all()
                    
                    if len(recent_data) < 20:
                        continue
                    
                    # Convert to DataFrame
                    df = pd.DataFrame([{
                        'Date': r.date,
                        'Open': r.open_price,
                        'High': r.high_price,
                        'Low': r.low_price,
                        'Close': r.close_price,
                        'Volume': r.volume
                    } for r in reversed(recent_data)])
                    
                    # Check if stock should be priority
                    is_priority = TechnicalIndicators.identify_priority_stocks(df, stock.symbol)
                    
                    # Update priority
                    stock.priority = 1 if is_priority else 0
                    
                    # Update last price
                    if recent_data:
                        stock.last_price = recent_data[0].close_price
                
                except Exception as e:
                    logger.error(f"Error updating priority for {stock.symbol}: {e}")
                    continue
            
            session.commit()
            
            priority_count = session.query(Stock).filter(Stock.priority > 0).count()
            logger.info(f"Updated priority stocks. {priority_count} stocks marked as priority")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating priority stocks: {e}")
        finally:
            session.close()
    
    def archive_priority_prices(self, retention_days: int = 30):
        """Archive old priority price data"""
        session = get_session()
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Move old records to archive
            old_records = session.query(PriorityCurrentPrice)\
                .filter(PriorityCurrentPrice.datetime < cutoff_date).all()
            
            for record in old_records:
                archive_record = PriorityArchivePrice(
                    stock_id=record.stock_id,
                    datetime=record.datetime,
                    open_price=record.open_price,
                    current_price=record.current_price,
                    percent_change=record.percent_change,
                    volume=record.volume
                )
                session.add(archive_record)
                session.delete(record)
            
            session.commit()
            logger.info(f"Archived {len(old_records)} priority price records")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error archiving priority prices: {e}")
        finally:
            session.close()
    
    async def run_daily_update(self):
        """Run complete daily data update"""
        logger.info("Starting daily data update...")
        
        try:
            # Update stock database with new S&P 500 stocks
            self.update_stock_database()
            
            # Update historical data
            self.update_historical_data()
            
            # Update priority stock identification
            self.update_priority_stocks()
            
            # Archive old priority price data
            self.archive_priority_prices()
            
            logger.info("Daily data update completed successfully")
        
        except Exception as e:
            logger.error(f"Error in daily data update: {e}")
    
    def get_real_time_data(self, symbols: List[str]) -> Dict:
        """Get real-time market data for symbols"""
        try:
            return self.broker_manager.get_market_data(symbols)
        except Exception as e:
            logger.error(f"Error getting real-time data: {e}")
            return {}
    
    def update_current_prices(self):
        """Update current prices for all priority stocks"""
        session = get_session()
        try:
            priority_stocks = session.query(Stock).filter(Stock.priority > 0).all()
            
            if not priority_stocks:
                return
            
            symbols = [stock.symbol for stock in priority_stocks]
            market_data = self.get_real_time_data(symbols)
            
            for stock in priority_stocks:
                if stock.symbol in market_data:
                    data = market_data[stock.symbol]
                    
                    # Update stock current price
                    stock.last_price = data['price']
                    stock.change_percent = data.get('change_percent', 0)
                    
            session.commit()
            logger.info(f"Updated current prices for {len(priority_stocks)} priority stocks")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating current prices: {e}")
        finally:
            session.close()
