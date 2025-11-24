#!/usr/bin/env python3
import os, psycopg2, psycopg2.extras as pgx
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

load_dotenv(".env")
DB_URL = os.getenv("DATABASE_URL")
KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
SEC = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")

conn = psycopg2.connect(DB_URL)
tc = TradingClient(KEY, SEC, paper=True)

# last 7 days
after = datetime.now(timezone.utc) - timedelta(days=7)
req = GetOrdersRequest(
    status=QueryOrderStatus.ALL,
    after=after
)
orders = tc.get_orders(req)

with conn, conn.cursor() as cur:
    for o in orders:
        meta = {
            "asset_class": str(o.asset_class),
            "type": str(o.type),
            "time_in_force": str(o.time_in_force),
            "notional": getattr(o, "notional", None),
            "qty": getattr(o, "qty", None),
            "limit_price": getattr(o, "limit_price", None),
            "avg_price": getattr(o, "filled_avg_price", None),
            "client_order_id": getattr(o, "client_order_id", None),
        }
        cur.execute("""
            INSERT INTO orders(
              account_id, symbol, asset_type, side, qty, limit_price, status, broker_order_id, submitted_at, filled_at, meta
            )
            VALUES (NULL, %s, 'stock', %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (
            o.symbol,
            str(o.side),
            float(o.qty) if o.qty else None,
            float(o.limit_price) if o.limit_price else None,
            str(o.status),
            o.id,
            o.submitted_at,
            o.filled_at,
            pgx.Json(meta)
        ))

print(f"Synced {len(orders)} orders from Alpaca → Neon.")
