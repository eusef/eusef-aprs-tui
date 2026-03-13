"""APRS packet dataclasses (Issue #6).

Frozen (immutable) dataclasses representing AX.25 frames and decoded APRS
packets.  A single flat APRSPacket is used rather than subclasses -- the
``info_type`` field discriminates packet types.  This matches how aprslib
returns data as a dict and keeps pattern-matching simple.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AX25Frame:
    """Raw AX.25 link-layer frame."""

    source: str  # "W3ADO-1"
    destination: str  # "APRS"
    digipeaters: tuple[str, ...] = ()  # ("WIDE1-1", "WIDE2-1*")
    info: bytes = b""
    control: int = 0x03
    pid: int = 0xF0


@dataclass(frozen=True)
class APRSPacket:
    """Decoded APRS packet -- one flat type for all packet formats.

    Fields that do not apply to a given ``info_type`` are left as ``None``
    (or their default).  The ``parsed`` dict carries the full aprslib output
    for anything not explicitly modelled here.
    """

    raw: str  # Original packet string

    # --- Header / metadata ---------------------------------------------------
    source: str = ""  # Source callsign
    destination: str = ""  # Destination callsign
    path: tuple[str, ...] = ()  # Digipeater path
    info_type: str = "unknown"  # position, message, weather, object, status, telemetry, mic-e, raw
    timestamp: datetime | None = None  # When received
    transport: str = ""  # Which transport it arrived on
    parse_error: str | None = None  # Set if parsing failed

    # --- Position fields (info_type in ("position", "mic-e")) -----------------
    latitude: float | None = None
    longitude: float | None = None
    symbol_table: str | None = None  # "/" or "\"
    symbol_code: str | None = None  # e.g., ">" for car
    altitude: float | None = None  # feet
    speed: float | None = None  # knots (from Mic-E)
    course: int | None = None  # degrees (from Mic-E)
    comment: str | None = None

    # --- Message fields (info_type == "message") ------------------------------
    addressee: str | None = None  # Destination callsign for message
    message_text: str | None = None
    message_id: str | None = None  # Message number for ack tracking
    is_ack: bool = False
    is_rej: bool = False

    # --- Weather fields (info_type == "weather") ------------------------------
    wx_temperature: float | None = None  # Fahrenheit
    wx_humidity: int | None = None  # Percent
    wx_pressure: float | None = None  # Millibars
    wx_wind_speed: float | None = None  # MPH
    wx_wind_dir: int | None = None  # Degrees
    wx_rain_1h: float | None = None  # Inches

    # --- Object fields (info_type == "object") --------------------------------
    object_name: str | None = None
    alive: bool = True  # False = killed object

    # --- Status fields (info_type == "status") --------------------------------
    status_text: str | None = None

    # --- Telemetry fields (info_type == "telemetry") --------------------------
    telemetry_seq: str | None = None
    telemetry_values: tuple[int, ...] | None = None

    # --- Full aprslib parse dict ----------------------------------------------
    parsed: dict[str, Any] = field(default_factory=dict)
