"""Streaming results output for real-time evaluation feedback."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from rich.console import Console
from rich.live import Live
from rich.table import Table

from .pricing import format_cost

if TYPE_CHECKING:
    from .harness import TaskResult


@dataclass
class StreamingConfig:
    """Configuration for streaming output."""

    enabled: bool = True
    console_updates: bool = True
    progressive_json: Path | None = None
    progressive_yaml: Path | None = None
    progressive_markdown: Path | None = None


class StreamingOutputHandler:
    """Handles streaming output of evaluation results as they arrive.

    This class provides real-time updates to the console and progressive
    file writing to JSON, YAML, and Markdown formats.
    """

    def __init__(
        self,
        config: StreamingConfig,
        metadata: dict[str, Any],
        console: Console | None = None,
    ) -> None:
        """Initialize streaming output handler.

        Args:
            config: Streaming configuration.
            metadata: Evaluation metadata (model, config, etc.).
            console: Rich console for output (creates new if None).
        """
        self.config = config
        self.metadata = metadata
        self.console = console or Console()
        self.results: list[TaskResult] = []
        self.live: Live | None = None
        self._mcp_resolved = 0
        self._mcp_total = 0
        self._baseline_resolved = 0
        self._baseline_total = 0
        self._mcp_cost = 0.0
        self._baseline_cost = 0.0

    def start(self) -> None:
        """Start streaming output with live console updates."""
        if not self.config.enabled or not self.config.console_updates:
            return

        # Initialize progressive files
        if self.config.progressive_json:
            self._init_progressive_json()
        if self.config.progressive_yaml:
            self._init_progressive_yaml()
        if self.config.progressive_markdown:
            self._init_progressive_markdown()

        # Start live console display
        self.live = Live(
            self._generate_table(),
            console=self.console,
            refresh_per_second=2,
            auto_refresh=True,
        )
        self.live.start()

    def stop(self) -> None:
        """Stop streaming output and finalize files."""
        if self.live:
            self.live.stop()
            self.live = None

    def add_result(self, result: "TaskResult") -> None:
        """Add a completed task result and update all outputs.

        Args:
            result: Completed task result.
        """
        self.results.append(result)

        # Update statistics
        if result.mcp:
            self._mcp_total += 1
            if result.mcp.get("resolved"):
                self._mcp_resolved += 1
            if result.mcp.get("cost"):
                self._mcp_cost += result.mcp.get("cost", 0.0)

        if result.baseline:
            self._baseline_total += 1
            if result.baseline.get("resolved"):
                self._baseline_resolved += 1
            if result.baseline.get("cost"):
                self._baseline_cost += result.baseline.get("cost", 0.0)

        # Update live display
        if self.live:
            self.live.update(self._generate_table())

        # Update progressive files
        if self.config.progressive_json:
            self._update_progressive_json()
        if self.config.progressive_yaml:
            self._update_progressive_yaml()
        if self.config.progressive_markdown:
            self._update_progressive_markdown()

    def _generate_table(self) -> Table:
        """Generate Rich table with current results."""
        table = Table(title="Live Evaluation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("MCP Agent", style="green")
        table.add_column("Baseline", style="yellow")

        # Resolved count
        table.add_row(
            "Resolved",
            f"{self._mcp_resolved}/{self._mcp_total}",
            f"{self._baseline_resolved}/{self._baseline_total}",
        )

        # Resolution rate
        mcp_rate = self._mcp_resolved / self._mcp_total if self._mcp_total > 0 else 0
        baseline_rate = (
            self._baseline_resolved / self._baseline_total if self._baseline_total > 0 else 0
        )
        table.add_row(
            "Resolution Rate",
            f"{mcp_rate:.1%}",
            f"{baseline_rate:.1%}",
        )

        # Cost
        table.add_row(
            "Total Cost",
            format_cost(self._mcp_cost),
            format_cost(self._baseline_cost),
        )

        # Cost per task
        mcp_cost_per_task = self._mcp_cost / self._mcp_total if self._mcp_total > 0 else 0.0
        baseline_cost_per_task = (
            self._baseline_cost / self._baseline_total if self._baseline_total > 0 else 0.0
        )
        table.add_row(
            "Cost per Task",
            format_cost(mcp_cost_per_task),
            format_cost(baseline_cost_per_task),
        )

        # Improvement
        if baseline_rate > 0:
            improvement = ((mcp_rate - baseline_rate) / baseline_rate) * 100
            improvement_str = f"{improvement:+.1f}%"
        else:
            improvement_str = "N/A"

        table.add_row(
            "Improvement",
            improvement_str,
            "",
        )

        return table

    def _init_progressive_json(self) -> None:
        """Initialize progressive JSON file with metadata."""
        if not self.config.progressive_json:
            return

        self.config.progressive_json.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "metadata": self.metadata,
            "summary": self._get_current_summary(),
            "tasks": [],
        }
        with open(self.config.progressive_json, "w") as f:
            json.dump(data, f, indent=2)

    def _init_progressive_yaml(self) -> None:
        """Initialize progressive YAML file with metadata."""
        if not self.config.progressive_yaml:
            return

        self.config.progressive_yaml.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "metadata": self.metadata,
            "summary": self._get_current_summary(),
            "tasks": [],
        }
        with open(self.config.progressive_yaml, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def _init_progressive_markdown(self) -> None:
        """Initialize progressive Markdown file with header."""
        if not self.config.progressive_markdown:
            return

        self.config.progressive_markdown.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Evaluation Results (Live)",
            "",
            f"**Generated:** {self.metadata.get('timestamp', 'Unknown')}",
            f"**Model:** {self.metadata.get('config', {}).get('model', 'Unknown')}",
            f"**Dataset:** {self.metadata.get('config', {}).get('dataset', 'Unknown')}",
            "",
            "## Summary (Updating...)",
            "",
            "Results are being collected...",
            "",
        ]
        self.config.progressive_markdown.write_text("\n".join(lines))

    def _update_progressive_json(self) -> None:
        """Update progressive JSON file with latest results."""
        if not self.config.progressive_json:
            return

        data = {
            "metadata": self.metadata,
            "summary": self._get_current_summary(),
            "tasks": [],
        }

        for task in self.results:
            task_data = {"instance_id": task.instance_id}
            if task.mcp:
                task_data["mcp"] = task.mcp
            if task.baseline:
                task_data["baseline"] = task.baseline
            data["tasks"].append(task_data)

        with open(self.config.progressive_json, "w") as f:
            json.dump(data, f, indent=2)

    def _update_progressive_yaml(self) -> None:
        """Update progressive YAML file with latest results."""
        if not self.config.progressive_yaml:
            return

        data = {
            "metadata": self.metadata,
            "summary": self._get_current_summary(),
            "tasks": [],
        }

        for task in self.results:
            task_data = {"instance_id": task.instance_id}
            if task.mcp:
                task_data["mcp"] = task.mcp
            if task.baseline:
                task_data["baseline"] = task.baseline
            data["tasks"].append(task_data)

        with open(self.config.progressive_yaml, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def _update_progressive_markdown(self) -> None:
        """Update progressive Markdown file with latest results."""
        if not self.config.progressive_markdown:
            return

        lines = [
            "# Evaluation Results (Live)",
            "",
            f"**Generated:** {self.metadata.get('timestamp', 'Unknown')}",
            f"**Model:** {self.metadata.get('config', {}).get('model', 'Unknown')}",
            f"**Dataset:** {self.metadata.get('config', {}).get('dataset', 'Unknown')}",
            "",
            "## Summary",
            "",
        ]

        # Summary table
        mcp_rate = self._mcp_resolved / self._mcp_total if self._mcp_total > 0 else 0
        baseline_rate = (
            self._baseline_resolved / self._baseline_total if self._baseline_total > 0 else 0
        )

        lines.extend(
            [
                "| Metric | MCP Agent | Baseline |",
                "|--------|-----------|----------|",
                f"| Resolved | {self._mcp_resolved}/{self._mcp_total} | {self._baseline_resolved}/{self._baseline_total} |",
                f"| Resolution Rate | {mcp_rate:.1%} | {baseline_rate:.1%} |",
                f"| Total Cost | {format_cost(self._mcp_cost)} | {format_cost(self._baseline_cost)} |",
                "",
            ]
        )

        # Improvement
        if baseline_rate > 0:
            improvement = ((mcp_rate - baseline_rate) / baseline_rate) * 100
            lines.append(f"**Improvement:** {improvement:+.1f}%")
        else:
            lines.append("**Improvement:** N/A")
        lines.append("")

        # Per-task results
        lines.extend(
            [
                "## Per-Task Results",
                "",
                "| Instance ID | MCP | Baseline |",
                "|-------------|-----|----------|",
            ]
        )

        for task in self.results:
            mcp_status = "PASS" if task.mcp and task.mcp.get("resolved") else "FAIL"
            if task.mcp is None:
                mcp_status = "-"

            baseline_status = "PASS" if task.baseline and task.baseline.get("resolved") else "FAIL"
            if task.baseline is None:
                baseline_status = "-"

            lines.append(f"| {task.instance_id} | {mcp_status} | {baseline_status} |")

        lines.append("")
        lines.append(f"_Last updated: {len(self.results)} tasks completed_")

        self.config.progressive_markdown.write_text("\n".join(lines))

    def _get_current_summary(self) -> dict[str, Any]:
        """Get current summary statistics."""
        mcp_rate = self._mcp_resolved / self._mcp_total if self._mcp_total > 0 else 0
        baseline_rate = (
            self._baseline_resolved / self._baseline_total if self._baseline_total > 0 else 0
        )

        if baseline_rate > 0:
            improvement = ((mcp_rate - baseline_rate) / baseline_rate) * 100
            improvement_str = f"{improvement:+.1f}%"
        else:
            improvement_str = "N/A"

        return {
            "mcp": {
                "resolved": self._mcp_resolved,
                "total": self._mcp_total,
                "rate": mcp_rate,
                "total_cost": self._mcp_cost,
                "cost_per_task": self._mcp_cost / self._mcp_total if self._mcp_total > 0 else 0.0,
            },
            "baseline": {
                "resolved": self._baseline_resolved,
                "total": self._baseline_total,
                "rate": baseline_rate,
                "total_cost": self._baseline_cost,
                "cost_per_task": (
                    self._baseline_cost / self._baseline_total if self._baseline_total > 0 else 0.0
                ),
            },
            "improvement": improvement_str,
        }

    def get_results(self) -> list["TaskResult"]:
        """Get all collected results.

        Returns:
            List of task results.
        """
        return self.results


def create_streaming_handler(
    enabled: bool,
    metadata: dict[str, Any],
    console_updates: bool = True,
    progressive_json: Path | None = None,
    progressive_yaml: Path | None = None,
    progressive_markdown: Path | None = None,
) -> StreamingOutputHandler:
    """Factory function to create a streaming output handler.

    Args:
        enabled: Whether streaming is enabled.
        metadata: Evaluation metadata.
        console_updates: Whether to show live console updates.
        progressive_json: Path for progressive JSON output.
        progressive_yaml: Path for progressive YAML output.
        progressive_markdown: Path for progressive Markdown output.

    Returns:
        Configured StreamingOutputHandler.
    """
    config = StreamingConfig(
        enabled=enabled,
        console_updates=console_updates,
        progressive_json=progressive_json,
        progressive_yaml=progressive_yaml,
        progressive_markdown=progressive_markdown,
    )
    return StreamingOutputHandler(config, metadata)
