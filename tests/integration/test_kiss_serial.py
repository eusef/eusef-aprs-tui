"""Integration tests for KISS-over-serial transport (transport/kiss_serial.py).

Covers: Issue #29 - KISS serial transport (pyserial + @work thread=True)
Sprint: 6 (Serial + Bluetooth Transports)
PRD refs: AC-03 (KISS serial connection - open device, baud rate, disconnect detection)
          QA 18.1 (device detection, baud rate handling, USB hot-plug disconnect/reconnect)

Module under test: aprs_tui.transport.kiss_serial
Estimated implementation: ~120-150 lines

Serial transport uses pyserial with asyncio run_in_executor() (ADR-3).
These tests use socat to create a virtual serial loopback pair for testing
without real hardware.

Note: Tests marked @pytest.mark.serial require socat installed.
"""
from __future__ import annotations

import pytest


# ==========================================================================
# Serial connection lifecycle
# ==========================================================================

class TestKissSerialConnect:
    """KISS serial transport connection and disconnection."""

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_connect_to_serial_device(self):
        """Transport opens the serial device at the configured baud rate.
        Uses socat PTY pair for loopback."""
        pass

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_connect_sets_connected_true(self):
        """After successful open, is_connected() returns True."""
        pass

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_connect_nonexistent_device_raises(self):
        """Connecting to /dev/nonexistent raises a clear error."""
        pass

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_connect_wrong_baud_rate(self):
        """Connecting with an unsupported baud rate raises an error or warning."""
        pass

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_disconnect(self):
        """disconnect() closes the serial port; is_connected() returns False."""
        pass

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_display_name(self):
        """display_name shows device path and baud rate."""
        pass


# ==========================================================================
# Serial receive via socat loopback
# ==========================================================================

class TestKissSerialReceive:
    """Reading KISS frames from serial port via socat loopback."""

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_receive_frame_via_loopback(self):
        """Write a KISS frame to one end of socat PTY pair; transport receives it."""
        pass

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_receive_uses_thread_executor(self):
        """Serial read runs in a thread executor (not blocking the event loop)."""
        pass


# ==========================================================================
# USB hot-plug (AC-03 disconnect detection)
# ==========================================================================

class TestKissSerialHotPlug:
    """USB device disconnect and reconnect detection."""

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_detect_usb_disconnect(self):
        """When the serial device disappears (socat killed), the transport
        detects the disconnect and signals it (AC-03)."""
        pass

    @pytest.mark.serial
    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    async def test_disconnect_does_not_crash(self):
        """An unexpected device removal does not raise an unhandled exception."""
        pass


# ==========================================================================
# Baud rate handling
# ==========================================================================

class TestKissSerialBaudRate:
    """Baud rate configuration for different TNC hardware."""

    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    def test_default_baud_9600(self):
        """Default baud rate is 9600 (standard for most TNCs)."""
        pass

    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    def test_ninotnc_baud_57600(self):
        """NinoTNC uses 57600 baud (non-standard)."""
        pass

    @pytest.mark.skip(reason="Sprint 6: Not implemented yet")
    def test_supported_baud_rates(self):
        """Supported baud rates include 1200, 9600, 19200, 57600, 115200."""
        pass
