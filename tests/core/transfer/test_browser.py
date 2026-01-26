"""Tests for device file browser."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from orange.core.transfer.browser import DeviceBrowser, FileInfo
from orange.exceptions import DeviceNotFoundError, TransferError


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_file_info_creation(self) -> None:
        """FileInfo should be created with all fields."""
        info = FileInfo(
            name="test.jpg",
            path="/DCIM/100APPLE/test.jpg",
            size=1024000,
            is_directory=False,
            modified_time=datetime(2026, 1, 25, 12, 0, 0),
            created_time=datetime(2026, 1, 24, 10, 0, 0),
            permissions=0o644,
        )
        assert info.name == "test.jpg"
        assert info.path == "/DCIM/100APPLE/test.jpg"
        assert info.size == 1024000
        assert info.is_directory is False

    def test_size_human_bytes(self) -> None:
        """size_human should format bytes."""
        info = FileInfo(name="small.txt", path="/small.txt", size=512, is_directory=False)
        assert "B" in info.size_human

    def test_size_human_kilobytes(self) -> None:
        """size_human should format kilobytes."""
        info = FileInfo(name="medium.txt", path="/medium.txt", size=1024 * 50, is_directory=False)
        assert "KB" in info.size_human

    def test_size_human_megabytes(self) -> None:
        """size_human should format megabytes."""
        info = FileInfo(name="large.jpg", path="/large.jpg", size=1024 * 1024 * 5, is_directory=False)
        assert "MB" in info.size_human

    def test_size_human_gigabytes(self) -> None:
        """size_human should format gigabytes."""
        info = FileInfo(name="huge.mov", path="/huge.mov", size=1024 * 1024 * 1024 * 2, is_directory=False)
        assert "GB" in info.size_human

    def test_size_human_directory(self) -> None:
        """size_human should return dash for directories."""
        info = FileInfo(name="folder", path="/folder", size=0, is_directory=True)
        assert info.size_human == "-"

    def test_to_dict(self) -> None:
        """to_dict should return all fields."""
        info = FileInfo(
            name="test.jpg",
            path="/DCIM/test.jpg",
            size=1024,
            is_directory=False,
            modified_time=datetime(2026, 1, 25, 12, 0, 0),
        )
        d = info.to_dict()
        assert d["name"] == "test.jpg"
        assert d["path"] == "/DCIM/test.jpg"
        assert d["size"] == 1024
        assert d["is_directory"] is False
        assert "size_human" in d
        assert d["modified_time"] is not None

    def test_to_dict_optional_fields(self) -> None:
        """to_dict should handle None optional fields."""
        info = FileInfo(name="test.txt", path="/test.txt", size=100, is_directory=False)
        d = info.to_dict()
        assert d["modified_time"] is None
        assert d["created_time"] is None


class TestDeviceBrowser:
    """Tests for DeviceBrowser class."""

    @pytest.fixture
    def mock_afc(self) -> Mock:
        """Create a mock AFC service."""
        mock = Mock()
        mock.listdir.return_value = [".", "..", "file1.txt", "folder1"]
        mock.stat.return_value = {
            "st_size": "1024",
            "st_ifmt": "S_IFREG",
            "st_mtime": "1706180400000000000",
        }
        mock.exists.return_value = True
        mock.isdir.return_value = False
        return mock

    @pytest.fixture
    def mock_lockdown(self) -> Mock:
        """Create a mock lockdown client."""
        return Mock()

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_ensure_connected(self, mock_afc_class, mock_create_lockdown) -> None:
        """_ensure_connected should establish connection."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_create_lockdown.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        result = browser._ensure_connected()

        mock_create_lockdown.assert_called_once_with("test-udid")
        mock_afc_class.assert_called_once_with(mock_lockdown)
        assert result == mock_afc

    @patch("orange.core.transfer.browser.create_lockdown_client")
    def test_ensure_connected_device_not_found(self, mock_create_usbmux) -> None:
        """_ensure_connected should raise DeviceNotFoundError on failure."""
        mock_create_usbmux.side_effect = Exception("No device")

        browser = DeviceBrowser("invalid-udid")
        with pytest.raises(DeviceNotFoundError):
            browser._ensure_connected()

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_list_directory(self, mock_afc_class, mock_create_usbmux, mock_afc, mock_lockdown) -> None:
        """list_directory should return FileInfo list."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc

        # Configure mock for directory listing
        mock_afc.listdir.return_value = [".", "..", "photo.jpg", "video.mov"]
        mock_afc.stat.side_effect = lambda path: {
            "st_size": "1024",
            "st_ifmt": "S_IFREG",
            "st_mtime": "1706180400000000000",
        }

        browser = DeviceBrowser("test-udid")
        result = browser.list_directory("/DCIM")

        assert len(result) == 2  # Excludes . and ..
        assert all(isinstance(item, FileInfo) for item in result)

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_list_directory_error(self, mock_afc_class, mock_create_usbmux, mock_lockdown) -> None:
        """list_directory should raise TransferError on failure."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc = Mock()
        mock_afc.listdir.side_effect = Exception("Permission denied")
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        with pytest.raises(TransferError):
            browser.list_directory("/protected")

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_exists(self, mock_afc_class, mock_create_usbmux, mock_afc, mock_lockdown) -> None:
        """exists should return True for existing paths."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc.exists.return_value = True
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        assert browser.exists("/DCIM") is True

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_exists_not_found(self, mock_afc_class, mock_create_usbmux, mock_afc, mock_lockdown) -> None:
        """exists should return False for non-existent paths."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc.exists.return_value = False
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        assert browser.exists("/nonexistent") is False

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_is_directory(self, mock_afc_class, mock_create_usbmux, mock_afc, mock_lockdown) -> None:
        """is_directory should return True for directories."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc.isdir.return_value = True
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        assert browser.is_directory("/DCIM") is True

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_stat(self, mock_afc_class, mock_create_usbmux, mock_afc, mock_lockdown) -> None:
        """stat should return FileInfo for a path."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc.stat.return_value = {
            "st_size": "2048",
            "st_ifmt": "S_IFREG",
            "st_mtime": "1706180400000000000",
        }
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        info = browser.stat("/DCIM/photo.jpg")

        assert info.name == "photo.jpg"
        assert info.size == 2048
        assert info.is_directory is False

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_stat_directory(self, mock_afc_class, mock_create_usbmux, mock_afc, mock_lockdown) -> None:
        """stat should recognize directories."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc.stat.return_value = {
            "st_size": "0",
            "st_ifmt": "S_IFDIR",
        }
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        info = browser.stat("/DCIM")

        assert info.is_directory is True

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_context_manager(self, mock_afc_class, mock_create_usbmux, mock_lockdown) -> None:
        """DeviceBrowser should work as context manager."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc = Mock()
        mock_afc_class.return_value = mock_afc

        with DeviceBrowser("test-udid") as browser:
            browser._ensure_connected()

        mock_afc.close.assert_called_once()

    @patch("orange.core.transfer.browser.create_lockdown_client")
    @patch("orange.core.transfer.browser.AfcService")
    def test_walk(self, mock_afc_class, mock_create_usbmux, mock_lockdown) -> None:
        """walk should yield directory contents recursively."""
        mock_create_usbmux.return_value = mock_lockdown
        mock_afc = Mock()

        # Setup mock responses for walk
        def listdir_side_effect(path):
            if path == "/DCIM":
                return [".", "..", "100APPLE", "photo.jpg"]
            elif path == "/DCIM/100APPLE":
                return [".", "..", "IMG_0001.jpg"]
            return [".", ".."]

        def isdir_side_effect(path):
            return path in ["/DCIM", "/DCIM/100APPLE"]

        mock_afc.listdir.side_effect = listdir_side_effect
        mock_afc.isdir.side_effect = isdir_side_effect
        mock_afc_class.return_value = mock_afc

        browser = DeviceBrowser("test-udid")
        results = list(browser.walk("/DCIM"))

        assert len(results) >= 1
        # First result should be root directory
        dirpath, dirnames, filenames = results[0]
        assert dirpath == "/DCIM"
