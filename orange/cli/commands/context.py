"""
CLI commands for managing Orange context.

This module provides commands for viewing and managing the persistent
context state that Orange uses across commands.
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

from orange.core.context import get_context, OrangeContext


def get_console(ctx: click.Context) -> Console:
    """Get the Rich console from context."""
    return ctx.obj.get("console", Console()) if ctx.obj else Console()


@click.group()
def context() -> None:
    """View and manage Orange context.

    Orange remembers recent backups, exports, and other resources
    so you don't have to specify paths repeatedly.

    Examples:

        Show current context:
        $ orange context show

        List recent backups:
        $ orange context backups

        Clear all context:
        $ orange context clear
    """
    pass


@context.command("show")
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def show_cmd(ctx: click.Context, as_json: bool) -> None:
    """Show current context state."""
    console = get_console(ctx)
    ctx_manager = get_context()

    if as_json:
        click.echo(json.dumps(ctx_manager.to_dict(), indent=2))
        return

    state = ctx_manager.state

    # Last backup
    if state.last_backup:
        backup = state.last_backup
        exists = "[green]✓[/green]" if backup.exists() else "[red]✗ (deleted)[/red]"
        content = [
            f"[bold]Path:[/bold] {backup.path} {exists}",
            f"[bold]Device:[/bold] {backup.device_name}",
            f"[bold]iOS:[/bold] {backup.ios_version}",
            f"[bold]Created:[/bold] {backup.created_at}",
        ]
        panel = Panel(
            "\n".join(content),
            title="Last Backup",
            border_style="cyan",
        )
        console.print(panel)
    else:
        console.print("[dim]No recent backup in context[/dim]")

    console.print()

    # Current device
    if state.current_device:
        device = state.current_device
        content = [
            f"[bold]UDID:[/bold] {device.udid}",
            f"[bold]Name:[/bold] {device.name}",
            f"[bold]iOS:[/bold] {device.ios_version}",
            f"[bold]Last seen:[/bold] {device.last_seen}",
        ]
        panel = Panel(
            "\n".join(content),
            title="Current Device",
            border_style="green",
        )
        console.print(panel)
    else:
        console.print("[dim]No current device in context[/dim]")

    console.print()

    # Last export
    if state.last_export:
        export = state.last_export
        content = [
            f"[bold]Path:[/bold] {export.path}",
            f"[bold]Type:[/bold] {export.export_type}",
            f"[bold]Records:[/bold] {export.record_count}",
            f"[bold]Created:[/bold] {export.created_at}",
        ]
        panel = Panel(
            "\n".join(content),
            title="Last Export",
            border_style="yellow",
        )
        console.print(panel)
    else:
        console.print("[dim]No recent export in context[/dim]")


@context.command("backups")
@click.option(
    "--all", "show_all",
    is_flag=True,
    help="Show all backups, including deleted ones.",
)
@click.pass_context
def backups_cmd(ctx: click.Context, show_all: bool) -> None:
    """List recent backups in context."""
    console = get_console(ctx)
    ctx_manager = get_context()

    backups = ctx_manager.get_recent_backups(existing_only=not show_all)

    if not backups:
        console.print("[yellow]No recent backups in context.[/yellow]")
        console.print("Run 'orange backup create' to create a backup.")
        return

    table = Table(title="Recent Backups")
    table.add_column("#", style="dim")
    table.add_column("Device", style="cyan")
    table.add_column("iOS", style="green")
    table.add_column("Created", style="blue")
    table.add_column("Status", style="dim")
    table.add_column("Path", style="dim", max_width=40)

    for i, backup in enumerate(backups, 1):
        status = "[green]exists[/green]" if backup.exists() else "[red]deleted[/red]"
        table.add_row(
            str(i),
            backup.device_name,
            backup.ios_version,
            backup.created_at[:19],  # Trim microseconds
            status,
            backup.path,
        )

    console.print(table)
    console.print()
    console.print("[dim]Use 'orange backup browse' to browse the most recent backup[/dim]")


@context.command("clear")
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def clear_cmd(ctx: click.Context, yes: bool) -> None:
    """Clear all context."""
    console = get_console(ctx)

    if not yes:
        if not click.confirm("Clear all context? This cannot be undone."):
            console.print("Cancelled.")
            return

    ctx_manager = get_context()
    ctx_manager.clear()
    console.print("[green]✓ Context cleared[/green]")


@context.command("path")
@click.pass_context
def path_cmd(ctx: click.Context) -> None:
    """Show context file path."""
    console = get_console(ctx)
    ctx_manager = get_context()
    console.print(f"Context file: {ctx_manager._context_file}")
