"""MCP server configuration templates.

This module provides pre-configured templates for popular MCP servers,
making it easy for users to get started with common configurations.
"""

import importlib.resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class MCPTemplate(BaseModel):
    """Metadata for an MCP server configuration template."""

    id: str = Field(description="Unique template identifier")
    name: str = Field(description="Human-readable template name")
    description: str = Field(description="Description of what this MCP server does")
    package: str | None = Field(
        default=None, description="NPM package or Python package name"
    )
    requires_api_key: bool = Field(
        default=False, description="Whether this server requires an API key"
    )
    env_vars: list[str] = Field(
        default_factory=list, description="Required environment variables"
    )
    config: dict[str, Any] = Field(description="Template configuration")


# Registry of built-in templates
TEMPLATES: dict[str, MCPTemplate] = {}


def register_template(template: MCPTemplate) -> None:
    """Register a template in the global registry.

    Args:
        template: Template to register
    """
    TEMPLATES[template.id] = template


def get_template(template_id: str) -> MCPTemplate | None:
    """Get a template by ID.

    Args:
        template_id: Template identifier

    Returns:
        Template if found, None otherwise
    """
    return TEMPLATES.get(template_id)


def list_templates() -> list[MCPTemplate]:
    """List all available templates.

    Returns:
        List of all registered templates
    """
    return list(TEMPLATES.values())


def load_template_from_yaml(yaml_path: Path) -> MCPTemplate:
    """Load a template from a YAML file.

    Args:
        yaml_path: Path to YAML file

    Returns:
        Loaded template

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Template file not found: {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid template YAML: {yaml_path}")

    return MCPTemplate(**data)


def apply_template(template: MCPTemplate, output_path: Path, overrides: dict[str, Any] | None = None) -> None:
    """Apply a template to create a configuration file.

    Args:
        template: Template to apply
        output_path: Path to write configuration file
        overrides: Optional configuration overrides to merge

    Raises:
        FileExistsError: If output file already exists
    """
    if output_path.exists():
        raise FileExistsError(f"Configuration file already exists: {output_path}")

    # Start with template config
    config = template.config.copy()

    # Apply overrides if provided
    if overrides:
        config.update(overrides)

    # Write to YAML
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False)


def validate_template(template: MCPTemplate) -> list[str]:
    """Validate that a template is well-formed.

    Args:
        template: Template to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required fields
    if not template.id:
        errors.append("Template must have an id")
    if not template.name:
        errors.append("Template must have a name")
    if not template.description:
        errors.append("Template must have a description")

    # Validate config structure
    if not template.config:
        errors.append("Template must have a config section")
    elif not isinstance(template.config, dict):
        errors.append("Template config must be a dictionary")
    else:
        # Check for required config keys
        if "mcp_server" not in template.config:
            errors.append("Template config must include mcp_server section")
        else:
            mcp = template.config["mcp_server"]
            if not isinstance(mcp, dict):
                errors.append("mcp_server must be a dictionary")
            else:
                if "command" not in mcp:
                    errors.append("mcp_server must specify command")
                if "args" not in mcp:
                    errors.append("mcp_server must specify args")

    # Validate env_vars match config
    if template.env_vars and "mcp_server" in template.config:
        mcp = template.config["mcp_server"]
        if isinstance(mcp, dict) and "env" in mcp:
            env = mcp["env"]
            if isinstance(env, dict):
                config_env_vars = set(env.keys())
                declared_env_vars = set(template.env_vars)
                # Check if declared env vars are used in config
                for var in declared_env_vars:
                    if var not in config_env_vars:
                        # Check if it's referenced with ${VAR} syntax
                        env_str = str(env)
                        if f"${{{var}}}" not in env_str:
                            errors.append(
                                f"Declared env var '{var}' not found in config"
                            )

    return errors


def _load_builtin_templates() -> None:
    """Load all built-in templates from the templates directory."""
    try:
        # Try to load templates from package resources
        if hasattr(importlib.resources, "files"):
            # Python 3.9+
            try:
                templates_dir = importlib.resources.files("mcpbr") / "data" / "templates"
                # Use iterdir() for traversable paths
                for item in templates_dir.iterdir():
                    if item.name.endswith(".yaml"):
                        try:
                            # Read the template file
                            content = item.read_text()
                            data = yaml.safe_load(content)
                            if isinstance(data, dict):
                                template = MCPTemplate(**data)
                                register_template(template)
                        except Exception:
                            # Skip invalid templates
                            pass
            except Exception:
                # Directory doesn't exist or can't be read
                pass
    except Exception:
        # If loading fails, we just won't have built-in templates
        pass


# Load built-in templates on module import
_load_builtin_templates()
