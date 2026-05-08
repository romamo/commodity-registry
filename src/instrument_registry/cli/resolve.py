from __future__ import annotations

import json
import logging
import sys
from typing import Any

import agentyper as typer
import pandas as pd  # type: ignore[import-untyped]
from pydantic_market_data.models import (
    Currency,
    CurrencyCode,
    Price,
    PriceOnDate,
    PriceVerificationError,
    SecurityQuery,
)

from . import common

logger = logging.getLogger(__name__)


def _read_pipe() -> list[dict[str, Any]]:
    raw = sys.stdin.read().strip()
    if not raw:
        common.exit_with_error("Stdin is empty", error_type="ArgError")
        raise AssertionError("unreachable")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return parsed
        common.exit_with_error("Stdin JSON must be an object or array", error_type="ArgError")
        raise AssertionError("unreachable")
    except json.JSONDecodeError:
        pass
    # JSONL: one JSON object per line
    records: list[dict[str, Any]] = []
    for line_num, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                common.exit_with_error(
                    f"JSONL line {line_num} must be a JSON object", error_type="ArgError"
                )
                raise AssertionError("unreachable")
            records.append(obj)
        except json.JSONDecodeError as exc:
            common.exit_with_error(f"Invalid JSON on line {line_num}: {exc}", error_type="ArgError")
            raise AssertionError("unreachable") from None
    if not records:
        common.exit_with_error("Stdin contains no valid JSON objects", error_type="ArgError")
        raise AssertionError("unreachable")
    return records


def _resolve_criteria(
    *,
    ctx: typer.Context,
    isin: str | None,
    symbol: str | None,
    figi: str | None,
    currency: str | None,
    asset_class: str | None,
    price: float | None,
    date: str | None,
    price_on: PriceOnDate | None = None,
    dry_run: bool,
    report_price: bool,
    reg: Any,
    target_path: Any,
) -> None:
    from ..finder import get_available_providers, resolve_and_persist, verify_ticker

    query_label = isin or figi or symbol or "(stdin)"
    logger.info("Resolving query: %s", query_label)

    if price is not None and date:
        price_on = PriceOnDate(
            price=Price(price),
            date=pd.to_datetime(date).date(),
        )

    criteria = SecurityQuery(
        isin=isin,
        symbol=symbol,
        figi=figi,
        currency=CurrencyCode(Currency(currency.upper())) if currency else None,
        price_on=price_on,
        asset_class=asset_class,
    )

    result = resolve_and_persist(
        criteria,
        registry=reg,
        store=True,
        target_path=target_path,
        dry_run=dry_run,
        include_price=report_price,
    )

    if not result:
        providers = get_available_providers()
        if not providers:
            common.exit_with_error(
                f"Could not resolve '{query_label}'. Install providers: uv tool install "
                "'instrument-registry[providers]'"
            )
        common.exit_with_error(f"Could not resolve '{query_label}'")
    assert result is not None

    res, new_instrument = result

    if date and price is not None and new_instrument is not None:
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

    if new_instrument is None:
        _candidates = reg.find_candidates(criteria)
        if _candidates and common.emit_structured(_candidates[0]):
            return
    else:
        if common.emit_structured(new_instrument):
            return
    if common.emit_structured(res):
        return

    p_val = getattr(res.price, "value", res.price) if res.price else 0.0
    p_label = f"Price {res.price_date}" if res.price_date else "Last Price"
    price_str = f" [{p_label}: {p_val:.2f} {res.currency}]" if res.price else ""
    country_str = f" | Country: {res.country}" if res.country else ""
    meta_str = f" | Meta: {res.metadata}" if res.metadata else ""
    provider_str = f" ({res.provider.value})" if res.provider else ""
    print(
        f"Resolved: {res.name} -> {str(res.symbol)}{provider_str}{price_str}{country_str}{meta_str}"
    )


def command(
    ctx: typer.Context,
    query: str | None = typer.Argument(None, help="Instrument query or identifier"),  # noqa: B008
    registry_path: str | None = common.REGISTRY_PATH_OPTION,
    no_bundled: bool = common.NO_BUNDLED_OPTION,
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Preferred provider name for external resolution",
    ),  # noqa: B008
    figi: str | None = typer.Option(
        None,
        "--figi",
        help="FIGI identifier for direct security lookup via OpenFIGI",
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
    report_price: bool = typer.Option(  # noqa: B008
        False,
        "--report-price",
        is_flag=True,
        help="Fetch and include the current price (or historical price if --date is given)",
    ),
    asset_class: str | None = typer.Option(
        None,
        "--asset-class",
        help="Restrict matches to this asset class",
    ),  # noqa: B008
    no_save: bool = typer.Option(  # noqa: B008
        False,
        "--no-save",
        is_flag=True,
        help="Resolve and return output without writing to registry file",
    ),
) -> None:
    """Resolve a query from local registries first, then external providers."""
    del provider  # Provider filtering is not implemented yet.
    from ..interfaces import ProviderName, SearchResult

    common.configure_registry_scope(
        ctx=ctx,
        registry_path=registry_path,
        no_bundled=no_bundled,
    )

    reg = common.registry()
    target_path = common.primary_registry_path()

    if query is not None and common.is_ibkr_conid(query):
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

    if query is not None:
        isin = query if common.is_isin(query) else None
        symbol = query if not isin else None
        _resolve_criteria(
            ctx=ctx,
            isin=isin,
            symbol=symbol,
            figi=figi,
            currency=currency,
            asset_class=asset_class,
            price=price,
            date=date,
            dry_run=no_save,
            report_price=report_price,
            reg=reg,
            target_path=target_path,
        )
    else:
        if sys.stdin.isatty():
            common.exit_with_error("No query provided", error_type="ArgError")
            raise AssertionError("unreachable")
        for pipe_data in _read_pipe():
            rec_price = (
                price
                if price is not None
                else (
                    float(pipe_data["target_price"])
                    if pipe_data.get("target_price") is not None
                    else None
                )
            )
            rec_date = (
                date
                if date is not None
                else (
                    str(pipe_data["target_date"])
                    if pipe_data.get("target_date") is not None
                    else None
                )
            )
            raw_price_on = pipe_data.get("price_on") if rec_price is None else None
            pipe_price_on: PriceOnDate | None = None
            if raw_price_on and raw_price_on.get("price") is not None and raw_price_on.get("date"):
                pipe_price_on = PriceOnDate(
                    price=Price(float(raw_price_on["price"])),
                    date=pd.to_datetime(str(raw_price_on["date"])).date(),
                )
            _resolve_criteria(
                ctx=ctx,
                isin=pipe_data.get("isin"),
                symbol=pipe_data.get("symbol"),
                figi=figi or pipe_data.get("figi"),
                currency=currency or pipe_data.get("currency"),
                asset_class=asset_class or pipe_data.get("asset_class"),
                price=rec_price,
                date=rec_date,
                price_on=pipe_price_on,
                dry_run=no_save,
                report_price=report_price,
                reg=reg,
                target_path=target_path,
            )
