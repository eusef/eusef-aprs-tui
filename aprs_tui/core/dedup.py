"""Packet deduplication filter for dual-mode operation."""
from __future__ import annotations

import hashlib
import time

from aprs_tui.protocol.types import APRSPacket


class DeduplicationFilter:
    """Drops duplicate packets within a configurable time window.

    Dedup key = hash(source callsign + raw packet text).
    """

    def __init__(self, window: float = 30.0) -> None:
        self._window = window
        self._seen: dict[str, float] = {}  # hash -> timestamp

    def is_duplicate(self, pkt: APRSPacket) -> bool:
        """Check if packet is a duplicate. Returns True if it should be dropped."""
        if pkt.parse_error:
            return False  # Never dedup parse errors

        key = self._make_key(pkt)
        now = time.monotonic()

        # Cleanup expired entries periodically
        if len(self._seen) > 1000:
            self._cleanup(now)

        if key in self._seen:
            if now - self._seen[key] < self._window:
                return True  # Duplicate within window

        self._seen[key] = now
        return False

    def _make_key(self, pkt: APRSPacket) -> str:
        source = (pkt.source or "").upper()
        raw = pkt.raw or ""
        # Hash source + raw to create a compact key
        return hashlib.md5(f"{source}:{raw}".encode(), usedforsecurity=False).hexdigest()

    def _cleanup(self, now: float) -> None:
        expired = [k for k, t in self._seen.items() if now - t >= self._window]
        for k in expired:
            del self._seen[k]

    def reset(self) -> None:
        self._seen.clear()

    @property
    def window(self) -> float:
        return self._window
