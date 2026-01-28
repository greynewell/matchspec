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
    Incremental Evaluation:
      mcpbr run -c config.yaml --retry-failed  # Re-run failed tasks
      mcpbr state                              # View current state
      mcpbr state --clear                      # Clear state

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
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory for all outputs (logs, state, results). Default: .mcpbr_run_TIMESTAMP",
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
    output_dir: Path | None,
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
    Regression Detection:
      mcpbr run -c config.yaml --baseline-results baseline.json
      mcpbr run -c config.yaml --baseline-results baseline.json --regression-threshold 0.1
      mcpbr run -c config.yaml --baseline-results baseline.json --slack-webhook https://...
      mcpbr run -c config.yaml --baseline-results baseline.json --discord-webhook https://...
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
        # Default: timestamped directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

    # Determine which tasks to run based on incremental flags
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
    elif task_ids:
        selected_task_ids = list(task_ids)

    run_mcp = not baseline_only
    run_baseline = not mcp_only
    verbose = verbosity > 0

    # Run MCP pre-flight health check if MCP is enabled
    if run_mcp and not skip_health_check:
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
    console.print(f"  Run MCP: {run_mcp}, Run Baseline: {run_baseline}")
    console.print(f"  Pre-built images: {config.use_prebuilt_images}")
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


if __name__ == "__main__":
    main()
