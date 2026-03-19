"""Tests for the map setup wizard step (step_map_setup)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# wizard.py lives at the project root, not inside a package
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from aprs_tui.config import AppConfig, MapConfig, StationConfig


class TestStepMapSetupCanBeImported:
    """Verify the step function can be imported and called."""

    def test_import(self) -> None:
        from wizard import step_map_setup

        assert callable(step_map_setup)


class TestStepMapSetupDisabled:
    """When user says no to 'Enable map panel?', config.map.enabled is False."""

    def test_map_disabled(self) -> None:
        from wizard import step_map_setup

        config = AppConfig(station=StationConfig(callsign="W7TEST"))
        assert config.map.enabled is True  # default

        with patch("wizard.questionary") as mock_q:
            # "Enable map panel?" -> No
            mock_q.confirm.return_value.ask.return_value = False

            result = step_map_setup(config)

        assert result.map.enabled is False


class TestStepMapSetupSkipDownload:
    """When user enables map but skips download."""

    def test_skip_download(self) -> None:
        from wizard import step_map_setup

        config = AppConfig(station=StationConfig(callsign="W7TEST"))

        with patch("wizard.questionary") as mock_q:
            # First confirm: "Enable map panel?" -> Yes
            # Second confirm: "Download offline maps now?" -> No
            mock_q.confirm.return_value.ask.side_effect = [True, False]

            result = step_map_setup(config)

        assert result.map.enabled is True


class TestStepMapSetupDownloadParams:
    """Verify the step produces correct download parameters from user input."""

    def test_center_radius_params(self, tmp_path: Path) -> None:
        """Center+radius mode with station position produces correct bbox."""
        from wizard import step_map_setup

        config = AppConfig(
            station=StationConfig(
                callsign="W7TEST", latitude=45.5, longitude=-122.6
            )
        )

        mock_dl = MagicMock()
        mock_output_path = tmp_path / "w7test-region.mbtiles"
        mock_output_path.write_bytes(b"x" * (5 * 1024 * 1024))
        mock_dl.download.return_value = mock_output_path

        mock_reg = MagicMock()

        with (
            patch("wizard.questionary") as mock_q,
            patch(
                "aprs_tui.map.downloader.TileDownloader",
                return_value=mock_dl,
            ),
            patch(
                "aprs_tui.map.registry.MapRegistry",
                return_value=mock_reg,
            ),
            patch(
                "aprs_tui.map.registry.default_maps_dir",
                return_value=tmp_path,
            ),
        ):
            # Confirms: enable=Yes, download=Yes, proceed=Yes
            mock_q.confirm.return_value.ask.side_effect = [True, True, True]

            # Selects: region_mode=center, zoom=14
            mock_q.select.return_value.ask.side_effect = ["center", 14]

            # Text: radius=200
            mock_q.text.return_value.ask.return_value = "200"

            result = step_map_setup(config)

        # Verify the downloader was called with correct parameters
        mock_dl.download.assert_called_once()
        _, kwargs = mock_dl.download.call_args
        assert kwargs["min_zoom"] == 0
        assert kwargs["max_zoom"] == 14
        # Bbox should be roughly centered on 45.5, -122.6
        assert kwargs["min_lat"] < 45.5 < kwargs["max_lat"]
        assert kwargs["min_lon"] < -122.6 < kwargs["max_lon"]
        assert result.map.enabled is True

    def test_bbox_manual_params(self, tmp_path: Path) -> None:
        """Manual bounding box mode passes correct coordinates."""
        from wizard import step_map_setup

        config = AppConfig(
            station=StationConfig(callsign="W7TEST", latitude=0.0, longitude=0.0)
        )

        mock_dl = MagicMock()
        mock_output_path = tmp_path / "w7test-region.mbtiles"
        mock_output_path.write_bytes(b"x" * (1024 * 1024))
        mock_dl.download.return_value = mock_output_path

        mock_reg = MagicMock()

        with (
            patch("wizard.questionary") as mock_q,
            patch(
                "aprs_tui.map.downloader.TileDownloader",
                return_value=mock_dl,
            ),
            patch(
                "aprs_tui.map.registry.MapRegistry",
                return_value=mock_reg,
            ),
            patch(
                "aprs_tui.map.registry.default_maps_dir",
                return_value=tmp_path,
            ),
        ):
            # Confirms: enable=Yes, download=Yes, proceed=Yes
            mock_q.confirm.return_value.ask.side_effect = [True, True, True]

            # Select: region_mode=bbox (no station pos, only choice), zoom=10
            mock_q.select.return_value.ask.side_effect = ["bbox", 10]

            # Text inputs: min_lat, max_lat, min_lon, max_lon
            mock_q.text.return_value.ask.side_effect = [
                "40.0", "41.0", "-74.5", "-73.5"
            ]

            result = step_map_setup(config)

        mock_dl.download.assert_called_once()
        _, kwargs = mock_dl.download.call_args
        assert kwargs["min_lat"] == 40.0
        assert kwargs["max_lat"] == 41.0
        assert kwargs["min_lon"] == -74.5
        assert kwargs["max_lon"] == -73.5
        assert kwargs["max_zoom"] == 10
        assert result.map.enabled is True
