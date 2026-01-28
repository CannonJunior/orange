"""Tests for notes exporter."""

import json
import pytest
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from orange.core.export.notes import NoteExporter
from orange.core.export.models import Note
from orange.exceptions import ExportError


class TestNoteExporter:
    """Tests for NoteExporter class."""

    @pytest.fixture
    def mock_backup_reader(self) -> Mock:
        """Create a mock BackupReader."""
        return Mock()

    @pytest.fixture
    def sample_notes(self) -> list[Note]:
        """Create sample notes for testing."""
        return [
            Note(
                note_id=1,
                title="Shopping List",
                content="- Milk\n- Bread\n- Eggs",
                folder_name="Personal",
                created_date=datetime(2024, 1, 15, 10, 0),
                modified_date=datetime(2024, 1, 15, 10, 30),
            ),
            Note(
                note_id=2,
                title="Meeting Notes",
                content="Discussed Q1 goals.\nAction items: Review budget.",
                folder_name="Work",
                is_pinned=True,
                created_date=datetime(2024, 1, 14, 9, 0),
            ),
            Note(
                note_id=3,
                title="Private Note",
                content="[This note is locked]",
                is_locked=True,
            ),
        ]

    def test_init(self, mock_backup_reader: Mock) -> None:
        """NoteExporter should initialize with backup reader."""
        exporter = NoteExporter(mock_backup_reader)
        assert exporter._reader is mock_backup_reader
        assert exporter._db_path is None

    def test_ensure_database_not_found(self, mock_backup_reader: Mock) -> None:
        """_ensure_database should raise error if database not found."""
        mock_backup_reader.extract_database.return_value = None

        exporter = NoteExporter(mock_backup_reader)
        with pytest.raises(ExportError, match="Could not extract Notes"):
            exporter._ensure_database()

    def test_export_json(
        self,
        mock_backup_reader: Mock,
        sample_notes: list[Note],
    ) -> None:
        """export_json should create valid JSON file."""
        exporter = NoteExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes.json"
            result = exporter.export_json(sample_notes, output_path)

            assert result == output_path
            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert "export_date" in data
            assert data["note_count"] == 3
            assert len(data["notes"]) == 3

    def test_export_csv(
        self,
        mock_backup_reader: Mock,
        sample_notes: list[Note],
    ) -> None:
        """export_csv should create valid CSV file."""
        exporter = NoteExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes.csv"
            result = exporter.export_csv(sample_notes, output_path)

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()
            # Check header exists
            assert "Title" in content
            assert "Content" in content
            assert "Folder" in content
            # Check notes were written
            assert "Shopping List" in content
            assert "Meeting Notes" in content

    def test_export_csv_truncates_long_content(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_csv should truncate very long content."""
        exporter = NoteExporter(mock_backup_reader)
        notes = [
            Note(
                note_id=1,
                title="Long Note",
                content="x" * 2000,  # Very long content
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes.csv"
            exporter.export_csv(notes, output_path)

            content = output_path.read_text()
            # Content should be truncated with ellipsis
            assert "..." in content

    def test_export_html(
        self,
        mock_backup_reader: Mock,
        sample_notes: list[Note],
    ) -> None:
        """export_html should create valid HTML file."""
        exporter = NoteExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes.html"
            result = exporter.export_html(sample_notes, output_path)

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()

            assert "<!DOCTYPE html>" in content
            assert "Notes Export" in content
            assert "Shopping List" in content

    def test_export_html_custom_title(
        self,
        mock_backup_reader: Mock,
        sample_notes: list[Note],
    ) -> None:
        """export_html should use custom title."""
        exporter = NoteExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes.html"
            exporter.export_html(sample_notes, output_path, title="My Notes")

            content = output_path.read_text()
            assert "My Notes" in content

    def test_export_html_shows_badges(
        self,
        mock_backup_reader: Mock,
        sample_notes: list[Note],
    ) -> None:
        """export_html should show pinned/locked badges."""
        exporter = NoteExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes.html"
            exporter.export_html(sample_notes, output_path)

            content = output_path.read_text()
            assert "Pinned" in content
            assert "Locked" in content

    def test_export_html_escapes_content(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_html should escape HTML in content."""
        exporter = NoteExporter(mock_backup_reader)
        notes = [
            Note(
                note_id=1,
                title="Test",
                content="<script>alert('xss')</script>",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes.html"
            exporter.export_html(notes, output_path)

            content = output_path.read_text()
            # Script tags should be escaped
            assert "<script>" not in content
            assert "&lt;script&gt;" in content

    def test_export_empty_notes(self, mock_backup_reader: Mock) -> None:
        """Exporters should handle empty note list."""
        exporter = NoteExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "empty.json"
            exporter.export_json([], json_path)

            with open(json_path) as f:
                data = json.load(f)
            assert data["note_count"] == 0

    def test_extract_text_from_bytes(self, mock_backup_reader: Mock) -> None:
        """_extract_text_from_bytes should extract readable text."""
        exporter = NoteExporter(mock_backup_reader)

        # Simple UTF-8 text
        result = exporter._extract_text_from_bytes(b"Hello world")
        assert result == "Hello world"

        # Text with control characters
        result = exporter._extract_text_from_bytes(b"Hello\x00\x01world")
        assert "Hello" in result
        assert "world" in result

    def test_extract_text_cleans_whitespace(self, mock_backup_reader: Mock) -> None:
        """_extract_text_from_bytes should clean excessive whitespace."""
        exporter = NoteExporter(mock_backup_reader)

        # Multiple newlines should be reduced
        result = exporter._extract_text_from_bytes(b"Line1\n\n\n\n\nLine2")
        assert result == "Line1\n\nLine2"


class TestNoteExporterWithDatabase:
    """Tests that require a mock Notes database."""

    @pytest.fixture
    def mock_notes_db_ios9(self) -> Path:
        """Create a mock iOS 9+ Notes database."""
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "notes.sqlite"

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create iOS 9+ Core Data schema
        cursor.execute("""
            CREATE TABLE ZICCLOUDSYNCINGOBJECT (
                Z_PK INTEGER PRIMARY KEY,
                ZTITLE TEXT,
                ZSNIPPET TEXT,
                ZCREATIONDATE REAL,
                ZMODIFICATIONDATE REAL,
                ZFOLDER INTEGER,
                ZACCOUNT INTEGER,
                ZISPINNED INTEGER,
                ZISPASSWORDPROTECTED INTEGER,
                ZNOTEDATA INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE ZICNOTEDATA (
                Z_PK INTEGER PRIMARY KEY,
                ZDATA BLOB
            )
        """)

        # Insert test data (Apple epoch for 2024-01-15 = 727261200)
        cursor.execute("""
            INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES
            (1, 'Shopping List', 'Milk, Bread, Eggs', 727261200, 727264800, NULL, NULL, 0, 0, 1)
        """)
        cursor.execute("""
            INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES
            (2, 'Meeting Notes', 'Q1 Goals', 727261200, 727261200, NULL, NULL, 1, 0, 2)
        """)
        cursor.execute("""
            INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES
            (3, 'Secret Note', 'Locked content', 727261200, 727261200, NULL, NULL, 0, 1, 3)
        """)

        # Insert note data (simplified - just text bytes)
        cursor.execute(
            "INSERT INTO ZICNOTEDATA VALUES (1, ?)",
            (b"Full content: Milk, Bread, Eggs",)
        )
        cursor.execute(
            "INSERT INTO ZICNOTEDATA VALUES (2, ?)",
            (b"Q1 Goals discussion notes",)
        )
        cursor.execute(
            "INSERT INTO ZICNOTEDATA VALUES (3, ?)",
            (b"This is a locked note",)
        )

        conn.commit()
        conn.close()

        return db_path

    @pytest.fixture
    def mock_notes_db_legacy(self) -> Path:
        """Create a mock legacy Notes database."""
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "notes.sqlite"

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create legacy schema
        cursor.execute("""
            CREATE TABLE note (
                ROWID INTEGER PRIMARY KEY,
                title TEXT,
                creation_date REAL,
                modification_date REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE note_body (
                note_id INTEGER PRIMARY KEY,
                content TEXT
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO note VALUES (1, 'Old Note', 727261200, 727261200)
        """)
        cursor.execute("""
            INSERT INTO note_body VALUES (1, 'Legacy note content')
        """)

        conn.commit()
        conn.close()

        return db_path

    def test_get_notes_ios9(self, mock_notes_db_ios9: Path) -> None:
        """get_notes should read from iOS 9+ database."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_ios9

        exporter = NoteExporter(mock_reader)
        notes = exporter.get_notes()

        assert len(notes) == 3
        titles = [n.title for n in notes]
        assert "Shopping List" in titles
        assert "Meeting Notes" in titles

    def test_get_notes_detects_pinned(self, mock_notes_db_ios9: Path) -> None:
        """get_notes should detect pinned notes."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_ios9

        exporter = NoteExporter(mock_reader)
        notes = exporter.get_notes()

        pinned_notes = [n for n in notes if n.is_pinned]
        assert len(pinned_notes) == 1
        assert pinned_notes[0].title == "Meeting Notes"

    def test_get_notes_detects_locked(self, mock_notes_db_ios9: Path) -> None:
        """get_notes should detect locked notes."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_ios9

        exporter = NoteExporter(mock_reader)
        notes = exporter.get_notes()

        locked_notes = [n for n in notes if n.is_locked]
        assert len(locked_notes) == 1
        assert locked_notes[0].title == "Secret Note"

    def test_get_notes_with_search(self, mock_notes_db_ios9: Path) -> None:
        """get_notes should filter by search term."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_ios9

        exporter = NoteExporter(mock_reader)
        notes = exporter.get_notes(search="Shopping")

        assert len(notes) == 1
        assert notes[0].title == "Shopping List"

    def test_get_notes_with_limit(self, mock_notes_db_ios9: Path) -> None:
        """get_notes should respect limit."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_ios9

        exporter = NoteExporter(mock_reader)
        notes = exporter.get_notes(limit=1)

        assert len(notes) == 1

    def test_get_notes_legacy(self, mock_notes_db_legacy: Path) -> None:
        """get_notes should read from legacy database."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_legacy

        exporter = NoteExporter(mock_reader)
        notes = exporter.get_notes()

        assert len(notes) == 1
        assert notes[0].title == "Old Note"
        assert notes[0].content == "Legacy note content"

    def test_get_statistics(self, mock_notes_db_ios9: Path) -> None:
        """get_statistics should return correct counts."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_ios9

        exporter = NoteExporter(mock_reader)
        stats = exporter.get_statistics()

        assert stats["total_notes"] == 3
        assert stats["pinned_notes"] == 1
        assert stats["locked_notes"] == 1

    def test_detect_schema_ios9(self, mock_notes_db_ios9: Path) -> None:
        """_detect_schema should detect iOS 9+ schema."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_ios9

        exporter = NoteExporter(mock_reader)
        exporter._ensure_database()

        conn = sqlite3.connect(str(exporter._db_path))
        schema = exporter._detect_schema(conn)
        conn.close()

        assert schema == "ios9plus"

    def test_detect_schema_legacy(self, mock_notes_db_legacy: Path) -> None:
        """_detect_schema should detect legacy schema."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_notes_db_legacy

        exporter = NoteExporter(mock_reader)
        exporter._ensure_database()

        conn = sqlite3.connect(str(exporter._db_path))
        schema = exporter._detect_schema(conn)
        conn.close()

        assert schema == "legacy"
