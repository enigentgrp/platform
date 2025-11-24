#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_options.py
Full options backtester implementing the rules from your spec:
- Uses daily bars for the underlying
- Signals use SMA(21) and 1×StdDev bands + consecutive up/down moves
- Sector ETF confirmation optional
- Options legs (CALL/PUT) chosen via nearest strike to a % target and weekly expiry (next Friday after T+2)
- Pricing via Alpaca Options historical data (if available) OR CSV fallback
- Fills at NEXT BAR OPEN to avoid lookahead bias
Outputs:
- CSV of trades
- CSV of daily equity
- Printed summary (CAGR, total return, max DD, Sharpe, win rate)

Requirements:
    pip install alpaca-py pandas numpy python-dotenv
For CSV fallback (no API), prepare:
    data/underlying/AAPL.csv   with columns: date,open,high,low,close,volume
    data/options/options.csv   with columns: date,occ,open,high,low,close,volume
"""
import os, sys, math, argparse
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

# --------- Config defaults (can be overridden by CLI/env) ---------
SMA_LEN              = int(os.getenv("SMA_LEN", "21"))
CONSECUTIVE_PERIODS  = int(os.getenv("CONSECUTIVE_PERIODS", "2"))
SD_ABS_THRESH_PCT    = float(os.getenv("SD_ABS_THRESH_PCT", "0.0"))
CASH_INVEST_STOCK_PCT= float(os.getenv("CASH_INVEST_STOCK_PCT", "0.25"))
CASH_INVEST_OPTION_PCT=float(os.getenv("CASH_INVEST_OPTION_PCT", "0.25"))
MOMENTUM_DECR_PCT    = float(os.getenv("MOMENTUM_DECR_PCT", "0.20"))
OPT_STRIKE_PRICE_PCT_TARGET = float(os.getenv("OPT_STRIKE_PRICE_PCT_TARGET", "0.00"))
MIN_OPTIONS_VOL      = int(os.getenv("MIN_OPTIONS_VOL", "50"))
INITIAL_CASH         = float(os.getenv("INITIAL_CASH", "100000"))
SECTOR_CONFIRM       = os.getenv("SECTOR_CONFIRM", "false").lower() == "true"

# Sector ETF mapping (optional confirmation)
SECTOR_ETFS = {
    "Energy":"XLE","Materials":"XLB","Industrials":"XLI","Consumer Discretionary":"XLY","Consumer Staples":"XLP",
    "Healthcare":"XLV","Financials":"XLF","Information Technology":"XLK","Communication Services":"XLC",
    "Utilities":"XLU","Real Estate":"XLRE"
}

# --------- Alpaca Option Data (optional) ----------
HAVE_ALPACA = False
try:
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import OptionBarsRequest, StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    ALPACA_KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
    ALPACA_SEC = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
    if ALPACA_KEY and ALPACA_SEC:
        HAVE_ALPACA = True
except Exception:
    HAVE_ALPACA = False

def to_date(x) -> date:
    if isinstance(x, date): return x
    return datetime.strptime(str(x)[:10], "%Y-%m-%d").date()

def next_friday_after_t_plus_2(d: date) -> date:
    anchor = d + timedelta(days=2)
    days_ahead = (4 - anchor.weekday()) % 7
    if days_ahead == 0: days_ahead = 7
    return anchor + timedelta(days=days_ahead)

def occ_symbol(under: str, expiry: date, cp: str, strike: float) -> str:
    y = expiry.year % 100
    m = expiry.month
    d = expiry.day
    cp1 = "C" if cp.upper().startswith("C") else "P"
    strike_int = int(round(strike * 1000))
    return f"{under.upper()}{y:02d}{m:02d}{d:02d}{cp1}{strike_int:08d}"

def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = equity/roll_max - 1.0
    return dd.min()

def sharpe_ratio(returns: pd.Series, rf: float = 0.0) -> float:
    if returns.std(ddof=1) == 0: return 0.0
    ann = np.sqrt(252) * (returns.mean() - rf) / returns.std(ddof=1)
    return float(ann)

class UnderlyingProvider:
    def get_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame: ...
    def get_sector(self, symbol: str) -> Optional[str]:
        return None

class OptionsProvider:
    def get_day_bar(self, occ: str, day: date) -> Optional[Dict]:
        ...

class AlpacaProvider(UnderlyingProvider, OptionsProvider):
    def __init__(self, key: str, secret: str):
        self.sclient = StockHistoricalDataClient(key, secret)
        self.oclient = OptionHistoricalDataClient(key, secret)

    def get_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame.Day, start=start, end=end, limit=10000, adjustment="split")
        bars = self.sclient.get_stock_bars(req)
        df = getattr(bars, "df", None)
        if df is None or df.empty: return pd.DataFrame()
        df = df.reset_index()
        df = df[df["symbol"]==symbol].copy()
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date
        return df[["date","open","high","low","close","volume"]].sort_values("date").drop_duplicates("date")

    def get_day_bar(self, occ: str, day: date) -> Optional[Dict]:
        start = day
        end = day + timedelta(days=1)
        try:
            req = OptionBarsRequest(symbol_or_symbols=[occ], timeframe=TimeFrame.Day, start=start, end=end, limit=2)
            bars = self.oclient.get_option_bars(req)
        except Exception:
            return None
        df = getattr(bars, "df", None)
        if df is None or df.empty: return None
        df = df.reset_index()
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date
        row = df[df["date"]==day]
        if row.empty: return None
        r = row.iloc[0]
        return {"close": float(r.get("close", np.nan)), "volume": int(r.get("volume", 0))}

class CSVProvider(UnderlyingProvider, OptionsProvider):
    def __init__(self, root: Path):
        self.root = Path(root)

    def get_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        f = self.root / "underlying" / f"{symbol.upper()}.csv"
        if not f.exists(): return pd.DataFrame()
        df = pd.read_csv(f)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[(df["date"]>=start) & (df["date"]<=end)].copy()
        return df[["date","open","high","low","close","volume"]].sort_values("date")

    def get_day_bar(self, occ: str, day: date) -> Optional[Dict]:
        f = self.root / "options" / "options.csv"
        if not f.exists(): return None
        df = pd.read_csv(f)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        row = df[(df["date"]==day) & (df["occ"]==occ)]
        if row.empty: return None
        r = row.iloc[0]
        return {"close": float(r.get("close", np.nan)), "volume": int(r.get("volume", 0))}

from dataclasses import dataclass, field

@dataclass
class Position:
    qty_stock: float = 0.0
    options: Dict[str, int] = field(default_factory=dict)
    last_prices: Dict[str, float] = field(default_factory=dict)

@dataclass
class Trade:
    date: date
    symbol: str
    asset: str
    side: str
    qty: float
    price: float
    notional: float
    meta: Dict = field(default_factory=dict)

class Backtester:
    def __init__(self, under: str, provider_u, provider_o,
                 start: date, end: date, cash0: float = INITIAL_CASH, strike_pct=OPT_STRIKE_PRICE_PCT_TARGET,
                 min_opt_vol=MIN_OPTIONS_VOL, consec=CONSECUTIVE_PERIODS, sma_len=SMA_LEN,
                 sd_abs_pct=SD_ABS_THRESH_PCT, cash_stock_pct=CASH_INVEST_STOCK_PCT,
                 cash_opt_pct=CASH_INVEST_OPTION_PCT, momentum_decr_pct=MOMENTUM_DECR_PCT,
                 sector_confirm=SECTOR_CONFIRM, sector_symbol: Optional[str]=None):
        self.symbol = under.upper()
        self.pu = provider_u
        self.po = provider_o
        self.start = start
        self.end = end
        self.cash = float(cash0)
        self.pos = Position()
        self.ledger: List[Trade] = []
        self.equity_series: List[Tuple[date, float]] = []

        self.strike_pct = strike_pct
        self.min_opt_vol = int(min_opt_vol)
        self.consec = int(consec)
        self.sma_len = int(sma_len)
        self.sd_abs_pct = float(sd_abs_pct)
        self.cash_stock_pct = float(cash_stock_pct)
        self.cash_opt_pct = float(cash_opt_pct)
        self.momentum_decr_pct = float(momentum_decr_pct)
        self.sector_confirm = bool(sector_confirm)
        self.sector_symbol = sector_symbol

        self.df = self.pu.get_daily(self.symbol, self.start - timedelta(days=200), self.end + timedelta(days=2))
        if self.df.empty:
            raise SystemExit(f"No underlying data for {self.symbol}")
        self.df = self.df.drop_duplicates("date").sort_values("date").reset_index(drop=True)

        if self.sector_confirm and sector_symbol:
            self.df_sector = self.pu.get_daily(sector_symbol, self.start - timedelta(days=200), self.end + timedelta(days=2))
        else:
            self.df_sector = pd.DataFrame()

    def pick_occ(self, day: date, last_px: float, cp: str) -> Optional[str]:
        target = last_px * (1 + self.strike_pct if cp=="CALL" else 1 - self.strike_pct)
        expiry = next_friday_after_t_plus_2(day)
        candidates = []
        for off in range(0, 11):
            for sgn in (+1, -1):
                strike = max(0.5, round(target + sgn*off, 2))
                occ = occ_symbol(self.symbol, expiry, "C" if cp=="CALL" else "P", strike)
                candidates.append((abs(strike-target), strike, occ))
        candidates.sort(key=lambda x: x[0])
        for _, strike, occ in candidates:
            bar = self.po.get_day_bar(occ, day)
            if not bar: continue
            vol = int(bar.get("volume", 0))
            if vol >= self.min_opt_vol and np.isfinite(bar.get("close", np.nan)):
                return occ
        return None

    def price_occ(self, occ: str, day: date) -> Optional[float]:
        bar = self.po.get_day_bar(occ, day)
        if not bar: return None
        px = bar.get("close", None)
        return float(px) if px is not None and np.isfinite(px) else None

    def sector_trend(self, day_idx: int) -> int:
        if self.df_sector.empty or day_idx < 2:
            return 0
        closes = self.df_sector.loc[:day_idx, "close"].tail(5).tolist()
        ups = sum(1 for a,b in zip(closes[:-1], closes[1:]) if b>a)
        downs = sum(1 for a,b in zip(closes[:-1], closes[1:]) if b<a)
        return 1 if ups>downs else (-1 if downs>ups else 0)

    def mtm_equity(self, d: date, idx: int) -> float:
        close = float(self.df.loc[idx, "close"])
        eq = self.cash + self.pos.qty_stock * close
        for occ, qty in self.pos.options.items():
            px = self.price_occ(occ, d)
            if px is not None:
                self.pos.last_prices[occ] = px
            px_use = self.pos.last_prices.get(occ, 0.0)
            eq += qty * px_use * 100.0
        return eq

    def trade_stock(self, d: date, price: float, dollars: float, side: str):
        if dollars <= 0: return
        qty = dollars / price
        if side == "buy":
            self.cash -= dollars
            self.pos.qty_stock += qty
        else:
            sell_qty = min(qty, self.pos.qty_stock)
            proceeds = sell_qty * price
            self.cash += proceeds
            self.pos.qty_stock -= sell_qty
            qty = sell_qty
        self.ledger.append(Trade(d, self.symbol, "stock", side, qty, price, qty*price))

    def trade_option(self, d: date, occ: str, price: float, dollars: float, side: str):
        if dollars <= 0 or price <= 0: return
        contracts = max(1, int(dollars // (price*100.0)))
        notional = contracts * price * 100.0
        if side == "buy":
            if self.cash < notional: return
            self.cash -= notional
            self.pos.options[occ] = self.pos.options.get(occ, 0) + contracts
        else:
            have = self.pos.options.get(occ, 0)
            if have <= 0: return
            sell_qty = min(have, contracts)
            proceeds = sell_qty * price * 100.0
            self.cash += proceeds
            left = have - sell_qty
            if left>0: self.pos.options[occ] = left
            else: self.pos.options.pop(occ, None)
            contracts = sell_qty
        self.ledger.append(Trade(d, self.symbol, occ, side, contracts, price, notional, {"multiplier":100}))

    def run(self):
        df = self.df[(self.df["date"]>=self.start) & (self.df["date"]<=self.end)].reset_index(drop=True)
        if len(df) < self.sma_len + 5:
            print("Warning: short history window.")
        closes = self.df["close"].values
        sma = pd.Series(closes).rolling(self.sma_len).mean().values
        sdv = pd.Series(closes).rolling(self.sma_len).std(ddof=0).values

        price_window: List[float] = []
        for i in range(len(df)-1):
            day_idx = self.df.index[self.df["date"]==df.loc[i,"date"]][0]
            today = df.loc[i, "date"]
            open_next = float(df.loc[i+1, "open"])
            last_close = float(self.df.loc[day_idx, "close"])
            sma21 = float(sma[day_idx]) if not math.isnan(sma[day_idx]) else None
            sd21  = float(sdv[day_idx]) if not math.isnan(sdv[day_idx]) else None

            price_window.append(last_close)
            if len(price_window) > self.consec + 3:
                price_window = price_window[-(self.consec+3):]

            moves = []
            for a,b in zip(price_window[:-1], price_window[1:]):
                if b>a: moves.append(1)
                elif b<a: moves.append(-1)
                else: moves.append(0)
            rising = len(moves)>=self.consec and all(m==1 for m in moves[-self.consec:])
            falling= len(moves)>=self.consec and all(m==-1 for m in moves[-self.consec:])

            above_plus_sd = (sma21 is not None and sd21 is not None and last_close > sma21 + sd21 and
                             (sma21<=0 or abs((last_close - sma21)/sma21) >= self.sd_abs_pct))
            below_minus_sd= (sma21 is not None and sd21 is not None and last_close < sma21 - sd21 and
                             (sma21<=0 or abs((last_close - sma21)/sma21) >= self.sd_abs_pct))

            st = self.sector_trend(self.df.index[self.df["date"]==df.loc[i,"date"]][0]) if self.sector_confirm else 0
            sector_falling = (st==-1); sector_rising = (st==+1)

            dec_mom = False
            if len(price_window) >= 4:
                deltas = [b-a for a,b in zip(price_window[:-1], price_window[1:])]
                m_now, m_prev = abs(deltas[-1]), abs(deltas[-2])
                if m_prev > 0 and (m_prev - m_now)/m_prev >= self.momentum_decr_pct:
                    dec_mom = True

            if falling and (above_plus_sd or sector_falling):
                for occ in list(self.pos.options.keys()):
                    if "C" in occ[len(self.symbol):len(self.symbol)+7]:
                        px = self.price_occ(occ, df.loc[i+1, "date"]) or 0.0
                        if px>0: self.trade_option(df.loc[i+1,"date"], occ, px, 1e12, "sell")
                occp = self.pick_occ(today, last_close, "PUT")
                if occp:
                    pxp = self.price_occ(occp, df.loc[i+1, "date"]) or 0.0
                    self.trade_option(df.loc[i+1,"date"], occp, pxp, self.cash * self.cash_opt_pct, "buy")

            if rising and (below_minus_sd or sector_rising):
                for occ in list(self.pos.options.keys()):
                    if "P" in occ[len(self.symbol):len(self.symbol)+7]:
                        px = self.price_occ(occ, df.loc[i+1, "date"]) or 0.0
                        if px>0: self.trade_option(df.loc[i+1,"date"], occ, px, 1e12, "sell")
                occc = self.pick_occ(today, last_close, "CALL")
                if occc:
                    pxc = self.price_occ(occc, df.loc[i+1, "date"]) or 0.0
                    self.trade_option(df.loc[i+1,"date"], occc, pxc, self.cash * self.cash_opt_pct, "buy")
                self.trade_stock(df.loc[i+1,"date"], open_next, self.cash * self.cash_stock_pct, "buy")

            if dec_mom:
                last_move = moves[-1] if moves else 0
                if last_move > 0:
                    occc = self.pick_occ(today, last_close, "CALL")
                    if occc:
                        pxc = self.price_occ(occc, df.loc[i+1,"date"]) or 0.0
                        self.trade_option(df.loc[i+1,"date"], occc, pxc, self.cash * (self.cash_opt_pct*0.5), "buy")
                elif last_move < 0:
                    occp = self.pick_occ(today, last_close, "PUT")
                    if occp:
                        pxp = self.price_occ(occp, df.loc[i+1,"date"]) or 0.0
                        self.trade_option(df.loc[i+1,"date"], occp, pxp, self.cash * (self.cash_opt_pct*0.5), "buy")

            if len(moves)>=2 and ((moves[-2]==1 and moves[-1]==-1) or (moves[-2]==-1 and moves[-1]==1)):
                for occ in list(self.pos.options.keys()):
                    px = self.price_occ(occ, df.loc[i+1, "date"]) or 0.0
                    if px>0: self.trade_option(df.loc[i+1,"date"], occ, px, 1e12, "sell")
                if self.pos.qty_stock > 0:
                    dollars = (self.pos.qty_stock*open_next) * 0.5
                    self.trade_stock(df.loc[i+1,"date"], open_next, dollars, "sell")

            eq = self.mtm_equity(today, self.df.index[self.df["date"]==today][0])
            self.equity_series.append((today, eq))

        last_day = df.loc[len(df)-1, "date"]
        last_idx = self.df.index[self.df["date"]==last_day][0]
        self.equity_series.append((last_day, self.mtm_equity(last_day, last_idx)))

    def results(self, outdir: Path):
        outdir.mkdir(parents=True, exist_ok=True)
        tdf = pd.DataFrame([t.__dict__ for t in self.ledger])
        if not tdf.empty:
            tdf.to_csv(outdir / "trades.csv", index=False)
        edf = pd.DataFrame(self.equity_series, columns=["date","equity"])
        edf.to_csv(outdir / "equity.csv", index=False)

        if len(edf) > 2:
            rets = edf["equity"].pct_change().fillna(0.0)
            total_ret = edf["equity"].iloc[-1] / edf["equity"].iloc[0] - 1.0
            cagr = (1+total_ret) ** (252/ max(1, len(edf))) - 1.0
            dd = max_drawdown(edf["equity"])
            sharpe = sharpe_ratio(rets)
            wins = 0; losses = 0
            if not tdf.empty:
                grouped = tdf.groupby("asset")
                for asset, g in grouped:
                    buys = g[g["side"]=="buy"]["notional"].sum()
                    sells= g[g["side"]=="sell"]["notional"].sum()
                    if sells > buys: wins += 1
                    elif sells < buys: losses += 1
            summary = {
                "start": str(self.start),
                "end": str(self.end),
                "init_cash": INITIAL_CASH,
                "final_equity": float(edf["equity"].iloc[-1]),
                "total_return_pct": float(total_ret*100),
                "CAGR_pct": float(cagr*100),
                "max_drawdown_pct": float(dd*100),
                "sharpe": float(sharpe),
                "wins": int(wins),
                "losses": int(losses),
                "num_trades": int(len(tdf)),
            }
        else:
            summary = {"note":"not enough data to compute metrics"}
        pd.DataFrame([summary]).to_csv(outdir / "summary.csv", index=False)
        return summary

def main():
    p = argparse.ArgumentParser(description="Full options backtester (Alpaca or CSV).")
    p.add_argument("--symbol", default="AAPL")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--cash", type=float, default=INITIAL_CASH)
    p.add_argument("--provider", choices=["alpaca","csv"], default="alpaca" if HAVE_ALPACA else "csv")
    p.add_argument("--data-root", default="data", help="CSV root when provider=csv")
    p.add_argument("--sector-symbol", default=None, help="Optional sector ETF symbol for confirmation (e.g., XLK)")
    p.add_argument("--out", default="bt_out")
    args = p.parse_args()

    start = to_date(args.start); end = to_date(args.end)
    if start >= end:
        raise SystemExit("start must be < end")

    if args.provider=="alpaca":
        if not HAVE_ALPACA:
            raise SystemExit("Alpaca option data not available or keys missing. Use --provider csv.")
        ALPACA_KEY = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY_ID")
        ALPACA_SEC = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
        prov = AlpacaProvider(ALPACA_KEY, ALPACA_SEC)
    else:
        prov = CSVProvider(Path(args.data_root))

    bt = Backtester(
        under=args.symbol,
        provider_u=prov,
        provider_o=prov,
        start=start, end=end, cash0=args.cash,
        strike_pct=OPT_STRIKE_PRICE_PCT_TARGET, min_opt_vol=MIN_OPTIONS_VOL,
        consec=CONSECUTIVE_PERIODS, sma_len=SMA_LEN, sd_abs_pct=SD_ABS_THRESH_PCT,
        cash_stock_pct=CASH_INVEST_STOCK_PCT, cash_opt_pct=CASH_INVEST_OPTION_PCT,
        momentum_decr_pct=MOMENTUM_DECR_PCT,
        sector_confirm=SECTOR_CONFIRM, sector_symbol=args.sector_symbol
    )
    bt.run()
    summary = bt.results(Path(args.out))
    print("Backtest complete. Summary:")
    for k,v in summary.items():
        print(f"  {k}: {v}")
    print(f"Artifacts written to: {args.out}/ (trades.csv, equity.csv, summary.csv)")

if __name__ == "__main__":
    main()
