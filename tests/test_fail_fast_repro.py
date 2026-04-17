import pytest

from instrument_registry.registry import InstrumentRegistry


def test_registry_fail_fast_on_invalid_yaml(tmp_path):
    """
    Ensure the registry raises an exception when loading an invalid YAML file
    (e.g. missing required field 'currency').
    """
    # Create invalid YAML file
    invalid_yaml = tmp_path / "manual.yaml"
    content = """
instruments:
- name: INVALID_COMMODITY
  isin: US0000000001
  instrument_type: Stock
  asset_class: Stock
  # Missing currency
  tickers:
    yahoo: INVALID
"""
    invalid_yaml.write_text(content)

    # Attempt to load registry
    # We expect pydantic.ValidationError or similar to be raised
    with pytest.raises(Exception) as excinfo:
        # Load registry with only this path
        InstrumentRegistry(include_bundled=False, extra_paths=[invalid_yaml])

    # Verify the error message contains relevant details if possible,
    # but primarily we just want it to crash (raise) instead of swallowing the error.
    assert (
        "validation error" in str(excinfo.value).lower()
        or "field required" in str(excinfo.value).lower()
    )
