from datetime import date, datetime, timezone
from sqlalchemy.orm import Session

from ..models import OptionQuote
from ..partitioning import ensure_partition
from ..providers.base import MarketDataProvider
from .common import get_or_create_data_source, get_or_create_option_contract, get_or_create_symbol


class OptionQuoteService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(self, provider: MarketDataProvider, symbol: str) -> int:
        rows = provider.fetch_option_quotes(symbol)
        source = get_or_create_data_source(self.db, provider.source_code)
        snapshot_time = datetime.now(timezone.utc)
        ensure_partition(self.db, "option_quotes", snapshot_time)

        inserted = 0
        for row in rows:
            underlying = get_or_create_symbol(self.db, row["symbol"])
            expiration = date.fromisoformat(row["expiration"])
            contract = get_or_create_option_contract(self.db, underlying.id, expiration, row["strike"], row["option_type"])
            existing = self.db.query(OptionQuote).filter(
                OptionQuote.option_contract_id == contract.id,
                OptionQuote.source_id == source.id,
                OptionQuote.quote_time == snapshot_time,
            ).first()
            if existing:
                continue
            self.db.add(OptionQuote(
                option_contract_id=contract.id,
                source_id=source.id,
                quote_time=snapshot_time,
                bid=row.get("bid"),
                ask=row.get("ask"),
                last_price=row.get("last_price"),
                volume=row.get("volume"),
                open_interest=row.get("open_interest"),
                implied_volatility=row.get("implied_volatility"),
                delta=row.get("delta"),
                gamma=row.get("gamma"),
                theta=row.get("theta"),
                vega=row.get("vega"),
                rho=row.get("rho"),
            ))
            inserted += 1
        self.db.commit()
        return inserted

    def list_quotes(self, limit: int = 50):
        return (
            self.db.query(OptionQuote)
            .order_by(OptionQuote.quote_time.desc())
            .limit(limit)
            .all()
        )
