"""Tests for Orange context management."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from orange.core.context import (
    OrangeContext,
    OrangeContextState,
    BackupContext,
    DeviceContext,
    ExportContext,
    get_context,
    CONTEXT_VERSION,
)


@pytest.fixture
def temp_context_file(tmp_path):
    """Create a temporary context file path."""
    return tmp_path / "context.json"


@pytest.fixture
def temp_backup_dir(tmp_path):
    """Create a temporary backup directory."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    return backup_dir


class TestBackupContext:
    """Tests for BackupContext dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        backup = BackupContext(
            path="/path/to/backup",
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
            created_at="2026-02-01T12:00:00",
            is_encrypted=True,
            size_bytes=1000,
        )

        result = backup.to_dict()

        assert result["path"] == "/path/to/backup"
        assert result["device_udid"] == "123"
        assert result["is_encrypted"] is True

    def test_from_dict(self):
        """Should create from dictionary."""
        data = {
            "path": "/path/to/backup",
            "device_udid": "123",
            "device_name": "iPhone",
            "ios_version": "17.0",
            "created_at": "2026-02-01T12:00:00",
            "is_encrypted": False,
            "size_bytes": 500,
        }

        backup = BackupContext.from_dict(data)

        assert backup.path == "/path/to/backup"
        assert backup.device_udid == "123"
        assert backup.size_bytes == 500

    def test_path_obj(self):
        """Should return path as Path object."""
        backup = BackupContext(
            path="/path/to/backup",
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
            created_at="2026-02-01T12:00:00",
        )

        assert backup.path_obj == Path("/path/to/backup")

    def test_exists_true(self, temp_backup_dir):
        """Should return True when backup exists."""
        backup = BackupContext(
            path=str(temp_backup_dir),
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
            created_at="2026-02-01T12:00:00",
        )

        assert backup.exists() is True

    def test_exists_false(self):
        """Should return False when backup doesn't exist."""
        backup = BackupContext(
            path="/nonexistent/path",
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
            created_at="2026-02-01T12:00:00",
        )

        assert backup.exists() is False


class TestOrangeContext:
    """Tests for OrangeContext class."""

    def test_creates_empty_state_when_no_file(self, temp_context_file):
        """Should create empty state when context file doesn't exist."""
        ctx = OrangeContext(temp_context_file)

        assert ctx.state.version == CONTEXT_VERSION
        assert ctx.state.last_backup is None
        assert ctx.state.recent_backups == []

    def test_loads_existing_state(self, temp_context_file):
        """Should load state from existing file."""
        state_data = {
            "version": 1,
            "last_backup": {
                "path": "/path/to/backup",
                "device_udid": "123",
                "device_name": "iPhone",
                "ios_version": "17.0",
                "created_at": "2026-02-01T12:00:00",
                "is_encrypted": False,
                "size_bytes": 0,
            },
            "recent_backups": [],
            "current_device": None,
            "last_export": None,
            "recent_exports": [],
        }

        temp_context_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_context_file, "w") as f:
            json.dump(state_data, f)

        ctx = OrangeContext(temp_context_file)

        assert ctx.state.last_backup is not None
        assert ctx.state.last_backup.path == "/path/to/backup"

    def test_set_last_backup(self, temp_context_file, temp_backup_dir):
        """Should set and persist last backup."""
        ctx = OrangeContext(temp_context_file)

        ctx.set_last_backup(
            path=temp_backup_dir,
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
        )

        assert ctx.state.last_backup is not None
        assert ctx.state.last_backup.device_udid == "123"

        # Verify persisted
        ctx2 = OrangeContext(temp_context_file)
        assert ctx2.state.last_backup is not None
        assert ctx2.state.last_backup.device_udid == "123"

    def test_set_last_backup_adds_to_recent(self, temp_context_file, temp_backup_dir):
        """Should add backup to recent backups list."""
        ctx = OrangeContext(temp_context_file)

        ctx.set_last_backup(
            path=temp_backup_dir,
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
        )

        assert len(ctx.state.recent_backups) == 1
        assert ctx.state.recent_backups[0].device_udid == "123"

    def test_recent_backups_limit(self, temp_context_file, tmp_path):
        """Should limit recent backups to MAX_RECENT_ITEMS."""
        ctx = OrangeContext(temp_context_file)

        # Add 15 backups
        for i in range(15):
            backup_dir = tmp_path / f"backup_{i}"
            backup_dir.mkdir()
            ctx.set_last_backup(
                path=backup_dir,
                device_udid=f"device_{i}",
                device_name=f"iPhone {i}",
                ios_version="17.0",
            )

        # Should only keep 10 (MAX_RECENT_ITEMS)
        assert len(ctx.state.recent_backups) == 10
        # Most recent should be first
        assert ctx.state.recent_backups[0].device_udid == "device_14"

    def test_get_backup_by_device(self, temp_context_file, tmp_path):
        """Should find backup by device UDID."""
        ctx = OrangeContext(temp_context_file)

        backup1 = tmp_path / "backup1"
        backup1.mkdir()
        backup2 = tmp_path / "backup2"
        backup2.mkdir()

        ctx.set_last_backup(
            path=backup1,
            device_udid="device_1",
            device_name="iPhone 1",
            ios_version="17.0",
        )
        ctx.set_last_backup(
            path=backup2,
            device_udid="device_2",
            device_name="iPhone 2",
            ios_version="17.0",
        )

        result = ctx.get_backup_by_device("device_1")

        assert result is not None
        assert result.device_udid == "device_1"

    def test_get_backup_by_device_not_found(self, temp_context_file):
        """Should return None when device backup not found."""
        ctx = OrangeContext(temp_context_file)

        result = ctx.get_backup_by_device("nonexistent")

        assert result is None

    def test_set_current_device(self, temp_context_file):
        """Should set and persist current device."""
        ctx = OrangeContext(temp_context_file)

        ctx.set_current_device(
            udid="123",
            name="iPhone",
            ios_version="17.0",
            model="iPhone15,2",
        )

        assert ctx.state.current_device is not None
        assert ctx.state.current_device.udid == "123"
        assert ctx.state.current_device.model == "iPhone15,2"

    def test_set_last_export(self, temp_context_file, tmp_path):
        """Should set and persist last export."""
        ctx = OrangeContext(temp_context_file)
        export_path = tmp_path / "export.json"
        backup_path = tmp_path / "backup"

        ctx.set_last_export(
            path=export_path,
            export_type="messages",
            backup_path=backup_path,
            record_count=100,
        )

        assert ctx.state.last_export is not None
        assert ctx.state.last_export.export_type == "messages"
        assert ctx.state.last_export.record_count == 100

    def test_clear(self, temp_context_file, tmp_path):
        """Should clear all context."""
        ctx = OrangeContext(temp_context_file)
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        ctx.set_last_backup(
            path=backup_dir,
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
        )

        ctx.clear()

        assert ctx.state.last_backup is None
        assert ctx.state.recent_backups == []

    def test_handles_corrupt_file(self, temp_context_file):
        """Should handle corrupt context file gracefully."""
        temp_context_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_context_file, "w") as f:
            f.write("not valid json {{{")

        ctx = OrangeContext(temp_context_file)

        # Should create empty state
        assert ctx.state.last_backup is None

    def test_to_dict(self, temp_context_file, tmp_path):
        """Should convert context to dictionary."""
        ctx = OrangeContext(temp_context_file)
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        ctx.set_last_backup(
            path=backup_dir,
            device_udid="123",
            device_name="iPhone",
            ios_version="17.0",
        )

        result = ctx.to_dict()

        assert "version" in result
        assert "last_backup" in result
        assert result["last_backup"]["device_udid"] == "123"


class TestGetContext:
    """Tests for get_context singleton."""

    def test_returns_same_instance(self):
        """Should return the same instance on multiple calls."""
        # Reset singleton
        import orange.core.context as ctx_module
        ctx_module._context = None

        ctx1 = get_context()
        ctx2 = get_context()

        assert ctx1 is ctx2


class TestOrangeContextState:
    """Tests for OrangeContextState dataclass."""

    def test_to_dict_empty(self):
        """Should convert empty state to dict."""
        state = OrangeContextState()

        result = state.to_dict()

        assert result["version"] == CONTEXT_VERSION
        assert result["last_backup"] is None
        assert result["recent_backups"] == []

    def test_from_dict_empty(self):
        """Should create state from empty dict."""
        state = OrangeContextState.from_dict({})

        assert state.version == CONTEXT_VERSION
        assert state.last_backup is None

    def test_round_trip(self):
        """Should survive round-trip to/from dict."""
        state = OrangeContextState(
            last_backup=BackupContext(
                path="/path",
                device_udid="123",
                device_name="iPhone",
                ios_version="17.0",
                created_at="2026-02-01T12:00:00",
            ),
            current_device=DeviceContext(
                udid="123",
                name="iPhone",
            ),
        )

        data = state.to_dict()
        restored = OrangeContextState.from_dict(data)

        assert restored.last_backup.device_udid == "123"
        assert restored.current_device.name == "iPhone"
