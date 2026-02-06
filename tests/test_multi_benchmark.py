"""Tests for the multi-benchmark runner module."""

import asyncio

import pytest

from mcpbr.multi_benchmark import (
    BenchmarkResult,
    BenchmarkRun,
    MultiBenchmarkResults,
    MultiBenchmarkRunner,
    partition_tasks,
)

# ===========================================================================
# BenchmarkRun dataclass tests
# ===========================================================================


class TestBenchmarkRun:
    """Tests for the BenchmarkRun dataclass."""

    def test_minimal_creation(self) -> None:
        """Test creating a BenchmarkRun with only required fields."""
        run = BenchmarkRun(benchmark="swe-bench-lite")
        assert run.benchmark == "swe-bench-lite"
        assert run.sample_size is None
        assert run.task_ids == []
        assert run.extra_config == {}

    def test_full_creation(self) -> None:
        """Test creating a BenchmarkRun with all fields."""
        run = BenchmarkRun(
            benchmark="humaneval",
            sample_size=50,
            task_ids=["task_1", "task_2"],
            extra_config={"timeout_seconds": 600},
        )
        assert run.benchmark == "humaneval"
        assert run.sample_size == 50
        assert run.task_ids == ["task_1", "task_2"]
        assert run.extra_config == {"timeout_seconds": 600}

    def test_task_ids_default_is_independent(self) -> None:
        """Test that default task_ids lists are independent across instances."""
        run_a = BenchmarkRun(benchmark="a")
        run_b = BenchmarkRun(benchmark="b")
        run_a.task_ids.append("id_1")
        assert run_b.task_ids == []

    def test_extra_config_default_is_independent(self) -> None:
        """Test that default extra_config dicts are independent across instances."""
        run_a = BenchmarkRun(benchmark="a")
        run_b = BenchmarkRun(benchmark="b")
        run_a.extra_config["key"] = "value"
        assert run_b.extra_config == {}


# ===========================================================================
# BenchmarkResult dataclass tests
# ===========================================================================


class TestBenchmarkResult:
    """Tests for the BenchmarkResult dataclass."""

    def test_defaults(self) -> None:
        """Test that BenchmarkResult has sensible defaults."""
        result = BenchmarkResult(benchmark="humaneval")
        assert result.benchmark == "humaneval"
        assert result.pass_rate is None
        assert result.total_tasks == 0
        assert result.resolved_tasks == 0
        assert result.duration_seconds == 0.0
        assert result.error is None
        assert result.results == {}

    def test_successful_result(self) -> None:
        """Test creating a successful benchmark result."""
        result = BenchmarkResult(
            benchmark="swe-bench-lite",
            pass_rate=0.75,
            total_tasks=100,
            resolved_tasks=75,
            duration_seconds=3600.0,
            results={"raw": "data"},
        )
        assert result.pass_rate == 0.75
        assert result.total_tasks == 100
        assert result.resolved_tasks == 75
        assert result.duration_seconds == 3600.0
        assert result.error is None
        assert result.results == {"raw": "data"}

    def test_error_result(self) -> None:
        """Test creating an error benchmark result."""
        result = BenchmarkResult(
            benchmark="gsm8k",
            error="Dataset download failed",
            duration_seconds=5.0,
        )
        assert result.error == "Dataset download failed"
        assert result.pass_rate is None
        assert result.total_tasks == 0

    def test_results_default_is_independent(self) -> None:
        """Test that default results dicts are independent across instances."""
        result_a = BenchmarkResult(benchmark="a")
        result_b = BenchmarkResult(benchmark="b")
        result_a.results["key"] = "value"
        assert result_b.results == {}


# ===========================================================================
# MultiBenchmarkResults tests
# ===========================================================================


class TestMultiBenchmarkResults:
    """Tests for MultiBenchmarkResults and its summary property."""

    def test_empty_results(self) -> None:
        """Test summary with no benchmarks."""
        results = MultiBenchmarkResults()
        summary = results.summary
        assert summary["total_benchmarks"] == 0
        assert summary["successful"] == 0
        assert summary["failed"] == 0
        assert summary["avg_pass_rate"] == 0
        assert summary["total_tasks"] == 0
        assert summary["total_resolved"] == 0
        assert summary["total_duration_seconds"] == 0.0

    def test_all_successful(self) -> None:
        """Test summary when all benchmarks succeed."""
        results = MultiBenchmarkResults(
            benchmarks=[
                BenchmarkResult(
                    benchmark="a",
                    pass_rate=0.80,
                    total_tasks=100,
                    resolved_tasks=80,
                ),
                BenchmarkResult(
                    benchmark="b",
                    pass_rate=0.60,
                    total_tasks=50,
                    resolved_tasks=30,
                ),
            ],
            total_duration_seconds=120.0,
        )
        summary = results.summary
        assert summary["total_benchmarks"] == 2
        assert summary["successful"] == 2
        assert summary["failed"] == 0
        assert summary["avg_pass_rate"] == pytest.approx(0.70)
        assert summary["total_tasks"] == 150
        assert summary["total_resolved"] == 110
        assert summary["total_duration_seconds"] == 120.0

    def test_some_failures(self) -> None:
        """Test summary when some benchmarks fail."""
        results = MultiBenchmarkResults(
            benchmarks=[
                BenchmarkResult(
                    benchmark="good",
                    pass_rate=0.90,
                    total_tasks=10,
                    resolved_tasks=9,
                ),
                BenchmarkResult(
                    benchmark="bad",
                    error="timeout",
                    total_tasks=5,
                    resolved_tasks=0,
                ),
            ],
        )
        summary = results.summary
        assert summary["total_benchmarks"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1
        # avg_pass_rate only considers successful benchmarks
        assert summary["avg_pass_rate"] == pytest.approx(0.90)
        # total_tasks includes all benchmarks (even failed ones)
        assert summary["total_tasks"] == 15
        assert summary["total_resolved"] == 9

    def test_all_failures(self) -> None:
        """Test summary when all benchmarks fail."""
        results = MultiBenchmarkResults(
            benchmarks=[
                BenchmarkResult(benchmark="fail1", error="err1"),
                BenchmarkResult(benchmark="fail2", error="err2"),
            ],
        )
        summary = results.summary
        assert summary["total_benchmarks"] == 2
        assert summary["successful"] == 0
        assert summary["failed"] == 2
        assert summary["avg_pass_rate"] == 0

    def test_pass_rate_none_treated_as_zero(self) -> None:
        """Test that pass_rate=None in successful results is treated as 0.0."""
        results = MultiBenchmarkResults(
            benchmarks=[
                BenchmarkResult(benchmark="a", pass_rate=None, total_tasks=10),
            ],
        )
        summary = results.summary
        # No error, so it counts as successful
        assert summary["successful"] == 1
        # pass_rate None -> 0 in the sum
        assert summary["avg_pass_rate"] == 0.0


# ===========================================================================
# MultiBenchmarkRunner initialization tests
# ===========================================================================


class TestMultiBenchmarkRunnerInit:
    """Tests for MultiBenchmarkRunner initialization."""

    def test_default_init(self) -> None:
        """Test default initialization values."""
        runner = MultiBenchmarkRunner(base_config={"model": "sonnet"})
        assert runner.base_config == {"model": "sonnet"}
        assert runner.max_concurrent == 2

    def test_custom_max_concurrent(self) -> None:
        """Test setting custom max_concurrent."""
        runner = MultiBenchmarkRunner(base_config={}, max_concurrent=5)
        assert runner.max_concurrent == 5

    def test_max_concurrent_zero_raises(self) -> None:
        """Test that max_concurrent=0 raises ValueError."""
        with pytest.raises(ValueError, match="max_concurrent must be >= 1"):
            MultiBenchmarkRunner(base_config={}, max_concurrent=0)

    def test_max_concurrent_negative_raises(self) -> None:
        """Test that negative max_concurrent raises ValueError."""
        with pytest.raises(ValueError, match="max_concurrent must be >= 1"):
            MultiBenchmarkRunner(base_config={}, max_concurrent=-1)

    def test_base_config_stored_as_is(self) -> None:
        """Test that base_config is stored without modification."""
        config = {"model": "sonnet", "timeout": 300}
        runner = MultiBenchmarkRunner(base_config=config)
        assert runner.base_config is config


# ===========================================================================
# MultiBenchmarkRunner.run tests
# ===========================================================================


class TestMultiBenchmarkRunnerRun:
    """Tests for the async run method."""

    def test_run_empty_benchmarks(self) -> None:
        """Test running with no benchmarks returns empty results."""
        runner = MultiBenchmarkRunner(base_config={})
        results = asyncio.run(runner.run([]))
        assert results.benchmarks == []
        assert results.total_duration_seconds == 0.0

    def test_run_single_benchmark(self) -> None:
        """Test running a single benchmark."""
        runner = MultiBenchmarkRunner(base_config={})
        benchmarks = [BenchmarkRun(benchmark="humaneval")]
        results = asyncio.run(runner.run(benchmarks))
        assert len(results.benchmarks) == 1
        assert results.benchmarks[0].benchmark == "humaneval"
        assert results.benchmarks[0].error is None
        assert results.total_duration_seconds >= 0

    def test_run_multiple_benchmarks(self) -> None:
        """Test running multiple benchmarks."""
        runner = MultiBenchmarkRunner(base_config={}, max_concurrent=3)
        benchmarks = [
            BenchmarkRun(benchmark="humaneval"),
            BenchmarkRun(benchmark="gsm8k"),
            BenchmarkRun(benchmark="mbpp"),
        ]
        results = asyncio.run(runner.run(benchmarks))
        assert len(results.benchmarks) == 3
        benchmark_names = {r.benchmark for r in results.benchmarks}
        assert benchmark_names == {"humaneval", "gsm8k", "mbpp"}

    def test_run_records_duration(self) -> None:
        """Test that total_duration_seconds is populated."""
        runner = MultiBenchmarkRunner(base_config={})
        benchmarks = [BenchmarkRun(benchmark="a")]
        results = asyncio.run(runner.run(benchmarks))
        assert results.total_duration_seconds >= 0

    def test_run_flags_passed_through(self) -> None:
        """Test that run_mcp and run_baseline flags don't cause errors."""
        runner = MultiBenchmarkRunner(base_config={})
        benchmarks = [BenchmarkRun(benchmark="test")]
        # Should not raise regardless of flag values
        results = asyncio.run(runner.run(benchmarks, run_mcp=False, run_baseline=True))
        assert len(results.benchmarks) == 1


# ===========================================================================
# partition_tasks tests
# ===========================================================================


class TestPartitionTasks:
    """Tests for the partition_tasks utility function."""

    def test_even_split(self) -> None:
        """Test partitioning tasks that divide evenly."""
        task_ids = ["t1", "t2", "t3", "t4", "t5", "t6"]
        partitions = partition_tasks(task_ids, 3)
        assert len(partitions) == 3
        assert all(len(p) == 2 for p in partitions)
        # All tasks are present
        all_ids = [tid for p in partitions for tid in p]
        assert sorted(all_ids) == sorted(task_ids)

    def test_uneven_split(self) -> None:
        """Test partitioning tasks that don't divide evenly."""
        task_ids = ["t1", "t2", "t3", "t4", "t5"]
        partitions = partition_tasks(task_ids, 3)
        assert len(partitions) == 3
        sizes = sorted([len(p) for p in partitions], reverse=True)
        assert sizes == [2, 2, 1]
        # All tasks preserved
        all_ids = [tid for p in partitions for tid in p]
        assert sorted(all_ids) == sorted(task_ids)

    def test_single_partition(self) -> None:
        """Test partitioning into a single partition returns all tasks."""
        task_ids = ["t1", "t2", "t3"]
        partitions = partition_tasks(task_ids, 1)
        assert len(partitions) == 1
        assert partitions[0] == task_ids

    def test_more_partitions_than_tasks(self) -> None:
        """Test partitioning with more partitions than tasks."""
        task_ids = ["t1", "t2"]
        partitions = partition_tasks(task_ids, 5)
        assert len(partitions) == 5
        non_empty = [p for p in partitions if p]
        assert len(non_empty) == 2
        # All tasks preserved
        all_ids = [tid for p in partitions for tid in p]
        assert sorted(all_ids) == sorted(task_ids)

    def test_empty_task_list(self) -> None:
        """Test partitioning an empty list returns empty partitions."""
        partitions = partition_tasks([], 3)
        assert len(partitions) == 3
        assert all(p == [] for p in partitions)

    def test_zero_partitions_raises(self) -> None:
        """Test that zero partitions raises ValueError."""
        with pytest.raises(ValueError, match="num_partitions must be >= 1"):
            partition_tasks(["t1"], 0)

    def test_negative_partitions_raises(self) -> None:
        """Test that negative partitions raises ValueError."""
        with pytest.raises(ValueError, match="num_partitions must be >= 1"):
            partition_tasks(["t1"], -1)

    def test_preserves_all_task_ids(self) -> None:
        """Test that all task IDs appear exactly once across partitions."""
        task_ids = [f"task_{i}" for i in range(17)]
        partitions = partition_tasks(task_ids, 4)
        all_ids = [tid for p in partitions for tid in p]
        assert sorted(all_ids) == sorted(task_ids)

    def test_single_task_single_partition(self) -> None:
        """Test partitioning a single task into one partition."""
        partitions = partition_tasks(["only"], 1)
        assert partitions == [["only"]]

    def test_round_robin_distribution(self) -> None:
        """Test that tasks are distributed round-robin across partitions."""
        task_ids = ["a", "b", "c", "d", "e"]
        partitions = partition_tasks(task_ids, 3)
        # Round-robin: a->0, b->1, c->2, d->0, e->1
        assert partitions[0] == ["a", "d"]
        assert partitions[1] == ["b", "e"]
        assert partitions[2] == ["c"]
