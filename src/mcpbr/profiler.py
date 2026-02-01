"""Comprehensive performance profiling infrastructure for MCP benchmark runs.

This module provides detailed performance profiling including:
- Tool call latency tracking with percentiles
- Memory usage profiling
- Docker and MCP server overhead tracking
- Tool discovery and switching metrics
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ToolCallProfile:
    """Profile data for a single tool call.

    Attributes:
        tool_name: Name of the tool that was called.
        start_time: When the tool call started.
        end_time: When the tool call completed.
        success: Whether the tool call succeeded.
        parameters: Tool call parameters (for debugging).
        result_size_bytes: Size of the result in bytes.
        error: Error message if the call failed.
    """

    tool_name: str
    start_time: datetime
    end_time: datetime
    success: bool
    parameters: dict[str, Any] = field(default_factory=dict)
    result_size_bytes: int = 0
    error: str | None = None

    @property
    def duration_ms(self) -> float:
        """Calculate duration in milliseconds."""
        return (self.end_time - self.start_time).total_seconds() * 1000

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class MemorySample:
    """Memory usage sample at a point in time.

    Attributes:
        timestamp: When the sample was taken.
        rss_mb: Resident Set Size in megabytes.
        vms_mb: Virtual Memory Size in megabytes.
    """

    timestamp: datetime
    rss_mb: float
    vms_mb: float


class PerformanceProfiler:
    """Comprehensive performance profiling for MCP benchmark runs.

    Tracks detailed performance metrics including tool call latencies,
    memory usage, infrastructure overhead, and generates insights.
    """

    def __init__(self, enable_memory_profiling: bool = True) -> None:
        """Initialize the performance profiler.

        Args:
            enable_memory_profiling: Whether to enable memory sampling.
        """
        self.tool_calls: list[ToolCallProfile] = []
        self.task_start: datetime | None = None
        self.task_end: datetime | None = None
        self.memory_samples: list[MemorySample] = []
        self.enable_memory_profiling = enable_memory_profiling

        # Infrastructure overhead tracking
        self.docker_startup_time: float | None = None
        self.docker_teardown_time: float | None = None
        self.mcp_server_startup_time: float | None = None

        # First tool use tracking
        self._first_tool_time: datetime | None = None

    def start_task(self) -> None:
        """Mark the start of a task."""
        self.task_start = datetime.now(timezone.utc)

    def end_task(self) -> None:
        """Mark the end of a task."""
        self.task_end = datetime.now(timezone.utc)

    def record_tool_call(
        self,
        tool_name: str,
        start_time: datetime,
        end_time: datetime,
        success: bool,
        parameters: dict[str, Any] | None = None,
        result_size_bytes: int = 0,
        error: str | None = None,
    ) -> None:
        """Record a tool call for profiling.

        Args:
            tool_name: Name of the tool.
            start_time: When the call started.
            end_time: When the call completed.
            success: Whether it succeeded.
            parameters: Tool parameters.
            result_size_bytes: Size of result.
            error: Error message if failed.
        """
        profile = ToolCallProfile(
            tool_name=tool_name,
            start_time=start_time,
            end_time=end_time,
            success=success,
            parameters=parameters or {},
            result_size_bytes=result_size_bytes,
            error=error,
        )
        self.tool_calls.append(profile)

        # Track first tool use
        if self._first_tool_time is None:
            self._first_tool_time = start_time

    def sample_memory(self) -> None:
        """Sample current memory usage."""
        if not self.enable_memory_profiling:
            return

        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()

            sample = MemorySample(
                timestamp=datetime.now(timezone.utc),
                rss_mb=memory_info.rss / 1024 / 1024,
                vms_mb=memory_info.vms / 1024 / 1024,
            )
            self.memory_samples.append(sample)
        except ImportError:
            # psutil not available, disable memory profiling
            self.enable_memory_profiling = False
        except Exception:
            # Failed to sample memory, skip silently
            pass

    def record_docker_startup(self, duration_seconds: float) -> None:
        """Record Docker container startup time.

        Args:
            duration_seconds: Time taken to start container.
        """
        self.docker_startup_time = duration_seconds

    def record_docker_teardown(self, duration_seconds: float) -> None:
        """Record Docker container teardown time.

        Args:
            duration_seconds: Time taken to teardown container.
        """
        self.docker_teardown_time = duration_seconds

    def record_mcp_startup(self, duration_seconds: float) -> None:
        """Record MCP server startup time.

        Args:
            duration_seconds: Time taken to initialize MCP server.
        """
        self.mcp_server_startup_time = duration_seconds

    def _calculate_percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile from a list of values.

        Args:
            values: List of numeric values.
            percentile: Percentile to calculate (0-100).

        Returns:
            The percentile value.
        """
        if not values:
            return 0.0

        # Use quantiles for accurate percentile calculation
        try:
            return statistics.quantiles(values, n=100)[percentile - 1]
        except statistics.StatisticsError:
            # Fall back to sorted list approach for small datasets
            sorted_values = sorted(values)
            index = int(len(sorted_values) * percentile / 100)
            return sorted_values[min(index, len(sorted_values) - 1)]

    def _calculate_tool_latencies(self) -> dict[str, dict[str, Any]]:
        """Calculate latency statistics per tool.

        Returns:
            Dictionary mapping tool names to latency stats.
        """
        tool_latencies: dict[str, list[float]] = {}

        for call in self.tool_calls:
            if call.tool_name not in tool_latencies:
                tool_latencies[call.tool_name] = []
            tool_latencies[call.tool_name].append(call.duration_seconds)

        result = {}
        for tool_name, latencies in tool_latencies.items():
            if not latencies:
                continue

            result[tool_name] = {
                "count": len(latencies),
                "avg_seconds": statistics.mean(latencies),
                "min_seconds": min(latencies),
                "max_seconds": max(latencies),
                "p50_seconds": self._calculate_percentile(latencies, 50),
                "p95_seconds": self._calculate_percentile(latencies, 95),
                "p99_seconds": self._calculate_percentile(latencies, 99),
                "total_seconds": sum(latencies),
            }

        return result

    def _calculate_memory_profile(self) -> dict[str, Any] | None:
        """Calculate memory usage statistics.

        Returns:
            Dictionary with memory stats or None if no samples.
        """
        if not self.memory_samples:
            return None

        rss_values = [s.rss_mb for s in self.memory_samples]
        vms_values = [s.vms_mb for s in self.memory_samples]

        return {
            "peak_rss_mb": max(rss_values),
            "avg_rss_mb": statistics.mean(rss_values),
            "peak_vms_mb": max(vms_values),
            "avg_vms_mb": statistics.mean(vms_values),
            "sample_count": len(self.memory_samples),
        }

    def _calculate_time_to_first_tool(self) -> float | None:
        """Calculate time from task start to first tool use.

        Returns:
            Duration in seconds or None if no tools used.
        """
        if self.task_start is None or self._first_tool_time is None:
            return None

        return (self._first_tool_time - self.task_start).total_seconds()

    def _calculate_tool_switching_overhead(self) -> float:
        """Calculate average time between tool calls (switching overhead).

        Returns:
            Average switching time in seconds.
        """
        if len(self.tool_calls) < 2:
            return 0.0

        gaps = []
        for i in range(1, len(self.tool_calls)):
            prev_call = self.tool_calls[i - 1]
            curr_call = self.tool_calls[i]

            # Time between previous call ending and current call starting
            gap = (curr_call.start_time - prev_call.end_time).total_seconds()
            if gap > 0:  # Only count positive gaps
                gaps.append(gap)

        return statistics.mean(gaps) if gaps else 0.0

    def _calculate_task_duration(self) -> float:
        """Calculate total task duration.

        Returns:
            Duration in seconds or 0 if task not completed.
        """
        if self.task_start is None or self.task_end is None:
            return 0.0

        return (self.task_end - self.task_start).total_seconds()

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report.

        Returns:
            Dictionary containing all performance metrics.
        """
        report: dict[str, Any] = {
            "task_duration_seconds": self._calculate_task_duration(),
            "tool_call_latencies": self._calculate_tool_latencies(),
            "time_to_first_tool_seconds": self._calculate_time_to_first_tool(),
            "tool_switching_overhead_seconds": self._calculate_tool_switching_overhead(),
            "total_tool_calls": len(self.tool_calls),
            "successful_tool_calls": sum(1 for c in self.tool_calls if c.success),
            "failed_tool_calls": sum(1 for c in self.tool_calls if not c.success),
        }

        # Add memory profile if available
        memory_profile = self._calculate_memory_profile()
        if memory_profile:
            report["memory_profile"] = memory_profile

        # Add infrastructure overhead
        if self.docker_startup_time is not None:
            report["docker_startup_seconds"] = self.docker_startup_time
        if self.docker_teardown_time is not None:
            report["docker_teardown_seconds"] = self.docker_teardown_time
        if self.mcp_server_startup_time is not None:
            report["mcp_server_startup_seconds"] = self.mcp_server_startup_time

        return report

    def get_insights(self) -> list[str]:
        """Generate actionable insights from profiling data.

        Returns:
            List of insight strings describing performance characteristics.
        """
        insights = []
        report = self.generate_report()

        # Identify slowest tools
        tool_latencies = report.get("tool_call_latencies", {})
        if tool_latencies:
            sorted_tools = sorted(
                tool_latencies.items(),
                key=lambda x: x[1]["avg_seconds"],
                reverse=True,
            )
            if sorted_tools:
                slowest_tool, stats = sorted_tools[0]
                insights.append(
                    f"{slowest_tool} is the slowest tool "
                    f"(avg: {stats['avg_seconds']:.1f}s, p95: {stats['p95_seconds']:.1f}s)"
                )

        # Infrastructure overhead
        docker_time = report.get("docker_startup_seconds")
        if docker_time and docker_time > 5:
            insights.append(f"Docker startup adds {docker_time:.1f}s overhead per task")

        mcp_time = report.get("mcp_server_startup_seconds")
        if mcp_time and mcp_time > 2:
            insights.append(f"MCP server initialization takes {mcp_time:.1f}s")

        # Tool discovery speed
        time_to_first = report.get("time_to_first_tool_seconds")
        if time_to_first is not None:
            if time_to_first < 5:
                insights.append(f"Fast tool discovery: first tool use in {time_to_first:.1f}s")
            elif time_to_first > 15:
                insights.append(f"Slow tool discovery: {time_to_first:.1f}s until first tool use")

        # Memory usage
        memory = report.get("memory_profile")
        if memory:
            peak_mb = memory.get("peak_rss_mb", 0)
            if peak_mb > 1000:
                insights.append(f"High memory usage: peak {peak_mb:.0f}MB")

        # Tool failure rate
        total_calls = report.get("total_tool_calls", 0)
        failed_calls = report.get("failed_tool_calls", 0)
        if total_calls > 0:
            failure_rate = failed_calls / total_calls
            if failure_rate > 0.1:
                insights.append(
                    f"High tool failure rate: {failure_rate:.1%} ({failed_calls}/{total_calls})"
                )

        return insights


def merge_profiling_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple profiling reports into aggregate statistics.

    Args:
        reports: List of individual task profiling reports.

    Returns:
        Aggregated profiling statistics.
    """
    if not reports:
        return {}

    # Aggregate tool latencies
    all_tool_latencies: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        tool_latencies = report.get("tool_call_latencies", {})
        for tool_name, stats in tool_latencies.items():
            if tool_name not in all_tool_latencies:
                all_tool_latencies[tool_name] = []
            all_tool_latencies[tool_name].append(stats)

    # Calculate aggregate tool statistics
    aggregated_tools = {}
    for tool_name, stats_list in all_tool_latencies.items():
        total_count = sum(s["count"] for s in stats_list)
        all_avg = [s["avg_seconds"] for s in stats_list]
        all_p95 = [s["p95_seconds"] for s in stats_list]
        all_p99 = [s["p99_seconds"] for s in stats_list]

        aggregated_tools[tool_name] = {
            "total_calls": total_count,
            "avg_seconds": statistics.mean(all_avg),
            "p95_seconds": statistics.mean(all_p95),
            "p99_seconds": statistics.mean(all_p99),
        }

    # Aggregate other metrics
    task_durations = [
        r.get("task_duration_seconds", 0) for r in reports if r.get("task_duration_seconds")
    ]
    time_to_first_tools = [
        r.get("time_to_first_tool_seconds", 0)
        for r in reports
        if r.get("time_to_first_tool_seconds") is not None
    ]

    aggregated = {
        "total_tasks": len(reports),
        "avg_task_duration_seconds": statistics.mean(task_durations) if task_durations else 0,
        "tool_latencies": aggregated_tools,
    }

    if time_to_first_tools:
        aggregated["avg_time_to_first_tool_seconds"] = statistics.mean(time_to_first_tools)

    # Aggregate infrastructure overhead
    docker_startups = [
        r.get("docker_startup_seconds") for r in reports if r.get("docker_startup_seconds")
    ]
    if docker_startups:
        aggregated["avg_docker_startup_seconds"] = statistics.mean(docker_startups)

    mcp_startups = [
        r.get("mcp_server_startup_seconds") for r in reports if r.get("mcp_server_startup_seconds")
    ]
    if mcp_startups:
        aggregated["avg_mcp_server_startup_seconds"] = statistics.mean(mcp_startups)

    return aggregated
