"""
Tests for device detection functionality.

Tests the DeviceDetector class and DeviceInfo dataclass.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orange.core.connection.device import (
    ConnectionType,
    DeviceDetector,
    DeviceInfo,
    DeviceState,
)
from orange.exceptions import DeviceNotFoundError


class TestDeviceInfo:
    """Tests for DeviceInfo dataclass."""

    def test_device_info_creation(self, mock_device_info: DeviceInfo) -> None:
        """DeviceInfo should be created with all required fields."""
        assert mock_device_info.udid == "00008030-001234567890001E"
        assert mock_device_info.name == "Test iPhone"
        assert mock_device_info.model == "iPhone"
        assert mock_device_info.ios_version == "17.0"
        assert mock_device_info.paired is True

    def test_device_info_display_name(self, mock_device_info: DeviceInfo) -> None:
        """display_name should return the device name."""
        assert mock_device_info.display_name == "Test iPhone"

    def test_device_info_display_name_fallback(self) -> None:
        """display_name should fallback to model + UDID if name is empty."""
        device = DeviceInfo(
            udid="00008030-001234567890001E",
            name="",
            model="iPhone",
            model_number="iPhone14,2",
            ios_version="17.0",
            build_version="21A329",
            serial_number="TEST",
            connection_type=ConnectionType.USB,
            state=DeviceState.PAIRED,
        )
        assert "iPhone" in device.display_name
        assert "00008030" in device.display_name

    def test_device_info_short_udid(self, mock_device_info: DeviceInfo) -> None:
        """short_udid should return abbreviated UDID."""
        assert mock_device_info.short_udid == "00008030..."

    def test_device_info_to_dict(self, mock_device_info: DeviceInfo) -> None:
        """to_dict should return serializable dictionary."""
        data = mock_device_info.to_dict()
        assert data["udid"] == mock_device_info.udid
        assert data["name"] == mock_device_info.name
        assert data["connection_type"] == "usb"
        assert data["state"] == "paired"
        assert data["battery_level"] == 85

    def test_connection_type_enum(self) -> None:
        """ConnectionType enum should have expected values."""
        assert ConnectionType.USB.value == "usb"
        assert ConnectionType.WIFI.value == "wifi"
        assert ConnectionType.UNKNOWN.value == "unknown"

    def test_device_state_enum(self) -> None:
        """DeviceState enum should have expected values."""
        assert DeviceState.CONNECTED.value == "connected"
        assert DeviceState.PAIRED.value == "paired"
        assert DeviceState.UNPAIRED.value == "unpaired"
        assert DeviceState.DISCONNECTED.value == "disconnected"


class TestDeviceDetector:
    """Tests for DeviceDetector class."""

    def test_list_devices_returns_list(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """list_devices should return a list."""
        detector = DeviceDetector()
        result = detector.list_devices()
        assert isinstance(result, list)

    def test_list_devices_returns_device_info_objects(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """Each item in list_devices should be a DeviceInfo instance."""
        detector = DeviceDetector()
        devices = detector.list_devices()
        assert len(devices) == 1
        assert isinstance(devices[0], DeviceInfo)

    def test_list_devices_extracts_correct_info(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """Device info should match the lockdown values."""
        detector = DeviceDetector()
        devices = detector.list_devices()

        device = devices[0]
        assert device.name == "Test iPhone"
        assert device.ios_version == "17.0"
        assert device.model_number == "iPhone14,2"
        assert device.battery_level == 85

    def test_list_devices_empty_when_no_devices(self) -> None:
        """list_devices should return empty list when no devices."""
        with patch(
            "orange.core.connection.device.usbmux_list_devices",
            return_value=[],
        ):
            detector = DeviceDetector()
            devices = detector.list_devices()
            assert devices == []

    def test_get_device_returns_device_info(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """get_device should return DeviceInfo for valid UDID."""
        detector = DeviceDetector()
        device = detector.get_device("00008030-001234567890001E")
        assert device is not None
        assert device.name == "Test iPhone"

    def test_get_device_returns_none_for_invalid_udid(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """get_device should return None for invalid UDID."""
        detector = DeviceDetector()
        device = detector.get_device("invalid-udid-12345")
        assert device is None

    def test_get_device_or_raise_returns_device(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """get_device_or_raise should return DeviceInfo for valid UDID."""
        detector = DeviceDetector()
        device = detector.get_device_or_raise("00008030-001234567890001E")
        assert device.name == "Test iPhone"

    def test_get_device_or_raise_raises_for_invalid_udid(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """get_device_or_raise should raise DeviceNotFoundError for invalid UDID."""
        detector = DeviceDetector()
        with pytest.raises(DeviceNotFoundError) as exc_info:
            detector.get_device_or_raise("invalid-udid")

        assert "invalid-udid" in str(exc_info.value)

    def test_detector_excludes_wifi_when_disabled(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """DeviceDetector should exclude Wi-Fi devices when include_wifi=False."""
        wifi_device = MagicMock()
        wifi_device.serial = "wifi-device-udid"
        wifi_device.connection_type = "Network"

        with patch(
            "orange.core.connection.device.usbmux_list_devices",
            return_value=[wifi_device],
        ):
            with patch(
                "orange.core.connection.device.create_using_usbmux",
                return_value=mock_lockdown_client,
            ):
                detector = DeviceDetector(include_wifi=False)
                devices = detector.list_devices()
                assert len(devices) == 0

    def test_detector_includes_wifi_by_default(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """DeviceDetector should include Wi-Fi devices by default."""
        wifi_device = MagicMock()
        wifi_device.serial = "wifi-device-udid"
        wifi_device.connection_type = "Network"

        with patch(
            "orange.core.connection.device.usbmux_list_devices",
            return_value=[wifi_device],
        ):
            with patch(
                "orange.core.connection.device.create_using_usbmux",
                return_value=mock_lockdown_client,
            ):
                detector = DeviceDetector(include_wifi=True)
                devices = detector.list_devices()
                assert len(devices) == 1

    def test_refresh_clears_cache(
        self,
        patch_usbmux_list: MagicMock,
        patch_create_lockdown: MagicMock,
    ) -> None:
        """refresh should clear and repopulate the device cache."""
        detector = DeviceDetector()

        # Initial list
        devices = detector.list_devices()
        assert len(devices) == 1

        # Modify mock to return empty
        patch_usbmux_list.return_value = []

        # Without refresh, should still return cached
        devices = detector.list_devices(refresh=False)
        assert len(devices) == 1

        # With refresh, should return empty
        devices = detector.list_devices(refresh=True)
        assert len(devices) == 0
