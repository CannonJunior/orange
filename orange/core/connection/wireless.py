"""
Wireless device discovery and connection via Wi-Fi Sync.

This module provides functionality for discovering and connecting to iOS
devices over Wi-Fi using Apple's standard Wi-Fi Sync protocol - the same
protocol used by iTunes and Finder.

NO DEVELOPER MODE REQUIRED.

Requirements:
    - Device must be paired with this computer (one-time USB pairing)
    - Wi-Fi connections must be enabled on the device
    - Device and computer must be on the same network

The workflow:
    1. Pair device via USB (one-time): `orange device pair <udid>`
    2. Enable Wi-Fi: `orange device wifi --enable`
    3. Disconnect USB - device now accessible wirelessly
    4. Use normally: `orange device list`, `orange device info`, etc.

Example:
    from orange.core.connection.wireless import (
        WirelessDiscovery,
        enable_wifi_connections,
    )

    # Enable Wi-Fi on a USB-connected device
    enable_wifi_connections(udid, enable=True)

    # Later, discover the device wirelessly
    discovery = WirelessDiscovery()
    devices = discovery.discover()
"""

from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Standard Wi-Fi sync port (lockdownd)
LOCKDOWN_PORT = 62078

# Bonjour service type for Wi-Fi sync devices
WIFI_SYNC_SERVICE = "_apple-mobdev2._tcp.local."


@dataclass
class WirelessDeviceInfo:
    """Information about a wirelessly discovered device."""

    name: str
    hostname: str
    address: str
    port: int
    udid: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "hostname": self.hostname,
            "address": self.address,
            "port": self.port,
            "udid": self.udid,
            "model": self.model,
            "os_version": self.os_version,
        }


class WirelessDiscovery:
    """
    Discovers iOS devices on the local network via Bonjour/mDNS.

    This uses Apple's standard Wi-Fi Sync protocol (_apple-mobdev2._tcp),
    which is the same protocol used by iTunes and Finder. No Developer
    Mode is required.

    Prerequisites:
        - Device must have been paired via USB at least once
        - Wi-Fi connections must be enabled on the device
        - Both devices must be on the same network

    Example:
        discovery = WirelessDiscovery()
        devices = discovery.discover(timeout=5)
        for device in devices:
            print(f"Found: {device.name} at {device.address}")
    """

    def __init__(self) -> None:
        """Initialize wireless discovery."""
        logger.debug("WirelessDiscovery initialized")

    def discover(self, timeout: float = 5.0) -> list[WirelessDeviceInfo]:
        """
        Discover iOS devices on the network.

        Uses Bonjour to find devices advertising the _apple-mobdev2._tcp
        service (standard Wi-Fi sync).

        Args:
            timeout: How long to scan in seconds.

        Returns:
            List of discovered devices.
        """
        devices: list[WirelessDeviceInfo] = []

        try:
            from pymobiledevice3.bonjour import browse_mobdev2

            logger.debug(f"Scanning for Wi-Fi sync devices ({timeout}s)...")

            # browse_mobdev2 is async, so we need to run it with asyncio
            services = asyncio.run(browse_mobdev2(timeout=timeout))

            for service in services:
                # ServiceInstance has: instance, host, port, addresses, properties
                # addresses is a list of Address objects with ip and iface attributes
                address = ""
                if service.addresses:
                    address = service.addresses[0].ip

                device = WirelessDeviceInfo(
                    name=service.instance,
                    hostname=service.host or service.instance,
                    address=address,
                    port=service.port or LOCKDOWN_PORT,
                )
                devices.append(device)
                logger.debug(f"Found: {device.name} at {device.address}:{device.port}")

        except ImportError:
            logger.warning("Bonjour discovery not available")
        except Exception as e:
            logger.error(f"Discovery error: {e}")

        logger.info(f"Discovered {len(devices)} wireless device(s)")
        return devices

    def discover_with_info(self, timeout: float = 5.0) -> list[WirelessDeviceInfo]:
        """
        Discover devices and retrieve their full information.

        This connects to each discovered device to get UDID, model, etc.

        Args:
            timeout: Scan timeout in seconds.

        Returns:
            List of devices with full information.
        """
        devices = self.discover(timeout=timeout)

        for device in devices:
            try:
                info = self._get_device_info(device.address, device.port)
                if info:
                    device.udid = info.get("UniqueDeviceID")
                    device.model = info.get("ProductType")
                    device.os_version = info.get("ProductVersion")
            except Exception as e:
                logger.debug(f"Could not get info for {device.name}: {e}")

        return devices

    def _get_device_info(
        self, address: str, port: int
    ) -> Optional[dict[str, Any]]:
        """Connect to device and retrieve its information."""
        try:
            from pymobiledevice3.lockdown import create_using_tcp

            lockdown = create_using_tcp(hostname=address, port=port)
            return lockdown.all_values
        except Exception as e:
            logger.debug(f"Could not connect to {address}:{port}: {e}")
            return None


def enable_wifi_connections(udid: Optional[str] = None, enable: bool = True) -> bool:
    """
    Enable or disable Wi-Fi connections on a device.

    This must be done while the device is connected via USB. After enabling,
    the device will be accessible over Wi-Fi when on the same network.

    Args:
        udid: Device UDID. If None, uses the first connected device.
        enable: True to enable, False to disable.

    Returns:
        True if successful, False otherwise.
    """
    try:
        from pymobiledevice3.lockdown import create_using_usbmux

        logger.info(f"{'Enabling' if enable else 'Disabling'} Wi-Fi connections...")

        lockdown = create_using_usbmux(serial=udid)
        lockdown.set_value(
            enable,
            key="EnableWifiConnections",
            domain="com.apple.mobile.wireless_lockdown"
        )

        logger.info(f"Wi-Fi connections {'enabled' if enable else 'disabled'}")
        return True

    except Exception as e:
        logger.error(f"Failed to set Wi-Fi connections: {e}")
        return False


def get_wifi_connections_state(udid: Optional[str] = None) -> Optional[bool]:
    """
    Check if Wi-Fi connections are enabled on a device.

    Args:
        udid: Device UDID. If None, uses the first connected device.

    Returns:
        True if enabled, False if disabled, None if unknown.
    """
    try:
        from pymobiledevice3.lockdown import create_using_usbmux

        lockdown = create_using_usbmux(serial=udid)
        return lockdown.get_value(
            key="EnableWifiConnections",
            domain="com.apple.mobile.wireless_lockdown"
        )

    except Exception as e:
        logger.error(f"Failed to get Wi-Fi connections state: {e}")
        return None


def connect_wireless(
    address: str,
    port: int = LOCKDOWN_PORT
) -> Any:
    """
    Connect to a device over Wi-Fi.

    Args:
        address: IP address or hostname of the device.
        port: Port number (default: 62078).

    Returns:
        LockdownClient connected to the device.
    """
    from pymobiledevice3.lockdown import create_using_tcp

    logger.info(f"Connecting to {address}:{port}...")
    return create_using_tcp(hostname=address, port=port)


def is_device_reachable(address: str, port: int = LOCKDOWN_PORT, timeout: float = 2.0) -> bool:
    """
    Check if a device is reachable over the network.

    Args:
        address: IP address or hostname.
        port: Port number.
        timeout: Connection timeout in seconds.

    Returns:
        True if reachable, False otherwise.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((address, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# Convenience function
def discover_wifi_devices(timeout: float = 5.0) -> list[WirelessDeviceInfo]:
    """
    Convenience function to discover Wi-Fi sync devices.

    Args:
        timeout: Scan duration in seconds.

    Returns:
        List of discovered devices.
    """
    discovery = WirelessDiscovery()
    return discovery.discover(timeout=timeout)
