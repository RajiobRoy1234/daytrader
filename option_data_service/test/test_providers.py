from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.providers.alpaca_provider import AlpacaProvider
from app.providers.occ import parse_occ_symbol
from app.providers.tradier_provider import _as_list


def test_parse_occ_symbol_call():
    contract = parse_occ_symbol("AAPL240722C00220000")
    assert contract.root == "AAPL"
    assert contract.expiration == date(2024, 7, 22)
    assert contract.option_type == "call"
    assert contract.strike == 220.0


def test_parse_occ_symbol_put_fractional_strike():
    contract = parse_occ_symbol("SPY260821P00450500")
    assert contract.option_type == "put"
    assert contract.strike == 450.5


def test_parse_occ_symbol_rejects_garbage():
    with pytest.raises(ValueError):
        parse_occ_symbol("not-an-occ-symbol")


def test_tradier_as_list_normalizes_single_item_and_none():
    assert _as_list(None) == []
    assert _as_list({"a": 1}) == [{"a": 1}]
    assert _as_list([{"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]


def test_alpaca_fetch_corporate_actions_parses_splits_and_dividends():
    """No network: mocks requests.get to verify the response-parsing logic against a payload
    shaped like Alpaca's documented corporate-actions schema."""
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "corporate_actions": {
            "forward_splits": [
                {"symbol": "AAPL", "old_rate": 1, "new_rate": 4, "process_date": "2020-08-31"},
            ],
            "reverse_splits": [],
            "cash_dividends": [
                {"symbol": "AAPL", "rate": 0.24, "ex_date": "2026-05-15", "currency": "USD"},
                {"symbol": "MSFT", "rate": 0.75, "ex_date": "2026-05-14"},
            ],
        },
        "next_page_token": None,
    }
    fake_response.raise_for_status = MagicMock()

    provider = AlpacaProvider()
    provider.key_id, provider.secret_key = "test-key", "test-secret"

    with patch("app.providers.alpaca_provider.requests.get", return_value=fake_response) as mock_get:
        result = provider.fetch_corporate_actions(["AAPL", "MSFT"], date(2020, 1, 1), date(2026, 12, 31))

    assert mock_get.call_args.kwargs["params"]["symbols"] == "AAPL,MSFT"
    assert result["AAPL"]["splits"] == [{"effective_date": date(2020, 8, 31), "ratio_from": 1, "ratio_to": 4}]
    assert result["AAPL"]["dividends"] == [{"effective_date": date(2026, 5, 15), "amount": 0.24, "currency": "USD"}]
    assert result["MSFT"]["splits"] == []
    assert result["MSFT"]["dividends"] == [{"effective_date": date(2026, 5, 14), "amount": 0.75, "currency": "USD"}]


def test_alpaca_fetch_corporate_actions_requires_credentials():
    provider = AlpacaProvider()
    provider.key_id, provider.secret_key = None, None
    with pytest.raises(Exception):
        provider.fetch_corporate_actions(["AAPL"], date(2020, 1, 1), date(2026, 1, 1))
