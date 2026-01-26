"""Tests for backup reader."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
import plistlib
import sqlite3
import tempfile

from orange.core.backup.reader import BackupReader
from orange.core.backup.models import BackupFile
from orange.exceptions import BackupError


class TestBackupReader:
    """Tests for BackupReader class."""

    @pytest.fixture
    def mock_backup(self, tmp_path: Path) -> Path:
        """Create a mock backup directory structure."""
        backup_dir = tmp_path / "mock-backup"
        backup_dir.mkdir()

        # Create Info.plist
        info_plist = backup_dir / "Info.plist"
        info_data = {
            "Device Name": "Test iPhone",
            "Target Identifier": "mock-udid",
            "Product Version": "17.0",
            "Build Version": "21A329",
            "Last Backup Date": datetime.now(),
        }
        with open(info_plist, "wb") as f:
            plistlib.dump(info_data, f)

        # Create Manifest.plist
        manifest_plist = backup_dir / "Manifest.plist"
        manifest_data = {"IsEncrypted": False}
        with open(manifest_plist, "wb") as f:
            plistlib.dump(manifest_data, f)

        # Create Manifest.db
        manifest_db = backup_dir / "Manifest.db"
        conn = sqlite3.connect(str(manifest_db))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE Files (
                fileID TEXT PRIMARY KEY,
                domain TEXT,
                relativePath TEXT,
                flags INTEGER,
                file BLOB
            )
        """)

        # Insert test files
        test_files = [
            ("abc123", "HomeDomain", "Library/SMS/sms.db"),
            ("def456", "HomeDomain", "Library/Preferences/test.plist"),
            ("ghi789", "CameraRollDomain", "Media/DCIM/100APPLE/IMG_001.HEIC"),
        ]
        for file_id, domain, path in test_files:
            cursor.execute(
                "INSERT INTO Files (fileID, domain, relativePath, flags, file) VALUES (?, ?, ?, ?, ?)",
                (file_id, domain, path, 0, None),
            )

        conn.commit()
        conn.close()

        return backup_dir

    def test_init_valid_backup(self, mock_backup: Path) -> None:
        """Reader should initialize with valid backup."""
        reader = BackupReader(mock_backup)
        assert reader.path == mock_backup
        assert reader.is_encrypted is False

    def test_init_nonexistent_backup(self, tmp_path: Path) -> None:
        """Reader should raise for nonexistent backup."""
        with pytest.raises(BackupError):
            BackupReader(tmp_path / "nonexistent")

    def test_init_invalid_backup(self, tmp_path: Path) -> None:
        """Reader should raise for backup without Manifest.plist."""
        backup_dir = tmp_path / "invalid"
        backup_dir.mkdir()

        with pytest.raises(BackupError):
            BackupReader(backup_dir)

    def test_list_domains(self, mock_backup: Path) -> None:
        """list_domains should return all domains."""
        reader = BackupReader(mock_backup)
        domains = reader.list_domains()

        assert "HomeDomain" in domains
        assert "CameraRollDomain" in domains
        assert len(domains) == 2

    def test_list_files_all(self, mock_backup: Path) -> None:
        """list_files should return all files."""
        reader = BackupReader(mock_backup)
        files = reader.list_files()

        assert len(files) == 3
        file_ids = [f.file_id for f in files]
        assert "abc123" in file_ids
        assert "def456" in file_ids
        assert "ghi789" in file_ids

    def test_list_files_by_domain(self, mock_backup: Path) -> None:
        """list_files should filter by domain."""
        reader = BackupReader(mock_backup)
        files = reader.list_files(domain="HomeDomain")

        assert len(files) == 2
        for f in files:
            assert f.domain == "HomeDomain"

    def test_list_files_by_path_filter(self, mock_backup: Path) -> None:
        """list_files should filter by path."""
        reader = BackupReader(mock_backup)
        files = reader.list_files(path_filter="sms.db")

        assert len(files) == 1
        assert files[0].relative_path == "Library/SMS/sms.db"

    def test_get_file(self, mock_backup: Path) -> None:
        """get_file should return specific file by ID."""
        reader = BackupReader(mock_backup)
        file_info = reader.get_file("abc123")

        assert file_info is not None
        assert file_info.file_id == "abc123"
        assert file_info.domain == "HomeDomain"

    def test_get_file_not_found(self, mock_backup: Path) -> None:
        """get_file should return None for unknown file."""
        reader = BackupReader(mock_backup)
        file_info = reader.get_file("nonexistent")

        assert file_info is None

    def test_extract_file(self, mock_backup: Path, tmp_path: Path) -> None:
        """extract_file should copy file to destination."""
        # Create the actual file in backup
        file_dir = mock_backup / "ab"
        file_dir.mkdir()
        (file_dir / "abc123").write_text("test content")

        reader = BackupReader(mock_backup)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extracted = reader.extract_file("abc123", output_dir)

        assert extracted is not None
        assert extracted.exists()

    def test_extract_file_not_found(self, mock_backup: Path, tmp_path: Path) -> None:
        """extract_file should return None if file doesn't exist."""
        reader = BackupReader(mock_backup)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # File ID exists in manifest but not on disk
        extracted = reader.extract_file("abc123", output_dir)

        assert extracted is None

    def test_iter_files(self, mock_backup: Path) -> None:
        """iter_files should yield all files."""
        reader = BackupReader(mock_backup)
        files = list(reader.iter_files())

        assert len(files) == 3

    def test_iter_files_by_domain(self, mock_backup: Path) -> None:
        """iter_files should filter by domain."""
        reader = BackupReader(mock_backup)
        files = list(reader.iter_files(domain="CameraRollDomain"))

        assert len(files) == 1
        assert files[0].domain == "CameraRollDomain"

    def test_encrypted_backup_detection(self, tmp_path: Path) -> None:
        """Reader should detect encrypted backups."""
        backup_dir = tmp_path / "encrypted-backup"
        backup_dir.mkdir()

        # Create Manifest.plist with encryption
        manifest_plist = backup_dir / "Manifest.plist"
        manifest_data = {"IsEncrypted": True}
        with open(manifest_plist, "wb") as f:
            plistlib.dump(manifest_data, f)

        # Create Manifest.db
        manifest_db = backup_dir / "Manifest.db"
        conn = sqlite3.connect(str(manifest_db))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE Files (
                fileID TEXT PRIMARY KEY,
                domain TEXT,
                relativePath TEXT,
                flags INTEGER,
                file BLOB
            )
        """)
        conn.commit()
        conn.close()

        reader = BackupReader(backup_dir)
        assert reader.is_encrypted is True
