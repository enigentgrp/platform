#!/usr/bin/env python3
"""
Test script to verify Alpaca paper trading connection
"""
import os
# Load env FIRST
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
# Now import modules that may read env
from services.broker_apis import AlpacaAPI, BrokerManager

def test_alpaca_connection():
    """Test the Alpaca API connection"""
    print("Testing Alpaca Paper Trading Connection...")
    print("=" * 50)
    
    # Check environment variables
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    print(f"API Key present: {'Yes' if api_key else 'No'}")
    print(f"Secret Key present: {'Yes' if secret_key else 'No'}")
    
    if not api_key or not secret_key:
        print("\n❌ Missing Alpaca API credentials!")
        return False
    
    # Test direct Alpaca API
    print("\n1. Testing direct Alpaca API...")
    alpaca = AlpacaAPI(paper_trading=True)
    
    # Test authentication
    auth_result = alpaca.authenticate()
    print(f"Authentication: {'✅ Success' if auth_result else '❌ Failed'}")
    
    if not auth_result:
        return False
    
    # Test account info
    print("\n2. Testing account information...")
    account_info = alpaca.get_account_info()
    if 'error' not in account_info:
        print("✅ Account info retrieved successfully:")
        print(f"   Account: {account_info.get('account_number', 'N/A')}")
        print(f"   Cash: ${account_info.get('cash', 0):,.2f}")
        print(f"   Portfolio Value: ${account_info.get('portfolio_value', 0):,.2f}")
        print(f"   Buying Power: ${account_info.get('buying_power', 0):,.2f}")
    else:
        print(f"❌ Account info error: {account_info['error']}")
        return False
    
    # Test positions
    print("\n3. Testing positions...")
    positions = alpaca.get_positions()
    print(f"✅ Retrieved {len(positions)} positions")
    
    # Test market data
    print("\n4. Testing market data...")
    market_data = alpaca.get_market_data(['AAPL', 'TSLA'])
    if market_data:
        print("✅ Market data retrieved:")
        for symbol, data in market_data.items():
            print(f"   {symbol}: ${data.get('price', 0):.2f}")
    
    # Test via BrokerManager
    print("\n5. Testing via BrokerManager...")
    broker_manager = BrokerManager()
    broker_manager.set_active_broker('alpaca')
    
    manager_account = broker_manager.get_account_info()
    if 'error' not in manager_account:
        print("✅ BrokerManager working correctly")
    else:
        print(f"❌ BrokerManager error: {manager_account['error']}")
        return False
    
    print("\n🎉 All tests passed! Alpaca paper trading is ready.")
    return True

if __name__ == "__main__":
    test_alpaca_connection()
