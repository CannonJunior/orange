"""Tests for decryption exceptions."""

import pytest

from orange.core.apps.decrypt.exceptions import (
    DecryptionError,
    FridaConnectionError,
    FridaNotInstalledError,
    JailbreakRequiredError,
    AppNotFoundError,
    AppNotRunningError,
    BinaryNotEncryptedError,
    MachOParseError,
    SSHConnectionError,
)
from orange.exceptions import OrangeError


class TestDecryptionExceptions:
    """Test decryption exception hierarchy and messages."""

    def test_decryption_error_inherits_from_orange_error(self):
        """DecryptionError should inherit from OrangeError."""
        error = DecryptionError("Test error")
        assert isinstance(error, OrangeError)
        assert isinstance(error, Exception)

    def test_decryption_error_with_details(self):
        """DecryptionError should include details in string."""
        error = DecryptionError("Test error", "Additional details")
        assert "Test error" in str(error)
        assert "Additional details" in str(error)

    def test_frida_connection_error(self):
        """FridaConnectionError should have helpful message."""
        error = FridaConnectionError()
        assert isinstance(error, DecryptionError)
        assert "connect" in str(error).lower() or "frida" in str(error).lower()

    def test_frida_connection_error_custom_message(self):
        """FridaConnectionError should accept custom message."""
        error = FridaConnectionError("Custom error", "Extra info")
        assert "Custom error" in str(error)
        assert "Extra info" in str(error)

    def test_frida_not_installed_error(self):
        """FridaNotInstalledError should suggest installation."""
        error = FridaNotInstalledError()
        assert isinstance(error, DecryptionError)
        assert "pip install" in str(error)
        assert "frida" in str(error).lower()

    def test_jailbreak_required_error(self):
        """JailbreakRequiredError should explain requirement."""
        error = JailbreakRequiredError()
        assert isinstance(error, DecryptionError)
        assert "jailbreak" in str(error).lower()

    def test_app_not_found_error(self):
        """AppNotFoundError should include bundle ID."""
        bundle_id = "com.example.app"
        error = AppNotFoundError(bundle_id)
        assert isinstance(error, DecryptionError)
        assert bundle_id in str(error)
        assert error.bundle_id == bundle_id

    def test_app_not_running_error(self):
        """AppNotRunningError should include bundle ID and reason."""
        bundle_id = "com.example.app"
        reason = "process crashed"
        error = AppNotRunningError(bundle_id, reason)
        assert isinstance(error, DecryptionError)
        assert bundle_id in str(error)
        assert reason in str(error)
        assert error.bundle_id == bundle_id

    def test_app_not_running_error_without_reason(self):
        """AppNotRunningError should work without reason."""
        bundle_id = "com.example.app"
        error = AppNotRunningError(bundle_id)
        assert bundle_id in str(error)

    def test_binary_not_encrypted_error(self):
        """BinaryNotEncryptedError should include binary name."""
        binary_name = "MyApp"
        error = BinaryNotEncryptedError(binary_name)
        assert isinstance(error, DecryptionError)
        assert binary_name in str(error)
        assert error.binary_name == binary_name

    def test_macho_parse_error(self):
        """MachOParseError should have default message."""
        error = MachOParseError()
        assert isinstance(error, DecryptionError)
        assert "mach-o" in str(error).lower() or "parse" in str(error).lower()

    def test_macho_parse_error_custom_message(self):
        """MachOParseError should accept custom message."""
        error = MachOParseError("Invalid magic number")
        assert "Invalid magic number" in str(error)

    def test_ssh_connection_error(self):
        """SSHConnectionError should include host."""
        host = "192.168.1.100"
        error = SSHConnectionError(host)
        assert isinstance(error, DecryptionError)
        assert host in str(error)
        assert error.host == host

    def test_ssh_connection_error_with_reason(self):
        """SSHConnectionError should include reason if provided."""
        host = "192.168.1.100"
        reason = "connection refused"
        error = SSHConnectionError(host, reason)
        assert host in str(error)
        assert reason in str(error)

    def test_all_exceptions_catchable_as_decryption_error(self):
        """All decryption exceptions should be catchable as DecryptionError."""
        exceptions = [
            FridaConnectionError(),
            FridaNotInstalledError(),
            JailbreakRequiredError(),
            AppNotFoundError("com.test"),
            AppNotRunningError("com.test"),
            BinaryNotEncryptedError("test"),
            MachOParseError(),
            SSHConnectionError("localhost"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except DecryptionError as e:
                pass  # Should catch all
            except Exception:
                pytest.fail(f"{type(exc).__name__} not catchable as DecryptionError")

    def test_all_exceptions_catchable_as_orange_error(self):
        """All decryption exceptions should be catchable as OrangeError."""
        exceptions = [
            DecryptionError("test"),
            FridaConnectionError(),
            AppNotFoundError("com.test"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except OrangeError:
                pass  # Should catch all
            except Exception:
                pytest.fail(f"{type(exc).__name__} not catchable as OrangeError")
