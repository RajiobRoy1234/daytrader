import os
from typing import Dict, List

from .base import MarketDataProvider, ProviderNotConfiguredError

# blpapi is Bloomberg's own SDK, not on PyPI - install from Bloomberg's package index:
#   pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi
# It talks to a running Bloomberg Terminal (Desktop API, default localhost:8194) or a B-PIPE
# server, so this only works on a machine with an active Bloomberg session/entitlement.
try:
    import blpapi
except ImportError:
    blpapi = None


class BloombergProvider(MarketDataProvider):
    """Bloomberg Desktop/Server API (//blp/refdata). Needs blpapi installed (see above) and a
    reachable Bloomberg session - BLOOMBERG_HOST/BLOOMBERG_PORT default to the standard local
    Desktop API address. Field mnemonics below (OPT_CHAIN, PX_BID, PX_ASK, PX_LAST, PX_VOLUME)
    are common Bloomberg fields, but exact availability depends on your entitlements - verify
    against your terminal if a field comes back empty."""

    source_code = "bloomberg"

    def __init__(self):
        self.host = os.getenv("BLOOMBERG_HOST", "localhost")
        self.port = int(os.getenv("BLOOMBERG_PORT", "8194"))

    def _open_session(self):
        if blpapi is None:
            raise ProviderNotConfiguredError(
                "blpapi is not installed. Install it from Bloomberg's package index: "
                "pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi"
            )
        options = blpapi.SessionOptions()
        options.setServerHost(self.host)
        options.setServerPort(self.port)
        session = blpapi.Session(options)
        if not session.start():
            raise ProviderNotConfiguredError(f"Could not connect to a Bloomberg session at {self.host}:{self.port}")
        if not session.openService("//blp/refdata"):
            raise ProviderNotConfiguredError("Could not open //blp/refdata - check your Bloomberg entitlements")
        return session

    def fetch_option_quotes(self, symbol: str) -> List[Dict]:
        session = self._open_session()
        try:
            service = session.getService("//blp/refdata")

            chain_request = service.createRequest("ReferenceDataRequest")
            chain_request.getElement("securities").appendValue(f"{symbol} US Equity")
            chain_request.getElement("fields").appendValue("OPT_CHAIN")
            session.sendRequest(chain_request)
            contract_tickers = self._collect_field(session, "OPT_CHAIN", "Security Description")
            if not contract_tickers:
                return []

            quote_request = service.createRequest("ReferenceDataRequest")
            for ticker in contract_tickers:
                quote_request.getElement("securities").appendValue(ticker)
            for field in ("PX_BID", "PX_ASK", "PX_LAST", "PX_VOLUME", "OPT_STRIKE_PX", "OPT_PUT_CALL", "OPT_EXPIRE_DT"):
                quote_request.getElement("fields").appendValue(field)
            session.sendRequest(quote_request)

            rows: List[Dict] = []
            while True:
                event = session.nextEvent(10000)
                for msg in event:
                    if not msg.hasElement("securityData"):
                        continue
                    for security in msg.getElement("securityData").values():
                        fields = security.getElement("fieldData")
                        rows.append({
                            "symbol": symbol,
                            "expiration": str(fields.getElementAsDatetime("OPT_EXPIRE_DT").date()),
                            "strike": fields.getElementAsFloat("OPT_STRIKE_PX"),
                            "option_type": "call" if fields.getElementAsString("OPT_PUT_CALL").upper().startswith("C") else "put",
                            "bid": fields.getElementAsFloat("PX_BID") if fields.hasElement("PX_BID") else None,
                            "ask": fields.getElementAsFloat("PX_ASK") if fields.hasElement("PX_ASK") else None,
                            "last_price": fields.getElementAsFloat("PX_LAST") if fields.hasElement("PX_LAST") else None,
                            "volume": fields.getElementAsInteger("PX_VOLUME") if fields.hasElement("PX_VOLUME") else None,
                        })
                if event.eventType() == blpapi.Event.RESPONSE:
                    break
            return rows
        finally:
            session.stop()

    @staticmethod
    def _collect_field(session, bulk_field: str, sub_field: str) -> List[str]:
        values: List[str] = []
        while True:
            event = session.nextEvent(10000)
            for msg in event:
                if not msg.hasElement("securityData"):
                    continue
                for security in msg.getElement("securityData").values():
                    field_data = security.getElement("fieldData")
                    if not field_data.hasElement(bulk_field):
                        continue
                    bulk = field_data.getElement(bulk_field)
                    for i in range(bulk.numValues()):
                        values.append(bulk.getValueAsElement(i).getElementAsString(sub_field))
            if event.eventType() == blpapi.Event.RESPONSE:
                break
        return values
