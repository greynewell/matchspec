"""Configuration validation with detailed error messages and suggestions."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .config import VALID_BENCHMARKS, VALID_HARNESSES, VALID_PROVIDERS, HarnessConfig


@dataclass
class ConfigValidationError:
    """A validation error with context and suggestions."""

    field: str
    error: str
    line_number: int | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    valid: bool
    errors: list[ConfigValidationError]
    warnings: list[ConfigValidationError]

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0


class ConfigValidator:
    """Validates YAML/TOML configuration files for mcpbr."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self.errors: list[ConfigValidationError] = []
        self.warnings: list[ConfigValidationError] = []

    def validate_file(self, config_path: str | Path) -> ValidationResult:
        """Validate a configuration file.

        Args:
            config_path: Path to the configuration file.

        Returns:
            ValidationResult with errors and warnings.
        """
        self.errors = []
        self.warnings = []

        path = Path(config_path)

        # Check file exists
        if not path.exists():
            self.errors.append(
                ConfigValidationError(
                    field="file",
                    error=f"Configuration file not found: {path}",
                    suggestion="Check the file path and ensure the file exists.",
                )
            )
            return ValidationResult(valid=False, errors=self.errors, warnings=self.warnings)

        # Check file extension
        if path.suffix not in [".yaml", ".yml", ".toml"]:
            self.warnings.append(
                ConfigValidationError(
                    field="file",
                    error=f"Unexpected file extension: {path.suffix}",
                    suggestion="Configuration files should use .yaml, .yml, or .toml extension.",
                )
            )

        # Read and parse file
        try:
            with open(path) as f:
                content = f.read()
                raw_config = self._parse_config(content, path.suffix)
        except yaml.YAMLError as e:
            error_msg = str(e)
            line_num = None
            if hasattr(e, "problem_mark"):
                mark = e.problem_mark
                line_num = mark.line + 1 if mark else None
                error_msg = f"YAML syntax error at line {line_num}: {getattr(e, 'problem', str(e))}"

            self.errors.append(
                ConfigValidationError(
                    field="syntax",
                    error=error_msg,
                    line_number=line_num,
                    suggestion="Check YAML syntax. Common issues: incorrect indentation, missing colons, unquoted special characters.",
                )
            )
            return ValidationResult(valid=False, errors=self.errors, warnings=self.warnings)
        except Exception as e:
            self.errors.append(
                ConfigValidationError(
                    field="parsing",
                    error=f"Failed to parse configuration file: {e}",
                    suggestion="Ensure the file is valid YAML or TOML format.",
                )
            )
            return ValidationResult(valid=False, errors=self.errors, warnings=self.warnings)

        # Validate structure and fields
        self._validate_structure(raw_config)

        # Validate API key format (if Anthropic provider)
        if raw_config.get("provider", "anthropic") == "anthropic":
            self._validate_api_key()

        # Try to create HarnessConfig to trigger Pydantic validation
        # Skip this if config uses extends, since it won't be complete until merged
        if not self.has_errors and "extends" not in raw_config:
            self._validate_with_pydantic(raw_config)

        return ValidationResult(
            valid=not self.has_errors, errors=self.errors, warnings=self.warnings
        )

    def _parse_config(self, content: str, suffix: str) -> dict[str, Any]:
        """Parse configuration file content.

        Args:
            content: File content.
            suffix: File extension.

        Returns:
            Parsed configuration dictionary.
        """
        if suffix in [".yaml", ".yml"]:
            return yaml.safe_load(content) or {}
        elif suffix == ".toml":
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore
                except ImportError as e:
                    raise ImportError(
                        "TOML support requires tomli package. Install with: pip install tomli"
                    ) from e
            return tomllib.loads(content)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _validate_structure(self, config: dict[str, Any]) -> None:
        """Validate the configuration structure.

        Args:
            config: Parsed configuration dictionary.
        """
        # Validate extends field if present (optional field)
        extends = config.get("extends")
        if extends is not None:
            if not isinstance(extends, (str, list)):
                self.errors.append(
                    ConfigValidationError(
                        field="extends",
                        error="'extends' must be a string (single path/URL) or list (multiple paths/URLs)",
                        suggestion="Use 'extends: ./base.yaml' or 'extends: [./base1.yaml, ./base2.yaml]'",
                    )
                )
            elif isinstance(extends, list):
                for i, item in enumerate(extends):
                    if not isinstance(item, str):
                        self.errors.append(
                            ConfigValidationError(
                                field=f"extends[{i}]",
                                error=f"extends list items must be strings, got {type(item).__name__}",
                                suggestion="Each item in extends list should be a path or URL string",
                            )
                        )

        # Check for mcp_server section
        # Note: If using extends, mcp_server might come from base config
        if "mcp_server" not in config:
            if "extends" not in config:
                # No mcp_server and no extends - this is an error
                self.errors.append(
                    ConfigValidationError(
                        field="mcp_server",
                        error="Missing required field: mcp_server",
                        suggestion="Add an 'mcp_server' section with 'command' and 'args' fields.",
                    )
                )
            # If extends is present but no mcp_server, that's okay - it might come from the base
        else:
            # mcp_server is present, validate it
            self._validate_mcp_server(config["mcp_server"])

        # Validate provider
        provider = config.get("provider", "anthropic")
        if provider not in VALID_PROVIDERS:
            self.errors.append(
                ConfigValidationError(
                    field="provider",
                    error=f"Invalid provider: '{provider}'",
                    suggestion=f"Valid providers: {', '.join(VALID_PROVIDERS)}",
                )
            )

        # Validate agent_harness
        harness = config.get("agent_harness", "claude-code")
        if harness not in VALID_HARNESSES:
            self.errors.append(
                ConfigValidationError(
                    field="agent_harness",
                    error=f"Invalid agent_harness: '{harness}'",
                    suggestion=f"Valid harnesses: {', '.join(VALID_HARNESSES)}",
                )
            )

        # Validate benchmark
        benchmark = config.get("benchmark", "swe-bench-verified")
        if benchmark not in VALID_BENCHMARKS:
            self.errors.append(
                ConfigValidationError(
                    field="benchmark",
                    error=f"Invalid benchmark: '{benchmark}'",
                    suggestion=f"Valid benchmarks: {', '.join(VALID_BENCHMARKS)}",
                )
            )

        # Validate model (just check it's a non-empty string)
        model = config.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            self.errors.append(
                ConfigValidationError(
                    field="model",
                    error="Model must be a non-empty string",
                    suggestion="Use a valid Anthropic model ID like 'claude-sonnet-4-5-20250514' or 'sonnet'",
                )
            )

        # Validate numeric fields
        self._validate_numeric_field(
            config, "timeout_seconds", min_value=30, suggestion="Should be at least 30 seconds"
        )
        self._validate_numeric_field(
            config,
            "max_concurrent",
            min_value=1,
            suggestion="Should be at least 1 for concurrent execution",
        )
        self._validate_numeric_field(
            config, "max_iterations", min_value=1, suggestion="Should be at least 1"
        )
        self._validate_numeric_field(
            config, "sample_size", min_value=1, required=False, allow_null=True
        )
        self._validate_numeric_field(
            config,
            "cybergym_level",
            min_value=0,
            max_value=3,
            required=False,
            suggestion="CyberGym level must be between 0 and 3",
        )

        # Validate agent_prompt placeholder
        agent_prompt = config.get("agent_prompt")
        if (
            agent_prompt
            and isinstance(agent_prompt, str)
            and "{problem_statement}" not in agent_prompt
        ):
            self.warnings.append(
                ConfigValidationError(
                    field="agent_prompt",
                    error="agent_prompt doesn't contain {problem_statement} placeholder",
                    suggestion="Include {problem_statement} placeholder to inject the task description",
                )
            )

    def _validate_mcp_server(self, mcp_server: Any) -> None:
        """Validate MCP server configuration.

        Args:
            mcp_server: MCP server configuration dictionary.
        """
        if not isinstance(mcp_server, dict):
            self.errors.append(
                ConfigValidationError(
                    field="mcp_server",
                    error="mcp_server must be a dictionary/object",
                    suggestion="Use 'mcp_server:' followed by indented fields like 'command:' and 'args:'",
                )
            )
            return

        # Check required command field
        if "command" not in mcp_server:
            self.errors.append(
                ConfigValidationError(
                    field="mcp_server.command",
                    error="Missing required field: command",
                    suggestion="Add 'command' field (e.g., 'npx', 'python', 'uvx')",
                )
            )
        elif not isinstance(mcp_server["command"], str) or not mcp_server["command"].strip():
            self.errors.append(
                ConfigValidationError(
                    field="mcp_server.command",
                    error="command must be a non-empty string",
                    suggestion="Provide the executable command like 'npx' or 'python'",
                )
            )

        # Validate args field
        args = mcp_server.get("args", [])
        if not isinstance(args, list):
            self.errors.append(
                ConfigValidationError(
                    field="mcp_server.args",
                    error="args must be a list/array",
                    suggestion="Use YAML list syntax with '-' prefix for each argument",
                )
            )
        else:
            # Check for {workdir} placeholder
            has_workdir = any("{workdir}" in str(arg) for arg in args)
            if not has_workdir:
                self.warnings.append(
                    ConfigValidationError(
                        field="mcp_server.args",
                        error="args doesn't contain {workdir} placeholder",
                        suggestion="Include {workdir} placeholder to pass the task working directory to your MCP server",
                    )
                )

        # Validate env field (optional)
        env = mcp_server.get("env")
        if env is not None:
            if not isinstance(env, dict):
                self.errors.append(
                    ConfigValidationError(
                        field="mcp_server.env",
                        error="env must be a dictionary/object",
                        suggestion="Use key-value pairs for environment variables",
                    )
                )
            else:
                # Check for environment variable references
                for key, value in env.items():
                    if isinstance(value, str) and "${" in value:
                        # Extract variable names
                        var_refs = re.findall(r"\$\{(\w+)\}", value)
                        for var in var_refs:
                            if var not in os.environ:
                                self.warnings.append(
                                    ConfigValidationError(
                                        field=f"mcp_server.env.{key}",
                                        error=f"Environment variable ${{{var}}} is not set",
                                        suggestion=f"Set {var} environment variable before running",
                                    )
                                )

        # Validate name field (optional)
        name = mcp_server.get("name")
        if name is not None and (not isinstance(name, str) or not name.strip()):
            self.errors.append(
                ConfigValidationError(
                    field="mcp_server.name",
                    error="name must be a non-empty string if provided",
                    suggestion="Provide a descriptive name for the MCP server",
                )
            )

    def _validate_numeric_field(
        self,
        config: dict[str, Any],
        field: str,
        min_value: int | None = None,
        max_value: int | None = None,
        required: bool = False,
        allow_null: bool = False,
        suggestion: str | None = None,
    ) -> None:
        """Validate a numeric configuration field.

        Args:
            config: Configuration dictionary.
            field: Field name to validate.
            min_value: Minimum allowed value.
            max_value: Maximum allowed value.
            required: Whether the field is required.
            allow_null: Whether null/None values are allowed.
            suggestion: Custom suggestion message.
        """
        value = config.get(field)

        if value is None:
            if required and not allow_null:
                self.errors.append(
                    ConfigValidationError(
                        field=field,
                        error=f"Missing required field: {field}",
                        suggestion=suggestion or f"Add '{field}' field with a numeric value",
                    )
                )
            return

        if not isinstance(value, (int, float)):
            self.errors.append(
                ConfigValidationError(
                    field=field,
                    error=f"{field} must be a number, got {type(value).__name__}",
                    suggestion=suggestion or f"Use a numeric value for {field}",
                )
            )
            return

        if min_value is not None and value < min_value:
            self.errors.append(
                ConfigValidationError(
                    field=field,
                    error=f"{field} must be at least {min_value}, got {value}",
                    suggestion=suggestion or f"Set {field} to {min_value} or higher",
                )
            )

        if max_value is not None and value > max_value:
            self.errors.append(
                ConfigValidationError(
                    field=field,
                    error=f"{field} must be at most {max_value}, got {value}",
                    suggestion=suggestion or f"Set {field} to {max_value} or lower",
                )
            )

    def _validate_api_key(self) -> None:
        """Validate API key format for Anthropic provider."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            self.warnings.append(
                ConfigValidationError(
                    field="environment",
                    error="ANTHROPIC_API_KEY environment variable is not set",
                    suggestion="Set ANTHROPIC_API_KEY before running evaluation",
                )
            )
            return

        # Check basic format (Anthropic keys start with 'sk-ant-')
        if not api_key.startswith("sk-ant-"):
            self.warnings.append(
                ConfigValidationError(
                    field="environment",
                    error="ANTHROPIC_API_KEY doesn't match expected format",
                    suggestion="Anthropic API keys should start with 'sk-ant-'. Verify your API key.",
                )
            )
        elif len(api_key) < 20:
            self.warnings.append(
                ConfigValidationError(
                    field="environment",
                    error="ANTHROPIC_API_KEY seems too short",
                    suggestion="Anthropic API keys are typically longer. Verify your API key.",
                )
            )

    def _validate_with_pydantic(self, config: dict[str, Any]) -> None:
        """Validate configuration using Pydantic models.

        Args:
            config: Configuration dictionary.
        """
        try:
            HarnessConfig(**config)
        except ValidationError as e:
            for error in e.errors():
                field_path = ".".join(str(loc) for loc in error["loc"])
                error_msg = error["msg"]

                # Try to provide helpful suggestions based on error type
                suggestion = self._get_pydantic_error_suggestion(dict(error))

                self.errors.append(
                    ConfigValidationError(
                        field=field_path,
                        error=error_msg,
                        suggestion=suggestion,
                    )
                )

    def _get_pydantic_error_suggestion(self, error: dict[str, Any]) -> str | None:
        """Generate helpful suggestions for Pydantic validation errors.

        Args:
            error: Pydantic error dictionary.

        Returns:
            Suggestion string or None.
        """
        error_type = error.get("type", "")
        field = error.get("loc", [])[-1] if error.get("loc") else ""

        suggestions = {
            "missing": f"Add the required '{field}' field to your configuration",
            "string_type": f"'{field}' should be a text string, not a number or other type",
            "int_type": f"'{field}' should be an integer number",
            "value_error": "Check the field value meets the validation requirements",
        }

        for error_pattern, suggestion in suggestions.items():
            if error_pattern in error_type:
                return suggestion

        return None

    @property
    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0


def validate_config(config_path: str | Path) -> ValidationResult:
    """Validate a configuration file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        ValidationResult with errors and warnings.
    """
    validator = ConfigValidator()
    return validator.validate_file(config_path)
