import os
from datetime import timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()                 # loads .env from CWD; pass a path if needed
except Exception:
    pass

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# change symbol if you like (AAPL, XLK, etc.)
SYMBOL = os.getenv("TEST_SYMBOL", "XLK")
NOTIONAL = float(os.getenv("TEST_NOTIONAL", "10"))

tc = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)
o = tc.submit_order(MarketOrderRequest(
    symbol=SYMBOL,
    notional=round(NOTIONAL, 2),
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY
))
print("Submitted order:", o.id, SYMBOL, NOTIONAL)
