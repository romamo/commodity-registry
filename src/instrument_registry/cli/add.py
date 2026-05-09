from __future__ import annotations

import logging
from typing import Any

import agentyper as typer
import pandas as pd  # type: ignore[import-untyped]
from pydantic_market_data.models import Currency, CurrencyCode, Price, PriceOnDate, SecurityQuery

from ..models import AssetClass, InstrumentType
from . import common

logger = logging.getLogger(__name__)


def command(
    ctx: typer.Context,
    query: str | None = typer.Argument(None, help="Instrument query or identifier"),  # noqa: B008
    registry_path: str | None = common.REGISTRY_PATH_OPTION,
    no_bundled: bool = common.NO_BUNDLED_OPTION,
    canonical: str | None = typer.Option(
        None,
        "--canonical",
        help="Canonical instrument symbol to store (overrides auto-derived symbol)",
    ),  # noqa: B008
    isin: str | None = typer.Option(None, "--isin", help="ISIN code"),  # noqa: B008
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        help="Provider symbol to store when no fetch result is used",
    ),  # noqa: B008
    instrument_type: InstrumentType | None = typer.Option(  # noqa: B008
        None,
        "--instrument-type",
        help="Instrument type to store",
    ),
    asset_class: AssetClass | None = typer.Option(  # noqa: B008
        None,
        "--asset-class",
        help="Asset class to store",
    ),
    currency: str | None = typer.Option(
        None,
        "--currency",
        help="Primary trading currency",
    ),  # noqa: B008
    figi: str | None = typer.Option(None, "--figi", help="Optional FIGI"),  # noqa: B008
    ibkr: int | None = typer.Option(
        None,
        "--ibkr",
        help="Interactive Brokers conid",
    ),  # noqa: B008
    country: str | None = typer.Option(
        None,
        "--country",
        help="Country or region of origin",
    ),  # noqa: B008
    validation_date: str | None = typer.Option(
        None,
        "--validation-date",
        help="Historical date for an initial validation point",
    ),  # noqa: B008
    validation_price: float | None = typer.Option(
        None,
        "--validation-price",
        help="Historical price for an initial validation point",
    ),  # noqa: B008
    fetch: bool = False,
    dry_run: bool = False,
) -> None:
    """Add or update an instrument in the explicit user registry write target."""
    del figi  # Not stored independently yet.
    from ..finder import search_isin
    from ..registry import add_instrument

    common.configure_registry_scope(
        ctx=ctx,
        registry_path=registry_path,
        no_bundled=no_bundled,
    )

    try:
        target_path = common.require_write_target()
    except ValueError as exc:
        common.exit_with_error(str(exc))

    if target_path.is_dir():
        target_path = target_path / "manual.yaml"

    final_isin: Any = isin
    ticker = symbol
    if query:
        if common.is_isin(query):
            if not final_isin:
                final_isin = query
        elif not ticker:
            ticker = query

    reg = common.registry()
    existing_entry = reg.find_by_isin(final_isin, currency) if (final_isin and currency) else None
    if existing_entry and not canonical:
        logger.info(
            "Preserving existing symbol '%s' for instrument %s/%s",
            existing_entry.symbol,
            final_isin,
            currency,
        )
        canonical = existing_entry.symbol

    price_on = (
        PriceOnDate(
            price=Price(validation_price),
            date=pd.to_datetime(validation_date).date(),
        )
        if validation_price is not None and validation_date
        else None
    )
    criteria = SecurityQuery(
        isin=final_isin,
        symbol=ticker,
        currency=CurrencyCode(Currency(currency.upper())) if currency else None,
        price_on=price_on,
    )

    metadata = None
    if fetch:
        logger.info("Searching for metadata...")
        results = search_isin(criteria)
        if results:
            metadata = results[0]
            metadata_symbol = (
                str(metadata.symbol.root)
                if hasattr(metadata.symbol, "root")
                else str(metadata.symbol)
            )
            logger.info(
                "Found candidate: %s (%s) - %s",
                metadata_symbol,
                metadata.provider.value if metadata.provider else "unknown",
                metadata.name,
            )
            if not criteria.symbol:
                criteria.symbol = metadata_symbol
            if not currency:
                metadata_currency = (
                    metadata.currency.root
                    if (metadata.currency and hasattr(metadata.currency, "root"))
                    else metadata.currency
                )
                currency = str(metadata_currency) if metadata_currency else None
                criteria.currency = metadata_currency
        else:
            logger.warning("No online metadata found.")
            if not ticker and not final_isin:
                common.exit_with_error("No ticker or ISIN provided and no online match found.")

    missing = []
    if not final_isin and not ticker:
        missing.append("--isin or --symbol")
    if not currency:
        missing.append("--currency")

    if missing:
        common.exit_with_error(f"Missing required fields: {', '.join(missing)}")

    if not criteria.symbol and ticker:
        criteria.symbol = ticker

    try:
        instrument = add_instrument(
            criteria=criteria,
            metadata=metadata,
            target_path=target_path,
            instrument_type=InstrumentType(instrument_type) if instrument_type else None,
            asset_class=AssetClass(asset_class) if asset_class else None,
            symbol=canonical,
            dry_run=dry_run,
            registry=reg,
            country=country,
            ibkr=ibkr,
        )
        if common.emit_structured(instrument):
            return
        print(f"Successfully processed {instrument.symbol}")
    except ValueError as exc:
        common.exit_with_error(str(exc))
