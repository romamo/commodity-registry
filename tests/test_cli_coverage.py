from unittest.mock import patch

import pytest
from pydantic_settings import CliApp

from commodity_registry.cli import AppCLI


@patch("commodity_registry.finder.resolve_and_persist")
def test_cli_resolve_success(mock_resolve, capsys):
    from pydantic_market_data.models import Currency

    from commodity_registry.interfaces import ProviderName, SearchResult

    mock_resolve.return_value = SearchResult(
        provider=ProviderName.YAHOO, ticker="AAPL", name="Apple Inc.", currency=Currency("USD")
    )

    with patch("sys.argv", ["commodity-reg", "resolve", "AAPL"]):
        try:
            CliApp.run(AppCLI)
        except SystemExit as e:
            assert getattr(e, "code", 0) == 0

    captured = capsys.readouterr()
    assert "Resolved: Apple Inc. -> AAPL (yahoo)" in captured.out


@patch("commodity_registry.finder.resolve_and_persist")
def test_cli_resolve_not_found(mock_resolve):
    mock_resolve.return_value = None

    with patch("sys.argv", ["commodity-reg", "resolve", "INVALIDTICKER"]):
        with pytest.raises(SystemExit) as exc:
            CliApp.run(AppCLI)
        assert exc.value.code == 1
