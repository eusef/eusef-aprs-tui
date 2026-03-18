"""Configuration system for APRS TUI.

Provides Pydantic v2 models for structured config and TOML load/save via
tomllib (read) and tomli-w (write). Supports platformdirs-based default
config path, atomic writes, and backup of existing config files.

Issue: #1 - Config model (Pydantic) + TOML load/write
Sprint: 1 (Foundation)
"""
from __future__ import annotations

import re
import shutil
import tomllib
from pathlib import Path
from typing import Annotated, Literal, Self

import tomli_w
from platformdirs import user_config_dir
from pydantic import BaseModel, Field, field_validator


def default_config_path() -> Path:
    """Return the platform-appropriate default config file path.

    Uses platformdirs to resolve ``user_config_dir('aprs-tui') / 'config.toml'``.
    """
    return Path(user_config_dir("aprs-tui")) / "config.toml"


class StationConfig(BaseModel):
    """Station identity, position, and APRS symbol settings."""

    callsign: str
    ssid: Annotated[int, Field(ge=0, le=15)] = 0
    latitude: Annotated[float, Field(ge=-90, le=90)] = 0.0
    longitude: Annotated[float, Field(ge=-180, le=180)] = 0.0
    symbol_table: str = "/"
    symbol_code: str = "-"

    @field_validator("callsign")
    @classmethod
    def _validate_callsign(cls, v: str) -> str:
        """Validate amateur radio callsign format (3-7 alphanumeric chars)."""
        if not re.fullmatch(r"[A-Za-z0-9]{3,7}", v):
            raise ValueError(
                f"Invalid callsign '{v}': must be 3-7 alphanumeric characters"
            )
        return v.upper()


class ServerConfig(BaseModel):
    """Transport server connection settings."""

    protocol: Literal[
        "kiss-tcp", "kiss-serial", "kiss-bt", "kiss-ble", "kiss-ble-hybrid", "aprs-is"
    ] = "kiss-tcp"
    host: str = "127.0.0.1"
    port: Annotated[int, Field(ge=0, le=65535)] = 8001
    serial_device: str = ""  # Classic BT serial path for hybrid BLE+Serial TX


class BeaconConfig(BaseModel):
    """Periodic position beacon settings."""

    enabled: bool = False
    interval: Annotated[int, Field(ge=60)] = 600
    latitude: Annotated[float, Field(ge=-90, le=90)] = 0.0
    longitude: Annotated[float, Field(ge=-180, le=180)] = 0.0
    comment: str = ""


class APRSISConfig(BaseModel):
    """APRS-IS internet gateway settings."""

    enabled: bool = False
    host: str = "rotate.aprs2.net"
    port: Annotated[int, Field(ge=1, le=65535)] = 14580
    filter: str = ""
    passcode: int = -1


class ConnectionConfig(BaseModel):
    """Connection management settings."""

    reconnect_interval: int = 10
    max_reconnect_attempts: int = 0  # 0 = infinite
    health_timeout: int = 60


class AppConfig(BaseModel):
    """Top-level application configuration.

    Aggregates all sub-configs and provides classmethods for TOML I/O.
    """

    station: StationConfig
    server: ServerConfig = ServerConfig()
    beacon: BeaconConfig = BeaconConfig()
    aprs_is: APRSISConfig = APRSISConfig()
    connection: ConnectionConfig = ConnectionConfig()

    @classmethod
    def load(cls, path: Path | None = None) -> Self:
        """Load and validate config from a TOML file.

        Parameters
        ----------
        path:
            Path to the TOML config file. If *None*, uses
            :func:`default_config_path`.

        Raises
        ------
        FileNotFoundError
            If the config file does not exist.
        tomllib.TOMLDecodeError
            If the file is not valid TOML.
        pydantic.ValidationError
            If the parsed data fails validation.
        """
        if path is None:
            path = default_config_path()

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        raw = path.read_bytes()
        data = tomllib.loads(raw.decode())
        return cls.model_validate(data)

    def save(self, path: Path | None = None) -> None:
        """Write this config to a TOML file atomically.

        If *path* already exists, a backup is created at ``<path>.bak``
        before overwriting. The write is performed atomically: data is
        first written to a ``.tmp`` sibling, then renamed into place.

        Parameters
        ----------
        path:
            Destination file path. If *None*, uses
            :func:`default_config_path`.
        """
        if path is None:
            path = default_config_path()

        # Ensure parent directories exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Back up existing config
        if path.exists():
            backup = path.parent / (path.name + ".bak")
            shutil.copy2(path, backup)

        # Serialize to dict, converting for TOML compatibility
        data = self.model_dump()

        # Atomic write: write to .tmp then rename
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_bytes(tomli_w.dumps(data).encode())
        tmp_path.rename(path)
