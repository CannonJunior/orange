"""Tests for contact exporter."""

import json
import pytest
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from orange.core.export.contacts import ContactExporter
from orange.core.export.models import Contact, ContactPhone, ContactEmail, ContactAddress
from orange.exceptions import ExportError


class TestContactExporter:
    """Tests for ContactExporter class."""

    @pytest.fixture
    def mock_backup_reader(self) -> Mock:
        """Create a mock BackupReader."""
        return Mock()

    @pytest.fixture
    def sample_contacts(self) -> list[Contact]:
        """Create sample contacts for testing."""
        return [
            Contact(
                contact_id=1,
                first_name="John",
                last_name="Doe",
                phones=[ContactPhone("+1234567890", "mobile")],
                emails=[ContactEmail("john@example.com", "home")],
            ),
            Contact(
                contact_id=2,
                first_name="Jane",
                last_name="Smith",
                organization="Acme Corp",
                job_title="Engineer",
                phones=[
                    ContactPhone("+1987654321", "mobile"),
                    ContactPhone("+1555555555", "work"),
                ],
            ),
            Contact(
                contact_id=3,
                first_name="Bob",
                last_name="Wilson",
                addresses=[
                    ContactAddress(
                        street="123 Main St",
                        city="San Francisco",
                        state="CA",
                        postal_code="94105",
                    )
                ],
            ),
        ]

    def test_init(self, mock_backup_reader: Mock) -> None:
        """ContactExporter should initialize with backup reader."""
        exporter = ContactExporter(mock_backup_reader)
        assert exporter._reader is mock_backup_reader
        assert exporter._db_path is None

    def test_ensure_database_not_found(self, mock_backup_reader: Mock) -> None:
        """_ensure_database should raise error if database not found."""
        mock_backup_reader.extract_database.return_value = None

        exporter = ContactExporter(mock_backup_reader)
        with pytest.raises(ExportError, match="Could not extract AddressBook"):
            exporter._ensure_database()

    def test_clean_label(self, mock_backup_reader: Mock) -> None:
        """_clean_label should clean iOS label format."""
        exporter = ContactExporter(mock_backup_reader)

        assert exporter._clean_label("_$!<Mobile>!$_") == "mobile"
        assert exporter._clean_label("_$!<Home>!$_") == "home"
        assert exporter._clean_label("work") == "work"
        assert exporter._clean_label(None) == "other"

    def test_export_json(
        self,
        mock_backup_reader: Mock,
        sample_contacts: list[Contact],
    ) -> None:
        """export_json should create valid JSON file."""
        exporter = ContactExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.json"
            result = exporter.export_json(sample_contacts, output_path)

            assert result == output_path
            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert "export_date" in data
            assert data["contact_count"] == 3
            assert len(data["contacts"]) == 3

    def test_export_csv(
        self,
        mock_backup_reader: Mock,
        sample_contacts: list[Contact],
    ) -> None:
        """export_csv should create valid CSV file."""
        exporter = ContactExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.csv"
            result = exporter.export_csv(sample_contacts, output_path)

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()
            lines = content.strip().split("\n")

            # Header + 3 contacts
            assert len(lines) == 4
            assert "First Name" in lines[0]
            assert "Last Name" in lines[0]

    def test_export_vcf(
        self,
        mock_backup_reader: Mock,
        sample_contacts: list[Contact],
    ) -> None:
        """export_vcf should create valid vCard file."""
        exporter = ContactExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.vcf"
            result = exporter.export_vcf(sample_contacts, output_path)

            assert result == output_path
            assert output_path.exists()

            content = output_path.read_text()

            # Should have 3 vCards
            assert content.count("BEGIN:VCARD") == 3
            assert content.count("END:VCARD") == 3

            # Check vCard format
            assert "VERSION:3.0" in content
            assert "FN:John Doe" in content

    def test_export_vcf_with_phone(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_vcf should include phone numbers."""
        exporter = ContactExporter(mock_backup_reader)
        contacts = [
            Contact(
                contact_id=1,
                first_name="John",
                phones=[ContactPhone("+1234567890", "mobile")],
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.vcf"
            exporter.export_vcf(contacts, output_path)

            content = output_path.read_text()
            assert "TEL;TYPE=CELL:+1234567890" in content

    def test_export_vcf_with_email(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_vcf should include email addresses."""
        exporter = ContactExporter(mock_backup_reader)
        contacts = [
            Contact(
                contact_id=1,
                first_name="John",
                emails=[ContactEmail("john@example.com", "home")],
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.vcf"
            exporter.export_vcf(contacts, output_path)

            content = output_path.read_text()
            assert "EMAIL;TYPE=HOME:john@example.com" in content

    def test_export_vcf_with_address(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_vcf should include addresses."""
        exporter = ContactExporter(mock_backup_reader)
        contacts = [
            Contact(
                contact_id=1,
                first_name="John",
                addresses=[
                    ContactAddress(
                        street="123 Main St",
                        city="San Francisco",
                        state="CA",
                    )
                ],
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.vcf"
            exporter.export_vcf(contacts, output_path)

            content = output_path.read_text()
            assert "ADR;TYPE=HOME:" in content
            assert "123 Main St" in content
            assert "San Francisco" in content

    def test_export_vcf_with_organization(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_vcf should include organization."""
        exporter = ContactExporter(mock_backup_reader)
        contacts = [
            Contact(
                contact_id=1,
                first_name="John",
                organization="Acme Corp",
                department="Engineering",
                job_title="Developer",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.vcf"
            exporter.export_vcf(contacts, output_path)

            content = output_path.read_text()
            assert "ORG:Acme Corp;Engineering" in content
            assert "TITLE:Developer" in content

    def test_export_vcf_with_birthday(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_vcf should include birthday."""
        exporter = ContactExporter(mock_backup_reader)
        contacts = [
            Contact(
                contact_id=1,
                first_name="John",
                birthday=datetime(1990, 5, 15),
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.vcf"
            exporter.export_vcf(contacts, output_path)

            content = output_path.read_text()
            assert "BDAY:1990-05-15" in content

    def test_export_vcf_escapes_special_chars(
        self,
        mock_backup_reader: Mock,
    ) -> None:
        """export_vcf should escape special characters in notes."""
        exporter = ContactExporter(mock_backup_reader)
        contacts = [
            Contact(
                contact_id=1,
                first_name="John",
                notes="Line 1\nLine 2, with comma",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "contacts.vcf"
            exporter.export_vcf(contacts, output_path)

            content = output_path.read_text()
            # Newlines should be escaped
            assert "\\n" in content
            # Commas should be escaped
            assert "\\," in content

    def test_vcard_phone_type_mapping(self, mock_backup_reader: Mock) -> None:
        """_vcard_phone_type should map labels correctly."""
        exporter = ContactExporter(mock_backup_reader)

        assert exporter._vcard_phone_type("mobile") == "CELL"
        assert exporter._vcard_phone_type("home") == "HOME"
        assert exporter._vcard_phone_type("work") == "WORK"
        assert exporter._vcard_phone_type("fax") == "FAX"
        assert exporter._vcard_phone_type("pager") == "PAGER"
        assert exporter._vcard_phone_type("other") == "VOICE"

    def test_export_empty_contacts(self, mock_backup_reader: Mock) -> None:
        """Exporters should handle empty contact list."""
        exporter = ContactExporter(mock_backup_reader)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "empty.json"
            exporter.export_json([], json_path)

            with open(json_path) as f:
                data = json.load(f)
            assert data["contact_count"] == 0


class TestContactExporterWithDatabase:
    """Tests that require a mock AddressBook database."""

    @pytest.fixture
    def mock_addressbook_db(self) -> Path:
        """Create a mock AddressBook database."""
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "AddressBook.sqlitedb"

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create tables matching iOS AddressBook schema
        cursor.execute("""
            CREATE TABLE ABPerson (
                ROWID INTEGER PRIMARY KEY,
                First TEXT,
                Last TEXT,
                Middle TEXT,
                Prefix TEXT,
                Suffix TEXT,
                Nickname TEXT,
                Organization TEXT,
                Department TEXT,
                JobTitle TEXT,
                Birthday REAL,
                Note TEXT,
                CreationDate REAL,
                ModificationDate REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE ABMultiValue (
                UID INTEGER PRIMARY KEY,
                record_id INTEGER,
                property INTEGER,
                label INTEGER,
                value TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE ABMultiValueLabel (
                ROWID INTEGER PRIMARY KEY,
                value TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE ABMultiValueEntry (
                UID INTEGER PRIMARY KEY,
                parent_id INTEGER,
                key TEXT,
                value TEXT
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO ABPerson VALUES
            (1, 'John', 'Doe', NULL, NULL, NULL, NULL, 'Acme Corp', NULL, 'Developer', NULL, 'Test note', 727267800, 727267800)
        """)
        cursor.execute("""
            INSERT INTO ABPerson VALUES
            (2, 'Jane', 'Smith', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 727267800, 727267800)
        """)

        # Add phone number (property=3 is phone)
        cursor.execute("INSERT INTO ABMultiValue VALUES (1, 1, 3, -1, '+1234567890')")
        # Add email (property=4 is email)
        cursor.execute("INSERT INTO ABMultiValue VALUES (2, 1, 4, -2, 'john@example.com')")

        conn.commit()
        conn.close()

        return db_path

    def test_get_contacts_from_database(self, mock_addressbook_db: Path) -> None:
        """get_contacts should read from database."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_addressbook_db

        exporter = ContactExporter(mock_reader)
        contacts = exporter.get_contacts()

        assert len(contacts) == 2
        assert contacts[0].first_name == "John"
        assert contacts[0].last_name == "Doe"

    def test_get_contacts_with_search(self, mock_addressbook_db: Path) -> None:
        """get_contacts should filter by search term."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_addressbook_db

        exporter = ContactExporter(mock_reader)
        contacts = exporter.get_contacts(search="John")

        assert len(contacts) == 1
        assert contacts[0].first_name == "John"

    def test_get_contacts_with_limit(self, mock_addressbook_db: Path) -> None:
        """get_contacts should respect limit."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_addressbook_db

        exporter = ContactExporter(mock_reader)
        contacts = exporter.get_contacts(limit=1)

        assert len(contacts) == 1

    def test_get_statistics(self, mock_addressbook_db: Path) -> None:
        """get_statistics should return correct counts."""
        mock_reader = Mock()
        mock_reader.extract_database.return_value = mock_addressbook_db

        exporter = ContactExporter(mock_reader)
        stats = exporter.get_statistics()

        assert stats["total_contacts"] == 2
        assert stats["with_phones"] == 1
        assert stats["with_emails"] == 1
