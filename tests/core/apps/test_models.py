"""Tests for app models."""

import pytest

from orange.core.apps.models import AppInfo, AppType, _format_size


class TestAppType:
    """Tests for AppType enum."""

    def test_app_type_values(self) -> None:
        """AppType should have expected values."""
        assert AppType.USER.value == "User"
        assert AppType.SYSTEM.value == "System"
        assert AppType.HIDDEN.value == "Hidden"
        assert AppType.ANY.value == "Any"


class TestAppInfo:
    """Tests for AppInfo dataclass."""

    def test_app_info_creation(self) -> None:
        """AppInfo should be created with required fields."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example App",
            version="1.0.0",
            short_version="1.0",
            app_type=AppType.USER,
        )
        assert app.bundle_id == "com.example.app"
        assert app.name == "Example App"
        assert app.version == "1.0.0"
        assert app.short_version == "1.0"
        assert app.app_type == AppType.USER

    def test_app_info_defaults(self) -> None:
        """AppInfo should have sensible defaults."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example App",
            version="1.0.0",
            short_version="1.0",
            app_type=AppType.USER,
        )
        assert app.path is None
        assert app.container_path is None
        assert app.size == 0
        assert app.data_size == 0
        assert app.is_sideloaded is False
        assert app.icon_files == []
        assert app.entitlements == {}
        assert app.extra == {}

    def test_size_human_bytes(self) -> None:
        """size_human should format bytes correctly."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example",
            version="1.0",
            short_version="1.0",
            app_type=AppType.USER,
            size=500,
        )
        assert "B" in app.size_human

    def test_size_human_kilobytes(self) -> None:
        """size_human should format kilobytes correctly."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example",
            version="1.0",
            short_version="1.0",
            app_type=AppType.USER,
            size=50 * 1024,
        )
        assert "KB" in app.size_human

    def test_size_human_megabytes(self) -> None:
        """size_human should format megabytes correctly."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example",
            version="1.0",
            short_version="1.0",
            app_type=AppType.USER,
            size=100 * 1024 * 1024,
        )
        assert "MB" in app.size_human

    def test_size_human_gigabytes(self) -> None:
        """size_human should format gigabytes correctly."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example",
            version="1.0",
            short_version="1.0",
            app_type=AppType.USER,
            size=2 * 1024 * 1024 * 1024,
        )
        assert "GB" in app.size_human

    def test_total_size(self) -> None:
        """total_size should sum app and data sizes."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example",
            version="1.0",
            short_version="1.0",
            app_type=AppType.USER,
            size=1000,
            data_size=500,
        )
        assert app.total_size == 1500

    def test_is_extractable_user_app(self) -> None:
        """User apps should be extractable."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example",
            version="1.0",
            short_version="1.0",
            app_type=AppType.USER,
        )
        assert app.is_extractable is True

    def test_is_extractable_system_app(self) -> None:
        """System apps should not be extractable."""
        app = AppInfo(
            bundle_id="com.apple.mobilesafari",
            name="Safari",
            version="1.0",
            short_version="1.0",
            app_type=AppType.SYSTEM,
        )
        assert app.is_extractable is False

    def test_to_dict(self) -> None:
        """to_dict should return all fields."""
        app = AppInfo(
            bundle_id="com.example.app",
            name="Example App",
            version="1.0.0",
            short_version="1.0",
            app_type=AppType.USER,
            size=1024,
            data_size=512,
        )
        d = app.to_dict()

        assert d["bundle_id"] == "com.example.app"
        assert d["name"] == "Example App"
        assert d["version"] == "1.0.0"
        assert d["short_version"] == "1.0"
        assert d["app_type"] == "User"
        assert d["size"] == 1024
        assert d["data_size"] == 512
        assert d["total_size"] == 1536
        assert "size_human" in d
        assert d["is_extractable"] is True


class TestFormatSize:
    """Tests for _format_size helper function."""

    def test_format_zero(self) -> None:
        """Should format zero bytes."""
        assert _format_size(0) == "0 B"

    def test_format_bytes(self) -> None:
        """Should format bytes."""
        assert "B" in _format_size(100)
        assert "100" in _format_size(100)

    def test_format_kilobytes(self) -> None:
        """Should format kilobytes."""
        assert "KB" in _format_size(2048)

    def test_format_megabytes(self) -> None:
        """Should format megabytes."""
        assert "MB" in _format_size(5 * 1024 * 1024)

    def test_format_gigabytes(self) -> None:
        """Should format gigabytes."""
        assert "GB" in _format_size(3 * 1024 * 1024 * 1024)

    def test_format_terabytes(self) -> None:
        """Should format terabytes."""
        assert "TB" in _format_size(2 * 1024 * 1024 * 1024 * 1024)
