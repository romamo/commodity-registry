import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_market_data.models import Price, Security, SecurityCriteria, Symbol

from instrument_registry.finder import (
    _fallback_cache_dir,
    _get_cache_dir,
    _init_cache,
    fetch_metadata,
    search_isin,
    verify_ticker,
)


@pytest.fixture
def mock_yahoo_source():
    with patch("instrument_registry.finder.YFinanceDataSource") as mock:
        yield mock


@pytest.fixture
def mock_ft_source():
    with patch("instrument_registry.finder.FTDataSource") as mock:
        yield mock


def test_search_isin_yahoo_only(mock_yahoo_source, mock_ft_source):
    # Setup mocks
    mock_yahoo_instance = MagicMock()
    mock_yahoo_source.return_value = mock_yahoo_instance

    # Simulate FT not installed by making it None in the finder module
    with patch("instrument_registry.finder.FTDataSource", None):
        mock_security = Security(
            symbol=Symbol(root="AAPL"), name="Apple Inc.", currency="USD", exchange="NASDAQ"
        )

        mock_yahoo_instance.resolve.return_value = mock_security

        criteria = SecurityCriteria(isin="US0378331005")
        results = search_isin(criteria)

        assert len(results) == 1
        assert results[0].provider == "yahoo"
        assert str(results[0].symbol) == "AAPL"
        assert results[0].name == "Apple Inc."


def test_fetch_metadata_failure(mock_yahoo_source):
    mock_yahoo_instance = MagicMock()
    mock_yahoo_source.return_value = mock_yahoo_instance
    mock_yahoo_instance.resolve.return_value = None

    data = fetch_metadata("INVALID", provider="yahoo")
    assert data is None


def test_verify_ticker_success(mock_yahoo_source):
    mock_yahoo_instance = MagicMock()
    mock_yahoo_source.return_value = mock_yahoo_instance
    mock_yahoo_instance.validate.return_value = True

    test_date = datetime.date(2024, 1, 1)
    test_price = Price(190.0)
    result = verify_ticker("AAPL", test_date, test_price, provider="yahoo")
    assert result is True

    mock_yahoo_instance.validate.assert_called_with(Symbol(root="AAPL"), test_date, test_price)


def test_resolve_currency():
    from instrument_registry.finder import resolve_currency

    # Simple pair
    res = resolve_currency("EURUSD")
    assert str(res.symbol) == "EURUSD=X"
    assert str(res.currency) == "USD"

    # With slash
    res = resolve_currency("EUR/GBP")
    assert str(res.symbol) == "EURGBP=X"
    assert str(res.currency) == "GBP"

    # Inverse USD
    res = resolve_currency("USDEUR")
    assert str(res.symbol) == "EUR=X"

    # Invalid
    assert resolve_currency("INVALID") is None
    assert resolve_currency("ABC/DEFG") is None


def test_resolve_security_registry_match():
    from pydantic_market_data.models import SecurityCriteria

    from instrument_registry.finder import resolve_security

    mock_reg = MagicMock()
    mock_comm = MagicMock()
    mock_comm.name = "GOLD"
    mock_comm.currency = "USD"
    mock_comm.tickers = MagicMock()
    mock_comm.tickers.yahoo = "GC=F"
    mock_comm.asset_class = "Commodity"
    mock_comm.instrument_type = "Future"
    mock_comm.country = None
    mock_comm.metadata = None

    mock_reg.find_candidates.return_value = [mock_comm]

    criteria = SecurityCriteria(symbol="GOLD")
    res = resolve_security(criteria, registry=mock_reg)

    assert res.name == "GOLD"
    assert str(res.symbol) == "GC=F"
    assert str(res.currency) == "USD"
    mock_reg.find_candidates.assert_called_once_with(criteria)


def test_get_cache_dir_uses_env_override(monkeypatch):
    monkeypatch.setenv("INSTRUMENT_REGISTRY_CACHE_DIR", ".cache/instrument-registry")

    assert _get_cache_dir() == Path(".cache/instrument-registry")


def test_get_cache_dir_defaults_to_platformdirs(monkeypatch):
    monkeypatch.delenv("INSTRUMENT_REGISTRY_CACHE_DIR", raising=False)

    with patch(
        "instrument_registry.finder.platformdirs.user_cache_dir",
        return_value="/tmp/ir-cache",
    ):
        assert _get_cache_dir() == Path("/tmp/ir-cache")


def test_init_cache_falls_back_to_local_cache(monkeypatch):
    monkeypatch.delenv("INSTRUMENT_REGISTRY_CACHE_DIR", raising=False)

    cache_calls: list[str] = []

    def fake_cache(path: str):
        cache_calls.append(path)
        if len(cache_calls) == 1:
            raise OSError("sandbox denied")
        return "fallback-cache"

    with patch("instrument_registry.finder.diskcache.Cache", side_effect=fake_cache):
        with patch(
            "instrument_registry.finder.platformdirs.user_cache_dir",
            return_value="/blocked/cache",
        ):
            assert _init_cache() == "fallback-cache"

    assert cache_calls == ["/blocked/cache", str(_fallback_cache_dir())]
