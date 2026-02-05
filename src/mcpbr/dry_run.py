"""Dry-run mode for previewing evaluations without executing them.

This module provides functionality to preview what an evaluation would do,
validate configurations, estimate costs and time, and check infrastructure
readiness -- all without making actual API calls or running tasks.

Useful for debugging configuration issues and estimating costs before
committing to a full evaluation run.
"""

import logging
import os
import shutil
from dataclasses import dataclass, field

import docker
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .benchmarks import create_benchmark
from .config import HarnessConfig
from .config_validator import ConfigValidator, ValidationResult
from .pricing import format_cost, get_model_pricing

logger = logging.getLogger(__name__)

# Historical estimates for average tokens per task by benchmark type.
# These are rough estimates based on typical evaluation runs and are used
# when no better data is available. Values represent (input_tokens, output_tokens).
_ESTIMATED_TOKENS_PER_TASK: dict[str, tuple[int, int]] = {
    "swe-bench-lite": (50_000, 10_000),
    "swe-bench-verified": (50_000, 10_000),
    "swe-bench-full": (50_000, 10_000),
    "humaneval": (5_000, 2_000),
    "mbpp": (5_000, 2_000),
    "gsm8k": (3_000, 1_000),
    "math": (5_000, 2_000),
    "truthfulqa": (2_000, 500),
    "bigbench-hard": (5_000, 2_000),
    "hellaswag": (2_000, 500),
    "arc": (3_000, 1_000),
    "apps": (10_000, 5_000),
    "codecontests": (15_000, 8_000),
    "bigcodebench": (10_000, 5_000),
    "leetcode": (10_000, 5_000),
    "codereval": (20_000, 8_000),
    "repoqa": (30_000, 5_000),
    "toolbench": (10_000, 5_000),
    "aider-polyglot": (30_000, 10_000),
    "terminalbench": (20_000, 8_000),
    "gaia": (15_000, 5_000),
    "agentbench": (20_000, 8_000),
    "webarena": (20_000, 8_000),
    "mlagentbench": (25_000, 10_000),
    "intercode": (15_000, 5_000),
    "cybergym": (30_000, 10_000),
    "mcptoolbench": (10_000, 5_000),
    "custom": (10_000, 5_000),
    "mmmu": (5_000, 2_000),
    "longbench": (30_000, 5_000),
    "adversarial": (10_000, 5_000),
}

# Historical average minutes per task (wall-clock time).
# Accounts for Docker setup, agent execution, and evaluation.
_ESTIMATED_MINUTES_PER_TASK: dict[str, float] = {
    "swe-bench-lite": 8.0,
    "swe-bench-verified": 8.0,
    "swe-bench-full": 8.0,
    "humaneval": 2.0,
    "mbpp": 2.0,
    "gsm8k": 1.0,
    "math": 2.0,
    "truthfulqa": 0.5,
    "bigbench-hard": 1.5,
    "hellaswag": 0.5,
    "arc": 1.0,
    "apps": 4.0,
    "codecontests": 6.0,
    "bigcodebench": 4.0,
    "leetcode": 4.0,
    "codereval": 6.0,
    "repoqa": 5.0,
    "toolbench": 3.0,
    "aider-polyglot": 7.0,
    "terminalbench": 5.0,
    "gaia": 5.0,
    "agentbench": 6.0,
    "webarena": 6.0,
    "mlagentbench": 7.0,
    "intercode": 4.0,
    "cybergym": 8.0,
    "mcptoolbench": 3.0,
    "custom": 3.0,
    "mmmu": 2.0,
    "longbench": 5.0,
    "adversarial": 3.0,
}


@dataclass
class DryRunResult:
    """Result of a dry-run evaluation preview.

    Contains all information about what an evaluation would do, including
    task details, cost estimates, configuration validation, and infrastructure
    readiness checks.

    Attributes:
        benchmark_name: Name of the benchmark to run.
        total_tasks: Total number of tasks that would be executed.
        task_ids: List of task IDs that would be executed.
        estimated_cost_usd: Estimated total cost in USD based on model pricing.
        estimated_time_minutes: Estimated total wall-clock time in minutes.
        config_valid: Whether the configuration passed validation.
        config_errors: List of configuration validation error messages.
        docker_available: Whether Docker is available and running.
        mcp_servers_reachable: Mapping of MCP server names to reachability status.
        warnings: List of warning messages about the evaluation.
    """

    benchmark_name: str
    total_tasks: int
    task_ids: list[str]
    estimated_cost_usd: float | None
    estimated_time_minutes: float | None
    config_valid: bool
    config_errors: list[str]
    docker_available: bool
    mcp_servers_reachable: dict[str, bool]
    warnings: list[str] = field(default_factory=list)


def _check_docker_available() -> bool:
    """Check whether Docker is available and running.

    Returns:
        True if Docker daemon is reachable, False otherwise.
    """
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _check_mcp_server_reachable(command: str) -> bool:
    """Check whether an MCP server command is available in PATH.

    This checks that the command is installed and executable, which is a
    necessary prerequisite for the MCP server to be reachable at runtime.

    Args:
        command: The MCP server command to check (e.g., 'npx', 'uvx').

    Returns:
        True if the command is found in PATH, False otherwise.
    """
    return shutil.which(command) is not None


def _validate_config_from_object(config: HarnessConfig) -> ValidationResult:
    """Validate a HarnessConfig object using the config validator.

    Since ConfigValidator works on files, we perform structural validation
    directly on the config object instead.

    Args:
        config: The harness configuration to validate.

    Returns:
        ValidationResult with errors and warnings.
    """
    validator = ConfigValidator()

    # Validate API key (Anthropic provider)
    if config.provider == "anthropic":
        validator._validate_api_key()

    # If we have no errors from the validator and the config object was
    # successfully created (Pydantic validated), it is valid.
    return ValidationResult(
        valid=not validator.has_errors,
        errors=validator.errors,
        warnings=validator.warnings,
    )


def _estimate_cost(
    model_id: str,
    benchmark_name: str,
    num_tasks: int,
) -> float | None:
    """Estimate the cost of running an evaluation based on model pricing.

    Uses historical token usage estimates per benchmark type and the model's
    pricing to compute an approximate total cost.

    Args:
        model_id: The model identifier for pricing lookup.
        benchmark_name: The benchmark name for token estimation.
        num_tasks: The number of tasks to estimate for.

    Returns:
        Estimated cost in USD, or None if pricing is unavailable.
    """
    pricing = get_model_pricing(model_id)
    if pricing is None:
        return None

    input_tokens, output_tokens = _ESTIMATED_TOKENS_PER_TASK.get(benchmark_name, (10_000, 5_000))

    # Calculate per-task cost
    input_cost = (input_tokens / 1_000_000) * pricing.input_price_per_mtok
    output_cost = (output_tokens / 1_000_000) * pricing.output_price_per_mtok
    per_task_cost = input_cost + output_cost

    return per_task_cost * num_tasks


def _estimate_time(
    benchmark_name: str,
    num_tasks: int,
    max_concurrent: int,
    timeout_seconds: int,
) -> float:
    """Estimate the wall-clock time for running an evaluation.

    Uses historical per-task time estimates and accounts for concurrency.
    The estimate is capped by the configured timeout per task.

    Args:
        benchmark_name: The benchmark name for time estimation.
        num_tasks: The number of tasks to run.
        max_concurrent: Maximum concurrent tasks.
        timeout_seconds: Configured timeout per task in seconds.

    Returns:
        Estimated wall-clock time in minutes.
    """
    per_task_minutes = _ESTIMATED_MINUTES_PER_TASK.get(benchmark_name, 3.0)

    # Cap per-task time at the configured timeout
    timeout_minutes = timeout_seconds / 60.0
    per_task_minutes = min(per_task_minutes, timeout_minutes)

    # Account for concurrency: tasks run in batches of max_concurrent
    effective_concurrency = max(1, min(max_concurrent, num_tasks)) if num_tasks > 0 else 1
    total_minutes = (num_tasks / effective_concurrency) * per_task_minutes

    return total_minutes


async def dry_run(config: HarnessConfig, verbosity: int = 0) -> DryRunResult:
    """Preview what an evaluation would do without executing it.

    Loads the benchmark tasks, validates the configuration, checks Docker
    availability, checks MCP server reachability, and estimates cost and
    time. Does NOT make any API calls or run any tasks.

    Args:
        config: The harness configuration to preview.
        verbosity: Verbosity level (0=minimal, 1=summary, 2=detailed).

    Returns:
        DryRunResult containing all preview information.
    """
    warnings: list[str] = []
    config_errors: list[str] = []
    task_ids: list[str] = []
    total_tasks = 0

    # 1. Validate configuration
    validation_result = _validate_config_from_object(config)
    config_valid = validation_result.valid
    for error in validation_result.errors:
        config_errors.append(f"{error.field}: {error.error}")
    for warning in validation_result.warnings:
        warnings.append(f"Config warning ({warning.field}): {warning.error}")

    # 2. Load benchmark tasks
    benchmark_name = config.benchmark
    try:
        benchmark_kwargs = {}
        if config.benchmark == "cybergym":
            benchmark_kwargs["level"] = config.cybergym_level

        benchmark = create_benchmark(config.benchmark, **benchmark_kwargs)
        tasks = benchmark.load_tasks(
            sample_size=config.sample_size,
            filter_difficulty=config.filter_difficulty,
            filter_category=config.filter_category,
            filter_tags=config.filter_tags,
        )
        total_tasks = len(tasks)
        task_ids = [t.get("instance_id", f"task_{i}") for i, t in enumerate(tasks)]
    except Exception as e:
        warnings.append(f"Failed to load benchmark tasks: {e}")
        total_tasks = config.sample_size if config.sample_size else 0

    # 3. Check Docker availability
    docker_available = _check_docker_available()
    if not docker_available:
        warnings.append(
            "Docker is not available. Evaluation requires Docker to create "
            "isolated task environments."
        )

    # 4. Check MCP server reachability
    mcp_servers_reachable: dict[str, bool] = {}
    if config.comparison_mode:
        if config.mcp_server_a and config.mcp_server_a.command:
            name_a = config.mcp_server_a.name or "mcp_server_a"
            reachable = _check_mcp_server_reachable(config.mcp_server_a.command)
            mcp_servers_reachable[name_a] = reachable
            if not reachable:
                warnings.append(
                    f"MCP server A command '{config.mcp_server_a.command}' not found in PATH."
                )
        if config.mcp_server_b and config.mcp_server_b.command:
            name_b = config.mcp_server_b.name or "mcp_server_b"
            reachable = _check_mcp_server_reachable(config.mcp_server_b.command)
            mcp_servers_reachable[name_b] = reachable
            if not reachable:
                warnings.append(
                    f"MCP server B command '{config.mcp_server_b.command}' not found in PATH."
                )
    elif config.mcp_server and config.mcp_server.command:
        name = config.mcp_server.name or "mcp_server"
        reachable = _check_mcp_server_reachable(config.mcp_server.command)
        mcp_servers_reachable[name] = reachable
        if not reachable:
            warnings.append(f"MCP server command '{config.mcp_server.command}' not found in PATH.")

    # 5. Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        warnings.append(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Evaluation requires a valid API key."
        )

    # 6. Estimate cost
    estimated_cost = _estimate_cost(config.model, benchmark_name, total_tasks)
    if estimated_cost is None:
        warnings.append(
            f"Could not estimate cost: pricing unavailable for model '{config.model}'. "
            f"Cost estimation uses historical token usage averages and may vary."
        )
    else:
        # Add a note about estimation accuracy
        if verbosity >= 1:
            warnings.append(
                "Cost estimate is based on historical averages and actual costs may vary "
                "significantly depending on task complexity and agent behavior."
            )

    # 7. Estimate time
    estimated_time = _estimate_time(
        benchmark_name,
        total_tasks,
        config.max_concurrent,
        config.timeout_seconds,
    )

    # 8. Budget warning
    if config.budget is not None and estimated_cost is not None:
        if estimated_cost > config.budget:
            warnings.append(
                f"Estimated cost ({format_cost(estimated_cost)}) exceeds budget "
                f"({format_cost(config.budget)}). Evaluation may be halted early."
            )

    return DryRunResult(
        benchmark_name=benchmark_name,
        total_tasks=total_tasks,
        task_ids=task_ids,
        estimated_cost_usd=estimated_cost,
        estimated_time_minutes=estimated_time,
        config_valid=config_valid,
        config_errors=config_errors,
        docker_available=docker_available,
        mcp_servers_reachable=mcp_servers_reachable,
        warnings=warnings,
    )


def format_dry_run_report(result: DryRunResult) -> None:
    """Print a rich-formatted dry-run report to the console.

    Displays a comprehensive overview of what the evaluation would do,
    including task details, cost estimates, infrastructure readiness,
    and any warnings or errors.

    Args:
        result: The DryRunResult to format and display.
    """
    console = Console()

    # Header
    console.print()
    console.print(
        Panel(
            "[bold]Dry Run Report[/bold]\n[dim]Preview of evaluation without executing tasks[/dim]",
            border_style="cyan",
        )
    )

    # Benchmark & Tasks table
    task_table = Table(
        title="Evaluation Overview",
        show_header=True,
        header_style="bold cyan",
    )
    task_table.add_column("Property", style="bold")
    task_table.add_column("Value")

    task_table.add_row("Benchmark", result.benchmark_name)
    task_table.add_row("Total Tasks", str(result.total_tasks))
    task_table.add_row(
        "Estimated Cost",
        format_cost(result.estimated_cost_usd) if result.estimated_cost_usd is not None else "N/A",
    )

    if result.estimated_time_minutes is not None:
        hours = int(result.estimated_time_minutes // 60)
        minutes = int(result.estimated_time_minutes % 60)
        if hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"
        task_table.add_row("Estimated Time", time_str)
    else:
        task_table.add_row("Estimated Time", "N/A")

    console.print()
    console.print(task_table)

    # Task IDs (show first 10, then summarize)
    if result.task_ids:
        console.print()
        console.print("[bold]Task IDs:[/bold]")
        display_count = min(10, len(result.task_ids))
        for task_id in result.task_ids[:display_count]:
            console.print(f"  [dim]-[/dim] {task_id}")
        if len(result.task_ids) > display_count:
            console.print(f"  [dim]... and {len(result.task_ids) - display_count} more[/dim]")

    # Infrastructure Readiness table
    infra_table = Table(
        title="Infrastructure Readiness",
        show_header=True,
        header_style="bold cyan",
    )
    infra_table.add_column("Check", style="bold")
    infra_table.add_column("Status", justify="center")
    infra_table.add_column("Details")

    # Config validation
    if result.config_valid:
        infra_table.add_row("Configuration", "[green]PASS[/green]", "Valid")
    else:
        error_summary = "; ".join(result.config_errors[:3])
        if len(result.config_errors) > 3:
            error_summary += f" (+{len(result.config_errors) - 3} more)"
        infra_table.add_row("Configuration", "[red]FAIL[/red]", error_summary)

    # Docker
    if result.docker_available:
        infra_table.add_row("Docker", "[green]PASS[/green]", "Running")
    else:
        infra_table.add_row("Docker", "[red]FAIL[/red]", "Not available")

    # MCP servers
    for server_name, reachable in result.mcp_servers_reachable.items():
        if reachable:
            infra_table.add_row(f"MCP: {server_name}", "[green]PASS[/green]", "Command found")
        else:
            infra_table.add_row(f"MCP: {server_name}", "[red]FAIL[/red]", "Command not found")

    # API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        infra_table.add_row("API Key", "[green]PASS[/green]", f"Set ({masked})")
    else:
        infra_table.add_row("API Key", "[red]FAIL[/red]", "Not set")

    console.print()
    console.print(infra_table)

    # Warnings
    if result.warnings:
        console.print()
        console.print("[yellow bold]Warnings:[/yellow bold]")
        for warning in result.warnings:
            console.print(f"  [yellow]-[/yellow] {warning}")

    # Config errors
    if result.config_errors:
        console.print()
        console.print("[red bold]Configuration Errors:[/red bold]")
        for error in result.config_errors:
            console.print(f"  [red]-[/red] {error}")

    # Summary
    console.print()
    all_clear = (
        result.config_valid
        and result.docker_available
        and all(result.mcp_servers_reachable.values())
        and api_key is not None
    )
    if all_clear:
        console.print(
            Panel(
                "[green bold]All checks passed.[/green bold]\nThe evaluation is ready to run.",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[red bold]Some checks failed.[/red bold]\n"
                "Please resolve the issues above before running the evaluation.",
                border_style="red",
            )
        )

    console.print()
