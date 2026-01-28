"""
Data models for exported iOS data.

This module contains dataclasses representing messages, contacts,
calendar events, and notes extracted from iOS backups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MessageType(Enum):
    """Type of message."""

    SMS = "sms"
    IMESSAGE = "imessage"
    MMS = "mms"


class MessageDirection(Enum):
    """Direction of message flow."""

    SENT = "sent"
    RECEIVED = "received"


@dataclass
class MessageAttachment:
    """
    Attachment in a message.

    Attributes:
        attachment_id: Unique identifier for the attachment.
        filename: Original filename.
        mime_type: MIME type of the attachment.
        file_path: Path in backup (for extraction).
        size: Size in bytes.
        transfer_state: 0=complete, 1=pending, etc.
    """

    attachment_id: int
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_path: Optional[str] = None
    size: int = 0
    transfer_state: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attachment_id": self.attachment_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "file_path": self.file_path,
            "size": self.size,
        }


@dataclass
class Message:
    """
    A text message (SMS or iMessage).

    Attributes:
        message_id: Unique message identifier.
        text: Message content.
        date: When the message was sent/received.
        date_read: When the message was read (if applicable).
        direction: Whether sent or received.
        message_type: SMS, iMessage, or MMS.
        sender: Sender phone number or email.
        recipient: Recipient(s).
        chat_id: Conversation identifier.
        is_read: Whether the message has been read.
        attachments: List of attachments.
    """

    message_id: int
    text: Optional[str]
    date: datetime
    direction: MessageDirection
    message_type: MessageType
    sender: Optional[str] = None
    recipient: Optional[str] = None
    chat_id: Optional[int] = None
    date_read: Optional[datetime] = None
    date_delivered: Optional[datetime] = None
    is_read: bool = True
    is_delivered: bool = True
    subject: Optional[str] = None
    service: Optional[str] = None
    attachments: list[MessageAttachment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "text": self.text,
            "date": self.date.isoformat() if self.date else None,
            "date_read": self.date_read.isoformat() if self.date_read else None,
            "direction": self.direction.value,
            "message_type": self.message_type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "chat_id": self.chat_id,
            "is_read": self.is_read,
            "subject": self.subject,
            "service": self.service,
            "attachments": [a.to_dict() for a in self.attachments],
        }


@dataclass
class ContactPhone:
    """Phone number for a contact."""

    number: str
    label: str = "mobile"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"number": self.number, "label": self.label}


@dataclass
class ContactEmail:
    """Email address for a contact."""

    email: str
    label: str = "home"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"email": self.email, "label": self.label}


@dataclass
class ContactAddress:
    """Physical address for a contact."""

    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    label: str = "home"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "label": self.label,
        }

    def format_single_line(self) -> str:
        """Format address as single line."""
        parts = []
        if self.street:
            parts.append(self.street)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass
class Contact:
    """
    A contact from the address book.

    Attributes:
        contact_id: Unique contact identifier.
        first_name: First name.
        last_name: Last name.
        organization: Company/organization name.
        phones: List of phone numbers.
        emails: List of email addresses.
        addresses: List of physical addresses.
        birthday: Birthday date.
        notes: Contact notes.
    """

    contact_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    nickname: Optional[str] = None
    organization: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    phones: list[ContactPhone] = field(default_factory=list)
    emails: list[ContactEmail] = field(default_factory=list)
    addresses: list[ContactAddress] = field(default_factory=list)
    birthday: Optional[datetime] = None
    notes: Optional[str] = None
    image_data: Optional[bytes] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

    @property
    def display_name(self) -> str:
        """Get full display name."""
        parts = []
        if self.prefix:
            parts.append(self.prefix)
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        if self.last_name:
            parts.append(self.last_name)
        if self.suffix:
            parts.append(self.suffix)

        name = " ".join(parts)
        if not name and self.organization:
            return self.organization
        if not name and self.nickname:
            return self.nickname
        return name or "Unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "contact_id": self.contact_id,
            "display_name": self.display_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "middle_name": self.middle_name,
            "prefix": self.prefix,
            "suffix": self.suffix,
            "nickname": self.nickname,
            "organization": self.organization,
            "department": self.department,
            "job_title": self.job_title,
            "phones": [p.to_dict() for p in self.phones],
            "emails": [e.to_dict() for e in self.emails],
            "addresses": [a.to_dict() for a in self.addresses],
            "birthday": self.birthday.isoformat() if self.birthday else None,
            "notes": self.notes,
            "created_date": (
                self.created_date.isoformat() if self.created_date else None
            ),
            "modified_date": (
                self.modified_date.isoformat() if self.modified_date else None
            ),
        }


@dataclass
class CalendarEvent:
    """
    A calendar event.

    Attributes:
        event_id: Unique event identifier.
        title: Event title/summary.
        start_date: Event start date/time.
        end_date: Event end date/time.
        location: Event location.
        notes: Event description/notes.
        all_day: Whether this is an all-day event.
        calendar_name: Name of the calendar.
    """

    event_id: int
    title: str
    start_date: datetime
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    all_day: bool = False
    calendar_name: Optional[str] = None
    calendar_id: Optional[int] = None
    recurrence_rule: Optional[str] = None
    url: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "title": self.title,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "location": self.location,
            "notes": self.notes,
            "all_day": self.all_day,
            "calendar_name": self.calendar_name,
            "recurrence_rule": self.recurrence_rule,
            "url": self.url,
        }


@dataclass
class Note:
    """
    A note from the Notes app.

    Attributes:
        note_id: Unique note identifier.
        title: Note title.
        content: Note text content.
        created_date: When the note was created.
        modified_date: When the note was last modified.
        folder_name: Folder containing the note.
    """

    note_id: int
    title: str
    content: str
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    folder_name: Optional[str] = None
    folder_id: Optional[int] = None
    is_pinned: bool = False
    is_locked: bool = False
    account_name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "note_id": self.note_id,
            "title": self.title,
            "content": self.content,
            "created_date": (
                self.created_date.isoformat() if self.created_date else None
            ),
            "modified_date": (
                self.modified_date.isoformat() if self.modified_date else None
            ),
            "folder_name": self.folder_name,
            "is_pinned": self.is_pinned,
            "is_locked": self.is_locked,
            "account_name": self.account_name,
        }
