"""APRS packet encoder for position beacons and messages."""
from __future__ import annotations


def encode_position(lat: float, lon: float, symbol_table: str = "/",
                    symbol_code: str = ">", comment: str = "") -> str:
    """Encode an APRS uncompressed position string.

    Format: !DDMM.MMN/DDDMM.MMW> comment
    The symbol_table char goes between lat and lon, symbol_code after lon.

    Returns just the info field (everything after the : in a full packet).
    """
    # Convert decimal degrees to APRS DDMM.MM format
    lat_dir = "N" if lat >= 0 else "S"
    lat = abs(lat)
    lat_deg = int(lat)
    lat_min = (lat - lat_deg) * 60

    lon_dir = "E" if lon >= 0 else "W"
    lon = abs(lon)
    lon_deg = int(lon)
    lon_min = (lon - lon_deg) * 60

    pos = (
        f"!{lat_deg:02d}{lat_min:05.2f}{lat_dir}"
        f"{symbol_table}"
        f"{lon_deg:03d}{lon_min:05.2f}{lon_dir}"
        f"{symbol_code}"
    )
    if comment:
        pos += comment
    return pos


def encode_message(addressee: str, text: str, msg_id: str | None = None) -> str:
    """Encode an APRS message string.

    Format: :ADDRESSEE :text{NNN
    Addressee is padded to exactly 9 characters.
    Text max 67 characters.
    """
    addr = addressee.ljust(9)[:9]
    text = text[:67]
    msg = f":{addr}:{text}"
    if msg_id is not None:
        msg += f"{{{msg_id}"
    return msg


def encode_ack(addressee: str, msg_id: str) -> str:
    """Encode an APRS message acknowledgment.

    Format: :ADDRESSEE :ackNNN
    """
    addr = addressee.ljust(9)[:9]
    return f":{addr}:ack{msg_id}"


def encode_rej(addressee: str, msg_id: str) -> str:
    """Encode an APRS message rejection.

    Format: :ADDRESSEE :rejNNN
    """
    addr = addressee.ljust(9)[:9]
    return f":{addr}:rej{msg_id}"


def build_packet(source: str, destination: str, info: str,
                 path: list[str] | None = None) -> str:
    """Build a full APRS text packet: SOURCE>DEST,PATH:info"""
    header = f"{source}>{destination}"
    if path:
        header += "," + ",".join(path)
    return f"{header}:{info}"
