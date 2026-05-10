import pytest
import yaml
from pydantic import ValidationError

from instrument_registry.models import AssetClass, Instrument, InstrumentType
from instrument_registry.registry import _save_instrument_to_file


@pytest.fixture
def temp_registry_file(tmp_path):
    f = tmp_path / "manual.yaml"
    f.write_text("instruments: []")
    return f


def test_invalid_isin_validation():
    """Ensure invalid ISINs are rejected by the model."""
    with pytest.raises(ValidationError, match="Invalid ISIN format"):
        Instrument(
            symbol="INVALID",
            isin="SHORT",
            instrument_type=InstrumentType.ETF,
            asset_class=AssetClass.EQUITY_ETF,
            currency="USD",
        )


def test_currency_normalization():
    """Ensure currencies are handled by the model (normalization check)."""
    comm = Instrument(
        symbol="TEST",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="usd",  # lowercase
    )
    assert str(comm.currency) == "USD"


def test_idempotent_addition(temp_registry_file):
    """Adding the exact same commodity multiple times should not create duplicates."""
    comm = Instrument(
        symbol="AAPL",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )

    # Add twice
    _save_instrument_to_file(comm, temp_registry_file)
    _save_instrument_to_file(comm, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert len(data["instruments"]) == 1
    assert data["instruments"][0]["symbol"] == "AAPL"


def test_instrument_priority_isin_currency(temp_registry_file):
    """
    If ISIN + Currency matches, it should update that record even if the name
    in the new object is different (derived), unless we specifically handle it.
    Actually, _save_instrument_to_file uses the new object's name if it matches ISIN/Currency.
    The CLI layer is responsible for preserving the name.
    """
    # 1. Add initial
    comm1 = Instrument(
        symbol="CUSTOM_NAME",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_instrument_to_file(comm1, temp_registry_file)

    # 2. Add with different symbol but same ISIN/Currency
    comm2 = Instrument(
        symbol="AAPL",  # Derived symbol
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_instrument_to_file(comm2, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert len(data["instruments"]) == 1
    # In the registry layer, it updates the record.
    # The CLI layer is where we reuse the existing symbol.
    assert data["instruments"][0]["symbol"] == "AAPL"


def test_same_symbol_different_isin_replaces_existing(temp_registry_file):
    """
    Two instruments with the same symbol but different ISINs: the second write
    replaces the first because _save_instrument_to_file matches on symbol.
    """
    comm1 = Instrument(
        symbol="SHARED",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_instrument_to_file(comm1, temp_registry_file)

    comm2 = Instrument(
        symbol="SHARED",
        isin="US5949181045",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_instrument_to_file(comm2, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert len(data["instruments"]) == 1
    assert data["instruments"][0]["isin"] == "US5949181045"


def test_cli_name_preservation(temp_registry_file):
    """Test that CLI add command preserves existing symbol for same ISIN/Currency."""
    from instrument_registry.cli import main

    # 1. Manually create an entry with a custom symbol
    comm1 = Instrument(
        symbol="CUSTOM_NAME",
        isin="US0378331005",
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
    )
    _save_instrument_to_file(comm1, temp_registry_file)

    # 2. Use the public CLI entrypoint to update the same instrument
    main(
        [
            "add",
            "--registry-path",
            str(temp_registry_file),
            "--no-bundled",
            "--isin",
            "US0378331005",
            "--currency",
            "USD",
            "--symbol",
            "AAPL",
            "--instrument-type",
            "Stock",
            "--asset-class",
            "Stock",
        ]
    )

    # 3. Verify symbol is still CUSTOM_NAME
    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert data["instruments"][0]["symbol"] == "CUSTOM_NAME"
    assert data["instruments"][0]["tickers"]["yahoo"] == "AAPL"  # Updated ticker


def test_dual_listing_coexistence(temp_registry_file):
    """Verify that same ISIN with different currencies can coexist."""
    comm_eur = Instrument(
        symbol="GDX_EUR",
        isin="IE00BQQP9F84",
        instrument_type=InstrumentType.ETF,
        asset_class=AssetClass.EQUITY_ETF,
        currency="EUR",
    )
    comm_gbp = Instrument(
        symbol="GDX_GBP",
        isin="IE00BQQP9F84",
        instrument_type=InstrumentType.ETF,
        asset_class=AssetClass.EQUITY_ETF,
        currency="GBP",
    )

    _save_instrument_to_file(comm_eur, temp_registry_file)
    _save_instrument_to_file(comm_gbp, temp_registry_file)

    with open(temp_registry_file) as f:
        data = yaml.safe_load(f)

    assert len(data["instruments"]) == 2
    currencies = [c["currency"] for c in data["instruments"]]
    assert "EUR" in currencies
    assert "GBP" in currencies
