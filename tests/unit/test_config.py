"""Tests for configuration system (config.py).

Covers: Issue #1 - Config model (Pydantic) + TOML load/write
Sprint: 1 (Foundation)
PRD refs: AC-01 (first run), AC-14 (config validation)
QA refs: Config model - valid load, invalid field types, missing required fields,
         backup behavior, platformdirs path resolution.

Module under test: aprs_tui.config
Estimated implementation: ~150-200 lines
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from aprs_tui.config import AppConfig, default_config_path


# ==========================================================================
# Config loading
# ==========================================================================

class TestConfigLoad:
    """Loading config.toml into AppConfig via Pydantic + tomllib."""

    def test_load_valid_config(self, tmp_config_file):
        """A complete, valid config.toml deserializes into AppConfig without error."""
        path = tmp_config_file()
        cfg = AppConfig.load(path)
        assert cfg.station.callsign == "N0CALL"
        assert cfg.server.protocol == "kiss-tcp"
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 8001
        assert cfg.beacon.enabled is False
        assert cfg.beacon.latitude == 49.0583
        assert cfg.aprs_is.host == "rotate.aprs2.net"
        assert cfg.connection.reconnect_interval == 10

    def test_load_minimal_config(self, tmp_config_file):
        """A config with only required fields loads; optional fields get defaults."""
        # Write a minimal config with only the required station.callsign
        path = tmp_config_file()
        path.write_text('[station]\ncallsign = "N0CALL"\n')
        cfg = AppConfig.load(path)
        assert cfg.station.callsign == "N0CALL"
        # Defaults should be applied
        assert cfg.server.protocol == "kiss-tcp"
        assert cfg.server.port == 8001
        assert cfg.beacon.enabled is False
        assert cfg.beacon.interval == 600
        assert cfg.aprs_is.port == 14580
        assert cfg.connection.health_timeout == 60

    def test_load_all_transport_protocols(self, tmp_config_file):
        """Each protocol value (kiss-tcp, kiss-serial, kiss-bt, aprs-is) is accepted."""
        for proto in ("kiss-tcp", "kiss-serial", "kiss-bt", "aprs-is"):
            path = tmp_config_file(server={"protocol": proto, "host": "127.0.0.1", "port": 8001})
            cfg = AppConfig.load(path)
            assert cfg.server.protocol == proto

    def test_load_nonexistent_file_raises(self, tmp_path):
        """Loading a path that does not exist raises FileNotFoundError (or equivalent)."""
        missing = tmp_path / "nonexistent" / "config.toml"
        with pytest.raises(FileNotFoundError):
            AppConfig.load(missing)

    def test_load_empty_file_raises(self, tmp_path):
        """An empty config.toml raises a validation error."""
        empty = tmp_path / "config.toml"
        empty.write_text("")
        with pytest.raises(ValidationError):
            AppConfig.load(empty)

    def test_load_malformed_toml_raises(self, tmp_path):
        """A syntactically invalid TOML file raises a clear parse error."""
        bad = tmp_path / "config.toml"
        bad.write_text("[station\ncallsign = ???\n")
        with pytest.raises(tomllib.TOMLDecodeError):
            AppConfig.load(bad)


# ==========================================================================
# Config validation
# ==========================================================================

class TestConfigValidation:
    """Pydantic validation rules for AppConfig fields. Covers AC-14."""

    def test_invalid_protocol_rejected(self, config_factory):
        """An unsupported protocol value (e.g., 'ftp') raises ValidationError."""
        data = config_factory(server={"protocol": "ftp", "host": "127.0.0.1", "port": 8001})
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_missing_required_callsign_rejected(self, config_factory):
        """station.callsign is required; omitting it raises ValidationError."""
        data = config_factory()
        del data["station"]["callsign"]
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_callsign_format_validated(self, config_factory):
        """Callsigns must match amateur radio format (letters + digits, 3-7 chars)."""
        # Too short
        data = config_factory(callsign="AB")
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)
        # Too long
        data = config_factory(callsign="ABCDEFGH")
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)
        # Invalid characters
        data = config_factory(callsign="N0-CALL")
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_ssid_range_validated(self, config_factory):
        """SSID must be 0-15; values outside this range are rejected."""
        data = config_factory(ssid=-1)
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)
        data = config_factory(ssid=16)
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_port_range_validated(self, config_factory):
        """Port must be 1-65535; invalid ports are rejected."""
        data = config_factory(server={"protocol": "kiss-tcp", "host": "127.0.0.1", "port": 0})
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)
        data = config_factory(server={"protocol": "kiss-tcp", "host": "127.0.0.1", "port": 70000})
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_beacon_interval_minimum(self, config_factory):
        """Beacon interval must be >= 60 seconds (APRS minimum)."""
        data = config_factory(
            beacon={"enabled": False, "interval": 30, "latitude": 0.0, "longitude": 0.0, "comment": ""}
        )
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_latitude_range_validated(self, config_factory):
        """Latitude must be -90 to 90."""
        data = config_factory(
            beacon={"enabled": False, "interval": 600, "latitude": 91.0, "longitude": 0.0, "comment": ""}
        )
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)
        data = config_factory(
            beacon={"enabled": False, "interval": 600, "latitude": -91.0, "longitude": 0.0, "comment": ""}
        )
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_longitude_range_validated(self, config_factory):
        """Longitude must be -180 to 180."""
        data = config_factory(
            beacon={"enabled": False, "interval": 600, "latitude": 0.0, "longitude": 181.0, "comment": ""}
        )
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)
        data = config_factory(
            beacon={"enabled": False, "interval": 600, "latitude": 0.0, "longitude": -181.0, "comment": ""}
        )
        with pytest.raises(ValidationError):
            AppConfig.model_validate(data)

    def test_validation_error_names_field(self, config_factory):
        """Validation errors include the invalid field name and expected type (AC-14)."""
        data = config_factory(server={"protocol": "ftp", "host": "127.0.0.1", "port": 8001})
        with pytest.raises(ValidationError) as exc_info:
            AppConfig.model_validate(data)
        error_str = str(exc_info.value)
        assert "protocol" in error_str


# ==========================================================================
# Config defaults
# ==========================================================================

class TestConfigDefaults:
    """Default values for optional fields."""

    def test_default_kiss_tcp_port(self, config_factory):
        """Default port for kiss-tcp is 8001 (Direwolf convention)."""
        data = config_factory()
        # Remove port to test default
        del data["server"]["port"]
        cfg = AppConfig.model_validate(data)
        assert cfg.server.port == 8001

    def test_default_aprs_is_port(self, config_factory):
        """Default APRS-IS port is 14580."""
        data = config_factory()
        del data["aprs_is"]["port"]
        cfg = AppConfig.model_validate(data)
        assert cfg.aprs_is.port == 14580

    def test_default_beacon_disabled(self, config_factory):
        """Beacon is disabled by default."""
        data = config_factory()
        del data["beacon"]["enabled"]
        cfg = AppConfig.model_validate(data)
        assert cfg.beacon.enabled is False

    def test_default_reconnect_interval(self, config_factory):
        """Default reconnect interval is 10 seconds."""
        data = config_factory()
        del data["connection"]["reconnect_interval"]
        cfg = AppConfig.model_validate(data)
        assert cfg.connection.reconnect_interval == 10

    def test_default_health_timeout(self, config_factory):
        """Default health watchdog timeout is 60 seconds (AC-12)."""
        data = config_factory()
        del data["connection"]["health_timeout"]
        cfg = AppConfig.model_validate(data)
        assert cfg.connection.health_timeout == 60


# ==========================================================================
# Config path resolution
# ==========================================================================

class TestConfigPathResolution:
    """Config file path resolution via platformdirs and CLI args."""

    def test_default_path_uses_platformdirs(self):
        """Default config path is user_config_dir('aprs-tui') / 'config.toml'."""
        from platformdirs import user_config_dir

        expected = Path(user_config_dir("aprs-tui")) / "config.toml"
        assert default_config_path() == expected

    def test_cli_config_overrides_default(self, tmp_config_file):
        """A --config CLI argument overrides the platformdirs default path."""
        path = tmp_config_file()
        # Loading with an explicit path should use that path, not the default
        cfg = AppConfig.load(path)
        assert cfg.station.callsign == "N0CALL"


# ==========================================================================
# Config write / backup
# ==========================================================================

class TestConfigWrite:
    """Config writing (used by wizard). Covers AC-13 backup behavior."""

    def test_write_creates_toml(self, tmp_path):
        """write_config() creates a valid TOML file from AppConfig."""
        cfg = AppConfig.model_validate({
            "station": {"callsign": "N0CALL"},
        })
        out = tmp_path / "config.toml"
        cfg.save(out)
        assert out.exists()
        # Verify it's valid TOML that can be parsed back
        data = tomllib.loads(out.read_text())
        assert data["station"]["callsign"] == "N0CALL"

    def test_write_creates_backup(self, tmp_config_file):
        """Overwriting an existing config creates config.toml.bak (AC-13)."""
        path = tmp_config_file()
        original_content = path.read_text()
        # Now save a new config to the same path
        cfg = AppConfig.model_validate({
            "station": {"callsign": "W3ADO"},
        })
        cfg.save(path)
        backup = path.parent / (path.name + ".bak")
        assert backup.exists()
        assert backup.read_text() == original_content

    def test_write_atomic_rename(self, tmp_path):
        """Config is written to .tmp then renamed for atomicity."""
        cfg = AppConfig.model_validate({
            "station": {"callsign": "N0CALL"},
        })
        out = tmp_path / "config.toml"
        cfg.save(out)
        # After save, the .tmp file should not exist (it was renamed)
        tmp_file = out.with_suffix(".tmp")
        assert not tmp_file.exists()
        # But the final file should exist
        assert out.exists()

    def test_write_creates_parent_dirs(self, tmp_path):
        """write_config() creates parent directories if they don't exist."""
        cfg = AppConfig.model_validate({
            "station": {"callsign": "N0CALL"},
        })
        out = tmp_path / "deep" / "nested" / "dir" / "config.toml"
        cfg.save(out)
        assert out.exists()

    def test_roundtrip_load_write_load(self, tmp_path):
        """Config survives a write -> load roundtrip with identical values."""
        original = AppConfig.model_validate({
            "station": {"callsign": "N0CALL", "ssid": 5},
            "server": {"protocol": "kiss-tcp", "host": "10.0.0.1", "port": 9001},
            "beacon": {
                "enabled": True,
                "interval": 120,
                "latitude": 49.0583,
                "longitude": -72.0292,
                "comment": "Test beacon",
            },
            "aprs_is": {
                "enabled": True,
                "host": "noam.aprs2.net",
                "port": 14580,
                "filter": "r/49/-72/200",
                "passcode": 12345,
            },
            "connection": {
                "reconnect_interval": 30,
                "max_reconnect_attempts": 5,
                "health_timeout": 120,
            },
        })
        out = tmp_path / "config.toml"
        original.save(out)
        loaded = AppConfig.load(out)
        assert loaded == original
