# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2026-02-15

### Added
- Recursive directory scanning: `load_path` now recursively finds all `.yaml`/`.yml` files.
- Dynamic provider discovery: `finder.py` now dynamically detects available providers (`py-yfinance`, `py-ftmarkets`).
- Caching: Integrated `diskcache` to cache external metadata requests for 24 hours.
- Validation: Added strict ISIN validation (Luhn algorithm) to `Commodity` model.

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
