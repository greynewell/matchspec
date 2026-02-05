"""Tests for graceful degradation module."""

# ruff: noqa: N801

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from mcpbr.graceful_degradation import (
    ExecutionCheckpoint,
    FailureType,
    GracefulExecutor,
    TaskFailure,
    classify_failure,
)


class TestFailureType:
    """Tests for FailureType enum."""

    def test_transient_value(self) -> None:
        """Test transient failure type value."""
        assert FailureType.TRANSIENT.value == "transient"

    def test_permanent_value(self) -> None:
        """Test permanent failure type value."""
        assert FailureType.PERMANENT.value == "permanent"

    def test_unknown_value(self) -> None:
        """Test unknown failure type value."""
        assert FailureType.UNKNOWN.value == "unknown"


class TestTaskFailure:
    """Tests for TaskFailure dataclass."""

    def test_creation(self) -> None:
        """Test creating a TaskFailure."""
        failure = TaskFailure(
            task_id="task-1",
            error="Connection reset",
            failure_type=FailureType.TRANSIENT,
            timestamp="2024-01-01T00:00:00Z",
        )
        assert failure.task_id == "task-1"
        assert failure.error == "Connection reset"
        assert failure.failure_type == FailureType.TRANSIENT
        assert failure.retryable is True

    def test_non_retryable(self) -> None:
        """Test creating a non-retryable TaskFailure."""
        failure = TaskFailure(
            task_id="task-2",
            error="Invalid config",
            failure_type=FailureType.PERMANENT,
            timestamp="2024-01-01T00:00:00Z",
            retryable=False,
        )
        assert failure.retryable is False
        assert failure.failure_type == FailureType.PERMANENT


class TestClassifyFailure:
    """Tests for classify_failure function."""

    def test_timeout_is_transient(self) -> None:
        """Test that timeout errors are classified as transient."""
        error = TimeoutError("Connection timed out")
        result = classify_failure(error)
        assert result == FailureType.TRANSIENT

    def test_connection_error_is_transient(self) -> None:
        """Test that connection errors are classified as transient."""
        error = ConnectionError("Connection refused")
        result = classify_failure(error)
        assert result == FailureType.TRANSIENT

    def test_os_error_is_transient(self) -> None:
        """Test that OS errors are classified as transient."""
        error = OSError("No space left on device")
        result = classify_failure(error)
        assert result == FailureType.TRANSIENT

    def test_value_error_is_permanent(self) -> None:
        """Test that value errors are classified as permanent."""
        error = ValueError("Invalid argument")
        result = classify_failure(error)
        assert result == FailureType.PERMANENT

    def test_type_error_is_permanent(self) -> None:
        """Test that type errors are classified as permanent."""
        error = TypeError("Wrong type")
        result = classify_failure(error)
        assert result == FailureType.PERMANENT

    def test_key_error_is_permanent(self) -> None:
        """Test that key errors are classified as permanent."""
        error = KeyError("missing_key")
        result = classify_failure(error)
        assert result == FailureType.PERMANENT

    def test_unknown_error_is_unknown(self) -> None:
        """Test that generic exceptions are classified as unknown."""
        error = RuntimeError("Something weird happened")
        result = classify_failure(error)
        assert result == FailureType.UNKNOWN

    def test_asyncio_timeout_is_transient(self) -> None:
        """Test that asyncio.TimeoutError is classified as transient."""
        error = asyncio.TimeoutError()
        result = classify_failure(error)
        assert result == FailureType.TRANSIENT


class TestExecutionCheckpoint:
    """Tests for ExecutionCheckpoint dataclass."""

    def test_empty_checkpoint(self) -> None:
        """Test creating an empty checkpoint."""
        checkpoint = ExecutionCheckpoint()
        assert checkpoint.completed_tasks == []
        assert checkpoint.failed_tasks == []
        assert checkpoint.skipped_tasks == []

    def test_checkpoint_with_data(self) -> None:
        """Test creating a checkpoint with data."""
        failure = TaskFailure(
            task_id="task-2",
            error="Timeout",
            failure_type=FailureType.TRANSIENT,
            timestamp="2024-01-01T00:00:00Z",
        )
        checkpoint = ExecutionCheckpoint(
            completed_tasks=["task-1", "task-3"],
            failed_tasks=[failure],
            skipped_tasks=["task-4"],
        )
        assert len(checkpoint.completed_tasks) == 2
        assert len(checkpoint.failed_tasks) == 1
        assert len(checkpoint.skipped_tasks) == 1

    def test_save_and_load_json_roundtrip(self) -> None:
        """Test that checkpoint save/load JSON round-trip preserves data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"

            failure = TaskFailure(
                task_id="task-2",
                error="Connection timeout",
                failure_type=FailureType.TRANSIENT,
                timestamp="2024-01-01T00:00:00Z",
            )
            original = ExecutionCheckpoint(
                completed_tasks=["task-1", "task-3"],
                failed_tasks=[failure],
                skipped_tasks=["task-4"],
            )

            original.save(path)
            loaded = ExecutionCheckpoint.load(path)

            assert loaded.completed_tasks == original.completed_tasks
            assert loaded.skipped_tasks == original.skipped_tasks
            assert len(loaded.failed_tasks) == 1
            assert loaded.failed_tasks[0].task_id == "task-2"
            assert loaded.failed_tasks[0].error == "Connection timeout"
            assert loaded.failed_tasks[0].failure_type == FailureType.TRANSIENT
            assert loaded.failed_tasks[0].timestamp == "2024-01-01T00:00:00Z"

    def test_save_creates_valid_json(self) -> None:
        """Test that save creates valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"

            checkpoint = ExecutionCheckpoint(
                completed_tasks=["task-1"],
                failed_tasks=[],
                skipped_tasks=[],
            )
            checkpoint.save(path)

            # Verify JSON is valid
            data = json.loads(path.read_text())
            assert "completed" in data
            assert "failed" in data
            assert "skipped" in data
            assert data["completed"] == ["task-1"]

    def test_load_with_multiple_failures(self) -> None:
        """Test loading checkpoint with multiple failure types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"

            failures = [
                TaskFailure(
                    task_id="task-1",
                    error="Timeout",
                    failure_type=FailureType.TRANSIENT,
                    timestamp="2024-01-01T00:00:00Z",
                ),
                TaskFailure(
                    task_id="task-2",
                    error="Invalid config",
                    failure_type=FailureType.PERMANENT,
                    timestamp="2024-01-01T00:01:00Z",
                ),
                TaskFailure(
                    task_id="task-3",
                    error="Unknown error",
                    failure_type=FailureType.UNKNOWN,
                    timestamp="2024-01-01T00:02:00Z",
                ),
            ]

            original = ExecutionCheckpoint(
                completed_tasks=["task-4"],
                failed_tasks=failures,
                skipped_tasks=[],
            )

            original.save(path)
            loaded = ExecutionCheckpoint.load(path)

            assert len(loaded.failed_tasks) == 3
            assert loaded.failed_tasks[0].failure_type == FailureType.TRANSIENT
            assert loaded.failed_tasks[1].failure_type == FailureType.PERMANENT
            assert loaded.failed_tasks[2].failure_type == FailureType.UNKNOWN


class TestGracefulExecutor:
    """Tests for GracefulExecutor class."""

    def test_init_defaults(self) -> None:
        """Test GracefulExecutor default initialization."""
        executor = GracefulExecutor()
        assert executor.continue_on_error is True
        assert executor.max_failures is None
        assert executor.checkpoint is not None

    def test_init_custom_params(self) -> None:
        """Test GracefulExecutor with custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = GracefulExecutor(
                continue_on_error=False,
                max_failures=3,
                checkpoint_dir=Path(tmpdir),
            )
            assert executor.continue_on_error is False
            assert executor.max_failures == 3

    def test_execute_task_success(self) -> None:
        """Test executing a successful task."""

        async def _test():
            executor = GracefulExecutor()

            async def successful_task():
                return {"resolved": True, "cost": 0.50}

            result = await executor.execute_task("task-1", successful_task())
            assert result == {"resolved": True, "cost": 0.50}
            assert "task-1" in executor.checkpoint.completed_tasks
            assert len(executor.checkpoint.failed_tasks) == 0

        asyncio.run(_test())

    def test_execute_task_failure_isolated(self) -> None:
        """Test that a failing task is isolated and recorded."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True)

            async def failing_task():
                raise ValueError("Task failed")

            result = await executor.execute_task("task-1", failing_task())
            assert result is None
            assert "task-1" not in executor.checkpoint.completed_tasks
            assert len(executor.checkpoint.failed_tasks) == 1
            assert executor.checkpoint.failed_tasks[0].task_id == "task-1"
            assert "Task failed" in executor.checkpoint.failed_tasks[0].error

        asyncio.run(_test())

    def test_continue_on_error_true_continues_after_failure(self) -> None:
        """Test that continue_on_error=True continues after failure."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True)

            async def failing_task():
                raise RuntimeError("Task exploded")

            async def successful_task():
                return {"resolved": True}

            # First task fails
            result1 = await executor.execute_task("task-1", failing_task())
            assert result1 is None

            # should_continue returns True
            assert executor.should_continue() is True

            # Second task succeeds
            result2 = await executor.execute_task("task-2", successful_task())
            assert result2 == {"resolved": True}

            assert len(executor.checkpoint.completed_tasks) == 1
            assert len(executor.checkpoint.failed_tasks) == 1

        asyncio.run(_test())

    def test_continue_on_error_false_stops_on_first_failure(self) -> None:
        """Test that continue_on_error=False stops on first failure."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=False)

            async def failing_task():
                raise RuntimeError("Task exploded")

            # First task fails
            result = await executor.execute_task("task-1", failing_task())
            assert result is None

            # should_continue returns False
            assert executor.should_continue() is False

        asyncio.run(_test())

    def test_max_failures_threshold(self) -> None:
        """Test that max_failures threshold stops after N failures."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True, max_failures=2)

            async def failing_task():
                raise RuntimeError("Task exploded")

            # First failure
            await executor.execute_task("task-1", failing_task())
            assert executor.should_continue() is True

            # Second failure (at threshold)
            await executor.execute_task("task-2", failing_task())
            assert executor.should_continue() is False

        asyncio.run(_test())

    def test_max_failures_not_triggered_by_successes(self) -> None:
        """Test that successful tasks don't count toward max_failures."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True, max_failures=2)

            async def successful_task():
                return {"resolved": True}

            async def failing_task():
                raise RuntimeError("Task exploded")

            # Success, failure, success, failure
            await executor.execute_task("task-1", successful_task())
            assert executor.should_continue() is True

            await executor.execute_task("task-2", failing_task())
            assert executor.should_continue() is True

            await executor.execute_task("task-3", successful_task())
            assert executor.should_continue() is True

            await executor.execute_task("task-4", failing_task())
            # Now at 2 failures, should stop
            assert executor.should_continue() is False

        asyncio.run(_test())

    def test_should_continue_with_no_failures(self) -> None:
        """Test should_continue when no failures have occurred."""
        executor = GracefulExecutor()
        assert executor.should_continue() is True

    def test_should_continue_after_successes_only(self) -> None:
        """Test should_continue with only successful tasks."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True, max_failures=1)

            async def successful_task():
                return {"resolved": True}

            await executor.execute_task("task-1", successful_task())
            await executor.execute_task("task-2", successful_task())
            await executor.execute_task("task-3", successful_task())

            assert executor.should_continue() is True

        asyncio.run(_test())

    def test_partial_report_generation_empty(self) -> None:
        """Test partial report with no tasks."""
        executor = GracefulExecutor()
        report = executor.get_partial_report()

        assert report["total_tasks"] == 0
        assert report["completed_count"] == 0
        assert report["failed_count"] == 0
        assert report["skipped_count"] == 0
        assert report["success_rate"] == 0.0

    def test_partial_report_with_mixed_results(self) -> None:
        """Test partial report with both successes and failures."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True)

            async def successful_task():
                return {"resolved": True}

            async def failing_task():
                raise RuntimeError("Task exploded")

            # Run some tasks
            await executor.execute_task("task-1", successful_task())
            await executor.execute_task("task-2", failing_task())
            await executor.execute_task("task-3", successful_task())
            await executor.execute_task("task-4", failing_task())
            await executor.execute_task("task-5", successful_task())

            report = executor.get_partial_report()

            assert report["total_tasks"] == 5
            assert report["completed_count"] == 3
            assert report["failed_count"] == 2
            assert report["skipped_count"] == 0
            assert report["success_rate"] == pytest.approx(0.6)
            assert len(report["failures"]) == 2

        asyncio.run(_test())

    def test_partial_report_includes_failure_details(self) -> None:
        """Test that partial report includes failure details."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True)

            async def failing_task():
                raise ValueError("Bad input data")

            await executor.execute_task("task-1", failing_task())

            report = executor.get_partial_report()
            assert len(report["failures"]) == 1
            assert report["failures"][0]["task_id"] == "task-1"
            assert "Bad input data" in report["failures"][0]["error"]
            assert report["failures"][0]["failure_type"] == "permanent"

        asyncio.run(_test())

    def test_partial_report_success_rate_all_successes(self) -> None:
        """Test partial report success rate with all successes."""

        async def _test():
            executor = GracefulExecutor()

            async def successful_task():
                return {"resolved": True}

            await executor.execute_task("task-1", successful_task())
            await executor.execute_task("task-2", successful_task())

            report = executor.get_partial_report()
            assert report["success_rate"] == pytest.approx(1.0)

        asyncio.run(_test())

    def test_partial_report_success_rate_all_failures(self) -> None:
        """Test partial report success rate with all failures."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True)

            async def failing_task():
                raise RuntimeError("Fail")

            await executor.execute_task("task-1", failing_task())
            await executor.execute_task("task-2", failing_task())

            report = executor.get_partial_report()
            assert report["success_rate"] == pytest.approx(0.0)

        asyncio.run(_test())

    def test_checkpoint_save_on_execute(self) -> None:
        """Test that checkpoint is saved after each task when checkpoint_dir is set."""

        async def _test():
            with tempfile.TemporaryDirectory() as tmpdir:
                checkpoint_dir = Path(tmpdir)
                executor = GracefulExecutor(checkpoint_dir=checkpoint_dir)

                async def successful_task():
                    return {"resolved": True}

                await executor.execute_task("task-1", successful_task())

                # Verify checkpoint file was saved
                checkpoint_path = checkpoint_dir / "checkpoint.json"
                assert checkpoint_path.exists()

                # Load and verify
                loaded = ExecutionCheckpoint.load(checkpoint_path)
                assert "task-1" in loaded.completed_tasks

        asyncio.run(_test())

    def test_checkpoint_save_on_failure(self) -> None:
        """Test that checkpoint is saved when a task fails."""

        async def _test():
            with tempfile.TemporaryDirectory() as tmpdir:
                checkpoint_dir = Path(tmpdir)
                executor = GracefulExecutor(
                    continue_on_error=True,
                    checkpoint_dir=checkpoint_dir,
                )

                async def failing_task():
                    raise RuntimeError("Task failed")

                await executor.execute_task("task-1", failing_task())

                # Verify checkpoint file was saved with the failure
                checkpoint_path = checkpoint_dir / "checkpoint.json"
                assert checkpoint_path.exists()

                loaded = ExecutionCheckpoint.load(checkpoint_path)
                assert len(loaded.failed_tasks) == 1
                assert loaded.failed_tasks[0].task_id == "task-1"

        asyncio.run(_test())

    def test_failure_classification_in_execute(self) -> None:
        """Test that failures are classified correctly during execution."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True)

            async def timeout_task():
                raise TimeoutError("Timed out")

            async def value_error_task():
                raise ValueError("Bad value")

            await executor.execute_task("task-1", timeout_task())
            await executor.execute_task("task-2", value_error_task())

            failures = executor.checkpoint.failed_tasks
            assert len(failures) == 2
            assert failures[0].failure_type == FailureType.TRANSIENT
            assert failures[1].failure_type == FailureType.PERMANENT

        asyncio.run(_test())

    def test_partial_results_saved_when_tasks_fail(self) -> None:
        """Test that partial results are available when some tasks fail."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True)
            collected_results = []

            async def successful_task(idx):
                return {"resolved": True, "task": idx}

            async def failing_task():
                raise RuntimeError("Failed")

            # Run interleaved success/failure
            for i in range(5):
                if i % 2 == 0:
                    result = await executor.execute_task(f"task-{i}", successful_task(i))
                else:
                    result = await executor.execute_task(f"task-{i}", failing_task())

                if result is not None:
                    collected_results.append(result)

            # We should have 3 successful results
            assert len(collected_results) == 3
            # And 2 failures recorded
            assert len(executor.checkpoint.failed_tasks) == 2
            # And 3 completed
            assert len(executor.checkpoint.completed_tasks) == 3

        asyncio.run(_test())

    def test_skipped_tasks_tracking(self) -> None:
        """Test that skipped tasks are tracked in checkpoint."""

        async def _test():
            executor = GracefulExecutor(continue_on_error=True, max_failures=1)

            async def failing_task():
                raise RuntimeError("Failed")

            # Fail enough to stop
            await executor.execute_task("task-1", failing_task())
            assert executor.should_continue() is False

            # Remaining tasks would be skipped
            executor.checkpoint.skipped_tasks.append("task-2")
            executor.checkpoint.skipped_tasks.append("task-3")

            report = executor.get_partial_report()
            assert report["skipped_count"] == 2
            assert report["failed_count"] == 1

        asyncio.run(_test())
