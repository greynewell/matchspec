"""HTML report generation for mcpbr evaluation results.

Generates standalone, interactive HTML reports with embedded Chart.js charts,
responsive layout, dark mode support, and sortable per-task results tables.
"""

import html
import json
from pathlib import Path
from typing import Any


def _escape_html(text: Any) -> str:
    """Safely escape HTML entities in user-provided content.

    Args:
        text: The text to escape. Non-string values are converted to string first.

    Returns:
        HTML-escaped string safe for embedding in HTML documents.
    """
    return html.escape(str(text))


def _generate_css(dark_mode: bool) -> str:
    """Generate CSS styles for the HTML report.

    Includes responsive layout rules, dark mode support via
    ``prefers-color-scheme`` media query, and an optional dark mode
    class for explicit toggling.

    Args:
        dark_mode: When True, the default theme is dark.

    Returns:
        A CSS string (without ``<style>`` tags).
    """
    # Base light-theme variables
    light_vars = """
        --bg-primary: #ffffff;
        --bg-secondary: #f8f9fa;
        --bg-card: #ffffff;
        --text-primary: #212529;
        --text-secondary: #6c757d;
        --border-color: #dee2e6;
        --accent: #0d6efd;
        --accent-secondary: #6610f2;
        --success: #198754;
        --danger: #dc3545;
        --table-stripe: #f8f9fa;
        --shadow: 0 2px 8px rgba(0,0,0,0.08);
    """
    dark_vars = """
        --bg-primary: #1a1a2e;
        --bg-secondary: #16213e;
        --bg-card: #1e2a3a;
        --text-primary: #e0e0e0;
        --text-secondary: #a0a0a0;
        --border-color: #2d3748;
        --accent: #4da6ff;
        --accent-secondary: #a78bfa;
        --success: #34d399;
        --danger: #f87171;
        --table-stripe: #1e2a3a;
        --shadow: 0 2px 8px rgba(0,0,0,0.3);
    """

    initial_vars = dark_vars if dark_mode else light_vars

    return f"""
        :root {{
            {initial_vars}
        }}

        @media (prefers-color-scheme: dark) {{
            :root:not(.light-mode) {{
                {dark_vars}
            }}
        }}

        .dark-mode {{
            {dark_vars}
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 0;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem 1rem;
        }}

        /* Header */
        .report-header {{
            text-align: center;
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 2px solid var(--border-color);
        }}
        .report-header h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: var(--accent);
        }}
        .report-header .meta {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .report-header .meta span {{
            margin: 0 0.75rem;
        }}

        /* Dark-mode toggle */
        .theme-toggle {{
            position: fixed;
            top: 1rem;
            right: 1rem;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.4rem 0.8rem;
            cursor: pointer;
            font-size: 0.85rem;
            color: var(--text-primary);
            box-shadow: var(--shadow);
            z-index: 1000;
        }}

        /* Summary cards */
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: var(--shadow);
            text-align: center;
        }}
        .card .card-label {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .card .card-value {{
            font-size: 1.75rem;
            font-weight: 700;
        }}
        .card .card-detail {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }}
        .card-value.success {{ color: var(--success); }}
        .card-value.danger  {{ color: var(--danger); }}
        .card-value.accent  {{ color: var(--accent); }}

        /* Charts grid */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .chart-container {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: var(--shadow);
        }}
        .chart-container h3 {{
            margin-bottom: 1rem;
            font-size: 1.1rem;
            color: var(--text-primary);
        }}
        .chart-container canvas {{
            max-height: 320px;
        }}

        /* Task table */
        .table-section {{
            margin-top: 2rem;
        }}
        .table-section h2 {{
            margin-bottom: 1rem;
            font-size: 1.4rem;
        }}
        .table-wrapper {{
            overflow-x: auto;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        thead {{
            background: var(--bg-secondary);
        }}
        th {{
            padding: 0.75rem 1rem;
            text-align: left;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }}
        th:hover {{
            color: var(--accent);
        }}
        th .sort-indicator {{
            margin-left: 4px;
            font-size: 0.7rem;
        }}
        td {{
            padding: 0.6rem 1rem;
            border-top: 1px solid var(--border-color);
        }}
        tbody tr:nth-child(even) {{
            background: var(--table-stripe);
        }}
        tbody tr:hover {{
            background: var(--bg-secondary);
        }}
        .pass {{
            color: var(--success);
            font-weight: 600;
        }}
        .fail {{
            color: var(--danger);
            font-weight: 600;
        }}
        .dash {{
            color: var(--text-secondary);
        }}
        .error-cell {{
            color: var(--danger);
            font-size: 0.85rem;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .container {{
                padding: 1rem 0.5rem;
            }}
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
            .summary-cards {{
                grid-template-columns: 1fr 1fr;
            }}
            .report-header h1 {{
                font-size: 1.5rem;
            }}
        }}
        @media (max-width: 480px) {{
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
        }}
    """


def _generate_summary_cards(summary: dict[str, Any]) -> str:
    """Generate HTML for summary metric cards.

    Args:
        summary: The ``summary`` dict from evaluation results.

    Returns:
        HTML string for the summary cards section.
    """
    mcp = summary.get("mcp", {})
    baseline = summary.get("baseline", {})
    improvement = summary.get("improvement", "N/A")

    mcp_rate = mcp.get("rate", 0)
    baseline_rate = baseline.get("rate", 0)
    mcp_resolved = mcp.get("resolved", 0)
    mcp_total = mcp.get("total", 0)
    baseline_resolved = baseline.get("resolved", 0)
    baseline_total = baseline.get("total", 0)

    mcp_cost = mcp.get("total_cost")
    baseline_cost = baseline.get("total_cost")

    cards = f"""
    <div class="summary-cards">
        <div class="card">
            <div class="card-label">MCP Resolution Rate</div>
            <div class="card-value success">{mcp_rate * 100:.1f}%</div>
            <div class="card-detail">{mcp_resolved}/{mcp_total} tasks</div>
        </div>
        <div class="card">
            <div class="card-label">Baseline Resolution Rate</div>
            <div class="card-value">{baseline_rate * 100:.1f}%</div>
            <div class="card-detail">{baseline_resolved}/{baseline_total} tasks</div>
        </div>
        <div class="card">
            <div class="card-label">Improvement</div>
            <div class="card-value accent">{_escape_html(improvement)}</div>
        </div>
    """

    # Cost cards
    if mcp_cost is not None:
        cards += f"""
        <div class="card">
            <div class="card-label">MCP Total Cost</div>
            <div class="card-value">${mcp_cost:.2f}</div>
            <div class="card-detail">${mcp.get("cost_per_task", 0):.3f}/task</div>
        </div>
        """

    if baseline_cost is not None:
        cards += f"""
        <div class="card">
            <div class="card-label">Baseline Total Cost</div>
            <div class="card-value">${baseline_cost:.2f}</div>
            <div class="card-detail">${baseline.get("cost_per_task", 0):.3f}/task</div>
        </div>
        """

    cards += "</div>"
    return cards


def _generate_task_table(tasks: list[dict[str, Any]]) -> str:
    """Generate HTML for the per-task results table.

    Args:
        tasks: List of task result dicts.

    Returns:
        HTML string containing a ``<table>`` element.
    """
    rows = []
    for task in tasks:
        instance_id = _escape_html(task.get("instance_id", ""))
        mcp = task.get("mcp", {}) or {}
        baseline = task.get("baseline", {}) or {}

        mcp_resolved = mcp.get("resolved")
        baseline_resolved = baseline.get("resolved")

        if mcp_resolved is True:
            mcp_label = '<span class="pass">PASS</span>'
        elif mcp_resolved is False:
            mcp_label = '<span class="fail">FAIL</span>'
        else:
            mcp_label = '<span class="dash">-</span>'

        if baseline_resolved is True:
            baseline_label = '<span class="pass">PASS</span>'
        elif baseline_resolved is False:
            baseline_label = '<span class="fail">FAIL</span>'
        else:
            baseline_label = '<span class="dash">-</span>'

        mcp_cost = mcp.get("cost")
        cost_cell = f"${mcp_cost:.2f}" if mcp_cost is not None else "-"

        error = mcp.get("error", "") or baseline.get("error", "") or ""
        error_escaped = _escape_html(error) if error else ""

        rows.append(
            f"<tr>"
            f"<td>{instance_id}</td>"
            f"<td>{mcp_label}</td>"
            f"<td>{baseline_label}</td>"
            f"<td>{cost_cell}</td>"
            f'<td class="error-cell" title="{error_escaped}">{error_escaped}</td>'
            f"</tr>"
        )

    body = "\n".join(rows)

    return f"""
    <div class="table-wrapper">
        <table id="taskTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Instance ID <span class="sort-indicator"></span></th>
                    <th onclick="sortTable(1)">MCP <span class="sort-indicator"></span></th>
                    <th onclick="sortTable(2)">Baseline <span class="sort-indicator"></span></th>
                    <th onclick="sortTable(3)">Cost <span class="sort-indicator"></span></th>
                    <th onclick="sortTable(4)">Error <span class="sort-indicator"></span></th>
                </tr>
            </thead>
            <tbody>
                {body}
            </tbody>
        </table>
    </div>
    """


def _generate_chart_js(results_data: dict[str, Any]) -> str:
    """Generate JavaScript for Chart.js chart initialization and table sorting.

    Produces code for:
    - Bar chart comparing MCP vs baseline resolution rates
    - Bar chart comparing costs
    - Doughnut chart for tool usage (if data available)
    - Bar chart for token usage (if data available)
    - Table sorting function

    Args:
        results_data: The full evaluation results dict.

    Returns:
        A JavaScript string (without ``<script>`` tags).
    """
    summary = results_data.get("summary", {})
    mcp = summary.get("mcp", {})
    baseline = summary.get("baseline", {})
    comp_stats = summary.get("comprehensive_stats", {})

    mcp_rate = mcp.get("rate", 0) * 100
    baseline_rate = baseline.get("rate", 0) * 100
    mcp_cost = mcp.get("total_cost", 0)
    baseline_cost = baseline.get("total_cost", 0)

    js_parts: list[str] = []

    # --- Dark-mode toggle ---
    js_parts.append("""
    function toggleDarkMode() {
        document.documentElement.classList.toggle('dark-mode');
        const btn = document.getElementById('themeToggle');
        if (document.documentElement.classList.contains('dark-mode')) {
            btn.textContent = 'Light Mode';
        } else {
            btn.textContent = 'Dark Mode';
        }
    }
    """)

    # --- Chart.js default config ---
    js_parts.append("""
    Chart.defaults.color = getComputedStyle(document.documentElement)
        .getPropertyValue('--text-primary').trim() || '#212529';
    Chart.defaults.borderColor = getComputedStyle(document.documentElement)
        .getPropertyValue('--border-color').trim() || '#dee2e6';
    """)

    # --- Resolution Rate Chart ---
    js_parts.append(f"""
    new Chart(document.getElementById('resolutionChart'), {{
        type: 'bar',
        data: {{
            labels: ['MCP Agent', 'Baseline'],
            datasets: [{{
                label: 'Resolution Rate (%)',
                data: [{mcp_rate:.1f}, {baseline_rate:.1f}],
                backgroundColor: ['rgba(25,135,84,0.7)', 'rgba(255,193,7,0.7)'],
                borderColor: ['#198754', '#ffc107'],
                borderWidth: 2,
                borderRadius: 6,
                maxBarThickness: 80
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ display: false }},
                title: {{ display: false }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    max: 100,
                    ticks: {{ callback: v => v + '%' }}
                }}
            }}
        }}
    }});
    """)

    # --- Cost Chart ---
    js_parts.append(f"""
    new Chart(document.getElementById('costChart'), {{
        type: 'bar',
        data: {{
            labels: ['MCP Agent', 'Baseline'],
            datasets: [{{
                label: 'Total Cost ($)',
                data: [{mcp_cost}, {baseline_cost}],
                backgroundColor: ['rgba(13,110,253,0.7)', 'rgba(102,16,242,0.7)'],
                borderColor: ['#0d6efd', '#6610f2'],
                borderWidth: 2,
                borderRadius: 6,
                maxBarThickness: 80
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ display: false }},
                title: {{ display: false }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    ticks: {{ callback: v => '$' + v.toFixed(2) }}
                }}
            }}
        }}
    }});
    """)

    # --- Token Chart (only with comprehensive_stats) ---
    mcp_tokens = comp_stats.get("mcp_tokens", {})
    baseline_tokens = comp_stats.get("baseline_tokens", {})
    if mcp_tokens or baseline_tokens:
        mcp_input = mcp_tokens.get("total_input", 0)
        mcp_output = mcp_tokens.get("total_output", 0)
        baseline_input = baseline_tokens.get("total_input", 0)
        baseline_output = baseline_tokens.get("total_output", 0)

        js_parts.append(f"""
        new Chart(document.getElementById('tokenChart'), {{
            type: 'bar',
            data: {{
                labels: ['Input Tokens', 'Output Tokens'],
                datasets: [
                    {{
                        label: 'MCP Agent',
                        data: [{mcp_input}, {mcp_output}],
                        backgroundColor: 'rgba(25,135,84,0.7)',
                        borderColor: '#198754',
                        borderWidth: 2,
                        borderRadius: 6
                    }},
                    {{
                        label: 'Baseline',
                        data: [{baseline_input}, {baseline_output}],
                        backgroundColor: 'rgba(255,193,7,0.7)',
                        borderColor: '#ffc107',
                        borderWidth: 2,
                        borderRadius: 6
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{ callback: v => v.toLocaleString() }}
                    }}
                }}
            }}
        }});
        """)

    # --- Tool Usage Doughnut (only with tool data) ---
    mcp_tools = comp_stats.get("mcp_tools", {})
    most_used = mcp_tools.get("most_used_tools", {})
    if most_used:
        tool_labels = json.dumps(list(most_used.keys()))
        tool_values = json.dumps(list(most_used.values()))
        # Generate distinct colors for each tool slice
        palette = [
            "rgba(13,110,253,0.7)",
            "rgba(25,135,84,0.7)",
            "rgba(255,193,7,0.7)",
            "rgba(102,16,242,0.7)",
            "rgba(220,53,69,0.7)",
            "rgba(32,201,151,0.7)",
            "rgba(253,126,20,0.7)",
            "rgba(111,66,193,0.7)",
        ]
        colors = json.dumps(palette[: len(most_used)])

        js_parts.append(f"""
        new Chart(document.getElementById('toolChart'), {{
            type: 'doughnut',
            data: {{
                labels: {tool_labels},
                datasets: [{{
                    data: {tool_values},
                    backgroundColor: {colors},
                    borderWidth: 2,
                    hoverOffset: 8
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{ display: false }},
                    legend: {{ position: 'bottom' }}
                }}
            }}
        }});
        """)

    # --- Table sort function ---
    js_parts.append("""
    let sortDirection = {};
    function sortTable(columnIndex) {
        const table = document.getElementById('taskTable');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const dir = sortDirection[columnIndex] === 'asc' ? 'desc' : 'asc';
        sortDirection[columnIndex] = dir;

        rows.sort((a, b) => {
            let aText = a.cells[columnIndex].textContent.trim();
            let bText = b.cells[columnIndex].textContent.trim();
            // Try numeric sort
            let aNum = parseFloat(aText.replace('$', ''));
            let bNum = parseFloat(bText.replace('$', ''));
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return dir === 'asc' ? aNum - bNum : bNum - aNum;
            }
            // Fallback to string sort
            return dir === 'asc'
                ? aText.localeCompare(bText)
                : bText.localeCompare(aText);
        });

        rows.forEach(row => tbody.appendChild(row));
    }
    """)

    return "\n".join(js_parts)


class HTMLReportGenerator:
    """Generates standalone, interactive HTML reports from evaluation results.

    The report embeds all CSS and JavaScript inline so it can be viewed as a
    single ``.html`` file with no server required.  Chart.js is loaded via
    CDN.

    Args:
        results_data: Full evaluation results dict.
        title: Report title displayed in the header and ``<title>`` tag.
        dark_mode: When ``True``, the report defaults to dark theme.
    """

    def __init__(
        self,
        results_data: dict[str, Any],
        title: str = "mcpbr Evaluation Report",
        dark_mode: bool = False,
    ) -> None:
        self._results = results_data
        self._title = title
        self._dark_mode = dark_mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Generate a complete standalone HTML string.

        Returns:
            The full HTML document as a string.
        """
        metadata = self._results.get("metadata", {})
        config = metadata.get("config", {})
        summary = self._results.get("summary", {})
        tasks = self._results.get("tasks", [])
        comp_stats = summary.get("comprehensive_stats", {})

        timestamp = _escape_html(metadata.get("timestamp", ""))
        model = _escape_html(config.get("model", ""))
        benchmark = _escape_html(config.get("benchmark", ""))

        css = _generate_css(self._dark_mode)
        summary_cards = _generate_summary_cards(summary)
        task_table = _generate_task_table(tasks)
        chart_js = _generate_chart_js(self._results)

        # Determine which chart containers to render
        has_token_data = bool(comp_stats.get("mcp_tokens") or comp_stats.get("baseline_tokens"))
        has_tool_data = bool(comp_stats.get("mcp_tools", {}).get("most_used_tools"))

        dark_class = ' class="dark-mode"' if self._dark_mode else ""

        # Build chart containers
        charts_html = """
        <div class="charts-grid">
            <div class="chart-container">
                <h3>Resolution Rate Comparison</h3>
                <canvas id="resolutionChart"></canvas>
            </div>
            <div class="chart-container">
                <h3>Cost Comparison</h3>
                <canvas id="costChart"></canvas>
            </div>
        """

        if has_token_data:
            charts_html += """
            <div class="chart-container">
                <h3>Token Usage Comparison</h3>
                <canvas id="tokenChart"></canvas>
            </div>
            """

        if has_tool_data:
            charts_html += """
            <div class="chart-container">
                <h3>Tool Usage Breakdown</h3>
                <canvas id="toolChart"></canvas>
            </div>
            """

        charts_html += "</div>"

        return f"""<!DOCTYPE html>
<html lang="en"{dark_class}>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape_html(self._title)}</title>
    <style>
    {css}
    </style>
</head>
<body>
    <button id="themeToggle" class="theme-toggle" onclick="toggleDarkMode()">
        {"Light Mode" if self._dark_mode else "Dark Mode"}
    </button>

    <div class="container">
        <div class="report-header">
            <h1>{_escape_html(self._title)}</h1>
            <div class="meta">
                <span>Generated: {timestamp}</span>
                <span>Model: {model}</span>
                <span>Benchmark: {benchmark}</span>
            </div>
        </div>

        {summary_cards}

        {charts_html}

        <div class="table-section">
            <h2>Per-Task Results</h2>
            {task_table}
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
    {chart_js}
    </script>
</body>
</html>"""

    def save(self, output_path: Path) -> None:
        """Save the generated HTML report to a file.

        Creates parent directories if they do not exist.

        Args:
            output_path: Filesystem path for the output HTML file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.generate(), encoding="utf-8")
