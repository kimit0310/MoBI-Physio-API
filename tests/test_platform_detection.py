"""Tests for platform detection functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest

from mobi_physio_api.platform_detection import (
    get_plux_sdk_path,
    setup_plux_import_path,
)


class TestPlatformDetection:
    """Test platform detection functions."""

    def test_get_plux_sdk_path_macos_arm(self) -> None:
        """Test macOS ARM path detection."""
        with (
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="arm64"),
        ):
            result = get_plux_sdk_path()
            assert result.startswith("PLUX-API-Python3/M1_")

    def test_get_plux_sdk_path_macos_intel(self) -> None:
        """Test macOS Intel path detection."""
        with (
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="x86_64"),
        ):
            result = get_plux_sdk_path()
            assert "Intel" in result

    def test_get_plux_sdk_path_linux(self) -> None:
        """Test Linux path detection."""
        with patch("platform.system", return_value="Linux"):
            result = get_plux_sdk_path()
            assert result == "PLUX-API-Python3/Linux64"

    def test_get_plux_sdk_path_windows(self) -> None:
        """Test Windows path detection."""
        with patch("platform.system", return_value="Windows"):
            result = get_plux_sdk_path()
            assert result.startswith("PLUX-API-Python3/Win")

    def test_get_plux_sdk_path_unsupported(self) -> None:
        """Test unsupported platform detection."""
        with (
            patch("platform.system", return_value="FreeBSD"),
            pytest.raises(RuntimeError, match="Unsupported platform"),
        ):
            get_plux_sdk_path()

    def test_setup_plux_import_path(self) -> None:
        """Test PLUX import path setup."""
        base_path = Path("/test/path")

        with (
            patch("sys.path") as mock_path,
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = setup_plux_import_path(base_path)

            # Should return a path string
            assert isinstance(result, str)
            # Should add the path to sys.path
            mock_path.insert.assert_called_once()

    def test_setup_plux_import_path_current_dir(self) -> None:
        """Test PLUX import path setup with current directory."""
        with patch("sys.path") as mock_path:
            result = setup_plux_import_path()

            # Should return a path string
            assert isinstance(result, str)
            # Should add the path to sys.path
            mock_path.insert.assert_called_once()
