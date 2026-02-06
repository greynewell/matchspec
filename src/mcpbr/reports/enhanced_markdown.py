"""Enhanced markdown report generation for mcpbr evaluation results.

Generates GitHub-flavored markdown reports with mermaid diagrams,
shields.io badges, collapsible sections, and detailed analysis tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote


def generate_badge(label: str, value: str, color: str) -> str:
    """Generate a shields.io badge in markdown image syntax.

    Args:
        label: Badge label (left side).
        value: Badge value (right side).
        color: Badge color name or hex (e.g., "green", "blue", "ff5733").

    Returns:
        Markdown image string for the badge.
    """
    encoded_label = quote(label, safe="")
    encoded_value = quote(value, safe="")
    encoded_color = quote(color, safe="")
    url = f"https://img.shields.io/badge/{encoded_label}-{encoded_value}-{encoded_color}"
    return f"![{label}: {value}]({url})"


def generate_mermaid_pie(title: str, data: dict[str, int]) -> str:
    """Generate a mermaid pie chart code block.

    Args:
        title: Chart title.
        data: Mapping of category names to integer counts.

    Returns:
        Mermaid pie chart wrapped in a fenced code block.
    """
    lines = ["```mermaid", "pie showData", f"    title {title}"]
    for label, count in data.items():
        lines.append(f'    "{label}" : {count}')
    lines.append("```")
    return "\n".join(lines)


def generate_mermaid_bar(title: str, data: dict[str, float]) -> str:
    """Generate a mermaid xychart-beta bar chart code block.

    Args:
        title: Chart title.
        data: Mapping of category labels to float values.

    Returns:
        Mermaid xychart-beta bar chart wrapped in a fenced code block.
    """
    if not data:
        labels_str = '["N/A"]'
        values_str = "[0]"
    else:
        labels = [f'"{k}"' for k in data]
        values = [str(v) for v in data.values()]
        labels_str = f"[{', '.join(labels)}]"
        values_str = f"[{', '.join(values)}]"

    lines = [
        "```mermaid",
        "xychart-beta",
        f'    title "{title}"',
        f"    x-axis {labels_str}",
        '    y-axis "Cost (USD)"',
        f"    bar {values_str}",
        "```",
    ]
    return "\n".join(lines)


def generate_collapsible(summary: str, content: str) -> str:
    """Generate a collapsible section using HTML details/summary tags.

    Args:
        summary: Summary text shown when collapsed.
        content: Content shown when expanded.

    Returns:
        HTML details/summary block as a string.
    """
    return f"<details>\n<summary>{summary}</summary>\n\n{content}\n\n</details>"


def _escape_table_cell(value: str) -> str:
    """Escape pipe characters for use inside GFM table cells.

    Args:
        value: Raw cell value.

    Returns:
        Value with pipe characters escaped.
    """
    return value.replace("|", "\\|")


class EnhancedMarkdownGenerator:
    """Generate enhanced GitHub-flavored markdown reports.

    Produces reports with shields.io badges, mermaid charts,
    collapsible sections, and analysis of MCP vs baseline outcomes.

    Args:
        results_data: Evaluation results dictionary.
    """

    def __init__(self, results_data: dict[str, Any]) -> None:
        self.results_data = results_data

    def generate(self) -> str:
        """Generate the enhanced markdown report.

        Returns:
            Complete markdown document as a string.
        """
        sections: list[str] = []

        metadata = self.results_data.get("metadata", {})
        summary = self.results_data.get("summary", {})
        tasks = self.results_data.get("tasks", [])
        config = metadata.get("config", {})

        mcp = summary.get("mcp", {})
        baseline = summary.get("baseline", {}) or {}
        improvement = summary.get("improvement", "N/A")

        model = config.get("model", "unknown")
        benchmark = config.get("benchmark", "unknown")
        mcp_rate = mcp.get("rate", 0) or 0
        mcp_resolved = mcp.get("resolved", 0) or 0
        mcp_total = mcp.get("total", 0) or 0
        mcp_cost = mcp.get("total_cost")
        baseline_rate = baseline.get("rate", 0) or 0
        baseline_cost = baseline.get("total_cost")

        # ---- Title ----
        sections.append("# mcpbr Evaluation Report\n")

        # ---- Badges ----
        rate_pct = f"{mcp_rate * 100:.0f}%"
        badge_color = "brightgreen" if mcp_rate >= 0.5 else ("yellow" if mcp_rate >= 0.3 else "red")
        badges = [
            generate_badge("resolution rate", rate_pct, badge_color),
            generate_badge("model", model, "blue"),
            generate_badge("benchmark", benchmark, "blueviolet"),
        ]
        sections.append(" ".join(badges) + "\n")

        # ---- Summary section ----
        sections.append("## Summary\n")
        summary_rows = [
            ("MCP Resolution Rate", f"{mcp_rate * 100:.1f}%"),
            ("MCP Resolved", f"{mcp_resolved}/{mcp_total}"),
        ]
        if baseline:
            summary_rows.append(("Baseline Resolution Rate", f"{baseline_rate * 100:.1f}%"))
            summary_rows.append(
                ("Baseline Resolved", f"{baseline.get('resolved', 0)}/{baseline.get('total', 0)}")
            )
        summary_rows.append(("Improvement", str(improvement)))

        sections.append("| Metric | Value |")
        sections.append("|--------|-------|")
        for label, value in summary_rows:
            sections.append(f"| {label} | {value} |")
        sections.append("")

        # ---- Cost comparison ----
        if mcp_cost is not None or baseline_cost is not None:
            sections.append("## Cost Analysis\n")
            cost_data: dict[str, float] = {}
            if mcp_cost is not None:
                cost_data["MCP"] = round(mcp_cost, 4)
            if baseline_cost is not None:
                cost_data["Baseline"] = round(baseline_cost, 4)

            sections.append(generate_mermaid_bar("Cost Comparison (USD)", cost_data))
            sections.append("")

            sections.append("| Metric | Value |")
            sections.append("|--------|-------|")
            if mcp_cost is not None:
                sections.append(f"| MCP Total Cost | ${mcp_cost:.4f} |")
            if baseline_cost is not None:
                sections.append(f"| Baseline Total Cost | ${baseline_cost:.4f} |")
            if mcp_cost is not None and baseline_cost is not None:
                diff = mcp_cost - baseline_cost
                diff_label = "Additional Cost (MCP)" if diff >= 0 else "Cost Savings (MCP)"
                sections.append(f"| {diff_label} | ${abs(diff):.4f} |")
            sections.append("")

        # ---- Resolution outcome pie chart ----
        sections.append("## Resolution Outcomes\n")
        outcome_counts = self._categorize_outcomes(tasks)
        sections.append(generate_mermaid_pie("Task Resolution Outcomes", outcome_counts))
        sections.append("")

        # ---- Analysis section ----
        sections.append("## Analysis\n")
        mcp_only_wins = [
            t
            for t in tasks
            if t.get("mcp", {}).get("resolved")
            and not (t.get("baseline", {}) or {}).get("resolved")
        ]
        baseline_only_wins = [
            t
            for t in tasks
            if not t.get("mcp", {}).get("resolved")
            and (t.get("baseline", {}) or {}).get("resolved")
        ]

        sections.append(f"- **MCP-only wins:** {len(mcp_only_wins)}")
        sections.append(f"- **Baseline-only wins:** {len(baseline_only_wins)}")
        sections.append("")

        if mcp_only_wins:
            sections.append("### MCP-Only Wins\n")
            sections.append("| Instance ID |")
            sections.append("|-------------|")
            for t in mcp_only_wins:
                iid = _escape_table_cell(str(t.get("instance_id", "unknown")))
                sections.append(f"| {iid} |")
            sections.append("")

        if baseline_only_wins:
            sections.append("### Baseline-Only Wins\n")
            sections.append("| Instance ID |")
            sections.append("|-------------|")
            for t in baseline_only_wins:
                iid = _escape_table_cell(str(t.get("instance_id", "unknown")))
                sections.append(f"| {iid} |")
            sections.append("")

        # ---- Per-task results (collapsible) ----
        if tasks:
            task_content = self._build_task_table(tasks)
            sections.append(
                generate_collapsible("Per-Task Results (click to expand)", task_content)
            )
            sections.append("")

        # ---- Error details (collapsible) ----
        stats = summary.get("comprehensive_stats", {})
        error_content = self._build_error_section(stats)
        sections.append(generate_collapsible("Error Details (click to expand)", error_content))
        sections.append("")

        return "\n".join(sections)

    def save(self, output_path: Path) -> None:
        """Save the enhanced markdown report to a file.

        Args:
            output_path: Path to save the markdown file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate()
        output_path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _categorize_outcomes(tasks: list[dict[str, Any]]) -> dict[str, int]:
        """Categorize tasks into resolution outcome buckets.

        Categories:
        - MCP Only: resolved by MCP but not baseline
        - Baseline Only: resolved by baseline but not MCP
        - Both: resolved by both
        - Neither: resolved by neither

        Args:
            tasks: List of task result dicts.

        Returns:
            Mapping of category name to count.
        """
        mcp_only = 0
        baseline_only = 0
        both = 0
        neither = 0

        for task in tasks:
            mcp_resolved = (task.get("mcp") or {}).get("resolved", False)
            bl_resolved = (task.get("baseline") or {}).get("resolved", False)

            if mcp_resolved and bl_resolved:
                both += 1
            elif mcp_resolved and not bl_resolved:
                mcp_only += 1
            elif not mcp_resolved and bl_resolved:
                baseline_only += 1
            else:
                neither += 1

        return {
            "MCP Only": mcp_only,
            "Baseline Only": baseline_only,
            "Both": both,
            "Neither": neither,
        }

    @staticmethod
    def _build_task_table(tasks: list[dict[str, Any]]) -> str:
        """Build a GFM table of per-task results.

        Args:
            tasks: List of task result dicts.

        Returns:
            Markdown table as a string.
        """
        has_baseline = any(t.get("baseline") for t in tasks)

        header = "| Instance ID | MCP Resolved | MCP Cost"
        sep = "|-------------|:------------:|--------:"
        if has_baseline:
            header += " | Baseline Resolved | Baseline Cost"
            sep += " |:-----------------:|-------------:"
        header += " |"
        if not has_baseline:
            sep += " |"
        if not sep.endswith("|"):
            sep += " |"

        lines = [header, sep]
        for task in tasks:
            iid = _escape_table_cell(str(task.get("instance_id", "unknown")))
            mcp_data = task.get("mcp", {}) or {}
            mcp_res = "Yes" if mcp_data.get("resolved") else "No"
            mcp_cost = mcp_data.get("cost")
            mcp_cost_str = f"${mcp_cost:.4f}" if mcp_cost is not None else "N/A"

            row = f"| {iid} | {mcp_res} | {mcp_cost_str}"

            if has_baseline:
                bl_data = task.get("baseline", {}) or {}
                bl_res = "Yes" if bl_data.get("resolved") else "No"
                bl_cost = bl_data.get("cost")
                bl_cost_str = f"${bl_cost:.4f}" if bl_cost is not None else "N/A"
                row += f" | {bl_res} | {bl_cost_str}"

            row += " |"
            lines.append(row)

        return "\n".join(lines)

    @staticmethod
    def _build_error_section(stats: dict[str, Any]) -> str:
        """Build error details content for the collapsible section.

        Args:
            stats: Comprehensive stats dictionary.

        Returns:
            Markdown content describing errors.
        """
        if not stats:
            return "No error data available."

        errors = stats.get("mcp_errors", {})
        if not errors or errors.get("total_errors", 0) == 0:
            return "No errors recorded."

        lines = [
            f"**Total Errors:** {errors.get('total_errors', 0)}",
            "",
        ]

        categories = errors.get("error_categories", {})
        if categories:
            lines.append("| Error Category | Count |")
            lines.append("|----------------|------:|")
            for cat, count in sorted(categories.items()):
                lines.append(f"| {cat} | {count} |")

        return "\n".join(lines)
