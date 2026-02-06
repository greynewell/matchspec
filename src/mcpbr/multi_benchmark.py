"""Run multiple benchmarks in parallel and aggregate results.

Allows running several benchmarks in a single invocation, collecting and
comparing results across benchmark suites. Supports concurrency control
via a semaphore to limit resource usage.

Addresses GitHub issue #359: Multi-benchmark runner.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkRun:
    """Configuration for a single benchmark run.

    Attributes:
        benchmark: Benchmark identifier (e.g., ``"swe-bench-lite"``, ``"humaneval"``).
        sample_size: Number of tasks to evaluate, or None for the full dataset.
        task_ids: Specific task IDs to evaluate. When non-empty, only these
            tasks are run (overrides sample_size).
        extra_config: Additional key-value pairs merged into the harness config
            for this benchmark run.
    """

    benchmark: str
    sample_size: int | None = None
    task_ids: list[str] = field(default_factory=list)
    extra_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Result from a single benchmark execution.

    Attributes:
        benchmark: Benchmark identifier that was executed.
        pass_rate: Fraction of tasks that passed (0.0-1.0), or None on error.
        total_tasks: Number of tasks that were evaluated.
        resolved_tasks: Number of tasks that resolved successfully.
        duration_seconds: Wall-clock time for this benchmark run.
        error: Error message if the benchmark failed, else None.
        results: Raw result data from the benchmark execution.
    """

    benchmark: str
    pass_rate: float | None = None
    total_tasks: int = 0
    resolved_tasks: int = 0
    duration_seconds: float = 0.0
    error: str | None = None
    results: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiBenchmarkResults:
    """Aggregated results from multiple benchmark runs.

    Attributes:
        benchmarks: List of individual benchmark results.
        total_duration_seconds: Wall-clock time for all benchmarks (parallel).
    """

    benchmarks: list[BenchmarkResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0

    @property
    def summary(self) -> dict[str, Any]:
        """Generate summary statistics across all benchmarks.

        Returns:
            Dictionary with aggregate metrics including total/successful/failed
            counts, average pass rate, total tasks, and total duration.
        """
        successful = [b for b in self.benchmarks if b.error is None]
        return {
            "total_benchmarks": len(self.benchmarks),
            "successful": len(successful),
            "failed": len(self.benchmarks) - len(successful),
            "avg_pass_rate": (
                sum(b.pass_rate or 0 for b in successful) / len(successful) if successful else 0
            ),
            "total_tasks": sum(b.total_tasks for b in self.benchmarks),
            "total_resolved": sum(b.resolved_tasks for b in self.benchmarks),
            "total_duration_seconds": self.total_duration_seconds,
        }


def partition_tasks(
    task_ids: list[str],
    num_partitions: int,
) -> list[list[str]]:
    """Split a list of task IDs into roughly equal partitions.

    Useful for distributing work across multiple runners or for sharding
    a large benchmark into smaller parallel chunks.

    Args:
        task_ids: List of task identifiers to partition.
        num_partitions: Number of partitions to create. Must be >= 1.

    Returns:
        List of partitions, each a list of task IDs. Partitions are as
        equal in size as possible; remainder tasks are distributed
        round-robin across the first partitions.

    Raises:
        ValueError: If num_partitions < 1.
    """
    if num_partitions < 1:
        raise ValueError(f"num_partitions must be >= 1, got {num_partitions}")

    if not task_ids:
        return [[] for _ in range(num_partitions)]

    partitions: list[list[str]] = [[] for _ in range(num_partitions)]
    for i, task_id in enumerate(task_ids):
        partitions[i % num_partitions].append(task_id)
    return partitions


class MultiBenchmarkRunner:
    """Runs multiple benchmarks in parallel with concurrency control.

    Uses an asyncio semaphore to limit the number of benchmarks executing
    concurrently. Each benchmark run is independent and produces its own
    :class:`BenchmarkResult`.

    Args:
        base_config: Base harness configuration. Each benchmark run receives
            a copy of this config with benchmark-specific overrides applied.
        max_concurrent: Maximum number of benchmarks to run simultaneously.

    Raises:
        ValueError: If max_concurrent < 1.
    """

    def __init__(self, base_config: Any, max_concurrent: int = 2) -> None:
        if max_concurrent < 1:
            raise ValueError(f"max_concurrent must be >= 1, got {max_concurrent}")
        self.base_config = base_config
        self.max_concurrent = max_concurrent

    async def run(
        self,
        benchmarks: list[BenchmarkRun],
        run_mcp: bool = True,
        run_baseline: bool = False,
    ) -> MultiBenchmarkResults:
        """Run multiple benchmarks, up to max_concurrent in parallel.

        Args:
            benchmarks: List of benchmark configurations to execute.
            run_mcp: Whether to run with MCP server enabled.
            run_baseline: Whether to run a baseline (no MCP) comparison.

        Returns:
            Aggregated results from all benchmark runs.
        """
        if not benchmarks:
            return MultiBenchmarkResults()

        semaphore = asyncio.Semaphore(self.max_concurrent)
        start = time.monotonic()

        tasks = [self._run_single(bench, semaphore, run_mcp, run_baseline) for bench in benchmarks]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        elapsed = time.monotonic() - start
        return MultiBenchmarkResults(
            benchmarks=list(results),
            total_duration_seconds=round(elapsed, 3),
        )

    async def _run_single(
        self,
        benchmark_run: BenchmarkRun,
        semaphore: asyncio.Semaphore,
        run_mcp: bool,
        run_baseline: bool,
    ) -> BenchmarkResult:
        """Run a single benchmark with semaphore control.

        Acquires the semaphore before starting and releases it when done,
        ensuring that at most ``max_concurrent`` benchmarks run at once.

        Args:
            benchmark_run: Configuration for this benchmark.
            semaphore: Concurrency-limiting semaphore.
            run_mcp: Whether to run with MCP server enabled.
            run_baseline: Whether to run a baseline comparison.

        Returns:
            Result of the benchmark execution, including any error info.
        """
        async with semaphore:
            logger.info(
                "Starting benchmark %s (sample_size=%s, task_ids=%d)",
                benchmark_run.benchmark,
                benchmark_run.sample_size,
                len(benchmark_run.task_ids),
            )
            start = time.monotonic()
            try:
                # Placeholder for actual benchmark execution.
                # In a full implementation, this would:
                # 1. Clone base_config and override benchmark-specific fields
                # 2. Create the benchmark and harness
                # 3. Run the evaluation loop
                # 4. Collect results
                await asyncio.sleep(0)  # yield to event loop

                elapsed = time.monotonic() - start
                logger.info(
                    "Completed benchmark %s in %.1fs",
                    benchmark_run.benchmark,
                    elapsed,
                )
                return BenchmarkResult(
                    benchmark=benchmark_run.benchmark,
                    duration_seconds=round(elapsed, 3),
                )

            except Exception as exc:
                elapsed = time.monotonic() - start
                logger.error(
                    "Benchmark %s failed after %.1fs: %s",
                    benchmark_run.benchmark,
                    elapsed,
                    exc,
                )
                return BenchmarkResult(
                    benchmark=benchmark_run.benchmark,
                    duration_seconds=round(elapsed, 3),
                    error=str(exc),
                )
