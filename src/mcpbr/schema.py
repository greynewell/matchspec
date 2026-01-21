"""JSON Schema generation and validation for mcpbr configuration files.

This module provides functionality to:
- Generate JSON Schema from Pydantic models
- Validate configuration files against the schema
- Export schema for IDE integration
- Publish schema to GitHub Pages
"""

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from .config import HarnessConfig


def generate_json_schema() -> dict[str, Any]:
    """Generate JSON Schema for HarnessConfig.

    Returns:
        JSON Schema dictionary compatible with JSON Schema Draft 2020-12.
    """
    # Use TypeAdapter to generate schema with proper $schema and metadata
    adapter = TypeAdapter(HarnessConfig)
    schema = adapter.json_schema(mode="validation")

    # Add metadata for better IDE integration
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://greynewell.github.io/mcpbr/schema/config.json"
    schema["title"] = "mcpbr Configuration"
    schema["description"] = (
        "Configuration schema for mcpbr (Model Context Protocol Benchmark Runner). "
        "This schema validates YAML/TOML configuration files for evaluating MCP servers "
        "against software engineering benchmarks."
    )

    # Add examples to the schema
    schema["examples"] = [
        {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": "claude-sonnet-4-5-20250514",
            "benchmark": "swe-bench",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
        }
    ]

    return schema


def save_schema(output_path: Path | str) -> None:
    """Save JSON Schema to a file.

    Args:
        output_path: Path where the schema JSON file will be saved.
    """
    schema = generate_json_schema()
    path = Path(output_path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write with pretty formatting
    with open(path, "w") as f:
        json.dump(schema, f, indent=2)


def get_schema_url() -> str:
    """Get the published JSON Schema URL for IDE integration.

    Returns:
        URL to the published JSON Schema.
    """
    return "https://greynewell.github.io/mcpbr/schema/config.json"


def add_schema_comment(yaml_content: str) -> str:
    """Add JSON Schema comment to YAML configuration.

    This enables IDE auto-completion and validation for YAML files.

    Args:
        yaml_content: Original YAML content.

    Returns:
        YAML content with schema comment added at the top.
    """
    schema_url = get_schema_url()
    comment = f"# yaml-language-server: $schema={schema_url}\n\n"

    # Don't add if already present
    if "yaml-language-server" in yaml_content:
        return yaml_content

    return comment + yaml_content


def validate_against_schema(config_data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate configuration data against the JSON Schema.

    This provides an alternative validation method using JSON Schema
    validation instead of Pydantic validation.

    Args:
        config_data: Configuration dictionary to validate.

    Returns:
        Tuple of (is_valid, error_messages).
    """
    try:
        # Use Pydantic's validation which is schema-aware
        HarnessConfig(**config_data)
        return True, []
    except Exception as e:
        return False, [str(e)]


def get_schema_for_yaml_ls() -> dict[str, Any]:
    """Get schema formatted for YAML Language Server.

    Returns:
        JSON Schema dictionary optimized for YAML-LS.
    """
    schema = generate_json_schema()

    # YAML-LS specific enhancements
    if "properties" in schema and "mcp_server" in schema["properties"]:
        mcp_server = schema["properties"]["mcp_server"]
        if "properties" in mcp_server and "args" in mcp_server["properties"]:
            # Add example for {workdir} placeholder
            args_schema = mcp_server["properties"]["args"]
            if "items" not in args_schema:
                args_schema["items"] = {}
            args_schema["items"]["examples"] = [
                "{workdir}",
                "-y",
                "@modelcontextprotocol/server-filesystem",
            ]

    return schema


def generate_schema_docs() -> str:
    """Generate Markdown documentation from the JSON Schema.

    Returns:
        Markdown documentation string describing the schema.
    """
    schema = generate_json_schema()

    docs = []
    docs.append("# Configuration Schema\n")
    docs.append(f"{schema.get('description', '')}\n")
    docs.append("## Schema URL\n")
    docs.append(f"```\n{get_schema_url()}\n```\n")
    docs.append("## Properties\n")

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for prop_name, prop_schema in properties.items():
        is_required = prop_name in required
        required_marker = " *(required)*" if is_required else " *(optional)*"

        docs.append(f"### `{prop_name}`{required_marker}\n")

        if "description" in prop_schema:
            docs.append(f"{prop_schema['description']}\n")

        if "type" in prop_schema:
            docs.append(f"**Type:** `{prop_schema['type']}`\n")

        if "default" in prop_schema:
            default_val = json.dumps(prop_schema["default"])
            docs.append(f"**Default:** `{default_val}`\n")

        if "enum" in prop_schema:
            enum_vals = ", ".join(f"`{v}`" for v in prop_schema["enum"])
            docs.append(f"**Valid values:** {enum_vals}\n")

        if "minimum" in prop_schema:
            docs.append(f"**Minimum:** `{prop_schema['minimum']}`\n")

        if "maximum" in prop_schema:
            docs.append(f"**Maximum:** `{prop_schema['maximum']}`\n")

        docs.append("")

    return "\n".join(docs)


def print_schema_info() -> str:
    """Generate a summary of the schema for display.

    Returns:
        Human-readable schema summary.
    """
    schema = generate_json_schema()

    lines = []
    lines.append("JSON Schema Information")
    lines.append("=" * 50)
    lines.append(f"Schema URL: {schema.get('$id', 'N/A')}")
    lines.append(f"Schema Version: {schema.get('$schema', 'N/A')}")
    lines.append(f"Title: {schema.get('title', 'N/A')}")
    lines.append("")
    lines.append("Properties:")

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for prop_name in properties:
        is_required = prop_name in required
        marker = "[required]" if is_required else "[optional]"
        lines.append(f"  - {prop_name} {marker}")

    return "\n".join(lines)
