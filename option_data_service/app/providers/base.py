from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List


class ProviderNotConfiguredError(Exception):
    """Raised when a provider is invoked without the credentials/config it needs."""


class MarketDataProvider(ABC):
    """Common interface every vendor feed (Yahoo, Bloomberg, CBOE, Schwab, ...) implements.
    Each fetch_* method returns plain dicts shaped for the matching service in app/services/
    to resolve into Symbol/OptionContract rows and insert - the DB layer never talks to a
    vendor SDK directly."""

    source_code: str

    @abstractmethod
    def fetch_option_quotes(self, symbol: str) -> List[Dict]:
        """Current option chain for `symbol`. Each row: symbol, expiration (YYYY-MM-DD),
        strike, option_type ('call'/'put'), bid, ask, last_price, volume, and optionally
        open_interest/implied_volatility/delta/gamma/theta/vega/rho."""
        raise NotImplementedError

    def fetch_price_bars(self, symbol: str, interval: str, start: date, end: date) -> List[Dict]:
        """OHLCV bars for `symbol` between start/end. Each row: bar_time (datetime), open,
        high, low, close, adj_close, volume."""
        raise NotImplementedError(f"{self.source_code} provider does not implement fetch_price_bars")

    def fetch_stock_ticks(self, symbol: str, start: datetime, end: datetime) -> List[Dict]:
        """Raw trade/quote ticks for `symbol`. Each row: tick_time, tick_type ('trade'/
        'quote'), price, size, bid, ask, exchange, conditions."""
        raise NotImplementedError(f"{self.source_code} provider does not implement fetch_stock_ticks")

    def fetch_option_ticks(self, contract_symbol: str, start: datetime, end: datetime) -> List[Dict]:
        """Raw trade/quote ticks for one vendor-native option contract symbol. Same row shape
        as fetch_stock_ticks."""
        raise NotImplementedError(f"{self.source_code} provider does not implement fetch_option_ticks")

    def fetch_corporate_actions(self, symbols: List[str], start: date, end: date) -> Dict[str, Dict[str, List[Dict]]]:
        """Splits/dividends for multiple symbols in one call. Returns
        {ticker: {'splits': [{'effective_date','ratio_from','ratio_to'}, ...],
                  'dividends': [{'effective_date','amount','currency'}, ...]}}."""
        raise NotImplementedError(f"{self.source_code} provider does not implement fetch_corporate_actions")
