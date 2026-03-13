"""KISS transport over Bluetooth SPP serial devices."""
from __future__ import annotations

import logging
import platform

from .kiss_serial import KissSerialTransport

logger = logging.getLogger(__name__)


def get_bt_device_path(device_name: str = "") -> str:
    """Get the platform-appropriate BT serial device path.

    macOS: /dev/cu.* (NOT /dev/tty.* per ADR-9 - tty blocks on carrier detect)
    Linux: /dev/rfcomm0 (via rfcomm bind)
    """
    system = platform.system()
    if system == "Darwin":
        # macOS: cu.* devices are created automatically on BT pair
        if device_name:
            return f"/dev/cu.{device_name}"
        return "/dev/cu.BluetoothSerial"
    else:
        # Linux: rfcomm0 is the default binding
        return "/dev/rfcomm0"


class KissBtTransport(KissSerialTransport):
    """KISS transport over Bluetooth SPP.

    Extends KissSerialTransport with BT-specific defaults:
    - Read timeout of 5s to detect silent BT disconnects
    - Platform-aware device paths

    Args:
        device: BT serial device path (e.g., /dev/rfcomm0 or /dev/cu.DeviceName)
        baudrate: Baud rate (default 9600)
        timeout: Read timeout (default 5.0 - longer for BT latency)
    """

    def __init__(self, device: str, baudrate: int = 9600, timeout: float = 5.0) -> None:
        super().__init__(device=device, baudrate=baudrate, timeout=timeout)

    @property
    def display_name(self) -> str:
        return f"BT KISS {self._device}@{self._baudrate}"
