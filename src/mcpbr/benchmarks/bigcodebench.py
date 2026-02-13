"""BigCodeBench benchmark implementation."""

import base64
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class BigCodeBenchBenchmark:
    """BigCodeBench benchmark implementation.

    BigCodeBench evaluates LLMs on practical and challenging coding tasks
    that require composing multiple function calls from diverse libraries.
    It includes 1,140 tasks covering 139 libraries across 7 domains.

    Evaluation runs generated code against provided test cases.
    """

    name = "bigcodebench"

    def __init__(self, dataset: str = "bigcode/bigcodebench"):
        """Initialize BigCodeBench benchmark.

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
        """Load tasks from BigCodeBench dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for BigCodeBench.
            filter_difficulty: Unused for BigCodeBench.
            filter_category: Filter by domain/library.
            filter_tags: Filter by library tags.

        Returns:
            List of BigCodeBench task dictionaries.
        """
        _ = level
        _ = filter_difficulty

        dataset = load_dataset(self.dataset, split="v0.1.2")

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = bool(task_ids) or bool(filter_category) or bool(filter_tags)
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        tasks = list(dataset)

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("task_id", "") in task_id_set]

        if filter_category:
            category_set = {c.lower() for c in filter_category}
            tasks = [
                t for t in tasks if any(c in t.get("domain", "").lower() for c in category_set)
            ]

        if filter_tags:
            tasks = [
                t
                for t in tasks
                if all(
                    tag.lower() in [lib.lower() for lib in t.get("libs", [])] for tag in filter_tags
                )
            ]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks: list[dict[str, Any]] = []
        for task in tasks:
            augmented = dict(task)
            task_id = task.get("task_id", str(len(augmented_tasks)))
            augmented["instance_id"] = f"bigcodebench_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert BigCodeBench task to normalized format.

        Args:
            task: BigCodeBench task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "bigcodebench_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="bigcodebench/code",
            commit="HEAD",
            metadata={
                "instruct_prompt": task.get("instruct_prompt", ""),
                "complete_prompt": task.get("complete_prompt", ""),
                "test": task.get("test", ""),
                "libs": task.get("libs", []),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: BigCodeBench task dictionary.

        Returns:
            Problem statement for the agent.
        """
        prompt = task.get("instruct_prompt", "") or task.get("complete_prompt", "")
        libs = task.get("libs", [])

        statement = f"Complete the following coding task:\n\n{prompt}\n\n"
        if libs:
            statement += f"Required libraries: {', '.join(libs)}\n\n"
        statement += "Save your implementation to a file named 'solution.py'."
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for BigCodeBench task.

        Args:
            task: BigCodeBench task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "bigcodebench_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "bigcodebench/code",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for BigCodeBench task.

        Runs the test cases against the generated code.

        Args:
            env: Task environment.
            task: BigCodeBench task dictionary.
            solution: Solution code to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        test_code = task.get("test", "")
        if not test_code:
            return {"resolved": False, "error": "No test code provided"}

        # Combine solution and test code
        full_test = f"{solution}\n\n{test_code}\n"
        encoded = base64.b64encode(full_test.encode()).decode()

        exit_code, stdout, stderr = await env.exec_command(
            f"echo '{encoded}' | base64 -d > test_solution.py && python3 test_solution.py",
            timeout=60,
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
            _task: BigCodeBench task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get BigCodeBench prompt template.

        Returns:
            Prompt template for BigCodeBench tasks.
        """
        return (
            "Complete the following coding task:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Implement the function as specified\n"
            "- Use the required libraries correctly\n"
            "- Ensure your code handles edge cases\n"
            "- Save your implementation to 'solution.py'"
        )

    def get_default_sandbox_level(self) -> str | None:
        return None
