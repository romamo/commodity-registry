from commodity_registry.registry import CommodityRegistry, SecurityCriteria


def test_smoke():
    print("Smoke test starting...")
    registry = CommodityRegistry()
    assert registry is not None
    
    # Verify search (string)
    res = registry.find_candidates("AAPL")
    assert isinstance(res, list)
    
    # Verify search (Criteria)
    res2 = registry.find_candidates(SecurityCriteria(symbol="AAPL"))
    assert isinstance(res2, list)
    
    print("Smoke test passed.")


if __name__ == "__main__":
    test_smoke()
