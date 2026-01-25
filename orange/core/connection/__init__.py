"""
Device connection module for Orange.

This module provides functionality for detecting, pairing, and connecting
to iOS devices over USB and Wi-Fi.

Example:
    from orange.core.connection import ConnectionManager, DeviceDetector

    # List available devices (USB + Wi-Fi)
    detector = DeviceDetector()
    devices = detector.list_devices()

    # Discover wireless devices
    from orange.core.connection import WirelessDiscovery
    discovery = WirelessDiscovery()
    wireless_devices = discovery.discover()

    # Connect to a device
    manager = ConnectionManager()
    with manager.connect(devices[0].udid) as conn:
        print(f"Connected to {conn.device_name}")
"""

from orange.core.connection.device import (
    ConnectionType,
    DeviceDetector,
    DeviceInfo,
    DeviceState,
)
from orange.core.connection.pairing import PairingManager, PairingState
from orange.core.connection.manager import ConnectionManager, DeviceConnection
from orange.core.connection.wireless import (
    WirelessDiscovery,
    WirelessDeviceInfo,
    discover_wifi_devices,
    enable_wifi_connections,
    get_wifi_connections_state,
    connect_wireless,
    is_device_reachable,
    LOCKDOWN_PORT,
)

__all__ = [
    "ConnectionManager",
    "ConnectionType",
    "DeviceConnection",
    "DeviceDetector",
    "DeviceInfo",
    "DeviceState",
    "LOCKDOWN_PORT",
    "PairingManager",
    "PairingState",
    "WirelessDeviceInfo",
    "WirelessDiscovery",
    "connect_wireless",
    "discover_wifi_devices",
    "enable_wifi_connections",
    "get_wifi_connections_state",
    "is_device_reachable",
]
