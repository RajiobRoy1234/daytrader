from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .services import OptionDataService

app = FastAPI(title="Option Data Service", version="1.0.0")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/ingest")
def ingest_quotes(db: Session = Depends(get_db)):
    service = OptionDataService(db)
    count = service.ingest_latest()
    return {"inserted": count}


@app.get("/quotes")
def list_quotes(limit: int = 50, db: Session = Depends(get_db)):
    service = OptionDataService(db)
    quotes = service.list_quotes(limit=limit)
    return [
        {
            "symbol": quote.symbol,
            "expiration": quote.expiration,
            "strike": quote.strike,
            "option_type": quote.option_type,
            "bid": quote.bid,
            "ask": quote.ask,
            "last_price": quote.last_price,
            "volume": quote.volume,
            "timestamp": quote.timestamp.isoformat(),
        }
        for quote in quotes
    ]
