from __future__ import annotations

import logging

import agentyper as typer
from pydantic_market_data.models import SecurityQuery

from . import common

logger = logging.getLogger(__name__)


def command(
    ctx: typer.Context,
    registry_path: str | None = common.REGISTRY_PATH_OPTION,
    no_bundled: bool = common.NO_BUNDLED_OPTION,
    isin: str | None = typer.Option(
        None,
        "--isin",
        help="Fetch using an ISIN",
    ),  # noqa: B008
    figi: str | None = typer.Option(
        None,
        "--figi",
        help="Fetch using a FIGI (FT Markets only)",
    ),  # noqa: B008
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        help="Fetch using a provider symbol",
    ),  # noqa: B008
    price: bool = False,
) -> None:
    """Fetch provider details after checking user and bundled registries first."""
    from ..finder import fetch_price, resolve_security

    common.configure_registry_scope(
        ctx=ctx,
        registry_path=registry_path,
        no_bundled=no_bundled,
    )

    provider_hint = "ft" if figi and not isin and not symbol else "yahoo"
    common.require_live_providers("instrument-reg fetch", provider=provider_hint)
    logger.info("Fetching details for ISIN=%s, FIGI=%s, Ticker=%s", isin, figi, symbol)
    criteria = SecurityQuery(isin=isin, figi=figi, symbol=symbol)
    try:
        res = resolve_security(criteria, verify=True, registry=common.registry())
    except ImportError:
        common.exit_missing_provider(provider=provider_hint)

    if not res:
        logger.warning("No results found.")
        return

    if price:
        try:
            fetched_price = fetch_price(res.symbol, provider=res.provider)
        except ImportError:
            common.exit_missing_provider(provider=res.provider)
        if fetched_price is not None:
            res.price = fetched_price

    typer.output(res)
