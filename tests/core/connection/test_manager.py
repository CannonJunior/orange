"""
Tests for connection manager functionality.

Tests the ConnectionManager and DeviceConnection classes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orange.core.connection.manager import (
    ConnectionManager,
    DeviceConnection,
)
from orange.exceptions import (
    DeviceNotFoundError,
    DeviceNotPairedError,
    ConnectionTimeoutError,
)

from pymobiledevice3.exceptions import (
    ConnectionFailedError,
    MuxException,
)


class TestDeviceConnection:
    """Tests for DeviceConnection class."""

    def test_connection_properties(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """DeviceConnection should expose device properties."""
        conn = DeviceConnection("test-udid", mock_lockdown_client)

        assert conn.udid == "test-udid"
        assert conn.device_name == "Test iPhone"
        assert conn.ios_version == "17.0"
        assert conn.model == "iPhone"
        assert conn.is_connected is True

    def test_connection_get_all_values(
        self,
        mock_lockdown_client: MagicMock,
        mock_lockdown_values: dict,
    ) -> None:
        """get_all_values should return all device values."""
        conn = DeviceConnection("test-udid", mock_lockdown_client)
        values = conn.get_all_values()

        assert values["DeviceName"] == "Test iPhone"
        assert values["ProductVersion"] == "17.0"

    def test_connection_close(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """close should mark connection as closed."""
        conn = DeviceConnection("test-udid", mock_lockdown_client)
        assert conn.is_connected is True

        conn.close()
        assert conn.is_connected is False

    def test_connection_close_is_idempotent(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """close should be safe to call multiple times."""
        conn = DeviceConnection("test-udid", mock_lockdown_client)
        conn.close()
        conn.close()  # Should not raise
        assert conn.is_connected is False

    def test_connection_context_manager(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """DeviceConnection should work as context manager."""
        with DeviceConnection("test-udid", mock_lockdown_client) as conn:
            assert conn.is_connected is True
            assert conn.device_name == "Test iPhone"

        assert conn.is_connected is False


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_init_creates_manager(self) -> None:
        """ConnectionManager should initialize properly."""
        manager = ConnectionManager()
        assert manager is not None

    def test_list_devices_delegates_to_detector(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """list_devices should return devices from detector."""
        # Also need to patch the detector's create_using_usbmux
        with patch(
            "orange.core.connection.manager.create_using_usbmux",
        ):
            manager = ConnectionManager()
            devices = manager.list_devices()
            assert isinstance(devices, list)

    def test_connect_returns_connection(
        self,
        patch_manager_lockdown: MagicMock,
    ) -> None:
        """connect context manager should yield DeviceConnection."""
        manager = ConnectionManager()

        with manager.connect("test-udid", timeout=5) as conn:
            assert isinstance(conn, DeviceConnection)
            assert conn.is_connected is True

    def test_connect_raises_device_not_found(self) -> None:
        """connect should raise DeviceNotFoundError when device not found."""
        with patch(
            "orange.core.connection.manager.create_using_usbmux",
            side_effect=MuxException("Not found"),
        ):
            manager = ConnectionManager()
            with pytest.raises(DeviceNotFoundError):
                with manager.connect("invalid-udid", timeout=1):
                    pass

    def test_connect_raises_device_not_paired(self) -> None:
        """connect should raise DeviceNotPairedError when not paired."""
        with patch(
            "orange.core.connection.manager.create_using_usbmux",
            side_effect=ConnectionFailedError("NotPaired"),
        ):
            manager = ConnectionManager()
            with pytest.raises(DeviceNotPairedError):
                with manager.connect("test-udid", timeout=1):
                    pass

    def test_get_connection_reuses_existing(
        self,
        patch_manager_lockdown: MagicMock,
    ) -> None:
        """get_connection should reuse existing connections."""
        manager = ConnectionManager()

        conn1 = manager.get_connection("test-udid", timeout=5)
        conn2 = manager.get_connection("test-udid", timeout=5)

        assert conn1 is conn2

    def test_disconnect_closes_connection(
        self,
        patch_manager_lockdown: MagicMock,
    ) -> None:
        """disconnect should close and remove connection."""
        manager = ConnectionManager()

        conn = manager.get_connection("test-udid", timeout=5)
        assert conn.is_connected is True

        manager.disconnect("test-udid")
        assert manager.is_connected("test-udid") is False

    def test_close_all_closes_all_connections(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """close_all should close all connections."""
        with patch(
            "orange.core.connection.manager.create_using_usbmux",
            return_value=mock_lockdown_client,
        ):
            manager = ConnectionManager()

            # Create multiple connections
            conn1 = manager.get_connection("udid-1", timeout=5)
            conn2 = manager.get_connection("udid-2", timeout=5)

            assert manager.is_connected("udid-1") is True
            assert manager.is_connected("udid-2") is True

            manager.close_all()

            assert manager.is_connected("udid-1") is False
            assert manager.is_connected("udid-2") is False

    def test_on_device_connected_callback(
        self,
        patch_manager_lockdown: MagicMock,
    ) -> None:
        """on_device_connected callback should be called on connection."""
        connected_udids = []

        def on_connected(udid: str) -> None:
            connected_udids.append(udid)

        manager = ConnectionManager()
        manager.on_device_connected(on_connected)

        manager.get_connection("test-udid", timeout=5)

        assert "test-udid" in connected_udids

    def test_on_device_disconnected_callback(
        self,
        patch_manager_lockdown: MagicMock,
    ) -> None:
        """on_device_disconnected callback should be called on disconnect."""
        disconnected_udids = []

        def on_disconnected(udid: str) -> None:
            disconnected_udids.append(udid)

        manager = ConnectionManager()
        manager.on_device_disconnected(on_disconnected)

        manager.get_connection("test-udid", timeout=5)
        manager.disconnect("test-udid")

        assert "test-udid" in disconnected_udids

    def test_context_manager_closes_all(
        self,
        patch_manager_lockdown: MagicMock,
    ) -> None:
        """ConnectionManager context manager should close all on exit."""
        with ConnectionManager() as manager:
            conn = manager.get_connection("test-udid", timeout=5)
            assert conn.is_connected is True

        # After context exit, connection should be closed
        assert manager.is_connected("test-udid") is False

    def test_is_connected_returns_false_for_unknown(self) -> None:
        """is_connected should return False for unknown UDIDs."""
        manager = ConnectionManager()
        assert manager.is_connected("unknown-udid") is False
