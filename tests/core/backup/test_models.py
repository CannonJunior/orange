"""Tests for backup models."""

import pytest
from datetime import datetime
from pathlib import Path

from orange.core.backup.models import (
    BackupInfo,
    BackupFile,
    BackupProgress,
    BackupStatus,
)


class TestBackupStatus:
    """Tests for BackupStatus enum."""

    def test_status_values_exist(self) -> None:
        """All expected status values should exist."""
        assert BackupStatus.PENDING.value == "pending"
        assert BackupStatus.IN_PROGRESS.value == "in_progress"
        assert BackupStatus.COMPLETED.value == "completed"
        assert BackupStatus.FAILED.value == "failed"
        assert BackupStatus.CANCELLED.value == "cancelled"


class TestBackupInfo:
    """Tests for BackupInfo dataclass."""

    @pytest.fixture
    def backup_info(self) -> BackupInfo:
        """Create a sample BackupInfo for testing."""
        return BackupInfo(
            backup_id="test-backup-id",
            device_name="Test iPhone",
            device_udid="00008030-001234567890001E",
            ios_version="17.0",
            build_version="21A329",
            backup_date=datetime(2026, 1, 25, 12, 0, 0),
            is_encrypted=False,
            is_full=True,
            size_bytes=1024 * 1024 * 500,  # 500 MB
            path=Path("/backups/test"),
            product_type="iPhone14,2",
            serial_number="TESTSERIAL123",
        )

    def test_backup_info_creation(self, backup_info: BackupInfo) -> None:
        """BackupInfo should be created with all fields."""
        assert backup_info.backup_id == "test-backup-id"
        assert backup_info.device_name == "Test iPhone"
        assert backup_info.device_udid == "00008030-001234567890001E"
        assert backup_info.ios_version == "17.0"
        assert backup_info.is_encrypted is False
        assert backup_info.is_full is True

    def test_display_name(self, backup_info: BackupInfo) -> None:
        """display_name should return formatted string."""
        assert "Test iPhone" in backup_info.display_name
        assert "2026-01-25" in backup_info.display_name

    def test_size_human(self, backup_info: BackupInfo) -> None:
        """size_human should return human-readable size."""
        assert "MB" in backup_info.size_human or "GB" in backup_info.size_human

    def test_size_human_bytes(self) -> None:
        """size_human should handle bytes."""
        info = BackupInfo(
            backup_id="test",
            device_name="Test",
            device_udid="test",
            ios_version="17.0",
            build_version="21A329",
            backup_date=datetime.now(),
            is_encrypted=False,
            is_full=True,
            size_bytes=512,
            path=Path("/test"),
        )
        assert "B" in info.size_human

    def test_size_human_gigabytes(self) -> None:
        """size_human should handle gigabytes."""
        info = BackupInfo(
            backup_id="test",
            device_name="Test",
            device_udid="test",
            ios_version="17.0",
            build_version="21A329",
            backup_date=datetime.now(),
            is_encrypted=False,
            is_full=True,
            size_bytes=1024 * 1024 * 1024 * 5,  # 5 GB
            path=Path("/test"),
        )
        assert "GB" in info.size_human

    def test_to_dict(self, backup_info: BackupInfo) -> None:
        """to_dict should return all fields."""
        d = backup_info.to_dict()
        assert d["backup_id"] == "test-backup-id"
        assert d["device_name"] == "Test iPhone"
        assert d["is_encrypted"] is False
        assert "size_human" in d
        assert d["path"] == "/backups/test"


class TestBackupFile:
    """Tests for BackupFile dataclass."""

    @pytest.fixture
    def backup_file(self) -> BackupFile:
        """Create a sample BackupFile for testing."""
        return BackupFile(
            file_id="abc123def456",
            domain="HomeDomain",
            relative_path="Library/SMS/sms.db",
            flags=0,
            size=1024000,
            mode=0o100644,
            modified_time=datetime(2026, 1, 25, 12, 0, 0),
            is_directory=False,
            is_encrypted=False,
        )

    def test_backup_file_creation(self, backup_file: BackupFile) -> None:
        """BackupFile should be created with all fields."""
        assert backup_file.file_id == "abc123def456"
        assert backup_file.domain == "HomeDomain"
        assert backup_file.relative_path == "Library/SMS/sms.db"
        assert backup_file.is_directory is False

    def test_full_path(self, backup_file: BackupFile) -> None:
        """full_path should combine domain and relative path."""
        assert backup_file.full_path == "HomeDomain/Library/SMS/sms.db"

    def test_filename(self, backup_file: BackupFile) -> None:
        """filename should return just the file name."""
        assert backup_file.filename == "sms.db"

    def test_to_dict(self, backup_file: BackupFile) -> None:
        """to_dict should return all fields."""
        d = backup_file.to_dict()
        assert d["file_id"] == "abc123def456"
        assert d["domain"] == "HomeDomain"
        assert d["full_path"] == "HomeDomain/Library/SMS/sms.db"

    def test_directory_file(self) -> None:
        """BackupFile should handle directories."""
        dir_file = BackupFile(
            file_id="dir123",
            domain="HomeDomain",
            relative_path="Library/Preferences",
            flags=0,
            size=0,
            mode=0o40755,
            is_directory=True,
            is_encrypted=False,
        )
        assert dir_file.is_directory is True
        assert dir_file.filename == "Preferences"


class TestBackupProgress:
    """Tests for BackupProgress dataclass."""

    def test_progress_creation(self) -> None:
        """BackupProgress should be created with defaults."""
        progress = BackupProgress(status=BackupStatus.PENDING)
        assert progress.status == BackupStatus.PENDING
        assert progress.percentage == 0.0
        assert progress.is_complete is False

    def test_is_complete_completed(self) -> None:
        """is_complete should return True for COMPLETED status."""
        progress = BackupProgress(
            status=BackupStatus.COMPLETED,
            percentage=100.0,
        )
        assert progress.is_complete is True

    def test_is_complete_failed(self) -> None:
        """is_complete should return True for FAILED status."""
        progress = BackupProgress(
            status=BackupStatus.FAILED,
            error_message="Test error",
        )
        assert progress.is_complete is True

    def test_is_complete_in_progress(self) -> None:
        """is_complete should return False for IN_PROGRESS status."""
        progress = BackupProgress(
            status=BackupStatus.IN_PROGRESS,
            percentage=50.0,
        )
        assert progress.is_complete is False
