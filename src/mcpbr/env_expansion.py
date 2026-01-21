"""Environment variable expansion for configuration files."""

import os
import re
from pathlib import Path
from typing import Any


def load_dotenv_file(dotenv_path: Path | None = None) -> None:
    """Load environment variables from a .env file.

    Args:
        dotenv_path: Path to .env file. If None, looks for .env in current directory.
    """
    if dotenv_path is None:
        dotenv_path = Path(".env")

    if not dotenv_path.exists():
        return

    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE or KEY='VALUE' or KEY="VALUE"
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]

                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value


def expand_env_vars(value: Any, required_vars: set[str] | None = None) -> Any:
    """Recursively expand environment variables in config values.

    Supports two syntaxes:
    - ${VAR}: Simple substitution, empty string if not found
    - ${VAR:-default}: Substitution with default value

    Args:
        value: Config value to expand (can be str, dict, list, or other)
        required_vars: Set to track required environment variables (modified in place)

    Returns:
        Value with environment variables expanded.

    Raises:
        ValueError: If a required environment variable is missing (no default provided).
    """
    if required_vars is None:
        required_vars = set()

    if isinstance(value, str):
        return _expand_string(value, required_vars)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v, required_vars) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item, required_vars) for item in value]
    else:
        return value


def _expand_string(text: str, required_vars: set[str]) -> str:
    """Expand environment variables in a string.

    Supports:
    - ${VAR}: Required variable (error if missing)
    - ${VAR:-default}: Optional variable with default value

    Args:
        text: String to expand
        required_vars: Set to track required environment variables

    Returns:
        Expanded string

    Raises:
        ValueError: If a required environment variable is missing.
    """
    # Pattern: ${VAR} or ${VAR:-default}
    pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}"

    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        default_value = match.group(2)  # None if not provided

        env_value = os.environ.get(var_name)

        if env_value is not None:
            return env_value
        elif default_value is not None:
            # Default value provided, use it
            return default_value
        else:
            # Required variable missing
            required_vars.add(var_name)
            raise ValueError(
                f"Required environment variable '{var_name}' is not set. "
                f"Either set it in your environment or provide a default value "
                f"using ${{{{VAR:-default}}}} syntax."
            )

    return re.sub(pattern, replace, text)


def validate_config_security(config_dict: dict[str, Any]) -> list[str]:
    """Check configuration for potential security issues.

    Args:
        config_dict: Raw configuration dictionary

    Returns:
        List of security warnings
    """
    warnings = []

    def check_sensitive_data(value: Any, path: str = "", key: str = "") -> None:
        """Recursively check for sensitive data patterns."""
        if isinstance(value, str):
            # Skip if value is an environment variable reference
            if value.startswith("${"):
                return

            # Check if the key name suggests sensitive data
            key_lower = key.lower()

            # Check for API keys (more specific patterns first)
            if any(keyword in key_lower for keyword in ["api_key", "api-key", "apikey"]):
                if len(value) > 5:  # Avoid warning on short values
                    warnings.append(
                        f"Possible API key hardcoded at '{path}'. "
                        f"Consider using environment variables: ${{API_KEY}}"
                    )
            # Check for generic "key" last to avoid false positives
            elif key_lower.endswith("key") and not key_lower.endswith("_key"):
                if len(value) > 10:  # Higher threshold for generic "key"
                    warnings.append(
                        f"Possible API key hardcoded at '{path}'. "
                        f"Consider using environment variables: ${{API_KEY}}"
                    )

            # Check for tokens in key name
            if "token" in key_lower and len(value) > 10:
                warnings.append(
                    f"Possible token hardcoded at '{path}'. Consider using environment variables."
                )

            # Check for passwords in key name
            if "password" in key_lower:
                warnings.append(
                    f"Password appears to be hardcoded at '{path}'. "
                    f"Consider using environment variables: ${{DB_PASSWORD}}"
                )

        elif isinstance(value, dict):
            for k, v in value.items():
                new_path = f"{path}.{k}" if path else k
                check_sensitive_data(v, new_path, k)

        elif isinstance(value, list):
            for i, item in enumerate(value):
                new_path = f"{path}[{i}]"
                check_sensitive_data(item, new_path, "")

    check_sensitive_data(config_dict)
    return warnings
