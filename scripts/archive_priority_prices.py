#!/usr/bin/env python3
import os, psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

SQL = """
INSERT INTO priority_archive_price(symbol, ts, price_open, price_last, pct_change, source)
SELECT symbol, ts, price_open, price_last, pct_change, source
FROM priority_current_price;

-- purge current
TRUNCATE priority_current_price;

-- purge archive older than X days (EVAR)
WITH t AS (
  SELECT COALESCE((SELECT value_num FROM env_globals WHERE key='PRIORITY_ARCHIVE_RETENTION_DAYS'), 30) AS keepdays
)
DELETE FROM priority_archive_price
USING t
WHERE ts < now() - (t.keepdays || ' days')::interval;
"""

if __name__ == "__main__":
  conn = psycopg2.connect(DB_URL)
  with conn, conn.cursor() as cur:
    cur.execute(SQL)
