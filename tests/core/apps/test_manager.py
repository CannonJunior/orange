"""Tests for app manager."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile

from orange.core.apps.manager import AppManager, AppExtractionError
from orange.core.apps.models import AppInfo, AppType
from orange.exceptions import DeviceNotFoundError


class TestAppManager:
    """Tests for AppManager class."""

    @pytest.fixture
    def mock_installation_proxy(self) -> Mock:
        """Create a mock InstallationProxyService."""
        mock = Mock()
        mock.get_apps.return_value = {
            "com.example.app": {
                "CFBundleDisplayName": "Example App",
                "CFBundleName": "Example",
                "CFBundleVersion": "1.0.0",
                "CFBundleShortVersionString": "1.0",
                "ApplicationType": "User",
                "Path": "/var/containers/Bundle/Application/UUID/Example.app",
                "Container": "/var/mobile/Containers/Data/Application/UUID",
                "StaticDiskUsage": 1024000,
                "DynamicDiskUsage": 512000,
                "MinimumOSVersion": "14.0",
                "CFBundleExecutable": "Example",
            },
            "com.netflix.Netflix": {
                "CFBundleDisplayName": "Netflix",
                "CFBundleName": "Netflix",
                "CFBundleVersion": "18.14.0",
                "CFBundleShortVersionString": "18.14",
                "ApplicationType": "User",
                "Path": "/var/containers/Bundle/Application/UUID/Netflix.app",
                "Container": "/var/mobile/Containers/Data/Application/UUID",
                "StaticDiskUsage": 150000000,
                "DynamicDiskUsage": 50000000,
                "MinimumOSVersion": "15.0",
                "CFBundleExecutable": "Netflix",
                "iTunesMetadata": {"some": "data"},
            },
        }
        mock.close = Mock()
        return mock

    @pytest.fixture
    def mock_lockdown(self) -> Mock:
        """Create a mock lockdown client."""
        return Mock()

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_ensure_connected(
        self, mock_proxy_class, mock_create_lockdown, mock_lockdown
    ) -> None:
        """_ensure_connected should establish connection."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy = Mock()
        mock_proxy_class.return_value = mock_proxy

        manager = AppManager("test-udid")
        result = manager._ensure_connected()

        mock_create_lockdown.assert_called_once_with("test-udid")
        assert result == mock_proxy

    @patch("orange.core.apps.manager.create_lockdown_client")
    def test_ensure_connected_device_not_found(
        self, mock_create_lockdown
    ) -> None:
        """_ensure_connected should raise DeviceNotFoundError."""
        mock_create_lockdown.side_effect = Exception("No device")

        manager = AppManager("invalid-udid")
        with pytest.raises(DeviceNotFoundError):
            manager._ensure_connected()

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_list_apps(
        self,
        mock_proxy_class,
        mock_create_lockdown,
        mock_lockdown,
        mock_installation_proxy,
    ) -> None:
        """list_apps should return list of AppInfo."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy_class.return_value = mock_installation_proxy

        manager = AppManager("test-udid")
        apps = manager.list_apps()

        assert len(apps) == 2
        assert all(isinstance(app, AppInfo) for app in apps)
        mock_installation_proxy.get_apps.assert_called_once()

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_list_apps_by_type(
        self,
        mock_proxy_class,
        mock_create_lockdown,
        mock_lockdown,
        mock_installation_proxy,
    ) -> None:
        """list_apps should filter by app type."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy_class.return_value = mock_installation_proxy

        manager = AppManager("test-udid")
        manager.list_apps(app_type=AppType.USER)

        mock_installation_proxy.get_apps.assert_called_with(
            application_type="User",
            calculate_sizes=True,
            bundle_identifiers=None,
        )

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_get_app(
        self,
        mock_proxy_class,
        mock_create_lockdown,
        mock_lockdown,
        mock_installation_proxy,
    ) -> None:
        """get_app should return AppInfo for specific bundle ID."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_installation_proxy.get_apps.return_value = {
            "com.netflix.Netflix": {
                "CFBundleDisplayName": "Netflix",
                "CFBundleVersion": "18.14.0",
                "CFBundleShortVersionString": "18.14",
                "ApplicationType": "User",
            },
        }
        mock_proxy_class.return_value = mock_installation_proxy

        manager = AppManager("test-udid")
        app = manager.get_app("com.netflix.Netflix")

        assert app is not None
        assert app.bundle_id == "com.netflix.Netflix"
        assert app.name == "Netflix"

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_get_app_not_found(
        self, mock_proxy_class, mock_create_lockdown, mock_lockdown
    ) -> None:
        """get_app should return None for unknown bundle ID."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy = Mock()
        mock_proxy.get_apps.return_value = {}
        mock_proxy_class.return_value = mock_proxy

        manager = AppManager("test-udid")
        app = manager.get_app("com.nonexistent.app")

        assert app is None

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_search_apps(
        self,
        mock_proxy_class,
        mock_create_lockdown,
        mock_lockdown,
        mock_installation_proxy,
    ) -> None:
        """search_apps should find apps by name."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy_class.return_value = mock_installation_proxy

        manager = AppManager("test-udid")
        results = manager.search_apps("netflix")

        assert len(results) == 1
        assert results[0].name == "Netflix"

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_search_apps_by_bundle_id(
        self,
        mock_proxy_class,
        mock_create_lockdown,
        mock_lockdown,
        mock_installation_proxy,
    ) -> None:
        """search_apps should find apps by bundle ID."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy_class.return_value = mock_installation_proxy

        manager = AppManager("test-udid")
        results = manager.search_apps("com.example")

        assert len(results) == 1
        assert results[0].bundle_id == "com.example.app"

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_context_manager(
        self, mock_proxy_class, mock_create_lockdown, mock_lockdown
    ) -> None:
        """AppManager should work as context manager."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy = Mock()
        mock_proxy_class.return_value = mock_proxy

        with AppManager("test-udid") as manager:
            manager._ensure_connected()

        mock_proxy.close.assert_called()

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_parse_app_info_user_app(
        self, mock_proxy_class, mock_create_lockdown, mock_lockdown
    ) -> None:
        """_parse_app_info should correctly parse user app."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy_class.return_value = Mock()

        manager = AppManager("test-udid")
        info = {
            "CFBundleDisplayName": "Test App",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0",
            "ApplicationType": "User",
            "StaticDiskUsage": 1000,
            "DynamicDiskUsage": 500,
        }

        app = manager._parse_app_info("com.test.app", info)

        assert app.bundle_id == "com.test.app"
        assert app.name == "Test App"
        assert app.app_type == AppType.USER
        assert app.size == 1000
        assert app.data_size == 500
        assert app.is_sideloaded is True  # No iTunesMetadata

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_parse_app_info_app_store(
        self, mock_proxy_class, mock_create_lockdown, mock_lockdown
    ) -> None:
        """_parse_app_info should detect App Store apps."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy_class.return_value = Mock()

        manager = AppManager("test-udid")
        info = {
            "CFBundleDisplayName": "App Store App",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0",
            "ApplicationType": "User",
            "iTunesMetadata": {"some": "data"},
        }

        app = manager._parse_app_info("com.appstore.app", info)

        assert app.is_sideloaded is False  # Has iTunesMetadata

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_extract_ipa_app_not_found(
        self, mock_proxy_class, mock_create_lockdown, mock_lockdown
    ) -> None:
        """extract_ipa should raise error for unknown app."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy = Mock()
        mock_proxy.get_apps.return_value = {}
        mock_proxy_class.return_value = mock_proxy

        manager = AppManager("test-udid")

        with pytest.raises(AppExtractionError, match="App not found"):
            manager.extract_ipa("com.nonexistent.app", Path("./test.ipa"))

    @patch("orange.core.apps.manager.create_lockdown_client")
    @patch("orange.core.apps.manager.InstallationProxyService")
    def test_extract_ipa_system_app(
        self, mock_proxy_class, mock_create_lockdown, mock_lockdown
    ) -> None:
        """extract_ipa should raise error for system apps."""
        mock_create_lockdown.return_value = mock_lockdown
        mock_proxy = Mock()
        mock_proxy.get_apps.return_value = {
            "com.apple.mobilesafari": {
                "CFBundleDisplayName": "Safari",
                "CFBundleVersion": "1.0",
                "CFBundleShortVersionString": "1.0",
                "ApplicationType": "System",
            },
        }
        mock_proxy_class.return_value = mock_proxy

        manager = AppManager("test-udid")

        with pytest.raises(AppExtractionError, match="Cannot extract system app"):
            manager.extract_ipa("com.apple.mobilesafari", Path("./Safari.ipa"))
