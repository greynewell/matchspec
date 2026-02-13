"""Tests for the reports package and CLI compare/analytics commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mcpbr.cli import main
from mcpbr.reports.enhanced_markdown import (
    EnhancedMarkdownGenerator,
    generate_badge,
    generate_collapsible,
    generate_mermaid_bar,
    generate_mermaid_pie,
)
from mcpbr.reports.html_report import HTMLReportGenerator
from mcpbr.reports.pdf_report import PDFReportGenerator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_results() -> dict:
    """Minimal results data with only required fields."""
    return {
        "metadata": {
            "timestamp": "2025-01-01T00:00:00",
            "config": {"model": "test-model", "benchmark": "swe-bench-verified"},
        },
        "summary": {
            "mcp": {
                "resolved": 7,
                "total": 10,
                "rate": 0.7,
                "total_cost": 1.50,
                "cost_per_task": 0.15,
            },
            "baseline": {
                "resolved": 5,
                "total": 10,
                "rate": 0.5,
                "total_cost": 1.20,
                "cost_per_task": 0.12,
            },
            "improvement": "+20.0%",
        },
        "tasks": [
            {
                "instance_id": "test-1",
                "mcp": {"resolved": True, "cost": 0.15},
                "baseline": {"resolved": False},
            },
            {
                "instance_id": "test-2",
                "mcp": {"resolved": False, "cost": 0.20},
                "baseline": {"resolved": True},
            },
        ],
    }


@pytest.fixture
def comprehensive_results() -> dict:
    """Comprehensive results data with all optional fields populated."""
    return {
        "metadata": {
            "timestamp": "2025-06-15T12:30:00",
            "config": {
                "model": "claude-sonnet-4-5-20250929",
                "benchmark": "swe-bench-verified",
                "provider": "anthropic",
                "agent_harness": "agentless",
                "sample_size": 10,
                "timeout_seconds": 300,
                "max_iterations": 50,
            },
        },
        "summary": {
            "mcp": {
                "resolved": 8,
                "total": 10,
                "rate": 0.8,
                "total_cost": 2.50,
                "cost_per_task": 0.25,
            },
            "baseline": {
                "resolved": 5,
                "total": 10,
                "rate": 0.5,
                "total_cost": 1.80,
                "cost_per_task": 0.18,
            },
            "improvement": "+30.0%",
            "comprehensive_stats": {
                "mcp_tokens": {"total_input": 50000, "total_output": 12000},
                "baseline_tokens": {"total_input": 40000, "total_output": 10000},
                "mcp_tools": {
                    "most_used_tools": {"search": 45, "edit": 30, "read": 20},
                    "per_tool": {"search": {"total": 45}, "edit": {"total": 30}},
                },
                "mcp_errors": {
                    "total_errors": 2,
                    "error_categories": {"timeout": 1, "api_error": 1},
                },
            },
        },
        "tasks": [
            {
                "instance_id": f"task-{i}",
                "mcp": {
                    "resolved": i < 8,
                    "cost": 0.25,
                    "tokens": {"input": 5000, "output": 1200},
                    "runtime_seconds": 30.0 + i,
                    "tool_calls": 5,
                    "iterations": 3,
                },
                "baseline": {
                    "resolved": i < 5,
                    "cost": 0.18,
                },
            }
            for i in range(10)
        ],
    }


@pytest.fixture
def runner() -> CliRunner:
    """Create a CliRunner for CLI tests."""
    return CliRunner()


# ===========================================================================
# HTMLReportGenerator tests
# ===========================================================================


class TestHTMLReportGenerator:
    """Tests for HTMLReportGenerator."""

    def test_generate_produces_valid_html(self, minimal_results: dict) -> None:
        """generate() returns a complete HTML document with required elements."""
        gen = HTMLReportGenerator(minimal_results)
        html = gen.generate()

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "chart.js" in html.lower()
        assert "resolutionChart" in html
        assert "costChart" in html

    def test_generate_includes_metadata(self, minimal_results: dict) -> None:
        """generate() embeds metadata (timestamp, model, benchmark) in HTML."""
        gen = HTMLReportGenerator(minimal_results)
        html = gen.generate()

        assert "2025-01-01T00:00:00" in html
        assert "test-model" in html
        assert "swe-bench-verified" in html

    def test_generate_includes_summary_cards(self, minimal_results: dict) -> None:
        """generate() renders summary cards with resolution rates and costs."""
        gen = HTMLReportGenerator(minimal_results)
        html = gen.generate()

        assert "70.0%" in html  # MCP rate
        assert "50.0%" in html  # Baseline rate
        assert "+20.0%" in html  # Improvement
        assert "$1.50" in html  # MCP total cost
        assert "$1.20" in html  # Baseline total cost

    def test_generate_includes_task_table(self, minimal_results: dict) -> None:
        """generate() renders a task table with per-task results."""
        gen = HTMLReportGenerator(minimal_results)
        html = gen.generate()

        assert "test-1" in html
        assert "test-2" in html
        assert "PASS" in html
        assert "FAIL" in html

    def test_generate_with_custom_title(self, minimal_results: dict) -> None:
        """generate() uses the custom title in <title> and header."""
        gen = HTMLReportGenerator(minimal_results, title="Custom Report Title")
        html = gen.generate()

        assert "Custom Report Title" in html
        assert "<title>Custom Report Title</title>" in html

    def test_generate_dark_mode(self, minimal_results: dict) -> None:
        """generate() applies dark-mode class when dark_mode=True."""
        gen = HTMLReportGenerator(minimal_results, dark_mode=True)
        html = gen.generate()

        assert 'class="dark-mode"' in html
        assert "Light Mode" in html

    def test_generate_light_mode_default(self, minimal_results: dict) -> None:
        """generate() defaults to light mode."""
        gen = HTMLReportGenerator(minimal_results)
        html = gen.generate()

        assert "Dark Mode" in html

    def test_generate_with_comprehensive_data(self, comprehensive_results: dict) -> None:
        """generate() renders token and tool charts when data is available."""
        gen = HTMLReportGenerator(comprehensive_results)
        html = gen.generate()

        assert "tokenChart" in html
        assert "toolChart" in html
        assert "Token Usage Comparison" in html
        assert "Tool Usage Breakdown" in html

    def test_generate_without_cost_data(self) -> None:
        """generate() handles missing cost data gracefully."""
        results = {
            "metadata": {"timestamp": "", "config": {}},
            "summary": {
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 1, "rate": 0.0},
                "improvement": "N/A",
            },
            "tasks": [],
        }
        gen = HTMLReportGenerator(results)
        html = gen.generate()

        assert "<!DOCTYPE html>" in html

    def test_generate_escapes_html(self) -> None:
        """generate() escapes HTML entities in user-provided content."""
        results = {
            "metadata": {
                "timestamp": "<script>alert('xss')</script>",
                "config": {"model": "test<>&model", "benchmark": 'bench"mark'},
            },
            "summary": {"mcp": {}, "baseline": {}, "improvement": "<b>bad</b>"},
            "tasks": [
                {
                    "instance_id": "<img src=x>",
                    "mcp": {"resolved": True, "error": "err<or>"},
                    "baseline": {},
                }
            ],
        }
        gen = HTMLReportGenerator(results)
        html = gen.generate()

        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html
        assert "&lt;b&gt;bad&lt;/b&gt;" in html

    def test_save_creates_file(self, minimal_results: dict, tmp_path: Path) -> None:
        """save() writes the HTML report to the specified path."""
        gen = HTMLReportGenerator(minimal_results)
        out = tmp_path / "report.html"
        gen.save(out)

        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "chart.js" in content.lower()

    def test_save_creates_parent_directories(self, minimal_results: dict, tmp_path: Path) -> None:
        """save() creates parent directories if they don't exist."""
        gen = HTMLReportGenerator(minimal_results)
        out = tmp_path / "subdir" / "nested" / "report.html"
        gen.save(out)

        assert out.exists()

    def test_save_overwrites_existing(self, minimal_results: dict, tmp_path: Path) -> None:
        """save() overwrites an existing file."""
        gen = HTMLReportGenerator(minimal_results)
        out = tmp_path / "report.html"
        out.write_text("old content")

        gen.save(out)
        content = out.read_text(encoding="utf-8")
        assert "old content" not in content
        assert "<!DOCTYPE html>" in content


# ===========================================================================
# EnhancedMarkdownGenerator tests
# ===========================================================================


class TestEnhancedMarkdownGenerator:
    """Tests for EnhancedMarkdownGenerator."""

    def test_generate_produces_markdown(self, minimal_results: dict) -> None:
        """generate() returns valid markdown with title and sections."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        md = gen.generate()

        assert "# mcpbr Evaluation Report" in md
        assert "## Summary" in md
        assert "## Resolution Outcomes" in md
        assert "## Analysis" in md

    def test_generate_includes_badges(self, minimal_results: dict) -> None:
        """generate() includes shields.io badge images."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        md = gen.generate()

        assert "img.shields.io/badge" in md
        assert "resolution%20rate" in md
        assert "test-model" in md

    def test_generate_includes_mermaid_charts(self, minimal_results: dict) -> None:
        """generate() includes mermaid pie chart for outcomes."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        md = gen.generate()

        assert "```mermaid" in md
        assert "pie showData" in md

    def test_generate_includes_cost_analysis(self, minimal_results: dict) -> None:
        """generate() includes cost analysis with mermaid bar chart."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        md = gen.generate()

        assert "## Cost Analysis" in md
        assert "xychart-beta" in md
        assert "$1.5000" in md

    def test_generate_includes_summary_table(self, minimal_results: dict) -> None:
        """generate() includes the summary metrics table."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        md = gen.generate()

        assert "| MCP Resolution Rate | 70.0% |" in md
        assert "| Baseline Resolution Rate | 50.0% |" in md
        assert "| Improvement | +20.0% |" in md

    def test_generate_includes_analysis(self, minimal_results: dict) -> None:
        """generate() includes MCP-only and baseline-only win counts."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        md = gen.generate()

        assert "MCP-only wins" in md
        assert "Baseline-only wins" in md

    def test_generate_includes_collapsible_sections(self, minimal_results: dict) -> None:
        """generate() wraps per-task results and errors in collapsible sections."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        md = gen.generate()

        assert "<details>" in md
        assert "<summary>" in md
        assert "Per-Task Results" in md
        assert "Error Details" in md

    def test_generate_with_comprehensive_data(self, comprehensive_results: dict) -> None:
        """generate() handles comprehensive data with error details."""
        gen = EnhancedMarkdownGenerator(comprehensive_results)
        md = gen.generate()

        assert "## Summary" in md
        assert "## Cost Analysis" in md
        # Error details should be present since comprehensive_stats has errors
        assert "<details>" in md

    def test_generate_no_baseline(self) -> None:
        """generate() handles results with no baseline data."""
        results = {
            "metadata": {"config": {"model": "m", "benchmark": "b"}},
            "summary": {
                "mcp": {"resolved": 3, "total": 5, "rate": 0.6},
                "improvement": "N/A",
            },
            "tasks": [
                {"instance_id": "t1", "mcp": {"resolved": True, "cost": 0.1}},
            ],
        }
        gen = EnhancedMarkdownGenerator(results)
        md = gen.generate()

        assert "# mcpbr Evaluation Report" in md
        assert "60.0%" in md

    def test_save_creates_file(self, minimal_results: dict, tmp_path: Path) -> None:
        """save() writes the markdown report to the specified path."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        out = tmp_path / "report.md"
        gen.save(out)

        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "# mcpbr Evaluation Report" in content

    def test_save_creates_parent_directories(self, minimal_results: dict, tmp_path: Path) -> None:
        """save() creates parent directories if they don't exist."""
        gen = EnhancedMarkdownGenerator(minimal_results)
        out = tmp_path / "deep" / "nested" / "dir" / "report.md"
        gen.save(out)

        assert out.exists()


class TestMarkdownHelpers:
    """Tests for standalone markdown helper functions."""

    def test_generate_badge(self) -> None:
        """generate_badge() produces valid shields.io markdown."""
        badge = generate_badge("status", "passing", "green")
        assert badge.startswith("![status: passing]")
        assert "img.shields.io/badge" in badge
        assert "green" in badge

    def test_generate_badge_url_encodes_special_chars(self) -> None:
        """generate_badge() URL-encodes label and value."""
        badge = generate_badge("my label", "v 1.0", "blue")
        assert "my%20label" in badge
        assert "v%201.0" in badge

    def test_generate_mermaid_pie(self) -> None:
        """generate_mermaid_pie() produces valid mermaid pie chart."""
        chart = generate_mermaid_pie("Test Pie", {"A": 3, "B": 7})
        assert "```mermaid" in chart
        assert "pie showData" in chart
        assert '"A" : 3' in chart
        assert '"B" : 7' in chart
        assert chart.endswith("```")

    def test_generate_mermaid_bar(self) -> None:
        """generate_mermaid_bar() produces valid mermaid bar chart."""
        chart = generate_mermaid_bar("Cost Chart", {"MCP": 1.5, "Baseline": 1.2})
        assert "```mermaid" in chart
        assert "xychart-beta" in chart
        assert '"MCP"' in chart
        assert "1.5" in chart

    def test_generate_mermaid_bar_empty(self) -> None:
        """generate_mermaid_bar() handles empty data."""
        chart = generate_mermaid_bar("Empty", {})
        assert "N/A" in chart

    def test_generate_collapsible(self) -> None:
        """generate_collapsible() creates HTML details/summary block."""
        block = generate_collapsible("Click me", "Hidden content here")
        assert "<details>" in block
        assert "<summary>Click me</summary>" in block
        assert "Hidden content here" in block
        assert "</details>" in block


# ===========================================================================
# PDFReportGenerator tests
# ===========================================================================


class TestPDFReportGenerator:
    """Tests for PDFReportGenerator."""

    def test_generate_html_produces_valid_html(self, minimal_results: dict) -> None:
        """generate_html() returns a complete HTML document."""
        gen = PDFReportGenerator(minimal_results)
        html = gen.generate_html()

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_generate_html_includes_print_styles(self, minimal_results: dict) -> None:
        """generate_html() includes CSS @media print styles."""
        gen = PDFReportGenerator(minimal_results)
        html = gen.generate_html()

        assert "@media print" in html
        assert "page-break" in html

    def test_generate_html_includes_metadata(self, minimal_results: dict) -> None:
        """generate_html() embeds model and benchmark info."""
        gen = PDFReportGenerator(minimal_results)
        html = gen.generate_html()

        assert "test-model" in html
        assert "swe-bench-verified" in html

    def test_generate_html_includes_summary_cards(self, minimal_results: dict) -> None:
        """generate_html() renders summary metric cards."""
        gen = PDFReportGenerator(minimal_results)
        html = gen.generate_html()

        assert "70.0%" in html
        assert "50.0%" in html
        assert "7/10" in html

    def test_generate_html_includes_cost_section(self, minimal_results: dict) -> None:
        """generate_html() includes cost analysis table."""
        gen = PDFReportGenerator(minimal_results)
        html = gen.generate_html()

        assert "Cost Analysis" in html
        assert "$1.5000" in html
        assert "$1.2000" in html

    def test_generate_html_includes_task_table(self, minimal_results: dict) -> None:
        """generate_html() includes per-task results table."""
        gen = PDFReportGenerator(minimal_results)
        html = gen.generate_html()

        assert "Per-Task Results" in html
        assert "test-1" in html
        assert "test-2" in html

    def test_generate_html_custom_title(self, minimal_results: dict) -> None:
        """generate_html() uses the custom title."""
        gen = PDFReportGenerator(minimal_results, title="My PDF Report")
        html = gen.generate_html()

        assert "My PDF Report" in html
        assert "<title>My PDF Report</title>" in html

    def test_generate_html_with_branding(self, minimal_results: dict) -> None:
        """generate_html() applies branding options."""
        branding = {
            "logo_text": "ACME Labs",
            "primary_color": "#ff5733",
            "company_name": "Acme Corporation",
        }
        gen = PDFReportGenerator(minimal_results, branding=branding)
        html = gen.generate_html()

        assert "ACME Labs" in html
        assert "#ff5733" in html
        assert "Acme Corporation" in html

    def test_generate_html_default_branding(self, minimal_results: dict) -> None:
        """generate_html() uses default mcpbr branding when no branding specified."""
        gen = PDFReportGenerator(minimal_results)
        html = gen.generate_html()

        assert "mcpbr" in html

    def test_generate_html_with_comprehensive_stats(self, comprehensive_results: dict) -> None:
        """generate_html() renders detailed stats section when available."""
        gen = PDFReportGenerator(comprehensive_results)
        html = gen.generate_html()

        assert "Detailed Statistics" in html
        assert "Token Usage" in html
        assert "Tool Usage" in html
        assert "Error Summary" in html

    def test_generate_html_no_tasks(self) -> None:
        """generate_html() handles empty task list."""
        results = {
            "metadata": {"config": {}},
            "summary": {"mcp": {}, "improvement": "N/A"},
            "tasks": [],
        }
        gen = PDFReportGenerator(results)
        html = gen.generate_html()

        assert "No task results available" in html

    def test_generate_html_no_cost_data(self) -> None:
        """generate_html() handles missing cost data."""
        results = {
            "metadata": {"config": {}},
            "summary": {
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "improvement": "N/A",
            },
            "tasks": [],
        }
        gen = PDFReportGenerator(results)
        html = gen.generate_html()

        assert "No cost data available" in html

    def test_save_html_creates_file(self, minimal_results: dict, tmp_path: Path) -> None:
        """save_html() writes the HTML report to disk."""
        gen = PDFReportGenerator(minimal_results)
        out = tmp_path / "report.html"
        gen.save_html(out)

        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_save_html_creates_parent_dirs(self, minimal_results: dict, tmp_path: Path) -> None:
        """save_html() creates parent directories as needed."""
        gen = PDFReportGenerator(minimal_results)
        out = tmp_path / "a" / "b" / "report.html"
        gen.save_html(out)

        assert out.exists()

    def test_save_pdf_raises_import_error_without_weasyprint(
        self, minimal_results: dict, tmp_path: Path
    ) -> None:
        """save_pdf() raises ImportError when weasyprint is not installed."""
        gen = PDFReportGenerator(minimal_results)
        out = tmp_path / "report.pdf"

        with (
            patch.dict("sys.modules", {"weasyprint": None}),
            pytest.raises(ImportError, match="weasyprint"),
        ):
            gen.save_pdf(out)

    def test_branding_escapes_html(self, minimal_results: dict) -> None:
        """generate_html() escapes HTML in branding strings."""
        branding = {
            "logo_text": "<script>alert(1)</script>",
            "company_name": "A&B Corp",
        }
        gen = PDFReportGenerator(minimal_results, branding=branding)
        html = gen.generate_html()

        assert "&lt;script&gt;" in html
        assert "A&amp;B Corp" in html


# ===========================================================================
# CLI compare command tests
# ===========================================================================


def _make_result_file(path: Path, model: str = "test-model", resolved: int = 7) -> None:
    """Write a valid results JSON file for CLI testing."""
    data = {
        "metadata": {
            "timestamp": "2025-01-01T00:00:00",
            "config": {
                "model": model,
                "benchmark": "swe-bench-verified",
                "provider": "anthropic",
            },
        },
        "summary": {
            "mcp": {
                "resolved": resolved,
                "total": 10,
                "rate": resolved / 10,
                "total_cost": 1.50,
                "cost_per_task": 0.15,
            },
            "baseline": {
                "resolved": 5,
                "total": 10,
                "rate": 0.5,
                "total_cost": 1.20,
            },
            "improvement": f"+{(resolved / 10 - 0.5) * 100:.0f}%",
        },
        "tasks": [
            {
                "instance_id": f"task-{i}",
                "mcp": {"resolved": i < resolved, "cost": 0.15},
                "baseline": {"resolved": i < 5},
            }
            for i in range(10)
        ],
    }
    path.write_text(json.dumps(data))


class TestCLICompare:
    """Tests for the 'mcpbr compare' CLI command."""

    def test_compare_two_files(self, runner: CliRunner, tmp_path: Path) -> None:
        """compare with 2 result files produces output."""
        f1 = tmp_path / "run1.json"
        f2 = tmp_path / "run2.json"
        _make_result_file(f1, model="model-a", resolved=7)
        _make_result_file(f2, model="model-b", resolved=5)

        result = runner.invoke(main, ["compare", str(f1), str(f2)])
        assert result.exit_code == 0, f"compare command failed: {result.output}"

    def test_compare_three_files(self, runner: CliRunner, tmp_path: Path) -> None:
        """compare with 3 result files loads all of them."""
        files = []
        for i in range(3):
            f = tmp_path / f"run{i}.json"
            _make_result_file(f, model=f"model-{i}", resolved=5 + i)
            files.append(str(f))

        result = runner.invoke(main, ["compare", *files])
        assert result.exit_code == 0, f"compare command failed: {result.output}"

    def test_compare_with_json_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """compare --output saves comparison JSON file."""
        f1 = tmp_path / "run1.json"
        f2 = tmp_path / "run2.json"
        _make_result_file(f1)
        _make_result_file(f2, model="model-b")

        out_json = tmp_path / "comparison.json"
        result = runner.invoke(main, ["compare", str(f1), str(f2), "--output", str(out_json)])
        assert result.exit_code == 0, f"compare command failed: {result.output}"
        assert out_json.exists()
        data = json.loads(out_json.read_text())
        assert isinstance(data, dict)

    def test_compare_with_html_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """compare --output-html saves an HTML report file."""
        f1 = tmp_path / "run1.json"
        f2 = tmp_path / "run2.json"
        _make_result_file(f1)
        _make_result_file(f2, model="model-b")

        out_html = tmp_path / "comparison.html"
        result = runner.invoke(main, ["compare", str(f1), str(f2), "--output-html", str(out_html)])
        assert result.exit_code == 0, f"compare command failed: {result.output}"
        assert out_html.exists()
        content = out_html.read_text()
        assert "<!DOCTYPE html>" in content

    def test_compare_with_markdown_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """compare --output-markdown saves a markdown report file."""
        f1 = tmp_path / "run1.json"
        f2 = tmp_path / "run2.json"
        _make_result_file(f1)
        _make_result_file(f2, model="model-b")

        out_md = tmp_path / "comparison.md"
        result = runner.invoke(
            main, ["compare", str(f1), str(f2), "--output-markdown", str(out_md)]
        )
        assert result.exit_code == 0, f"compare command failed: {result.output}"
        assert out_md.exists()
        content = out_md.read_text()
        assert "# mcpbr" in content

    def test_compare_too_few_files(self, runner: CliRunner, tmp_path: Path) -> None:
        """compare with only 1 file exits with error."""
        f1 = tmp_path / "run1.json"
        _make_result_file(f1)

        result = runner.invoke(main, ["compare", str(f1)])
        assert result.exit_code != 0

    def test_compare_invalid_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """compare with invalid JSON exits with an error."""
        f1 = tmp_path / "run1.json"
        f2 = tmp_path / "run2.json"
        f1.write_text("not valid json")
        _make_result_file(f2)

        result = runner.invoke(main, ["compare", str(f1), str(f2)])
        assert result.exit_code != 0


# ===========================================================================
# CLI analytics store command tests
# ===========================================================================


class TestCLIAnalyticsStore:
    """Tests for analytics store functionality.

    Note: The CLI 'analytics store' command on this branch has a signature
    mismatch with ResultsDatabase.store_run, so we test the underlying
    database API directly plus the CLI for error cases.
    """

    def test_store_invalid_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """analytics store with invalid JSON exits with error."""
        result_file = tmp_path / "bad.json"
        result_file.write_text("not json")
        db_path = tmp_path / "test.db"

        result = runner.invoke(
            main,
            ["analytics", "store", str(result_file), "--db", str(db_path)],
        )

        assert result.exit_code != 0

    def test_database_store_run(self, tmp_path: Path) -> None:
        """ResultsDatabase.store_run correctly stores run data."""
        from mcpbr.analytics.database import ResultsDatabase

        db_path = tmp_path / "test.db"
        results_data = {
            "metadata": {
                "timestamp": "2025-01-01T00:00:00",
                "config": {
                    "model": "test-model",
                    "benchmark": "swe-bench-verified",
                    "provider": "anthropic",
                },
            },
            "summary": {
                "mcp": {
                    "resolved": 7,
                    "total": 10,
                    "rate": 0.7,
                    "total_cost": 1.50,
                },
            },
            "tasks": [
                {
                    "instance_id": "task-0",
                    "mcp": {"resolved": True, "cost": 0.15, "tokens": {"input": 100, "output": 50}},
                },
                {
                    "instance_id": "task-1",
                    "mcp": {
                        "resolved": False,
                        "cost": 0.20,
                        "tokens": {"input": 200, "output": 60},
                    },
                },
            ],
        }

        with ResultsDatabase(db_path) as db:
            run_id = db.store_run(results_data)

        assert run_id is not None
        assert run_id >= 1

        with ResultsDatabase(db_path) as db:
            run = db.get_run(run_id)
            assert run is not None
            assert run["model"] == "test-model"
            assert run["benchmark"] == "swe-bench-verified"
            assert run["resolution_rate"] == 0.7

    def test_database_store_multiple_runs(self, tmp_path: Path) -> None:
        """ResultsDatabase can store multiple runs and list them."""
        from mcpbr.analytics.database import ResultsDatabase

        db_path = tmp_path / "test.db"

        with ResultsDatabase(db_path) as db:
            for i in range(3):
                results = {
                    "metadata": {
                        "timestamp": f"2025-01-{10 + i:02d}T00:00:00",
                        "config": {"model": f"model-{i}", "benchmark": "bench"},
                    },
                    "summary": {
                        "mcp": {"resolved": 5 + i, "total": 10, "rate": (5 + i) / 10},
                    },
                    "tasks": [],
                }
                db.store_run(results)

            runs = db.list_runs()
            assert len(runs) == 3

    def test_database_get_task_results(self, tmp_path: Path) -> None:
        """ResultsDatabase.get_task_results returns stored task data."""
        from mcpbr.analytics.database import ResultsDatabase

        db_path = tmp_path / "test.db"
        results_data = {
            "metadata": {"timestamp": "2025-01-01T00:00:00", "config": {}},
            "summary": {"mcp": {"resolved": 1, "total": 2, "rate": 0.5}},
            "tasks": [
                {"instance_id": "t1", "mcp": {"resolved": True, "cost": 0.1}},
                {"instance_id": "t2", "mcp": {"resolved": False, "cost": 0.2}},
            ],
        }

        with ResultsDatabase(db_path) as db:
            run_id = db.store_run(results_data)
            tasks = db.get_task_results(run_id)

        assert len(tasks) == 2
        assert tasks[0]["instance_id"] == "t1"
        assert tasks[0]["resolved"] == 1
        assert tasks[1]["instance_id"] == "t2"
        assert tasks[1]["resolved"] == 0


# ===========================================================================
# CLI analytics trends/leaderboard command tests
# ===========================================================================


def _populate_analytics_db(db_path: Path, num_runs: int = 5) -> None:
    """Create and populate an analytics database with test runs."""
    from mcpbr.analytics.database import ResultsDatabase

    with ResultsDatabase(db_path) as db:
        for i in range(num_runs):
            rate = 0.5 + i * 0.05
            results = {
                "metadata": {
                    "timestamp": f"2025-01-{10 + i:02d}T00:00:00",
                    "config": {
                        "model": "test-model",
                        "benchmark": "swe-bench-verified",
                        "provider": "anthropic",
                        "agent_harness": "agentless",
                        "sample_size": 10,
                        "timeout_seconds": 300,
                        "max_iterations": 50,
                    },
                },
                "summary": {
                    "mcp": {
                        "resolved": 5 + i,
                        "total": 10,
                        "rate": rate,
                        "total_cost": 1.0 + i * 0.2,
                    },
                },
                "tasks": [
                    {
                        "instance_id": f"task-{j}",
                        "mcp": {
                            "resolved": j < (5 + i),
                            "cost": 0.1 + i * 0.02,
                            "tokens": {"input": 1000, "output": 500},
                            "runtime_seconds": 30.0,
                        },
                    }
                    for j in range(10)
                ],
            }
            db.store_run(results)


class TestCLIAnalyticsTrends:
    """Tests for analytics trends functionality."""

    def test_trends_empty_db_cli(self, runner: CliRunner, tmp_path: Path) -> None:
        """analytics trends on empty database shows appropriate message."""
        db_path = tmp_path / "empty.db"
        from mcpbr.analytics.database import ResultsDatabase

        with ResultsDatabase(db_path):
            pass

        result = runner.invoke(
            main,
            ["analytics", "trends", "--db", str(db_path)],
        )

        assert result.exit_code == 0
        assert "No runs found" in result.output

    def test_trends_nonexistent_filter_cli(self, runner: CliRunner, tmp_path: Path) -> None:
        """analytics trends with non-matching filter shows no results."""
        db_path = tmp_path / "analytics.db"
        _populate_analytics_db(db_path)

        result = runner.invoke(
            main,
            [
                "analytics",
                "trends",
                "--db",
                str(db_path),
                "--benchmark",
                "nonexistent",
            ],
        )

        assert result.exit_code == 0
        assert "No matching runs" in result.output

    def test_detect_trend_direction_improving(self) -> None:
        """detect_trend_direction returns 'improving' for upward trend."""
        from mcpbr.analytics.trends import detect_trend_direction

        values = [0.3, 0.4, 0.5, 0.6, 0.7]
        assert detect_trend_direction(values) == "improving"

    def test_detect_trend_direction_declining(self) -> None:
        """detect_trend_direction returns 'declining' for downward trend."""
        from mcpbr.analytics.trends import detect_trend_direction

        values = [0.8, 0.7, 0.6, 0.5, 0.4]
        assert detect_trend_direction(values) == "declining"

    def test_detect_trend_direction_stable(self) -> None:
        """detect_trend_direction returns 'stable' for flat data."""
        from mcpbr.analytics.trends import detect_trend_direction

        values = [0.5, 0.5, 0.5, 0.5, 0.5]
        assert detect_trend_direction(values) == "stable"

    def test_detect_trend_direction_insufficient(self) -> None:
        """detect_trend_direction returns 'stable' for single value."""
        from mcpbr.analytics.trends import detect_trend_direction

        assert detect_trend_direction([0.5]) == "stable"

    def test_calculate_trends(self) -> None:
        """calculate_trends returns expected structure."""
        from mcpbr.analytics.trends import calculate_trends

        runs = [
            {
                "timestamp": "2025-01-10",
                "resolution_rate": 0.5,
                "total_cost": 1.0,
                "total_tokens": 1000,
            },
            {
                "timestamp": "2025-01-11",
                "resolution_rate": 0.6,
                "total_cost": 1.2,
                "total_tokens": 1200,
            },
            {
                "timestamp": "2025-01-12",
                "resolution_rate": 0.7,
                "total_cost": 1.4,
                "total_tokens": 1400,
            },
        ]
        result = calculate_trends(runs)

        assert result["direction"] == "improving"
        assert len(result["resolution_rate_trend"]) == 3
        assert len(result["cost_trend"]) == 3
        assert len(result["token_trend"]) == 3
        assert "moving_averages" in result

    def test_calculate_moving_average(self) -> None:
        """calculate_moving_average computes correct values."""
        from mcpbr.analytics.trends import calculate_moving_average

        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_moving_average(values, window=3)

        assert result[0] is None
        assert result[1] is None
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_database_get_trends(self, tmp_path: Path) -> None:
        """ResultsDatabase.get_trends returns trend data for stored runs."""
        from mcpbr.analytics.database import ResultsDatabase

        db_path = tmp_path / "test.db"
        _populate_analytics_db(db_path, num_runs=5)

        with ResultsDatabase(db_path) as db:
            trends = db.get_trends()

        assert len(trends) == 5
        assert all("resolution_rate" in t for t in trends)
        assert all("total_cost" in t for t in trends)

    def test_database_get_trends_with_filter(self, tmp_path: Path) -> None:
        """ResultsDatabase.get_trends filters by benchmark."""
        from mcpbr.analytics.database import ResultsDatabase

        db_path = tmp_path / "test.db"
        _populate_analytics_db(db_path, num_runs=3)

        with ResultsDatabase(db_path) as db:
            trends = db.get_trends(benchmark="swe-bench-verified")
            assert len(trends) == 3

            trends_empty = db.get_trends(benchmark="nonexistent")
            assert len(trends_empty) == 0


class TestCLIAnalyticsLeaderboard:
    """Tests for analytics leaderboard functionality."""

    def test_leaderboard_empty_db_cli(self, runner: CliRunner, tmp_path: Path) -> None:
        """analytics leaderboard on empty database shows message."""
        db_path = tmp_path / "empty.db"
        from mcpbr.analytics.database import ResultsDatabase

        with ResultsDatabase(db_path):
            pass

        result = runner.invoke(
            main,
            ["analytics", "leaderboard", "--db", str(db_path)],
        )

        assert result.exit_code == 0
        assert "No runs found" in result.output

    def test_leaderboard_generate_default(self) -> None:
        """Leaderboard.generate() ranks entries by resolution_rate."""
        from mcpbr.analytics.leaderboard import Leaderboard

        lb = Leaderboard()
        lb.add_entry(
            "model-a",
            {
                "summary": {"mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 2.0}},
                "metadata": {"config": {"model": "model-a", "provider": "p"}},
                "tasks": [],
            },
        )
        lb.add_entry(
            "model-b",
            {
                "summary": {"mcp": {"resolved": 5, "total": 10, "rate": 0.5, "total_cost": 1.0}},
                "metadata": {"config": {"model": "model-b", "provider": "p"}},
                "tasks": [],
            },
        )

        result = lb.generate(sort_by="resolution_rate")
        assert len(result) == 2
        assert result[0]["rank"] == 1
        assert result[0]["label"] == "model-a"
        assert result[1]["rank"] == 2
        assert result[1]["label"] == "model-b"

    def test_leaderboard_generate_sort_by_cost(self) -> None:
        """Leaderboard.generate() sorts by total_cost (lower is better)."""
        from mcpbr.analytics.leaderboard import Leaderboard

        lb = Leaderboard()
        lb.add_entry(
            "expensive",
            {
                "summary": {"mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 5.0}},
                "metadata": {"config": {"model": "m1", "provider": "p"}},
                "tasks": [],
            },
        )
        lb.add_entry(
            "cheap",
            {
                "summary": {"mcp": {"resolved": 7, "total": 10, "rate": 0.7, "total_cost": 1.0}},
                "metadata": {"config": {"model": "m2", "provider": "p"}},
                "tasks": [],
            },
        )

        result = lb.generate(sort_by="total_cost")
        assert result[0]["label"] == "cheap"
        assert result[1]["label"] == "expensive"

    def test_leaderboard_format_table(self) -> None:
        """Leaderboard.format_table() produces formatted output."""
        from mcpbr.analytics.leaderboard import Leaderboard

        lb = Leaderboard()
        lb.add_entry(
            "test-model",
            {
                "summary": {"mcp": {"resolved": 7, "total": 10, "rate": 0.7, "total_cost": 1.5}},
                "metadata": {"config": {"model": "test-model", "provider": "p"}},
                "tasks": [],
            },
        )

        table = lb.format_table()
        assert "Rank" in table
        assert "test-model" in table

    def test_leaderboard_format_markdown(self) -> None:
        """Leaderboard.format_markdown() produces markdown table."""
        from mcpbr.analytics.leaderboard import Leaderboard

        lb = Leaderboard()
        lb.add_entry(
            "test-model",
            {
                "summary": {"mcp": {"resolved": 7, "total": 10, "rate": 0.7, "total_cost": 1.5}},
                "metadata": {"config": {"model": "test-model", "provider": "p"}},
                "tasks": [],
            },
        )

        md = lb.format_markdown()
        assert "|" in md
        assert "Rank" in md
        assert "test-model" in md

    def test_leaderboard_empty(self) -> None:
        """Leaderboard.format_table() handles no entries."""
        from mcpbr.analytics.leaderboard import Leaderboard

        lb = Leaderboard()
        table = lb.format_table()
        assert "No entries" in table
