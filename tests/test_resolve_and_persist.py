from unittest.mock import MagicMock, patch

import pytest
from pydantic_market_data.models import SecurityQuery

from instrument_registry.finder import resolve_and_persist
from instrument_registry.interfaces import SearchResult
from instrument_registry.registry import InstrumentRegistry


@pytest.fixture
def mock_registry(tmp_path):
    # Create a registry backed by a temp file
    reg = InstrumentRegistry(include_bundled=False, extra_paths=[tmp_path])
    return reg


@patch("instrument_registry.finder.search_isin")
@patch("instrument_registry.finder.resolve_security")
@patch("instrument_registry.registry.add_instrument")
@patch("platformdirs.user_data_dir")
def test_resolve_and_persist_new_discovery(
    mock_dirs, mock_add, mock_resolve, mock_search, mock_registry
):
    # Setup path
    mock_dirs.return_value = "/tmp/mock_data_dir"

    # Setup: Not in registry, but found online
    criteria = SecurityQuery(symbol="NEW.STOCK", isin="US0378331005")

    # Mock resolve_security to return a result (simulating online hit)
    res = SearchResult(
        provider="yahoo",  # ProviderName implicitly handles string if matches
        symbol="NEW.STOCK",
        name="New Stock Inc",
        currency="USD",
        asset_class="Stock",
        instrument_type="Stock",
    )
    mock_resolve.return_value = res

    # Execute
    result = resolve_and_persist(criteria, registry=mock_registry, store=True)

    # Verify
    assert result == res
    mock_add.assert_called_once()
    args, kwargs = mock_add.call_args
    assert kwargs["criteria"] == criteria
    assert kwargs["metadata"] == res
    # Ensure it tries to save to the default dir
    assert str(kwargs["target_path"]) == "/tmp/mock_data_dir"


@patch("instrument_registry.finder.resolve_security")
@patch("instrument_registry.registry.add_instrument")
def test_resolve_and_persist_existing(mock_add, mock_resolve, mock_registry):
    # Setup: Already in registry (simulated by resolve_security returning it from registry check)
    # But wait, resolve_and_persist calls resolve_security FIRST.
    # If resolve_security returns it, we need to know if it came from registry or online.
    # resolve_and_persist checks registry manually to decide if it should store.

    criteria = SecurityQuery(symbol="EXISTING", isin="US5949181045")

    res = SearchResult(provider="yahoo", symbol="EXISTING", name="Existing Stock", currency="USD")
    mock_resolve.return_value = res

    # Mock registry.find_candidates to return a match
    with patch.object(mock_registry, "find_candidates", return_value=[MagicMock()]):
        result = resolve_and_persist(criteria, registry=mock_registry, store=True)

        assert result == res
        # Should NOT add because it was found in registry
        mock_add.assert_not_called()
