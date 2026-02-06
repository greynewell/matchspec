"""Leaderboard generation for MCP server benchmark results.

Provides tools for ranking and comparing multiple evaluation runs side-by-side,
with output as structured data, ASCII tables, or Markdown tables.
"""

from __future__ import annotations

from typing import Any


def _extract_entry_metrics(label: str, results_data: dict[str, Any]) -> dict[str, Any]:
    """Extract leaderboard metrics from a results_data dictionary.

    Args:
        label: Human-readable label for this entry.
        results_data: Evaluation results with ``summary.mcp`` and ``tasks``.

    Returns:
        Dictionary with all fields needed for a leaderboard entry.
    """
    summary = results_data.get("summary", {}).get("mcp", {})
    tasks = results_data.get("tasks", [])
    metadata = results_data.get("metadata", {})
    config = metadata.get("config", {})

    resolved = summary.get("resolved", 0)
    total = summary.get("total", 0)
    rate = summary.get("rate", 0.0)
    total_cost = summary.get("total_cost", 0.0)

    total_tokens = 0
    total_runtime = 0.0
    task_count = len(tasks)

    for task in tasks:
        mcp = task.get("mcp", {})
        tokens = mcp.get("tokens", {})
        total_tokens += tokens.get("input", 0) + tokens.get("output", 0)
        total_runtime += mcp.get("runtime_seconds", 0.0)

    avg_tokens = total_tokens // task_count if task_count > 0 else 0
    avg_runtime = total_runtime / task_count if task_count > 0 else 0.0
    cost_per_resolved = total_cost / resolved if resolved > 0 else None

    return {
        "label": label,
        "model": config.get("model", "unknown"),
        "provider": config.get("provider", "unknown"),
        "resolution_rate": rate,
        "resolved": resolved,
        "total": total,
        "total_cost": total_cost,
        "cost_per_resolved": round(cost_per_resolved, 4) if cost_per_resolved is not None else None,
        "avg_tokens": avg_tokens,
        "avg_runtime": round(avg_runtime, 2),
    }


# Valid sort keys for leaderboard generation
_SORT_KEYS = {
    "resolution_rate",
    "total_cost",
    "cost_per_resolved",
    "avg_tokens",
    "avg_runtime",
    "resolved",
}

# Sort keys where lower is better
_LOWER_IS_BETTER = {"total_cost", "cost_per_resolved", "avg_tokens", "avg_runtime"}


class Leaderboard:
    """Generate ranked leaderboards from multiple evaluation results.

    Collects results from multiple configurations or models and produces
    a ranked comparison sorted by any supported metric.

    Example::

        lb = Leaderboard()
        lb.add_entry("Claude Sonnet", results_sonnet)
        lb.add_entry("GPT-4o", results_gpt4o)
        print(lb.format_table())
    """

    def __init__(self) -> None:
        """Initialize an empty leaderboard."""
        self._entries: list[tuple[str, dict[str, Any]]] = []

    def add_entry(self, label: str, results_data: dict[str, Any]) -> None:
        """Add a result set to the leaderboard.

        Args:
            label: Human-readable label for this entry (e.g., model name
                or configuration description).
            results_data: Evaluation results dictionary with ``summary.mcp``
                and ``tasks`` keys.
        """
        self._entries.append((label, results_data))

    def generate(self, sort_by: str = "resolution_rate") -> list[dict[str, Any]]:
        """Generate the sorted leaderboard.

        Args:
            sort_by: Metric to sort by. Supported values: ``"resolution_rate"``,
                ``"total_cost"``, ``"cost_per_resolved"``, ``"avg_tokens"``,
                ``"avg_runtime"``, ``"resolved"``. Default is
                ``"resolution_rate"`` (higher is better).

        Returns:
            List of ranked entry dictionaries, each containing ``rank``,
            ``label``, ``model``, ``provider``, ``resolution_rate``,
            ``resolved``, ``total``, ``total_cost``, ``cost_per_resolved``,
            ``avg_tokens``, and ``avg_runtime``.

        Raises:
            ValueError: If *sort_by* is not a supported sort key.
        """
        if sort_by not in _SORT_KEYS:
            raise ValueError(
                f"Unsupported sort key: {sort_by!r}. "
                f"Supported keys: {', '.join(sorted(_SORT_KEYS))}"
            )

        metrics = [_extract_entry_metrics(label, data) for label, data in self._entries]

        reverse = sort_by not in _LOWER_IS_BETTER

        def sort_key(entry: dict[str, Any]) -> float:
            val = entry.get(sort_by)
            if val is None:
                # Push None values to the end regardless of sort direction
                return float("-inf") if reverse else float("inf")
            return float(val)

        metrics.sort(key=sort_key, reverse=reverse)

        # Assign ranks
        for i, entry in enumerate(metrics, start=1):
            entry["rank"] = i

        return metrics

    def format_table(self, sort_by: str = "resolution_rate") -> str:
        """Format the leaderboard as an ASCII table.

        Args:
            sort_by: Metric to sort by (see :meth:`generate` for options).

        Returns:
            Multi-line ASCII table string.
        """
        entries = self.generate(sort_by=sort_by)

        if not entries:
            return "No entries in leaderboard."

        # Define columns: (header, width, format_fn)
        columns: list[tuple[str, int, Any]] = [
            ("Rank", 6, lambda e: str(e["rank"])),
            ("Label", 24, lambda e: _truncate(e["label"], 24)),
            ("Model", 20, lambda e: _truncate(e["model"], 20)),
            ("Rate", 8, lambda e: f"{e['resolution_rate']:.1%}"),
            ("Resolved", 10, lambda e: f"{e['resolved']}/{e['total']}"),
            ("Cost", 10, lambda e: f"${e['total_cost']:.4f}"),
            (
                "$/Resolved",
                12,
                lambda e: (
                    f"${e['cost_per_resolved']:.4f}"
                    if e["cost_per_resolved"] is not None
                    else "N/A"
                ),
            ),
            ("Avg Tokens", 12, lambda e: f"{e['avg_tokens']:,}"),
            ("Avg Time", 10, lambda e: f"{e['avg_runtime']:.1f}s"),
        ]

        # Build header
        header_parts = []
        separator_parts = []
        for name, width, _ in columns:
            header_parts.append(name.ljust(width))
            separator_parts.append("-" * width)

        header = " | ".join(header_parts)
        separator = "-+-".join(separator_parts)

        lines = [header, separator]

        for entry in entries:
            row_parts = []
            for _, width, fmt_fn in columns:
                row_parts.append(fmt_fn(entry).ljust(width))
            lines.append(" | ".join(row_parts))

        return "\n".join(lines)

    def format_markdown(self, sort_by: str = "resolution_rate") -> str:
        """Format the leaderboard as a Markdown table.

        Args:
            sort_by: Metric to sort by (see :meth:`generate` for options).

        Returns:
            Markdown-formatted table string.
        """
        entries = self.generate(sort_by=sort_by)

        if not entries:
            return "No entries in leaderboard."

        headers = [
            "Rank",
            "Label",
            "Model",
            "Rate",
            "Resolved",
            "Cost",
            "$/Resolved",
            "Avg Tokens",
            "Avg Time",
        ]

        header_line = "| " + " | ".join(headers) + " |"
        separator_line = "| " + " | ".join("---" for _ in headers) + " |"

        lines = [header_line, separator_line]

        for entry in entries:
            cost_per = (
                f"${entry['cost_per_resolved']:.4f}"
                if entry["cost_per_resolved"] is not None
                else "N/A"
            )
            row = [
                str(entry["rank"]),
                entry["label"].replace("|", "\\|"),
                entry["model"].replace("|", "\\|"),
                f"{entry['resolution_rate']:.1%}",
                f"{entry['resolved']}/{entry['total']}",
                f"${entry['total_cost']:.4f}",
                cost_per,
                f"{entry['avg_tokens']:,}",
                f"{entry['avg_runtime']:.1f}s",
            ]
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)


def generate_leaderboard(
    results_list: list[tuple[str, dict[str, Any]]],
    sort_by: str = "resolution_rate",
) -> list[dict[str, Any]]:
    """Convenience function to generate a leaderboard from multiple results.

    Args:
        results_list: List of ``(label, results_data)`` tuples.
        sort_by: Metric to sort by (default ``"resolution_rate"``).

    Returns:
        Sorted list of leaderboard entry dictionaries.
    """
    lb = Leaderboard()
    for label, data in results_list:
        lb.add_entry(label, data)
    return lb.generate(sort_by=sort_by)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if needed.

    Args:
        text: The string to truncate.
        max_len: Maximum allowed length.

    Returns:
        Truncated string, with ``"..."`` suffix if it was shortened.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
