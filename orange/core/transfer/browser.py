"""
Device file browser for iOS devices.

This module provides functionality for browsing the file system
of connected iOS devices using AFC (Apple File Conduit).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Any

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.afc import AfcService

from orange.exceptions import DeviceNotFoundError, TransferError

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """
    Information about a file or directory on the device.

    Attributes:
        name: File or directory name
        path: Full path on device
        size: Size in bytes (0 for directories)
        is_directory: Whether this is a directory
        modified_time: Last modification time
        created_time: Creation time
        permissions: File permissions
    """

    name: str
    path: str
    size: int
    is_directory: bool
    modified_time: Optional[datetime] = None
    created_time: Optional[datetime] = None
    permissions: Optional[int] = None

    @property
    def size_human(self) -> str:
        """Get human-readable size string."""
        if self.is_directory:
            return "-"
        size = self.size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(size) < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "size_human": self.size_human,
            "is_directory": self.is_directory,
            "modified_time": self.modified_time.isoformat() if self.modified_time else None,
            "created_time": self.created_time.isoformat() if self.created_time else None,
        }


class DeviceBrowser:
    """
    Browse files on an iOS device.

    Uses AFC (Apple File Conduit) to access the device's media
    partition (/var/mobile/Media).

    Example:
        browser = DeviceBrowser()

        # List root directory
        for item in browser.list_directory("/"):
            print(f"{item.name}: {item.size_human}")

        # Check if path exists
        if browser.exists("/DCIM"):
            print("Camera roll found")

        # Get file info
        info = browser.stat("/DCIM/100APPLE/IMG_0001.HEIC")
        print(f"Size: {info.size_human}")
    """

    def __init__(self, udid: Optional[str] = None):
        """
        Initialize device browser.

        Args:
            udid: Device UDID. If None, uses first connected device.

        Raises:
            DeviceNotFoundError: If device is not connected.
        """
        self._udid = udid
        self._afc: Optional[AfcService] = None
        self._lockdown = None

        logger.debug(f"DeviceBrowser initialized for {udid or 'first device'}")

    def _ensure_connected(self) -> AfcService:
        """Ensure AFC connection is established."""
        if self._afc is None:
            try:
                self._lockdown = create_using_usbmux(serial=self._udid)
                self._afc = AfcService(self._lockdown)
                logger.debug("AFC connection established")
            except Exception as e:
                raise DeviceNotFoundError(self._udid or "unknown") from e

        return self._afc

    def close(self) -> None:
        """Close the AFC connection."""
        if self._afc:
            try:
                self._afc.close()
            except Exception:
                pass
            self._afc = None
            self._lockdown = None

    def __enter__(self) -> "DeviceBrowser":
        """Context manager entry."""
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def list_directory(self, path: str = "/") -> list[FileInfo]:
        """
        List contents of a directory.

        Args:
            path: Directory path on device.

        Returns:
            List of FileInfo for each item in the directory.

        Raises:
            TransferError: If directory cannot be listed.
        """
        afc = self._ensure_connected()

        try:
            items = afc.listdir(path)
            result: list[FileInfo] = []

            for name in items:
                if name in (".", ".."):
                    continue

                full_path = f"{path.rstrip('/')}/{name}"
                try:
                    info = self._get_file_info(full_path, name)
                    result.append(info)
                except Exception as e:
                    logger.debug(f"Could not stat {full_path}: {e}")

            # Sort: directories first, then by name
            result.sort(key=lambda x: (not x.is_directory, x.name.lower()))
            return result

        except Exception as e:
            raise TransferError(f"Failed to list directory {path}: {e}") from e

    def stat(self, path: str) -> FileInfo:
        """
        Get information about a file or directory.

        Args:
            path: Path on device.

        Returns:
            FileInfo for the path.

        Raises:
            TransferError: If path cannot be accessed.
        """
        afc = self._ensure_connected()

        try:
            name = Path(path).name or "/"
            return self._get_file_info(path, name)
        except Exception as e:
            raise TransferError(f"Failed to stat {path}: {e}") from e

    def exists(self, path: str) -> bool:
        """
        Check if a path exists on the device.

        Args:
            path: Path to check.

        Returns:
            True if path exists.
        """
        afc = self._ensure_connected()

        try:
            return afc.exists(path)
        except Exception:
            return False

    def is_directory(self, path: str) -> bool:
        """
        Check if a path is a directory.

        Args:
            path: Path to check.

        Returns:
            True if path is a directory.
        """
        afc = self._ensure_connected()

        try:
            return afc.isdir(path)
        except Exception:
            return False

    def walk(
        self,
        path: str = "/",
        max_depth: int = -1,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        """
        Walk a directory tree (like os.walk).

        Args:
            path: Starting path.
            max_depth: Maximum depth (-1 for unlimited).

        Yields:
            Tuples of (dirpath, dirnames, filenames).
        """
        afc = self._ensure_connected()

        try:
            yield from self._walk_recursive(path, max_depth, 0)
        except Exception as e:
            logger.error(f"Walk failed at {path}: {e}")

    def _walk_recursive(
        self,
        path: str,
        max_depth: int,
        current_depth: int,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        """Recursive directory walker."""
        if max_depth >= 0 and current_depth > max_depth:
            return

        afc = self._ensure_connected()

        try:
            items = afc.listdir(path)
        except Exception:
            return

        dirs: list[str] = []
        files: list[str] = []

        for name in items:
            if name in (".", ".."):
                continue

            full_path = f"{path.rstrip('/')}/{name}"
            try:
                if afc.isdir(full_path):
                    dirs.append(name)
                else:
                    files.append(name)
            except Exception:
                files.append(name)

        yield path, dirs, files

        for dir_name in dirs:
            dir_path = f"{path.rstrip('/')}/{dir_name}"
            yield from self._walk_recursive(dir_path, max_depth, current_depth + 1)

    def get_device_info(self) -> dict[str, Any]:
        """
        Get AFC device information.

        Returns:
            Dictionary with device storage info.
        """
        afc = self._ensure_connected()

        try:
            return afc.get_device_info()
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return {}

    def _get_file_info(self, path: str, name: str) -> FileInfo:
        """Get FileInfo for a path."""
        afc = self._ensure_connected()

        stat_info = afc.stat(path)

        # Parse timestamps
        modified_time = None
        created_time = None

        if "st_mtime" in stat_info:
            try:
                # AFC returns nanoseconds
                mtime = int(stat_info["st_mtime"]) / 1_000_000_000
                modified_time = datetime.fromtimestamp(mtime)
            except Exception:
                pass

        if "st_birthtime" in stat_info:
            try:
                btime = int(stat_info["st_birthtime"]) / 1_000_000_000
                created_time = datetime.fromtimestamp(btime)
            except Exception:
                pass

        return FileInfo(
            name=name,
            path=path,
            size=int(stat_info.get("st_size", 0)),
            is_directory=stat_info.get("st_ifmt") == "S_IFDIR",
            modified_time=modified_time,
            created_time=created_time,
            permissions=int(stat_info.get("st_mode", 0)) if "st_mode" in stat_info else None,
        )
