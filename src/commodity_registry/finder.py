import logging
from typing import Any

from .interfaces import SearchResult

try:
    from py_yfinance import YFinanceDataSource
except ImportError:
    YFinanceDataSource = None

try:
    from ftmarkets import FTDataSource
except ImportError:
    FTDataSource = None

from pydantic_market_data.models import SecurityCriteria
import diskcache

logger = logging.getLogger(__name__)

# Initialize cache (expires in 1 day by default)
cache = diskcache.Cache(".cache")


def get_source(provider: str):
    if provider == "yahoo":
        return YFinanceDataSource() if YFinanceDataSource else None
    if provider == "ft":
        return FTDataSource() if FTDataSource else None
    return None


def get_available_providers() -> list[str]:
    """Returns a list of available data providers (e.g. ['yahoo', 'ft'])."""
    providers = []
    if YFinanceDataSource:
        providers.append("yahoo")
    if FTDataSource:
        providers.append("ft")
    return providers


@cache.memoize(expire=86400) # 24 hours
def fetch_metadata(ticker: str, isin: str | None = None, provider: str = "yahoo") -> dict[str, Any]:
    """
    Fetches common metadata for a security.
    """
    source = get_source(provider)
    if not source:
        logger.error(f"Provider '{provider}' not available or not installed.")
        return {}

    try:
        criteria = SecurityCriteria(symbol=ticker, isin=isin)
        symbol = source.resolve(criteria)

        if not symbol:
            return {}

        return {
            "name": symbol.name,
            "currency": symbol.currency,
            "ticker": symbol.ticker,
        }

    except Exception as e:
        logger.error(f"Error fetching metadata from {provider} for {ticker}: {e}")
        return {}


@cache.memoize(expire=86400)
def search_isin(criteria: SecurityCriteria) -> list["SearchResult"]:
    """
    Searches for securities across all providers using SecurityCriteria.
    Returns typed search results from each provider.
    """
    results = []
    providers = get_available_providers()

    for p in providers:
        source = get_source(p)
        try:
            symbol_result = source.resolve(criteria)
            if symbol_result:
                results.append(
                    SearchResult(
                        provider=p,
                        ticker=symbol_result.ticker,
                        name=symbol_result.name,
                        currency=symbol_result.currency,
                    )
                )
        except Exception as e:
            logger.debug(f"Search failed for {criteria.isin} on {p}: {e}")

    return results


def verify_ticker(ticker: str, date: str, price: float, provider: str = "yahoo") -> bool:
    """
    Verifies if a ticker traded at a specific price on a given date.
    """
    source = get_source(provider)
    if not source:
        return False

    try:
        return source.validate(ticker, date, price)
    except Exception as e:
        logger.error(f"Error verifying ticker {ticker} on {date} via {provider}: {e}")
        return False


def resolve_currency(
    symbol: str, target_currency: str = "USD", verify: bool = False
) -> "SearchResult | None":
    """
    Programmatically resolves standard currencies to Yahoo tickers (e.g. EUR -> EURUSD=X).
    Supports pairs strings like 'EURUSD', 'EUR/USD', 'EUR-USD'.
    If verify=True, performs a live lookup to ensure the ticker exists.
    Returns a SearchResult or None if not a valid currency pair or not found.
    """
    if not symbol:
        return None
        
    base = symbol.upper()
    quote = target_currency.upper()
    
    # Handle composite inputs (e.g. "EURUSD", "EUR/USD")
    if len(base) == 6 and base.isalpha():
        # "EURUSD" -> base=EUR, quote=USD
        quote = base[3:]
        base = base[:3]
    elif "/" in base:
        parts = base.split("/")
        if len(parts) == 2:
            base = parts[0]
            quote = parts[1]
    elif "-" in base:
        parts = base.split("-")
        if len(parts) == 2:
            base = parts[0]
            quote = parts[1]

    # Validate lengths and characters (must be 3 alphabetic letters each)
    if len(base) != 3 or len(quote) != 3 or not base.isalpha() or not quote.isalpha():
        return None
        
    if base == quote:
        return None
        
    # 1. Target is USD (e.g. EUR in USD -> EURUSD=X)
    if quote == "USD":
        ticker = f"{base}USD=X"
        
    # 2. Symbol is USD (e.g. USD in EUR -> EUR=X)
    # Yahoo convention: "{CURRENCY}=X" usually means "USD/{CURRENCY}" (Price of USD in CURRENCY)
    elif base == "USD":
        ticker = f"{quote}=X"
        
    # 3. Cross Rates (e.g. EUR in JPY -> EURJPY=X)
    else:
        ticker = f"{base}{quote}=X"
    
    if verify:
        # Avoid circular import if fetch_metadata moved, but here they are in same file
        if not fetch_metadata(ticker, provider="yahoo"):
            return None

    return SearchResult(
        provider="yahoo",
        ticker=ticker,
        name=base,
        currency=quote
    )


def fetch_price(ticker: str, provider: str = "yahoo") -> float | None:
    """
    Fetches the current real-time/delayed price for a ticker.
    """
    source = get_source(provider)
    if not source:
        return None
        
    try:
        # Check if source has get_price method (it should if it follows implicit interface)
        if hasattr(source, "get_price"):
            return source.get_price(ticker)
        return None
    except Exception as e:
        logger.error(f"Error fetching price for {ticker} from {provider}: {e}")
        return None
