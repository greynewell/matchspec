---
faq:
  - q: "What report formats does mcpbr support?"
    a: "mcpbr supports three report formats: interactive HTML with Chart.js charts and dark mode, enhanced GitHub-flavored Markdown with mermaid diagrams and shields.io badges, and print-friendly PDF via weasyprint with custom branding."
  - q: "How do I generate an HTML report programmatically?"
    a: "Create an HTMLReportGenerator with your results data, optionally set title and dark_mode, then call generate() for the HTML string or save() to write directly to a file."
  - q: "Do PDF reports require additional dependencies?"
    a: "Yes. PDF export requires weasyprint, which is an optional dependency. Install it with pip install weasyprint. The HTML-based report can also be printed to PDF from a browser without weasyprint."
---

# Reports API Reference

The `mcpbr.reports` package provides report generation in three formats: interactive HTML, enhanced Markdown, and print-friendly PDF. All generators accept the standard mcpbr evaluation results dictionary.

```python
from mcpbr.reports import (
    HTMLReportGenerator,
    EnhancedMarkdownGenerator,
    PDFReportGenerator,
)
```

---

## HTMLReportGenerator

Generates standalone, interactive HTML reports with embedded Chart.js charts, responsive layout, dark mode support, and sortable per-task results tables.

::: mcpbr.reports.HTMLReportGenerator
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - generate
        - save

### Usage

=== "Generate and save"

    ```python
    from pathlib import Path
    from mcpbr.reports import HTMLReportGenerator

    generator = HTMLReportGenerator(
        results_data=results,
        title="My MCP Server Evaluation",
        dark_mode=False,
    )

    # Save to file
    generator.save(Path("reports/evaluation.html"))
    ```

=== "Generate HTML string"

    ```python
    from mcpbr.reports import HTMLReportGenerator

    generator = HTMLReportGenerator(results_data=results)
    html_content = generator.generate()

    # Use the HTML string (e.g., serve via web framework)
    print(len(html_content), "characters")
    ```

=== "Dark mode"

    ```python
    from mcpbr.reports import HTMLReportGenerator

    generator = HTMLReportGenerator(
        results_data=results,
        title="Dark Mode Report",
        dark_mode=True,
    )
    generator.save(Path("reports/dark-report.html"))
    ```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results_data` | `dict[str, Any]` | (required) | Full evaluation results dictionary |
| `title` | `str` | `"mcpbr Evaluation Report"` | Report title for header and `<title>` tag |
| `dark_mode` | `bool` | `False` | When `True`, the report defaults to dark theme |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `generate()` | `str` | Generate a complete standalone HTML document |
| `save(output_path)` | `None` | Save the HTML report to a file (creates parent directories) |

### Features

The generated HTML report includes:

- **Summary cards**: Resolution rate, baseline comparison, improvement, and cost metrics
- **Charts** (via Chart.js CDN):
    - Bar chart comparing MCP vs baseline resolution rates
    - Bar chart comparing costs
    - Stacked bar chart for token usage (input vs output, when data available)
    - Doughnut chart for MCP tool usage breakdown (when data available)
- **Sortable per-task results table**: Click column headers to sort
- **Dark mode toggle**: Fixed button in the top-right corner
- **Responsive layout**: Works on desktop, tablet, and mobile
- **Self-contained**: All CSS and JavaScript inline, only Chart.js loaded via CDN

!!! note "Offline Viewing"
    The report requires a network connection only for loading Chart.js from CDN. All other assets are embedded inline. For fully offline viewing, you can download Chart.js and replace the CDN reference.

---

## EnhancedMarkdownGenerator

Generates GitHub-flavored Markdown reports with shields.io badges, mermaid charts, collapsible sections, and detailed analysis tables.

::: mcpbr.reports.EnhancedMarkdownGenerator
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - generate
        - save

### Usage

=== "Generate and save"

    ```python
    from pathlib import Path
    from mcpbr.reports import EnhancedMarkdownGenerator

    generator = EnhancedMarkdownGenerator(results_data=results)
    generator.save(Path("reports/evaluation.md"))
    ```

=== "Generate Markdown string"

    ```python
    from mcpbr.reports import EnhancedMarkdownGenerator

    generator = EnhancedMarkdownGenerator(results_data=results)
    markdown = generator.generate()
    print(markdown)
    ```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results_data` | `dict[str, Any]` | (required) | Full evaluation results dictionary |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `generate()` | `str` | Generate the enhanced Markdown document |
| `save(output_path)` | `None` | Save the Markdown report to a file |

### Features

The generated Markdown report includes:

- **Shields.io badges**: Resolution rate (color-coded), model, benchmark
- **Summary table**: Key metrics in a clean GFM table
- **Mermaid charts**:
    - Bar chart for cost comparison (MCP vs baseline)
    - Pie chart for resolution outcome distribution (MCP Only, Baseline Only, Both, Neither)
- **Analysis section**: MCP-only wins and baseline-only wins with instance IDs
- **Collapsible sections** (HTML `<details>`/`<summary>`):
    - Per-task results table (expandable)
    - Error details (expandable)

!!! tip "GitHub Rendering"
    The generated Markdown renders fully on GitHub, including mermaid diagrams and collapsible sections. Shields.io badges require an internet connection to display.

### Utility Functions

The module also exports helper functions for building Markdown components:

```python
from mcpbr.reports.enhanced_markdown import (
    generate_badge,
    generate_mermaid_pie,
    generate_mermaid_bar,
    generate_collapsible,
)

# Create a shields.io badge
badge = generate_badge("status", "passing", "brightgreen")
# ![status: passing](https://img.shields.io/badge/status-passing-brightgreen)

# Create a mermaid pie chart
chart = generate_mermaid_pie("Results", {"Passed": 45, "Failed": 5})

# Create a mermaid bar chart
bar = generate_mermaid_bar("Cost Comparison", {"MCP": 1.23, "Baseline": 0.98})

# Create a collapsible section
section = generate_collapsible("Click to expand", "Hidden content here")
```

---

## PDFReportGenerator

Generates print-friendly HTML reports with CSS `@media print` styles, page breaks, page counters, and custom branding. Optionally converts to PDF using weasyprint.

::: mcpbr.reports.PDFReportGenerator
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - generate_html
        - save_html
        - save_pdf

### Usage

=== "Save as HTML (no extra dependencies)"

    ```python
    from pathlib import Path
    from mcpbr.reports import PDFReportGenerator

    generator = PDFReportGenerator(
        results_data=results,
        title="Q4 Evaluation Report",
    )
    generator.save_html(Path("reports/evaluation-print.html"))
    ```

=== "Save as PDF (requires weasyprint)"

    ```python
    from pathlib import Path
    from mcpbr.reports import PDFReportGenerator

    generator = PDFReportGenerator(
        results_data=results,
        title="Q4 Evaluation Report",
    )
    generator.save_pdf(Path("reports/evaluation.pdf"))
    ```

=== "Custom branding"

    ```python
    from pathlib import Path
    from mcpbr.reports import PDFReportGenerator

    generator = PDFReportGenerator(
        results_data=results,
        title="Acme Corp MCP Evaluation",
        branding={
            "logo_text": "ACME",
            "primary_color": "#e63946",
            "company_name": "Acme Corporation",
        },
    )
    generator.save_pdf(Path("reports/acme-report.pdf"))
    ```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `results_data` | `dict[str, Any]` | (required) | Full evaluation results dictionary |
| `title` | `str` | `"mcpbr Evaluation Report"` | Report title |
| `branding` | `dict \| None` | `None` | Custom branding configuration |

### Branding Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `logo_text` | `str` | `"mcpbr"` | Logo text displayed in the report header |
| `primary_color` | `str` | `"#2563eb"` | Primary color for headings and accents (hex or CSS color name) |
| `company_name` | `str` | `"mcpbr"` | Company name in the subtitle and page footer |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `generate_html()` | `str` | Generate print-friendly HTML document |
| `save_html(output_path)` | `None` | Save the HTML report to a file |
| `save_pdf(output_path)` | `None` | Convert to PDF and save (requires weasyprint) |

### Features

The generated report includes:

- **Executive summary first**: Summary cards with key metrics at the top
- **Cost analysis table**: MCP vs baseline cost comparison
- **Detailed statistics**: Token usage, tool usage, and error summary (when available)
- **Per-task results table**: Full task-by-task breakdown with page break before it
- **Print-optimized CSS**:
    - `@media print` rules for proper pagination
    - `page-break-inside: avoid` on sections
    - Page counters via CSS `@page` rules
    - Title in the page footer
- **Custom branding**: Colors, company name, and logo text

!!! warning "weasyprint Dependency"
    `save_pdf()` requires the `weasyprint` package, which is not installed by default. Install it with:
    ```bash
    pip install weasyprint
    ```
    weasyprint itself requires system libraries (cairo, pango). See the [weasyprint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) for platform-specific instructions.

    Alternatively, use `save_html()` and print to PDF from a browser, which requires no extra dependencies.

---

## Common Patterns

### Generate All Report Formats

```python
from pathlib import Path
from mcpbr.reports import (
    HTMLReportGenerator,
    EnhancedMarkdownGenerator,
    PDFReportGenerator,
)

output_dir = Path("reports")

# Interactive HTML
HTMLReportGenerator(results, title="Evaluation").save(output_dir / "report.html")

# GitHub Markdown
EnhancedMarkdownGenerator(results).save(output_dir / "report.md")

# Print-friendly HTML (always works)
PDFReportGenerator(results, title="Evaluation").save_html(output_dir / "report-print.html")

# PDF (if weasyprint is available)
try:
    PDFReportGenerator(results, title="Evaluation").save_pdf(output_dir / "report.pdf")
except ImportError:
    print("weasyprint not available, skipping PDF")
```

### Results Data Structure

All report generators expect a results dictionary with this structure:

```python
results_data = {
    "metadata": {
        "timestamp": "2025-01-15T10:30:00Z",
        "config": {
            "model": "sonnet",
            "provider": "anthropic",
            "benchmark": "swe-bench-verified",
            "agent_harness": "claude-code",
        },
    },
    "summary": {
        "mcp": {
            "resolved": 45,
            "total": 100,
            "rate": 0.45,
            "total_cost": 12.50,
            "cost_per_task": 0.125,
        },
        "baseline": {
            "resolved": 38,
            "total": 100,
            "rate": 0.38,
            "total_cost": 10.20,
        },
        "improvement": "+18.4%",
        "comprehensive_stats": { ... },  # Optional, adds more detail
    },
    "tasks": [
        {
            "instance_id": "django__django-11099",
            "mcp": {
                "resolved": True,
                "cost": 0.15,
                "tokens": {"input": 5000, "output": 1200},
                "iterations": 3,
                "tool_calls": 12,
                "runtime_seconds": 120.5,
            },
            "baseline": {
                "resolved": False,
                "cost": 0.12,
            },
        },
        # ... more tasks
    ],
}
```
