"""
Tests for CLI commands.

Tests the command-line interface for Orange.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from orange.cli.main import cli
from orange.core.connection.device import (
    ConnectionType,
    DeviceInfo,
    DeviceState,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_devices() -> list[DeviceInfo]:
    """Create mock device list for testing."""
    return [
        DeviceInfo(
            udid="00008030-001234567890001E",
            name="Test iPhone",
            model="iPhone",
            model_number="iPhone14,2",
            ios_version="17.0",
            build_version="21A329",
            serial_number="TESTSERIAL",
            connection_type=ConnectionType.USB,
            state=DeviceState.PAIRED,
            battery_level=85,
            battery_charging=False,
            paired=True,
        ),
    ]


class TestDeviceListCommand:
    """Tests for 'orange device list' command."""

    def test_list_no_devices(self, cli_runner: CliRunner) -> None:
        """Should show message when no devices found."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = []

            result = cli_runner.invoke(cli, ["device", "list"])

            assert result.exit_code == 0
            assert "No iOS devices found" in result.output

    def test_list_with_devices(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should display device table when devices found."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            result = cli_runner.invoke(cli, ["device", "list"])

            assert result.exit_code == 0
            assert "Test iPhone" in result.output
            assert "17.0" in result.output

    def test_list_json_output(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should output JSON when --json flag used."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            result = cli_runner.invoke(cli, ["device", "list", "--json"])

            assert result.exit_code == 0
            assert '"udid"' in result.output
            assert '"name"' in result.output
            assert "Test iPhone" in result.output

    def test_list_json_empty(self, cli_runner: CliRunner) -> None:
        """Should output empty JSON array when no devices."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = []

            result = cli_runner.invoke(cli, ["device", "list", "--json"])

            assert result.exit_code == 0
            assert "[]" in result.output


class TestDeviceInfoCommand:
    """Tests for 'orange device info' command."""

    def test_info_no_devices(self, cli_runner: CliRunner) -> None:
        """Should show error when no devices found."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = []

            result = cli_runner.invoke(cli, ["device", "info"])

            assert result.exit_code == 1
            assert "No iOS devices found" in result.output

    def test_info_single_device_no_udid(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should auto-select single device when no UDID given."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            result = cli_runner.invoke(cli, ["device", "info"])

            assert result.exit_code == 0
            assert "Test iPhone" in result.output

    def test_info_with_udid(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should show info for specified UDID."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            result = cli_runner.invoke(
                cli, ["device", "info", "00008030-001234567890001E"]
            )

            assert result.exit_code == 0
            assert "Test iPhone" in result.output
            assert "17.0" in result.output

    def test_info_partial_udid(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should match partial UDID."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            result = cli_runner.invoke(cli, ["device", "info", "00008030"])

            assert result.exit_code == 0
            assert "Test iPhone" in result.output

    def test_info_invalid_udid(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should show error for invalid UDID."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            result = cli_runner.invoke(cli, ["device", "info", "invalid"])

            assert result.exit_code == 1
            assert "Device not found" in result.output

    def test_info_json_output(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should output JSON when --json flag used."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            result = cli_runner.invoke(
                cli, ["device", "info", "--json"]
            )

            assert result.exit_code == 0
            assert '"udid"' in result.output


class TestDevicePairCommand:
    """Tests for 'orange device pair' command."""

    def test_pair_already_paired(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should indicate when device is already paired."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            with patch(
                "orange.cli.commands.device.PairingManager"
            ) as MockPairing:
                MockPairing.return_value.is_paired.return_value = True

                result = cli_runner.invoke(
                    cli, ["device", "pair", "00008030"]
                )

                assert result.exit_code == 0
                assert "already paired" in result.output

    def test_pair_device_not_found(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Should show error when no devices found."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = []

            result = cli_runner.invoke(
                cli, ["device", "pair", "invalid-udid"]
            )

            assert result.exit_code == 1
            assert "No iOS devices found" in result.output


class TestDeviceIsPairedCommand:
    """Tests for 'orange device is-paired' command."""

    def test_is_paired_true(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should exit 0 and show message when paired."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            with patch(
                "orange.cli.commands.device.PairingManager"
            ) as MockPairing:
                MockPairing.return_value.is_paired.return_value = True

                result = cli_runner.invoke(
                    cli, ["device", "is-paired", "00008030"]
                )

                assert result.exit_code == 0
                assert "is paired" in result.output

    def test_is_paired_false(
        self,
        cli_runner: CliRunner,
        mock_devices: list[DeviceInfo],
    ) -> None:
        """Should exit 1 and show message when not paired."""
        with patch(
            "orange.cli.commands.device.DeviceDetector"
        ) as MockDetector:
            MockDetector.return_value.list_devices.return_value = mock_devices

            with patch(
                "orange.cli.commands.device.PairingManager"
            ) as MockPairing:
                MockPairing.return_value.is_paired.return_value = False

                result = cli_runner.invoke(
                    cli, ["device", "is-paired", "00008030"]
                )

                assert result.exit_code == 1
                assert "not paired" in result.output


class TestVersionFlag:
    """Tests for --version flag."""

    def test_version_output(self, cli_runner: CliRunner) -> None:
        """Should display version information."""
        result = cli_runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "Orange" in result.output
        assert "0.1.0" in result.output


class TestHelpCommand:
    """Tests for --help flag."""

    def test_help_output(self, cli_runner: CliRunner) -> None:
        """Should display help information."""
        result = cli_runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Orange" in result.output
        assert "device" in result.output

    def test_device_help_output(self, cli_runner: CliRunner) -> None:
        """Should display device command help."""
        result = cli_runner.invoke(cli, ["device", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "info" in result.output
        assert "pair" in result.output
