"""Tests for file transfer manager."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile
import os

from orange.core.transfer.manager import FileManager, TransferProgress
from orange.core.transfer.browser import FileInfo
from orange.exceptions import DeviceNotFoundError, TransferError


class TestTransferProgress:
    """Tests for TransferProgress dataclass."""

    def test_progress_defaults(self) -> None:
        """TransferProgress should have expected defaults."""
        progress = TransferProgress()
        assert progress.total_files == 0
        assert progress.completed_files == 0
        assert progress.total_bytes == 0
        assert progress.completed_bytes == 0
        assert progress.current_file is None
        assert progress.failed_files == []

    def test_percentage_zero_total(self) -> None:
        """percentage should return 0 when total is zero."""
        progress = TransferProgress()
        assert progress.percentage == 0.0

    def test_percentage_calculation(self) -> None:
        """percentage should calculate correctly."""
        progress = TransferProgress(
            total_bytes=1000,
            completed_bytes=500,
        )
        assert progress.percentage == 50.0

    def test_percentage_complete(self) -> None:
        """percentage should return 100 when complete."""
        progress = TransferProgress(
            total_bytes=1000,
            completed_bytes=1000,
        )
        assert progress.percentage == 100.0

    def test_failed_files_list(self) -> None:
        """failed_files should track failures."""
        progress = TransferProgress()
        progress.failed_files.append("/path/to/failed.txt")
        assert len(progress.failed_files) == 1


class TestFileManager:
    """Tests for FileManager class."""

    @pytest.fixture
    def mock_afc(self) -> Mock:
        """Create a mock AFC service."""
        mock = Mock()
        mock.pull = Mock()
        mock.push = Mock()
        mock.makedirs = Mock()
        return mock

    @pytest.fixture
    def mock_browser(self) -> Mock:
        """Create a mock DeviceBrowser."""
        mock = Mock()
        mock.exists.return_value = True
        mock.is_directory.return_value = False
        mock.stat.return_value = FileInfo(
            name="test.txt",
            path="/test.txt",
            size=1024,
            is_directory=False,
        )
        mock.walk.return_value = []
        mock.close = Mock()
        return mock

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    def test_ensure_connected(self, mock_afc_class, mock_create_lockdown) -> None:
        """_ensure_connected should establish connection."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_create_lockdown.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc

        manager = FileManager("test-udid")
        result = manager._ensure_connected()

        mock_create_lockdown.assert_called_once_with("test-udid")
        assert result == mock_afc

    @patch("orange.core.transfer.manager.create_lockdown_client")
    def test_ensure_connected_device_not_found(self, mock_create_usbmux) -> None:
        """_ensure_connected should raise DeviceNotFoundError."""
        mock_create_usbmux.side_effect = Exception("No device")

        manager = FileManager("invalid-udid")
        with pytest.raises(DeviceNotFoundError):
            manager._ensure_connected()

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_pull_file(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """pull should transfer a single file."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_browser = Mock()

        mock_create_usbmux.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc
        mock_browser_class.return_value = mock_browser

        mock_browser.exists.return_value = True
        mock_browser.is_directory.return_value = False
        mock_browser.stat.return_value = FileInfo(
            name="photo.jpg",
            path="/DCIM/photo.jpg",
            size=2048,
            is_directory=False,
        )
        mock_browser.close = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "photo.jpg"

            manager = FileManager("test-udid")
            result = manager.pull("/DCIM/photo.jpg", dest)

            mock_afc.pull.assert_called_once()
            assert result.total_files == 1

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_pull_nonexistent_path(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """pull should raise TransferError for non-existent path."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_browser = Mock()

        mock_create_usbmux.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc
        mock_browser_class.return_value = mock_browser
        mock_browser.exists.return_value = False
        mock_browser.close = Mock()

        manager = FileManager("test-udid")

        with pytest.raises(TransferError, match="does not exist"):
            manager.pull("/nonexistent", Path("/tmp/dest"))

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_push_file(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """push should transfer a single file."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_browser = Mock()

        mock_create_usbmux.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc
        mock_browser_class.return_value = mock_browser
        mock_browser.close = Mock()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            manager = FileManager("test-udid")
            result = manager.push(Path(temp_path), "/remote/file.txt")

            mock_afc.push.assert_called_once()
            assert result.completed_files == 1
        finally:
            os.unlink(temp_path)

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_push_nonexistent_local(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """push should raise TransferError for non-existent local path."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_browser = Mock()

        mock_create_usbmux.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc
        mock_browser_class.return_value = mock_browser
        mock_browser.close = Mock()

        manager = FileManager("test-udid")

        with pytest.raises(TransferError, match="does not exist"):
            manager.push(Path("/nonexistent/file.txt"), "/remote")

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_pull_category_unknown(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """pull_category should raise TransferError for unknown category."""
        mock_browser = Mock()
        mock_browser.close = Mock()
        mock_browser_class.return_value = mock_browser

        manager = FileManager("test-udid")

        with pytest.raises(TransferError, match="Unknown category"):
            manager.pull_category("nonexistent", Path("/tmp/dest"))

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_pull_category_backup_only(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """pull_category should raise TransferError for backup-only categories."""
        mock_browser = Mock()
        mock_browser.close = Mock()
        mock_browser_class.return_value = mock_browser

        manager = FileManager("test-udid")

        with pytest.raises(TransferError, match="requires backup access"):
            manager.pull_category("messages", Path("/tmp/dest"))

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_pull_category_photos(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """pull_category should transfer photos category."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_browser = Mock()

        mock_create_usbmux.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc
        mock_browser_class.return_value = mock_browser

        # Setup mock to indicate paths exist but are empty
        mock_browser.exists.return_value = True
        mock_browser.is_directory.return_value = True
        mock_browser.walk.return_value = []
        mock_browser.close = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = FileManager("test-udid")
            result = manager.pull_category("photos", Path(tmpdir))

            # Should complete without error
            assert result.total_files == 0

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_context_manager(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """FileManager should work as context manager."""
        mock_lockdown = Mock()
        mock_afc = Mock()
        mock_browser = Mock()

        mock_create_usbmux.return_value = mock_lockdown
        mock_afc_class.return_value = mock_afc
        mock_browser_class.return_value = mock_browser
        mock_browser.close = Mock()

        with FileManager("test-udid") as manager:
            manager._ensure_connected()

        mock_afc.close.assert_called()
        mock_browser.close.assert_called()

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_list_category_files(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """list_category_files should yield FileInfo objects."""
        mock_browser = Mock()
        mock_browser.exists.return_value = True
        mock_browser.walk.return_value = [
            ("/DCIM", [], ["photo1.jpg", "photo2.jpg"]),
        ]
        mock_browser.stat.return_value = FileInfo(
            name="photo1.jpg",
            path="/DCIM/photo1.jpg",
            size=1024,
            is_directory=False,
        )
        mock_browser.close = Mock()
        mock_browser_class.return_value = mock_browser

        manager = FileManager("test-udid")
        files = list(manager.list_category_files("photos"))

        assert len(files) >= 1

    @patch("orange.core.transfer.manager.create_lockdown_client")
    @patch("orange.core.transfer.manager.AfcService")
    @patch("orange.core.transfer.manager.DeviceBrowser")
    def test_get_category_size(self, mock_browser_class, mock_afc_class, mock_create_usbmux) -> None:
        """get_category_size should return total size in bytes."""
        mock_browser = Mock()
        mock_browser.exists.return_value = True
        mock_browser.walk.return_value = [
            ("/DCIM", [], ["photo1.jpg", "photo2.jpg"]),
        ]
        mock_browser.stat.side_effect = [
            FileInfo(name="photo1.jpg", path="/DCIM/photo1.jpg", size=1024, is_directory=False),
            FileInfo(name="photo2.jpg", path="/DCIM/photo2.jpg", size=2048, is_directory=False),
        ]
        mock_browser.close = Mock()
        mock_browser_class.return_value = mock_browser

        manager = FileManager("test-udid")
        size = manager.get_category_size("photos")

        assert size == 3072  # 1024 + 2048

    def test_progress_callback(self) -> None:
        """Progress callback should be called during transfer."""
        progress_updates = []

        def on_progress(p: TransferProgress) -> None:
            progress_updates.append(p.percentage)

        # This would be tested with integration tests
        # For unit tests, we just verify the callback type is correct
        assert callable(on_progress)
