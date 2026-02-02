"""
Context management for Orange CLI.

This module provides persistent state management across Orange CLI commands,
allowing commands to share information about recently created resources
(backups, exports, etc.) and current working context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Default context file location
CONTEXT_FILE = Path.home() / ".orange" / "context.json"
CONTEXT_VERSION = 1
MAX_RECENT_ITEMS = 10


@dataclass
class BackupContext:
    """Information about a backup in context."""

    path: str
    device_udid: str
    device_name: str
    ios_version: str
    created_at: str
    is_encrypted: bool = False
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupContext:
        """Create from dictionary."""
        return cls(
            path=data.get("path", ""),
            device_udid=data.get("device_udid", ""),
            device_name=data.get("device_name", ""),
            ios_version=data.get("ios_version", ""),
            created_at=data.get("created_at", ""),
            is_encrypted=data.get("is_encrypted", False),
            size_bytes=data.get("size_bytes", 0),
        )

    @property
    def path_obj(self) -> Path:
        """Get path as Path object."""
        return Path(self.path)

    def exists(self) -> bool:
        """Check if backup still exists."""
        return self.path_obj.exists()


@dataclass
class DeviceContext:
    """Information about a device in context."""

    udid: str
    name: str
    ios_version: str = ""
    model: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceContext:
        """Create from dictionary."""
        return cls(
            udid=data.get("udid", ""),
            name=data.get("name", ""),
            ios_version=data.get("ios_version", ""),
            model=data.get("model", ""),
            last_seen=data.get("last_seen", ""),
        )


@dataclass
class ExportContext:
    """Information about an export in context."""

    path: str
    export_type: str  # messages, contacts, calendar, notes
    backup_path: str
    created_at: str
    record_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportContext:
        """Create from dictionary."""
        return cls(
            path=data.get("path", ""),
            export_type=data.get("export_type", ""),
            backup_path=data.get("backup_path", ""),
            created_at=data.get("created_at", ""),
            record_count=data.get("record_count", 0),
        )


@dataclass
class OrangeContextState:
    """Full context state."""

    version: int = CONTEXT_VERSION
    last_backup: Optional[BackupContext] = None
    recent_backups: list[BackupContext] = field(default_factory=list)
    current_device: Optional[DeviceContext] = None
    last_export: Optional[ExportContext] = None
    recent_exports: list[ExportContext] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "last_backup": self.last_backup.to_dict() if self.last_backup else None,
            "recent_backups": [b.to_dict() for b in self.recent_backups],
            "current_device": self.current_device.to_dict() if self.current_device else None,
            "last_export": self.last_export.to_dict() if self.last_export else None,
            "recent_exports": [e.to_dict() for e in self.recent_exports],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrangeContextState:
        """Create from dictionary."""
        return cls(
            version=data.get("version", CONTEXT_VERSION),
            last_backup=BackupContext.from_dict(data["last_backup"]) if data.get("last_backup") else None,
            recent_backups=[BackupContext.from_dict(b) for b in data.get("recent_backups", [])],
            current_device=DeviceContext.from_dict(data["current_device"]) if data.get("current_device") else None,
            last_export=ExportContext.from_dict(data["last_export"]) if data.get("last_export") else None,
            recent_exports=[ExportContext.from_dict(e) for e in data.get("recent_exports", [])],
        )


class OrangeContext:
    """
    Manages persistent context state across Orange CLI commands.

    This allows commands to share information about recently created
    resources and maintain working context across invocations.

    Example:
        ctx = OrangeContext()

        # After creating a backup
        ctx.set_last_backup(backup_info)

        # In another command, get the last backup
        backup = ctx.get_last_backup()
        if backup and backup.exists():
            print(f"Using backup at {backup.path}")
    """

    def __init__(self, context_file: Optional[Path] = None):
        """
        Initialize context manager.

        Args:
            context_file: Path to context file. Defaults to ~/.orange/context.json
        """
        self._context_file = context_file or CONTEXT_FILE
        self._state: Optional[OrangeContextState] = None
        self._load()

    def _load(self) -> None:
        """Load context from file."""
        if self._context_file.exists():
            try:
                with open(self._context_file, "r") as f:
                    data = json.load(f)
                self._state = OrangeContextState.from_dict(data)
                logger.debug(f"Loaded context from {self._context_file}")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Failed to load context: {e}")
                self._state = OrangeContextState()
        else:
            self._state = OrangeContextState()

    def _save(self) -> None:
        """Save context to file."""
        self._context_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._context_file, "w") as f:
                json.dump(self._state.to_dict(), f, indent=2)
            logger.debug(f"Saved context to {self._context_file}")
        except OSError as e:
            logger.warning(f"Failed to save context: {e}")

    @property
    def state(self) -> OrangeContextState:
        """Get the current state."""
        if self._state is None:
            self._state = OrangeContextState()
        return self._state

    # Backup context methods

    def set_last_backup(
        self,
        path: Path,
        device_udid: str,
        device_name: str,
        ios_version: str = "",
        is_encrypted: bool = False,
        size_bytes: int = 0,
    ) -> None:
        """
        Set the last created backup.

        Args:
            path: Path to the backup directory
            device_udid: Device UDID
            device_name: Device name
            ios_version: iOS version
            is_encrypted: Whether backup is encrypted
            size_bytes: Backup size in bytes
        """
        backup = BackupContext(
            path=str(path),
            device_udid=device_udid,
            device_name=device_name,
            ios_version=ios_version,
            created_at=datetime.now().isoformat(),
            is_encrypted=is_encrypted,
            size_bytes=size_bytes,
        )

        self.state.last_backup = backup

        # Add to recent backups (avoid duplicates by path)
        self.state.recent_backups = [
            b for b in self.state.recent_backups
            if b.path != backup.path
        ]
        self.state.recent_backups.insert(0, backup)
        self.state.recent_backups = self.state.recent_backups[:MAX_RECENT_ITEMS]

        self._save()

    def get_last_backup(self) -> Optional[BackupContext]:
        """
        Get the last created backup.

        Returns:
            BackupContext if available, None otherwise
        """
        return self.state.last_backup

    def get_recent_backups(self, existing_only: bool = True) -> list[BackupContext]:
        """
        Get recent backups.

        Args:
            existing_only: If True, filter out backups that no longer exist

        Returns:
            List of recent BackupContext objects
        """
        backups = self.state.recent_backups
        if existing_only:
            backups = [b for b in backups if b.exists()]
        return backups

    def get_backup_by_device(self, device_udid: str) -> Optional[BackupContext]:
        """
        Get the most recent backup for a specific device.

        Args:
            device_udid: Device UDID to find backup for

        Returns:
            BackupContext if found, None otherwise
        """
        for backup in self.state.recent_backups:
            if backup.device_udid == device_udid and backup.exists():
                return backup
        return None

    # Device context methods

    def set_current_device(
        self,
        udid: str,
        name: str,
        ios_version: str = "",
        model: str = "",
    ) -> None:
        """
        Set the current working device.

        Args:
            udid: Device UDID
            name: Device name
            ios_version: iOS version
            model: Device model
        """
        self.state.current_device = DeviceContext(
            udid=udid,
            name=name,
            ios_version=ios_version,
            model=model,
            last_seen=datetime.now().isoformat(),
        )
        self._save()

    def get_current_device(self) -> Optional[DeviceContext]:
        """
        Get the current working device.

        Returns:
            DeviceContext if set, None otherwise
        """
        return self.state.current_device

    # Export context methods

    def set_last_export(
        self,
        path: Path,
        export_type: str,
        backup_path: Path,
        record_count: int = 0,
    ) -> None:
        """
        Set the last created export.

        Args:
            path: Path to the export file/directory
            export_type: Type of export (messages, contacts, etc.)
            backup_path: Path to the source backup
            record_count: Number of records exported
        """
        export = ExportContext(
            path=str(path),
            export_type=export_type,
            backup_path=str(backup_path),
            created_at=datetime.now().isoformat(),
            record_count=record_count,
        )

        self.state.last_export = export

        # Add to recent exports
        self.state.recent_exports = [
            e for e in self.state.recent_exports
            if e.path != export.path
        ]
        self.state.recent_exports.insert(0, export)
        self.state.recent_exports = self.state.recent_exports[:MAX_RECENT_ITEMS]

        self._save()

    def get_last_export(self) -> Optional[ExportContext]:
        """
        Get the last created export.

        Returns:
            ExportContext if available, None otherwise
        """
        return self.state.last_export

    # Utility methods

    def clear(self) -> None:
        """Clear all context."""
        self._state = OrangeContextState()
        self._save()

    def to_dict(self) -> dict[str, Any]:
        """Get context as dictionary."""
        return self.state.to_dict()


# Singleton instance for easy access
_context: Optional[OrangeContext] = None


def get_context() -> OrangeContext:
    """
    Get the global context instance.

    Returns:
        OrangeContext singleton instance
    """
    global _context
    if _context is None:
        _context = OrangeContext()
    return _context
