"""Tests for runtime tracking feature."""

import pytest

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import format_runtime
from mcpbr.statistics import RuntimeStatistics, calculate_comprehensive_statistics


class TestFormatRuntime:
    """Tests for runtime formatting helper."""

    def test_format_seconds(self) -> None:
        """Test formatting times under 60 seconds."""
        assert format_runtime(0) == "0s"
        assert format_runtime(15) == "15s"
        assert format_runtime(59) == "59s"
        assert format_runtime(59.9) == "59s"

    def test_format_minutes(self) -> None:
        """Test formatting times in minutes."""
        assert format_runtime(60) == "1m 0s"
        assert format_runtime(90) == "1m 30s"
        assert format_runtime(125) == "2m 5s"
        assert format_runtime(3599) == "59m 59s"

    def test_format_hours(self) -> None:
        """Test formatting times in hours."""
        assert format_runtime(3600) == "1h 0m 0s"
        assert format_runtime(3661) == "1h 1m 1s"
        assert format_runtime(7200) == "2h 0m 0s"
        assert format_runtime(4523) == "1h 15m 23s"


class TestRuntimeStatistics:
    """Tests for RuntimeStatistics dataclass."""

    def test_basic_runtime_stats(self) -> None:
        """Test basic runtime statistics calculation."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 120.5, "resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"runtime_seconds": 85.2, "resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={"runtime_seconds": 200.0, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.total_runtime == pytest.approx(405.7, rel=1e-4)
        assert stats.mcp_runtime.avg_runtime_per_task == pytest.approx(405.7 / 3, rel=1e-4)
        assert stats.mcp_runtime.max_runtime == 200.0
        assert stats.mcp_runtime.min_runtime == 85.2
        # Only resolved tasks: 120.5 + 200.0 = 320.5, divided by 2 = 160.25
        assert stats.mcp_runtime.runtime_per_resolved == pytest.approx(160.25, rel=1e-4)

    def test_runtime_stats_no_resolved(self) -> None:
        """Test runtime statistics when no tasks are resolved."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 100.0, "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.runtime_per_resolved is None

    def test_runtime_stats_per_task(self) -> None:
        """Test per-task runtime tracking."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 150.5, "resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"runtime_seconds": 75.0, "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert "task-1" in stats.mcp_runtime.per_task
        assert "task-2" in stats.mcp_runtime.per_task
        assert stats.mcp_runtime.per_task["task-1"] == 150.5
        assert stats.mcp_runtime.per_task["task-2"] == 75.0

    def test_runtime_stats_serialization(self) -> None:
        """Test runtime statistics serialization to dict."""
        stats = RuntimeStatistics(
            total_runtime=500.567,
            avg_runtime_per_task=100.1134,
            runtime_per_resolved=250.2835,
            min_runtime=50.123,
            max_runtime=200.456,
        )

        data = stats.to_dict()

        assert data["total_runtime"] == pytest.approx(500.57, rel=1e-4)
        assert data["avg_runtime_per_task"] == pytest.approx(100.11, rel=1e-4)
        assert data["runtime_per_resolved"] == pytest.approx(250.28, rel=1e-4)
        assert data["min_runtime"] == pytest.approx(50.12, rel=1e-4)
        assert data["max_runtime"] == pytest.approx(200.46, rel=1e-4)

    def test_runtime_stats_empty_tasks(self) -> None:
        """Test runtime statistics with empty task list."""
        results = EvaluationResults(metadata={}, summary={}, tasks=[])

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.total_runtime == 0.0
        assert stats.mcp_runtime.avg_runtime_per_task == 0.0
        assert stats.mcp_runtime.runtime_per_resolved is None
        assert stats.mcp_runtime.min_runtime == 0.0
        assert stats.mcp_runtime.max_runtime == 0.0

    def test_runtime_stats_missing_field(self) -> None:
        """Test handling of missing runtime_seconds field."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"resolved": True},  # No runtime_seconds field
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        # Should default to 0.0
        assert stats.mcp_runtime.total_runtime == 0.0
        assert stats.mcp_runtime.per_task["task-1"] == 0.0

    def test_runtime_stats_baseline_comparison(self) -> None:
        """Test runtime statistics for both MCP and baseline."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 150.0, "resolved": True},
                    baseline={"runtime_seconds": 120.0, "resolved": False},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"runtime_seconds": 100.0, "resolved": False},
                    baseline={"runtime_seconds": 80.0, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        # MCP stats
        assert stats.mcp_runtime.total_runtime == 250.0
        assert stats.mcp_runtime.avg_runtime_per_task == 125.0
        assert stats.mcp_runtime.runtime_per_resolved == 150.0  # Only task-1 resolved

        # Baseline stats
        assert stats.baseline_runtime.total_runtime == 200.0
        assert stats.baseline_runtime.avg_runtime_per_task == 100.0
        assert stats.baseline_runtime.runtime_per_resolved == 80.0  # Only task-2 resolved

    def test_runtime_stats_single_task(self) -> None:
        """Test runtime statistics with a single task."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 275.5, "resolved": True},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.total_runtime == 275.5
        assert stats.mcp_runtime.avg_runtime_per_task == 275.5
        assert stats.mcp_runtime.min_runtime == 275.5
        assert stats.mcp_runtime.max_runtime == 275.5
        assert stats.mcp_runtime.runtime_per_resolved == 275.5

    def test_runtime_stats_zero_runtime(self) -> None:
        """Test handling of zero runtime."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 0.0, "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.total_runtime == 0.0
        assert stats.mcp_runtime.min_runtime == 0.0


class TestRuntimeIntegration:
    """Tests for runtime tracking integration."""

    def test_comprehensive_stats_includes_runtime(self) -> None:
        """Test that comprehensive statistics includes runtime data."""
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
                        "runtime_seconds": 120.0,
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)
        data = stats.to_dict()

        # Verify runtime is included in serialization
        assert "mcp_runtime" in data
        assert "baseline_runtime" in data
        assert "total_runtime" in data["mcp_runtime"]
        assert data["mcp_runtime"]["total_runtime"] == 120.0

    def test_runtime_with_errors(self) -> None:
        """Test runtime tracking with task errors."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "runtime_seconds": 100.0,
                        "error": "Timeout exceeded",
                        "resolved": False,
                    },
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={
                        "runtime_seconds": 50.0,
                        "error": "Connection failed",
                        "resolved": False,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        # Runtime should still be tracked even with errors
        assert stats.mcp_runtime.total_runtime == 150.0
        assert stats.mcp_runtime.avg_runtime_per_task == 75.0

    def test_runtime_with_mixed_results(self) -> None:
        """Test runtime tracking with mixed success/failure results."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "runtime_seconds": 200.0,
                        "resolved": True,
                        "patch_applied": True,
                    },
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={
                        "runtime_seconds": 100.0,
                        "resolved": False,
                        "patch_applied": False,
                    },
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp={
                        "runtime_seconds": 150.0,
                        "resolved": True,
                        "patch_applied": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.total_runtime == 450.0
        assert stats.mcp_runtime.avg_runtime_per_task == 150.0
        # 2 tasks resolved: 200.0 + 150.0 = 350.0, divided by 2 = 175.0
        assert stats.mcp_runtime.runtime_per_resolved == 175.0

    def test_runtime_baseline_only(self) -> None:
        """Test runtime statistics with baseline only (no MCP data)."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    baseline={
                        "runtime_seconds": 100.0,
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        # MCP should be empty
        assert stats.mcp_runtime.total_runtime == 0.0
        # Baseline should have data
        assert stats.baseline_runtime.total_runtime == 100.0

    def test_runtime_with_cache_hit(self) -> None:
        """Test that runtime can be tracked even with cache hits."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={
                        "runtime_seconds": 50.0,
                        "cache_hit": True,
                        "resolved": True,
                    },
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={
                        "runtime_seconds": 150.0,
                        "cache_hit": False,
                        "resolved": True,
                    },
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        # Both should be counted regardless of cache status
        assert stats.mcp_runtime.total_runtime == 200.0
        assert stats.mcp_runtime.avg_runtime_per_task == 100.0

    def test_large_runtime_values(self) -> None:
        """Test handling of large runtime values."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 10800.0, "resolved": True},  # 3 hours
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"runtime_seconds": 7200.0, "resolved": True},  # 2 hours
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.total_runtime == 18000.0
        assert stats.mcp_runtime.max_runtime == 10800.0
        assert stats.mcp_runtime.min_runtime == 7200.0

    def test_fractional_runtime_values(self) -> None:
        """Test handling of fractional runtime values."""
        results = EvaluationResults(
            metadata={},
            summary={},
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp={"runtime_seconds": 123.456, "resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp={"runtime_seconds": 78.912, "resolved": False},
                ),
            ],
        )

        stats = calculate_comprehensive_statistics(results)

        assert stats.mcp_runtime.total_runtime == pytest.approx(202.368, rel=1e-4)
        assert stats.mcp_runtime.avg_runtime_per_task == pytest.approx(101.184, rel=1e-4)
