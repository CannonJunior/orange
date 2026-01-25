"""
Device pairing and trust management.

This module handles the pairing workflow between the host computer
and iOS devices, including establishing trust, managing pairing records,
and handling the "Trust This Computer" prompt.

Example:
    pairing_mgr = PairingManager(udid)

    if not pairing_mgr.is_paired():
        print("Please tap 'Trust' on your device...")
        success = pairing_mgr.pair(
            on_prompt=lambda: print("Waiting for user..."),
            timeout=60
        )
        if success:
            print("Pairing successful!")
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Callable, Optional

from pymobiledevice3.lockdown import create_using_usbmux, LockdownClient
from pymobiledevice3.exceptions import (
    PairingError as PyMobilePairingError,
    ConnectionFailedError,
    MuxException,
    PasswordRequiredError,
)

from orange.constants import DEFAULT_PAIRING_TIMEOUT
from orange.exceptions import (
    DeviceNotFoundError,
    PairingError,
    PairingTimeoutError,
    ConnectionError,
)

logger = logging.getLogger(__name__)


class PairingState(Enum):
    """State of the pairing process."""

    NOT_PAIRED = "not_paired"
    PAIRING_IN_PROGRESS = "pairing_in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    PAIRED = "paired"
    PAIRING_FAILED = "pairing_failed"


class PairingManager:
    """
    Manages device pairing and trust relationships.

    This class handles the complete pairing workflow with iOS devices,
    including checking pairing status, initiating pairing, and handling
    user prompts.

    The pairing process:
    1. Host initiates pairing request
    2. Device shows "Trust This Computer?" dialog
    3. User must enter passcode and tap "Trust"
    4. Cryptographic keys are exchanged
    5. Pairing record is saved on both host and device

    Example:
        manager = PairingManager("00008030-001234567890001E")

        # Check if already paired
        if manager.is_paired():
            print("Device is already paired")
        else:
            # Initiate pairing
            success = manager.pair()
            if success:
                print("Paired successfully!")
    """

    def __init__(self, udid: str):
        """
        Initialize pairing manager for a device.

        Args:
            udid: The unique device identifier to manage pairing for.
        """
        self._udid = udid
        self._state = PairingState.NOT_PAIRED
        self._lockdown: Optional[LockdownClient] = None
        logger.debug(f"PairingManager initialized for device {udid[:8]}...")

    @property
    def udid(self) -> str:
        """The device UDID this manager is for."""
        return self._udid

    @property
    def state(self) -> PairingState:
        """Current pairing state."""
        return self._state

    def is_paired(self) -> bool:
        """
        Check if the device is currently paired with this computer.

        Returns:
            True if the device is paired, False otherwise.
        """
        try:
            lockdown = create_using_usbmux(serial=self._udid)
            # If we can get all_values, we're paired
            _ = lockdown.all_values
            self._state = PairingState.PAIRED
            return True

        except ConnectionFailedError:
            logger.debug(f"Device {self._udid[:8]}... is not paired")
            self._state = PairingState.NOT_PAIRED
            return False

        except MuxException as e:
            logger.error(f"Failed to check pairing status: {e}")
            raise DeviceNotFoundError(self._udid)

    def pair(
        self,
        on_prompt: Optional[Callable[[], None]] = None,
        timeout: int = DEFAULT_PAIRING_TIMEOUT,
        poll_interval: float = 1.0,
    ) -> bool:
        """
        Initiate pairing with the device.

        This method starts the pairing process and waits for the user
        to accept the "Trust This Computer?" prompt on their device.
        The user will need to enter their passcode (iOS 11+) and tap "Trust".

        Args:
            on_prompt: Optional callback function to call when the user
                      needs to interact with the device. This is called
                      when the pairing process is waiting for user action.
            timeout: Maximum seconds to wait for user to accept pairing.
                    Default is 60 seconds.
            poll_interval: How often to check for pairing completion.
                          Default is 1 second.

        Returns:
            True if pairing was successful, False if it failed or timed out.

        Raises:
            DeviceNotFoundError: If the device is not connected.
            PairingError: If pairing fails for a reason other than timeout.
        """
        self._state = PairingState.PAIRING_IN_PROGRESS
        logger.info(f"Initiating pairing with device {self._udid[:8]}...")

        try:
            # Create lockdown client
            lockdown = create_using_usbmux(
                serial=self._udid,
                autopair=False,  # Don't auto-pair, we want to control it
            )

            # Check if we need to pair
            if lockdown.paired:
                logger.info("Device is already paired")
                self._state = PairingState.PAIRED
                return True

            # Notify that we're waiting for user
            self._state = PairingState.WAITING_FOR_USER
            if on_prompt:
                on_prompt()

            # Attempt to pair
            start_time = time.time()

            while (time.time() - start_time) < timeout:
                try:
                    lockdown.pair()
                    logger.info("Pairing successful!")
                    self._state = PairingState.PAIRED
                    return True

                except PasswordRequiredError:
                    # User hasn't accepted yet, keep waiting
                    logger.debug("Waiting for user to accept pairing...")
                    time.sleep(poll_interval)

                except PyMobilePairingError as e:
                    # Some other pairing error
                    error_msg = str(e)
                    if "UserDeniedPairing" in error_msg:
                        logger.warning("User denied pairing request")
                        self._state = PairingState.PAIRING_FAILED
                        raise PairingError(self._udid, "User denied pairing")
                    elif "PasswordProtected" in error_msg:
                        # Device is locked, wait
                        logger.debug("Device is locked, waiting...")
                        time.sleep(poll_interval)
                    else:
                        # Unknown error
                        logger.error(f"Pairing error: {e}")
                        self._state = PairingState.PAIRING_FAILED
                        raise PairingError(self._udid, str(e))

            # Timeout reached
            logger.warning(f"Pairing timed out after {timeout} seconds")
            self._state = PairingState.PAIRING_FAILED
            raise PairingTimeoutError(self._udid, timeout)

        except MuxException as e:
            logger.error(f"Device not found: {e}")
            self._state = PairingState.NOT_PAIRED
            raise DeviceNotFoundError(self._udid)

        except ConnectionFailedError as e:
            logger.error(f"Connection failed: {e}")
            self._state = PairingState.PAIRING_FAILED
            raise PairingError(self._udid, str(e))

    def unpair(self) -> bool:
        """
        Remove pairing with the device.

        This will remove the pairing record from the host computer.
        Note that the device may still have the pairing record; the user
        can remove it from Settings > General > Reset > Reset Location & Privacy.

        Returns:
            True if unpairing was successful, False otherwise.
        """
        try:
            lockdown = create_using_usbmux(serial=self._udid)
            lockdown.unpair()
            logger.info(f"Unpaired from device {self._udid[:8]}...")
            self._state = PairingState.NOT_PAIRED
            return True

        except MuxException:
            raise DeviceNotFoundError(self._udid)

        except Exception as e:
            logger.error(f"Failed to unpair: {e}")
            return False

    def validate_pairing(self) -> bool:
        """
        Validate that the existing pairing is still valid.

        iOS pairing records can expire (after 30 days of non-use in iOS 11+)
        or be invalidated by the user. This method checks if the current
        pairing record is still accepted by the device.

        Returns:
            True if pairing is valid, False if it needs to be re-established.
        """
        try:
            lockdown = create_using_usbmux(serial=self._udid)
            lockdown.validate_pairing()
            self._state = PairingState.PAIRED
            return True

        except ConnectionFailedError:
            logger.debug("Pairing validation failed")
            self._state = PairingState.NOT_PAIRED
            return False

        except MuxException:
            raise DeviceNotFoundError(self._udid)

        except Exception as e:
            logger.warning(f"Pairing validation error: {e}")
            self._state = PairingState.NOT_PAIRED
            return False


def check_any_device_paired() -> bool:
    """
    Check if any iOS device is currently paired with this computer.

    Returns:
        True if at least one device is paired, False otherwise.
    """
    from orange.core.connection.device import DeviceDetector

    detector = DeviceDetector()
    devices = detector.list_devices()

    for device in devices:
        if device.paired:
            return True

    return False
