"""Tests for Frida client."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from orange.core.apps.decrypt.frida_client import (
    FridaClient,
    FridaDeviceInfo,
    FridaAppInfo,
    _get_frida,
)
from orange.core.apps.decrypt.exceptions import (
    FridaConnectionError,
    FridaNotInstalledError,
    AppNotFoundError,
    AppNotRunningError,
)


class TestFridaDeviceInfo:
    """Test FridaDeviceInfo dataclass."""

    def test_from_frida_device_usb(self):
        """Should create info from USB Frida device."""
        mock_device = Mock()
        mock_device.id = "00008030-12345678"
        mock_device.name = "iPhone"
        mock_device.type = "usb"

        info = FridaDeviceInfo.from_frida_device(mock_device)

        assert info.id == "00008030-12345678"
        assert info.name == "iPhone"
        assert info.type == "usb"
        assert info.udid == "00008030-12345678"

    def test_from_frida_device_remote(self):
        """Should create info from remote Frida device."""
        mock_device = Mock()
        mock_device.id = "remote-device"
        mock_device.name = "Remote iPhone"
        mock_device.type = "remote"

        info = FridaDeviceInfo.from_frida_device(mock_device)

        assert info.type == "remote"
        assert info.udid is None


class TestFridaAppInfo:
    """Test FridaAppInfo dataclass."""

    def test_from_frida_app(self):
        """Should create info from Frida app object."""
        mock_app = Mock()
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example App"
        mock_app.pid = 1234

        info = FridaAppInfo.from_frida_app(mock_app)

        assert info.identifier == "com.example.app"
        assert info.name == "Example App"
        assert info.pid == 1234

    def test_from_frida_app_not_running(self):
        """Should handle app without pid attribute."""
        mock_app = Mock(spec=["identifier", "name"])
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example App"

        info = FridaAppInfo.from_frida_app(mock_app)

        assert info.pid == 0


class TestFridaClientInit:
    """Test FridaClient initialization."""

    def test_init_with_udid(self):
        """Should store UDID."""
        client = FridaClient(udid="00008030-12345678")
        assert client.udid == "00008030-12345678"
        assert client.host is None

    def test_init_with_host(self):
        """Should store remote host."""
        client = FridaClient(host="localhost:27042")
        assert client.host == "localhost:27042"
        assert client.udid is None

    def test_init_defaults(self):
        """Should have None defaults."""
        client = FridaClient()
        assert client.udid is None
        assert client.host is None


class TestFridaClientConnect:
    """Test FridaClient connection methods."""

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_connect_via_usb(self, mock_get_frida):
        """Should connect via USB with UDID."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_device.name = "iPhone"
        mock_frida.get_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient(udid="00008030-12345678")
        result = client.connect()

        assert result is client  # Returns self
        assert client.is_connected
        mock_frida.get_device.assert_called_once_with("00008030-12345678")

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_connect_auto_detect(self, mock_get_frida):
        """Should auto-detect USB device when no UDID."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_device.name = "iPhone"
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()

        assert client.is_connected
        mock_frida.get_usb_device.assert_called_once_with(timeout=5)

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_connect_remote(self, mock_get_frida):
        """Should connect to remote host."""
        mock_frida = Mock()
        mock_device_manager = Mock()
        mock_device = Mock()
        mock_device.name = "Remote iPhone"
        mock_device_manager.add_remote_device.return_value = mock_device
        mock_frida.get_device_manager.return_value = mock_device_manager
        mock_get_frida.return_value = mock_frida

        client = FridaClient(host="localhost:27042")
        client.connect()

        assert client.is_connected
        mock_device_manager.add_remote_device.assert_called_once_with("localhost:27042")

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_connect_timeout_raises(self, mock_get_frida):
        """Should raise FridaConnectionError on timeout."""
        # Create proper exception classes
        class MockTimedOutError(Exception):
            pass

        class MockServerNotRunningError(Exception):
            pass

        class MockInvalidArgumentError(Exception):
            pass

        mock_frida = Mock()
        mock_frida.TimedOutError = MockTimedOutError
        mock_frida.ServerNotRunningError = MockServerNotRunningError
        mock_frida.InvalidArgumentError = MockInvalidArgumentError
        mock_frida.get_usb_device.side_effect = MockTimedOutError()
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        with pytest.raises(FridaConnectionError):
            client.connect()

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_connect_server_not_running_raises(self, mock_get_frida):
        """Should raise FridaConnectionError when server not running."""
        class MockServerNotRunningError(Exception):
            pass

        class MockTimedOutError(Exception):
            pass

        class MockInvalidArgumentError(Exception):
            pass

        mock_frida = Mock()
        mock_frida.ServerNotRunningError = MockServerNotRunningError
        mock_frida.TimedOutError = MockTimedOutError
        mock_frida.InvalidArgumentError = MockInvalidArgumentError
        mock_frida.get_usb_device.side_effect = MockServerNotRunningError()
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        with pytest.raises(FridaConnectionError) as exc_info:
            client.connect()

        assert "not running" in str(exc_info.value).lower()


class TestFridaClientDeviceProperty:
    """Test device property access."""

    def test_device_not_connected_raises(self):
        """Should raise when accessing device before connect."""
        client = FridaClient()
        with pytest.raises(FridaConnectionError):
            _ = client.device

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_device_returns_connected_device(self, mock_get_frida):
        """Should return device after connect."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()

        assert client.device is mock_device


class TestFridaClientListDevices:
    """Test device listing."""

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_list_devices(self, mock_get_frida):
        """Should list available Frida devices."""
        mock_frida = Mock()
        mock_usb_device = Mock()
        mock_usb_device.id = "usb-device"
        mock_usb_device.name = "USB iPhone"
        mock_usb_device.type = "usb"

        mock_local_device = Mock()
        mock_local_device.id = "local"
        mock_local_device.name = "Local"
        mock_local_device.type = "local"

        mock_frida.enumerate_devices.return_value = [mock_usb_device, mock_local_device]
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        devices = client.list_devices()

        # Should filter out local device
        assert len(devices) == 1
        assert devices[0].id == "usb-device"


class TestFridaClientAppOperations:
    """Test app-related operations."""

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_get_installed_apps(self, mock_get_frida):
        """Should enumerate installed apps."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_app = Mock()
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example"
        mock_app.pid = 0
        mock_device.enumerate_applications.return_value = [mock_app]
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        apps = client.get_installed_apps()

        assert len(apps) == 1
        assert apps[0].identifier == "com.example.app"

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_get_app_info_found(self, mock_get_frida):
        """Should return app info when found."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_app = Mock()
        mock_app.identifier = "com.netflix.Netflix"
        mock_app.name = "Netflix"
        mock_app.pid = 1234
        mock_device.enumerate_applications.return_value = [mock_app]
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        info = client.get_app_info("com.netflix.Netflix")

        assert info is not None
        assert info.identifier == "com.netflix.Netflix"

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_get_app_info_not_found(self, mock_get_frida):
        """Should return None when app not found."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_device.enumerate_applications.return_value = []
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        info = client.get_app_info("com.nonexistent.app")

        assert info is None


class TestFridaClientSpawn:
    """Test app spawning."""

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_spawn_success(self, mock_get_frida):
        """Should spawn and attach to app."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_session = Mock()

        mock_app = Mock()
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example"
        mock_app.pid = 0
        mock_device.enumerate_applications.return_value = [mock_app]
        mock_device.spawn.return_value = 1234
        mock_device.attach.return_value = mock_session

        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        session = client.spawn("com.example.app")

        assert session is mock_session
        mock_device.spawn.assert_called_once_with(["com.example.app"])
        mock_device.attach.assert_called_once_with(1234)
        mock_device.resume.assert_called_once_with(1234)

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_spawn_app_not_found(self, mock_get_frida):
        """Should raise AppNotFoundError when app not installed."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_device.enumerate_applications.return_value = []
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()

        with pytest.raises(AppNotFoundError) as exc_info:
            client.spawn("com.nonexistent.app")

        assert exc_info.value.bundle_id == "com.nonexistent.app"


class TestFridaClientAttach:
    """Test process attachment."""

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_attach_by_pid(self, mock_get_frida):
        """Should attach to process by PID."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_session = Mock()
        mock_device.attach.return_value = mock_session
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        session = client.attach(pid=1234)

        assert session is mock_session
        mock_device.attach.assert_called_once_with(1234)

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_attach_by_bundle_id(self, mock_get_frida):
        """Should attach to running app by bundle ID."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_session = Mock()

        mock_app = Mock()
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example"
        mock_app.pid = 5678
        mock_device.enumerate_applications.return_value = [mock_app]
        mock_device.attach.return_value = mock_session

        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        session = client.attach(bundle_id="com.example.app")

        assert session is mock_session
        mock_device.attach.assert_called_once_with(5678)

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_attach_app_not_running(self, mock_get_frida):
        """Should raise when app not running."""
        mock_frida = Mock()
        mock_device = Mock()

        mock_app = Mock()
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example"
        mock_app.pid = 0  # Not running
        mock_device.enumerate_applications.return_value = [mock_app]

        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()

        with pytest.raises(AppNotRunningError):
            client.attach(bundle_id="com.example.app")

    def test_attach_requires_pid_or_bundle_id(self):
        """Should raise when neither pid nor bundle_id provided."""
        client = FridaClient()
        with pytest.raises(ValueError):
            client.attach()


class TestFridaClientContextManager:
    """Test context manager protocol."""

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_context_manager_connects(self, mock_get_frida):
        """Should connect on enter."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_device.name = "iPhone"
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        with FridaClient() as client:
            assert client.is_connected

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_context_manager_closes(self, mock_get_frida):
        """Should close on exit."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_device.name = "iPhone"
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        with FridaClient() as client:
            pass

        assert not client.is_connected


class TestFridaClientClose:
    """Test cleanup."""

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_close_detaches_sessions(self, mock_get_frida):
        """Should detach all sessions on close."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_session = Mock()
        mock_app = Mock()
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example"
        mock_app.pid = 0
        mock_device.enumerate_applications.return_value = [mock_app]
        mock_device.spawn.return_value = 1234
        mock_device.attach.return_value = mock_session
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        client.spawn("com.example.app")
        client.close()

        mock_session.detach.assert_called_once()
        assert not client.is_connected

    @patch("orange.core.apps.decrypt.frida_client._get_frida")
    def test_close_handles_detach_errors(self, mock_get_frida):
        """Should not raise on detach errors."""
        mock_frida = Mock()
        mock_device = Mock()
        mock_session = Mock()
        mock_session.detach.side_effect = Exception("Detach failed")
        mock_app = Mock()
        mock_app.identifier = "com.example.app"
        mock_app.name = "Example"
        mock_app.pid = 0
        mock_device.enumerate_applications.return_value = [mock_app]
        mock_device.spawn.return_value = 1234
        mock_device.attach.return_value = mock_session
        mock_frida.get_usb_device.return_value = mock_device
        mock_get_frida.return_value = mock_frida

        client = FridaClient()
        client.connect()
        client.spawn("com.example.app")

        # Should not raise
        client.close()
