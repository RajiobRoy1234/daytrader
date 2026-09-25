import os
from datetime import date, datetime
from typing import Dict, List
import pandas as pd
import yfinance as yf

from .base import MarketDataProvider


class YahooOptionsProvider(MarketDataProvider):
    source_code = "yahoo"

    def __init__(self, symbol: str | None = None):
        self.symbol = symbol or os.getenv("OPTION_SYMBOL", "SPY")

    def fetch_option_quotes(self, symbol: str | None = None) -> List[Dict]:
        symbol = symbol or self.symbol
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        if not expirations:
            return []

        rows: List[Dict] = []
        for expiration in expirations[:3]:
            option_chain = ticker.option_chain(expiration)
            for option_type, chain in (("call", option_chain.calls), ("put", option_chain.puts)):
                for row in chain.itertuples(index=False):
                    rows.append({
                        "symbol": symbol,
                        "expiration": expiration,
                        "strike": float(row.strike),
                        "option_type": option_type,
                        "bid": float(row.bid) if row.bid else None,
                        "ask": float(row.ask) if row.ask else None,
                        "last_price": float(row.lastPrice) if row.lastPrice else None,
                        "volume": int(row.volume) if row.volume else 0,
                    })
        return rows

    def fetch_price_bars(self, symbol: str, interval: str, start: date, end: date) -> List[Dict]:
        # yfinance uses the same interval spelling we do ('1d', '1h', '5m', '1m', ...); Yahoo
        # itself limits how far back intraday intervals go (e.g. ~7 days for '1m').
        history = yf.Ticker(symbol).history(start=start, end=end, interval=interval)
        return [
            {
                "bar_time": row.Index.to_pydatetime() if hasattr(row.Index, "to_pydatetime") else datetime.combine(row.Index, datetime.min.time()),
                "open": float(row.Open) if pd.notna(row.Open) else None,
                "high": float(row.High) if pd.notna(row.High) else None,
                "low": float(row.Low) if pd.notna(row.Low) else None,
                "close": float(row.Close) if pd.notna(row.Close) else None,
                "adj_close": float(row.Close) if pd.notna(row.Close) else None,
                "volume": int(row.Volume) if pd.notna(row.Volume) else None,
            }
            for row in history.itertuples(index=True)
        ]
