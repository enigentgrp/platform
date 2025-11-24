#!/usr/bin/env python3
"""
Simple Alpaca paper-trading loop example.
Fetches latest minute prices, generates a basic buy/sell signal,
and submits market orders accordingly.
"""

import os
from dotenv import load_dotenv
load_dotenv()
import time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Load keys from environment
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
if not API_KEY or not SECRET_KEY:
    raise SystemExit("❌ Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in environment!")

# Initialize Alpaca clients
trade = TradingClient(API_KEY, SECRET_KEY, paper=True)
data = StockHistoricalDataClient(API_KEY, SECRET_KEY)

def fetch_data(symbol: str):
    """Fetch last 2 minutes of bar data."""
    bars = data.get_stock_bars(
        StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame.Minute, limit=2)
    ).df
    if bars is None or bars.empty:
        return None
    bars = bars.reset_index()
    return bars

def signal_logic(df):
    """Simple buy/sell/hold rule."""
    if len(df) < 2:
        return "hold"
    last = df.iloc[-1]["close"]
    prev = df.iloc[-2]["close"]
    if last > prev * 1.01:
        return "buy"
    elif last < prev * 0.99:
        return "sell"
    return "hold"

def place_order(symbol: str, action: str):
    """Submit a small market order ($5 worth)."""
    try:
        order_req = MarketOrderRequest(
            symbol=symbol,
            notional=5.0,  # buy/sell ~$5
            side=OrderSide.BUY if action == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = trade.submit_order(order_req)
        print(f"✅ {action.upper()} order submitted: {order.id}")
    except Exception as e:
        print(f"❌ Order failed: {e}")

def main_loop():
    symbol = "AAPL"
    print(f"Starting simple trading loop for {symbol}...")
    while True:
        try:
            df = fetch_data(symbol)
            if df is None:
                print("No data retrieved; retrying...")
                time.sleep(60)
                continue

            action = signal_logic(df)
            last_price = df.iloc[-1]['close']
            print(f"{symbol} last price: {last_price:.2f} → Signal: {action}")

            if action in ("buy", "sell"):
                place_order(symbol, action)

            time.sleep(60)  # wait 1 minute
        except KeyboardInterrupt:
            print("\nLoop stopped by user.")
            break
        except Exception as e:
            print("Loop error:", e)
            time.sleep(30)

if __name__ == "__main__":
    main_loop()
