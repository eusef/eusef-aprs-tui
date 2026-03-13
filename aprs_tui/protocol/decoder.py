"""APRS packet decoder -- aprslib wrapper (Issue #5).

Wraps ``aprslib.parse()`` and normalises the result dict into a frozen
:class:`APRSPacket` dataclass.  The public entry-point :func:`decode_packet`
**never raises** -- on any parse failure it returns an ``APRSPacket`` with
``parse_error`` set and as much header information as could be extracted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aprslib

from aprs_tui.protocol.types import APRSPacket


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_header(raw_line: str) -> tuple[str, str, tuple[str, ...]]:
    """Best-effort extraction of source, destination, and path from the
    raw packet header (the part before the first ``:``)."""
    source = ""
    destination = ""
    path: tuple[str, ...] = ()

    if ":" not in raw_line:
        return source, destination, path

    header = raw_line.split(":", 1)[0]

    if ">" not in header:
        return source, destination, path

    source, rest = header.split(">", 1)

    parts = rest.split(",")
    destination = parts[0] if parts else ""
    if len(parts) > 1:
        path = tuple(parts[1:])

    return source, destination, path


def _safe_float(data: dict[str, Any], key: str) -> float | None:
    """Return *key* from *data* as a float, or ``None``."""
    val = data.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(data: dict[str, Any], key: str) -> int | None:
    """Return *key* from *data* as an int, or ``None``."""
    val = data.get(key)
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Format-specific field extractors
# ---------------------------------------------------------------------------

def _meters_to_feet(val: float | None) -> float | None:
    """Convert meters to feet, returning None if input is None."""
    return val / 0.3048 if val is not None else None


def _kmh_to_knots(val: float | None) -> float | None:
    """Convert km/h to knots, returning None if input is None."""
    return val / 1.852 if val is not None else None


def _celsius_to_fahrenheit(val: float | None) -> float | None:
    """Convert Celsius to Fahrenheit, returning None if input is None."""
    return (val * 1.8) + 32 if val is not None else None


def _ms_to_mph(val: float | None) -> float | None:
    """Convert m/s to MPH, returning None if input is None."""
    return val / 0.44704 if val is not None else None


def _mm_to_inches(val: float | None) -> float | None:
    """Convert millimetres to inches, returning None if input is None."""
    return val / 25.4 if val is not None else None


def _position_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields for uncompressed / compressed position packets."""
    fields: dict[str, Any] = {"info_type": "position"}
    fields["latitude"] = _safe_float(data, "latitude")
    fields["longitude"] = _safe_float(data, "longitude")
    fields["symbol_table"] = data.get("symbol_table")
    fields["symbol_code"] = data.get("symbol")
    # aprslib returns altitude in meters; convert to feet
    fields["altitude"] = _meters_to_feet(_safe_float(data, "altitude"))
    fields["comment"] = data.get("comment")
    return fields


def _mic_e_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields for Mic-E encoded packets."""
    fields: dict[str, Any] = {"info_type": "mic-e"}
    fields["latitude"] = _safe_float(data, "latitude")
    fields["longitude"] = _safe_float(data, "longitude")
    fields["symbol_table"] = data.get("symbol_table")
    fields["symbol_code"] = data.get("symbol")
    # aprslib returns speed in km/h; convert to knots
    fields["speed"] = _kmh_to_knots(_safe_float(data, "speed"))
    fields["course"] = _safe_int(data, "course")
    fields["comment"] = data.get("comment")
    # aprslib returns altitude in meters; convert to feet
    fields["altitude"] = _meters_to_feet(_safe_float(data, "altitude"))
    return fields


def _message_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields for APRS message / ack / reject packets."""
    fields: dict[str, Any] = {"info_type": "message"}

    # aprslib uses "addresse" (sic -- missing trailing 'e')
    addressee = data.get("addresse") or data.get("addressee")
    if addressee is not None:
        addressee = addressee.strip()
    fields["addressee"] = addressee

    fields["message_text"] = data.get("message_text")
    fields["message_id"] = data.get("msgNo")

    response = data.get("response")
    fields["is_ack"] = response == "ack"
    fields["is_rej"] = response == "rej"
    return fields


def _weather_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields for weather report packets.

    aprslib returns metric values; we convert to the imperial units
    documented in APRSPacket (Fahrenheit, MPH, inches, etc.).
    Pressure (mbar) and humidity (%) need no conversion.
    """
    fields: dict[str, Any] = {"info_type": "weather"}
    wx = data.get("weather", {})
    if isinstance(wx, dict):
        # aprslib: Celsius -> Fahrenheit
        fields["wx_temperature"] = _celsius_to_fahrenheit(_safe_float(wx, "temperature"))
        fields["wx_humidity"] = _safe_int(wx, "humidity")
        # aprslib: pressure is already in mbar (raw/10)
        fields["wx_pressure"] = _safe_float(wx, "pressure")
        # aprslib: m/s -> MPH
        fields["wx_wind_speed"] = _ms_to_mph(_safe_float(wx, "wind_speed"))
        # aprslib: wind direction is degrees (no conversion)
        fields["wx_wind_dir"] = _safe_int(wx, "wind_direction")
        # aprslib: mm -> inches
        fields["wx_rain_1h"] = _mm_to_inches(_safe_float(wx, "rain_1h"))

    # Weather packets can also include position
    fields["latitude"] = _safe_float(data, "latitude")
    fields["longitude"] = _safe_float(data, "longitude")
    fields["comment"] = data.get("comment")
    return fields


def _object_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields for object report packets."""
    fields: dict[str, Any] = {"info_type": "object"}
    obj_name = data.get("object_name")
    if obj_name is not None:
        obj_name = obj_name.strip()
    fields["object_name"] = obj_name
    fields["alive"] = data.get("alive", True)
    fields["latitude"] = _safe_float(data, "latitude")
    fields["longitude"] = _safe_float(data, "longitude")
    fields["symbol_table"] = data.get("symbol_table")
    fields["symbol_code"] = data.get("symbol")
    fields["comment"] = data.get("comment")
    return fields


def _status_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields for status report packets."""
    return {
        "info_type": "status",
        "status_text": data.get("status"),
    }


def _telemetry_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields for telemetry packets."""
    fields: dict[str, Any] = {"info_type": "telemetry"}
    fields["telemetry_seq"] = data.get("seq")

    tvals = data.get("vals")
    if tvals is not None and isinstance(tvals, (list, tuple)):
        try:
            fields["telemetry_values"] = tuple(int(v) for v in tvals)
        except (ValueError, TypeError):
            pass
    return fields


# Mapping from aprslib "format" value to extractor function
_FORMAT_MAP: dict[str, Any] = {
    "uncompressed": _position_fields,
    "compressed": _position_fields,
    "mic-e": _mic_e_fields,
    "message": _message_fields,
    "object": _object_fields,
    "status": _status_fields,
    "wx": _weather_fields,
    "telemetry": _telemetry_fields,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def decode_packet(raw_line: str, transport: str = "") -> APRSPacket:
    """Decode an APRS text-format packet string into an :class:`APRSPacket`.

    Uses ``aprslib.parse()`` internally.  **Never raises** -- catches all
    exceptions and returns a packet with ``parse_error`` set.

    Args:
        raw_line: APRS packet like ``"W3ADO-1>APRS,WIDE1-1:!4903.50N/07201.75W-"``
        transport: Name of transport that received this packet.

    Returns:
        A frozen :class:`APRSPacket` instance.
    """
    now = datetime.now(timezone.utc)

    # 0. Coerce to string for safety (e.g. if caller passes None or bytes)
    if not isinstance(raw_line, str):
        try:
            raw_str = str(raw_line)
        except Exception:  # noqa: BLE001
            raw_str = ""
        return APRSPacket(
            raw=raw_str,
            transport=transport,
            timestamp=now,
            parse_error=f"raw_line is not a string (got {type(raw_line).__name__})",
        )

    # 1. Best-effort header extraction (available even on parse errors)
    source, destination, path = _extract_header(raw_line)

    # 2. Attempt aprslib parse
    try:
        data: dict[str, Any] = aprslib.parse(raw_line)
    except (aprslib.ParseError, aprslib.UnknownFormat) as exc:
        return APRSPacket(
            raw=raw_line,
            source=source,
            destination=destination,
            path=path,
            transport=transport,
            timestamp=now,
            parse_error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        return APRSPacket(
            raw=raw_line,
            source=source,
            destination=destination,
            path=path,
            transport=transport,
            timestamp=now,
            parse_error=str(exc),
        )

    # 3. Use aprslib's parsed fields for header (more reliable than regex)
    source = data.get("from", source)
    destination = data.get("to", destination)
    raw_path = data.get("path", [])
    if isinstance(raw_path, (list, tuple)):
        path = tuple(raw_path)
    else:
        path = ()

    # 4. Map format-specific fields
    fmt = data.get("format", "")
    extractor = _FORMAT_MAP.get(fmt)
    extra_fields: dict[str, Any] = {}
    if extractor is not None:
        extra_fields = extractor(data)
    else:
        extra_fields["info_type"] = "raw"

    # 5. Build and return the packet
    return APRSPacket(
        raw=raw_line,
        source=source,
        destination=destination,
        path=path,
        transport=transport,
        timestamp=now,
        parsed=dict(data),
        **extra_fields,
    )
