"""Cross-platform compatibility utilities for Windows support.

Provides platform-aware path resolution and command helpers to ensure
mcpbr works correctly on Windows, macOS, and Linux.
"""

import os
import platform
import shutil
import tempfile
from pathlib import Path


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def get_temp_dir() -> Path:
    """Get platform-appropriate temporary directory.

    Returns:
        Path to temp directory (e.g., /tmp on Unix, %TEMP% on Windows).
    """
    return Path(tempfile.gettempdir())


def get_data_dir() -> Path:
    """Get platform-appropriate data directory for mcpbr.

    - Linux: ~/.mcpbr
    - macOS: ~/.mcpbr
    - Windows: %LOCALAPPDATA%/mcpbr or ~/.mcpbr as fallback

    Returns:
        Path to mcpbr data directory.
    """
    if is_windows():
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "mcpbr"
    return Path.home() / ".mcpbr"


def get_cache_dir() -> Path:
    """Get platform-appropriate cache directory for mcpbr.

    - Linux: ~/.cache/mcpbr
    - macOS: ~/.cache/mcpbr
    - Windows: %LOCALAPPDATA%/mcpbr/cache

    Returns:
        Path to mcpbr cache directory.
    """
    if is_windows():
        return get_data_dir() / "cache"
    return Path.home() / ".cache" / "mcpbr"


def get_config_dir() -> Path:
    """Get platform-appropriate config directory for mcpbr.

    Returns:
        Path to mcpbr configuration directory.
    """
    if is_windows():
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / "mcpbr"
    return Path.home() / ".mcpbr"


def which(command: str) -> str | None:
    """Cross-platform command lookup (like Unix `which`).

    Args:
        command: Command name to find.

    Returns:
        Full path to command, or None if not found.
    """
    return shutil.which(command)


def get_shell() -> list[str]:
    """Get the platform-appropriate shell command prefix.

    Returns:
        Shell command as a list suitable for subprocess.
    """
    if is_windows():
        # Prefer PowerShell, fall back to cmd
        pwsh = which("pwsh") or which("powershell")
        if pwsh:
            return [pwsh, "-NoProfile", "-Command"]
        return ["cmd", "/c"]
    return ["/bin/bash", "-c"]


def get_docker_socket_path() -> str:
    """Get the platform-appropriate Docker socket path.

    Returns:
        Docker socket URI.
    """
    if is_windows():
        return "npipe:////./pipe/docker_engine"
    return "unix:///var/run/docker.sock"


def normalize_path_for_docker(path: Path) -> str:
    """Convert a local path to a format Docker can use as a volume mount.

    On Windows, Docker requires paths in a specific format for bind mounts
    (e.g., /c/Users/... instead of C:\\Users\\...).

    Args:
        path: Local filesystem path.

    Returns:
        Path string suitable for Docker volume mounts.
    """
    path_str = str(path.resolve())
    if is_windows():
        # Convert C:\Users\... to /c/Users/...
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            return f"/{drive}{rest}"
    return path_str


def ensure_executable(path: Path) -> None:
    """Ensure a file has executable permissions (no-op on Windows).

    Args:
        path: Path to the file.
    """
    if not is_windows():
        path.chmod(path.stat().st_mode | 0o111)
