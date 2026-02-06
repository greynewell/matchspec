"""Tests for Prometheus metrics export."""

import tempfile
from pathlib import Path

from mcpbr.prometheus import export_metrics, format_metric


class TestFormatMetric:
    """format_metric() produces valid Prometheus exposition lines."""

    def test_basic_metric(self):
        line = format_metric("mcpbr_resolution_rate", 0.75)
        assert line == "mcpbr_resolution_rate 0.75"

    def test_metric_with_labels(self):
        line = format_metric(
            "mcpbr_resolution_rate",
            0.75,
            labels={"benchmark": "humaneval", "model": "claude-sonnet-4-5"},
        )
        assert "mcpbr_resolution_rate{" in line
        assert 'benchmark="humaneval"' in line
        assert 'model="claude-sonnet-4-5"' in line
        assert "} 0.75" in line

    def test_metric_with_help(self):
        line = format_metric("mcpbr_total_cost", 12.5, help_text="Total cost in USD")
        assert "# HELP mcpbr_total_cost Total cost in USD" in line
        assert "mcpbr_total_cost 12.5" in line

    def test_metric_with_type(self):
        line = format_metric("mcpbr_total_cost", 12.5, metric_type="gauge")
        assert "# TYPE mcpbr_total_cost gauge" in line

    def test_integer_value(self):
        line = format_metric("mcpbr_tasks_total", 42)
        assert "mcpbr_tasks_total 42" in line


class TestExportMetrics:
    """export_metrics() includes resolution_rate, cost, runtime with labels."""

    def test_includes_resolution_rate(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {
                    "resolved": 8,
                    "total": 10,
                    "rate": 0.8,
                    "total_cost": 12.50,
                },
                "baseline": {
                    "resolved": 3,
                    "total": 10,
                    "rate": 0.3,
                    "total_cost": 5.00,
                },
            },
        }
        output = export_metrics(results)
        assert "mcpbr_resolution_rate" in output
        assert "0.8" in output

    def test_includes_cost(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        output = export_metrics(results)
        assert "mcpbr_total_cost" in output
        assert "12.5" in output

    def test_includes_task_counts(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        output = export_metrics(results)
        assert "mcpbr_tasks_total" in output
        assert "mcpbr_tasks_resolved" in output

    def test_file_export(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "metrics.prom"
            export_metrics(results, output_path=path)
            assert path.exists()
            content = path.read_text()
            assert "mcpbr_resolution_rate" in content

    def test_labels_include_benchmark_and_model(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        output = export_metrics(results)
        assert 'benchmark="humaneval"' in output
        assert 'model="claude-sonnet-4-5"' in output
