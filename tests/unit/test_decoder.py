"""Tests for APRS packet decoder (protocol/decoder.py).

Covers: Issue #5 - APRS packet decoder (aprslib wrapper)
Sprint: 1 (Foundation)
PRD refs: AC-07 (packet decoding - all types, parse errors, no crash),
          QA 18.1 (all packet types, ParseError handling)

Module under test: aprs_tui.protocol.decoder
Estimated implementation: ~100-150 lines

The decoder wraps aprslib.parse() and normalizes results into APRSPacket
dataclasses. ~5-10% of real-world packets cause ParseError in aprslib;
the decoder must catch all errors and return partial packets with parse_error
set, never crashing.

Supported packet types: position, compressed position, Mic-E, message,
message ack/rej, weather, object, status, telemetry.
"""
from __future__ import annotations

import pytest


# ==========================================================================
# Position packets
# ==========================================================================

class TestDecodePosition:
    """Decoding APRS position packets (uncompressed and compressed)."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_uncompressed_position(self, sample_packets):
        """Standard uncompressed position (!DDMM.MMN/DDDMM.MMW) decodes
        to APRSPacket with info_type='position' and correct lat/lon."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_compressed_position(self, sample_packets):
        """Compressed position (Base91) decodes to correct lat/lon."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_position_extracts_symbol(self, sample_packets):
        """Symbol table and symbol code are extracted from position packet."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_position_extracts_comment(self, sample_packets):
        """Comment text after position data is captured."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_position_with_altitude(self):
        """Position with /A=NNNNNN altitude extension parses altitude."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_position_with_phg(self, sample_packets):
        """Position with PHGxxxx (power/height/gain) extension is parsed."""
        pass


# ==========================================================================
# Mic-E packets
# ==========================================================================

class TestDecodeMicE:
    """Decoding Mic-E encoded position packets."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_mic_e_position(self, sample_packets):
        """Mic-E packet decodes to info_type='mic-e' with valid lat/lon."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_mic_e_extracts_speed_course(self):
        """Mic-E packet extracts speed and course when present."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_mic_e_extracts_status(self):
        """Mic-E status text (after position data) is captured."""
        pass


# ==========================================================================
# Message packets
# ==========================================================================

class TestDecodeMessage:
    """Decoding APRS message, ack, and reject packets."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_message(self, sample_packets):
        """Standard message (:ADDRESSEE:text{NNN) decodes with info_type='message'."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_message_extracts_addressee(self, sample_packets):
        """Addressee field (9-char padded) is extracted and trimmed."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_message_extracts_msgno(self, sample_packets):
        """Message number ({NNN) is extracted for ack tracking."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_message_ack(self, sample_packets):
        """Message ack (:ADDRESSEE:ackNNN) is recognized as ack=True."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_message_reject(self, sample_packets):
        """Message reject (:ADDRESSEE:rejNNN) is recognized as rej=True."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_message_no_msgno(self):
        """A message without a sequence number ({NNN) still decodes."""
        pass


# ==========================================================================
# Weather packets
# ==========================================================================

class TestDecodeWeather:
    """Decoding APRS weather report packets."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_weather_report(self, sample_packets):
        """Positionless weather report decodes with info_type='weather'."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_weather_with_position(self):
        """Weather report combined with position data parses both."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_weather_extracts_fields(self):
        """Wind, temperature, rain, humidity, pressure fields are extracted."""
        pass


# ==========================================================================
# Object packets
# ==========================================================================

class TestDecodeObject:
    """Decoding APRS object reports."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_object(self, sample_packets):
        """Object report (;NAME_____*...) decodes with info_type='object'."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_object_extracts_name(self, sample_packets):
        """Object name (9-char padded) is extracted and trimmed."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_killed_object(self):
        """Killed object (;NAME_____\\_...) is recognized."""
        pass


# ==========================================================================
# Status and telemetry packets
# ==========================================================================

class TestDecodeStatusTelemetry:
    """Decoding APRS status and telemetry packets."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_status(self, sample_packets):
        """Status report (>text) decodes with info_type='status'."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decode_telemetry(self, sample_packets):
        """Telemetry (T#NNN,...) decodes with info_type='telemetry'."""
        pass


# ==========================================================================
# Error handling (AC-07: no crash on parse failure)
# ==========================================================================

class TestDecodeErrors:
    """Parse error handling. The decoder must never crash - ~5-10% of
    real-world packets cause ParseError in aprslib."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_malformed_packet_returns_partial(self, sample_packets):
        """A malformed packet returns APRSPacket with parse_error set, not None."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_malformed_packet_preserves_raw(self, sample_packets):
        """A malformed packet's raw field contains the original packet string."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_malformed_packet_has_source(self, sample_packets):
        """Even on parse failure, source callsign is extracted from the header."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_empty_packet_string(self):
        """An empty string returns a packet with parse_error set."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_no_header_delimiter(self):
        """A string with no ':' (no info field separator) returns parse_error."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_unknown_format_handled(self):
        """aprslib.UnknownFormat exception is caught and reported as parse_error."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_decoder_never_raises(self, sample_packets):
        """No input to decode_packet() raises an unhandled exception."""
        pass


# ==========================================================================
# Metadata
# ==========================================================================

class TestDecodeMetadata:
    """APRSPacket metadata fields are populated correctly."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_source_callsign_extracted(self, sample_packets):
        """source field matches the from-callsign in the packet header."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_destination_extracted(self, sample_packets):
        """destination field matches the to-callsign in the packet header."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_path_extracted(self, sample_packets):
        """path field contains the digipeater list."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_transport_tag_preserved(self):
        """transport field records which transport the packet arrived on."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_timestamp_set(self):
        """timestamp is set to approximately now on decode."""
        pass
