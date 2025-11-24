#!/usr/bin/env python3
"""
tes_alpacca.py
Test script to verify Alpaca paper trading connection end-to-end.
- Validates env vars
- Authenticates
- Reads account info
- Reads positions (handles fractional qty safely)
- Fetches simple market data
- Tests through BrokerManager
Exits with code 0 on success, 1 on failure.
"""
import os
import sys
from decimal import Decimal, InvalidOperation

# Load env FIRST
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Now import modules that may read env
from services.broker_apis import AlpacaAPI, BrokerManager


# ---------- Helpers ----------
def to_decimal(x, default=Decimal("0")):
    if x is None or x == "":
        return default
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        return default

def money(x):
    d = to_decimal(x)
    # Normalize for pretty printing like 100,123.45
    return f"${d.quantize(Decimal('0.01')):,.2f}"

def ok(flag):
    return "✅ Success" if flag else "❌ Failed"


# ---------- Tests ----------
def test_alpaca_connection():
    print("Testing Alpaca Paper Trading Connection...")
    print("=" * 60)

    # 0) Env
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    print(f"API Key present: {'Yes' if api_key else 'No'}")
    print(f"Secret Key present: {'Yes' if secret_key else 'No'}")
    if not api_key or not secret_key:
        print("\n❌ Missing Alpaca API credentials!")
        return False

    # 1) Direct Alpaca API
    print("\n1) Testing direct Alpaca API...")
    alpaca = AlpacaAPI(paper_trading=True)
    auth_result = alpaca.authenticate()
    print(f"Authentication: {ok(auth_result)}")
    if not auth_result:
        return False

    # 2) Account info
    print("\n2) Testing account information...")
    account_info = alpaca.get_account_info()
    if isinstance(account_info, dict) and "error" in account_info:
        print(f"❌ Account info error: {account_info['error']}")
        return False

    acct = account_info or {}
    print("✅ Account info retrieved successfully:")
    print(f"   Account: {acct.get('account_number', 'N/A')}")
    print(f"   Cash: {money(acct.get('cash', 0))}")
    print(f"   Portfolio Value: {money(acct.get('portfolio_value', 0))}")
    print(f"   Buying Power: {money(acct.get('buying_power', 0))}")

    # 3) Positions
    print("\n3) Testing positions...")
    try:
        positions = alpaca.get_positions()
    except Exception as e:
        print(f"❌ get_positions raised an exception: {e}")
        return False

    if isinstance(positions, dict) and "error" in positions:
        print(f"❌ Positions error: {positions['error']}")
        return False

    positions = positions or []
    print(f"✅ Retrieved {len(positions)} positions")
    # Preview up to first 10 positions without assuming ints
    for pos in positions[:10]:
        sym = pos.get("symbol", "???")
        qty = to_decimal(pos.get("qty"))
        price = to_decimal(pos.get("current_price"))
        mv = to_decimal(pos.get("market_value"))
        side = pos.get("side", "")
        print(f"   {sym}: qty={qty} {side} @ {money(price)} (mv {money(mv)})")

    # 4) Market data
    print("\n4) Testing market data...")
    try:
        market_data = alpaca.get_market_data(["AAPL", "TSLA"])
    except Exception as e:
        print(f"❌ Market data error: {e}")
        return False

    if not market_data:
        print("❌ No market data returned.")
        return False

    print("✅ Market data retrieved:")
    for symbol, data in market_data.items():
        price = to_decimal((data or {}).get("price", 0))
        print(f"   {symbol}: {money(price)}")

    # 5) Via BrokerManager
    print("\n5) Testing via BrokerManager...")
    try:
        broker_manager = BrokerManager()
        broker_manager.set_active_broker("alpaca")
        manager_account = broker_manager.get_account_info()
    except Exception as e:
        print(f"❌ BrokerManager exception: {e}")
        return False

    if isinstance(manager_account, dict) and "error" in manager_account:
        print(f"❌ BrokerManager error: {manager_account['error']}")
        return False

    print("✅ BrokerManager working correctly")

    print("\n🎉 All tests passed! Alpaca paper trading is ready.")
    return True


if __name__ == "__main__":
    success = test_alpaca_connection()
    sys.exit(0 if success else 1)
