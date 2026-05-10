import pytest
from pydantic import ValidationError

from instrument_registry.registry import InstrumentRegistry


def test_registry_fail_fast_on_invalid_yaml(tmp_path):
    """Registry must raise ValidationError immediately on load, not swallow it."""
    invalid_yaml = tmp_path / "manual.yaml"
    # 'symbol' is required; 'name' is not a recognised field and 'currency' is missing.
    invalid_yaml.write_text(
        "instruments:\n"
        "- name: INVALID_COMMODITY\n"
        "  isin: US0000000001\n"
        "  instrument_type: Stock\n"
        "  asset_class: Stock\n"
        "  tickers:\n"
        "    yahoo: INVALID\n"
    )

    with pytest.raises(ValidationError) as excinfo:
        InstrumentRegistry(include_bundled=False, extra_paths=[invalid_yaml])

    # Errors are nested: ('instruments', 0, 'symbol') — extract the field name (last loc element)
    errors = excinfo.value.errors()
    missing_fields = {e["loc"][-1] for e in errors if e["type"] == "missing"}
    assert "symbol" in missing_fields
    assert "currency" in missing_fields
