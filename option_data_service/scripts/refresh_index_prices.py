"""Refresh OHLCV price bars for every current member of an index (default: S&P 500).
Run load_index_constituents.py first so the membership list is up to date.

    python scripts/refresh_index_prices.py                                  # SP500, daily bars, via yahoo
    python scripts/refresh_index_prices.py --index DJIA --interval 1d
    python scripts/refresh_index_prices.py --source schwab --start 2026-01-01
    python scripts/refresh_index_prices.py --symbols AAPL MSFT --limit 5
"""
import argparse
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.providers import PROVIDERS
from app.services import IndexConstituentService, PriceHistoryService


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index", default="SP500", help="Index code to refresh (e.g. SP500, DJIA)")
    parser.add_argument("--source", default="yahoo", choices=sorted(PROVIDERS), help="Provider to pull bars from")
    parser.add_argument("--interval", default="1d", help="Bar interval (1d, 1h, 5m, 1m, ... - must be supported by --source)")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 1, 1), help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="End date, YYYY-MM-DD (defaults to today)")
    parser.add_argument("--symbols", nargs="*", help="Specific tickers to refresh instead of the full index")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N constituents (ignored with --symbols)")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between symbols")
    args = parser.parse_args()

    end = args.end or date.today()
    db = SessionLocal()
    try:
        if args.symbols:
            tickers = args.symbols
        else:
            constituents = IndexConstituentService(db).current_constituents(args.index, limit=args.limit or 600)
            tickers = [c.symbol.ticker for c in constituents]

        provider = PROVIDERS[args.source]()
        service = PriceHistoryService(db)

        print(f"Refreshing {len(tickers)} symbols from {args.index} via {args.source} ({args.start} to {end}, interval={args.interval})...")
        total_inserted = 0
        total_failed = 0
        for i, ticker in enumerate(tickers, 1):
            try:
                inserted = service.ingest(provider, ticker, args.interval, args.start, end)
                total_inserted += inserted
                print(f"[{i}/{len(tickers)}] {ticker}: {inserted} new bars")
            except Exception as exc:
                total_failed += 1
                print(f"[{i}/{len(tickers)}] {ticker}: failed ({exc})")
            time.sleep(args.sleep)

        print(f"\nDone. {total_inserted} bars inserted, {total_failed} symbols failed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
