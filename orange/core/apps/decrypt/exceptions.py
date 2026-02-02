"""
Exceptions for IPA decryption operations.

This module defines custom exceptions for various failure modes
encountered during app decryption.
"""

from typing import Optional

from orange.exceptions import OrangeError


class DecryptionError(OrangeError):
    """Base exception for decryption-related errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message, details)


class FridaConnectionError(DecryptionError):
    """Failed to connect to Frida on device."""

    def __init__(
        self,
        message: str = "Failed to connect to Frida on device",
        details: Optional[str] = None,
    ):
        super().__init__(message, details)


class FridaNotInstalledError(DecryptionError):
    """Frida is not installed or available."""

    def __init__(self):
        super().__init__(
            "Frida tools not installed",
            "Install with: pip install frida-tools",
        )


class JailbreakRequiredError(DecryptionError):
    """Device must be jailbroken for this operation."""

    def __init__(self):
        super().__init__(
            "Jailbreak required",
            "This operation requires a jailbroken device with Frida server installed.",
        )


class AppNotFoundError(DecryptionError):
    """Target app not found on device."""

    def __init__(self, bundle_id: str):
        self.bundle_id = bundle_id
        super().__init__(
            "App not found on device",
            f"Bundle ID: {bundle_id}",
        )


class AppNotRunningError(DecryptionError):
    """Failed to spawn or attach to target app."""

    def __init__(self, bundle_id: str, reason: str = ""):
        self.bundle_id = bundle_id
        details = f"Bundle ID: {bundle_id}"
        if reason:
            details += f", Reason: {reason}"
        super().__init__("Failed to run app", details)


class BinaryNotEncryptedError(DecryptionError):
    """Binary is not FairPlay encrypted."""

    def __init__(self, binary_name: str):
        self.binary_name = binary_name
        super().__init__(
            "Binary is not encrypted",
            f"'{binary_name}' has cryptid=0 (already decrypted)",
        )


class MachOParseError(DecryptionError):
    """Failed to parse Mach-O binary."""

    def __init__(self, message: str = "Failed to parse Mach-O binary"):
        super().__init__(message)


class SSHConnectionError(DecryptionError):
    """Failed to establish SSH connection to device."""

    def __init__(self, host: str, reason: str = ""):
        self.host = host
        details = f"Host: {host}"
        if reason:
            details += f", Reason: {reason}"
        super().__init__("SSH connection failed", details)
