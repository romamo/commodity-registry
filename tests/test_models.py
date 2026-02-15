import pytest
from pydantic import ValidationError
from commodity_registry.models import Commodity, ValidationPoint, Tickers, AssetClass, InstrumentType

def test_validation_point_valid():
    vp = ValidationPoint(date="2024-01-01", price=100.5)
    assert vp.date == "2024-01-01"
    assert vp.price == 100.5

def test_tickers_valid():
    tickers = Tickers(yahoo="AAPL", ft="AAPL:NSQ")
    assert tickers.yahoo == "AAPL"
    assert tickers.ft == "AAPL:NSQ"

def test_commodity_minimal():
    c = Commodity(
        name="TEST_ETF",
        asset_class=AssetClass.EQUITY_ETF,
        instrument_type=InstrumentType.ETF,
        currency="USD"
    )
    assert c.name == "TEST_ETF"
    assert c.currency == "USD"
    assert c.asset_class == AssetClass.EQUITY_ETF

def test_commodity_full():
    c = Commodity(
        name="TEST",
        isin="US0378331005", # Valid AAPL ISIN
        instrument_type=InstrumentType.STOCK,
        asset_class=AssetClass.STOCK,
        currency="USD",
        tickers={"yahoo": "TEST"},
        validation_points=[{"date": "2024-01-01", "price": 100.0}]
    )
    assert c.isin == "US0378331005"
    assert c.tickers.yahoo == "TEST"
    assert len(c.validation_points) == 1

def test_isin_validation():
    # Valid ISIN (Apple)
    Commodity(name="AAPL", isin="US0378331005", instrument_type=InstrumentType.STOCK, asset_class=AssetClass.STOCK, currency="USD")
    
    # Invalid Length
    with pytest.raises(ValidationError, match="12 alphanumeric"):
        Commodity(name="BAD", isin="US123", instrument_type=InstrumentType.STOCK, asset_class=AssetClass.STOCK, currency="USD")
        
    # Invalid Country Code
    with pytest.raises(ValidationError, match="2-letter country code"):
        Commodity(name="BAD", isin="120378331005", instrument_type=InstrumentType.STOCK, asset_class=AssetClass.STOCK, currency="USD")
        
    # Invalid Checksum (last digit changed from 5 to 6)
    with pytest.raises(ValidationError, match="Invalid ISIN checksum"):
        Commodity(name="BAD", isin="US0378331006", instrument_type=InstrumentType.STOCK, asset_class=AssetClass.STOCK, currency="USD")

def test_commodity_invalid_currency():
    with pytest.raises(ValidationError):
        Commodity(
            name="Test",
            asset_class=AssetClass.EQUITY_ETF,
            instrument_type=InstrumentType.ETF,
            currency="INVALID" # Should be 3-4 chars 
        )

def test_enums():
    assert AssetClass.EQUITY_ETF == "EquityETF"
    assert InstrumentType.ETF == "ETF"
    
    with pytest.raises(ValueError):
        InstrumentType("InvalidType")
