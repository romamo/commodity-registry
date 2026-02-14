"""
Interface definitions for commodity registry.

Defines Protocols for type safety and Pydantic models for typed returns.
"""

from typing import Protocol

from pydantic import BaseModel
from pydantic_market_data.models import SecurityCriteria, Symbol

from .models import Commodity


class DataProvider(Protocol):
    """Protocol for market data providers (Yahoo, FT, etc.)"""

    def resolve(self, criteria: SecurityCriteria) -> Symbol | None:
        """Resolve security using search criteria"""
        ...

    def validate(self, ticker: str, date: str, price: float) -> bool:
        """Verify price against historical data"""
        ...


class CommodityLookup(Protocol):
    """Protocol for commodity lookup operations"""

    def find_by_isin(self, isin: str, currency: str | None = None) -> Commodity | None: ...

    def find_candidates(self, token: str, currency: str | None = None) -> list[Commodity]: ...

    def find_by_ticker(self, provider: str, ticker: str) -> Commodity | None: ...


class SearchResult(BaseModel):
    """Result from multi-provider search"""

    provider: str  # "yahoo", "ft", etc.
    ticker: str
    name: str
    currency: str
