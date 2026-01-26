"""
CLI commands for file browsing and transfer.

This module provides commands for browsing device files and
transferring files/categories between iOS devices and computers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from orange.core.transfer import (
    DeviceBrowser,
    FileManager,
    FileInfo,
    CATEGORIES,
    get_category,
    list_categories,
)
from orange.core.transfer.categories import AccessMethod
from orange.core.connection import DeviceDetector
from orange.exceptions import OrangeError, DeviceNotFoundError, TransferError

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
        detector = DeviceDetector()
        devices = detector.list_devices()
    except Exception as e:
        raise DeviceNotFoundError(
            "No iOS device connected. Please connect a device via USB and try again."
        ) from e

    if not devices:
        raise DeviceNotFoundError(
            "No iOS device connected. Please connect a device via USB and try again."
        )

    if len(devices) > 1:
        raise click.UsageError(
            "Multiple devices connected. Please specify UDID.\n"
            "Use 'orange device list' to see connected devices."
        )

    return devices[0].udid


@click.group()
def files() -> None:
    """
    Browse and transfer files on iOS devices.

    Use AFC (Apple File Conduit) to access the device's media partition
    and transfer files directly without a full backup.

    Examples:

        List files in root:
        $ orange files browse

        List files in DCIM:
        $ orange files browse /DCIM

        Pull photos:
        $ orange files pull-category photos ./photos

        Pull specific directory:
        $ orange files pull /DCIM/100APPLE ./photos
    """
    pass


@files.command("browse")
@click.argument("path", default="/")
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def browse_cmd(
    ctx: click.Context,
    path: str,
    udid: Optional[str],
    as_json: bool,
) -> None:
    """
    Browse files on the device.

    PATH is the directory to list (default: root).

    Examples:

        $ orange files browse
        $ orange files browse /DCIM
        $ orange files browse /DCIM/100APPLE --json
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)

        with DeviceBrowser(device_udid) as browser:
            items = browser.list_directory(path)

            if as_json:
                import json
                console.print(json.dumps([item.to_dict() for item in items], indent=2))
                return

            if not items:
                console.print(f"[dim]Empty directory: {path}[/dim]")
                return

            table = Table(title=f"Files in {path}")
            table.add_column("Name", style="cyan")
            table.add_column("Size", justify="right")
            table.add_column("Modified", style="dim")
            table.add_column("Type", style="dim")

            for item in items:
                file_type = "📁" if item.is_directory else "📄"
                modified = item.modified_time.strftime("%Y-%m-%d %H:%M") if item.modified_time else "-"

                table.add_row(
                    item.name,
                    item.size_human,
                    modified,
                    file_type,
                )

            console.print(table)
            console.print(f"\n[dim]{len(items)} items[/dim]")

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@files.command("categories")
@click.option("--afc-only", is_flag=True, help="Show only AFC-accessible categories.")
@click.pass_context
def categories_cmd(ctx: click.Context, afc_only: bool) -> None:
    """
    List available data categories.

    Categories with AFC access can be transferred directly.
    Categories with BACKUP access require a full/partial backup.

    Examples:

        $ orange files categories
        $ orange files categories --afc-only
    """
    console = get_console(ctx)

    categories = list_categories(AccessMethod.AFC if afc_only else None)

    table = Table(title="Data Categories")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Access", style="dim")

    for cat in categories:
        access_style = "green" if cat.access_method == AccessMethod.AFC else "yellow"
        access_text = f"[{access_style}]{cat.access_method.value.upper()}[/{access_style}]"

        table.add_row(
            cat.id,
            cat.name,
            cat.description,
            access_text,
        )

    console.print(table)

    console.print("\n[dim]AFC = Direct file access (fast)[/dim]")
    console.print("[dim]BACKUP = Requires backup extraction (use 'orange backup create')[/dim]")


@files.command("pull")
@click.argument("remote_path")
@click.argument("local_path", type=click.Path())
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.pass_context
def pull_cmd(
    ctx: click.Context,
    remote_path: str,
    local_path: str,
    udid: Optional[str],
) -> None:
    """
    Pull (download) files from the device.

    REMOTE_PATH is the path on the device.
    LOCAL_PATH is the destination on your computer.

    Examples:

        $ orange files pull /DCIM/100APPLE ./photos
        $ orange files pull /Downloads ./downloads
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)
        local = Path(local_path)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Transferring...", total=100)

            def on_progress(p):
                progress.update(task, completed=p.percentage, description=f"[cyan]{p.current_file or 'Scanning...'}[/cyan]")

            with FileManager(device_udid) as manager:
                result = manager.pull(remote_path, local, progress_callback=on_progress)

        console.print(f"\n[green]✓[/green] Transferred {result.completed_files} files ({_format_bytes(result.completed_bytes)})")

        if result.failed_files:
            console.print(f"[yellow]⚠[/yellow] {len(result.failed_files)} files failed")

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@files.command("push")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_path")
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.pass_context
def push_cmd(
    ctx: click.Context,
    local_path: str,
    remote_path: str,
    udid: Optional[str],
) -> None:
    """
    Push (upload) files to the device.

    LOCAL_PATH is the file or directory on your computer.
    REMOTE_PATH is the destination on the device.

    Examples:

        $ orange files push ./music /iTunes_Control/Music
        $ orange files push ./photo.jpg /DCIM
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)
        local = Path(local_path)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Transferring...", total=100)

            def on_progress(p):
                progress.update(task, completed=p.percentage, description=f"[cyan]{p.current_file or 'Scanning...'}[/cyan]")

            with FileManager(device_udid) as manager:
                result = manager.push(local, remote_path, progress_callback=on_progress)

        console.print(f"\n[green]✓[/green] Transferred {result.completed_files} files ({_format_bytes(result.completed_bytes)})")

        if result.failed_files:
            console.print(f"[yellow]⚠[/yellow] {len(result.failed_files)} files failed")

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@files.command("pull-category")
@click.argument("category")
@click.argument("local_path", type=click.Path())
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.pass_context
def pull_category_cmd(
    ctx: click.Context,
    category: str,
    local_path: str,
    udid: Optional[str],
) -> None:
    """
    Pull all files for a data category.

    CATEGORY is the category ID (e.g., photos, music, books).
    LOCAL_PATH is the destination directory.

    Only AFC-accessible categories can be pulled directly.
    For BACKUP categories, use 'orange backup create' instead.

    Examples:

        $ orange files pull-category photos ./my-photos
        $ orange files pull-category music ./my-music
        $ orange files pull-category recordings ./voice-memos
    """
    console = get_console(ctx)

    # Validate category
    cat = get_category(category)
    if cat is None:
        console.print(f"[red]Error:[/red] Unknown category: {category}")
        console.print("\nAvailable categories:")
        for c in CATEGORIES.values():
            access = "[green]AFC[/green]" if c.access_method == AccessMethod.AFC else "[yellow]BACKUP[/yellow]"
            console.print(f"  {c.id}: {c.name} ({access})")
        raise SystemExit(1)

    if cat.access_method != AccessMethod.AFC:
        console.print(f"[yellow]Note:[/yellow] '{cat.name}' requires backup access.")
        console.print(f"Use 'orange backup create' to backup, then extract from backup.")
        raise SystemExit(1)

    try:
        device_udid = get_device_udid(udid)
        local = Path(local_path)

        console.print(f"[bold]Pulling {cat.name}...[/bold]")
        console.print(f"Paths: {', '.join(cat.afc_paths or [])}\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning...", total=100)

            def on_progress(p):
                desc = p.current_file or "Scanning..."
                # Truncate long paths
                if len(desc) > 50:
                    desc = "..." + desc[-47:]
                progress.update(task, completed=p.percentage, description=f"[cyan]{desc}[/cyan]")

            with FileManager(device_udid) as manager:
                result = manager.pull_category(category, local, progress_callback=on_progress)

        console.print(f"\n[green]✓[/green] Transferred {result.completed_files} files ({_format_bytes(result.completed_bytes)})")
        console.print(f"[dim]Saved to: {local.absolute()}[/dim]")

        if result.failed_files:
            console.print(f"[yellow]⚠[/yellow] {len(result.failed_files)} files failed")

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@files.command("size")
@click.argument("category")
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.pass_context
def size_cmd(
    ctx: click.Context,
    category: str,
    udid: Optional[str],
) -> None:
    """
    Show size of a category on the device.

    CATEGORY is the category ID (e.g., photos, music).

    Examples:

        $ orange files size photos
        $ orange files size music
    """
    console = get_console(ctx)

    cat = get_category(category)
    if cat is None:
        console.print(f"[red]Error:[/red] Unknown category: {category}")
        raise SystemExit(1)

    if cat.access_method != AccessMethod.AFC:
        console.print(f"[yellow]Note:[/yellow] '{cat.name}' requires backup access.")
        console.print("Size information not available for backup categories.")
        raise SystemExit(1)

    try:
        device_udid = get_device_udid(udid)

        with console.status(f"[cyan]Calculating size of {cat.name}...[/cyan]"):
            with FileManager(device_udid) as manager:
                total_bytes = manager.get_category_size(category)

        console.print(f"\n[bold]{cat.name}[/bold]: {_format_bytes(total_bytes)}")

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@files.command("info")
@click.argument("path")
@click.option("--udid", "-u", help="Device UDID (optional if single device).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def info_cmd(
    ctx: click.Context,
    path: str,
    udid: Optional[str],
    as_json: bool,
) -> None:
    """
    Show information about a file or directory.

    PATH is the path on the device.

    Examples:

        $ orange files info /DCIM
        $ orange files info /DCIM/100APPLE/IMG_0001.HEIC
    """
    console = get_console(ctx)

    try:
        device_udid = get_device_udid(udid)

        with DeviceBrowser(device_udid) as browser:
            info = browser.stat(path)

            if as_json:
                import json
                console.print(json.dumps(info.to_dict(), indent=2))
                return

            table = Table(title=f"File Info: {path}")
            table.add_column("Property", style="cyan")
            table.add_column("Value")

            table.add_row("Name", info.name)
            table.add_row("Path", info.path)
            table.add_row("Type", "Directory" if info.is_directory else "File")
            table.add_row("Size", info.size_human)

            if info.modified_time:
                table.add_row("Modified", info.modified_time.strftime("%Y-%m-%d %H:%M:%S"))
            if info.created_time:
                table.add_row("Created", info.created_time.strftime("%Y-%m-%d %H:%M:%S"))
            if info.permissions:
                table.add_row("Permissions", oct(info.permissions))

            console.print(table)

    except OrangeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


def _format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
