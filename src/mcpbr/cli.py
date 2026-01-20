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
from .reporting import print_summary, save_json_results, save_markdown_report, save_yaml_results

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
      init       Generate a configuration file from a template
      templates  List available configuration templates
      models     List supported models for evaluation
      providers  List available model providers
      harnesses  List available agent harnesses
      benchmarks List available benchmarks
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
@click.option(
    "--yaml",
    "-y",
    "yaml_output",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to save YAML results (alternative to --output for YAML format)",
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
    yaml_output: Path | None,
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
      mcpbr run -c config.yaml --yaml out.yaml  # Save as YAML
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

    if yaml_output:
        save_yaml_results(results, yaml_output)
        console.print(f"[green]YAML results saved to {yaml_output}[/green]")

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
