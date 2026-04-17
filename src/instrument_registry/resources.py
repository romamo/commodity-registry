import importlib.resources
from collections.abc import Iterator
from pathlib import Path

PACKAGE_DATA_PATH = "instrument_registry.data"
INSTRUMENTS_DIR = "instruments"


def get_schema_path() -> Path:
    """Returns the path to the bundled JSON schema."""
    return Path(
        str(importlib.resources.files(PACKAGE_DATA_PATH).joinpath("instruments.schema.json"))
    )


def get_instrument_files() -> Iterator[Path]:
    """Yields paths to all bundled YAML instrument files."""
    data_dir = importlib.resources.files(PACKAGE_DATA_PATH).joinpath(INSTRUMENTS_DIR)
    if not data_dir.is_dir():
        return

    for entry in data_dir.iterdir():
        if entry.name.endswith(".yaml") or entry.name.endswith(".yml"):
            yield Path(str(entry))
