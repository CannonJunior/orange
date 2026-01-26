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

    # Connect to any device (USB or Wi-Fi)
    from orange.core.connection import create_lockdown_client
    lockdown = create_lockdown_client(udid)  # Auto-detects USB or Wi-Fi
"""

from typing import Optional
from pymobiledevice3.lockdown import create_using_usbmux, create_using_tcp, LockdownClient

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


def create_lockdown_client(udid: Optional[str] = None) -> LockdownClient:
    """
    Create a lockdown client for a device, auto-detecting USB or Wi-Fi.

    This function first tries to connect via USB (usbmuxd), and if that
    fails, it searches for the device via Wi-Fi (Bonjour).

    Args:
        udid: Device UDID. If None, connects to first available device.

    Returns:
        LockdownClient connected to the device.

    Raises:
        DeviceNotFoundError: If device cannot be found via USB or Wi-Fi.
    """
    from orange.exceptions import DeviceNotFoundError

    # First, try USB connection via usbmuxd
    try:
        return create_using_usbmux(serial=udid)
    except Exception:
        pass

    # If USB fails, try to find device via Wi-Fi
    detector = DeviceDetector(include_wifi=True)
    devices = detector.list_devices()

    if not devices:
        raise DeviceNotFoundError(udid or "No devices found")

    # Find matching device or use first one
    target_device = None
    if udid:
        for device in devices:
            if device.udid == udid:
                target_device = device
                break
        if not target_device:
            raise DeviceNotFoundError(udid)
    else:
        target_device = devices[0]

    # Connect based on connection type
    if target_device.connection_type == ConnectionType.WIFI:
        wifi_address = target_device.wifi_address
        wifi_port = target_device.extra.get("wifi_port", LOCKDOWN_PORT) if target_device.extra else LOCKDOWN_PORT
        if wifi_address:
            # Load pairing record for Wi-Fi connection
            pair_record = _load_pairing_record(target_device.udid)
            return create_using_tcp(
                hostname=wifi_address,
                port=wifi_port,
                autopair=False,
                pair_record=pair_record,
            )

    # Fallback to USB
    return create_using_usbmux(serial=target_device.udid)


def _load_pairing_record(udid: str) -> Optional[dict]:
    """Load pairing record for a device from the system lockdown directory."""
    import plistlib
    from pathlib import Path

    # Standard pairing record locations
    pairing_paths = [
        Path(f"/var/lib/lockdown/{udid}.plist"),  # Linux
        Path.home() / "Library/Lockdown" / f"{udid}.plist",  # macOS
    ]

    for path in pairing_paths:
        if path.exists():
            try:
                with open(path, "rb") as f:
                    return plistlib.load(f)
            except Exception:
                pass

    return None

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
    "create_lockdown_client",
    "discover_wifi_devices",
    "enable_wifi_connections",
    "get_wifi_connections_state",
    "is_device_reachable",
]
