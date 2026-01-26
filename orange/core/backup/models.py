"""
Data models for backup operations.

This module contains dataclasses representing backup metadata,
file information, and status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class BackupStatus(Enum):
    """Status of a backup operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackupInfo:
    """
    Metadata about an iOS backup.

    Attributes:
        backup_id: Unique identifier (typically device UDID)
        device_name: User-assigned device name
        device_udid: Device's unique identifier
        ios_version: iOS version at time of backup
        build_version: iOS build version
        backup_date: When the backup was created
        is_encrypted: Whether the backup is encrypted
        is_full: Whether this is a full or incremental backup
        size_bytes: Total size of backup in bytes
        path: Path to the backup directory
        product_type: Device model (e.g., "iPhone14,2")
        serial_number: Device serial number
    """

    backup_id: str
    device_name: str
    device_udid: str
    ios_version: str
    build_version: str
    backup_date: datetime
    is_encrypted: bool
    is_full: bool
    size_bytes: int
    path: Path
    product_type: Optional[str] = None
    serial_number: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Get a display-friendly name for the backup."""
        date_str = self.backup_date.strftime("%Y-%m-%d %H:%M")
        return f"{self.device_name} - {date_str}"

    @property
    def size_human(self) -> str:
        """Get human-readable size string."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(size) < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "backup_id": self.backup_id,
            "device_name": self.device_name,
            "device_udid": self.device_udid,
            "ios_version": self.ios_version,
            "build_version": self.build_version,
            "backup_date": self.backup_date.isoformat(),
            "is_encrypted": self.is_encrypted,
            "is_full": self.is_full,
            "size_bytes": self.size_bytes,
            "size_human": self.size_human,
            "path": str(self.path),
            "product_type": self.product_type,
            "serial_number": self.serial_number,
        }


@dataclass
class BackupFile:
    """
    Information about a file within a backup.

    Attributes:
        file_id: Internal file identifier (hash-based filename)
        domain: Backup domain (e.g., "HomeDomain", "CameraRollDomain")
        relative_path: Path relative to domain root
        flags: File flags
        size: File size in bytes
        mode: File mode/permissions
        modified_time: Last modification time
        is_directory: Whether this is a directory
        is_encrypted: Whether the file content is encrypted
    """

    file_id: str
    domain: str
    relative_path: str
    flags: int
    size: int
    mode: int
    modified_time: Optional[datetime] = None
    is_directory: bool = False
    is_encrypted: bool = False

    @property
    def full_path(self) -> str:
        """Get the full path including domain."""
        return f"{self.domain}/{self.relative_path}"

    @property
    def filename(self) -> str:
        """Get just the filename."""
        return Path(self.relative_path).name

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_id": self.file_id,
            "domain": self.domain,
            "relative_path": self.relative_path,
            "full_path": self.full_path,
            "flags": self.flags,
            "size": self.size,
            "mode": self.mode,
            "modified_time": self.modified_time.isoformat() if self.modified_time else None,
            "is_directory": self.is_directory,
            "is_encrypted": self.is_encrypted,
        }


@dataclass
class BackupProgress:
    """Progress information for a backup/restore operation."""

    status: BackupStatus
    percentage: float = 0.0
    current_file: Optional[str] = None
    files_completed: int = 0
    files_total: int = 0
    bytes_completed: int = 0
    bytes_total: int = 0
    error_message: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.status in (
            BackupStatus.COMPLETED,
            BackupStatus.FAILED,
            BackupStatus.CANCELLED,
        )
