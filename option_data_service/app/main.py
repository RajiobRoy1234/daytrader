from datetime import date, datetime
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import Company
from .providers import PROVIDERS
from .services import (
    CorporateActionService,
    IndexConstituentService,
    OptionQuoteService,
    OptionTickService,
    PriceHistoryService,
    StockTickService,
)

app = FastAPI(title="Option Data Service", version="1.0.0")


def _provider(source: str):
    provider_cls = PROVIDERS.get(source)
    if provider_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown source {source!r}; choose one of {sorted(PROVIDERS)}")
    return provider_cls()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/ingest/options")
def ingest_options(symbol: str = "SPY", source: str = "yahoo", db: Session = Depends(get_db)):
    service = OptionQuoteService(db)
    inserted = service.ingest(_provider(source), symbol)
    return {"inserted": inserted}


@app.get("/options")
def list_options(limit: int = 50, db: Session = Depends(get_db)):
    service = OptionQuoteService(db)
    quotes = service.list_quotes(limit=limit)
    return [
        {
            "symbol": quote.contract.underlying.ticker,
            "expiration": quote.contract.expiration.isoformat(),
            "strike": float(quote.contract.strike),
            "option_type": quote.contract.option_type,
            "source": quote.source.code,
            "bid": quote.bid,
            "ask": quote.ask,
            "last_price": quote.last_price,
            "volume": quote.volume,
            "quote_time": quote.quote_time.isoformat(),
        }
        for quote in quotes
    ]


@app.post("/ingest/prices")
def ingest_prices(
    symbol: str = "SPY",
    source: str = "yahoo",
    interval: str = "1d",
    start: date = date(2024, 1, 1),
    end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    service = PriceHistoryService(db)
    inserted = service.ingest(_provider(source), symbol, interval, start, end or date.today())
    return {"inserted": inserted}


@app.get("/prices")
def list_prices(symbol: str = "SPY", interval: str = "1d", limit: int = 100, db: Session = Depends(get_db)):
    service = PriceHistoryService(db)
    bars = service.list_bars(symbol, interval=interval, limit=limit)
    return [
        {
            "bar_time": bar.bar_time.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "adj_close": bar.adj_close,
            "volume": bar.volume,
        }
        for bar in bars
    ]


@app.post("/ingest/stock-ticks")
def ingest_stock_ticks(symbol: str, source: str, start: datetime, end: datetime, db: Session = Depends(get_db)):
    service = StockTickService(db)
    inserted = service.ingest(_provider(source), symbol, start, end)
    return {"inserted": inserted}


@app.post("/ingest/option-ticks")
def ingest_option_ticks(
    underlying: str,
    expiration: date,
    strike: float,
    option_type: str,
    contract_symbol: str,
    source: str,
    start: datetime,
    end: datetime,
    db: Session = Depends(get_db),
):
    service = OptionTickService(db)
    inserted = service.ingest(_provider(source), underlying, expiration, strike, option_type, contract_symbol, start, end)
    return {"inserted": inserted}


@app.get("/companies")
def list_companies(search: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Company)
    if search:
        query = query.filter(Company.name.ilike(f"%{search}%"))
    companies = query.order_by(Company.name).limit(limit).all()
    return [
        {
            "id": company.id,
            "name": company.name,
            "cik": company.cik,
            "sector": company.sector,
            "industry": company.industry,
        }
        for company in companies
    ]


@app.get("/indices/{code}/constituents")
def list_index_constituents(code: str, limit: int = 600, db: Session = Depends(get_db)):
    service = IndexConstituentService(db)
    constituents = service.current_constituents(code, limit=limit)
    return [
        {
            "ticker": constituent.symbol.ticker,
            "company": constituent.symbol.company.name if constituent.symbol.company else None,
            "sector": constituent.symbol.company.sector if constituent.symbol.company else None,
            "added_date": constituent.added_date.isoformat() if constituent.added_date else None,
        }
        for constituent in constituents
    ]


@app.get("/corporate-actions")
def list_corporate_actions(symbol: str, limit: int = 100, db: Session = Depends(get_db)):
    service = CorporateActionService(db)
    actions = service.list_for_symbol(symbol, limit=limit)
    return [
        {
            "action_type": action.action_type,
            "effective_date": action.effective_date.isoformat(),
            "split_ratio_from": action.split_ratio_from,
            "split_ratio_to": action.split_ratio_to,
            "dividend_amount": action.dividend_amount,
            "dividend_currency": action.dividend_currency,
            "source": action.source.code,
        }
        for action in actions
    ]
