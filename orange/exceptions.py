"""
Custom exceptions for the Orange package.

All Orange-specific exceptions inherit from OrangeError to allow
catching all package exceptions with a single except clause.
"""

from typing import Optional


class OrangeError(Exception):
    """Base exception for all Orange errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


# Connection errors
class ConnectionError(OrangeError):
    """Base class for connection-related errors."""

    pass


class DeviceNotFoundError(ConnectionError):
    """Device with specified UDID not found."""

    def __init__(self, udid: str):
        self.udid = udid
        super().__init__(
            f"Device not found",
            f"No device found with UDID: {udid}"
        )


class DeviceNotPairedError(ConnectionError):
    """Device is not paired with this computer."""

    def __init__(self, udid: str):
        self.udid = udid
        super().__init__(
            "Device not paired",
            f"Device {udid} is not paired with this computer. Run 'orange device pair {udid}' first."
        )


class PairingError(ConnectionError):
    """Failed to establish pairing with device."""

    def __init__(self, udid: str, reason: Optional[str] = None):
        self.udid = udid
        details = f"Device: {udid}"
        if reason:
            details += f", Reason: {reason}"
        super().__init__("Pairing failed", details)


class PairingTimeoutError(PairingError):
    """Pairing timed out waiting for user to accept."""

    def __init__(self, udid: str, timeout: int):
        self.timeout = timeout
        super().__init__(
            udid,
            f"User did not accept trust prompt within {timeout} seconds"
        )


class ConnectionTimeoutError(ConnectionError):
    """Connection to device timed out."""

    def __init__(self, udid: str, timeout: int):
        self.udid = udid
        self.timeout = timeout
        super().__init__(
            "Connection timeout",
            f"Could not connect to device {udid} within {timeout} seconds"
        )


class ServiceError(ConnectionError):
    """Failed to start or communicate with a device service."""

    def __init__(self, service_name: str, reason: Optional[str] = None):
        self.service_name = service_name
        details = f"Service: {service_name}"
        if reason:
            details += f", Reason: {reason}"
        super().__init__("Service error", details)


# Backup errors
class BackupError(OrangeError):
    """Base class for backup-related errors."""

    pass


class BackupNotFoundError(BackupError):
    """Specified backup not found."""

    def __init__(self, backup_id: str):
        self.backup_id = backup_id
        super().__init__(
            "Backup not found",
            f"No backup found with ID: {backup_id}"
        )


class BackupEncryptedError(BackupError):
    """Backup is encrypted but no password provided."""

    def __init__(self, backup_id: str):
        self.backup_id = backup_id
        super().__init__(
            "Backup is encrypted",
            f"Backup {backup_id} is encrypted. Please provide the password."
        )


class BackupDecryptionError(BackupError):
    """Failed to decrypt backup (likely wrong password)."""

    def __init__(self, backup_id: str):
        self.backup_id = backup_id
        super().__init__(
            "Decryption failed",
            f"Could not decrypt backup {backup_id}. Is the password correct?"
        )


# Transfer errors
class TransferError(OrangeError):
    """Base class for file transfer errors."""

    pass


class FileNotFoundOnDeviceError(TransferError):
    """Specified file not found on device."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(
            "File not found on device",
            f"Path: {path}"
        )


class TransferInterruptedError(TransferError):
    """File transfer was interrupted."""

    def __init__(self, path: str, bytes_transferred: int, total_bytes: int):
        self.path = path
        self.bytes_transferred = bytes_transferred
        self.total_bytes = total_bytes
        super().__init__(
            "Transfer interrupted",
            f"Transferred {bytes_transferred}/{total_bytes} bytes of {path}"
        )


# Data extraction errors
class DataExtractionError(OrangeError):
    """Base class for data extraction errors."""

    pass


class DatabaseError(DataExtractionError):
    """Error reading or parsing a database file."""

    def __init__(self, database: str, reason: Optional[str] = None):
        self.database = database
        details = f"Database: {database}"
        if reason:
            details += f", Reason: {reason}"
        super().__init__("Database error", details)


# Export errors
class ExportError(OrangeError):
    """Base class for data export errors."""

    pass


class ExportFormatError(ExportError):
    """Unsupported or invalid export format."""

    def __init__(self, format_name: str, supported_formats: list[str]):
        self.format_name = format_name
        self.supported_formats = supported_formats
        super().__init__(
            "Unsupported export format",
            f"'{format_name}' not supported. Use one of: {', '.join(supported_formats)}"
        )
