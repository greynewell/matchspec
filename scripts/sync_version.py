#!/usr/bin/env python3
"""
Sync version across all project files.

This script reads the version from pyproject.toml and updates it in:
- .claude-plugin/plugin.json
- .claude-plugin/marketplace.json
- .claude-plugin/package.json
- package.json (root, if it exists)

Usage:
    python scripts/sync_version.py
"""

import json
import sys
import tomllib
from pathlib import Path


class VersionNotFoundError(Exception):
    """Raised when version cannot be found in pyproject.toml."""

    pass


def get_version_from_pyproject(pyproject_path: Path) -> str:
    """Extract version from pyproject.toml."""
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    try:
        version = data["project"]["version"]
    except KeyError as e:
        raise VersionNotFoundError(
            "Could not find version in pyproject.toml [project] section"
        ) from e

    return version


def update_plugin_json(plugin_json_path: Path, version: str) -> None:
    """Update version in .claude-plugin/plugin.json."""
    if not plugin_json_path.exists():
        print(f"Warning: {plugin_json_path} does not exist. Skipping.")
        return

    with open(plugin_json_path, encoding="utf-8") as f:
        data = json.load(f)

    old_version = data.get("version", "unknown")
    data["version"] = version

    with open(plugin_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"Updated {plugin_json_path}: {old_version} -> {version}")


def update_package_json(package_json_path: Path, version: str) -> None:
    """Update version in package.json."""
    if not package_json_path.exists():
        print(f"Info: {package_json_path} does not exist. Skipping npm package sync.")
        return

    with open(package_json_path, encoding="utf-8") as f:
        data = json.load(f)

    old_version = data.get("version", "unknown")
    data["version"] = version

    with open(package_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"Updated {package_json_path}: {old_version} -> {version}")


def update_marketplace_json(marketplace_json_path: Path, version: str) -> None:
    """Update version in .claude-plugin/marketplace.json."""
    if not marketplace_json_path.exists():
        print(f"Info: {marketplace_json_path} does not exist. Skipping marketplace.json sync.")
        return

    with open(marketplace_json_path, encoding="utf-8") as f:
        data = json.load(f)

    old_version = data.get("version", "unknown")
    data["version"] = version

    # Also update version in plugins array
    if "plugins" in data and isinstance(data["plugins"], list):
        for plugin in data["plugins"]:
            plugin["version"] = version

    with open(marketplace_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"Updated {marketplace_json_path}: {old_version} -> {version}")


def update_init_py(init_py_path: Path, version: str) -> None:
    """Update __version__ in src/mcpbr/__init__.py."""
    if not init_py_path.exists():
        print(f"Warning: {init_py_path} does not exist. Skipping.")
        return

    content = init_py_path.read_text(encoding="utf-8")
    import re

    new_content, count = re.subn(
        r'__version__\s*=\s*"[^"]*"',
        f'__version__ = "{version}"',
        content,
    )
    if count == 0:
        print(f"Warning: No __version__ found in {init_py_path}")
        return

    init_py_path.write_text(new_content, encoding="utf-8")
    print(f"Updated {init_py_path}: __version__ -> {version}")


def main() -> None:
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"
    plugin_json_path = project_root / ".claude-plugin" / "plugin.json"
    marketplace_json_path = project_root / ".claude-plugin" / "marketplace.json"
    plugin_package_json_path = project_root / ".claude-plugin" / "package.json"
    package_json_path = project_root / "package.json"
    init_py_path = project_root / "src" / "mcpbr" / "__init__.py"

    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found", file=sys.stderr)
        sys.exit(1)

    # Get version from pyproject.toml
    version = get_version_from_pyproject(pyproject_path)
    print(f"Found version in pyproject.toml: {version}")

    # Update plugin.json
    update_plugin_json(plugin_json_path, version)

    # Update marketplace.json (if it exists)
    update_marketplace_json(marketplace_json_path, version)

    # Update plugin's package.json (if it exists)
    update_package_json(plugin_package_json_path, version)

    # Update root package.json (if it exists)
    update_package_json(package_json_path, version)

    # Update __init__.py
    update_init_py(init_py_path, version)

    print("\nVersion sync complete!")


if __name__ == "__main__":
    main()
