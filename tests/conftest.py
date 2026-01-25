"""
Pytest configuration and fixtures for Orange tests.

This module provides common fixtures used across the test suite,
including mock devices, connections, and backups.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from orange.core.connection.device import (
    ConnectionType,
    DeviceInfo,
    DeviceState,
)
from orange.config import Config


# Test device data
TEST_DEVICE_UDID = "00008030-001234567890001E"
TEST_DEVICE_NAME = "Test iPhone"
TEST_DEVICE_MODEL = "iPhone"
TEST_DEVICE_MODEL_NUMBER = "iPhone14,2"
TEST_IOS_VERSION = "17.0"
TEST_BUILD_VERSION = "21A329"
TEST_SERIAL_NUMBER = "TESTSERIAL123"


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Create a mock DeviceInfo for testing."""
    return DeviceInfo(
        udid=TEST_DEVICE_UDID,
        name=TEST_DEVICE_NAME,
        model=TEST_DEVICE_MODEL,
        model_number=TEST_DEVICE_MODEL_NUMBER,
        ios_version=TEST_IOS_VERSION,
        build_version=TEST_BUILD_VERSION,
        serial_number=TEST_SERIAL_NUMBER,
        connection_type=ConnectionType.USB,
        state=DeviceState.PAIRED,
        wifi_address="AA:BB:CC:DD:EE:FF",
        battery_level=85,
        battery_charging=False,
        paired=True,
    )


@pytest.fixture
def mock_unpaired_device_info() -> DeviceInfo:
    """Create a mock unpaired DeviceInfo for testing."""
    return DeviceInfo(
        udid="00008030-999999999999999E",
        name="Unknown (Not Paired)",
        model="Unknown",
        model_number="Unknown",
        ios_version="Unknown",
        build_version="Unknown",
        serial_number="Unknown",
        connection_type=ConnectionType.USB,
        state=DeviceState.UNPAIRED,
        paired=False,
    )


@pytest.fixture
def mock_lockdown_values() -> dict[str, Any]:
    """Create mock lockdown values returned by device."""
    return {
        "DeviceName": TEST_DEVICE_NAME,
        "DeviceClass": TEST_DEVICE_MODEL,
        "ProductType": TEST_DEVICE_MODEL_NUMBER,
        "ProductVersion": TEST_IOS_VERSION,
        "BuildVersion": TEST_BUILD_VERSION,
        "SerialNumber": TEST_SERIAL_NUMBER,
        "UniqueDeviceID": TEST_DEVICE_UDID,
        "WiFiAddress": "AA:BB:CC:DD:EE:FF",
        "BatteryCurrentCapacity": 85,
        "BatteryIsCharging": False,
        "HardwareModel": "D63AP",
        "ActivationState": "Activated",
    }


@pytest.fixture
def mock_mux_device() -> MagicMock:
    """Create a mock usbmux device."""
    device = MagicMock()
    device.serial = TEST_DEVICE_UDID
    device.connection_type = "USB"
    return device


@pytest.fixture
def mock_lockdown_client(mock_lockdown_values: dict[str, Any]) -> MagicMock:
    """Create a mock LockdownClient."""
    client = MagicMock()
    client.all_values = mock_lockdown_values
    client.paired = True
    client.get_value = lambda key, domain=None: mock_lockdown_values.get(key)
    return client


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Create a test configuration with temporary directories."""
    return Config(
        config_dir=tmp_path / "config",
        backup_dir=tmp_path / "backups",
        export_dir=tmp_path / "exports",
        log_dir=tmp_path / "logs",
    )


@pytest.fixture
def patch_usbmux_list(mock_mux_device: MagicMock):
    """Patch usbmux.list_devices to return mock device."""
    with patch(
        "orange.core.connection.device.usbmux_list_devices",
        return_value=[mock_mux_device],
    ) as mock:
        yield mock


@pytest.fixture
def patch_create_lockdown(mock_lockdown_client: MagicMock):
    """Patch create_using_usbmux to return mock lockdown client."""
    with patch(
        "orange.core.connection.device.create_using_usbmux",
        return_value=mock_lockdown_client,
    ) as mock:
        yield mock


@pytest.fixture
def patch_pairing_lockdown(mock_lockdown_client: MagicMock):
    """Patch create_using_usbmux for pairing module."""
    with patch(
        "orange.core.connection.pairing.create_using_usbmux",
        return_value=mock_lockdown_client,
    ) as mock:
        yield mock


@pytest.fixture
def patch_manager_lockdown(mock_lockdown_client: MagicMock):
    """Patch create_using_usbmux for manager module."""
    with patch(
        "orange.core.connection.manager.create_using_usbmux",
        return_value=mock_lockdown_client,
    ) as mock:
        yield mock
