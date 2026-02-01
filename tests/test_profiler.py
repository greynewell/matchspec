"""Tests for performance profiling infrastructure."""

import time
from datetime import datetime, timezone

import pytest

from mcpbr.profiler import (
    MemorySample,
    PerformanceProfiler,
    ToolCallProfile,
    merge_profiling_reports,
)


class TestToolCallProfile:
    """Tests for ToolCallProfile dataclass."""

    def test_duration_calculation(self) -> None:
        """Test duration calculation in milliseconds and seconds."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, 1, 500000, tzinfo=timezone.utc)  # 1.5 seconds later

        profile = ToolCallProfile(
            tool_name="Read",
            start_time=start,
            end_time=end,
            success=True,
        )

        assert profile.duration_seconds == pytest.approx(1.5, rel=1e-2)
        assert profile.duration_ms == pytest.approx(1500, rel=1e-2)

    def test_tool_call_with_error(self) -> None:
        """Test tool call profile with error information."""
        start = datetime.now(timezone.utc)
        end = start
        profile = ToolCallProfile(
            tool_name="Bash",
            start_time=start,
            end_time=end,
            success=False,
            error="Command not found",
        )

        assert not profile.success
        assert profile.error == "Command not found"
        assert profile.duration_seconds >= 0


class TestPerformanceProfiler:
    """Tests for PerformanceProfiler class."""

    def test_initialization(self) -> None:
        """Test profiler initialization."""
        profiler = PerformanceProfiler()
        assert profiler.enable_memory_profiling is True
        assert len(profiler.tool_calls) == 0
        assert profiler.task_start is None
        assert profiler.task_end is None

    def test_task_timing(self) -> None:
        """Test task start and end timing."""
        profiler = PerformanceProfiler()
        profiler.start_task()
        assert profiler.task_start is not None

        time.sleep(0.1)

        profiler.end_task()
        assert profiler.task_end is not None
        assert profiler.task_end > profiler.task_start

    def test_record_tool_call(self) -> None:
        """Test recording tool calls."""
        profiler = PerformanceProfiler()
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)

        profiler.record_tool_call(
            tool_name="Read",
            start_time=start,
            end_time=end,
            success=True,
            parameters={"file_path": "/test/file.py"},
            result_size_bytes=1024,
        )

        assert len(profiler.tool_calls) == 1
        assert profiler.tool_calls[0].tool_name == "Read"
        assert profiler.tool_calls[0].success is True
        assert profiler.tool_calls[0].result_size_bytes == 1024

    def test_memory_sampling(self) -> None:
        """Test memory sampling functionality."""
        profiler = PerformanceProfiler(enable_memory_profiling=True)

        # Sample memory multiple times
        profiler.sample_memory()
        time.sleep(0.01)
        profiler.sample_memory()

        # Should have samples (unless psutil not available)
        # We can't guarantee samples due to psutil dependency
        assert isinstance(profiler.memory_samples, list)

    def test_memory_sampling_disabled(self) -> None:
        """Test that memory sampling can be disabled."""
        profiler = PerformanceProfiler(enable_memory_profiling=False)
        profiler.sample_memory()
        assert len(profiler.memory_samples) == 0

    def test_infrastructure_overhead_tracking(self) -> None:
        """Test Docker and MCP overhead tracking."""
        profiler = PerformanceProfiler()

        profiler.record_docker_startup(2.5)
        profiler.record_docker_teardown(1.0)
        profiler.record_mcp_startup(3.2)

        assert profiler.docker_startup_time == 2.5
        assert profiler.docker_teardown_time == 1.0
        assert profiler.mcp_server_startup_time == 3.2

    def test_time_to_first_tool(self) -> None:
        """Test time-to-first-tool tracking."""
        profiler = PerformanceProfiler()
        profiler.start_task()
        time.sleep(0.1)

        start = datetime.now(timezone.utc)
        profiler.record_tool_call("Read", start, start, True)

        time_to_first = profiler._calculate_time_to_first_tool()
        assert time_to_first is not None
        assert time_to_first >= 0.1

    def test_tool_switching_overhead(self) -> None:
        """Test tool switching overhead calculation."""
        profiler = PerformanceProfiler()

        # Record two tool calls with gap between them
        start1 = datetime.now(timezone.utc)
        end1 = start1
        profiler.record_tool_call("Read", start1, end1, True)

        time.sleep(0.05)

        start2 = datetime.now(timezone.utc)
        end2 = start2
        profiler.record_tool_call("Bash", start2, end2, True)

        overhead = profiler._calculate_tool_switching_overhead()
        assert overhead >= 0.05

    def test_tool_latency_calculation(self) -> None:
        """Test tool latency statistics calculation."""
        from datetime import timedelta

        profiler = PerformanceProfiler()

        # Add multiple tool calls with varying latencies
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            start = base_time
            # Simulate different latencies
            latency_ms = 100 + i * 10  # 100ms to 190ms
            end = start + timedelta(milliseconds=latency_ms)
            profiler.record_tool_call("Read", start, end, True)

        latencies = profiler._calculate_tool_latencies()
        assert "Read" in latencies
        assert latencies["Read"]["count"] == 10
        assert "avg_seconds" in latencies["Read"]
        assert "p50_seconds" in latencies["Read"]
        assert "p95_seconds" in latencies["Read"]
        assert "p99_seconds" in latencies["Read"]

    def test_generate_report(self) -> None:
        """Test comprehensive report generation."""
        profiler = PerformanceProfiler()
        profiler.start_task()

        # Record some tool calls
        start = datetime.now(timezone.utc)
        profiler.record_tool_call("Read", start, start, True)
        profiler.record_tool_call("Bash", start, start, False, error="Command failed")

        profiler.record_docker_startup(2.0)
        profiler.sample_memory()

        time.sleep(0.1)
        profiler.end_task()

        report = profiler.generate_report()

        assert "task_duration_seconds" in report
        assert report["task_duration_seconds"] >= 0.1
        assert "tool_call_latencies" in report
        assert "total_tool_calls" in report
        assert report["total_tool_calls"] == 2
        assert report["successful_tool_calls"] == 1
        assert report["failed_tool_calls"] == 1
        assert "docker_startup_seconds" in report
        assert report["docker_startup_seconds"] == 2.0

    def test_insights_generation(self) -> None:
        """Test automated insights generation."""
        profiler = PerformanceProfiler()
        profiler.start_task()

        # Add slow tool calls
        from datetime import timedelta

        base_time = datetime.now(timezone.utc)
        start = base_time
        end = start + timedelta(seconds=5)  # 5 second call
        profiler.record_tool_call("Bash", start, end, True)

        # Add infrastructure overhead
        profiler.record_docker_startup(6.0)
        profiler.record_mcp_startup(3.0)

        time.sleep(0.01)
        profiler.end_task()

        insights = profiler.get_insights()

        assert len(insights) > 0
        # Should identify slow tool
        assert any("Bash" in insight for insight in insights)
        # Should identify Docker overhead
        assert any("Docker" in insight for insight in insights)
        # Should identify MCP overhead
        assert any("MCP" in insight for insight in insights)

    def test_high_failure_rate_insight(self) -> None:
        """Test insight generation for high tool failure rate."""
        profiler = PerformanceProfiler()
        profiler.start_task()

        start = datetime.now(timezone.utc)
        # Record mostly failing tool calls
        for i in range(10):
            profiler.record_tool_call("Bash", start, start, success=(i < 2), error="Failed")

        profiler.end_task()

        insights = profiler.get_insights()
        # Should flag high failure rate (8/10 = 80%)
        assert any("failure rate" in insight.lower() for insight in insights)


class TestMemorySample:
    """Tests for MemorySample dataclass."""

    def test_memory_sample_creation(self) -> None:
        """Test creating memory samples."""
        sample = MemorySample(
            timestamp=datetime.now(timezone.utc),
            rss_mb=256.5,
            vms_mb=512.0,
        )

        assert sample.rss_mb == 256.5
        assert sample.vms_mb == 512.0
        assert sample.timestamp is not None


class TestMergeProfilingReports:
    """Tests for merging multiple profiling reports."""

    def test_merge_empty_reports(self) -> None:
        """Test merging empty report list."""
        result = merge_profiling_reports([])
        assert result == {}

    def test_merge_single_report(self) -> None:
        """Test merging a single report."""
        report = {
            "task_duration_seconds": 10.0,
            "tool_call_latencies": {
                "Read": {
                    "count": 5,
                    "avg_seconds": 1.0,
                    "p95_seconds": 1.5,
                    "p99_seconds": 1.8,
                }
            },
        }

        result = merge_profiling_reports([report])
        assert result["total_tasks"] == 1
        assert "tool_latencies" in result

    def test_merge_multiple_reports(self) -> None:
        """Test merging multiple reports."""
        reports = [
            {
                "task_duration_seconds": 10.0,
                "tool_call_latencies": {
                    "Read": {
                        "count": 5,
                        "avg_seconds": 1.0,
                        "p95_seconds": 1.5,
                        "p99_seconds": 1.8,
                    }
                },
                "time_to_first_tool_seconds": 2.0,
                "docker_startup_seconds": 3.0,
                "mcp_server_startup_seconds": 1.5,
            },
            {
                "task_duration_seconds": 12.0,
                "tool_call_latencies": {
                    "Read": {
                        "count": 3,
                        "avg_seconds": 1.2,
                        "p95_seconds": 1.6,
                        "p99_seconds": 1.9,
                    },
                    "Bash": {
                        "count": 2,
                        "avg_seconds": 2.0,
                        "p95_seconds": 2.5,
                        "p99_seconds": 2.8,
                    },
                },
                "time_to_first_tool_seconds": 3.0,
                "docker_startup_seconds": 2.5,
                "mcp_server_startup_seconds": 1.2,
            },
        ]

        result = merge_profiling_reports(reports)

        assert result["total_tasks"] == 2
        assert result["avg_task_duration_seconds"] == pytest.approx(11.0)
        assert "tool_latencies" in result
        assert "Read" in result["tool_latencies"]
        assert "Bash" in result["tool_latencies"]
        assert result["tool_latencies"]["Read"]["total_calls"] == 8
        assert result["avg_time_to_first_tool_seconds"] == pytest.approx(2.5)
        assert result["avg_docker_startup_seconds"] == pytest.approx(2.75)
        assert result["avg_mcp_server_startup_seconds"] == pytest.approx(1.35)


class TestProfilingIntegration:
    """Integration tests for profiling in real scenarios."""

    def test_complete_profiling_workflow(self) -> None:
        """Test complete profiling workflow from start to finish."""
        profiler = PerformanceProfiler(enable_memory_profiling=True)

        # Start task
        profiler.start_task()

        # Simulate Docker startup
        profiler.record_docker_startup(2.5)

        # Sample memory
        profiler.sample_memory()

        # Simulate tool calls
        start1 = datetime.now(timezone.utc)
        time.sleep(0.05)
        end1 = datetime.now(timezone.utc)
        profiler.record_tool_call("Read", start1, end1, True, result_size_bytes=1024)

        time.sleep(0.02)

        start2 = datetime.now(timezone.utc)
        time.sleep(0.03)
        end2 = datetime.now(timezone.utc)
        profiler.record_tool_call("Bash", start2, end2, True)

        # Sample memory again
        profiler.sample_memory()

        # Simulate MCP startup
        profiler.record_mcp_startup(1.5)

        # End task
        time.sleep(0.01)
        profiler.end_task()

        # Simulate Docker teardown
        profiler.record_docker_teardown(0.5)

        # Generate report
        report = profiler.generate_report()

        # Verify report completeness
        assert "task_duration_seconds" in report
        assert report["task_duration_seconds"] > 0
        assert "tool_call_latencies" in report
        assert "Read" in report["tool_call_latencies"]
        assert "Bash" in report["tool_call_latencies"]
        assert report["total_tool_calls"] == 2
        assert report["successful_tool_calls"] == 2
        assert report["failed_tool_calls"] == 0
        assert "docker_startup_seconds" in report
        assert "docker_teardown_seconds" in report
        assert "mcp_server_startup_seconds" in report
        assert "time_to_first_tool_seconds" in report
        assert "tool_switching_overhead_seconds" in report

        # Generate insights
        insights = profiler.get_insights()
        assert isinstance(insights, list)

    def test_profiling_with_errors(self) -> None:
        """Test profiling when tool calls fail."""
        profiler = PerformanceProfiler()
        profiler.start_task()

        start = datetime.now(timezone.utc)
        end = start

        # Mix of successful and failed calls
        profiler.record_tool_call("Read", start, end, True)
        profiler.record_tool_call("Bash", start, end, False, error="Command not found")
        profiler.record_tool_call("Write", start, end, True)
        profiler.record_tool_call("Bash", start, end, False, error="Permission denied")

        profiler.end_task()

        report = profiler.generate_report()

        assert report["total_tool_calls"] == 4
        assert report["successful_tool_calls"] == 2
        assert report["failed_tool_calls"] == 2
        assert "Bash" in report["tool_call_latencies"]

    def test_percentile_calculation_edge_cases(self) -> None:
        """Test percentile calculation with edge cases."""
        profiler = PerformanceProfiler()

        # Single value
        start = datetime.now(timezone.utc)
        profiler.record_tool_call("Read", start, start, True)

        latencies = profiler._calculate_tool_latencies()
        assert "Read" in latencies
        # All percentiles should be the same for single value
        assert latencies["Read"]["p50_seconds"] == latencies["Read"]["p95_seconds"]

        # Two values
        from datetime import timedelta

        profiler2 = PerformanceProfiler()
        base = datetime.now(timezone.utc)
        profiler2.record_tool_call("Read", base, base, True)
        end2 = base + timedelta(seconds=1)
        profiler2.record_tool_call("Read", base, end2, True)

        latencies2 = profiler2._calculate_tool_latencies()
        assert "Read" in latencies2
        assert latencies2["Read"]["count"] == 2
