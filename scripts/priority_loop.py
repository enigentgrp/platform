#!/usr/bin/env python3
import os, time, psycopg2
import psycopg2.extras as pgx
from datetime import datetime, timezone
from dotenv import load_dotenv

from alpaca.data.live import StockDataStream  # websocket if you want live ticks
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockQuotesRequest, StockLatestQuoteRequest

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
SEC = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")

def evar(conn, key, default):
  with conn.cursor() as cur:
    cur.execute("SELECT COALESCE(value_num, NULL), COALESCE(value_text, NULL), COALESCE(value_bool, NULL) FROM env_globals WHERE key=%s", (key,))
    r = cur.fetchone()
  if not r: return default
  num, txt, boo = r
  return num if num is not None else (txt if txt is not None else (boo if boo is not None else default))

def get_priority_symbols(conn):
  with conn.cursor() as cur:
    cur.execute("SELECT symbol FROM stock_demographics WHERE priority>0")
    return [r[0] for r in cur.fetchall()]

def insert_tick(conn, sym, open_px, last_px):
  pct = None
  if open_px and last_px:
    try: pct = (last_px/open_px - 1.0)
    except ZeroDivisionError: pct = None
  with conn.cursor() as cur:
    cur.execute("""
      INSERT INTO priority_current_price(symbol, ts, price_open, price_last, pct_change, source)
      VALUES (%s, now(), %s, %s, %s, 'alpaca/iex')
      ON CONFLICT (symbol, ts) DO NOTHING;
    """, (sym, open_px, last_px, pct))
  conn.commit()

def main():
  conn = psycopg2.connect(DB_URL)
  interval = int(evar(conn, 'PRICE_CHECK_INTERVAL_SEC', 5))
  print(f"Looping every {interval}s on priority>0…")

  hist = StockHistoricalDataClient(KEY, SEC)
  # cache today's open per symbol (naive: latest previous close for demo)
  opens = {}

  while True:
    syms = get_priority_symbols(conn)
    if not syms:
      time.sleep(interval); continue

    # Pull latest NBBO/quote per symbol (one by one for simplicity; batch if you want)
    for s in syms:
      try:
        q = hist.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=s))
        qd = q[s]
        last_px = float(qd.ask_price or qd.bid_price or 0)
        if s not in opens:
          # simple open proxy: use last trade/prev close; refine as needed
          opens[s] = last_px
        insert_tick(conn, s, opens[s], last_px)
      except Exception as e:
        # swallow and continue
        pass
      time.sleep(0.05)
    time.sleep(interval)

if __name__ == "__main__":
  main()
