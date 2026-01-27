"""
Data models for iOS app management.

This module defines the data structures used to represent
iOS applications and their metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class AppType(Enum):
    """Type of iOS application."""

    USER = "User"  # App Store or sideloaded apps
    SYSTEM = "System"  # Built-in iOS apps
    HIDDEN = "Hidden"  # Hidden system apps
    ANY = "Any"  # All types


@dataclass
class AppInfo:
    """
    Information about an installed iOS application.

    Attributes:
        bundle_id: Unique bundle identifier (e.g., "com.netflix.Netflix")
        name: Display name of the app
        version: App version string
        short_version: Short version (marketing version)
        app_type: Type of app (User, System, Hidden)
        path: Path to app bundle on device
        container_path: Path to app's data container
        size: Size of app bundle in bytes
        data_size: Size of app data in bytes
        is_sideloaded: Whether app was sideloaded (not from App Store)
        min_os_version: Minimum required iOS version
        executable_name: Name of main executable
        icon_files: List of icon file names
        entitlements: App entitlements dictionary
        extra: Additional metadata
    """

    bundle_id: str
    name: str
    version: str
    short_version: str
    app_type: AppType
    path: Optional[str] = None
    container_path: Optional[str] = None
    size: int = 0
    data_size: int = 0
    is_sideloaded: bool = False
    min_os_version: Optional[str] = None
    executable_name: Optional[str] = None
    icon_files: list[str] = field(default_factory=list)
    entitlements: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def size_human(self) -> str:
        """Get human-readable size of app bundle."""
        return _format_size(self.size)

    @property
    def data_size_human(self) -> str:
        """Get human-readable size of app data."""
        return _format_size(self.data_size)

    @property
    def total_size(self) -> int:
        """Get total size (bundle + data)."""
        return self.size + self.data_size

    @property
    def total_size_human(self) -> str:
        """Get human-readable total size."""
        return _format_size(self.total_size)

    @property
    def is_extractable(self) -> bool:
        """Check if app can be extracted as IPA."""
        # System apps cannot be extracted
        return self.app_type == AppType.USER

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "bundle_id": self.bundle_id,
            "name": self.name,
            "version": self.version,
            "short_version": self.short_version,
            "app_type": self.app_type.value,
            "path": self.path,
            "container_path": self.container_path,
            "size": self.size,
            "size_human": self.size_human,
            "data_size": self.data_size,
            "data_size_human": self.data_size_human,
            "total_size": self.total_size,
            "total_size_human": self.total_size_human,
            "is_sideloaded": self.is_sideloaded,
            "is_extractable": self.is_extractable,
            "min_os_version": self.min_os_version,
            "executable_name": self.executable_name,
        }


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes == 0:
        return "0 B"

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0

    return f"{size_bytes:.1f} PB"
