import base64
import os
from datetime import date, datetime
from typing import Dict, List

import requests

from .base import MarketDataProvider, ProviderNotConfiguredError

# Verified against Schwab's public developer docs (developer.schwab.com) at the time this was
# written: OAuth endpoints and the /marketdata/v1 base are stable, but request/response field
# names can shift with your app's entitlements - check the portal if a call 4xxs.
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
MARKET_DATA_BASE_URL = os.getenv("SCHWAB_MARKET_DATA_BASE_URL", "https://api.schwabapi.com/marketdata/v1")

# Schwab's pricehistory endpoint buckets by (periodType, frequencyType, frequency) rather than
# a free interval string; this maps our generic interval onto the closest supported bucket.
_FREQUENCY_MAP = {
    "1m": ("minute", 1),
    "5m": ("minute", 5),
    "30m": ("minute", 30),
    "1d": ("daily", 1),
}


class SchwabProvider(MarketDataProvider):
    """Charles Schwab Trader API. Requires a registered app and a refresh token obtained once
    via the OAuth authorization-code flow (SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET /
    SCHWAB_REFRESH_TOKEN env vars) - access tokens expire every 30 minutes and are refreshed
    here automatically; the refresh token itself expires every 7 days and must be
    re-authorized out of band (there is no way to automate that step headlessly).

    The Trader API exposes quotes/chains/price history but not a raw historical-tick
    download, so fetch_stock_ticks/fetch_option_ticks are left unimplemented - real-time
    ticks come from Schwab's separate streaming endpoint, not this REST client."""

    source_code = "schwab"

    def __init__(self):
        self.client_id = os.getenv("SCHWAB_CLIENT_ID")
        self.client_secret = os.getenv("SCHWAB_CLIENT_SECRET")
        self.refresh_token = os.getenv("SCHWAB_REFRESH_TOKEN")

    def _auth_headers(self) -> Dict[str, str]:
        if not (self.client_id and self.client_secret and self.refresh_token):
            raise ProviderNotConfiguredError(
                "Set SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, and SCHWAB_REFRESH_TOKEN. "
                "Register an app at https://developer.schwab.com/dashboard/apps and complete "
                "the OAuth authorization-code flow once to obtain a refresh token."
            )
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = requests.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": self.refresh_token},
            timeout=10,
        )
        response.raise_for_status()
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def fetch_option_quotes(self, symbol: str) -> List[Dict]:
        headers = self._auth_headers()
        response = requests.get(f"{MARKET_DATA_BASE_URL}/chains", headers=headers, params={"symbol": symbol}, timeout=10)
        response.raise_for_status()
        payload = response.json()

        rows: List[Dict] = []
        for map_key, option_type in (("callExpDateMap", "call"), ("putExpDateMap", "put")):
            for expiration_key, strikes in payload.get(map_key, {}).items():
                expiration = expiration_key.split(":")[0]  # Schwab returns "YYYY-MM-DD:daysToExpiration"
                for strike, contracts in strikes.items():
                    for contract in contracts:
                        rows.append({
                            "symbol": symbol,
                            "expiration": expiration,
                            "strike": float(strike),
                            "option_type": option_type,
                            "bid": contract.get("bid"),
                            "ask": contract.get("ask"),
                            "last_price": contract.get("last"),
                            "volume": contract.get("totalVolume"),
                            "open_interest": contract.get("openInterest"),
                            "implied_volatility": contract.get("volatility"),
                            "delta": contract.get("delta"),
                            "gamma": contract.get("gamma"),
                            "theta": contract.get("theta"),
                            "vega": contract.get("vega"),
                            "rho": contract.get("rho"),
                        })
        return rows

    def fetch_price_bars(self, symbol: str, interval: str, start: date, end: date) -> List[Dict]:
        if interval not in _FREQUENCY_MAP:
            raise ValueError(f"schwab provider does not support interval {interval!r} (supported: {sorted(_FREQUENCY_MAP)})")
        frequency_type, frequency = _FREQUENCY_MAP[interval]
        headers = self._auth_headers()
        response = requests.get(
            f"{MARKET_DATA_BASE_URL}/pricehistory",
            headers=headers,
            params={
                "symbol": symbol,
                "periodType": "day" if frequency_type == "minute" else "year",
                "frequencyType": frequency_type,
                "frequency": frequency,
                "startDate": int(datetime(start.year, start.month, start.day).timestamp() * 1000),
                "endDate": int(datetime(end.year, end.month, end.day).timestamp() * 1000),
            },
            timeout=10,
        )
        response.raise_for_status()
        return [
            {
                "bar_time": datetime.fromtimestamp(candle["datetime"] / 1000),
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
                "adj_close": candle.get("close"),
                "volume": candle.get("volume"),
            }
            for candle in response.json().get("candles", [])
        ]
