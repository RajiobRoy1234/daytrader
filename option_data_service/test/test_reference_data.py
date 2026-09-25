from datetime import date

from app.models import Company, CorporateAction, IndexConstituent, MarketIndex, Symbol
from app.services import CorporateActionService, IndexConstituentService

# Deliberately fake tickers/index code (not real S&P 500 / DJIA members) so these tests don't
# collide with real data that scripts/load_index_constituents.py may have already committed to
# this same database - table-wide counts would otherwise pick up that real data too.
ROW_A = {
    "ticker": "ZZTESTA",
    "company_name": "Testonic Corp A",
    "sector": "Test Sector",
    "industry": "Test Industry A",
    "cik": "0000000001",
    "added_date": date(1999, 1, 1),
}
ROW_B = {
    "ticker": "ZZTESTB",
    "company_name": "Testonic Corp B",
    "sector": "Test Sector",
    "industry": "Test Industry B",
    "cik": "0000000002",
    "added_date": date(1999, 1, 1),
}
TEST_INDEX_CODE = "ZZTESTIDX"


def test_upsert_constituents_creates_company_symbol_and_membership(db_session):
    service = IndexConstituentService(db_session)
    added = service.upsert_constituents(TEST_INDEX_CODE, "Test Index", [ROW_A, ROW_B])
    assert added == 2

    a = db_session.query(Symbol).filter(Symbol.ticker == "ZZTESTA").one()
    assert a.company.name == "Testonic Corp A"
    assert a.company.sector == "Test Sector"
    assert a.company.cik == "0000000001"

    current = service.current_constituents(TEST_INDEX_CODE)
    assert {c.symbol.ticker for c in current} == {"ZZTESTA", "ZZTESTB"}


def test_upsert_constituents_is_idempotent(db_session):
    service = IndexConstituentService(db_session)
    service.upsert_constituents(TEST_INDEX_CODE, "Test Index", [ROW_A])
    added_again = service.upsert_constituents(TEST_INDEX_CODE, "Test Index", [ROW_A])
    assert added_again == 0
    assert len(service.current_constituents(TEST_INDEX_CODE)) == 1


def test_upsert_constituents_reconciles_company_name_spelled_differently_across_sources(db_session):
    """Regression test: a symbol seen once under 'Testonic Corp A' and again under a
    differently-spelled name for the same ticker (as DJIA vs. S&P 500's Wikipedia tables do
    for real companies) must stay one Company, enriched, not a second orphaned Company with
    the earlier data silently disconnected from the symbol."""
    service = IndexConstituentService(db_session)
    service.upsert_constituents(TEST_INDEX_CODE, "Test Index", [ROW_A])

    other_spelling_row = {**ROW_A, "company_name": "Testonic Corp A (short name)", "sector": None, "industry": None, "cik": None}
    service.upsert_constituents("ZZOTHERIDX", "Other Test Index", [other_spelling_row])

    companies_for_ticker = (
        db_session.query(Company).join(Symbol, Symbol.company_id == Company.id).filter(Symbol.ticker == "ZZTESTA").all()
    )
    assert len(companies_for_ticker) == 1
    a = db_session.query(Symbol).filter(Symbol.ticker == "ZZTESTA").one()
    assert a.company.name == "Testonic Corp A"
    assert a.company.cik == "0000000001"


def test_upsert_constituents_marks_dropped_member_removed(db_session):
    service = IndexConstituentService(db_session)
    service.upsert_constituents(TEST_INDEX_CODE, "Test Index", [ROW_A, ROW_B])
    # Re-run with only A in the fetched list - B should be marked removed, not deleted.
    service.upsert_constituents(TEST_INDEX_CODE, "Test Index", [ROW_A])

    current = service.current_constituents(TEST_INDEX_CODE)
    assert {c.symbol.ticker for c in current} == {"ZZTESTA"}

    b_membership = (
        db_session.query(IndexConstituent)
        .join(Symbol, IndexConstituent.symbol_id == Symbol.id)
        .join(MarketIndex, IndexConstituent.index_id == MarketIndex.id)
        .filter(Symbol.ticker == "ZZTESTB", MarketIndex.code == TEST_INDEX_CODE)
        .one()
    )
    assert b_membership.removed_date == date.today()


def test_corporate_action_ingest_dedupes_by_effective_date(db_session):
    service = CorporateActionService(db_session)
    splits = [{"effective_date": date(2020, 8, 31), "ratio_from": 1, "ratio_to": 4}]
    dividends = [{"effective_date": date(2026, 5, 15), "amount": 0.24, "currency": "USD"}]

    first = service.ingest_for_symbol("yahoo", "ZZTESTA", splits, dividends)
    second = service.ingest_for_symbol("yahoo", "ZZTESTA", splits, dividends)
    assert first == 2
    assert second == 0

    actions = service.list_for_symbol("ZZTESTA")
    assert len(actions) == 2
    split = next(a for a in actions if a.action_type == "split")
    assert split.split_ratio_from == 1
    assert split.split_ratio_to == 4


def test_companies_and_constituents_and_actions_endpoints(client, db_session):
    IndexConstituentService(db_session).upsert_constituents(TEST_INDEX_CODE, "Test Index", [ROW_A, ROW_B])
    CorporateActionService(db_session).ingest_for_symbol(
        "yahoo", "ZZTESTA",
        splits=[{"effective_date": date(2020, 8, 31), "ratio_from": 1, "ratio_to": 4}],
        dividends=[],
    )

    response = client.get("/companies", params={"search": "Testonic Corp A"})
    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Testonic Corp A"]

    response = client.get("/indices/ZZTESTIDX/constituents")
    assert response.status_code == 200
    assert {c["ticker"] for c in response.json()} == {"ZZTESTA", "ZZTESTB"}

    response = client.get("/corporate-actions", params={"symbol": "ZZTESTA"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["action_type"] == "split"
    assert body[0]["split_ratio_to"] == 4
