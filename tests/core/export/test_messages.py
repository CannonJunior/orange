"""Tests for message exporter."""

import json
import pytest
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from orange.core.export.messages import MessageExporter, SMS_DB_DOMAIN, SMS_DB_PATH
from orange.core.export.models import Message, MessageDirection, MessageType
from orange.exceptions import ExportError


class TestMessageExporter:
    """Tests for MessageExporter class."""

    @pytest.fixture
    def mock_backup_reader(self) -> Mock:
        """Create a mock BackupReader."""
        return Mock()

    @pytest.fixture
    def sample_messages(self) -> list[Message]:
        """Create sample messages for testing."""
        return [
            Message(
                message_id=1,
                text="Hello!",
                date=datetime(2024, 1, 15, 10, 30),
                direction=MessageDirection.SENT,
                message_type=MessageType.IMESSAGE,
                sender="Me",
                recipient="+1234567890",
            ),
            Message(
                message_id=2,
                text="Hi there",
                date=datetime(2024, 1, 15, 10, 31),
                direction=MessageDirection.RECEIVED,
                message_type=MessageType.IMESSAGE,
                sender="+1234567890",
                recipient="Me",
            ),
            Message(
                message_id=3,
                text="How are you?",
                date=datetime(2024, 1, 15, 10, 32),
                direction=MessageDirection.SENT,
                message_type=MessageType.SMS,
                sender="Me",
                recipient="+1234567890",
            ),
        ]

    def test_init(self, mock_backup_reader: Mock) -> None:
        """MessageExporter should initialize with backup reader."""
        exporter = MessageExporter(mock_backup_reader)
        assert exporter._reader is mock_backup_reader
        assert exporter._db_path is None

    def test_ensure_database_not_found(self, mock_backup_reader: Mock) -> None:
        """_ensure_database should raise error if database not found."""
        mock_backup_reader.extract_database.return_value = None

        exporter = MessageExporter(mock_backup_reader)
        with pytest.raises(ExportError, match="Could not extract SMS database"):
            exporter._ensure_database()

        mock_backup_reader.extract_database.assert_called_once_with(
            SMS_DB_DOMAIN, SMS_DB_PATH
        )

    def test_parse_date_nanoseconds(self, mock_backup_reader: Mock) -> None:
        """_parse_date should handle nanosecond timestamps."""
        exporter = MessageExporter(mock_backup_reader)

        # Nanosecond timestamp (very large number)
        # This represents approximately 2024-01-15 10:30:00 in Apple time
        ns_timestamp = 727267800000000000  # nanoseconds since Apple epoch
        result = exporter._parse_date(ns_timestamp)

        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_date_seconds(self, mock_backup_reader: Mock) -> None:
        """_parse_date should handle second timestamps."""
        exporter = MessageExporter(mock_backup_reader)

        # Second timestamp (smaller number)
        sec_timestamp = 727267800  # seconds since Apple epoch
        result = exporter._parse_date(sec_timestamp)

        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_date_zero(self, mock_backup_reader: Mock) -> None:
        """_parse_date should return None for zero timestamp."""
        exporter = MessageExporter(mock_backup_reader)
        assert exporter._parse_date(0) is None
        assert exporter._parse_date(None) is None

    def test_get_message_type_imessage(self, mock_backup_reader: Mock) -> None:
        """_get_message_type should detect iMessage."""
        exporter = MessageExporter(mock_backup_reader)
        assert exporter._get_message_type("iMessage") == MessageType.IMESSAGE
        assert exporter._get_message_type("IMESSAGE") == MessageType.IMESSAGE

    def test_get_message_type_sms(self, mock_backup_reader: Mock) -> None:
        """_get_message_type should detect SMS."""
        exporter = MessageExporter(mock_backup_reader)
        assert exporter._get_message_type("SMS") == MessageType.SMS
        assert exporter._get_message_type("sms") == MessageType.SMS

    def test_get_message_type_mms(self, mock_backup_reader: Mock) -> None:
        """_get_message_type should detect MMS."""
        exporter = MessageExporter(mock_backup_reader)
        assert exporter._get_message_type("MMS") == MessageType.MMS

    def test_get_message_type_default(self, mock_backup_reader: Mock) -> None:
        """_get_message_type should default to SMS."""
        exporter = MessageExporter(mock_backup_reader)
        assert exporter._get_message_type(None) == MessageType.SMS
        assert exporter._get_message_type("unknown") == MessageType.SMS

    def test_export_json(
        self,
        mock_backup_reader: Mock,
        sample_messages: list[Message],
    ) -> None:
        """export_json should create valid JSON file."""
        exporter = MessageExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "messages.json"
            result = exporter.export_json(sample_messages, output_path)

            assert result == output_path
            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert "export_date" in data
            assert data["message_count"] == 3
            assert len(data["messages"]) == 3

    def test_export_json_pretty(
        self,
        mock_backup_reader: Mock,
        sample_messages: list[Message],
    ) -> None:
        """export_json should support pretty formatting."""
        exporter = MessageExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "messages.json"
            exporter.export_json(sample_messages, output_path, pretty=True)

            content = output_path.read_text()
            # Pretty format should have newlines
            assert "\n" in content

    def test_export_csv(
        self,
        mock_backup_reader: Mock,
        sample_messages: list[Message],
    ) -> None:
        """export_csv should create valid CSV file."""
        exporter = MessageExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "messages.csv"
            result = exporter.export_csv(sample_messages, output_path)

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()
            lines = content.strip().split("\n")

            # Header + 3 messages
            assert len(lines) == 4
            assert "Date" in lines[0]
            assert "Direction" in lines[0]

    def test_export_html(
        self,
        mock_backup_reader: Mock,
        sample_messages: list[Message],
    ) -> None:
        """export_html should create valid HTML file."""
        exporter = MessageExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "messages.html"
            result = exporter.export_html(
                sample_messages, output_path, title="Test Messages"
            )

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()
            assert "<!DOCTYPE html>" in content
            assert "Test Messages" in content
            assert "Hello!" in content

    def test_export_html_escapes_content(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_html should escape HTML in message content."""
        exporter = MessageExporter(mock_backup_reader)
        messages = [
            Message(
                message_id=1,
                text="<script>alert('xss')</script>",
                date=datetime.now(),
                direction=MessageDirection.SENT,
                message_type=MessageType.SMS,
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "messages.html"
            exporter.export_html(messages, output_path)

            content = output_path.read_text()
            # Script tags should be escaped
            assert "<script>" not in content
            assert "&lt;script&gt;" in content

    def test_export_empty_messages(self, mock_backup_reader: Mock) -> None:
        """Exporters should handle empty message list."""
        exporter = MessageExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "empty.json"
            exporter.export_json([], json_path)

            with open(json_path) as f:
                data = json.load(f)
            assert data["message_count"] == 0

    def test_export_creates_parent_dirs(
        self,
        mock_backup_reader: Mock,
        sample_messages: list[Message],
    ) -> None:
        """Export should create parent directories if needed."""
        exporter = MessageExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "nested" / "messages.json"
            exporter.export_json(sample_messages, output_path)

            assert output_path.exists()


class TestMessageExporterWithDatabase:
    """Tests that require a mock SMS database."""

    @pytest.fixture
    def mock_sms_db(self) -> Path:
        """Create a mock SMS database."""
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "sms.db"

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create tables matching iOS SMS schema
        cursor.execute("""
            CREATE TABLE handle (
                ROWID INTEGER PRIMARY KEY,
                id TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE chat (
                ROWID INTEGER PRIMARY KEY,
                chat_identifier TEXT,
                display_name TEXT,
                service_name TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE message (
                ROWID INTEGER PRIMARY KEY,
                text TEXT,
                date INTEGER,
                date_read INTEGER,
                date_delivered INTEGER,
                is_from_me INTEGER,
                is_read INTEGER,
                is_delivered INTEGER,
                service TEXT,
                subject TEXT,
                handle_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE chat_message_join (
                chat_id INTEGER,
                message_id INTEGER,
                message_date INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE attachment (
                ROWID INTEGER PRIMARY KEY,
                filename TEXT,
                mime_type TEXT,
                transfer_state INTEGER,
                total_bytes INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE message_attachment_join (
                message_id INTEGER,
                attachment_id INTEGER
            )
        """)

        # Insert test data
        cursor.execute("INSERT INTO handle VALUES (1, '+1234567890')")
        cursor.execute("INSERT INTO handle VALUES (2, 'test@example.com')")

        cursor.execute(
            "INSERT INTO chat VALUES (1, '+1234567890', 'Test Contact', 'iMessage')"
        )

        # Insert messages (using Apple epoch timestamp)
        cursor.execute("""
            INSERT INTO message VALUES
            (1, 'Hello world', 727267800000000000, NULL, NULL, 1, 1, 1, 'iMessage', NULL, 1)
        """)
        cursor.execute("""
            INSERT INTO message VALUES
            (2, 'Reply message', 727267860000000000, NULL, NULL, 0, 1, 1, 'iMessage', NULL, 1)
        """)

        cursor.execute("INSERT INTO chat_message_join VALUES (1, 1, 727267800000000000)")
        cursor.execute("INSERT INTO chat_message_join VALUES (1, 2, 727267860000000000)")

        conn.commit()
        conn.close()

        return db_path

    def test_get_messages_from_database(self, mock_sms_db: Path) -> None:
        """get_messages should read from database."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_sms_db

        exporter = MessageExporter(mock_reader)
        messages = exporter.get_messages()

        assert len(messages) == 2
        assert messages[0].text == "Hello world"
        assert messages[0].direction == MessageDirection.SENT
        assert messages[1].direction == MessageDirection.RECEIVED

    def test_get_conversations(self, mock_sms_db: Path) -> None:
        """get_conversations should list conversations."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_sms_db

        exporter = MessageExporter(mock_reader)
        conversations = exporter.get_conversations()

        assert len(conversations) == 1
        assert conversations[0]["identifier"] == "+1234567890"
        assert conversations[0]["message_count"] == 2

    def test_get_statistics(self, mock_sms_db: Path) -> None:
        """get_statistics should return correct counts."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_sms_db

        exporter = MessageExporter(mock_reader)
        stats = exporter.get_statistics()

        assert stats["total_messages"] == 2
        assert stats["sent_messages"] == 1
        assert stats["received_messages"] == 1
        assert stats["contacts"] == 2

    def test_get_messages_with_contact_filter(self, mock_sms_db: Path) -> None:
        """get_messages should filter by contact."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_sms_db

        exporter = MessageExporter(mock_reader)
        messages = exporter.get_messages(contact="+1234567890")

        assert len(messages) == 2  # Both messages are with this contact

    def test_get_messages_with_limit(self, mock_sms_db: Path) -> None:
        """get_messages should respect limit."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_sms_db

        exporter = MessageExporter(mock_reader)
        messages = exporter.get_messages(limit=1)

        assert len(messages) == 1
