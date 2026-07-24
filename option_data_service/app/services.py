from sqlalchemy.orm import Session
from .models import OptionQuote
from .database import Base, engine
from .providers.yahoo_provider import YahooOptionsProvider

Base.metadata.create_all(bind=engine)


class OptionDataService:
    def __init__(self, db: Session):
        self.db = db

    def ingest_latest(self) -> int:
        provider = YahooOptionsProvider()
        rows = provider.fetch_quotes()
        inserted = 0
        for row in rows:
            existing = self.db.query(OptionQuote).filter(
                OptionQuote.symbol == row["symbol"],
                OptionQuote.expiration == row["expiration"],
                OptionQuote.strike == row["strike"],
                OptionQuote.option_type == row["option_type"],
            ).first()
            if existing:
                continue
            quote = OptionQuote(**row)
            self.db.add(quote)
            inserted += 1
        self.db.commit()
        return inserted

    def list_quotes(self, limit: int = 50):
        return self.db.query(OptionQuote).order_by(OptionQuote.timestamp.desc()).limit(limit).all()
