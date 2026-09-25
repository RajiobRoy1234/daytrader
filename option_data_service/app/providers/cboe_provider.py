import os
from typing import Dict, List

import requests

from .base import MarketDataProvider, ProviderNotConfiguredError

# Cboe DataShop's "All Access API" is hosted at api.livevol.com; full endpoint reference is at
# https://api.livevol.com/v1/docs/Help?apiGroupName=allaccess (subscription required to view).
# The base URL and Basic-auth scheme below are documented; the option-chain path is
# subscription-specific, so it's left as a required env var rather than guessed here - copy
# it from the docs above once you have DataShop access.
BASE_URL = os.getenv("CBOE_API_BASE_URL", "https://api.livevol.com/v1")


class CBOEProvider(MarketDataProvider):
    """Cboe DataShop All Access API. Requires CBOE_API_USERNAME/CBOE_API_PASSWORD (HTTP Basic
    auth, per your DataShop subscription) and CBOE_OPTION_CHAIN_PATH - the exact path depends
    on which DataShop product you're subscribed to, so it isn't hardcoded here; find it at
    https://api.livevol.com/v1/docs/Help?apiGroupName=allaccess."""

    source_code = "cboe"

    def __init__(self):
        self.username = os.getenv("CBOE_API_USERNAME")
        self.password = os.getenv("CBOE_API_PASSWORD")
        self.option_chain_path = os.getenv("CBOE_OPTION_CHAIN_PATH")

    def _require_config(self):
        if not (self.username and self.password):
            raise ProviderNotConfiguredError("Set CBOE_API_USERNAME and CBOE_API_PASSWORD for your DataShop subscription.")
        if not self.option_chain_path:
            raise ProviderNotConfiguredError(
                "Set CBOE_OPTION_CHAIN_PATH to the option-chain endpoint path for your DataShop "
                "product (see https://api.livevol.com/v1/docs/Help?apiGroupName=allaccess)."
            )

    def fetch_option_quotes(self, symbol: str) -> List[Dict]:
        self._require_config()
        response = requests.get(
            f"{BASE_URL}{self.option_chain_path}",
            auth=(self.username, self.password),
            params={"symbol": symbol},
            timeout=10,
        )
        response.raise_for_status()
        # Response shape is subscription-specific (equity options vs. index options vs.
        # multi-asset feeds return different envelopes) - adapt this mapping to match yours.
        rows: List[Dict] = []
        for item in response.json().get("options", []):
            rows.append({
                "symbol": symbol,
                "expiration": item["expiration"],
                "strike": float(item["strike"]),
                "option_type": "call" if item.get("option_type", "").lower().startswith("c") else "put",
                "bid": item.get("bid"),
                "ask": item.get("ask"),
                "last_price": item.get("last"),
                "volume": item.get("volume"),
                "open_interest": item.get("open_interest"),
                "implied_volatility": item.get("iv"),
                "delta": item.get("delta"),
                "gamma": item.get("gamma"),
                "theta": item.get("theta"),
                "vega": item.get("vega"),
            })
        return rows
