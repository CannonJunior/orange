"""Tests for export data models."""

import pytest
from datetime import datetime

from orange.core.export.models import (
    Message,
    MessageAttachment,
    MessageDirection,
    MessageType,
    Contact,
    ContactPhone,
    ContactEmail,
    ContactAddress,
    CalendarEvent,
    Note,
)


class TestMessageAttachment:
    """Tests for MessageAttachment dataclass."""

    def test_attachment_creation(self) -> None:
        """MessageAttachment should be created with required fields."""
        attachment = MessageAttachment(
            attachment_id=1,
            filename="photo.jpg",
            mime_type="image/jpeg",
            size=1024,
        )
        assert attachment.attachment_id == 1
        assert attachment.filename == "photo.jpg"
        assert attachment.mime_type == "image/jpeg"
        assert attachment.size == 1024

    def test_attachment_to_dict(self) -> None:
        """to_dict should return all fields."""
        attachment = MessageAttachment(
            attachment_id=1,
            filename="photo.jpg",
            mime_type="image/jpeg",
            size=1024,
        )
        d = attachment.to_dict()
        assert d["attachment_id"] == 1
        assert d["filename"] == "photo.jpg"


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self) -> None:
        """Message should be created with required fields."""
        msg = Message(
            message_id=123,
            text="Hello world",
            date=datetime(2024, 1, 15, 10, 30),
            direction=MessageDirection.SENT,
            message_type=MessageType.IMESSAGE,
        )
        assert msg.message_id == 123
        assert msg.text == "Hello world"
        assert msg.direction == MessageDirection.SENT
        assert msg.message_type == MessageType.IMESSAGE

    def test_message_defaults(self) -> None:
        """Message should have sensible defaults."""
        msg = Message(
            message_id=1,
            text="Test",
            date=datetime.now(),
            direction=MessageDirection.RECEIVED,
            message_type=MessageType.SMS,
        )
        assert msg.sender is None
        assert msg.recipient is None
        assert msg.attachments == []
        assert msg.is_read is True

    def test_message_to_dict(self) -> None:
        """to_dict should return all fields."""
        msg = Message(
            message_id=1,
            text="Test message",
            date=datetime(2024, 1, 15, 10, 30),
            direction=MessageDirection.SENT,
            message_type=MessageType.IMESSAGE,
            sender="Me",
            recipient="+1234567890",
        )
        d = msg.to_dict()
        assert d["message_id"] == 1
        assert d["text"] == "Test message"
        assert d["direction"] == "sent"
        assert d["message_type"] == "imessage"
        assert d["sender"] == "Me"

    def test_message_with_attachments(self) -> None:
        """Message should handle attachments."""
        attachment = MessageAttachment(
            attachment_id=1,
            filename="photo.jpg",
            mime_type="image/jpeg",
        )
        msg = Message(
            message_id=1,
            text="Check this out",
            date=datetime.now(),
            direction=MessageDirection.SENT,
            message_type=MessageType.IMESSAGE,
            attachments=[attachment],
        )
        assert len(msg.attachments) == 1
        d = msg.to_dict()
        assert len(d["attachments"]) == 1


class TestContactPhone:
    """Tests for ContactPhone dataclass."""

    def test_phone_creation(self) -> None:
        """ContactPhone should be created correctly."""
        phone = ContactPhone(number="+1234567890", label="mobile")
        assert phone.number == "+1234567890"
        assert phone.label == "mobile"

    def test_phone_to_dict(self) -> None:
        """to_dict should return all fields."""
        phone = ContactPhone(number="+1234567890", label="work")
        d = phone.to_dict()
        assert d["number"] == "+1234567890"
        assert d["label"] == "work"


class TestContactEmail:
    """Tests for ContactEmail dataclass."""

    def test_email_creation(self) -> None:
        """ContactEmail should be created correctly."""
        email = ContactEmail(email="test@example.com", label="home")
        assert email.email == "test@example.com"
        assert email.label == "home"


class TestContactAddress:
    """Tests for ContactAddress dataclass."""

    def test_address_creation(self) -> None:
        """ContactAddress should be created correctly."""
        addr = ContactAddress(
            street="123 Main St",
            city="San Francisco",
            state="CA",
            postal_code="94105",
            country="USA",
        )
        assert addr.street == "123 Main St"
        assert addr.city == "San Francisco"

    def test_format_single_line(self) -> None:
        """format_single_line should create comma-separated address."""
        addr = ContactAddress(
            street="123 Main St",
            city="San Francisco",
            state="CA",
            postal_code="94105",
        )
        formatted = addr.format_single_line()
        assert "123 Main St" in formatted
        assert "San Francisco" in formatted
        assert "CA" in formatted

    def test_format_single_line_partial(self) -> None:
        """format_single_line should handle missing fields."""
        addr = ContactAddress(city="San Francisco", state="CA")
        formatted = addr.format_single_line()
        assert formatted == "San Francisco, CA"


class TestContact:
    """Tests for Contact dataclass."""

    def test_contact_creation(self) -> None:
        """Contact should be created with required fields."""
        contact = Contact(
            contact_id=1,
            first_name="John",
            last_name="Doe",
        )
        assert contact.contact_id == 1
        assert contact.first_name == "John"
        assert contact.last_name == "Doe"

    def test_contact_defaults(self) -> None:
        """Contact should have sensible defaults."""
        contact = Contact(contact_id=1)
        assert contact.phones == []
        assert contact.emails == []
        assert contact.addresses == []
        assert contact.notes is None

    def test_display_name_full(self) -> None:
        """display_name should combine name parts."""
        contact = Contact(
            contact_id=1,
            first_name="John",
            middle_name="Q",
            last_name="Doe",
        )
        assert contact.display_name == "John Q Doe"

    def test_display_name_first_only(self) -> None:
        """display_name should work with first name only."""
        contact = Contact(contact_id=1, first_name="John")
        assert contact.display_name == "John"

    def test_display_name_organization(self) -> None:
        """display_name should fall back to organization."""
        contact = Contact(contact_id=1, organization="Acme Corp")
        assert contact.display_name == "Acme Corp"

    def test_display_name_unknown(self) -> None:
        """display_name should return Unknown for empty contact."""
        contact = Contact(contact_id=1)
        assert contact.display_name == "Unknown"

    def test_contact_to_dict(self) -> None:
        """to_dict should return all fields."""
        contact = Contact(
            contact_id=1,
            first_name="John",
            last_name="Doe",
            phones=[ContactPhone("+1234567890", "mobile")],
            emails=[ContactEmail("john@example.com", "home")],
        )
        d = contact.to_dict()
        assert d["contact_id"] == 1
        assert d["display_name"] == "John Doe"
        assert len(d["phones"]) == 1
        assert len(d["emails"]) == 1


class TestCalendarEvent:
    """Tests for CalendarEvent dataclass."""

    def test_event_creation(self) -> None:
        """CalendarEvent should be created with required fields."""
        event = CalendarEvent(
            event_id=1,
            title="Team Meeting",
            start_date=datetime(2024, 1, 15, 10, 0),
            end_date=datetime(2024, 1, 15, 11, 0),
        )
        assert event.event_id == 1
        assert event.title == "Team Meeting"
        assert event.start_date.hour == 10

    def test_event_defaults(self) -> None:
        """CalendarEvent should have sensible defaults."""
        event = CalendarEvent(
            event_id=1,
            title="Test",
            start_date=datetime.now(),
        )
        assert event.all_day is False
        assert event.location is None
        assert event.notes is None

    def test_event_to_dict(self) -> None:
        """to_dict should return all fields."""
        event = CalendarEvent(
            event_id=1,
            title="Team Meeting",
            start_date=datetime(2024, 1, 15, 10, 0),
            location="Conference Room A",
        )
        d = event.to_dict()
        assert d["event_id"] == 1
        assert d["title"] == "Team Meeting"
        assert d["location"] == "Conference Room A"


class TestNote:
    """Tests for Note dataclass."""

    def test_note_creation(self) -> None:
        """Note should be created with required fields."""
        note = Note(
            note_id=1,
            title="My Note",
            content="This is the content",
        )
        assert note.note_id == 1
        assert note.title == "My Note"
        assert note.content == "This is the content"

    def test_note_defaults(self) -> None:
        """Note should have sensible defaults."""
        note = Note(note_id=1, title="Test", content="Content")
        assert note.is_pinned is False
        assert note.is_locked is False
        assert note.folder_name is None

    def test_note_to_dict(self) -> None:
        """to_dict should return all fields."""
        note = Note(
            note_id=1,
            title="My Note",
            content="Content here",
            is_pinned=True,
            folder_name="Personal",
        )
        d = note.to_dict()
        assert d["note_id"] == 1
        assert d["title"] == "My Note"
        assert d["is_pinned"] is True
        assert d["folder_name"] == "Personal"


class TestMessageDirection:
    """Tests for MessageDirection enum."""

    def test_direction_values(self) -> None:
        """MessageDirection should have expected values."""
        assert MessageDirection.SENT.value == "sent"
        assert MessageDirection.RECEIVED.value == "received"


class TestMessageType:
    """Tests for MessageType enum."""

    def test_type_values(self) -> None:
        """MessageType should have expected values."""
        assert MessageType.SMS.value == "sms"
        assert MessageType.IMESSAGE.value == "imessage"
        assert MessageType.MMS.value == "mms"
