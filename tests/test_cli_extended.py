from unittest.mock import MagicMock, patch

import pytest
from pydantic_market_data.models import Currency
from pydantic_settings import CliApp

from commodity_registry.cli import AppCLI
from commodity_registry.interfaces import ProviderName, SearchResult


@pytest.fixture
def mock_registry(tmp_path):
    reg_dir = tmp_path / "reg"
    reg_dir.mkdir()
    manual_file = reg_dir / "manual.yaml"
    with open(manual_file, "w") as f:
        f.write("commodities: []")
    return reg_dir


def test_cli_verbosity_debug():
    # Test only the root flag propagation logic
    with patch("sys.argv", ["commodity-reg", "-vv", "resolve", "AAPL"]):
        with patch("commodity_registry.cli.setup_logging") as mock_log:
            with patch("commodity_registry.finder.resolve_and_persist", return_value=None):
                with pytest.raises(SystemExit):
                    CliApp.run(AppCLI)
            mock_log.assert_called()


@patch("commodity_registry.registry.get_registry")
@patch("commodity_registry.cli.setup_logging")
def test_cli_lint_basic(mock_log, mock_get_reg, capsys):
    mock_reg = MagicMock()
    mock_reg.get_all.return_value = []
    mock_reg.load_errors = []
    mock_get_reg.return_value = mock_reg

    with patch("sys.argv", ["commodity-reg", "lint"]):
        CliApp.run(AppCLI)


@patch("commodity_registry.finder.search_isin")
@patch("commodity_registry.registry.add_commodity")
def test_cli_add_success(mock_add, mock_search, mock_registry, capsys):
    mock_search.return_value = [
        SearchResult(
            provider=ProviderName.YAHOO, ticker="AAPL", name="Apple Inc.", currency=Currency("USD")
        )
    ]

    mock_comm = MagicMock()
    mock_comm.name = "AAPL"
    mock_add.return_value = mock_comm

    args = [
        "commodity-reg",
        "add",
        "AAPL",
        "--instrument-type",
        "ETF",
        "--asset-class",
        "CommodityETF",
        "--currency",
        "USD",
        "--registry-path",
        str(mock_registry),
        "--fetch",
    ]

    with patch("sys.argv", args):
        CliApp.run(AppCLI)

    mock_add.assert_called_once()
    assert "Successfully processed AAPL" in capsys.readouterr().out


@patch("commodity_registry.finder.resolve_security")
def test_cli_fetch_success(mock_resolve, capsys):
    mock_resolve.return_value = SearchResult(
        provider=ProviderName.YAHOO, ticker="AAPL", name="Apple Inc.", currency=Currency("USD")
    )

    with patch("sys.argv", ["commodity-reg", "fetch", "--ticker", "AAPL"]):
        CliApp.run(AppCLI)

    captured = capsys.readouterr()
    assert "Found Details (YAHOO)" in captured.out
    assert "Ticker:   AAPL" in captured.out


def test_cli_help(capsys):
    with patch("sys.argv", ["commodity-reg", "--help"]):
        with pytest.raises(SystemExit) as exc:
            CliApp.run(AppCLI)
        assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "subcommand" in captured.out


@patch("commodity_registry.finder.search_isin")
@patch("commodity_registry.registry.add_commodity")
def test_cli_add_no_metadata(mock_add, mock_search, mock_registry):
    """Test add command when no online metadata is found and no identifier is provided."""
    mock_search.return_value = []

    # Missing both ticker and isin, and fetch is on
    args = [
        "commodity-reg",
        "add",
        "--instrument-type",
        "ETF",
        "--asset-class",
        "CommodityETF",
        "--currency",
        "USD",
        "--registry-path",
        str(mock_registry),
        "--fetch",
    ]

    with patch("sys.argv", args):
        with pytest.raises(SystemExit) as e:
            CliApp.run(AppCLI)
        assert e.value.code == 1


@patch("commodity_registry.finder.verify_ticker")
@patch("commodity_registry.finder.fetch_metadata")
@patch("commodity_registry.finder.resolve_security")
def test_cli_lint_with_verify(mock_resolve, mock_fetch, mock_verify, mock_registry, capsys):
    """Test lint command with verification enabled and detailed audit path."""
    from commodity_registry.models import (
        AssetClass,
        Commodity,
        InstrumentType,
        Tickers,
        ValidationPoint,
    )
    from commodity_registry.registry import _save_commodity_to_file

    mock_fetch.return_value = MagicMock(
        ticker="AAPL", name="Apple Inc.", currency=Currency("USD"), isin="US0378331005"
    )
    mock_verify.return_value = True

    # Create a small registry with ticker and validation points
    reg_file = mock_registry / "manual.yaml"
    comm = Commodity(
        name="AAPL",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
        tickers=Tickers(yahoo="AAPL"),
        validation_points=[ValidationPoint(date="2024-01-01", price=150.0)],
    )
    _save_commodity_to_file(comm, reg_file)
    _save_commodity_to_file(comm, reg_file)

    args = ["commodity-reg", "-vv", "lint", "--path", str(reg_file), "--verify"]

    with patch("sys.argv", args):
        CliApp.run(AppCLI)

    output = capsys.readouterr().out
    assert "AAPL(yahoo AAPL): OK" in output
    assert "ISIN:     US0378331005 [OK]" in output
    assert "Price:    150.0" in output or "OK: Range Match" in output


def test_cli_fetch_no_results(capsys):
    """Test fetch command when no results are found."""
    with patch("commodity_registry.finder.resolve_security", return_value=None):
        with patch("sys.argv", ["commodity-reg", "fetch", "--ticker", "NONEXISTENT"]):
            CliApp.run(AppCLI)

    # Just ensure it doesn't crash


@patch("commodity_registry.finder.fetch_price")
@patch("commodity_registry.finder.resolve_security")
def test_cli_fetch_with_price(mock_resolve, mock_price, capsys):
    """Test fetch command with price fetching enabled."""
    mock_resolve.return_value = SearchResult(
        provider=ProviderName.YAHOO, ticker="AAPL", name="Apple Inc.", currency=Currency("USD")
    )
    mock_price.return_value = 150.0

    args = ["commodity-reg", "fetch", "--ticker", "AAPL", "--price"]

    with patch("sys.argv", args):
        CliApp.run(AppCLI)

    output = capsys.readouterr().out
    assert "Price:    150.0" in output


@patch("commodity_registry.finder.resolve_and_persist")
def test_cli_resolve_json(mock_resolve, mock_registry, capsys):
    """Test resolve command with JSON output."""
    mock_resolve.return_value = SearchResult(
        provider=ProviderName.YAHOO, ticker="AAPL", name="Apple Inc.", currency=Currency("USD")
    )

    args = ["commodity-reg", "resolve", "--format", "json", "AAPL"]

    with patch("sys.argv", args):
        CliApp.run(AppCLI)

    output = capsys.readouterr().out
    assert '"ticker": "AAPL"' in output
