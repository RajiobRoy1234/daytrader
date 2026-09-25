import re
from datetime import date
from typing import NamedTuple

# Standard OCC option symbol format: ROOT (padded) + YYMMDD + C/P + strike*1000 as 8 digits
# zero-padded, e.g. "AAPL240722C00220000". Used by Alpaca (and most US options data feeds)
# as the option contract identifier.
_OCC_RE = re.compile(r"^(?P<root>[A-Z]{1,6})(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})(?P<type>[CP])(?P<strike>\d{8})$")


class OccContract(NamedTuple):
    root: str
    expiration: date
    option_type: str
    strike: float


def parse_occ_symbol(symbol: str) -> OccContract:
    match = _OCC_RE.match(symbol.strip())
    if not match:
        raise ValueError(f"{symbol!r} is not a standard OCC option symbol")
    year = 2000 + int(match.group("yy"))
    return OccContract(
        root=match.group("root"),
        expiration=date(year, int(match.group("mm")), int(match.group("dd"))),
        option_type="call" if match.group("type") == "C" else "put",
        strike=int(match.group("strike")) / 1000,
    )
