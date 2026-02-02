"""
CLI commands for data export.

Provides commands for exporting messages, contacts, calendar events,
and notes from iOS backups.
"""

from __future__ import annotations

import click
from pathlib import Path
from typing import Optional

from rich.console import Console

from orange.constants import DEFAULT_BACKUP_DIR, DEFAULT_EXPORT_DIR
from orange.core.backup.reader import BackupReader
from orange.core.context import get_context
from orange.core.export import (
    MessageExporter,
    ContactExporter,
    CalendarExporter,
    NoteExporter,
)
from orange.exceptions import BackupError, ExportError

# Console for output
console = Console()


def info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def _find_backup(backup_path: Optional[str] = None) -> Path:
    """
    Find a backup to use for export.

    Args:
        backup_path: Explicit path to backup, or None to use from context or most recent.

    Returns:
        Path to the backup directory.

    Raises:
        click.ClickException: If no backup found.
    """
    if backup_path:
        path = Path(backup_path)
        if not path.exists():
            raise click.ClickException(f"Backup not found: {backup_path}")
        return path

    # Check context for last backup
    ctx_manager = get_context()
    last_backup = ctx_manager.get_last_backup()
    if last_backup and last_backup.exists():
        info(f"Using backup from context: {last_backup.path}")
        return last_backup.path_obj

    # Fall back to looking for backups in default location
    backup_dir = DEFAULT_BACKUP_DIR
    if not backup_dir.exists():
        raise click.ClickException(
            f"No backups found. Create one with 'orange backup create' "
            f"or specify --backup path"
        )

    # Find most recent backup
    backups = sorted(
        backup_dir.iterdir(),
        key=lambda p: p.stat().st_mtime if p.is_dir() else 0,
        reverse=True,
    )

    for backup in backups:
        if backup.is_dir() and (backup / "Manifest.plist").exists():
            return backup

    raise click.ClickException(
        f"No valid backups found in {backup_dir}. "
        f"Create one with 'orange backup create' or specify --backup path"
    )


def _get_output_path(
    output: Optional[str],
    default_name: str,
    export_type: str,
) -> Path:
    """Get output path, using default if not specified."""
    if output:
        return Path(output)

    # Use default export directory
    export_dir = DEFAULT_EXPORT_DIR / export_type
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir / default_name


@click.group("export")
def export() -> None:
    """Export data from iOS backups.

    Extract and export messages, contacts, calendar events, and notes
    from iOS backups to various formats (JSON, CSV, HTML, VCF, ICS).

    Example:
        orange export messages -o messages.json
        orange export contacts --format vcf
        orange export calendar --format ics
        orange export notes --format html
    """
    pass


# ============================================================================
# Messages Commands
# ============================================================================


@export.command("messages")
@click.option(
    "--backup", "-b",
    help="Path to backup directory. Uses most recent if not specified.",
)
@click.option(
    "--output", "-o",
    help="Output file path.",
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "csv", "html"]),
    default="json",
    help="Output format.",
)
@click.option(
    "--contact", "-c",
    help="Filter messages by contact phone/email.",
)
@click.option(
    "--limit", "-l",
    type=int,
    help="Maximum number of messages to export.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def messages_cmd(
    backup: Optional[str],
    output: Optional[str],
    output_format: str,
    contact: Optional[str],
    limit: Optional[int],
    password: Optional[str],
) -> None:
    """Export messages (SMS/iMessage) from backup.

    Extracts text messages and iMessages from an iOS backup and
    exports them to JSON, CSV, or HTML format.

    Example:
        orange export messages
        orange export messages --format html -o chat.html
        orange export messages --contact "+1234567890"
    """
    try:
        backup_path = _find_backup(backup)
        info(f"Using backup: {backup_path.name}")

        reader = BackupReader(backup_path, password=password)

        if reader.is_encrypted and not password:
            warning("Backup is encrypted. Some data may not be extractable.")

        exporter = MessageExporter(reader)

        # Get messages
        info("Extracting messages...")
        messages = exporter.get_messages(contact=contact, limit=limit)

        if not messages:
            warning("No messages found in backup.")
            return

        # Get statistics
        stats = exporter.get_statistics()
        info(
            f"Found {stats['total_messages']} total messages "
            f"({stats['sent_messages']} sent, {stats['received_messages']} received)"
        )

        # Determine output path
        default_name = f"messages.{output_format}"
        if contact:
            safe_contact = contact.replace("+", "").replace(" ", "_")[:20]
            default_name = f"messages_{safe_contact}.{output_format}"

        output_path = _get_output_path(output, default_name, "messages")

        # Export
        if output_format == "json":
            exporter.export_json(messages, output_path)
        elif output_format == "csv":
            exporter.export_csv(messages, output_path)
        elif output_format == "html":
            title = f"Messages with {contact}" if contact else "Messages"
            exporter.export_html(messages, output_path, title=title)

        success(f"Exported {len(messages)} messages to {output_path}")

    except (BackupError, ExportError) as e:
        error(str(e))
        raise click.Abort()


@export.command("conversations")
@click.option(
    "--backup", "-b",
    help="Path to backup directory.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def conversations_cmd(
    backup: Optional[str],
    password: Optional[str],
) -> None:
    """List message conversations in backup.

    Shows all conversations found in the backup with message counts.

    Example:
        orange export conversations
    """
    try:
        backup_path = _find_backup(backup)
        reader = BackupReader(backup_path, password=password)
        exporter = MessageExporter(reader)

        conversations = exporter.get_conversations()

        if not conversations:
            warning("No conversations found in backup.")
            return

        click.echo("\nConversations:")
        click.echo("-" * 60)

        for conv in conversations:
            display_name = conv["display_name"] or conv["identifier"]
            service = conv["service"] or "unknown"
            count = conv["message_count"]
            click.echo(f"  {display_name:<30} ({service}) - {count} messages")

        click.echo(f"\nTotal: {len(conversations)} conversations")

    except (BackupError, ExportError) as e:
        error(str(e))
        raise click.Abort()


# ============================================================================
# Contacts Commands
# ============================================================================


@export.command("contacts")
@click.option(
    "--backup", "-b",
    help="Path to backup directory.",
)
@click.option(
    "--output", "-o",
    help="Output file path.",
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "csv", "vcf"]),
    default="vcf",
    help="Output format. VCF (vCard) is best for importing to other apps.",
)
@click.option(
    "--search", "-s",
    help="Search contacts by name.",
)
@click.option(
    "--limit", "-l",
    type=int,
    help="Maximum number of contacts to export.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def contacts_cmd(
    backup: Optional[str],
    output: Optional[str],
    output_format: str,
    search: Optional[str],
    limit: Optional[int],
    password: Optional[str],
) -> None:
    """Export contacts from backup.

    Extracts contacts from an iOS backup and exports them to
    JSON, CSV, or vCard (VCF) format.

    VCF format is recommended for importing to other apps like
    Google Contacts, Outlook, or Apple Contacts.

    Example:
        orange export contacts
        orange export contacts --format vcf -o contacts.vcf
        orange export contacts --search "John"
    """
    try:
        backup_path = _find_backup(backup)
        info(f"Using backup: {backup_path.name}")

        reader = BackupReader(backup_path, password=password)
        exporter = ContactExporter(reader)

        # Get contacts
        info("Extracting contacts...")
        contacts = exporter.get_contacts(search=search, limit=limit)

        if not contacts:
            warning("No contacts found in backup.")
            return

        # Get statistics
        stats = exporter.get_statistics()
        info(
            f"Found {stats['total_contacts']} contacts "
            f"({stats['with_phones']} with phones, "
            f"{stats['with_emails']} with emails)"
        )

        # Determine output path
        default_name = f"contacts.{output_format}"
        output_path = _get_output_path(output, default_name, "contacts")

        # Export
        if output_format == "json":
            exporter.export_json(contacts, output_path)
        elif output_format == "csv":
            exporter.export_csv(contacts, output_path)
        elif output_format == "vcf":
            exporter.export_vcf(contacts, output_path)

        success(f"Exported {len(contacts)} contacts to {output_path}")

    except (BackupError, ExportError) as e:
        error(str(e))
        raise click.Abort()


# ============================================================================
# Calendar Commands
# ============================================================================


@export.command("calendar")
@click.option(
    "--backup", "-b",
    help="Path to backup directory.",
)
@click.option(
    "--output", "-o",
    help="Output file path.",
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "csv", "ics"]),
    default="ics",
    help="Output format. ICS (iCalendar) is best for importing.",
)
@click.option(
    "--calendar", "-c", "calendar_id",
    type=int,
    help="Export only events from specific calendar ID.",
)
@click.option(
    "--search", "-s",
    help="Search events by title/location.",
)
@click.option(
    "--limit", "-l",
    type=int,
    help="Maximum number of events to export.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def calendar_cmd(
    backup: Optional[str],
    output: Optional[str],
    output_format: str,
    calendar_id: Optional[int],
    search: Optional[str],
    limit: Optional[int],
    password: Optional[str],
) -> None:
    """Export calendar events from backup.

    Extracts calendar events from an iOS backup and exports them to
    JSON, CSV, or iCalendar (ICS) format.

    ICS format is recommended for importing to Google Calendar,
    Outlook, or Apple Calendar.

    Example:
        orange export calendar
        orange export calendar --format ics -o events.ics
        orange export calendar --search "meeting"
    """
    try:
        backup_path = _find_backup(backup)
        info(f"Using backup: {backup_path.name}")

        reader = BackupReader(backup_path, password=password)
        exporter = CalendarExporter(reader)

        # Get events
        info("Extracting calendar events...")
        events = exporter.get_events(
            calendar_id=calendar_id,
            search=search,
            limit=limit,
        )

        if not events:
            warning("No calendar events found in backup.")
            return

        # Get statistics
        stats = exporter.get_statistics()
        info(
            f"Found {stats['total_events']} events in "
            f"{stats['total_calendars']} calendars"
        )

        # Determine output path
        default_name = f"calendar.{output_format}"
        output_path = _get_output_path(output, default_name, "calendar")

        # Export
        if output_format == "json":
            exporter.export_json(events, output_path)
        elif output_format == "csv":
            exporter.export_csv(events, output_path)
        elif output_format == "ics":
            exporter.export_ics(events, output_path)

        success(f"Exported {len(events)} events to {output_path}")

    except (BackupError, ExportError) as e:
        error(str(e))
        raise click.Abort()


@export.command("calendars")
@click.option(
    "--backup", "-b",
    help="Path to backup directory.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def calendars_cmd(
    backup: Optional[str],
    password: Optional[str],
) -> None:
    """List calendars in backup.

    Shows all calendars found in the backup with event counts.

    Example:
        orange export calendars
    """
    try:
        backup_path = _find_backup(backup)
        reader = BackupReader(backup_path, password=password)
        exporter = CalendarExporter(reader)

        calendars = exporter.get_calendars()

        if not calendars:
            warning("No calendars found in backup.")
            return

        click.echo("\nCalendars:")
        click.echo("-" * 50)

        for cal in calendars:
            name = cal["title"] or "Untitled"
            count = cal["event_count"]
            cal_id = cal["calendar_id"]
            click.echo(f"  [{cal_id}] {name:<30} ({count} events)")

        click.echo(f"\nTotal: {len(calendars)} calendars")
        click.echo("\nTip: Use --calendar ID to export a specific calendar")

    except (BackupError, ExportError) as e:
        error(str(e))
        raise click.Abort()


# ============================================================================
# Notes Commands
# ============================================================================


@export.command("notes")
@click.option(
    "--backup", "-b",
    help="Path to backup directory.",
)
@click.option(
    "--output", "-o",
    help="Output file path.",
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "csv", "html"]),
    default="html",
    help="Output format.",
)
@click.option(
    "--search", "-s",
    help="Search notes by title/content.",
)
@click.option(
    "--limit", "-l",
    type=int,
    help="Maximum number of notes to export.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def notes_cmd(
    backup: Optional[str],
    output: Optional[str],
    output_format: str,
    search: Optional[str],
    limit: Optional[int],
    password: Optional[str],
) -> None:
    """Export notes from backup.

    Extracts notes from an iOS backup and exports them to
    JSON, CSV, or HTML format.

    Note: Password-protected notes cannot be exported without
    unlocking them first on the device.

    Example:
        orange export notes
        orange export notes --format html -o notes.html
        orange export notes --search "recipe"
    """
    try:
        backup_path = _find_backup(backup)
        info(f"Using backup: {backup_path.name}")

        reader = BackupReader(backup_path, password=password)
        exporter = NoteExporter(reader)

        # Get notes
        info("Extracting notes...")
        notes = exporter.get_notes(search=search, limit=limit)

        if not notes:
            warning("No notes found in backup.")
            return

        # Get statistics
        stats = exporter.get_statistics()
        info(
            f"Found {stats['total_notes']} notes "
            f"({stats['pinned_notes']} pinned, {stats['locked_notes']} locked)"
        )

        # Determine output path
        default_name = f"notes.{output_format}"
        output_path = _get_output_path(output, default_name, "notes")

        # Export
        if output_format == "json":
            exporter.export_json(notes, output_path)
        elif output_format == "csv":
            exporter.export_csv(notes, output_path)
        elif output_format == "html":
            exporter.export_html(notes, output_path)

        success(f"Exported {len(notes)} notes to {output_path}")

    except (BackupError, ExportError) as e:
        error(str(e))
        raise click.Abort()


@export.command("folders")
@click.option(
    "--backup", "-b",
    help="Path to backup directory.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def folders_cmd(
    backup: Optional[str],
    password: Optional[str],
) -> None:
    """List note folders in backup.

    Shows all note folders found in the backup.

    Example:
        orange export folders
    """
    try:
        backup_path = _find_backup(backup)
        reader = BackupReader(backup_path, password=password)
        exporter = NoteExporter(reader)

        folders = exporter.get_folders()

        if not folders:
            warning("No note folders found in backup.")
            return

        click.echo("\nNote Folders:")
        click.echo("-" * 40)

        for folder in folders:
            name = folder["title"] or "Untitled"
            count = folder["note_count"]
            click.echo(f"  {name:<30} ({count} notes)")

        click.echo(f"\nTotal: {len(folders)} folders")

    except (BackupError, ExportError) as e:
        error(str(e))
        raise click.Abort()


# ============================================================================
# Summary Command
# ============================================================================


@export.command("summary")
@click.option(
    "--backup", "-b",
    help="Path to backup directory.",
)
@click.option(
    "--password", "-p",
    help="Backup password (if encrypted).",
)
def summary_cmd(
    backup: Optional[str],
    password: Optional[str],
) -> None:
    """Show summary of exportable data in backup.

    Displays counts of messages, contacts, calendar events, and notes
    available for export.

    Example:
        orange export summary
    """
    try:
        backup_path = _find_backup(backup)
        info(f"Using backup: {backup_path.name}")

        reader = BackupReader(backup_path, password=password)

        if reader.is_encrypted:
            warning("Backup is encrypted. Some statistics may be incomplete.")

        click.echo("\nExportable Data Summary")
        click.echo("=" * 50)

        # Messages
        try:
            msg_exporter = MessageExporter(reader)
            msg_stats = msg_exporter.get_statistics()
            click.echo(f"\nMessages:")
            click.echo(f"  Total:     {msg_stats['total_messages']:,}")
            click.echo(f"  Sent:      {msg_stats['sent_messages']:,}")
            click.echo(f"  Received:  {msg_stats['received_messages']:,}")
            click.echo(f"  Chats:     {msg_stats['conversations']}")
            if msg_stats['first_message']:
                click.echo(
                    f"  Date range: "
                    f"{msg_stats['first_message'].strftime('%Y-%m-%d')} to "
                    f"{msg_stats['last_message'].strftime('%Y-%m-%d')}"
                )
        except ExportError:
            click.echo(f"\nMessages: Not available")

        # Contacts
        try:
            contact_exporter = ContactExporter(reader)
            contact_stats = contact_exporter.get_statistics()
            click.echo(f"\nContacts:")
            click.echo(f"  Total:       {contact_stats['total_contacts']:,}")
            click.echo(f"  With phone:  {contact_stats['with_phones']:,}")
            click.echo(f"  With email:  {contact_stats['with_emails']:,}")
        except ExportError:
            click.echo(f"\nContacts: Not available")

        # Calendar
        try:
            cal_exporter = CalendarExporter(reader)
            cal_stats = cal_exporter.get_statistics()
            click.echo(f"\nCalendar:")
            click.echo(f"  Total events: {cal_stats['total_events']:,}")
            click.echo(f"  Calendars:    {cal_stats['total_calendars']}")
            click.echo(f"  All-day:      {cal_stats['all_day_events']:,}")
        except ExportError:
            click.echo(f"\nCalendar: Not available")

        # Notes
        try:
            note_exporter = NoteExporter(reader)
            note_stats = note_exporter.get_statistics()
            click.echo(f"\nNotes:")
            click.echo(f"  Total:   {note_stats['total_notes']:,}")
            click.echo(f"  Folders: {note_stats['total_folders']}")
            click.echo(f"  Pinned:  {note_stats['pinned_notes']:,}")
            click.echo(f"  Locked:  {note_stats['locked_notes']:,}")
        except ExportError:
            click.echo(f"\nNotes: Not available")

        click.echo("\n" + "=" * 50)
        click.echo("Use 'orange export <type>' to export specific data")

    except BackupError as e:
        error(str(e))
        raise click.Abort()
