"""Tests for APRS packet encoder (protocol/encoder.py).

Covers: Issue #16 - APRS packet encoder (position, message, AX.25)
Sprint: 3 (Station List + Beaconing)
PRD refs: AC-08 (messaging format), AC-09 (beacon position format)

Module under test: aprs_tui.protocol.encoder
Estimated implementation: ~100-150 lines

The encoder builds APRS packets for transmission:
- Position beacon: uncompressed lat/lon + symbol + comment
- Message: :{addressee:9s}:{text}{{{msgno}
- Message ack: :{addressee:9s}:ack{msgno}
- Also constructs full AX.25 frames for KISS transmission.
"""
from __future__ import annotations

from aprs_tui.protocol.ax25 import ax25_decode, ax25_encode
from aprs_tui.protocol.encoder import (
    build_packet,
    encode_ack,
    encode_message,
    encode_position,
    encode_rej,
)
from aprs_tui.protocol.kiss import kiss_deframe, kiss_frame

# ==========================================================================
# Position encoding (for beacons)
# ==========================================================================

class TestEncodePosition:
    """Building APRS position beacon strings."""

    def test_encode_uncompressed_position(self):
        """Latitude and longitude encode to !DDMM.MMN/DDDMM.MMW format."""
        result = encode_position(49.0583, -72.0292)
        # 49.0583 -> 49deg 03.50min N
        # -72.0292 -> 72deg 01.75min W
        assert result.startswith("!")
        assert "4903.50N" in result
        assert "07201.75W" in result

    def test_encode_position_includes_symbol(self):
        """Symbol table char and symbol code are placed correctly in the string."""
        result = encode_position(49.0583, -72.0292, "\\", "k")
        # symbol_table between lat and lon, symbol_code after lon
        assert "N\\072" in result
        assert result.endswith("Wk")

    def test_encode_position_includes_comment(self):
        """Comment text appended after the position data."""
        result = encode_position(49.0583, -72.0292, "/", ">", "Test")
        assert result == "!4903.50N/07201.75W>Test"

    def test_encode_position_north_east(self):
        """Positive lat/lon encodes as N/E."""
        result = encode_position(48.8566, 2.3522)
        assert "N" in result
        assert "E" in result
        assert "S" not in result
        assert "W" not in result

    def test_encode_position_south_west(self):
        """Negative lat/lon encodes as S/W."""
        result = encode_position(-33.8688, -70.0)
        assert "S" in result
        assert "W" in result
        # Verify direction markers: lat is negative -> S, lon is negative -> W
        assert "N" not in result
        assert "E" not in result

    def test_encode_position_precision(self):
        """Position encodes to 2-decimal-minute precision (hundredths of a minute)."""
        # 49.0583 degrees = 49 degrees + 0.0583 * 60 = 49 degrees 3.498 minutes
        # Rounded to 2 decimals = 3.50
        result = encode_position(49.0583, -72.0292)
        assert "4903.50" in result
        assert "07201.75" in result

    def test_encode_position_zero_zero(self):
        """Position at 0,0 (null island) encodes correctly."""
        result = encode_position(0.0, 0.0)
        assert result == "!0000.00N/00000.00E>"

    def test_encode_position_extreme_values(self):
        """Positions at +/-90 lat and +/-180 lon encode correctly."""
        result_north = encode_position(90.0, 180.0)
        assert "9000.00N" in result_north
        assert "18000.00E" in result_north

        result_south = encode_position(-90.0, -180.0)
        assert "9000.00S" in result_south
        assert "18000.00W" in result_south


# ==========================================================================
# Message encoding
# ==========================================================================

class TestEncodeMessage:
    """Building APRS message strings (AC-08)."""

    def test_encode_message_format(self):
        """Message encodes as :{addressee:9s}:{text}{{{msgno}."""
        result = encode_message("N0CALL", "Hello", "001")
        assert result == ":N0CALL   :Hello{001"

    def test_encode_message_pads_addressee(self):
        """Addressee is padded to exactly 9 characters with spaces."""
        result = encode_message("AB", "Hi")
        # "AB" padded to 9 chars = "AB       "
        assert result.startswith(":AB       :")

    def test_encode_message_sequence_number(self):
        """Message number is appended as {NNN."""
        result = encode_message("N0CALL", "Test", "042")
        assert result.endswith("{042")

    def test_encode_message_max_length_67(self):
        """Message text is truncated at 67 characters (APRS spec limit)."""
        long_text = "A" * 100
        result = encode_message("N0CALL", long_text)
        # Extract the text part: after ":N0CALL   :" which is 11 chars
        text_part = result[11:]
        assert len(text_part) == 67

    def test_encode_message_empty_text(self):
        """A message with empty text body still formats correctly."""
        result = encode_message("N0CALL", "")
        assert result == ":N0CALL   :"

    def test_encode_message_no_msg_id(self):
        """A message without msg_id has no trailing {NNN."""
        result = encode_message("N0CALL", "Hello")
        assert "{" not in result
        assert result == ":N0CALL   :Hello"


# ==========================================================================
# Message ack/reject encoding
# ==========================================================================

class TestEncodeAck:
    """Building APRS message ack and reject strings."""

    def test_encode_ack(self):
        """Ack encodes as :{addressee:9s}:ack{msgno}."""
        result = encode_ack("N0CALL", "001")
        assert result == ":N0CALL   :ack001"

    def test_encode_reject(self):
        """Reject encodes as :{addressee:9s}:rej{msgno}."""
        result = encode_rej("N0CALL", "001")
        assert result == ":N0CALL   :rej001"


# ==========================================================================
# Full packet construction (text line with header)
# ==========================================================================

class TestEncodeFullPacket:
    """Building complete APRS text lines (SRC>DST,PATH:info)."""

    def test_encode_full_position_packet(self):
        """Complete position packet includes source, destination, and info field."""
        info = encode_position(49.0583, -72.0292, "/", ">", "Test")
        packet = build_packet("N0CALL-9", "APRS", info)
        assert packet == "N0CALL-9>APRS:!4903.50N/07201.75W>Test"

    def test_encode_full_message_packet(self):
        """Complete message packet includes source, destination, and message body."""
        info = encode_message("W3ADO-1", "Hello", "001")
        packet = build_packet("N0CALL", "APRS", info)
        assert packet == "N0CALL>APRS::W3ADO-1  :Hello{001"

    def test_encode_includes_digipeater_path(self):
        """Packet with WIDE1-1,WIDE2-1 path includes digis in header."""
        info = encode_position(49.0583, -72.0292)
        packet = build_packet("N0CALL-9", "APRS", info, ["WIDE1-1", "WIDE2-1"])
        assert "N0CALL-9>APRS,WIDE1-1,WIDE2-1:" in packet

    def test_encode_uses_configured_callsign(self):
        """Source callsign matches the station config callsign-SSID."""
        info = encode_position(0.0, 0.0)
        packet = build_packet("W3ADO-7", "APRS", info)
        assert packet.startswith("W3ADO-7>")


# ==========================================================================
# AX.25 frame construction (for KISS transport)
# ==========================================================================

class TestEncodeAx25Frame:
    """Building AX.25 binary frames from APRS text for KISS transmission."""

    def test_encode_ax25_frame(self):
        """Encoder produces a valid AX.25 binary frame from APRS text."""
        info = encode_position(49.0583, -72.0292, "/", ">", "Test")
        frame = ax25_encode(
            "N0CALL-9", "APRS",
            ["WIDE1-1", "WIDE2-1"],
            info.encode("latin-1"),
        )
        assert isinstance(frame, bytes)
        # Minimum: dest(7) + src(7) + 2 digis(14) + ctrl(1) + pid(1) + info
        assert len(frame) >= 30

    def test_encode_ax25_frame_decodeable(self):
        """AX.25 frame from encoder can be decoded back by ax25.decode()."""
        info = encode_position(49.0583, -72.0292, "/", ">", "Test")
        frame = ax25_encode(
            "N0CALL-9", "APRS",
            ["WIDE1-1", "WIDE2-1"],
            info.encode("latin-1"),
        )
        decoded = ax25_decode(frame)
        assert decoded.source == "N0CALL-9"
        assert decoded.destination == "APRS"
        assert decoded.info == info.encode("latin-1")
        assert "WIDE1-1" in decoded.digipeaters
        assert "WIDE2-1" in decoded.digipeaters

    def test_encode_ax25_frame_kissable(self):
        """AX.25 frame can be wrapped in KISS framing for transport."""
        info = encode_position(49.0583, -72.0292)
        ax25_data = ax25_encode("N0CALL", "APRS", [], info.encode("latin-1"))
        kissed = kiss_frame(ax25_data)
        # KISS frame starts and ends with FEND (0xC0)
        assert kissed[0] == 0xC0
        assert kissed[-1] == 0xC0
        # Deframe should recover the original AX.25 data
        recovered = kiss_deframe(kissed)
        assert len(recovered) == 1
        assert recovered[0] == ax25_data
