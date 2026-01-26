# Orange Project - Implementation Plan

**Version:** 1.1
**Date:** January 25, 2026
**Status:** Phase 1 Complete - In Production

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Scope](#project-scope)
3. [Architecture Overview](#architecture-overview)
4. [Module Specifications](#module-specifications)
5. [Phase 1: Connection Module (MVP)](#phase-1-connection-module-mvp)
6. [Phase 2: Backup Engine](#phase-2-backup-engine)
7. [Phase 3: File Transfer](#phase-3-file-transfer)
8. [Phase 4: Data Extraction](#phase-4-data-extraction)
9. [Phase 5: Format Conversion](#phase-5-format-conversion)
10. [Phase 6: Export & Distribution](#phase-6-export--distribution)
11. [Testing Strategy](#testing-strategy)
12. [Development Environment](#development-environment)
13. [Coding Standards](#coding-standards)
14. [Risk Mitigation](#risk-mitigation)
15. [Future Considerations](#future-considerations)

---

## Executive Summary

Orange is a cross-platform iOS file transfer and data management platform. This implementation plan defines a modular architecture where each component can be developed, tested, and released independently while maintaining interoperability.

**Primary Goal:** Create reusable modules for iOS device communication that can power multiple applications (file transfer, health data sync, backup management, etc.).

**MVP Deliverable:** A working CLI tool that can detect iOS devices, establish trust, and retrieve basic device information.

---

## Implementation Progress

### Phase 1: Connection Module - COMPLETE (2026-01-25)

| Component | Status | Notes |
|-----------|--------|-------|
| Device Detection (USB) | ✅ Complete | `DeviceDetector`, `DeviceInfo` classes |
| Device Pairing | ✅ Complete | `PairingManager`, trust workflow |
| Wi-Fi Device Discovery | ✅ Complete | Standard Wi-Fi Sync protocol (no Developer Mode) |
| Connection Management | ✅ Complete | `ConnectionManager`, `DeviceConnection` |
| CLI Commands | ✅ Complete | `list`, `info`, `pair`, `unpair`, `ping`, `scan`, `wifi` |
| Test Suite | ✅ Complete | 65 tests, 62% coverage |

**Implementation Details:**
- Wi-Fi Sync uses Apple's standard protocol (port 62078, Bonjour `_apple-mobdev2._tcp`)
- Same protocol as iTunes/Finder - NO Developer Mode required
- Requires one-time USB pairing, then wireless thereafter
- CLI commands auto-select device when only one is connected (UDID optional)

**Known Issues (Backlog):**
- `orange device scan` shows Device Name but Model/iOS/UDID columns are empty
- See `BACKLOG-TODO-LIST.md` for details

### Phases 2-6: Planned

See detailed specifications below.

---

## Project Scope

### In Scope

| Feature | Priority | Phase |
|---------|----------|-------|
| Device detection (USB) | Critical | 1 |
| Device pairing/trust | Critical | 1 |
| Device info retrieval | Critical | 1 |
| Wi-Fi device discovery | High | 1 |
| Full device backup | High | 2 |
| Encrypted backup support | High | 2 |
| Backup decryption | High | 2 |
| Photo/video transfer | High | 3 |
| Music transfer | High | 3 |
| Document transfer | Medium | 3 |
| Message extraction | High | 4 |
| Contact extraction | Medium | 4 |
| Calendar/Notes extraction | Medium | 4 |
| Audio format conversion | Medium | 5 |
| Video format conversion | Low | 5 |
| PDF export | High | 6 |
| CSV/JSON export | Medium | 6 |
| macOS distribution | High | 6 |
| Windows distribution | High | 6 |
| Linux distribution | High | 6 |

### Out of Scope (v1.0)

- GUI application (future phase)
- iOS companion app (separate project for HealthKit)
- Android device support
- Cloud sync features
- Real-time device mirroring
- App installation/management

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Applications                              │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│   CLI App   │   GUI App   │   REST API  │  Health App │  Future │
│  (Phase 1)  │  (Future)   │  (Future)   │  (Separate) │   ...   │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────┬────┘
       │             │             │             │           │
       ▼             ▼             ▼             ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Orange Core Library                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ Export    │ │ Convert   │ │ Data      │ │ Transfer  │       │
│  │ Module    │ │ Module    │ │ Module    │ │ Module    │       │
│  │ (Phase 6) │ │ (Phase 5) │ │ (Phase 4) │ │ (Phase 3) │       │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘       │
│        │             │             │             │              │
│        └─────────────┴──────┬──────┴─────────────┘              │
│                             ▼                                    │
│                    ┌───────────────┐                            │
│                    │ Backup Module │                            │
│                    │  (Phase 2)    │                            │
│                    └───────┬───────┘                            │
│                            │                                     │
│                            ▼                                     │
│                    ┌───────────────┐                            │
│                    │  Connection   │                            │
│                    │    Module     │                            │
│                    │  (Phase 1)    │                            │
│                    └───────┬───────┘                            │
└────────────────────────────┼────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Dependencies                         │
├─────────────────────────────────────────────────────────────────┤
│  pymobiledevice3  │  pycryptodome  │  click  │  ffmpeg (opt)   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      iOS Device                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │lockdownd│  │  afcd   │  │ backup  │  │ other   │            │
│  │         │  │  (AFC)  │  │ agent   │  │services │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
orange/
├── CLAUDE.md                          # Project guidelines
├── PLANNING.md                        # This file
├── TASK.md                            # Task tracking
├── BACKLOG-TODO-LIST.md               # Deferred tasks
├── ORANGE-CONTEXT-ENGINEERING-PROMPT.md
├── README.md                          # User documentation
├── pyproject.toml                     # Project configuration
├── requirements.txt                   # Dependencies
├── setup.py                           # Package setup
│
├── docs/                              # Documentation
│   ├── literature-review-ios-emulation.md
│   ├── api/                           # API documentation
│   └── guides/                        # User guides
│
├── orange/                            # Main package
│   ├── __init__.py
│   ├── __main__.py                    # Entry point
│   ├── config.py                      # Configuration management
│   ├── exceptions.py                  # Custom exceptions
│   ├── constants.py                   # Project constants
│   │
│   ├── core/                          # Core library modules
│   │   ├── __init__.py
│   │   │
│   │   ├── connection/                # Phase 1 ✅ COMPLETE
│   │   │   ├── __init__.py
│   │   │   ├── device.py              # Device detection & info
│   │   │   ├── pairing.py             # Trust establishment
│   │   │   ├── wireless.py            # Wi-Fi Sync discovery & connection
│   │   │   └── manager.py             # Connection state management
│   │   │
│   │   ├── backup/                    # Phase 2
│   │   │   ├── __init__.py
│   │   │   ├── create.py              # Backup creation
│   │   │   ├── restore.py             # Backup restoration
│   │   │   ├── decrypt.py             # Encrypted backup handling
│   │   │   ├── parse.py               # Backup file parsing
│   │   │   └── manifest.py            # Manifest.db handling
│   │   │
│   │   ├── transfer/                  # Phase 3
│   │   │   ├── __init__.py
│   │   │   ├── afc.py                 # AFC protocol wrapper
│   │   │   ├── media.py               # Photo/video/music transfer
│   │   │   ├── documents.py           # Document transfer
│   │   │   └── progress.py            # Progress tracking
│   │   │
│   │   ├── data/                      # Phase 4
│   │   │   ├── __init__.py
│   │   │   ├── messages/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sms.py             # SMS database parsing
│   │   │   │   ├── imessage.py        # iMessage handling
│   │   │   │   └── attachments.py     # Attachment extraction
│   │   │   ├── contacts/
│   │   │   │   ├── __init__.py
│   │   │   │   └── addressbook.py     # Contact database parsing
│   │   │   ├── calendar/
│   │   │   │   ├── __init__.py
│   │   │   │   └── events.py          # Calendar extraction
│   │   │   └── notes/
│   │   │       ├── __init__.py
│   │   │       └── parser.py          # Notes extraction
│   │   │
│   │   ├── convert/                   # Phase 5
│   │   │   ├── __init__.py
│   │   │   ├── audio.py               # Audio conversion
│   │   │   ├── video.py               # Video conversion
│   │   │   └── image.py               # Image conversion (HEIC)
│   │   │
│   │   └── export/                    # Phase 6
│   │       ├── __init__.py
│   │       ├── pdf.py                 # PDF generation
│   │       ├── csv_export.py          # CSV export
│   │       ├── json_export.py         # JSON export
│   │       └── html_export.py         # HTML export
│   │
│   └── cli/                           # CLI application
│       ├── __init__.py
│       ├── main.py                    # CLI entry point
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── device.py              # Device commands
│       │   ├── backup.py              # Backup commands
│       │   ├── transfer.py            # Transfer commands
│       │   ├── export.py              # Export commands
│       │   └── config.py              # Config commands
│       └── utils.py                   # CLI utilities
│
├── tests/                             # Test suite
│   ├── __init__.py
│   ├── conftest.py                    # Pytest fixtures
│   ├── core/
│   │   ├── connection/
│   │   │   ├── test_device.py
│   │   │   ├── test_pairing.py
│   │   │   └── test_manager.py
│   │   ├── backup/
│   │   ├── transfer/
│   │   ├── data/
│   │   ├── convert/
│   │   └── export/
│   └── cli/
│       └── test_commands.py
│
├── scripts/                           # Utility scripts
│   ├── build.py                       # Build script
│   └── release.py                     # Release script
│
└── outputs/                           # Skill outputs directory
    └── .gitkeep
```

---

## Module Specifications

### Module Interface Contracts

Each module follows a consistent interface pattern:

```python
# Example: Connection Module Interface
from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class DeviceInfo:
    """Device information container."""
    udid: str
    name: str
    model: str
    ios_version: str
    serial_number: str
    wifi_address: Optional[str]
    battery_level: Optional[int]

class ConnectionInterface(ABC):
    """Interface for device connection operations."""

    @abstractmethod
    def list_devices(self) -> List[DeviceInfo]:
        """List all connected iOS devices."""
        pass

    @abstractmethod
    def connect(self, udid: str) -> 'DeviceConnection':
        """Connect to a specific device."""
        pass

    @abstractmethod
    def pair(self, udid: str) -> bool:
        """Initiate pairing with a device."""
        pass

    @abstractmethod
    def is_paired(self, udid: str) -> bool:
        """Check if device is paired."""
        pass
```

### Module Dependencies

```
                    ┌─────────────┐
                    │   export    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ convert │  │  data   │  │transfer │
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                    ┌─────────┐
                    │ backup  │
                    └────┬────┘
                         │
                         ▼
                   ┌──────────┐
                   │connection│
                   └──────────┘
```

---

## Phase 1: Connection Module (MVP) - COMPLETE ✅

### Objective

Establish reliable device detection, pairing, and connection management as the foundation for all other modules.

### Deliverables - All Complete

1. **Device Detection** (`device.py`) ✅
   - Enumerate connected USB devices
   - Identify iOS devices by UDID
   - Retrieve basic device information
   - Support partial UDID matching

2. **Pairing System** (`pairing.py`) ✅
   - Check pairing status
   - Initiate pairing workflow
   - Handle "Trust This Computer" prompt
   - Manage pairing records

3. **Wi-Fi Discovery** (`wireless.py`) ✅
   - Bonjour/mDNS device discovery via `_apple-mobdev2._tcp`
   - Standard Wi-Fi Sync protocol (same as iTunes/Finder)
   - NO Developer Mode required
   - Enable/disable Wi-Fi connections on device

4. **Connection Manager** (`manager.py`) ✅
   - Multi-device connection pool
   - Connection state tracking
   - Context manager support
   - Event callbacks for connect/disconnect

### Technical Specifications

#### device.py

```python
"""
Device detection and information retrieval.

Classes:
    DeviceInfo: Dataclass containing device metadata
    DeviceDetector: Handles device enumeration

Dependencies:
    - pymobiledevice3.lockdown
    - pymobiledevice3.usbmux
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

class ConnectionType(Enum):
    USB = "usb"
    WIFI = "wifi"
    UNKNOWN = "unknown"

class DeviceState(Enum):
    CONNECTED = "connected"
    PAIRED = "paired"
    UNPAIRED = "unpaired"
    DISCONNECTED = "disconnected"

@dataclass
class DeviceInfo:
    """Container for iOS device information."""
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
    extra: Dict[str, Any] = field(default_factory=dict)

class DeviceDetector:
    """Handles iOS device detection and enumeration."""

    def __init__(self, include_wifi: bool = True):
        """
        Initialize the device detector.

        Args:
            include_wifi: Whether to include Wi-Fi connected devices
        """
        pass

    def list_devices(self) -> List[DeviceInfo]:
        """
        List all connected iOS devices.

        Returns:
            List of DeviceInfo objects for each connected device
        """
        pass

    def get_device(self, udid: str) -> Optional[DeviceInfo]:
        """
        Get information for a specific device.

        Args:
            udid: The device's unique identifier

        Returns:
            DeviceInfo if found, None otherwise
        """
        pass

    def refresh(self) -> None:
        """Refresh the device list."""
        pass
```

#### pairing.py

```python
"""
Device pairing and trust management.

Classes:
    PairingManager: Handles device pairing operations

Dependencies:
    - pymobiledevice3.lockdown
"""

from typing import Optional, Callable
from enum import Enum

class PairingState(Enum):
    NOT_PAIRED = "not_paired"
    PAIRING_IN_PROGRESS = "pairing_in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    PAIRED = "paired"
    PAIRING_FAILED = "pairing_failed"

class PairingManager:
    """Manages device pairing and trust relationships."""

    def __init__(self, udid: str):
        """
        Initialize pairing manager for a device.

        Args:
            udid: Target device UDID
        """
        pass

    def is_paired(self) -> bool:
        """Check if device is currently paired."""
        pass

    def pair(
        self,
        on_prompt: Optional[Callable[[], None]] = None,
        timeout: int = 60
    ) -> bool:
        """
        Initiate pairing with the device.

        Args:
            on_prompt: Callback when user action needed on device
            timeout: Seconds to wait for user to accept

        Returns:
            True if pairing successful, False otherwise
        """
        pass

    def unpair(self) -> bool:
        """Remove pairing with device."""
        pass

    def validate_pairing(self) -> bool:
        """Validate existing pairing is still valid."""
        pass
```

#### manager.py

```python
"""
Connection pool and lifecycle management.

Classes:
    DeviceConnection: Represents an active connection
    ConnectionManager: Manages multiple device connections

Dependencies:
    - orange.core.connection.device
    - orange.core.connection.pairing
"""

from typing import Optional, List, Dict, Callable
from contextlib import contextmanager

class DeviceConnection:
    """Represents an active connection to an iOS device."""

    @property
    def udid(self) -> str:
        """Device UDID."""
        pass

    @property
    def is_connected(self) -> bool:
        """Connection status."""
        pass

    def get_lockdown_client(self):
        """Get lockdown service client."""
        pass

    def get_service(self, service_name: str):
        """Get a specific device service."""
        pass

    def close(self) -> None:
        """Close the connection."""
        pass

class ConnectionManager:
    """
    Manages connections to multiple iOS devices.

    Provides connection pooling, automatic reconnection,
    and event-driven device state notifications.
    """

    def __init__(self):
        """Initialize the connection manager."""
        pass

    def on_device_connected(self, callback: Callable[[str], None]) -> None:
        """Register callback for device connection events."""
        pass

    def on_device_disconnected(self, callback: Callable[[str], None]) -> None:
        """Register callback for device disconnection events."""
        pass

    def list_devices(self) -> List[DeviceInfo]:
        """List all available devices."""
        pass

    @contextmanager
    def connect(self, udid: str):
        """
        Context manager for device connection.

        Usage:
            with manager.connect(udid) as conn:
                info = conn.get_device_info()
        """
        pass

    def get_connection(self, udid: str) -> Optional[DeviceConnection]:
        """Get existing connection or create new one."""
        pass

    def close_all(self) -> None:
        """Close all active connections."""
        pass
```

### CLI Commands (Phase 1) - All Implemented ✅

```bash
# List connected devices (USB + Wi-Fi)
orange device list
orange device list --json
orange device list --no-wifi

# Show device details (UDID optional if single device)
orange device info [udid]
orange device info --all
orange device info --json

# Pairing operations (UDID optional if single device)
orange device pair [udid]
orange device unpair [udid]
orange device is-paired [udid]

# Connection testing
orange device ping [udid]

# Wi-Fi Sync (standard Apple protocol, no Developer Mode)
orange device wifi --enable [udid]   # Enable Wi-Fi (requires USB)
orange device wifi --disable [udid]  # Disable Wi-Fi
orange device wifi --status [udid]   # Check Wi-Fi status
orange device scan                    # Discover Wi-Fi devices on network
```

### Test Cases

#### test_device.py

```python
"""Tests for device detection functionality."""

import pytest
from orange.core.connection.device import DeviceDetector, DeviceInfo

class TestDeviceDetector:
    """Test cases for DeviceDetector."""

    def test_list_devices_returns_list(self):
        """list_devices should return a list."""
        detector = DeviceDetector()
        result = detector.list_devices()
        assert isinstance(result, list)

    def test_list_devices_returns_device_info_objects(self):
        """Each item should be a DeviceInfo instance."""
        detector = DeviceDetector()
        devices = detector.list_devices()
        for device in devices:
            assert isinstance(device, DeviceInfo)

    def test_get_device_with_invalid_udid_returns_none(self):
        """get_device with invalid UDID should return None."""
        detector = DeviceDetector()
        result = detector.get_device("invalid-udid-12345")
        assert result is None

    def test_device_info_has_required_fields(self):
        """DeviceInfo should have all required fields."""
        # Mock device for testing
        info = DeviceInfo(
            udid="test-udid",
            name="Test iPhone",
            model="iPhone",
            model_number="iPhone14,2",
            ios_version="17.0",
            build_version="21A329",
            serial_number="TESTSERIAL",
            connection_type=ConnectionType.USB,
            state=DeviceState.CONNECTED
        )
        assert info.udid == "test-udid"
        assert info.name == "Test iPhone"
```

#### test_pairing.py

```python
"""Tests for pairing functionality."""

import pytest
from unittest.mock import Mock, patch
from orange.core.connection.pairing import PairingManager, PairingState

class TestPairingManager:
    """Test cases for PairingManager."""

    def test_is_paired_returns_bool(self):
        """is_paired should return boolean."""
        # This would need mocking in real implementation
        pass

    def test_pair_with_timeout(self):
        """pair should respect timeout parameter."""
        pass

    def test_unpair_removes_pairing(self):
        """unpair should remove the pairing record."""
        pass
```

### Implementation Steps

1. **Setup project structure** (Day 1)
   - Create directory structure
   - Initialize pyproject.toml
   - Set up virtual environment
   - Configure pytest

2. **Implement DeviceDetector** (Days 2-3)
   - Wrap pymobiledevice3 usbmux
   - Implement device enumeration
   - Add DeviceInfo parsing
   - Write unit tests

3. **Implement PairingManager** (Days 4-5)
   - Wrap pymobiledevice3 lockdown
   - Implement pairing workflow
   - Add timeout handling
   - Write unit tests

4. **Implement ConnectionManager** (Days 6-7)
   - Create connection pool
   - Add event callbacks
   - Implement auto-reconnect
   - Write integration tests

5. **Implement CLI commands** (Days 8-9)
   - Set up Click framework
   - Implement device commands
   - Add JSON output support
   - Write CLI tests

6. **Documentation & polish** (Day 10)
   - Write API documentation
   - Create usage examples
   - Review and refactor

---

## Phase 2: Backup Engine

### Objective

Implement full device backup and restore capabilities with support for encrypted backups.

### Deliverables

1. **Backup Creation** (`create.py`)
   - Full device backup
   - Incremental backup support
   - Progress tracking
   - Cancellation support

2. **Backup Restoration** (`restore.py`)
   - Full restore
   - Selective restore
   - Application data restore

3. **Encryption Handling** (`decrypt.py`)
   - Backup decryption
   - Key derivation (PBKDF2)
   - AES-256 decryption

4. **Backup Parsing** (`parse.py`, `manifest.py`)
   - Manifest.db reading
   - File hash mapping
   - Metadata extraction

### Key Classes

```python
@dataclass
class BackupInfo:
    """Backup metadata."""
    backup_id: str
    device_name: str
    device_udid: str
    ios_version: str
    backup_date: datetime
    is_encrypted: bool
    size_bytes: int
    path: Path

class BackupManager:
    """Manages backup operations."""

    def create_backup(
        self,
        connection: DeviceConnection,
        destination: Path,
        encrypted: bool = True,
        password: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> BackupInfo:
        pass

    def restore_backup(
        self,
        connection: DeviceConnection,
        backup_path: Path,
        password: Optional[str] = None,
        selective: Optional[List[str]] = None
    ) -> bool:
        pass

    def list_backups(self, backup_dir: Optional[Path] = None) -> List[BackupInfo]:
        pass

class BackupReader:
    """Reads and parses backup contents."""

    def __init__(self, backup_path: Path, password: Optional[str] = None):
        pass

    def list_files(self, domain: Optional[str] = None) -> List[BackupFile]:
        pass

    def extract_file(self, file_id: str, destination: Path) -> Path:
        pass

    def get_database(self, relative_path: str) -> Path:
        """Extract and return path to a database file."""
        pass
```

### CLI Commands (Phase 2)

```bash
# Backup operations
orange backup create <udid> --destination ./backups
orange backup create <udid> --encrypted --password "secret"
orange backup list
orange backup info <backup-id>

# Restore operations
orange backup restore <udid> <backup-id>
orange backup restore <udid> <backup-id> --selective messages,contacts

# Backup exploration
orange backup browse <backup-id>
orange backup extract <backup-id> <file-path> --output ./extracted
```

---

## Phase 3: File Transfer

### Objective

Enable bidirectional file transfer between iOS devices and computers.

### Deliverables

1. **AFC Wrapper** (`afc.py`)
   - File system operations
   - Directory traversal
   - File read/write

2. **Media Transfer** (`media.py`)
   - Photo import/export
   - Video transfer
   - Music synchronization

3. **Document Transfer** (`documents.py`)
   - App document access
   - iTunes File Sharing

4. **Progress Tracking** (`progress.py`)
   - Transfer progress
   - Speed calculation
   - ETA estimation

### Key Classes

```python
class AFCClient:
    """Apple File Conduit client wrapper."""

    def list_directory(self, path: str) -> List[AFCFileInfo]:
        pass

    def read_file(self, remote_path: str) -> bytes:
        pass

    def write_file(self, remote_path: str, data: bytes) -> None:
        pass

    def pull_file(
        self,
        remote_path: str,
        local_path: Path,
        progress: Optional[Callable[[int, int], None]] = None
    ) -> None:
        pass

    def push_file(
        self,
        local_path: Path,
        remote_path: str,
        progress: Optional[Callable[[int, int], None]] = None
    ) -> None:
        pass

class MediaTransfer:
    """High-level media transfer operations."""

    def export_photos(
        self,
        connection: DeviceConnection,
        destination: Path,
        albums: Optional[List[str]] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> List[Path]:
        pass

    def import_music(
        self,
        connection: DeviceConnection,
        files: List[Path],
        convert_if_needed: bool = True
    ) -> int:
        pass
```

### CLI Commands (Phase 3)

```bash
# Photo operations
orange transfer photos export <udid> --output ./photos
orange transfer photos export <udid> --album "Favorites" --output ./favorites

# Music operations
orange transfer music import <udid> ./my-music/*.flac
orange transfer music export <udid> --output ./music

# File operations
orange transfer pull <udid> /DCIM/100APPLE/IMG_0001.HEIC ./local/
orange transfer push <udid> ./document.pdf /Documents/MyApp/
```

---

## Phase 4: Data Extraction

### Objective

Extract and parse specific data types from device backups.

### Deliverables

1. **Message Extraction** (`data/messages/`)
   - SMS parsing
   - iMessage handling
   - Attachment extraction
   - Conversation threading

2. **Contact Extraction** (`data/contacts/`)
   - Address book parsing
   - Contact photos
   - Group handling

3. **Calendar Extraction** (`data/calendar/`)
   - Event parsing
   - Recurring events
   - Reminders

4. **Notes Extraction** (`data/notes/`)
   - Note content
   - Attachments
   - Folders

### Key Classes

```python
@dataclass
class Message:
    """Represents a single message."""
    id: int
    text: str
    date: datetime
    is_from_me: bool
    sender: str
    chat_id: int
    attachments: List['Attachment']
    read: bool

class MessageExtractor:
    """Extracts messages from backup."""

    def __init__(self, backup_reader: BackupReader):
        pass

    def get_conversations(self) -> List[Conversation]:
        pass

    def get_messages(
        self,
        conversation_id: Optional[int] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        search: Optional[str] = None
    ) -> List[Message]:
        pass

    def extract_attachments(
        self,
        messages: List[Message],
        destination: Path
    ) -> Dict[int, Path]:
        pass
```

### CLI Commands (Phase 4)

```bash
# Message extraction
orange data messages list <backup-id>
orange data messages export <backup-id> --format pdf --output ./messages
orange data messages search <backup-id> "search term"

# Contact extraction
orange data contacts export <backup-id> --format vcf --output ./contacts

# Calendar extraction
orange data calendar export <backup-id> --format ics --output ./calendar
```

---

## Phase 5: Format Conversion

### Objective

Convert media files between formats for Apple compatibility.

### Deliverables

1. **Audio Conversion** (`convert/audio.py`)
   - FLAC → ALAC (lossless)
   - MP3/AAC handling
   - Metadata preservation

2. **Video Conversion** (`convert/video.py`)
   - MKV → MP4
   - Codec transcoding
   - Resolution handling

3. **Image Conversion** (`convert/image.py`)
   - HEIC ↔ JPEG
   - PNG handling
   - Metadata preservation

### Implementation Notes

- Use ffmpeg for audio/video conversion
- Use pillow-heif for HEIC handling
- Preserve metadata during conversion
- Support batch operations

---

## Phase 6: Export & Distribution

### Objective

Generate export files and prepare for distribution.

### Export Deliverables

1. **PDF Export** (`export/pdf.py`)
   - Message conversation formatting
   - Attachment embedding
   - Contact cards

2. **CSV Export** (`export/csv_export.py`)
   - Structured data output
   - Configurable columns

3. **JSON Export** (`export/json_export.py`)
   - Full data structure
   - Schema documentation

### Distribution Deliverables

1. **macOS**
   - App bundle (.app)
   - DMG installer
   - Notarization

2. **Windows**
   - Executable (.exe)
   - MSI installer
   - Code signing

3. **Linux**
   - AppImage
   - Flatpak
   - Snap

### CLI Commands (Phase 6)

```bash
# Export commands
orange export messages <backup-id> --format pdf --output ./export.pdf
orange export contacts <backup-id> --format vcf --output ./contacts.vcf
orange export all <backup-id> --output ./full-export/
```

---

## Testing Strategy

### Test Pyramid

```
         ┌───────────┐
         │   E2E     │  10%  - Full workflow tests
         │   Tests   │        - Require real device
         ├───────────┤
         │Integration│  30%  - Module interaction
         │   Tests   │        - Mock external deps
         ├───────────┤
         │   Unit    │  60%  - Individual functions
         │   Tests   │        - Fast, isolated
         └───────────┘
```

### Test Categories

| Category | Location | Coverage Target |
|----------|----------|-----------------|
| Unit | `tests/core/*/test_*.py` | 80% |
| Integration | `tests/integration/` | 70% |
| E2E | `tests/e2e/` | Critical paths |
| CLI | `tests/cli/` | All commands |

### Mock Strategy

```python
# conftest.py - Shared fixtures

@pytest.fixture
def mock_device():
    """Mock iOS device for testing."""
    return MockDevice(
        udid="test-udid-12345",
        name="Test iPhone",
        ios_version="17.0"
    )

@pytest.fixture
def mock_backup():
    """Mock backup for testing."""
    return MockBackup(
        path=Path("tests/fixtures/mock_backup"),
        encrypted=False
    )
```

### Test Fixtures

```
tests/
├── fixtures/
│   ├── mock_backup/          # Minimal backup structure
│   │   ├── Manifest.db
│   │   ├── Manifest.plist
│   │   └── Info.plist
│   ├── sample_messages.db    # Test message database
│   └── sample_contacts.db    # Test contacts database
```

---

## Development Environment

### Requirements

```
# requirements.txt
pymobiledevice3>=4.0.0
click>=8.1.0
rich>=13.0.0          # CLI formatting
pycryptodome>=3.19.0  # Backup decryption
python-dotenv>=1.0.0  # Configuration
pillow>=10.0.0        # Image handling
pillow-heif>=0.13.0   # HEIC support

# Development
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0
black>=23.0.0
ruff>=0.1.0
mypy>=1.7.0
```

### Setup

```bash
# Clone and setup
git clone <repo>
cd orange

# Create virtual environment
python3 -m venv venv_linux
source venv_linux/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest

# Run CLI
orange --help
```

### pyproject.toml

```toml
[project]
name = "orange"
version = "0.1.0"
description = "Cross-platform iOS file transfer and data management"
requires-python = ">=3.10"
dependencies = [
    "pymobiledevice3>=4.0.0",
    "click>=8.1.0",
    "rich>=13.0.0",
    "pycryptodome>=3.19.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]
conversion = [
    "pillow>=10.0.0",
    "pillow-heif>=0.13.0",
]

[project.scripts]
orange = "orange.cli.main:cli"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
addopts = "-v --cov=orange --cov-report=term-missing"

[tool.black]
line-length = 88
target-version = ["py310"]

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_ignores = true
```

---

## Coding Standards

### Python Style

- **Formatter:** Black (line length 88)
- **Linter:** Ruff
- **Type checker:** mypy
- **Docstrings:** Google style

### Code Organization

```python
"""
Module docstring explaining purpose.

Classes:
    ClassName: Brief description

Functions:
    function_name: Brief description
"""

from __future__ import annotations

# Standard library imports
import os
from pathlib import Path
from typing import Optional, List

# Third-party imports
import click
from rich.console import Console

# Local imports
from orange.core.connection import DeviceConnection
from orange.config import Config

# Constants
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# Module code...
```

### Error Handling

```python
# Custom exceptions in orange/exceptions.py
class OrangeError(Exception):
    """Base exception for Orange."""
    pass

class DeviceNotFoundError(OrangeError):
    """Device with specified UDID not found."""
    pass

class PairingError(OrangeError):
    """Failed to pair with device."""
    pass

class BackupError(OrangeError):
    """Backup operation failed."""
    pass

# Usage
def connect(udid: str) -> DeviceConnection:
    device = detector.get_device(udid)
    if device is None:
        raise DeviceNotFoundError(f"No device found with UDID: {udid}")
    # ...
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

def some_function():
    logger.debug("Starting operation")
    try:
        # operation
        logger.info("Operation completed successfully")
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        raise
```

---

## Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|------------|
| iOS version breaks compatibility | Pin pymobiledevice3 version; test with multiple iOS versions |
| Performance with large backups | Implement streaming; chunk large operations |
| Cross-platform issues | CI testing on all platforms; platform-specific code paths |
| Dependency vulnerabilities | Regular updates; security scanning |

### Operational Risks

| Risk | Mitigation |
|------|------------|
| User data loss | Never modify device without explicit consent; backup before restore |
| Privacy concerns | Local-only processing; clear data handling documentation |
| Support burden | Comprehensive documentation; clear error messages |

---

## Future Considerations

### Potential Extensions

1. **GUI Application**
   - Electron or Qt-based
   - Cross-platform consistency
   - Drag-and-drop interface

2. **iOS Companion App**
   - HealthKit integration
   - Direct file sharing
   - Real-time sync

3. **REST API**
   - Remote device management
   - Web interface
   - Integration with other tools

4. **Plugin System**
   - Third-party data extractors
   - Custom export formats
   - Community contributions

### Technology Considerations

- Consider Rust for performance-critical components
- Evaluate WASM for browser-based tools
- Monitor Apple's evolving security model

---

## Appendix: Configuration Schema

```python
# orange/config.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os

@dataclass
class Config:
    """Application configuration."""

    # Paths
    backup_directory: Path = field(
        default_factory=lambda: Path.home() / ".orange" / "backups"
    )
    export_directory: Path = field(
        default_factory=lambda: Path.home() / ".orange" / "exports"
    )
    log_directory: Path = field(
        default_factory=lambda: Path.home() / ".orange" / "logs"
    )

    # Connection
    connection_timeout: int = 30
    wifi_discovery_enabled: bool = True
    auto_reconnect: bool = True

    # Transfer
    chunk_size: int = 1024 * 1024  # 1MB
    max_concurrent_transfers: int = 4

    # Conversion
    audio_format: str = "alac"  # alac, aac, mp3
    video_format: str = "mp4"
    image_format: str = "jpeg"  # jpeg, png, heic
    preserve_metadata: bool = True

    # Export
    pdf_include_attachments: bool = True
    csv_delimiter: str = ","
    json_indent: int = 2

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from file or environment."""
        pass

    def save(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        pass
```

---

*Implementation Plan v1.0 - Orange Project*
*Generated: January 25, 2026*
