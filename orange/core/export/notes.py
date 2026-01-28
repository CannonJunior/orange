"""
Notes exporter for iOS backups.

Parses the Notes database from iOS backups and exports
notes to various formats.
"""

from __future__ import annotations

import csv
import html
import json
import logging
import re
import sqlite3
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from orange.constants import APPLE_EPOCH_OFFSET
from orange.core.backup.reader import BackupReader
from orange.core.export.models import Note
from orange.exceptions import ExportError

logger = logging.getLogger(__name__)

# iOS Notes database location - varies by iOS version
NOTES_DB_DOMAIN = "HomeDomain"
NOTES_DB_PATHS = [
    "Library/Notes/notes.sqlite",  # iOS 9+
    "Library/Notes/NotesV7.storedata",  # iOS 9+
    "Library/Notes/NotesV6.storedata",  # iOS 8
    "Library/Notes/NotesV4.storedata",  # iOS 7
]


class NoteExporter:
    """
    Exports notes from iOS backups.

    Parses the Notes database and exports notes to JSON, CSV,
    or HTML formats.

    Example:
        reader = BackupReader("/path/to/backup")
        exporter = NoteExporter(reader)

        # Get all notes
        notes = exporter.get_notes()

        # Export to HTML
        exporter.export_html(notes, Path("./notes.html"))
    """

    def __init__(self, backup_reader: BackupReader):
        """
        Initialize notes exporter.

        Args:
            backup_reader: BackupReader instance for the backup.
        """
        self._reader = backup_reader
        self._db_path: Optional[Path] = None
        self._db_version: Optional[str] = None
        self._folders: dict[int, str] = {}  # folder_id -> name
        self._accounts: dict[int, str] = {}  # account_id -> name

    def _ensure_database(self) -> Path:
        """
        Extract and return path to Notes database.

        Returns:
            Path to the extracted database file.

        Raises:
            ExportError: If database cannot be extracted.
        """
        if self._db_path and self._db_path.exists():
            return self._db_path

        # Try each possible database path
        for db_path in NOTES_DB_PATHS:
            extracted = self._reader.extract_database(NOTES_DB_DOMAIN, db_path)
            if extracted and extracted.exists():
                self._db_path = extracted
                self._db_version = db_path
                self._load_metadata()
                return extracted

        raise ExportError(
            f"Could not extract Notes database from backup. "
            f"Make sure the backup contains notes data in {NOTES_DB_DOMAIN}/"
        )

    def _load_metadata(self) -> None:
        """Load folder and account information."""
        if not self._db_path:
            return

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            # Try to load folders
            try:
                cursor.execute(
                    "SELECT Z_PK, ZTITLE FROM ZICCLOUDSYNCINGOBJECT "
                    "WHERE ZTITLE IS NOT NULL"
                )
                for row in cursor.fetchall():
                    self._folders[row[0]] = row[1]
            except sqlite3.Error:
                # Different schema, try alternative
                try:
                    cursor.execute("SELECT ROWID, name FROM NoteFolder")
                    for row in cursor.fetchall():
                        self._folders[row[0]] = row[1]
                except sqlite3.Error:
                    pass

            # Try to load accounts
            try:
                cursor.execute(
                    "SELECT Z_PK, ZNAME FROM ZICCLOUDSYNCINGOBJECT "
                    "WHERE ZNAME IS NOT NULL"
                )
                for row in cursor.fetchall():
                    self._accounts[row[0]] = row[1]
            except sqlite3.Error:
                pass

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not load notes metadata: {e}")

    def _parse_date(self, date_value: Optional[float]) -> Optional[datetime]:
        """Parse iOS timestamp to datetime."""
        if date_value is None:
            return None

        try:
            # Notes uses seconds since Apple epoch (like Core Data)
            unix_timestamp = date_value + APPLE_EPOCH_OFFSET
            return datetime.fromtimestamp(unix_timestamp)
        except (ValueError, OSError):
            return None

    def _detect_schema(self, conn: sqlite3.Connection) -> str:
        """Detect the database schema version."""
        cursor = conn.cursor()

        # Check for iOS 9+ schema (Core Data)
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='ZICCLOUDSYNCINGOBJECT'"
            )
            if cursor.fetchone():
                return "ios9plus"
        except sqlite3.Error:
            pass

        # Check for older schema
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='note'"
            )
            if cursor.fetchone():
                return "legacy"
        except sqlite3.Error:
            pass

        return "unknown"

    def get_notes(
        self,
        folder_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Note]:
        """
        Get notes from the backup.

        Args:
            folder_id: Filter by specific folder.
            search: Search string for note title/content.
            limit: Maximum number of notes to return.

        Returns:
            List of Note objects.
        """
        self._ensure_database()
        notes: list[Note] = []

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row

            schema = self._detect_schema(conn)

            if schema == "ios9plus":
                notes = self._get_notes_ios9plus(
                    conn, folder_id, search, limit
                )
            elif schema == "legacy":
                notes = self._get_notes_legacy(conn, folder_id, search, limit)
            else:
                logger.warning(f"Unknown Notes database schema")

            conn.close()

        except sqlite3.Error as e:
            raise ExportError(f"Failed to read notes: {e}") from e

        return notes

    def _get_notes_ios9plus(
        self,
        conn: sqlite3.Connection,
        folder_id: Optional[int],
        search: Optional[str],
        limit: Optional[int],
    ) -> list[Note]:
        """Get notes from iOS 9+ database schema."""
        notes: list[Note] = []
        cursor = conn.cursor()

        # iOS 9+ uses Core Data with ZICCLOUDSYNCINGOBJECT table
        query = """
            SELECT
                note.Z_PK as note_id,
                note.ZTITLE as title,
                note.ZSNIPPET as snippet,
                note.ZCREATIONDATE as created,
                note.ZMODIFICATIONDATE as modified,
                note.ZFOLDER as folder_id,
                note.ZACCOUNT as account_id,
                note.ZISPINNED as is_pinned,
                note.ZISPASSWORDPROTECTED as is_locked,
                notedata.ZDATA as content_data
            FROM ZICCLOUDSYNCINGOBJECT note
            LEFT JOIN ZICNOTEDATA notedata ON note.ZNOTEDATA = notedata.Z_PK
            WHERE note.ZTITLE IS NOT NULL
        """

        params: list[Any] = []

        if folder_id is not None:
            query += " AND note.ZFOLDER = ?"
            params.append(folder_id)

        if search:
            query += " AND (note.ZTITLE LIKE ? OR note.ZSNIPPET LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])

        query += " ORDER BY note.ZMODIFICATIONDATE DESC"

        if limit:
            query += f" LIMIT {limit}"

        try:
            cursor.execute(query, params)

            for row in cursor.fetchall():
                note = self._parse_note_ios9plus(row)
                if note:
                    notes.append(note)

        except sqlite3.Error as e:
            logger.warning(f"Error querying iOS 9+ notes: {e}")

        return notes

    def _parse_note_ios9plus(self, row: sqlite3.Row) -> Optional[Note]:
        """Parse a note from iOS 9+ database."""
        try:
            # Extract content from compressed data if available
            content = ""
            content_data = row["content_data"]

            if content_data:
                content = self._extract_note_content(content_data)
            elif row["snippet"]:
                content = row["snippet"]

            folder_name = self._folders.get(row["folder_id"])
            account_name = self._accounts.get(row["account_id"])

            return Note(
                note_id=row["note_id"],
                title=row["title"] or "Untitled",
                content=content,
                created_date=self._parse_date(row["created"]),
                modified_date=self._parse_date(row["modified"]),
                folder_name=folder_name,
                folder_id=row["folder_id"],
                is_pinned=bool(row["is_pinned"]),
                is_locked=bool(row["is_locked"]),
                account_name=account_name,
            )

        except Exception as e:
            logger.debug(f"Failed to parse note: {e}")
            return None

    def _extract_note_content(self, data: bytes) -> str:
        """
        Extract text content from note data.

        iOS stores note content as compressed protobuf data.
        We attempt to decompress and extract readable text.
        """
        try:
            # Try gzip decompression
            try:
                decompressed = zlib.decompress(data, zlib.MAX_WBITS | 16)
                data = decompressed
            except zlib.error:
                # Try raw deflate
                try:
                    decompressed = zlib.decompress(data, -zlib.MAX_WBITS)
                    data = decompressed
                except zlib.error:
                    pass

            # Extract printable text from the data
            # The actual format is protobuf, but we can extract readable text
            text = self._extract_text_from_bytes(data)
            return text

        except Exception as e:
            logger.debug(f"Could not extract note content: {e}")
            return ""

    def _extract_text_from_bytes(self, data: bytes) -> str:
        """Extract readable text from bytes."""
        # Try to decode as UTF-8
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = data.decode("latin-1", errors="ignore")

        # Remove non-printable characters but keep newlines
        text = "".join(
            char for char in text
            if char.isprintable() or char in "\n\r\t"
        )

        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    def _get_notes_legacy(
        self,
        conn: sqlite3.Connection,
        folder_id: Optional[int],
        search: Optional[str],
        limit: Optional[int],
    ) -> list[Note]:
        """Get notes from legacy database schema (iOS 8 and earlier)."""
        notes: list[Note] = []
        cursor = conn.cursor()

        query = """
            SELECT
                note.ROWID as note_id,
                note.title,
                note_body.content as content,
                note.creation_date as created,
                note.modification_date as modified
            FROM note
            LEFT JOIN note_body ON note.ROWID = note_body.note_id
        """

        params: list[Any] = []

        if search:
            query += " WHERE (note.title LIKE ? OR note_body.content LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])

        query += " ORDER BY note.modification_date DESC"

        if limit:
            query += f" LIMIT {limit}"

        try:
            cursor.execute(query, params)

            for row in cursor.fetchall():
                # Legacy format has simpler structure
                note = Note(
                    note_id=row["note_id"],
                    title=row["title"] or "Untitled",
                    content=row["content"] or "",
                    created_date=self._parse_date(row["created"]),
                    modified_date=self._parse_date(row["modified"]),
                )
                notes.append(note)

        except sqlite3.Error as e:
            logger.warning(f"Error querying legacy notes: {e}")

        return notes

    def get_folders(self) -> list[dict[str, Any]]:
        """
        Get list of note folders.

        Returns:
            List of dicts with folder info.
        """
        self._ensure_database()
        folders: list[dict[str, Any]] = []

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Try iOS 9+ query
            try:
                cursor.execute("""
                    SELECT
                        f.Z_PK as folder_id,
                        f.ZTITLE as title,
                        COUNT(n.Z_PK) as note_count
                    FROM ZICCLOUDSYNCINGOBJECT f
                    LEFT JOIN ZICCLOUDSYNCINGOBJECT n ON n.ZFOLDER = f.Z_PK
                    WHERE f.ZTITLE IS NOT NULL
                    GROUP BY f.Z_PK
                    ORDER BY f.ZTITLE
                """)

                for row in cursor.fetchall():
                    folders.append({
                        "folder_id": row["folder_id"],
                        "title": row["title"],
                        "note_count": row["note_count"],
                    })

            except sqlite3.Error:
                # Try legacy query
                cursor.execute("""
                    SELECT ROWID as folder_id, name as title FROM NoteFolder
                """)
                for row in cursor.fetchall():
                    folders.append({
                        "folder_id": row["folder_id"],
                        "title": row["title"],
                        "note_count": 0,
                    })

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not list folders: {e}")

        return folders

    def get_statistics(self) -> dict[str, Any]:
        """
        Get notes statistics.

        Returns:
            Dict with statistics including total notes,
            folders, pinned count, etc.
        """
        self._ensure_database()
        stats: dict[str, Any] = {
            "total_notes": 0,
            "total_folders": len(self._folders),
            "pinned_notes": 0,
            "locked_notes": 0,
            "first_note": None,
            "last_note": None,
        }

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            schema = self._detect_schema(conn)

            if schema == "ios9plus":
                # Count notes
                cursor.execute(
                    "SELECT COUNT(*) FROM ZICCLOUDSYNCINGOBJECT "
                    "WHERE ZTITLE IS NOT NULL"
                )
                stats["total_notes"] = cursor.fetchone()[0]

                # Pinned notes
                cursor.execute(
                    "SELECT COUNT(*) FROM ZICCLOUDSYNCINGOBJECT "
                    "WHERE ZISPINNED = 1"
                )
                stats["pinned_notes"] = cursor.fetchone()[0]

                # Locked notes
                cursor.execute(
                    "SELECT COUNT(*) FROM ZICCLOUDSYNCINGOBJECT "
                    "WHERE ZISPASSWORDPROTECTED = 1"
                )
                stats["locked_notes"] = cursor.fetchone()[0]

                # Date range
                cursor.execute("""
                    SELECT MIN(ZCREATIONDATE), MAX(ZMODIFICATIONDATE)
                    FROM ZICCLOUDSYNCINGOBJECT WHERE ZTITLE IS NOT NULL
                """)
                row = cursor.fetchone()
                if row[0]:
                    stats["first_note"] = self._parse_date(row[0])
                if row[1]:
                    stats["last_note"] = self._parse_date(row[1])

            elif schema == "legacy":
                cursor.execute("SELECT COUNT(*) FROM note")
                stats["total_notes"] = cursor.fetchone()[0]

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not get statistics: {e}")

        return stats

    def export_json(
        self,
        notes: list[Note],
        output_path: Path,
        pretty: bool = True,
    ) -> Path:
        """
        Export notes to JSON format.

        Args:
            notes: List of notes to export.
            output_path: Path for output file.
            pretty: Whether to format with indentation.

        Returns:
            Path to the created file.
        """
        data = {
            "export_date": datetime.now().isoformat(),
            "note_count": len(notes),
            "notes": [n.to_dict() for n in notes],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)

        logger.info(f"Exported {len(notes)} notes to {output_path}")
        return output_path

    def export_csv(
        self,
        notes: list[Note],
        output_path: Path,
    ) -> Path:
        """
        Export notes to CSV format.

        Args:
            notes: List of notes to export.
            output_path: Path for output file.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                "Title",
                "Content",
                "Folder",
                "Created",
                "Modified",
                "Pinned",
                "Locked",
            ])

            # Write notes
            for note in notes:
                # Truncate content for CSV
                content_preview = note.content[:1000]
                if len(note.content) > 1000:
                    content_preview += "..."

                writer.writerow([
                    note.title,
                    content_preview,
                    note.folder_name or "",
                    (note.created_date.isoformat()
                     if note.created_date else ""),
                    (note.modified_date.isoformat()
                     if note.modified_date else ""),
                    "Yes" if note.is_pinned else "No",
                    "Yes" if note.is_locked else "No",
                ])

        logger.info(f"Exported {len(notes)} notes to {output_path}")
        return output_path

    def export_html(
        self,
        notes: list[Note],
        output_path: Path,
        title: str = "Notes Export",
    ) -> Path:
        """
        Export notes to HTML format.

        Args:
            notes: List of notes to export.
            output_path: Path for output file.
            title: Page title.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self._generate_html(notes, title)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Exported {len(notes)} notes to {output_path}")
        return output_path

    def _generate_html(self, notes: list[Note], title: str) -> str:
        """Generate HTML content for notes."""
        css = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                             Roboto, Helvetica, Arial, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background: #fefcf3;
            }
            h1 { color: #333; }
            .stats { color: #666; margin-bottom: 30px; font-size: 14px; }
            .note {
                background: #fff;
                border: 1px solid #e0ddd4;
                border-radius: 8px;
                margin: 20px 0;
                padding: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            }
            .note-title {
                font-size: 18px;
                font-weight: 600;
                color: #333;
                margin: 0 0 10px 0;
            }
            .note-meta {
                font-size: 12px;
                color: #888;
                margin-bottom: 15px;
            }
            .note-meta span {
                margin-right: 15px;
            }
            .note-content {
                white-space: pre-wrap;
                line-height: 1.6;
                color: #444;
            }
            .badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
                margin-left: 8px;
            }
            .badge-pinned { background: #fff3cd; color: #856404; }
            .badge-locked { background: #f8d7da; color: #721c24; }
        </style>
        """

        notes_html = []
        for note in notes:
            badges = ""
            if note.is_pinned:
                badges += '<span class="badge badge-pinned">Pinned</span>'
            if note.is_locked:
                badges += '<span class="badge badge-locked">Locked</span>'

            folder_info = f" | {note.folder_name}" if note.folder_name else ""
            date_info = ""
            if note.modified_date:
                date_info = note.modified_date.strftime("%Y-%m-%d %H:%M")
            elif note.created_date:
                date_info = note.created_date.strftime("%Y-%m-%d %H:%M")

            content_escaped = html.escape(note.content)

            notes_html.append(f"""
                <div class="note">
                    <h2 class="note-title">
                        {html.escape(note.title)}{badges}
                    </h2>
                    <div class="note-meta">
                        <span>{date_info}</span>
                        <span>{folder_info}</span>
                    </div>
                    <div class="note-content">{content_escaped}</div>
                </div>
            """)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)}</title>
    {css}
</head>
<body>
    <h1>{html.escape(title)}</h1>
    <div class="stats">
        Exported {len(notes)} notes on {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </div>
    {''.join(notes_html)}
</body>
</html>
"""
