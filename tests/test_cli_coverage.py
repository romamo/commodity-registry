from unittest.mock import patch

import pytest

from instrument_registry.cli import main


@patch("instrument_registry.finder.resolve_and_persist")
def test_cli_resolve_success(mock_resolve, capsys):
    from pydantic_market_data.models import Currency

    from instrument_registry.interfaces import ProviderName, SearchResult

    mock_resolve.return_value = SearchResult(
        provider=ProviderName.YAHOO, symbol="AAPL", name="Apple Inc.", currency=Currency("USD")
    )

    try:
        main(["resolve", "AAPL", "--format", "table"])
    except SystemExit as e:
        assert getattr(e, "code", 0) == 0

    captured = capsys.readouterr()
    assert "Resolved: Apple Inc. -> AAPL (yahoo)" in captured.out


@patch("instrument_registry.finder.resolve_and_persist")
def test_cli_resolve_not_found(mock_resolve):
    mock_resolve.return_value = None

    with pytest.raises(SystemExit) as exc:
        main(["resolve", "INVALIDTICKER"])
    assert exc.value.code == 1
