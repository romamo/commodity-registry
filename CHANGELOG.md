# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-02-15

### Added
- Programmatic Currency Resolution: Integrated smart lookup logic in `finder.py` to automatically resolve standard currencies to Yahoo tickers (e.g. `EUR` -> `EURUSD=X`).
- **Live Verification**: Programmatic currency hits are now verified against the live provider to ensure "True Truth" resolution.
- Currency Pair Support: Added parsing for composite pair strings like `EURUSD`, `EUR/JPY`, and `EUR-USD`.
- CLI Price Fetch: Added `--price` flag to the `fetch` command to retrieve the latest market price.
- Recursive directory scanning: `load_path` now recursively finds all `.yaml`/`.yml` files.
- Dynamic provider discovery: Dynamically detects available providers (`py-yfinance`, `py-ftmarkets`).
- Caching: Integrated `diskcache` for 24-hour metadata caching.

### Changed
- `CLI`: Updated help text and logic to use dynamic provider list.
- `README.md`: Completely rewritten with Concepts, Configuration, and Programmatic Usage sections.
- `registry.py`: Duplicate handling logic improved.

### Removed
- Unused `test_invalid.beancount` file.

## [0.1.0] - 2026-02-09

### Added

- Initial release of `commodity-registry`.
- Comprehensive CLI for instrument data management.
- Support for ISIN, Ticker, and Name mapping.
- Integration with Yahoo Finance and FT Markets (optional).
- Standardized OSS package structure.
- GitHub Actions for CI and Trusted Publishing.
