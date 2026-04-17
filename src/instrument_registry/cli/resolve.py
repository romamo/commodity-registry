from __future__ import annotations

import logging

import agentyper as typer
import pandas as pd  # type: ignore[import-untyped]
from pydantic_market_data.models import (
    Currency,
    CurrencyCode,
    Price,
    PriceVerificationError,
    SecurityCriteria,
)

from . import common

logger = logging.getLogger(__name__)


def command(
    ctx: typer.Context,
    query: str,
    registry_path: str | None = common.REGISTRY_PATH_OPTION,
    no_bundled: bool = common.NO_BUNDLED_OPTION,
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Preferred provider name for external resolution",
    ),  # noqa: B008
    currency: str | None = typer.Option(
        None,
        "--currency",
        help="Restrict matches to this currency code",
    ),  # noqa: B008
    date: str | None = typer.Option(
        None,
        "--date",
        help="Historical date used with --price verification",
    ),  # noqa: B008
    price: float | None = typer.Option(
        None,
        "--price",
        help="Historical price used with --date verification",
    ),  # noqa: B008
    report_price: bool = False,
    asset_class: str | None = typer.Option(
        None,
        "--asset-class",
        help="Restrict matches to this asset class",
    ),  # noqa: B008
    dry_run: bool = False,
) -> None:
    """Resolve a query from local registries first, then external providers."""
    del provider  # Provider filtering is not implemented yet.
    from ..finder import get_available_providers, resolve_and_persist, verify_ticker
    from ..interfaces import ProviderName, SearchResult

    common.configure_registry_scope(
        ctx=ctx,
        registry_path=registry_path,
        no_bundled=no_bundled,
    )

    logger.info("Resolving query: %s", query)
    reg = common.registry()

    if common.is_ibkr_conid(query):
        logger.info("Numeric query detected. Checking registry for IBKR conid: %s...", query)
        res_comp = reg.find_by_ticker("IBKR", query)
        if res_comp:
            conid_result = SearchResult(
                provider=ProviderName.YAHOO,
                symbol=res_comp.tickers.yahoo if res_comp.tickers else res_comp.name,
                name=res_comp.name,
                currency=res_comp.currency,
                asset_class=res_comp.asset_class,
                instrument_type=res_comp.instrument_type,
                country=res_comp.country,
            )
            if common.emit_structured(conid_result):
                return
            print(
                "Resolved (via IBKR conid): "
                f"{conid_result.name} -> {str(conid_result.symbol)} (IBKR:{query})"
            )
            return

    isin = query if common.is_isin(query) else None
    symbol = query if not isin else None
    criteria = SecurityCriteria(
        isin=isin,
        symbol=symbol,
        currency=CurrencyCode(Currency(currency.upper())) if currency else None,
        target_price=Price(price) if price is not None else None,
        target_date=pd.to_datetime(date).date() if date else None,
        asset_class=asset_class,
    )

    target_path = common.primary_registry_path()
    res: SearchResult | None = resolve_and_persist(
        criteria,
        registry=reg,
        store=True,
        target_path=target_path,
        dry_run=dry_run,
        include_price=report_price,
    )

    if not res:
        providers = get_available_providers()
        if not providers:
            common.exit_with_error(
                f"Could not resolve '{query}'. Install providers: uv tool install "
                "'instrument-registry[providers]'"
            )
        common.exit_with_error(f"Could not resolve '{query}'")
    assert res is not None

    if date and price is not None:
        logger.info("Verifying price %s on %s...", price, date)
        v_date = pd.to_datetime(date).date()
        try:
            if verify_ticker(res.symbol, v_date, price, provider=res.provider):
                if ctx.format_ == "table":
                    print(f"  [OK] Verified {res.name} via {res.provider.upper()} ({res.symbol})")
            else:
                common.exit_with_error(
                    f"  [!] FAILED: Price {price} on {date} does not match {res.symbol}"
                )
        except PriceVerificationError as exc:
            common.exit_with_error(f"  [!] FAILED: {exc}")

    if common.emit_structured(res):
        return

    p_val = getattr(res.price, "value", res.price) if res.price else 0.0
    p_label = f"Price {res.price_date}" if res.price_date else "Last Price"
    price_str = f" [{p_label}: {p_val:.2f} {res.currency}]" if res.price else ""
    country_str = f" | Country: {res.country}" if res.country else ""
    meta_str = f" | Meta: {res.metadata}" if res.metadata else ""
    print(
        f"Resolved: {res.name} -> {str(res.symbol)} ({res.provider.value})"
        f"{price_str}{country_str}{meta_str}"
    )
