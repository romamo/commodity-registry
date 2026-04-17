from unittest.mock import MagicMock, patch

import pytest

py_yfinance_source = pytest.importorskip("py_yfinance.source")
YFinanceDataSource = py_yfinance_source.YFinanceDataSource


# Simple mock for a DataFrame to avoid complex MagicMocking of .iloc
class MockDataFrame:
    def __init__(self, data):
        self.data = data
        self.empty = False

    @property
    def iloc(self):
        return self

    def __getitem__(self, index):
        # Allow index access like df.iloc[-1]
        if index == -1:
            return self.data
        raise IndexError("MockDataFrame only supports index -1")


@patch("py_yfinance.source.yf.Ticker")
def test_get_price_optimization(mock_ticker_cls):
    """
    Unit test for py-yfinance optimization: ensure get_price makes minimal calls.
    """
    # Setup the mock ticker instance
    mock_ticker_instance = MagicMock()
    mock_ticker_cls.return_value = mock_ticker_instance

    # Create robust mock history
    # get_price calls: hist = t.history(...); if not hist.empty; return hist.iloc[-1]["Close"]
    mock_row = {"Close": 150.0}
    mock_hist = MockDataFrame(mock_row)

    mock_ticker_instance.history.return_value = mock_hist

    ds = YFinanceDataSource()
    from pydantic_market_data.models import Symbol

    price = ds.get_price(Symbol(root="AAPL"))

    from pydantic_market_data.models import Price

    assert price == Price(150.0), f"Expected Price(150.0), got {price}"

    # 2. history() should be called EXACTLY once
    assert mock_ticker_instance.history.call_count == 1

    # 3. Verify arguments: interval="1d", auto_adjust=False, actions=False
    call_args = mock_ticker_instance.history.call_args
    _, kwargs = call_args

    assert kwargs.get("interval") == "1d"
    assert kwargs.get("auto_adjust") is False
    assert kwargs.get("actions") is False
    assert "start" in kwargs
    assert "end" in kwargs

    print("Optimization verified: Single history call with strict parameters.")
