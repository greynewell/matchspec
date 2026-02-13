"""Configuration inheritance and merging support."""

import urllib.request
from pathlib import Path
from typing import Any

import yaml


class CircularInheritanceError(Exception):
    """Raised when circular inheritance is detected in config files."""


class ConfigInheritanceError(Exception):
    """Raised when there's an error loading or merging inherited configs."""


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two configuration dictionaries.

    The override dict takes precedence. For nested dicts, merge recursively.
    For lists and other types, the override value completely replaces the base value.

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = deep_merge(result[key], value)
        else:
            # Override value completely replaces base value
            result[key] = value

    return result


def resolve_config_path(extends_path: str, current_config_path: Path) -> str:
    """Resolve a config path that may be relative, absolute, or a URL.

    Args:
        extends_path: Path or URL specified in the extends field
        current_config_path: Path to the config file containing the extends field

    Returns:
        Resolved absolute path or URL
    """
    # Check if it's a URL
    if extends_path.startswith(("http://", "https://")):
        return extends_path

    # Convert to Path for easier handling
    path = Path(extends_path)

    # If it's absolute, return as-is
    if path.is_absolute():
        return str(path)

    # If relative, resolve relative to the current config file's directory
    resolved = (current_config_path.parent / path).resolve()
    return str(resolved)


def load_config_file(config_path: str) -> dict[str, Any]:
    """Load a config file from a path or URL.

    Args:
        config_path: File path or HTTP/HTTPS URL to load

    Returns:
        Parsed configuration dictionary

    Raises:
        ConfigInheritanceError: If the config cannot be loaded or parsed
    """
    try:
        # Check if it's a URL
        if config_path.startswith(("http://", "https://")):
            with urllib.request.urlopen(config_path, timeout=10) as response:  # noqa: S310 -- URL scheme validated above
                content = response.read().decode("utf-8")
                return yaml.safe_load(content) or {}
        else:
            # Load from file
            path = Path(config_path)
            if not path.exists():
                raise ConfigInheritanceError(f"Config file not found: {config_path}")

            with open(path) as f:
                content = f.read()
                return yaml.safe_load(content) or {}

    except yaml.YAMLError as e:
        raise ConfigInheritanceError(f"Failed to parse config file {config_path}: {e}") from e
    except Exception as e:
        raise ConfigInheritanceError(f"Failed to load config file {config_path}: {e}") from e


def load_config_with_inheritance(
    config_path: str | Path, _visited: set[str] | None = None
) -> dict[str, Any]:
    """Load a config file with support for inheritance via extends field.

    Recursively loads and merges base configurations. Detects circular dependencies.

    Args:
        config_path: Path to the configuration file
        _visited: Set of already visited config paths (for circular dependency detection)

    Returns:
        Merged configuration dictionary with inheritance applied

    Raises:
        CircularInheritanceError: If circular inheritance is detected
        ConfigInheritanceError: If there's an error loading or merging configs
    """
    if _visited is None:
        _visited = set()

    # Convert to Path and resolve to absolute path
    current_path = Path(config_path).resolve()
    current_path_str = str(current_path)

    # Check for circular dependency
    if current_path_str in _visited:
        raise CircularInheritanceError(
            f"Circular inheritance detected: {current_path_str} has already been loaded"
        )

    _visited.add(current_path_str)

    # Load the current config
    config = load_config_file(current_path_str)

    # Check if there's an extends field
    extends = config.get("extends")
    if extends is None:
        # No inheritance, return as-is (but remove extends field if present)
        config.pop("extends", None)
        return config

    # Handle multiple extends (list) or single extends (string)
    extends_list = extends if isinstance(extends, list) else [extends]

    # Load and merge base configs (in order, so later ones override earlier ones)
    merged_config: dict[str, Any] = {}
    for base_path in extends_list:
        resolved_path = resolve_config_path(base_path, current_path)

        # For URLs, we need to handle visited tracking differently
        # since we don't have a proper path
        if resolved_path.startswith(("http://", "https://")):
            # Load remote config
            if resolved_path in _visited:
                raise CircularInheritanceError(
                    f"Circular inheritance detected: {resolved_path} has already been loaded"
                )
            _visited.add(resolved_path)
            base_config = load_config_file(resolved_path)

            # If the remote config also has extends, we need to handle it
            # For simplicity, we'll only support local extends in remote configs
            if "extends" in base_config:
                raise ConfigInheritanceError(
                    f"Remote config {resolved_path} cannot use 'extends' field. "
                    "Only local configs support inheritance chains."
                )

            base_config.pop("extends", None)
        else:
            # Recursively load base config with inheritance
            base_config = load_config_with_inheritance(resolved_path, _visited)

        # Merge base config into result
        merged_config = deep_merge(merged_config, base_config)

    # Remove extends field from current config before merging
    current_config = config.copy()
    current_config.pop("extends", None)

    # Merge current config on top (current config takes precedence)
    final_config = deep_merge(merged_config, current_config)

    return final_config
