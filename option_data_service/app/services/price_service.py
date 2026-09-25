from datetime import date
from sqlalchemy.orm import Session

from ..models import PriceBar, Symbol
from ..providers.base import MarketDataProvider
from .common import get_or_create_data_source, get_or_create_symbol


class PriceHistoryService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(self, provider: MarketDataProvider, symbol: str, interval: str, start: date, end: date) -> int:
        rows = provider.fetch_price_bars(symbol, interval, start, end)
        source = get_or_create_data_source(self.db, provider.source_code)
        sym = get_or_create_symbol(self.db, symbol)

        inserted = 0
        for row in rows:
            existing = self.db.query(PriceBar).filter(
                PriceBar.symbol_id == sym.id,
                PriceBar.source_id == source.id,
                PriceBar.interval == interval,
                PriceBar.bar_time == row["bar_time"],
            ).first()
            if existing:
                continue
            self.db.add(PriceBar(
                symbol_id=sym.id,
                source_id=source.id,
                interval=interval,
                bar_time=row["bar_time"],
                open=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                adj_close=row.get("adj_close"),
                volume=row.get("volume"),
            ))
            inserted += 1
        self.db.commit()
        return inserted

    def list_bars(self, symbol: str, interval: str = "1d", limit: int = 100):
        return (
            self.db.query(PriceBar)
            .join(Symbol, PriceBar.symbol_id == Symbol.id)
            .filter(Symbol.ticker == symbol, PriceBar.interval == interval)
            .order_by(PriceBar.bar_time.desc())
            .limit(limit)
            .all()
        )
