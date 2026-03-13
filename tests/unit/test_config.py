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

import pytest


# ==========================================================================
# Config loading
# ==========================================================================

class TestConfigLoad:
    """Loading config.toml into AppConfig via Pydantic + tomllib."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_load_valid_config(self, tmp_config_file):
        """A complete, valid config.toml deserializes into AppConfig without error."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_load_minimal_config(self, tmp_config_file):
        """A config with only required fields loads; optional fields get defaults."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_load_all_transport_protocols(self, tmp_config_file):
        """Each protocol value (kiss-tcp, kiss-serial, kiss-bt, aprs-is) is accepted."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_load_nonexistent_file_raises(self, tmp_path):
        """Loading a path that does not exist raises FileNotFoundError (or equivalent)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_load_empty_file_raises(self, tmp_path):
        """An empty config.toml raises a validation error."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_load_malformed_toml_raises(self, tmp_path):
        """A syntactically invalid TOML file raises a clear parse error."""
        pass


# ==========================================================================
# Config validation
# ==========================================================================

class TestConfigValidation:
    """Pydantic validation rules for AppConfig fields. Covers AC-14."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_invalid_protocol_rejected(self, config_factory):
        """An unsupported protocol value (e.g., 'ftp') raises ValidationError."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_missing_required_callsign_rejected(self, config_factory):
        """station.callsign is required; omitting it raises ValidationError."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_callsign_format_validated(self, config_factory):
        """Callsigns must match amateur radio format (letters + digits, 3-7 chars)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_ssid_range_validated(self, config_factory):
        """SSID must be 0-15; values outside this range are rejected."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_port_range_validated(self, config_factory):
        """Port must be 1-65535; invalid ports are rejected."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_beacon_interval_minimum(self, config_factory):
        """Beacon interval must be >= 60 seconds (APRS minimum)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_latitude_range_validated(self, config_factory):
        """Latitude must be -90 to 90."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_longitude_range_validated(self, config_factory):
        """Longitude must be -180 to 180."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_validation_error_names_field(self, config_factory):
        """Validation errors include the invalid field name and expected type (AC-14)."""
        pass


# ==========================================================================
# Config defaults
# ==========================================================================

class TestConfigDefaults:
    """Default values for optional fields."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_default_kiss_tcp_port(self, config_factory):
        """Default port for kiss-tcp is 8001 (Direwolf convention)."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_default_aprs_is_port(self, config_factory):
        """Default APRS-IS port is 14580."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_default_beacon_disabled(self, config_factory):
        """Beacon is disabled by default."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_default_reconnect_interval(self, config_factory):
        """Default reconnect interval is 10 seconds."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_default_health_timeout(self, config_factory):
        """Default health watchdog timeout is 60 seconds (AC-12)."""
        pass


# ==========================================================================
# Config path resolution
# ==========================================================================

class TestConfigPathResolution:
    """Config file path resolution via platformdirs and CLI args."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_default_path_uses_platformdirs(self):
        """Default config path is user_config_dir('aprs-tui') / 'config.toml'."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    def test_cli_config_overrides_default(self, tmp_config_file):
        """A --config CLI argument overrides the platformdirs default path."""
        pass


# ==========================================================================
# Config write / backup
# ==========================================================================

class TestConfigWrite:
    """Config writing (used by wizard). Covers AC-13 backup behavior."""

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    def test_write_creates_toml(self, tmp_path):
        """write_config() creates a valid TOML file from AppConfig."""
        pass

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    def test_write_creates_backup(self, tmp_config_file):
        """Overwriting an existing config creates config.toml.bak (AC-13)."""
        pass

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    def test_write_atomic_rename(self, tmp_path):
        """Config is written to .tmp then renamed for atomicity."""
        pass

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    def test_write_creates_parent_dirs(self, tmp_path):
        """write_config() creates parent directories if they don't exist."""
        pass

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    def test_roundtrip_load_write_load(self, tmp_path):
        """Config survives a write -> load roundtrip with identical values."""
        pass
