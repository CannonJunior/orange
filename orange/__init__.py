"""
Orange - Cross-platform iOS file transfer and data management.

This package provides tools for transferring messages, music, files, and data
between iPhone/iPad and Mac, Windows, or Linux computers.
"""

__version__ = "0.1.0"
__author__ = "Orange Contributors"

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
    "__version__",
]
