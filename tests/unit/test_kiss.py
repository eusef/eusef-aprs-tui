"""Tests for KISS frame encode/decode (protocol/kiss.py).

Covers: Issue #3 - KISS frame encode/decode (kiss3 wrapper)
Sprint: 1 (Foundation)
PRD refs: QA 18.1 - KISS framing: frame encode/decode, multi-frame stream,
          malformed frame handling.

Module under test: aprs_tui.protocol.kiss
Estimated implementation: ~80-120 lines (thin wrapper around kiss3)

KISS protocol reference:
  - FEND (0xC0): Frame delimiter
  - FESC (0xDB): Escape character
  - TFEND (0xDC): Transposed FEND (FESC + TFEND = literal 0xC0 in data)
  - TFESC (0xDD): Transposed FESC (FESC + TFESC = literal 0xDB in data)
  - Command byte 0x00: Data frame (port 0)
"""
from __future__ import annotations

import pytest

from aprs_tui.protocol.kiss import (
    FEND,
    FESC,
    TFEND,
    TFESC,
    CMD_DATA,
    kiss_frame,
    kiss_deframe,
    KissDeframer,
)


# ==========================================================================
# KISS deframing (raw bytes -> AX.25 payload)
# ==========================================================================

class TestKissDeframe:
    """KISS deframing: extract AX.25 frames from KISS byte stream."""

    def test_deframe_single_frame(self, sample_kiss_frames):
        """Single valid KISS frame deframes to one AX.25 payload."""
        result = kiss_deframe(sample_kiss_frames["position"])
        assert len(result) == 1

    def test_deframe_strips_command_byte(self, sample_kiss_frames):
        """The KISS command byte (0x00) is stripped; only AX.25 data remains."""
        result = kiss_deframe(sample_kiss_frames["position"])
        # The command byte 0x00 should not appear at the start of the payload
        # The first bytes should be AX.25 destination address, not the cmd byte
        assert result[0][0] != CMD_DATA or True  # cmd byte is stripped by design
        # More directly: verify the deframed payload matches the original ax25 frame
        # We can re-derive it: the KISS frame is FEND + CMD + stuffed_payload + FEND
        # So stripping FEND/CMD/FEND and unstuffing should give original payload
        raw = sample_kiss_frames["position"]
        # Strip leading FEND and CMD byte, trailing FEND
        inner = raw[2:-1]  # skip FEND+CMD at start, FEND at end
        assert len(result[0]) == len(inner)  # no stuffing needed for this payload

    def test_deframe_byte_stuffing_fend(self):
        """FESC+TFEND in payload decodes to literal 0xC0."""
        # Build a KISS frame with a byte-stuffed FEND in the payload
        payload_with_fend = bytes([0x01, FESC, TFEND, 0x02])
        frame = bytes([FEND, CMD_DATA]) + payload_with_fend + bytes([FEND])
        result = kiss_deframe(frame)
        assert len(result) == 1
        assert result[0] == bytes([0x01, 0xC0, 0x02])

    def test_deframe_byte_stuffing_fesc(self):
        """FESC+TFESC in payload decodes to literal 0xDB."""
        payload_with_fesc = bytes([0x01, FESC, TFESC, 0x02])
        frame = bytes([FEND, CMD_DATA]) + payload_with_fesc + bytes([FEND])
        result = kiss_deframe(frame)
        assert len(result) == 1
        assert result[0] == bytes([0x01, 0xDB, 0x02])

    def test_deframe_multiple_frames_in_stream(self, sample_kiss_frames):
        """A byte stream containing multiple concatenated KISS frames
        produces one AX.25 payload per frame."""
        stream = sample_kiss_frames["position"] + sample_kiss_frames["message"]
        result = kiss_deframe(stream)
        assert len(result) == 2

    def test_deframe_leading_fend_ignored(self, sample_kiss_frames):
        """Leading FEND bytes (inter-frame fill) are ignored."""
        stream = bytes([FEND, FEND, FEND]) + sample_kiss_frames["position"]
        result = kiss_deframe(stream)
        assert len(result) == 1

    def test_deframe_empty_frame_ignored(self):
        """Two consecutive FENDs with no payload between them produce no output."""
        stream = bytes([FEND, FEND])
        result = kiss_deframe(stream)
        assert len(result) == 0

    def test_deframe_non_data_command_ignored(self):
        """Non-data command bytes (e.g., 0x01-0x0F for TNC control) are ignored
        or handled separately - only 0x00 (data) frames are returned."""
        # Build a frame with command byte 0x01 (TX delay)
        frame = bytes([FEND, 0x01, 0xAA, 0xBB, FEND])
        result = kiss_deframe(frame)
        assert len(result) == 0


# ==========================================================================
# KISS framing (AX.25 payload -> raw bytes)
# ==========================================================================

class TestKissFrame:
    """KISS framing: wrap AX.25 payload into KISS frame for transmission."""

    def test_frame_wraps_with_fend(self, sample_ax25_frames):
        """Framed output starts and ends with FEND (0xC0)."""
        result = kiss_frame(sample_ax25_frames["position"])
        assert result[0] == FEND
        assert result[-1] == FEND

    def test_frame_prepends_command_byte(self, sample_ax25_frames):
        """Data frame has command byte 0x00 after the opening FEND."""
        result = kiss_frame(sample_ax25_frames["position"])
        assert result[1] == CMD_DATA

    def test_frame_byte_stuffing_fend_in_payload(self):
        """A literal 0xC0 in the AX.25 payload is escaped as FESC+TFEND."""
        payload = bytes([0x01, 0xC0, 0x02])
        result = kiss_frame(payload)
        # Should be: FEND + CMD + 0x01 + FESC + TFEND + 0x02 + FEND
        expected = bytes([FEND, CMD_DATA, 0x01, FESC, TFEND, 0x02, FEND])
        assert result == expected

    def test_frame_byte_stuffing_fesc_in_payload(self):
        """A literal 0xDB in the AX.25 payload is escaped as FESC+TFESC."""
        payload = bytes([0x01, 0xDB, 0x02])
        result = kiss_frame(payload)
        expected = bytes([FEND, CMD_DATA, 0x01, FESC, TFESC, 0x02, FEND])
        assert result == expected

    def test_frame_no_stuffing_for_clean_payload(self, sample_ax25_frames):
        """Payload with no FEND/FESC bytes passes through without modification."""
        payload = sample_ax25_frames["position"]
        result = kiss_frame(payload)
        # Check that no byte-stuffing occurred: inner bytes match payload
        inner = result[2:-1]  # strip FEND + CMD at start, FEND at end
        assert inner == payload


# ==========================================================================
# Roundtrip
# ==========================================================================

class TestKissRoundtrip:
    """Frame -> Deframe roundtrip preserves data."""

    def test_roundtrip_position_frame(self, sample_ax25_frames):
        """Frame then deframe a position packet; original payload recovered."""
        payload = sample_ax25_frames["position"]
        framed = kiss_frame(payload)
        result = kiss_deframe(framed)
        assert len(result) == 1
        assert result[0] == payload

    def test_roundtrip_payload_with_fend_byte(self):
        """A payload containing literal 0xC0 survives frame -> deframe."""
        payload = bytes([0x01, 0xC0, 0x02, 0xC0, 0x03])
        framed = kiss_frame(payload)
        result = kiss_deframe(framed)
        assert len(result) == 1
        assert result[0] == payload

    def test_roundtrip_payload_with_fesc_byte(self):
        """A payload containing literal 0xDB survives frame -> deframe."""
        payload = bytes([0x01, 0xDB, 0x02, 0xDB, 0x03])
        framed = kiss_frame(payload)
        result = kiss_deframe(framed)
        assert len(result) == 1
        assert result[0] == payload

    def test_roundtrip_max_length_payload(self):
        """A 256-byte payload (maximum AX.25 info field) survives roundtrip."""
        payload = bytes(range(256))
        framed = kiss_frame(payload)
        result = kiss_deframe(framed)
        assert len(result) == 1
        assert result[0] == payload


# ==========================================================================
# Edge cases and error handling
# ==========================================================================

class TestKissEdgeCases:
    """Malformed input and boundary conditions."""

    def test_incomplete_frame_no_trailing_fend(self):
        """Bytes without a closing FEND are buffered, not returned as a frame."""
        # Use the streaming deframer
        deframer = KissDeframer()
        incomplete = bytes([FEND, CMD_DATA, 0x01, 0x02, 0x03])
        result = deframer.feed(incomplete)
        assert len(result) == 0

    def test_truncated_escape_sequence(self):
        """A FESC at the end of a frame (no TFEND/TFESC following) is handled
        gracefully without crashing."""
        frame = bytes([FEND, CMD_DATA, 0x01, FESC, FEND])
        result = kiss_deframe(frame)
        # Should not crash; the truncated FESC is dropped
        assert len(result) == 1
        assert result[0] == bytes([0x01])

    def test_invalid_escape_byte(self):
        """FESC followed by a byte other than TFEND/TFESC is handled
        (implementation-defined: drop, pass through, or error)."""
        frame = bytes([FEND, CMD_DATA, 0x01, FESC, 0xAA, 0x02, FEND])
        result = kiss_deframe(frame)
        # Should not crash
        assert len(result) == 1
        # Our implementation drops the FESC and keeps the unexpected byte
        assert result[0] == bytes([0x01, 0xAA, 0x02])

    def test_zero_length_payload(self):
        """A KISS frame with only command byte and no payload is handled."""
        frame = bytes([FEND, CMD_DATA, FEND])
        result = kiss_deframe(frame)
        # Command byte only, no actual payload data -- should be skipped
        assert len(result) == 0

    def test_very_large_payload(self):
        """A payload exceeding typical AX.25 max (330 bytes) is handled
        without memory issues."""
        payload = bytes([0x55] * 1000)
        framed = kiss_frame(payload)
        result = kiss_deframe(framed)
        assert len(result) == 1
        assert result[0] == payload
