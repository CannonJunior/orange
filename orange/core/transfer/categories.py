"""
Data categories for selective backup and transfer.

This module defines categories of data that can be backed up or
transferred from iOS devices, along with their access methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AccessMethod(Enum):
    """How to access this data category."""

    AFC = "afc"  # Direct file access via AFC
    BACKUP = "backup"  # Requires full/partial backup
    SERVICE = "service"  # Requires specific iOS service


@dataclass
class DataCategory:
    """
    Definition of a data category for backup/transfer.

    Attributes:
        id: Unique identifier for the category
        name: Human-readable name
        description: What this category contains
        access_method: How to access this data
        afc_paths: Paths accessible via AFC (if applicable)
        backup_domains: Backup domains containing this data (if applicable)
        service_name: iOS service name (if applicable)
        requires_pairing: Whether device must be paired
        requires_backup_password: Whether encrypted backup password is needed
    """

    id: str
    name: str
    description: str
    access_method: AccessMethod
    afc_paths: Optional[list[str]] = None
    backup_domains: Optional[list[str]] = None
    service_name: Optional[str] = None
    requires_pairing: bool = True
    requires_backup_password: bool = False


# Define available data categories
CATEGORIES: dict[str, DataCategory] = {
    "photos": DataCategory(
        id="photos",
        name="Photos & Videos",
        description="Camera roll photos and videos",
        access_method=AccessMethod.AFC,
        afc_paths=["/DCIM", "/PhotoData"],
    ),
    "downloads": DataCategory(
        id="downloads",
        name="Downloads",
        description="Downloaded files",
        access_method=AccessMethod.AFC,
        afc_paths=["/Downloads"],
    ),
    "books": DataCategory(
        id="books",
        name="Books",
        description="iBooks and PDFs",
        access_method=AccessMethod.AFC,
        afc_paths=["/Books"],
    ),
    "recordings": DataCategory(
        id="recordings",
        name="Voice Memos",
        description="Voice recordings",
        access_method=AccessMethod.AFC,
        afc_paths=["/Recordings"],
    ),
    "podcasts": DataCategory(
        id="podcasts",
        name="Podcasts",
        description="Downloaded podcast episodes",
        access_method=AccessMethod.AFC,
        afc_paths=["/iTunes_Control/iTunes/Podcasts"],
    ),
    "music": DataCategory(
        id="music",
        name="Music",
        description="Music library (purchased and synced)",
        access_method=AccessMethod.AFC,
        afc_paths=["/iTunes_Control/Music"],
    ),
    "messages": DataCategory(
        id="messages",
        name="Messages",
        description="SMS and iMessage conversations",
        access_method=AccessMethod.BACKUP,
        backup_domains=["HomeDomain"],
        requires_backup_password=False,  # True for full message history
    ),
    "contacts": DataCategory(
        id="contacts",
        name="Contacts",
        description="Address book contacts",
        access_method=AccessMethod.BACKUP,
        backup_domains=["HomeDomain"],
    ),
    "calendar": DataCategory(
        id="calendar",
        name="Calendar",
        description="Calendar events and reminders",
        access_method=AccessMethod.BACKUP,
        backup_domains=["HomeDomain"],
    ),
    "notes": DataCategory(
        id="notes",
        name="Notes",
        description="Notes app content",
        access_method=AccessMethod.BACKUP,
        backup_domains=["HomeDomain"],
    ),
    "safari": DataCategory(
        id="safari",
        name="Safari Data",
        description="Bookmarks, history, and reading list",
        access_method=AccessMethod.BACKUP,
        backup_domains=["HomeDomain"],
    ),
    "health": DataCategory(
        id="health",
        name="Health Data",
        description="Health and fitness data",
        access_method=AccessMethod.BACKUP,
        backup_domains=["HealthDomain"],
        requires_backup_password=True,
    ),
    "keychain": DataCategory(
        id="keychain",
        name="Keychain",
        description="Passwords and secure data",
        access_method=AccessMethod.BACKUP,
        backup_domains=["KeychainDomain"],
        requires_backup_password=True,
    ),
    "settings": DataCategory(
        id="settings",
        name="Settings",
        description="Device settings and preferences",
        access_method=AccessMethod.BACKUP,
        backup_domains=["SystemPreferencesDomain", "HomeDomain"],
    ),
    "apps": DataCategory(
        id="apps",
        name="App Data",
        description="Application data and documents",
        access_method=AccessMethod.BACKUP,
        backup_domains=["AppDomain", "AppDomainGroup"],
    ),
}


def get_category(category_id: str) -> Optional[DataCategory]:
    """
    Get a category by ID.

    Args:
        category_id: Category identifier

    Returns:
        DataCategory if found, None otherwise
    """
    return CATEGORIES.get(category_id)


def list_categories(access_method: Optional[AccessMethod] = None) -> list[DataCategory]:
    """
    List available categories.

    Args:
        access_method: Filter by access method

    Returns:
        List of matching categories
    """
    categories = list(CATEGORIES.values())

    if access_method:
        categories = [c for c in categories if c.access_method == access_method]

    return categories


def get_afc_categories() -> list[DataCategory]:
    """Get categories that can be accessed directly via AFC."""
    return list_categories(AccessMethod.AFC)


def get_backup_categories() -> list[DataCategory]:
    """Get categories that require backup access."""
    return list_categories(AccessMethod.BACKUP)
