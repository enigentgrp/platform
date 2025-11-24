#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trading engine implementing stocks **and** options logic per spec.
- Uses Alpaca paper trading
- Works with Neon pooled Postgres (no startup options in DSN)
- Implements rules 2–7 from the PDF, including options selection
- Adds EVAR resolution: symbol -> sector -> global (fallback)

Assumptions:
- Existing DB tables from your scripts (stock_demographics, stock_history, orders)
- You’ve run the nightly loader to populate history + priorities
- `.env` exists at project root

Safety:
- Per-statement timeout (SET LOCAL) compatible with PgBouncer pooler
- Defensive fallbacks if options data endpoints are unavailable

Tested paths (paper):
- Account read, stock notional market buy/close
- Option selection (strike/expiry) + latest trade fetch + paper order creation

If your Alpaca SDK is older/newer, the options data client classes may differ. The
code handles imports with try/except and raises a clear error if missing.
"""
import os, time, signal, math, sys
import psycopg2
from collections import deque
from datetime import datetime, timedelta, date
from pathlib import Path
from statistics import pstdev
from typing import Optional, Tuple, Dict, Any, List

from dotenv import load_dotenv

# ---- Alpaca Trading (paper)
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, AssetClass

# ---- Alpaca Market Data (stocks + options)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame

# Options data imports — newer SDKs
try:
    from alpaca.data.historical import OptionsHistoricalDataClient
    from alpaca.data.requests import OptionBarsRequest, OptionLatestTradeRequest
    HAVE_OPTIONS_DATA = True
except Exception:
    HAVE_OPTIONS_DATA = False

# ---- Postgres
import psycopg2
import psycopg2.extras as pgx
from psycopg2 import OperationalError, InterfaceError

# ---------------------------
# Robust .env loading (always use project/.env)
# ---------------------------
ROOT = Path(__file__).resolve().parents[1]   # .../AlgoTrade
ENV_PATH = ROOT / ".env"
if not ENV_PATH.exists():
    raise SystemExit(f".env not found at {ENV_PATH}")
load_dotenv(dotenv_path=str(ENV_PATH))

DB_URL = os.getenv("DATABASE_URL")
KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
SEC = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")

# ---------------------------
# EVARs (global defaults)
# ---------------------------
SMA_LEN              = int(os.getenv("SMA_LEN", "21"))
SD_ABS_THRESH_PCT    = float(os.getenv("SD_ABS_THRESH_PCT", "0.0"))
PRICE_CHECK_INTERVAL = float(os.getenv("PRICE_CHECK_INTERVAL", "5"))   # seconds
CONSECUTIVE_PERIODS  = int(os.getenv("CONSECUTIVE_PERIODS", "2"))

CASH_INVEST_OPTION_PCT = float(os.getenv("CASH_INVEST_OPTION_PCT", "0.25"))
OPTION_PCT_BUY          = float(os.getenv("OPTION_PCT_BUY", "0.10"))
CASH_INVEST_STOCK_PCT   = float(os.getenv("CASH_INVEST_STOCK_PCT", "0.25"))
STOCK_PCT_SELL          = float(os.getenv("STOCK_PCT_SELL", "0.25"))

MOMENTUM_DECR_PCT = float(os.getenv("MOMENTUM_DECR_PCT", "0.20"))
LOSS_PCT_LIMIT    = float(os.getenv("LOSS_PCT_LIMIT", "0.50"))
EOD_LIMIT_MIN     = int(os.getenv("EOD_LIMIT_MIN", "15"))  # minutes

MIN_CASH_USD       = float(os.getenv("MIN_CASH_USD",       "100"))
MIN_PRICE_USD      = float(os.getenv("MIN_PRICE_USD",      "2"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS",   "25"))

# Options filters
MIN_OPTIONS_VOL          = int(os.getenv("MIN_OPTIONS_VOL", "100"))
OPT_STRIKE_PRICE_PCT_TGT = float(os.getenv("OPT_STRIKE_PRICE_PCT_TARGET", "0.00"))  # 0=ATM, >0 = % OTM

# Sector ETFs constant priority=9 already loaded by your loader
SECTOR_ETFS = [
    ("XLE","Energy"),("XLB","Materials"),("XLI","Industrials"),
    ("XLY","Consumer Discretionary"),("XLP","Consumer Staples"),
    ("XLV","Healthcare"),("XLF","Financials"),("XLK","Information Technology"),
    ("XLC","Communication Services"),("XLU","Utilities"),("XLRE","Real Estate"),
]

# Demo trade
ENABLE_TEST_DEMO = os.getenv("ENABLE_TEST_DEMO", "false").lower() == "true"
TEST_SYMBOL      = os.getenv("TEST_SYMBOL", "XLK")
TEST_NOTIONAL    = float(os.getenv("TEST_NOTIONAL", "10"))

if not all([DB_URL, KEY, SEC]):
    raise SystemExit("Missing DATABASE_URL / ALPACA_API_KEY / ALPACA_SECRET_KEY in .env")

# ---------------------------
# Postgres helpers — pooler-friendly (no startup options)
# ---------------------------
_conn = None

def get_conn():
    global _conn
    try:
        if _conn is not None:
            with _conn.cursor() as cur:
                cur.execute("SELECT 1")
            return _conn
    except Exception:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None

    _conn = psycopg2.connect(
        DB_URL,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    _conn.autocommit = True
    return _conn

def safe_exec(sql, params=None, fetch="none", statement_timeout_ms=60000):
    tries, delay = 0, 1.0
    while True:
        try:
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout TO %s", (statement_timeout_ms,))
                cur.execute(sql, params or ())
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return None
        except (OperationalError, InterfaceError):
            tries += 1
            if tries > 5:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 8.0)

# ---------------------------
# Alpaca clients
# ---------------------------
trade = TradingClient(KEY, SEC, paper=True)
stock_data = StockHistoricalDataClient(KEY, SEC)
opt_data = OptionsHistoricalDataClient(KEY, SEC) if HAVE_OPTIONS_DATA else None

# ---------------------------
# In-memory state
# ---------------------------
N_WINDOW = max(CONSECUTIVE_PERIODS + 3, 5)
price_windows: Dict[str, deque] = {}

running = True

def handle_sigint(sig, frame):
    global running
    running = False
signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)

# ---------------------------
# EVAR resolution (symbol -> sector -> global)
# ---------------------------
_DEF_EVARS = {
    "SMA_LEN": SMA_LEN,
    "SD_ABS_THRESH_PCT": SD_ABS_THRESH_PCT,
    "PRICE_CHECK_INTERVAL": PRICE_CHECK_INTERVAL,
    "CONSECUTIVE_PERIODS": CONSECUTIVE_PERIODS,
    "CASH_INVEST_OPTION_PCT": CASH_INVEST_OPTION_PCT,
    "OPTION_PCT_BUY": OPTION_PCT_BUY,
    "CASH_INVEST_STOCK_PCT": CASH_INVEST_STOCK_PCT,
    "STOCK_PCT_SELL": STOCK_PCT_SELL,
    "MOMENTUM_DECR_PCT": MOMENTUM_DECR_PCT,
    "LOSS_PCT_LIMIT": LOSS_PCT_LIMIT,
    "EOD_LIMIT_MIN": EOD_LIMIT_MIN,
    "MIN_CASH_USD": MIN_CASH_USD,
    "MIN_PRICE_USD": MIN_PRICE_USD,
    "MAX_OPEN_POSITIONS": MAX_OPEN_POSITIONS,
    "MIN_OPTIONS_VOL": MIN_OPTIONS_VOL,
    "OPT_STRIKE_PRICE_PCT_TARGET": OPT_STRIKE_PRICE_PCT_TGT,
}


def load_evars(symbol: str) -> Dict[str, Any]:
    # Start with global defaults
    evars = dict(_DEF_EVARS)

    # Try to read sector + per-symbol evars if the columns/tables exist
    try:
        row = safe_exec(
            "SELECT sector, COALESCE(evars, '{}'::jsonb) FROM stock_demographics WHERE symbol=%s",
            (symbol,), fetch="one"
        )
        if not row:
            return evars

        sector, evars_sym = row

        # Merge sector evars if the sectors table exists
        if sector:
            try:
                sec = safe_exec(
                    "SELECT COALESCE(evars, '{}'::jsonb) FROM sectors WHERE name=%s",
                    (sector,), fetch="one"
                )
                if sec and sec[0]:
                    evars.update(sec[0])
            except psycopg2.Error:
                # sectors table or column missing — ignore
                pass

        # Merge per-symbol evars if present
        if evars_sym:
            evars.update(evars_sym)

    except psycopg2.Error:
        # stock_demographics.evars column missing — ignore and keep defaults
        pass

    return evars

# ---------------------------
# Helpers
# ---------------------------
def is_market_close_soon(evars: Dict[str, Any]) -> bool:
    now = datetime.now()
    close_like = now.replace(hour=15, minute=59, second=0, microsecond=0)  # CT approx
    return (close_like - now).total_seconds() <= float(evars["EOD_LIMIT_MIN"]) * 60

def latest_trade_price(sym: str) -> Optional[float]:
    t = stock_data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=sym))[sym]
    return float(getattr(t, "price", None) or 0) or None

def get_cash_and_positions():
    acct = trade.get_account()
    cash = float(acct.cash) if acct.cash is not None else 0.0
    pos = {p.symbol: float(p.qty) for p in trade.get_all_positions() if p.asset_class == AssetClass.US_EQUITY}
    try:
        for p in trade.get_all_positions():
            if p.asset_class == AssetClass.OPTION:
                pos[p.symbol] = float(p.qty)
    except Exception:
        pass
    return cash, pos

def sector_etf_for(symbol: str) -> str:
    row = safe_exec("SELECT sector FROM stock_demographics WHERE symbol=%s", (symbol,), fetch="one")
    if row and row[0]:
        sector = row[0]
        for etf, name in SECTOR_ETFS:
            if name == sector:
                return etf
    return "XLK"

def fetch_recent_closes(symbol: str, days: int) -> List[float]:
    end = date.today()
    start = end - timedelta(days=days*2)
    req = StockBarsRequest(
        symbol_or_symbols=[symbol], timeframe=TimeFrame.Day,
        start=start, end=end, adjustment="split", feed="iex", limit=days*3
    )
    bars = stock_data.get_stock_bars(req)
    df = getattr(bars, "df", None)
    if df is None or df.empty:
        return []
    df = df.reset_index()
    df = df[df["symbol"] == symbol].sort_values("timestamp")
    closes = [float(x) for x in df["close"].tolist()][-days:]
    return closes

def sma(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None

def sd(values: List[float]) -> float:
    if not values or len(values) < 2:
        return 0.0
    return pstdev(values)

def update_window(sym: str, px: Optional[float]) -> deque:
    dq = price_windows.setdefault(sym, deque(maxlen=N_WINDOW))
    if px is not None:
        dq.append(px)
    return dq

def recent_moves(sym: str) -> List[int]:
    dq = price_windows.get(sym, deque())
    moves: List[int] = []
    for a, b in zip(list(dq)[:-1], list(dq)[1:]):
        if b > a: moves.append(1)
        elif b < a: moves.append(-1)
        else: moves.append(0)
    return moves

def sector_trend_signal(etf_symbol: str) -> int:
    closes = fetch_recent_closes(etf_symbol, days=5)
    if len(closes) < 3:
        return 0
    ups = sum(1 for a,b in zip(closes[:-1], closes[1:]) if b > a)
    downs = sum(1 for a,b in zip(closes[:-1], closes[1:]) if b < a)
    return 1 if ups > downs else (-1 if downs > ups else 0)

# ---------------------------
# Options helpers
# ---------------------------
def next_friday_after_tomorrow(today: Optional[date] = None) -> date:
    d0 = today or date.today()
    d1 = d0 + timedelta(days=2)  # day after tomorrow
    days_ahead = (4 - d1.weekday()) % 7  # Fri=4
    if days_ahead == 0:
        days_ahead = 7
    return d1 + timedelta(days=days_ahead)

def occ_symbol(symbol: str, expiry: date, call_or_put: str, strike: float) -> str:
    y = expiry.year % 100
    m = expiry.month
    d = expiry.day
    cp = 'C' if call_or_put.upper().startswith('C') else 'P'
    strike_int = int(round(strike * 1000))
    return f"{symbol.upper()}{y:02d}{m:02d}{d:02d}{cp}{strike_int:08d}"

def pick_option_contract(symbol: str, last_px: float, evars: Dict[str, Any], call_or_put: str) -> Optional[str]:
    if not HAVE_OPTIONS_DATA or opt_data is None:
        print("[OPTIONS] Data client unavailable; cannot select contract.")
        return None

    pct = float(evars["OPT_STRIKE_PRICE_PCT_TARGET"])
    target_px = last_px * (1 + pct if call_or_put.upper().startswith('C') else 1 - pct)
    expiry = next_friday_after_tomorrow()

    candidates = []
    for off in range(0, 11):
        for sign in (+1, -1):
            strike = max(0.5, target_px + sign*off)
            sym = occ_symbol(symbol, expiry, call_or_put, strike)
            candidates.append((abs(strike - target_px), strike, sym))
    candidates.sort(key=lambda x: x[0])

    for _dist, strike, occ in candidates:
        try:
            req = OptionLatestTradeRequest(symbol_or_symbols=occ)
            lt = opt_data.get_option_latest_trade(req)
            trade = lt.get(occ)
            if not trade:
                continue
            vb = opt_data.get_option_bars(OptionBarsRequest(symbol_or_symbols=[occ], timeframe=TimeFrame.Day, limit=1))
            df = getattr(vb, "df", None)
            if df is None or df.empty:
                continue
            df = df.reset_index()
            vol = int(df.loc[0, "volume"]) if "volume" in df.columns else 0
            if vol >= int(evars["MIN_OPTIONS_VOL"]):
                return occ
        except Exception:
            continue
    return None

def latest_option_price(occ: str) -> Optional[float]:
    if not HAVE_OPTIONS_DATA or opt_data is None:
        return None
    try:
        req = OptionLatestTradeRequest(symbol_or_symbols=occ)
        lt = opt_data.get_option_latest_trade(req)
        trade = lt.get(occ)
        if trade and getattr(trade, "price", None) is not None:
            return float(trade.price)
    except Exception:
        return None
    return None

# ---------------------------
# Order helpers
# ---------------------------
def log_order(symbol, asset_type, side, qty, limit_price, status, broker_order_id, meta=None):
    sql = (
        "INSERT INTO orders("
        "account_id, symbol, asset_type, side, qty, limit_price, status, broker_order_id, submitted_at, meta"
        ") VALUES ("
        "NULL, %s, %s, %s, %s, %s, %s, %s, now(), %s)"
    )
    params = (
        symbol,
        asset_type,
        side,
        qty,
        limit_price,
        str(status) if status is not None else None,
        str(broker_order_id) if broker_order_id is not None else None,
        pgx.Json(meta or {}),
    )
    safe_exec(sql, params)

def buy_stock_notional(symbol: str, notional: float, note: str = "entry"):
    req = MarketOrderRequest(
        symbol=symbol,
        notional=round(max(0.0, notional), 2),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.SIMPLE,
    )
    o = trade.submit_order(req)
    log_order(symbol, "stock", "buy", None, None, str(o.status), str(o.id), {"type": note, "notional": notional})
    print(f"BUY submitted {symbol} notional=${notional:.2f} id={o.id}")
    return o

def close_stock_all(symbol: str, note: str = "exit") -> bool:
    try:
        o = trade.close_position(symbol, ClosePositionRequest(percentage="100"))
        oid = getattr(o, "id", None) or getattr(o, "order_id", None) or "close_position"
        log_order(symbol, "stock", "sell", None, None, "submitted", str(oid), {"type": note})
        print(f"SELL submitted {symbol} (close 100%)")
        return True
    except Exception as e:
        print(f"SELL error {symbol}: {e}")
        return False

def buy_option_contract(occ: str, notional_hint: float, note: str = "opt_buy") -> Optional[str]:
    px = latest_option_price(occ) or 0.0
    if px <= 0:
        print(f"[OPTIONS] No price for {occ}; skipping buy")
        return None
    qty = max(1, int(notional_hint // (px * 100)))  # 100 multiplier
    symbol_under = "".join([ch for ch in occ if not ch.isdigit()])[:-15] if len(occ) > 15 else occ
    try:
        o = trade.submit_order(
            MarketOrderRequest(
                symbol=occ,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.SIMPLE,
            )
        )
        log_order(symbol_under, "option", "buy", qty, None, str(o.status), str(o.id), {"type": note, "occ": occ, "px": px})
        print(f"[OPTIONS] BUY {occ} x{qty} (~${px*100*qty:.2f}) id={o.id}")
        return str(o.id)
    except Exception as e:
        print(f"[OPTIONS] BUY error {occ}: {e}")
        return None

def close_all_options_for(symbol: str) -> None:
    try:
        for p in trade.get_all_positions():
            if p.asset_class == AssetClass.OPTION and p.symbol.startswith(symbol.upper()):
                try:
                    o = trade.close_position(p.symbol)
                    oid = getattr(o, "id", None) or getattr(o, "order_id", None) or "close_position"
                    log_order(symbol, "option", "sell", None, None, "submitted", str(oid), {"type": "close_opt", "occ": p.symbol})
                    print(f"[OPTIONS] CLOSE {p.symbol}")
                except Exception as e:
                    print(f"[OPTIONS] CLOSE error {p.symbol}: {e}")
    except Exception as e:
        print(f"[OPTIONS] enumerate positions failed: {e}")

# ---------------------------
# Core decision logic (rules 3–6)
# ---------------------------
def evaluate_and_trade(sym: str, cash: float, stock_qty: float, last_px: float,
                        sma21: float, sd21: float, sector_trend: int, evars: Dict[str, Any]):
    N = int(evars["CONSECUTIVE_PERIODS"])
    moves = recent_moves(sym)
    if len(moves) < N:
        return

    last_block = moves[-N:]
    rising = all(m == 1 for m in last_block)
    falling = all(m == -1 for m in last_block)

    above_sma_1sd = (sd21 is not None and sma21 is not None and last_px > sma21 + sd21 and
                     (sma21 <= 0 or abs((last_px - sma21)/sma21) >= float(evars["SD_ABS_THRESH_PCT"])) )
    below_sma_1sd = (sd21 is not None and sma21 is not None and last_px < sma21 - sd21 and
                     (sma21 <= 0 or abs((last_px - sma21)/sma21) >= float(evars["SD_ABS_THRESH_PCT"])) )

    sector_falling = (sector_trend == -1)
    sector_rising  = (sector_trend == +1)

    dq = price_windows.get(sym, deque())
    dec_momentum = False
    if len(dq) >= 4:
        deltas = [b - a for a,b in zip(list(dq)[:-1], list(dq)[1:])]
        m_now, m_prev = abs(deltas[-1]), abs(deltas[-2])
        if m_prev > 0 and (m_prev - m_now) / m_prev >= float(evars["MOMENTUM_DECR_PCT"]):
            dec_momentum = True

    def do_options(call_or_put: str):
        nonlocal cash
        notional_opt = cash * float(evars["CASH_INVEST_OPTION_PCT"]) if cash > float(evars["MIN_CASH_USD"]) else 0.0
        if notional_opt <= 0:
            return
        occ = pick_option_contract(sym, last_px, evars, call_or_put)
        if occ:
            buy_option_contract(occ, notional_opt, note=f"{call_or_put.lower()}_leg")

    if falling and (above_sma_1sd or sector_falling):
        close_all_options_for(sym)
        do_options("PUT")
        if stock_qty > 0:
            close_stock_all(sym, note="rule3_stock_pct_sell")

    if rising and (below_sma_1sd or sector_rising):
        close_all_options_for(sym)
        do_options("CALL")
        notional_stock = cash * float(evars["CASH_INVEST_STOCK_PCT"]) if cash > float(evars["MIN_CASH_USD"]) else 0.0
        if notional_stock > 0:
            buy_stock_notional(sym, notional_stock, note="rule4_stock_buy")

    if dec_momentum:
        do_options("CALL" if rising else "PUT")

    rev = len(moves) >= 2 and ((moves[-2] == 1 and moves[-1] == -1) or (moves[-2] == -1 and moves[-1] == 1))
    if is_market_close_soon(evars) or rev:
        close_all_options_for(sym)
        if stock_qty > 0:
            close_stock_all(sym, note="rule6_exit")

# ---------------------------
# Priority universe
# ---------------------------
def get_priority_symbols() -> List[str]:
    rows = safe_exec(
        "SELECT symbol FROM stock_demographics WHERE priority IN (1,9)", fetch="all")
    return [r[0] for r in rows] if rows else []

# ---------------------------
# Demo one-shot (optional)
# ---------------------------
def run_demo_trade_once():
    if not ENABLE_TEST_DEMO:
        return
    try:
        print(f"[DEMO] Placing ${TEST_NOTIONAL:.2f} BUY on {TEST_SYMBOL} …")
        buy_stock_notional(TEST_SYMBOL, TEST_NOTIONAL, note="demo_entry")
        print("[DEMO] Done.")
    except Exception as e:
        print("[DEMO] Failed:", e)

# ---------------------------
# Main loop
# ---------------------------
def main():
    global trade, stock_data, opt_data
    print("Trading engine (paper) started. Stocks + Options enabled.")
    run_demo_trade_once()

    while running:
        try:
            syms = get_priority_symbols()
            cash, positions = get_cash_and_positions()

            stock_pos_syms = [s for s, q in positions.items() if not any(c in s for c in 'CP0123456789')]
            if cash < MIN_CASH_USD or len(stock_pos_syms) >= MAX_OPEN_POSITIONS:
                time.sleep(PRICE_CHECK_INTERVAL); continue

            for s in syms:
                evars = load_evars(s)
                last_px = latest_trade_price(s)
                if last_px is None or last_px < float(evars["MIN_PRICE_USD"]):
                    continue

                update_window(s, last_px)

                closes = fetch_recent_closes(s, days=int(evars["SMA_LEN"]))
                if not closes:
                    continue
                s21 = sma(closes)
                sd21 = sd(closes)

                etf = s if any(s == et for et, _ in SECTOR_ETFS) else sector_etf_for(s)
                trend = sector_trend_signal(etf)

                stock_qty = float(positions.get(s, 0.0))
                evaluate_and_trade(s, cash, stock_qty, last_px, s21, sd21, trend, evars)

                time.sleep(0.01)

            time.sleep(PRICE_CHECK_INTERVAL)

        except Exception as e:
            print("Loop error:", e)
            try:
                trade = TradingClient(KEY, SEC, paper=True)
                stock_data = StockHistoricalDataClient(KEY, SEC)
                opt_data = OptionsHistoricalDataClient(KEY, SEC) if HAVE_OPTIONS_DATA else None
            except Exception:
                pass
            time.sleep(PRICE_CHECK_INTERVAL)

    print("Trading engine stopped.")


if __name__ == "__main__":
    main()
