"""InterCode benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class InterCodeBenchmark:
    """InterCode benchmark implementation.

    InterCode is a framework for interactive code environments that evaluates
    agents on tasks requiring multi-turn interaction with code interpreters.
    Environments include Bash, SQL, and Python, where agents must iteratively
    write and debug code through observation-action loops.

    Evaluation checks if the agent achieves the target state in the
    interactive environment.
    """

    name = "intercode"

    def __init__(self, dataset: str = "intercode-benchmark/intercode"):
        """Initialize InterCode benchmark.

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
        """Load tasks from InterCode dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for InterCode.
            filter_difficulty: Filter by difficulty.
            filter_category: Filter by environment type (bash, sql, python).
            filter_tags: Unused for InterCode.

        Returns:
            List of InterCode task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")
        tasks = list(dataset)

        if filter_category:
            env_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("environment", "").lower() in env_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if str(t.get("task_id", "")) in task_id_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            task_id = task.get("task_id", str(idx))
            augmented["instance_id"] = f"intercode_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert InterCode task to normalized format.

        Args:
            task: InterCode task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "intercode_unknown")
        environment = task.get("environment", "bash")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo=f"intercode/{environment}",
            commit="HEAD",
            metadata={
                "query": task.get("query", ""),
                "environment": environment,
                "gold_solution": task.get("gold_solution", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: InterCode task dictionary.

        Returns:
            Problem statement for the agent.
        """
        query = task.get("query", task.get("description", "No task description"))
        environment = task.get("environment", "bash")

        return (
            f"Complete the following task in a {environment} environment:\n\n"
            f"{query}\n\n"
            f"Use the {environment} interpreter to solve this interactively."
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for InterCode task.

        Args:
            task: InterCode task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "intercode_unknown")
        environment = task.get("environment", "bash")
        temp_task = {
            "instance_id": instance_id,
            "repo": f"intercode/{environment}",
            "base_commit": "HEAD",
        }
        env = await docker_manager.create_environment(temp_task)

        # Install environment-specific tools
        if environment == "sql":
            await env.exec_command(
                "apt-get update -qq && apt-get install -y -qq sqlite3 2>&1",
                timeout=120,
            )

        return env

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for InterCode task.

        Checks if the agent achieved the correct state.

        Args:
            env: Task environment.
            task: InterCode task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        gold_solution = task.get("gold_solution", "")
        environment = task.get("environment", "bash")

        if not gold_solution:
            return {"resolved": False, "error": "No gold solution available"}

        # Run gold solution and compare output
        if environment == "bash":
            cmd = gold_solution
        elif environment == "sql":
            cmd = f'echo "{gold_solution}" | sqlite3 database.db'
        elif environment == "python":
            cmd = f'python3 -c "{gold_solution}"'
        else:
            cmd = gold_solution

        exit_code_gold, stdout_gold, _ = await env.exec_command(cmd, timeout=30)
        exit_code_agent, stdout_agent, _ = await env.exec_command(
            "cat output.txt 2>/dev/null || echo ''",
            timeout=10,
        )

        resolved = stdout_gold.strip() == stdout_agent.strip()
        return {
            "resolved": resolved,
            "gold_output": stdout_gold[:500],
            "agent_output": stdout_agent[:500],
        }

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            task: InterCode task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get InterCode prompt template.

        Returns:
            Prompt template for interactive code tasks.
        """
        return (
            "Complete the following interactive coding task:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Use the code interpreter to solve the task\n"
            "- Test your solution iteratively\n"
            "- Debug any errors you encounter\n"
            "- Save your final output to 'output.txt'"
        )
