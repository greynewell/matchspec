"""Tests for reporting utilities."""

import csv
import json
import tempfile
from pathlib import Path

import pytest
import yaml

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import (
    save_csv_results,
    save_json_results,
    save_markdown_report,
    save_yaml_results,
)


@pytest.fixture
def sample_results() -> EvaluationResults:
    """Create sample evaluation results for testing."""
    return EvaluationResults(
        metadata={
            "timestamp": "2026-01-20T12:00:00Z",
            "config": {
                "model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic",
                "agent_harness": "claude-code",
                "benchmark": "swe-bench",
                "dataset": "SWE-bench/SWE-bench_Lite",
                "sample_size": 2,
                "timeout_seconds": 300,
                "max_iterations": 10,
                "cybergym_level": None,
            },
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "args_note": "{workdir} is replaced with task repository path at runtime",
            },
        },
        summary={
            "mcp": {"resolved": 1, "total": 2, "rate": 0.5},
            "baseline": {"resolved": 0, "total": 2, "rate": 0.0},
            "improvement": "+100.0%",
        },
        tasks=[
            TaskResult(
                instance_id="test-task-1",
                mcp={
                    "resolved": True,
                    "patch_applied": True,
                    "patch_generated": True,
                    "tokens": {"input": 1000, "output": 500},
                    "iterations": 3,
                    "tool_calls": 10,
                    "tool_usage": {"read_file": 5, "write_file": 3, "bash": 2},
                    "fail_to_pass": {"passed": 2, "total": 2},
                    "pass_to_pass": {"passed": 5, "total": 5},
                    "error": "",
                    "eval_error": "",
                },
                baseline={
                    "resolved": False,
                    "patch_applied": False,
                    "patch_generated": True,
                    "tokens": {"input": 800, "output": 400},
                    "iterations": 1,
                    "tool_calls": 0,
                    "error": "",
                    "eval_error": "",
                },
            ),
            TaskResult(
                instance_id="test-task-2",
                mcp={
                    "resolved": False,
                    "patch_applied": False,
                    "patch_generated": False,
                    "tokens": {"input": 500, "output": 200},
                    "iterations": 5,
                    "tool_calls": 15,
                    "error": "Timeout",
                },
                baseline={
                    "resolved": False,
                    "patch_applied": False,
                    "patch_generated": False,
                    "tokens": {"input": 400, "output": 150},
                    "iterations": 1,
                    "tool_calls": 0,
                    "error": "Parse error",
                },
            ),
        ],
    )


class TestSaveYamlResults:
    """Tests for save_yaml_results function."""

    def test_saves_valid_yaml(self, sample_results: EvaluationResults) -> None:
        """Test that YAML output is valid and contains expected data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yaml"
            save_yaml_results(sample_results, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                data = yaml.safe_load(f)

            assert "metadata" in data
            assert "summary" in data
            assert "tasks" in data
            assert len(data["tasks"]) == 2
            assert data["tasks"][0]["instance_id"] == "test-task-1"
            assert data["tasks"][0]["mcp"]["resolved"] is True
            assert data["tasks"][0]["baseline"]["resolved"] is False

    def test_creates_parent_directories(self, sample_results: EvaluationResults) -> None:
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "nested" / "results.yaml"
            save_yaml_results(sample_results, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_yaml_is_human_readable(self, sample_results: EvaluationResults) -> None:
        """Test that YAML output is properly formatted and human-readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yaml"
            save_yaml_results(sample_results, output_path)

            content = output_path.read_text()

            # Check for human-readable formatting (not flow style)
            assert "metadata:" in content
            assert "summary:" in content
            assert "tasks:" in content
            assert "instance_id:" in content

            # Should not use flow style (inline braces)
            assert "{" not in content or content.count("{") < 5  # Allow minimal braces

    def test_yaml_preserves_order(self, sample_results: EvaluationResults) -> None:
        """Test that YAML preserves the expected order of fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yaml"
            save_yaml_results(sample_results, output_path)

            content = output_path.read_text()
            lines = content.split("\n")

            # Find indices of major sections
            metadata_idx = next(i for i, line in enumerate(lines) if line.startswith("metadata:"))
            summary_idx = next(i for i, line in enumerate(lines) if line.startswith("summary:"))
            tasks_idx = next(i for i, line in enumerate(lines) if line.startswith("tasks:"))

            # Check that sections appear in expected order
            assert metadata_idx < summary_idx < tasks_idx

    def test_yaml_json_equivalence(self, sample_results: EvaluationResults) -> None:
        """Test that YAML and JSON outputs contain the same data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "results.json"
            yaml_path = Path(tmpdir) / "results.yaml"

            save_json_results(sample_results, json_path)
            save_yaml_results(sample_results, yaml_path)

            with open(json_path) as f:
                json_data = json.load(f)

            with open(yaml_path) as f:
                yaml_data = yaml.safe_load(f)

            # Both should contain the same data
            assert json_data == yaml_data

    def test_handles_unicode(self, sample_results: EvaluationResults) -> None:
        """Test that YAML properly handles Unicode characters."""
        # Add unicode to results
        sample_results.tasks[0].instance_id = "test-task-🔥"
        sample_results.metadata["config"]["note"] = "测试 unicode"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yaml"
            save_yaml_results(sample_results, output_path)

            with open(output_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            assert data["tasks"][0]["instance_id"] == "test-task-🔥"
            assert data["metadata"]["config"]["note"] == "测试 unicode"

    def test_handles_none_values(self) -> None:
        """Test that YAML properly handles None values."""
        results = EvaluationResults(
            metadata={"timestamp": "2026-01-20T12:00:00Z", "config": {}},
            summary={"mcp": {"resolved": 0, "total": 1, "rate": 0.0}},
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={"resolved": False, "error": None},
                    baseline=None,  # Baseline not run
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yaml"
            save_yaml_results(results, output_path)

            with open(output_path) as f:
                data = yaml.safe_load(f)

            # None values should be preserved
            assert data["tasks"][0]["mcp"]["error"] is None
            assert "baseline" not in data["tasks"][0]


@pytest.fixture
def partial_results() -> EvaluationResults:
    """Create evaluation results with missing MCP or baseline data."""
    return EvaluationResults(
        metadata={
            "timestamp": "2024-01-01T00:00:00Z",
            "config": {
                "model": "claude-sonnet-4-5-20250514",
                "provider": "anthropic",
                "agent_harness": "claude-code",
                "benchmark": "swe-bench",
                "dataset": "SWE-bench/SWE-bench_Lite",
                "sample_size": 2,
                "timeout_seconds": 300,
                "max_iterations": 10,
                "cybergym_level": None,
            },
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "args_note": "{workdir} is replaced with task repository path at runtime",
            },
        },
        summary={
            "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
            "baseline": {"resolved": 0, "total": 1, "rate": 0.0},
            "improvement": "+100.0%",
        },
        tasks=[
            TaskResult(
                instance_id="test-task-mcp-only",
                mcp={
                    "resolved": True,
                    "patch_applied": True,
                    "patch_generated": True,
                    "tokens": {"input": 1000, "output": 500},
                    "iterations": 3,
                    "tool_calls": 10,
                },
                baseline=None,
            ),
            TaskResult(
                instance_id="test-task-baseline-only",
                mcp=None,
                baseline={
                    "resolved": False,
                    "patch_applied": False,
                    "patch_generated": False,
                    "tokens": {"input": 400, "output": 150},
                    "iterations": 1,
                    "tool_calls": 0,
                },
            ),
        ],
    )


class TestCSVExport:
    """Tests for CSV export functionality."""

    def test_save_summary_csv(self, sample_results: EvaluationResults, tmp_path: Path) -> None:
        """Test saving summary CSV format."""
        csv_path = tmp_path / "results_summary.csv"
        save_csv_results(sample_results, csv_path, format="summary")

        assert csv_path.exists()

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

        # Check first task
        row1 = rows[0]
        assert row1["instance_id"] == "test-task-1"
        assert row1["mcp_resolved"] == "True"
        assert row1["baseline_resolved"] == "False"
        assert row1["mcp_tokens_in"] == "1000"
        assert row1["mcp_tokens_out"] == "500"
        assert row1["baseline_tokens_in"] == "800"
        assert row1["baseline_tokens_out"] == "400"
        assert row1["mcp_iterations"] == "3"
        assert row1["baseline_iterations"] == "1"
        assert row1["mcp_tool_calls"] == "10"
        assert row1["baseline_tool_calls"] == "0"
        assert row1["mcp_patch_generated"] == "True"
        assert row1["baseline_patch_generated"] == "True"
        assert row1["mcp_error"] == ""
        assert row1["baseline_error"] == ""

        # Check second task
        row2 = rows[1]
        assert row2["instance_id"] == "test-task-2"
        assert row2["mcp_resolved"] == "False"
        assert row2["baseline_resolved"] == "False"
        assert row2["mcp_error"] == "Timeout"
        assert row2["baseline_error"] == "Parse error"

    def test_save_detailed_csv(self, sample_results: EvaluationResults, tmp_path: Path) -> None:
        """Test saving detailed CSV format."""
        csv_path = tmp_path / "results_detailed.csv"
        save_csv_results(sample_results, csv_path, format="detailed")

        assert csv_path.exists()

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

        # Check first task has additional fields
        row1 = rows[0]
        assert row1["instance_id"] == "test-task-1"
        assert row1["mcp_patch_applied"] == "True"
        assert row1["baseline_patch_applied"] == "False"
        assert row1["mcp_fail_to_pass_passed"] == "2"
        assert row1["mcp_fail_to_pass_total"] == "2"
        assert row1["mcp_pass_to_pass_passed"] == "5"
        assert row1["mcp_pass_to_pass_total"] == "5"
        assert row1["mcp_eval_error"] == ""
        assert row1["baseline_eval_error"] == ""

        # Check tool_usage is JSON string
        tool_usage = json.loads(row1["mcp_tool_usage"])
        assert tool_usage["read_file"] == 5
        assert tool_usage["write_file"] == 3
        assert tool_usage["bash"] == 2

        # Check second task
        row2 = rows[1]
        assert row2["instance_id"] == "test-task-2"
        assert row2["mcp_fail_to_pass_passed"] == ""
        assert row2["mcp_tool_usage"] == ""

    def test_save_csv_with_partial_results(
        self, partial_results: EvaluationResults, tmp_path: Path
    ) -> None:
        """Test CSV export with missing MCP or baseline data."""
        csv_path = tmp_path / "results_partial.csv"
        save_csv_results(partial_results, csv_path, format="summary")

        assert csv_path.exists()

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

        # Check MCP-only task
        row1 = rows[0]
        assert row1["instance_id"] == "test-task-mcp-only"
        assert row1["mcp_resolved"] == "True"
        assert row1["baseline_resolved"] == ""
        assert row1["baseline_tokens_in"] == ""

        # Check baseline-only task
        row2 = rows[1]
        assert row2["instance_id"] == "test-task-baseline-only"
        assert row2["mcp_resolved"] == ""
        assert row2["baseline_resolved"] == "False"
        assert row2["mcp_tokens_in"] == ""

    def test_save_csv_creates_parent_dirs(
        self, sample_results: EvaluationResults, tmp_path: Path
    ) -> None:
        """Test that CSV export creates parent directories."""
        csv_path = tmp_path / "subdir" / "results.csv"
        save_csv_results(sample_results, csv_path, format="summary")

        assert csv_path.exists()
        assert csv_path.parent.exists()

    def test_save_csv_invalid_format(
        self, sample_results: EvaluationResults, tmp_path: Path
    ) -> None:
        """Test that invalid format raises ValueError."""
        csv_path = tmp_path / "results.csv"

        with pytest.raises(ValueError, match="Invalid CSV format"):
            save_csv_results(sample_results, csv_path, format="invalid")

    def test_csv_summary_headers(self, sample_results: EvaluationResults, tmp_path: Path) -> None:
        """Test that summary CSV has correct headers."""
        csv_path = tmp_path / "results.csv"
        save_csv_results(sample_results, csv_path, format="summary")

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

        expected_headers = [
            "instance_id",
            "mcp_resolved",
            "baseline_resolved",
            "mcp_tokens_in",
            "mcp_tokens_out",
            "baseline_tokens_in",
            "baseline_tokens_out",
            "mcp_iterations",
            "baseline_iterations",
            "mcp_tool_calls",
            "baseline_tool_calls",
            "mcp_patch_generated",
            "baseline_patch_generated",
            "mcp_error",
            "baseline_error",
        ]

        assert headers == expected_headers

    def test_csv_detailed_headers(self, sample_results: EvaluationResults, tmp_path: Path) -> None:
        """Test that detailed CSV has correct headers."""
        csv_path = tmp_path / "results.csv"
        save_csv_results(sample_results, csv_path, format="detailed")

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

        # Check that detailed has all the extra columns
        assert "mcp_patch_applied" in headers
        assert "baseline_patch_applied" in headers
        assert "mcp_fail_to_pass_passed" in headers
        assert "mcp_fail_to_pass_total" in headers
        assert "mcp_tool_usage" in headers
        assert "baseline_tool_usage" in headers


class TestJSONExport:
    """Tests for JSON export functionality."""

    def test_save_json_results(self, sample_results: EvaluationResults, tmp_path: Path) -> None:
        """Test saving JSON results."""
        json_path = tmp_path / "results.json"
        save_json_results(sample_results, json_path)

        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "summary" in data
        assert "tasks" in data
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["instance_id"] == "test-task-1"


class TestMarkdownExport:
    """Tests for Markdown export functionality."""

    def test_save_markdown_report(self, sample_results: EvaluationResults, tmp_path: Path) -> None:
        """Test saving Markdown report."""
        md_path = tmp_path / "report.md"
        save_markdown_report(sample_results, md_path)

        assert md_path.exists()

        content = md_path.read_text()
        assert "# SWE-bench MCP Evaluation Report" in content
        assert "## Summary" in content
        assert "## MCP Server Configuration" in content
        assert "## Per-Task Results" in content
        assert "test-task-1" in content
        assert "test-task-2" in content
