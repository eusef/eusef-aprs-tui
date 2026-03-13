"""Transport abstraction for APRS TUI.

Defines the Transport ABC that all transport implementations must follow,
and the ConnectionState enum tracking transport lifecycle.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class ConnectionState(Enum):
    """Lifecycle states for a transport connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class Transport(ABC):
    """Abstract base class for APRS data transports.

    All transports (KISS TCP, KISS serial, APRS-IS, etc.) implement this
    interface so the rest of the application is transport-agnostic.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish the transport connection."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the transport connection."""
        ...

    @abstractmethod
    async def read_frame(self) -> bytes:
        """Read one deframed payload (e.g., one AX.25 frame from KISS)."""
        ...

    @abstractmethod
    async def write_frame(self, data: bytes) -> None:
        """Write a frame (will be KISS-framed for KISS transports)."""
        ...

    @property
    @abstractmethod
    def state(self) -> ConnectionState:
        """Current connection state."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name like 'KISS TCP 127.0.0.1:8001'."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the transport is currently connected."""
        return self.state == ConnectionState.CONNECTED
