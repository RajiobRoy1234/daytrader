from datetime import date, datetime, timezone

from sqlalchemy import text

from app.models import DataSource, OptionQuote, PriceBar, StockTick, Symbol
from app.services import OptionQuoteService, PriceHistoryService, StockTickService
from .fakes import FakeProvider

# FakeProvider always reports symbol "SPY" under source "fake" - scope every assertion to that
# combination rather than table-wide counts, since this DB may also hold real data committed
# by live provider runs (Tradier/Yahoo/etc.) outside of any test transaction.


def test_ingest_option_quotes_creates_symbol_and_contract(db_session):
    service = OptionQuoteService(db_session)
    inserted = service.ingest(FakeProvider(), "SPY")
    assert inserted == 2

    quotes = (
        db_session.query(OptionQuote)
        .join(OptionQuote.source)
        .filter(DataSource.code == "fake")
        .all()
    )
    assert len(quotes) == 2
    assert {q.contract.option_type for q in quotes} == {"call", "put"}
    assert quotes[0].contract.underlying.ticker == "SPY"
    assert quotes[0].source.code == "fake"


def test_ingest_option_quotes_is_idempotent_per_snapshot(db_session):
    service = OptionQuoteService(db_session)
    service.ingest(FakeProvider(), "SPY")
    # Re-running against the same provider resolves the same symbol/contract rows rather than
    # duplicating them; only the option_quotes snapshot grows.
    service.ingest(FakeProvider(), "SPY")

    count = db_session.query(OptionQuote).join(OptionQuote.source).filter(DataSource.code == "fake").count()
    assert count == 4


def test_ingest_price_bars_dedupes_by_bar_time(db_session):
    service = PriceHistoryService(db_session)
    first = service.ingest(FakeProvider(), "SPY", "1d", date(2026, 7, 1), date(2026, 7, 20))
    second = service.ingest(FakeProvider(), "SPY", "1d", date(2026, 7, 1), date(2026, 7, 20))
    assert first == 1
    assert second == 0

    count = (
        db_session.query(PriceBar)
        .join(Symbol, PriceBar.symbol_id == Symbol.id)
        .join(DataSource, PriceBar.source_id == DataSource.id)
        .filter(Symbol.ticker == "SPY", DataSource.code == "fake")
        .count()
    )
    assert count == 1


def test_ingest_stock_ticks_writes_into_monthly_partition(db_session):
    service = StockTickService(db_session)
    start = datetime(2026, 7, 20, 14, 30, tzinfo=timezone.utc)
    end = datetime(2026, 7, 20, 14, 31, tzinfo=timezone.utc)
    inserted = service.ingest(FakeProvider(), "SPY", start, end)
    assert inserted == 1

    count = (
        db_session.query(StockTick)
        .join(Symbol, StockTick.symbol_id == Symbol.id)
        .join(DataSource, StockTick.source_id == DataSource.id)
        .filter(Symbol.ticker == "SPY", DataSource.code == "fake")
        .count()
    )
    assert count == 1

    row = db_session.execute(text(
        "SELECT count(*) FROM stock_ticks_2026_07 t "
        "JOIN symbols s ON s.id = t.symbol_id "
        "WHERE s.ticker = 'SPY'"
    )).scalar()
    assert row == 1


def test_list_options_endpoint(client):
    from app.providers import PROVIDERS

    PROVIDERS["fake"] = FakeProvider
    try:
        response = client.post("/ingest/options", params={"symbol": "SPY", "source": "fake"})
        assert response.status_code == 200
        assert response.json() == {"inserted": 2}

        response = client.get("/options", params={"limit": 500})
        assert response.status_code == 200
        spy_rows = [row for row in response.json() if row["symbol"] == "SPY" and row["source"] == "fake"]
        assert len(spy_rows) == 2
        assert {row["option_type"] for row in spy_rows} == {"call", "put"}
    finally:
        del PROVIDERS["fake"]


def test_ingest_options_rejects_unknown_source(client):
    response = client.post("/ingest/options", params={"symbol": "SPY", "source": "not-a-real-vendor"})
    assert response.status_code == 400
