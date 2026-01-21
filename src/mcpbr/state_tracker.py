"""State tracking for incremental evaluation.

This module provides functionality to track task completion status,
allowing users to resume evaluations and skip already-completed tasks.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TaskState:
    """State for a single task."""

    instance_id: str
    task_hash: str
    completed: bool = False
    mcp_result: dict[str, Any] | None = None
    baseline_result: dict[str, Any] | None = None
    timestamp: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "instance_id": self.instance_id,
            "task_hash": self.task_hash,
            "completed": self.completed,
            "mcp_result": self.mcp_result,
            "baseline_result": self.baseline_result,
            "timestamp": self.timestamp,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        """Create from dictionary."""
        return cls(
            instance_id=data["instance_id"],
            task_hash=data["task_hash"],
            completed=data.get("completed", False),
            mcp_result=data.get("mcp_result"),
            baseline_result=data.get("baseline_result"),
            timestamp=data.get("timestamp"),
            error=data.get("error"),
        )


@dataclass
class EvaluationState:
    """State for an entire evaluation run."""

    state_version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    config_hash: str = ""
    tasks: dict[str, TaskState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "state_version": self.state_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config_hash": self.config_hash,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationState":
        """Create from dictionary."""
        tasks = {k: TaskState.from_dict(v) for k, v in data.get("tasks", {}).items()}
        return cls(
            state_version=data.get("state_version", "1.0"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            config_hash=data.get("config_hash", ""),
            tasks=tasks,
        )


def compute_task_hash(task: dict[str, Any]) -> str:
    """Compute a hash for a task to detect changes.

    Args:
        task: Task dictionary from benchmark.

    Returns:
        SHA256 hash of the task definition.
    """
    # Use critical fields that define the task
    task_def = {
        "instance_id": task.get("instance_id"),
        "problem_statement": task.get("problem_statement"),
        "repo": task.get("repo"),
        "base_commit": task.get("base_commit"),
        "version": task.get("version"),
        # Include test definitions if present
        "FAIL_TO_PASS": task.get("FAIL_TO_PASS"),
        "PASS_TO_PASS": task.get("PASS_TO_PASS"),
    }
    task_json = json.dumps(task_def, sort_keys=True)
    return hashlib.sha256(task_json.encode()).hexdigest()


def compute_config_hash(config: Any) -> str:
    """Compute a hash for the configuration.

    Args:
        config: HarnessConfig object.

    Returns:
        SHA256 hash of the config.
    """
    # Use fields that affect evaluation results
    config_def = {
        "model": config.model,
        "provider": config.provider,
        "agent_harness": config.agent_harness,
        "benchmark": config.benchmark,
        "dataset": config.dataset,
        "timeout_seconds": config.timeout_seconds,
        "max_iterations": config.max_iterations,
        # Include MCP server config
        "mcp_server_command": config.mcp_server.command,
        "mcp_server_args": config.mcp_server.args,
    }
    config_json = json.dumps(config_def, sort_keys=True)
    return hashlib.sha256(config_json.encode()).hexdigest()


class StateTracker:
    """Tracks evaluation state and persists to disk."""

    def __init__(self, state_dir: Path | None = None):
        """Initialize state tracker.

        Args:
            state_dir: Directory to store state files. Defaults to .mcpbr_state/
        """
        self.state_dir = state_dir or Path(".mcpbr_state")
        self.state_file = self.state_dir / "evaluation_state.json"
        self.state: EvaluationState | None = None

    def load_state(self) -> EvaluationState:
        """Load state from disk, or create new state if none exists.

        Returns:
            EvaluationState object.
        """
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                self.state = EvaluationState.from_dict(data)
        else:
            self.state = EvaluationState()
        return self.state

    def save_state(self) -> None:
        """Save state to disk."""
        if self.state is None:
            return

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state.updated_at = datetime.now(timezone.utc).isoformat()

        with open(self.state_file, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def clear_state(self) -> None:
        """Clear all state."""
        if self.state_file.exists():
            self.state_file.unlink()
        self.state = EvaluationState()

    def is_task_completed(self, instance_id: str, task_hash: str) -> bool:
        """Check if a task is completed and unchanged.

        Args:
            instance_id: Task instance ID.
            task_hash: Current hash of the task.

        Returns:
            True if task is completed and hash matches, False otherwise.
        """
        if self.state is None:
            return False

        task_state = self.state.tasks.get(instance_id)
        if task_state is None:
            return False

        # Check if task definition has changed
        if task_state.task_hash != task_hash:
            return False

        return task_state.completed

    def mark_task_completed(
        self,
        instance_id: str,
        task_hash: str,
        mcp_result: dict[str, Any] | None = None,
        baseline_result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Mark a task as completed.

        Args:
            instance_id: Task instance ID.
            task_hash: Hash of the task definition.
            mcp_result: MCP evaluation result.
            baseline_result: Baseline evaluation result.
            error: Error message if task failed.
        """
        if self.state is None:
            self.state = EvaluationState()

        # Determine if task is actually completed (has results or error)
        completed = (mcp_result is not None or baseline_result is not None) or error is not None

        self.state.tasks[instance_id] = TaskState(
            instance_id=instance_id,
            task_hash=task_hash,
            completed=completed,
            mcp_result=mcp_result,
            baseline_result=baseline_result,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error=error,
        )

    def get_task_result(self, instance_id: str) -> TaskState | None:
        """Get the cached result for a task.

        Args:
            instance_id: Task instance ID.

        Returns:
            TaskState if found, None otherwise.
        """
        if self.state is None:
            return None
        return self.state.tasks.get(instance_id)

    def get_failed_tasks(self) -> list[str]:
        """Get list of instance IDs for failed tasks.

        Returns:
            List of instance IDs where task failed (error or not resolved).
        """
        if self.state is None:
            return []

        failed = []
        for instance_id, task_state in self.state.tasks.items():
            if not task_state.completed:
                continue

            # Check if task has error
            if task_state.error:
                failed.append(instance_id)
                continue

            # Check if task was not resolved (in either MCP or baseline)
            mcp_resolved = task_state.mcp_result and task_state.mcp_result.get("resolved", False)
            baseline_resolved = task_state.baseline_result and task_state.baseline_result.get(
                "resolved", False
            )

            if not (mcp_resolved or baseline_resolved):
                failed.append(instance_id)

        return failed

    def get_completed_count(self) -> int:
        """Get count of completed tasks.

        Returns:
            Number of completed tasks.
        """
        if self.state is None:
            return 0
        return sum(1 for t in self.state.tasks.values() if t.completed)

    def validate_config(self, config: Any) -> tuple[bool, str]:
        """Validate that config matches the one used for cached results.

        Args:
            config: HarnessConfig object.

        Returns:
            Tuple of (is_valid, error_message).
        """
        current_hash = compute_config_hash(config)

        if self.state is None:
            return True, ""

        # Set config hash if not present
        if not self.state.config_hash:
            self.state.config_hash = current_hash
            return True, ""

        # If no tasks yet, any config is valid (but don't update hash)
        if not self.state.tasks:
            return True, ""

        # Compare hashes
        if current_hash != self.state.config_hash:
            return (
                False,
                "Configuration has changed since last run. "
                "Use --reset-state to clear cached results and start fresh.",
            )

        return True, ""
