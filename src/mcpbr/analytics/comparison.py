"""Multi-model comparison engine for mcpbr evaluation results.

Provides tools for comparing evaluation results across multiple models,
generating summary tables, pairwise comparisons, cost-performance frontiers,
and winner analysis across different metrics.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any


@dataclass
class _ResultEntry:
    """Internal container for a labeled set of evaluation results.

    Attributes:
        label: Human-readable label for this result set (e.g., "claude-sonnet").
        data: Raw results dictionary loaded from a results JSON file.
    """

    label: str
    data: dict[str, Any]


class ComparisonEngine:
    """Engine for comparing evaluation results across multiple models.

    Supports adding multiple labeled result sets and generating comprehensive
    comparisons including summary tables, task matrices, unique wins, rankings,
    pairwise comparisons, cost-performance frontiers, and winner analysis.

    Example::

        engine = ComparisonEngine()
        engine.add_results("claude-sonnet", sonnet_data)
        engine.add_results("gpt-4o", gpt4o_data)
        comparison = engine.compare()
    """

    def __init__(self) -> None:
        """Initialize the comparison engine with an empty results list."""
        self._entries: list[_ResultEntry] = []

    def add_results(self, label: str, results_data: dict[str, Any]) -> None:
        """Add a labeled result set for comparison.

        Args:
            label: Human-readable label identifying the model or run
                (e.g., "claude-sonnet-run-1").
            results_data: Results dictionary with the standard mcpbr output
                structure containing ``metadata``, ``summary``, and ``tasks``
                keys.
        """
        self._entries.append(_ResultEntry(label=label, data=results_data))

    def compare(self) -> dict[str, Any]:
        """Generate a comprehensive comparison across all added result sets.

        Returns:
            Dictionary containing:
                - ``models``: List of model labels.
                - ``summary_table``: List of dicts with per-model summary metrics
                  including label, model, provider, benchmark, resolved, total,
                  rate, cost, avg_cost_per_task, and avg_tokens.
                - ``task_matrix``: Dict mapping instance_id to a dict of
                  {label: resolved_bool} for each model.
                - ``unique_wins``: Dict mapping label to list of instance_ids
                  that only that model resolved.
                - ``rankings``: Dict with ``by_rate``, ``by_cost_efficiency``,
                  and ``by_speed`` lists, each sorted best-first.
                - ``pairwise``: List of pairwise comparison dicts between all
                  model pairs, including rate difference.

        Raises:
            ValueError: If fewer than two result sets have been added.
        """
        if len(self._entries) < 2:
            raise ValueError(
                f"At least 2 result sets required for comparison, got {len(self._entries)}"
            )

        models = [e.label for e in self._entries]
        summary_table = self._build_summary_table()
        task_matrix = self._build_task_matrix()
        unique_wins = self._build_unique_wins(task_matrix)
        rankings = self._build_rankings(summary_table)
        pairwise = self._build_pairwise(summary_table)

        return {
            "models": models,
            "summary_table": summary_table,
            "task_matrix": task_matrix,
            "unique_wins": unique_wins,
            "rankings": rankings,
            "pairwise": pairwise,
        }

    def get_cost_performance_frontier(self) -> list[dict[str, Any]]:
        """Compute the Pareto frontier of cost vs resolution rate.

        Points on the frontier represent models where no other model is both
        cheaper and has a higher resolution rate. The frontier is sorted by
        ascending cost.

        Returns:
            List of dicts, each with ``label``, ``cost``, and ``rate`` keys,
            representing models on the Pareto-optimal frontier.

        Raises:
            ValueError: If fewer than two result sets have been added.
        """
        if len(self._entries) < 2:
            raise ValueError(
                f"At least 2 result sets required for frontier, got {len(self._entries)}"
            )

        points = []
        for entry in self._entries:
            summary = entry.data.get("summary", {}).get("mcp", {})
            cost = summary.get("total_cost", 0.0)
            rate = summary.get("rate", 0.0)
            points.append({"label": entry.label, "cost": cost, "rate": rate})

        # Sort by cost ascending, then by rate descending for tie-breaking
        points.sort(key=lambda p: (p["cost"], -p["rate"]))

        frontier: list[dict[str, Any]] = []
        best_rate = -1.0

        for point in points:
            if point["rate"] > best_rate:
                frontier.append(point)
                best_rate = point["rate"]

        return frontier

    def get_winner_analysis(self) -> dict[str, Any]:
        """Determine which model wins on each metric.

        Evaluates models across resolution rate, total cost, cost efficiency
        (cost per resolved task), and average speed (runtime per task).

        Returns:
            Dictionary with metric names as keys and dicts containing
            ``winner`` (label) and ``value`` (the winning metric value).

        Raises:
            ValueError: If fewer than two result sets have been added.
        """
        if len(self._entries) < 2:
            raise ValueError(
                f"At least 2 result sets required for winner analysis, got {len(self._entries)}"
            )

        summary_table = self._build_summary_table()

        winners: dict[str, Any] = {}

        # Best resolution rate (highest wins)
        best_rate = max(summary_table, key=lambda r: r["rate"])
        winners["highest_resolution_rate"] = {
            "winner": best_rate["label"],
            "value": best_rate["rate"],
        }

        # Lowest total cost (lowest wins)
        best_cost = min(summary_table, key=lambda r: r["cost"])
        winners["lowest_total_cost"] = {
            "winner": best_cost["label"],
            "value": best_cost["cost"],
        }

        # Best cost efficiency: lowest avg_cost_per_task among models that resolved > 0
        models_with_resolved = [r for r in summary_table if r["resolved"] > 0]
        if models_with_resolved:
            best_efficiency = min(models_with_resolved, key=lambda r: r["avg_cost_per_task"])
            winners["best_cost_efficiency"] = {
                "winner": best_efficiency["label"],
                "value": best_efficiency["avg_cost_per_task"],
            }

        # Fastest average speed (lowest avg runtime)
        models_with_speed = []
        for entry in self._entries:
            tasks = entry.data.get("tasks", [])
            runtimes = []
            for task in tasks:
                mcp = task.get("mcp", {})
                runtime = mcp.get("runtime_seconds", 0.0)
                if runtime > 0:
                    runtimes.append(runtime)
            if runtimes:
                avg_runtime = sum(runtimes) / len(runtimes)
                models_with_speed.append({"label": entry.label, "avg_runtime": avg_runtime})

        if models_with_speed:
            fastest = min(models_with_speed, key=lambda r: r["avg_runtime"])
            winners["fastest_avg_speed"] = {
                "winner": fastest["label"],
                "value": fastest["avg_runtime"],
            }

        return winners

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_summary_table(self) -> list[dict[str, Any]]:
        """Build the summary table with one row per result set.

        Returns:
            List of dicts, each containing label, model, provider, benchmark,
            resolved, total, rate, cost, avg_cost_per_task, and avg_tokens.
        """
        rows: list[dict[str, Any]] = []

        for entry in self._entries:
            metadata = entry.data.get("metadata", {})
            config = metadata.get("config", {})
            summary = entry.data.get("summary", {}).get("mcp", {})
            tasks = entry.data.get("tasks", [])

            resolved = summary.get("resolved", 0)
            total = summary.get("total", 0)
            rate = summary.get("rate", 0.0)
            cost = summary.get("total_cost", 0.0)

            # Compute avg_cost_per_task
            avg_cost_per_task = cost / total if total > 0 else 0.0

            # Compute avg_tokens across tasks
            total_tokens = 0
            token_task_count = 0
            for task in tasks:
                mcp = task.get("mcp", {})
                tokens = mcp.get("tokens", {})
                input_tok = tokens.get("input", 0)
                output_tok = tokens.get("output", 0)
                task_total = input_tok + output_tok
                if task_total > 0:
                    total_tokens += task_total
                    token_task_count += 1

            avg_tokens = total_tokens / token_task_count if token_task_count > 0 else 0.0

            rows.append(
                {
                    "label": entry.label,
                    "model": config.get("model", "unknown"),
                    "provider": config.get("provider", "unknown"),
                    "benchmark": config.get("benchmark", "unknown"),
                    "resolved": resolved,
                    "total": total,
                    "rate": rate,
                    "cost": cost,
                    "avg_cost_per_task": round(avg_cost_per_task, 6),
                    "avg_tokens": round(avg_tokens, 1),
                }
            )

        return rows

    def _build_task_matrix(self) -> dict[str, dict[str, bool]]:
        """Build a task matrix mapping instance_id to per-model resolution.

        Returns:
            Dict mapping instance_id to {label: resolved_bool} for each model.
        """
        matrix: dict[str, dict[str, bool]] = defaultdict(dict)

        for entry in self._entries:
            tasks = entry.data.get("tasks", [])
            for task in tasks:
                instance_id = task.get("instance_id", "")
                mcp = task.get("mcp", {})
                resolved = bool(mcp.get("resolved", False))
                matrix[instance_id][entry.label] = resolved

        return dict(matrix)

    def _build_unique_wins(self, task_matrix: dict[str, dict[str, bool]]) -> dict[str, list[str]]:
        """Identify instance_ids uniquely resolved by each model.

        Args:
            task_matrix: Task matrix from ``_build_task_matrix``.

        Returns:
            Dict mapping label to list of instance_ids that only that
            model resolved.
        """
        unique_wins: dict[str, list[str]] = {e.label: [] for e in self._entries}

        for instance_id, results in task_matrix.items():
            resolvers = [label for label, resolved in results.items() if resolved]
            if len(resolvers) == 1:
                unique_wins[resolvers[0]].append(instance_id)

        return unique_wins

    def _build_rankings(self, summary_table: list[dict[str, Any]]) -> dict[str, list[str]]:
        """Build rankings of models across different metrics.

        Args:
            summary_table: Summary table from ``_build_summary_table``.

        Returns:
            Dict with ``by_rate``, ``by_cost_efficiency``, and ``by_speed``
            keys. Each value is a list of labels sorted best-first.
        """
        # By resolution rate (highest first)
        by_rate = sorted(summary_table, key=lambda r: r["rate"], reverse=True)

        # By cost efficiency (lowest avg_cost_per_task first, excluding zero-total)
        eligible = [r for r in summary_table if r["total"] > 0]
        by_cost = sorted(eligible, key=lambda r: r["avg_cost_per_task"])

        # By speed (lowest avg runtime first)
        speed_data: list[dict[str, Any]] = []
        for entry in self._entries:
            tasks = entry.data.get("tasks", [])
            runtimes = []
            for task in tasks:
                mcp = task.get("mcp", {})
                runtime = mcp.get("runtime_seconds", 0.0)
                if runtime > 0:
                    runtimes.append(runtime)
            avg_runtime = sum(runtimes) / len(runtimes) if runtimes else float("inf")
            speed_data.append({"label": entry.label, "avg_runtime": avg_runtime})

        by_speed = sorted(speed_data, key=lambda r: r["avg_runtime"])

        return {
            "by_rate": [r["label"] for r in by_rate],
            "by_cost_efficiency": [r["label"] for r in by_cost],
            "by_speed": [r["label"] for r in by_speed],
        }

    def _build_pairwise(self, summary_table: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build pairwise comparisons between all model pairs.

        Args:
            summary_table: Summary table from ``_build_summary_table``.

        Returns:
            List of dicts, each containing ``model_a``, ``model_b``,
            ``rate_a``, ``rate_b``, ``rate_difference``, ``cost_a``,
            ``cost_b``, and ``better`` (label of the model with higher rate).
        """
        rate_lookup = {r["label"]: r["rate"] for r in summary_table}
        cost_lookup = {r["label"]: r["cost"] for r in summary_table}

        labels = [e.label for e in self._entries]
        pairwise: list[dict[str, Any]] = []

        for label_a, label_b in combinations(labels, 2):
            rate_a = rate_lookup.get(label_a, 0.0)
            rate_b = rate_lookup.get(label_b, 0.0)
            cost_a = cost_lookup.get(label_a, 0.0)
            cost_b = cost_lookup.get(label_b, 0.0)

            if rate_a >= rate_b:
                better = label_a
            else:
                better = label_b

            pairwise.append(
                {
                    "model_a": label_a,
                    "model_b": label_b,
                    "rate_a": rate_a,
                    "rate_b": rate_b,
                    "rate_difference": round(abs(rate_a - rate_b), 4),
                    "cost_a": cost_a,
                    "cost_b": cost_b,
                    "better": better,
                }
            )

        return pairwise


def compare_results_files(
    file_paths: list[str | Path],
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """Load JSON result files and compare them.

    Convenience function that creates a ComparisonEngine, loads each file,
    and returns the comparison.

    Args:
        file_paths: Paths to JSON result files. Each file must contain a
            valid mcpbr results dictionary.
        labels: Optional list of labels for each file. If not provided,
            labels are derived from the file stem (filename without extension).

    Returns:
        Comparison dictionary from ``ComparisonEngine.compare()``.

    Raises:
        ValueError: If fewer than two file paths are provided, or if labels
            length does not match file_paths length.
        FileNotFoundError: If any file path does not exist.
        json.JSONDecodeError: If any file contains invalid JSON.
    """
    if len(file_paths) < 2:
        raise ValueError(f"At least 2 file paths required, got {len(file_paths)}")

    if labels is not None and len(labels) != len(file_paths):
        raise ValueError(
            f"Labels length ({len(labels)}) must match file_paths length ({len(file_paths)})"
        )

    engine = ComparisonEngine()

    for i, fp in enumerate(file_paths):
        path = Path(fp)
        if not path.exists():
            raise FileNotFoundError(f"Results file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        label = labels[i] if labels is not None else path.stem
        engine.add_results(label, data)

    return engine.compare()


def format_comparison_table(comparison: dict[str, Any]) -> str:
    """Format a comparison result as an ASCII table.

    Produces a human-readable table with columns for each metric in the
    summary table, plus sections for unique wins, rankings, and pairwise
    comparisons.

    Args:
        comparison: Comparison dictionary from ``ComparisonEngine.compare()``.

    Returns:
        Multi-line string formatted as an ASCII table suitable for
        console output.
    """
    lines: list[str] = []
    summary_table = comparison.get("summary_table", [])

    lines.append("=" * 100)
    lines.append("MULTI-MODEL COMPARISON")
    lines.append("=" * 100)
    lines.append("")

    # ---- Summary Table ----
    if summary_table:
        lines.append("SUMMARY")
        lines.append("-" * 100)

        # Column headers and widths
        headers = [
            ("Label", 20),
            ("Model", 25),
            ("Resolved", 10),
            ("Rate", 8),
            ("Cost ($)", 10),
            ("Avg $/Task", 12),
            ("Avg Tokens", 12),
        ]

        header_line = ""
        for name, width in headers:
            header_line += f"{name:<{width}}"
        lines.append(header_line)
        lines.append("-" * 100)

        for row in summary_table:
            resolved_str = f"{row['resolved']}/{row['total']}"
            rate_str = f"{row['rate']:.1%}"
            cost_str = f"{row['cost']:.4f}"
            avg_cost_str = f"{row['avg_cost_per_task']:.6f}"
            avg_tokens_str = f"{row['avg_tokens']:.0f}"

            line = (
                f"{row['label']:<20}"
                f"{row['model']:<25}"
                f"{resolved_str:<10}"
                f"{rate_str:<8}"
                f"{cost_str:<10}"
                f"{avg_cost_str:<12}"
                f"{avg_tokens_str:<12}"
            )
            lines.append(line)

        lines.append("")

    # ---- Unique Wins ----
    unique_wins = comparison.get("unique_wins", {})
    if unique_wins:
        lines.append("UNIQUE WINS (tasks only this model resolved)")
        lines.append("-" * 100)
        for label, instances in unique_wins.items():
            count = len(instances)
            if count > 0:
                preview = ", ".join(instances[:5])
                suffix = f" ... (+{count - 5} more)" if count > 5 else ""
                lines.append(f"  {label:<20} {count:>4} unique: {preview}{suffix}")
            else:
                lines.append(f"  {label:<20}    0 unique")
        lines.append("")

    # ---- Rankings ----
    rankings = comparison.get("rankings", {})
    if rankings:
        lines.append("RANKINGS")
        lines.append("-" * 100)

        for metric, ranked_labels in rankings.items():
            display_metric = metric.replace("_", " ").replace("by ", "").title()
            ranked_str = " > ".join(f"{i + 1}. {lbl}" for i, lbl in enumerate(ranked_labels))
            lines.append(f"  {display_metric + ':':<25} {ranked_str}")

        lines.append("")

    # ---- Pairwise Comparisons ----
    pairwise = comparison.get("pairwise", [])
    if pairwise:
        lines.append("PAIRWISE COMPARISONS")
        lines.append("-" * 100)

        for pair in pairwise:
            rate_diff_pct = pair["rate_difference"] * 100
            lines.append(
                f"  {pair['model_a']} vs {pair['model_b']}: "
                f"{pair['rate_a']:.1%} vs {pair['rate_b']:.1%} "
                f"(diff: {rate_diff_pct:.1f}pp) "
                f"| Winner: {pair['better']}"
            )

        lines.append("")

    lines.append("=" * 100)

    return "\n".join(lines)
