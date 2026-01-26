"""Tests for backup manager."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import plistlib

from orange.core.backup.manager import BackupManager, DEFAULT_BACKUP_DIR
from orange.core.backup.models import BackupInfo
from orange.exceptions import BackupError, DeviceNotFoundError


class TestBackupManager:
    """Tests for BackupManager class."""

    def test_init_default_directory(self) -> None:
        """Manager should use default backup directory."""
        manager = BackupManager()
        assert manager.backup_dir == DEFAULT_BACKUP_DIR

    def test_init_custom_directory(self, tmp_path: Path) -> None:
        """Manager should use custom backup directory."""
        manager = BackupManager(backup_dir=tmp_path)
        assert manager.backup_dir == tmp_path

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Manager should create backup directory if it doesn't exist."""
        new_dir = tmp_path / "new_backup_dir"
        assert not new_dir.exists()

        manager = BackupManager(backup_dir=new_dir)
        assert new_dir.exists()

    def test_list_backups_empty(self, tmp_path: Path) -> None:
        """list_backups should return empty list when no backups exist."""
        manager = BackupManager(backup_dir=tmp_path)
        backups = manager.list_backups()
        assert backups == []

    def test_list_backups_nonexistent_directory(self, tmp_path: Path) -> None:
        """list_backups should return empty list for nonexistent directory."""
        manager = BackupManager(backup_dir=tmp_path)
        backups = manager.list_backups(tmp_path / "nonexistent")
        assert backups == []

    def test_list_backups_finds_backups(self, tmp_path: Path) -> None:
        """list_backups should find valid backup directories."""
        # Create a fake backup
        backup_dir = tmp_path / "test-udid"
        backup_dir.mkdir()

        # Create Info.plist
        info_plist = backup_dir / "Info.plist"
        info_data = {
            "Device Name": "Test iPhone",
            "Target Identifier": "test-udid",
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

        manager = BackupManager(backup_dir=tmp_path)
        backups = manager.list_backups()

        assert len(backups) == 1
        assert backups[0].device_name == "Test iPhone"
        assert backups[0].device_udid == "test-udid"
        assert backups[0].ios_version == "17.0"

    def test_get_backup_info(self, tmp_path: Path) -> None:
        """get_backup_info should return BackupInfo for valid backup."""
        # Create a fake backup
        backup_dir = tmp_path / "test-udid"
        backup_dir.mkdir()

        info_plist = backup_dir / "Info.plist"
        info_data = {
            "Device Name": "Test iPhone",
            "Target Identifier": "test-udid",
            "Product Version": "17.0",
            "Build Version": "21A329",
            "Last Backup Date": datetime.now(),
        }
        with open(info_plist, "wb") as f:
            plistlib.dump(info_data, f)

        manifest_plist = backup_dir / "Manifest.plist"
        manifest_data = {"IsEncrypted": True}
        with open(manifest_plist, "wb") as f:
            plistlib.dump(manifest_data, f)

        manager = BackupManager()
        backup_info = manager.get_backup_info(backup_dir)

        assert backup_info.device_name == "Test iPhone"
        assert backup_info.is_encrypted is True

    def test_get_backup_info_missing_info_plist(self, tmp_path: Path) -> None:
        """get_backup_info should raise for missing Info.plist."""
        backup_dir = tmp_path / "invalid-backup"
        backup_dir.mkdir()

        manager = BackupManager()
        with pytest.raises(BackupError):
            manager.get_backup_info(backup_dir)

    def test_delete_backup(self, tmp_path: Path) -> None:
        """delete_backup should remove the backup directory."""
        backup_dir = tmp_path / "to-delete"
        backup_dir.mkdir()
        (backup_dir / "test.txt").write_text("test")

        manager = BackupManager()
        result = manager.delete_backup(backup_dir)

        assert result is True
        assert not backup_dir.exists()

    def test_delete_backup_nonexistent(self, tmp_path: Path) -> None:
        """delete_backup should return False for nonexistent directory."""
        manager = BackupManager()
        result = manager.delete_backup(tmp_path / "nonexistent")
        assert result is False

    @patch("orange.core.backup.manager.create_lockdown_client")
    @patch("orange.core.backup.manager.Mobilebackup2Service")
    def test_create_backup_success(
        self,
        mock_backup_service: MagicMock,
        mock_create_usbmux: MagicMock,
        tmp_path: Path,
    ) -> None:
        """create_backup should create a backup successfully."""
        # Setup mocks
        mock_lockdown = Mock()
        mock_lockdown.udid = "test-udid"
        mock_lockdown.all_values = {"DeviceName": "Test iPhone"}
        mock_create_usbmux.return_value = mock_lockdown

        mock_service_instance = Mock()
        mock_backup_service.return_value = mock_service_instance

        # Create fake backup output
        backup_dir = tmp_path / "test-udid"
        backup_dir.mkdir()
        info_plist = backup_dir / "Info.plist"
        info_data = {
            "Device Name": "Test iPhone",
            "Target Identifier": "test-udid",
            "Product Version": "17.0",
            "Build Version": "21A329",
            "Last Backup Date": datetime.now(),
        }
        with open(info_plist, "wb") as f:
            plistlib.dump(info_data, f)
        manifest_plist = backup_dir / "Manifest.plist"
        with open(manifest_plist, "wb") as f:
            plistlib.dump({"IsEncrypted": False}, f)

        manager = BackupManager()
        backup_info = manager.create_backup(
            udid="test-udid",
            destination=tmp_path,
        )

        assert backup_info.device_name == "Test iPhone"
        mock_service_instance.backup.assert_called_once()

    @patch("orange.core.backup.manager.create_lockdown_client")
    def test_create_backup_device_not_found(
        self,
        mock_create_usbmux: MagicMock,
    ) -> None:
        """create_backup should raise DeviceNotFoundError."""
        mock_create_usbmux.side_effect = FileNotFoundError("Device not found")

        manager = BackupManager()
        with pytest.raises(DeviceNotFoundError):
            manager.create_backup(udid="invalid-udid")
