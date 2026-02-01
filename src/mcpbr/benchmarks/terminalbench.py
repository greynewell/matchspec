"""TerminalBench benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class TerminalBenchBenchmark:
    """TerminalBench benchmark implementation.

    TerminalBench evaluates AI agents' ability to complete tasks in a
    terminal/shell environment. Tasks range from file manipulation and
    system administration to scripting and tool usage, testing practical
    command-line competency.

    Evaluation checks the terminal state after task execution against
    expected outcomes.
    """

    name = "terminalbench"

    def __init__(self, dataset: str = "ia03/terminal-bench"):
        """Initialize TerminalBench benchmark.

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
        """Load tasks from TerminalBench.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for TerminalBench.
            filter_difficulty: Filter by difficulty.
            filter_category: Filter by task category.
            filter_tags: Unused for TerminalBench.

        Returns:
            List of TerminalBench task dictionaries.
        """
        _ = level
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")
        tasks = list(dataset)

        if filter_difficulty:
            diff_set = {d.lower() for d in filter_difficulty}
            tasks = [t for t in tasks if t.get("difficulty", "").lower() in diff_set]

        if filter_category:
            cat_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("category", "").lower() in cat_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("task_id", "") in task_id_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            task_id = task.get("task_id", str(idx))
            augmented["instance_id"] = f"terminalbench_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert TerminalBench task to normalized format.

        Args:
            task: TerminalBench task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "terminalbench_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="terminalbench/tasks",
            commit="HEAD",
            metadata={
                "instruction": task.get("instruction", ""),
                "category": task.get("category", ""),
                "difficulty": task.get("difficulty", ""),
                "validation_command": task.get("validation_command", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: TerminalBench task dictionary.

        Returns:
            Problem statement for the agent.
        """
        instruction = task.get("instruction", task.get("description", "No instruction provided"))
        category = task.get("category", "")

        statement = "Complete the following terminal task"
        if category:
            statement += f" ({category})"
        statement += f":\n\n{instruction}"
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for TerminalBench task.

        Args:
            task: TerminalBench task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "terminalbench_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "terminalbench/tasks",
            "base_commit": "HEAD",
        }
        env = await docker_manager.create_environment(temp_task)

        # Run setup commands if provided
        setup_cmd = task.get("setup_command", "")
        if setup_cmd:
            exit_code, _stdout, stderr = await env.exec_command(setup_cmd, timeout=60)
            if exit_code != 0:
                raise RuntimeError(f"Setup command failed (exit {exit_code}): {stderr[:500]}")

        return env

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        _solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for TerminalBench task.

        Runs the validation command to check terminal state.

        Args:
            env: Task environment.
            task: TerminalBench task dictionary.
            _solution: Solution to evaluate (unused; validation checks env state).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        validation_cmd = task.get("validation_command", "")
        if not validation_cmd:
            return {"resolved": False, "error": "No validation command provided"}

        exit_code, stdout, stderr = await env.exec_command(
            validation_cmd,
            timeout=30,
        )

        passed = exit_code == 0
        return {
            "resolved": passed,
            "exit_code": exit_code,
            "stdout": stdout[:1000] if stdout else "",
            "stderr": stderr[:1000] if stderr else "",
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: TerminalBench task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get TerminalBench prompt template.

        Returns:
            Prompt template for terminal tasks.
        """
        return (
            "Complete the following terminal task:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Use shell commands to accomplish the task\n"
            "- Ensure your changes persist in the terminal environment\n"
            "- You have full access to standard Unix tools"
        )
