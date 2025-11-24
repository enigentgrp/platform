#!/usr/bin/env python3
import os, time
from datetime import date, timedelta
from io import StringIO

import pandas as pd
import requests
import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
ALPACA_KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
SD_PCT_THRESHOLD = float(os.getenv("SD_PCT_THRESHOLD", "0.0"))

if not DB_URL:
    raise SystemExit("DATABASE_URL missing in .env")
if not (ALPACA_KEY and ALPACA_SECRET):
    raise SystemExit("Alpaca keys missing in .env")

SECTOR_ETFS = [
    ("XLE","Energy"),("XLB","Materials"),("XLI","Industrials"),
    ("XLY","Consumer Discretionary"),("XLP","Consumer Staples"),
    ("XLV","Healthcare"),("XLF","Financials"),("XLK","Information Technology"),
    ("XLC","Communication Services"),("XLU","Utilities"),("XLRE","Real Estate"),
]

def ensure_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_demographics (
          symbol TEXT PRIMARY KEY,
          name TEXT, sector TEXT, industry TEXT, market_cap BIGINT,
          priority SMALLINT DEFAULT 0,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now()
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_history (
          symbol TEXT NOT NULL, bar_date DATE NOT NULL,
          open_price NUMERIC(18,6), high_price NUMERIC(18,6),
          low_price NUMERIC(18,6), close_price NUMERIC(18,6),
          volume BIGINT, adjusted BOOLEAN DEFAULT TRUE,
          PRIMARY KEY(symbol, bar_date)
        );""")
    conn.commit()

def get_sp500_symbols():
    """
    Robustly load the S&P 500 table from Wikipedia and return
    columns: symbol, name, sector
    """
    wiki = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(wiki, headers=headers, timeout=20)
    r.raise_for_status()

    # read_html can produce MultiIndex columns; grab the first table with 'Symbol'
    tables = pd.read_html(StringIO(r.text))
    table = None
    for t in tables:
        cols = [str(c).strip() for c in (t.columns.to_flat_index()
                                         if hasattr(t.columns, "to_flat_index")
                                         else list(t.columns))]
        if any(c.lower() == "symbol" for c in cols):
            t.columns = cols  # normalize
            table = t
            break
    if table is None:
        raise RuntimeError("Could not find S&P 500 table with a 'Symbol' column.")

    # Normalize column names (string + strip already done)
    lower_map = {c.lower(): c for c in table.columns}
    # Wikipedia sometimes uses "Security" (usual) or "Company"
    name_col = lower_map.get("security") or lower_map.get("company")
    sector_col = (lower_map.get("gics sector") or
                  lower_map.get("gics sector ") or
                  lower_map.get("gics sector "))  # sometimes a nbsp

    if not name_col or not sector_col or "Symbol" not in table.columns:
        # As a fallback, try case-insensitive picks
        def pick(colname):
            for c in table.columns:
                if c.strip().lower() == colname:
                    return c
            return None
        name_col = name_col or pick("security") or pick("company")
        sector_col = sector_col or pick("gics sector")
        if not name_col or not sector_col:
            raise RuntimeError(f"Unexpected table columns: {list(table.columns)}")

    df = table.rename(columns={
        "Symbol": "symbol",
        name_col: "name",
        sector_col: "sector"
    })

    # Keep only the fields we need
    demo = df[["symbol", "name", "sector"]].copy()

    # Clean symbol formatting (strip whitespace)
    demo["symbol"] = demo["symbol"].astype(str).str.strip()

    return demo

def upsert_demographics(conn, demo_df):
    with conn.cursor() as cur:
        for _, r in demo_df.iterrows():
            cur.execute("""
              INSERT INTO stock_demographics(symbol,name,sector,updated_at)
              VALUES (%s,%s,%s,now())
              ON CONFLICT(symbol) DO UPDATE SET
                name=EXCLUDED.name, sector=EXCLUDED.sector, updated_at=now();""",
                (r["symbol"], r.get("name"), r.get("sector")))
        for sym, sector in SECTOR_ETFS:
            cur.execute("""
              INSERT INTO stock_demographics(symbol,name,sector,priority,updated_at)
              VALUES (%s,%s,%s,9,now())
              ON CONFLICT(symbol) DO UPDATE SET priority=9, sector=EXCLUDED.sector, updated_at=now();""",
              (sym, sector+" Sector ETF", sector))
    conn.commit()

def fetch_30d_and_upsert(conn, symbols):
    client = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
    end = date.today()
    start = end - timedelta(days=40)  # buffer to ensure ~30 trading days
    rows = []
    BATCH=100
    for i in range(0, len(symbols), BATCH):
        batch = symbols[i:i+BATCH]
        req = StockBarsRequest(symbol_or_symbols=batch, timeframe=TimeFrame.Day,
                               start=start, end=end, adjustment="split",
                               feed="iex", limit=10000)
        bars = client.get_stock_bars(req)
        df = getattr(bars, "df", None)
        if df is None or df.empty:
            continue
        df = df.reset_index()  # symbol, timestamp, open, high, low, close, volume, ...
        df["bar_date"] = pd.to_datetime(df["timestamp"]).dt.date
        for _, r in df.iterrows():
            rows.append((r["symbol"], r["bar_date"], r.get("open"), r.get("high"),
                         r.get("low"), r.get("close"), int(r.get("volume") or 0), True))
        time.sleep(0.4)   # be gentle

    if not rows:
        return
    with conn.cursor() as cur:
        pgx.execute_batch(cur, """
          INSERT INTO stock_history(symbol,bar_date,open_price,high_price,low_price,close_price,volume,adjusted)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT(symbol,bar_date) DO UPDATE SET
            open_price=EXCLUDED.open_price, high_price=EXCLUDED.high_price,
            low_price=EXCLUDED.low_price, close_price=EXCLUDED.close_price,
            volume=EXCLUDED.volume, adjusted=EXCLUDED.adjusted;
        """, rows, page_size=2000)
    conn.commit()

def set_priorities(conn, pct_buffer=SD_PCT_THRESHOLD):
    with conn.cursor() as cur:
        cur.execute(f"""
          WITH last_day AS (
            SELECT symbol, max(bar_date) AS d FROM stock_history GROUP BY symbol
          ),
          w AS (
            SELECT h.symbol, h.bar_date,
                   avg(h.close_price) OVER (
                     PARTITION BY h.symbol ORDER BY h.bar_date
                     ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
                   ) AS ma21,
                   stddev_samp(h.close_price) OVER (
                     PARTITION BY h.symbol ORDER BY h.bar_date
                     ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
                   ) AS sd21,
                   h.close_price
            FROM stock_history h
            JOIN last_day ld ON ld.symbol=h.symbol AND ld.d=h.bar_date
          ),
          signal AS (
            SELECT symbol,
                   CASE
                     WHEN sd21 IS NOT NULL
                          AND abs(close_price - ma21) > sd21
                          AND (CASE WHEN ma21>0 THEN abs(close_price-ma21)/ma21 ELSE 0 END) >= %s
                     THEN 1 ELSE 0
                   END AS pr
            FROM w
          )
          UPDATE stock_demographics d
             SET priority = CASE WHEN d.priority = 9 THEN 9 ELSE s.pr END,
                 updated_at = now()
          FROM signal s
          WHERE d.symbol = s.symbol;
        """, (pct_buffer,))
    conn.commit()

def main():
    print("Connecting DB…")
    conn = psycopg2.connect(DB_URL)
    ensure_tables(conn)

    print("Loading S&P 500 list…")
    spx = get_sp500_symbols()
    upsert_demographics(conn, spx)

    all_syms = spx["symbol"].tolist() + [s for (s, _) in SECTOR_ETFS]
    print(f"Fetching last 30d for {len(all_syms)} symbols…")
    fetch_30d_and_upsert(conn, all_syms)

    print("Computing priorities (|close - SMA21| > 1×SD)…")
    set_priorities(conn)
    conn.close()
    print("Done ✅")

if __name__ == "__main__":
    main()
