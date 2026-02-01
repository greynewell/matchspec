"""Reporting utilities for evaluation results."""

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from rich.console import Console
from rich.table import Table

from .pricing import format_cost

if TYPE_CHECKING:
    from .harness import EvaluationResults
    from .statistics import ComprehensiveStatistics


def format_runtime(seconds: float) -> str:
    """Format runtime in seconds to human-readable format.

    Args:
        seconds: Runtime in seconds.

    Returns:
        Formatted string (e.g., "45m 23s", "1h 5m 30s", "15s").
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"


class ToolCoverageReport:
    """Analyzes tool coverage across evaluation runs.

    Tracks which MCP tools are available vs. actually used to help developers
    understand tool discoverability and usefulness.
    """

    def __init__(self, available_tools: list[str] | None = None) -> None:
        """Initialize tool coverage report.

        Args:
            available_tools: List of available MCP tool names. If None, will be
                inferred from usage data.
        """
        self.available_tools = set(available_tools) if available_tools else set()
        self.tool_usage_counter: Counter[str] = Counter()

    def add_task_usage(self, tool_usage: dict[str, int]) -> None:
        """Add tool usage from a single task.

        Args:
            tool_usage: Dictionary mapping tool names to call counts.
        """
        self.tool_usage_counter.update(tool_usage)
        # Track all tools that were used (for when available_tools not provided)
        self.available_tools.update(tool_usage.keys())

    def get_coverage_metrics(self) -> dict[str, int | float | list[str]]:
        """Calculate coverage metrics.

        Returns:
            Dictionary with coverage metrics including:
            - total_available: Total number of available tools
            - total_used: Number of tools actually used
            - coverage_rate: Percentage of tools used (0-1)
            - unused_tools: List of tools that were never called
            - most_used: List of (tool_name, count) tuples for most used tools
            - least_used: List of (tool_name, count) tuples for least used tools
        """
        used_tools = set(self.tool_usage_counter.keys())
        unused_tools = sorted(self.available_tools - used_tools)

        total_available = len(self.available_tools)
        total_used = len(used_tools)
        coverage_rate = total_used / total_available if total_available > 0 else 0.0

        # Get most and least used tools (among those that were used)
        most_used = self.tool_usage_counter.most_common(10)
        least_used = self.tool_usage_counter.most_common()[:-11:-1] if used_tools else []

        return {
            "total_available": total_available,
            "total_used": total_used,
            "coverage_rate": coverage_rate,
            "unused_tools": unused_tools,
            "most_used": most_used,
            "least_used": least_used,
        }

    def to_dict(self) -> dict[str, int | float | list[str] | dict[str, int]]:
        """Convert coverage report to dictionary format.

        Returns:
            Dictionary representation suitable for JSON/YAML serialization.
        """
        metrics = self.get_coverage_metrics()
        return {
            "total_available": metrics["total_available"],
            "total_used": metrics["total_used"],
            "coverage_rate": metrics["coverage_rate"],
            "unused_tools": metrics["unused_tools"],
            "most_used": dict(metrics["most_used"]),
            "least_used": dict(metrics["least_used"]),
            "all_tool_usage": dict(self.tool_usage_counter),
        }


def calculate_tool_coverage(
    results: "EvaluationResults", available_tools: list[str] | None = None
) -> dict[str, int | float | list[str] | dict[str, int]]:
    """Calculate tool coverage from evaluation results.

    Args:
        results: Evaluation results containing task data.
        available_tools: Optional list of available tool names. If not provided,
            will be inferred from tool usage data.

    Returns:
        Dictionary with tool coverage metrics.
    """
    coverage = ToolCoverageReport(available_tools)

    # Collect tool usage from all tasks (MCP agent only)
    for task in results.tasks:
        if task.mcp and task.mcp.get("tool_usage"):
            coverage.add_task_usage(task.mcp["tool_usage"])

    return coverage.to_dict()


def print_comprehensive_statistics(stats: "ComprehensiveStatistics", console: Console) -> None:
    """Print comprehensive statistics to the console.

    Args:
        stats: Comprehensive statistics object.
        console: Rich console for output.
    """
    # Token Usage Statistics
    console.print()
    console.print("[bold]Token Usage Statistics[/bold]")
    console.print()

    token_table = Table(title="Token Usage Comparison")
    token_table.add_column("Metric", style="cyan")
    token_table.add_column("MCP Agent", style="green", justify="right")
    token_table.add_column("Baseline", style="yellow", justify="right")

    token_table.add_row(
        "Total Input",
        f"{stats.mcp_tokens.total_input:,}",
        f"{stats.baseline_tokens.total_input:,}",
    )
    token_table.add_row(
        "Total Output",
        f"{stats.mcp_tokens.total_output:,}",
        f"{stats.baseline_tokens.total_output:,}",
    )
    token_table.add_row(
        "Total Tokens",
        f"{stats.mcp_tokens.total_tokens:,}",
        f"{stats.baseline_tokens.total_tokens:,}",
    )
    token_table.add_row(
        "Avg Input/Task",
        f"{stats.mcp_tokens.avg_input_per_task:,.0f}",
        f"{stats.baseline_tokens.avg_input_per_task:,.0f}",
    )
    token_table.add_row(
        "Avg Output/Task",
        f"{stats.mcp_tokens.avg_output_per_task:,.0f}",
        f"{stats.baseline_tokens.avg_output_per_task:,.0f}",
    )
    token_table.add_row(
        "Max Input/Task",
        f"{stats.mcp_tokens.max_input_per_task:,}",
        f"{stats.baseline_tokens.max_input_per_task:,}",
    )
    token_table.add_row(
        "Max Output/Task",
        f"{stats.mcp_tokens.max_output_per_task:,}",
        f"{stats.baseline_tokens.max_output_per_task:,}",
    )

    console.print(token_table)

    # Iteration Statistics
    console.print()
    console.print("[bold]Iteration Statistics[/bold]")
    console.print()

    iter_table = Table(title="Iteration Comparison")
    iter_table.add_column("Metric", style="cyan")
    iter_table.add_column("MCP Agent", style="green", justify="right")
    iter_table.add_column("Baseline", style="yellow", justify="right")

    iter_table.add_row(
        "Total Iterations",
        f"{stats.mcp_iterations.total_iterations:,}",
        f"{stats.baseline_iterations.total_iterations:,}",
    )
    iter_table.add_row(
        "Avg Iterations/Task",
        f"{stats.mcp_iterations.avg_iterations:.1f}",
        f"{stats.baseline_iterations.avg_iterations:.1f}",
    )
    iter_table.add_row(
        "Max Iterations",
        f"{stats.mcp_iterations.max_iterations}",
        f"{stats.baseline_iterations.max_iterations}",
    )
    iter_table.add_row(
        "Min Iterations",
        f"{stats.mcp_iterations.min_iterations}",
        f"{stats.baseline_iterations.min_iterations}",
    )

    console.print(iter_table)

    # Runtime Statistics
    if stats.mcp_runtime.total_runtime > 0 or stats.baseline_runtime.total_runtime > 0:
        console.print()
        console.print("[bold]Runtime Statistics[/bold]")
        console.print()

        runtime_table = Table(title="Runtime Comparison")
        runtime_table.add_column("Metric", style="cyan")
        runtime_table.add_column("MCP Agent", style="green", justify="right")
        runtime_table.add_column("Baseline", style="yellow", justify="right")

        runtime_table.add_row(
            "Total Runtime",
            format_runtime(stats.mcp_runtime.total_runtime),
            format_runtime(stats.baseline_runtime.total_runtime),
        )
        runtime_table.add_row(
            "Avg Runtime/Task",
            format_runtime(stats.mcp_runtime.avg_runtime_per_task),
            format_runtime(stats.baseline_runtime.avg_runtime_per_task),
        )
        if stats.mcp_runtime.runtime_per_resolved is not None:
            mcp_runtime_resolved = format_runtime(stats.mcp_runtime.runtime_per_resolved)
        else:
            mcp_runtime_resolved = "N/A"
        if stats.baseline_runtime.runtime_per_resolved is not None:
            baseline_runtime_resolved = format_runtime(stats.baseline_runtime.runtime_per_resolved)
        else:
            baseline_runtime_resolved = "N/A"
        runtime_table.add_row(
            "Runtime/Resolved",
            mcp_runtime_resolved,
            baseline_runtime_resolved,
        )
        runtime_table.add_row(
            "Min Runtime",
            format_runtime(stats.mcp_runtime.min_runtime),
            format_runtime(stats.baseline_runtime.min_runtime),
        )
        runtime_table.add_row(
            "Max Runtime",
            format_runtime(stats.mcp_runtime.max_runtime),
            format_runtime(stats.baseline_runtime.max_runtime),
        )

        console.print(runtime_table)

    # MCP Tool Statistics
    if stats.mcp_tools.total_calls > 0:
        console.print()
        console.print("[bold]MCP Tool Usage Statistics[/bold]")
        console.print()

        tool_summary = Table(title="Tool Call Summary")
        tool_summary.add_column("Metric", style="cyan")
        tool_summary.add_column("Value", style="green", justify="right")

        tool_summary.add_row("Total Calls", f"{stats.mcp_tools.total_calls:,}")
        tool_summary.add_row("Successful Calls", f"{stats.mcp_tools.total_successes:,}")
        tool_summary.add_row("Failed Calls", f"{stats.mcp_tools.total_failures:,}")
        tool_summary.add_row("Failure Rate", f"{stats.mcp_tools.failure_rate:.1%}")
        tool_summary.add_row("Unique Tools Used", f"{stats.mcp_tools.unique_tools_used}")
        tool_summary.add_row("Avg Calls/Task", f"{stats.mcp_tools.avg_calls_per_task:.1f}")

        console.print(tool_summary)

        # Most used tools
        if stats.mcp_tools.most_used_tools:
            console.print()
            console.print("[bold]Top 10 Most Used Tools:[/bold]")
            top_tools_table = Table()
            top_tools_table.add_column("Tool", style="cyan")
            top_tools_table.add_column("Calls", justify="right")
            top_tools_table.add_column("Success Rate", justify="right")

            for tool_name, count in stats.mcp_tools.most_used_tools[:10]:
                per_tool = stats.mcp_tools.per_tool.get(tool_name, {})
                success_rate = 1.0 - per_tool.get("failure_rate", 0.0)
                top_tools_table.add_row(tool_name, f"{count:,}", f"{success_rate:.1%}")

            console.print(top_tools_table)

        # Most failed tools
        if stats.mcp_tools.most_failed_tools and stats.mcp_tools.total_failures > 0:
            console.print()
            console.print("[bold]Top 10 Most Failed Tools:[/bold]")
            failed_tools_table = Table()
            failed_tools_table.add_column("Tool", style="cyan")
            failed_tools_table.add_column("Failures", justify="right")
            failed_tools_table.add_column("Failure Rate", justify="right", style="red")

            for tool_name, fail_count in stats.mcp_tools.most_failed_tools[:10]:
                per_tool = stats.mcp_tools.per_tool.get(tool_name, {})
                failure_rate = per_tool.get("failure_rate", 0.0)
                failed_tools_table.add_row(tool_name, f"{fail_count:,}", f"{failure_rate:.1%}")

            console.print(failed_tools_table)

    # Error Analysis
    if stats.mcp_errors.total_errors > 0 or stats.baseline_errors.total_errors > 0:
        console.print()
        console.print("[bold]Error Analysis[/bold]")
        console.print()

        error_table = Table(title="Error Comparison")
        error_table.add_column("Metric", style="cyan")
        error_table.add_column("MCP Agent", style="green", justify="right")
        error_table.add_column("Baseline", style="yellow", justify="right")

        error_table.add_row(
            "Total Errors",
            f"{stats.mcp_errors.total_errors}",
            f"{stats.baseline_errors.total_errors}",
        )
        error_table.add_row(
            "Error Rate",
            f"{stats.mcp_errors.error_rate:.1%}",
            f"{stats.baseline_errors.error_rate:.1%}",
        )
        error_table.add_row(
            "Timeout Count",
            f"{stats.mcp_errors.timeout_count}",
            f"{stats.baseline_errors.timeout_count}",
        )
        error_table.add_row(
            "Timeout Rate",
            f"{stats.mcp_errors.timeout_rate:.1%}",
            f"{stats.baseline_errors.timeout_rate:.1%}",
        )

        console.print(error_table)

        # MCP Error Categories
        if stats.mcp_errors.error_categories:
            console.print()
            console.print("[bold]MCP Error Categories:[/bold]")
            for category, count in sorted(
                stats.mcp_errors.error_categories.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                console.print(f"  {category}: {count}")

        # Baseline Error Categories
        if stats.baseline_errors.error_categories:
            console.print()
            console.print("[bold]Baseline Error Categories:[/bold]")
            for category, count in sorted(
                stats.baseline_errors.error_categories.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                console.print(f"  {category}: {count}")


def print_comparison_summary(results: "EvaluationResults", console: Console) -> None:
    """Print side-by-side comparison summary.

    Args:
        results: Evaluation results from comparison mode.
        console: Rich console for output.
    """
    if not results.summary.get("mcp_server_a"):
        # Not comparison mode, fallback to regular print_summary
        print_summary(results, console)
        return

    summary = results.summary
    comp = summary["comparison"]

    # Comparison title
    console.print()
    console.print("[bold cyan]Side-by-Side MCP Server Comparison[/bold cyan]")
    console.print()

    # Resolution comparison table
    table = Table(title="Resolution Rate Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column(summary["mcp_server_a"]["name"], style="green")
    table.add_column(summary["mcp_server_b"]["name"], style="yellow")
    table.add_column("Δ (A - B)", style="magenta")

    a_resolved = summary["mcp_server_a"]["resolved"]
    b_resolved = summary["mcp_server_b"]["resolved"]
    a_total = summary["mcp_server_a"]["total"]
    b_total = summary["mcp_server_b"]["total"]
    a_rate = summary["mcp_server_a"]["resolution_rate"]
    b_rate = summary["mcp_server_b"]["resolution_rate"]

    table.add_row(
        "Resolved Tasks",
        f"{a_resolved}/{a_total}",
        f"{b_resolved}/{b_total}",
        f"+{comp['a_vs_b_delta']}" if comp["a_vs_b_delta"] > 0 else str(comp["a_vs_b_delta"]),
    )
    table.add_row(
        "Resolution Rate",
        f"{a_rate:.1%}",
        f"{b_rate:.1%}",
        f"+{comp['a_vs_b_improvement_pct']:.1f}%"
        if comp["a_vs_b_improvement_pct"] > 0
        else f"{comp['a_vs_b_improvement_pct']:.1f}%",
    )

    console.print(table)

    # Per-task comparison table
    console.print()
    task_table = Table(title="Per-Task Results")
    task_table.add_column("Instance ID", style="cyan")
    task_table.add_column(summary["mcp_server_a"]["name"], style="green")
    task_table.add_column(summary["mcp_server_b"]["name"], style="yellow")
    task_table.add_column("Winner", style="magenta bold")

    for task in results.tasks:
        a_resolved = task.mcp_server_a and task.mcp_server_a.get("resolved")
        b_resolved = task.mcp_server_b and task.mcp_server_b.get("resolved")

        a_status = "[green]PASS[/green]" if a_resolved else "[red]FAIL[/red]"
        b_status = "[green]PASS[/green]" if b_resolved else "[red]FAIL[/red]"

        if a_resolved and not b_resolved:
            winner = f"[green]{summary['mcp_server_a']['name']}[/green]"
        elif b_resolved and not a_resolved:
            winner = f"[yellow]{summary['mcp_server_b']['name']}[/yellow]"
        elif a_resolved and b_resolved:
            winner = "[dim]Both[/dim]"
        else:
            winner = "[dim]Neither[/dim]"

        task_table.add_row(task.instance_id, a_status, b_status, winner)

    console.print(task_table)

    # Unique wins summary
    if comp["a_unique_wins"]:
        console.print()
        console.print(
            f"[green]✓ {summary['mcp_server_a']['name']} unique wins:[/green] "
            f"{len(comp['a_unique_wins'])} tasks"
        )
        for task_id in comp["a_unique_wins"][:5]:
            console.print(f"  - {task_id}")
        if len(comp["a_unique_wins"]) > 5:
            console.print(f"  ... and {len(comp['a_unique_wins']) - 5} more")

    if comp["b_unique_wins"]:
        console.print()
        console.print(
            f"[yellow]✓ {summary['mcp_server_b']['name']} unique wins:[/yellow] "
            f"{len(comp['b_unique_wins'])} tasks"
        )
        for task_id in comp["b_unique_wins"][:5]:
            console.print(f"  - {task_id}")
        if len(comp["b_unique_wins"]) > 5:
            console.print(f"  ... and {len(comp['b_unique_wins']) - 5} more")

    console.print()


def print_summary(results: "EvaluationResults", console: Console) -> None:
    """Print a summary of evaluation results to the console.

    Args:
        results: Evaluation results.
        console: Rich console for output.
    """
    console.print()
    console.print("[bold]Evaluation Results[/bold]")
    console.print()

    # Show incremental evaluation stats if enabled
    incremental = results.metadata.get("incremental", {})
    if incremental.get("enabled"):
        console.print("[cyan]Incremental Evaluation:[/cyan]")
        total = incremental.get("total_tasks", 0)
        cached = incremental.get("cached_tasks", 0)
        evaluated = incremental.get("evaluated_tasks", 0)
        console.print(f"  Total tasks: {total}")
        console.print(f"  Cached (skipped): {cached}")
        console.print(f"  Evaluated: {evaluated}")
        if incremental.get("resumed_from"):
            console.print(f"  Resumed from: {incremental['resumed_from']}")
        console.print()

    table = Table(title="Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("MCP Agent", style="green")
    table.add_column("Baseline", style="yellow")

    mcp = results.summary["mcp"]
    baseline = results.summary["baseline"]

    table.add_row(
        "Resolved",
        f"{mcp['resolved']}/{mcp['total']}",
        f"{baseline['resolved']}/{baseline['total']}",
    )
    table.add_row(
        "Resolution Rate",
        f"{mcp['rate']:.1%}",
        f"{baseline['rate']:.1%}",
    )

    console.print(table)
    console.print()
    console.print(f"[bold]Improvement:[/bold] {results.summary['improvement']}")

    # Print tool coverage if available
    tool_coverage = results.summary.get("tool_coverage")
    if tool_coverage:
        console.print()
        console.print("[bold]Tool Coverage Analysis[/bold]")
        console.print()

        coverage_table = Table(title="MCP Tool Usage")
        coverage_table.add_column("Metric", style="cyan")
        coverage_table.add_column("Value", style="green")

        coverage_table.add_row("Available Tools", str(tool_coverage.get("total_available", 0)))
        coverage_table.add_row("Used Tools", str(tool_coverage.get("total_used", 0)))
        coverage_rate = tool_coverage.get("coverage_rate", 0.0)
        coverage_table.add_row("Coverage Rate", f"{coverage_rate:.1%}")

        console.print(coverage_table)

        # Show most used tools
        most_used = tool_coverage.get("most_used", {})
        if most_used:
            console.print()
            console.print("[bold]Most Used Tools:[/bold]")
            for tool_name, count in list(most_used.items())[:5]:
                console.print(f"  {tool_name}: {count}")

        # Show unused tools
        unused_tools = tool_coverage.get("unused_tools", [])
        if unused_tools:
            console.print()
            console.print(f"[bold]Unused Tools ({len(unused_tools)}):[/bold]")
            for tool_name in unused_tools[:10]:
                console.print(f"  {tool_name}")
            if len(unused_tools) > 10:
                console.print(f"  ... and {len(unused_tools) - 10} more")

    # Print MCP tool call failure statistics
    mcp_tool_stats = results.summary.get("mcp_tool_stats")
    if mcp_tool_stats and mcp_tool_stats.get("total_tool_calls", 0) > 0:
        console.print()
        console.print("[bold]MCP Tool Call Statistics[/bold]")
        console.print()

        total_calls = mcp_tool_stats.get("total_tool_calls", 0)
        total_failures = mcp_tool_stats.get("total_failures", 0)
        failure_rate = mcp_tool_stats.get("failure_rate", 0.0)

        stats_table = Table(title="Tool Call Reliability")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")

        stats_table.add_row("Total Calls", f"{total_calls:,}")
        stats_table.add_row("Failed Calls", f"{total_failures:,}")
        stats_table.add_row("Failure Rate", f"{failure_rate:.1%}")

        console.print(stats_table)

        if mcp_tool_stats.get("high_failure_rate"):
            console.print()
            console.print(
                f"[bold yellow]⚠️  Warning: High failure rate detected ({failure_rate:.1%})[/bold yellow]"
            )
            console.print(
                "[dim]This may indicate MCP server issues or infrastructure problems.[/dim]"
            )

        # Show per-tool breakdown if there are failures
        if total_failures > 0:
            by_tool = mcp_tool_stats.get("by_tool", {})
            if by_tool:
                console.print()
                console.print("[bold]Per-Tool Breakdown:[/bold]")
                console.print()

                tool_table = Table()
                tool_table.add_column("Tool", style="cyan")
                tool_table.add_column("Total", justify="right")
                tool_table.add_column("Failed", justify="right")
                tool_table.add_column("Failure Rate", justify="right")

                # Filter to only tools with failures and sort by failure rate (descending)
                failing_tools = [
                    (name, stats) for name, stats in by_tool.items() if stats.get("failed", 0) > 0
                ]
                failing_tools.sort(key=lambda x: x[1].get("failure_rate", 0.0), reverse=True)

                for tool_name, stats in failing_tools[:10]:
                    total = stats.get("total", 0)
                    failed = stats.get("failed", 0)
                    rate = stats.get("failure_rate", 0.0)

                    # Color code by severity
                    rate_style = "bold red" if rate > 0.5 else "yellow" if rate > 0.1 else ""

                    tool_table.add_row(
                        tool_name,
                        f"{total:,}",
                        f"{failed:,}",
                        f"{rate:.1%}",
                        style=rate_style,
                    )

                console.print(tool_table)

                if len(failing_tools) > 10:
                    remaining = len(failing_tools) - 10
                    console.print(f"[dim]... and {remaining} more tools with failures[/dim]")

    # Print cost analysis
    console.print()
    console.print("[bold]Cost Analysis[/bold]")
    console.print()

    cost_table = Table(title="Cost Breakdown")
    cost_table.add_column("Metric", style="cyan")
    cost_table.add_column("MCP Agent", style="green")
    cost_table.add_column("Baseline", style="yellow")

    cost_table.add_row(
        "Total Cost",
        format_cost(mcp.get("total_cost")),
        format_cost(baseline.get("total_cost")),
    )
    cost_table.add_row(
        "Cost per Task",
        format_cost(mcp.get("cost_per_task")),
        format_cost(baseline.get("cost_per_task")),
    )
    cost_table.add_row(
        "Cost per Resolved",
        format_cost(mcp.get("cost_per_resolved")),
        format_cost(baseline.get("cost_per_resolved")),
    )

    console.print(cost_table)

    # Print cost comparison
    cost_comparison = results.summary.get("cost_comparison", {})
    total_diff = cost_comparison.get("total_difference")
    cost_per_additional = cost_comparison.get("cost_per_additional_resolution")

    if total_diff is not None:
        console.print()
        baseline_cost = baseline.get("total_cost", 0)
        if baseline_cost > 0:
            pct = abs(total_diff) / baseline_cost * 100
            if total_diff > 0:
                console.print(
                    f"[bold]MCP Additional Cost:[/bold] {format_cost(total_diff)} ({pct:+.1f}%)"
                )
            else:
                console.print(
                    f"[bold]MCP Cost Savings:[/bold] {format_cost(abs(total_diff))} ({pct:.1f}%)"
                )
        else:
            # No baseline cost available (e.g., --mcp-only mode)
            if total_diff > 0:
                console.print(
                    f"[bold]MCP Additional Cost:[/bold] {format_cost(total_diff)} (N/A - no baseline)"
                )
            else:
                console.print(
                    f"[bold]MCP Cost Savings:[/bold] {format_cost(abs(total_diff))} (N/A - no baseline)"
                )

    if cost_per_additional is not None:
        console.print(
            f"[bold]Cost per Additional Resolution:[/bold] {format_cost(cost_per_additional)}"
        )

    # Check if budget was specified
    budget = results.metadata["config"].get("budget")
    if budget is not None:
        total_spent = mcp.get("total_cost", 0) + baseline.get("total_cost", 0)
        console.print()
        console.print(f"[bold]Budget:[/bold] {format_cost(budget)}")
        console.print(f"[bold]Total Spent:[/bold] {format_cost(total_spent)}")
        if results.metadata["config"].get("budget_exceeded"):
            console.print("[yellow]Budget limit reached - evaluation halted early[/yellow]")

    # Print comprehensive statistics if available
    comprehensive_stats = results.summary.get("comprehensive_stats")
    if comprehensive_stats:
        from .statistics import ComprehensiveStatistics

        # Convert dict back to dataclass
        stats_obj = ComprehensiveStatistics()
        stats_dict = comprehensive_stats

        # Reconstruct the statistics object from the dict
        from .statistics import (
            CostStatistics,
            ErrorStatistics,
            IterationStatistics,
            RuntimeStatistics,
            TokenStatistics,
            ToolStatistics,
        )

        # Helper to convert dict to dataclass
        def dict_to_stats(cls, data):
            kwargs = {}
            for k, v in data.items():
                if k not in cls.__dataclass_fields__:
                    continue
                # Convert dict back to list of tuples for ToolStatistics fields
                if cls == ToolStatistics and k in ("most_used_tools", "most_failed_tools"):
                    kwargs[k] = list(v.items()) if isinstance(v, dict) else v
                else:
                    kwargs[k] = v
            return cls(**kwargs)

        stats_obj.mcp_tokens = dict_to_stats(TokenStatistics, stats_dict["mcp_tokens"])
        stats_obj.baseline_tokens = dict_to_stats(TokenStatistics, stats_dict["baseline_tokens"])
        stats_obj.mcp_costs = dict_to_stats(CostStatistics, stats_dict["mcp_costs"])
        stats_obj.baseline_costs = dict_to_stats(CostStatistics, stats_dict["baseline_costs"])
        stats_obj.mcp_tools = dict_to_stats(ToolStatistics, stats_dict["mcp_tools"])
        stats_obj.mcp_errors = dict_to_stats(ErrorStatistics, stats_dict["mcp_errors"])
        stats_obj.baseline_errors = dict_to_stats(ErrorStatistics, stats_dict["baseline_errors"])
        stats_obj.mcp_iterations = dict_to_stats(IterationStatistics, stats_dict["mcp_iterations"])
        stats_obj.baseline_iterations = dict_to_stats(
            IterationStatistics, stats_dict["baseline_iterations"]
        )
        stats_obj.mcp_runtime = dict_to_stats(RuntimeStatistics, stats_dict.get("mcp_runtime", {}))
        stats_obj.baseline_runtime = dict_to_stats(
            RuntimeStatistics, stats_dict.get("baseline_runtime", {})
        )

        print_comprehensive_statistics(stats_obj, console)

    console.print()
    console.print("[bold]Per-Task Results[/bold]")

    task_table = Table()
    task_table.add_column("Instance ID", style="dim")
    task_table.add_column("MCP", justify="center")
    task_table.add_column("Baseline", justify="center")
    task_table.add_column("Error", style="red", max_width=50)

    for task in results.tasks:
        mcp_status = (
            "[green]PASS[/green]" if task.mcp and task.mcp.get("resolved") else "[red]FAIL[/red]"
        )
        if task.mcp is None:
            mcp_status = "[dim]-[/dim]"

        baseline_status = (
            "[green]PASS[/green]"
            if task.baseline and task.baseline.get("resolved")
            else "[red]FAIL[/red]"
        )
        if task.baseline is None:
            baseline_status = "[dim]-[/dim]"

        error_msg = ""
        if task.mcp and task.mcp.get("error"):
            error_msg = task.mcp.get("error", "")
        elif task.baseline and task.baseline.get("error"):
            error_msg = task.baseline.get("error", "")

        if len(error_msg) > 50:
            error_msg = error_msg[:47] + "..."

        task_table.add_row(task.instance_id, mcp_status, baseline_status, error_msg)

    console.print(task_table)


def save_json_results(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results to a JSON file.

    Args:
        results: Evaluation results.
        output_path: Path to save the JSON file.
    """
    data = {
        "metadata": results.metadata,
        "summary": results.summary,
        "tasks": [],
    }

    for task in results.tasks:
        task_data = {
            "instance_id": task.instance_id,
        }
        if task.mcp:
            task_data["mcp"] = task.mcp
        if task.mcp_server_a:
            task_data["mcp_server_a"] = task.mcp_server_a
        if task.mcp_server_b:
            task_data["mcp_server_b"] = task.mcp_server_b
        if task.baseline:
            task_data["baseline"] = task.baseline
        data["tasks"].append(task_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


def save_yaml_results(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results to a YAML file.

    Args:
        results: Evaluation results.
        output_path: Path to save the YAML file.
    """
    data = {
        "metadata": results.metadata,
        "summary": results.summary,
        "tasks": [],
    }

    for task in results.tasks:
        task_data = {
            "instance_id": task.instance_id,
        }
        if task.mcp:
            task_data["mcp"] = task.mcp
        if task.mcp_server_a:
            task_data["mcp_server_a"] = task.mcp_server_a
        if task.mcp_server_b:
            task_data["mcp_server_b"] = task.mcp_server_b
        if task.baseline:
            task_data["baseline"] = task.baseline
        data["tasks"].append(task_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def save_xml_results(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results to an XML file.

    Args:
        results: Evaluation results.
        output_path: Path to save the XML file.
    """
    root = ET.Element("evaluation_results")

    # Add metadata section
    metadata_elem = ET.SubElement(root, "metadata")
    _dict_to_xml(results.metadata, metadata_elem)

    # Add summary section
    summary_elem = ET.SubElement(root, "summary")
    _dict_to_xml(results.summary, summary_elem)

    # Add tasks section
    tasks_elem = ET.SubElement(root, "tasks")
    for task in results.tasks:
        task_elem = ET.SubElement(tasks_elem, "task")
        task_elem.set("instance_id", task.instance_id)

        if task.mcp:
            mcp_elem = ET.SubElement(task_elem, "mcp")
            _dict_to_xml(task.mcp, mcp_elem)

        if task.mcp_server_a:
            mcp_a_elem = ET.SubElement(task_elem, "mcp_server_a")
            _dict_to_xml(task.mcp_server_a, mcp_a_elem)

        if task.mcp_server_b:
            mcp_b_elem = ET.SubElement(task_elem, "mcp_server_b")
            _dict_to_xml(task.mcp_server_b, mcp_b_elem)

        if task.baseline:
            baseline_elem = ET.SubElement(task_elem, "baseline")
            _dict_to_xml(task.baseline, baseline_elem)

    # Pretty print the XML
    ET.indent(root, space="  ", level=0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def _dict_to_xml(data: dict | list | str | int | float | bool | None, parent: ET.Element) -> None:
    """Convert a dictionary or other data structure to XML elements.

    Args:
        data: The data to convert (dict, list, or primitive value).
        parent: The parent XML element to append to.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            # Skip None values in dictionaries to match JSON/YAML behavior
            if value is None:
                continue
            # Sanitize key to be valid XML element name
            safe_key = str(key).replace(" ", "_").replace("-", "_")
            child = ET.SubElement(parent, safe_key)
            _dict_to_xml(value, child)
    elif isinstance(data, list):
        for item in data:
            item_elem = ET.SubElement(parent, "item")
            _dict_to_xml(item, item_elem)
    elif data is None:
        # For explicit None values (not in dict), use empty string
        parent.text = ""
    elif isinstance(data, bool):
        parent.text = str(data).lower()
    else:
        parent.text = str(data)


def save_markdown_report(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results as a Markdown report.

    Args:
        results: Evaluation results.
        output_path: Path to save the Markdown file.
    """
    lines = []

    lines.append("# SWE-bench MCP Evaluation Report")
    lines.append("")
    lines.append(f"**Generated:** {results.metadata['timestamp']}")
    lines.append(f"**Model:** {results.metadata['config']['model']}")
    if "dataset" in results.metadata["config"]:
        lines.append(f"**Dataset:** {results.metadata['config']['dataset']}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")

    mcp = results.summary["mcp"]
    baseline = results.summary["baseline"]

    lines.append("| Metric | MCP Agent | Baseline |")
    lines.append("|--------|-----------|----------|")
    lines.append(
        f"| Resolved | {mcp['resolved']}/{mcp['total']} | {baseline['resolved']}/{baseline['total']} |"
    )
    lines.append(f"| Resolution Rate | {mcp['rate']:.1%} | {baseline['rate']:.1%} |")
    lines.append("")
    lines.append(f"**Improvement:** {results.summary['improvement']}")
    lines.append("")

    # Add cost analysis
    lines.append("## Cost Analysis")
    lines.append("")
    lines.append("| Metric | MCP Agent | Baseline |")
    lines.append("|--------|-----------|----------|")
    lines.append(
        f"| Total Cost | {format_cost(mcp.get('total_cost'))} | {format_cost(baseline.get('total_cost'))} |"
    )
    lines.append(
        f"| Cost per Task | {format_cost(mcp.get('cost_per_task'))} | {format_cost(baseline.get('cost_per_task'))} |"
    )
    lines.append(
        f"| Cost per Resolved | {format_cost(mcp.get('cost_per_resolved'))} | {format_cost(baseline.get('cost_per_resolved'))} |"
    )
    lines.append("")

    cost_comparison = results.summary.get("cost_comparison", {})
    total_diff = cost_comparison.get("total_difference")
    cost_per_additional = cost_comparison.get("cost_per_additional_resolution")

    if total_diff is not None:
        baseline_cost = baseline.get("total_cost", 0)
        if baseline_cost > 0:
            pct = abs(total_diff) / baseline_cost * 100
            if total_diff > 0:
                lines.append(f"**MCP Additional Cost:** {format_cost(total_diff)} ({pct:+.1f}%)")
            else:
                lines.append(f"**MCP Cost Savings:** {format_cost(abs(total_diff))} ({pct:.1f}%)")
        else:
            # No baseline cost available (e.g., --mcp-only mode)
            if total_diff > 0:
                lines.append(
                    f"**MCP Additional Cost:** {format_cost(total_diff)} (N/A - no baseline)"
                )
            else:
                lines.append(
                    f"**MCP Cost Savings:** {format_cost(abs(total_diff))} (N/A - no baseline)"
                )

    if cost_per_additional is not None:
        lines.append(f"**Cost per Additional Resolution:** {format_cost(cost_per_additional)}")

    budget = results.metadata["config"].get("budget")
    if budget is not None:
        total_spent = mcp.get("total_cost", 0) + baseline.get("total_cost", 0)
        lines.append("")
        lines.append(f"**Budget:** {format_cost(budget)}")
        lines.append(f"**Total Spent:** {format_cost(total_spent)}")
        if results.metadata["config"].get("budget_exceeded"):
            lines.append("**Note:** Budget limit reached - evaluation halted early")

    lines.append("")

    # Add tool coverage analysis
    tool_coverage = results.summary.get("tool_coverage")
    if tool_coverage:
        lines.append("## Tool Coverage Analysis")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Available Tools | {tool_coverage.get('total_available', 0)} |")
        lines.append(f"| Used Tools | {tool_coverage.get('total_used', 0)} |")
        coverage_rate = tool_coverage.get("coverage_rate", 0.0)
        lines.append(f"| Coverage Rate | {coverage_rate:.1%} |")
        lines.append("")

        # Most used tools
        most_used = tool_coverage.get("most_used", {})
        if most_used:
            lines.append("### Most Used Tools")
            lines.append("")
            lines.append("| Tool | Call Count |")
            lines.append("|------|------------|")
            for tool_name, count in list(most_used.items())[:10]:
                lines.append(f"| {tool_name} | {count} |")
            lines.append("")

        # Unused tools
        unused_tools = tool_coverage.get("unused_tools", [])
        if unused_tools:
            lines.append(f"### Unused Tools ({len(unused_tools)})")
            lines.append("")
            for tool_name in unused_tools:
                lines.append(f"- {tool_name}")
            lines.append("")

    # Add MCP tool failure statistics
    mcp_tool_stats = results.summary.get("mcp_tool_stats")
    if mcp_tool_stats and mcp_tool_stats.get("total_tool_calls", 0) > 0:
        lines.append("## MCP Tool Call Statistics")
        lines.append("")

        total_calls = mcp_tool_stats.get("total_tool_calls", 0)
        total_failures = mcp_tool_stats.get("total_failures", 0)
        failure_rate = mcp_tool_stats.get("failure_rate", 0.0)

        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Tool Calls | {total_calls:,} |")
        lines.append(f"| Failed Calls | {total_failures:,} |")
        lines.append(f"| Failure Rate | {failure_rate:.1%} |")
        lines.append("")

        if mcp_tool_stats.get("high_failure_rate"):
            lines.append(
                f"**⚠️ Warning:** High failure rate detected ({failure_rate:.1%}). "
                "This may indicate MCP server issues or infrastructure problems."
            )
            lines.append("")

        # Per-tool breakdown
        by_tool = mcp_tool_stats.get("by_tool", {})
        if by_tool:
            # Filter to only tools with failures and sort by failure rate (descending)
            failing_tools = [
                (name, stats) for name, stats in by_tool.items() if stats.get("failed", 0) > 0
            ]
            failing_tools.sort(key=lambda x: x[1].get("failure_rate", 0.0), reverse=True)

            if failing_tools:
                lines.append("### Per-Tool Breakdown")
                lines.append("")
                lines.append("| Tool | Total Calls | Succeeded | Failed | Failure Rate |")
                lines.append("|------|-------------|-----------|--------|--------------|")

                # Show top 10 failing tools (matching console output)
                for tool_name, stats in failing_tools[:10]:
                    total = stats.get("total", 0)
                    succeeded = stats.get("succeeded", 0)
                    failed = stats.get("failed", 0)
                    rate = stats.get("failure_rate", 0.0)
                    lines.append(
                        f"| {tool_name} | {total:,} | {succeeded:,} | {failed:,} | {rate:.1%} |"
                    )

                lines.append("")

                if len(failing_tools) > 10:
                    remaining = len(failing_tools) - 10
                    lines.append(f"*... and {remaining} more tools with failures*")
                    lines.append("")

                # Show sample errors for top 3 failing tools
                has_errors = False
                for tool_name, stats in failing_tools[:3]:
                    sample_errors = stats.get("sample_errors", [])
                    if sample_errors:
                        if not has_errors:
                            lines.append("### Sample Errors")
                            lines.append("")
                            has_errors = True

                        lines.append(f"**{tool_name}:**")
                        lines.append("")
                        for error in sample_errors[:2]:  # First 2 errors per tool
                            lines.append(f"- {error}")
                        lines.append("")

    # Add comprehensive statistics if available
    comprehensive_stats = results.summary.get("comprehensive_stats")
    if comprehensive_stats:
        lines.append("## Comprehensive Statistics")
        lines.append("")

        # Token Usage
        lines.append("### Token Usage")
        lines.append("")
        lines.append("| Metric | MCP Agent | Baseline |")
        lines.append("|--------|-----------|----------|")
        mcp_tok = comprehensive_stats["mcp_tokens"]
        base_tok = comprehensive_stats["baseline_tokens"]
        lines.append(f"| Total Input | {mcp_tok['total_input']:,} | {base_tok['total_input']:,} |")
        lines.append(
            f"| Total Output | {mcp_tok['total_output']:,} | {base_tok['total_output']:,} |"
        )
        lines.append(
            f"| Total Tokens | {mcp_tok['total_tokens']:,} | {base_tok['total_tokens']:,} |"
        )
        lines.append(
            f"| Avg Input/Task | {mcp_tok['avg_input_per_task']:,.0f} | "
            f"{base_tok['avg_input_per_task']:,.0f} |"
        )
        lines.append(
            f"| Avg Output/Task | {mcp_tok['avg_output_per_task']:,.0f} | "
            f"{base_tok['avg_output_per_task']:,.0f} |"
        )
        lines.append(
            f"| Max Input/Task | {mcp_tok['max_input_per_task']:,} | "
            f"{base_tok['max_input_per_task']:,} |"
        )
        lines.append(
            f"| Max Output/Task | {mcp_tok['max_output_per_task']:,} | "
            f"{base_tok['max_output_per_task']:,} |"
        )
        lines.append("")

        # Cost Breakdown
        lines.append("### Detailed Cost Breakdown")
        lines.append("")
        lines.append("| Metric | MCP Agent | Baseline |")
        lines.append("|--------|-----------|----------|")
        mcp_cost = comprehensive_stats["mcp_costs"]
        base_cost = comprehensive_stats["baseline_costs"]
        lines.append(
            f"| Total Cost | {format_cost(mcp_cost['total_cost'])} | "
            f"{format_cost(base_cost['total_cost'])} |"
        )
        lines.append(
            f"| Avg Cost/Task | {format_cost(mcp_cost['avg_cost_per_task'])} | "
            f"{format_cost(base_cost['avg_cost_per_task'])} |"
        )
        lines.append(
            f"| Max Cost/Task | {format_cost(mcp_cost['max_cost_per_task'])} | "
            f"{format_cost(base_cost['max_cost_per_task'])} |"
        )
        lines.append(
            f"| Min Cost/Task | {format_cost(mcp_cost['min_cost_per_task'])} | "
            f"{format_cost(base_cost['min_cost_per_task'])} |"
        )
        if mcp_cost.get("cost_per_resolved"):
            lines.append(
                f"| Cost/Resolved | {format_cost(mcp_cost['cost_per_resolved'])} | "
                f"{format_cost(base_cost.get('cost_per_resolved'))} |"
            )
        lines.append("")

        # Iteration Statistics
        lines.append("### Iteration Statistics")
        lines.append("")
        lines.append("| Metric | MCP Agent | Baseline |")
        lines.append("|--------|-----------|----------|")
        mcp_iter = comprehensive_stats["mcp_iterations"]
        base_iter = comprehensive_stats["baseline_iterations"]
        lines.append(
            f"| Total Iterations | {mcp_iter['total_iterations']:,} | "
            f"{base_iter['total_iterations']:,} |"
        )
        lines.append(
            f"| Avg Iterations/Task | {mcp_iter['avg_iterations']:.1f} | "
            f"{base_iter['avg_iterations']:.1f} |"
        )
        lines.append(
            f"| Max Iterations | {mcp_iter['max_iterations']} | {base_iter['max_iterations']} |"
        )
        lines.append(
            f"| Min Iterations | {mcp_iter['min_iterations']} | {base_iter['min_iterations']} |"
        )
        lines.append("")

        # Runtime Statistics
        mcp_runtime = comprehensive_stats.get("mcp_runtime", {})
        base_runtime = comprehensive_stats.get("baseline_runtime", {})
        if mcp_runtime.get("total_runtime", 0) > 0 or base_runtime.get("total_runtime", 0) > 0:
            lines.append("### Runtime Statistics")
            lines.append("")
            lines.append("| Metric | MCP Agent | Baseline |")
            lines.append("|--------|-----------|----------|")
            lines.append(
                f"| Total Runtime | {format_runtime(mcp_runtime.get('total_runtime', 0))} | "
                f"{format_runtime(base_runtime.get('total_runtime', 0))} |"
            )
            lines.append(
                f"| Avg Runtime/Task | {format_runtime(mcp_runtime.get('avg_runtime_per_task', 0))} | "
                f"{format_runtime(base_runtime.get('avg_runtime_per_task', 0))} |"
            )
            mcp_runtime_resolved = (
                format_runtime(mcp_runtime["runtime_per_resolved"])
                if mcp_runtime.get("runtime_per_resolved")
                else "N/A"
            )
            base_runtime_resolved = (
                format_runtime(base_runtime["runtime_per_resolved"])
                if base_runtime.get("runtime_per_resolved")
                else "N/A"
            )
            lines.append(f"| Runtime/Resolved | {mcp_runtime_resolved} | {base_runtime_resolved} |")
            lines.append(
                f"| Min Runtime | {format_runtime(mcp_runtime.get('min_runtime', 0))} | "
                f"{format_runtime(base_runtime.get('min_runtime', 0))} |"
            )
            lines.append(
                f"| Max Runtime | {format_runtime(mcp_runtime.get('max_runtime', 0))} | "
                f"{format_runtime(base_runtime.get('max_runtime', 0))} |"
            )
            lines.append("")

        # Iteration Distribution
        if mcp_iter.get("distribution"):
            lines.append("#### MCP Iteration Distribution")
            lines.append("")
            lines.append("| Iterations | Task Count |")
            lines.append("|------------|------------|")
            for iters, count in sorted(mcp_iter["distribution"].items(), key=lambda x: int(x[0])):
                lines.append(f"| {iters} | {count} |")
            lines.append("")

        # MCP Tool Usage
        mcp_tools = comprehensive_stats["mcp_tools"]
        if mcp_tools["total_calls"] > 0:
            lines.append("### MCP Tool Usage Statistics")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Total Calls | {mcp_tools['total_calls']:,} |")
            lines.append(f"| Successful Calls | {mcp_tools['total_successes']:,} |")
            lines.append(f"| Failed Calls | {mcp_tools['total_failures']:,} |")
            lines.append(f"| Failure Rate | {mcp_tools['failure_rate']:.1%} |")
            lines.append(f"| Unique Tools Used | {mcp_tools['unique_tools_used']} |")
            lines.append(f"| Avg Calls/Task | {mcp_tools['avg_calls_per_task']:.1f} |")
            lines.append("")

            # Most used tools
            if mcp_tools.get("most_used_tools"):
                lines.append("#### Top 10 Most Used Tools")
                lines.append("")
                lines.append("| Tool | Calls | Success Rate |")
                lines.append("|------|-------|--------------|")
                for tool_name, count in list(mcp_tools["most_used_tools"].items())[:10]:
                    per_tool = mcp_tools["per_tool"].get(tool_name, {})
                    success_rate = 1.0 - per_tool.get("failure_rate", 0.0)
                    lines.append(f"| {tool_name} | {count:,} | {success_rate:.1%} |")
                lines.append("")

            # Most failed tools
            if mcp_tools.get("most_failed_tools") and mcp_tools["total_failures"] > 0:
                lines.append("#### Top 10 Most Failed Tools")
                lines.append("")
                lines.append("| Tool | Failures | Failure Rate |")
                lines.append("|------|----------|--------------|")
                for tool_name, fail_count in list(mcp_tools["most_failed_tools"].items())[:10]:
                    per_tool = mcp_tools["per_tool"].get(tool_name, {})
                    failure_rate = per_tool.get("failure_rate", 0.0)
                    lines.append(f"| {tool_name} | {fail_count:,} | {failure_rate:.1%} |")
                lines.append("")

        # Error Analysis
        mcp_err = comprehensive_stats["mcp_errors"]
        base_err = comprehensive_stats["baseline_errors"]
        if mcp_err["total_errors"] > 0 or base_err["total_errors"] > 0:
            lines.append("### Error Analysis")
            lines.append("")
            lines.append("| Metric | MCP Agent | Baseline |")
            lines.append("|--------|-----------|----------|")
            lines.append(
                f"| Total Errors | {mcp_err['total_errors']} | {base_err['total_errors']} |"
            )
            lines.append(
                f"| Error Rate | {mcp_err['error_rate']:.1%} | {base_err['error_rate']:.1%} |"
            )
            lines.append(
                f"| Timeout Count | {mcp_err['timeout_count']} | {base_err['timeout_count']} |"
            )
            lines.append(
                f"| Timeout Rate | {mcp_err['timeout_rate']:.1%} | {base_err['timeout_rate']:.1%} |"
            )
            lines.append("")

            # Error categories
            if mcp_err.get("error_categories"):
                lines.append("#### MCP Error Categories")
                lines.append("")
                for category, count in sorted(
                    mcp_err["error_categories"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    lines.append(f"- **{category}**: {count}")
                lines.append("")

            if base_err.get("error_categories"):
                lines.append("#### Baseline Error Categories")
                lines.append("")
                for category, count in sorted(
                    base_err["error_categories"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    lines.append(f"- **{category}**: {count}")
                lines.append("")

            # Sample errors
            if mcp_err.get("sample_errors"):
                lines.append("#### Sample Errors (MCP)")
                lines.append("")
                for sample in mcp_err["sample_errors"][:5]:
                    lines.append(
                        f"- **{sample['instance_id']}** [{sample['category']}]: {sample['error']}"
                    )
                lines.append("")

    lines.append("## MCP Server Configuration")
    lines.append("")
    lines.append("```")
    lines.append(f"command: {results.metadata['mcp_server']['command']}")
    lines.append(f"args: {results.metadata['mcp_server']['args']}")
    lines.append("```")
    lines.append("")

    lines.append("## Per-Task Results")
    lines.append("")
    lines.append("| Instance ID | MCP | Baseline |")
    lines.append("|-------------|-----|----------|")

    for task in results.tasks:
        mcp_status = "PASS" if task.mcp and task.mcp.get("resolved") else "FAIL"
        if task.mcp is None:
            mcp_status = "-"

        baseline_status = "PASS" if task.baseline and task.baseline.get("resolved") else "FAIL"
        if task.baseline is None:
            baseline_status = "-"

        lines.append(f"| {task.instance_id} | {mcp_status} | {baseline_status} |")

    lines.append("")

    mcp_only = []
    baseline_only = []
    both = []
    neither = []

    for task in results.tasks:
        mcp_resolved = task.mcp and task.mcp.get("resolved")
        baseline_resolved = task.baseline and task.baseline.get("resolved")

        if mcp_resolved and baseline_resolved:
            both.append(task.instance_id)
        elif mcp_resolved:
            mcp_only.append(task.instance_id)
        elif baseline_resolved:
            baseline_only.append(task.instance_id)
        else:
            neither.append(task.instance_id)

    lines.append("## Analysis")
    lines.append("")
    lines.append(f"- **Resolved by both:** {len(both)}")
    lines.append(f"- **Resolved by MCP only:** {len(mcp_only)}")
    lines.append(f"- **Resolved by Baseline only:** {len(baseline_only)}")
    lines.append(f"- **Resolved by neither:** {len(neither)}")
    lines.append("")

    if mcp_only:
        lines.append("### Tasks Resolved by MCP Only")
        lines.append("")
        for task_id in mcp_only:
            lines.append(f"- {task_id}")
        lines.append("")

    if baseline_only:
        lines.append("### Tasks Resolved by Baseline Only")
        lines.append("")
        for task_id in baseline_only:
            lines.append(f"- {task_id}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
