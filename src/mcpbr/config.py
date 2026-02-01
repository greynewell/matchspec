"""Configuration models and loading for swebench-mcp."""

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from rich.console import Console

from .config_inheritance import load_config_with_inheritance
from .env_expansion import expand_env_vars, load_dotenv_file, validate_config_security
from .models import DEFAULT_MODEL

VALID_PROVIDERS = ("anthropic",)
VALID_HARNESSES = ("claude-code",)
VALID_BENCHMARKS = (
    "swe-bench-lite",
    "swe-bench-verified",
    "swe-bench-full",
    "cybergym",
    "humaneval",
    "mcptoolbench",
)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    name: str = Field(
        default="mcpbr", description="Name to register the MCP server as (appears in tool names)"
    )
    command: str = Field(
        description="Command to start the MCP server (e.g., 'npx', 'uvx', 'python')"
    )
    args: list[str] = Field(
        default_factory=list,
        description="Arguments to pass to the command. Use {workdir} as placeholder.",
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the MCP server",
    )
    startup_timeout_ms: int = Field(
        default=60000,
        description="Timeout in milliseconds for MCP server startup (default: 60s)",
    )
    tool_timeout_ms: int = Field(
        default=900000,
        description="Timeout in milliseconds for MCP tool execution (default: 15 min for long-running tools)",
    )

    def get_args_for_workdir(self, workdir: str) -> list[str]:
        """Replace {workdir} placeholder in args with actual path."""
        result = []
        for arg in self.args:
            result.append(arg.replace("{workdir}", workdir))
        return result

    def get_expanded_env(self) -> dict[str, str]:
        """Expand ${VAR} references in env values using os.environ.

        Returns:
            Dictionary with environment variables expanded.
        """
        result = {}
        for key, value in self.env.items():
            expanded = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)
            result[key] = expanded
        return result


class HarnessConfig(BaseModel):
    """Main configuration for the test harness.

    Supports multiple model providers and agent harnesses.
    """

    # Single server field (for backward compatibility)
    mcp_server: MCPServerConfig | None = Field(
        default=None, description="MCP server configuration (single server mode)"
    )

    # Comparison mode fields
    mcp_server_a: MCPServerConfig | None = Field(
        default=None, description="First MCP server for comparison"
    )
    mcp_server_b: MCPServerConfig | None = Field(
        default=None, description="Second MCP server for comparison"
    )
    comparison_mode: bool = Field(default=False, description="Enable side-by-side comparison mode")

    provider: str = Field(
        default="anthropic",
        description="Model provider (currently only anthropic is supported)",
    )

    agent_harness: str = Field(
        default="claude-code",
        description="Agent harness (currently only claude-code is supported)",
    )

    agent_prompt: str | None = Field(
        default=None,
        description="Custom prompt template for the agent. Use {problem_statement} placeholder.",
    )

    model: str = Field(
        default=DEFAULT_MODEL,
        description="Model ID for the selected provider",
    )

    benchmark: str = Field(
        default="swe-bench-verified",
        description="Benchmark to run (swe-bench-lite, swe-bench-verified, swe-bench-full, cybergym, mcptoolbench)",
    )

    cybergym_level: int = Field(
        default=1,
        description="CyberGym difficulty level (0-3), controls context given to agent",
    )

    sample_size: int | None = Field(
        default=None,
        description="Number of tasks to evaluate (None for full dataset)",
    )

    timeout_seconds: int = Field(
        default=300,
        description="Timeout for each task in seconds",
    )

    max_concurrent: int = Field(
        default=4,
        description="Maximum concurrent task evaluations",
    )

    max_iterations: int = Field(
        default=10,
        description="Maximum agent iterations per task",
    )

    thinking_budget: int | None = Field(
        default=None,
        description="Extended thinking token budget. Set to enable thinking mode (e.g., 10000)",
    )

    @field_validator("thinking_budget")
    @classmethod
    def validate_thinking_budget(cls, v: int | None) -> int | None:
        """Validate thinking_budget is within acceptable bounds.

        Claude API requires budget_tokens >= 1024 and < max_tokens.
        Claude Code caps thinking at 31999 tokens by default.
        """
        if v is None:
            return v
        if v < 1024:
            raise ValueError("thinking_budget must be at least 1024 tokens (Claude API minimum)")
        if v > 31999:
            raise ValueError("thinking_budget cannot exceed 31999 tokens (Claude Code maximum)")
        return v

    use_prebuilt_images: bool = Field(
        default=True,
        description="Use pre-built SWE-bench Docker images when available",
    )

    budget: float | None = Field(
        default=None,
        description="Maximum budget in USD for the evaluation (halts when reached)",
    )

    cache_enabled: bool = Field(
        default=False,
        description="Enable result caching to avoid re-running identical evaluations",
    )

    cache_dir: Path | None = Field(
        default=None,
        description="Directory to store cache files (default: ~/.cache/mcpbr)",
    )

    output_dir: str | None = Field(
        default=None,
        description="Directory for all evaluation outputs (logs, state, results). Default: .mcpbr_run_TIMESTAMP",
    )

    disable_logs: bool = Field(
        default=False,
        description="Disable detailed execution logs (logs are enabled by default to output_dir/logs/)",
    )

    filter_difficulty: list[str] | None = Field(
        default=None,
        description="Filter benchmarks by difficulty (e.g., ['easy', 'medium', 'hard'] or ['0', '1', '2', '3'] for CyberGym)",
    )

    filter_category: list[str] | None = Field(
        default=None,
        description="Filter benchmarks by category (e.g., ['browser', 'finance'] for MCPToolBench)",
    )

    filter_tags: list[str] | None = Field(
        default=None,
        description="Filter benchmarks by tags (requires all tags to match)",
    )

    enable_profiling: bool = Field(
        default=False,
        description="Enable comprehensive performance profiling (tool latency, memory, overhead)",
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in VALID_PROVIDERS:
            raise ValueError(
                f"Invalid provider: {v}. Valid providers: {', '.join(VALID_PROVIDERS)}"
            )
        return v

    @field_validator("agent_harness")
    @classmethod
    def validate_agent_harness(cls, v: str) -> str:
        if v not in VALID_HARNESSES:
            raise ValueError(
                f"Invalid agent_harness: {v}. Valid harnesses: {', '.join(VALID_HARNESSES)}"
            )
        return v

    @field_validator("benchmark")
    @classmethod
    def validate_benchmark(cls, v: str) -> str:
        if v not in VALID_BENCHMARKS:
            raise ValueError(
                f"Invalid benchmark: {v}. Valid benchmarks: {', '.join(VALID_BENCHMARKS)}"
            )
        return v

    @field_validator("cybergym_level")
    @classmethod
    def validate_cybergym_level(cls, v: int) -> int:
        if v < 0 or v > 3:
            raise ValueError("cybergym_level must be between 0 and 3")
        return v

    @model_validator(mode="after")
    def validate_model_for_provider(self) -> "HarnessConfig":
        """Validate model ID based on the provider.

        Anthropic provider accepts any model ID (direct API).
        """
        return self

    @model_validator(mode="after")
    def validate_server_config(self) -> "HarnessConfig":
        """Validate MCP server configuration consistency."""
        if self.comparison_mode:
            if not (self.mcp_server_a and self.mcp_server_b):
                raise ValueError("comparison_mode requires both mcp_server_a and mcp_server_b")
            if self.mcp_server:
                raise ValueError("comparison_mode: use mcp_server_a/b instead of mcp_server")
        else:
            if not self.mcp_server:
                raise ValueError("mcp_server required when comparison_mode is false")
            if self.mcp_server_a or self.mcp_server_b:
                raise ValueError("mcp_server_a/b only valid in comparison_mode")
        return self

    @field_validator("max_concurrent")
    @classmethod
    def validate_max_concurrent(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_concurrent must be at least 1")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 30:
            raise ValueError("timeout_seconds must be at least 30")
        return v

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("budget must be positive")
        return v


def load_config(config_path: str | Path, warn_security: bool = True) -> HarnessConfig:
    """Load configuration from a YAML file with environment variable expansion.

    Automatically loads .env file from current directory if it exists.
    Supports ${VAR} and ${VAR:-default} syntax for environment variables.
    Supports config inheritance via the 'extends' field.

    Args:
        config_path: Path to the YAML configuration file.
        warn_security: Whether to print security warnings for hardcoded secrets.

    Returns:
        Validated HarnessConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid or required environment variables are missing.
        CircularInheritanceError: If circular inheritance is detected.
        ConfigInheritanceError: If there's an error loading or merging inherited configs.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Load .env file if it exists in the current directory
    load_dotenv_file()

    # Load raw YAML with inheritance support
    raw_config: dict[str, Any] = load_config_with_inheritance(path)

    # Check for security issues before expansion
    if warn_security:
        security_warnings = validate_config_security(raw_config)
        if security_warnings:
            console = Console(stderr=True)
            console.print("[yellow]⚠ Security warnings:[/yellow]")
            for warning in security_warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            console.print()

    # Expand environment variables
    required_vars: set[str] = set()
    try:
        expanded_config = expand_env_vars(raw_config, required_vars)
    except ValueError as e:
        # Provide helpful error message for missing required variables
        raise ValueError(
            f"Configuration error: {e}\n\n"
            f"You can either:\n"
            f"1. Set the environment variable before running mcpbr\n"
            f"2. Add it to a .env file in the current directory\n"
            f"3. Provide a default value in the config: ${{{{VAR:-default}}}}"
        ) from e

    return HarnessConfig(**expanded_config)


def create_default_config() -> HarnessConfig:
    """Create a default configuration for testing."""
    return HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        provider="anthropic",
        agent_harness="claude-code",
        model=DEFAULT_MODEL,
    )
