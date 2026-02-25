"""
Coverage tests for the untested paths in finder.py.

These tests focus on pure logic functions that don't require live network
access, using mocks wherever a provider call would occur.
"""

from unittest.mock import MagicMock, patch

import pytest

from commodity_registry.finder import (
    _map_asset_class,
    fetch_price,
    get_available_providers,
    resolve_currency,
)
from commodity_registry.interfaces import ProviderName

# ---------------------------------------------------------------------------
# _map_asset_class
# ---------------------------------------------------------------------------


class TestMapAssetClass:
    def test_etf_keyword(self):
        from commodity_registry.models import AssetClass

        assert _map_asset_class("EquityETF") == AssetClass.EQUITY_ETF

    def test_stock_keyword(self):
        from commodity_registry.models import AssetClass

        assert _map_asset_class("STOCK") == AssetClass.STOCK

    def test_equity_keyword(self):
        from commodity_registry.models import AssetClass

        assert _map_asset_class("equity") == AssetClass.STOCK

    def test_crypto_keyword(self):
        from commodity_registry.models import AssetClass

        assert _map_asset_class("CryptoCurrency") == AssetClass.CRYPTO

    def test_unknown_returns_none(self):
        assert _map_asset_class("BOND") is None

    def test_empty_returns_none(self):
        assert _map_asset_class("") is None


# ---------------------------------------------------------------------------
# resolve_currency
# ---------------------------------------------------------------------------


class TestResolveCurrency:
    def test_simple_base_vs_usd(self):
        """EUR with default USD target -> EURUSD=X"""
        res = resolve_currency("EUR")
        assert res is not None
        assert res.ticker.root == "EURUSD=X"

    def test_usd_base(self):
        """USD vs EUR -> EUR=X (Yahoo convention)"""
        from pydantic_market_data.models import Currency

        res = resolve_currency("USD", target_currency=Currency("EUR"))
        assert res is not None
        assert res.ticker.root == "EUR=X"

    def test_cross_rate(self):
        """EUR vs JPY -> EURJPY=X"""
        from pydantic_market_data.models import Currency

        res = resolve_currency("EUR", target_currency=Currency("JPY"))
        assert res is not None
        assert res.ticker.root == "EURJPY=X"

    def test_composite_six_char(self):
        """'EURUSD' string -> ticker EURUSD=X"""
        res = resolve_currency("EURUSD")
        assert res.ticker.root == "EURUSD=X"

    def test_slash_notation(self):
        """'EUR/USD' -> ticker EURUSD=X"""
        res = resolve_currency("EUR/USD")
        assert res.ticker.root == "EURUSD=X"

    def test_dash_notation(self):
        """'EUR-USD' -> ticker EURUSD=X"""
        res = resolve_currency("EUR-USD")
        assert res.ticker.root == "EURUSD=X"

    def test_same_currency_returns_none(self):
        """EUR vs EUR is not a valid pair."""
        from pydantic_market_data.models import Currency

        res = resolve_currency("EUR", target_currency=Currency("EUR"))
        assert res is None

    def test_empty_symbol_returns_none(self):
        assert resolve_currency("") is None

    def test_non_alpha_returns_none(self):
        """Non-alphabetic 3-char codes should be rejected."""
        assert resolve_currency("123") is None

    def test_too_short_returns_none(self):
        assert resolve_currency("EU") is None

    def test_verify_calls_fetch_metadata(self):
        """When verify=True, fetch_metadata is called to confirm ticker exists."""
        with patch(
            "commodity_registry.finder.fetch_metadata", return_value=MagicMock()
        ) as mock_fetch:
            res = resolve_currency("EUR", verify=True)
            assert res is not None
            mock_fetch.assert_called_once_with("EURUSD=X", provider=ProviderName.YAHOO)

    def test_verify_returns_none_if_not_found(self):
        """When verify=True and fetch_metadata returns None, result is None."""
        with patch("commodity_registry.finder.fetch_metadata", return_value=None):
            res = resolve_currency("EUR", verify=True)
            assert res is None


# ---------------------------------------------------------------------------
# get_available_providers
# ---------------------------------------------------------------------------


class TestGetAvailableProviders:
    def test_returns_yahoo_when_available(self):
        with patch("commodity_registry.finder.YFinanceDataSource", MagicMock()):
            with patch("commodity_registry.finder.FTDataSource", None):
                providers = get_available_providers()
        assert ProviderName.YAHOO in providers
        assert ProviderName.FT not in providers

    def test_returns_ft_when_available(self):
        with patch("commodity_registry.finder.YFinanceDataSource", None):
            with patch("commodity_registry.finder.FTDataSource", MagicMock()):
                providers = get_available_providers()
        assert ProviderName.FT in providers
        assert ProviderName.YAHOO not in providers

    def test_empty_when_none_available(self):
        with patch("commodity_registry.finder.YFinanceDataSource", None):
            with patch("commodity_registry.finder.FTDataSource", None):
                providers = get_available_providers()
        assert providers == []


# ---------------------------------------------------------------------------
# fetch_price
# ---------------------------------------------------------------------------


class TestFetchPrice:
    def test_returns_price_when_get_price_exists(self):
        mock_provider = MagicMock()
        mock_provider.get_price.return_value = 123.45

        with patch("commodity_registry.finder.get_data_provider", return_value=mock_provider):
            price = fetch_price("AAPL", provider=ProviderName.YAHOO)

        assert price is not None
        assert float(price.value) == pytest.approx(123.45)

    def test_returns_none_when_get_price_returns_none(self):
        mock_provider = MagicMock()
        mock_provider.get_price.return_value = None

        with patch("commodity_registry.finder.get_data_provider", return_value=mock_provider):
            price = fetch_price("AAPL", provider=ProviderName.YAHOO)

        assert price is None
