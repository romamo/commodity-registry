# Commodity Registry

Single source of truth for financial instrument data.
Used to map ISINs, Tickers, and Names to canonical commodity identifiers for Beancount and other financial tools.

## Concepts

- **Canonical Name**: The unique identifier used in Beancount ledgers (e.g., `AAPL`, `CSPX`).
- **ISIN**: International Securities Identification Number (e.g., `US0378331005`). primary key for resolution.
- **FIGI**: Financial Instrument Global Identifier.
- **Ticker**: Provider-specific symbol (e.g., `AAPL` for Yahoo, `CSPX.L` for Yahoo).

## Installation

```bash
uv tool install commodity-registry
```

## Configuration

The registry loads data from two sources:
1.  **Bundled Data**: Built-in common commodities (ETFs, Stocks).
2.  **User Data**: Custom YAML files located at `PATH_COMMODITY_REGISTRY`.

Set the environment variable to point to your custom registry:

```bash
export PATH_COMMODITY_REGISTRY=~/path/to/my/registry
```

The registry recursively scans this directory for `.yaml` and `.yml` files.

## Usage

### Resolve a Token
Find the canonical commodity for an ISIN, Ticker, or Name.

```bash
commodity-reg resolve US0378331005
# Output: Resolved: AAPL
```

### Automatic Currency Resolution
The registry programmatically resolves standard currencies to Yahoo tickers if they are not in your custom registry:
- `resolve EUR` -> `EURUSD=X`
- `resolve EUR/JPY` -> `EURJPY=X`
- `resolve USD/JPY` -> `JPY=X`

This eliminates the need to manually define standard Forex pairs in your registry files.

With price verification (checks if price matches historical data):
```bash
commodity-reg resolve US0378331005 --date 2024-01-01 --price 185.00
```

### Add a Commodity
Add a new commodity to your local registry.

```bash
# Auto-fetch metadata from Yahoo Finance
commodity-reg add US0378331005 --fetch

# Manually specify details
commodity-reg add --name AAPL --isin US0378331005 --ticker AAPL --instrument-type Stock --asset-class Stock --currency USD
```

### Linting
Validate your registry data and check for duplicates.

```bash
commodity-reg lint
```

Verify against live market data (checks if tickers are valid):

```bash
commodity-reg lint --verify
```

### Fetch Metadata
Look up security details from online providers (Yahoo Finance, FT).

```bash
commodity-reg fetch --isin US0378331005
```


## Programmatic Usage

You can use the registry in your Python scripts:

```python
from commodity_registry.registry import get_registry

# Initialize registry (loads bundled data + user data from env var)
reg = get_registry()

# 1. Resolve by ISIN
commodity = reg.find_by_isin("US0378331005")
if commodity:
    print(f"Name: {commodity.name}, Currency: {commodity.currency}")

# 2. Search by any token (ISIN, Name, FIGI)
candidates = reg.find_candidates("AAPL")
for c in candidates:
    print(f"Found: {c.name} ({c.isin})")

# 3. Look up by ticker
# Note: Ticker lookup requires the provider name
comm = reg.find_by_ticker("yahoo", "AAPL")
```


## Data Format (YAML)

```yaml
commodities:
  - name: AAPL
    isin: US0378331005
    instrument_type: Stock
    asset_class: Stock
    currency: USD
    tickers:
      yahoo: AAPL
    validation_points:
      - date: "2024-01-01"
        price: 185.64
```

## Contributing

- **Bundled Data**: Submit a PR to add common instruments to `src/commodity_registry/data/commodities/`.
- **Providers**: Implement new data sources in `src/commodity_registry/finder.py` by adding a class that implements the `DataSource` interface.
