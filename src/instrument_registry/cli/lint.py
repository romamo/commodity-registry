from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import agentyper as typer
from pydantic_market_data.models import Price, PriceVerificationError

from . import common

logger = logging.getLogger(__name__)


def _provider_pairs(instrument: Any) -> list[tuple[Any, str]]:
    from ..interfaces import ProviderName

    pairs: list[tuple[Any, str]] = []
    if not instrument.tickers:
        return pairs
    if instrument.tickers.yahoo:
        pairs.append((ProviderName.YAHOO, instrument.tickers.yahoo))
    if instrument.tickers.ft:
        pairs.append((ProviderName.FT, instrument.tickers.ft))
    return pairs


def _primary_provider_pair(instrument: Any) -> tuple[Any | None, str | None]:
    pairs = _provider_pairs(instrument)
    if pairs:
        return pairs[0]
    return None, None


def command(
    ctx: typer.Context,
    registry_path: str | None = common.REGISTRY_PATH_OPTION,
    no_bundled: bool = common.NO_BUNDLED_OPTION,
    path: str | None = typer.Option(
        None,
        "--path",
        help="Lint only this registry file or directory",
    ),  # noqa: B008
    verify: bool = False,
    only: str | None = typer.Option(
        None,
        "--only",
        help="Verify only the named instrument",
    ),  # noqa: B008
) -> None:
    """Validate registry files and optionally verify live provider data."""
    from ..finder import fetch_metadata, verify_ticker

    common.configure_registry_scope(
        ctx=ctx,
        registry_path=registry_path,
        no_bundled=no_bundled,
    )

    fmt = common.current_format()
    target_desc = "external path"
    if path:
        path_obj = Path(path).expanduser()
        reg = common.get_registry(include_bundled=False, extra_paths=[path_obj])
        target_desc = str(path_obj)
    else:
        reg = common.registry()
        target_desc = "registry"

    instruments = reg.get_all()
    errors = reg.load_errors.copy()
    warnings: list[str] = []
    checked_names: list[str] = []

    seen_isinc: dict[tuple[str, str], str] = {}
    for instrument in instruments:
        checked_names.append(instrument.symbol)
        instrument_ok = True
        if instrument.isin:
            key = (str(instrument.isin).upper(), str(instrument.currency).upper())
            if key in seen_isinc:
                errors.append(
                    f"Duplicate ISIN {instrument.isin} with currency {instrument.currency} in "
                    f"{instrument.symbol} and {seen_isinc[key]}"
                )
                instrument_ok = False
            seen_isinc[key] = instrument.symbol
        if common.STATE.debug:
            status_lbl = "OK" if instrument_ok else "FAILED"
            if fmt == "table":
                print(f"{instrument.symbol}: {status_lbl}")
            elif fmt == "json":
                common.emit_json_event(
                    {
                        "event": "instrument_checked",
                        "symbol": instrument.symbol,
                        "status": status_lbl,
                    }
                )

    if verify:
        targets = instruments
        if only:
            targets = [instrument for instrument in targets if instrument.symbol == only]
            if not targets:
                common.exit_with_error(f"Instrument '{only}' not found.")

        required_provider = next(
            (provider for provider, ticker in map(_primary_provider_pair, targets) if ticker),
            None,
        )
        common.require_live_providers(
            "instrument-reg lint --verify",
            provider=required_provider,
        )

        print(f"\n=== Granular Data Audit (Live) - {len(targets)} items ===")
        for instrument in targets:
            provider, ticker = _primary_provider_pair(instrument)

            if ticker and provider is not None:
                audit_log: list[str] = []
                success = True
                logger.debug("Fetching live metadata for %s via %s...", ticker, provider)
                try:
                    ext_data = fetch_metadata(ticker, provider=provider)
                except ImportError:
                    common.exit_missing_provider(provider=provider)

                if not ext_data:
                    audit_log.append(f"  [!] FAILED: No external data found for {ticker}")
                    warnings.append(f"{instrument.symbol}: No external metadata found")
                    success = False
                else:
                    ext_isin = ext_data.isin if hasattr(ext_data, "isin") else None
                    if instrument.isin and ext_isin:
                        if str(instrument.isin).upper() != ext_isin.upper():
                            audit_log.append(
                                f"  ISIN:     {instrument.isin} [MISMATCH: {ext_isin}]"
                            )
                            warnings.append(
                                f"{instrument.symbol}: ISIN mismatch (Registry: {instrument.isin}, "
                                f"Provider: {ext_isin})"
                            )
                            success = False
                        else:
                            audit_log.append(f"  ISIN:     {instrument.isin} [OK]")
                    else:
                        audit_log.append(
                            f"  ISIN:     {instrument.isin or 'N/A'} "
                            f"(Provider: {ext_isin or 'N/A'})"
                        )

                    ext_symbol = ext_data.symbol
                    if ext_symbol:
                        if ticker.upper() != str(ext_symbol).upper():
                            audit_log.append(f"  Ticker:   {ticker} [MISMATCH: {ext_symbol}]")
                            warnings.append(
                                f"{instrument.symbol}: Ticker mismatch (Registry: {ticker}, "
                                f"Provider: {ext_symbol})"
                            )
                            success = False
                        else:
                            audit_log.append(f"  Ticker:   {ticker} [OK]")
                    else:
                        audit_log.append(f"  Ticker:   {ticker} (Provider: {ext_symbol or 'N/A'})")

                    ext_curr = (
                        str(ext_data.currency.root)
                        if (ext_data.currency and hasattr(ext_data.currency, "root"))
                        else str(ext_data.currency)
                        if ext_data.currency
                        else None
                    )
                    status_curr = (
                        "[OK]"
                        if (
                            ext_curr
                            and instrument.currency
                            and ext_curr.upper() == str(instrument.currency).upper()
                        )
                        else f"[MISMATCH: {ext_curr}]"
                    )
                    audit_log.append(f"  Currency: {instrument.currency} {status_curr}")
                    if "MISMATCH" in status_curr:
                        warnings.append(f"{instrument.symbol}: Currency mismatch")
                        success = False

                    if instrument.figi:
                        audit_log.append(f"  FIGI:     {instrument.figi}")

                    if instrument.validation_points:
                        audit_log.append("  Historical Verification:")
                        for validation_point in instrument.validation_points:
                            verified_count = 0
                            vp_log = [
                                f"    - {validation_point.date} (Target: {validation_point.price}):"
                            ]
                            providers_to_check = _provider_pairs(instrument)

                            if not providers_to_check:
                                vp_log.append("      [SKIPPED: No ticker found]")
                                audit_log.extend(vp_log)
                                continue

                            for provider_name, ticker_value in providers_to_check:
                                v_price = (
                                    Price(validation_point.price)
                                    if isinstance(validation_point.price, (float, int))
                                    else validation_point.price
                                )
                                try:
                                    if verify_ticker(
                                        ticker_value,
                                        validation_point.date,
                                        v_price,
                                        provider=provider_name,
                                    ):
                                        vp_log.append(
                                            f"      * {provider_name.upper()}: [OK: Range Match]"
                                        )
                                        verified_count += 1
                                    else:
                                        vp_log.append(f"      * {provider_name.upper()}: [FAILED]")
                                except ImportError:
                                    common.exit_missing_provider(provider=provider_name)
                                except PriceVerificationError as exc:
                                    vp_log.append(
                                        f"      * {provider_name.upper()}: [FAILED: {exc}]"
                                    )

                            if verified_count == 0:
                                success = False
                                audit_log.extend(vp_log)
                                warnings.append(
                                    f"{instrument.symbol}: Price verification failed on "
                                    f"{validation_point.date}"
                                )
                            else:
                                audit_log.extend(vp_log)
                    else:
                        audit_log.append(
                            "  Historical Verification: [SKIPPED: No validation points]"
                        )

                status_lbl = "OK" if success else "FAILED"
                print(f"{instrument.symbol}({provider.value} {ticker}): {status_lbl}")
                if not success or common.STATE.debug:
                    for line in audit_log:
                        print(line)
            else:
                print(f"{instrument.symbol}: [SKIPPED: No compatible ticker]")

    lint_report = {
        "target": target_desc,
        "instrument_count": len(instruments),
        "checked": checked_names,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "verified": verify,
    }
    typer.output(lint_report, title="Lint Report")
    if errors:
        raise SystemExit(1)
