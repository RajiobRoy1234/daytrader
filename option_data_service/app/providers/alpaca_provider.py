import os
from datetime import date, datetime
from typing import Dict, List

import requests

from .base import MarketDataProvider, ProviderNotConfiguredError
from .occ import parse_occ_symbol

DATA_BASE_URL = os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets")

_TIMEFRAME_MAP = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1h": "1Hour", "1d": "1Day"}
_CORPORATE_ACTIONS_BATCH_SIZE = 50


class AlpacaProvider(MarketDataProvider):
    """Alpaca Market Data API. Free with a paper-trading account - sign up by email only (no
    approval wait) at https://alpaca.markets/ and generate ALPACA_API_KEY_ID/
    ALPACA_API_SECRET_KEY from the dashboard. Market data endpoints are shared between paper
    and live accounts.

    fetch_option_quotes returns a live snapshot (option contract symbols are parsed with the
    standard OCC format via occ.py, since that's more reliable than depending on exact response
    field casing). Alpaca's option/stock endpoints return current snapshots and historical
    bars, not a raw historical tick stream, so fetch_stock_ticks/fetch_option_ticks are left
    unimplemented."""

    source_code = "alpaca"

    def __init__(self):
        self.key_id = os.getenv("ALPACA_API_KEY_ID")
        self.secret_key = os.getenv("ALPACA_API_SECRET_KEY")

    def _headers(self) -> Dict[str, str]:
        if not (self.key_id and self.secret_key):
            raise ProviderNotConfiguredError(
                "Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY. Sign up free (paper trading, "
                "no approval wait) at https://alpaca.markets/ and generate keys from the dashboard."
            )
        return {"APCA-API-KEY-ID": self.key_id, "APCA-API-SECRET-KEY": self.secret_key}

    def fetch_option_quotes(self, symbol: str) -> List[Dict]:
        rows: List[Dict] = []
        page_token = None
        while True:
            params = {"feed": "indicative"}
            if page_token:
                params["page_token"] = page_token
            response = requests.get(
                f"{DATA_BASE_URL}/v1beta1/options/snapshots/{symbol}",
                headers=self._headers(), params=params, timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            for contract_symbol, snapshot in payload.get("snapshots", {}).items():
                try:
                    contract = parse_occ_symbol(contract_symbol)
                except ValueError:
                    continue
                # Field casing (latestQuote/latestTrade vs latest_quote/latest_trade, etc.) can
                # drift between Alpaca API versions - verify against a live response and adjust
                # these .get() keys if a field always comes back None.
                quote = snapshot.get("latestQuote") or snapshot.get("latest_quote") or {}
                trade = snapshot.get("latestTrade") or snapshot.get("latest_trade") or {}
                greeks = snapshot.get("greeks") or {}
                rows.append({
                    "symbol": symbol,
                    "expiration": contract.expiration.isoformat(),
                    "strike": contract.strike,
                    "option_type": contract.option_type,
                    "bid": quote.get("bp"),
                    "ask": quote.get("ap"),
                    "last_price": trade.get("p"),
                    "volume": trade.get("s"),
                    "implied_volatility": greeks.get("impliedVolatility") or greeks.get("iv"),
                    "delta": greeks.get("delta"),
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "vega": greeks.get("vega"),
                    "rho": greeks.get("rho"),
                })
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return rows

    def fetch_corporate_actions(self, symbols: List[str], start: date, end: date) -> Dict[str, Dict[str, List[Dict]]]:
        results: Dict[str, Dict[str, List[Dict]]] = {s: {"splits": [], "dividends": []} for s in symbols}

        # Batch to keep the `symbols` query param (and URL) a reasonable size.
        for batch_start in range(0, len(symbols), _CORPORATE_ACTIONS_BATCH_SIZE):
            batch = symbols[batch_start:batch_start + _CORPORATE_ACTIONS_BATCH_SIZE]
            page_token = None
            while True:
                params = {
                    "symbols": ",".join(batch),
                    "types": "forward_split,reverse_split,cash_dividend",
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }
                if page_token:
                    params["page_token"] = page_token
                response = requests.get(
                    f"{DATA_BASE_URL}/v1/corporate-actions", headers=self._headers(), params=params, timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
                actions = payload.get("corporate_actions") or {}

                # Field names below follow Alpaca's documented corporate-actions announcement
                # shape (grouped by type: forward_splits/reverse_splits/cash_dividends, each
                # entry carrying symbol/old_rate/new_rate/process_date or symbol/rate/ex_date) -
                # verify against a live response and adjust if a group comes back consistently
                # empty for a symbol you know had an action in this window.
                for split in (actions.get("forward_splits") or []) + (actions.get("reverse_splits") or []):
                    symbol = split.get("symbol")
                    old_rate, new_rate = split.get("old_rate"), split.get("new_rate")
                    effective = split.get("process_date") or split.get("ex_date")
                    if symbol in results and old_rate and new_rate and effective:
                        results[symbol]["splits"].append({
                            "effective_date": date.fromisoformat(effective),
                            "ratio_from": old_rate,
                            "ratio_to": new_rate,
                        })

                for dividend in actions.get("cash_dividends") or []:
                    symbol = dividend.get("symbol")
                    rate = dividend.get("rate")
                    effective = dividend.get("ex_date") or dividend.get("payable_date")
                    if symbol in results and rate and effective:
                        results[symbol]["dividends"].append({
                            "effective_date": date.fromisoformat(effective),
                            "amount": float(rate),
                            "currency": dividend.get("currency", "USD"),
                        })

                page_token = payload.get("next_page_token")
                if not page_token:
                    break

        return results

    def fetch_price_bars(self, symbol: str, interval: str, start: date, end: date) -> List[Dict]:
        if interval not in _TIMEFRAME_MAP:
            raise ValueError(f"alpaca provider does not support interval {interval!r} (supported: {sorted(_TIMEFRAME_MAP)})")

        rows: List[Dict] = []
        page_token = None
        while True:
            params = {
                "symbols": symbol,
                "timeframe": _TIMEFRAME_MAP[interval],
                "start": datetime(start.year, start.month, start.day).isoformat() + "Z",
                "end": datetime(end.year, end.month, end.day).isoformat() + "Z",
            }
            if page_token:
                params["page_token"] = page_token
            response = requests.get(f"{DATA_BASE_URL}/v2/stocks/bars", headers=self._headers(), params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            for bar in (payload.get("bars") or {}).get(symbol, []):
                rows.append({
                    "bar_time": datetime.fromisoformat(bar["t"].replace("Z", "+00:00")),
                    "open": bar.get("o"),
                    "high": bar.get("h"),
                    "low": bar.get("l"),
                    "close": bar.get("c"),
                    "adj_close": bar.get("c"),
                    "volume": bar.get("v"),
                })
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return rows
