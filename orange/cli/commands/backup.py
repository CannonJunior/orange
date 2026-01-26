"""
Backup-related CLI commands.

Commands for creating, restoring, and managing iOS device backups.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from orange.core.backup import BackupManager, BackupReader, BackupInfo
from orange.core.connection import DeviceDetector
from orange.exceptions import (
    BackupError,
    DeviceNotFoundError,
    DeviceNotPairedError,
)


def get_console(ctx: click.Context) -> Console:
    """Get the Rich console from context."""
    return ctx.obj.get("console", Console())


@click.group()
def backup() -> None:
    """Manage iOS device backups."""
    pass


@backup.command("create")
@click.argument("udid", required=False)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Backup destination directory.",
)
@click.option(
    "--full/--incremental",
    default=True,
    help="Create full or incremental backup.",
)
@click.pass_context
def create_cmd(
    ctx: click.Context,
    udid: Optional[str],
    output: Optional[Path],
    full: bool,
) -> None:
    """Create a backup of an iOS device.

    If UDID is not specified and only one device is connected,
    that device will be used automatically.
    """
    console = get_console(ctx)

    # Find device if UDID not specified
    if udid is None:
        detector = DeviceDetector()
        devices = detector.list_devices()

        if not devices:
            console.print("[red]No iOS devices found.[/red]")
            sys.exit(1)

        if len(devices) > 1:
            console.print("[yellow]Multiple devices found. Please specify UDID:[/yellow]")
            for dev in devices:
                console.print(f"  {dev.udid}  ({dev.name})")
            sys.exit(1)

        udid = devices[0].udid
        console.print(f"Using device: [cyan]{devices[0].name}[/cyan]")

    manager = BackupManager()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Creating backup...", total=100)

            def progress_callback(percentage: float) -> None:
                progress.update(task, completed=percentage)

            backup_info = manager.create_backup(
                udid=udid,
                destination=output,
                full=full,
                progress_callback=progress_callback,
            )

        console.print()
        console.print(f"[green]✓ Backup created successfully[/green]")
        console.print(f"  Device: {backup_info.device_name}")
        console.print(f"  Size: {backup_info.size_human}")
        console.print(f"  Path: {backup_info.path}")

    except DeviceNotFoundError:
        console.print("[red]✗ Device not found[/red]")
        sys.exit(1)

    except DeviceNotPairedError:
        console.print("[red]✗ Device not paired. Run 'orange device pair' first.[/red]")
        sys.exit(1)

    except BackupError as e:
        console.print(f"[red]✗ Backup failed: {e}[/red]")
        sys.exit(1)


@backup.command("restore")
@click.argument("backup_path", type=click.Path(exists=True, path_type=Path))
@click.argument("udid", required=False)
@click.option(
    "--password", "-p",
    help="Password for encrypted backups.",
)
@click.option(
    "--system/--no-system",
    default=False,
    help="Restore system files.",
)
@click.option(
    "--settings/--no-settings",
    default=True,
    help="Restore device settings.",
)
@click.option(
    "--reboot/--no-reboot",
    default=True,
    help="Reboot device after restore.",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def restore_cmd(
    ctx: click.Context,
    backup_path: Path,
    udid: Optional[str],
    password: Optional[str],
    system: bool,
    settings: bool,
    reboot: bool,
    yes: bool,
) -> None:
    """Restore a backup to an iOS device.

    BACKUP_PATH is the path to the backup directory to restore.
    """
    console = get_console(ctx)

    # Find device if UDID not specified
    if udid is None:
        detector = DeviceDetector()
        devices = detector.list_devices()

        if not devices:
            console.print("[red]No iOS devices found.[/red]")
            sys.exit(1)

        if len(devices) > 1:
            console.print("[yellow]Multiple devices found. Please specify UDID:[/yellow]")
            for dev in devices:
                console.print(f"  {dev.udid}  ({dev.name})")
            sys.exit(1)

        udid = devices[0].udid
        device_name = devices[0].name
    else:
        device_name = udid

    # Confirm restore
    if not yes:
        console.print(f"[yellow]Warning: This will restore backup to {device_name}[/yellow]")
        console.print("[yellow]All current data on the device may be overwritten.[/yellow]")
        if not click.confirm("Continue?"):
            console.print("Cancelled.")
            return

    manager = BackupManager()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Restoring backup...", total=100)

            def progress_callback(percentage: float) -> None:
                progress.update(task, completed=percentage)

            manager.restore_backup(
                udid=udid,
                backup_path=backup_path.parent,
                source_udid=backup_path.name,
                password=password,
                system=system,
                settings=settings,
                reboot=reboot,
                progress_callback=progress_callback,
            )

        console.print()
        console.print("[green]✓ Restore completed successfully[/green]")
        if reboot:
            console.print("[dim]Device will reboot shortly.[/dim]")

    except DeviceNotFoundError:
        console.print("[red]✗ Device not found[/red]")
        sys.exit(1)

    except BackupError as e:
        console.print(f"[red]✗ Restore failed: {e}[/red]")
        sys.exit(1)


@backup.command("list")
@click.option(
    "--dir", "-d",
    "backup_dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory to search for backups.",
)
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def list_cmd(
    ctx: click.Context,
    backup_dir: Optional[Path],
    as_json: bool,
) -> None:
    """List available backups."""
    console = get_console(ctx)

    manager = BackupManager(backup_dir=backup_dir)
    backups = manager.list_backups()

    if not backups:
        if as_json:
            click.echo("[]")
        else:
            console.print("[yellow]No backups found.[/yellow]")
            console.print(f"Backup directory: {manager.backup_dir}")
        return

    if as_json:
        output = [b.to_dict() for b in backups]
        click.echo(json.dumps(output, indent=2))
        return

    # Create table
    table = Table(title="iOS Backups")
    table.add_column("Device", style="cyan", no_wrap=True)
    table.add_column("iOS", style="green")
    table.add_column("Date", style="blue")
    table.add_column("Size", style="magenta")
    table.add_column("Encrypted", style="yellow")
    table.add_column("Path", style="dim")

    for backup in backups:
        date_str = backup.backup_date.strftime("%Y-%m-%d %H:%M")
        encrypted = "Yes" if backup.is_encrypted else "No"

        table.add_row(
            backup.device_name,
            backup.ios_version,
            date_str,
            backup.size_human,
            encrypted,
            str(backup.path.name),
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(backups)} backup(s) in {manager.backup_dir}[/dim]")


@backup.command("info")
@click.argument("backup_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def info_cmd(
    ctx: click.Context,
    backup_path: Path,
    as_json: bool,
) -> None:
    """Show detailed information about a backup."""
    console = get_console(ctx)

    try:
        manager = BackupManager()
        backup = manager.get_backup_info(backup_path)

        if as_json:
            click.echo(json.dumps(backup.to_dict(), indent=2))
            return

        # Display backup info
        content = []
        content.append(f"[bold]Device Name:[/bold] {backup.device_name}")
        content.append(f"[bold]Device UDID:[/bold] {backup.device_udid}")
        content.append(f"[bold]iOS Version:[/bold] {backup.ios_version} ({backup.build_version})")
        content.append(f"[bold]Backup Date:[/bold] {backup.backup_date.strftime('%Y-%m-%d %H:%M:%S')}")
        content.append(f"[bold]Size:[/bold] {backup.size_human}")
        content.append(f"[bold]Encrypted:[/bold] {'Yes' if backup.is_encrypted else 'No'}")

        if backup.product_type:
            content.append(f"[bold]Model:[/bold] {backup.product_type}")
        if backup.serial_number:
            content.append(f"[bold]Serial:[/bold] {backup.serial_number}")

        content.append(f"[bold]Path:[/bold] {backup.path}")

        panel = Panel(
            "\n".join(content),
            title=f"Backup: {backup.device_name}",
            border_style="cyan",
        )
        console.print(panel)

    except BackupError as e:
        console.print(f"[red]Failed to read backup: {e}[/red]")
        sys.exit(1)


@backup.command("browse")
@click.argument("backup_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--domain", "-d",
    help="Filter by domain (e.g., HomeDomain, CameraRollDomain).",
)
@click.option(
    "--filter", "-f",
    "path_filter",
    help="Filter by path substring.",
)
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def browse_cmd(
    ctx: click.Context,
    backup_path: Path,
    domain: Optional[str],
    path_filter: Optional[str],
    as_json: bool,
) -> None:
    """Browse files in a backup."""
    console = get_console(ctx)

    try:
        reader = BackupReader(backup_path)

        if domain is None and path_filter is None:
            # Show domains
            domains = reader.list_domains()

            if as_json:
                click.echo(json.dumps(domains, indent=2))
                return

            console.print("[bold]Backup Domains:[/bold]")
            for d in domains:
                console.print(f"  {d}")
            console.print(f"\n[dim]Use --domain <name> to browse a specific domain[/dim]")
            return

        # List files
        files = reader.list_files(domain=domain, path_filter=path_filter)

        if as_json:
            output = [f.to_dict() for f in files]
            click.echo(json.dumps(output, indent=2))
            return

        if not files:
            console.print("[yellow]No files found matching criteria.[/yellow]")
            return

        # Create table
        table = Table(title=f"Files in {domain or 'all domains'}")
        table.add_column("Domain", style="cyan", max_width=20)
        table.add_column("Path", style="green")
        table.add_column("Size", style="magenta", justify="right")
        table.add_column("Type", style="blue")

        # Limit display
        display_limit = 100
        for file in files[:display_limit]:
            file_type = "Dir" if file.is_directory else "File"
            size_str = f"{file.size:,}" if not file.is_directory else "-"

            table.add_row(
                file.domain,
                file.relative_path,
                size_str,
                file_type,
            )

        console.print(table)

        if len(files) > display_limit:
            console.print(f"\n[dim]Showing {display_limit} of {len(files)} files[/dim]")
        else:
            console.print(f"\n[dim]Found {len(files)} file(s)[/dim]")

    except BackupError as e:
        console.print(f"[red]Failed to read backup: {e}[/red]")
        sys.exit(1)


@backup.command("extract")
@click.argument("backup_path", type=click.Path(exists=True, path_type=Path))
@click.argument("file_path")
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=".",
    help="Output directory.",
)
@click.option(
    "--domain", "-d",
    help="File domain (required if file_path is relative).",
)
@click.option(
    "--password", "-p",
    help="Password for encrypted backups.",
)
@click.pass_context
def extract_cmd(
    ctx: click.Context,
    backup_path: Path,
    file_path: str,
    output: Path,
    domain: Optional[str],
    password: Optional[str],
) -> None:
    """Extract a file from a backup.

    FILE_PATH can be a file ID or a relative path (if --domain is specified).
    """
    console = get_console(ctx)

    try:
        reader = BackupReader(backup_path, password=password)

        # Try to find the file
        if domain:
            files = reader.list_files(domain=domain, path_filter=file_path)
            if not files:
                console.print(f"[red]File not found: {domain}/{file_path}[/red]")
                sys.exit(1)
            file_id = files[0].file_id
        else:
            # Assume it's a file ID
            file_id = file_path

        # Extract
        extracted = reader.extract_file(file_id, output)

        if extracted:
            console.print(f"[green]✓ Extracted to {extracted}[/green]")
        else:
            console.print("[red]✗ Failed to extract file[/red]")
            sys.exit(1)

    except BackupError as e:
        console.print(f"[red]Failed to extract: {e}[/red]")
        sys.exit(1)


@backup.command("delete")
@click.argument("backup_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def delete_cmd(
    ctx: click.Context,
    backup_path: Path,
    yes: bool,
) -> None:
    """Delete a backup."""
    console = get_console(ctx)

    try:
        manager = BackupManager()
        backup = manager.get_backup_info(backup_path)

        # Confirm
        if not yes:
            console.print(f"[yellow]About to delete backup:[/yellow]")
            console.print(f"  Device: {backup.device_name}")
            console.print(f"  Date: {backup.backup_date}")
            console.print(f"  Size: {backup.size_human}")
            if not click.confirm("Delete this backup?"):
                console.print("Cancelled.")
                return

        if manager.delete_backup(backup_path):
            console.print("[green]✓ Backup deleted[/green]")
        else:
            console.print("[red]✗ Failed to delete backup[/red]")
            sys.exit(1)

    except BackupError as e:
        console.print(f"[red]Failed to delete: {e}[/red]")
        sys.exit(1)
