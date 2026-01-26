"""
Device detection and information retrieval.

This module provides functionality for enumerating connected iOS devices
and retrieving their information.

Example:
    detector = DeviceDetector()
    devices = detector.list_devices()
    for device in devices:
        print(f"{device.name} ({device.ios_version})")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pymobiledevice3.lockdown import create_using_usbmux, create_using_tcp, LockdownClient
from pymobiledevice3.usbmux import list_devices as usbmux_list_devices
from pymobiledevice3.exceptions import (
    MuxException,
    ConnectionFailedError,
)

from orange.exceptions import DeviceNotFoundError, ConnectionError

# Standard Wi-Fi sync port
LOCKDOWN_PORT = 62078

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Type of connection to the device."""

    USB = "usb"
    WIFI = "wifi"
    UNKNOWN = "unknown"


class DeviceState(Enum):
    """Current state of the device."""

    CONNECTED = "connected"
    PAIRED = "paired"
    UNPAIRED = "unpaired"
    DISCONNECTED = "disconnected"
    LOCKED = "locked"


@dataclass
class DeviceInfo:
    """
    Container for iOS device information.

    Attributes:
        udid: Unique Device Identifier (40 hex chars for older devices,
              or UUID format for newer ones)
        name: User-assigned device name (e.g., "John's iPhone")
        model: Device model name (e.g., "iPhone", "iPad")
        model_number: Internal model number (e.g., "iPhone14,2")
        ios_version: iOS version string (e.g., "17.0")
        build_version: iOS build version (e.g., "21A329")
        serial_number: Hardware serial number
        connection_type: How the device is connected (USB or Wi-Fi)
        state: Current device state
        wifi_address: Wi-Fi MAC address (if available)
        battery_level: Battery percentage (0-100, if available)
        battery_charging: Whether device is charging
        storage_total: Total storage in bytes
        storage_available: Available storage in bytes
        paired: Whether device is paired with this computer
        extra: Additional device information
    """

    udid: str
    name: str
    model: str
    model_number: str
    ios_version: str
    build_version: str
    serial_number: str
    connection_type: ConnectionType
    state: DeviceState
    wifi_address: Optional[str] = None
    battery_level: Optional[int] = None
    battery_charging: Optional[bool] = None
    storage_total: Optional[int] = None
    storage_available: Optional[int] = None
    paired: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Get a display-friendly name for the device."""
        return self.name or f"{self.model} ({self.udid[:8]}...)"

    @property
    def short_udid(self) -> str:
        """Get a shortened UDID for display."""
        return f"{self.udid[:8]}..."

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "udid": self.udid,
            "name": self.name,
            "model": self.model,
            "model_number": self.model_number,
            "ios_version": self.ios_version,
            "build_version": self.build_version,
            "serial_number": self.serial_number,
            "connection_type": self.connection_type.value,
            "state": self.state.value,
            "wifi_address": self.wifi_address,
            "battery_level": self.battery_level,
            "battery_charging": self.battery_charging,
            "storage_total": self.storage_total,
            "storage_available": self.storage_available,
            "paired": self.paired,
        }


class DeviceDetector:
    """
    Handles iOS device detection and enumeration.

    This class provides methods for listing connected iOS devices,
    retrieving device information, and monitoring for device
    connection/disconnection events.

    Example:
        detector = DeviceDetector()

        # List all devices
        for device in detector.list_devices():
            print(f"{device.name}: {device.ios_version}")

        # Get specific device
        device = detector.get_device("00008030-001234567890001E")
        if device:
            print(f"Found: {device.name}")
    """

    def __init__(self, include_wifi: bool = True):
        """
        Initialize the device detector.

        Args:
            include_wifi: Whether to include Wi-Fi connected devices
                         in device listings. Default is True.
        """
        self._include_wifi = include_wifi
        self._device_cache: dict[str, DeviceInfo] = {}
        logger.debug(
            f"DeviceDetector initialized (include_wifi={include_wifi})"
        )

    def list_devices(self, refresh: bool = True) -> list[DeviceInfo]:
        """
        List all connected iOS devices.

        Args:
            refresh: Whether to refresh the device list. If False,
                    returns cached results.

        Returns:
            List of DeviceInfo objects for each connected device.
        """
        if refresh:
            self._refresh_device_list()

        return list(self._device_cache.values())

    def get_device(self, udid: str) -> Optional[DeviceInfo]:
        """
        Get information for a specific device.

        Args:
            udid: The device's unique identifier.

        Returns:
            DeviceInfo if found, None otherwise.
        """
        # Try cache first
        if udid in self._device_cache:
            return self._device_cache[udid]

        # Refresh and try again
        self._refresh_device_list()
        return self._device_cache.get(udid)

    def get_device_or_raise(self, udid: str) -> DeviceInfo:
        """
        Get information for a specific device, raising if not found.

        Args:
            udid: The device's unique identifier.

        Returns:
            DeviceInfo for the device.

        Raises:
            DeviceNotFoundError: If no device with the given UDID is found.
        """
        device = self.get_device(udid)
        if device is None:
            raise DeviceNotFoundError(udid)
        return device

    def refresh(self) -> None:
        """Refresh the device list."""
        self._refresh_device_list()

    def _refresh_device_list(self) -> None:
        """Internal method to refresh the device cache."""
        self._device_cache.clear()

        # First, try USB devices via usbmuxd
        try:
            mux_devices = usbmux_list_devices()

            for mux_device in mux_devices:
                try:
                    device_info = self._get_device_info(mux_device)
                    if device_info:
                        self._device_cache[device_info.udid] = device_info
                except Exception as e:
                    logger.warning(
                        f"Failed to get info for device: {e}"
                    )

        except (FileNotFoundError, OSError) as e:
            # Reason: usbmuxd socket not found - daemon not running or no device
            logger.debug(f"usbmuxd not available: {e}")

        except MuxException as e:
            logger.debug(f"usbmuxd error (may be normal if no USB devices): {e}")

        # Then, try Wi-Fi devices via Bonjour if enabled
        if self._include_wifi:
            self._discover_wifi_devices()

        logger.debug(f"Found {len(self._device_cache)} device(s)")

    def _discover_wifi_devices(self) -> None:
        """Discover Wi-Fi devices via Bonjour and add to cache."""
        try:
            from orange.core.connection.wireless import WirelessDiscovery

            discovery = WirelessDiscovery()
            # Use more retries for reliable discovery (mDNS is intermittent)
            wifi_devices = discovery.discover(timeout=5.0, retries=4, use_cache=True)

            for wifi_dev in wifi_devices:
                try:
                    address = wifi_dev.address
                    # Use standard lockdownd port (62078) instead of advertised port
                    # Bonjour often advertises a different port that doesn't work
                    port = LOCKDOWN_PORT

                    if not address:
                        continue

                    device_info = self._get_wifi_device_info(address, port)
                    if device_info and device_info.udid not in self._device_cache:
                        self._device_cache[device_info.udid] = device_info
                        logger.debug(f"Found Wi-Fi device: {device_info.name} at {address}")

                except Exception as e:
                    logger.debug(f"Could not get info for Wi-Fi device: {e}")

        except ImportError:
            logger.debug("Bonjour discovery not available")
        except Exception as e:
            logger.debug(f"Wi-Fi discovery error: {e}")

    def _get_wifi_device_info(self, address: str, port: int) -> Optional["DeviceInfo"]:
        """Get device info for a Wi-Fi device."""
        # Try connecting with available pairing records
        pair_records = self._get_available_pairing_records()

        # Try each pairing record until one works
        for udid, pair_record in pair_records.items():
            try:
                lockdown = create_using_tcp(
                    hostname=address,
                    port=port,
                    autopair=False,
                    pair_record=pair_record,
                )
                all_values = lockdown.all_values

                device_udid = all_values.get("UniqueDeviceID", "")
                if not device_udid:
                    continue

                return DeviceInfo(
                    udid=device_udid,
                    name=all_values.get("DeviceName", "Unknown"),
                    model=all_values.get("DeviceClass", "Unknown"),
                    model_number=all_values.get("ProductType", "Unknown"),
                    ios_version=all_values.get("ProductVersion", "Unknown"),
                    build_version=all_values.get("BuildVersion", "Unknown"),
                    serial_number=all_values.get("SerialNumber", "Unknown"),
                    connection_type=ConnectionType.WIFI,
                    state=DeviceState.PAIRED,
                    wifi_address=address,
                    battery_level=self._get_battery_level(all_values),
                    battery_charging=all_values.get("BatteryIsCharging"),
                    paired=True,
                    extra={
                        "hardware_model": all_values.get("HardwareModel"),
                        "wifi_port": port,
                    },
                )
            except Exception as e:
                logger.debug(f"Pairing record {udid[:8]}... failed for {address}:{port}: {e}")
                continue

        # If no pairing record worked, try without one (for unpaired discovery)
        try:
            lockdown = create_using_tcp(
                hostname=address,
                port=port,
                autopair=False,
            )
            all_values = lockdown.all_values

            device_udid = all_values.get("UniqueDeviceID", "")
            if not device_udid:
                return None

            return DeviceInfo(
                udid=device_udid,
                name=all_values.get("DeviceName", "Unknown"),
                model=all_values.get("DeviceClass", "Unknown"),
                model_number=all_values.get("ProductType", "Unknown"),
                ios_version=all_values.get("ProductVersion", "Unknown"),
                build_version=all_values.get("BuildVersion", "Unknown"),
                serial_number=all_values.get("SerialNumber", "Unknown"),
                connection_type=ConnectionType.WIFI,
                state=DeviceState.PAIRED,
                wifi_address=address,
                battery_level=self._get_battery_level(all_values),
                battery_charging=all_values.get("BatteryIsCharging"),
                paired=True,
                extra={
                    "hardware_model": all_values.get("HardwareModel"),
                    "wifi_port": port,
                },
            )
        except Exception as e:
            logger.debug(f"Could not connect to Wi-Fi device at {address}:{port}: {e}")
            return None

    def _get_available_pairing_records(self) -> dict[str, dict]:
        """Load all available pairing records from the system."""
        import plistlib
        from pathlib import Path

        records: dict[str, dict] = {}

        # Standard pairing record locations
        pairing_dirs = [
            Path("/var/lib/lockdown"),  # Linux
            Path.home() / "Library/Lockdown",  # macOS
        ]

        for pairing_dir in pairing_dirs:
            if not pairing_dir.exists():
                continue

            for plist_file in pairing_dir.glob("*.plist"):
                try:
                    # Extract UDID from filename (filename is {udid}.plist)
                    udid = plist_file.stem
                    if len(udid) < 20:  # Skip non-UDID files like SystemConfiguration.plist
                        continue

                    with open(plist_file, "rb") as f:
                        records[udid] = plistlib.load(f)
                except Exception as e:
                    logger.debug(f"Could not load pairing record {plist_file}: {e}")

        return records

    def _get_device_info(self, mux_device: Any) -> Optional[DeviceInfo]:
        """
        Get detailed information for a device.

        Args:
            mux_device: Device object from usbmux.

        Returns:
            DeviceInfo object or None if info couldn't be retrieved.
        """
        udid = mux_device.serial

        # Determine connection type
        conn_type = ConnectionType.USB
        if hasattr(mux_device, "connection_type"):
            if mux_device.connection_type == "Network":
                conn_type = ConnectionType.WIFI
                if not self._include_wifi:
                    return None

        try:
            # Create lockdown client to get device info
            lockdown = create_using_usbmux(serial=udid)
            all_values = lockdown.all_values

            # Extract device information
            device_info = DeviceInfo(
                udid=udid,
                name=all_values.get("DeviceName", "Unknown"),
                model=all_values.get("DeviceClass", "Unknown"),
                model_number=all_values.get("ProductType", "Unknown"),
                ios_version=all_values.get("ProductVersion", "Unknown"),
                build_version=all_values.get("BuildVersion", "Unknown"),
                serial_number=all_values.get("SerialNumber", "Unknown"),
                connection_type=conn_type,
                state=DeviceState.PAIRED,
                wifi_address=all_values.get("WiFiAddress"),
                battery_level=self._get_battery_level(all_values),
                battery_charging=all_values.get("BatteryIsCharging"),
                paired=True,
                extra={
                    "hardware_model": all_values.get("HardwareModel"),
                    "phone_number": all_values.get("PhoneNumber"),
                    "region_info": all_values.get("RegionInfo"),
                    "time_zone": all_values.get("TimeZone"),
                    "activation_state": all_values.get("ActivationState"),
                },
            )

            return device_info

        except ConnectionFailedError:
            # Device exists but is not paired
            logger.debug(f"Device {udid} is not paired")
            return DeviceInfo(
                udid=udid,
                name="Unknown (Not Paired)",
                model="Unknown",
                model_number="Unknown",
                ios_version="Unknown",
                build_version="Unknown",
                serial_number="Unknown",
                connection_type=conn_type,
                state=DeviceState.UNPAIRED,
                paired=False,
            )

        except Exception as e:
            logger.warning(f"Failed to get device info for {udid}: {e}")
            return None

    def _get_battery_level(self, all_values: dict[str, Any]) -> Optional[int]:
        """Extract battery level from device values."""
        battery = all_values.get("BatteryCurrentCapacity")
        if battery is not None:
            try:
                return int(battery)
            except (ValueError, TypeError):
                pass
        return None
