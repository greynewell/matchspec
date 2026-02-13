"""Command-line interface for mcpbr."""

import asyncio
import csv
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import VALID_BENCHMARKS, VALID_HARNESSES, VALID_PROVIDERS, load_config
from .config_validator import validate_config
from .docker_env import cleanup_all_resources, register_signal_handlers
from .harness import run_evaluation
from .harnesses import list_available_harnesses
from .junit_reporter import save_junit_xml
from .models import list_supported_models
from .output_validator import validate_output_file
from .regression import (
    detect_regressions,
    format_regression_report,
    load_baseline_results,
    send_notification,
)
from .reporting import (
    print_summary,
    save_json_results,
    save_markdown_report,
    save_xml_results,
    save_yaml_results,
)
from .state_tracker import StateTracker

console = Console()


class DefaultToRunGroup(click.Group):
    """Custom group that defaults to 'run' command when no subcommand given."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """If no subcommand is provided, insert 'run' as the default."""
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            return super().parse_args(ctx, args)

        # Don't default to 'run' if asking for help or version at the group level
        if args and args[0] in ("--help", "-h", "--version"):
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
      compare    Compare results from multiple runs
      analytics  Historical tracking and analysis
      init       Generate a configuration file from a template
      templates  List available configuration templates
      config     Configuration management commands
      models     List supported models for evaluation
      providers  List available model providers
      harnesses  List available agent harnesses
      benchmarks List available benchmarks
      state      View or manage evaluation state
      cleanup    Remove orphaned Docker containers

    \b
    Quick Start:
      mcpbr init -o config.yaml    # Create config
      mcpbr init -i                # Interactive config
      mcpbr templates              # List templates
      mcpbr run -c config.yaml     # Run evaluation
      mcpbr run -c config.yaml -M  # MCP only
      mcpbr run -c config.yaml -B  # Baseline only

    \b
    Reports:
      mcpbr run -c config.yaml --output-html report.html
      mcpbr run -c config.yaml --output-markdown report.md
      mcpbr run -c config.yaml --output-pdf report.pdf
      mcpbr compare run1.json run2.json --output-html comparison.html

    \b
    Analytics:
      mcpbr analytics store results.json           # Store in database
      mcpbr analytics trends --metric resolution_rate
      mcpbr analytics leaderboard
      mcpbr analytics regression --baseline v1.json --current v2.json

    \b
    Incremental Evaluation:
      mcpbr run -c config.yaml --retry-failed  # Re-run failed tasks
      mcpbr state                              # View current state
      mcpbr state --clear                      # Clear state

    \b
    Environment Variables:
      ANTHROPIC_API_KEY    Required for Anthropic API access
    """
    pass


def _build_results_dict(results):
    """Convert evaluation results to a plain dict for reports and integrations."""
    if isinstance(results, dict):
        return results
    if hasattr(results, "to_dict"):
        return results.to_dict()
    if hasattr(results, "__dict__"):
        return {
            "metadata": results.metadata,
            "summary": results.summary,
            "tasks": [
                {
                    "instance_id": t.instance_id,
                    "mcp": t.mcp,
                    "baseline": t.baseline,
                }
                for t in results.tasks
            ],
        }
    return json.loads(json.dumps(results, default=str))


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "-c",
    "config_path",
    default="mcpbr.yaml",
    type=click.Path(path_type=Path),
    help="Path to YAML configuration file (default: mcpbr.yaml, auto-created if missing)",
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
    help="Override benchmark from config (use 'mcpbr benchmarks' to list all)",
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
    "--output-junit",
    "junit_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save JUnit XML report (for CI/CD integration)",
)
@click.option(
    "--output-xml",
    "xml_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save XML results",
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
    help="Directory to write per-instance JSON log files (default: .mcpbr_state/logs/)",
)
@click.option(
    "--disable-logs",
    is_flag=True,
    help="Disable detailed execution logs (overrides default and config)",
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
@click.option(
    "--output-html",
    "html_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save interactive HTML report with charts",
)
@click.option(
    "--output-pdf",
    "pdf_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save PDF report (requires weasyprint)",
)
@click.option(
    "--output-markdown",
    "enhanced_md_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save enhanced Markdown report with mermaid diagrams and badges",
)
@click.option(
    "--yaml",
    "-y",
    "yaml_output",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save YAML results (alternative to --output for YAML format)",
)
@click.option(
    "--baseline-results",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to baseline results JSON for regression detection",
)
@click.option(
    "--regression-threshold",
    type=float,
    default=0.0,
    help="Maximum acceptable regression rate (0-1). Exit with code 1 if exceeded.",
)
@click.option(
    "--slack-webhook",
    type=str,
    default=None,
    help="Slack webhook URL for regression notifications",
)
@click.option(
    "--discord-webhook",
    type=str,
    default=None,
    help="Discord webhook URL for regression notifications",
)
@click.option(
    "--email-to",
    type=str,
    default=None,
    help="Email address for regression notifications",
)
@click.option(
    "--email-from",
    type=str,
    default=None,
    help="Sender email address for notifications",
)
@click.option(
    "--smtp-host",
    type=str,
    default=None,
    help="SMTP server hostname for email notifications",
)
@click.option(
    "--smtp-port",
    type=int,
    default=587,
    help="SMTP server port (default: 587)",
)
@click.option(
    "--smtp-user",
    type=str,
    default=None,
    help="SMTP username for authentication",
)
@click.option(
    "--smtp-password",
    type=str,
    default=None,
    help="SMTP password for authentication",
)
@click.option(
    "--budget",
    type=float,
    default=None,
    help="Maximum budget in USD (halts evaluation when reached)",
)
@click.option(
    "--retry-failed",
    is_flag=True,
    help="Re-run only tasks that failed in previous evaluation",
)
@click.option(
    "--from-task",
    type=str,
    default=None,
    help="Resume evaluation from a specific task ID",
)
@click.option(
    "--reset-state",
    is_flag=True,
    help="Clear evaluation state and start fresh (ignores cached results)",
)
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory to store state files (default: .mcpbr_state/)",
)
@click.option(
    "--no-incremental",
    is_flag=True,
    help="Disable incremental evaluation (always run all tasks)",
)
@click.option(
    "--skip-health-check",
    is_flag=True,
    help="Skip MCP server pre-flight health check",
)
@click.option(
    "--skip-preflight",
    is_flag=True,
    help="Skip comprehensive pre-flight validation (use with caution)",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory for all outputs (logs, state, results). Default: .mcpbr_run_TIMESTAMP",
)
@click.option(
    "--trial-mode",
    is_flag=True,
    help="Enable trial mode: isolated state, no caching (for repeated experiments)",
)
@click.option(
    "--filter-difficulty",
    multiple=True,
    help="Filter benchmarks by difficulty (can be specified multiple times, e.g., --filter-difficulty easy --filter-difficulty medium)",
)
@click.option(
    "--filter-category",
    multiple=True,
    help="Filter benchmarks by category (can be specified multiple times, e.g., --filter-category browser --filter-category finance)",
)
@click.option(
    "--filter-tags",
    multiple=True,
    help="Filter benchmarks by tags (can be specified multiple times, requires all tags to match)",
)
@click.option(
    "--profile",
    is_flag=True,
    help="Enable comprehensive performance profiling (tool latency, memory, overhead)",
)
@click.option(
    "--sampling-strategy",
    type=click.Choice(["sequential", "random", "stratified"]),
    default=None,
    help="Sampling strategy for task selection.",
)
@click.option(
    "--random-seed", type=int, default=None, help="Random seed for reproducible sampling."
)
@click.option(
    "--stratify-field",
    type=str,
    default=None,
    help="Field to stratify by (requires --sampling-strategy stratified).",
)
@click.option(
    "--notify-slack", type=str, default=None, help="Slack webhook URL for completion notifications."
)
@click.option(
    "--notify-discord",
    type=str,
    default=None,
    help="Discord webhook URL for completion notifications.",
)
@click.option("--notify-email", type=str, default=None, help="Email config JSON string.")
@click.option(
    "--slack-bot-token", type=str, default=None, help="Slack bot token for file uploads (xoxb-...)."
)
@click.option("--slack-channel", type=str, default=None, help="Slack channel ID for file uploads.")
@click.option(
    "--github-token",
    type=str,
    default=None,
    help="GitHub token for creating Gist reports in notifications.",
)
@click.option(
    "--upload-to",
    type=str,
    default=None,
    help="Upload results to cloud storage. Format: 's3://bucket', 'gs://bucket', 'az://account/container'.",
)
@click.option("--wandb/--no-wandb", default=None, help="Enable/disable W&B logging.")
@click.option("--wandb-project", type=str, default=None, help="W&B project name.")
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
    html_path: Path | None,
    pdf_path: Path | None,
    enhanced_md_path: Path | None,
    junit_path: Path | None,
    xml_path: Path | None,
    verbosity: int,
    log_file_path: Path | None,
    log_dir_path: Path | None,
    disable_logs: bool,
    task_ids: tuple[str, ...],
    prompt_override: str | None,
    no_prebuilt: bool,
    yaml_output: Path | None,
    baseline_results: Path | None,
    regression_threshold: float,
    slack_webhook: str | None,
    discord_webhook: str | None,
    email_to: str | None,
    email_from: str | None,
    smtp_host: str | None,
    smtp_port: int,
    smtp_user: str | None,
    smtp_password: str | None,
    budget: float | None,
    retry_failed: bool,
    from_task: str | None,
    reset_state: bool,
    state_dir: Path | None,
    no_incremental: bool,
    skip_health_check: bool,
    skip_preflight: bool,
    output_dir: Path | None,
    trial_mode: bool,
    filter_difficulty: tuple[str, ...],
    filter_category: tuple[str, ...],
    filter_tags: tuple[str, ...],
    profile: bool,
    sampling_strategy: str | None,
    random_seed: int | None,
    stratify_field: str | None,
    notify_slack: str | None,
    notify_discord: str | None,
    notify_email: str | None,
    slack_bot_token: str | None,
    slack_channel: str | None,
    github_token: str | None,
    upload_to: str | None,
    wandb: bool | None,
    wandb_project: str | None,
) -> None:
    """Run benchmark evaluation with the configured MCP server.

    \b
    Examples:
      mcpbr run -c config.yaml                    # Full evaluation (defaults to swe-bench-verified)
      mcpbr run -c config.yaml -M                 # MCP only
      mcpbr run -c config.yaml -B                 # Baseline only
      mcpbr run -c config.yaml -n 10              # Sample 10 tasks
      mcpbr run -c config.yaml -b swe-bench-lite  # Use Lite benchmark (300 tasks)
      mcpbr run -c config.yaml -v                 # Verbose output
      mcpbr run -c config.yaml -o out.json -r report.md
      mcpbr benchmarks                            # List all available benchmarks

    \b
    Incremental Evaluation:
      mcpbr run -c config.yaml --retry-failed     # Re-run only failed tasks
      mcpbr run -c config.yaml --from-task ID     # Resume from specific task
      mcpbr run -c config.yaml --reset-state      # Clear state and start fresh
      mcpbr run -c config.yaml --no-incremental   # Disable caching

    \b
    Trial Mode (for repeated experiments):
      mcpbr run -c config.yaml --trial-mode -o trial_1.json
      for i in {1..5}; do mcpbr run -c config.yaml --trial-mode -o trial_${i}.json; done

    \b
    Regression Detection:
      mcpbr run -c config.yaml --baseline-results baseline.json
      mcpbr run -c config.yaml --baseline-results baseline.json --regression-threshold 0.1
      mcpbr run -c config.yaml --baseline-results baseline.json --slack-webhook https://...
      mcpbr run -c config.yaml --baseline-results baseline.json --discord-webhook https://...

    \b
    Exit Codes:
      0   Success (at least one task resolved)
      1   Fatal error (invalid config, Docker unavailable, crash)
      2   No resolutions (evaluation ran but 0% success)
      3   Nothing evaluated (all tasks cached/skipped)
      130 Interrupted by user (Ctrl+C)
    """
    register_signal_handlers()

    if mcp_only and baseline_only:
        console.print("[red]Error: Cannot specify both --mcp-only and --baseline-only[/red]")
        sys.exit(1)

    # Auto-init: Create default config if it doesn't exist
    if not config_path.exists():
        from .templates import generate_config_yaml, get_template

        console.print(f"[yellow]Config file not found: {config_path}[/yellow]")
        console.print("[cyan]Creating default configuration...[/cyan]")

        template = get_template("filesystem")
        if not template:
            console.print("[red]Error: Could not load default template[/red]")
            sys.exit(1)

        config_yaml = generate_config_yaml(template)

        # Create parent directories if they don't exist
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(config_yaml)
            console.print(f"[green]✓ Created {config_path}[/green]")
            console.print("[dim]Edit this file to customize your MCP server configuration[/dim]\n")
        except OSError as e:
            console.print(f"[red]Error: Could not create config file: {e}[/red]")
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

    if budget is not None:
        if budget <= 0:
            console.print("[red]Error: Budget must be positive[/red]")
            sys.exit(1)
        config.budget = budget

    # Handle trial mode
    if trial_mode:
        # Override state settings for clean trials
        no_incremental = True

        # Generate unique state directory with microseconds for uniqueness
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        state_dir = Path(f".mcpbr_trial_{timestamp}")

        console.print("[cyan]Trial mode enabled:[/cyan]")
        console.print("  • State caching disabled")
        console.print(f"  • Isolated state dir: {state_dir}")
        console.print("  • Fresh evaluation guaranteed")
        console.print()

    # Apply filter overrides
    if filter_difficulty:
        config.filter_difficulty = list(filter_difficulty)

    if filter_category:
        config.filter_category = list(filter_category)

    if filter_tags:
        config.filter_tags = list(filter_tags)

    if profile:
        config.enable_profiling = True

    if sampling_strategy:
        config.sampling_strategy = sampling_strategy
    if random_seed is not None:
        config.random_seed = random_seed
    if stratify_field:
        config.stratify_field = stratify_field
    if notify_slack:
        config.notify_slack_webhook = notify_slack
    if notify_discord:
        config.notify_discord_webhook = notify_discord
    if notify_email:
        try:
            config.notify_email = json.loads(notify_email)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error: --notify-email must be valid JSON: {e}[/red]")
            sys.exit(1)
    if slack_bot_token:
        config.slack_bot_token = slack_bot_token
    if slack_channel:
        config.slack_channel = slack_channel
    if github_token:
        config.github_token = github_token
    if wandb is not None:
        config.wandb_enabled = wandb
    if wandb_project:
        config.wandb_project = wandb_project

    # Determine output directory AFTER all CLI overrides are applied
    import shutil
    from datetime import datetime

    if output_dir:
        # CLI flag takes precedence
        final_output_dir = output_dir
    elif config.output_dir:
        # Config setting
        final_output_dir = Path(config.output_dir)
    else:
        # Default: timestamped directory with microseconds for uniqueness.
        # Second-level precision causes collisions when multiple runs launch
        # simultaneously, corrupting shared state and results.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        final_output_dir = Path(f".mcpbr_run_{timestamp}")

    # Override state_dir to use output directory if not explicitly set
    if state_dir is None:
        state_dir = final_output_dir

    # Create output directory
    final_output_dir.mkdir(parents=True, exist_ok=True)

    # Copy config file to output directory with SameFileError handling
    config_copy_path = final_output_dir / "config.yaml"
    try:
        shutil.copy2(config_path, config_copy_path)
    except shutil.SameFileError:
        # Skip copy if source and destination are the same file
        pass

    # Create README.txt in output directory with finalized config values
    readme_content = f"""This directory contains the complete output from an mcpbr evaluation run.

Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Config: {config_path.name}
Benchmark: {config.benchmark}
Model: {config.model}
Provider: {config.provider}

Files:
- config.yaml: Configuration used for this run
- evaluation_state.json: Per-task results and state
- logs/: Detailed execution traces (MCP server logs)

To analyze results:
  mcpbr state --state-dir {final_output_dir}

To archive:
  tar -czf results.tar.gz {final_output_dir.name}
"""
    (final_output_dir / "README.txt").write_text(readme_content)

    # Initialize state tracker for incremental evaluation
    state_tracker = None
    use_incremental = not no_incremental
    if use_incremental:
        state_tracker = StateTracker(state_dir=state_dir)
        if reset_state:
            console.print("[yellow]Clearing evaluation state...[/yellow]")
            state_tracker.clear_state()
        else:
            state_tracker.load_state()
            # Validate config hasn't changed
            valid, error_msg = state_tracker.validate_config(config)
            if not valid:
                console.print(f"[red]Error: {error_msg}[/red]")
                sys.exit(1)

    # Determine which tasks to run based on incremental flags.
    # CLI --task/-t flags take precedence over config file task_ids.
    selected_task_ids: list[str] | None = None
    if use_incremental and state_tracker:
        if retry_failed:
            failed_tasks = state_tracker.get_failed_tasks()
            if failed_tasks:
                selected_task_ids = failed_tasks
                console.print(f"[cyan]Retrying {len(failed_tasks)} failed tasks[/cyan]")
            else:
                console.print("[green]No failed tasks to retry[/green]")
                return
        elif from_task:
            # This will be handled in run_evaluation by filtering tasks
            selected_task_ids = None  # Let run_evaluation handle the from_task logic
        elif task_ids:
            selected_task_ids = list(task_ids)
        elif config.task_ids:
            selected_task_ids = list(config.task_ids)
    elif task_ids:
        selected_task_ids = list(task_ids)
    elif config.task_ids:
        selected_task_ids = list(config.task_ids)

    run_mcp = not baseline_only
    run_baseline = not mcp_only
    verbose = verbosity > 0

    # Run comprehensive pre-flight validation
    if not skip_preflight:
        from .preflight import display_preflight_results, run_comprehensive_preflight

        checks, failures = run_comprehensive_preflight(config, config_path)
        display_preflight_results(checks, failures)

        if failures:
            console.print(
                "[yellow]Use --skip-preflight to proceed anyway (not recommended)[/yellow]"
            )
            sys.exit(1)
    elif not skip_health_check and run_mcp:
        # Fallback to old MCP-only check if pre-flight is skipped but health check is not
        from .smoke_test import run_mcp_preflight_check

        success, error_msg = asyncio.run(run_mcp_preflight_check(config_path))
        if not success:
            console.print(
                "\n[yellow]Use --skip-health-check to proceed anyway (not recommended)[/yellow]"
            )
            sys.exit(1)
        console.print()

    # Enable default logging if not explicitly disabled
    # Priority: CLI flags > config disable_logs > defaults
    if disable_logs or config.disable_logs:
        # User explicitly disabled logs
        log_dir_path = None
        log_file_path = None
    elif not log_dir_path and not log_file_path:
        # No explicit logging specified, enable default log directory in output_dir
        log_dir_path = final_output_dir / "logs"
        console.print(f"[dim]Logging enabled (default): {log_dir_path}/[/dim]")
        console.print(
            "[dim]To disable: use --disable-logs flag or set disable_logs: true in config[/dim]"
        )
        console.print()

    console.print("[bold]mcpbr Evaluation[/bold]")
    console.print(f"  Output directory: {final_output_dir}")
    console.print(f"  Config: {config_path}")
    console.print(f"  Provider: {config.provider}")
    console.print(f"  Model: {config.model}")
    console.print(f"  Agent Harness: {config.agent_harness}")
    console.print(f"  Benchmark: {config.benchmark}")
    if config.benchmark == "cybergym":
        console.print(f"  CyberGym Level: {config.cybergym_level}")
    console.print(f"  Sample size: {config.sample_size or 'full'}")
    if selected_task_ids:
        console.print(
            f"  Task IDs: {len(selected_task_ids)} pinned ({', '.join(selected_task_ids[:3])}{'...' if len(selected_task_ids) > 3 else ''})"
        )
    console.print(f"  Run MCP: {run_mcp}, Run Baseline: {run_baseline}")
    console.print(f"  Pre-built images: {config.use_prebuilt_images}")
    infra_mode = getattr(getattr(config, "infrastructure", None), "mode", "local")
    if infra_mode != "local":
        console.print(f"  Infrastructure: {infra_mode}")
    if config.budget is not None:
        console.print(f"  Budget: ${config.budget:.2f}")
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

        if infra_mode != "local":
            from .infrastructure.manager import InfrastructureManager

            # Merge CLI-only parameters into config so they propagate to remote VMs
            if selected_task_ids:
                config.task_ids = selected_task_ids

            infra_result = asyncio.run(
                InfrastructureManager.run_with_infrastructure(
                    config=config,
                    config_path=Path(config_path),
                    output_dir=final_output_dir,
                    run_mcp=run_mcp,
                    run_baseline=run_baseline,
                )
            )
            results = infra_result["results"]
        else:
            # Enable incremental save for crash recovery
            incremental_path = final_output_dir / "incremental_results"
            results = asyncio.run(
                run_evaluation(
                    config=config,
                    run_mcp=run_mcp,
                    run_baseline=run_baseline,
                    verbose=verbose,
                    verbosity=verbosity,
                    log_file=log_file,
                    log_dir=log_dir_path,
                    task_ids=selected_task_ids,
                    state_tracker=state_tracker,
                    from_task=from_task,
                    incremental_save_path=incremental_path,
                    mcp_logs_dir=final_output_dir,
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

    # Use comparison summary if in comparison mode
    if results.summary.get("mcp_server_a"):
        from .reporting import print_comparison_summary

        print_comparison_summary(results, console)
    else:
        print_summary(results, console)

    if output_path:
        save_json_results(results, output_path)
        console.print(f"\n[green]Results saved to {output_path}[/green]")

        # Validate output file
        valid, msg = validate_output_file(output_path)
        if not valid:
            console.print(f"[red]✗ {msg}[/red]")
            console.print("[yellow]Check logs for errors during evaluation[/yellow]")
            sys.exit(4)
        console.print(f"[green]✓ Output validated: {msg}[/green]")

    if yaml_output:
        save_yaml_results(results, yaml_output)
        console.print(f"[green]YAML results saved to {yaml_output}[/green]")

        # Validate YAML output file
        valid, msg = validate_output_file(yaml_output)
        if not valid:
            console.print(f"[red]✗ {msg}[/red]")
            console.print("[yellow]Check logs for errors during evaluation[/yellow]")
            sys.exit(4)
        console.print(f"[green]✓ Output validated: {msg}[/green]")

    if report_path:
        save_markdown_report(results, report_path)
        console.print(f"[green]Report saved to {report_path}[/green]")

    if junit_path:
        save_junit_xml(results, junit_path)
        console.print(f"[green]JUnit XML saved to {junit_path}[/green]")

    if xml_path:
        save_xml_results(results, xml_path)
        console.print(f"[green]XML results saved to {xml_path}[/green]")

    # Build results_dict once for reports and W&B
    results_dict = None

    # Enhanced report generation
    if html_path or pdf_path or enhanced_md_path:
        # Convert results to dict for report generators
        results_dict = _build_results_dict(results)

    if html_path:
        from .reports import HTMLReportGenerator

        generator = HTMLReportGenerator(results_dict)
        generator.save(html_path)
        console.print(f"[green]HTML report saved to {html_path}[/green]")

    if enhanced_md_path:
        from .reports import EnhancedMarkdownGenerator

        generator = EnhancedMarkdownGenerator(results_dict)
        generator.save(enhanced_md_path)
        console.print(f"[green]Enhanced Markdown report saved to {enhanced_md_path}[/green]")

    if pdf_path:
        from .reports import PDFReportGenerator

        generator = PDFReportGenerator(results_dict)
        try:
            generator.save_pdf(pdf_path)
            console.print(f"[green]PDF report saved to {pdf_path}[/green]")
        except ImportError:
            # Fall back to HTML if weasyprint not available
            html_fallback = pdf_path.with_suffix(".html")
            generator.save_html(html_fallback)
            console.print(
                f"[yellow]weasyprint not installed — saved print-ready HTML to {html_fallback}[/yellow]"
            )
            console.print("[dim]Install weasyprint for PDF: pip install weasyprint[/dim]")

    # Cloud storage upload
    cloud_cfg = upload_to or getattr(config, "cloud_storage", None)
    if cloud_cfg:
        try:
            from .storage.cloud import AzureBlobStorage, GCSStorage, S3Storage, create_cloud_storage

            # Parse --upload-to URI or use config dict
            if isinstance(cloud_cfg, str):
                if cloud_cfg.startswith("s3://"):
                    bucket = cloud_cfg[5:]
                    storage = S3Storage(bucket=bucket)
                elif cloud_cfg.startswith("gs://"):
                    bucket = cloud_cfg[5:]
                    storage = GCSStorage(bucket=bucket)
                elif cloud_cfg.startswith("az://"):
                    parts = cloud_cfg[5:].split("/", 1)
                    account = parts[0]
                    container = parts[1] if len(parts) > 1 else "mcpbr-runs"
                    storage = AzureBlobStorage(container=container, account=account)
                else:
                    raise ValueError(
                        f"Unknown cloud storage URI: {cloud_cfg}. "
                        "Use s3://bucket, gs://bucket, or az://account/container"
                    )
            else:
                storage = create_cloud_storage(cloud_cfg)

            # Upload output directory contents if available
            run_dir = output_dir or Path(f".mcpbr_run_{config.model}")
            if run_dir.exists():
                run_id = run_dir.name
                uploaded = 0
                for f in sorted(run_dir.rglob("*")):
                    if f.is_file():
                        rel = str(f.relative_to(run_dir))
                        storage.upload(f, f"{run_id}/{rel}")
                        uploaded += 1
                console.print(
                    f"[green]Uploaded {uploaded} files to cloud storage ({type(storage).__name__})[/green]"
                )
            elif output_path and output_path.exists():
                # Fall back to uploading just the results file
                run_id = output_path.stem
                uri = storage.upload(output_path, f"{run_id}/results.json")
                console.print(f"[green]Results uploaded to {uri}[/green]")

        except Exception as e:
            console.print(f"[red]Cloud storage upload failed: {e}[/red]")
            if verbose:
                console.print_exception()

    # W&B logging (v0.10.0)
    if getattr(config, "wandb_enabled", False):
        try:
            if results_dict is None:
                results_dict = _build_results_dict(results)
            from .wandb_integration import log_evaluation

            log_evaluation(results_dict, project=getattr(config, "wandb_project", None))
        except Exception as e:
            click.echo(f"W&B logging failed: {e}", err=True)

    # Regression detection
    if baseline_results:
        console.print("\n[bold]Regression Detection[/bold]")
        try:
            baseline_data = load_baseline_results(baseline_results)

            # Convert results to dict format for comparison
            current_data = {
                "tasks": [
                    {
                        "instance_id": task.instance_id,
                        "mcp": task.mcp,
                        "baseline": task.baseline,
                    }
                    for task in results.tasks
                ]
            }

            regression_report = detect_regressions(current_data, baseline_data)

            # Print regression report
            console.print(format_regression_report(regression_report))

            # Send notifications if configured
            email_config = None
            if email_to and email_from and smtp_host:
                email_config = {
                    "smtp_host": smtp_host,
                    "smtp_port": smtp_port,
                    "from_email": email_from,
                    "to_email": email_to,
                    "smtp_user": smtp_user,
                    "smtp_password": smtp_password,
                }

            send_notification(
                regression_report,
                slack_webhook=slack_webhook,
                discord_webhook=discord_webhook,
                email_config=email_config,
            )

            # Exit with code 1 if regression threshold exceeded
            if regression_report.exceeds_threshold(regression_threshold):
                console.print(
                    f"\n[red]Regression threshold exceeded: "
                    f"{regression_report.regression_rate:.1%} > {regression_threshold:.1%}[/red]"
                )
                sys.exit(1)

        except FileNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Regression detection failed: {e}[/red]")
            if verbose:
                console.print_exception()
            sys.exit(1)

    # Determine exit code based on evaluation results
    exit_code = 0

    # Check if anything was evaluated (exit code 3)
    incremental_info = results.metadata.get("incremental", {})
    if incremental_info.get("enabled"):
        evaluated_count = incremental_info.get("evaluated_tasks", 0)
        if evaluated_count == 0:
            console.print("\n[yellow]⚠ No tasks evaluated (all cached)[/yellow]")
            console.print("[dim]Use --reset-state or --no-incremental to re-run[/dim]")
            exit_code = 3

    # Check if anything was resolved (exit code 2)
    # Only check this if we actually evaluated tasks
    if exit_code == 0:
        mcp_resolved = results.summary["mcp"]["resolved"]
        baseline_resolved = results.summary["baseline"]["resolved"]
        mcp_total = results.summary["mcp"]["total"]
        baseline_total = results.summary["baseline"]["total"]

        # Only report "no resolutions" if tasks were actually run
        # If total is 0, no tasks were run (not a failure)
        if mcp_only and mcp_total > 0 and mcp_resolved == 0:
            console.print("\n[yellow]⚠ No tasks resolved (0% success)[/yellow]")
            exit_code = 2
        elif baseline_only and baseline_total > 0 and baseline_resolved == 0:
            console.print("\n[yellow]⚠ No tasks resolved (0% success)[/yellow]")
            exit_code = 2
        elif not mcp_only and not baseline_only:
            # For full run, check if either had tasks and none were resolved
            if (
                (mcp_total > 0 or baseline_total > 0)
                and mcp_resolved == 0
                and baseline_resolved == 0
            ):
                console.print("\n[yellow]⚠ No tasks resolved by either agent (0% success)[/yellow]")
                exit_code = 2

    # Exit with determined exit code
    if exit_code != 0:
        sys.exit(exit_code)


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("mcpbr.yaml"),
    help="Path to write example config (default: mcpbr.yaml)",
)
@click.option(
    "--template",
    "-t",
    "template_id",
    type=str,
    default=None,
    help="Use a specific template (use 'mcpbr templates' to list available templates)",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Interactive mode to select template and customize values",
)
@click.option(
    "--list-templates",
    "-l",
    is_flag=True,
    help="List available templates and exit",
)
def init(
    output_path: Path, template_id: str | None, interactive: bool, list_templates: bool
) -> None:
    """Generate a configuration file from a template.

    Can use a template or create a basic example config.

    \b
    Examples:
      mcpbr init                        # Creates mcpbr.yaml with default template
      mcpbr init -o my-config.yaml      # Custom filename
      mcpbr init -t filesystem          # Use filesystem template
      mcpbr init -t cybergym-basic      # Use CyberGym template
      mcpbr init -i                     # Interactive mode
      mcpbr init -l                     # List available templates
    """
    from .templates import generate_config_yaml, get_template
    from .templates import list_templates as get_all_templates

    # Handle list templates flag
    if list_templates:
        templates = get_all_templates()
        console.print("[bold]Available Templates[/bold]\n")
        for template in templates:
            console.print(f"[cyan]{template.id}[/cyan] - {template.name}")
            console.print(f"  {template.description}")
            console.print(f"  Category: {template.category} | Tags: {', '.join(template.tags)}\n")
        return

    # Check if output file already exists
    if output_path.exists():
        console.print(f"[red]Error: {output_path} already exists[/red]")
        sys.exit(1)

    # Interactive mode
    if interactive:
        from .templates import get_templates_by_category

        console.print("[bold]Interactive Configuration Generator[/bold]\n")

        # Display templates by category
        templates_by_cat = get_templates_by_category()
        console.print("Available templates:\n")

        template_choices: list[tuple[str, str]] = []
        idx = 1
        for category, templates in templates_by_cat.items():
            console.print(f"[bold]{category}[/bold]")
            for template in templates:
                console.print(f"  [{idx}] {template.name} - {template.description}")
                template_choices.append((str(idx), template.id))
                idx += 1
            console.print()

        # Get user selection
        choice = click.prompt(
            "Select a template",
            type=click.Choice([c[0] for c in template_choices]),
            show_choices=False,
        )

        # Find the selected template
        selected_id = next(tid for num, tid in template_choices if num == choice)
        template = get_template(selected_id)

        if not template:
            console.print("[red]Error: Invalid template selection[/red]")
            sys.exit(1)

        console.print(f"\n[green]Selected template: {template.name}[/green]")

        # Ask for customizations
        custom_values = {}

        if click.confirm("\nCustomize configuration values?", default=False):
            # Sample size
            sample_size = click.prompt(
                "Sample size (number of tasks, leave empty for default)",
                type=int,
                default=template.config.get("sample_size", 10),
                show_default=True,
            )
            custom_values["sample_size"] = sample_size

            # Timeout
            timeout = click.prompt(
                "Timeout per task (seconds)",
                type=int,
                default=template.config.get("timeout_seconds", 300),
                show_default=True,
            )
            custom_values["timeout_seconds"] = timeout

            # Max concurrent
            max_concurrent = click.prompt(
                "Maximum concurrent tasks",
                type=int,
                default=template.config.get("max_concurrent", 4),
                show_default=True,
            )
            custom_values["max_concurrent"] = max_concurrent

        config_yaml = generate_config_yaml(template, custom_values)

    # Template mode
    elif template_id:
        template = get_template(template_id)
        if not template:
            console.print(f"[red]Error: Template '{template_id}' not found[/red]")
            console.print("\nAvailable templates:")
            for t in get_all_templates():
                console.print(f"  - {t.id}")
            sys.exit(1)

        console.print(f"[green]Using template: {template.name}[/green]")
        config_yaml = generate_config_yaml(template)

    # Default mode (backwards compatible)
    else:
        template = get_template("filesystem")
        if not template:
            console.print("[red]Error: Default template not found[/red]")
            sys.exit(1)
        config_yaml = generate_config_yaml(template)

    # Write config file
    output_path.write_text(config_yaml)
    console.print(f"\n[green]Created config at {output_path}[/green]")
    console.print("\nEdit the config file and run:")
    console.print(f"  mcpbr run --config {output_path}")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--category",
    "-c",
    type=str,
    default=None,
    help="Filter templates by category",
)
@click.option(
    "--tag",
    type=str,
    default=None,
    help="Filter templates by tag",
)
def templates(category: str | None, tag: str | None) -> None:
    """List available configuration templates.

    Shows pre-built templates for common MCP server scenarios.

    \b
    Examples:
      mcpbr templates                    # List all templates
      mcpbr templates -c Security        # List security templates
      mcpbr templates --tag quick        # List quick test templates
    """
    from .templates import (
        get_templates_by_category,
        get_templates_by_tag,
    )
    from .templates import (
        list_templates as get_all_templates,
    )

    # Filter templates
    if tag:
        filtered = get_templates_by_tag(tag)
        title = f"Templates with tag '{tag}'"
    elif category:
        templates_by_cat = get_templates_by_category()
        filtered = templates_by_cat.get(category, [])
        title = f"Templates in category '{category}'"
    else:
        filtered = get_all_templates()
        title = "Available Configuration Templates"

    if not filtered:
        console.print("[yellow]No templates found matching criteria[/yellow]")
        return

    # Display templates in a table
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Template ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Category")
    table.add_column("Description")
    table.add_column("Tags", style="dim")

    for template in filtered:
        table.add_row(
            template.id,
            template.name,
            template.category,
            template.description,
            ", ".join(template.tags[:3]),  # Limit tags for display
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(filtered)} template(s)[/dim]")
    console.print("[dim]Use 'mcpbr init -t <template-id>' to use a template[/dim]")
    console.print("[dim]Use 'mcpbr init -i' for interactive template selection[/dim]")


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
    table.add_column("Tasks")
    table.add_column("Description")

    # SWE-bench variants
    table.add_row(
        "swe-bench-verified",
        "Subset",
        "Bug fixing (manually validated tests) - DEFAULT",
    )
    table.add_row(
        "swe-bench-lite",
        "300",
        "Bug fixing (quick testing, curated tasks)",
    )
    table.add_row(
        "swe-bench-full",
        "2,294",
        "Bug fixing (complete benchmark, research)",
    )
    # Other benchmarks
    table.add_row(
        "cybergym",
        "Varies",
        "Security exploits (PoC generation, difficulty levels 0-3)",
    )
    table.add_row(
        "mcptoolbench",
        "Varies",
        "MCP tool use (tool discovery, selection, invocation)",
    )

    console.print(table)
    console.print("\n[dim]Use -b/--benchmark flag to select a benchmark[/dim]")
    console.print("[dim]Examples:[/dim]")
    console.print("[dim]  mcpbr run -c config.yaml -b swe-bench-verified[/dim]")
    console.print("[dim]  mcpbr run -c config.yaml -b swe-bench-full -n 50[/dim]")
    console.print("[dim]  mcpbr run -c config.yaml -b cybergym --level 2[/dim]")
    console.print("[dim]  mcpbr run -c config.yaml -b mcptoolbench[/dim]")


@main.group(context_settings={"help_option_names": ["-h", "--help"]})
def config() -> None:
    """Configuration file management commands.

    \b
    Examples:
      mcpbr config validate config.yaml     # Validate configuration
      mcpbr config schema                   # Show JSON schema
      mcpbr config schema --save schema.json  # Save schema to file
    """
    pass


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show resources that would be removed without removing them",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force removal of all resources regardless of age",
)
@click.option(
    "--retention-hours",
    type=int,
    default=None,
    help="Only remove resources older than this many hours (default: 24)",
)
@click.option(
    "--containers-only",
    is_flag=True,
    help="Only remove containers",
)
@click.option(
    "--volumes-only",
    is_flag=True,
    help="Only remove volumes",
)
@click.option(
    "--networks-only",
    is_flag=True,
    help="Only remove networks",
)
def cleanup(
    dry_run: bool,
    force: bool,
    retention_hours: int | None,
    containers_only: bool,
    volumes_only: bool,
    networks_only: bool,
) -> None:
    """Remove orphaned mcpbr Docker resources.

    Finds and removes Docker containers, volumes, and networks created by mcpbr
    that were not properly cleaned up (e.g., due to crashes or interruptions).

    By default, only removes resources older than 24 hours. Use --force to
    remove all resources immediately.

    \b
    Examples:
      mcpbr cleanup --dry-run              # Preview what would be removed
      mcpbr cleanup                        # Remove with confirmation
      mcpbr cleanup -f                     # Force remove without confirmation
      mcpbr cleanup --retention-hours 48   # Only remove resources older than 48h
      mcpbr cleanup --containers-only      # Only remove containers
      mcpbr cleanup --volumes-only         # Only remove volumes
    """
    try:
        from docker.errors import DockerException
    except ImportError:
        console.print("[red]Error: docker package not available[/red]")
        sys.exit(1)

    # Validate mutually exclusive flags
    exclusive_flags = [containers_only, volumes_only, networks_only]
    if sum(exclusive_flags) > 1:
        console.print("[red]Error: Cannot specify multiple --*-only flags[/red]")
        sys.exit(1)

    try:
        # Get preview of what would be removed
        preview_report = cleanup_all_resources(
            dry_run=True, force=force, retention_hours=retention_hours
        )

        # Filter based on --*-only flags
        if containers_only:
            preview_report.volumes_removed = []
            preview_report.networks_removed = []
        elif volumes_only:
            preview_report.containers_removed = []
            preview_report.networks_removed = []
        elif networks_only:
            preview_report.containers_removed = []
            preview_report.volumes_removed = []
    except DockerException as e:
        console.print(f"[red]Error connecting to Docker: {e}[/red]")
        console.print("[dim]Make sure Docker is running.[/dim]")
        sys.exit(1)

    if preview_report.total_removed == 0:
        console.print("[green]No orphaned mcpbr resources found.[/green]")
        if not force and retention_hours is None:
            console.print("[dim]Use --force to remove all resources regardless of age.[/dim]")
        return

    console.print("[bold]Found orphaned mcpbr resources:[/bold]\n")

    if preview_report.containers_removed:
        console.print(f"  [cyan]Containers ({len(preview_report.containers_removed)}):[/cyan]")
        for name in preview_report.containers_removed[:10]:
            console.print(f"    - {name}")
        if len(preview_report.containers_removed) > 10:
            console.print(f"    ... and {len(preview_report.containers_removed) - 10} more")
        console.print()

    if preview_report.volumes_removed:
        console.print(f"  [cyan]Volumes ({len(preview_report.volumes_removed)}):[/cyan]")
        for name in preview_report.volumes_removed[:10]:
            console.print(f"    - {name}")
        if len(preview_report.volumes_removed) > 10:
            console.print(f"    ... and {len(preview_report.volumes_removed) - 10} more")
        console.print()

    if preview_report.networks_removed:
        console.print(f"  [cyan]Networks ({len(preview_report.networks_removed)}):[/cyan]")
        for name in preview_report.networks_removed[:10]:
            console.print(f"    - {name}")
        if len(preview_report.networks_removed) > 10:
            console.print(f"    ... and {len(preview_report.networks_removed) - 10} more")
        console.print()

    if dry_run:
        console.print("[yellow]Dry run - no resources were removed.[/yellow]")
        return

    if not force:
        confirm = click.confirm("Remove these resources?", default=True)
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Perform actual cleanup
    report = cleanup_all_resources(dry_run=False, force=force, retention_hours=retention_hours)

    # Filter based on --*-only flags
    if containers_only:
        report.volumes_removed = []
        report.networks_removed = []
    elif volumes_only:
        report.containers_removed = []
        report.networks_removed = []
    elif networks_only:
        report.containers_removed = []
        report.volumes_removed = []

    console.print(f"[green]Removed {report.total_removed} resource(s).[/green]")

    if report.errors:
        console.print(f"\n[yellow]Encountered {len(report.errors)} error(s):[/yellow]")
        for error in report.errors[:5]:
            console.print(f"  - {error}")
        if len(report.errors) > 5:
            console.print(f"  ... and {len(report.errors) - 5} more")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory containing state files (default: .mcpbr_state/)",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear all evaluation state",
)
def state(state_dir: Path | None, clear: bool) -> None:
    """View or manage evaluation state.

    Shows information about completed tasks and allows clearing state.

    \b
    Examples:
      mcpbr state                # View current state
      mcpbr state --clear        # Clear all state
    """
    tracker = StateTracker(state_dir=state_dir)

    if clear:
        if not tracker.state_file.exists():
            console.print("[yellow]No state to clear[/yellow]")
            return

        confirm = click.confirm("Clear all evaluation state?", default=False)
        if confirm:
            tracker.clear_state()
            console.print("[green]State cleared[/green]")
        else:
            console.print("[yellow]Aborted[/yellow]")
        return

    # Load and display state
    if not tracker.state_file.exists():
        console.print("[yellow]No evaluation state found[/yellow]")
        console.print(f"[dim]State will be created in: {tracker.state_file}[/dim]")
        return

    tracker.load_state()

    if not tracker.state or not tracker.state.tasks:
        console.print("[yellow]No tasks in state[/yellow]")
        return

    console.print("[bold]Evaluation State[/bold]")
    console.print(f"  Location: {tracker.state_file}")
    console.print(f"  Created: {tracker.state.created_at}")
    console.print(f"  Updated: {tracker.state.updated_at}")
    console.print()

    completed = sum(1 for t in tracker.state.tasks.values() if t.completed)
    console.print(f"[bold]Tasks:[/bold] {completed}/{len(tracker.state.tasks)} completed")
    console.print()

    # Show failed tasks
    failed_tasks = tracker.get_failed_tasks()
    if failed_tasks:
        console.print(f"[bold]Failed Tasks ({len(failed_tasks)}):[/bold]")
        for task_id in failed_tasks[:10]:
            task_state = tracker.state.tasks[task_id]
            error = task_state.error or "Not resolved"
            console.print(f"  - {task_id}: {error}")
        if len(failed_tasks) > 10:
            console.print(f"  ... and {len(failed_tasks) - 10} more")
        console.print()

    # Show some statistics
    mcp_resolved = 0
    baseline_resolved = 0
    for task_state in tracker.state.tasks.values():
        if task_state.completed:
            if task_state.mcp_result and task_state.mcp_result.get("resolved"):
                mcp_resolved += 1
            if task_state.baseline_result and task_state.baseline_result.get("resolved"):
                baseline_resolved += 1

    if completed > 0:
        console.print("[bold]Resolution Rates:[/bold]")
        console.print(f"  MCP: {mcp_resolved}/{completed} ({mcp_resolved / completed:.1%})")
        console.print(
            f"  Baseline: {baseline_resolved}/{completed} ({baseline_resolved / completed:.1%})"
        )
        console.print()

    # Show MCP tool call statistics
    total_tool_calls = 0
    total_failures = 0
    tool_usage: dict[str, int] = {}
    tool_failures: dict[str, int] = {}

    for task_state in tracker.state.tasks.values():
        if task_state.completed and task_state.mcp_result:
            # Aggregate successful tool calls
            if "tool_usage" in task_state.mcp_result:
                for tool_name, count in task_state.mcp_result["tool_usage"].items():
                    tool_usage[tool_name] = tool_usage.get(tool_name, 0) + count
                    total_tool_calls += count

            # Aggregate failed tool calls
            if "tool_failures" in task_state.mcp_result:
                for tool_name, count in task_state.mcp_result["tool_failures"].items():
                    tool_failures[tool_name] = tool_failures.get(tool_name, 0) + count
                    total_failures += count

    if total_tool_calls > 0:
        failure_rate = total_failures / total_tool_calls
        console.print("[bold]MCP Tool Statistics:[/bold]")
        console.print(f"  Total calls: {total_tool_calls:,}")
        console.print(f"  Failures: {total_failures:,} ({failure_rate:.1%})")

        if failure_rate > 0.1:
            console.print(
                f"  [bold yellow]⚠️  High failure rate detected ({failure_rate:.1%})[/bold yellow]"
            )

        # Show per-tool breakdown if there are failures
        if total_failures > 0:
            console.print()
            console.print("[bold]  By tool:[/bold]")

            # Sort by failure rate (descending)
            # Note: tool_usage contains total calls (successful + failed)
            # tool_failures contains only failed calls
            # So succeeded = total - failed, not total + failed
            tool_stats = []
            for tool_name in set(list(tool_usage.keys()) + list(tool_failures.keys())):
                total = tool_usage.get(tool_name, 0)  # Total calls (not success count!)
                failure_count = tool_failures.get(tool_name, 0)
                # Derive success count (avoid negative values in edge cases)
                success_count = max(total - failure_count, 0)
                rate = failure_count / total if total > 0 else 0.0
                tool_stats.append((tool_name, total, success_count, failure_count, rate))

            tool_stats.sort(key=lambda x: x[4], reverse=True)  # Sort by failure rate

            # Only show tools with failures, limit to top 10
            failing_tools = [t for t in tool_stats if t[3] > 0]
            for tool_name, total, _success, failed, rate in failing_tools[:10]:
                style = "bold red" if rate > 0.5 else "yellow" if rate > 0.1 else "dim"
                console.print(
                    f"    {tool_name}: {total:,} calls, {failed:,} failed ({rate:.1%})",
                    style=style,
                )

            if len(failing_tools) > 10:
                remaining = len(failing_tools) - 10
                console.print(f"    ... and {remaining} more tools with failures")


@config.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("config_path", type=click.Path(exists=False, path_type=Path))
def validate(config_path: Path) -> None:
    """Validate a configuration file.

    Checks YAML/TOML syntax, validates required fields, checks API key format,
    and provides detailed error messages with suggestions.

    \b
    Examples:
      mcpbr config validate config.yaml        # Validate config
      mcpbr config validate my-config.toml     # Validate TOML config

    Exit codes:
      0 - Configuration is valid
      1 - Configuration has errors
    """
    console.print(f"[bold]Validating configuration:[/bold] {config_path}\n")

    result = validate_config(config_path)

    # Display errors
    if result.has_errors:
        console.print(f"[red bold]Found {len(result.errors)} error(s):[/red bold]\n")
        for i, error in enumerate(result.errors, 1):
            location = f"[cyan]{error.field}[/cyan]"
            if error.line_number:
                location += f" (line {error.line_number})"

            console.print(f"  [red]{i}.[/red] {location}")
            console.print(f"     [red]Error:[/red] {error.error}")
            if error.suggestion:
                console.print(f"     [yellow]Suggestion:[/yellow] {error.suggestion}")
            console.print()

    # Display warnings
    if result.has_warnings:
        console.print(f"[yellow bold]Found {len(result.warnings)} warning(s):[/yellow bold]\n")
        for i, warning in enumerate(result.warnings, 1):
            location = f"[cyan]{warning.field}[/cyan]"
            if warning.line_number:
                location += f" (line {warning.line_number})"

            console.print(f"  [yellow]{i}.[/yellow] {location}")
            console.print(f"     [yellow]Warning:[/yellow] {warning.error}")
            if warning.suggestion:
                console.print(f"     [dim]Suggestion:[/dim] {warning.suggestion}")
            console.print()

    # Summary
    if result.valid:
        if result.has_warnings:
            console.print(
                "[green]Configuration is valid[/green] but has warnings that should be addressed."
            )
        else:
            console.print("[green bold]Configuration is valid![/green bold]")
        sys.exit(0)
    else:
        console.print("[red bold]Configuration validation failed.[/red bold]")
        console.print("[dim]Fix the errors above and run validation again.[/dim]")
        sys.exit(1)


@config.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--save",
    "-s",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Save schema to a file instead of displaying",
)
@click.option(
    "--docs",
    "-d",
    is_flag=True,
    help="Generate Markdown documentation from schema",
)
def schema(output_path: Path | None, docs: bool) -> None:
    """Show or save the JSON Schema for configuration files.

    The JSON Schema enables IDE auto-completion and validation support
    for YAML configuration files.

    \b
    Examples:
      mcpbr config schema                      # Display schema
      mcpbr config schema --save schema.json   # Save to file
      mcpbr config schema --docs               # Show documentation
    """
    from .schema import (
        generate_schema_docs,
        get_schema_url,
        print_schema_info,
        save_schema,
    )

    if docs:
        # Generate and display Markdown documentation
        docs_content = generate_schema_docs()
        console.print(docs_content)
        return

    if output_path:
        # Save schema to file
        try:
            save_schema(output_path)
            console.print(f"[green]Schema saved to {output_path}[/green]")
            console.print("\n[dim]To use this schema in VS Code, add this to your YAML file:[/dim]")
            console.print(
                f"[dim]# yaml-language-server: $schema=file://{output_path.absolute()}[/dim]"
            )
        except Exception as e:
            console.print(f"[red]Error saving schema: {e}[/red]")
            sys.exit(1)
    else:
        # Display schema info
        info = print_schema_info()
        console.print(info)
        console.print("\n[dim]Use --save to export the schema to a file[/dim]")
        console.print("[dim]Use --docs to see detailed documentation[/dim]")
        console.print("\n[dim]Published schema URL:[/dim]")
        console.print(f"[cyan]{get_schema_url()}[/cyan]")


@config.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--add-schema",
    is_flag=True,
    help="Add schema comment to enable IDE auto-completion",
)
def annotate(config_path: Path, add_schema: bool) -> None:
    """Add IDE integration comments to configuration file.

    Adds YAML Language Server schema comment to enable auto-completion
    and validation in supported IDEs (VS Code, IntelliJ, etc.).

    \b
    Examples:
      mcpbr config annotate config.yaml --add-schema  # Add schema comment
    """
    from .schema import add_schema_comment

    if not add_schema:
        console.print("[yellow]Use --add-schema to add IDE integration[/yellow]")
        return

    try:
        content = config_path.read_text()
        annotated = add_schema_comment(content)

        if content == annotated:
            console.print("[yellow]Schema comment already present[/yellow]")
            return

        # Write back the annotated content
        config_path.write_text(annotated)
        console.print(f"[green]Added schema comment to {config_path}[/green]")
        console.print("[dim]Your IDE should now provide auto-completion for this file[/dim]")

    except Exception as e:
        console.print(f"[red]Error annotating config: {e}[/red]")
        sys.exit(1)


@main.group(context_settings={"help_option_names": ["-h", "--help"]})
def cache() -> None:
    """Cache management commands.

    Manage the benchmark result cache to avoid re-running identical evaluations.

    \b
    Examples:
      mcpbr cache stats    # Show cache statistics
      mcpbr cache clear    # Clear all cached results
      mcpbr cache prune    # Remove old cache entries
    """
    pass


@cache.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Cache directory (default: ~/.cache/mcpbr)",
)
def stats(cache_dir: Path | None) -> None:
    """Show cache statistics.

    Displays information about cached results including total entries,
    disk usage, and oldest/newest cache entries.

    \b
    Examples:
      mcpbr cache stats                        # Default cache directory
      mcpbr cache stats --cache-dir ./cache    # Custom cache directory
    """
    from .cache import ResultCache

    result_cache = ResultCache(cache_dir=cache_dir, enabled=True)
    cache_stats = result_cache.get_stats()

    console.print("[bold]Cache Statistics[/bold]\n")
    console.print(f"  Cache directory: {cache_stats.cache_dir}")
    console.print(f"  Total entries:   {cache_stats.total_entries}")
    console.print(f"  Total size:      {cache_stats.format_size()}")

    if cache_stats.oldest_entry:
        console.print(
            f"  Oldest entry:    {cache_stats.oldest_entry.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    if cache_stats.newest_entry:
        console.print(
            f"  Newest entry:    {cache_stats.newest_entry.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    if cache_stats.total_entries == 0:
        console.print("\n[dim]Cache is empty[/dim]")


@cache.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Cache directory (default: ~/.cache/mcpbr)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def clear(cache_dir: Path | None, force: bool) -> None:
    """Clear all cached results.

    Removes all entries from the cache. This operation cannot be undone.

    \b
    Examples:
      mcpbr cache clear           # Clear with confirmation
      mcpbr cache clear -f        # Clear without confirmation
    """
    from .cache import ResultCache

    result_cache = ResultCache(cache_dir=cache_dir, enabled=True)
    cache_stats = result_cache.get_stats()

    if cache_stats.total_entries == 0:
        console.print("[yellow]Cache is already empty[/yellow]")
        return

    console.print(f"[yellow]About to clear {cache_stats.total_entries} cached result(s)[/yellow]")
    console.print(f"[yellow]Total size: {cache_stats.format_size()}[/yellow]")

    if not force:
        confirm = click.confirm("Are you sure you want to clear the cache?", default=False)
        if not confirm:
            console.print("[dim]Aborted[/dim]")
            return

    removed = result_cache.clear()
    console.print(f"[green]Cleared {removed} cached result(s)[/green]")


@cache.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Cache directory (default: ~/.cache/mcpbr)",
)
@click.option(
    "--max-age-days",
    type=int,
    default=None,
    help="Remove entries older than this many days",
)
@click.option(
    "--max-size-mb",
    type=int,
    default=None,
    help="Remove oldest entries if cache exceeds this size in MB",
)
def prune(cache_dir: Path | None, max_age_days: int | None, max_size_mb: int | None) -> None:
    """Remove old cache entries based on age or size limits.

    Prunes the cache by removing entries older than a specified age or
    keeping only the most recent entries within a size limit.

    \b
    Examples:
      mcpbr cache prune --max-age-days 30      # Remove entries older than 30 days
      mcpbr cache prune --max-size-mb 100      # Keep only 100 MB of newest entries
      mcpbr cache prune --max-age-days 7 --max-size-mb 50  # Combine both limits
    """
    from .cache import ResultCache

    if max_age_days is None and max_size_mb is None:
        console.print(
            "[red]Error: Must specify at least one of --max-age-days or --max-size-mb[/red]"
        )
        sys.exit(1)

    result_cache = ResultCache(cache_dir=cache_dir, enabled=True)
    cache_stats_before = result_cache.get_stats()

    if cache_stats_before.total_entries == 0:
        console.print("[yellow]Cache is empty[/yellow]")
        return

    console.print(
        f"[dim]Current cache: {cache_stats_before.total_entries} entries, "
        f"{cache_stats_before.format_size()}[/dim]"
    )

    removed = result_cache.prune(max_age_days=max_age_days, max_size_mb=max_size_mb)

    if removed > 0:
        cache_stats_after = result_cache.get_stats()
        console.print(f"[green]Removed {removed} cached result(s)[/green]")
        console.print(
            f"[dim]Remaining: {cache_stats_after.total_entries} entries, "
            f"{cache_stats_after.format_size()}[/dim]"
        )
    else:
        console.print("[dim]No entries removed[/dim]")


@main.command(name="smoke-test", context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file (default: mcpbr.yaml)",
)
def smoke_test(config_path: Path | None) -> None:
    """Run smoke tests to validate setup before running evaluations.

    Validates configuration, checks Docker availability, tests API connectivity,
    and verifies MCP server configuration. This is useful for quickly checking
    that your environment is properly configured before running a full evaluation.

    \b
    Tests performed:
      ✓ Configuration validation
      ✓ Docker daemon connectivity
      ✓ Anthropic API authentication
      ✓ MCP server configuration

    \b
    Examples:
      mcpbr smoke-test                    # Use mcpbr.yaml in current directory
      mcpbr smoke-test -c config.yaml     # Use specific config file
    """
    from .smoke_test import run_smoke_test

    # Default to mcpbr.yaml if no config provided
    if config_path is None:
        config_path = Path("mcpbr.yaml")
        if not config_path.exists():
            console.print(
                "[red]Error: No configuration file specified and mcpbr.yaml not found.[/red]"
            )
            console.print("[dim]Run 'mcpbr smoke-test -c <config-file>' or create mcpbr.yaml[/dim]")
            sys.exit(1)

    # Run smoke tests
    success = asyncio.run(run_smoke_test(config_path))

    # Exit with appropriate code
    sys.exit(0 if success else 1)


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "input_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["csv"]),
    required=True,
    help="Export format",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output file path",
)
def export(input_path: Path, output_format: str, output_path: Path) -> None:
    """Export evaluation results to different formats.

    Args:
        input_path: Path to the input JSON file containing results.
        output_format: Export format (currently only 'csv' is supported).
        output_path: Path to write the output file.
    """
    if output_format != "csv":
        console.print(f"[red]Unsupported format: {output_format}[/red]")
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text())
    except Exception as e:
        console.print(f"[red]Failed to read JSON: {e}[/red]")
        sys.exit(1)

    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        console.print("[red]Expected 'tasks' to be a list[/red]")
        sys.exit(1)

    rows = [t for t in tasks if isinstance(t, dict)]

    if not rows:
        console.print("[yellow]No rows to export[/yellow]")
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"[green]Exported {len(rows)} rows to {output_path}[/green]")


@main.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "result_files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--output-html",
    "html_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Save comparison as interactive HTML report",
)
@click.option(
    "--output-markdown",
    "md_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Save comparison as enhanced Markdown report",
)
@click.option(
    "--output",
    "-o",
    "json_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Save comparison data as JSON",
)
def compare(
    result_files: tuple[Path, ...],
    html_path: Path | None,
    md_path: Path | None,
    json_path: Path | None,
) -> None:
    """Compare results from multiple evaluation runs.

    Provide two or more JSON result files to generate a side-by-side comparison
    with statistical significance testing and Pareto frontier analysis.

    \b
    Examples:
      mcpbr compare run1.json run2.json
      mcpbr compare run1.json run2.json run3.json --output-html comparison.html
      mcpbr compare *.json --output-markdown comparison.md
    """
    if len(result_files) < 2:
        console.print("[red]Error: At least 2 result files are required for comparison[/red]")
        sys.exit(1)

    from .analytics.comparison import ComparisonEngine, format_comparison_table

    engine = ComparisonEngine()

    for path in result_files:
        try:
            data = json.loads(path.read_text())
            label = path.stem
            engine.add_results(label, data)
        except Exception as e:
            console.print(f"[red]Error loading {path}: {e}[/red]")
            sys.exit(1)

    comparison = engine.compare()

    # Print comparison table to console
    table_output = format_comparison_table(comparison)
    console.print(table_output)

    # Statistical significance
    summary_table = comparison.get("summary_table", [])
    if len(summary_table) >= 2:
        from .analytics.statistical import compare_resolution_rates

        console.print("\n[bold]Statistical Significance[/bold]")
        for i in range(len(summary_table)):
            for j in range(i + 1, len(summary_table)):
                a_data = summary_table[i]
                b_data = summary_table[j]

                result = compare_resolution_rates(a_data, b_data)
                chi2 = result["chi2_test"]
                sig = (
                    "[green]significant[/green]"
                    if chi2["significant"]
                    else "[dim]not significant[/dim]"
                )
                a_label = a_data.get("label", f"model-{i}")
                b_label = b_data.get("label", f"model-{j}")
                console.print(f"  {a_label} vs {b_label}: p={chi2['p_value']:.4f} ({sig})")

    # Winner analysis
    winners = engine.get_winner_analysis()
    if winners:
        console.print("\n[bold]Winner Analysis[/bold]")
        for metric, winner in winners.items():
            console.print(f"  {metric}: [cyan]{winner}[/cyan]")

    # Pareto frontier
    frontier = engine.get_cost_performance_frontier()
    if frontier:
        console.print("\n[bold]Cost-Performance Frontier[/bold]")
        for entry in frontier:
            console.print(
                f"  [cyan]{entry['label']}[/cyan]: {entry['rate']:.1%} @ ${entry['cost']:.2f}"
            )

    # Save outputs
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(comparison, indent=2, default=str))
        console.print(f"\n[green]Comparison JSON saved to {json_path}[/green]")

    if html_path:
        from .reports import HTMLReportGenerator

        # Build a combined results dict for the HTML report
        html_data = {
            "metadata": {"comparison": True, "files": [str(f) for f in result_files]},
            "summary": comparison.get("summary", {}),
            "tasks": [],
        }
        generator = HTMLReportGenerator(html_data, title="mcpbr Comparison Report")
        generator.save(html_path)
        console.print(f"[green]HTML comparison report saved to {html_path}[/green]")

    if md_path:
        from .reports import EnhancedMarkdownGenerator

        md_data = {
            "metadata": {"comparison": True, "files": [str(f) for f in result_files]},
            "summary": comparison.get("summary", {}),
            "tasks": [],
        }
        generator = EnhancedMarkdownGenerator(md_data)
        generator.save(md_path)
        console.print(f"[green]Markdown comparison report saved to {md_path}[/green]")


@main.group(context_settings={"help_option_names": ["-h", "--help"]})
def analytics() -> None:
    """Analytics commands for historical tracking and analysis.

    \b
    Commands:
      store        Store evaluation results in the analytics database
      trends       Show performance trends over time
      leaderboard  Generate model/server leaderboard from stored results
      regression   Detect performance regressions between runs

    \b
    Examples:
      mcpbr analytics store results.json
      mcpbr analytics trends --metric resolution_rate
      mcpbr analytics leaderboard
      mcpbr analytics regression --baseline run1.json --current run2.json
    """
    pass


@analytics.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "result_file",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=Path(".mcpbr_analytics.db"),
    help="Path to analytics database (default: .mcpbr_analytics.db)",
)
@click.option(
    "--label",
    type=str,
    default=None,
    help="Optional label for this run",
)
def store(result_file: Path, db_path: Path, label: str | None) -> None:
    """Store evaluation results in the analytics database.

    Results are stored in a local SQLite database for trend analysis,
    leaderboard generation, and regression detection.

    \b
    Examples:
      mcpbr analytics store results.json
      mcpbr analytics store results.json --label "v1.0 baseline"
      mcpbr analytics store results.json --db custom.db
    """
    from .analytics.database import ResultsDatabase

    try:
        data = json.loads(result_file.read_text())
    except Exception as e:
        console.print(f"[red]Error loading {result_file}: {e}[/red]")
        sys.exit(1)

    metadata = data.get("metadata", {})
    config = metadata.get("config", {})
    summary = data.get("summary", {})
    tasks = data.get("tasks", [])

    mcp_summary = summary.get("mcp", {})
    total_tasks = mcp_summary.get("total", 0)
    resolved_tasks = mcp_summary.get("resolved", 0)
    resolution_rate = mcp_summary.get("rate", 0)
    total_cost = mcp_summary.get("total_cost", 0)

    run_data = {
        "benchmark": config.get("benchmark", "unknown"),
        "model": config.get("model", "unknown"),
        "provider": config.get("provider", "unknown"),
        "agent_harness": config.get("agent_harness", "unknown"),
        "sample_size": config.get("sample_size", 0),
        "timeout_seconds": config.get("timeout_seconds", 0),
        "max_iterations": config.get("max_iterations", 0),
        "resolution_rate": resolution_rate,
        "total_cost": total_cost or 0,
        "total_tasks": total_tasks,
        "resolved_tasks": resolved_tasks,
        "metadata_json": json.dumps({"label": label, "source": str(result_file)}),
    }

    task_results = []
    for task in tasks:
        mcp = task.get("mcp", {}) or {}
        task_results.append(
            {
                "instance_id": task.get("instance_id", ""),
                "resolved": mcp.get("resolved", False),
                "cost": mcp.get("cost", 0),
                "tokens_input": mcp.get("tokens_input", 0),
                "tokens_output": mcp.get("tokens_output", 0),
                "iterations": mcp.get("iterations", 0),
                "tool_calls": mcp.get("tool_calls", 0),
                "runtime_seconds": mcp.get("runtime_seconds", 0),
                "error": mcp.get("error", ""),
            }
        )

    with ResultsDatabase(db_path) as db:
        run_id = db.store_run(run_data, task_results)
        console.print(f"[green]Stored run #{run_id} in {db_path}[/green]")
        console.print(f"  {resolved_tasks}/{total_tasks} resolved ({resolution_rate:.1%})")
        if label:
            console.print(f"  Label: {label}")


@analytics.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--db",
    "db_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path(".mcpbr_analytics.db"),
    help="Path to analytics database",
)
@click.option(
    "--metric",
    type=click.Choice(["resolution_rate", "total_cost", "resolved_tasks"]),
    default="resolution_rate",
    help="Metric to analyze trends for",
)
@click.option(
    "--benchmark",
    "-b",
    type=str,
    default=None,
    help="Filter by benchmark name",
)
@click.option(
    "--model",
    "-m",
    type=str,
    default=None,
    help="Filter by model name",
)
@click.option(
    "--last",
    "-n",
    "last_n",
    type=int,
    default=20,
    help="Number of recent runs to analyze (default: 20)",
)
def trends(
    db_path: Path,
    metric: str,
    benchmark: str | None,
    model: str | None,
    last_n: int,
) -> None:
    """Show performance trends over time.

    Analyzes historical results to show how metrics change over time,
    including trend direction, moving averages, and slope.

    \b
    Examples:
      mcpbr analytics trends
      mcpbr analytics trends --metric total_cost
      mcpbr analytics trends --benchmark swe-bench-verified --last 50
      mcpbr analytics trends --model claude-sonnet-4-5-20250929
    """
    from .analytics.database import ResultsDatabase
    from .analytics.trends import calculate_trends, detect_trend_direction

    with ResultsDatabase(db_path) as db:
        runs = db.list_runs()

    if not runs:
        console.print("[yellow]No runs found in database[/yellow]")
        return

    # Filter runs
    filtered = runs
    if benchmark:
        filtered = [r for r in filtered if r.get("benchmark") == benchmark]
    if model:
        filtered = [r for r in filtered if r.get("model") == model]

    # Take last N
    filtered = filtered[-last_n:]

    if not filtered:
        console.print("[yellow]No matching runs found[/yellow]")
        return

    values = [r.get(metric, 0) for r in filtered]

    trend_result = calculate_trends(filtered)
    direction = detect_trend_direction(values)

    direction_style = {
        "improving": "[green]Improving[/green]",
        "declining": "[red]Declining[/red]",
        "stable": "[dim]Stable[/dim]",
        "insufficient_data": "[yellow]Insufficient data[/yellow]",
    }

    console.print(f"[bold]Trend Analysis: {metric}[/bold]")
    console.print(f"  Runs analyzed: {len(filtered)}")
    console.print(f"  Direction: {direction_style.get(direction, direction)}")
    console.print(f"  Slope: {trend_result.get('slope', 0):.4f}")
    console.print(f"  Current: {values[-1]:.4f}")
    if len(values) >= 2:
        console.print(f"  Previous: {values[-2]:.4f}")
        delta = values[-1] - values[-2]
        delta_str = f"+{delta:.4f}" if delta >= 0 else f"{delta:.4f}"
        console.print(f"  Change: {delta_str}")

    # Show recent values
    console.print(f"\n[bold]Recent {min(10, len(values))} values:[/bold]")
    for i, v in enumerate(values[-10:]):
        run = filtered[-(10 - i) if len(values) >= 10 else i]
        ts = run.get("timestamp", "")[:19]
        console.print(f"  {ts}  {v:.4f}")


@analytics.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--db",
    "db_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path(".mcpbr_analytics.db"),
    help="Path to analytics database",
)
@click.option(
    "--benchmark",
    "-b",
    type=str,
    default=None,
    help="Filter by benchmark name",
)
@click.option(
    "--sort-by",
    type=click.Choice(["resolution_rate", "total_cost", "resolved_tasks"]),
    default="resolution_rate",
    help="Metric to sort by (default: resolution_rate)",
)
@click.option(
    "--output-markdown",
    "md_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Save leaderboard as Markdown file",
)
def leaderboard(
    db_path: Path,
    benchmark: str | None,
    sort_by: str,
    md_path: Path | None,
) -> None:
    """Generate a leaderboard from stored results.

    Ranks models and configurations by performance across stored runs.

    \b
    Examples:
      mcpbr analytics leaderboard
      mcpbr analytics leaderboard --benchmark swe-bench-verified
      mcpbr analytics leaderboard --sort-by total_cost
      mcpbr analytics leaderboard --output-markdown leaderboard.md
    """
    from .analytics.database import ResultsDatabase
    from .analytics.leaderboard import Leaderboard

    with ResultsDatabase(db_path) as db:
        runs = db.list_runs()

    if not runs:
        console.print("[yellow]No runs found in database[/yellow]")
        return

    # Filter
    if benchmark:
        runs = [r for r in runs if r.get("benchmark") == benchmark]

    if not runs:
        console.print("[yellow]No matching runs found[/yellow]")
        return

    lb = Leaderboard()
    for run in runs:
        label = f"{run.get('model', 'unknown')} ({run.get('provider', '')})"
        # Convert database run dict to results_data format expected by Leaderboard
        results_data = {
            "summary": {
                "mcp": {
                    "resolved": run.get("resolved_tasks", 0),
                    "total": run.get("total_tasks", 0),
                    "rate": run.get("resolution_rate", 0),
                    "total_cost": run.get("total_cost", 0),
                }
            },
            "metadata": {
                "config": {
                    "model": run.get("model", "unknown"),
                    "provider": run.get("provider", "unknown"),
                }
            },
            "tasks": [],
        }
        lb.add_entry(label, results_data)

    console.print(lb.format_table(sort_by=sort_by))

    if md_path:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(lb.format_markdown(sort_by=sort_by))
        console.print(f"\n[green]Leaderboard saved to {md_path}[/green]")


@analytics.command(name="regression", context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--baseline",
    "baseline_file",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to baseline results JSON",
)
@click.option(
    "--current",
    "current_file",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to current results JSON",
)
@click.option(
    "--threshold",
    type=float,
    default=0.05,
    help="Significance threshold for detecting regressions (default: 0.05)",
)
def regression_cmd(
    baseline_file: Path,
    current_file: Path,
    threshold: float,
) -> None:
    """Detect performance regressions between two runs.

    Compares baseline and current results using statistical tests to
    identify significant regressions in resolution rate, cost, and latency.

    \b
    Examples:
      mcpbr analytics regression --baseline v1.json --current v2.json
      mcpbr analytics regression --baseline v1.json --current v2.json --threshold 0.1
    """
    from .analytics.regression_detector import RegressionDetector

    try:
        baseline_data = json.loads(baseline_file.read_text())
        current_data = json.loads(current_file.read_text())
    except Exception as e:
        console.print(f"[red]Error loading files: {e}[/red]")
        sys.exit(1)

    detector = RegressionDetector(threshold=threshold)
    result = detector.detect(current_data, baseline_data)
    report = detector.format_report()

    console.print(report)

    # Exit with non-zero if regressions detected
    if result.get("overall_status") == "fail":
        sys.exit(1)


@main.group()
def tutorial():
    """Interactive tutorials for learning mcpbr."""
    pass


@tutorial.command("list")
def tutorial_list():
    """List available tutorials."""
    from .tutorial import TutorialEngine

    engine = TutorialEngine()
    tutorials = engine.list_tutorials()

    table = Table(title="Available Tutorials")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Difficulty")
    table.add_column("Time", justify="right")
    table.add_column("Status")

    for t in tutorials:
        progress = engine.get_progress(t.id)
        if progress and progress.completed_at:
            status = "[green]completed[/green]"
        elif progress:
            done = len(progress.completed_steps)
            total = len(t.steps)
            status = f"[yellow]{done}/{total}[/yellow]"
        else:
            status = "[dim]not started[/dim]"

        diff_colors = {"beginner": "green", "intermediate": "yellow", "advanced": "red"}
        color = diff_colors.get(t.difficulty, "white")
        difficulty = f"[{color}]{t.difficulty}[/{color}]"

        table.add_row(t.id, t.title, difficulty, f"{t.estimated_minutes} min", status)

    console.print(table)


@tutorial.command("start")
@click.argument("tutorial_id")
@click.option("--reset", is_flag=True, help="Reset progress and start over")
def tutorial_start(tutorial_id, reset):
    """Start or resume an interactive tutorial."""
    from .tutorial import TutorialEngine

    engine = TutorialEngine()
    tut = engine.get_tutorial(tutorial_id)
    if tut is None:
        console.print(f"[red]Unknown tutorial: {tutorial_id}[/red]")
        console.print("Run [cyan]mcpbr tutorial list[/cyan] to see available tutorials.")
        sys.exit(1)

    if reset:
        engine.reset_tutorial(tutorial_id)

    progress = engine.start_tutorial(tutorial_id)

    console.print(f"\n[bold]{tut.title}[/bold]")
    console.print(f"[dim]{tut.description}[/dim]\n")

    for i, step in enumerate(tut.steps):
        if step.id in progress.completed_steps:
            continue

        console.print(f"[bold cyan]Step {i + 1}/{len(tut.steps)}: {step.title}[/bold cyan]\n")
        console.print(step.content)
        console.print()

        if step.action == "check" and step.validation:
            ok, msg = engine.validate_step(step)
            if ok:
                console.print("[green]Check passed![/green]\n")
            else:
                console.print(f"[yellow]Check failed: {msg}[/yellow]")
                if step.hint:
                    console.print(f"[dim]Hint: {step.hint}[/dim]")
                console.print("[dim]Press Enter to continue anyway, or Ctrl+C to quit.[/dim]")
                try:
                    input()
                except (KeyboardInterrupt, EOFError):
                    engine.save_progress(progress)
                    console.print("\n[dim]Progress saved. Resume with:[/dim]")
                    console.print(f"  [cyan]mcpbr tutorial start {tutorial_id}[/cyan]")
                    return
        else:
            console.print("[dim]Press Enter to continue, or Ctrl+C to quit.[/dim]")
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                engine.save_progress(progress)
                console.print("\n[dim]Progress saved. Resume with:[/dim]")
                console.print(f"  [cyan]mcpbr tutorial start {tutorial_id}[/cyan]")
                return

        progress = engine.complete_step(progress, step.id)

    console.print("[bold green]Tutorial complete![/bold green]\n")


@tutorial.command("progress")
def tutorial_progress():
    """Show tutorial completion progress."""
    from .tutorial import TutorialEngine

    engine = TutorialEngine()
    tutorials = engine.list_tutorials()

    for t in tutorials:
        progress = engine.get_progress(t.id)
        done = len(progress.completed_steps) if progress else 0
        total = len(t.steps)
        pct = (done / total * 100) if total > 0 else 0

        if progress and progress.completed_at:
            bar = "[green]" + "#" * 20 + "[/green]"
            label = "completed"
        else:
            filled = int(pct / 5)
            bar = "[cyan]" + "#" * filled + "[/cyan]" + "[dim]" + "-" * (20 - filled) + "[/dim]"
            label = f"{done}/{total}"

        console.print(f"  {t.title:<35} {bar} {pct:5.0f}% ({label})")


@tutorial.command("reset")
@click.argument("tutorial_id")
def tutorial_reset(tutorial_id):
    """Reset tutorial progress."""
    from .tutorial import TutorialEngine

    engine = TutorialEngine()
    engine.reset_tutorial(tutorial_id)
    console.print(f"[green]Reset progress for tutorial: {tutorial_id}[/green]")


@main.command()
@click.argument("results_file", type=click.Path(exists=True))
def badge(results_file):
    """Generate shields.io badge markdown from evaluation results."""
    import json

    from .badges import generate_badges_from_results

    with open(results_file) as f:
        results = json.load(f)
    badges = generate_badges_from_results(results)
    for b in badges:
        click.echo(b)


@main.command("export-metrics")
@click.argument("results_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default=None, help="Output file path.")
def export_metrics_cmd(results_file, output):
    """Export evaluation results as Prometheus metrics."""
    import json
    from pathlib import Path

    from .prometheus import export_metrics

    with open(results_file) as f:
        results = json.load(f)
    output_path = Path(output) if output else None
    metrics = export_metrics(results, output_path=output_path)
    if not output:
        click.echo(metrics)
    else:
        click.echo(f"Metrics written to {output}")


@main.command("run-status")
def run_status_cmd():
    """Show status of the current Azure VM run."""
    import json
    from pathlib import Path

    from .infrastructure.azure import AzureProvider
    from .run_state import RunState

    state_path = Path.home() / ".mcpbr" / "run_state.json"
    state = RunState.load(state_path)
    if state is None:
        click.echo("No active run found.")
        return
    status = AzureProvider.get_run_status(state)
    click.echo(json.dumps(status, indent=2))


@main.command("run-ssh")
def run_ssh_cmd():
    """Print SSH command for the current Azure VM run."""
    from pathlib import Path

    from .infrastructure.azure import AzureProvider
    from .run_state import RunState

    state_path = Path.home() / ".mcpbr" / "run_state.json"
    state = RunState.load(state_path)
    if state is None:
        click.echo("No active run found.")
        return
    click.echo(AzureProvider.get_ssh_command(state))


@main.command("run-stop")
def run_stop_cmd():
    """Stop and deallocate the current Azure VM run."""
    from pathlib import Path

    from .infrastructure.azure import AzureProvider
    from .run_state import RunState

    state_path = Path.home() / ".mcpbr" / "run_state.json"
    state = RunState.load(state_path)
    if state is None:
        click.echo("No active run found.")
        return
    if not click.confirm(f"Deallocate VM {state.vm_name}?", default=False):
        click.echo("Aborted.")
        return
    AzureProvider.stop_run(state)
    click.echo(f"VM {state.vm_name} deallocated.")


@main.command("run-logs")
def run_logs_cmd():
    """Show logs from the current run."""
    from pathlib import Path

    state_dir = Path.home() / ".mcpbr"
    log_dir = state_dir / "logs"
    if not log_dir.exists():
        click.echo("No logs found.")
        return
    for log_file in sorted(log_dir.glob("*.log")):
        click.echo(f"--- {log_file.name} ---")
        click.echo(log_file.read_text())


if __name__ == "__main__":
    main()
