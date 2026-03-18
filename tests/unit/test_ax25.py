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

from aprs_tui.protocol.ax25 import (
    AX25Frame,
    ax25_decode,
    ax25_encode,
    ax25_to_text,
    decode_address,
    encode_address,
)

# ==========================================================================
# AX.25 address parsing
# ==========================================================================

class TestAx25AddressDecode:
    """Decoding AX.25 7-byte address fields to callsign-SSID strings."""

    def test_decode_simple_callsign(self):
        """6-char callsign with SSID 0 decodes to 'W3ADO' (no -0 suffix)."""
        addr = encode_address("W3ADO", ssid=0)
        callsign, ssid, is_last, has_been_repeated = decode_address(addr)
        assert callsign == "W3ADO"
        assert ssid == 0

    def test_decode_callsign_with_ssid(self):
        """Callsign with non-zero SSID decodes to 'W3ADO-1'."""
        addr = encode_address("W3ADO", ssid=1)
        callsign, ssid, is_last, has_been_repeated = decode_address(addr)
        assert callsign == "W3ADO"
        assert ssid == 1

    def test_decode_short_callsign_strips_padding(self):
        """Callsign shorter than 6 chars (space-padded) has trailing spaces stripped."""
        addr = encode_address("AB", ssid=0)
        callsign, ssid, _, _ = decode_address(addr)
        assert callsign == "AB"
        assert " " not in callsign

    def test_decode_max_ssid_15(self):
        """SSID 15 decodes correctly (maximum valid SSID)."""
        addr = encode_address("W3ADO", ssid=15)
        callsign, ssid, _, _ = decode_address(addr)
        assert ssid == 15

    def test_decode_end_of_address_marker(self):
        """The last address in the chain has bit 0 of byte 6 set to 1."""
        addr = encode_address("W3ADO", ssid=1, last=True)
        _, _, is_last, _ = decode_address(addr)
        assert is_last is True

        addr_not_last = encode_address("W3ADO", ssid=1, last=False)
        _, _, is_last, _ = decode_address(addr_not_last)
        assert is_last is False

    def test_decode_has_been_repeated_flag(self):
        """Digipeater address with H-bit set indicates it has been repeated."""
        # Build an address with H-bit (bit 7 of byte 6) set
        addr = bytearray(encode_address("WIDE1", ssid=1))
        addr[6] |= 0x80  # set H-bit
        callsign, ssid, _, has_been_repeated = decode_address(bytes(addr))
        assert has_been_repeated is True
        assert callsign == "WIDE1"
        assert ssid == 1


# ==========================================================================
# AX.25 address encoding
# ==========================================================================

class TestAx25AddressEncode:
    """Encoding callsign-SSID strings to AX.25 7-byte address fields."""

    def test_encode_simple_callsign(self):
        """'W3ADO' encodes to 7 bytes with each char left-shifted, SSID 0."""
        addr = encode_address("W3ADO", ssid=0)
        assert len(addr) == 7
        # Each character should be left-shifted by 1
        for i, ch in enumerate("W3ADO "):
            assert addr[i] == ord(ch) << 1

    def test_encode_callsign_with_ssid(self):
        """'W3ADO-1' encodes with SSID=1 in byte 6."""
        addr = encode_address("W3ADO", ssid=1)
        ssid_byte = addr[6]
        extracted_ssid = (ssid_byte >> 1) & 0x0F
        assert extracted_ssid == 1

    def test_encode_pads_short_callsign(self):
        """'N0CALL' shorter than 6 chars is padded with spaces (0x40 after shift)."""
        addr = encode_address("AB", ssid=0)
        # Positions 2-5 should be space (0x20) left-shifted = 0x40
        for i in range(2, 6):
            assert addr[i] == 0x40

    def test_encode_last_address_marker(self):
        """Last address in chain has end-of-address bit set in byte 6."""
        addr = encode_address("W3ADO", ssid=0, last=True)
        assert addr[6] & 0x01 == 1

        addr_not_last = encode_address("W3ADO", ssid=0, last=False)
        assert addr_not_last[6] & 0x01 == 0

    def test_encode_preserves_case_uppercase(self):
        """Callsigns are stored as uppercase in AX.25."""
        addr = encode_address("w3ado", ssid=0)
        callsign, _, _, _ = decode_address(addr)
        assert callsign == "W3ADO"


# ==========================================================================
# Full frame decode (binary -> text line)
# ==========================================================================

class TestAx25FrameDecode:
    """Decoding complete AX.25 binary frames to text-format APRS strings."""

    def test_decode_simple_ui_frame(self, sample_ax25_frames):
        """A standard UI frame decodes to 'SRC>DST:info_field' text format."""
        frame = ax25_decode(sample_ax25_frames["position"])
        text = ax25_to_text(frame)
        assert "W3ADO-1" in text
        assert "APRS" in text
        assert "!4903.50N/07201.75W-" in text
        assert text == "W3ADO-1>APRS:!4903.50N/07201.75W-"

    def test_decode_frame_with_digipeaters(self):
        """A frame with 2 digipeaters decodes to 'SRC>DST,DIGI1,DIGI2:info'."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            digipeaters=["WIDE1-1", "WIDE2-1"],
            info=b"!4903.50N/07201.75W-",
        )
        frame = ax25_decode(frame_bytes)
        text = ax25_to_text(frame)
        assert text == "W3ADO-1>APRS,WIDE1-1,WIDE2-1:!4903.50N/07201.75W-"

    def test_decode_frame_with_repeated_digi(self):
        """A repeated digipeater address shows as 'WIDE1-1*' (with asterisk)."""
        # Build frame manually with H-bit set on first digi
        frame_bytes = bytearray(ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            digipeaters=["WIDE1-1", "WIDE2-1"],
            info=b"test",
        ))
        # Set H-bit on first digipeater (byte 6 of digi1 address)
        # Dest=7 + Src=7 = 14, so first digi starts at 14, its SSID byte is at 14+6=20
        frame_bytes[20] |= 0x80
        frame = ax25_decode(bytes(frame_bytes))
        text = ax25_to_text(frame)
        assert "WIDE1-1*" in text

    def test_decode_frame_max_digipeaters(self):
        """A frame with 8 digipeaters (AX.25 maximum) decodes correctly."""
        digis = [f"DIGI{i}-{i}" for i in range(1, 9)]
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            digipeaters=digis,
            info=b"test",
        )
        frame = ax25_decode(frame_bytes)
        assert len(frame.digipeaters) == 8
        text = ax25_to_text(frame)
        for d in digis:
            assert d in text

    def test_decode_verifies_control_byte(self):
        """Control byte must be 0x03 (UI frame). Other values are rejected."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=b"test",
        )
        # Replace control byte (at offset 14) with something else
        frame_bytes = bytearray(frame_bytes)
        frame_bytes[14] = 0xFF
        with pytest.raises(ValueError, match="control byte"):
            ax25_decode(bytes(frame_bytes))

    def test_decode_verifies_pid_byte(self):
        """PID byte must be 0xF0 (no layer-3 protocol). Other values rejected."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=b"test",
        )
        # Replace PID byte (at offset 15) with something else
        frame_bytes = bytearray(frame_bytes)
        frame_bytes[15] = 0xCC
        with pytest.raises(ValueError, match="PID byte"):
            ax25_decode(bytes(frame_bytes))

    def test_decode_extracts_info_field(self, sample_ax25_frames):
        """The info field (everything after PID) is preserved as-is."""
        frame = ax25_decode(sample_ax25_frames["position"])
        assert frame.info == b"!4903.50N/07201.75W-"

    def test_decode_output_parseable_by_aprslib(self, sample_ax25_frames):
        """The decoded text line can be passed to aprslib.parse() successfully."""
        try:
            import aprslib
        except ImportError:
            pytest.skip("aprslib not installed")

        frame = ax25_decode(sample_ax25_frames["position"])
        text = ax25_to_text(frame)
        parsed = aprslib.parse(text)
        assert parsed["from"] == "W3ADO-1"


# ==========================================================================
# Full frame encode (text line -> binary)
# ==========================================================================

class TestAx25FrameEncode:
    """Encoding text-format APRS strings to AX.25 binary frames."""

    def test_encode_simple_packet(self):
        """'W3ADO-1>APRS:!4903.50N/07201.75W-' encodes to valid AX.25 binary."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=b"!4903.50N/07201.75W-",
        )
        # Should be dest(7) + src(7) + ctrl(1) + pid(1) + info(20) = 36 bytes
        assert len(frame_bytes) == 7 + 7 + 1 + 1 + 20
        # Verify it can be decoded back
        frame = ax25_decode(frame_bytes)
        assert frame.source == "W3ADO-1"
        assert frame.destination == "APRS"

    def test_encode_with_digipeater_path(self):
        """'SRC>DST,WIDE1-1,WIDE2-1:info' includes digipeater addresses."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            digipeaters=["WIDE1-1", "WIDE2-1"],
            info=b"test",
        )
        # dest(7) + src(7) + 2*digi(14) + ctrl(1) + pid(1) + info(4) = 34
        assert len(frame_bytes) == 7 + 7 + 14 + 1 + 1 + 4
        frame = ax25_decode(frame_bytes)
        assert len(frame.digipeaters) == 2

    def test_encode_sets_control_and_pid(self):
        """Encoded frame has Control=0x03 and PID=0xF0."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=b"test",
        )
        # Control is at offset 14 (after dest+src), PID at offset 15
        assert frame_bytes[14] == 0x03
        assert frame_bytes[15] == 0xF0

    def test_encode_sets_end_of_address_marker(self):
        """Last address (source if no digis, last digi otherwise) has end marker."""
        # No digipeaters -- source is last
        frame_no_digi = ax25_encode(
            source="W3ADO-1", destination="APRS", info=b"test"
        )
        # Source SSID byte is at offset 13 (dest=7, src bytes 7-13, ssid at 13)
        assert frame_no_digi[13] & 0x01 == 1
        # Dest should NOT have end marker
        assert frame_no_digi[6] & 0x01 == 0

        # With digipeaters -- last digi is last
        frame_with_digi = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            digipeaters=["WIDE1-1"],
            info=b"test",
        )
        # Source should NOT have end marker when digis present
        assert frame_with_digi[13] & 0x01 == 0
        # Last digi SSID byte at offset 20 (dest=7, src=7, digi starts at 14, ssid at 20)
        assert frame_with_digi[20] & 0x01 == 1


# ==========================================================================
# Roundtrip
# ==========================================================================

class TestAx25Roundtrip:
    """Encode -> Decode roundtrip preserves the APRS text line."""

    def test_roundtrip_position_packet(self):
        """Text -> binary -> text roundtrip for a position packet."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=b"!4903.50N/07201.75W-",
        )
        frame = ax25_decode(frame_bytes)
        text = ax25_to_text(frame)
        assert text == "W3ADO-1>APRS:!4903.50N/07201.75W-"

    def test_roundtrip_message_packet(self):
        """Text -> binary -> text roundtrip for a message packet."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=b":N0CALL   :Hello{001",
        )
        frame = ax25_decode(frame_bytes)
        text = ax25_to_text(frame)
        assert text == "W3ADO-1>APRS::N0CALL   :Hello{001"

    def test_roundtrip_with_digipeaters(self):
        """Roundtrip preserves digipeater path."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            digipeaters=["WIDE1-1", "WIDE2-1"],
            info=b"!4903.50N/07201.75W-",
        )
        frame = ax25_decode(frame_bytes)
        text = ax25_to_text(frame)
        assert text == "W3ADO-1>APRS,WIDE1-1,WIDE2-1:!4903.50N/07201.75W-"

    def test_roundtrip_binary_first(self, sample_ax25_frames):
        """Binary -> text -> binary roundtrip for known AX.25 frames."""
        original = sample_ax25_frames["position"]
        frame = ax25_decode(original)
        # Re-encode from decoded components
        rebuilt = ax25_encode(
            source=frame.source,
            destination=frame.destination,
            digipeaters=[d.rstrip("*") for d in frame.digipeaters],
            info=frame.info,
        )
        assert rebuilt == original


# ==========================================================================
# Edge cases and error handling
# ==========================================================================

class TestAx25EdgeCases:
    """Malformed frames and boundary conditions."""

    def test_frame_too_short(self):
        """Frame shorter than minimum (14 bytes: dest + src) raises error."""
        with pytest.raises(ValueError, match="too short"):
            ax25_decode(b"\x00" * 10)

    def test_frame_missing_end_marker(self):
        """Frame where no address has end-of-address bit set is handled."""
        # Build addresses without end marker -- decoder should raise or handle
        dest = encode_address("APRS", ssid=0, last=False)
        src = encode_address("W3ADO", ssid=1, last=False)  # no end marker!
        # This will make the decoder look for more digipeater addresses
        # and eventually run out of bytes
        frame = dest + src + bytes([0x03, 0xF0]) + b"test"
        with pytest.raises(ValueError):
            ax25_decode(frame)

    def test_frame_non_ascii_in_callsign(self):
        """Non-printable bytes in callsign field handled gracefully."""
        # Build a valid frame structure but with weird callsign bytes
        dest = encode_address("APRS", ssid=0, last=False)
        src = encode_address("W3ADO", ssid=1, last=True)
        frame = dest + src + bytes([0x03, 0xF0]) + b"test"
        # Corrupt a callsign byte
        frame = bytearray(frame)
        frame[0] = 0x02  # not a valid shifted ASCII char
        # Should not crash
        result = ax25_decode(bytes(frame))
        assert isinstance(result, AX25Frame)

    def test_frame_empty_info_field(self):
        """A frame with no info field (just addresses + control + PID) handled."""
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=b"",
        )
        frame = ax25_decode(frame_bytes)
        assert frame.info == b""

    def test_frame_maximum_info_field_256_bytes(self):
        """A frame with 256-byte info field (AX.25 max) encodes/decodes correctly."""
        info = bytes(range(256))
        frame_bytes = ax25_encode(
            source="W3ADO-1",
            destination="APRS",
            info=info,
        )
        frame = ax25_decode(frame_bytes)
        assert frame.info == info
        assert len(frame.info) == 256
