import os
from typing import List, Dict
import yfinance as yf


class YahooOptionsProvider:
    def __init__(self, symbol: str | None = None):
        self.symbol = symbol or os.getenv("OPTION_SYMBOL", "SPY")

    def fetch_quotes(self) -> List[Dict]:
        ticker = yf.Ticker(self.symbol)
        expirations = ticker.options
        if not expirations:
            return []

        rows: List[Dict] = []
        for expiration in expirations[:3]:
            option_chain = ticker.option_chain(expiration)
            calls = option_chain.calls
            puts = option_chain.puts
            for row in calls.itertuples(index=False):
                rows.append({
                    "symbol": self.symbol,
                    "expiration": expiration,
                    "strike": float(row.strike),
                    "option_type": "call",
                    "bid": float(row.bid) if row.bid else None,
                    "ask": float(row.ask) if row.ask else None,
                    "last_price": float(row.lastPrice) if row.lastPrice else None,
                    "volume": int(row.volume) if row.volume else 0,
                })
            for row in puts.itertuples(index=False):
                rows.append({
                    "symbol": self.symbol,
                    "expiration": expiration,
                    "strike": float(row.strike),
                    "option_type": "put",
                    "bid": float(row.bid) if row.bid else None,
                    "ask": float(row.ask) if row.ask else None,
                    "last_price": float(row.lastPrice) if row.lastPrice else None,
                    "volume": int(row.volume) if row.volume else 0,
                })
        return rows
