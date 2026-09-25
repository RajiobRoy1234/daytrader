from datetime import date, datetime, timezone
from typing import Dict, List

from app.providers.base import MarketDataProvider


class FakeProvider(MarketDataProvider):
    """Canned in-memory provider so tests don't depend on a real vendor's network/API."""

    source_code = "fake"

    def fetch_option_quotes(self, symbol: str) -> List[Dict]:
        return [
            {
                "symbol": symbol,
                "expiration": "2026-08-21",
                "strike": 450.0,
                "option_type": "call",
                "bid": 10.1,
                "ask": 10.3,
                "last_price": 10.2,
                "volume": 123,
            },
            {
                "symbol": symbol,
                "expiration": "2026-08-21",
                "strike": 450.0,
                "option_type": "put",
                "bid": 5.1,
                "ask": 5.3,
                "last_price": 5.2,
                "volume": 45,
            },
        ]

    def fetch_price_bars(self, symbol: str, interval: str, start: date, end: date) -> List[Dict]:
        return [
            {
                "bar_time": datetime(2026, 7, 20, tzinfo=timezone.utc),
                "open": 440.0,
                "high": 445.0,
                "low": 438.0,
                "close": 442.0,
                "adj_close": 442.0,
                "volume": 1_000_000,
            },
        ]

    def fetch_stock_ticks(self, symbol: str, start: datetime, end: datetime) -> List[Dict]:
        return [
            {"tick_time": start, "tick_type": "trade", "price": 441.5, "size": 100, "exchange": "XNAS"},
        ]

    def fetch_option_ticks(self, contract_symbol: str, start: datetime, end: datetime) -> List[Dict]:
        return [
            {"tick_time": start, "tick_type": "trade", "price": 10.2, "size": 5, "exchange": "CBOE"},
        ]
