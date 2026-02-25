"""
Interface definitions for commodity registry.

Defines Protocols for type safety and Pydantic models for typed returns.
"""

from datetime import date
from enum import Enum
from typing import Protocol

from pydantic import BaseModel
from pydantic_market_data.models import (
    Currency,
    CurrencyCode,
    Price,
    SecurityCriteria,
    Symbol,
    Ticker,
)

from .models import AssetClass, Commodity, InstrumentType


class ProviderName(str, Enum):
    YAHOO = "yahoo"
    FT = "ft"
    GOOGLE = "google"


class DataProvider(Protocol):
    """Protocol for market data providers (Yahoo, FT, etc.)"""

    def resolve(self, criteria: SecurityCriteria) -> Symbol | None:
        """Resolve security using search criteria"""
        ...

    def validate(self, ticker: Ticker.Input, date: date, price: Price.Input) -> bool:
        """Verify price against historical data"""
        ...

    def get_price(self, ticker: Ticker.Input, date: date | None = None) -> float | None:
        """Fetch the price for a ticker (current or historical)"""
        ...


class CommodityLookup(Protocol):
    """Protocol for commodity lookup operations"""

    def find_by_isin(self, isin: str, currency: Currency | None = None) -> Commodity | None: ...

    def find_candidates(self, criteria: SecurityCriteria) -> list[Commodity]: ...

    def find_by_ticker(self, provider: str, ticker: Ticker.Input) -> Commodity | None: ...


class SearchResult(BaseModel):
    """Result from multi-provider search"""

    provider: ProviderName
    ticker: Ticker.Input
    name: str
    currency: CurrencyCode.Input | None = None
    asset_class: AssetClass | None = None
    instrument_type: InstrumentType | None = None
    price: Price.Input | None = None
    price_date: date | None = None
