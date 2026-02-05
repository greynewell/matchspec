"""Public Python SDK for mcpbr.

Provides a programmatic interface for running MCP server benchmarks
from Python code, without requiring the CLI.

Example usage::

    from mcpbr import MCPBenchmark, list_benchmarks, list_models

    # List available benchmarks
    for b in list_benchmarks():
        print(b["name"])

    # Create and run a benchmark
    bench = MCPBenchmark({
        "mcp_server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        },
        "benchmark": "humaneval",
        "model": "sonnet",
    })

    is_valid, errors = bench.validate()
    plan = bench.dry_run()

    # Async execution
    import asyncio
    result = asyncio.run(bench.run())
    print(result.success, result.summary)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .benchmarks import BENCHMARK_REGISTRY
from .config import VALID_PROVIDERS, HarnessConfig, load_config
from .models import SUPPORTED_MODELS, validate_model


@dataclass
class BenchmarkResult:
    """Result of a benchmark run.

    Attributes:
        success: Whether the benchmark completed successfully.
        summary: Aggregated results (e.g., pass rate, resolved count).
        tasks: Per-task results as a list of dicts.
        metadata: Run metadata (benchmark name, model, timestamps, etc.).
        total_cost: Total API cost in USD.
        total_tokens: Total tokens consumed.
        duration_seconds: Wall-clock duration of the run.
    """

    success: bool
    summary: dict[str, Any]
    tasks: list[dict[str, Any]]
    metadata: dict[str, Any]
    total_cost: float = 0.0
    total_tokens: int = 0
    duration_seconds: float = 0.0


class MCPBenchmark:
    """High-level interface for configuring and running MCP benchmarks.

    Can be initialized from a config dict, a YAML file path (str or Path),
    or an existing HarnessConfig instance.

    Args:
        config: A dict of config values, a path to a YAML config file
            (str or Path), or a HarnessConfig instance.

    Raises:
        FileNotFoundError: If a file path is given and the file does not exist.
        ValueError: If the config dict is invalid.
    """

    def __init__(self, config: dict[str, Any] | str | Path) -> None:
        if isinstance(config, HarnessConfig):
            self.config: HarnessConfig = config
        elif isinstance(config, (str, Path)):
            path = Path(config)
            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")
            self.config = load_config(path, warn_security=False)
        elif isinstance(config, dict):
            self.config = HarnessConfig(**config)
        else:
            raise TypeError(
                f"config must be a dict, str, Path, or HarnessConfig, got {type(config).__name__}"
            )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the current configuration.

        Checks that the configuration is internally consistent, the model
        is recognized, and required fields are present.

        Returns:
            A tuple of (is_valid, list_of_warnings_or_errors).
        """
        errors: list[str] = []

        # Validate model is in the supported registry
        model_valid, model_error = validate_model(self.config.model)
        if not model_valid:
            errors.append(f"Model warning: {model_error}")

        # Validate benchmark is in the registry
        if self.config.benchmark not in BENCHMARK_REGISTRY:
            errors.append(
                f"Unknown benchmark: {self.config.benchmark}. "
                f"Available: {', '.join(BENCHMARK_REGISTRY.keys())}"
            )

        # Validate provider
        if self.config.provider not in VALID_PROVIDERS:
            errors.append(
                f"Unknown provider: {self.config.provider}. Available: {', '.join(VALID_PROVIDERS)}"
            )

        is_valid = len(errors) == 0
        return is_valid, errors

    def dry_run(self) -> dict[str, Any]:
        """Generate an execution plan without running anything.

        Returns:
            A dict describing what would be executed, including benchmark,
            model, provider, MCP server config, and runtime settings.
        """
        plan: dict[str, Any] = {
            "benchmark": self.config.benchmark,
            "model": self.config.model,
            "provider": self.config.provider,
            "agent_harness": self.config.agent_harness,
            "timeout_seconds": self.config.timeout_seconds,
            "max_concurrent": self.config.max_concurrent,
            "max_iterations": self.config.max_iterations,
            "sample_size": self.config.sample_size,
        }

        # Include MCP server info
        if self.config.mcp_server:
            plan["mcp_server"] = {
                "command": self.config.mcp_server.command,
                "args": self.config.mcp_server.args,
                "name": self.config.mcp_server.name,
            }

        # Include comparison mode info if applicable
        if self.config.comparison_mode:
            plan["comparison_mode"] = True
            if self.config.mcp_server_a:
                plan["mcp_server_a"] = {
                    "command": self.config.mcp_server_a.command,
                    "args": self.config.mcp_server_a.args,
                    "name": self.config.mcp_server_a.name,
                }
            if self.config.mcp_server_b:
                plan["mcp_server_b"] = {
                    "command": self.config.mcp_server_b.command,
                    "args": self.config.mcp_server_b.args,
                    "name": self.config.mcp_server_b.name,
                }

        # Optional settings
        if self.config.budget is not None:
            plan["budget"] = self.config.budget
        if self.config.thinking_budget is not None:
            plan["thinking_budget"] = self.config.thinking_budget
        if self.config.agent_prompt is not None:
            plan["agent_prompt"] = self.config.agent_prompt

        return plan

    async def run(self, **kwargs: Any) -> BenchmarkResult:
        """Execute the benchmark.

        This is the main entry point for running a benchmark programmatically.
        It delegates to the internal _execute method, which can be overridden
        or mocked for testing.

        Args:
            **kwargs: Additional keyword arguments passed to the executor.

        Returns:
            BenchmarkResult with the evaluation results.
        """
        return await self._execute(**kwargs)

    async def _execute(self, **kwargs: Any) -> BenchmarkResult:
        """Internal execution method.

        Override or mock this method for testing. In production, this
        would orchestrate the full benchmark pipeline (task loading,
        environment creation, agent execution, evaluation).

        Args:
            **kwargs: Additional keyword arguments.

        Returns:
            BenchmarkResult with the evaluation results.

        Raises:
            NotImplementedError: Full execution pipeline is not yet
                wired into the SDK. Use the CLI for actual runs.
        """
        raise NotImplementedError(
            "Full benchmark execution via the SDK is not yet implemented. "
            "Use the `mcpbr` CLI for actual benchmark runs, or mock "
            "MCPBenchmark._execute for testing."
        )


def list_benchmarks() -> list[dict[str, str]]:
    """List all available benchmarks.

    Returns:
        A list of dicts, each containing 'name' (the benchmark identifier)
        and 'class' (the benchmark class name).
    """
    return [{"name": name, "class": cls.__name__} for name, cls in BENCHMARK_REGISTRY.items()]


def list_providers() -> list[str]:
    """List all supported model providers.

    Returns:
        A list of provider name strings.
    """
    return list(VALID_PROVIDERS)


def list_models() -> list[dict[str, str]]:
    """List all supported models with their metadata.

    Returns:
        A list of dicts, each containing 'id', 'provider',
        'display_name', 'context_window', 'supports_tools', and 'notes'.
    """
    return [
        {
            "id": info.id,
            "provider": info.provider,
            "display_name": info.display_name,
            "context_window": info.context_window,
            "supports_tools": info.supports_tools,
            "notes": info.notes,
        }
        for info in SUPPORTED_MODELS.values()
    ]


def get_version() -> str:
    """Get the current mcpbr version.

    Returns:
        The version string (e.g., '0.6.0').
    """
    return __version__
