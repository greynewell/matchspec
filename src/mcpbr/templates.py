"""Configuration templates for common MCP server scenarios."""

from dataclasses import dataclass
from typing import Any

from .models import DEFAULT_MODEL


@dataclass
class Template:
    """Configuration template with metadata."""

    id: str
    name: str
    description: str
    category: str
    config: dict[str, Any]
    tags: list[str]


# Template definitions
TEMPLATES = {
    "filesystem": Template(
        id="filesystem",
        name="Filesystem Server (Basic)",
        description="Basic filesystem access with the official Anthropic MCP server",
        category="File Operations",
        config={
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        },
        tags=["filesystem", "basic", "official", "recommended"],
    ),
    "filesystem-readonly": Template(
        id="filesystem-readonly",
        name="Filesystem Server (Read-Only)",
        description="Read-only filesystem access for safe exploration",
        category="File Operations",
        config={
            "mcp_server": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "{workdir}",
                    "--readonly",
                ],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        },
        tags=["filesystem", "readonly", "safe", "official"],
    ),
    "supermodel": Template(
        id="supermodel",
        name="Supermodel Codebase Analysis",
        description="Advanced codebase analysis with Supermodel MCP server",
        category="Code Analysis",
        config={
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@supermodeltools/mcp-server"],
                "env": {"SUPERMODEL_API_KEY": "${SUPERMODEL_API_KEY}"},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench",
            "sample_size": 10,
            "timeout_seconds": 600,
            "max_concurrent": 2,
            "max_iterations": 15,
        },
        tags=["codebase", "analysis", "advanced", "api-key"],
    ),
    "cybergym-basic": Template(
        id="cybergym-basic",
        name="CyberGym Security Testing",
        description="Security vulnerability testing with CyberGym benchmark",
        category="Security",
        config={
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "cybergym",
            "cybergym_level": 1,
            "sample_size": 5,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        },
        tags=["security", "cybergym", "vulnerability", "basic"],
    ),
    "cybergym-advanced": Template(
        id="cybergym-advanced",
        name="CyberGym Advanced Security",
        description="Advanced security testing with maximum context (level 3)",
        category="Security",
        config={
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "cybergym",
            "cybergym_level": 3,
            "sample_size": 5,
            "timeout_seconds": 600,
            "max_concurrent": 2,
            "max_iterations": 20,
        },
        tags=["security", "cybergym", "vulnerability", "advanced"],
    ),
    "quick-test": Template(
        id="quick-test",
        name="Quick Test (Single Task)",
        description="Fast single-task evaluation for quick testing",
        category="Testing",
        config={
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench",
            "sample_size": 1,
            "timeout_seconds": 300,
            "max_concurrent": 1,
            "max_iterations": 10,
        },
        tags=["testing", "quick", "development", "single-task"],
    ),
    "production": Template(
        id="production",
        name="Production Evaluation",
        description="Full-scale production evaluation with optimal settings",
        category="Production",
        config={
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench",
            "sample_size": None,
            "timeout_seconds": 600,
            "max_concurrent": 8,
            "max_iterations": 30,
            "use_prebuilt_images": True,
        },
        tags=["production", "full-scale", "performance"],
    ),
    "custom-python": Template(
        id="custom-python",
        name="Custom Python MCP Server",
        description="Template for custom Python-based MCP servers",
        category="Custom",
        config={
            "mcp_server": {
                "command": "python",
                "args": ["-m", "my_mcp_server", "--workspace", "{workdir}"],
                "env": {"LOG_LEVEL": "debug"},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        },
        tags=["custom", "python", "development"],
    ),
    "custom-node": Template(
        id="custom-node",
        name="Custom Node.js MCP Server",
        description="Template for custom Node.js-based MCP servers",
        category="Custom",
        config={
            "mcp_server": {
                "command": "node",
                "args": ["path/to/server.js", "{workdir}"],
                "env": {"NODE_ENV": "production"},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        },
        tags=["custom", "nodejs", "development"],
    ),
}


def list_templates() -> list[Template]:
    """List all available templates.

    Returns:
        List of Template objects sorted by category and name.
    """
    return sorted(TEMPLATES.values(), key=lambda t: (t.category, t.name))


def get_template(template_id: str) -> Template | None:
    """Get a template by ID.

    Args:
        template_id: Template identifier.

    Returns:
        Template object or None if not found.
    """
    return TEMPLATES.get(template_id)


def get_templates_by_category() -> dict[str, list[Template]]:
    """Get templates grouped by category.

    Returns:
        Dictionary mapping category names to lists of templates.
    """
    result: dict[str, list[Template]] = {}
    for template in list_templates():
        if template.category not in result:
            result[template.category] = []
        result[template.category].append(template)
    return result


def get_templates_by_tag(tag: str) -> list[Template]:
    """Get templates that have a specific tag.

    Args:
        tag: Tag to filter by.

    Returns:
        List of templates with the specified tag.
    """
    return [t for t in list_templates() if tag in t.tags]


def generate_config_yaml(template: Template, custom_values: dict[str, Any] | None = None) -> str:
    """Generate a YAML configuration string from a template.

    Args:
        template: Template to use.
        custom_values: Optional dictionary of values to override in the template.

    Returns:
        YAML configuration string.
    """
    import yaml

    config = template.config.copy()

    # Apply custom values if provided
    if custom_values:
        for key, value in custom_values.items():
            if key in config:
                config[key] = value

    # Generate YAML with comments header
    yaml_content = f"""# mcpbr - Model Context Protocol Benchmark Runner
#
# Template: {template.name}
# {template.description}
#
# Requires ANTHROPIC_API_KEY environment variable.

"""

    # Convert config to YAML
    yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)

    return yaml_content + yaml_str
