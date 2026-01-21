"""Reporting utilities for evaluation results."""

import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from rich.console import Console
from rich.table import Table

from .pricing import format_cost

if TYPE_CHECKING:
    from .harness import EvaluationResults


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
        if total_diff > 0:
            console.print(
                f"[bold]MCP Additional Cost:[/bold] {format_cost(total_diff)} "
                f"({abs(total_diff) / baseline.get('total_cost', 1) * 100:+.1f}%)"
            )
        else:
            console.print(
                f"[bold]MCP Cost Savings:[/bold] {format_cost(abs(total_diff))} "
                f"({abs(total_diff) / baseline.get('total_cost', 1) * 100:.1f}%)"
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
        if task.baseline:
            task_data["baseline"] = task.baseline
        data["tasks"].append(task_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


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
        if total_diff > 0:
            lines.append(
                f"**MCP Additional Cost:** {format_cost(total_diff)} "
                f"({abs(total_diff) / baseline.get('total_cost', 1) * 100:+.1f}%)"
            )
        else:
            lines.append(
                f"**MCP Cost Savings:** {format_cost(abs(total_diff))} "
                f"({abs(total_diff) / baseline.get('total_cost', 1) * 100:.1f}%)"
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
