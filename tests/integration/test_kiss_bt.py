"""Integration tests for KISS-over-Bluetooth transport (transport/kiss_bt.py).

Covers: Issue #30 - KISS Bluetooth SPP transport
Sprint: 6 (Serial + Bluetooth Transports)

Module under test: aprs_tui.transport.kiss_bt

Verifies that KissBtTransport inherits correctly from KissSerialTransport,
has BT-appropriate defaults, and that get_bt_device_path returns
platform-correct paths.
"""
from __future__ import annotations

from unittest.mock import patch

from aprs_tui.transport.base import ConnectionState
from aprs_tui.transport.kiss_bt import KissBtTransport, get_bt_device_path
from aprs_tui.transport.kiss_serial import KissSerialTransport


class TestKissBtTransport:
    """KissBtTransport class behavior."""

    def test_inherits_from_kiss_serial(self):
        """KissBtTransport is a subclass of KissSerialTransport."""
        assert issubclass(KissBtTransport, KissSerialTransport)

    def test_default_timeout_5s(self):
        """BT transport uses 5s timeout (longer than serial's 1s default)."""
        transport = KissBtTransport(device="/dev/rfcomm0")
        assert transport._timeout == 5.0

    def test_default_baudrate_9600(self):
        """BT transport defaults to 9600 baud."""
        transport = KissBtTransport(device="/dev/rfcomm0")
        assert transport._baudrate == 9600

    def test_display_name(self):
        """display_name shows BT KISS prefix."""
        transport = KissBtTransport(device="/dev/rfcomm0", baudrate=9600)
        assert transport.display_name == "BT KISS /dev/rfcomm0@9600"

    def test_display_name_macos(self):
        """display_name for macOS BT device."""
        transport = KissBtTransport(device="/dev/cu.MyTNC", baudrate=9600)
        assert transport.display_name == "BT KISS /dev/cu.MyTNC@9600"

    def test_initial_state_disconnected(self):
        """Transport starts in DISCONNECTED state."""
        transport = KissBtTransport(device="/dev/rfcomm0")
        assert transport.state == ConnectionState.DISCONNECTED
        assert not transport.is_connected

    async def test_disconnect_without_connect(self):
        """Disconnecting without connecting does not crash."""
        transport = KissBtTransport(device="/dev/rfcomm0")
        await transport.disconnect()
        assert transport.state == ConnectionState.DISCONNECTED


class TestGetBtDevicePath:
    """get_bt_device_path helper function."""

    @patch("aprs_tui.transport.kiss_bt.platform.system", return_value="Darwin")
    def test_macos_default(self, _mock):
        """macOS without device name returns /dev/cu.BluetoothSerial."""
        assert get_bt_device_path() == "/dev/cu.BluetoothSerial"

    @patch("aprs_tui.transport.kiss_bt.platform.system", return_value="Darwin")
    def test_macos_with_device_name(self, _mock):
        """macOS with device name returns /dev/cu.<name>."""
        assert get_bt_device_path("MyTNC-SerialPort") == "/dev/cu.MyTNC-SerialPort"

    @patch("aprs_tui.transport.kiss_bt.platform.system", return_value="Linux")
    def test_linux_default(self, _mock):
        """Linux returns /dev/rfcomm0."""
        assert get_bt_device_path() == "/dev/rfcomm0"

    @patch("aprs_tui.transport.kiss_bt.platform.system", return_value="Linux")
    def test_linux_ignores_device_name(self, _mock):
        """Linux always returns /dev/rfcomm0 regardless of device_name."""
        assert get_bt_device_path("SomeDevice") == "/dev/rfcomm0"
