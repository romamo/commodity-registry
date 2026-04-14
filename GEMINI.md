# Commodity Registry: Project Context

A Python-based single source of truth for financial instrument data. This project maps ISINs, Tickers, and Names to canonical commodity identifiers for use in financial tools like Beancount.

## Project Overview

- **Core Purpose**: Resolve financial symbols and ISINs to a canonical registry, providing metadata (currency, asset class) and price verification.
- **Main Technologies**:
  - **Language**: Python 3.10+
  - **Data Modeling**: [Pydantic v2](https://docs.pydantic.dev/latest/) for robust validation and settings.
  - **Data Storage**: YAML files (Strict loading, no duplicate keys).
  - **Market Data**: Integrates with `py-yfinance` and `py-ftmarkets`.
  - **Caching**: [diskcache](https://grantjenks.com/docs/diskcache/) for metadata and price persistence.
  - **CLI Framework**: Custom CLI implementation in `src/commodity_registry/cli.py`.

## Architecture & Concepts

- **Models (`models.py`)**: Defines `Commodity`, `Tickers`, `ValidationPoint`, and enums for `InstrumentType` and `AssetClass`.
- **Registry (`registry.py`)**: Manages bundled and user-provided commodity data. Supports lookups by ISIN, Name, FIGI, and Ticker.
- **Finder (`finder.py`)**: Handles external data fetching, metadata resolution, and price verification.
- **Interfaces (`interfaces.py`)**: Uses Python `Protocols` for `DataProvider` and `CommodityLookup` to ensure modularity.
- **Resolution Strategy**:
  1.  **Local Registry**: Check bundled and user YAML files.
  2.  **Programmatic FX**: Resolve currency pairs (e.g., `EURUSD=X`) without explicit registry entries.
  3.  **Online Search**: Query providers (Yahoo, FT) for unknown symbols/ISINs.

## Commands

### Environment Setup
The project uses `uv` for dependency management.
```bash
uv sync --all-extras
source .venv/bin/activate
```

### Building & Running
- **Install Tool**: `uv tool install .`
- **CLI Usage**: `commodity-reg --help`
- **Resolve Token**: `commodity-reg resolve [TOKEN]`
- **Add Commodity**: `commodity-reg add [ISIN] --fetch`

### Testing & Quality
- **Run Tests**: `pytest`
- **Linting**: `ruff check .`
- **Type Checking**: `mypy .`
- **Security Audit**: `bandit -r src/`

## Development Conventions

- **Data Integrity**: All commodity data must adhere to the Pydantic models in `models.py`.
- **User Data**: User-specific registries are loaded from the path specified in `COMMODITY_REGISTRY_PATH`.
- **Bundled Data**: Permanent common instruments are stored in `src/commodity_registry/data/commodities/`.
- **Testing Strategy**: New features must include a smoke test or unit test in the `tests/` directory.
- **Optional Dependencies**: Market data providers (Yahoo, FT) are optional; use `try...except ImportError` when adding new providers in `finder.py`.
- **Caching**: External lookups should be cached using the `@cache.memoize` decorator in `finder.py`.
