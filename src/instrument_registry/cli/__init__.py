from __future__ import annotations

import importlib.metadata
import sys

import agentyper as typer

from . import common
from .add import command as add_command
from .fetch import command as fetch_command
from .lint import command as lint_command
from .resolve import command as resolve_command

app = typer.Agentyper(
    name="instrument-reg",
    version=importlib.metadata.version("instrument-registry"),
    help="Instrument Registry CLI Application",
)


@app.callback()
def root(
    ctx: typer.Context,
) -> None:
    del ctx
    verbosity = common.explicit_verbosity()
    common.configure_state(
        verbosity=verbosity,
        registry_path=None,
        bundled=True,
    )


app.command(name="resolve")(resolve_command)
app.command(name="lint")(lint_command)
app.command(name="add")(add_command)
app.command(name="fetch")(fetch_command)

AppCLI = app

# Re-export for compatibility with existing tests and callers.
get_registry = common.get_registry
setup_logging = common.setup_logging


def main(args: list[str] | None = None) -> None:
    old_argv = sys.argv
    sys.argv = ["instrument-reg", *(args or old_argv[1:])]
    try:
        app(args=args)
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    main()
