from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class InstrumentType(StrEnum):
    ETF = "ETF"
    ETC = "ETC"
    ETN = "ETN"
    STOCK = "Stock"
    INDEX = "Index"
    FUTURE = "Future"
    CRYPTO = "Crypto"
    CASH = "Cash"


class AssetClass(StrEnum):
    EQUITY_ETF = "EquityETF"
    FIXED_INCOME_ETF = "FixedIncomeETF"
    COMMODITY_ETF = "CommodityETF"
    MONEY_MARKET_ETF = "MoneyMarketETF"
    STOCK = "Stock"
    CASH = "Cash"
    CRYPTO = "Crypto"
    COMMODITY = "Commodity"


class RiskProfile(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    SPECULATIVE = "Speculative"


class Liquidity(StrEnum):
    INSTANT = "Instant"
    T_PLUS_2 = "T+2"
    LOCKED = "Locked"


class Tickers(BaseModel):
    yahoo: str | None = None
    ft: str | None = Field(None, description="Financial Times ticker")
    google: str | None = None


class ValidationPoint(BaseModel):
    date: str = Field(..., description="ISO 8601 date YYYY-MM-DD")
    price: float = Field(
        ...,
        description=(
            "Expected price on that date. Verification passes if this price "
            "is within the intraday High-Low range."
        ),
    )


class Commodity(BaseModel):
    name: str = Field(
        ..., description="Canonical Beancount commodity name", pattern=r"^[A-Z][A-Z0-9\._-]*$"
    )
    isin: str | None = None
    figi: str | None = Field(None, description="Composite FIGI identifier")
    instrument_type: InstrumentType
    asset_class: AssetClass
    currency: str
    issuer: str | None = None
    underlying: str | None = None
    tickers: Tickers | None = None
    validation_points: list[ValidationPoint] | None = Field(
        None, description="Historical verification price points"
    )
    provider: str | None = None
    risk_profile: RiskProfile | None = None
    liquidity: Liquidity | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if not v.isupper() or len(v) != 3:
            raise ValueError("Currency must be a 3-letter uppercase ISO code")
        return v


class CommodityFile(BaseModel):
    commodities: list[Commodity]
