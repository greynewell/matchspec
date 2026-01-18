"""Base types and protocol for benchmark abstraction."""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..docker_env import DockerEnvironmentManager, TaskEnvironment


@dataclass
class BenchmarkTask:
    """Normalized task representation across different benchmarks."""

    task_id: str
    problem_statement: str
    repo: str
    commit: str
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Benchmark(Protocol):
    """Protocol for benchmark implementations.

    Each benchmark (SWE-bench, CyberGym, etc.) implements this protocol
    to provide task loading, environment setup, and evaluation.
    """

    name: str

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from the benchmark dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Difficulty/context level (benchmark-specific, e.g., CyberGym 0-3).

        Returns:
            List of task dictionaries in benchmark-specific format.
        """
        ...

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert benchmark-specific task format to normalized BenchmarkTask.

        Args:
            task: Task in benchmark-specific format.

        Returns:
            Normalized BenchmarkTask.
        """
        ...

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create an isolated environment for the task.

        Args:
            task: Task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        ...

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for the task.

        Args:
            env: Task environment.
            task: Task dictionary.
            solution: Solution to evaluate (e.g., patch, PoC code).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        ...

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for the task, if available.

        Args:
            task: Task dictionary.

        Returns:
            Docker image name or None if no pre-built image exists.
        """
        ...

    def get_prompt_template(self) -> str:
        """Get the benchmark-specific prompt template for agents.

        Returns:
            Prompt template string with {problem_statement} placeholder.
        """
        ...
