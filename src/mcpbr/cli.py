"""Command-line interface for mcpbr."""

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import VALID_BENCHMARKS, VALID_HARNESSES, VALID_PROVIDERS, load_config
from .docker_env import cleanup_orphaned_containers, register_signal_handlers
from .harness import run_evaluation
from .harnesses import list_available_harnesses
from .models import DEFAULT_MODEL, list_supported_models
from .reporting import print_summary, save_json_results, save_markdown_report

console = Console()


class DefaultToRunGroup(click.Group):
    """Custom group that defaults to 'run' command when no subcommand given."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """If no subcommand is provided, insert 'run' as the default."""
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            return super().parse_args(ctx, args)

        # Don't default to 'run' if asking for help at the group level
        if args and args[0] in ("--help", "-h"):
            return super().parse_args(ctx, args)

        if not args or args[0].startswith("-"):
            args = ["run", *args]

        return super().parse_args(ctx, args)


@click.group(cls=DefaultToRunGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option()
def main() -> None:
    """mcpbr - Model Context Protocol Benchmark Runner.

    Evaluate MCP servers against SWE-bench tasks by comparing
    an agent with MCP tools vs a baseline without tools.

    \b
    Commands:
      run        Run benchmark evaluation (default command)
      init       Generate an example configuration file
      models     List supported models for evaluation
      providers  List available model providers
      harnesses  List available agent harnesses
      benchmarks List available benchmarks
      cleanup    Remove orphaned Docker containers

    \b
    Quick Start:
      mcpbr init -o config.yaml    # Create config
      mcpbr run -c config.yaml     # Run evaluation
      mcpbr run -c config.yaml -M  # MCP only
      mcpbr run -c config.yaml -B  # Baseline only

    \b
    Environment Variables:
      ANTHROPIC_API_KEY    Required for Anthropic API access
    """
    pass


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML configuration file",
)
@click.option(
    "--model",
    "-m",
    "model_override",
    type=str,
    default=None,
    help="Override model from config (e.g., 'claude-sonnet-4-5-20250514')",
)
@click.option(
    "--provider",
    "-p",
    "provider_override",
    type=click.Choice(VALID_PROVIDERS),
    default=None,
    help="Override provider from config",
)
@click.option(
    "--harness",
    "harness_override",
    type=click.Choice(VALID_HARNESSES),
    default=None,
    help="Override agent harness from config",
)
@click.option(
    "--benchmark",
    "-b",
    "benchmark_override",
    type=click.Choice(VALID_BENCHMARKS),
    default=None,
    help="Override benchmark from config (swe-bench or cybergym)",
)
@click.option(
    "--level",
    "level_override",
    type=click.IntRange(0, 3),
    default=None,
    help="Override CyberGym difficulty level (0-3)",
)
@click.option(
    "--sample",
    "-n",
    "sample_size",
    type=int,
    default=None,
    help="Override sample size from config",
)
@click.option(
    "--mcp-only",
    "-M",
    is_flag=True,
    help="Run only MCP evaluation (skip baseline)",
)
@click.option(
    "--baseline-only",
    "-B",
    is_flag=True,
    help="Run only baseline evaluation (skip MCP)",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save JSON results",
)
@click.option(
    "--report",
    "-r",
    "report_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save Markdown report",
)
@click.option(
    "--verbose",
    "-v",
    "verbosity",
    count=True,
    help="Verbose output (-v summary, -vv detailed)",
)
@click.option(
    "--log-file",
    "-l",
    "log_file_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to write raw JSON log output (single file for all tasks)",
)
@click.option(
    "--log-dir",
    "log_dir_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory to write per-instance JSON log files",
)
@click.option(
    "--task",
    "-t",
    "task_ids",
    multiple=True,
    help="Run specific task(s) by instance_id (can be repeated)",
)
@click.option(
    "--prompt",
    "prompt_override",
    type=str,
    default=None,
    help="Override agent prompt. Use {problem_statement} placeholder.",
)
@click.option(
    "--no-prebuilt",
    is_flag=True,
    help="Disable pre-built SWE-bench images (build from scratch)",
)
def run(
    config_path: Path,
    model_override: str | None,
    provider_override: str | None,
    harness_override: str | None,
    benchmark_override: str | None,
    level_override: int | None,
    sample_size: int | None,
    mcp_only: bool,
    baseline_only: bool,
    output_path: Path | None,
    report_path: Path | None,
    verbosity: int,
    log_file_path: Path | None,
    log_dir_path: Path | None,
    task_ids: tuple[str, ...],
    prompt_override: str | None,
    no_prebuilt: bool,
) -> None:
    """Run SWE-bench evaluation with the configured MCP server.

    \b
    Examples:
      mcpbr run -c config.yaml           # Full evaluation
      mcpbr run -c config.yaml -M        # MCP only
      mcpbr run -c config.yaml -B        # Baseline only
      mcpbr run -c config.yaml -n 10     # Sample 10 tasks
      mcpbr run -c config.yaml -v        # Verbose output
      mcpbr run -c config.yaml -o out.json -r report.md
    """
    register_signal_handlers()

    if mcp_only and baseline_only:
        console.print("[red]Error: Cannot specify both --mcp-only and --baseline-only[/red]")
        sys.exit(1)

    try:
        config = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

    if model_override:
        config.model = model_override

    if provider_override:
        config.provider = provider_override

    if harness_override:
        config.agent_harness = harness_override

    if benchmark_override:
        config.benchmark = benchmark_override

    if level_override is not None:
        config.cybergym_level = level_override

    if sample_size is not None:
        config.sample_size = sample_size

    if prompt_override:
        config.agent_prompt = prompt_override

    if no_prebuilt:
        config.use_prebuilt_images = False

    run_mcp = not baseline_only
    run_baseline = not mcp_only
    verbose = verbosity > 0

    console.print("[bold]mcpbr Evaluation[/bold]")
    console.print(f"  Config: {config_path}")
    console.print(f"  Provider: {config.provider}")
    console.print(f"  Model: {config.model}")
    console.print(f"  Agent Harness: {config.agent_harness}")
    console.print(f"  Benchmark: {config.benchmark}")
    if config.benchmark == "cybergym":
        console.print(f"  CyberGym Level: {config.cybergym_level}")
    dataset_display = config.dataset if config.dataset else "default"
    console.print(f"  Dataset: {dataset_display}")
    console.print(f"  Sample size: {config.sample_size or 'full'}")
    console.print(f"  Run MCP: {run_mcp}, Run Baseline: {run_baseline}")
    console.print(f"  Pre-built images: {config.use_prebuilt_images}")
    if log_file_path:
        console.print(f"  Log file: {log_file_path}")
    if log_dir_path:
        console.print(f"  Log dir: {log_dir_path}")
    console.print()

    log_file = None
    try:
        if log_file_path:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_file_path, "w")

        if log_dir_path:
            log_dir_path.mkdir(parents=True, exist_ok=True)

        results = asyncio.run(
            run_evaluation(
                config=config,
                run_mcp=run_mcp,
                run_baseline=run_baseline,
                verbose=verbose,
                verbosity=verbosity,
                log_file=log_file,
                log_dir=log_dir_path,
                task_ids=list(task_ids) if task_ids else None,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Evaluation interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Evaluation failed: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)
    finally:
        if log_file:
            log_file.close()

    print_summary(results, console)

    if output_path:
        save_json_results(results, output_path)
        console.print(f"\n[green]Results saved to {output_path}[/green]")

    if report_path:
        save_markdown_report(results, report_path)
        console.print(f"[green]Report saved to {report_path}[/green]")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("mcpbr.yaml"),
    help="Path to write example config (default: mcpbr.yaml)",
)
def init(output_path: Path) -> None:
    """Generate an example configuration file.

    \b
    Examples:
      mcpbr init                    # Creates mcpbr.yaml
      mcpbr init -o my-config.yaml  # Custom filename
    """
    if output_path.exists():
        console.print(f"[red]Error: {output_path} already exists[/red]")
        sys.exit(1)

    example_config = f"""\
# mcpbr - Model Context Protocol Benchmark Runner
#
# Configure your MCP server and evaluation parameters.
# Requires ANTHROPIC_API_KEY environment variable.

mcp_server:
  # Command to start the MCP server
  command: "npx"

  # Arguments for the command
  # Use {{workdir}} as placeholder for task working directory
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{{workdir}}"

  # Environment variables (optional)
  env: {{}}

# Model provider (currently only anthropic is supported)
provider: "anthropic"

# Agent harness (currently only claude-code is supported)
agent_harness: "claude-code"

# Custom agent prompt (optional)
# Use {{problem_statement}} as placeholder for the issue text
# agent_prompt: |
#   Fix the following bug in this repository:
#
#   {{problem_statement}}
#
#   Make the minimal changes necessary to fix the issue.

# Model ID (Anthropic model identifier)
model: "{DEFAULT_MODEL}"

# Benchmark to run (swe-bench or cybergym)
benchmark: "swe-bench"

# HuggingFace dataset (optional, benchmark provides default)
# dataset: "SWE-bench/SWE-bench_Lite"

# CyberGym difficulty level (0-3, only used for cybergym benchmark)
# Higher levels provide more context to the agent
cybergym_level: 1

# Number of tasks (null for full dataset)
sample_size: 10

# Timeout per task in seconds
timeout_seconds: 300

# Maximum parallel evaluations
max_concurrent: 4

# Maximum agent iterations per task
max_iterations: 10
"""
    output_path.write_text(example_config)
    console.print(f"[green]Created example config at {output_path}[/green]")
    console.print("\nEdit the config file and run:")
    console.print(f"  mcpbr run --config {output_path}")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
def models() -> None:
    """List supported Anthropic models for evaluation.

    \b
    Examples:
      mcpbr models  # List all supported models
    """
    all_models = list_supported_models()

    if not all_models:
        console.print("[yellow]No supported models found[/yellow]")
        return

    table = Table(title="Supported Anthropic Models")
    table.add_column("Model ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Context", justify="right")

    for model in all_models:
        context_str = f"{model.context_window:,}"
        table.add_row(
            model.id,
            model.display_name,
            context_str,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(all_models)} models[/dim]")
    console.print("[dim]Use --model flag with 'run' command to select a model[/dim]")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
def harnesses() -> None:
    """List available agent harnesses.

    Shows all supported agent backends and their requirements.
    Currently only claude-code is supported.
    """
    console.print("[bold]Available Agent Harnesses[/bold]\n")

    available = list_available_harnesses()
    for harness in available:
        label = f"[cyan]{harness}[/cyan] (default)"
        console.print(label)
        console.print("  Shells out to Claude Code CLI with MCP server support")
        console.print("  Requires: claude CLI installed")
        console.print()


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
def providers() -> None:
    """List available model providers.

    Shows all supported LLM providers and their required environment variables.
    Currently only anthropic is supported.
    """
    console.print("[bold]Available Model Providers[/bold]\n")

    table = Table()
    table.add_column("Provider", style="cyan")
    table.add_column("Env Variable", style="yellow")
    table.add_column("Description")

    table.add_row("anthropic", "ANTHROPIC_API_KEY", "Direct Anthropic API")

    console.print(table)
    console.print("\n[dim]Set ANTHROPIC_API_KEY environment variable before running[/dim]")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
def benchmarks() -> None:
    """List available benchmarks.

    Shows all supported benchmarks and their characteristics.
    """
    console.print("[bold]Available Benchmarks[/bold]\n")

    table = Table()
    table.add_column("Benchmark", style="cyan")
    table.add_column("Description")
    table.add_column("Output Type")

    table.add_row(
        "swe-bench",
        "Software bug fixes in GitHub repositories",
        "Patch (unified diff)",
    )
    table.add_row(
        "cybergym",
        "Security vulnerability exploitation (PoC generation)",
        "Exploit code",
    )

    console.print(table)
    console.print("\n[dim]Use --benchmark flag with 'run' command to select a benchmark[/dim]")
    console.print("[dim]Example: mcpbr run -c config.yaml --benchmark cybergym --level 2[/dim]")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show containers that would be removed without removing them",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def cleanup(dry_run: bool, force: bool) -> None:
    """Remove orphaned mcpbr Docker containers.

    Finds and removes any Docker containers created by mcpbr that were
    not properly cleaned up (e.g., due to crashes or interruptions).

    \b
    Examples:
      mcpbr cleanup --dry-run  # Preview what would be removed
      mcpbr cleanup            # Remove with confirmation
      mcpbr cleanup -f         # Remove without confirmation
    """
    try:
        from docker.errors import DockerException
    except ImportError:
        console.print("[red]Error: docker package not available[/red]")
        sys.exit(1)

    try:
        containers = cleanup_orphaned_containers(dry_run=True)
    except DockerException as e:
        console.print(f"[red]Error connecting to Docker: {e}[/red]")
        console.print("[dim]Make sure Docker is running.[/dim]")
        sys.exit(1)

    if not containers:
        console.print("[green]No orphaned mcpbr containers found.[/green]")
        return

    console.print(f"[bold]Found {len(containers)} mcpbr container(s):[/bold]\n")
    for name in containers:
        console.print(f"  [cyan]{name}[/cyan]")
    console.print()

    if dry_run:
        console.print("[yellow]Dry run - no containers were removed.[/yellow]")
        return

    if not force:
        confirm = click.confirm("Remove these containers?", default=True)
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            return

    removed = cleanup_orphaned_containers(dry_run=False)
    console.print(f"[green]Removed {len(removed)} container(s).[/green]")


if __name__ == "__main__":
    main()
