import pytest
from unittest.mock import MagicMock, patch
from pydantic_market_data.models import SecurityCriteria, Symbol
from commodity_registry.finder import search_isin, fetch_metadata, verify_ticker

@pytest.fixture
def mock_yahoo_source():
    with patch("commodity_registry.finder.YFinanceDataSource") as mock:
        yield mock

@pytest.fixture
def mock_ft_source():
    with patch("commodity_registry.finder.FTDataSource") as mock:
        yield mock

def test_search_isin_yahoo_only(mock_yahoo_source, mock_ft_source):
    # Setup mocks
    mock_yahoo_instance = MagicMock()
    mock_yahoo_source.return_value = mock_yahoo_instance
    
    # Simulate FT not installed by making it None in the finder module
    with patch("commodity_registry.finder.FTDataSource", None):
        # Mock resolve result
        mock_symbol = Symbol(
            ticker="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ"
        )
        mock_yahoo_instance.resolve.return_value = mock_symbol
        
        criteria = SecurityCriteria(isin="US0378331005")
        results = search_isin(criteria)
        
        assert len(results) == 1
        assert results[0].provider == "yahoo"
        assert results[0].ticker == "AAPL"
        assert results[0].name == "Apple Inc."

def test_fetch_metadata_failure(mock_yahoo_source):
    mock_yahoo_instance = MagicMock()
    mock_yahoo_source.return_value = mock_yahoo_instance
    mock_yahoo_instance.resolve.return_value = None
    
    data = fetch_metadata("INVALID", provider="yahoo")
    assert data == {}

def test_verify_ticker_success(mock_yahoo_source):
    mock_yahoo_instance = MagicMock()
    mock_yahoo_source.return_value = mock_yahoo_instance
    mock_yahoo_instance.validate.return_value = True
    
    result = verify_ticker("AAPL", "2024-01-01", 190.0, provider="yahoo")
    assert result is True
    mock_yahoo_instance.validate.assert_called_with("AAPL", "2024-01-01", 190.0)
