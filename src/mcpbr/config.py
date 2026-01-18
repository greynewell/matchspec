"""Configuration models and loading for swebench-mcp."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from .models import DEFAULT_MODEL

VALID_PROVIDERS = ("anthropic",)
VALID_HARNESSES = ("claude-code",)
VALID_BENCHMARKS = ("swe-bench", "cybergym")


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

    mcp_server: MCPServerConfig = Field(description="MCP server configuration")

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
        default="swe-bench",
        description="Benchmark to run (swe-bench or cybergym)",
    )

    dataset: str | None = Field(
        default=None,
        description="HuggingFace dataset to use (optional, benchmark provides default)",
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

    use_prebuilt_images: bool = Field(
        default=True,
        description="Use pre-built SWE-bench Docker images when available",
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


def load_config(config_path: str | Path) -> HarnessConfig:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated HarnessConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw_config: dict[str, Any] = yaml.safe_load(f)

    return HarnessConfig(**raw_config)


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
