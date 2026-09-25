import os
from datetime import date, datetime
from typing import Dict, List

import requests

from .base import MarketDataProvider, ProviderNotConfiguredError

_SANDBOX_URL = "https://sandbox.tradier.com/v1"
_PRODUCTION_URL = "https://api.tradier.com/v1"
BASE_URL = os.getenv("TRADIER_BASE_URL") or (
    _PRODUCTION_URL if os.getenv("TRADIER_ENV", "sandbox") == "production" else _SANDBOX_URL
)

_HISTORY_INTERVALS = {"1d": "daily"}
_TIMESALES_INTERVALS = {"1m": "1min", "5m": "5min", "15m": "15min"}


def _as_list(value) -> List:
    """Tradier collapses a single-item array to a bare object in JSON responses (a well-known
    quirk of this API) - normalize both shapes to a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class TradierProvider(MarketDataProvider):
    """Tradier Brokerage API. TRADIER_ACCESS_TOKEN can be a free Sandbox token - sign up at
    tradier.com and generate one instantly at https://web.tradier.com/user/api, no approval
    wait, delayed data. Sandbox is the default; set TRADIER_ENV=production once you have a
    funded account and a production token for real-time data.

    The REST API doesn't expose historical tick-by-tick trade data, so
    fetch_stock_ticks/fetch_option_ticks are left unimplemented."""

    source_code = "tradier"

    def __init__(self):
        self.token = os.getenv("TRADIER_ACCESS_TOKEN")

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise ProviderNotConfiguredError(
                "Set TRADIER_ACCESS_TOKEN. Sign up free at tradier.com, then generate a "
                "Sandbox token instantly at https://web.tradier.com/user/api - no approval wait."
            )
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    def _get(self, path: str, params: dict) -> dict:
        response = requests.get(f"{BASE_URL}{path}", headers=self._headers(), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def fetch_option_quotes(self, symbol: str) -> List[Dict]:
        expirations_payload = self._get("/markets/options/expirations", {"symbol": symbol})
        expirations = _as_list((expirations_payload.get("expirations") or {}).get("date"))

        rows: List[Dict] = []
        for expiration in expirations[:3]:
            payload = self._get("/markets/options/chains", {"symbol": symbol, "expiration": expiration, "greeks": "true"})
            for option in _as_list((payload.get("options") or {}).get("option")):
                greeks = option.get("greeks") or {}
                rows.append({
                    "symbol": symbol,
                    "expiration": expiration,
                    "strike": float(option["strike"]),
                    "option_type": option["option_type"],
                    "bid": option.get("bid"),
                    "ask": option.get("ask"),
                    "last_price": option.get("last"),
                    "volume": option.get("volume"),
                    "open_interest": option.get("open_interest"),
                    "implied_volatility": greeks.get("mid_iv") or greeks.get("smv_vol"),
                    "delta": greeks.get("delta"),
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "vega": greeks.get("vega"),
                })
        return rows

    def fetch_price_bars(self, symbol: str, interval: str, start: date, end: date) -> List[Dict]:
        if interval in _HISTORY_INTERVALS:
            payload = self._get("/markets/history", {
                "symbol": symbol,
                "interval": _HISTORY_INTERVALS[interval],
                "start": start.isoformat(),
                "end": end.isoformat(),
            })
            days = _as_list((payload.get("history") or {}).get("day"))
            return [
                {
                    "bar_time": datetime.fromisoformat(day["date"]),
                    "open": day.get("open"),
                    "high": day.get("high"),
                    "low": day.get("low"),
                    "close": day.get("close"),
                    "adj_close": day.get("close"),
                    "volume": day.get("volume"),
                }
                for day in days
            ]
        if interval in _TIMESALES_INTERVALS:
            payload = self._get("/markets/timesales", {
                "symbol": symbol,
                "interval": _TIMESALES_INTERVALS[interval],
                "start": start.strftime("%Y-%m-%d %H:%M"),
                "end": end.strftime("%Y-%m-%d %H:%M"),
            })
            series = _as_list((payload.get("series") or {}).get("data"))
            return [
                {
                    "bar_time": datetime.fromisoformat(bar["time"]),
                    "open": bar.get("open"),
                    "high": bar.get("high"),
                    "low": bar.get("low"),
                    "close": bar.get("close"),
                    "adj_close": bar.get("close"),
                    "volume": bar.get("volume"),
                }
                for bar in series
            ]
        supported = sorted({**_HISTORY_INTERVALS, **_TIMESALES_INTERVALS})
        raise ValueError(f"tradier provider does not support interval {interval!r} (supported: {supported})")
