import importlib.resources
from collections.abc import Iterator
from pathlib import Path

PACKAGE_DATA_PATH = "commodity_registry.data"
COMMODITIES_DIR = "commodities"


def get_schema_path() -> Path:
    """Returns the path to the bundled JSON schema."""
    return importlib.resources.files(PACKAGE_DATA_PATH).joinpath("commodities.schema.json")


def get_commodity_files() -> Iterator[Path]:
    """Yields paths to all bundled YAML commodity files."""
    data_dir = importlib.resources.files(PACKAGE_DATA_PATH).joinpath(COMMODITIES_DIR)
    if not data_dir.is_dir():
        return

    for entry in data_dir.iterdir():
        if entry.name.endswith(".yaml") or entry.name.endswith(".yml"):
            yield entry
