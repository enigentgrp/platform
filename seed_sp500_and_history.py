#!/usr/bin/env python3
import os, sys, time
from datetime import datetime, timedelta

# --- Load .env ASAP ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- Config from env ---
DB_URL = os.getenv("DATABASE_URL")
ALPACA_KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
DAYS_BACK = int(os.getenv("DAYS_BACK", "90"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))

if not DB_URL:
    sys.exit("DATABASE_URL missing")
if not (ALPACA_KEY and ALPACA_SECRET):
    sys.exit("Alpaca keys missing")

import pandas as pd
import psycopg2
import psycopg2.extras as pgx
import requests
from io import StringIO

# Alpaca Market Data client
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
data_client = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)


# ---------- Helpers ----------
def ensure_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_demographics (
          symbol     TEXT PRIMARY KEY,
          name       TEXT,
          sector     TEXT,
          industry   TEXT,
          market_cap BIGINT,
          priority   SMALLINT DEFAULT 0,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now()
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_history (
          symbol      TEXT NOT NULL,
          bar_date    DATE NOT NULL,
          open_price  NUMERIC(18,6),
          high_price  NUMERIC(18,6),
          low_price   NUMERIC(18,6),
          close_price NUMERIC(18,6),
          volume      BIGINT,
          adjusted    BOOLEAN DEFAULT TRUE,
          PRIMARY KEY(symbol, bar_date)
        );""")
    conn.commit()


def get_sp500_symbols():
    """
    Returns (symbols_list, demographics_df) with columns: symbol, name, sector.
    Tries Wikipedia with a real User-Agent; falls back to DataHub CSV if blocked.
    """
    wiki_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(wiki_url, headers=headers, timeout=20)
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))
        df = tables[0]
        df.columns = [c.strip() for c in df.columns]
        demo = df[["Symbol", "Security", "GICS Sector"]].rename(
            columns={"Symbol": "symbol", "Security": "name", "GICS Sector": "sector"}
        )
        syms = demo["symbol"].astype(str).str.strip().unique().tolist()
        return syms, demo
    except Exception as e:
        print(f"⚠️ Wikipedia fetch failed ({e}). Falling back to DataHub CSV…")
        csv_url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
        r = requests.get(csv_url, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        # normalize column names
        cols = {c.lower(): c for c in df.columns}
        symbol_col = cols.get("symbol", "Symbol")
        name_col = cols.get("name", "Name")
        sector_col = cols.get("sector", "Sector")
        demo = df[[symbol_col, name_col, sector_col]].rename(
            columns={symbol_col: "symbol", name_col: "name", sector_col: "sector"}
        )
        syms = demo["symbol"].astype(str).str.strip().unique().tolist()
        return syms, demo


def upsert_demographics(conn, demo_df):
    with conn.cursor() as cur:
        for _, r in demo_df.iterrows():
            cur.execute("""
                INSERT INTO stock_demographics(symbol, name, sector, updated_at)
                VALUES (%s,%s,%s, now())
                ON CONFLICT (symbol) DO UPDATE
                  SET name=EXCLUDED.name,
                      sector=EXCLUDED.sector,
                      updated_at=now();
            """, (r["symbol"], r.get("name"), r.get("sector")))
    conn.commit()


def fetch_bars(symbols, start, end):
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        adjustment="split",   # adjusted prices
        feed="iex",           # free paper feed
        limit=10000
    )
    return data_client.get_stock_bars(req)


def bars_to_rows(bars):
    """
    Convert alpaca-py bars to list of rows for insertion.
    Supports both .df (DataFrame) and .data (dict-of-lists) variants.
    """
    rows = []

    # Preferred: bars.df is a DataFrame with MultiIndex (symbol, timestamp)
    df = getattr(bars, "df", None)
    if df is not None and not df.empty:
        # Ensure index has symbol & timestamp
        if "symbol" in df.index.names and "timestamp" in df.index.names:
            for (sym, ts), row in df.iterrows():
                rows.append((
                    sym,
                    ts.date(),
                    float(row.get("open")) if row.get("open") is not None else None,
                    float(row.get("high")) if row.get("high") is not None else None,
                    float(row.get("low")) if row.get("low") is not None else None,
                    float(row.get("close")) if row.get("close") is not None else None,
                    int(row.get("volume")) if row.get("volume") is not None else None,
                    True
                ))
            return rows

    # Fallback: older object shape with .data dict
    data = getattr(bars, "data", None)
    if isinstance(data, dict):
        for sym, blist in data.items():
            for b in blist:
                rows.append((
                    sym,
                    b.timestamp.date(),
                    float(getattr(b, "open", None)) if getattr(b, "open", None) is not None else None,
                    float(getattr(b, "high", None)) if getattr(b, "high", None) is not None else None,
                    float(getattr(b, "low", None))  if getattr(b, "low", None)  is not None else None,
                    float(getattr(b, "close", None)) if getattr(b, "close", None) is not None else None,
                    int(getattr(b, "volume", None)) if getattr(b, "volume", None) is not None else None,
                    True
                ))
    return rows


def upsert_history(conn, rows):
    if not rows:
        return
    with conn.cursor() as cur:
        pgx.execute_batch(cur, """
            INSERT INTO stock_history(symbol, bar_date, open_price, high_price, low_price, close_price, volume, adjusted)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (symbol, bar_date) DO UPDATE SET
                open_price=EXCLUDED.open_price,
                high_price=EXCLUDED.high_price,
                low_price=EXCLUDED.low_price,
                close_price=EXCLUDED.close_price,
                volume=EXCLUDED.volume,
                adjusted=EXCLUDED.adjusted;
        """, rows, page_size=1000)
    conn.commit()


def main():
    print("Fetching S&P 500 list…")
    syms, demo = get_sp500_symbols()
    print(f"Got {len(syms)} symbols")

    print("Connecting to Postgres…")
    conn = psycopg2.connect(DB_URL)

    # Optional (safe): ensure tables exist
    ensure_tables(conn)

    print("Upserting demographics…")
    upsert_demographics(conn, demo)

    end = datetime.utcnow().date()
    start = end - timedelta(days=DAYS_BACK)
    print(f"Fetching bars {start} → {end} (BATCH_SIZE={BATCH_SIZE})…")

    for i in range(0, len(syms), BATCH_SIZE):
        batch = syms[i:i+BATCH_SIZE]
        try:
            bars = fetch_bars(batch, start, end)
            rows = bars_to_rows(bars)
            upsert_history(conn, rows)
            print(f"   ✅ stored bars for {len(batch)} symbols [{i+1}-{i+len(batch)}], rows={len(rows)}")
            time.sleep(0.4)  # be kind to the API
        except Exception as e:
            print(f"   ⚠️ batch {i//BATCH_SIZE+1} failed: {e}")
            time.sleep(1.5)

    conn.close()
    print("🎉 Done. Demographics + history ready.")


if __name__ == "__main__":
    main()
