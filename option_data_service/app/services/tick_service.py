from datetime import date, datetime
from sqlalchemy.orm import Session

from ..models import OptionTick, StockTick
from ..partitioning import ensure_partitions_for_range
from ..providers.base import MarketDataProvider
from .common import get_or_create_data_source, get_or_create_option_contract, get_or_create_symbol


class StockTickService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(self, provider: MarketDataProvider, symbol: str, start: datetime, end: datetime) -> int:
        rows = provider.fetch_stock_ticks(symbol, start, end)
        if not rows:
            return 0
        source = get_or_create_data_source(self.db, provider.source_code)
        sym = get_or_create_symbol(self.db, symbol)
        ensure_partitions_for_range(self.db, "stock_ticks", start, end)

        for row in rows:
            self.db.add(StockTick(
                symbol_id=sym.id,
                source_id=source.id,
                tick_time=row["tick_time"],
                tick_type=row.get("tick_type", "trade"),
                price=row.get("price"),
                size=row.get("size"),
                bid=row.get("bid"),
                ask=row.get("ask"),
                exchange=row.get("exchange"),
                conditions=row.get("conditions"),
            ))
        self.db.commit()
        return len(rows)


class OptionTickService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(
        self,
        provider: MarketDataProvider,
        underlying_symbol: str,
        expiration: date,
        strike: float,
        option_type: str,
        contract_symbol: str,
        start: datetime,
        end: datetime,
    ) -> int:
        """`contract_symbol` is the vendor-native option symbol to request ticks for (each
        vendor spells option contracts differently - see OptionContractSourceMap); the other
        fields resolve/create the canonical OptionContract ticks are stored against."""
        rows = provider.fetch_option_ticks(contract_symbol, start, end)
        if not rows:
            return 0
        source = get_or_create_data_source(self.db, provider.source_code)
        underlying = get_or_create_symbol(self.db, underlying_symbol)
        contract = get_or_create_option_contract(self.db, underlying.id, expiration, strike, option_type)
        ensure_partitions_for_range(self.db, "option_ticks", start, end)

        for row in rows:
            self.db.add(OptionTick(
                option_contract_id=contract.id,
                source_id=source.id,
                tick_time=row["tick_time"],
                tick_type=row.get("tick_type", "trade"),
                price=row.get("price"),
                size=row.get("size"),
                bid=row.get("bid"),
                ask=row.get("ask"),
                exchange=row.get("exchange"),
                conditions=row.get("conditions"),
            ))
        self.db.commit()
        return len(rows)
