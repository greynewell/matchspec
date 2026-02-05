"""Interactive configuration wizard for creating mcpbr config files.

Provides a step-by-step CLI wizard that guides users through creating
a valid YAML configuration file with helpful inline comments.
"""

from pathlib import Path
from typing import Any

import click
import yaml

from .config import VALID_BENCHMARKS
from .models import DEFAULT_MODEL, SUPPORTED_MODELS, list_supported_models

# Preset configurations for common MCP server use cases
PRESETS: dict[str, dict[str, Any]] = {
    "filesystem": {
        "description": "Local filesystem access (read/write files in the workspace)",
        "mcp_server": {
            "name": "filesystem",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            "env": {},
        },
    },
    "web-search": {
        "description": "Web search capabilities via Brave Search API",
        "mcp_server": {
            "name": "brave-search",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        },
    },
    "database": {
        "description": "PostgreSQL database access via MCP",
        "mcp_server": {
            "name": "postgres",
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-postgres",
                "${DATABASE_URL}",
            ],
            "env": {},
        },
    },
    "custom": {
        "description": "Custom MCP server (you provide command, args, and env)",
        "mcp_server": None,
    },
}


class ConfigWizard:
    """Interactive wizard for creating mcpbr configuration files.

    Guides users through configuring an MCP server, selecting a model
    and benchmark, and setting advanced options. Generates a valid YAML
    config file with inline comments.

    Example usage::

        wizard = ConfigWizard()
        config = wizard.run()
        # config is a dict ready for YAML serialization
    """

    def __init__(self) -> None:
        """Initialize the configuration wizard."""
        self.config: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        """Run the full interactive configuration wizard.

        Walks the user through each configuration section in order:
        preset selection, model, benchmark, MCP servers, and advanced
        settings. Returns the assembled configuration dictionary.

        Returns:
            Complete configuration dictionary suitable for YAML output.
        """
        click.echo("\n===  mcpbr Configuration Wizard  ===\n")
        click.echo("This wizard will help you create a configuration file")
        click.echo("for running MCP server benchmarks.\n")

        self._select_preset()
        self._configure_model()
        self._configure_benchmark()
        self._configure_mcp_servers()
        self._configure_advanced()

        return self.config

    def _select_preset(self) -> None:
        """Prompt the user to select a preset MCP server configuration.

        Displays available presets with descriptions and applies the
        selected preset's MCP server config to self.config. For the
        'custom' preset, delegates to manual MCP server configuration.
        """
        click.echo("--- Step 1: Select a Preset ---\n")
        click.echo("Choose a starting point for your MCP server configuration:\n")

        preset_names = list(PRESETS.keys())
        for i, name in enumerate(preset_names, 1):
            desc = PRESETS[name]["description"]
            click.echo(f"  [{i}] {name} - {desc}")

        click.echo()

        choice = click.prompt(
            "Select a preset",
            type=click.IntRange(1, len(preset_names)),
            default=1,
        )

        selected_name = preset_names[choice - 1]
        preset = PRESETS[selected_name]

        click.echo(f"\nSelected: {selected_name}\n")

        if preset["mcp_server"] is not None:
            self.config["mcp_server"] = dict(preset["mcp_server"])
        else:
            # Custom preset: gather MCP server details manually
            self.config["mcp_server"] = self._prompt_custom_mcp_server()

    def _prompt_custom_mcp_server(self) -> dict[str, Any]:
        """Prompt the user to configure a custom MCP server.

        Asks for server name, command, arguments, and optional
        environment variables.

        Returns:
            MCP server configuration dictionary.
        """
        click.echo("--- Custom MCP Server Configuration ---\n")

        name = click.prompt("Server name", type=str, default="my-server")
        command = click.prompt(
            "Command to start the server (e.g., npx, uvx, python, node)",
            type=str,
        )

        args_str = click.prompt(
            "Arguments (space-separated, use {workdir} for workspace path)",
            type=str,
            default="",
        )
        args = args_str.split() if args_str.strip() else []

        env: dict[str, str] = {}
        if click.confirm("Add environment variables?", default=False):
            while True:
                key = click.prompt("  Variable name (empty to finish)", type=str, default="")
                if not key:
                    break
                value = click.prompt(f"  Value for {key}", type=str)
                env[key] = value

        return {
            "name": name,
            "command": command,
            "args": args,
            "env": env,
        }

    def _configure_model(self) -> None:
        """Prompt the user to select an LLM model for evaluation.

        Displays available models from the model registry and lets the
        user pick one, defaulting to the project default model.
        """
        click.echo("--- Step 2: Select a Model ---\n")

        models = list_supported_models()
        # Show unique models (skip duplicates from aliases pointing to same display name)
        seen_display: set[str] = set()
        unique_models: list[tuple[str, str]] = []
        for m in models:
            if m.display_name not in seen_display:
                seen_display.add(m.display_name)
                unique_models.append((m.id, m.display_name))

        click.echo("Available models:\n")
        for model_id, display_name in unique_models:
            marker = " (default)" if model_id == DEFAULT_MODEL else ""
            click.echo(f"  - {model_id}: {display_name}{marker}")

        click.echo()

        model_id = click.prompt(
            "Model ID",
            type=str,
            default=DEFAULT_MODEL,
        )

        # Warn if model is not in the supported list but allow it
        if model_id not in SUPPORTED_MODELS:
            click.echo(
                f"\nWarning: '{model_id}' is not in the known model list. "
                "It may still work if your provider supports it."
            )
            if not click.confirm("Use this model anyway?", default=True):
                model_id = DEFAULT_MODEL
                click.echo(f"Using default model: {model_id}")

        self.config["model"] = model_id

    def _configure_benchmark(self) -> None:
        """Prompt the user to select a benchmark for evaluation.

        Shows all valid benchmarks and lets the user pick one. Defaults
        to swe-bench-verified.
        """
        click.echo("\n--- Step 3: Select a Benchmark ---\n")

        click.echo("Available benchmarks:\n")
        for benchmark in VALID_BENCHMARKS:
            marker = " (default)" if benchmark == "swe-bench-verified" else ""
            click.echo(f"  - {benchmark}{marker}")

        click.echo()

        benchmark = click.prompt(
            "Benchmark",
            type=click.Choice(list(VALID_BENCHMARKS), case_sensitive=False),
            default="swe-bench-verified",
            show_choices=False,
        )

        self.config["benchmark"] = benchmark

    def _configure_mcp_servers(self) -> None:
        """Prompt the user to refine MCP server connection settings.

        Asks about the connection type (stdio vs SSE) and allows
        customization of timeouts and optional setup commands.
        """
        click.echo("\n--- Step 4: MCP Server Settings ---\n")

        # Connection type
        click.echo("MCP server connection type:\n")
        click.echo("  [1] stdio - Standard I/O (local process, most common)")
        click.echo("  [2] sse   - Server-Sent Events (remote HTTP server)")
        click.echo()

        conn_choice = click.prompt(
            "Connection type",
            type=click.IntRange(1, 2),
            default=1,
        )

        if conn_choice == 2:
            # SSE mode: override command/args with SSE URL
            sse_url = click.prompt("SSE server URL", type=str)
            self.config["mcp_server"]["command"] = "npx"
            self.config["mcp_server"]["args"] = [
                "-y",
                "@modelcontextprotocol/client-sse",
                sse_url,
            ]
            click.echo(f"\nConfigured SSE connection to: {sse_url}")

        # Server name
        current_name = self.config["mcp_server"].get("name", "mcpbr")
        name = click.prompt("Server name", type=str, default=current_name)
        self.config["mcp_server"]["name"] = name

        # Startup timeout
        startup_timeout = click.prompt(
            "Startup timeout (ms)",
            type=int,
            default=60000,
        )
        if startup_timeout != 60000:
            self.config["mcp_server"]["startup_timeout_ms"] = startup_timeout

        # Tool timeout
        tool_timeout = click.prompt(
            "Tool execution timeout (ms)",
            type=int,
            default=900000,
        )
        if tool_timeout != 900000:
            self.config["mcp_server"]["tool_timeout_ms"] = tool_timeout

        # Setup command
        if click.confirm("Add a setup command (runs before agent starts)?", default=False):
            setup_cmd = click.prompt(
                "Setup command (use {workdir} for workspace path)",
                type=str,
            )
            self.config["mcp_server"]["setup_command"] = setup_cmd

    def _configure_advanced(self) -> None:
        """Prompt the user for advanced evaluation settings.

        Covers sample size, timeout, concurrency, iteration limits,
        thinking budget, and budget cap.
        """
        click.echo("\n--- Step 5: Advanced Settings ---\n")

        if not click.confirm("Configure advanced settings?", default=False):
            # Apply sensible defaults
            self.config.setdefault("provider", "anthropic")
            self.config.setdefault("agent_harness", "claude-code")
            self.config.setdefault("sample_size", 10)
            self.config.setdefault("timeout_seconds", 300)
            self.config.setdefault("max_concurrent", 4)
            self.config.setdefault("max_iterations", 10)
            return

        # Provider (currently only anthropic)
        self.config["provider"] = "anthropic"
        self.config["agent_harness"] = "claude-code"

        # Sample size
        sample_input = click.prompt(
            "Sample size (number of tasks, or 'all' for full dataset)",
            type=str,
            default="10",
        )
        if sample_input.lower() == "all":
            self.config["sample_size"] = None
        else:
            try:
                sample_val = int(sample_input)
                if sample_val < 1:
                    click.echo("Sample size must be at least 1. Using 10.")
                    sample_val = 10
                self.config["sample_size"] = sample_val
            except ValueError:
                click.echo("Invalid number. Using default of 10.")
                self.config["sample_size"] = 10

        # Timeout
        timeout = click.prompt(
            "Timeout per task (seconds, minimum 30)",
            type=int,
            default=300,
        )
        if timeout < 30:
            click.echo("Timeout must be at least 30 seconds. Using 30.")
            timeout = 30
        self.config["timeout_seconds"] = timeout

        # Max concurrent
        max_concurrent = click.prompt(
            "Maximum concurrent tasks",
            type=int,
            default=4,
        )
        if max_concurrent < 1:
            click.echo("Must be at least 1. Using 1.")
            max_concurrent = 1
        self.config["max_concurrent"] = max_concurrent

        # Max iterations
        max_iterations = click.prompt(
            "Maximum agent iterations per task",
            type=int,
            default=10,
        )
        if max_iterations < 1:
            click.echo("Must be at least 1. Using 1.")
            max_iterations = 1
        self.config["max_iterations"] = max_iterations

        # Thinking budget
        if click.confirm("Enable extended thinking?", default=False):
            thinking = click.prompt(
                "Thinking budget (tokens, 1024-31999)",
                type=int,
                default=10000,
            )
            if thinking < 1024:
                click.echo("Minimum is 1024. Using 1024.")
                thinking = 1024
            elif thinking > 31999:
                click.echo("Maximum is 31999. Using 31999.")
                thinking = 31999
            self.config["thinking_budget"] = thinking

        # Budget cap
        if click.confirm("Set a budget cap (USD)?", default=False):
            budget = click.prompt("Maximum budget (USD)", type=float)
            if budget <= 0:
                click.echo("Budget must be positive. Skipping budget cap.")
            else:
                self.config["budget"] = budget

    def _generate_config(self, output_path: Path) -> str:
        """Generate a YAML config file with inline comments.

        Writes the current configuration to the specified path as YAML,
        with a header and inline comments explaining each field.

        Args:
            output_path: File path to write the YAML configuration to.

        Returns:
            The generated YAML string.
        """
        yaml_str = generate_commented_yaml(self.config)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml_str)

        return yaml_str


def generate_commented_yaml(config: dict[str, Any]) -> str:
    """Generate a YAML configuration string with helpful inline comments.

    Produces a human-readable YAML file with a header block and comments
    explaining each configuration field. The output is compatible with
    ``mcpbr.config.load_config()``.

    Args:
        config: Configuration dictionary to serialize.

    Returns:
        YAML string with inline comments.
    """
    lines: list[str] = []

    # Header
    lines.append("# mcpbr - Model Context Protocol Benchmark Runner")
    lines.append("#")
    lines.append("# Generated by the interactive configuration wizard.")
    lines.append("# Edit this file to customize your evaluation settings.")
    lines.append("#")
    lines.append("# Requires ANTHROPIC_API_KEY environment variable.")
    lines.append("# Docs: https://github.com/greynewell/mcpbr")
    lines.append("")

    # MCP server section
    mcp = config.get("mcp_server", {})
    lines.append("# MCP server configuration")
    lines.append("# The MCP server provides tools for the agent to use during evaluation.")
    lines.append("mcp_server:")
    lines.append("  # Name to register the server as (appears in tool names like mcp__<name>__*)")
    lines.append(f'  name: "{mcp.get("name", "mcpbr")}"')
    lines.append("")
    lines.append("  # Command to start the MCP server")
    lines.append(f'  command: "{mcp.get("command", "npx")}"')
    lines.append("")
    lines.append("  # Arguments to pass to the command")
    lines.append("  # Use {workdir} as a placeholder for the task working directory")
    lines.append("  args:")
    for arg in mcp.get("args", []):
        lines.append(f'    - "{arg}"')
    lines.append("")

    # Environment variables
    env = mcp.get("env", {})
    lines.append("  # Environment variables for the MCP server")
    if env:
        lines.append("  env:")
        for key, value in env.items():
            lines.append(f'    {key}: "{value}"')
    else:
        lines.append("  env: {}")
    lines.append("")

    # Optional MCP server fields
    if "startup_timeout_ms" in mcp:
        lines.append("  # Timeout for MCP server startup (ms)")
        lines.append(f"  startup_timeout_ms: {mcp['startup_timeout_ms']}")
        lines.append("")

    if "tool_timeout_ms" in mcp:
        lines.append("  # Timeout for MCP tool execution (ms)")
        lines.append(f"  tool_timeout_ms: {mcp['tool_timeout_ms']}")
        lines.append("")

    if "setup_command" in mcp:
        lines.append("  # Shell command to run before the agent starts (outside task timer)")
        lines.append(f'  setup_command: "{mcp["setup_command"]}"')
        lines.append("")

    # Provider
    lines.append("# Model provider (currently only anthropic is supported)")
    lines.append(f'provider: "{config.get("provider", "anthropic")}"')
    lines.append("")

    # Agent harness
    lines.append("# Agent harness (currently only claude-code is supported)")
    lines.append(f'agent_harness: "{config.get("agent_harness", "claude-code")}"')
    lines.append("")

    # Model
    lines.append("# Model ID for the selected provider")
    lines.append("# Run 'mcpbr models' to see available options")
    lines.append(f'model: "{config.get("model", DEFAULT_MODEL)}"')
    lines.append("")

    # Benchmark
    lines.append("# Benchmark to run")
    lines.append("# Run 'mcpbr benchmarks' to see all available benchmarks")
    lines.append(f'benchmark: "{config.get("benchmark", "swe-bench-verified")}"')
    lines.append("")

    # Sample size
    sample_size = config.get("sample_size")
    lines.append("# Number of tasks to evaluate (null for full dataset)")
    if sample_size is None:
        lines.append("sample_size: null")
    else:
        lines.append(f"sample_size: {sample_size}")
    lines.append("")

    # Timeout
    lines.append("# Timeout for each task in seconds (minimum 30)")
    lines.append(f"timeout_seconds: {config.get('timeout_seconds', 300)}")
    lines.append("")

    # Max concurrent
    lines.append("# Maximum concurrent task evaluations")
    lines.append(f"max_concurrent: {config.get('max_concurrent', 4)}")
    lines.append("")

    # Max iterations
    lines.append("# Maximum agent iterations per task")
    lines.append(f"max_iterations: {config.get('max_iterations', 10)}")
    lines.append("")

    # Thinking budget
    if "thinking_budget" in config:
        lines.append("# Extended thinking token budget (1024-31999)")
        lines.append(f"thinking_budget: {config['thinking_budget']}")
        lines.append("")

    # Budget
    if "budget" in config:
        lines.append("# Maximum budget in USD (halts evaluation when reached)")
        lines.append(f"budget: {config['budget']}")
        lines.append("")

    return "\n".join(lines) + "\n"


def validate_config_dict(config: dict[str, Any]) -> list[str]:
    """Validate a configuration dictionary and return a list of errors.

    Performs basic validation of required fields and value ranges without
    constructing a full Pydantic model.

    Args:
        config: Configuration dictionary to validate.

    Returns:
        List of error messages. Empty list means the config is valid.
    """
    errors: list[str] = []

    # Check mcp_server
    mcp = config.get("mcp_server")
    if not mcp:
        errors.append("mcp_server is required")
    elif not isinstance(mcp, dict):
        errors.append("mcp_server must be a dictionary")
    else:
        if not mcp.get("command"):
            errors.append("mcp_server.command is required")

    # Check benchmark
    benchmark = config.get("benchmark", "swe-bench-verified")
    if benchmark not in VALID_BENCHMARKS:
        errors.append(
            f"Invalid benchmark: '{benchmark}'. Valid benchmarks: {', '.join(VALID_BENCHMARKS)}"
        )

    # Check timeout
    timeout = config.get("timeout_seconds", 300)
    if isinstance(timeout, int) and timeout < 30:
        errors.append("timeout_seconds must be at least 30")

    # Check max_concurrent
    max_concurrent = config.get("max_concurrent", 4)
    if isinstance(max_concurrent, int) and max_concurrent < 1:
        errors.append("max_concurrent must be at least 1")

    # Check thinking_budget
    thinking = config.get("thinking_budget")
    if thinking is not None:
        if isinstance(thinking, int):
            if thinking < 1024:
                errors.append("thinking_budget must be at least 1024")
            elif thinking > 31999:
                errors.append("thinking_budget cannot exceed 31999")

    # Check budget
    budget = config.get("budget")
    if budget is not None and isinstance(budget, (int, float)) and budget <= 0:
        errors.append("budget must be positive")

    return errors


def run_wizard(output_path: Path) -> None:
    """Run the configuration wizard and write the result to a file.

    Entry point for invoking the wizard from the CLI. Creates a
    ConfigWizard instance, runs it, validates the result, and writes
    the YAML config to the specified output path.

    Args:
        output_path: Path to write the generated YAML configuration.

    Raises:
        click.Abort: If the user cancels the wizard.
    """
    wizard = ConfigWizard()

    try:
        config = wizard.run()
    except (click.Abort, EOFError):
        click.echo("\nWizard cancelled.")
        return

    # Validate before writing
    errors = validate_config_dict(config)
    if errors:
        click.echo("\nConfiguration has issues:")
        for error in errors:
            click.echo(f"  - {error}")
        if not click.confirm("\nWrite config anyway?", default=False):
            click.echo("Aborted.")
            return

    yaml_str = wizard._generate_config(output_path)

    click.echo(f"\nConfiguration saved to: {output_path}")
    click.echo("\nTo validate your config:")
    click.echo(f"  mcpbr config validate {output_path}")
    click.echo("\nTo run an evaluation:")
    click.echo(f"  mcpbr run --config {output_path}")

    # Verify the generated YAML is parseable
    try:
        yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        click.echo(f"\nWarning: Generated YAML may have syntax issues: {e}")
