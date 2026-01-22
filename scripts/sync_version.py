#!/usr/bin/env python3
"""
Sync version across all project files.

This script reads the version from pyproject.toml and updates it in:
- .claude-plugin/plugin.json

Usage:
    python scripts/sync_version.py
"""

import json
import re
import sys
from pathlib import Path


def get_version_from_pyproject(pyproject_path: Path) -> str:
    """Extract version from pyproject.toml."""
    content = pyproject_path.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def update_plugin_json(plugin_json_path: Path, version: str) -> None:
    """Update version in .claude-plugin/plugin.json."""
    if not plugin_json_path.exists():
        print(f"Warning: {plugin_json_path} does not exist. Skipping.")
        return

    with open(plugin_json_path) as f:
        data = json.load(f)

    old_version = data.get("version", "unknown")
    data["version"] = version

    with open(plugin_json_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"Updated {plugin_json_path}: {old_version} -> {version}")


def main() -> None:
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"
    plugin_json_path = project_root / ".claude-plugin" / "plugin.json"

    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found", file=sys.stderr)
        sys.exit(1)

    # Get version from pyproject.toml
    version = get_version_from_pyproject(pyproject_path)
    print(f"Found version in pyproject.toml: {version}")

    # Update plugin.json
    update_plugin_json(plugin_json_path, version)

    print("\nVersion sync complete!")


if __name__ == "__main__":
    main()
