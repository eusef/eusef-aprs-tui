"""KISS frame encode/decode.

Implements the KISS TNC protocol framing layer (TNC2 spec).
Handles byte-stuffing/unstuffing and streaming deframing for TCP reads.

Reference: http://www.ax25.net/kiss.aspx
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# KISS protocol constants
# ---------------------------------------------------------------------------

FEND = 0xC0    # Frame delimiter
FESC = 0xDB    # Escape character
TFEND = 0xDC   # Transposed FEND (FESC + TFEND = literal 0xC0 in data)
TFESC = 0xDD   # Transposed FESC (FESC + TFESC = literal 0xDB in data)
CMD_DATA = 0x00  # Data frame command (port 0)


# ---------------------------------------------------------------------------
# Byte-stuffing helpers
# ---------------------------------------------------------------------------

def _stuff(data: bytes) -> bytes:
    """Apply KISS byte-stuffing to *data*.

    0xC0 in payload -> FESC + TFEND
    0xDB in payload -> FESC + TFESC
    """
    out = bytearray()
    for b in data:
        if b == FEND:
            out.extend([FESC, TFEND])
        elif b == FESC:
            out.extend([FESC, TFESC])
        else:
            out.append(b)
    return bytes(out)


def _unstuff(data: bytes) -> bytes:
    """Reverse KISS byte-stuffing in *data*.

    FESC + TFEND -> 0xC0
    FESC + TFESC -> 0xDB
    A lone FESC at end of data or FESC followed by an unexpected byte
    is silently dropped (graceful handling of malformed input).
    """
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == FESC:
            i += 1
            if i >= len(data):
                # Truncated escape at end -- drop it
                break
            nb = data[i]
            if nb == TFEND:
                out.append(FEND)
            elif nb == TFESC:
                out.append(FESC)
            else:
                # Invalid escape sequence -- drop the FESC, keep the byte
                out.append(nb)
        else:
            out.append(b)
        i += 1
    return bytes(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def kiss_frame(data: bytes, command: int = CMD_DATA) -> bytes:
    """Wrap an AX.25 payload in a KISS envelope.

    Returns: FEND + command_byte + byte-stuffed data + FEND
    """
    return bytes([FEND, command]) + _stuff(data) + bytes([FEND])


def kiss_deframe(data: bytes) -> list[bytes]:
    """Extract AX.25 payloads from a KISS byte stream.

    Splits on FEND delimiters, strips command byte, reverses byte-stuffing.
    Skips empty frames and non-data (command != 0x00) frames.
    """
    frames: list[bytes] = []
    # Split on FEND
    parts: list[bytearray] = []
    current = bytearray()
    for b in data:
        if b == FEND:
            if current:
                parts.append(current)
                current = bytearray()
        else:
            current.append(b)
    # Any trailing bytes without closing FEND are ignored (incomplete frame)

    for part in parts:
        if len(part) < 1:
            continue
        command = part[0]
        if command != CMD_DATA:
            continue
        payload = bytes(part[1:])
        if not payload:
            continue
        frames.append(_unstuff(payload))
    return frames


class KissDeframer:
    """Streaming deframer for handling partial TCP reads.

    Accumulates bytes via :meth:`feed` and returns complete frames as they
    become available.  Handles frames split across multiple ``feed()`` calls.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._in_frame = False

    def feed(self, data: bytes) -> list[bytes]:
        """Feed raw bytes and return any complete frames extracted.

        Returns a list of raw AX.25 payloads (byte-stuffing already reversed,
        command byte stripped).  The list may be empty if no complete frame has
        been received yet.
        """
        frames: list[bytes] = []
        for b in data:
            if b == FEND:
                if self._in_frame and self._buffer:
                    # End of a frame -- process it
                    command = self._buffer[0]
                    if command == CMD_DATA and len(self._buffer) > 1:
                        payload = _unstuff(bytes(self._buffer[1:]))
                        frames.append(payload)
                    self._buffer.clear()
                    self._in_frame = False
                else:
                    # Start of a new frame (or inter-frame fill)
                    self._buffer.clear()
                    self._in_frame = True
            else:
                if self._in_frame:
                    self._buffer.append(b)
        return frames
