"""Tests for reporting utilities."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import save_json_results, save_markdown_report, save_yaml_results


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
                "dataset": "SWE-bench/SWE-bench_Lite",
                "sample_size": 2,
                "timeout_seconds": 300,
                "max_iterations": 10,
            },
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
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
                    "patch_generated": True,
                    "tokens": {"input": 100, "output": 500},
                    "iterations": 5,
                    "tool_calls": 10,
                    "tool_usage": {"Read": 3, "Write": 2, "Bash": 5},
                    "resolved": True,
                    "patch_applied": True,
                },
                baseline={
                    "patch_generated": True,
                    "tokens": {"input": 50, "output": 300},
                    "iterations": 3,
                    "tool_calls": 5,
                    "tool_usage": {"Read": 2, "Write": 1, "Bash": 2},
                    "resolved": False,
                    "patch_applied": True,
                },
            ),
            TaskResult(
                instance_id="test-task-2",
                mcp={
                    "patch_generated": False,
                    "tokens": {"input": 80, "output": 400},
                    "iterations": 4,
                    "tool_calls": 8,
                    "tool_usage": {"Read": 4, "Bash": 4},
                    "resolved": False,
                    "patch_applied": False,
                },
                baseline={
                    "patch_generated": False,
                    "tokens": {"input": 40, "output": 200},
                    "iterations": 2,
                    "tool_calls": 3,
                    "tool_usage": {"Read": 1, "Bash": 2},
                    "resolved": False,
                    "patch_applied": False,
                },
            ),
        ],
    )


class TestSaveJsonResults:
    """Tests for save_json_results function."""

    def test_saves_valid_json(self, sample_results: EvaluationResults) -> None:
        """Test that JSON output is valid and contains expected data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.json"
            save_json_results(sample_results, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

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
            output_path = Path(tmpdir) / "subdir" / "nested" / "results.json"
            save_json_results(sample_results, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()


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


class TestSaveMarkdownReport:
    """Tests for save_markdown_report function."""

    def test_saves_valid_markdown(self, sample_results: EvaluationResults) -> None:
        """Test that Markdown output is valid and contains expected sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            save_markdown_report(sample_results, output_path)

            assert output_path.exists()

            content = output_path.read_text()

            # Check for expected sections
            assert "# SWE-bench MCP Evaluation Report" in content
            assert "## Summary" in content
            assert "## MCP Server Configuration" in content
            assert "## Per-Task Results" in content
            assert "## Analysis" in content

            # Check for task data
            assert "test-task-1" in content
            assert "test-task-2" in content

    def test_creates_parent_directories(self, sample_results: EvaluationResults) -> None:
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "nested" / "report.md"
            save_markdown_report(sample_results, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()
