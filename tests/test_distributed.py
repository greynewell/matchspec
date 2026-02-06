"""Tests for the distributed execution coordinator module."""

import pytest

from mcpbr.config import HarnessConfig
from mcpbr.distributed import (
    SUPPORTED_PROVIDERS,
    DistributedCoordinator,
    TaskPartitioner,
    WorkerResult,
)

# ===========================================================================
# TaskPartitioner.partition tests
# ===========================================================================


class TestPartition:
    """Tests for TaskPartitioner.partition."""

    def test_even_split(self) -> None:
        """Test even distribution of tasks across workers."""
        ids = ["t1", "t2", "t3", "t4"]
        result = TaskPartitioner.partition(ids, 2)
        assert len(result) == 2
        assert sorted(result[0] + result[1]) == sorted(ids)
        # Each worker gets exactly 2 tasks
        assert len(result[0]) == 2
        assert len(result[1]) == 2

    def test_uneven_split(self) -> None:
        """Test that extra tasks are distributed across earlier workers."""
        ids = ["t1", "t2", "t3", "t4", "t5"]
        result = TaskPartitioner.partition(ids, 3)
        assert len(result) == 3
        sizes = sorted([len(p) for p in result], reverse=True)
        # 5 tasks / 3 workers -> 2, 2, 1
        assert sizes == [2, 2, 1]
        # All tasks preserved
        all_ids = []
        for p in result:
            all_ids.extend(p)
        assert sorted(all_ids) == sorted(ids)

    def test_single_worker(self) -> None:
        """Test all tasks go to a single worker."""
        ids = ["t1", "t2", "t3"]
        result = TaskPartitioner.partition(ids, 1)
        assert len(result) == 1
        assert result[0] == ids

    def test_empty_list(self) -> None:
        """Test partitioning an empty task list returns empty partitions."""
        result = TaskPartitioner.partition([], 3)
        assert len(result) == 3
        assert all(p == [] for p in result)

    def test_more_workers_than_tasks(self) -> None:
        """Test that extra workers are omitted when tasks < workers."""
        ids = ["t1", "t2"]
        result = TaskPartitioner.partition(ids, 5)
        # Only 2 non-empty partitions are returned
        assert len(result) == 2
        assert all(len(p) == 1 for p in result)
        all_ids = []
        for p in result:
            all_ids.extend(p)
        assert sorted(all_ids) == sorted(ids)

    def test_single_task_single_worker(self) -> None:
        """Test one task with one worker."""
        result = TaskPartitioner.partition(["t1"], 1)
        assert result == [["t1"]]

    def test_single_task_multiple_workers(self) -> None:
        """Test one task distributed across multiple workers."""
        result = TaskPartitioner.partition(["t1"], 4)
        assert len(result) == 1
        assert result[0] == ["t1"]

    def test_invalid_num_workers_zero(self) -> None:
        """Test that num_workers=0 raises ValueError."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            TaskPartitioner.partition(["t1"], 0)

    def test_invalid_num_workers_negative(self) -> None:
        """Test that negative num_workers raises ValueError."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            TaskPartitioner.partition(["t1"], -1)

    def test_large_partition(self) -> None:
        """Test partitioning a large number of tasks."""
        ids = [f"task_{i}" for i in range(100)]
        result = TaskPartitioner.partition(ids, 7)
        assert len(result) == 7
        total = sum(len(p) for p in result)
        assert total == 100
        # Check all IDs preserved
        all_ids = []
        for p in result:
            all_ids.extend(p)
        assert sorted(all_ids) == sorted(ids)

    def test_preserves_order(self) -> None:
        """Test that round-robin assignment preserves relative order per worker."""
        ids = ["a", "b", "c", "d", "e", "f"]
        result = TaskPartitioner.partition(ids, 3)
        # Worker 0 gets indices 0,3 -> ["a", "d"]
        # Worker 1 gets indices 1,4 -> ["b", "e"]
        # Worker 2 gets indices 2,5 -> ["c", "f"]
        assert result[0] == ["a", "d"]
        assert result[1] == ["b", "e"]
        assert result[2] == ["c", "f"]


# ===========================================================================
# TaskPartitioner.partition_by_difficulty tests
# ===========================================================================


class TestPartitionByDifficulty:
    """Tests for TaskPartitioner.partition_by_difficulty."""

    def test_balanced_by_difficulty(self) -> None:
        """Test that tasks are balanced by difficulty weight."""
        tasks = [
            {"instance_id": "easy1", "difficulty": 1},
            {"instance_id": "easy2", "difficulty": 1},
            {"instance_id": "hard1", "difficulty": 10},
            {"instance_id": "hard2", "difficulty": 10},
        ]
        result = TaskPartitioner.partition_by_difficulty(tasks, 2)
        assert len(result) == 2
        # Each worker should get one hard and one easy task for balance
        all_ids = []
        for p in result:
            all_ids.extend(p)
        assert sorted(all_ids) == ["easy1", "easy2", "hard1", "hard2"]

    def test_empty_tasks(self) -> None:
        """Test partitioning empty task list by difficulty."""
        result = TaskPartitioner.partition_by_difficulty([], 3)
        assert len(result) == 3
        assert all(p == [] for p in result)

    def test_uses_estimated_cost_fallback(self) -> None:
        """Test that estimated_cost is used when difficulty is absent."""
        tasks = [
            {"instance_id": "t1", "estimated_cost": 5.0},
            {"instance_id": "t2", "estimated_cost": 3.0},
            {"instance_id": "t3", "estimated_cost": 1.0},
        ]
        result = TaskPartitioner.partition_by_difficulty(tasks, 2)
        assert len(result) == 2
        all_ids = []
        for p in result:
            all_ids.extend(p)
        assert sorted(all_ids) == ["t1", "t2", "t3"]

    def test_default_weight_when_no_fields(self) -> None:
        """Test that tasks without difficulty or cost use weight 1.0."""
        tasks = [
            {"instance_id": "t1"},
            {"instance_id": "t2"},
            {"instance_id": "t3"},
            {"instance_id": "t4"},
        ]
        result = TaskPartitioner.partition_by_difficulty(tasks, 2)
        assert len(result) == 2
        # All equal weight -> 2 tasks per worker
        sizes = sorted([len(p) for p in result])
        assert sizes == [2, 2]

    def test_more_workers_than_tasks(self) -> None:
        """Test difficulty partitioning with more workers than tasks."""
        tasks = [{"instance_id": "t1", "difficulty": 5}]
        result = TaskPartitioner.partition_by_difficulty(tasks, 5)
        assert len(result) == 1
        assert result[0] == ["t1"]

    def test_invalid_num_workers(self) -> None:
        """Test that num_workers < 1 raises ValueError."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            TaskPartitioner.partition_by_difficulty([{"instance_id": "t1"}], 0)


# ===========================================================================
# WorkerResult tests
# ===========================================================================


class TestWorkerResult:
    """Tests for the WorkerResult dataclass."""

    def test_default_construction(self) -> None:
        """Test WorkerResult with only required fields."""
        wr = WorkerResult(worker_id="w0")
        assert wr.worker_id == "w0"
        assert wr.task_results == []
        assert wr.duration_seconds == 0.0
        assert wr.error is None

    def test_full_construction(self) -> None:
        """Test WorkerResult with all fields populated."""
        wr = WorkerResult(
            worker_id="w1",
            task_results=[{"instance_id": "t1", "mcp": {"resolved": True}}],
            duration_seconds=42.5,
            error=None,
        )
        assert wr.worker_id == "w1"
        assert len(wr.task_results) == 1
        assert wr.duration_seconds == 42.5
        assert wr.error is None

    def test_error_state(self) -> None:
        """Test WorkerResult representing a failed worker."""
        wr = WorkerResult(
            worker_id="w-err",
            duration_seconds=1.0,
            error="Connection refused",
        )
        assert wr.error == "Connection refused"
        assert wr.task_results == []


# ===========================================================================
# DistributedCoordinator.merge_results tests
# ===========================================================================


class TestMergeResults:
    """Tests for DistributedCoordinator.merge_results."""

    def test_merge_empty(self) -> None:
        """Test merging zero worker results."""
        merged = DistributedCoordinator.merge_results([])
        assert merged["total_tasks"] == 0
        assert merged["total_resolved"] == 0
        assert merged["resolution_rate"] == 0.0
        assert merged["total_cost"] == 0.0
        assert merged["worker_count"] == 0
        assert merged["errors"] == []

    def test_merge_single_worker(self) -> None:
        """Test merging a single worker's results."""
        wr = WorkerResult(
            worker_id="w0",
            task_results=[
                {
                    "instance_id": "t1",
                    "mcp": {
                        "resolved": True,
                        "cost": 0.05,
                        "tokens": {"input": 100, "output": 50},
                    },
                },
                {
                    "instance_id": "t2",
                    "mcp": {
                        "resolved": False,
                        "cost": 0.03,
                        "tokens": {"input": 80, "output": 40},
                    },
                },
            ],
            duration_seconds=10.0,
        )
        merged = DistributedCoordinator.merge_results([wr])
        assert merged["total_tasks"] == 2
        assert merged["total_resolved"] == 1
        assert merged["resolution_rate"] == 0.5
        assert abs(merged["total_cost"] - 0.08) < 1e-9
        assert merged["total_tokens_in"] == 180
        assert merged["total_tokens_out"] == 90
        assert merged["worker_count"] == 1
        assert merged["max_duration_seconds"] == 10.0
        assert merged["errors"] == []

    def test_merge_multiple_workers(self) -> None:
        """Test merging results from multiple workers."""
        wr1 = WorkerResult(
            worker_id="w0",
            task_results=[
                {
                    "instance_id": "t1",
                    "mcp": {
                        "resolved": True,
                        "cost": 0.10,
                        "tokens": {"input": 200, "output": 100},
                    },
                },
            ],
            duration_seconds=5.0,
        )
        wr2 = WorkerResult(
            worker_id="w1",
            task_results=[
                {
                    "instance_id": "t2",
                    "mcp": {
                        "resolved": True,
                        "cost": 0.15,
                        "tokens": {"input": 300, "output": 150},
                    },
                },
                {
                    "instance_id": "t3",
                    "mcp": {
                        "resolved": False,
                        "cost": 0.05,
                        "tokens": {"input": 50, "output": 25},
                    },
                },
            ],
            duration_seconds=8.0,
        )
        merged = DistributedCoordinator.merge_results([wr1, wr2])
        assert merged["total_tasks"] == 3
        assert merged["total_resolved"] == 2
        assert abs(merged["total_cost"] - 0.30) < 1e-9
        assert merged["total_tokens_in"] == 550
        assert merged["total_tokens_out"] == 275
        assert merged["worker_count"] == 2
        assert merged["total_duration_seconds"] == 13.0
        assert merged["max_duration_seconds"] == 8.0
        assert merged["errors"] == []

    def test_merge_with_errors(self) -> None:
        """Test merging when some workers had errors."""
        wr_ok = WorkerResult(
            worker_id="w0",
            task_results=[
                {"instance_id": "t1", "mcp": {"resolved": True, "cost": 0.01}},
            ],
            duration_seconds=3.0,
        )
        wr_err = WorkerResult(
            worker_id="w1",
            duration_seconds=0.5,
            error="Timeout waiting for cloud instance",
        )
        merged = DistributedCoordinator.merge_results([wr_ok, wr_err])
        assert merged["total_tasks"] == 1
        assert merged["total_resolved"] == 1
        assert len(merged["errors"]) == 1
        assert merged["errors"][0]["worker_id"] == "w1"
        assert "Timeout" in merged["errors"][0]["error"]

    def test_merge_with_baseline_results(self) -> None:
        """Test merging aggregates baseline cost and tokens."""
        wr = WorkerResult(
            worker_id="w0",
            task_results=[
                {
                    "instance_id": "t1",
                    "mcp": {
                        "resolved": True,
                        "cost": 0.10,
                        "tokens": {"input": 100, "output": 50},
                    },
                    "baseline": {
                        "resolved": False,
                        "cost": 0.08,
                        "tokens": {"input": 90, "output": 45},
                    },
                },
            ],
            duration_seconds=6.0,
        )
        merged = DistributedCoordinator.merge_results([wr])
        assert merged["total_tasks"] == 1
        assert merged["total_resolved"] == 1  # Only MCP resolved counts
        # Cost includes both MCP and baseline
        assert abs(merged["total_cost"] - 0.18) < 1e-9
        assert merged["total_tokens_in"] == 190
        assert merged["total_tokens_out"] == 95

    def test_merge_with_none_cost(self) -> None:
        """Test merging handles None cost gracefully."""
        wr = WorkerResult(
            worker_id="w0",
            task_results=[
                {
                    "instance_id": "t1",
                    "mcp": {
                        "resolved": False,
                        "cost": None,
                        "tokens": {"input": 10, "output": 5},
                    },
                },
            ],
            duration_seconds=1.0,
        )
        merged = DistributedCoordinator.merge_results([wr])
        assert merged["total_cost"] == 0.0

    def test_merge_no_mcp_field(self) -> None:
        """Test merging task results that lack mcp/baseline fields entirely."""
        wr = WorkerResult(
            worker_id="w0",
            task_results=[{"instance_id": "t1"}],
            duration_seconds=1.0,
        )
        merged = DistributedCoordinator.merge_results([wr])
        assert merged["total_tasks"] == 1
        assert merged["total_resolved"] == 0
        assert merged["total_cost"] == 0.0


# ===========================================================================
# DistributedCoordinator initialization tests
# ===========================================================================


class TestDistributedCoordinatorInit:
    """Tests for DistributedCoordinator construction and properties."""

    @pytest.fixture()
    def minimal_config(self) -> HarnessConfig:
        """Create a minimal HarnessConfig for testing."""
        from mcpbr.config import MCPServerConfig

        return HarnessConfig(
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            ),
        )

    def test_basic_init(self, minimal_config: HarnessConfig) -> None:
        """Test basic coordinator initialization."""
        coord = DistributedCoordinator(minimal_config, num_workers=4)
        assert coord.num_workers == 4
        assert coord.provider == "local"
        assert coord.config is minimal_config

    def test_default_num_workers(self, minimal_config: HarnessConfig) -> None:
        """Test that default num_workers is 2."""
        coord = DistributedCoordinator(minimal_config)
        assert coord.num_workers == 2

    def test_invalid_num_workers(self, minimal_config: HarnessConfig) -> None:
        """Test that num_workers < 1 raises ValueError."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            DistributedCoordinator(minimal_config, num_workers=0)

    def test_negative_num_workers(self, minimal_config: HarnessConfig) -> None:
        """Test that negative num_workers raises ValueError."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            DistributedCoordinator(minimal_config, num_workers=-3)

    def test_provider_from_config(self) -> None:
        """Test that provider is read from infrastructure config."""
        from mcpbr.config import InfrastructureConfig, MCPServerConfig

        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="echo", args=["test"]),
            infrastructure=InfrastructureConfig(mode="local"),
        )
        coord = DistributedCoordinator(config, num_workers=2)
        assert coord.provider == "local"


# ===========================================================================
# DistributedCoordinator.run tests (with empty task list)
# ===========================================================================


class TestDistributedCoordinatorRun:
    """Tests for DistributedCoordinator.run with edge cases."""

    @pytest.fixture()
    def minimal_config(self) -> HarnessConfig:
        """Create a minimal HarnessConfig for testing."""
        from mcpbr.config import MCPServerConfig

        return HarnessConfig(
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            ),
        )

    @pytest.mark.asyncio
    async def test_run_with_no_tasks_returns_empty(self, minimal_config: HarnessConfig) -> None:
        """Test that running with no tasks returns empty results."""
        coord = DistributedCoordinator(minimal_config, num_workers=2)
        results = await coord.run(task_ids=[])
        assert results.tasks == []
        assert results.metadata["distributed"] is True


# ===========================================================================
# Module-level constants
# ===========================================================================


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_supported_providers(self) -> None:
        """Test that SUPPORTED_PROVIDERS contains expected values."""
        assert "local" in SUPPORTED_PROVIDERS
        assert "aws" in SUPPORTED_PROVIDERS
        assert "gcp" in SUPPORTED_PROVIDERS
        assert "kubernetes" in SUPPORTED_PROVIDERS
        assert "azure" in SUPPORTED_PROVIDERS

    def test_supported_providers_is_tuple(self) -> None:
        """Test that SUPPORTED_PROVIDERS is immutable (tuple)."""
        assert isinstance(SUPPORTED_PROVIDERS, tuple)
