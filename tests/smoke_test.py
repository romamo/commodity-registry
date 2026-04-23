from pydantic_market_data.models import SecurityQuery

from instrument_registry.registry import InstrumentRegistry


def test_smoke():
    print("Smoke test starting...")
    registry = InstrumentRegistry()
    assert registry is not None

    # Verify search (string wrapped in Criteria)
    res = registry.find_candidates(SecurityQuery(symbol="AAPL"))
    assert isinstance(res, list)

    # Verify search (Criteria)
    res2 = registry.find_candidates(SecurityQuery(symbol="AAPL"))
    assert isinstance(res2, list)

    print("Smoke test passed.")


if __name__ == "__main__":
    test_smoke()
