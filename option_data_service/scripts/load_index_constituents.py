"""Load current S&P 500 and Dow 30 constituents into the DB, from Wikipedia.

Wikipedia is used because there's no free official API for index membership (S&P Dow Jones
Indices sells that data commercially) - it's the standard source for this in the open-source
finance-tooling world, and its S&P 500 table includes GICS sector/sub-industry, which is
exactly the shape our Company table wants.

Safe to re-run: symbols already in an index are left alone, newly-appeared ones are added, and
any current member no longer in the freshly-fetched list is marked removed (as of today)
rather than deleted, so index membership history is preserved.

    python scripts/load_index_constituents.py
"""
import io
import os
import sys
from datetime import datetime

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services import IndexConstituentService

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
DJIA_URL = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"

# Wikipedia rejects the default urllib/pandas user agent (403) - a normal browser-looking UA
# is enough to get through; no login or special access needed.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; option-data-service/1.0)"}


def _fetch_tables(url: str) -> list:
    response = requests.get(url, headers=_HEADERS, timeout=15)
    response.raise_for_status()
    return pd.read_html(io.StringIO(response.text))


def _find_column(columns, *candidates) -> str | None:
    lowered = {str(c).lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _parse_date(value) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).split("[")[0].strip()  # strip footnote markers, e.g. "1957-03-04[1]"
    for fmt in ("%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def load_sp500_rows() -> list:
    table = _fetch_tables(SP500_URL)[0]
    symbol_col = _find_column(table.columns, "Symbol")
    name_col = _find_column(table.columns, "Security")
    sector_col = _find_column(table.columns, "GICS Sector")
    industry_col = _find_column(table.columns, "GICS Sub-Industry")
    added_col = _find_column(table.columns, "Date added")
    cik_col = _find_column(table.columns, "CIK")
    if not (symbol_col and name_col):
        raise RuntimeError("Could not find Symbol/Security columns in the S&P 500 Wikipedia table - its layout may have changed")

    rows = []
    for _, record in table.iterrows():
        rows.append({
            "ticker": str(record[symbol_col]).strip().replace(".", "-"),
            "company_name": str(record[name_col]).strip(),
            "sector": str(record[sector_col]).strip() if sector_col and pd.notna(record[sector_col]) else None,
            "industry": str(record[industry_col]).strip() if industry_col and pd.notna(record[industry_col]) else None,
            "cik": str(int(record[cik_col])).zfill(10) if cik_col and pd.notna(record[cik_col]) else None,
            "added_date": _parse_date(record[added_col]) if added_col else None,
        })
    return rows


def load_djia_rows() -> list:
    table = None
    for candidate in _fetch_tables(DJIA_URL):
        cols = [str(c) for c in candidate.columns]
        if _find_column(cols, "Symbol") and (_find_column(cols, "Company") or _find_column(cols, "Security")):
            table = candidate
            break
    if table is None:
        raise RuntimeError("Could not find the DJIA components table on Wikipedia - its layout may have changed")

    symbol_col = _find_column(table.columns, "Symbol")
    name_col = _find_column(table.columns, "Company") or _find_column(table.columns, "Security")
    sector_col = _find_column(table.columns, "Sector") or _find_column(table.columns, "Industry")
    added_col = _find_column(table.columns, "Date added")

    rows = []
    for _, record in table.iterrows():
        rows.append({
            "ticker": str(record[symbol_col]).strip().replace(".", "-"),
            "company_name": str(record[name_col]).strip(),
            "sector": str(record[sector_col]).strip() if sector_col and pd.notna(record[sector_col]) else None,
            "industry": None,
            "cik": None,
            "added_date": _parse_date(record[added_col]) if added_col else None,
        })
    return rows


def main():
    db = SessionLocal()
    try:
        service = IndexConstituentService(db)

        sp500_rows = load_sp500_rows()
        added = service.upsert_constituents("SP500", "S&P 500", sp500_rows)
        print(f"S&P 500: {len(sp500_rows)} fetched, {added} newly added")

        djia_rows = load_djia_rows()
        added = service.upsert_constituents("DJIA", "Dow Jones Industrial Average", djia_rows)
        print(f"DJIA: {len(djia_rows)} fetched, {added} newly added")
    finally:
        db.close()


if __name__ == "__main__":
    main()
