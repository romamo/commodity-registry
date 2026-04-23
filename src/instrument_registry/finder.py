from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .registry import InstrumentRegistry

import diskcache  # type: ignore[import-untyped]
import platformdirs
from pydantic_market_data.models import (
    Currency,
    CurrencyCode,
    Price,
    SecurityQuery,
    Symbol,
)

from .interfaces import DataProvider, InstrumentLookup, ProviderName, SearchResult
from .models import AssetClass, InstrumentType, _map_asset_class

logger = logging.getLogger(__name__)

CACHE_DIR_ENV_VAR = "INSTRUMENT_REGISTRY_CACHE_DIR"

_RAW_TYPE_MAP: list[tuple[str, InstrumentType, AssetClass]] = [
    ("ETF", InstrumentType.ETF, AssetClass.EQUITY_ETF),
    ("MUTUALFUND", InstrumentType.ETF, AssetClass.EQUITY_ETF),
    ("INDEX", InstrumentType.INDEX, AssetClass.STOCK),
    ("CRYPTOCURRENCY", InstrumentType.CRYPTO, AssetClass.CRYPTO),
    ("CURRENCY", InstrumentType.CASH, AssetClass.CASH),
    ("CASH", InstrumentType.CASH, AssetClass.CASH),
]


def _infer_types(raw_asset_class: str | None) -> tuple[InstrumentType, AssetClass]:
    raw = (raw_asset_class or "").upper()
    for keyword, inst_type, asset_class in _RAW_TYPE_MAP:
        if keyword in raw:
            return inst_type, asset_class
    return InstrumentType.STOCK, AssetClass.STOCK


def _get_cache_dir() -> Path:
    """Return the cache directory, allowing an env-var override for sandboxed runs."""
    cache_dir = os.getenv(CACHE_DIR_ENV_VAR)
    if cache_dir:
        return Path(cache_dir).expanduser()
    return Path(platformdirs.user_cache_dir("instrument-registry"))


def _fallback_cache_dir() -> Path:
    """Use a local cache directory when the platform cache is unavailable."""
    return Path.cwd() / ".cache" / "instrument-registry"


def _init_cache() -> diskcache.Cache:
    cache_dir = _get_cache_dir()
    try:
        return diskcache.Cache(str(cache_dir))
    except (OSError, sqlite3.OperationalError) as exc:
        if os.getenv(CACHE_DIR_ENV_VAR):
            raise

        fallback_dir = _fallback_cache_dir()
        logger.warning(
            "Could not open cache directory %s (%s). Falling back to %s.",
            cache_dir,
            exc,
            fallback_dir,
        )
        return diskcache.Cache(str(fallback_dir))


# Initialize cache (expires in 1 day by default)
cache = _init_cache()


try:
    from py_yfinance import YFinanceDataSource as _YFDS

    YFinanceDataSource: type[Any] | None = _YFDS
except ImportError as e:
    # Optional dependency exception handling:
    # py-yfinance is an optional plugin. If it's missing, we just log and proceed
    # with other available providers (or local registry data only).
    logger.debug(f"Failed to import py_yfinance: {e}")
    YFinanceDataSource = None

try:
    from ftmarkets import FTDataSource as _FTDS

    FTDataSource: type[Any] | None = _FTDS
except ImportError as e:
    # Optional dependency exception handling for FTMarkets as well.
    logger.debug(f"Failed to import ftmarkets: {e}")
    FTDataSource = None

# Default provider selection logic moved to get_data_provider helper


def get_data_provider(provider: ProviderName) -> DataProvider:
    if provider == ProviderName.YAHOO:
        if YFinanceDataSource is None:
            raise ImportError("py-yfinance is not installed. Install with [providers] extra.")
        return YFinanceDataSource()
    if provider == ProviderName.FT:
        if FTDataSource is None:
            raise ImportError("ftmarkets is not installed. Install with [providers] extra.")
        return FTDataSource()
    raise ValueError(f"Unknown provider: {provider}")


def get_available_providers() -> list[ProviderName]:
    """Returns a list of available data providers."""
    providers: list[ProviderName] = []
    if YFinanceDataSource is not None:
        providers.append(ProviderName.YAHOO)
    if FTDataSource is not None:
        providers.append(ProviderName.FT)
    return providers


@cache.memoize(expire=86400)  # 24 hours
def fetch_metadata(
    symbol: Symbol.Input, isin: str | None = None, provider: ProviderName = ProviderName.YAHOO
) -> SearchResult | None:
    """
    Fetches common metadata for a security.
    """
    data_provider = get_data_provider(provider)

    # try...except removed to fail fast.
    # data_provider.resolve may raise ValidationError or other source-specific errors.
    # Boundary conversion
    symbol_vo = Symbol(symbol) if not isinstance(symbol, Symbol) else symbol
    criteria = SecurityQuery(symbol=symbol_vo, isin=isin)
    security = data_provider.resolve(criteria)

    if not security:
        logger.debug(f"No security resolved for {symbol} via {provider}")
        return None

    logger.debug(
        f"Fetched metadata for {symbol} ({provider}): ISIN={getattr(security, 'isin', None)}"
    )

    currency_val = (
        CurrencyCode(Currency(str(security.currency).upper())) if security.currency else None
    )

    return SearchResult(
        provider=provider,
        symbol=security.symbol,
        name=security.name,
        currency=currency_val,
        asset_class=None,  # Not currently resolved via basic symbol search
        instrument_type=None,
        price=None,
    )


@cache.memoize(expire=86400)
def derive_provider_ticker(
    name: str, asset_class: AssetClass | str | None, provider: ProviderName | str
) -> str | None:
    """
    Derives a provider-specific ticker based on an instrument's name and asset class.
    Used when an explicit ticker is missing from the registry.
    """
    # Normalize provider name
    p_name = provider.value if isinstance(provider, ProviderName) else str(provider).lower()

    if p_name == ProviderName.YAHOO.value:
        # Yahoo Crypto Pattern: {TOKEN}-USD
        ac = str(asset_class).upper() if asset_class else ""
        if ("CRYPTO" in ac) and "-" not in name:
            return f"{name}-USD"

    return None


def search_isin(criteria: SecurityQuery) -> list[SearchResult]:
    """
    Searches for securities across all providers using SecurityQuery.
    Returns typed search results from each provider.
    """
    results = []
    providers = get_available_providers()

    for p in providers:
        try:
            data_provider = get_data_provider(p)
            security_result = data_provider.resolve(criteria)
            if security_result:
                aclass = (
                    _map_asset_class(security_result.asset_class)
                    if security_result.asset_class
                    else None
                )

                # Filtering by requested asset_class if provided
                if criteria.asset_class:
                    req_aclass = _map_asset_class(criteria.asset_class)
                    if req_aclass and aclass and aclass != req_aclass:
                        logger.debug(
                            f"Skipping result {security_result.symbol} due to asset class mismatch"
                        )
                        continue

                inst_type, resolved_aclass = _infer_types(security_result.asset_class)
                results.append(
                    SearchResult(
                        provider=p,
                        symbol=security_result.symbol,
                        name=security_result.name,
                        currency=security_result.currency,
                        asset_class=aclass or resolved_aclass,
                        instrument_type=inst_type,
                        price=None,
                        price_date=None,
                    )
                )
                # Optimization: First match is enough
                return results
        except Exception as e:
            logger.warning(
                f"Provider {p} failed to resolve {criteria.isin or criteria.symbol}: {e}"
            )
            continue
        else:
            logger.debug(f"No results from provider {p} for {criteria.isin or criteria.symbol}")

    if not results and criteria.symbol and criteria.asset_class:
        derived = derive_provider_ticker(
            str(criteria.symbol), criteria.asset_class, ProviderName.YAHOO
        )
        if derived and derived != str(criteria.symbol):
            crypto_criteria = criteria.model_copy(update={"symbol": derived})
            logger.debug(f"Retrying resolution with derived ticker: {crypto_criteria.symbol}")
            return search_isin(crypto_criteria)

    return results


def verify_ticker(
    symbol: Symbol.Input,
    date: date,
    price: Price.Input,
    provider: ProviderName = ProviderName.YAHOO,
) -> bool:
    """
    Verifies if a ticker traded at a specific price on a given date.
    """
    data_provider = get_data_provider(provider)
    # try...except removed to fail fast.
    # Boundary conversion
    symbol_vo = Symbol(symbol) if not isinstance(symbol, Symbol) else symbol
    price_vo = Price(price) if not isinstance(price, Price) else price
    return data_provider.validate(symbol_vo, date, price_vo)


def resolve_currency(
    symbol: str, target_currency: CurrencyCode.Input | None = None, verify: bool = False
) -> SearchResult | None:
    """
    Programmatically resolves standard currencies to Yahoo tickers (e.g. EUR -> EURUSD=X).
    Supports pairs strings like 'EURUSD', 'EUR/USD', 'EUR-USD'.
    If verify=True, performs a live lookup to ensure the ticker exists.
    Returns a SearchResult or None if not a valid currency pair or not found.
    """
    if target_currency is None:
        target_currency = "USD"

    quote_str = str(target_currency).upper()
    if not symbol:
        return None

    base = symbol.upper()

    # Handle composite inputs (e.g. "EURUSD", "EUR/USD")
    if len(base) == 6 and base.isalpha():
        # "EURUSD" -> base=EUR, quote=USD
        quote_str = base[3:].upper()
        base = base[:3]
    elif "/" in base:
        parts = base.split("/")
        if len(parts) == 2:
            base = parts[0]
            quote_str = parts[1].upper()
    elif "-" in base:
        parts = base.split("-")
        if len(parts) == 2:
            base = parts[0]
            quote_str = parts[1].upper()

    # Validate lengths and characters (must be 3 alphabetic letters each)
    if len(base) != 3 or len(quote_str) != 3 or not base.isalpha() or not quote_str.isalpha():
        return None

    if base == quote_str:
        return None

    # 1. Target is USD (e.g. EUR in USD -> EURUSD=X)
    if quote_str == "USD":
        ticker = f"{base}USD=X"

    # 2. Symbol is USD (e.g. USD in EUR -> EUR=X)
    # Yahoo convention: "{CURRENCY}=X" usually means "USD/{CURRENCY}" (Price of USD in CURRENCY)
    elif base == "USD":
        ticker = f"{quote_str}=X"

    # 3. Cross Rates (e.g. EUR in JPY -> EURJPY=X)
    else:
        ticker = f"{base}{quote_str}=X"

    if verify:
        # Avoid circular import if fetch_metadata moved, but here they are in same file
        if not fetch_metadata(ticker, provider=ProviderName.YAHOO):
            return None

    from .models import AssetClass, InstrumentType

    return SearchResult(
        provider=ProviderName.YAHOO,
        symbol=Symbol(root=ticker),
        name=base,
        currency=CurrencyCode(Currency(quote_str)),
        asset_class=AssetClass.CASH,
        instrument_type=InstrumentType.CASH,
    )


def resolve_security(
    criteria: SecurityQuery,
    verify: bool = False,
    registry: InstrumentLookup | None = None,
    include_price: bool = False,
) -> SearchResult | None:
    """
    Unified security resolution routine.
    1. Check Registry (Strict fields)
    2. Try Programmatic Currency Resolution (if it looks like a pair)
    3. Perform Online Search (ISIN then Symbol)
    """
    # 1. Registry Match (Final Truth)
    if registry:
        candidates = registry.find_candidates(criteria)
        if candidates:
            cand = candidates[0]
            # Convert Instrument to SearchResult
            # Determine the best ticker and source from registry + derivation
            best_ticker = None
            source = ProviderName.YAHOO

            if cand.tickers:
                if cand.tickers.yahoo:
                    best_ticker = cand.tickers.yahoo
                    source = ProviderName.YAHOO
                elif cand.tickers.ft:
                    best_ticker = cand.tickers.ft
                    source = ProviderName.FT
                elif cand.tickers.google:
                    best_ticker = cand.tickers.google
                    source = ProviderName.GOOGLE

            if not best_ticker:
                # Better way to bypass hardcoding: Derive ticker if missing from registry
                best_ticker = derive_provider_ticker(
                    cand.name, cand.asset_class, ProviderName.YAHOO
                )
                source = ProviderName.YAHOO

            # Optional: Fetch price (current or historical)
            price = None
            price_date = None
            if best_ticker and include_price:
                target_date = criteria.price_on.date if criteria.price_on else None
                price = fetch_price(best_ticker, provider=source, date=target_date)
                price_date = target_date or date.today()

            return SearchResult(
                provider=source,
                symbol=Symbol(root=best_ticker) if best_ticker else Symbol(root=cand.name),
                name=cand.name,
                currency=cand.currency,
                asset_class=cand.asset_class,
                instrument_type=cand.instrument_type,
                price=price,
                price_date=price_date,
                country=cand.country,
                metadata=cand.metadata,
            )

    # 2. Programmatic FX Resolution
    # Only perform FX resolution if the user is searching for CASH/FOREX
    # or hasn't specified an asset class. Symbols like 'TRX' should be resolved
    # via online search if looking for Crypto.
    if criteria.symbol:
        from .models import AssetClass

        is_cash_search = (
            criteria.asset_class is None
            or _map_asset_class(criteria.asset_class) == AssetClass.CASH
        )
        if is_cash_search:
            fx_res = resolve_currency(
                str(criteria.symbol), target_currency=criteria.currency, verify=verify
            )
            if fx_res:
                return fx_res

    # 3. Online Search
    results = search_isin(criteria)
    if results:
        res = results[0]
        # Fetch price (current or historical)
        if include_price:
            target_date = criteria.price_on.date if criteria.price_on else None
            res.price = fetch_price(res.symbol, provider=res.provider, date=target_date)
            res.price_date = target_date or date.today()
        return res

    return None


def resolve_and_persist(
    criteria: SecurityQuery,
    registry: InstrumentRegistry | None = None,
    store: bool = True,
    target_path: Path | None = None,
    dry_run: bool = False,
    include_price: bool = False,
) -> SearchResult | None:
    """
    High-level resolution workflow:
    1. Check Registry (Local)
    2. Online Search + Validation
    3. Auto-Save to Registry (if new and store=True)

    Returns SearchResult or None.
    """
    # 1. Resolve (logic encapsulated in resolve_security)
    # verify=True ensures online results are validated (price check)
    res = resolve_security(criteria, verify=True, registry=registry, include_price=include_price)

    if not res:
        return None

    # 2. Check if we need to persist it
    if store and registry:
        # Check if known using a stricter criteria
        known_candidates = registry.find_candidates(criteria)
        logger.debug(
            f"Persistence check: found {len(known_candidates)} candidates "
            f"for {criteria.isin or criteria.symbol}"
        )
        if not known_candidates:
            # It's a new discovery!
            logger.info(f"Persisting new discovery: {res.name} ({res.symbol})")

            from .registry import add_instrument

            inst_type, asset_class = _infer_types(res.asset_class)

            # Do not persist CASH/CURRENCY to file
            if inst_type == InstrumentType.CASH or asset_class == AssetClass.CASH:
                logger.debug(f"Skipping persistence for {res.name} as it is CASH/CURRENCY.")
                # Skip persistence for FX/Cash instruments.
                return res

            # Determine target path
            if target_path:
                final_target_path = Path(target_path).expanduser()
            else:
                # Default logic
                import os

                import platformdirs

                env_path = os.getenv("INSTRUMENT_REGISTRY_PATH")
                if env_path:
                    final_target_path = Path(env_path).expanduser()
                else:
                    final_target_path = Path(platformdirs.user_data_dir("instrument-registry"))

            new_instrument = add_instrument(
                criteria=criteria,
                metadata=res,
                target_path=final_target_path,
                instrument_type=inst_type,
                asset_class=asset_class,
                dry_run=dry_run,
            )
            res.name = new_instrument.name

            if not dry_run:
                # Refresh registry to include new item
                registry.load_path(final_target_path)
                registry._rebuild_indices()

    return res


def fetch_price(
    symbol: Symbol.Input, provider: ProviderName = ProviderName.YAHOO, date: date | None = None
) -> Price | None:
    """
    Fetches the price for a ticker (current or historical).
    """
    data_provider = get_data_provider(provider)
    # Boundary conversion
    symbol_vo = Symbol(symbol) if not isinstance(symbol, Symbol) else symbol
    val = data_provider.get_price(symbol_vo, date=date)
    if val is None:
        return None
    # Support both float (from Protocol) and Price (from actual implementations)
    if isinstance(val, Price):
        return val
    return Price(val)
