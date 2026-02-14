from commodity_registry.registry import CommodityRegistry


def test_smoke():
    print("Smoke test starting...")
    registry = CommodityRegistry()
    assert registry is not None
    print("Smoke test passed.")


if __name__ == "__main__":
    test_smoke()
