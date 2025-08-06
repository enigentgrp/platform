import os
import requests
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

class BrokerAPI(ABC):
    """Abstract base class for broker API implementations"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv('BROKER_API_KEY')
        self.api_secret = api_secret or os.getenv('BROKER_API_SECRET')
        self.base_url = base_url
        self.session = requests.Session()
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the broker API"""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict:
        """Get account information"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        pass
    
    @abstractmethod
    def place_order(self, symbol: str, side: str, quantity: int, order_type: str = 'market', 
                   price: float = None, stop_price: float = None) -> Dict:
        """Place a trading order"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_market_data(self, symbols: List[str]) -> Dict:
        """Get real-time market data"""
        pass
    
    @abstractmethod
    def get_historical_data(self, symbol: str, timeframe: str = '1D', 
                          start_date: datetime = None, end_date: datetime = None) -> pd.DataFrame:
        """Get historical price data"""
        pass

class AlpacaAPI(BrokerAPI):
    """Alpaca Markets API implementation"""
    
    def __init__(self, paper_trading: bool = True):
        self.paper_trading = paper_trading
        if paper_trading:
            base_url = 'https://paper-api.alpaca.markets'
            data_url = 'https://data.alpaca.markets'
        else:
            base_url = 'https://api.alpaca.markets'
            data_url = 'https://data.alpaca.markets'
        
        # Use Alpaca-specific environment variables
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_SECRET_KEY')
        
        super().__init__(api_key=api_key, api_secret=api_secret, base_url=base_url)
        self.data_url = data_url
        self.authenticated = False
    
    def authenticate(self) -> bool:
        """Authenticate with Alpaca API"""
        try:
            if not self.api_key or not self.api_secret:
                print("Alpaca API keys not found in environment variables")
                return False
            
            headers = {
                'APCA-API-KEY-ID': self.api_key,
                'APCA-API-SECRET-KEY': self.api_secret
            }
            
            response = self.session.get(f'{self.base_url}/v2/account', headers=headers)
            if response.status_code == 200:
                self.session.headers.update(headers)
                self.authenticated = True
                print(f"Successfully authenticated with Alpaca {'Paper Trading' if self.paper_trading else 'Live Trading'}")
                return True
            else:
                print(f"Alpaca authentication failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error authenticating with Alpaca: {e}")
            return False
    
    def get_account_info(self) -> Dict:
        """Get Alpaca account information"""
        if not self.authenticated:
            return {'error': 'Not authenticated with Alpaca'}
        
        try:
            response = self.session.get(f'{self.base_url}/v2/account')
            if response.status_code == 200:
                data = response.json()
                return {
                    'account_number': data.get('account_number'),
                    'cash': float(data.get('cash', 0)),
                    'portfolio_value': float(data.get('portfolio_value', 0)),
                    'buying_power': float(data.get('buying_power', 0)),
                    'day_trade_count': int(data.get('daytrade_count', 0))
                }
        except Exception as e:
            print(f"Error getting account info: {e}")
        
        return {'error': 'Failed to retrieve account information'}
    
    def get_positions(self) -> List[Dict]:
        """Get current positions from Alpaca"""
        if not self.authenticated:
            return []
        
        try:
            response = self.session.get(f'{self.base_url}/v2/positions')
            if response.status_code == 200:
                positions = response.json()
                return [
                    {
                        'symbol': pos['symbol'],
                        'quantity': int(pos['qty']),
                        'market_value': float(pos['market_value']),
                        'cost_basis': float(pos['cost_basis']),
                        'unrealized_pnl': float(pos.get('unrealized_pnl', 0)),
                        'side': 'long' if int(pos['qty']) > 0 else 'short'
                    }
                    for pos in positions
                ]
        except Exception as e:
            print(f"Error getting positions: {e}")
        
        return []
    
    def place_order(self, symbol: str, side: str, quantity: int, order_type: str = 'market',
                   price: float = None, stop_price: float = None) -> Dict:
        """Place order with Alpaca"""
        if not self.authenticated:
            return {'error': 'Not authenticated with Alpaca'}
        
        order_data = {
            'symbol': symbol,
            'qty': quantity,
            'side': side,
            'type': order_type,
            'time_in_force': 'day'
        }
        
        if order_type == 'limit' and price:
            order_data['limit_price'] = price
        elif order_type == 'stop' and stop_price:
            order_data['stop_price'] = stop_price
        
        try:
            response = self.session.post(f'{self.base_url}/v2/orders', json=order_data)
            if response.status_code == 201:
                return response.json()
        except Exception as e:
            print(f"Error placing order: {e}")
        
        return {'error': 'Failed to place order'}
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status from Alpaca"""
        if not self.authenticated or order_id.startswith('mock_'):
            return {'id': order_id, 'status': 'filled'}
        
        try:
            response = self.session.get(f'{self.base_url}/v2/orders/{order_id}')
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting order status: {e}")
        
        return {'error': 'Failed to get order status'}
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order with Alpaca"""
        if not self.authenticated or order_id.startswith('mock_'):
            return True
        
        try:
            response = self.session.delete(f'{self.base_url}/v2/orders/{order_id}')
            return response.status_code == 204
        except Exception as e:
            print(f"Error cancelling order: {e}")
            return False
    
    def get_market_data(self, symbols: List[str]) -> Dict:
        """Get real-time market data using yfinance as fallback"""
        market_data = {}
        
        try:
            # Use yfinance for market data
            tickers = yf.Tickers(' '.join(symbols))
            for symbol in symbols:
                try:
                    ticker = tickers.tickers[symbol]
                    info = ticker.info
                    hist = ticker.history(period='1d', interval='1m')
                    
                    if not hist.empty:
                        latest = hist.iloc[-1]
                        market_data[symbol] = {
                            'price': float(latest['Close']),
                            'high': float(latest['High']),
                            'low': float(latest['Low']),
                            'volume': int(latest['Volume']),
                            'change_percent': ((float(latest['Close']) - float(hist.iloc[0]['Open'])) / float(hist.iloc[0]['Open'])) * 100
                        }
                except Exception:
                    # Fallback to basic info
                    market_data[symbol] = {
                        'price': 100.0,
                        'high': 102.0,
                        'low': 98.0,
                        'volume': 1000000,
                        'change_percent': 0.5
                    }
        except Exception as e:
            print(f"Error getting market data: {e}")
        
        return market_data
    
    def get_historical_data(self, symbol: str, timeframe: str = '1D',
                          start_date: datetime = None, end_date: datetime = None) -> pd.DataFrame:
        """Get historical data using yfinance"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=90)
            if not end_date:
                end_date = datetime.now()
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            
            if not hist.empty:
                hist.reset_index(inplace=True)
                hist.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
                return hist[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            
        except Exception as e:
            print(f"Error getting historical data for {symbol}: {e}")
        
        return pd.DataFrame()

class RobinhoodAPI(BrokerAPI):
    """Robinhood API implementation (mock for development)"""
    
    def __init__(self):
        super().__init__(base_url='https://robinhood.com/api')
        self.authenticated = False
    
    def authenticate(self) -> bool:
        """Mock authentication for Robinhood"""
        self.authenticated = True
        return True
    
    def get_account_info(self) -> Dict:
        """Mock account info for Robinhood"""
        return {
            'account_number': 'RH_MOCK_ACCOUNT',
            'cash': 50000.0,
            'portfolio_value': 50000.0,
            'buying_power': 50000.0,
            'day_trade_count': 0
        }
    
    def get_positions(self) -> List[Dict]:
        """Mock positions for Robinhood"""
        return []
    
    def place_order(self, symbol: str, side: str, quantity: int, order_type: str = 'market',
                   price: float = None, stop_price: float = None) -> Dict:
        """Mock order placement for Robinhood"""
        return {
            'id': f'rh_mock_order_{datetime.now().timestamp()}',
            'status': 'filled',
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'filled_price': price or 100.0
        }
    
    def get_order_status(self, order_id: str) -> Dict:
        """Mock order status for Robinhood"""
        return {'id': order_id, 'status': 'filled'}
    
    def cancel_order(self, order_id: str) -> bool:
        """Mock order cancellation for Robinhood"""
        return True
    
    def get_market_data(self, symbols: List[str]) -> Dict:
        """Mock market data for Robinhood"""
        return {symbol: {'price': 100.0, 'change_percent': 0.5} for symbol in symbols}
    
    def get_historical_data(self, symbol: str, timeframe: str = '1D',
                          start_date: datetime = None, end_date: datetime = None) -> pd.DataFrame:
        """Mock historical data for Robinhood"""
        return pd.DataFrame()

class TradierAPI(BrokerAPI):
    """Tradier API implementation (mock for development)"""
    
    def __init__(self, sandbox: bool = True):
        self.sandbox = sandbox
        base_url = 'https://sandbox.tradier.com' if sandbox else 'https://api.tradier.com'
        super().__init__(base_url=base_url)
        self.authenticated = False
    
    def authenticate(self) -> bool:
        """Mock authentication for Tradier"""
        self.authenticated = True
        print("Successfully authenticated with Tradier (Mock)")
        return True
    
    def get_account_info(self) -> Dict:
        """Mock account info for Tradier"""
        return {
            'account_number': 'TRADIER_MOCK_ACCOUNT',
            'cash': 75000.0,
            'portfolio_value': 75000.0,
            'buying_power': 75000.0,
            'day_trade_count': 0
        }
    
    def get_positions(self) -> List[Dict]:
        """Mock positions for Tradier"""
        return []
    
    def place_order(self, symbol: str, side: str, quantity: int, order_type: str = 'market',
                   price: float = None, stop_price: float = None) -> Dict:
        """Mock order placement for Tradier"""
        return {
            'id': f'tradier_mock_order_{datetime.now().timestamp()}',
            'status': 'filled',
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'filled_price': price or 100.0
        }
    
    def get_order_status(self, order_id: str) -> Dict:
        """Mock order status for Tradier"""
        return {'id': order_id, 'status': 'filled'}
    
    def cancel_order(self, order_id: str) -> bool:
        """Mock order cancellation for Tradier"""
        return True
    
    def get_market_data(self, symbols: List[str]) -> Dict:
        """Mock market data for Tradier"""
        return {symbol: {'price': 100.0, 'change_percent': 0.5} for symbol in symbols}
    
    def get_historical_data(self, symbol: str, timeframe: str = '1D',
                          start_date: datetime = None, end_date: datetime = None) -> pd.DataFrame:
        """Mock historical data for Tradier"""
        return pd.DataFrame()

class BrokerManager:
    """Manager class to handle multiple broker APIs with dynamic configuration"""
    
    def __init__(self):
        self.brokers = {
            'alpaca_paper': AlpacaAPI(paper_trading=True),
            'alpaca_live': AlpacaAPI(paper_trading=False),
            'robinhood': RobinhoodAPI(),
            'tradier_paper': TradierAPI(sandbox=True),
            'tradier_live': TradierAPI(sandbox=False)
        }
        self.active_broker = self._get_broker_from_env()
        self._authenticate_active_broker()
    
    def _get_broker_from_env(self) -> str:
        """Get active broker from environment variables or database"""
        from database.database import get_session
        from database.models import EnvironmentVariable
        
        try:
            session = get_session()
            trading_mode = session.query(EnvironmentVariable)\
                .filter(EnvironmentVariable.key == 'TRADING_MODE').first()
            active_broker = session.query(EnvironmentVariable)\
                .filter(EnvironmentVariable.key == 'ACTIVE_BROKER').first()
            
            mode = trading_mode.value if trading_mode else 'paper'
            broker_base = active_broker.value if active_broker else 'alpaca'
            
            # Map broker names to internal broker keys
            if broker_base == 'alpaca':
                broker = 'alpaca_paper' if mode == 'paper' else 'alpaca_live'
            elif broker_base == 'robinhood':
                broker = 'robinhood'
            elif broker_base == 'tradier':
                broker = 'tradier_paper' if mode == 'paper' else 'tradier_live'
            else:
                broker = 'alpaca_paper'  # Default
            
            session.close()
            return broker
        except Exception:
            return 'alpaca_paper'  # Default fallback
    
    def _authenticate_active_broker(self):
        """Authenticate with the currently active broker"""
        if self.active_broker in self.brokers:
            self.brokers[self.active_broker].authenticate()
    
    def get_active_broker_name(self) -> str:
        """Get the name of the currently active broker"""
        return self.active_broker
    
    def switch_broker(self, broker_name: str) -> bool:
        """Switch to a different broker and authenticate"""
        if broker_name in self.brokers:
            self.active_broker = broker_name
            self._authenticate_active_broker()
            return True
        return False
    
    def reload_configuration(self):
        """Reload broker configuration from database"""
        self.active_broker = self._get_broker_from_env()
        self._authenticate_active_broker()
    
    def set_active_broker(self, broker_name: str):
        """Set the active broker"""
        if broker_name in self.brokers:
            self.active_broker = broker_name
            return True
        return False
    
    def get_active_broker(self) -> BrokerAPI:
        """Get the currently active broker API"""
        return self.brokers[self.active_broker]
    
    def authenticate_all(self):
        """Authenticate with all broker APIs"""
        results = {}
        for name, broker in self.brokers.items():
            results[name] = broker.authenticate()
        return results
    
    # Delegate methods to active broker
    def get_account_info(self) -> Dict:
        return self.get_active_broker().get_account_info()
    
    def get_positions(self) -> List[Dict]:
        return self.get_active_broker().get_positions()
    
    def place_order(self, symbol: str, side: str, quantity: int, order_type: str = 'market',
                   price: float = None, stop_price: float = None) -> Dict:
        return self.get_active_broker().place_order(symbol, side, quantity, order_type, price, stop_price)
    
    def get_order_status(self, order_id: str) -> Dict:
        return self.get_active_broker().get_order_status(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        return self.get_active_broker().cancel_order(order_id)
    
    def get_market_data(self, symbols: List[str]) -> Dict:
        return self.get_active_broker().get_market_data(symbols)
    
    def get_historical_data(self, symbol: str, timeframe: str = '1D',
                          start_date: datetime = None, end_date: datetime = None) -> pd.DataFrame:
        return self.get_active_broker().get_historical_data(symbol, timeframe, start_date, end_date)
