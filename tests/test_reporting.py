"""Tests for reporting utilities."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml
from rich.console import Console

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import (
    ToolCoverageReport,
    calculate_tool_coverage,
    print_summary,
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
                "benchmark": "swe-bench-lite",
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


class TestToolCoverageReport:
    """Tests for ToolCoverageReport class."""

    def test_init_with_available_tools(self) -> None:
        """Test initialization with available tools list."""
        available_tools = ["Read", "Write", "Bash", "Grep", "Glob"]
        report = ToolCoverageReport(available_tools)

        assert len(report.available_tools) == 5
        assert "Read" in report.available_tools
        assert len(report.tool_usage_counter) == 0

    def test_init_without_available_tools(self) -> None:
        """Test initialization without available tools list."""
        report = ToolCoverageReport()

        assert len(report.available_tools) == 0
        assert len(report.tool_usage_counter) == 0

    def test_add_task_usage(self) -> None:
        """Test adding tool usage from tasks."""
        report = ToolCoverageReport(["Read", "Write", "Bash", "Grep"])

        # Add usage from first task
        report.add_task_usage({"Read": 3, "Write": 2, "Bash": 5})

        assert report.tool_usage_counter["Read"] == 3
        assert report.tool_usage_counter["Write"] == 2
        assert report.tool_usage_counter["Bash"] == 5

        # Add usage from second task
        report.add_task_usage({"Read": 4, "Bash": 4})

        assert report.tool_usage_counter["Read"] == 7
        assert report.tool_usage_counter["Write"] == 2
        assert report.tool_usage_counter["Bash"] == 9

    def test_add_task_usage_updates_available_tools(self) -> None:
        """Test that adding usage updates available tools when not initially provided."""
        report = ToolCoverageReport()

        report.add_task_usage({"Read": 3, "Write": 2})
        assert len(report.available_tools) == 2
        assert "Read" in report.available_tools
        assert "Write" in report.available_tools

    def test_get_coverage_metrics_full_coverage(self) -> None:
        """Test coverage metrics when all tools are used."""
        report = ToolCoverageReport(["Read", "Write", "Bash"])
        report.add_task_usage({"Read": 5, "Write": 3, "Bash": 2})

        metrics = report.get_coverage_metrics()

        assert metrics["total_available"] == 3
        assert metrics["total_used"] == 3
        assert metrics["coverage_rate"] == 1.0
        assert metrics["unused_tools"] == []

    def test_get_coverage_metrics_partial_coverage(self) -> None:
        """Test coverage metrics when some tools are unused."""
        report = ToolCoverageReport(["Read", "Write", "Bash", "Grep", "Glob"])
        report.add_task_usage({"Read": 10, "Bash": 5})

        metrics = report.get_coverage_metrics()

        assert metrics["total_available"] == 5
        assert metrics["total_used"] == 2
        assert metrics["coverage_rate"] == 0.4
        assert sorted(metrics["unused_tools"]) == ["Glob", "Grep", "Write"]

    def test_get_coverage_metrics_most_used(self) -> None:
        """Test most used tools ordering."""
        report = ToolCoverageReport()
        report.add_task_usage(
            {
                "Read": 10,
                "Bash": 20,
                "Write": 5,
                "Grep": 15,
                "Glob": 3,
            }
        )

        metrics = report.get_coverage_metrics()
        most_used = metrics["most_used"]

        # Should be ordered by count descending
        assert most_used[0] == ("Bash", 20)
        assert most_used[1] == ("Grep", 15)
        assert most_used[2] == ("Read", 10)

    def test_get_coverage_metrics_no_tools_used(self) -> None:
        """Test coverage metrics when no tools are used."""
        report = ToolCoverageReport(["Read", "Write", "Bash"])

        metrics = report.get_coverage_metrics()

        assert metrics["total_available"] == 3
        assert metrics["total_used"] == 0
        assert metrics["coverage_rate"] == 0.0
        assert len(metrics["unused_tools"]) == 3

    def test_to_dict(self) -> None:
        """Test conversion to dictionary format."""
        report = ToolCoverageReport(["Read", "Write", "Bash", "Grep"])
        report.add_task_usage({"Read": 10, "Bash": 5})

        result = report.to_dict()

        assert "total_available" in result
        assert "total_used" in result
        assert "coverage_rate" in result
        assert "unused_tools" in result
        assert "most_used" in result
        assert "least_used" in result
        assert "all_tool_usage" in result

        assert result["total_available"] == 4
        assert result["total_used"] == 2
        assert result["coverage_rate"] == 0.5
        assert isinstance(result["most_used"], dict)
        assert result["all_tool_usage"]["Read"] == 10


class TestCalculateToolCoverage:
    """Tests for calculate_tool_coverage function."""

    def test_calculate_coverage_from_results(self) -> None:
        """Test calculating coverage from evaluation results."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tool_usage": {"Read": 3, "Write": 2, "Bash": 5},
                        "resolved": True,
                    },
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={
                        "tool_usage": {"Read": 4, "Bash": 4, "Grep": 2},
                        "resolved": False,
                    },
                ),
            ],
        )

        coverage = calculate_tool_coverage(results)

        assert coverage["total_available"] == 4  # Read, Write, Bash, Grep
        assert coverage["total_used"] == 4
        assert coverage["coverage_rate"] == 1.0
        assert coverage["all_tool_usage"]["Read"] == 7
        assert coverage["all_tool_usage"]["Bash"] == 9

    def test_calculate_coverage_with_available_tools(self) -> None:
        """Test calculating coverage with predefined available tools."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tool_usage": {"Read": 3, "Write": 2},
                        "resolved": True,
                    },
                ),
            ],
        )

        available_tools = ["Read", "Write", "Bash", "Grep", "Glob"]
        coverage = calculate_tool_coverage(results, available_tools)

        assert coverage["total_available"] == 5
        assert coverage["total_used"] == 2
        assert coverage["coverage_rate"] == 0.4
        assert sorted(coverage["unused_tools"]) == ["Bash", "Glob", "Grep"]

    def test_calculate_coverage_skips_baseline(self) -> None:
        """Test that coverage calculation only uses MCP agent data."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tool_usage": {"Read": 5},
                        "resolved": True,
                    },
                    baseline={
                        "tool_usage": {"Write": 10},
                        "resolved": False,
                    },
                ),
            ],
        )

        coverage = calculate_tool_coverage(results)

        # Should only include MCP tool usage
        assert coverage["all_tool_usage"]["Read"] == 5
        assert "Write" not in coverage["all_tool_usage"]

    def test_calculate_coverage_handles_missing_tool_usage(self) -> None:
        """Test that missing tool_usage is handled gracefully."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "resolved": False,
                        # No tool_usage field
                    },
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={
                        "tool_usage": {"Read": 3},
                        "resolved": True,
                    },
                ),
            ],
        )

        coverage = calculate_tool_coverage(results)

        # Should only count task-2
        assert coverage["total_used"] == 1
        assert coverage["all_tool_usage"]["Read"] == 3


class TestMcpOnlyMode:
    """Tests for --mcp-only mode (no baseline data)."""

    @pytest.fixture
    def mcp_only_results(self) -> EvaluationResults:
        """Create evaluation results from --mcp-only mode."""
        return EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T12:00:00Z",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench-lite",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 2,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                },
            },
            summary={
                "mcp": {
                    "resolved": 1,
                    "total": 2,
                    "rate": 0.5,
                    "total_cost": 0.05,
                    "cost_per_task": 0.025,
                    "cost_per_resolved": 0.05,
                },
                "baseline": {
                    "resolved": 0,
                    "total": 0,
                    "rate": 0.0,
                    "total_cost": 0.0,  # Zero cost in baseline
                },
                "improvement": "N/A",
                "cost_comparison": {
                    "total_difference": 0.05,
                    "cost_per_additional_resolution": None,
                },
            },
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "tokens": {"input": 100, "output": 500},
                    },
                ),
                TaskResult(
                    instance_id="test-task-2",
                    mcp={
                        "resolved": False,
                        "patch_generated": False,
                        "tokens": {"input": 80, "output": 400},
                    },
                ),
            ],
        )

    @pytest.fixture
    def mcp_only_missing_baseline(self) -> EvaluationResults:
        """Create evaluation results with missing baseline cost."""
        return EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T12:00:00Z",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench-lite",
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                },
            },
            summary={
                "mcp": {
                    "resolved": 1,
                    "total": 2,
                    "rate": 0.5,
                    "total_cost": 0.05,
                },
                "baseline": {
                    "resolved": 0,
                    "total": 0,
                    "rate": 0.0,
                    # Missing total_cost key
                },
                "improvement": "N/A",
                "cost_comparison": {
                    "total_difference": 0.05,
                },
            },
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={"resolved": True},
                ),
            ],
        )

    def test_markdown_report_with_zero_baseline_cost(
        self, mcp_only_results: EvaluationResults
    ) -> None:
        """Test that markdown report handles zero baseline cost without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            # Should not raise ZeroDivisionError
            save_markdown_report(mcp_only_results, output_path)

            assert output_path.exists()
            content = output_path.read_text()

            # Should contain "N/A - no baseline" instead of percentage
            assert "(N/A - no baseline)" in content
            assert "MCP Additional Cost" in content or "MCP Cost Savings" in content

    def test_markdown_report_with_missing_baseline_cost(
        self, mcp_only_missing_baseline: EvaluationResults
    ) -> None:
        """Test that markdown report handles missing baseline cost without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            # Should not raise ZeroDivisionError
            save_markdown_report(mcp_only_missing_baseline, output_path)

            assert output_path.exists()
            content = output_path.read_text()

            # Should contain "N/A - no baseline" instead of percentage
            assert "(N/A - no baseline)" in content

    def test_print_summary_with_zero_baseline_cost(
        self, mcp_only_results: EvaluationResults
    ) -> None:
        """Test that print_summary handles zero baseline cost without crashing."""
        console = Console()
        # Should not raise ZeroDivisionError
        print_summary(mcp_only_results, console)

    def test_print_summary_with_missing_baseline_cost(
        self, mcp_only_missing_baseline: EvaluationResults
    ) -> None:
        """Test that print_summary handles missing baseline cost without crashing."""
        console = Console()
        # Should not raise ZeroDivisionError
        print_summary(mcp_only_missing_baseline, console)


class TestToolCoverageInReports:
    """Tests for tool coverage inclusion in different report formats."""

    @pytest.fixture
    def results_with_coverage(self) -> EvaluationResults:
        """Create evaluation results with tool coverage data."""
        return EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T12:00:00Z",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench-lite",
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
                "tool_coverage": {
                    "total_available": 5,
                    "total_used": 3,
                    "coverage_rate": 0.6,
                    "unused_tools": ["Write", "Edit"],
                    "most_used": {"Read": 10, "Bash": 8, "Grep": 3},
                    "least_used": {"Grep": 3},
                    "all_tool_usage": {"Read": 10, "Bash": 8, "Grep": 3},
                },
            },
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={
                        "patch_generated": True,
                        "tokens": {"input": 100, "output": 500},
                        "iterations": 5,
                        "tool_calls": 10,
                        "tool_usage": {"Read": 6, "Bash": 4},
                        "resolved": True,
                        "patch_applied": True,
                    },
                ),
                TaskResult(
                    instance_id="test-task-2",
                    mcp={
                        "patch_generated": False,
                        "tokens": {"input": 80, "output": 400},
                        "iterations": 4,
                        "tool_calls": 7,
                        "tool_usage": {"Read": 4, "Bash": 4, "Grep": 3},
                        "resolved": False,
                        "patch_applied": False,
                    },
                ),
            ],
        )

    def test_tool_coverage_in_json(self, results_with_coverage: EvaluationResults) -> None:
        """Test that tool coverage is included in JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.json"
            save_json_results(results_with_coverage, output_path)

            with open(output_path) as f:
                data = json.load(f)

            assert "tool_coverage" in data["summary"]
            coverage = data["summary"]["tool_coverage"]
            assert coverage["total_available"] == 5
            assert coverage["total_used"] == 3
            assert coverage["coverage_rate"] == 0.6
            assert "Read" in coverage["most_used"]
            assert "Write" in coverage["unused_tools"]

    def test_tool_coverage_in_yaml(self, results_with_coverage: EvaluationResults) -> None:
        """Test that tool coverage is included in YAML output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yaml"
            save_yaml_results(results_with_coverage, output_path)

            with open(output_path) as f:
                data = yaml.safe_load(f)

            assert "tool_coverage" in data["summary"]
            coverage = data["summary"]["tool_coverage"]
            assert coverage["total_available"] == 5
            assert coverage["total_used"] == 3
            assert coverage["coverage_rate"] == 0.6

    def test_tool_coverage_in_markdown(self, results_with_coverage: EvaluationResults) -> None:
        """Test that tool coverage is included in Markdown report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            save_markdown_report(results_with_coverage, output_path)

            content = output_path.read_text()

            # Check for tool coverage section
            assert "## Tool Coverage Analysis" in content
            assert "Available Tools" in content
            assert "Used Tools" in content
            assert "Coverage Rate" in content

            # Check for most used tools section
            assert "### Most Used Tools" in content
            assert "Read" in content
            assert "Bash" in content

            # Check for unused tools section
            assert "### Unused Tools" in content
            assert "Write" in content
            assert "Edit" in content
