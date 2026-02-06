"""Tests for cross-platform compatibility utilities."""

import platform
from pathlib import Path
from unittest.mock import patch

from mcpbr.compat import (
    ensure_executable,
    get_cache_dir,
    get_config_dir,
    get_data_dir,
    get_docker_socket_path,
    get_shell,
    get_temp_dir,
    is_linux,
    is_macos,
    is_windows,
    normalize_path_for_docker,
    which,
)


class TestPlatformDetection:
    """Tests for platform detection functions."""

    def test_is_windows(self) -> None:
        """Test Windows detection."""
        with patch("mcpbr.compat.platform.system", return_value="Windows"):
            assert is_windows() is True
        with patch("mcpbr.compat.platform.system", return_value="Linux"):
            assert is_windows() is False

    def test_is_macos(self) -> None:
        """Test macOS detection."""
        with patch("mcpbr.compat.platform.system", return_value="Darwin"):
            assert is_macos() is True
        with patch("mcpbr.compat.platform.system", return_value="Linux"):
            assert is_macos() is False

    def test_is_linux(self) -> None:
        """Test Linux detection."""
        with patch("mcpbr.compat.platform.system", return_value="Linux"):
            assert is_linux() is True
        with patch("mcpbr.compat.platform.system", return_value="Windows"):
            assert is_linux() is False

    def test_current_platform_detection(self) -> None:
        """Test that exactly one platform is detected."""
        current = platform.system()
        assert is_windows() == (current == "Windows")
        assert is_macos() == (current == "Darwin")
        assert is_linux() == (current == "Linux")


class TestDirectories:
    """Tests for directory path functions."""

    def test_get_temp_dir_returns_path(self) -> None:
        """Test temp dir returns a Path object."""
        result = get_temp_dir()
        assert isinstance(result, Path)

    def test_get_data_dir_unix(self) -> None:
        """Test data dir on Unix systems."""
        with patch("mcpbr.compat.is_windows", return_value=False):
            result = get_data_dir()
            assert str(result).endswith(".mcpbr")

    def test_get_data_dir_windows(self) -> None:
        """Test data dir on Windows with LOCALAPPDATA."""
        with (
            patch("mcpbr.compat.is_windows", return_value=True),
            patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}),
        ):
            result = get_data_dir()
            assert "mcpbr" in str(result)
            assert "AppData" in str(result)

    def test_get_data_dir_windows_fallback(self) -> None:
        """Test data dir on Windows without LOCALAPPDATA falls back to home."""
        with (
            patch("mcpbr.compat.is_windows", return_value=True),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = get_data_dir()
            assert str(result).endswith(".mcpbr")

    def test_get_cache_dir_unix(self) -> None:
        """Test cache dir on Unix systems."""
        with patch("mcpbr.compat.is_windows", return_value=False):
            result = get_cache_dir()
            assert ".cache" in str(result)
            assert "mcpbr" in str(result)

    def test_get_cache_dir_windows(self) -> None:
        """Test cache dir on Windows."""
        with (
            patch("mcpbr.compat.is_windows", return_value=True),
            patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}),
        ):
            result = get_cache_dir()
            assert "cache" in str(result)

    def test_get_config_dir_unix(self) -> None:
        """Test config dir on Unix."""
        with patch("mcpbr.compat.is_windows", return_value=False):
            result = get_config_dir()
            assert str(result).endswith(".mcpbr")

    def test_get_config_dir_windows(self) -> None:
        """Test config dir on Windows with APPDATA."""
        with (
            patch("mcpbr.compat.is_windows", return_value=True),
            patch.dict("os.environ", {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}),
        ):
            result = get_config_dir()
            assert "mcpbr" in str(result)


class TestCommandHelpers:
    """Tests for command execution helpers."""

    def test_which_finds_python(self) -> None:
        """Test which can find python."""
        result = which("python3") or which("python")
        assert result is not None

    def test_which_returns_none_for_missing(self) -> None:
        """Test which returns None for nonexistent commands."""
        result = which("definitely_not_a_real_command_12345")
        assert result is None

    def test_get_shell_unix(self) -> None:
        """Test Unix shell command."""
        with patch("mcpbr.compat.is_windows", return_value=False):
            result = get_shell()
            assert result == ["/bin/bash", "-c"]

    def test_get_shell_windows_powershell(self) -> None:
        """Test Windows shell command with PowerShell."""
        with (
            patch("mcpbr.compat.is_windows", return_value=True),
            patch(
                "mcpbr.compat.which", side_effect=lambda c: "C:\\pwsh.exe" if c == "pwsh" else None
            ),
        ):
            result = get_shell()
            assert "pwsh" in result[0] or "powershell" in result[0].lower()

    def test_get_shell_windows_cmd_fallback(self) -> None:
        """Test Windows falls back to cmd if no PowerShell."""
        with (
            patch("mcpbr.compat.is_windows", return_value=True),
            patch("mcpbr.compat.which", return_value=None),
        ):
            result = get_shell()
            assert result == ["cmd", "/c"]


class TestDockerHelpers:
    """Tests for Docker-related helpers."""

    def test_docker_socket_unix(self) -> None:
        """Test Unix Docker socket path."""
        with patch("mcpbr.compat.is_windows", return_value=False):
            result = get_docker_socket_path()
            assert result.startswith("unix://")

    def test_docker_socket_windows(self) -> None:
        """Test Windows Docker named pipe."""
        with patch("mcpbr.compat.is_windows", return_value=True):
            result = get_docker_socket_path()
            assert "npipe" in result

    def test_normalize_path_unix(self, tmp_path: Path) -> None:
        """Test path normalization on Unix (no-op)."""
        with patch("mcpbr.compat.is_windows", return_value=False):
            result = normalize_path_for_docker(tmp_path)
            assert result == str(tmp_path)

    def test_normalize_path_windows(self) -> None:
        """Test path normalization on Windows."""
        with (
            patch("mcpbr.compat.is_windows", return_value=True),
            patch.object(Path, "resolve", return_value=Path("C:\\Users\\test\\project")),
        ):
            result = normalize_path_for_docker(Path("C:\\Users\\test\\project"))
            assert result == "/c/Users/test/project"

    def test_ensure_executable_unix(self, tmp_path: Path) -> None:
        """Test ensure_executable sets execute bits on Unix."""
        test_file = tmp_path / "script.sh"
        test_file.write_text("#!/bin/bash\necho hello")

        with patch("mcpbr.compat.is_windows", return_value=False):
            ensure_executable(test_file)
            mode = test_file.stat().st_mode
            assert mode & 0o111  # Has some execute bit

    def test_ensure_executable_windows_noop(self, tmp_path: Path) -> None:
        """Test ensure_executable is a no-op on Windows."""
        test_file = tmp_path / "script.bat"
        test_file.write_text("echo hello")
        original_mode = test_file.stat().st_mode

        with patch("mcpbr.compat.is_windows", return_value=True):
            ensure_executable(test_file)
            assert test_file.stat().st_mode == original_mode
