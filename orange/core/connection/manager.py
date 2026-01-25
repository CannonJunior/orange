"""
Connection pool and lifecycle management.

This module provides high-level connection management for iOS devices,
including connection pooling, automatic reconnection, and event-driven
device state notifications.

Example:
    manager = ConnectionManager()

    # Register callbacks
    manager.on_device_connected(lambda udid: print(f"Connected: {udid}"))
    manager.on_device_disconnected(lambda udid: print(f"Disconnected: {udid}"))

    # Connect to a device
    with manager.connect(udid) as conn:
        print(f"Device name: {conn.device_name}")
        print(f"iOS version: {conn.ios_version}")

        # Use device services
        afc = conn.get_service("afc")
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Optional, TypeVar

from pymobiledevice3.lockdown import create_using_usbmux, LockdownClient
from pymobiledevice3.services.afc import AfcService
from pymobiledevice3.exceptions import (
    MuxException,
    ConnectionFailedError,
)

from orange.constants import (
    DEFAULT_CONNECTION_TIMEOUT,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_DELAY,
    SERVICE_AFC,
)
from orange.exceptions import (
    DeviceNotFoundError,
    DeviceNotPairedError,
    ConnectionTimeoutError,
    ServiceError,
)
from orange.core.connection.device import DeviceDetector, DeviceInfo, DeviceState

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ConnectionState:
    """Tracks the state of a device connection."""

    udid: str
    connected: bool = False
    last_connected: Optional[float] = None
    reconnect_attempts: int = 0
    error: Optional[str] = None


class DeviceConnection:
    """
    Represents an active connection to an iOS device.

    This class wraps a lockdown client and provides convenient access
    to device information and services. Use ConnectionManager.connect()
    to obtain instances.

    Attributes:
        udid: The device's unique identifier
        device_name: User-assigned device name
        ios_version: iOS version string
        is_connected: Whether the connection is active
    """

    def __init__(self, udid: str, lockdown: LockdownClient):
        """
        Initialize a device connection.

        Args:
            udid: Device unique identifier.
            lockdown: Established lockdown client.
        """
        self._udid = udid
        self._lockdown = lockdown
        self._services: dict[str, Any] = {}
        self._closed = False

        # Cache device info
        all_values = lockdown.all_values
        self._device_name = all_values.get("DeviceName", "Unknown")
        self._ios_version = all_values.get("ProductVersion", "Unknown")
        self._model = all_values.get("DeviceClass", "Unknown")

        logger.debug(f"DeviceConnection created for {self._device_name}")

    @property
    def udid(self) -> str:
        """Device unique identifier."""
        return self._udid

    @property
    def device_name(self) -> str:
        """User-assigned device name."""
        return self._device_name

    @property
    def ios_version(self) -> str:
        """iOS version string."""
        return self._ios_version

    @property
    def model(self) -> str:
        """Device model (e.g., 'iPhone', 'iPad')."""
        return self._model

    @property
    def is_connected(self) -> bool:
        """Whether the connection is active."""
        return not self._closed and self._lockdown is not None

    @property
    def lockdown(self) -> LockdownClient:
        """
        Get the underlying lockdown client.

        Returns:
            The LockdownClient for this connection.

        Raises:
            ConnectionError: If the connection is closed.
        """
        if self._closed:
            raise ConnectionError("Connection is closed")
        return self._lockdown

    def get_all_values(self) -> dict[str, Any]:
        """
        Get all device information values.

        Returns:
            Dictionary of all device information.
        """
        return self._lockdown.all_values

    def get_value(self, key: str, domain: Optional[str] = None) -> Any:
        """
        Get a specific device value.

        Args:
            key: The value key to retrieve.
            domain: Optional domain for the value.

        Returns:
            The requested value, or None if not found.
        """
        return self._lockdown.get_value(key=key, domain=domain)

    def get_service(self, service_name: str) -> Any:
        """
        Get a device service.

        Services are cached, so multiple calls with the same service name
        will return the same service instance.

        Args:
            service_name: Name of the service (e.g., "afc", "backup").

        Returns:
            The requested service client.

        Raises:
            ServiceError: If the service cannot be started.
        """
        if service_name in self._services:
            return self._services[service_name]

        try:
            if service_name == "afc" or service_name == SERVICE_AFC:
                service = AfcService(self._lockdown)
            else:
                # Generic service start
                service = self._lockdown.start_lockdown_service(service_name)

            self._services[service_name] = service
            return service

        except Exception as e:
            logger.error(f"Failed to start service {service_name}: {e}")
            raise ServiceError(service_name, str(e))

    def close(self) -> None:
        """
        Close the connection and release resources.

        After calling close(), the connection cannot be reused.
        """
        if self._closed:
            return

        logger.debug(f"Closing connection to {self._device_name}")

        # Close all services
        for name, service in self._services.items():
            try:
                if hasattr(service, "close"):
                    service.close()
            except Exception as e:
                logger.warning(f"Error closing service {name}: {e}")

        self._services.clear()
        self._closed = True

    def __enter__(self) -> DeviceConnection:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


class ConnectionManager:
    """
    Manages connections to multiple iOS devices.

    This class provides connection pooling, automatic reconnection,
    and event-driven device state notifications. It's the recommended
    way to manage device connections in applications.

    Example:
        manager = ConnectionManager()

        # List available devices
        devices = manager.list_devices()

        # Connect to first device
        if devices:
            with manager.connect(devices[0].udid) as conn:
                print(f"Connected to {conn.device_name}")
    """

    def __init__(
        self,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS,
    ):
        """
        Initialize the connection manager.

        Args:
            auto_reconnect: Whether to automatically attempt reconnection
                           when a connection is lost. Default is True.
            max_reconnect_attempts: Maximum number of reconnection attempts.
                                   Default is 3.
        """
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts

        self._detector = DeviceDetector()
        self._connections: dict[str, DeviceConnection] = {}
        self._connection_states: dict[str, ConnectionState] = {}
        self._lock = threading.RLock()

        # Event callbacks
        self._on_connected: list[Callable[[str], None]] = []
        self._on_disconnected: list[Callable[[str], None]] = []

        logger.debug("ConnectionManager initialized")

    def on_device_connected(self, callback: Callable[[str], None]) -> None:
        """
        Register callback for device connection events.

        The callback will be called with the device UDID when a device
        becomes connected.

        Args:
            callback: Function to call when a device connects.
        """
        self._on_connected.append(callback)

    def on_device_disconnected(self, callback: Callable[[str], None]) -> None:
        """
        Register callback for device disconnection events.

        The callback will be called with the device UDID when a device
        becomes disconnected.

        Args:
            callback: Function to call when a device disconnects.
        """
        self._on_disconnected.append(callback)

    def list_devices(self, refresh: bool = True) -> list[DeviceInfo]:
        """
        List all available devices.

        Args:
            refresh: Whether to refresh the device list.

        Returns:
            List of DeviceInfo for available devices.
        """
        return self._detector.list_devices(refresh=refresh)

    def get_device(self, udid: str) -> Optional[DeviceInfo]:
        """
        Get information for a specific device.

        Args:
            udid: The device UDID.

        Returns:
            DeviceInfo if found, None otherwise.
        """
        return self._detector.get_device(udid)

    @contextmanager
    def connect(
        self,
        udid: str,
        timeout: int = DEFAULT_CONNECTION_TIMEOUT,
    ) -> Generator[DeviceConnection, None, None]:
        """
        Context manager for device connection.

        This is the recommended way to connect to a device. The connection
        will be automatically closed when the context exits.

        Args:
            udid: The device UDID to connect to.
            timeout: Connection timeout in seconds.

        Yields:
            DeviceConnection for the connected device.

        Raises:
            DeviceNotFoundError: If the device is not connected.
            DeviceNotPairedError: If the device is not paired.
            ConnectionTimeoutError: If connection times out.

        Example:
            with manager.connect(udid) as conn:
                print(f"Connected to {conn.device_name}")
                # Connection is automatically closed when exiting
        """
        connection = self.get_connection(udid, timeout=timeout)
        try:
            yield connection
        finally:
            # Don't close - keep in pool for reuse
            pass

    def get_connection(
        self,
        udid: str,
        timeout: int = DEFAULT_CONNECTION_TIMEOUT,
    ) -> DeviceConnection:
        """
        Get a connection to a device.

        If a connection already exists in the pool, it will be reused.
        Otherwise, a new connection is established.

        Args:
            udid: The device UDID to connect to.
            timeout: Connection timeout in seconds.

        Returns:
            DeviceConnection for the device.

        Raises:
            DeviceNotFoundError: If the device is not connected.
            DeviceNotPairedError: If the device is not paired.
            ConnectionTimeoutError: If connection times out.
        """
        with self._lock:
            # Check for existing connection
            if udid in self._connections:
                conn = self._connections[udid]
                if conn.is_connected:
                    return conn
                else:
                    # Connection was closed, remove it
                    del self._connections[udid]

            # Create new connection
            connection = self._create_connection(udid, timeout)
            self._connections[udid] = connection

            # Update state
            self._connection_states[udid] = ConnectionState(
                udid=udid,
                connected=True,
                last_connected=time.time(),
            )

            # Fire callbacks
            for callback in self._on_connected:
                try:
                    callback(udid)
                except Exception as e:
                    logger.warning(f"Error in connected callback: {e}")

            return connection

    def _create_connection(
        self,
        udid: str,
        timeout: int,
    ) -> DeviceConnection:
        """
        Create a new connection to a device.

        Args:
            udid: Device UDID.
            timeout: Connection timeout.

        Returns:
            New DeviceConnection.

        Raises:
            DeviceNotFoundError: If device not found.
            DeviceNotPairedError: If device not paired.
            ConnectionTimeoutError: If connection times out.
        """
        logger.info(f"Connecting to device {udid[:8]}...")

        start_time = time.time()
        last_error: Optional[Exception] = None

        while (time.time() - start_time) < timeout:
            try:
                lockdown = create_using_usbmux(serial=udid)
                return DeviceConnection(udid, lockdown)

            except ConnectionFailedError as e:
                # Reason: Must catch ConnectionFailedError before MuxException
                # since ConnectionFailedError may be a subclass of MuxException
                error_msg = str(e)
                if "NotPaired" in error_msg or "InvalidHostID" in error_msg:
                    raise DeviceNotPairedError(udid)
                last_error = e
                logger.debug(f"Connection attempt failed: {e}")
                time.sleep(0.5)

            except MuxException as e:
                logger.debug(f"Device not found in mux: {e}")
                raise DeviceNotFoundError(udid)

            except Exception as e:
                last_error = e
                logger.debug(f"Connection error: {e}")
                time.sleep(0.5)

        # Timeout
        logger.error(f"Connection to {udid[:8]}... timed out")
        raise ConnectionTimeoutError(udid, timeout)

    def disconnect(self, udid: str) -> None:
        """
        Disconnect from a device.

        Args:
            udid: The device UDID to disconnect from.
        """
        with self._lock:
            if udid in self._connections:
                conn = self._connections.pop(udid)
                conn.close()

                # Update state
                if udid in self._connection_states:
                    self._connection_states[udid].connected = False

                # Fire callbacks
                for callback in self._on_disconnected:
                    try:
                        callback(udid)
                    except Exception as e:
                        logger.warning(f"Error in disconnected callback: {e}")

                logger.info(f"Disconnected from device {udid[:8]}...")

    def close_all(self) -> None:
        """Close all active connections."""
        with self._lock:
            for udid in list(self._connections.keys()):
                self.disconnect(udid)

    def is_connected(self, udid: str) -> bool:
        """
        Check if a device is currently connected.

        Args:
            udid: The device UDID.

        Returns:
            True if connected, False otherwise.
        """
        with self._lock:
            if udid in self._connections:
                return self._connections[udid].is_connected
            return False

    def __enter__(self) -> ConnectionManager:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close all connections."""
        self.close_all()
