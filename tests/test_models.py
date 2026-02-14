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
        name="TEST_ETF",
        asset_class=AssetClass.EQUITY_ETF,
        instrument_type=InstrumentType.ETF,
        currency="USD",
        isin="US1234567890",
        issuer="Test Issuer",
        underlying="Test Index",
        tickers=Tickers(yahoo="TEST"),
        validation_points=[ValidationPoint(date="2024-01-01", price=50.0)]
    )
    assert c.isin == "US1234567890"
    assert c.tickers.yahoo == "TEST"
    assert len(c.validation_points) == 1

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
