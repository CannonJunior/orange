"""
Data export module for iOS backup extraction.

This module provides functionality for extracting and exporting
data from iOS backups, including messages, contacts, calendar events,
and notes.
"""

from orange.core.export.models import (
    Message,
    MessageAttachment,
    Contact,
    ContactPhone,
    ContactEmail,
    ContactAddress,
    CalendarEvent,
    Note,
)
from orange.core.export.messages import MessageExporter
from orange.core.export.contacts import ContactExporter
from orange.core.export.calendar import CalendarExporter
from orange.core.export.notes import NoteExporter

__all__ = [
    # Models
    "Message",
    "MessageAttachment",
    "Contact",
    "ContactPhone",
    "ContactEmail",
    "ContactAddress",
    "CalendarEvent",
    "Note",
    # Exporters
    "MessageExporter",
    "ContactExporter",
    "CalendarExporter",
    "NoteExporter",
]
