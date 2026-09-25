from datetime import date
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from ..models import Company, CorporateAction, IndexConstituent, MarketIndex, Symbol
from ..providers.base import MarketDataProvider
from .common import get_or_create_data_source, get_or_create_symbol


def get_or_create_company(db: Session, name: str, **fields) -> Company:
    company = db.query(Company).filter(Company.name == name).first()
    if company:
        for key, value in fields.items():
            if value and not getattr(company, key, None):
                setattr(company, key, value)
        return company
    company = Company(name=name, **fields)
    db.add(company)
    db.flush()
    return company


def get_or_create_index(db: Session, code: str, name: str) -> MarketIndex:
    index = db.query(MarketIndex).filter(MarketIndex.code == code).first()
    if index:
        return index
    index = MarketIndex(code=code, name=name)
    db.add(index)
    db.flush()
    return index


class IndexConstituentService:
    """Loads a fetched constituent list (see scripts/load_index_constituents.py for the
    Wikipedia scrape) into companies/symbols/index_constituents. Membership is tracked with
    history: re-running against a fresh fetch adds new members and marks any current member
    missing from the new list as removed (as of today), rather than deleting rows."""

    def __init__(self, db: Session):
        self.db = db

    def upsert_constituents(self, index_code: str, index_name: str, rows: List[Dict]) -> int:
        """rows: [{'ticker', 'company_name', 'sector', 'industry', 'cik', 'added_date'}, ...]"""
        index = get_or_create_index(self.db, index_code, index_name)
        seen_symbol_ids = set()
        added = 0

        for row in rows:
            # Anchor on the symbol/ticker, not the company name string: different index
            # sources spell the same company differently ("Apple" vs "Apple Inc."), and
            # matching by name would create a duplicate Company and silently repoint the
            # symbol to it, orphaning whatever richer data the first-seen row had.
            symbol = get_or_create_symbol(self.db, row["ticker"])
            if symbol.company_id:
                company = self.db.get(Company, symbol.company_id)
                for key, value in (("sector", row.get("sector")), ("industry", row.get("industry")), ("cik", row.get("cik"))):
                    if value and not getattr(company, key, None):
                        setattr(company, key, value)
            else:
                company = get_or_create_company(
                    self.db, row["company_name"],
                    sector=row.get("sector"), industry=row.get("industry"), cik=row.get("cik"),
                )
                symbol.company_id = company.id
            seen_symbol_ids.add(symbol.id)

            existing = self.db.query(IndexConstituent).filter(
                IndexConstituent.index_id == index.id,
                IndexConstituent.symbol_id == symbol.id,
                IndexConstituent.removed_date.is_(None),
            ).first()
            if existing:
                continue
            self.db.add(IndexConstituent(index_id=index.id, symbol_id=symbol.id, added_date=row.get("added_date")))
            added += 1

        current = self.db.query(IndexConstituent).filter(
            IndexConstituent.index_id == index.id, IndexConstituent.removed_date.is_(None)
        ).all()
        for constituent in current:
            if constituent.symbol_id not in seen_symbol_ids:
                constituent.removed_date = date.today()

        self.db.commit()
        return added

    def current_constituents(self, index_code: str, limit: int = 600):
        return (
            self.db.query(IndexConstituent)
            .join(MarketIndex, IndexConstituent.index_id == MarketIndex.id)
            .filter(MarketIndex.code == index_code, IndexConstituent.removed_date.is_(None))
            .limit(limit)
            .all()
        )


class CorporateActionService:
    def __init__(self, db: Session):
        self.db = db

    def ingest_for_symbol(self, source_code: str, ticker: str, splits: List[Dict], dividends: List[Dict]) -> int:
        """splits: [{'effective_date', 'ratio_from', 'ratio_to'}, ...]
        dividends: [{'effective_date', 'amount', 'currency'}, ...]"""
        source = get_or_create_data_source(self.db, source_code)
        symbol = get_or_create_symbol(self.db, ticker)
        inserted = 0

        for row in splits:
            inserted += self._insert_if_new(symbol.id, source.id, "split", row["effective_date"], {
                "split_ratio_from": row["ratio_from"],
                "split_ratio_to": row["ratio_to"],
            })
        for row in dividends:
            inserted += self._insert_if_new(symbol.id, source.id, "dividend", row["effective_date"], {
                "dividend_amount": row["amount"],
                "dividend_currency": row.get("currency", "USD"),
            })

        self.db.commit()
        return inserted

    def ingest_from_provider(self, provider: MarketDataProvider, tickers: List[str], start: date, end: date) -> int:
        """Bulk path: one provider call for many tickers (provider.fetch_corporate_actions),
        vs. ingest_for_symbol's one-ticker-at-a-time path used by yfinance."""
        by_ticker = provider.fetch_corporate_actions(tickers, start, end)
        total = 0
        for ticker, actions in by_ticker.items():
            total += self.ingest_for_symbol(provider.source_code, ticker, actions.get("splits", []), actions.get("dividends", []))
        return total

    def _insert_if_new(self, symbol_id: int, source_id: int, action_type: str, effective_date: date, fields: Dict) -> int:
        existing = self.db.query(CorporateAction).filter(
            CorporateAction.symbol_id == symbol_id,
            CorporateAction.source_id == source_id,
            CorporateAction.action_type == action_type,
            CorporateAction.effective_date == effective_date,
        ).first()
        if existing:
            return 0
        self.db.add(CorporateAction(
            symbol_id=symbol_id, source_id=source_id, action_type=action_type,
            effective_date=effective_date, **fields,
        ))
        return 1

    def list_for_symbol(self, ticker: str, limit: int = 100):
        return (
            self.db.query(CorporateAction)
            .join(Symbol, CorporateAction.symbol_id == Symbol.id)
            .filter(Symbol.ticker == ticker)
            .order_by(CorporateAction.effective_date.desc())
            .limit(limit)
            .all()
        )
