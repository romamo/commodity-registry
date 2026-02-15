from enum import Enum

from pydantic import BaseModel, Field, field_validator


class InstrumentType(str, Enum):
    ETF = "ETF"
    ETC = "ETC"
    ETN = "ETN"
    STOCK = "Stock"
    INDEX = "Index"
    FUTURE = "Future"
    CRYPTO = "Crypto"
    CASH = "Cash"


class AssetClass(str, Enum):
    EQUITY_ETF = "EquityETF"
    FIXED_INCOME_ETF = "FixedIncomeETF"
    COMMODITY_ETF = "CommodityETF"
    MONEY_MARKET_ETF = "MoneyMarketETF"
    STOCK = "Stock"
    CASH = "Cash"
    CRYPTO = "Crypto"
    COMMODITY = "Commodity"


class RiskProfile(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    SPECULATIVE = "Speculative"


class Liquidity(str, Enum):
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

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.upper()
        if not v.isalnum() or len(v) != 12:
            raise ValueError("ISIN must be 12 alphanumeric characters")
        
        # Check country code
        if not v[:2].isalpha():
             raise ValueError("ISIN must start with 2-letter country code")

        # Luhn Algorithm Check
        digits = []
        for char in v:
            if char.isdigit():
                digits.append(int(char))
            else:
                # Convert letter to 2 digits: A=10, B=11, ...
                val = ord(char) - 55
                digits.append(val // 10)
                digits.append(val % 10)
        
        checksum = 0
        for i, digit in enumerate(reversed(digits)):
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
            
        if checksum % 10 != 0:
            raise ValueError(f"Invalid ISIN checksum for {v}")
            
        return v
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
