"""Central async pub/sub packet distribution system.

Decouples transport from UI. Transports publish decoded APRSPackets;
UI panels subscribe via bounded queues.

Issue #42: PacketLogger - file logging subscriber for raw packets.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from platformdirs import user_data_dir

from aprs_tui.protocol.types import APRSPacket


class PacketBus:
    """Async pub/sub bus for APRS packets.

    Transports publish packets, UI panels subscribe. Each subscriber
    gets its own bounded queue. When a subscriber's queue is full,
    the oldest packet is dropped (never blocks the publisher).
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._subscribers: dict[asyncio.Queue[APRSPacket], int] = {}  # queue -> dropped count

    def subscribe(self) -> asyncio.Queue[APRSPacket]:
        """Create and return a new subscriber queue."""
        queue: asyncio.Queue[APRSPacket] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers[queue] = 0
        return queue

    def unsubscribe(self, queue: asyncio.Queue[APRSPacket]) -> None:
        """Remove a subscriber queue."""
        self._subscribers.pop(queue, None)

    def publish(self, packet: APRSPacket) -> None:
        """Publish a packet to all subscribers.

        If a subscriber's queue is full, drop the oldest packet
        and add the new one. Never blocks.
        """
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(packet)
            except asyncio.QueueFull:
                # Drop oldest, add new
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(packet)
                except asyncio.QueueFull:
                    pass
                self._subscribers[queue] = self._subscribers.get(queue, 0) + 1

    def dropped_count(self, queue: asyncio.Queue[APRSPacket]) -> int:
        """Return the number of dropped packets for a subscriber."""
        return self._subscribers.get(queue, 0)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


class PacketLogger:
    """Logs raw packets to daily log files.

    Creates timestamped log files in the application data directory,
    rotating to a new file each day. Each line contains a timestamp
    followed by the raw packet string.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._log_dir = log_dir or Path(user_data_dir("aprs-tui"))
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._current_date: str = ""
        self._file = None

    def log_packet(self, pkt: APRSPacket) -> None:
        """Write a packet to the daily log file."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._rotate(today)
        if self._file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._file.write(f"{timestamp} {pkt.raw}\n")
            self._file.flush()

    def _rotate(self, date: str) -> None:
        """Rotate to a new log file for the given date."""
        if self._file:
            self._file.close()
        self._current_date = date
        log_path = self._log_dir / f"packets-{date}.log"
        self._file = open(log_path, "a")

    def close(self) -> None:
        """Close the current log file."""
        if self._file:
            self._file.close()
            self._file = None
