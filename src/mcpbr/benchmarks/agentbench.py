"""AgentBench benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class AgentBenchBenchmark:
    """AgentBench benchmark implementation.

    AgentBench is a multi-dimensional evolving benchmark for evaluating LLMs
    as agents across diverse environments including operating systems, databases,
    knowledge graphs, digital card games, lateral thinking puzzles, house-holding,
    and web shopping.

    Evaluation varies by environment type - task completion, accuracy, or success rate.
    """

    name = "agentbench"

    def __init__(self, dataset: str = "THUDM/AgentBench"):
        """Initialize AgentBench benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
        """
        self.dataset = dataset

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from AgentBench dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for AgentBench.
            filter_difficulty: Filter by difficulty.
            filter_category: Filter by environment type (os, db, kg, etc.).
            filter_tags: Unused for AgentBench.

        Returns:
            List of AgentBench task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = bool(task_ids) or bool(filter_category)
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        tasks = list(dataset)

        if filter_category:
            env_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("environment", "").lower() in env_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("task_id", "") in task_id_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            task_id = task.get("task_id", str(idx))
            augmented["instance_id"] = f"agentbench_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert AgentBench task to normalized format.

        Args:
            task: AgentBench task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "agentbench_unknown")
        environment = task.get("environment", "general")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo=f"agentbench/{environment}",
            commit="HEAD",
            metadata={
                "environment": environment,
                "instruction": task.get("instruction", ""),
                "expected_output": task.get("expected_output", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: AgentBench task dictionary.

        Returns:
            Problem statement for the agent.
        """
        instruction = task.get("instruction", task.get("description", "No instruction provided"))
        environment = task.get("environment", "general")

        return f"Complete the following task in the {environment} environment:\n\n{instruction}"

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for AgentBench task.

        Args:
            task: AgentBench task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "agentbench_unknown")
        environment = task.get("environment", "general")
        temp_task = {
            "instance_id": instance_id,
            "repo": f"agentbench/{environment}",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        _env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for AgentBench task.

        Checks task completion based on environment-specific criteria.

        Args:
            _env: Task environment (unused; evaluation is offline).
            task: AgentBench task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        expected = task.get("expected_output", "")
        if not expected:
            return {"resolved": False, "error": "No expected output available"}

        # Basic string matching evaluation
        resolved = expected.strip().lower() in solution.strip().lower()

        return {
            "resolved": resolved,
            "agent_output": solution[:500],
            "expected_output": expected,
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: AgentBench task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get AgentBench prompt template.

        Returns:
            Prompt template for agent tasks.
        """
        return (
            "Complete the following task as an autonomous agent:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Interact with the environment to complete the task\n"
            "- Use available tools and commands\n"
            "- Provide your final answer or result clearly"
        )
