import pytest
import yaml
from pathlib import Path
from commodity_registry.registry import CommodityRegistry, get_registry
from commodity_registry.models import AssetClass, InstrumentType

@pytest.fixture
def temp_registry_dir(tmp_path):
    # Create a mock registry structure
    reg_dir = tmp_path / "commodities"
    reg_dir.mkdir()
    
    # Create a base file
    base_file = reg_dir / "base.yaml"
    base_data = {
        "commodities": [
            {
                "name": "AAPL",
                "isin": "US0378331005",
                "asset_class": "Stock",
                "instrument_type": "Stock",
                "currency": "USD",
                "tickers": {"yahoo": "AAPL"}
            },
            {
                "name": "XAID",
                "isin": "GB00B00FHZ82",
                "asset_class": "CommodityETF",
                "instrument_type": "ETF",
                "currency": "GBP",
                "tickers": {"yahoo": "XAID.L"}
            }
        ]
    }
    with open(base_file, "w") as f:
        yaml.dump(base_data, f)
        
    return reg_dir

def test_registry_loading(temp_registry_dir):
    reg = CommodityRegistry(extra_paths=[temp_registry_dir], include_bundled=False)
    all_commodities = reg.get_all()
    assert len(all_commodities) == 2
    assert any(c.name == "AAPL" for c in all_commodities)
    assert any(c.name == "XAID" for c in all_commodities)

def test_find_by_isin(temp_registry_dir):
    reg = CommodityRegistry(extra_paths=[temp_registry_dir], include_bundled=False)
    c = reg.find_by_isin("US0378331005")
    assert c is not None
    assert c.name == "AAPL"

def test_find_candidates_by_name(temp_registry_dir):
    reg = CommodityRegistry(extra_paths=[temp_registry_dir], include_bundled=False)
    candidates = reg.find_candidates("AAPL")
    assert len(candidates) == 1
    assert candidates[0].name == "AAPL"

def test_find_by_ticker(temp_registry_dir):
    reg = CommodityRegistry(extra_paths=[temp_registry_dir], include_bundled=False)
    c = reg.find_by_ticker("yahoo", "XAID.L")
    assert c is not None
    assert c.name == "XAID"

def test_registry_merging(temp_registry_dir):
    # Add an override file
    override_file = temp_registry_dir / "override.yaml"
    override_data = {
        "commodities": [
            {
                "name": "AAPL",
                "isin": "US0378331005",
                "asset_class": "Stock",
                "instrument_type": "Stock",
                "currency": "USD",
                "issuer": "Overridden Issuer"
            }
        ]
    }
    with open(override_file, "w") as f:
        yaml.dump(override_data, f)
        
    reg = CommodityRegistry(extra_paths=[temp_registry_dir], include_bundled=False)
    c = reg.find_by_isin("US0378331005")
    assert c.issuer == "Overridden Issuer"
    # Ensure tickers are NOT lost if not in override (wait, need to check merge behavior)
    # The current implementation might replace the whole object if ISIN matches.
    # Let's verify merge logic in registry.py
    # NOTE: The current simple implementation overrides the entire object if ISIN matches.

def test_recursive_loading(temp_registry_dir):
    # Create a nested directory
    nested_dir = temp_registry_dir / "subdir" / "nested"
    nested_dir.mkdir(parents=True)
    
    # Add a file in the nested directory
    nested_file = nested_dir / "nested.yaml"
    nested_data = {
        "commodities": [
            {
                "name": "NESTED",
                "isin": "US0378331005", # Valid ISIN (reused AAPL for validity)
                "asset_class": "Stock",
                "instrument_type": "Stock",
                "currency": "USD"
            }
        ]
    }
    with open(nested_file, "w") as f:
        yaml.dump(nested_data, f)
        
    reg = CommodityRegistry(extra_paths=[temp_registry_dir], include_bundled=False)
    c = reg.find_candidates("NESTED")
    assert len(c) == 1
    assert c[0].name == "NESTED"
