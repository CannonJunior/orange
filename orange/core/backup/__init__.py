"""
Backup module for Orange.

This module provides functionality for creating, restoring, and managing
iOS device backups.

Example:
    from orange.core.backup import BackupManager, BackupInfo

    # Create a backup
    manager = BackupManager()
    backup = manager.create_backup(udid, destination="./backups")

    # List existing backups
    backups = manager.list_backups()

    # Restore a backup
    manager.restore_backup(udid, backup.path)
"""

from orange.core.backup.models import BackupInfo, BackupFile, BackupStatus
from orange.core.backup.manager import BackupManager
from orange.core.backup.reader import BackupReader

__all__ = [
    "BackupInfo",
    "BackupFile",
    "BackupManager",
    "BackupReader",
    "BackupStatus",
]
