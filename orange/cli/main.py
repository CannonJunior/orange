"""
Main CLI entry point for Orange.

This module defines the root CLI group and initializes the application.

Usage:
    orange --help
    orange device list
    orange device info <udid>
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from orange import __version__
from orange.config import Config, get_config
from orange.cli.commands import device, backup, files, apps, export

# Rich console for pretty output
console = Console()


def setup_logging(verbose: bool, debug: bool) -> None:
    """Configure logging based on verbosity flags."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.version_option(version=__version__, prog_name="Orange")
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Enable verbose output.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug output (more verbose than -v).",
)
@click.option(
    "--config",
    type=click.Path(exists=False),
    help="Path to config file.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    debug: bool,
    config: Optional[str],
) -> None:
    """
    Orange - Cross-platform iOS file transfer and data management.

    Transfer messages, music, files, and data between iPhone/iPad
    and your computer.

    Examples:

        List connected devices:
        $ orange device list

        Show device information:
        $ orange device info <udid>

        Pair with a device:
        $ orange device pair <udid>
    """
    # Setup logging
    setup_logging(verbose, debug)

    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug
    ctx.obj["console"] = console

    # Load configuration
    if config:
        from pathlib import Path
        ctx.obj["config"] = Config.load(Path(config))
    else:
        ctx.obj["config"] = get_config()


# Register command groups
cli.add_command(device.device)
cli.add_command(backup.backup)
cli.add_command(files.files)
cli.add_command(apps.apps)
cli.add_command(export.export)


# Convenience aliases
@cli.command("list")
@click.pass_context
def list_devices(ctx: click.Context) -> None:
    """Alias for 'device list'."""
    ctx.invoke(device.list_cmd)


@cli.command("info")
@click.argument("udid", required=False)
@click.pass_context
def device_info(ctx: click.Context, udid: Optional[str]) -> None:
    """Alias for 'device info'."""
    ctx.invoke(device.info_cmd, udid=udid)


def main() -> None:
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if "--debug" in sys.argv:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
