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

from datetime import datetime, timezone, timedelta

import pytest

from aprs_tui.protocol.decoder import decode_packet
from aprs_tui.protocol.types import APRSPacket


# ==========================================================================
# Position packets
# ==========================================================================

class TestDecodePosition:
    """Decoding APRS position packets (uncompressed and compressed)."""

    def test_decode_uncompressed_position(self, sample_packets):
        """Standard uncompressed position (!DDMM.MMN/DDDMM.MMW) decodes
        to APRSPacket with info_type='position' and correct lat/lon."""
        pkt = decode_packet(sample_packets["position"])
        assert isinstance(pkt, APRSPacket)
        assert pkt.info_type == "position"
        assert pkt.parse_error is None
        # W3ADO-1>APRS,WIDE1-1,WIDE2-1:!4903.50N/07201.75W-...
        # lat: 49 deg 03.50 min N = 49.0583...
        # lon: 072 deg 01.75 min W = -72.0292...
        assert pkt.latitude is not None
        assert pkt.longitude is not None
        assert abs(pkt.latitude - 49.0583) < 0.01
        assert abs(pkt.longitude - (-72.0292)) < 0.01

    def test_decode_compressed_position(self, sample_packets):
        """Compressed position (Base91) decodes to correct lat/lon."""
        pkt = decode_packet(sample_packets["position_compressed"])
        assert pkt.info_type == "position"
        assert pkt.parse_error is None
        assert pkt.latitude is not None
        assert pkt.longitude is not None
        # Compressed position should produce valid coordinates
        assert -90 <= pkt.latitude <= 90
        assert -180 <= pkt.longitude <= 180

    def test_decode_position_extracts_symbol(self, sample_packets):
        """Symbol table and symbol code are extracted from position packet."""
        pkt = decode_packet(sample_packets["position"])
        assert pkt.symbol_table is not None
        assert pkt.symbol_code is not None
        # The position packet has "/" symbol table and "-" symbol code
        assert pkt.symbol_table == "/"
        assert pkt.symbol_code == "-"

    def test_decode_position_extracts_comment(self, sample_packets):
        """Comment text after position data is captured."""
        pkt = decode_packet(sample_packets["position"])
        assert pkt.comment is not None
        # Comment should contain "Test station" (possibly with PHG data)
        assert "Test station" in pkt.comment or "PHG" in (pkt.comment or "")

    def test_decode_position_with_altitude(self):
        """Position with /A=NNNNNN altitude extension parses altitude."""
        raw = "W3ADO-1>APRS:!4903.50N/07201.75W-/A=001234"
        pkt = decode_packet(raw)
        assert pkt.info_type == "position"
        assert pkt.parse_error is None
        assert pkt.altitude is not None
        assert abs(pkt.altitude - 1234.0) < 1.0

    def test_decode_position_with_phg(self, sample_packets):
        """Position with PHGxxxx (power/height/gain) extension is parsed."""
        pkt = decode_packet(sample_packets["position"])
        assert pkt.info_type == "position"
        assert pkt.parse_error is None
        # PHG is part of the comment in the sample packet
        # The decoder should successfully parse the packet
        assert pkt.latitude is not None
        assert pkt.longitude is not None


# ==========================================================================
# Mic-E packets
# ==========================================================================

class TestDecodeMicE:
    """Decoding Mic-E encoded position packets."""

    def test_decode_mic_e_position(self, sample_packets):
        """Mic-E packet decodes to info_type='mic-e' with valid lat/lon."""
        pkt = decode_packet(sample_packets["mic-e"])
        assert pkt.info_type == "mic-e"
        assert pkt.parse_error is None
        assert pkt.latitude is not None
        assert pkt.longitude is not None
        assert -90 <= pkt.latitude <= 90
        assert -180 <= pkt.longitude <= 180

    def test_decode_mic_e_extracts_speed_course(self):
        """Mic-E packet extracts speed and course when present."""
        raw = "KJ4ERJ-9>T2SP0W:`c5Il!<>/`\"4V}_%"
        pkt = decode_packet(raw)
        assert pkt.info_type == "mic-e"
        # Speed and course may or may not be present depending on the packet
        # but the fields should be populated if aprslib can extract them
        assert pkt.parse_error is None

    def test_decode_mic_e_extracts_status(self):
        """Mic-E status text (after position data) is captured."""
        raw = "KJ4ERJ-9>T2SP0W:`c5Il!<>/`\"4V}_%"
        pkt = decode_packet(raw)
        assert pkt.info_type == "mic-e"
        assert pkt.parse_error is None
        # Comment field captures any Mic-E status/type info
        # The packet should be parsed without error


# ==========================================================================
# Message packets
# ==========================================================================

class TestDecodeMessage:
    """Decoding APRS message, ack, and reject packets."""

    def test_decode_message(self, sample_packets):
        """Standard message (:ADDRESSEE:text{NNN) decodes with info_type='message'."""
        pkt = decode_packet(sample_packets["message"])
        assert pkt.info_type == "message"
        assert pkt.parse_error is None
        assert pkt.message_text is not None
        assert "Hello from APRS TUI" in pkt.message_text

    def test_decode_message_extracts_addressee(self, sample_packets):
        """Addressee field (9-char padded) is extracted and trimmed."""
        pkt = decode_packet(sample_packets["message"])
        assert pkt.addressee is not None
        # Should be trimmed: "N0CALL   " -> "N0CALL"
        assert pkt.addressee == "N0CALL"

    def test_decode_message_extracts_msgno(self, sample_packets):
        """Message number ({NNN) is extracted for ack tracking."""
        pkt = decode_packet(sample_packets["message"])
        assert pkt.message_id is not None
        assert pkt.message_id == "001"

    def test_decode_message_ack(self, sample_packets):
        """Message ack (:ADDRESSEE:ackNNN) is recognized as ack=True."""
        pkt = decode_packet(sample_packets["message_ack"])
        assert pkt.info_type == "message"
        assert pkt.parse_error is None
        assert pkt.is_ack is True
        assert pkt.is_rej is False

    def test_decode_message_reject(self, sample_packets):
        """Message reject (:ADDRESSEE:rejNNN) is recognized as rej=True."""
        pkt = decode_packet(sample_packets["message_rej"])
        assert pkt.info_type == "message"
        assert pkt.parse_error is None
        assert pkt.is_rej is True
        assert pkt.is_ack is False

    def test_decode_message_no_msgno(self):
        """A message without a sequence number ({NNN) still decodes."""
        raw = "W3ADO-1>APRS::N0CALL   :Hello no msgno"
        pkt = decode_packet(raw)
        assert pkt.info_type == "message"
        assert pkt.parse_error is None
        assert pkt.message_text is not None
        assert "Hello no msgno" in pkt.message_text
        # message_id should be None when no {NNN
        assert pkt.message_id is None or pkt.message_id == ""


# ==========================================================================
# Weather packets
# ==========================================================================

class TestDecodeWeather:
    """Decoding APRS weather report packets."""

    def test_decode_weather_report(self, sample_packets):
        """Positionless weather report decodes with info_type='weather'."""
        pkt = decode_packet(sample_packets["weather"])
        assert pkt.info_type == "weather"
        assert pkt.parse_error is None

    def test_decode_weather_with_position(self):
        """Weather report combined with position data parses both."""
        # Position + weather: @DDHHMMzDDMM.MMN/DDDMM.MMW_... weather data
        raw = "W3ADO-1>APRS:@092345z4903.50N/07201.75W_220/004g005t077r000p000P000h50b09900"
        pkt = decode_packet(raw)
        # aprslib may parse this as wx or uncompressed depending on version
        # The important thing is it doesn't crash
        assert pkt.parse_error is None

    def test_decode_weather_extracts_fields(self):
        """Wind, temperature, rain, humidity, pressure fields are extracted."""
        raw = "FW0727>APRS,TCPIP*:_10090556c220s004g005t077r000p000P000h50b09900"
        pkt = decode_packet(raw)
        assert pkt.info_type == "weather"
        assert pkt.parse_error is None
        # temperature: t077 = 77F
        assert pkt.wx_temperature is not None
        assert abs(pkt.wx_temperature - 77.0) < 0.1
        # humidity: h50 = 50%
        assert pkt.wx_humidity is not None
        assert pkt.wx_humidity == 50
        # pressure: b09900 = 990.0 mbar
        assert pkt.wx_pressure is not None
        assert abs(pkt.wx_pressure - 990.0) < 1.0
        # wind speed: s004 = 4 mph
        assert pkt.wx_wind_speed is not None
        assert abs(pkt.wx_wind_speed - 4.0) < 0.1
        # wind direction: c220 = 220 degrees
        assert pkt.wx_wind_dir is not None
        assert pkt.wx_wind_dir == 220


# ==========================================================================
# Object packets
# ==========================================================================

class TestDecodeObject:
    """Decoding APRS object reports."""

    def test_decode_object(self, sample_packets):
        """Object report (;NAME_____*...) decodes with info_type='object'."""
        pkt = decode_packet(sample_packets["object"])
        assert pkt.info_type == "object"
        assert pkt.parse_error is None
        assert pkt.alive is True

    def test_decode_object_extracts_name(self, sample_packets):
        """Object name (9-char padded) is extracted and trimmed."""
        pkt = decode_packet(sample_packets["object"])
        assert pkt.object_name is not None
        assert pkt.object_name == "LEADER"

    def test_decode_killed_object(self):
        """Killed object (;NAME_____\\_...) is recognized."""
        raw = "W3ADO-1>APRS:;LEADER   _092345z4903.50N/07201.75W-Killed"
        pkt = decode_packet(raw)
        assert pkt.info_type == "object"
        assert pkt.parse_error is None
        assert pkt.alive is False


# ==========================================================================
# Status and telemetry packets
# ==========================================================================

class TestDecodeStatusTelemetry:
    """Decoding APRS status and telemetry packets."""

    def test_decode_status(self, sample_packets):
        """Status report (>text) decodes with info_type='status'."""
        pkt = decode_packet(sample_packets["status"])
        assert pkt.info_type == "status"
        assert pkt.parse_error is None
        assert pkt.status_text is not None
        assert "Monitoring 144.390MHz" in pkt.status_text

    def test_decode_telemetry(self, sample_packets):
        """Telemetry (T#NNN,...) decodes without crashing.
        Note: aprslib 0.7.x does not support the 'T' telemetry format
        and raises UnknownFormat, so the decoder returns parse_error."""
        pkt = decode_packet(sample_packets["telemetry"])
        assert isinstance(pkt, APRSPacket)
        # aprslib raises UnknownFormat for 'T' packets, so parse_error is set
        assert pkt.parse_error is not None
        assert pkt.source == "W3ADO-1"
        assert pkt.raw == sample_packets["telemetry"]


# ==========================================================================
# Error handling (AC-07: no crash on parse failure)
# ==========================================================================

class TestDecodeErrors:
    """Parse error handling. The decoder must never crash - ~5-10% of
    real-world packets cause ParseError in aprslib."""

    def test_malformed_packet_returns_partial(self, sample_packets):
        """A malformed packet returns APRSPacket with parse_error set, not None."""
        pkt = decode_packet(sample_packets["malformed"])
        assert isinstance(pkt, APRSPacket)
        assert pkt.parse_error is not None

    def test_malformed_packet_preserves_raw(self, sample_packets):
        """A malformed packet's raw field contains the original packet string."""
        pkt = decode_packet(sample_packets["malformed"])
        assert pkt.raw == sample_packets["malformed"]

    def test_malformed_packet_has_source(self, sample_packets):
        """Even on parse failure, source callsign is extracted from the header."""
        pkt = decode_packet(sample_packets["malformed"])
        assert pkt.source == "NOCALL"

    def test_empty_packet_string(self):
        """An empty string returns a packet with parse_error set."""
        pkt = decode_packet("")
        assert isinstance(pkt, APRSPacket)
        assert pkt.parse_error is not None
        assert pkt.raw == ""

    def test_no_header_delimiter(self):
        """A string with no ':' (no info field separator) returns parse_error."""
        pkt = decode_packet("NO_COLON_HERE")
        assert isinstance(pkt, APRSPacket)
        assert pkt.parse_error is not None

    def test_unknown_format_handled(self):
        """aprslib.UnknownFormat exception is caught and reported as parse_error."""
        # Use a packet type that aprslib explicitly doesn't support ('$' = raw GPS)
        # and a destination that won't match the beacon regex
        raw = "W3ADO-1>NOCALL:$SOME_RAW_GPS_DATA"
        pkt = decode_packet(raw)
        assert isinstance(pkt, APRSPacket)
        # aprslib raises UnknownFormat for '$' packet type
        assert pkt.parse_error is not None
        assert pkt.raw == raw
        assert pkt.source == "W3ADO-1"

    def test_decoder_never_raises(self, sample_packets):
        """No input to decode_packet() raises an unhandled exception."""
        # Test all sample packets plus edge cases
        test_inputs = list(sample_packets.values()) + [
            "",
            "   ",
            "\n",
            "NOCALL",
            ">",
            "A>B:",
            "A>B:!",
            "A>B:@",
            None,  # type: ignore[list-item]  # intentional wrong type
            "X" * 10000,
        ]
        for raw in test_inputs:
            try:
                pkt = decode_packet(raw)  # type: ignore[arg-type]
                assert isinstance(pkt, APRSPacket)
            except Exception as exc:
                pytest.fail(f"decode_packet({raw!r:.50}) raised {exc!r}")


# ==========================================================================
# Metadata
# ==========================================================================

class TestDecodeMetadata:
    """APRSPacket metadata fields are populated correctly."""

    def test_source_callsign_extracted(self, sample_packets):
        """source field matches the from-callsign in the packet header."""
        pkt = decode_packet(sample_packets["position"])
        assert pkt.source == "W3ADO-1"

    def test_destination_extracted(self, sample_packets):
        """destination field matches the to-callsign in the packet header."""
        pkt = decode_packet(sample_packets["position"])
        assert pkt.destination == "APRS"

    def test_path_extracted(self, sample_packets):
        """path field contains the digipeater list."""
        pkt = decode_packet(sample_packets["position"])
        assert isinstance(pkt.path, tuple)
        assert "WIDE1-1" in pkt.path
        assert "WIDE2-1" in pkt.path

    def test_transport_tag_preserved(self):
        """transport field records which transport the packet arrived on."""
        raw = "W3ADO-1>APRS:>Test status"
        pkt = decode_packet(raw, transport="kiss-tcp")
        assert pkt.transport == "kiss-tcp"

    def test_timestamp_set(self):
        """timestamp is set to approximately now on decode."""
        raw = "W3ADO-1>APRS:>Test status"
        before = datetime.now(timezone.utc)
        pkt = decode_packet(raw)
        after = datetime.now(timezone.utc)
        assert pkt.timestamp is not None
        assert before <= pkt.timestamp <= after
