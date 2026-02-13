"""MBPP (Mostly Basic Python Problems) benchmark implementation."""

import base64
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class MBPPBenchmark:
    """MBPP benchmark implementation.

    MBPP consists of ~1000 crowd-sourced Python programming problems
    designed to be solvable by entry-level programmers. Each task includes
    a problem description, a function signature, and test cases.

    Evaluation runs the provided test cases against the generated code.
    """

    name = "mbpp"

    def __init__(self, dataset: str = "google-research-datasets/mbpp", subset: str = "full"):
        """Initialize MBPP benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
            subset: Dataset subset (default: 'full').
        """
        self.dataset = dataset
        self.subset = subset

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from MBPP dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for MBPP.
            filter_difficulty: Unused for MBPP.
            filter_category: Unused for MBPP.
            filter_tags: Unused for MBPP.

        Returns:
            List of MBPP task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_category
        _ = filter_tags

        dataset = load_dataset(self.dataset, self.subset, split="test")

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = bool(task_ids)
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [item for item in dataset if str(item.get("task_id", "")) in task_id_set]
        else:
            tasks = list(dataset)

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks: list[dict[str, Any]] = []
        for task in tasks:
            augmented = dict(task)
            task_id = str(task.get("task_id", len(augmented_tasks)))
            augmented["instance_id"] = f"mbpp_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert MBPP task to normalized format.

        Args:
            task: MBPP task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", f"mbpp_{task.get('task_id', 'unknown')}")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="mbpp/code",
            commit="HEAD",
            metadata={
                "text": task.get("text", ""),
                "code": task.get("code", ""),
                "test_list": task.get("test_list", []),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: MBPP task dictionary.

        Returns:
            Problem statement for the agent.
        """
        text = task.get("text", "No description provided")
        test_list = task.get("test_list", [])

        statement = f"Write a Python function to solve the following problem:\n\n{text}\n\n"
        if test_list:
            statement += "Example test cases:\n"
            for test in test_list[:3]:
                statement += f"  {test}\n"
        statement += "\nSave your implementation to a file named 'solution.py'."
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for MBPP task.

        Args:
            task: MBPP task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "mbpp_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "mbpp/code",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for MBPP task.

        Runs the test cases against the generated code.

        Args:
            env: Task environment.
            task: MBPP task dictionary.
            solution: Solution code to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        test_list = task.get("test_list", [])
        if not test_list:
            return {"resolved": False, "error": "No test cases provided"}

        # Write solution and test file
        test_code = f"{solution}\n\n"
        for test in test_list:
            test_code += f"{test}\n"
        test_code += "\nprint('ALL_TESTS_PASSED')\n"

        encoded = base64.b64encode(test_code.encode()).decode()
        exit_code, stdout, stderr = await env.exec_command(
            f"echo '{encoded}' | base64 -d > test_solution.py && python3 test_solution.py",
            timeout=30,
        )

        passed = exit_code == 0 and "ALL_TESTS_PASSED" in stdout
        return {
            "resolved": passed,
            "exit_code": exit_code,
            "stdout": stdout[:1000] if stdout else "",
            "stderr": stderr[:1000] if stderr else "",
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for MBPP task.

        Args:
            _task: MBPP task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get MBPP prompt template.

        Returns:
            Prompt template for MBPP tasks.
        """
        return (
            "Write a Python function to solve the following problem:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Write clean, correct Python code\n"
            "- Ensure your implementation passes all test cases\n"
            "- Save your implementation to a file named 'solution.py'\n"
            "- Include ONLY the function implementation in the file"
        )

    def get_default_sandbox_level(self) -> str | None:
        return None
