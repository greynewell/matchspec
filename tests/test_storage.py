"""Tests for storage backends."""

import tempfile
from pathlib import Path

import pytest

from mcpbr.storage.base import StorageBackend
from mcpbr.storage.sqlite_backend import SQLiteBackend


@pytest.fixture
async def sqlite_backend():
    """Create a temporary SQLite backend for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_results.db"
        backend = SQLiteBackend(db_path)
        await backend.initialize()
        yield backend
        await backend.close()


class TestSQLiteBackend:
    """Tests for SQLiteBackend."""

    async def test_is_storage_backend(self) -> None:
        """Test SQLiteBackend implements StorageBackend."""
        assert issubclass(SQLiteBackend, StorageBackend)

    async def test_initialize_creates_database(self) -> None:
        """Test initialize creates the database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backend = SQLiteBackend(db_path)
            await backend.initialize()
            assert db_path.exists()
            await backend.close()

    async def test_store_and_retrieve_run(self, sqlite_backend: SQLiteBackend) -> None:
        """Test storing and retrieving a run."""
        run_id = "test-run-001"
        config = {
            "benchmark": "swe-bench-lite",
            "model": "claude-sonnet-4-5-20250929",
            "provider": "anthropic",
        }
        results = {
            "summary": {"pass_rate": 0.75, "total_tasks": 4, "resolved_tasks": 3},
            "tasks": [
                {"instance_id": "task-1", "status": "resolved"},
                {"instance_id": "task-2", "status": "resolved"},
                {"instance_id": "task-3", "status": "resolved"},
                {"instance_id": "task-4", "status": "failed"},
            ],
        }

        stored_id = await sqlite_backend.store_run(run_id, config, results)
        assert stored_id == run_id

        run = await sqlite_backend.get_run(run_id)
        assert run is not None
        assert run["run_id"] == run_id
        assert run["benchmark"] == "swe-bench-lite"
        assert run["model"] == "claude-sonnet-4-5-20250929"
        assert run["pass_rate"] == 0.75
        assert run["total_tasks"] == 4
        assert run["resolved_tasks"] == 3

    async def test_get_nonexistent_run(self, sqlite_backend: SQLiteBackend) -> None:
        """Test retrieving a run that doesn't exist."""
        run = await sqlite_backend.get_run("nonexistent")
        assert run is None

    async def test_list_runs(self, sqlite_backend: SQLiteBackend) -> None:
        """Test listing runs."""
        for i in range(5):
            await sqlite_backend.store_run(
                f"run-{i}",
                {"benchmark": "gsm8k", "model": f"model-{i}", "provider": "anthropic"},
                {
                    "summary": {
                        "pass_rate": 0.5 + i * 0.1,
                        "total_tasks": 10,
                        "resolved_tasks": 5 + i,
                    }
                },
            )

        runs = await sqlite_backend.list_runs()
        assert len(runs) == 5

    async def test_list_runs_with_benchmark_filter(self, sqlite_backend: SQLiteBackend) -> None:
        """Test filtering runs by benchmark."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.5}, "tasks": []},
        )
        await sqlite_backend.store_run(
            "run-2",
            {"benchmark": "humaneval", "model": "m1", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.7}, "tasks": []},
        )

        runs = await sqlite_backend.list_runs(benchmark="gsm8k")
        assert len(runs) == 1
        assert runs[0]["benchmark"] == "gsm8k"

    async def test_list_runs_with_model_filter(self, sqlite_backend: SQLiteBackend) -> None:
        """Test filtering runs by model."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "claude-opus", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.5}, "tasks": []},
        )
        await sqlite_backend.store_run(
            "run-2",
            {"benchmark": "gsm8k", "model": "gpt-4", "provider": "openai"},
            {"summary": {"pass_rate": 0.7}, "tasks": []},
        )

        runs = await sqlite_backend.list_runs(model="claude-opus")
        assert len(runs) == 1
        assert runs[0]["model"] == "claude-opus"

    async def test_list_runs_with_limit(self, sqlite_backend: SQLiteBackend) -> None:
        """Test limiting number of runs returned."""
        for i in range(10):
            await sqlite_backend.store_run(
                f"run-{i}",
                {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
                {"summary": {}, "tasks": []},
            )

        runs = await sqlite_backend.list_runs(limit=3)
        assert len(runs) == 3

    async def test_store_task_result(self, sqlite_backend: SQLiteBackend) -> None:
        """Test storing individual task results."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {}, "tasks": []},
        )

        await sqlite_backend.store_task_result(
            "run-1",
            "task-1",
            {"status": "resolved", "duration_seconds": 45.0},
        )

        tasks = await sqlite_backend.get_task_results("run-1")
        assert len(tasks) == 1
        assert tasks[0]["status"] == "resolved"

    async def test_get_task_results_with_status_filter(self, sqlite_backend: SQLiteBackend) -> None:
        """Test filtering task results by status."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {
                "summary": {},
                "tasks": [
                    {"instance_id": "t1", "status": "resolved"},
                    {"instance_id": "t2", "status": "failed"},
                    {"instance_id": "t3", "status": "resolved"},
                ],
            },
        )

        resolved = await sqlite_backend.get_task_results("run-1", status="resolved")
        assert len(resolved) == 2

        failed = await sqlite_backend.get_task_results("run-1", status="failed")
        assert len(failed) == 1

    async def test_delete_run(self, sqlite_backend: SQLiteBackend) -> None:
        """Test deleting a run."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {}, "tasks": [{"instance_id": "t1", "status": "resolved"}]},
        )

        deleted = await sqlite_backend.delete_run("run-1")
        assert deleted is True

        run = await sqlite_backend.get_run("run-1")
        assert run is None

    async def test_delete_nonexistent_run(self, sqlite_backend: SQLiteBackend) -> None:
        """Test deleting a run that doesn't exist."""
        deleted = await sqlite_backend.delete_run("nonexistent")
        assert deleted is False

    async def test_get_stats(self, sqlite_backend: SQLiteBackend) -> None:
        """Test aggregate statistics."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.6, "total_tasks": 10, "resolved_tasks": 6}, "tasks": []},
        )
        await sqlite_backend.store_run(
            "run-2",
            {"benchmark": "gsm8k", "model": "m2", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.8, "total_tasks": 10, "resolved_tasks": 8}, "tasks": []},
        )

        stats = await sqlite_backend.get_stats()
        assert stats["total_runs"] == 2
        assert stats["avg_pass_rate"] == pytest.approx(0.7)
        assert stats["max_pass_rate"] == 0.8
        assert stats["min_pass_rate"] == 0.6
        assert stats["total_tasks_evaluated"] == 20
        assert stats["total_tasks_resolved"] == 14

    async def test_get_stats_with_benchmark_filter(self, sqlite_backend: SQLiteBackend) -> None:
        """Test statistics filtered by benchmark."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.6, "total_tasks": 10, "resolved_tasks": 6}, "tasks": []},
        )
        await sqlite_backend.store_run(
            "run-2",
            {"benchmark": "humaneval", "model": "m1", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.9, "total_tasks": 5, "resolved_tasks": 4}, "tasks": []},
        )

        stats = await sqlite_backend.get_stats(benchmark="gsm8k")
        assert stats["total_runs"] == 1
        assert stats["avg_pass_rate"] == 0.6

    async def test_get_stats_empty(self, sqlite_backend: SQLiteBackend) -> None:
        """Test statistics with no data."""
        stats = await sqlite_backend.get_stats()
        assert stats["total_runs"] == 0

    async def test_store_run_with_metadata(self, sqlite_backend: SQLiteBackend) -> None:
        """Test storing run with metadata."""
        metadata = {"git_hash": "abc123", "machine": "test-vm"}
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {}, "tasks": []},
            metadata=metadata,
        )

        run = await sqlite_backend.get_run("run-1")
        assert run is not None
        assert run["metadata"]["git_hash"] == "abc123"

    async def test_upsert_run(self, sqlite_backend: SQLiteBackend) -> None:
        """Test that storing a run with the same ID updates it."""
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.5}, "tasks": []},
        )
        await sqlite_backend.store_run(
            "run-1",
            {"benchmark": "gsm8k", "model": "m1", "provider": "anthropic"},
            {"summary": {"pass_rate": 0.8}, "tasks": []},
        )

        run = await sqlite_backend.get_run("run-1")
        assert run["pass_rate"] == 0.8

    async def test_default_db_path(self) -> None:
        """Test default database path is under ~/.mcpbr/."""
        backend = SQLiteBackend()
        assert str(backend.db_path).endswith("results.db")
        assert ".mcpbr" in str(backend.db_path)
