import pytest
import yaml
from pydantic import ValidationError

from commodity_registry.models import AssetClass, Commodity, InstrumentType
from commodity_registry.registry import _save_commodity_to_file


@pytest.fixture
def temp_registry_file(tmp_path):
    f = tmp_path / "manual.yaml"
    f.write_text("commodities: []")
    return f


def test_invalid_isin_validation():
    """Ensure invalid ISINs are rejected by the model."""
    with pytest.raises(ValidationError, match="Invalid ISIN format"):
        Commodity(
            name="INVALID",
            isin="SHORT",
            instrument_type=InstrumentType.ETF,
            asset_class=AssetClass.EQUITY_ETF,
            currency="USD",
        )


def test_currency_normalization():
    """Ensure currencies are handled by the model (normalization check)."""
    comm = Commodity(
        name="TEST",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="usd",  # lowercase
    )
    assert str(comm.currency) == "USD"


def test_idempotent_addition(temp_registry_file):
    """Adding the exact same commodity multiple times should not create duplicates."""
    comm = Commodity(
        name="AAPL",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )

    # Add twice
    _save_commodity_to_file(comm, temp_registry_file)
    _save_commodity_to_file(comm, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert len(data["commodities"]) == 1
    assert data["commodities"][0]["name"] == "AAPL"


def test_instrument_priority_isin_currency(temp_registry_file):
    """
    If ISIN + Currency matches, it should update that record even if the name
    in the new object is different (derived), unless we specifically handle it.
    Actually, _save_commodity_to_file uses the new object's name if it matches ISIN/Currency.
    The CLI layer is responsible for preserving the name.
    """
    # 1. Add initial
    comm1 = Commodity(
        name="CUSTOM_NAME",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_commodity_to_file(comm1, temp_registry_file)

    # 2. Add with different name but same ISIN/Currency
    comm2 = Commodity(
        name="AAPL",  # Derived name
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_commodity_to_file(comm2, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert len(data["commodities"]) == 1
    # In the registry layer, it updates the record.
    # The CLI layer is where we reuse the existing name.
    assert data["commodities"][0]["name"] == "AAPL"


def test_ticker_collision_handling(temp_registry_file):
    """
    Adding two different instruments (different ISINs) that happen to share a name
    or ticker should be handled.
    """
    # 1. Add first instrument (Apple)
    comm1 = Commodity(
        name="SHARED",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_commodity_to_file(comm1, temp_registry_file)

    # 2. Add second instrument (Microsoft) with same name but different ISIN
    comm2 = Commodity(
        name="SHARED",
        isin="US5949181045",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_commodity_to_file(comm2, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    # Since name matches, it updates the existing record
    assert len(data["commodities"]) == 1
    assert data["commodities"][0]["isin"] == "US5949181045"


def test_cli_name_preservation(temp_registry_file):
    """Test that CLI add command preserves existing name for same ISIN/Currency."""
    from commodity_registry.cli import add

    # 1. Manually create an entry with a custom name
    comm1 = Commodity(
        name="CUSTOM_NAME",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_commodity_to_file(comm1, temp_registry_file)

    # 2. Use add instead of mock Namespace
    cmd = add(
        registry_path=[str(temp_registry_file)],
        bundled=False,
        v=False,
        isin="US0378331005",
        currency="USD",
        ticker="AAPL",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
    )

    cmd.cli_cmd()

    # 3. Verify name is still CUSTOM_NAME
    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert data["commodities"][0]["name"] == "CUSTOM_NAME"
    assert data["commodities"][0]["tickers"]["yahoo"] == "AAPL"  # Updated ticker


def test_dual_listing_coexistence(temp_registry_file):
    """Verify that same ISIN with different currencies can coexist."""
    comm_eur = Commodity(
        name="GDX_EUR",
        isin="IE00BQQP9F84",
        instrument_type=InstrumentType.ETF,
        asset_class=AssetClass.EQUITY_ETF,
        currency="EUR",
    )
    comm_gbp = Commodity(
        name="GDX_GBP",
        isin="IE00BQQP9F84",
        instrument_type=InstrumentType.ETF,
        asset_class=AssetClass.EQUITY_ETF,
        currency="GBP",
    )

    _save_commodity_to_file(comm_eur, temp_registry_file)
    _save_commodity_to_file(comm_gbp, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert len(data["commodities"]) == 2
    currencies = [c["currency"] for c in data["commodities"]]
    assert "EUR" in currencies
    assert "GBP" in currencies
