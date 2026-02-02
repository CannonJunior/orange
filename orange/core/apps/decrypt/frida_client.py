"""
Frida client for connecting to jailbroken iOS devices.

This module manages the Frida connection lifecycle, device discovery,
and process attachment for decryption operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Any, Callable

from orange.core.apps.decrypt.exceptions import (
    FridaConnectionError,
    FridaNotInstalledError,
    AppNotFoundError,
    AppNotRunningError,
)

logger = logging.getLogger(__name__)

# Lazy import Frida to provide better error messages
_frida = None


def _get_frida():
    """Lazy import frida module."""
    global _frida
    if _frida is None:
        try:
            import frida

            _frida = frida
        except ImportError as e:
            raise FridaNotInstalledError() from e
    return _frida


@dataclass
class FridaDeviceInfo:
    """Information about a Frida-accessible device."""

    id: str
    name: str
    type: str  # 'usb', 'remote', 'local'
    udid: Optional[str] = None

    @classmethod
    def from_frida_device(cls, device: Any) -> "FridaDeviceInfo":
        """Create from a Frida device object."""
        return cls(
            id=device.id,
            name=device.name,
            type=device.type,
            udid=device.id if device.type == "usb" else None,
        )


@dataclass
class FridaAppInfo:
    """Information about an app from Frida."""

    identifier: str
    name: str
    pid: int  # 0 if not running

    @classmethod
    def from_frida_app(cls, app: Any) -> "FridaAppInfo":
        """Create from a Frida application object."""
        return cls(
            identifier=app.identifier,
            name=app.name,
            pid=app.pid if hasattr(app, "pid") else 0,
        )


class FridaClient:
    """
    Manages Frida connection to jailbroken iOS devices.

    This class handles device discovery, connection management,
    and process spawning/attachment for decryption operations.

    Example:
        client = FridaClient(udid="00008030-...")
        client.connect()

        # Spawn and attach to an app
        session = client.spawn("com.netflix.Netflix")

        # Or attach to running app
        session = client.attach(pid=1234)

        client.close()

    Attributes:
        udid: Target device UDID (for USB connection)
        host: Remote host for SSH tunnel (e.g., "localhost:27042")
        device: Connected Frida device object
    """

    def __init__(
        self,
        udid: Optional[str] = None,
        host: Optional[str] = None,
    ):
        """
        Initialize Frida client.

        Args:
            udid: Target device UDID (for USB connection).
                  If None, will auto-detect single USB device.
            host: Remote Frida host (e.g., "localhost:27042").
                  Used when connecting via SSH tunnel.
        """
        self.udid = udid
        self.host = host
        self._device: Optional[Any] = None
        self._sessions: list[Any] = []

    @property
    def device(self) -> Any:
        """Get connected Frida device."""
        if self._device is None:
            raise FridaConnectionError("Not connected to device. Call connect() first.")
        return self._device

    @property
    def is_connected(self) -> bool:
        """Check if connected to a device."""
        return self._device is not None

    def list_devices(self) -> list[FridaDeviceInfo]:
        """
        List all available Frida devices.

        Returns:
            List of FridaDeviceInfo objects.

        Raises:
            FridaNotInstalledError: If Frida is not installed.
        """
        frida = _get_frida()
        devices = frida.enumerate_devices()
        return [
            FridaDeviceInfo.from_frida_device(d)
            for d in devices
            if d.type in ("usb", "remote")
        ]

    def connect(self) -> "FridaClient":
        """
        Connect to the target device.

        If host is specified, connects to remote Frida server.
        Otherwise, connects via USB using the specified UDID
        or auto-detects a single USB device.

        Returns:
            Self for method chaining.

        Raises:
            FridaConnectionError: If connection fails.
            FridaNotInstalledError: If Frida is not installed.
        """
        frida = _get_frida()

        try:
            if self.host:
                # Connect to remote Frida server (SSH tunnel)
                logger.debug(f"Connecting to remote Frida at {self.host}")
                self._device = frida.get_device_manager().add_remote_device(self.host)
            elif self.udid:
                # Connect to specific USB device
                logger.debug(f"Connecting to USB device {self.udid}")
                self._device = frida.get_device(self.udid)
            else:
                # Auto-detect USB device
                logger.debug("Auto-detecting USB device")
                self._device = frida.get_usb_device(timeout=5)

            logger.info(f"Connected to device: {self._device.name}")
            return self

        except frida.ServerNotRunningError as e:
            raise FridaConnectionError(
                "Frida server not running on device. "
                "Install Frida from Cydia/Sileo and ensure it's running."
            ) from e
        except frida.TimedOutError as e:
            raise FridaConnectionError(
                "Connection timed out. Ensure device is connected and Frida is running."
            ) from e
        except frida.InvalidArgumentError as e:
            raise FridaConnectionError(f"Invalid device: {e}") from e
        except Exception as e:
            raise FridaConnectionError(f"Failed to connect: {e}") from e

    def get_installed_apps(self) -> list[FridaAppInfo]:
        """
        List installed applications on device.

        Returns:
            List of FridaAppInfo objects.

        Raises:
            FridaConnectionError: If not connected.
        """
        try:
            apps = self.device.enumerate_applications()
            return [FridaAppInfo.from_frida_app(app) for app in apps]
        except Exception as e:
            raise FridaConnectionError(f"Failed to enumerate apps: {e}") from e

    def get_running_processes(self) -> list[dict]:
        """
        List running processes on device.

        Returns:
            List of process info dicts with 'pid' and 'name' keys.

        Raises:
            FridaConnectionError: If not connected.
        """
        try:
            processes = self.device.enumerate_processes()
            return [{"pid": p.pid, "name": p.name} for p in processes]
        except Exception as e:
            raise FridaConnectionError(f"Failed to enumerate processes: {e}") from e

    def get_app_info(self, bundle_id: str) -> Optional[FridaAppInfo]:
        """
        Get information about a specific app.

        Args:
            bundle_id: App bundle identifier.

        Returns:
            FridaAppInfo if found, None otherwise.
        """
        apps = self.get_installed_apps()
        for app in apps:
            if app.identifier == bundle_id:
                return app
        return None

    def spawn(
        self,
        bundle_id: str,
        on_message: Optional[Callable[[dict, Optional[bytes]], None]] = None,
    ) -> Any:
        """
        Spawn an app and attach to it.

        This launches the app in a suspended state, attaches Frida,
        then resumes execution. This ensures we can intercept
        from the very beginning of app execution.

        Args:
            bundle_id: App bundle identifier to spawn.
            on_message: Optional callback for Frida messages.

        Returns:
            Frida session object.

        Raises:
            AppNotFoundError: If app is not installed.
            AppNotRunningError: If app fails to spawn.
        """
        # Verify app exists
        app_info = self.get_app_info(bundle_id)
        if not app_info:
            raise AppNotFoundError(bundle_id)

        try:
            logger.debug(f"Spawning app: {bundle_id}")

            # Spawn in suspended state
            pid = self.device.spawn([bundle_id])
            logger.debug(f"Spawned with PID: {pid}")

            # Attach to the spawned process
            session = self.device.attach(pid)
            self._sessions.append(session)

            # Set up message handler if provided
            if on_message:
                session.on("detached", lambda reason: logger.debug(f"Detached: {reason}"))

            # Resume the process
            self.device.resume(pid)
            logger.debug(f"Resumed PID: {pid}")

            return session

        except Exception as e:
            raise AppNotRunningError(bundle_id, str(e)) from e

    def attach(
        self,
        pid: Optional[int] = None,
        bundle_id: Optional[str] = None,
        on_message: Optional[Callable[[dict, Optional[bytes]], None]] = None,
    ) -> Any:
        """
        Attach to a running process.

        Args:
            pid: Process ID to attach to.
            bundle_id: Alternatively, app bundle ID (finds running process).
            on_message: Optional callback for Frida messages.

        Returns:
            Frida session object.

        Raises:
            ValueError: If neither pid nor bundle_id provided.
            AppNotRunningError: If process not found or attach fails.
        """
        if pid is None and bundle_id is None:
            raise ValueError("Must provide either pid or bundle_id")

        # Find PID from bundle_id if needed
        if pid is None and bundle_id:
            app_info = self.get_app_info(bundle_id)
            if not app_info:
                raise AppNotFoundError(bundle_id)
            if app_info.pid == 0:
                raise AppNotRunningError(bundle_id, "App is not running")
            pid = app_info.pid

        try:
            logger.debug(f"Attaching to PID: {pid}")
            session = self.device.attach(pid)
            self._sessions.append(session)

            if on_message:
                session.on("detached", lambda reason: logger.debug(f"Detached: {reason}"))

            return session

        except Exception as e:
            raise AppNotRunningError(
                bundle_id or f"PID {pid}", str(e)
            ) from e

    def create_script(self, session: Any, source: str) -> Any:
        """
        Create a Frida script in a session.

        Args:
            session: Frida session object.
            source: JavaScript source code for the script.

        Returns:
            Frida script object (not yet loaded).
        """
        return session.create_script(source)

    def close(self) -> None:
        """
        Close all sessions and disconnect from device.

        This should be called when done with decryption operations
        to clean up resources.
        """
        # Detach from all sessions
        for session in self._sessions:
            try:
                session.detach()
            except Exception as e:
                logger.debug(f"Error detaching session: {e}")

        self._sessions.clear()
        self._device = None
        logger.debug("Frida client closed")

    def __enter__(self) -> "FridaClient":
        """Context manager entry - connect to device."""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close connection."""
        self.close()
