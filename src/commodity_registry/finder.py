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

logger = logging.getLogger(__name__)


def get_source(provider: str):
    if provider == "yahoo":
        return YFinanceDataSource() if YFinanceDataSource else None
    if provider == "ft":
        return FTDataSource() if FTDataSource else None
    return None


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


def search_isin(criteria: SecurityCriteria) -> list["SearchResult"]:
    """
    Searches for securities across all providers using SecurityCriteria.
    Returns typed search results from each provider.
    """
    results = []
    providers = []
    if YFinanceDataSource:
        providers.append("yahoo")
    if FTDataSource:
        providers.append("ft")

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
