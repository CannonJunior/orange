"""
Message exporter for iOS backups.

Parses the SMS/iMessage database (sms.db) from iOS backups and
exports messages to various formats.
"""

from __future__ import annotations

import csv
import html
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from orange.constants import APPLE_EPOCH_OFFSET, MESSAGE_DATE_DIVISOR
from orange.core.backup.reader import BackupReader
from orange.core.export.models import (
    Message,
    MessageAttachment,
    MessageDirection,
    MessageType,
)
from orange.exceptions import ExportError

logger = logging.getLogger(__name__)

# iOS SMS database location
SMS_DB_DOMAIN = "HomeDomain"
SMS_DB_PATH = "Library/SMS/sms.db"


class MessageExporter:
    """
    Exports messages from iOS backups.

    Parses the sms.db SQLite database and exports messages to
    JSON, CSV, or HTML formats.

    Example:
        reader = BackupReader("/path/to/backup")
        exporter = MessageExporter(reader)

        # Get all messages
        messages = exporter.get_messages()

        # Export to JSON
        exporter.export_json(messages, Path("./messages.json"))

        # Export conversation with specific contact
        conv = exporter.get_conversation("+1234567890")
        exporter.export_html(conv, Path("./conversation.html"))
    """

    def __init__(self, backup_reader: BackupReader):
        """
        Initialize message exporter.

        Args:
            backup_reader: BackupReader instance for the backup.
        """
        self._reader = backup_reader
        self._db_path: Optional[Path] = None
        self._handles: dict[int, str] = {}  # handle_id -> identifier
        self._chats: dict[int, dict] = {}  # chat_id -> chat info

    def _ensure_database(self) -> Path:
        """
        Extract and return path to SMS database.

        Returns:
            Path to the extracted sms.db file.

        Raises:
            ExportError: If database cannot be extracted.
        """
        if self._db_path and self._db_path.exists():
            return self._db_path

        db_path = self._reader.extract_database(SMS_DB_DOMAIN, SMS_DB_PATH)
        if not db_path:
            raise ExportError(
                f"Could not extract SMS database from backup. "
                f"Make sure the backup contains {SMS_DB_DOMAIN}/{SMS_DB_PATH}"
            )

        self._db_path = db_path
        self._load_handles()
        self._load_chats()
        return db_path

    def _load_handles(self) -> None:
        """Load phone number/email handles from database."""
        if not self._db_path:
            return

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            # Handle table maps ROWID to phone numbers/emails
            cursor.execute("SELECT ROWID, id FROM handle")
            for row in cursor.fetchall():
                self._handles[row[0]] = row[1]

            conn.close()
            logger.debug(f"Loaded {len(self._handles)} message handles")

        except sqlite3.Error as e:
            logger.warning(f"Could not load handles: {e}")

    def _load_chats(self) -> None:
        """Load chat information from database."""
        if not self._db_path:
            return

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get chat info including participants
            cursor.execute("""
                SELECT
                    c.ROWID,
                    c.chat_identifier,
                    c.display_name,
                    c.service_name
                FROM chat c
            """)

            for row in cursor.fetchall():
                self._chats[row["ROWID"]] = {
                    "identifier": row["chat_identifier"],
                    "display_name": row["display_name"],
                    "service": row["service_name"],
                }

            conn.close()
            logger.debug(f"Loaded {len(self._chats)} chats")

        except sqlite3.Error as e:
            logger.warning(f"Could not load chats: {e}")

    def _parse_date(self, date_value: Optional[int]) -> Optional[datetime]:
        """
        Parse iOS date value to datetime.

        iOS stores dates as nanoseconds since Apple epoch (Jan 1, 2001)
        in newer versions, or seconds in older versions.
        """
        if not date_value or date_value == 0:
            return None

        try:
            # Check if it's nanoseconds (very large number) or seconds
            if date_value > 1_000_000_000_000:
                # Nanoseconds - divide to get seconds
                seconds = date_value / MESSAGE_DATE_DIVISOR
            else:
                # Already in seconds
                seconds = date_value

            # Add Apple epoch offset to get Unix timestamp
            unix_timestamp = seconds + APPLE_EPOCH_OFFSET
            return datetime.fromtimestamp(unix_timestamp)

        except (ValueError, OSError) as e:
            logger.debug(f"Could not parse date {date_value}: {e}")
            return None

    def _get_message_type(self, service: Optional[str]) -> MessageType:
        """Determine message type from service name."""
        if service:
            service_lower = service.lower()
            if "imessage" in service_lower:
                return MessageType.IMESSAGE
            elif "sms" in service_lower:
                return MessageType.SMS
            elif "mms" in service_lower:
                return MessageType.MMS
        return MessageType.SMS

    def get_messages(
        self,
        chat_id: Optional[int] = None,
        contact: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[Message]:
        """
        Get messages from the backup.

        Args:
            chat_id: Filter by specific chat/conversation.
            contact: Filter by contact phone/email (partial match).
            start_date: Filter messages after this date.
            end_date: Filter messages before this date.
            limit: Maximum number of messages to return.

        Returns:
            List of Message objects.
        """
        self._ensure_database()
        messages: list[Message] = []

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query joining message with chat_message_join
            query = """
                SELECT
                    m.ROWID as message_id,
                    m.text,
                    m.date,
                    m.date_read,
                    m.date_delivered,
                    m.is_from_me,
                    m.is_read,
                    m.is_delivered,
                    m.service,
                    m.subject,
                    m.handle_id,
                    cmj.chat_id
                FROM message m
                LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            """

            conditions: list[str] = []
            params: list[Any] = []

            if chat_id is not None:
                conditions.append("cmj.chat_id = ?")
                params.append(chat_id)

            if contact:
                # Find handles matching contact
                matching_handles = [
                    h_id for h_id, identifier in self._handles.items()
                    if contact.lower() in identifier.lower()
                ]
                if matching_handles:
                    placeholders = ",".join("?" * len(matching_handles))
                    conditions.append(f"m.handle_id IN ({placeholders})")
                    params.extend(matching_handles)
                else:
                    # No matching handles - return empty
                    return []

            if start_date:
                # Convert to Apple timestamp
                unix_ts = start_date.timestamp()
                apple_ts = (unix_ts - APPLE_EPOCH_OFFSET) * MESSAGE_DATE_DIVISOR
                conditions.append("m.date >= ?")
                params.append(int(apple_ts))

            if end_date:
                unix_ts = end_date.timestamp()
                apple_ts = (unix_ts - APPLE_EPOCH_OFFSET) * MESSAGE_DATE_DIVISOR
                conditions.append("m.date <= ?")
                params.append(int(apple_ts))

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY m.date ASC"

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, params)

            for row in cursor.fetchall():
                message = self._parse_message_row(row)
                if message:
                    messages.append(message)

            conn.close()

        except sqlite3.Error as e:
            raise ExportError(f"Failed to read messages: {e}") from e

        # Load attachments for messages
        self._load_attachments(messages)

        return messages

    def _parse_message_row(self, row: sqlite3.Row) -> Optional[Message]:
        """Parse a database row into a Message object."""
        try:
            is_from_me = bool(row["is_from_me"])
            handle_id = row["handle_id"]

            # Determine sender/recipient
            other_party = self._handles.get(handle_id, "Unknown")
            if is_from_me:
                sender = "Me"
                recipient = other_party
                direction = MessageDirection.SENT
            else:
                sender = other_party
                recipient = "Me"
                direction = MessageDirection.RECEIVED

            return Message(
                message_id=row["message_id"],
                text=row["text"],
                date=self._parse_date(row["date"]) or datetime.now(),
                date_read=self._parse_date(row["date_read"]),
                date_delivered=self._parse_date(row["date_delivered"]),
                direction=direction,
                message_type=self._get_message_type(row["service"]),
                sender=sender,
                recipient=recipient,
                chat_id=row["chat_id"],
                is_read=bool(row["is_read"]),
                is_delivered=bool(row["is_delivered"]),
                subject=row["subject"],
                service=row["service"],
            )

        except Exception as e:
            logger.debug(f"Failed to parse message row: {e}")
            return None

    def _load_attachments(self, messages: list[Message]) -> None:
        """Load attachments for a list of messages."""
        if not messages or not self._db_path:
            return

        message_ids = [m.message_id for m in messages]
        message_map = {m.message_id: m for m in messages}

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get attachments linked to our messages
            placeholders = ",".join("?" * len(message_ids))
            cursor.execute(f"""
                SELECT
                    a.ROWID as attachment_id,
                    a.filename,
                    a.mime_type,
                    a.transfer_state,
                    a.total_bytes,
                    maj.message_id
                FROM attachment a
                JOIN message_attachment_join maj ON a.ROWID = maj.attachment_id
                WHERE maj.message_id IN ({placeholders})
            """, message_ids)

            for row in cursor.fetchall():
                msg = message_map.get(row["message_id"])
                if msg:
                    attachment = MessageAttachment(
                        attachment_id=row["attachment_id"],
                        filename=row["filename"],
                        mime_type=row["mime_type"],
                        size=row["total_bytes"] or 0,
                        transfer_state=row["transfer_state"] or 0,
                    )
                    msg.attachments.append(attachment)

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not load attachments: {e}")

    def get_conversations(self) -> list[dict[str, Any]]:
        """
        Get list of all conversations.

        Returns:
            List of conversation info dicts with keys:
            - chat_id: Conversation ID
            - identifier: Phone/email identifier
            - display_name: Display name if set
            - service: Service type (iMessage, SMS)
            - message_count: Number of messages
        """
        self._ensure_database()
        conversations: list[dict[str, Any]] = []

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    c.ROWID as chat_id,
                    c.chat_identifier,
                    c.display_name,
                    c.service_name,
                    COUNT(cmj.message_id) as message_count
                FROM chat c
                LEFT JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
                GROUP BY c.ROWID
                ORDER BY MAX(cmj.message_date) DESC
            """)

            for row in cursor.fetchall():
                conversations.append({
                    "chat_id": row["chat_id"],
                    "identifier": row["chat_identifier"],
                    "display_name": row["display_name"] or row["chat_identifier"],
                    "service": row["service_name"],
                    "message_count": row["message_count"],
                })

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not list conversations: {e}")

        return conversations

    def get_conversation(self, identifier: str) -> list[Message]:
        """
        Get all messages in a conversation by identifier.

        Args:
            identifier: Phone number or email address.

        Returns:
            List of messages in the conversation.
        """
        return self.get_messages(contact=identifier)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get message statistics.

        Returns:
            Dict with statistics including total messages, sent/received
            counts, and date range.
        """
        self._ensure_database()
        stats: dict[str, Any] = {
            "total_messages": 0,
            "sent_messages": 0,
            "received_messages": 0,
            "total_attachments": 0,
            "conversations": len(self._chats),
            "contacts": len(self._handles),
            "first_message": None,
            "last_message": None,
        }

        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()

            # Total and sent/received counts
            cursor.execute("SELECT COUNT(*) FROM message")
            stats["total_messages"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM message WHERE is_from_me = 1")
            stats["sent_messages"] = cursor.fetchone()[0]

            stats["received_messages"] = (
                stats["total_messages"] - stats["sent_messages"]
            )

            # Attachment count
            cursor.execute("SELECT COUNT(*) FROM attachment")
            stats["total_attachments"] = cursor.fetchone()[0]

            # Date range
            cursor.execute("SELECT MIN(date), MAX(date) FROM message")
            row = cursor.fetchone()
            if row[0]:
                stats["first_message"] = self._parse_date(row[0])
            if row[1]:
                stats["last_message"] = self._parse_date(row[1])

            conn.close()

        except sqlite3.Error as e:
            logger.warning(f"Could not get statistics: {e}")

        return stats

    def export_json(
        self,
        messages: list[Message],
        output_path: Path,
        pretty: bool = True,
    ) -> Path:
        """
        Export messages to JSON format.

        Args:
            messages: List of messages to export.
            output_path: Path for output file.
            pretty: Whether to format with indentation.

        Returns:
            Path to the created file.
        """
        data = {
            "export_date": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": [m.to_dict() for m in messages],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)

        logger.info(f"Exported {len(messages)} messages to {output_path}")
        return output_path

    def export_csv(
        self,
        messages: list[Message],
        output_path: Path,
    ) -> Path:
        """
        Export messages to CSV format.

        Args:
            messages: List of messages to export.
            output_path: Path for output file.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                "Date",
                "Direction",
                "Type",
                "Sender",
                "Recipient",
                "Text",
                "Subject",
                "Attachments",
            ])

            # Write messages
            for msg in messages:
                writer.writerow([
                    msg.date.isoformat() if msg.date else "",
                    msg.direction.value,
                    msg.message_type.value,
                    msg.sender or "",
                    msg.recipient or "",
                    msg.text or "",
                    msg.subject or "",
                    len(msg.attachments),
                ])

        logger.info(f"Exported {len(messages)} messages to {output_path}")
        return output_path

    def export_html(
        self,
        messages: list[Message],
        output_path: Path,
        title: str = "Messages Export",
    ) -> Path:
        """
        Export messages to HTML format with chat-style layout.

        Args:
            messages: List of messages to export.
            output_path: Path for output file.
            title: Page title.

        Returns:
            Path to the created file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self._generate_html(messages, title)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Exported {len(messages)} messages to {output_path}")
        return output_path

    def _generate_html(self, messages: list[Message], title: str) -> str:
        """Generate HTML content for messages."""
        # CSS for chat-style layout
        css = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                             Roboto, Helvetica, Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            h1 { color: #333; margin-bottom: 5px; }
            .stats { color: #666; margin-bottom: 20px; font-size: 14px; }
            .message {
                margin: 10px 0;
                padding: 10px 15px;
                border-radius: 18px;
                max-width: 70%;
                clear: both;
            }
            .sent {
                background: #007aff;
                color: white;
                float: right;
            }
            .received {
                background: #e9e9eb;
                color: #333;
                float: left;
            }
            .message-text { margin: 0; word-wrap: break-word; }
            .message-meta {
                font-size: 11px;
                margin-top: 5px;
                opacity: 0.7;
            }
            .sent .message-meta { color: #cce5ff; }
            .clearfix { clear: both; }
            .date-divider {
                text-align: center;
                color: #888;
                font-size: 12px;
                margin: 20px 0;
                clear: both;
            }
            .attachment {
                font-size: 12px;
                font-style: italic;
                margin-top: 5px;
            }
        </style>
        """

        # Build message HTML
        message_html = []
        last_date = None

        for msg in messages:
            # Add date divider if day changed
            msg_date = msg.date.date() if msg.date else None
            if msg_date and msg_date != last_date:
                message_html.append(
                    f'<div class="date-divider">'
                    f'{msg.date.strftime("%B %d, %Y")}</div>'
                )
                last_date = msg_date

            # Message bubble
            direction_class = (
                "sent" if msg.direction == MessageDirection.SENT else "received"
            )
            text_escaped = html.escape(msg.text or "[No text]")
            time_str = msg.date.strftime("%H:%M") if msg.date else ""

            attachment_html = ""
            if msg.attachments:
                attachment_html = (
                    f'<div class="attachment">'
                    f'[{len(msg.attachments)} attachment(s)]</div>'
                )

            message_html.append(f'''
                <div class="message {direction_class}">
                    <p class="message-text">{text_escaped}</p>
                    {attachment_html}
                    <div class="message-meta">{time_str}</div>
                </div>
                <div class="clearfix"></div>
            ''')

        # Combine into full HTML
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
        Exported {len(messages)} messages on {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </div>
    {''.join(message_html)}
</body>
</html>
"""
