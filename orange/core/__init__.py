"""
Orange core library modules.

This package contains the core functionality for iOS device communication,
backup management, file transfer, and data extraction.
"""

from orange.core.connection import (
    ConnectionManager,
    DeviceConnection,
    DeviceDetector,
    DeviceInfo,
    PairingManager,
)

__all__ = [
    "ConnectionManager",
    "DeviceConnection",
    "DeviceDetector",
    "DeviceInfo",
    "PairingManager",
]
