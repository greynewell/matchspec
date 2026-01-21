"""Tests for state tracker functionality."""

# ruff: noqa: N801

import json
import tempfile
from pathlib import Path

from mcpbr.state_tracker import (
    EvaluationState,
    StateTracker,
    TaskState,
    compute_config_hash,
    compute_task_hash,
)


class TestTaskState:
    """Tests for TaskState dataclass."""

    def test_to_dict(self) -> None:
        """Test converting TaskState to dictionary."""
        state = TaskState(
            instance_id="test-1",
            task_hash="abc123",
            completed=True,
            mcp_result={"resolved": True},
            baseline_result={"resolved": False},
            timestamp="2024-01-01T00:00:00Z",
            error=None,
        )
        result = state.to_dict()

        assert result["instance_id"] == "test-1"
        assert result["task_hash"] == "abc123"
        assert result["completed"] is True
        assert result["mcp_result"] == {"resolved": True}
        assert result["baseline_result"] == {"resolved": False}

    def test_from_dict(self) -> None:
        """Test creating TaskState from dictionary."""
        data = {
            "instance_id": "test-1",
            "task_hash": "abc123",
            "completed": True,
            "mcp_result": {"resolved": True},
            "baseline_result": None,
            "timestamp": "2024-01-01T00:00:00Z",
            "error": "Some error",
        }
        state = TaskState.from_dict(data)

        assert state.instance_id == "test-1"
        assert state.task_hash == "abc123"
        assert state.completed is True
        assert state.error == "Some error"


class TestEvaluationState:
    """Tests for EvaluationState dataclass."""

    def test_to_dict(self) -> None:
        """Test converting EvaluationState to dictionary."""
        task1 = TaskState(instance_id="test-1", task_hash="hash1")
        task2 = TaskState(instance_id="test-2", task_hash="hash2")

        state = EvaluationState(
            config_hash="config123",
            tasks={"test-1": task1, "test-2": task2},
        )
        result = state.to_dict()

        assert result["state_version"] == "1.0"
        assert result["config_hash"] == "config123"
        assert "tasks" in result
        assert "test-1" in result["tasks"]
        assert "test-2" in result["tasks"]

    def test_from_dict(self) -> None:
        """Test creating EvaluationState from dictionary."""
        data = {
            "state_version": "1.0",
            "config_hash": "config123",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "tasks": {
                "test-1": {
                    "instance_id": "test-1",
                    "task_hash": "hash1",
                    "completed": True,
                },
                "test-2": {
                    "instance_id": "test-2",
                    "task_hash": "hash2",
                    "completed": False,
                },
            },
        }
        state = EvaluationState.from_dict(data)

        assert state.state_version == "1.0"
        assert state.config_hash == "config123"
        assert len(state.tasks) == 2
        assert "test-1" in state.tasks
        assert "test-2" in state.tasks


class TestComputeTaskHash:
    """Tests for compute_task_hash function."""

    def test_same_task_same_hash(self) -> None:
        """Test that identical tasks produce the same hash."""
        task1 = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
            "repo": "owner/repo",
            "base_commit": "abc123",
        }
        task2 = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
            "repo": "owner/repo",
            "base_commit": "abc123",
        }

        hash1 = compute_task_hash(task1)
        hash2 = compute_task_hash(task2)

        assert hash1 == hash2

    def test_different_task_different_hash(self) -> None:
        """Test that different tasks produce different hashes."""
        task1 = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
            "repo": "owner/repo",
            "base_commit": "abc123",
        }
        task2 = {
            "instance_id": "test-1",
            "problem_statement": "Fix different bug",
            "repo": "owner/repo",
            "base_commit": "abc123",
        }

        hash1 = compute_task_hash(task1)
        hash2 = compute_task_hash(task2)

        assert hash1 != hash2

    def test_hash_is_consistent(self) -> None:
        """Test that hash is consistent across calls."""
        task = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
        }

        hash1 = compute_task_hash(task)
        hash2 = compute_task_hash(task)
        hash3 = compute_task_hash(task)

        assert hash1 == hash2 == hash3


class TestComputeConfigHash:
    """Tests for compute_config_hash function."""

    def test_same_config_same_hash(self) -> None:
        """Test that identical configs produce the same hash."""

        class MockConfig:
            model = "claude-3-5-sonnet"
            provider = "anthropic"
            agent_harness = "claude-code"
            benchmark = "swe-bench"
            dataset = None
            timeout_seconds = 300
            max_iterations = 10

            class mcp_server:
                command = "npx"
                args = ["-y", "filesystem"]

        config1 = MockConfig()
        config2 = MockConfig()

        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)

        assert hash1 == hash2

    def test_different_config_different_hash(self) -> None:
        """Test that different configs produce different hashes."""

        class MockConfig1:
            model = "claude-3-5-sonnet"
            provider = "anthropic"
            agent_harness = "claude-code"
            benchmark = "swe-bench"
            dataset = None
            timeout_seconds = 300
            max_iterations = 10

            class mcp_server:
                command = "npx"
                args = ["-y", "filesystem"]

        class MockConfig2:
            model = "claude-3-5-haiku"
            provider = "anthropic"
            agent_harness = "claude-code"
            benchmark = "swe-bench"
            dataset = None
            timeout_seconds = 300
            max_iterations = 10

            class mcp_server:
                command = "npx"
                args = ["-y", "filesystem"]

        config1 = MockConfig1()
        config2 = MockConfig2()

        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)

        assert hash1 != hash2


class TestStateTracker:
    """Tests for StateTracker class."""

    def test_init_creates_state_dir(self) -> None:
        """Test that initialization specifies state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)

            assert tracker.state_dir == state_dir
            assert tracker.state_file == state_dir / "evaluation_state.json"

    def test_load_state_creates_new_if_not_exists(self) -> None:
        """Test that load_state creates new state if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)

            state = tracker.load_state()

            assert state is not None
            assert len(state.tasks) == 0
            assert state.state_version == "1.0"

    def test_save_and_load_state(self) -> None:
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)

            # Load initial state
            tracker.load_state()

            # Mark a task as completed
            tracker.mark_task_completed(
                instance_id="test-1",
                task_hash="hash1",
                mcp_result={"resolved": True},
                baseline_result={"resolved": False},
            )

            # Save state
            tracker.save_state()

            # Create new tracker and load state
            tracker2 = StateTracker(state_dir=state_dir)
            tracker2.load_state()

            assert tracker2.state is not None
            assert "test-1" in tracker2.state.tasks
            assert tracker2.state.tasks["test-1"].completed

    def test_clear_state(self) -> None:
        """Test clearing state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)

            # Create and save state
            tracker.load_state()
            tracker.mark_task_completed("test-1", "hash1")
            tracker.save_state()

            assert tracker.state_file.exists()

            # Clear state
            tracker.clear_state()

            assert not tracker.state_file.exists()
            assert tracker.state is not None
            assert len(tracker.state.tasks) == 0

    def test_is_task_completed(self) -> None:
        """Test checking if task is completed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)
            tracker.load_state()

            # Task not in state
            assert not tracker.is_task_completed("test-1", "hash1")

            # Mark task as completed
            tracker.mark_task_completed("test-1", "hash1", mcp_result={"resolved": True})

            # Task is completed with correct hash
            assert tracker.is_task_completed("test-1", "hash1")

            # Task is not completed with different hash (definition changed)
            assert not tracker.is_task_completed("test-1", "hash2")

    def test_get_task_result(self) -> None:
        """Test getting cached task result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)
            tracker.load_state()

            # No result for non-existent task
            assert tracker.get_task_result("test-1") is None

            # Mark task as completed
            mcp_result = {"resolved": True, "tokens": {"input": 100, "output": 50}}
            tracker.mark_task_completed("test-1", "hash1", mcp_result=mcp_result)

            # Get result
            result = tracker.get_task_result("test-1")
            assert result is not None
            assert result.instance_id == "test-1"
            assert result.mcp_result == mcp_result

    def test_get_failed_tasks(self) -> None:
        """Test getting list of failed tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)
            tracker.load_state()

            # Mark tasks with different outcomes
            tracker.mark_task_completed(
                "task-1",
                "hash1",
                mcp_result={"resolved": True},  # Success
            )
            tracker.mark_task_completed(
                "task-2",
                "hash2",
                mcp_result={"resolved": False},  # Failed
            )
            tracker.mark_task_completed(
                "task-3",
                "hash3",
                error="Timeout",  # Error
            )
            tracker.mark_task_completed(
                "task-4",
                "hash4",
                mcp_result={"resolved": False},
                baseline_result={"resolved": False},  # Both failed
            )

            failed = tracker.get_failed_tasks()

            assert "task-1" not in failed  # Success
            assert "task-2" in failed  # Failed
            assert "task-3" in failed  # Error
            assert "task-4" in failed  # Both failed

    def test_get_completed_count(self) -> None:
        """Test getting count of completed tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)
            tracker.load_state()

            assert tracker.get_completed_count() == 0

            tracker.mark_task_completed("task-1", "hash1", mcp_result={"resolved": True})
            assert tracker.get_completed_count() == 1

            tracker.mark_task_completed("task-2", "hash2", mcp_result={"resolved": False})
            assert tracker.get_completed_count() == 2

    def test_validate_config(self) -> None:
        """Test config validation."""

        class MockConfig1:
            model = "claude-3-5-sonnet"
            provider = "anthropic"
            agent_harness = "claude-code"
            benchmark = "swe-bench"
            dataset = None
            timeout_seconds = 300
            max_iterations = 10

            class mcp_server:
                command = "npx"
                args = ["-y", "filesystem"]

        class MockConfig2:
            model = "claude-3-5-haiku"
            provider = "anthropic"
            agent_harness = "claude-code"
            benchmark = "swe-bench"
            dataset = None
            timeout_seconds = 300
            max_iterations = 10

            class mcp_server:
                command = "npx"
                args = ["-y", "filesystem"]

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)
            tracker.load_state()

            config1 = MockConfig1()
            config2 = MockConfig2()

            # Add a task so config validation matters
            tracker.mark_task_completed("test-1", "hash1", mcp_result={"resolved": True})

            # First validation always passes (sets the hash)
            valid, error = tracker.validate_config(config1)
            assert valid
            assert error == ""

            # Save state with config hash
            tracker.save_state()

            # Same config should pass
            tracker2 = StateTracker(state_dir=state_dir)
            tracker2.load_state()
            valid, error = tracker2.validate_config(config1)
            assert valid

            # Different config should fail
            valid, error = tracker2.validate_config(config2)
            assert not valid
            assert "Configuration has changed" in error

    def test_mark_task_not_completed_when_no_results(self) -> None:
        """Test that task is not marked completed if no results provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)
            tracker.load_state()

            # Mark task with no results or error
            tracker.mark_task_completed("test-1", "hash1")

            # Task should not be marked as completed
            task_state = tracker.state.tasks["test-1"]
            assert not task_state.completed

    def test_state_file_format(self) -> None:
        """Test that state file is valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "test_state"
            tracker = StateTracker(state_dir=state_dir)
            tracker.load_state()

            tracker.mark_task_completed("test-1", "hash1", mcp_result={"resolved": True})
            tracker.save_state()

            # Load JSON directly
            with open(tracker.state_file) as f:
                data = json.load(f)

            assert "state_version" in data
            assert "tasks" in data
            assert "test-1" in data["tasks"]
