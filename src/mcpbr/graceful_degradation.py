"""Graceful degradation for benchmark evaluation.

Provides fault-tolerant execution of benchmark tasks with failure isolation,
classification, checkpointing, and configurable error handling policies.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class FailureType(Enum):
    """Classification of task failure types."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


@dataclass
class TaskFailure:
    """Record of a single task failure.

    Attributes:
        task_id: Identifier of the failed task.
        error: Error message describing the failure.
        failure_type: Classification of the failure.
        timestamp: ISO 8601 timestamp of when the failure occurred.
        retryable: Whether the task could be retried.
    """

    task_id: str
    error: str
    failure_type: FailureType
    timestamp: str
    retryable: bool = True


@dataclass
class ExecutionCheckpoint:
    """Checkpoint of execution state for crash recovery and resumption.

    Tracks which tasks have completed, failed, or been skipped during
    an evaluation run. Can be serialized to/from JSON for persistence.

    Attributes:
        completed_tasks: List of task IDs that completed successfully.
        failed_tasks: List of TaskFailure records for failed tasks.
        skipped_tasks: List of task IDs that were skipped.
    """

    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[TaskFailure] = field(default_factory=list)
    skipped_tasks: list[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Save checkpoint to a JSON file.

        Args:
            path: File path to write the checkpoint to.
        """
        data = {
            "completed": self.completed_tasks,
            "failed": [
                {
                    "task_id": f.task_id,
                    "error": f.error,
                    "type": f.failure_type.value,
                    "timestamp": f.timestamp,
                }
                for f in self.failed_tasks
            ],
            "skipped": self.skipped_tasks,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> "ExecutionCheckpoint":
        """Load checkpoint from a JSON file.

        Args:
            path: File path to read the checkpoint from.

        Returns:
            ExecutionCheckpoint populated from the file.
        """
        data = json.loads(path.read_text())
        return cls(
            completed_tasks=data["completed"],
            failed_tasks=[
                TaskFailure(
                    task_id=f["task_id"],
                    error=f["error"],
                    failure_type=FailureType(f["type"]),
                    timestamp=f["timestamp"],
                )
                for f in data["failed"]
            ],
            skipped_tasks=data["skipped"],
        )


# Exception types considered transient (may succeed on retry)
_TRANSIENT_ERRORS = (
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    OSError,
    IOError,
)

# Exception types considered permanent (will not succeed on retry)
_PERMANENT_ERRORS = (
    ValueError,
    TypeError,
    KeyError,
    IndexError,
    AttributeError,
    NotImplementedError,
    SyntaxError,
    ImportError,
)


def classify_failure(error: Exception) -> FailureType:
    """Classify an error as transient, permanent, or unknown.

    Transient errors are those that may succeed on retry (timeouts,
    connection issues, resource exhaustion). Permanent errors are
    programming or configuration errors that will not resolve on retry.

    Args:
        error: The exception to classify.

    Returns:
        FailureType indicating the classification.
    """
    if isinstance(error, _TRANSIENT_ERRORS):
        return FailureType.TRANSIENT
    if isinstance(error, _PERMANENT_ERRORS):
        return FailureType.PERMANENT
    return FailureType.UNKNOWN


class GracefulExecutor:
    """Executor that provides graceful degradation for benchmark tasks.

    Isolates task failures so that one failing task does not prevent
    other tasks from executing. Supports configurable error policies
    including continue-on-error and max-failure thresholds.

    Args:
        continue_on_error: If True, continue executing tasks after failures.
            If False, stop on the first failure.
        max_failures: Maximum number of failures before stopping execution.
            None means no limit (continue until all tasks are processed).
        checkpoint_dir: Directory to save execution checkpoints for crash recovery.
            None means no checkpointing.
    """

    def __init__(
        self,
        continue_on_error: bool = True,
        max_failures: int | None = None,
        checkpoint_dir: Path | None = None,
    ) -> None:
        """Initialize GracefulExecutor.

        Args:
            continue_on_error: Whether to continue after task failures.
            max_failures: Maximum failures before halting. None for unlimited.
            checkpoint_dir: Directory for saving checkpoint files.
        """
        self.continue_on_error = continue_on_error
        self.max_failures = max_failures
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint = ExecutionCheckpoint()

    async def execute_task(self, task_id: str, coro: Any) -> Any | None:
        """Execute a single task with failure isolation.

        Wraps the coroutine execution in error handling that records
        failures without propagating them (when continue_on_error is True).

        Args:
            task_id: Identifier for the task being executed.
            coro: Awaitable coroutine to execute.

        Returns:
            The result of the coroutine, or None if the task failed.
        """
        try:
            result = await coro
            self.checkpoint.completed_tasks.append(task_id)
            self._save_checkpoint()
            return result
        except Exception as e:
            failure_type = classify_failure(e)
            failure = TaskFailure(
                task_id=task_id,
                error=str(e),
                failure_type=failure_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                retryable=failure_type == FailureType.TRANSIENT,
            )
            self.checkpoint.failed_tasks.append(failure)
            self._save_checkpoint()
            return None

    def should_continue(self) -> bool:
        """Determine whether execution should continue.

        Considers the continue_on_error flag and the max_failures threshold.

        Returns:
            True if execution should continue, False if it should stop.
        """
        failure_count = len(self.checkpoint.failed_tasks)

        # If any failure occurred and continue_on_error is False, stop
        if not self.continue_on_error and failure_count > 0:
            return False

        # If max_failures is set and we've reached it, stop
        if self.max_failures is not None and failure_count >= self.max_failures:
            return False

        return True

    def get_partial_report(self) -> dict[str, Any]:
        """Generate a report of execution progress including partial results.

        Returns:
            Dictionary with execution statistics and failure details.
        """
        completed_count = len(self.checkpoint.completed_tasks)
        failed_count = len(self.checkpoint.failed_tasks)
        skipped_count = len(self.checkpoint.skipped_tasks)
        total_tasks = completed_count + failed_count + skipped_count

        success_rate = completed_count / total_tasks if total_tasks > 0 else 0.0

        failures = [
            {
                "task_id": f.task_id,
                "error": f.error,
                "failure_type": f.failure_type.value,
                "timestamp": f.timestamp,
                "retryable": f.retryable,
            }
            for f in self.checkpoint.failed_tasks
        ]

        return {
            "total_tasks": total_tasks,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "success_rate": success_rate,
            "failures": failures,
        }

    def _save_checkpoint(self) -> None:
        """Save checkpoint to disk if checkpoint_dir is configured."""
        if self.checkpoint_dir is not None:
            checkpoint_path = self.checkpoint_dir / "checkpoint.json"
            self.checkpoint.save(checkpoint_path)
