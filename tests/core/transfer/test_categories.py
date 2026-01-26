"""Tests for transfer categories."""

import pytest

from orange.core.transfer.categories import (
    DataCategory,
    AccessMethod,
    CATEGORIES,
    get_category,
    list_categories,
    get_afc_categories,
    get_backup_categories,
)


class TestAccessMethod:
    """Tests for AccessMethod enum."""

    def test_access_method_values(self) -> None:
        """All expected access methods should exist."""
        assert AccessMethod.AFC.value == "afc"
        assert AccessMethod.BACKUP.value == "backup"
        assert AccessMethod.SERVICE.value == "service"


class TestDataCategory:
    """Tests for DataCategory dataclass."""

    def test_category_creation(self) -> None:
        """DataCategory should be created with required fields."""
        category = DataCategory(
            id="test",
            name="Test Category",
            description="A test category",
            access_method=AccessMethod.AFC,
        )
        assert category.id == "test"
        assert category.name == "Test Category"
        assert category.access_method == AccessMethod.AFC

    def test_category_with_afc_paths(self) -> None:
        """DataCategory should accept AFC paths."""
        category = DataCategory(
            id="photos",
            name="Photos",
            description="Photos and videos",
            access_method=AccessMethod.AFC,
            afc_paths=["/DCIM", "/PhotoData"],
        )
        assert category.afc_paths == ["/DCIM", "/PhotoData"]

    def test_category_with_backup_domains(self) -> None:
        """DataCategory should accept backup domains."""
        category = DataCategory(
            id="messages",
            name="Messages",
            description="SMS and iMessage",
            access_method=AccessMethod.BACKUP,
            backup_domains=["HomeDomain"],
        )
        assert category.backup_domains == ["HomeDomain"]

    def test_category_defaults(self) -> None:
        """DataCategory should have expected defaults."""
        category = DataCategory(
            id="test",
            name="Test",
            description="Test",
            access_method=AccessMethod.AFC,
        )
        assert category.afc_paths is None
        assert category.backup_domains is None
        assert category.service_name is None
        assert category.requires_pairing is True
        assert category.requires_backup_password is False


class TestCategoriesDict:
    """Tests for the CATEGORIES dictionary."""

    def test_photos_category_exists(self) -> None:
        """Photos category should exist with correct properties."""
        assert "photos" in CATEGORIES
        photos = CATEGORIES["photos"]
        assert photos.name == "Photos & Videos"
        assert photos.access_method == AccessMethod.AFC
        assert "/DCIM" in photos.afc_paths

    def test_messages_category_exists(self) -> None:
        """Messages category should exist with backup access."""
        assert "messages" in CATEGORIES
        messages = CATEGORIES["messages"]
        assert messages.name == "Messages"
        assert messages.access_method == AccessMethod.BACKUP

    def test_music_category_exists(self) -> None:
        """Music category should exist with AFC access."""
        assert "music" in CATEGORIES
        music = CATEGORIES["music"]
        assert music.access_method == AccessMethod.AFC

    def test_health_requires_password(self) -> None:
        """Health category should require backup password."""
        assert "health" in CATEGORIES
        health = CATEGORIES["health"]
        assert health.requires_backup_password is True

    def test_keychain_requires_password(self) -> None:
        """Keychain category should require backup password."""
        assert "keychain" in CATEGORIES
        keychain = CATEGORIES["keychain"]
        assert keychain.requires_backup_password is True

    def test_all_categories_have_required_fields(self) -> None:
        """All categories should have required fields."""
        for cat_id, category in CATEGORIES.items():
            assert category.id == cat_id
            assert category.name
            assert category.description
            assert isinstance(category.access_method, AccessMethod)


class TestGetCategory:
    """Tests for get_category function."""

    def test_get_existing_category(self) -> None:
        """get_category should return category when found."""
        category = get_category("photos")
        assert category is not None
        assert category.id == "photos"

    def test_get_nonexistent_category(self) -> None:
        """get_category should return None when not found."""
        category = get_category("nonexistent")
        assert category is None

    def test_get_category_case_sensitive(self) -> None:
        """get_category should be case sensitive."""
        category = get_category("PHOTOS")
        assert category is None


class TestListCategories:
    """Tests for list_categories function."""

    def test_list_all_categories(self) -> None:
        """list_categories should return all categories when no filter."""
        categories = list_categories()
        assert len(categories) == len(CATEGORIES)

    def test_list_afc_categories(self) -> None:
        """list_categories should filter by AFC access method."""
        categories = list_categories(AccessMethod.AFC)
        assert all(c.access_method == AccessMethod.AFC for c in categories)
        assert any(c.id == "photos" for c in categories)

    def test_list_backup_categories(self) -> None:
        """list_categories should filter by BACKUP access method."""
        categories = list_categories(AccessMethod.BACKUP)
        assert all(c.access_method == AccessMethod.BACKUP for c in categories)
        assert any(c.id == "messages" for c in categories)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_afc_categories(self) -> None:
        """get_afc_categories should return AFC categories."""
        categories = get_afc_categories()
        assert all(c.access_method == AccessMethod.AFC for c in categories)
        assert len(categories) > 0

    def test_get_backup_categories(self) -> None:
        """get_backup_categories should return backup categories."""
        categories = get_backup_categories()
        assert all(c.access_method == AccessMethod.BACKUP for c in categories)
        assert len(categories) > 0
