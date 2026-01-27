"""
CLI commands for iOS app management.

This module provides commands for listing installed apps,
extracting IPA files, and querying app information.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from orange.core.apps import AppManager, AppInfo, AppType
from orange.core.connection import DeviceDetector
from orange.exceptions import OrangeError, DeviceNotFoundError

logger = logging.getLogger(__name__)


def get_console(ctx: click.Context) -> Console:
    """Get console from context or create new one."""
    if ctx.obj and "console" in ctx.obj:
        return ctx.obj["console"]
    return Console()


def get_device_udid(udid: Optional[str]) -> str:
    """Get device UDID, auto-selecting if only one device connected."""
    if udid:
        return udid

    try:
        detector = DeviceDetector(include_wifi=True)
        devices = detector.list_devices()
    except Exception:
        raise click.ClickException(
            "No iOS device connected.\n"
            "Please connect a device via USB and try again."
        )

    if not devices:
        raise click.ClickException(
            "No iOS device connected.\n"
            "Please connect a device via USB and try again.\n"
            "Use 'orange device list' to check device status."
        )

    if len(devices) > 1:
        raise click.ClickException(
            "Multiple devices connected. Please specify --udid.\n"
            "Use 'orange device list' to see connected devices."
        )

    return devices[0].udid


@click.group()
def apps() -> None:
    """
    Manage installed iOS applications.

    List installed apps, extract IPA files, and query app information.
    Useful for sideloading apps to Apple Silicon Macs via PlayCover.

    Examples:

        List all user apps:
        $ orange apps list

        Search for Netflix:
        $ orange apps search netflix

        Get app details:
        $ orange apps info com.netflix.Netflix

        Extract IPA file:
        $ orange apps extract com.netflix.Netflix ./Netflix.ipa
    """
    pass


@apps.command("list")
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.option(
    "--type",
    "-t",
    "app_type",
    type=click.Choice(["user", "system", "all"]),
    default="user",
    help="Type of apps to list.",
)
@click.option("--no-sizes", is_flag=True, help="Skip size calculation (faster).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    udid: Optional[str],
    app_type: str,
    no_sizes: bool,
    as_json: bool,
) -> None:
    """
    List installed applications.

    Shows all installed apps with their bundle IDs, versions, and sizes.
    Use --type to filter by app type.

    Examples:

        $ orange apps list
        $ orange apps list --type system
        $ orange apps list --no-sizes --json
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)

        # Map type string to AppType
        type_map = {
            "user": AppType.USER,
            "system": AppType.SYSTEM,
            "all": AppType.ANY,
        }
        selected_type = type_map[app_type]

        with console.status("[bold blue]Loading apps..."):
            with AppManager(device_udid) as manager:
                apps = manager.list_apps(
                    app_type=selected_type,
                    calculate_sizes=not no_sizes,
                )

        if as_json:
            console.print(json.dumps([app.to_dict() for app in apps], indent=2))
            return

        if not apps:
            console.print(f"[dim]No {app_type} apps found.[/dim]")
            return

        table = Table(title=f"Installed Apps ({app_type.title()})")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Bundle ID", style="dim")
        table.add_column("Version", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Type", style="dim")

        for app in apps:
            # Truncate long bundle IDs
            bundle_display = app.bundle_id
            if len(bundle_display) > 35:
                bundle_display = bundle_display[:32] + "..."

            table.add_row(
                app.name,
                bundle_display,
                app.short_version,
                app.total_size_human if not no_sizes else "-",
                "Sideloaded" if app.is_sideloaded else "App Store",
            )

        console.print(table)
        console.print(f"\n[dim]{len(apps)} app(s) found[/dim]")

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@apps.command("search")
@click.argument("query")
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def search_cmd(
    ctx: click.Context,
    query: str,
    udid: Optional[str],
    as_json: bool,
) -> None:
    """
    Search for installed apps by name or bundle ID.

    Examples:

        $ orange apps search netflix
        $ orange apps search com.apple
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)

        with console.status(f"[bold blue]Searching for '{query}'..."):
            with AppManager(device_udid) as manager:
                apps = manager.search_apps(query)

        if as_json:
            console.print(json.dumps([app.to_dict() for app in apps], indent=2))
            return

        if not apps:
            console.print(f"[dim]No apps matching '{query}' found.[/dim]")
            return

        table = Table(title=f"Search Results: '{query}'")
        table.add_column("Name", style="cyan")
        table.add_column("Bundle ID", style="dim")
        table.add_column("Version", justify="right")
        table.add_column("Extractable", justify="center")

        for app in apps:
            table.add_row(
                app.name,
                app.bundle_id,
                app.short_version,
                "[green]Yes[/green]" if app.is_extractable else "[red]No[/red]",
            )

        console.print(table)

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@apps.command("info")
@click.argument("bundle_id")
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def info_cmd(
    ctx: click.Context,
    bundle_id: str,
    udid: Optional[str],
    as_json: bool,
) -> None:
    """
    Show detailed information about an app.

    Examples:

        $ orange apps info com.netflix.Netflix
        $ orange apps info com.apple.mobilesafari --json
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)

        with console.status(f"[bold blue]Loading app info..."):
            with AppManager(device_udid) as manager:
                app = manager.get_app(bundle_id)

        if not app:
            raise click.ClickException(f"App not found: {bundle_id}")

        if as_json:
            console.print(json.dumps(app.to_dict(), indent=2))
            return

        # Create info panel
        info_lines = [
            f"[bold]Name:[/bold] {app.name}",
            f"[bold]Bundle ID:[/bold] {app.bundle_id}",
            f"[bold]Version:[/bold] {app.short_version} ({app.version})",
            f"[bold]Type:[/bold] {app.app_type.value}",
            f"[bold]Source:[/bold] {'Sideloaded' if app.is_sideloaded else 'App Store'}",
            "",
            f"[bold]App Size:[/bold] {app.size_human}",
            f"[bold]Data Size:[/bold] {app.data_size_human}",
            f"[bold]Total Size:[/bold] {app.total_size_human}",
            "",
            f"[bold]Min iOS:[/bold] {app.min_os_version or 'Unknown'}",
            f"[bold]Executable:[/bold] {app.executable_name or 'Unknown'}",
            f"[bold]Extractable:[/bold] {'Yes' if app.is_extractable else 'No'}",
        ]

        if app.path:
            info_lines.append(f"[bold]Path:[/bold] {app.path}")

        panel = Panel(
            "\n".join(info_lines),
            title=f"[cyan]{app.name}[/cyan]",
            border_style="blue",
        )
        console.print(panel)

        # Show PlayCover hint for extractable apps
        if app.is_extractable:
            console.print(
                "\n[dim]Tip: Use 'orange apps extract' to create an IPA file.[/dim]"
            )

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@apps.command("extract")
@click.argument("bundle_id")
@click.argument("output", type=click.Path())
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.pass_context
def extract_cmd(
    ctx: click.Context,
    bundle_id: str,
    output: str,
    udid: Optional[str],
) -> None:
    """
    Extract an app as an IPA file.

    NOTE: The extracted IPA will be FairPlay encrypted if downloaded
    from the App Store. To use with PlayCover, you need a decrypted IPA.
    See: orange apps extract --help for more info.

    Examples:

        $ orange apps extract com.netflix.Netflix ./Netflix.ipa
        $ orange apps extract com.spotify.client ~/Desktop/Spotify.ipa

    For PlayCover usage:
        1. Get decrypted IPA from decrypt.day or similar
        2. Or use frida-ios-dump on a jailbroken device
        3. Install PlayCover from playcover.io
        4. Drag the decrypted IPA into PlayCover
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)
        output_path = Path(output)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Extracting {bundle_id}...", total=None)

            with AppManager(device_udid) as manager:
                result_path = manager.extract_ipa(bundle_id, output_path)

            progress.update(task, completed=True)

        console.print(f"\n[green]Successfully extracted:[/green] {result_path}")
        console.print()

        # Show warning about encryption
        console.print(
            Panel(
                "[yellow]Important:[/yellow] This IPA is likely FairPlay encrypted.\n\n"
                "To use with PlayCover on Apple Silicon Mac:\n"
                "1. Download a decrypted IPA from [cyan]decrypt.day[/cyan]\n"
                "2. Or decrypt using frida-ios-dump (requires jailbreak)\n"
                "3. Install PlayCover from [cyan]playcover.io[/cyan]\n"
                "4. Drag the [bold]decrypted[/bold] IPA into PlayCover",
                title="PlayCover Usage",
                border_style="yellow",
            )
        )

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@apps.command("playcover-guide")
@click.pass_context
def playcover_guide_cmd(ctx: click.Context) -> None:
    """
    Show guide for using iOS apps on Apple Silicon Macs.

    Displays step-by-step instructions for running iOS apps
    like Netflix on Apple Silicon Macs using PlayCover.
    """
    console = get_console(ctx)

    guide = """
[bold cyan]Running iOS Apps on Apple Silicon Macs[/bold cyan]

Apple Silicon Macs (M1/M2/M3/M4) can run iOS apps natively.
For apps like Netflix that block Mac App Store availability,
use PlayCover to sideload them.

[bold]Requirements:[/bold]
  - Apple Silicon Mac (M1, M2, M3, or M4 chip)
  - macOS 12.0 or later
  - PlayCover (free, open-source)
  - Decrypted IPA file

[bold]Step 1: Install PlayCover[/bold]
  Download from: [cyan]https://playcover.io[/cyan]
  Or via Homebrew: brew install --cask playcover-community

[bold]Step 2: Get Decrypted IPA[/bold]
  [yellow]Option A (Recommended):[/yellow]
    Download from [cyan]https://decrypt.day[/cyan]
    Search for the app you want (e.g., Netflix)

  [yellow]Option B (Requires Jailbreak):[/yellow]
    Use frida-ios-dump to decrypt from your device:
    $ frida-ios-dump -l  # List apps
    $ frida-ios-dump com.netflix.Netflix

  [dim]Note: IPAs extracted with 'orange apps extract' are
  FairPlay encrypted and won't work with PlayCover.[/dim]

[bold]Step 3: Install in PlayCover[/bold]
  1. Open PlayCover
  2. Drag the decrypted IPA into the window
  3. Wait for installation to complete
  4. Click the app icon to launch

[bold]Step 4: Sign In & Download[/bold]
  - Sign in to your Netflix account
  - Download content for offline viewing
  - Content downloads work just like on iPad!

[bold yellow]Important Notes:[/bold yellow]
  - Downloads on iPad do NOT sync to Mac
  - You must download content fresh on Mac
  - Some apps may have compatibility issues
  - PlayCover is not officially supported by Apple

[bold]Troubleshooting:[/bold]
  - "Encrypted IPA" error: Use a decrypted IPA
  - App crashes: Check PlayCover GitHub issues
  - Login issues: Clear app data and retry
"""

    console.print(Panel(guide, title="PlayCover Guide", border_style="blue"))
