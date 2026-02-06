"""PDF report generation for mcpbr evaluation results.

Generates print-friendly HTML reports that can be converted to PDF
using weasyprint (optional dependency). The HTML output includes
CSS @media print styles, page breaks, page counters, and supports
custom branding.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,8})$|^[a-zA-Z]{1,30}$")


def _safe_color(value: str, default: str) -> str:
    """Return value if it looks like a CSS color, otherwise default."""
    return value if _COLOR_RE.match(value) else default


class PDFReportGenerator:
    """Generate print-friendly HTML reports with optional PDF export.

    The generator produces executive-friendly HTML reports with:
    - Summary section first, details later
    - CSS @media print styles for proper pagination
    - Page numbers via CSS counters
    - Custom branding support (colors, company name, logo text)
    - Cost analysis and per-task results tables

    Args:
        results_data: Evaluation results dictionary.
        title: Report title. Defaults to "mcpbr Evaluation Report".
        branding: Optional branding configuration dict with keys:
            logo_text (str), primary_color (str hex), company_name (str).
    """

    def __init__(
        self,
        results_data: dict[str, Any],
        title: str = "mcpbr Evaluation Report",
        branding: dict | None = None,
    ) -> None:
        self.results_data = results_data
        self.title = title
        self.branding = branding

    def generate_html(self) -> str:
        """Generate print-friendly HTML report.

        Returns:
            Complete HTML document as a string with inline CSS for print styling.
        """
        primary_color = "#2563eb"
        company_name = "mcpbr"
        logo_text = "mcpbr"

        if self.branding:
            primary_color = _safe_color(
                self.branding.get("primary_color", primary_color), primary_color
            )
            company_name = html.escape(self.branding.get("company_name", company_name))
            logo_text = html.escape(self.branding.get("logo_text", logo_text))
        else:
            company_name = html.escape(company_name)
            logo_text = html.escape(logo_text)

        escaped_title = html.escape(self.title)

        metadata = self.results_data.get("metadata", {})
        summary = self.results_data.get("summary", {})
        tasks = self.results_data.get("tasks", [])
        config = metadata.get("config", {})

        mcp_summary = summary.get("mcp", {})
        baseline_summary = summary.get("baseline", {}) or {}
        improvement = summary.get("improvement", "N/A")

        mcp_rate = mcp_summary.get("rate", 0) or 0
        mcp_resolved = mcp_summary.get("resolved", 0) or 0
        mcp_total = mcp_summary.get("total", 0) or 0
        mcp_cost = mcp_summary.get("total_cost", None)

        baseline_rate = baseline_summary.get("rate", 0) or 0
        baseline_resolved = baseline_summary.get("resolved", 0) or 0
        baseline_total = baseline_summary.get("total", 0) or 0
        baseline_cost = baseline_summary.get("total_cost", None)

        model = config.get("model", "N/A")
        benchmark = config.get("benchmark", "N/A")

        # Build the summary metrics cards
        summary_cards = self._build_summary_cards(
            mcp_rate,
            mcp_resolved,
            mcp_total,
            baseline_rate,
            baseline_resolved,
            baseline_total,
            improvement,
        )

        # Build cost analysis section
        cost_section = self._build_cost_section(mcp_cost, baseline_cost)

        # Build per-task results table
        task_table = self._build_task_table(tasks)

        # Build comprehensive stats section if available
        stats_section = self._build_stats_section(summary)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_title}</title>
    <style>
        /* Base styles */
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #1f2937;
            line-height: 1.6;
            padding: 2rem;
            max-width: 1100px;
            margin: 0 auto;
        }}

        h1 {{
            color: {primary_color};
            font-size: 1.8rem;
            margin-bottom: 0.25rem;
        }}

        h2 {{
            color: {primary_color};
            font-size: 1.3rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
            border-bottom: 2px solid {primary_color};
            padding-bottom: 0.3rem;
        }}

        h3 {{
            font-size: 1.1rem;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
        }}

        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            border-bottom: 3px solid {primary_color};
            padding-bottom: 1rem;
        }}

        .header-left {{
            flex: 1;
        }}

        .logo {{
            font-size: 1.2rem;
            font-weight: bold;
            color: {primary_color};
        }}

        .subtitle {{
            color: #6b7280;
            font-size: 0.9rem;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }}

        .card {{
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}

        .card-value {{
            font-size: 1.8rem;
            font-weight: bold;
            color: {primary_color};
        }}

        .card-label {{
            font-size: 0.85rem;
            color: #6b7280;
            margin-top: 0.25rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.9rem;
        }}

        th, td {{
            border: 1px solid #d1d5db;
            padding: 0.5rem 0.75rem;
            text-align: left;
        }}

        th {{
            background-color: #f3f4f6;
            font-weight: 600;
        }}

        tr:nth-child(even) {{
            background-color: #f9fafb;
        }}

        .resolved {{
            color: #059669;
            font-weight: 600;
        }}

        .unresolved {{
            color: #dc2626;
        }}

        .cost-table {{
            max-width: 500px;
        }}

        .section {{
            page-break-inside: avoid;
        }}

        .page-break {{
            page-break-before: always;
            break-before: page;
        }}

        /* Print-specific styles */
        @media print {{
            body {{
                padding: 0;
                font-size: 10pt;
            }}

            .header {{
                page-break-after: avoid;
            }}

            h2 {{
                page-break-after: avoid;
            }}

            table {{
                page-break-inside: auto;
            }}

            tr {{
                page-break-inside: avoid;
            }}

            .cards {{
                page-break-inside: avoid;
            }}

            /* Page counter */
            @page {{
                counter-increment: page;
                margin: 2cm;

                @bottom-right {{
                    content: "Page " counter(page);
                    font-size: 9pt;
                    color: #6b7280;
                }}

                @bottom-left {{
                    content: "{escaped_title}";
                    font-size: 9pt;
                    color: #6b7280;
                }}
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <h1>{escaped_title}</h1>
            <div class="subtitle">
                Model: {html.escape(str(model))} |
                Benchmark: {html.escape(str(benchmark))} |
                Generated by {company_name}
            </div>
        </div>
        <div class="logo">{logo_text}</div>
    </div>

    <div class="section">
        <h2>Summary</h2>
        {summary_cards}
    </div>

    <div class="section">
        <h2>Cost Analysis</h2>
        {cost_section}
    </div>

    {stats_section}

    <div class="page-break"></div>

    <div class="section">
        <h2>Per-Task Results</h2>
        {task_table}
    </div>
</body>
</html>"""

    def save_html(self, output_path: Path) -> None:
        """Save the print-friendly HTML report to a file.

        Args:
            output_path: Path to save the HTML file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html_content = self.generate_html()
        output_path.write_text(html_content, encoding="utf-8")

    def save_pdf(self, output_path: Path) -> None:
        """Convert HTML to PDF using weasyprint and save.

        Args:
            output_path: Path to save the PDF file.

        Raises:
            ImportError: If weasyprint is not installed. Includes
                installation instructions in the error message.
        """
        try:
            import weasyprint
        except (ImportError, ModuleNotFoundError) as err:
            raise ImportError(
                "weasyprint is required for PDF export but is not installed. "
                "Install it with: pip install weasyprint\n"
                "For more information, see: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
            ) from err

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html_content = self.generate_html()
        doc = weasyprint.HTML(string=html_content)
        doc.write_pdf(str(output_path))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_summary_cards(
        self,
        mcp_rate: float,
        mcp_resolved: int,
        mcp_total: int,
        baseline_rate: float,
        baseline_resolved: int,
        baseline_total: int,
        improvement: str,
    ) -> str:
        """Build the summary metric cards HTML."""
        cards = [
            self._card(f"{mcp_rate * 100:.1f}%", "MCP Resolution Rate"),
            self._card(f"{mcp_resolved}/{mcp_total}", "MCP Resolved"),
        ]

        if baseline_total > 0:
            cards.append(self._card(f"{baseline_rate * 100:.1f}%", "Baseline Resolution Rate"))
            cards.append(self._card(f"{baseline_resolved}/{baseline_total}", "Baseline Resolved"))

        cards.append(self._card(html.escape(str(improvement)), "Improvement"))

        return '<div class="cards">' + "\n".join(cards) + "</div>"

    @staticmethod
    def _card(value: str, label: str) -> str:
        """Build a single metric card."""
        return (
            '<div class="card">'
            f'<div class="card-value">{value}</div>'
            f'<div class="card-label">{html.escape(label)}</div>'
            "</div>"
        )

    def _build_cost_section(
        self,
        mcp_cost: float | None,
        baseline_cost: float | None,
    ) -> str:
        """Build the cost analysis HTML section."""
        rows: list[str] = []

        if mcp_cost is not None:
            rows.append(f"<tr><td>MCP Total Cost</td><td>${mcp_cost:.4f}</td></tr>")

        if baseline_cost is not None:
            rows.append(f"<tr><td>Baseline Total Cost</td><td>${baseline_cost:.4f}</td></tr>")

        if mcp_cost is not None and baseline_cost is not None:
            diff = mcp_cost - baseline_cost
            label = "Additional Cost (MCP)" if diff >= 0 else "Cost Savings (MCP)"
            rows.append(f"<tr><td>{label}</td><td>${abs(diff):.4f}</td></tr>")

        if not rows:
            return "<p>No cost data available.</p>"

        return (
            '<table class="cost-table">'
            "<tr><th>Metric</th><th>Value</th></tr>" + "\n".join(rows) + "</table>"
        )

    def _build_task_table(self, tasks: list[dict[str, Any]]) -> str:
        """Build the per-task results table."""
        if not tasks:
            return "<p>No task results available.</p>"

        # Determine if we have baseline data
        has_baseline = any(task.get("baseline") for task in tasks)

        header_cells = "<th>Instance ID</th><th>MCP Resolved</th><th>MCP Cost</th>"
        if has_baseline:
            header_cells += "<th>Baseline Resolved</th><th>Baseline Cost</th>"

        rows: list[str] = []
        for task in tasks:
            instance_id = html.escape(str(task.get("instance_id", "unknown")))
            mcp = task.get("mcp", {}) or {}
            mcp_resolved = mcp.get("resolved", False)
            mcp_cost = mcp.get("cost")

            resolved_cls = "resolved" if mcp_resolved else "unresolved"
            resolved_text = "Yes" if mcp_resolved else "No"
            cost_text = f"${mcp_cost:.4f}" if mcp_cost is not None else "N/A"

            row = (
                f"<tr>"
                f"<td>{instance_id}</td>"
                f'<td class="{resolved_cls}">{resolved_text}</td>'
                f"<td>{cost_text}</td>"
            )

            if has_baseline:
                bl = task.get("baseline", {}) or {}
                bl_resolved = bl.get("resolved", False)
                bl_cost = bl.get("cost")
                bl_cls = "resolved" if bl_resolved else "unresolved"
                bl_text = "Yes" if bl_resolved else "No"
                bl_cost_text = f"${bl_cost:.4f}" if bl_cost is not None else "N/A"
                row += f'<td class="{bl_cls}">{bl_text}</td><td>{bl_cost_text}</td>'

            row += "</tr>"
            rows.append(row)

        return f"<table><tr>{header_cells}</tr>" + "\n".join(rows) + "</table>"

    def _build_stats_section(self, summary: dict[str, Any]) -> str:
        """Build the comprehensive statistics section if data is available."""
        stats = summary.get("comprehensive_stats")
        if not stats:
            return ""

        parts: list[str] = ['<div class="section">', "<h2>Detailed Statistics</h2>"]

        # Token usage
        mcp_tokens = stats.get("mcp_tokens", {})
        baseline_tokens = stats.get("baseline_tokens", {})
        if mcp_tokens or baseline_tokens:
            parts.append("<h3>Token Usage</h3>")
            parts.append("<table>")
            parts.append("<tr><th>Metric</th><th>MCP</th><th>Baseline</th></tr>")
            parts.append(
                "<tr><td>Input Tokens</td>"
                f"<td>{mcp_tokens.get('total_input', 0):,}</td>"
                f"<td>{baseline_tokens.get('total_input', 0):,}</td></tr>"
            )
            parts.append(
                "<tr><td>Output Tokens</td>"
                f"<td>{mcp_tokens.get('total_output', 0):,}</td>"
                f"<td>{baseline_tokens.get('total_output', 0):,}</td></tr>"
            )
            parts.append("</table>")

        # Tool usage
        mcp_tools = stats.get("mcp_tools", {})
        if mcp_tools:
            per_tool = mcp_tools.get("per_tool", {})
            if per_tool:
                parts.append("<h3>Tool Usage</h3>")
                parts.append("<table>")
                parts.append("<tr><th>Tool</th><th>Calls</th></tr>")
                for tool_name, tool_data in sorted(per_tool.items()):
                    total = tool_data.get("total", 0) if isinstance(tool_data, dict) else tool_data
                    parts.append(f"<tr><td>{html.escape(tool_name)}</td><td>{total}</td></tr>")
                parts.append("</table>")

        # Errors
        mcp_errors = stats.get("mcp_errors", {})
        if mcp_errors and mcp_errors.get("total_errors", 0) > 0:
            parts.append("<h3>Error Summary</h3>")
            parts.append(f"<p>Total errors: {mcp_errors['total_errors']}</p>")
            categories = mcp_errors.get("error_categories", {})
            if categories:
                parts.append("<table>")
                parts.append("<tr><th>Category</th><th>Count</th></tr>")
                for cat, count in sorted(categories.items()):
                    parts.append(f"<tr><td>{html.escape(str(cat))}</td><td>{count}</td></tr>")
                parts.append("</table>")

        parts.append("</div>")
        return "\n".join(parts)
