from pathlib import Path
from typing import Optional

import yaml
from pydantic_market_data.models import SecurityCriteria

from .interfaces import SearchResult
from .models import AssetClass, Commodity, CommodityFile, InstrumentType
from .resources import get_commodity_files


class StrictSafeLoader(yaml.SafeLoader):
    """YAML Loader that disallows duplicate keys."""

    def construct_mapping(self, node, deep=False):
        mapping = []
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    f"Duplicate key found in YAML: {key}", key_node.start_mark
                )
            mapping.append(key)
        return super().construct_mapping(node, deep=deep)


class CommodityRegistry:
    def __init__(self, include_bundled: bool = True, extra_paths: list[Path] | None = None):
        self._commodities: list[Commodity] = []
        self._load_errors: list[str] = []
        self._by_isin: dict[str, list[Commodity]] = {}
        self._by_figi: dict[str, Commodity] = {}
        self._by_name: dict[str, Commodity] = {}
        self._by_ticker: dict[str, Commodity] = {}  # Map "PROVIDER:TICKER" -> Commodity

        if include_bundled:
            self.load_bundled_data()

        if extra_paths:
            for p in extra_paths:
                self.load_path(p)

        self._rebuild_indices()

    def load_bundled_data(self):
        """Loads all commodity data from the bundled YAML files."""
        for file_path in get_commodity_files():
            self._load_file(file_path)

    def load_path(self, path: Path):
        """Loads commodity data from a specific file or directory (recursively)."""
        if path.is_dir():
            for p in sorted(path.rglob("*")):
                if p.is_file() and p.suffix in (".yaml", ".yml"):
                    self._load_file(p)
        else:
            self._load_file(path)

    def _load_file(self, path: Path):
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = yaml.load(f, Loader=StrictSafeLoader)

            if not data:
                return

            file_model = CommodityFile(**data)
            self._commodities.extend(file_model.commodities)
        except Exception as e:
            err_msg = f"Error loading {path}: {e}"
            print(err_msg)
            self._load_errors.append(err_msg)

    @property
    def load_errors(self) -> list[str]:
        return self._load_errors

    def _rebuild_indices(self):
        self._by_isin = {}
        for c in self._commodities:
            if c.isin:
                isin_key = c.isin.upper()
                if isin_key not in self._by_isin:
                    self._by_isin[isin_key] = []
                self._by_isin[isin_key].insert(0, c) # User overrides first

        self._by_figi = {}
        self._by_name = {c.name.upper(): c for c in self._commodities}
        self._by_ticker = {}

        for c in self._commodities:
            if c.figi:
                self._by_figi[c.figi.upper()] = c

            if c.tickers:
                for provider, ticker in c.tickers.model_dump().items():
                    if ticker:
                        # Later items in self._commodities override earlier ones
                        self._by_ticker[f"{provider.upper()}:{ticker.upper()}"] = c

    def find_by_isin(self, isin: str, currency: str | None = None) -> Commodity | None:
        matches = self.find_candidates(isin, currency)
        return matches[0] if matches else None

    def find_candidates(self, token: str, currency: str | None = None) -> list[Commodity]:
        """
        Finds all commodities matching a token (ISIN, Name, FIGI).
        If currency is provided, filters the results.
        Returns empty list if no match.
        """
        if not token:
            return []

        token = token.upper()
        candidates = []

        # 1. Try ISIN
        candidates.extend(self._by_isin.get(token, []))

        # 2. Try Name
        if token in self._by_name:
            candidates.append(self._by_name[token])

        # 3. Try FIGI
        if token in self._by_figi:
            candidates.append(self._by_figi[token])

        # Deduplicate (by object id or name)
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c.name not in seen:
                unique_candidates.append(c)
                seen.add(c.name)

        if currency:
            currency = currency.upper()
            unique_candidates = [c for c in unique_candidates if c.currency.upper() == currency]

        return unique_candidates

    def find_by_ticker(self, provider: str, ticker: str) -> Commodity | None:
        """
        Finds a commodity by provider-specific ticker.
        Example: find_by_ticker("yahoo", "4GLD.DE")
        """
        return self._by_ticker.get(f"{provider.upper()}:{ticker.upper()}")

    def get_all(self) -> list[Commodity]:
        return self._commodities


# Default registry if imported directly
def get_registry(
    include_bundled: bool = True, extra_paths: list[Path] | None = None
) -> CommodityRegistry:
    return CommodityRegistry(include_bundled=include_bundled, extra_paths=extra_paths)


registry = get_registry()


def add_commodity(
    criteria: SecurityCriteria,
    metadata: Optional["SearchResult"],  # None if not found online
    target_path: Path,
    instrument_type: InstrumentType,
    asset_class: AssetClass,
    verbose: bool = False,
    dry_run: bool = False,
) -> Commodity:
    """
    Adds a new commodity to the registry.

    Uses SecurityCriteria.symbol (from IBKR's underlyingSymbol or symbol field).
    Extracts base ticker (before ':') for Beancount name.
    Stores provider-specific tickers only if found online.
    """
    import re

    # 1. Determine ticker
    if not criteria.symbol:
        raise ValueError("SecurityCriteria.symbol is required")

    # 2. Extract base ticker for Beancount name
    # Example: "ALUM.L" -> "ALUM", "4GLD:GER:EUR" -> "4GLD"
    base_ticker = criteria.symbol.split(":")[0]

    # Sanitize name for Beancount (uppercase, alphanumeric + ._-)
    clean_name = re.sub(r"[^A-Z0-9\._-]", ".", base_ticker.upper())
    clean_name = re.sub(r"\.+", ".", clean_name).strip(".")

    # Ensure it starts with A-Z (Beancount requirement)
    if not re.match(r"^[A-Z]", clean_name):
        clean_name = "X." + clean_name

    # 3. Build tickers dict (only if found online)
    tickers_dict = None
    if metadata and metadata.ticker:
        tickers_dict = {metadata.provider: metadata.ticker}

    # 4. Create commodity
    commodity = Commodity(
        name=clean_name,
        isin=criteria.isin,
        instrument_type=instrument_type,
        asset_class=asset_class,
        currency=criteria.currency or (metadata.currency if metadata else None),
        tickers=tickers_dict,  # Can be None/Empty
        validation_points=[{"date": str(criteria.target_date), "price": criteria.target_price}]
        if criteria.target_date and criteria.target_price
        else None,
    )

    # 5. Save to file
    _save_commodity_to_file(commodity, target_path, verbose, dry_run=dry_run)

    return commodity


def _save_commodity_to_file(
    commodity: Commodity, target_path: Path, verbose: bool = False, dry_run: bool = False
):
    """
    Saves a commodity to the specified YAML file.
    Handles duplicate checks (ISIN/Name) by reading existing file content first.
    """
    if dry_run:
        print(f"\n[DRY RUN] Would save to: {target_path}")
        print(yaml.dump({"commodities": [commodity.model_dump(mode="json", exclude_none=True)]}, sort_keys=False))
        return

    data = None

    if target_path.suffix == "" or target_path.is_dir():
        target_path.mkdir(parents=True, exist_ok=True)
        target_path = target_path / "manual.yaml"
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing to check duplicates
    existing_commodities = []
    if target_path.exists():
        try:
            with open(target_path) as f:
                data = yaml.load(f, Loader=StrictSafeLoader)
                if data:
                    # Handle both list and dict formats
                    # (though usually it's a list or CommodityFile)
                    if isinstance(data, list):
                        existing_commodities = data
                    elif isinstance(data, dict) and "commodities" in data:
                        existing_commodities = data["commodities"]
                    # If it's just raw commodity dicts
        except Exception as e:
            if verbose:
                print(
                    f"Warning: Could not read existing file {target_path} for duplicate check: {e}"
                )

    # Check for duplicates and update if needed
    for i, existing in enumerate(existing_commodities):
        if isinstance(existing, dict):
            # Check ISIN or Name match
            match = False
            if commodity.isin and existing.get("isin") == commodity.isin:
                match = True
            elif existing.get("name") == commodity.name:
                match = True

            if match:
                if verbose:
                    print(f"Updating existing record for {commodity.name} in {target_path.name}")
                existing_commodities[i] = commodity.model_dump(mode="json", exclude_none=True)
                _save_to_yaml(data, existing_commodities, target_path)
                return

    # Append new if no match found
    existing_commodities.append(commodity.model_dump(mode="json", exclude_none=True))
    _save_to_yaml(data, existing_commodities, target_path)

    if verbose:
        print(f"Auto-added {commodity.name} to {target_path}")

def _save_to_yaml(data, commodities, target_path):
    if isinstance(data, dict) and "commodities" in data:
        data_to_dump = data
        data_to_dump["commodities"] = commodities
    else:
        data_to_dump = {"commodities": commodities}

    with open(target_path, "w") as f:
        yaml.dump(data_to_dump, f, sort_keys=False)
