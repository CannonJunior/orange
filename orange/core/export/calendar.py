"""
Calendar exporter for iOS backups.

Parses the Calendar database from iOS backups and exports
events to various formats including iCalendar (ICS).
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from orange.constants import APPLE_EPOCH_OFFSET
from orange.core.backup.reader import BackupReader
from orange.core.export.models import CalendarEvent
from orange.exceptions import ExportError

logger = logging.getLogger(__name__)

# iOS Calendar database location
CALENDAR_DB_DOMAIN = "HomeDomain"
CALENDAR_DB_PATH = "Library/Calendar/Calendar.sqlitedb"


class CalendarExporter:
    """
    Exports calendar events from iOS backups.

    Parses the Calendar.sqlitedb database and exports events
    to JSON, CSV, or iCalendar (ICS) formats.

    Example:
        reader = BackupReader("/path/to/backup")
        exporter = CalendarExporter(reader)

        # Get all events
        events = exporter.get_events()

        # Export to iCalendar
        exporter.export_ics(events, Path("./calendar.ics"))
    """

    def __init__(self, backup_reader: BackupReader):
        """
        Initialize calendar exporter.

        Args:
            backup_reader: BackupReader instance for the backup.
        """
        self._reader = backup_reader
        self._db_path: Optional[Path] = None
        self._calendars: dict[int, str] = {}  # calendar_id -> name

    def _ensure_database(self) -> Path:
        """
        Extract and return path to Calendar database.

        Returns:
            Path to the extracted database file.

        Raises:
            ExportError: If database cannot be extracted.
        """
        if self._db_path and self._db_path.exists():
            return self._db_path

        db_path = self._reader.extract_database(
            CALENDAR_DB_DOMAIN, CALENDAR_DB_PATH
        )
        if not db_path:
            raise ExportError(
                f"Could not extract Calendar database from backup. "
                f"Make sure the backup contains "
                f"{CALENDAR_DB_DOMAIN}/{CALENDAR_DB_PATH}"
            )

        self._db_path = db_path
        self._load_calendars()
        return db_path

    def _load_calendars(self) -> None:
        """Load calendar names from database."""
        if not self._db_path:
            return

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT ROWID, title FROM Calendar")
            for row in cursor.fetchall():
                self._calendars[row[0]] = row[1]

            conn.close()
            logger.debug(f"Loaded {len(self._calendars)} calendars")

        except sqlite3.Error as e:
            logger.warning(f"Could not load calendars: {e}")

    def _parse_date(self, date_value: Optional[float]) -> Optional[datetime]:
        """Parse iOS timestamp to datetime."""
        if date_value is None:
            return None

        try:
            # Calendar uses seconds since Apple epoch
            unix_timestamp = date_value + APPLE_EPOCH_OFFSET
            return datetime.fromtimestamp(unix_timestamp)
        except (ValueError, OSError):
            return None

    def get_calendars(self) -> list[dict[str, Any]]:
        """
        Get list of calendars.

        Returns:
            List of dicts with calendar info.
        """
        self._ensure_database()
        calendars: list[dict[str, Any]] = []

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    c.ROWID as calendar_id,
                    c.title,
                    c.color,
                    c.type,
                    COUNT(ci.ROWID) as event_count
                FROM Calendar c
                LEFT JOIN CalendarItem ci ON c.ROWID = ci.calendar_id
                GROUP BY c.ROWID
                ORDER BY c.title
            """)

            for row in cursor.fetchall():
                calendars.append({
                    "calendar_id": row["calendar_id"],
                    "title": row["title"],
                    "color": row["color"],
                    "type": row["type"],
                    "event_count": row["event_count"],
                })

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not list calendars: {e}")

        return calendars

    def get_events(
        self,
        calendar_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[CalendarEvent]:
        """
        Get calendar events from the backup.

        Args:
            calendar_id: Filter by specific calendar.
            start_date: Filter events starting after this date.
            end_date: Filter events starting before this date.
            search: Search string for event title/location.
            limit: Maximum number of events to return.

        Returns:
            List of CalendarEvent objects.
        """
        self._ensure_database()
        events: list[CalendarEvent] = []

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query CalendarItem table
            query = """
                SELECT
                    ci.ROWID as event_id,
                    ci.summary,
                    ci.location,
                    ci.description,
                    ci.start_date,
                    ci.end_date,
                    ci.all_day,
                    ci.calendar_id,
                    ci.url,
                    ci.creation_date,
                    ci.last_modified
                FROM CalendarItem ci
                WHERE ci.summary IS NOT NULL
            """

            params: list[Any] = []

            if calendar_id is not None:
                query += " AND ci.calendar_id = ?"
                params.append(calendar_id)

            if start_date:
                apple_ts = start_date.timestamp() - APPLE_EPOCH_OFFSET
                query += " AND ci.start_date >= ?"
                params.append(apple_ts)

            if end_date:
                apple_ts = end_date.timestamp() - APPLE_EPOCH_OFFSET
                query += " AND ci.start_date <= ?"
                params.append(apple_ts)

            if search:
                query += " AND (ci.summary LIKE ? OR ci.location LIKE ?)"
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern])

            query += " ORDER BY ci.start_date ASC"

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, params)

            for row in cursor.fetchall():
                event = self._parse_event_row(row)
                if event:
                    events.append(event)

            conn.close()

        except sqlite3.Error as e:
            raise ExportError(f"Failed to read calendar events: {e}") from e

        return events

    def _parse_event_row(self, row: sqlite3.Row) -> Optional[CalendarEvent]:
        """Parse a database row into a CalendarEvent object."""
        try:
            start_date = self._parse_date(row["start_date"])
            if not start_date:
                return None

            calendar_name = self._calendars.get(row["calendar_id"])

            return CalendarEvent(
                event_id=row["event_id"],
                title=row["summary"],
                start_date=start_date,
                end_date=self._parse_date(row["end_date"]),
                location=row["location"],
                notes=row["description"],
                all_day=bool(row["all_day"]),
                calendar_name=calendar_name,
                calendar_id=row["calendar_id"],
                url=row["url"],
                created_date=self._parse_date(row["creation_date"]),
                modified_date=self._parse_date(row["last_modified"]),
            )

        except Exception as e:
            logger.debug(f"Failed to parse event row: {e}")
            return None

    def get_statistics(self) -> dict[str, Any]:
        """
        Get calendar statistics.

        Returns:
            Dict with statistics including total events,
            calendars, date range, etc.
        """
        self._ensure_database()
        stats: dict[str, Any] = {
            "total_events": 0,
            "total_calendars": len(self._calendars),
            "all_day_events": 0,
            "first_event": None,
            "last_event": None,
        }

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            # Total events
            cursor.execute(
                "SELECT COUNT(*) FROM CalendarItem WHERE summary IS NOT NULL"
            )
            stats["total_events"] = cursor.fetchone()[0]

            # All-day events
            cursor.execute(
                "SELECT COUNT(*) FROM CalendarItem WHERE all_day = 1"
            )
            stats["all_day_events"] = cursor.fetchone()[0]

            # Date range
            cursor.execute("""
                SELECT MIN(start_date), MAX(start_date)
                FROM CalendarItem WHERE summary IS NOT NULL
            """)
            row = cursor.fetchone()
            if row[0]:
                stats["first_event"] = self._parse_date(row[0])
            if row[1]:
                stats["last_event"] = self._parse_date(row[1])

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not get statistics: {e}")

        return stats

    def export_json(
        self,
        events: list[CalendarEvent],
        output_path: Path,
        pretty: bool = True,
    ) -> Path:
        """
        Export events to JSON format.

        Args:
            events: List of events to export.
            output_path: Path for output file.
            pretty: Whether to format with indentation.

        Returns:
            Path to the created file.
        """
        data = {
            "export_date": datetime.now().isoformat(),
            "event_count": len(events),
            "events": [e.to_dict() for e in events],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)

        logger.info(f"Exported {len(events)} events to {output_path}")
        return output_path

    def export_csv(
        self,
        events: list[CalendarEvent],
        output_path: Path,
    ) -> Path:
        """
        Export events to CSV format.

        Args:
            events: List of events to export.
            output_path: Path for output file.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                "Title",
                "Start Date",
                "End Date",
                "All Day",
                "Location",
                "Calendar",
                "Notes",
                "URL",
            ])

            # Write events
            for event in events:
                writer.writerow([
                    event.title,
                    event.start_date.isoformat(),
                    event.end_date.isoformat() if event.end_date else "",
                    "Yes" if event.all_day else "No",
                    event.location or "",
                    event.calendar_name or "",
                    event.notes or "",
                    event.url or "",
                ])

        logger.info(f"Exported {len(events)} events to {output_path}")
        return output_path

    def export_ics(
        self,
        events: list[CalendarEvent],
        output_path: Path,
        calendar_name: str = "iOS Export",
    ) -> Path:
        """
        Export events to iCalendar (ICS) format.

        Args:
            events: List of events to export.
            output_path: Path for output file.
            calendar_name: Name for the exported calendar.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ics_content = self._generate_ics(events, calendar_name)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ics_content)

        logger.info(f"Exported {len(events)} events to {output_path}")
        return output_path

    def _generate_ics(
        self, events: list[CalendarEvent], calendar_name: str
    ) -> str:
        """Generate iCalendar content."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//Orange//iOS Backup Export//EN",
            f"X-WR-CALNAME:{calendar_name}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        for event in events:
            lines.extend(self._event_to_vevent(event))

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    def _event_to_vevent(self, event: CalendarEvent) -> list[str]:
        """Convert a CalendarEvent to VEVENT lines."""
        lines = ["BEGIN:VEVENT"]

        # UID - use event_id
        lines.append(f"UID:orange-{event.event_id}@backup")

        # Timestamp
        dtstamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
        lines.append(f"DTSTAMP:{dtstamp}")

        # Start/end dates
        if event.all_day:
            # All-day events use DATE format
            dtstart = event.start_date.strftime("%Y%m%d")
            lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
            if event.end_date:
                dtend = event.end_date.strftime("%Y%m%d")
            else:
                # All-day events without end are single day
                dtend = (event.start_date + timedelta(days=1)).strftime("%Y%m%d")
            lines.append(f"DTEND;VALUE=DATE:{dtend}")
        else:
            # Regular events use DATETIME format
            dtstart = event.start_date.strftime("%Y%m%dT%H%M%S")
            lines.append(f"DTSTART:{dtstart}")
            if event.end_date:
                dtend = event.end_date.strftime("%Y%m%dT%H%M%S")
                lines.append(f"DTEND:{dtend}")

        # Summary (title)
        lines.append(f"SUMMARY:{self._escape_ics(event.title)}")

        # Location
        if event.location:
            lines.append(f"LOCATION:{self._escape_ics(event.location)}")

        # Description (notes)
        if event.notes:
            lines.append(f"DESCRIPTION:{self._escape_ics(event.notes)}")

        # URL
        if event.url:
            lines.append(f"URL:{event.url}")

        # Created/Modified dates
        if event.created_date:
            created = event.created_date.strftime("%Y%m%dT%H%M%SZ")
            lines.append(f"CREATED:{created}")

        if event.modified_date:
            modified = event.modified_date.strftime("%Y%m%dT%H%M%SZ")
            lines.append(f"LAST-MODIFIED:{modified}")

        lines.append("END:VEVENT")
        return lines

    def _escape_ics(self, text: str) -> str:
        """Escape special characters for iCalendar format."""
        return (
            text
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
        )
