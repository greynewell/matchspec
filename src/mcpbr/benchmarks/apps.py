"""APPS benchmark implementation."""

import base64
import json
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class APPSBenchmark:
    """APPS benchmark implementation.

    APPS (Automated Programming Progress Standard) contains 10,000 coding
    problems collected from open-access coding websites. Problems span three
    difficulty levels: introductory, interview, and competition, with test
    cases and solutions provided.

    Evaluation runs the generated code against provided test cases.
    """

    name = "apps"

    def __init__(self, dataset: str = "metr-evals/apps", split: str = "test"):
        """Initialize APPS benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
            split: Dataset split to use.
        """
        self.dataset = dataset
        self.split = split

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from APPS dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for APPS.
            filter_difficulty: Filter by difficulty ('introductory', 'interview', 'competition').
            filter_category: Unused for APPS.
            filter_tags: Unused for APPS.

        Returns:
            List of APPS task dictionaries.
        """
        _ = level
        _ = filter_category
        _ = filter_tags

        dataset = load_dataset(self.dataset, split=self.split)

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = bool(task_ids) or bool(filter_difficulty)
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        tasks = list(dataset)

        if filter_difficulty:
            difficulty_set = {d.lower() for d in filter_difficulty}
            tasks = [t for t in tasks if t.get("difficulty", "").lower() in difficulty_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for i, t in enumerate(tasks) if str(i) in task_id_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            augmented["instance_id"] = f"apps_{idx}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert APPS task to normalized format.

        Args:
            task: APPS task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "apps_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="apps/code",
            commit="HEAD",
            metadata={
                "question": task.get("question", ""),
                "difficulty": task.get("difficulty", ""),
                "solutions": task.get("solutions", ""),
                "input_output": task.get("input_output", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: APPS task dictionary.

        Returns:
            Problem statement for the agent.
        """
        question = task.get("question", "No question provided")
        difficulty = task.get("difficulty", "unknown")

        return (
            f"Solve the following programming problem (difficulty: {difficulty}):\n\n"
            f"{question}\n\n"
            f"Your solution should read from stdin and write to stdout.\n"
            f"Save your solution to a file named 'solution.py'."
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for APPS task.

        Args:
            task: APPS task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "apps_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "apps/code",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for APPS task.

        Runs the solution against provided test cases.

        Args:
            env: Task environment.
            task: APPS task dictionary.
            solution: Solution code to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        # Write solution to container
        encoded_solution = base64.b64encode(solution.encode()).decode()
        exit_code, _stdout, stderr = await env.exec_command(
            f"printf '%s' '{encoded_solution}' | base64 -d > solution.py",
            timeout=10,
        )
        if exit_code != 0:
            return {"resolved": False, "error": f"Failed to write solution: {stderr[:500]}"}

        input_output = task.get("input_output", "")
        if not input_output:
            return {"resolved": False, "error": "No test cases provided"}

        try:
            test_cases = json.loads(input_output)
        except (json.JSONDecodeError, TypeError):
            return {"resolved": False, "error": "Could not parse test cases"}

        inputs = test_cases.get("inputs", [])
        outputs = test_cases.get("outputs", [])

        if not inputs or not outputs:
            return {"resolved": False, "error": "Empty test cases"}

        passed = 0
        total = min(len(inputs), len(outputs))

        for inp, expected in zip(inputs[:total], outputs[:total], strict=False):
            encoded_input = base64.b64encode(str(inp).encode()).decode()
            exit_code, stdout, _stderr = await env.exec_command(
                f"echo '{encoded_input}' | base64 -d | python3 solution.py",
                timeout=10,
            )
            if exit_code == 0 and stdout.strip() == str(expected).strip():
                passed += 1

        resolved = passed == total
        return {
            "resolved": resolved,
            "passed": passed,
            "total": total,
            "pass_rate": passed / total if total > 0 else 0.0,
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            task: APPS task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get APPS prompt template.

        Returns:
            Prompt template for APPS coding problems.
        """
        return (
            "Solve the following programming problem:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Read input from stdin and write output to stdout\n"
            "- Handle edge cases correctly\n"
            "- Save your solution to a file named 'solution.py'\n"
            "- Ensure your solution is efficient enough for the given constraints"
        )
