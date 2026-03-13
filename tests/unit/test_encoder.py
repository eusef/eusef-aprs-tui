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

import pytest


# ==========================================================================
# Position encoding (for beacons)
# ==========================================================================

class TestEncodePosition:
    """Building APRS position beacon strings."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_uncompressed_position(self):
        """Latitude and longitude encode to !DDMM.MMN/DDDMM.MMW format."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_position_includes_symbol(self):
        """Symbol table char and symbol code are placed correctly in the string."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_position_includes_comment(self):
        """Comment text appended after the position data."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_position_north_east(self):
        """Positive lat/lon encodes as N/E."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_position_south_west(self):
        """Negative lat/lon encodes as S/W."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_position_precision(self):
        """Position encodes to 2-decimal-minute precision (hundredths of a minute)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_position_zero_zero(self):
        """Position at 0,0 (null island) encodes correctly."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_position_extreme_values(self):
        """Positions at +/-90 lat and +/-180 lon encode correctly."""
        pass


# ==========================================================================
# Message encoding
# ==========================================================================

class TestEncodeMessage:
    """Building APRS message strings (AC-08)."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_message_format(self):
        """Message encodes as :{addressee:9s}:{text}{{{msgno}."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_message_pads_addressee(self):
        """Addressee is padded to exactly 9 characters with spaces."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_message_sequence_number(self):
        """Message number is appended as {NNN."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_message_max_length_67(self):
        """Message text is truncated at 67 characters (APRS spec limit)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_message_empty_text(self):
        """A message with empty text body still formats correctly."""
        pass


# ==========================================================================
# Message ack/reject encoding
# ==========================================================================

class TestEncodeAck:
    """Building APRS message ack and reject strings."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_ack(self):
        """Ack encodes as :{addressee:9s}:ack{msgno}."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_reject(self):
        """Reject encodes as :{addressee:9s}:rej{msgno}."""
        pass


# ==========================================================================
# Full packet construction (text line with header)
# ==========================================================================

class TestEncodeFullPacket:
    """Building complete APRS text lines (SRC>DST,PATH:info)."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_full_position_packet(self):
        """Complete position packet includes source, destination, and info field."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_full_message_packet(self):
        """Complete message packet includes source, destination, and message body."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_includes_digipeater_path(self):
        """Packet with WIDE1-1,WIDE2-1 path includes digis in header."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_uses_configured_callsign(self):
        """Source callsign matches the station config callsign-SSID."""
        pass


# ==========================================================================
# AX.25 frame construction (for KISS transport)
# ==========================================================================

class TestEncodeAx25Frame:
    """Building AX.25 binary frames from APRS text for KISS transmission."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_ax25_frame(self):
        """Encoder produces a valid AX.25 binary frame from APRS text."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_ax25_frame_decodeable(self):
        """AX.25 frame from encoder can be decoded back by ax25.decode()."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_encode_ax25_frame_kissable(self):
        """AX.25 frame can be wrapped in KISS framing for transport."""
        pass
