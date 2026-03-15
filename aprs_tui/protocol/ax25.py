"""AX.25 frame encode/decode.

Critical bridge between KISS binary frames and aprslib text-format parser.
aprslib expects strings like ``"W3ADO-1>APRS,WIDE1-1:!4903.50N/..."``
NOT binary AX.25 frames.

AX.25 UI frame structure (for APRS):
  [Dest 7B][Src 7B][Digipeaters 0-8x7B][Ctrl 0x03][PID 0xF0][Info variable]

Address encoding (per 7-byte field):
  Bytes 0-5: ASCII callsign chars, each left-shifted by 1 bit.
             Pad with spaces to 6 chars (0x20 -> 0x40 after shift).
  Byte 6:   SSID byte: 0b0RR_SSSS_H
             bits 5-6: reserved (set to 1)
             bits 1-4: SSID (0-15)
             bit 0:    end-of-address marker (1 on last address)
             bit 7:    has-been-repeated (H-bit, for digipeaters)
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class AX25Frame:
    """Decoded AX.25 UI frame."""

    source: str               # e.g. "W3ADO-1"
    destination: str          # e.g. "APRS"
    digipeaters: list[str] = field(default_factory=list)  # e.g. ["WIDE1-1", "WIDE2-1*"]
    info: bytes = b""         # raw info field
    control: int = 0x03       # UI frame
    pid: int = 0xF0           # no layer-3 protocol


# ---------------------------------------------------------------------------
# Address helpers
# ---------------------------------------------------------------------------

def decode_address(data: bytes) -> tuple[str, int, bool, bool]:
    """Decode a 7-byte AX.25 address field.

    Returns:
        (callsign, ssid, is_last, has_been_repeated)

    The six callsign characters are each right-shifted by 1 bit and
    trailing spaces are stripped.  SSID is extracted from bits 1-4 of
    byte 6.  Bit 0 of byte 6 is the end-of-address marker.  Bit 7 of
    byte 6 is the has-been-repeated (H-bit) flag.
    """
    if len(data) < 7:
        raise ValueError(f"Address field must be 7 bytes, got {len(data)}")

    callsign = "".join(chr(b >> 1) for b in data[:6]).rstrip()
    ssid_byte = data[6]
    ssid = (ssid_byte >> 1) & 0x0F
    is_last = bool(ssid_byte & 0x01)
    has_been_repeated = bool(ssid_byte & 0x80)
    return callsign, ssid, is_last, has_been_repeated


def encode_address(callsign: str, ssid: int = 0, last: bool = False) -> bytes:
    """Encode callsign + SSID to a 7-byte AX.25 address field.

    Each character is left-shifted by 1 bit.  The callsign is padded with
    spaces to 6 characters.  The SSID byte has reserved bits 5-6 set to 1.
    If *last* is True, the end-of-address marker (bit 0) is set.
    """
    call = callsign.upper().ljust(6)[:6]
    encoded = bytes([ord(c) << 1 for c in call])
    ssid_byte = 0b01100000 | ((ssid & 0x0F) << 1)
    if last:
        ssid_byte |= 0x01
    return encoded + bytes([ssid_byte])


def _parse_callsign_ssid(text: str) -> tuple[str, int]:
    """Parse a 'CALL-SSID' or 'CALL' string into (callsign, ssid)."""
    # Strip any trailing "*" (H-bit marker in text representation)
    clean = text.rstrip("*")
    if "-" in clean:
        call, ssid_str = clean.rsplit("-", 1)
        return call, int(ssid_str)
    return clean, 0


def _format_callsign(callsign: str, ssid: int) -> str:
    """Format callsign and SSID to standard text representation."""
    if ssid == 0:
        return callsign
    return f"{callsign}-{ssid}"


# ---------------------------------------------------------------------------
# Full frame decode
# ---------------------------------------------------------------------------

def ax25_decode(frame: bytes) -> AX25Frame:
    """Parse a binary AX.25 frame into an :class:`AX25Frame`.

    Raises :class:`ValueError` if the frame is too short, or has an
    unexpected control byte or PID.
    """
    # Minimum: dest(7) + src(7) + ctrl(1) + pid(1) = 16 bytes
    if len(frame) < 16:
        raise ValueError(
            f"AX.25 frame too short: {len(frame)} bytes (minimum 16)"
        )

    # --- Destination (first 7 bytes) ---
    dest_call, dest_ssid, dest_last, _ = decode_address(frame[0:7])

    # --- Source (next 7 bytes) ---
    src_call, src_ssid, src_last, _ = decode_address(frame[7:14])

    # --- Digipeaters (7 bytes each, until end-of-address is set) ---
    digipeaters: list[str] = []
    offset = 14
    last_seen = src_last

    while not last_seen:
        if offset + 7 > len(frame):
            raise ValueError("Frame truncated in digipeater address fields")
        digi_call, digi_ssid, digi_last, digi_repeated = decode_address(
            frame[offset : offset + 7]
        )
        digi_str = _format_callsign(digi_call, digi_ssid)
        if digi_repeated:
            digi_str += "*"
        digipeaters.append(digi_str)
        last_seen = digi_last
        offset += 7

    # --- Control byte ---
    if offset >= len(frame):
        raise ValueError("Frame truncated: missing control byte")
    control = frame[offset]
    if control != 0x03:
        raise ValueError(
            f"Unexpected control byte: 0x{control:02X} (expected 0x03 for UI)"
        )
    offset += 1

    # --- PID byte ---
    if offset >= len(frame):
        raise ValueError("Frame truncated: missing PID byte")
    pid = frame[offset]
    if pid != 0xF0:
        raise ValueError(
            f"Unexpected PID byte: 0x{pid:02X} (expected 0xF0)"
        )
    offset += 1

    # --- Info field (remainder) ---
    info = frame[offset:]

    return AX25Frame(
        source=_format_callsign(src_call, src_ssid),
        destination=_format_callsign(dest_call, dest_ssid),
        digipeaters=digipeaters,
        info=info,
        control=control,
        pid=pid,
    )


def ax25_to_text(frame: AX25Frame) -> str:
    """Convert an :class:`AX25Frame` to aprslib-compatible text.

    Format: ``SOURCE>DEST,DIGI1,DIGI2:info_field_as_text``

    The info field is decoded as latin-1 to preserve all byte values.
    """
    path_parts = [frame.destination] + frame.digipeaters
    path = ",".join(path_parts)
    info_text = frame.info.decode("latin-1")
    return f"{frame.source}>{path}:{info_text}"


# ---------------------------------------------------------------------------
# Full frame encode
# ---------------------------------------------------------------------------

def ax25_encode(
    source: str,
    destination: str,
    digipeaters: list[str] | None = None,
    info: bytes = b"",
) -> bytes:
    """Build a binary AX.25 UI frame from components.

    *source* and *destination* are ``"CALL-SSID"`` strings.
    *digipeaters* is an optional list of ``"CALL-SSID"`` strings.

    AX.25 command/response: For a UI command frame, destination c/r=1,
    source c/r=0. The c/r bit is bit 7 of the SSID byte.
    """
    if digipeaters is None:
        digipeaters = []

    # Destination is first, never last. Set c/r bit (bit 7) for command frame.
    dest_call, dest_ssid = _parse_callsign_ssid(destination)
    dest_addr = bytearray(encode_address(dest_call, dest_ssid, last=False))
    dest_addr[6] |= 0x80  # Set command bit on destination
    frame = bytearray(dest_addr)

    # Source -- last only if no digipeaters. c/r=0 for command frame (default).
    src_call, src_ssid = _parse_callsign_ssid(source)
    is_last_src = len(digipeaters) == 0
    frame.extend(encode_address(src_call, src_ssid, last=is_last_src))

    # Digipeaters
    for idx, digi in enumerate(digipeaters):
        digi_call, digi_ssid = _parse_callsign_ssid(digi)
        is_last_digi = idx == len(digipeaters) - 1
        frame.extend(encode_address(digi_call, digi_ssid, last=is_last_digi))

    # Control + PID
    frame.append(0x03)
    frame.append(0xF0)

    # Info field
    frame.extend(info)

    return bytes(frame)
