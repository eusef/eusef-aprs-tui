"""Station tracking - maintains a table of heard stations with distance/bearing."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from aprs_tui.protocol.types import APRSPacket


@dataclass
class StationRecord:
    callsign: str
    last_heard: float = 0.0  # time.monotonic()
    latitude: float | None = None
    longitude: float | None = None
    symbol_table: str | None = None
    symbol_code: str | None = None
    comment: str | None = None
    packet_count: int = 0
    last_info_type: str = ""
    distance_km: float | None = None
    bearing: float | None = None


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two points."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calc_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial bearing in degrees from point 1 to point 2."""
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = math.radians(lat2), math.radians(lon2)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(
        lat2
    ) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


class StationTracker:
    def __init__(
        self, own_lat: float | None = None, own_lon: float | None = None
    ) -> None:
        self._stations: dict[str, StationRecord] = {}
        self._own_lat = own_lat
        self._own_lon = own_lon

    def update(self, pkt: APRSPacket) -> None:
        """Update station table from an incoming packet."""
        if not pkt.source:
            return
        callsign = pkt.source.upper()

        if callsign not in self._stations:
            self._stations[callsign] = StationRecord(callsign=callsign)

        stn = self._stations[callsign]
        stn.last_heard = time.monotonic()
        stn.packet_count += 1
        stn.last_info_type = pkt.info_type

        # Update position from position or mic-e packets
        if (
            pkt.info_type in ("position", "mic-e")
            and pkt.latitude is not None
            and pkt.longitude is not None
        ):
            stn.latitude = pkt.latitude
            stn.longitude = pkt.longitude
            stn.symbol_table = pkt.symbol_table
            stn.symbol_code = pkt.symbol_code
            stn.comment = pkt.comment
            self._update_distance(stn)

    def _update_distance(self, stn: StationRecord) -> None:
        if (
            self._own_lat is not None
            and self._own_lon is not None
            and stn.latitude is not None
            and stn.longitude is not None
        ):
            stn.distance_km = haversine(
                self._own_lat, self._own_lon, stn.latitude, stn.longitude
            )
            stn.bearing = calc_bearing(
                self._own_lat, self._own_lon, stn.latitude, stn.longitude
            )

    def get_stations(self, sort_by: str = "last_heard") -> list[StationRecord]:
        """Return all stations sorted by the given field."""
        stations = list(self._stations.values())
        if sort_by == "last_heard":
            stations.sort(key=lambda s: s.last_heard, reverse=True)
        elif sort_by == "distance":
            stations.sort(
                key=lambda s: s.distance_km
                if s.distance_km is not None
                else float("inf")
            )
        elif sort_by == "callsign":
            stations.sort(key=lambda s: s.callsign)
        return stations

    def get_station(self, callsign: str) -> StationRecord | None:
        return self._stations.get(callsign.upper())

    @property
    def count(self) -> int:
        return len(self._stations)
