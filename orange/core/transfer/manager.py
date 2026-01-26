"""
File transfer manager for iOS devices.

This module provides functionality for transferring files between
iOS devices and computers, including selective category-based transfers.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Iterator, Optional

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.afc import AfcService

from orange.core.transfer.browser import DeviceBrowser, FileInfo
from orange.core.transfer.categories import (
    DataCategory,
    AccessMethod,
    CATEGORIES,
    get_category,
)
from orange.exceptions import DeviceNotFoundError, TransferError

logger = logging.getLogger(__name__)


from dataclasses import dataclass, field


@dataclass
class TransferProgress:
    """Progress information for a transfer operation."""

    total_files: int = 0
    completed_files: int = 0
    total_bytes: int = 0
    completed_bytes: int = 0
    current_file: Optional[str] = None
    failed_files: list[str] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        """Get completion percentage."""
        if self.total_bytes == 0:
            return 0.0
        return (self.completed_bytes / self.total_bytes) * 100


class FileManager:
    """
    Manages file transfers with iOS devices.

    Supports:
    - Pulling (downloading) files from device
    - Pushing (uploading) files to device
    - Category-based selective transfers
    - Progress tracking

    Example:
        manager = FileManager()

        # Pull photos from device
        manager.pull_category("photos", "./backup/photos")

        # Pull specific directory
        manager.pull("/DCIM/100APPLE", "./photos")

        # Pull with progress
        def on_progress(p):
            print(f"{p.percentage:.1f}% - {p.current_file}")

        manager.pull("/DCIM", "./backup", progress_callback=on_progress)
    """

    def __init__(self, udid: Optional[str] = None):
        """
        Initialize file manager.

        Args:
            udid: Device UDID. If None, uses first connected device.
        """
        self._udid = udid
        self._browser = DeviceBrowser(udid)
        self._afc: Optional[AfcService] = None
        self._lockdown = None

        logger.debug(f"FileManager initialized for {udid or 'first device'}")

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
        """Close connections."""
        if self._afc:
            try:
                self._afc.close()
            except Exception:
                pass
            self._afc = None
            self._lockdown = None
        self._browser.close()

    def __enter__(self) -> "FileManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def pull(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback: Optional[Callable[[TransferProgress], None]] = None,
    ) -> TransferProgress:
        """
        Pull (download) a file or directory from the device.

        Args:
            remote_path: Path on device.
            local_path: Local destination path.
            progress_callback: Optional callback for progress updates.

        Returns:
            TransferProgress with final statistics.

        Raises:
            TransferError: If transfer fails.
        """
        afc = self._ensure_connected()
        local_path = Path(local_path)

        progress = TransferProgress()

        try:
            # Check if source exists
            if not self._browser.exists(remote_path):
                raise TransferError(f"Remote path does not exist: {remote_path}")

            # Determine if file or directory
            if self._browser.is_directory(remote_path):
                # Pull directory recursively
                self._pull_directory(
                    remote_path,
                    local_path,
                    progress,
                    progress_callback,
                )
            else:
                # Pull single file
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self._pull_file(
                    remote_path,
                    local_path,
                    progress,
                    progress_callback,
                )

            return progress

        except TransferError:
            raise
        except Exception as e:
            raise TransferError(f"Pull failed: {e}") from e

    def pull_category(
        self,
        category_id: str,
        local_path: Path,
        progress_callback: Optional[Callable[[TransferProgress], None]] = None,
    ) -> TransferProgress:
        """
        Pull all files for a data category.

        Args:
            category_id: Category ID (e.g., "photos", "music").
            local_path: Local destination directory.
            progress_callback: Optional callback for progress updates.

        Returns:
            TransferProgress with final statistics.

        Raises:
            TransferError: If category not found or transfer fails.
        """
        category = get_category(category_id)
        if category is None:
            raise TransferError(f"Unknown category: {category_id}")

        if category.access_method != AccessMethod.AFC:
            raise TransferError(
                f"Category '{category.name}' requires backup access, not direct transfer. "
                f"Use 'orange backup create' and extract from backup."
            )

        if not category.afc_paths:
            raise TransferError(f"Category '{category.name}' has no AFC paths defined")

        local_path = Path(local_path)
        local_path.mkdir(parents=True, exist_ok=True)

        progress = TransferProgress()

        for remote_path in category.afc_paths:
            if self._browser.exists(remote_path):
                logger.info(f"Pulling {remote_path} for category {category_id}")
                category_dir = local_path / Path(remote_path).name
                self._pull_directory(
                    remote_path,
                    category_dir,
                    progress,
                    progress_callback,
                )
            else:
                logger.debug(f"Path does not exist, skipping: {remote_path}")

        return progress

    def push(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Optional[Callable[[TransferProgress], None]] = None,
    ) -> TransferProgress:
        """
        Push (upload) a file or directory to the device.

        Args:
            local_path: Local file or directory.
            remote_path: Destination path on device.
            progress_callback: Optional callback for progress updates.

        Returns:
            TransferProgress with final statistics.

        Raises:
            TransferError: If transfer fails.
        """
        afc = self._ensure_connected()
        local_path = Path(local_path)

        if not local_path.exists():
            raise TransferError(f"Local path does not exist: {local_path}")

        progress = TransferProgress()

        try:
            if local_path.is_dir():
                self._push_directory(
                    local_path,
                    remote_path,
                    progress,
                    progress_callback,
                )
            else:
                self._push_file(
                    local_path,
                    remote_path,
                    progress,
                    progress_callback,
                )

            return progress

        except TransferError:
            raise
        except Exception as e:
            raise TransferError(f"Push failed: {e}") from e

    def list_category_files(
        self,
        category_id: str,
    ) -> Iterator[FileInfo]:
        """
        List all files in a category.

        Args:
            category_id: Category ID.

        Yields:
            FileInfo for each file in the category.
        """
        category = get_category(category_id)
        if category is None:
            raise TransferError(f"Unknown category: {category_id}")

        if category.access_method != AccessMethod.AFC:
            raise TransferError(
                f"Category '{category.name}' requires backup access"
            )

        if not category.afc_paths:
            return

        for base_path in category.afc_paths:
            if not self._browser.exists(base_path):
                continue

            for dirpath, dirnames, filenames in self._browser.walk(base_path):
                for filename in filenames:
                    full_path = f"{dirpath.rstrip('/')}/{filename}"
                    try:
                        yield self._browser.stat(full_path)
                    except Exception:
                        pass

    def get_category_size(self, category_id: str) -> int:
        """
        Get total size of files in a category.

        Args:
            category_id: Category ID.

        Returns:
            Total size in bytes.
        """
        total = 0
        for file_info in self.list_category_files(category_id):
            if not file_info.is_directory:
                total += file_info.size
        return total

    def _pull_directory(
        self,
        remote_path: str,
        local_path: Path,
        progress: TransferProgress,
        callback: Optional[Callable[[TransferProgress], None]],
    ) -> None:
        """Pull a directory recursively."""
        local_path.mkdir(parents=True, exist_ok=True)

        # First pass: count files and sizes
        for dirpath, dirnames, filenames in self._browser.walk(remote_path):
            for filename in filenames:
                full_path = f"{dirpath.rstrip('/')}/{filename}"
                try:
                    info = self._browser.stat(full_path)
                    progress.total_files += 1
                    progress.total_bytes += info.size
                except Exception:
                    pass

        # Second pass: transfer files
        for dirpath, dirnames, filenames in self._browser.walk(remote_path):
            # Calculate relative path
            rel_dir = dirpath[len(remote_path):].lstrip("/")
            dest_dir = local_path / rel_dir if rel_dir else local_path
            dest_dir.mkdir(parents=True, exist_ok=True)

            for filename in filenames:
                full_path = f"{dirpath.rstrip('/')}/{filename}"
                dest_file = dest_dir / filename

                self._pull_file(full_path, dest_file, progress, callback)

    def _pull_file(
        self,
        remote_path: str,
        local_path: Path,
        progress: TransferProgress,
        callback: Optional[Callable[[TransferProgress], None]],
    ) -> None:
        """Pull a single file."""
        afc = self._ensure_connected()

        progress.current_file = remote_path

        try:
            # Get file size if not already counted
            if progress.total_files == 0:
                info = self._browser.stat(remote_path)
                progress.total_files = 1
                progress.total_bytes = info.size

            # Use AFC's pull method
            afc.pull(remote_path, str(local_path))

            # Update progress
            try:
                file_size = local_path.stat().st_size
                progress.completed_bytes += file_size
            except Exception:
                pass

            progress.completed_files += 1
            logger.debug(f"Pulled: {remote_path} -> {local_path}")

            if callback:
                callback(progress)

        except Exception as e:
            logger.warning(f"Failed to pull {remote_path}: {e}")
            progress.failed_files.append(remote_path)

    def _push_directory(
        self,
        local_path: Path,
        remote_path: str,
        progress: TransferProgress,
        callback: Optional[Callable[[TransferProgress], None]],
    ) -> None:
        """Push a directory recursively."""
        afc = self._ensure_connected()

        # Count files first
        for root, dirs, files in os.walk(local_path):
            for filename in files:
                local_file = Path(root) / filename
                progress.total_files += 1
                progress.total_bytes += local_file.stat().st_size

        # Create remote directory
        try:
            afc.makedirs(remote_path)
        except Exception:
            pass

        # Transfer files
        for root, dirs, files in os.walk(local_path):
            rel_dir = Path(root).relative_to(local_path)
            dest_dir = f"{remote_path.rstrip('/')}/{rel_dir}" if str(rel_dir) != "." else remote_path

            # Create subdirectories
            for dirname in dirs:
                try:
                    afc.makedirs(f"{dest_dir}/{dirname}")
                except Exception:
                    pass

            for filename in files:
                local_file = Path(root) / filename
                remote_file = f"{dest_dir}/{filename}"

                self._push_file(local_file, remote_file, progress, callback)

    def _push_file(
        self,
        local_path: Path,
        remote_path: str,
        progress: TransferProgress,
        callback: Optional[Callable[[TransferProgress], None]],
    ) -> None:
        """Push a single file."""
        afc = self._ensure_connected()

        progress.current_file = str(local_path)

        try:
            # Get file size if not already counted
            if progress.total_files == 0:
                progress.total_files = 1
                progress.total_bytes = local_path.stat().st_size

            # Use AFC's push method
            afc.push(str(local_path), remote_path)

            # Update progress
            progress.completed_bytes += local_path.stat().st_size
            progress.completed_files += 1
            logger.debug(f"Pushed: {local_path} -> {remote_path}")

            if callback:
                callback(progress)

        except Exception as e:
            logger.warning(f"Failed to push {local_path}: {e}")
            progress.failed_files.append(str(local_path))
