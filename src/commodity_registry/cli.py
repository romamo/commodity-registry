import argparse
import os
import sys
from pathlib import Path

from .models import AssetClass, InstrumentType
from .registry import get_registry


def get_registry_for_args(args):
    """Factory to create a registry based on CLI arguments."""
    extra_paths = []
    for p in args.registry_path:
        path = Path(p).expanduser()
        if path.exists():
            extra_paths.append(path)

    return get_registry(include_bundled=not args.no_bundled, extra_paths=extra_paths)


def resolve_cmd(args):
    """Resolves a token (ISIN, Name, Ticker) to a canonical commodity."""
    reg = get_registry_for_args(args)
    candidates = reg.find_candidates(args.token, currency=args.currency)

    # Backup: Try Ticker if no candidates found by ISIN/Name/FIGI
    if not candidates:
        if args.provider:
            c = reg.find_by_ticker(args.provider, args.token)
            if c:
                candidates.append(c)
        else:
            for provider in ["yahoo", "ibkr", "google"]:
                c = reg.find_by_ticker(provider, args.token)
                if c:
                    candidates.append(c)
                    break

    if not candidates:
        print(f"Could not resolve '{args.token}'")
        sys.exit(1)

    # 2. Result Selection & Optional Verification
    resolved_commodity = None

    if args.date and args.price:
        from .finder import verify_ticker

        print(
            f"Verifying {len(candidates)} candidate(s) against price {args.price} on {args.date}..."
        )

        for cand in candidates:
            # Check any available provider for this candidate
            if cand.tickers:
                for provider, ticker in cand.tickers.model_dump().items():
                    if ticker:
                        if verify_ticker(ticker, args.date, args.price):
                            print(f"  [OK] Verified {cand.name} via {provider.upper()} ({ticker})")
                            resolved_commodity = cand
                            break
            if resolved_commodity:
                break

        if not resolved_commodity:
            names = ", ".join(c.name for c in candidates)
            print(
                f"  [!] FAILED: Price {args.price} on {args.date} "
                f"does not match any known tickers for candidates: {names}"
            )
            sys.exit(1)
    else:
        # No verification requested, pick the first candidate
        resolved_commodity = candidates[0]

    print(f"Resolved: {resolved_commodity.name}")


def lint_cmd(args):
    """Validates data against the schema and rules."""
    from .finder import fetch_metadata

    if args.path:
        # Validate specific path
        path = Path(args.path).expanduser()
        print(f"Linting external path: {path}")
        reg = get_registry(include_bundled=False, extra_paths=[path])
    else:
        # Validate configured registry
        reg = get_registry_for_args(args)
        print(f"Linting registry ({len(reg.get_all())} commodities)...")

    # Validation already happened during loading via Pydantic.
    # We add logical checks here.
    errors = reg.load_errors.copy()
    warnings = []

    # Check 1: Unique ISINs
    seen_isins = {}
    for c in reg.get_all():
        if c.isin:
            if c.isin in seen_isins:
                errors.append(f"Duplicate ISIN {c.isin} in {c.name} and {seen_isins[c.isin]}")
            seen_isins[c.isin] = c.name

    # Check 2: Live Verification (if requested)
    if args.verify:
        from .finder import verify_ticker

        targets = reg.get_all()
        if args.only:
            targets = [c for c in targets if c.name == args.only]
            if not targets:
                print(f"Error: Commodity '{args.only}' not found.")
                sys.exit(1)

        print(f"\n=== Granular Data Audit (Live) - {len(targets)} items ===")
        for c in targets:
            ticker = None
            provider = "yahoo"

            if c.tickers:
                if c.tickers.yahoo:
                    ticker = c.tickers.yahoo
                    provider = "yahoo"
                elif c.tickers.ft:
                    ticker = c.tickers.ft
                    provider = "ft"
                elif c.tickers.google:
                    ticker = c.tickers.google
                    provider = "google"

            if ticker:
                audit_log = []
                success = True

                # Fetch metadata
                ext_data = fetch_metadata(ticker, provider=provider)

                if not ext_data:
                    audit_log.append(f"  [!] FAILED: No external data found for {ticker}")
                    warnings.append(f"{c.name}: No external metadata found")
                    success = False
                else:
                    audit_log.append(f"  ISIN:     {c.isin or 'N/A'}")

                    # Currency Check
                    ext_curr = ext_data.get("currency")
                    status_curr = (
                        "[OK]"
                        if ext_curr and ext_curr.upper() == c.currency.upper()
                        else f"[MISMATCH: {ext_curr}]"
                    )
                    audit_log.append(f"  Currency: {c.currency} {status_curr}")
                    if "MISMATCH" in status_curr:
                        warnings.append(f"{c.name}: Currency mismatch")
                        success = False

                    if c.figi:
                        audit_log.append(f"  FIGI:     {c.figi}")

                    # Historical Price Verification Points
                    if c.validation_points:
                        audit_log.append("  Historical Verification:")
                        for vp in c.validation_points:
                            verified_count = 0
                            vp_log = [f"    - {vp.date} (Target: {vp.price}):"]

                            providers_to_check = []
                            if c.tickers:
                                if c.tickers.yahoo:
                                    providers_to_check.append(("yahoo", c.tickers.yahoo))
                                if c.tickers.ft:
                                    providers_to_check.append(("ft", c.tickers.ft))
                                if c.tickers.google:
                                    providers_to_check.append(("google", c.tickers.google))

                            if not providers_to_check:
                                vp_log.append("      [SKIPPED: No ticker found]")
                                audit_log.extend(vp_log)
                                continue

                            for p, t_val in providers_to_check:
                                if verify_ticker(t_val, vp.date, vp.price, provider=p):
                                    vp_log.append(f"      * {p.upper()}: [OK: Range Match]")
                                    verified_count += 1
                                else:
                                    vp_log.append(f"      * {p.upper()}: [FAILED]")

                            if verified_count == 0:
                                success = False
                                audit_log.extend(vp_log)
                                warnings.append(f"{c.name}: Price verification failed on {vp.date}")
                            else:
                                audit_log.extend(vp_log)

                    else:
                        audit_log.append(
                            "  Historical Verification: [SKIPPED: No validation points]"
                        )

                # Print summary one-liner
                status_label = "OK" if success else "FAILED"
                print(f"{c.name}({provider} {ticker}): {status_label}")
                if not success:
                    for line in audit_log:
                        print(line)

            else:
                # Fallback if no online check possible
                if not c.tickers or not (c.tickers.yahoo or c.tickers.ft or c.tickers.google):
                    print(f"{c.name}: [SKIPPED: No compatible ticker]")
                    continue

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)

    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")

    print("All checks passed.")


def add_cmd(args):
    """Adds a new commodity to the registry via CLI arguments (non-interactive)."""
    from pydantic_market_data.models import SecurityCriteria

    from .finder import search_isin
    from .registry import add_commodity

    # 1. Resolve Target Path
    target_path = Path(args.registry_path[0]).expanduser()
    if target_path.is_dir():
        target_path = target_path / "manual.yaml"

    # Use positional token if provided and explicit flags are missing
    isin = args.isin
    ticker = args.ticker
    if args.token:
        if args.token.upper().startswith(("US", "GB", "DE", "FR", "NL")): # Simple ISIN heuristic
            if not isin: isin = args.token
        else:
            if not ticker: ticker = args.token

    name = args.name
    currency = args.currency
    inst_type_str = args.instrument_type
    asset_class_str = args.asset_class

    # 2. Build SecurityCriteria
    criteria = SecurityCriteria(
        isin=isin,
        symbol=ticker,
        currency=currency,
        target_price=float(args.validation_price) if args.validation_price else None,
        target_date=args.validation_date,
    )

    metadata = None

    # 3. Fetch Metadata if requested
    if args.fetch:
        print("Searching for metadata...")
        # Search using criteria
        results = search_isin(criteria)

        if results:
            metadata = results[0]
            print(f"Found candidate: {metadata.ticker} ({metadata.provider}) - {metadata.name}")

            # Auto-fill missing
            if not criteria.symbol:
                criteria.symbol = metadata.ticker
            if not name:
                name = metadata.name
            if not currency:
                currency = metadata.currency
                criteria.currency = currency  # Update criteria
        else:
            print("No online metadata found.")
            if not ticker and not isin:
                print("Error: No ticker or ISIN provided and no online match found.")
                sys.exit(1)

    # 4. Validation & Enum Conversion
    missing = []
    if not isin and not ticker:
        missing.append("--isin or --ticker")
    # For instrument type/asset class, we require them currently as CLI args
    if not inst_type_str:
        missing.append("--instrument-type")
    if not asset_class_str:
        missing.append("--asset-class")

    # If we still don't have currency (didn't fetch it, didn't provide it)
    if not currency:
        missing.append("--currency")

    if missing:
        print(f"Error: Missing required fields: {', '.join(missing)}")
        print("Note: Use --fetch with --isin or --ticker to auto-populate some fields.")
        sys.exit(1)

    try:
        # Convert string args to Enums
        inst_type = InstrumentType(inst_type_str)
        asset_class = AssetClass(asset_class_str)
    except ValueError as e:
        print(f"Error: Invalid enum value: {e}")
        print(f"Valid InstrumentTypes: {[e.value for e in InstrumentType]}")
        print(f"Valid AssetClasses: {[e.value for e in AssetClass]}")
        sys.exit(1)

    # 5. Add to Registry
    try:
        # If user provided a ticker manually, ensure it's in criteria
        if not criteria.symbol and ticker:
            criteria.symbol = ticker

        commodity = add_commodity(
            criteria=criteria,
            metadata=metadata,
            target_path=target_path,
            instrument_type=inst_type,
            asset_class=asset_class,
            verbose=True,
            dry_run=args.dry_run,
        )
        print(f"Successfully processed {commodity.name}")

    except Exception as e:
        print(f"Error adding commodity: {e}")
        sys.exit(1)


def fetch_cmd(args):
    """Searches for a security across providers and prints found details."""
    from .finder import fetch_metadata, search_isin

    if args.isin:
        print(f"Searching for ISIN: {args.isin}...")
        from pydantic_market_data.models import SecurityCriteria

        criteria = SecurityCriteria(isin=args.isin)
        results = search_isin(criteria)
        if not results:
            print("No results found.")
            return

        print("\nFound Identifiers:")
        for res in results:
            print(f"- [{res.provider.upper()}]")
            print(f"  Ticker:   {res.ticker}")
            print(f"  Name:     {res.name}")
            print(f"  Currency: {res.currency}")
    elif args.ticker:
        for p in ["yahoo", "ft"]:
            print(f"\nChecking [{p.upper()}] for {args.ticker}...")
            data = fetch_metadata(args.ticker, provider=p)
            if data:
                print(f"  Name:     {data.get('name')}")
                print(f"  Currency: {data.get('currency')}")
            else:
                print("  Not found.")
    else:
        print("Please provide --isin or --ticker")
        sys.exit(1)


def main():
    default_reg_path = os.getenv("PATH_COMMODITY_REGISTRY", "data/commodities/")
    parser = argparse.ArgumentParser(description="Commodity Registry CLI")
    parser.add_argument(
        "--registry-path",
        nargs="+",
        default=[default_reg_path],
        help="Paths to your user registry files or directories",
    )
    parser.add_argument("--no-bundled", action="store_true", help="Do not include bundled database")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # resolve
    p_resolve = subparsers.add_parser("resolve", help="Resolve a token to a commodity")
    p_resolve.add_argument("token", help="ISIN, Ticker, or Name")
    p_resolve.add_argument("--provider", help="Specific provider for ticker lookup (yahoo, ibkr)")
    p_resolve.add_argument("--currency", help="Optional currency for dual-listed instruments")
    p_resolve.add_argument("--date", help="Verification date (YYYY-MM-DD)")
    p_resolve.add_argument("--price", type=float, help="Expected price on that date")

    # lint
    p_lint = subparsers.add_parser("lint", help="Validate registry data")
    p_lint.add_argument("--path", help="Validate a specific YAML file or directory")
    p_lint.add_argument(
        "--verify", action="store_true", help="Perform live cross-check with external providers"
    )
    p_lint.add_argument("--only", help="Filter linting to a specific commodity name")

    # add
    p_add = subparsers.add_parser("add", help="Add a new commodity")
    p_add.add_argument("token", nargs="?", help="ISIN or Ticker (optional if flags provided)")
    p_add.add_argument("--name", help="Canonical name (e.g. AAPL)")
    p_add.add_argument("--isin", help="ISIN code")
    p_add.add_argument("--ticker", help="Ticker symbol (Yahoo Finance style)")
    p_add.add_argument("--instrument-type", help="Instrument type (ETF, Stock, etc.)")
    p_add.add_argument("--asset-class", help="Asset class (EquityETF, Stock, etc.)")
    p_add.add_argument("--currency", help="Currency (e.g. USD, EUR)")
    p_add.add_argument("--figi", help="FIGI identifier")
    p_add.add_argument("--validation-date", help="Validation date (YYYY-MM-DD)")
    p_add.add_argument("--validation-price", type=float, help="Validation price")
    p_add.add_argument(
        "--fetch", action="store_true", help="Fetch metadata online first"
    )
    p_add.add_argument("--dry-run", action="store_true", help="Print YAML to console without saving")
    p_add.add_argument("--verbose", action="store_true", help="Enable verbose output")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Fetch/Discover security details online")
    p_fetch.add_argument("--isin", help="ISIN to search for")
    p_fetch.add_argument("--ticker", help="Ticker to fetch metadata for")

    args = parser.parse_args()

    if args.command == "resolve":
        resolve_cmd(args)
    elif args.command == "lint":
        lint_cmd(args)
    elif args.command == "add":
        add_cmd(args)
    elif args.command == "fetch":
        fetch_cmd(args)


if __name__ == "__main__":
    main()
