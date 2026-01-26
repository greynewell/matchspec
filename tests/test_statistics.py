"""Tests for comprehensive statistics module."""

import pytest

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.statistics import (
    CostStatistics,
    TokenStatistics,
    _categorize_error,
    calculate_comprehensive_statistics,
)


class TestCategorizeError:
    """Tests for error categorization."""

    def test_timeout_errors(self) -> None:
        """Test timeout error categorization."""
        assert _categorize_error("Task timed out after 300s") == "timeout"
        assert _categorize_error("Timeout exceeded") == "timeout"
        assert _categorize_error("Operation TIMEOUT") == "timeout"

    def test_network_errors(self) -> None:
        """Test network error categorization."""
        assert _categorize_error("Connection refused") == "network"
        assert _categorize_error("Network error occurred") == "network"

    def test_permission_errors(self) -> None:
        """Test permission error categorization."""
        assert _categorize_error("Permission denied") == "permission"
        assert _categorize_error("Access denied to file") == "permission"

    def test_not_found_errors(self) -> None:
        """Test not found error categorization."""
        assert _categorize_error("File not found") == "not_found"
        assert _categorize_error("No such file or directory") == "not_found"

    def test_syntax_errors(self) -> None:
        """Test syntax error categorization."""
        assert _categorize_error("Syntax error in code") == "syntax"
        assert _categorize_error("Failed to parse JSON") == "syntax"

    def test_memory_errors(self) -> None:
        """Test memory error categorization."""
        assert _categorize_error("Out of memory") == "memory"
        assert _categorize_error("Memory allocation failed") == "memory"

    def test_docker_errors(self) -> None:
        """Test docker error categorization."""
        assert _categorize_error("Docker container failed") == "docker"
        assert _categorize_error("Container not running") == "docker"

    def test_mcp_errors(self) -> None:
        """Test MCP error categorization."""
        assert _categorize_error("MCP server connection failed") == "mcp_server"
        assert _categorize_error("MCP tool call error") == "mcp_server"

    def test_other_errors(self) -> None:
        """Test other error categorization."""
        assert _categorize_error("Unknown error occurred") == "other"
        assert _categorize_error("Something went wrong") == "other"


class TestTokenStatistics:
    """Tests for token statistics calculations."""

    def test_basic_token_stats(self) -> None:
        """Test basic token statistics calculation."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"tokens": {"input": 100, "output": 500}, "resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"tokens": {"input": 200, "output": 400}, "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_tokens.total_input == 300
        assert stats.mcp_tokens.total_output == 900
        assert stats.mcp_tokens.total_tokens == 1200
        assert stats.mcp_tokens.avg_input_per_task == 150.0
        assert stats.mcp_tokens.avg_output_per_task == 450.0
        assert stats.mcp_tokens.max_input_per_task == 200
        assert stats.mcp_tokens.min_input_per_task == 100

    def test_token_stats_with_empty_tasks(self) -> None:
        """Test token statistics with empty task list."""
        results = EvaluationResults(metadata={}, summary={}, tasks=[])

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_tokens.total_input == 0
        assert stats.mcp_tokens.total_output == 0
        assert stats.mcp_tokens.avg_input_per_task == 0.0

    def test_token_stats_per_task(self) -> None:
        """Test per-task token tracking."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"tokens": {"input": 100, "output": 500}, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert "task-1" in stats.mcp_tokens.per_task
        assert stats.mcp_tokens.per_task["task-1"]["input"] == 100
        assert stats.mcp_tokens.per_task["task-1"]["output"] == 500
        assert stats.mcp_tokens.per_task["task-1"]["total"] == 600

    def test_token_stats_serialization(self) -> None:
        """Test token statistics serialization to dict."""
        stats = TokenStatistics(
            total_input=1000,
            total_output=2000,
            total_tokens=3000,
            avg_input_per_task=100.5,
            avg_output_per_task=200.5,
            avg_tokens_per_task=300.5,
            max_input_per_task=500,
            max_output_per_task=1000,
            min_input_per_task=50,
            min_output_per_task=100,
        )

        data = stats.to_dict()

        assert data["total_input"] == 1000
        assert data["total_output"] == 2000
        assert data["avg_input_per_task"] == 100.5
        assert isinstance(data["avg_input_per_task"], float)


class TestCostStatistics:
    """Tests for cost statistics calculations."""

    def test_basic_cost_stats(self) -> None:
        """Test basic cost statistics calculation."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"cost": 0.0123, "resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"cost": 0.0456, "resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={"cost": 0.0200, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_costs.total_cost == pytest.approx(0.0779, rel=1e-4)
        assert stats.mcp_costs.avg_cost_per_task == pytest.approx(0.0779 / 3, rel=1e-4)
        assert stats.mcp_costs.max_cost_per_task == 0.0456
        assert stats.mcp_costs.min_cost_per_task == 0.0123
        assert stats.mcp_costs.cost_per_resolved == pytest.approx(0.0779 / 2, rel=1e-4)

    def test_cost_stats_no_resolved(self) -> None:
        """Test cost statistics when no tasks are resolved."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"cost": 0.01, "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_costs.cost_per_resolved is None

    def test_cost_stats_serialization(self) -> None:
        """Test cost statistics serialization with rounding."""
        stats = CostStatistics(
            total_cost=0.123456789,
            avg_cost_per_task=0.0123456,
            max_cost_per_task=0.05,
            min_cost_per_task=0.001,
            cost_per_resolved=0.0246912,
        )

        data = stats.to_dict()

        assert data["total_cost"] == pytest.approx(0.1235, rel=1e-4)
        assert data["avg_cost_per_task"] == pytest.approx(0.0123, rel=1e-4)


class TestToolStatistics:
    """Tests for tool usage statistics."""

    def test_basic_tool_stats(self) -> None:
        """Test basic tool statistics calculation."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tool_usage": {"Read": 5, "Write": 3, "Bash": 2},
                        "tool_failures": {"Write": 1},
                        "resolved": True,
                    },
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={
                        "tool_usage": {"Read": 3, "Bash": 4},
                        "tool_failures": {"Bash": 2},
                        "resolved": False,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_tools.total_calls == 17  # 5+3+2+3+4
        assert stats.mcp_tools.total_failures == 3  # 1+2
        assert stats.mcp_tools.total_successes == 14  # 17-3
        assert stats.mcp_tools.failure_rate == pytest.approx(3 / 17, rel=1e-4)
        assert stats.mcp_tools.unique_tools_used == 3
        assert stats.mcp_tools.avg_calls_per_task == 17 / 2

    def test_tool_stats_per_tool(self) -> None:
        """Test per-tool statistics."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tool_usage": {"Read": 10, "Write": 5},
                        "tool_failures": {"Write": 2},
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_tools.per_tool["Read"]["total"] == 10
        assert stats.mcp_tools.per_tool["Read"]["succeeded"] == 10
        assert stats.mcp_tools.per_tool["Read"]["failed"] == 0
        assert stats.mcp_tools.per_tool["Read"]["failure_rate"] == 0.0

        assert stats.mcp_tools.per_tool["Write"]["total"] == 5
        assert stats.mcp_tools.per_tool["Write"]["succeeded"] == 3
        assert stats.mcp_tools.per_tool["Write"]["failed"] == 2
        assert stats.mcp_tools.per_tool["Write"]["failure_rate"] == 0.4

    def test_tool_stats_most_used(self) -> None:
        """Test most used tools tracking."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tool_usage": {"Read": 10, "Write": 5, "Bash": 20},
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert len(stats.mcp_tools.most_used_tools) == 3
        assert stats.mcp_tools.most_used_tools[0] == ("Bash", 20)
        assert stats.mcp_tools.most_used_tools[1] == ("Read", 10)
        assert stats.mcp_tools.most_used_tools[2] == ("Write", 5)

    def test_tool_stats_no_tools(self) -> None:
        """Test tool statistics with no tool usage."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_tools.total_calls == 0
        assert stats.mcp_tools.unique_tools_used == 0
        assert stats.mcp_tools.failure_rate == 0.0


class TestErrorStatistics:
    """Tests for error statistics."""

    def test_basic_error_stats(self) -> None:
        """Test basic error statistics calculation."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"error": "Timeout exceeded", "resolved": False},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"error": "File not found", "resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={"resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_errors.total_errors == 2
        assert stats.mcp_errors.error_rate == pytest.approx(2 / 3, rel=1e-4)
        assert stats.mcp_errors.timeout_count == 1
        assert stats.mcp_errors.timeout_rate == pytest.approx(1 / 3, rel=1e-4)

    def test_error_categories(self) -> None:
        """Test error categorization."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"error": "Timeout exceeded", "resolved": False},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"error": "Connection refused", "resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={"error": "Docker container failed", "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_errors.error_categories["timeout"] == 1
        assert stats.mcp_errors.error_categories["network"] == 1
        assert stats.mcp_errors.error_categories["docker"] == 1

    def test_most_common_errors(self) -> None:
        """Test most common errors tracking."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"error": "Timeout exceeded", "resolved": False},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"error": "Timeout exceeded", "resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={"error": "File not found", "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert len(stats.mcp_errors.most_common_errors) == 2
        assert stats.mcp_errors.most_common_errors[0] == ("Timeout exceeded", 2)
        assert stats.mcp_errors.most_common_errors[1] == ("File not found", 1)

    def test_sample_errors(self) -> None:
        """Test sample error collection."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"error": "Error A", "resolved": False},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"error": "Error B", "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert len(stats.mcp_errors.sample_errors) == 2
        assert stats.mcp_errors.sample_errors[0]["instance_id"] == "task-1"
        assert stats.mcp_errors.sample_errors[0]["error"] == "Error A"
        assert stats.mcp_errors.sample_errors[1]["instance_id"] == "task-2"


class TestIterationStatistics:
    """Tests for iteration statistics."""

    def test_basic_iteration_stats(self) -> None:
        """Test basic iteration statistics calculation."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"iterations": 5, "resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"iterations": 3, "resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={"iterations": 7, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_iterations.total_iterations == 15
        assert stats.mcp_iterations.avg_iterations == 5.0
        assert stats.mcp_iterations.max_iterations == 7
        assert stats.mcp_iterations.min_iterations == 3

    def test_iteration_distribution(self) -> None:
        """Test iteration distribution tracking."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"iterations": 5, "resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"iterations": 5, "resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={"iterations": 3, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_iterations.distribution[5] == 2
        assert stats.mcp_iterations.distribution[3] == 1

    def test_iteration_per_task(self) -> None:
        """Test per-task iteration tracking."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"iterations": 5, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_iterations.per_task["task-1"] == 5


class TestComprehensiveStatistics:
    """Tests for comprehensive statistics integration."""

    def test_full_statistics_calculation(self) -> None:
        """Test full comprehensive statistics calculation."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tokens": {"input": 100, "output": 500},
                        "cost": 0.01,
                        "iterations": 5,
                        "tool_usage": {"Read": 3, "Write": 2},
                        "tool_failures": {"Write": 1},
                        "resolved": True,
                    },
                    baseline={
                        "tokens": {"input": 80, "output": 400},
                        "cost": 0.008,
                        "iterations": 3,
                        "resolved": False,
                    },
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={
                        "tokens": {"input": 200, "output": 600},
                        "cost": 0.02,
                        "iterations": 7,
                        "tool_usage": {"Read": 5, "Bash": 3},
                        "error": "Timeout exceeded",
                        "resolved": False,
                    },
                    baseline={
                        "tokens": {"input": 150, "output": 500},
                        "cost": 0.015,
                        "iterations": 5,
                        "error": "File not found",
                        "resolved": False,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        # Verify all components are calculated
        assert stats.mcp_tokens.total_tokens > 0
        assert stats.baseline_tokens.total_tokens > 0
        assert stats.mcp_costs.total_cost > 0
        assert stats.baseline_costs.total_cost > 0
        assert stats.mcp_tools.total_calls > 0
        assert stats.mcp_errors.total_errors > 0
        assert stats.baseline_errors.total_errors > 0
        assert stats.mcp_iterations.total_iterations > 0
        assert stats.baseline_iterations.total_iterations > 0

    def test_statistics_serialization(self) -> None:
        """Test comprehensive statistics serialization."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tokens": {"input": 100, "output": 500},
                        "cost": 0.01,
                        "iterations": 5,
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)
        data = stats.to_dict()

        # Verify structure
        assert "mcp_tokens" in data
        assert "baseline_tokens" in data
        assert "mcp_costs" in data
        assert "baseline_costs" in data
        assert "mcp_tools" in data
        assert "mcp_errors" in data
        assert "baseline_errors" in data
        assert "mcp_iterations" in data
        assert "baseline_iterations" in data

        # Verify nested structure
        assert "total_input" in data["mcp_tokens"]
        assert "total_cost" in data["mcp_costs"]
        assert "total_calls" in data["mcp_tools"]

    def test_empty_results(self) -> None:
        """Test statistics calculation with empty results."""
        results = EvaluationResults(metadata={}, summary={}, tasks=[])

        stats = calculate_comprehensive_statistics(results)

        # Should not raise errors and should have zero values
        assert stats.mcp_tokens.total_tokens == 0
        assert stats.mcp_costs.total_cost == 0.0
        assert stats.mcp_tools.total_calls == 0
        assert stats.mcp_errors.total_errors == 0
        assert stats.mcp_iterations.total_iterations == 0

    def test_baseline_only_results(self) -> None:
        """Test statistics with baseline only (no MCP data)."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    baseline={
                        "tokens": {"input": 100, "output": 500},
                        "cost": 0.01,
                        "iterations": 5,
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        # MCP should be empty
        assert stats.mcp_tokens.total_tokens == 0
        # Baseline should have data
        assert stats.baseline_tokens.total_tokens == 600


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_missing_tokens_field(self) -> None:
        """Test handling of missing tokens field."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)
        assert stats.mcp_tokens.total_tokens == 0

    def test_missing_cost_field(self) -> None:
        """Test handling of missing cost field."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)
        assert stats.mcp_costs.total_cost == 0.0

    def test_zero_iterations(self) -> None:
        """Test handling of zero iterations."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"iterations": 0, "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)
        assert stats.mcp_iterations.total_iterations == 0
        assert stats.mcp_iterations.min_iterations == 0

    def test_single_task_statistics(self) -> None:
        """Test statistics with a single task."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "tokens": {"input": 100, "output": 500},
                        "cost": 0.01,
                        "iterations": 5,
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_tokens.avg_input_per_task == 100.0
        assert stats.mcp_tokens.max_input_per_task == 100
        assert stats.mcp_tokens.min_input_per_task == 100
