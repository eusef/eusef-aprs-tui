"""Tests for AX.25 frame encode/decode (protocol/ax25.py).

Covers: Issue #4 - AX.25 frame encode/decode (binary <-> text)
Sprint: 1 (Foundation)
PRD refs: AC-07 (packet decoding pipeline), ADR-10 (AX.25 codec as separate module)

Module under test: aprs_tui.protocol.ax25
Estimated implementation: ~100-150 lines per direction (encode + decode)

This module is the critical bridge between KISS binary frames and aprslib's
text-format parser. aprslib expects strings like "W3ADO-1>APRS,WIDE1-1:!4903.50N/..."
NOT binary AX.25 frames. Without this codec, KISS-received packets cannot be parsed.

AX.25 UI frame structure (for APRS):
  [Dest 7B][Src 7B][Digipeaters 0-8x7B][Ctrl 0x03][PID 0xF0][Info variable]

Address encoding (per 7-byte field):
  Bytes 0-5: ASCII callsign chars, each left-shifted by 1 bit. Pad with space (0x40).
  Byte 6: 0bSSSS_RRRH where S=SSID(0-15), R=reserved(set to 1), H=has-been-repeated,
           bit 0 = end-of-address marker (1 on last address only).
"""
from __future__ import annotations

import pytest


# ==========================================================================
# AX.25 address parsing
# ==========================================================================

class TestAx25AddressDecode:
    """Decoding AX.25 7-byte address fields to callsign-SSID strings."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_simple_callsign(self):
        """6-char callsign with SSID 0 decodes to 'W3ADO' (no -0 suffix)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_callsign_with_ssid(self):
        """Callsign with non-zero SSID decodes to 'W3ADO-1'."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_short_callsign_strips_padding(self):
        """Callsign shorter than 6 chars (space-padded) has trailing spaces stripped."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_max_ssid_15(self):
        """SSID 15 decodes correctly (maximum valid SSID)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_end_of_address_marker(self):
        """The last address in the chain has bit 0 of byte 6 set to 1."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_has_been_repeated_flag(self):
        """Digipeater address with H-bit set indicates it has been repeated."""
        pass


# ==========================================================================
# AX.25 address encoding
# ==========================================================================

class TestAx25AddressEncode:
    """Encoding callsign-SSID strings to AX.25 7-byte address fields."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_simple_callsign(self):
        """'W3ADO' encodes to 7 bytes with each char left-shifted, SSID 0."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_callsign_with_ssid(self):
        """'W3ADO-1' encodes with SSID=1 in byte 6."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_pads_short_callsign(self):
        """'N0CALL' shorter than 6 chars is padded with spaces (0x40 after shift)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_last_address_marker(self):
        """Last address in chain has end-of-address bit set in byte 6."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_preserves_case_uppercase(self):
        """Callsigns are stored as uppercase in AX.25."""
        pass


# ==========================================================================
# Full frame decode (binary -> text line)
# ==========================================================================

class TestAx25FrameDecode:
    """Decoding complete AX.25 binary frames to text-format APRS strings."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_simple_ui_frame(self, sample_ax25_frames):
        """A standard UI frame decodes to 'SRC>DST:info_field' text format."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_frame_with_digipeaters(self):
        """A frame with 2 digipeaters decodes to 'SRC>DST,DIGI1,DIGI2:info'."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_frame_with_repeated_digi(self):
        """A repeated digipeater address shows as 'WIDE1-1*' (with asterisk)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_frame_max_digipeaters(self):
        """A frame with 8 digipeaters (AX.25 maximum) decodes correctly."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_verifies_control_byte(self):
        """Control byte must be 0x03 (UI frame). Other values are rejected."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_verifies_pid_byte(self):
        """PID byte must be 0xF0 (no layer-3 protocol). Other values rejected."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_extracts_info_field(self, sample_ax25_frames):
        """The info field (everything after PID) is preserved as-is."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_output_parseable_by_aprslib(self, sample_ax25_frames):
        """The decoded text line can be passed to aprslib.parse() successfully."""
        pass


# ==========================================================================
# Full frame encode (text line -> binary)
# ==========================================================================

class TestAx25FrameEncode:
    """Encoding text-format APRS strings to AX.25 binary frames."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_simple_packet(self):
        """'W3ADO-1>APRS:!4903.50N/07201.75W-' encodes to valid AX.25 binary."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_with_digipeater_path(self):
        """'SRC>DST,WIDE1-1,WIDE2-1:info' includes digipeater addresses."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_sets_control_and_pid(self):
        """Encoded frame has Control=0x03 and PID=0xF0."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_encode_sets_end_of_address_marker(self):
        """Last address (source if no digis, last digi otherwise) has end marker."""
        pass


# ==========================================================================
# Roundtrip
# ==========================================================================

class TestAx25Roundtrip:
    """Encode -> Decode roundtrip preserves the APRS text line."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_roundtrip_position_packet(self):
        """Text -> binary -> text roundtrip for a position packet."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_roundtrip_message_packet(self):
        """Text -> binary -> text roundtrip for a message packet."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_roundtrip_with_digipeaters(self):
        """Roundtrip preserves digipeater path."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_roundtrip_binary_first(self, sample_ax25_frames):
        """Binary -> text -> binary roundtrip for known AX.25 frames."""
        pass


# ==========================================================================
# Edge cases and error handling
# ==========================================================================

class TestAx25EdgeCases:
    """Malformed frames and boundary conditions."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_frame_too_short(self):
        """Frame shorter than minimum (14 bytes: dest + src) raises error."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_frame_missing_end_marker(self):
        """Frame where no address has end-of-address bit set is handled."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_frame_non_ascii_in_callsign(self):
        """Non-printable bytes in callsign field handled gracefully."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_frame_empty_info_field(self):
        """A frame with no info field (just addresses + control + PID) handled."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_frame_maximum_info_field_256_bytes(self):
        """A frame with 256-byte info field (AX.25 max) encodes/decodes correctly."""
        pass
