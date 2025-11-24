#!/usr/bin/env python3
import os, time, signal
from collections import deque
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import psycopg2, psycopg2.extras as pgx

# Alpaca (paper trading)
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

# ---------------------------
# Robust .env loading
# ---------------------------
ROOT = Path(__file__).resolve().parents[1]   # .../AlgoTrade
ENV_PATH = ROOT / ".env"
if not ENV_PATH.exists():
    raise SystemExit(f".env not found at {ENV_PATH}")
load_dotenv(dotenv_path=str(ENV_PATH))

DB_URL = os.getenv("DATABASE_URL")
KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
SEC = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")

# Strategy knobs
BUY_PCT_OF_CASH   = float(os.getenv("BUY_PCT_OF_CASH",   "0.25"))
STOP_LOSS_PCT     = float(os.getenv("STOP_LOSS_PCT",     "0.015"))
TAKE_PROFIT_PCT   = float(os.getenv("TAKE_PROFIT_PCT",   "0.03"))
TICK_INTERVAL_SEC = float(os.getenv("TICK_INTERVAL_SEC", "5"))
EOD_CUTOFF_HHMM   = os.getenv("EOD_CUTOFF_HHMM", "15:45")
MIN_CASH_USD      = float(os.getenv("MIN_CASH_USD",      "100"))
MIN_PRICE_USD     = float(os.getenv("MIN_PRICE_USD",     "2"))
MAX_OPEN_POSITIONS= int(os.getenv("MAX_OPEN_POSITIONS",  "10"))

# Demo trade toggles (optional)
ENABLE_TEST_DEMO  = os.getenv("ENABLE_TEST_DEMO", "false").lower() == "true"
TEST_SYMBOL       = os.getenv("TEST_SYMBOL", "XLK")
TEST_NOTIONAL     = float(os.getenv("TEST_NOTIONAL", "10"))
TEST_HOLD_SEC     = int(os.getenv("TEST_HOLD_SEC", "15"))

if not all([DB_URL, KEY, SEC]):
    raise SystemExit("Missing DATABASE_URL / ALPACA_API_KEY / ALPACA_SECRET_KEY in .env")

# ---------------------------
# Connections
# ---------------------------
conn = psycopg2.connect(DB_URL)
conn.autocommit = True
trade = TradingClient(KEY, SEC, paper=True)
data_client = StockHistoricalDataClient(KEY, SEC)

# ---------------------------
# In-memory state
# ---------------------------
N_CONSEC = 2
window = {}
N_WINDOW = 5

# ---------------------------
# Helpers
# ---------------------------
def is_eod_now():
    now_ct = datetime.now()  # Chromebook local time ~ America/Chicago
    return now_ct.strftime("%H:%M") >= EOD_CUTOFF_HHMM

def get_priority_symbols():
    # watch only real priority stocks (exclude sector ETFs priority=9)
    with conn.cursor() as cur:
        cur.execute("SELECT symbol FROM stock_demographics WHERE priority = 1")
        return [r[0] for r in cur.fetchall()]

def latest_trade_price(sym):
    t = data_client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=sym))[sym]
    return float(getattr(t, "price", None) or 0) or None

def get_cash_and_positions():
    acct = trade.get_account()
    cash = float(acct.cash) if acct.cash is not None else 0.0
    pos = {p.symbol: p for p in trade.get_all_positions()}  # keep full model
    return cash, pos

def log_order(symbol, side, qty, limit_price, broker_order_id, status, meta=None):
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO orders(account_id, symbol, asset_type, side, qty, limit_price, status, broker_order_id, submitted_at, meta)
        VALUES (NULL, %s, 'stock', %s, %s, %s, %s, %s, now(), %s)
        RETURNING id;
        """, (symbol, side, qty, limit_price, status, broker_order_id, pgx.Json(meta or {})))
        return cur.fetchone()[0]

def buy_market_notional(symbol, notional, last_px=None, note="entry"):
    # For notional orders, qty is unknown until filled → log qty=None (allowed after SQL change)
    req = MarketOrderRequest(
        symbol=symbol,
        notional=round(max(0.0, notional), 2),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.SIMPLE
    )
    o = trade.submit_order(req)
    log_order(symbol, "buy", None, None, o.id, o.status, meta={"type": note, "last_px": last_px, "notional": notional})
    print(f"BUY submitted {symbol} notional=${notional:.2f} id={o.id}")
    return o

def sell_market_all(symbol, note="exit", pos_map=None):
    """Close entire position (market) using percentage=100 AND log the known qty if we have it."""
    try:
        if pos_map is None:
            _, pos_map = get_cash_and_positions()
        qty_for_log = None
        if symbol in pos_map:
            # Alpaca model stores qty as string; convert to float for your DB
            try:
                qty_for_log = float(pos_map[symbol].qty)
            except Exception:
                qty_for_log = None

        o = trade.close_position(symbol, ClosePositionRequest(percentage="100"))
        broker_id = getattr(o, "id", None) or getattr(o, "order_id", None) or "close_position"
        log_order(symbol, "sell", qty_for_log, None, str(broker_id), "submitted", meta={"type": note})
        print(f"SELL submitted {symbol} (close 100%, qty_for_log={qty_for_log})")
        return True
    except Exception as e:
        print(f"SELL error {symbol}: {e}")
        return False

def check_reversal_signal(sym, last_px):
    dq = window.setdefault(sym, deque(maxlen=N_WINDOW))
    if last_px is None:
        return False
    dq.append(last_px)
    if len(dq) < N_CONSEC + 1:
        return False
    moves = []
    for a, b in zip(list(dq)[:-1], list(dq)[1:]):
        moves.append(1 if b > a else (-1 if b < a else 0))
    if len(moves) < N_CONSEC + 1:
        return False
    last_move = moves[-1]
    prev_block = moves[-(N_CONSEC+1):-1]
    if all(m == 1 for m in prev_block) and last_move == -1:
        return True
    if all(m == -1 for m in prev_block) and last_move == 1:
        return True
    return False

running = True
def handle_sigint(sig, frame):
    global running
    running = False
signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)

def run_demo_trade_once():
    if not ENABLE_TEST_DEMO:
        return
    try:
        print(f"[DEMO] Placing ${TEST_NOTIONAL:.2f} BUY on {TEST_SYMBOL} …")
        buy_market_notional(TEST_SYMBOL, TEST_NOTIONAL, note="demo_entry")
        time.sleep(max(3, TEST_HOLD_SEC))
        print(f"[DEMO] Closing {TEST_SYMBOL} position …")
        # refresh pos map to capture qty for logging
        _, pos_map = get_cash_and_positions()
        sell_market_all(TEST_SYMBOL, note="demo_exit", pos_map=pos_map)
        print("[DEMO] Done.")
    except Exception as e:
        print("[DEMO] Failed:", e)

def main():
    print("Trading engine (paper, long-only, stocks) started.")
    run_demo_trade_once()

    while running:
        try:
            if is_eod_now():
                print("[EOD] Liquidating all open positions…")
                _, positions = get_cash_and_positions()
                for sym in list(positions.keys()):
                    sell_market_all(sym, note="eod_exit", pos_map=positions)
                    time.sleep(0.1)
                print("[EOD] Done. Sleeping.")
                time.sleep(30)
                continue

            syms = get_priority_symbols()
            cash, positions = get_cash_and_positions()

            if cash < MIN_CASH_USD or len(positions) >= MAX_OPEN_POSITIONS:
                time.sleep(TICK_INTERVAL_SEC); continue

            for s in syms:
                last_px = latest_trade_price(s)
                if last_px is None or last_px < MIN_PRICE_USD:
                    continue

                have_pos = s in positions and float(positions[s].qty) > 0.0

                if not have_pos and check_reversal_signal(s, last_px):
                    notional = cash * BUY_PCT_OF_CASH
                    buy_market_notional(s, notional, last_px, note="entry")

                elif have_pos:
                    base = (window.get(s) or [last_px])[0]
                    if base:
                        if last_px >= base * (1.0 + TAKE_PROFIT_PCT):
                            sell_market_all(s, note="tp", pos_map=positions)
                        elif last_px <= base * (1.0 - STOP_LOSS_PCT):
                            sell_market_all(s, note="sl", pos_map=positions)

                time.sleep(0.02)

            time.sleep(TICK_INTERVAL_SEC)

        except Exception as e:
            print("Loop error:", e)
            time.sleep(TICK_INTERVAL_SEC)

    print("Trading engine stopped.")

if __name__ == "__main__":
    main()
