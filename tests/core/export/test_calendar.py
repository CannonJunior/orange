"""Tests for calendar exporter."""

import json
import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from orange.core.export.calendar import CalendarExporter
from orange.core.export.models import CalendarEvent
from orange.exceptions import ExportError


class TestCalendarExporter:
    """Tests for CalendarExporter class."""

    @pytest.fixture
    def mock_backup_reader(self) -> Mock:
        """Create a mock BackupReader."""
        return Mock()

    @pytest.fixture
    def sample_events(self) -> list[CalendarEvent]:
        """Create sample events for testing."""
        return [
            CalendarEvent(
                event_id=1,
                title="Team Meeting",
                start_date=datetime(2024, 1, 15, 10, 0),
                end_date=datetime(2024, 1, 15, 11, 0),
                location="Conference Room A",
                calendar_name="Work",
            ),
            CalendarEvent(
                event_id=2,
                title="Lunch with John",
                start_date=datetime(2024, 1, 15, 12, 0),
                end_date=datetime(2024, 1, 15, 13, 0),
                calendar_name="Personal",
            ),
            CalendarEvent(
                event_id=3,
                title="Vacation",
                start_date=datetime(2024, 1, 20),
                end_date=datetime(2024, 1, 25),
                all_day=True,
                calendar_name="Personal",
            ),
        ]

    def test_init(self, mock_backup_reader: Mock) -> None:
        """CalendarExporter should initialize with backup reader."""
        exporter = CalendarExporter(mock_backup_reader)
        assert exporter._reader is mock_backup_reader
        assert exporter._db_path is None

    def test_ensure_database_not_found(self, mock_backup_reader: Mock) -> None:
        """_ensure_database should raise error if database not found."""
        mock_backup_reader.extract_database.return_value = None

        exporter = CalendarExporter(mock_backup_reader)
        with pytest.raises(ExportError, match="Could not extract Calendar"):
            exporter._ensure_database()

    def test_export_json(
        self,
        mock_backup_reader: Mock,
        sample_events: list[CalendarEvent],
    ) -> None:
        """export_json should create valid JSON file."""
        exporter = CalendarExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.json"
            result = exporter.export_json(sample_events, output_path)

            assert result == output_path
            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert "export_date" in data
            assert data["event_count"] == 3
            assert len(data["events"]) == 3

    def test_export_csv(
        self,
        mock_backup_reader: Mock,
        sample_events: list[CalendarEvent],
    ) -> None:
        """export_csv should create valid CSV file."""
        exporter = CalendarExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.csv"
            result = exporter.export_csv(sample_events, output_path)

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()
            lines = content.strip().split("\n")

            # Header + 3 events
            assert len(lines) == 4
            assert "Title" in lines[0]
            assert "Start Date" in lines[0]

    def test_export_ics(
        self,
        mock_backup_reader: Mock,
        sample_events: list[CalendarEvent],
    ) -> None:
        """export_ics should create valid iCalendar file."""
        exporter = CalendarExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.ics"
            result = exporter.export_ics(sample_events, output_path)

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()

            # Check iCalendar format
            assert "BEGIN:VCALENDAR" in content
            assert "END:VCALENDAR" in content
            assert "VERSION:2.0" in content

            # Should have 3 events
            assert content.count("BEGIN:VEVENT") == 3
            assert content.count("END:VEVENT") == 3

    def test_export_ics_event_content(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_ics should include event details."""
        exporter = CalendarExporter(mock_backup_reader)
        events = [
            CalendarEvent(
                event_id=1,
                title="Test Meeting",
                start_date=datetime(2024, 1, 15, 10, 0),
                end_date=datetime(2024, 1, 15, 11, 0),
                location="Room 101",
                notes="Bring laptop",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.ics"
            exporter.export_ics(events, output_path)

            content = output_path.read_text()

            assert "SUMMARY:Test Meeting" in content
            assert "LOCATION:Room 101" in content
            assert "DESCRIPTION:Bring laptop" in content
            assert "DTSTART:20240115T100000" in content
            assert "DTEND:20240115T110000" in content

    def test_export_ics_all_day_event(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_ics should format all-day events correctly."""
        exporter = CalendarExporter(mock_backup_reader)
        events = [
            CalendarEvent(
                event_id=1,
                title="Holiday",
                start_date=datetime(2024, 1, 15),
                end_date=datetime(2024, 1, 16),
                all_day=True,
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.ics"
            exporter.export_ics(events, output_path)

            content = output_path.read_text()

            # All-day events use DATE format without time
            assert "DTSTART;VALUE=DATE:20240115" in content
            assert "DTEND;VALUE=DATE:20240116" in content

    def test_export_ics_escapes_special_chars(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_ics should escape special characters."""
        exporter = CalendarExporter(mock_backup_reader)
        events = [
            CalendarEvent(
                event_id=1,
                title="Meeting; Important",
                start_date=datetime(2024, 1, 15, 10, 0),
                notes="Agenda:\nItem 1, Item 2",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.ics"
            exporter.export_ics(events, output_path)

            content = output_path.read_text()

            # Special chars should be escaped
            assert "Meeting\\; Important" in content
            assert "\\n" in content
            assert "Item 1\\, Item 2" in content

    def test_export_ics_with_url(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_ics should include URL if present."""
        exporter = CalendarExporter(mock_backup_reader)
        events = [
            CalendarEvent(
                event_id=1,
                title="Webinar",
                start_date=datetime(2024, 1, 15, 10, 0),
                url="https://example.com/meeting",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.ics"
            exporter.export_ics(events, output_path)

            content = output_path.read_text()
            assert "URL:https://example.com/meeting" in content

    def test_export_ics_calendar_name(
        self,
        mock_backup_reader: Mock,
        sample_events: list[CalendarEvent],
    ) -> None:
        """export_ics should set calendar name."""
        exporter = CalendarExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calendar.ics"
            exporter.export_ics(
                sample_events, output_path, calendar_name="My Calendar"
            )

            content = output_path.read_text()
            assert "X-WR-CALNAME:My Calendar" in content

    def test_export_empty_events(self, mock_backup_reader: Mock) -> None:
        """Exporters should handle empty event list."""
        exporter = CalendarExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "empty.json"
            exporter.export_json([], json_path)

            with open(json_path) as f:
                data = json.load(f)
            assert data["event_count"] == 0


class TestCalendarExporterWithDatabase:
    """Tests that require a mock Calendar database."""

    @pytest.fixture
    def mock_calendar_db(self) -> Path:
        """Create a mock Calendar database."""
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "Calendar.sqlitedb"

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create tables matching iOS Calendar schema
        cursor.execute("""
            CREATE TABLE Calendar (
                ROWID INTEGER PRIMARY KEY,
                title TEXT,
                color TEXT,
                type INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE CalendarItem (
                ROWID INTEGER PRIMARY KEY,
                summary TEXT,
                location TEXT,
                description TEXT,
                start_date REAL,
                end_date REAL,
                all_day INTEGER,
                calendar_id INTEGER,
                url TEXT,
                creation_date REAL,
                last_modified REAL
            )
        """)

        # Insert test data
        cursor.execute("INSERT INTO Calendar VALUES (1, 'Work', '#FF0000', 0)")
        cursor.execute("INSERT INTO Calendar VALUES (2, 'Personal', '#00FF00', 0)")

        # Apple epoch timestamp for 2024-01-15 10:00 = 727261200
        cursor.execute("""
            INSERT INTO CalendarItem VALUES
            (1, 'Team Meeting', 'Conference Room', 'Weekly sync', 727261200, 727264800, 0, 1, NULL, 727261200, 727261200)
        """)
        cursor.execute("""
            INSERT INTO CalendarItem VALUES
            (2, 'Lunch Break', NULL, NULL, 727268400, 727272000, 0, 2, NULL, 727261200, 727261200)
        """)

        conn.commit()
        conn.close()

        return db_path

    def test_get_events_from_database(self, mock_calendar_db: Path) -> None:
        """get_events should read from database."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_calendar_db

        exporter = CalendarExporter(mock_reader)
        events = exporter.get_events()

        assert len(events) == 2
        assert events[0].title == "Team Meeting"
        assert events[0].location == "Conference Room"

    def test_get_calendars(self, mock_calendar_db: Path) -> None:
        """get_calendars should list calendars."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_calendar_db

        exporter = CalendarExporter(mock_reader)
        calendars = exporter.get_calendars()

        assert len(calendars) == 2
        titles = [c["title"] for c in calendars]
        assert "Work" in titles
        assert "Personal" in titles

    def test_get_events_by_calendar(self, mock_calendar_db: Path) -> None:
        """get_events should filter by calendar_id."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_calendar_db

        exporter = CalendarExporter(mock_reader)
        events = exporter.get_events(calendar_id=1)

        assert len(events) == 1
        assert events[0].title == "Team Meeting"

    def test_get_events_with_search(self, mock_calendar_db: Path) -> None:
        """get_events should filter by search term."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_calendar_db

        exporter = CalendarExporter(mock_reader)
        events = exporter.get_events(search="Meeting")

        assert len(events) == 1
        assert events[0].title == "Team Meeting"

    def test_get_events_with_limit(self, mock_calendar_db: Path) -> None:
        """get_events should respect limit."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_calendar_db

        exporter = CalendarExporter(mock_reader)
        events = exporter.get_events(limit=1)

        assert len(events) == 1

    def test_get_statistics(self, mock_calendar_db: Path) -> None:
        """get_statistics should return correct counts."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_calendar_db

        exporter = CalendarExporter(mock_reader)
        stats = exporter.get_statistics()

        assert stats["total_events"] == 2
        assert stats["total_calendars"] == 2
