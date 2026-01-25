"""
Tests for device pairing functionality.

Tests the PairingManager class and pairing workflow.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orange.core.connection.pairing import PairingManager, PairingState
from orange.exceptions import (
    DeviceNotFoundError,
    PairingError,
    PairingTimeoutError,
)

from pymobiledevice3.exceptions import (
    ConnectionFailedError,
    MuxException,
)


class TestPairingState:
    """Tests for PairingState enum."""

    def test_pairing_states_exist(self) -> None:
        """All expected pairing states should exist."""
        assert PairingState.NOT_PAIRED.value == "not_paired"
        assert PairingState.PAIRING_IN_PROGRESS.value == "pairing_in_progress"
        assert PairingState.WAITING_FOR_USER.value == "waiting_for_user"
        assert PairingState.PAIRED.value == "paired"
        assert PairingState.PAIRING_FAILED.value == "pairing_failed"


class TestPairingManager:
    """Tests for PairingManager class."""

    def test_init_sets_udid(self) -> None:
        """PairingManager should store the UDID."""
        udid = "00008030-001234567890001E"
        manager = PairingManager(udid)
        assert manager.udid == udid

    def test_init_sets_not_paired_state(self) -> None:
        """PairingManager should start in NOT_PAIRED state."""
        manager = PairingManager("test-udid")
        assert manager.state == PairingState.NOT_PAIRED

    def test_is_paired_returns_true_when_paired(
        self,
        patch_pairing_lockdown: MagicMock,
    ) -> None:
        """is_paired should return True when device is paired."""
        manager = PairingManager("test-udid")
        assert manager.is_paired() is True
        assert manager.state == PairingState.PAIRED

    def test_is_paired_returns_false_when_not_paired(self) -> None:
        """is_paired should return False when device is not paired."""
        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            side_effect=ConnectionFailedError(),
        ):
            manager = PairingManager("test-udid")
            assert manager.is_paired() is False
            assert manager.state == PairingState.NOT_PAIRED

    def test_is_paired_raises_device_not_found_on_mux_error(self) -> None:
        """is_paired should raise DeviceNotFoundError on MuxException."""
        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            side_effect=MuxException("Device not found"),
        ):
            manager = PairingManager("test-udid")
            with pytest.raises(DeviceNotFoundError):
                manager.is_paired()

    def test_pair_returns_true_when_already_paired(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """pair should return True immediately if already paired."""
        mock_lockdown_client.paired = True

        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            return_value=mock_lockdown_client,
        ):
            manager = PairingManager("test-udid")
            result = manager.pair(timeout=1)
            assert result is True
            assert manager.state == PairingState.PAIRED

    def test_pair_calls_on_prompt_callback(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """pair should call on_prompt callback when waiting for user."""
        mock_lockdown_client.paired = False
        mock_lockdown_client.pair = MagicMock()  # Successful pair

        callback_called = []

        def on_prompt() -> None:
            callback_called.append(True)

        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            return_value=mock_lockdown_client,
        ):
            manager = PairingManager("test-udid")
            manager.pair(on_prompt=on_prompt, timeout=1)

        assert len(callback_called) == 1

    def test_pair_raises_device_not_found_on_mux_error(self) -> None:
        """pair should raise DeviceNotFoundError on MuxException."""
        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            side_effect=MuxException("Device not found"),
        ):
            manager = PairingManager("test-udid")
            with pytest.raises(DeviceNotFoundError):
                manager.pair(timeout=1)

    def test_unpair_returns_true_on_success(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """unpair should return True on successful unpair."""
        mock_lockdown_client.unpair = MagicMock()

        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            return_value=mock_lockdown_client,
        ):
            manager = PairingManager("test-udid")
            result = manager.unpair()
            assert result is True
            assert manager.state == PairingState.NOT_PAIRED

    def test_unpair_raises_device_not_found_on_mux_error(self) -> None:
        """unpair should raise DeviceNotFoundError on MuxException."""
        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            side_effect=MuxException("Device not found"),
        ):
            manager = PairingManager("test-udid")
            with pytest.raises(DeviceNotFoundError):
                manager.unpair()

    def test_validate_pairing_returns_true_when_valid(
        self,
        mock_lockdown_client: MagicMock,
    ) -> None:
        """validate_pairing should return True when pairing is valid."""
        mock_lockdown_client.validate_pairing = MagicMock()

        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            return_value=mock_lockdown_client,
        ):
            manager = PairingManager("test-udid")
            result = manager.validate_pairing()
            assert result is True
            assert manager.state == PairingState.PAIRED

    def test_validate_pairing_returns_false_when_invalid(self) -> None:
        """validate_pairing should return False when pairing is invalid."""
        with patch(
            "orange.core.connection.pairing.create_using_usbmux",
            side_effect=ConnectionFailedError(),
        ):
            manager = PairingManager("test-udid")
            result = manager.validate_pairing()
            assert result is False
            assert manager.state == PairingState.NOT_PAIRED
