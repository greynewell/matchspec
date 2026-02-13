"""Interactive tutorial system for mcpbr.

Provides guided, step-by-step tutorials to help users learn mcpbr
from basic usage through advanced analytics and reporting.
"""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class TutorialStep:
    """A single step within a tutorial.

    Attributes:
        id: Unique step identifier.
        title: Step title displayed to the user.
        content: Rich-formatted instruction text (supports Rich markup).
        hint: Optional hint text shown on request.
        validation: What to check, e.g. "file_exists:mcpbr.yaml" or
            "command_runs:mcpbr --version". None means no validation.
        action: Action type - "info" (display only), "prompt" (wait for enter),
            or "check" (validate something).
    """

    id: str
    title: str
    content: str
    hint: str | None = None
    validation: str | None = None
    action: str = "info"


@dataclass
class Tutorial:
    """A complete tutorial consisting of multiple steps.

    Attributes:
        id: Tutorial identifier.
        title: Tutorial title.
        description: Short description of the tutorial.
        difficulty: One of "beginner", "intermediate", "advanced".
        estimated_minutes: Estimated time to complete in minutes.
        steps: Ordered list of tutorial steps.
    """

    id: str
    title: str
    description: str
    difficulty: str
    estimated_minutes: int
    steps: list[TutorialStep] = field(default_factory=list)


@dataclass
class TutorialProgress:
    """Tracks a user's progress through a tutorial.

    Attributes:
        tutorial_id: ID of the tutorial being tracked.
        current_step: 0-indexed current step position.
        completed_steps: List of step IDs that have been completed.
        started_at: ISO datetime string when the tutorial was started.
        completed_at: ISO datetime string when the tutorial was finished, or None.
    """

    tutorial_id: str
    current_step: int = 0
    completed_steps: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Built-in tutorials
# ---------------------------------------------------------------------------

TUTORIALS: dict[str, Tutorial] = {
    "getting-started": Tutorial(
        id="getting-started",
        title="Getting Started with mcpbr",
        description="Learn the basics of mcpbr: installation, configuration, and your first run.",
        difficulty="beginner",
        estimated_minutes=10,
        steps=[
            TutorialStep(
                id="welcome",
                title="Welcome to mcpbr",
                content=(
                    "[bold]Welcome to mcpbr![/bold]\n\n"
                    "mcpbr (Model Context Protocol Benchmark Runner) evaluates MCP servers\n"
                    "by running them against software engineering benchmarks.\n\n"
                    "This tutorial will walk you through:\n"
                    "  1. Verifying prerequisites\n"
                    "  2. Exploring available benchmarks and models\n"
                    "  3. Creating a configuration file\n"
                    "  4. Running your first evaluation\n"
                    "  5. Understanding the results"
                ),
                action="info",
            ),
            TutorialStep(
                id="check-docker",
                title="Check Docker is Running",
                content=(
                    "mcpbr uses Docker to run benchmark evaluations in isolated containers.\n\n"
                    "Let's verify Docker is installed and running on your system.\n"
                    "Run: [bold cyan]docker info[/bold cyan]"
                ),
                hint="Make sure Docker Desktop is running, or start the Docker daemon.",
                validation="command_runs:docker info",
                action="check",
            ),
            TutorialStep(
                id="check-mcpbr",
                title="Check mcpbr is Installed",
                content=(
                    "Let's verify mcpbr is installed correctly.\n\n"
                    "Run: [bold cyan]mcpbr --version[/bold cyan]"
                ),
                hint="Install mcpbr with: pip install mcpbr",
                validation="command_runs:mcpbr --version",
                action="check",
            ),
            TutorialStep(
                id="list-benchmarks",
                title="List Available Benchmarks",
                content=(
                    "mcpbr supports several benchmarks for evaluating MCP servers.\n\n"
                    "Run: [bold cyan]mcpbr benchmarks[/bold cyan]\n\n"
                    "This shows all available benchmarks including:\n"
                    "  - [cyan]swe-bench-verified[/cyan] - Real GitHub issues (gold standard)\n"
                    "  - [cyan]humaneval[/cyan] - Code generation tasks\n"
                    "  - [cyan]mbpp[/cyan] - Mostly basic programming problems\n"
                    "  - [cyan]cybergym[/cyan] - Security-focused challenges\n"
                    "  - And more!"
                ),
                action="info",
            ),
            TutorialStep(
                id="list-models",
                title="List Supported Models",
                content=(
                    "mcpbr works with multiple LLM providers and models.\n\n"
                    "Run: [bold cyan]mcpbr models[/bold cyan]\n\n"
                    "This shows all supported models with their providers,\n"
                    "input/output pricing, and context window sizes."
                ),
                action="info",
            ),
            TutorialStep(
                id="create-config",
                title="Create Your First Configuration",
                content=(
                    "Create a file called [bold]mcpbr.yaml[/bold] with this content:\n\n"
                    "[dim]─────────────────────────────────────[/dim]\n"
                    "[green]mcp_server:[/green]\n"
                    "[green]  command:[/green] npx\n"
                    "[green]  args:[/green] -y @modelcontextprotocol/server-filesystem "
                    "{workdir}\n\n"
                    "[green]benchmark:[/green] humaneval\n"
                    "[green]model:[/green] claude-sonnet-4-20250514\n"
                    "[green]provider:[/green] anthropic\n"
                    "[green]sample_size:[/green] 2\n"
                    "[dim]─────────────────────────────────────[/dim]\n\n"
                    "Or use the quick command:\n"
                    "  [bold cyan]mcpbr init -t quick-test -o mcpbr.yaml[/bold cyan]"
                ),
                hint="You can also run 'mcpbr init -i' for an interactive config wizard.",
                action="info",
            ),
            TutorialStep(
                id="run-evaluation",
                title="Run Your First Evaluation",
                content=(
                    "Now run the evaluation with:\n\n"
                    "  [bold cyan]mcpbr run -c mcpbr.yaml[/bold cyan]\n\n"
                    "This will:\n"
                    "  1. Validate your configuration\n"
                    "  2. Pull the benchmark dataset\n"
                    "  3. Set up Docker containers\n"
                    "  4. Run the MCP-assisted agent on each task\n"
                    "  5. Run a baseline agent (without MCP) for comparison\n"
                    "  6. Report results"
                ),
                hint="Use --skip-preflight to skip pre-flight checks if they fail.",
                action="info",
            ),
            TutorialStep(
                id="understanding-results",
                title="Understanding Results",
                content=(
                    "After a run completes, mcpbr reports:\n\n"
                    "  [bold]Resolution Rate[/bold] - % of tasks solved correctly\n"
                    "    Higher is better. Compares MCP vs baseline.\n\n"
                    "  [bold]Cost[/bold] - Total API cost in USD\n"
                    "    Tracks input/output tokens and their costs.\n\n"
                    "  [bold]Tokens[/bold] - Total tokens consumed\n"
                    "    Input tokens (prompt) and output tokens (completion).\n\n"
                    "  [bold]Per-task details[/bold] - Individual task outcomes\n"
                    "    Shows which tasks were resolved, failed, or errored."
                ),
                action="info",
            ),
            TutorialStep(
                id="next-steps",
                title="Next Steps",
                content=(
                    "[bold green]Congratulations![/bold green] "
                    "You've completed the Getting Started tutorial.\n\n"
                    "Continue learning with these tutorials:\n"
                    "  [cyan]mcpbr tutorial start configuration[/cyan]  "
                    "- Deep dive into configuration\n"
                    "  [cyan]mcpbr tutorial start benchmarks[/cyan]     "
                    "- Choosing & running benchmarks\n"
                    "  [cyan]mcpbr tutorial start analytics[/cyan]      "
                    "- Analytics & reporting\n\n"
                    "Run [bold cyan]mcpbr tutorial list[/bold cyan] to see all tutorials."
                ),
                action="info",
            ),
        ],
    ),
    "configuration": Tutorial(
        id="configuration",
        title="Configuration Deep Dive",
        description="Master mcpbr configuration: YAML structure, providers, benchmarks, and more.",
        difficulty="intermediate",
        estimated_minutes=15,
        steps=[
            TutorialStep(
                id="config-formats",
                title="Config File Formats",
                content=(
                    "[bold]mcpbr Configuration Overview[/bold]\n\n"
                    "mcpbr uses YAML configuration files. The structure has these top-level keys:\n\n"
                    "  [cyan]mcp_server[/cyan]    - MCP server connection settings\n"
                    "  [cyan]model[/cyan]          - LLM model to use\n"
                    "  [cyan]provider[/cyan]       - Model provider (anthropic, openai, etc.)\n"
                    "  [cyan]benchmark[/cyan]      - Which benchmark to run\n"
                    "  [cyan]sample_size[/cyan]    - Number of tasks to evaluate\n"
                    "  [cyan]budget[/cyan]         - Maximum spend in USD\n"
                    "  [cyan]timeout_seconds[/cyan] - Per-task timeout\n\n"
                    "Config files are validated before each run."
                ),
                action="info",
            ),
            TutorialStep(
                id="mcp-server-config",
                title="MCP Server Configuration",
                content=(
                    "[bold]MCP Server Settings[/bold]\n\n"
                    "The [cyan]mcp_server[/cyan] block defines how to launch your MCP server:\n\n"
                    "  [green]mcp_server:[/green]\n"
                    "    [green]command:[/green] npx          # Executable to run\n"
                    "    [green]args:[/green] -y @org/server  # Command arguments\n"
                    "    [green]env:[/green]                  # Environment variables\n"
                    "      API_KEY: ${MY_API_KEY}\n"
                    "    [green]setup_command:[/green] npm install  # Run before starting\n\n"
                    "Environment variables support ${VAR} expansion from your shell."
                ),
                action="info",
            ),
            TutorialStep(
                id="model-provider-selection",
                title="Model & Provider Selection",
                content=(
                    "[bold]Choosing Models & Providers[/bold]\n\n"
                    "mcpbr supports multiple providers:\n"
                    "  - [cyan]anthropic[/cyan] - Claude models (default)\n"
                    "  - [cyan]openai[/cyan] - GPT models\n"
                    "  - [cyan]google[/cyan] - Gemini models\n\n"
                    "Use model aliases for convenience:\n"
                    "  [green]model:[/green] claude-sonnet  # Resolves to latest Sonnet\n"
                    "  [green]model:[/green] gpt-4o         # OpenAI GPT-4o\n\n"
                    "Run [bold cyan]mcpbr models[/bold cyan] to see all options with pricing."
                ),
                action="info",
            ),
            TutorialStep(
                id="benchmark-selection",
                title="Benchmark Selection & Filtering",
                content=(
                    "[bold]Selecting & Filtering Benchmarks[/bold]\n\n"
                    "Choose a benchmark and optionally filter tasks:\n\n"
                    "  [green]benchmark:[/green] swe-bench-verified\n"
                    "  [green]filter_difficulty:[/green] [easy, medium]\n"
                    "  [green]filter_category:[/green] [bug-fix]\n"
                    "  [green]filter_tags:[/green] [python, django]\n\n"
                    "Filtering helps focus evaluations on specific task types."
                ),
                action="info",
            ),
            TutorialStep(
                id="sample-sizing",
                title="Sample Sizing & Budgets",
                content=(
                    "[bold]Controlling Evaluation Scope[/bold]\n\n"
                    "  [green]sample_size:[/green] 10      # Run only 10 tasks\n"
                    "  [green]budget:[/green] 5.00          # Stop at $5.00 spend\n"
                    "  [green]timeout_seconds:[/green] 300  # 5-minute per-task timeout\n\n"
                    "Start small with sample_size: 2-5 to validate your setup,\n"
                    "then increase for meaningful results (50+ tasks recommended)."
                ),
                action="info",
            ),
            TutorialStep(
                id="comparison-mode",
                title="Comparison Mode",
                content=(
                    "[bold]A/B Comparison Mode[/bold]\n\n"
                    "Compare two MCP server configurations side by side:\n\n"
                    "  [green]mcp_server_a:[/green]\n"
                    "    command: npx\n"
                    "    args: -y @org/server-v1\n\n"
                    "  [green]mcp_server_b:[/green]\n"
                    "    command: npx\n"
                    "    args: -y @org/server-v2\n\n"
                    "Run with: [bold cyan]mcpbr compare run_a.json run_b.json[/bold cyan]"
                ),
                action="info",
            ),
            TutorialStep(
                id="using-templates",
                title="Using Templates",
                content=(
                    "[bold]Configuration Templates[/bold]\n\n"
                    "mcpbr includes pre-built templates for common setups:\n\n"
                    "  [bold cyan]mcpbr templates[/bold cyan]           "
                    "# List all templates\n"
                    "  [bold cyan]mcpbr init -t quick-test[/bold cyan]  "
                    "# Generate from template\n"
                    "  [bold cyan]mcpbr init -i[/bold cyan]             "
                    "# Interactive wizard\n\n"
                    "Templates provide a starting point that you can customize."
                ),
                action="info",
            ),
            TutorialStep(
                id="advanced-options",
                title="Advanced Options",
                content=(
                    "[bold]Advanced Configuration[/bold]\n\n"
                    "  [cyan]Caching[/cyan] - Cache results to skip repeated evaluations\n"
                    "    [bold cyan]mcpbr cache stats[/bold cyan]\n\n"
                    "  [cyan]Profiling[/cyan] - Measure performance with --profile flag\n"
                    "    [bold cyan]mcpbr run -c config.yaml --profile[/bold cyan]\n\n"
                    "  [cyan]Checkpointing[/cyan] - Resume interrupted evaluations\n"
                    "    [bold cyan]mcpbr run -c config.yaml --state-dir ./state[/bold cyan]\n\n"
                    "  [cyan]Incremental runs[/cyan] - Only re-run failed tasks\n"
                    "    [bold cyan]mcpbr run -c config.yaml --retry-failed[/bold cyan]"
                ),
                action="info",
            ),
            TutorialStep(
                id="config-validation",
                title="Validation",
                content=(
                    "[bold]Validating Your Configuration[/bold]\n\n"
                    "Always validate before running:\n\n"
                    "  [bold cyan]mcpbr config validate config.yaml[/bold cyan]\n\n"
                    "This checks:\n"
                    "  - YAML syntax is valid\n"
                    "  - Required fields are present\n"
                    "  - Model/provider/benchmark are recognized\n"
                    "  - MCP server command is specified\n"
                    "  - No conflicting options"
                ),
                action="info",
            ),
        ],
    ),
    "benchmarks": Tutorial(
        id="benchmarks",
        title="Choosing & Running Benchmarks",
        description="Understand available benchmarks and how to select the right one.",
        difficulty="intermediate",
        estimated_minutes=15,
        steps=[
            TutorialStep(
                id="benchmark-overview",
                title="Benchmark Overview",
                content=(
                    "[bold]What Benchmarks Measure[/bold]\n\n"
                    "Benchmarks evaluate how well an LLM agent (with or without MCP tools)\n"
                    "can complete real-world tasks.\n\n"
                    "Key metrics:\n"
                    "  [cyan]Resolution rate[/cyan] - % of tasks completed correctly\n"
                    "  [cyan]Cost efficiency[/cyan] - Cost per resolved task\n"
                    "  [cyan]Token usage[/cyan] - Total tokens consumed\n"
                    "  [cyan]Latency[/cyan] - Time per task"
                ),
                action="info",
            ),
            TutorialStep(
                id="swe-benchmarks",
                title="Software Engineering Benchmarks",
                content=(
                    "[bold]SWE-bench Family[/bold]\n\n"
                    "  [cyan]swe-bench-verified[/cyan] (recommended)\n"
                    "    Human-verified subset of SWE-bench. Real GitHub issues\n"
                    "    from popular Python projects. Gold standard for evaluation.\n\n"
                    "  [cyan]swe-bench-lite[/cyan]\n"
                    "    Smaller curated subset. Good for quick evaluations.\n\n"
                    "  [cyan]swe-bench-full[/cyan]\n"
                    "    Complete dataset. 2000+ tasks. Very time-consuming."
                ),
                action="info",
            ),
            TutorialStep(
                id="code-gen-benchmarks",
                title="Code Generation Benchmarks",
                content=(
                    "[bold]Code Generation Benchmarks[/bold]\n\n"
                    "  [cyan]humaneval[/cyan]\n"
                    "    164 hand-crafted Python programming problems.\n"
                    "    Tests function-level code generation.\n\n"
                    "  [cyan]mbpp[/cyan]\n"
                    "    Mostly Basic Programming Problems.\n"
                    "    974 crowd-sourced Python tasks with test cases.\n\n"
                    "These are great for quick smoke-tests of your setup."
                ),
                action="info",
            ),
            TutorialStep(
                id="security-benchmarks",
                title="Security Benchmarks",
                content=(
                    "[bold]Security Benchmarks[/bold]\n\n"
                    "  [cyan]cybergym[/cyan]\n"
                    "    Security-focused challenges at multiple difficulty levels:\n"
                    "      - Level 1: Basic security tasks\n"
                    "      - Level 2: Intermediate challenges\n"
                    "      - Level 3: Advanced security scenarios\n\n"
                    "    Configure with:\n"
                    "      [green]benchmark:[/green] cybergym\n"
                    "      [green]cybergym_level:[/green] 1"
                ),
                action="info",
            ),
            TutorialStep(
                id="tool-use-benchmarks",
                title="Tool Use Benchmarks",
                content=(
                    "[bold]Tool Use Benchmarks[/bold]\n\n"
                    "  [cyan]mcptoolbench[/cyan]\n"
                    "    Tests how well agents use MCP tools for various tasks.\n"
                    "    Specifically designed for MCP server evaluation.\n\n"
                    "  [cyan]toolbench[/cyan]\n"
                    "    General tool-use benchmark. Tests the agent's ability\n"
                    "    to select and use the right tools for each task."
                ),
                action="info",
            ),
            TutorialStep(
                id="filtering-tasks",
                title="Filtering Tasks",
                content=(
                    "[bold]Filtering Benchmark Tasks[/bold]\n\n"
                    "Narrow your evaluation to specific task types:\n\n"
                    "  [green]filter_difficulty:[/green] [easy, medium]\n"
                    "  [green]filter_category:[/green] [bug-fix, feature]\n"
                    "  [green]filter_tags:[/green] [python, django, numpy]\n\n"
                    "Combine filters to focus on exactly the tasks you care about.\n"
                    "All filters are AND-ed together."
                ),
                action="info",
            ),
            TutorialStep(
                id="interpreting-results",
                title="Interpreting Results",
                content=(
                    "[bold]Understanding Benchmark Results[/bold]\n\n"
                    "  [cyan]Resolution rate[/cyan]\n"
                    "    MCP: 45% vs Baseline: 30% means the MCP server helps.\n"
                    "    Look for statistically significant differences.\n\n"
                    "  [cyan]Cost efficiency[/cyan]\n"
                    "    $0.50/task (MCP) vs $0.30/task (baseline)\n"
                    "    Higher cost is acceptable if resolution rate improves.\n\n"
                    "  [cyan]Cost per resolved task[/cyan]\n"
                    "    The most useful metric: total cost / resolved tasks."
                ),
                action="info",
            ),
            TutorialStep(
                id="comparing-runs",
                title="Comparing Runs",
                content=(
                    "[bold]Comparing Multiple Runs[/bold]\n\n"
                    "Compare two result files side by side:\n\n"
                    "  [bold cyan]mcpbr compare run1.json run2.json[/bold cyan]\n\n"
                    "Options:\n"
                    "  [dim]--output-html report.html[/dim]  Generate HTML report\n"
                    "  [dim]--output-markdown report.md[/dim]  Generate Markdown\n\n"
                    "The comparison shows resolution rate, cost, and token differences\n"
                    "with statistical significance testing."
                ),
                action="info",
            ),
            TutorialStep(
                id="best-practices",
                title="Best Practices for Benchmarking",
                content=(
                    "[bold]Benchmarking Best Practices[/bold]\n\n"
                    "  1. [cyan]Start small[/cyan] - Use sample_size: 2-5 to validate setup\n"
                    "  2. [cyan]Use verified benchmarks[/cyan] - swe-bench-verified over full\n"
                    "  3. [cyan]Set budgets[/cyan] - Prevent runaway costs\n"
                    "  4. [cyan]Run both modes[/cyan] - Always compare MCP vs baseline\n"
                    "  5. [cyan]Use enough samples[/cyan] - 50+ tasks for reliable results\n"
                    "  6. [cyan]Check significance[/cyan] - Don't trust small differences\n"
                    "  7. [cyan]Document configs[/cyan] - Save configs with results\n"
                    "  8. [cyan]Iterate[/cyan] - Improve your MCP server based on results"
                ),
                action="info",
            ),
        ],
    ),
    "analytics": Tutorial(
        id="analytics",
        title="Analytics & Reporting",
        description="Track results over time, generate reports, and detect regressions.",
        difficulty="advanced",
        estimated_minutes=20,
        steps=[
            TutorialStep(
                id="analytics-overview",
                title="Analytics Overview",
                content=(
                    "[bold]mcpbr Analytics System[/bold]\n\n"
                    "mcpbr includes a built-in analytics system for:\n\n"
                    "  - [cyan]Storing[/cyan] evaluation results in a local database\n"
                    "  - [cyan]Trending[/cyan] performance metrics over time\n"
                    "  - [cyan]Ranking[/cyan] models and servers on leaderboards\n"
                    "  - [cyan]Detecting[/cyan] performance regressions\n"
                    "  - [cyan]Generating[/cyan] publication-ready reports"
                ),
                action="info",
            ),
            TutorialStep(
                id="storing-results",
                title="Storing Results",
                content=(
                    "[bold]Storing Evaluation Results[/bold]\n\n"
                    "After running an evaluation, store the results:\n\n"
                    "  [bold cyan]mcpbr analytics store results.json[/bold cyan]\n\n"
                    "This saves the results to a local SQLite database at\n"
                    "~/.mcpbr/analytics.db for trend tracking and comparison."
                ),
                action="info",
            ),
            TutorialStep(
                id="trend-analysis",
                title="Trend Analysis",
                content=(
                    "[bold]Analyzing Trends[/bold]\n\n"
                    "Track how metrics change over time:\n\n"
                    "  [bold cyan]mcpbr analytics trends "
                    "--metric resolution_rate[/bold cyan]\n"
                    "  [bold cyan]mcpbr analytics trends "
                    "--metric total_cost[/bold cyan]\n"
                    "  [bold cyan]mcpbr analytics trends "
                    "--metric avg_tokens[/bold cyan]\n\n"
                    "Filter by model, provider, or benchmark:\n"
                    "  [dim]--model claude-sonnet-4-20250514[/dim]\n"
                    "  [dim]--benchmark swe-bench-verified[/dim]"
                ),
                action="info",
            ),
            TutorialStep(
                id="leaderboards",
                title="Leaderboards",
                content=(
                    "[bold]Generating Leaderboards[/bold]\n\n"
                    "Rank models and servers by performance:\n\n"
                    "  [bold cyan]mcpbr analytics leaderboard[/bold cyan]\n"
                    "  [bold cyan]mcpbr analytics leaderboard "
                    "--sort-by cost_efficiency[/bold cyan]\n\n"
                    "Export as Markdown:\n"
                    "  [bold cyan]mcpbr analytics leaderboard "
                    "--md leaderboard.md[/bold cyan]"
                ),
                action="info",
            ),
            TutorialStep(
                id="regression-detection",
                title="Regression Detection",
                content=(
                    "[bold]Detecting Regressions[/bold]\n\n"
                    "Compare two runs for significant regressions:\n\n"
                    "  [bold cyan]mcpbr analytics regression "
                    "--baseline v1.json --current v2.json[/bold cyan]\n\n"
                    "Options:\n"
                    "  [dim]--threshold 0.05[/dim]  Significance level (default: 0.05)\n\n"
                    "Exits with non-zero code if regressions detected,\n"
                    "making it ideal for CI/CD pipelines."
                ),
                action="info",
            ),
            TutorialStep(
                id="html-reports",
                title="HTML Reports",
                content=(
                    "[bold]Generating HTML Reports[/bold]\n\n"
                    "Create rich, interactive HTML reports:\n\n"
                    "  [bold cyan]mcpbr run -c config.yaml "
                    "--output-html report.html[/bold cyan]\n\n"
                    "HTML reports include:\n"
                    "  - Summary statistics with charts\n"
                    "  - Per-task detail tables\n"
                    "  - Cost breakdowns\n"
                    "  - MCP vs baseline comparison"
                ),
                action="info",
            ),
            TutorialStep(
                id="markdown-reports",
                title="Markdown Reports",
                content=(
                    "[bold]Generating Markdown Reports[/bold]\n\n"
                    "Create reports suitable for GitHub, docs, or wikis:\n\n"
                    "  [bold cyan]mcpbr run -c config.yaml "
                    "--output-markdown report.md[/bold cyan]\n\n"
                    "Markdown reports are great for:\n"
                    "  - Including in pull requests\n"
                    "  - Documentation sites\n"
                    "  - Sharing with teams"
                ),
                action="info",
            ),
            TutorialStep(
                id="pdf-reports",
                title="PDF Reports",
                content=(
                    "[bold]Generating PDF Reports[/bold]\n\n"
                    "Create publication-ready PDF reports:\n\n"
                    "  [bold cyan]mcpbr run -c config.yaml "
                    "--output-pdf report.pdf[/bold cyan]\n\n"
                    "PDF reports are ideal for:\n"
                    "  - Formal documentation\n"
                    "  - Stakeholder presentations\n"
                    "  - Archival purposes"
                ),
                action="info",
            ),
            TutorialStep(
                id="statistical-comparison",
                title="Statistical Comparison",
                content=(
                    "[bold]Statistical Comparison[/bold]\n\n"
                    "Compare runs with statistical rigor:\n\n"
                    "  [bold cyan]mcpbr compare run1.json run2.json[/bold cyan]\n\n"
                    "The comparison includes:\n"
                    "  - Fisher's exact test for resolution rate\n"
                    "  - Mann-Whitney U test for cost distributions\n"
                    "  - Confidence intervals for all metrics\n"
                    "  - Effect size calculations\n\n"
                    "[bold green]Tutorial complete![/bold green] "
                    "You now know how to track, analyze,\n"
                    "and report on your MCP server evaluations."
                ),
                action="info",
            ),
        ],
    ),
}


class TutorialEngine:
    """Engine for managing and running interactive tutorials.

    Handles tutorial discovery, progress tracking, and step validation.

    Args:
        progress_dir: Directory for storing progress files.
            Defaults to ~/.mcpbr/tutorials/.
    """

    def __init__(self, progress_dir: Path | None = None) -> None:
        """Initialize the tutorial engine.

        Args:
            progress_dir: Directory for storing progress JSON files.
                Defaults to ~/.mcpbr/tutorials/.
        """
        if progress_dir is None:
            self.progress_dir = Path.home() / ".mcpbr" / "tutorials"
        else:
            self.progress_dir = progress_dir

    def list_tutorials(self) -> list[Tutorial]:
        """Return all available tutorials.

        Returns:
            List of all built-in Tutorial objects.
        """
        return list(TUTORIALS.values())

    def get_tutorial(self, tutorial_id: str) -> Tutorial | None:
        """Get a tutorial by its identifier.

        Args:
            tutorial_id: The unique tutorial ID.

        Returns:
            The Tutorial if found, or None.
        """
        return TUTORIALS.get(tutorial_id)

    def start_tutorial(self, tutorial_id: str) -> TutorialProgress:
        """Start or resume a tutorial.

        If saved progress exists, it is loaded and returned.
        Otherwise, new progress is created and saved.

        Args:
            tutorial_id: The tutorial to start.

        Returns:
            The current TutorialProgress.

        Raises:
            ValueError: If the tutorial_id is not recognized.
        """
        tutorial = self.get_tutorial(tutorial_id)
        if tutorial is None:
            raise ValueError(f"Unknown tutorial: {tutorial_id}")

        existing = self.get_progress(tutorial_id)
        if existing is not None:
            return existing

        progress = TutorialProgress(
            tutorial_id=tutorial_id,
            current_step=0,
            completed_steps=[],
            started_at=datetime.now(UTC).isoformat(),
            completed_at=None,
        )
        self.save_progress(progress)
        return progress

    def get_progress(self, tutorial_id: str) -> TutorialProgress | None:
        """Load saved progress for a tutorial.

        Args:
            tutorial_id: The tutorial whose progress to load.

        Returns:
            The saved TutorialProgress, or None if no progress exists.
        """
        progress_file = self.progress_dir / f"{tutorial_id}.json"
        if not progress_file.exists():
            return None

        try:
            data = json.loads(progress_file.read_text())
            return TutorialProgress(
                tutorial_id=data["tutorial_id"],
                current_step=data.get("current_step", 0),
                completed_steps=data.get("completed_steps", []),
                started_at=data.get("started_at", ""),
                completed_at=data.get("completed_at"),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def save_progress(self, progress: TutorialProgress) -> None:
        """Save tutorial progress to disk.

        Args:
            progress: The TutorialProgress to persist.
        """
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        progress_file = self.progress_dir / f"{progress.tutorial_id}.json"
        data = {
            "tutorial_id": progress.tutorial_id,
            "current_step": progress.current_step,
            "completed_steps": progress.completed_steps,
            "started_at": progress.started_at,
            "completed_at": progress.completed_at,
        }
        progress_file.write_text(json.dumps(data, indent=2))

    def complete_step(self, progress: TutorialProgress, step_id: str) -> TutorialProgress:
        """Mark a step as completed and advance progress.

        Args:
            progress: The current progress object.
            step_id: The ID of the step to mark complete.

        Returns:
            Updated TutorialProgress with the step marked complete.
        """
        if step_id not in progress.completed_steps:
            progress.completed_steps.append(step_id)

        tutorial = self.get_tutorial(progress.tutorial_id)
        if tutorial is not None:
            # Advance current_step to the next incomplete step
            for i, step in enumerate(tutorial.steps):
                if step.id not in progress.completed_steps:
                    progress.current_step = i
                    break
            else:
                # All steps completed
                progress.current_step = len(tutorial.steps)
                progress.completed_at = datetime.now(UTC).isoformat()

        self.save_progress(progress)
        return progress

    def reset_tutorial(self, tutorial_id: str) -> None:
        """Delete saved progress for a tutorial.

        Args:
            tutorial_id: The tutorial whose progress to reset.
        """
        progress_file = self.progress_dir / f"{tutorial_id}.json"
        if progress_file.exists():
            progress_file.unlink()

    def validate_step(self, step: TutorialStep) -> tuple[bool, str]:
        """Validate a step's condition.

        Supports the following validation types:
          - "file_exists:<path>" - checks if the file exists
          - "command_runs:<cmd>" - checks if the command exits with code 0
          - None - always passes

        Args:
            step: The TutorialStep to validate.

        Returns:
            A tuple of (success, message). On success the message is empty.
            On failure the message describes what went wrong.
        """
        if step.validation is None:
            return (True, "")

        if step.validation.startswith("file_exists:"):
            filepath = step.validation[len("file_exists:") :]
            if Path(filepath).exists():
                return (True, "")
            return (False, f"File not found: {filepath}")

        if step.validation.startswith("command_runs:"):
            cmd = step.validation[len("command_runs:") :]
            try:
                result = subprocess.run(  # noqa: S602 -- tutorial validation runs user-defined shell commands by design
                    cmd,
                    shell=True,
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return (True, "")
                return (False, f"Command failed with exit code {result.returncode}: {cmd}")
            except subprocess.TimeoutExpired:
                return (False, f"Command timed out: {cmd}")
            except OSError as e:
                return (False, f"Command error: {e}")

        return (False, f"Unknown validation type: {step.validation}")
