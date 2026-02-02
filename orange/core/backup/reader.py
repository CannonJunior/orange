"""
Backup reader for parsing and extracting files from iOS backups.

This module provides functionality for reading backup contents,
extracting files, and querying backup databases.
"""

from __future__ import annotations

import logging
import plistlib
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from orange.core.backup.models import BackupFile, BackupInfo
from orange.exceptions import BackupError

logger = logging.getLogger(__name__)


class BackupReader:
    """
    Reads and parses iOS backup contents.

    Provides functionality for listing files, extracting specific files,
    and accessing backup databases.

    Example:
        reader = BackupReader("./backups/device-udid")

        # List all files
        for file in reader.list_files():
            print(f"{file.domain}: {file.relative_path}")

        # Extract a specific file
        reader.extract_file(file.file_id, "./extracted/")

        # Get a database
        db_path = reader.extract_database("HomeDomain", "Library/SMS/sms.db")
    """

    def __init__(
        self,
        backup_path: Path,
        password: Optional[str] = None,
    ):
        """
        Initialize backup reader.

        Args:
            backup_path: Path to the backup directory.
            password: Password for encrypted backups.

        Raises:
            BackupError: If backup path is invalid.
        """
        self._path = Path(backup_path)
        self._password = password
        self._manifest_db: Optional[Path] = None
        self._info: Optional[BackupInfo] = None
        self._is_encrypted: bool = False

        if not self._path.exists():
            raise BackupError(f"Backup path does not exist: {backup_path}")

        self._load_manifest()
        logger.debug(f"BackupReader initialized for {backup_path}")

    @property
    def path(self) -> Path:
        """Get the backup path."""
        return self._path

    @property
    def is_encrypted(self) -> bool:
        """Check if backup is encrypted."""
        return self._is_encrypted

    def _load_manifest(self) -> None:
        """Load and validate the manifest files."""
        manifest_plist = self._path / "Manifest.plist"
        manifest_db = self._path / "Manifest.db"

        if not manifest_plist.exists():
            raise BackupError("Manifest.plist not found - invalid backup")

        # Read manifest plist
        with open(manifest_plist, "rb") as f:
            manifest = plistlib.load(f)

        self._is_encrypted = manifest.get("IsEncrypted", False)

        if self._is_encrypted and not self._password:
            logger.warning("Backup is encrypted but no password provided")

        # Check for Manifest.db (iOS 10+)
        if manifest_db.exists():
            self._manifest_db = manifest_db
        else:
            # Older backup format uses Manifest.mbdb
            mbdb = self._path / "Manifest.mbdb"
            if mbdb.exists():
                raise BackupError(
                    "Legacy backup format (Manifest.mbdb) not supported. "
                    "Only iOS 10+ backups with Manifest.db are supported."
                )

    def get_info(self) -> BackupInfo:
        """
        Get backup metadata.

        Returns:
            BackupInfo with backup details.
        """
        if self._info is not None:
            return self._info

        from orange.core.backup.manager import BackupManager

        manager = BackupManager()
        self._info = manager.get_backup_info(self._path)
        return self._info

    def list_files(
        self,
        domain: Optional[str] = None,
        path_filter: Optional[str] = None,
    ) -> list[BackupFile]:
        """
        List files in the backup.

        Args:
            domain: Filter by domain (e.g., "HomeDomain", "CameraRollDomain").
            path_filter: Filter by path substring.

        Returns:
            List of BackupFile objects.
        """
        if self._manifest_db is None:
            raise BackupError("Manifest.db not found")

        files: list[BackupFile] = []

        try:
            conn = sqlite3.connect(str(self._manifest_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query
            query = "SELECT * FROM Files"
            params: list[Any] = []
            conditions: list[str] = []

            if domain:
                conditions.append("domain = ?")
                params.append(domain)

            if path_filter:
                conditions.append("relativePath LIKE ?")
                params.append(f"%{path_filter}%")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            cursor.execute(query, params)

            for row in cursor.fetchall():
                file_info = self._parse_file_row(row)
                if file_info:
                    files.append(file_info)

            conn.close()

        except sqlite3.Error as e:
            raise BackupError(f"Failed to read manifest: {e}") from e

        return files

    def list_domains(self) -> list[str]:
        """
        List all domains in the backup.

        Returns:
            List of domain names.
        """
        if self._manifest_db is None:
            raise BackupError("Manifest.db not found")

        try:
            conn = sqlite3.connect(str(self._manifest_db))
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT domain FROM Files ORDER BY domain")
            domains = [row[0] for row in cursor.fetchall()]
            conn.close()
            return domains

        except sqlite3.Error as e:
            raise BackupError(f"Failed to list domains: {e}") from e

    def get_file(self, file_id: str) -> Optional[BackupFile]:
        """
        Get a specific file by ID.

        Args:
            file_id: The file's identifier (hash).

        Returns:
            BackupFile if found, None otherwise.
        """
        if self._manifest_db is None:
            return None

        try:
            conn = sqlite3.connect(str(self._manifest_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Files WHERE fileID = ?", (file_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._parse_file_row(row)
            return None

        except sqlite3.Error:
            return None

    def extract_file(
        self,
        file_id: str,
        destination: Path,
        preserve_path: bool = False,
    ) -> Optional[Path]:
        """
        Extract a file from the backup.

        Args:
            file_id: The file's identifier.
            destination: Directory to extract to.
            preserve_path: Whether to preserve the domain/relative path structure.

        Returns:
            Path to extracted file, or None if not found.
        """
        file_info = self.get_file(file_id)
        if not file_info:
            logger.warning(f"File not found: {file_id}")
            return None

        # Find the actual file in backup
        # Files are stored as: backup_path / file_id[:2] / file_id
        source = self._path / file_id[:2] / file_id

        if not source.exists():
            # Try without subdirectory (older format)
            source = self._path / file_id
            if not source.exists():
                logger.warning(f"Backup file not found: {file_id}")
                return None

        # Determine destination path
        dest_dir = Path(destination)
        if preserve_path:
            dest_path = dest_dir / file_info.domain / file_info.relative_path
        else:
            dest_path = dest_dir / file_info.filename

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        if self._is_encrypted and self._password:
            # TODO: Implement decryption
            logger.warning("Encrypted file extraction not yet implemented")
            return None
        else:
            shutil.copy2(source, dest_path)

        logger.debug(f"Extracted {file_info.filename} to {dest_path}")
        return dest_path

    def extract_database(
        self,
        domain: str,
        relative_path: str,
        destination: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Extract a database file from the backup.

        Args:
            domain: The file's domain (e.g., "HomeDomain").
            relative_path: Relative path to the database.
            destination: Where to extract. If None, uses temp directory.

        Returns:
            Path to the extracted database, or None if not found.
        """
        # Find the file
        files = self.list_files(domain=domain, path_filter=relative_path)

        if not files:
            logger.warning(f"Database not found: {domain}/{relative_path}")
            return None

        # Find exact match
        target = None
        for f in files:
            if f.relative_path == relative_path:
                target = f
                break

        if not target:
            # Use first match
            target = files[0]

        # Extract to temp or specified location
        if destination is None:
            destination = Path(tempfile.mkdtemp(prefix="orange_backup_"))

        return self.extract_file(target.file_id, destination)

    def iter_files(
        self,
        domain: Optional[str] = None,
        batch_size: int = 1000,
    ) -> Iterator[BackupFile]:
        """
        Iterate over files in the backup (memory-efficient).

        Args:
            domain: Filter by domain.
            batch_size: Number of rows to fetch at a time.

        Yields:
            BackupFile objects.
        """
        if self._manifest_db is None:
            return

        try:
            conn = sqlite3.connect(str(self._manifest_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM Files"
            params: list[Any] = []

            if domain:
                query += " WHERE domain = ?"
                params.append(domain)

            cursor.execute(query, params)

            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break

                for row in rows:
                    file_info = self._parse_file_row(row)
                    if file_info:
                        yield file_info

            conn.close()

        except sqlite3.Error as e:
            logger.error(f"Error iterating files: {e}")

    def _parse_file_row(self, row: sqlite3.Row) -> Optional[BackupFile]:
        """Parse a database row into a BackupFile object."""
        try:
            # Parse the file blob if present
            file_blob = row["file"]
            flags = 0
            size = 0
            mode = 0
            modified_time = None

            if file_blob:
                # The file column contains a binary plist (NSKeyedArchiver format)
                try:
                    file_data = plistlib.loads(file_blob)

                    # Handle NSKeyedArchiver format where data is in $objects[1]
                    if "$objects" in file_data and len(file_data["$objects"]) > 1:
                        metadata = file_data["$objects"][1]
                        if isinstance(metadata, dict):
                            size = metadata.get("Size", 0)
                            mode = metadata.get("Mode", 0)
                            flags = metadata.get("Flags", 0)

                            # Parse modification time
                            mtime = metadata.get("LastModified")
                            if mtime:
                                modified_time = datetime.fromtimestamp(mtime)
                    else:
                        # Fallback for older backup formats
                        size = file_data.get("Size", 0)
                        mode = file_data.get("Mode", 0)
                        flags = file_data.get("Flags", 0)

                        mtime = file_data.get("LastModified")
                        if mtime:
                            modified_time = datetime.fromtimestamp(mtime)

                except Exception:
                    pass

            return BackupFile(
                file_id=row["fileID"],
                domain=row["domain"],
                relative_path=row["relativePath"],
                flags=flags,
                size=size,
                mode=mode,
                modified_time=modified_time,
                is_directory=(mode & 0o40000) != 0,
                is_encrypted=self._is_encrypted,
            )

        except Exception as e:
            logger.debug(f"Failed to parse file row: {e}")
            return None
