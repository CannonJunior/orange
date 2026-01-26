"""
Backup manager for creating and restoring iOS backups.

This module provides high-level backup operations using pymobiledevice3's
Mobilebackup2Service.
"""

from __future__ import annotations

import logging
import plistlib
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from pymobiledevice3.lockdown import create_using_usbmux, LockdownClient
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

from orange.core.backup.models import BackupInfo, BackupProgress, BackupStatus
from orange.exceptions import (
    BackupError,
    DeviceNotFoundError,
    DeviceNotPairedError,
)

logger = logging.getLogger(__name__)

# Default backup directory
DEFAULT_BACKUP_DIR = Path.home() / ".orange" / "backups"


class BackupManager:
    """
    Manages iOS device backup operations.

    Provides functionality for creating backups, restoring backups,
    listing existing backups, and managing backup encryption.

    Example:
        manager = BackupManager()

        # Create a backup
        backup = manager.create_backup(
            udid="00008030-001234567890001E",
            destination="./backups",
            progress_callback=lambda p: print(f"{p}%")
        )

        # List backups
        for backup in manager.list_backups():
            print(f"{backup.device_name}: {backup.backup_date}")

        # Restore a backup
        manager.restore_backup(udid, backup.path)
    """

    def __init__(self, backup_dir: Optional[Path] = None):
        """
        Initialize the backup manager.

        Args:
            backup_dir: Default directory for backups. If None, uses
                       ~/.orange/backups
        """
        self._backup_dir = Path(backup_dir) if backup_dir else DEFAULT_BACKUP_DIR
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"BackupManager initialized (backup_dir={self._backup_dir})")

    @property
    def backup_dir(self) -> Path:
        """Get the default backup directory."""
        return self._backup_dir

    def create_backup(
        self,
        udid: Optional[str] = None,
        destination: Optional[Path] = None,
        full: bool = True,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> BackupInfo:
        """
        Create a backup of an iOS device.

        Args:
            udid: Device UDID. If None, uses first connected device.
            destination: Backup destination directory. If None, uses default.
            full: Whether to create a full backup (True) or incremental (False).
            progress_callback: Optional callback for progress updates (0-100).

        Returns:
            BackupInfo with details about the created backup.

        Raises:
            DeviceNotFoundError: If device is not connected.
            DeviceNotPairedError: If device is not paired.
            BackupError: If backup fails.
        """
        dest = Path(destination) if destination else self._backup_dir
        dest.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating {'full' if full else 'incremental'} backup to {dest}")

        try:
            # Connect to device
            lockdown = create_using_usbmux(serial=udid)
            device_udid = lockdown.udid
            device_name = lockdown.all_values.get("DeviceName", "Unknown")

            logger.info(f"Backing up {device_name} ({device_udid})")

            # Create backup service
            backup_service = Mobilebackup2Service(lockdown)

            # Wrapper for progress callback
            def progress_wrapper(percentage: float) -> None:
                if progress_callback:
                    progress_callback(percentage)
                logger.debug(f"Backup progress: {percentage:.1f}%")

            # Perform backup
            backup_service.backup(
                full=full,
                backup_directory=str(dest),
                progress_callback=progress_wrapper,
            )

            # Get backup info
            backup_path = dest / device_udid
            backup_info = self._parse_backup_info(backup_path)

            logger.info(f"Backup completed: {backup_info.display_name}")
            return backup_info

        except FileNotFoundError as e:
            raise DeviceNotFoundError(udid or "unknown") from e
        except Exception as e:
            error_msg = str(e)
            if "not paired" in error_msg.lower():
                raise DeviceNotPairedError(udid or "unknown") from e
            logger.error(f"Backup failed: {e}")
            raise BackupError(f"Backup failed: {e}") from e

    def restore_backup(
        self,
        udid: Optional[str] = None,
        backup_path: Optional[Path] = None,
        source_udid: Optional[str] = None,
        password: Optional[str] = None,
        system: bool = False,
        settings: bool = True,
        reboot: bool = True,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """
        Restore a backup to an iOS device.

        Args:
            udid: Target device UDID. If None, uses first connected device.
            backup_path: Path to backup directory. If None, uses default.
            source_udid: UDID of backup to restore (if different from target).
            password: Password for encrypted backups.
            system: Whether to restore system files.
            settings: Whether to restore device settings.
            reboot: Whether to reboot device after restore.
            progress_callback: Optional callback for progress updates (0-100).

        Returns:
            True if restore completed successfully.

        Raises:
            DeviceNotFoundError: If device is not connected.
            BackupError: If restore fails.
        """
        backup_dir = Path(backup_path) if backup_path else self._backup_dir

        logger.info(f"Restoring backup from {backup_dir}")

        try:
            # Connect to device
            lockdown = create_using_usbmux(serial=udid)
            device_name = lockdown.all_values.get("DeviceName", "Unknown")

            logger.info(f"Restoring to {device_name}")

            # Create backup service
            backup_service = Mobilebackup2Service(lockdown)

            # Wrapper for progress callback
            def progress_wrapper(percentage: float) -> None:
                if progress_callback:
                    progress_callback(percentage)
                logger.debug(f"Restore progress: {percentage:.1f}%")

            # Perform restore
            backup_service.restore(
                backup_directory=str(backup_dir),
                system=system,
                settings=settings,
                reboot=reboot,
                password=password or "",
                source=source_udid or "",
                progress_callback=progress_wrapper,
            )

            logger.info("Restore completed")
            return True

        except FileNotFoundError as e:
            raise DeviceNotFoundError(udid or "unknown") from e
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise BackupError(f"Restore failed: {e}") from e

    def list_backups(
        self,
        backup_dir: Optional[Path] = None,
    ) -> list[BackupInfo]:
        """
        List all available backups.

        Args:
            backup_dir: Directory to search for backups. If None, uses default.

        Returns:
            List of BackupInfo for each found backup.
        """
        search_dir = Path(backup_dir) if backup_dir else self._backup_dir

        if not search_dir.exists():
            return []

        backups: list[BackupInfo] = []

        for item in search_dir.iterdir():
            if not item.is_dir():
                continue

            # Check for Info.plist (indicates a backup)
            info_plist = item / "Info.plist"
            if info_plist.exists():
                try:
                    backup_info = self._parse_backup_info(item)
                    backups.append(backup_info)
                except Exception as e:
                    logger.warning(f"Failed to parse backup at {item}: {e}")

        # Sort by date, newest first
        backups.sort(key=lambda b: b.backup_date, reverse=True)
        return backups

    def get_backup_info(
        self,
        backup_path: Path,
    ) -> BackupInfo:
        """
        Get information about a specific backup.

        Args:
            backup_path: Path to the backup directory.

        Returns:
            BackupInfo with backup details.

        Raises:
            BackupError: If backup info cannot be read.
        """
        return self._parse_backup_info(backup_path)

    def delete_backup(
        self,
        backup_path: Path,
    ) -> bool:
        """
        Delete a backup.

        Args:
            backup_path: Path to the backup directory.

        Returns:
            True if deleted successfully.
        """
        import shutil

        if not backup_path.exists():
            return False

        try:
            shutil.rmtree(backup_path)
            logger.info(f"Deleted backup at {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False

    def change_password(
        self,
        udid: Optional[str] = None,
        backup_dir: Optional[Path] = None,
        old_password: str = "",
        new_password: str = "",
    ) -> bool:
        """
        Change or set backup encryption password.

        Args:
            udid: Device UDID.
            backup_dir: Backup directory.
            old_password: Current password (empty to enable encryption).
            new_password: New password (empty to disable encryption).

        Returns:
            True if password changed successfully.
        """
        backup_directory = Path(backup_dir) if backup_dir else self._backup_dir

        try:
            lockdown = create_using_usbmux(serial=udid)
            backup_service = Mobilebackup2Service(lockdown)

            backup_service.change_password(
                backup_directory=str(backup_directory),
                old=old_password,
                new=new_password,
            )

            action = "enabled" if new_password else "disabled"
            logger.info(f"Backup encryption {action}")
            return True

        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            raise BackupError(f"Failed to change password: {e}") from e

    def _parse_backup_info(self, backup_path: Path) -> BackupInfo:
        """Parse backup metadata from Info.plist."""
        info_plist = backup_path / "Info.plist"
        manifest_plist = backup_path / "Manifest.plist"

        if not info_plist.exists():
            raise BackupError(f"No Info.plist found at {backup_path}")

        try:
            with open(info_plist, "rb") as f:
                info = plistlib.load(f)

            # Check for encryption in Manifest.plist
            is_encrypted = False
            if manifest_plist.exists():
                with open(manifest_plist, "rb") as f:
                    manifest = plistlib.load(f)
                    is_encrypted = manifest.get("IsEncrypted", False)

            # Calculate backup size
            size_bytes = sum(
                f.stat().st_size for f in backup_path.rglob("*") if f.is_file()
            )

            # Parse date
            backup_date = info.get("Last Backup Date")
            if isinstance(backup_date, str):
                backup_date = datetime.fromisoformat(backup_date)
            elif not isinstance(backup_date, datetime):
                backup_date = datetime.now()

            return BackupInfo(
                backup_id=info.get("Target Identifier", backup_path.name),
                device_name=info.get("Device Name", "Unknown"),
                device_udid=info.get("Target Identifier", backup_path.name),
                ios_version=info.get("Product Version", "Unknown"),
                build_version=info.get("Build Version", "Unknown"),
                backup_date=backup_date,
                is_encrypted=is_encrypted,
                is_full=True,  # Can't easily determine from plist
                size_bytes=size_bytes,
                path=backup_path,
                product_type=info.get("Product Type"),
                serial_number=info.get("Serial Number"),
            )

        except Exception as e:
            raise BackupError(f"Failed to parse backup info: {e}") from e
