"""Load historical stock splits and dividends for symbols already in the DB - typically run
after load_index_constituents.py. Two sources:

  --source yahoo (default): yfinance, one HTTP request per symbol, full history.
  --source alpaca: Alpaca's /v1/corporate-actions endpoint, one bulk request for many symbols
                    at once over an explicit date range (--start/--end) - needs
                    ALPACA_API_KEY_ID/ALPACA_API_SECRET_KEY in .env.

    python scripts/load_corporate_actions.py                              # every symbol, via yahoo
    python scripts/load_corporate_actions.py --symbols AAPL MSFT
    python scripts/load_corporate_actions.py --limit 20 --sleep 1.0
    python scripts/load_corporate_actions.py --top 10                     # rank by live market
                                                                            # cap (via yahoo) first
    python scripts/load_corporate_actions.py --source alpaca --symbols AAPL MSFT --start 2000-01-01
"""
import argparse
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf

from app.database import SessionLocal
from app.models import Symbol
from app.providers import PROVIDERS
from app.services import CorporateActionService


def rank_by_market_cap(tickers, sleep: float, top: int):
    """Fetch live market cap per ticker and return the top N, highest first. Slow (one Yahoo
    request per candidate) and skips any ticker Yahoo won't give a market cap for."""
    caps = {}
    for i, ticker in enumerate(tickers, 1):
        try:
            cap = yf.Ticker(ticker).fast_info.get("market_cap")
            if cap:
                caps[ticker] = cap
                print(f"  [{i}/{len(tickers)}] {ticker}: market cap ${cap:,.0f}")
            else:
                print(f"  [{i}/{len(tickers)}] {ticker}: no market cap returned")
        except Exception as exc:
            print(f"  [{i}/{len(tickers)}] {ticker}: failed ({exc})")
        time.sleep(sleep)

    ranked = sorted(caps, key=caps.get, reverse=True)[:top]
    if len(ranked) < top:
        print(f"\nWarning: only got market cap for {len(caps)}/{len(tickers)} candidates - returning {len(ranked)} of the requested top {top}.")
    return ranked


def fetch_actions(ticker: str):
    stock = yf.Ticker(ticker)

    splits = []
    for when, ratio in stock.splits.items():
        if not ratio:
            continue
        # yfinance expresses a split as one float ratio (4.0 for a 4-for-1 split, 0.1 for a
        # 1-for-10 reverse split) rather than separate from/to legs - split it back out.
        if ratio >= 1:
            ratio_from, ratio_to = 1, ratio
        else:
            ratio_from, ratio_to = round(1 / ratio), 1
        splits.append({"effective_date": when.date(), "ratio_from": ratio_from, "ratio_to": ratio_to})

    dividends = [{"effective_date": when.date(), "amount": float(amount)} for when, amount in stock.dividends.items()]
    return splits, dividends


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["yahoo", "alpaca"], default="yahoo", help="Which provider to pull from")
    parser.add_argument("--symbols", nargs="*", help="Specific tickers to load; defaults to every symbol already in the DB")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N symbols (ignored with --symbols/--top)")
    parser.add_argument("--top", type=int, default=None, help="Rank candidates by live market cap (via yahoo) first, keep only the top N")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between symbols (--source yahoo only)")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2000, 1, 1), help="Start date, YYYY-MM-DD (--source alpaca only)")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="End date, YYYY-MM-DD (--source alpaca only; defaults to today)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.symbols:
            tickers = args.symbols
        else:
            query = db.query(Symbol.ticker).order_by(Symbol.ticker)
            if args.limit and not args.top:
                query = query.limit(args.limit)
            tickers = [row[0] for row in query.all()]

        if args.top:
            print(f"Ranking {len(tickers)} candidates by live market cap via Yahoo (this fetches one quote per symbol - slow)...")
            tickers = rank_by_market_cap(tickers, args.sleep, args.top)
            print(f"\nTop {len(tickers)} by market cap: {', '.join(tickers)}\n")

        service = CorporateActionService(db)

        if args.source == "alpaca":
            provider = PROVIDERS["alpaca"]()
            end = args.end or date.today()
            print(f"Fetching corporate actions for {len(tickers)} symbols from Alpaca ({args.start} to {end})...")
            inserted = service.ingest_from_provider(provider, tickers, args.start, end)
            print(f"\nDone. {inserted} corporate actions inserted.")
            return

        total_inserted = 0
        total_failed = 0
        for i, ticker in enumerate(tickers, 1):
            try:
                splits, dividends = fetch_actions(ticker)
                inserted = service.ingest_for_symbol("yahoo", ticker, splits, dividends)
                total_inserted += inserted
                print(f"[{i}/{len(tickers)}] {ticker}: {inserted} new actions ({len(splits)} splits, {len(dividends)} dividends seen)")
            except Exception as exc:
                total_failed += 1
                print(f"[{i}/{len(tickers)}] {ticker}: failed ({exc})")
            time.sleep(args.sleep)

        print(f"\nDone. {total_inserted} corporate actions inserted, {total_failed} symbols failed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
