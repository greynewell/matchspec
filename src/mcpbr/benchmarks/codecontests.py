"""CodeContests benchmark implementation."""

import json
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class CodeContestsBenchmark:
    """CodeContests benchmark implementation.

    CodeContests is a competitive programming benchmark from DeepMind
    containing problems from Codeforces, CodeChef, and other platforms.
    Problems include natural language descriptions with input/output
    specifications and multiple test cases.

    Evaluation runs the generated code against provided test cases.
    """

    name = "codecontests"

    def __init__(self, dataset: str = "deepmind/code_contests"):
        """Initialize CodeContests benchmark.

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
        """Load tasks from CodeContests dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Filter by difficulty rating.
            filter_difficulty: Filter by difficulty level.
            filter_category: Filter by source platform.
            filter_tags: Unused for CodeContests.

        Returns:
            List of CodeContests task dictionaries.
        """
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")
        tasks = list(dataset)

        if level is not None:
            tasks = [t for t in tasks if t.get("difficulty", 0) == level]

        if filter_difficulty:
            diff_set = {int(d) for d in filter_difficulty if d.isdigit()}
            if diff_set:
                tasks = [t for t in tasks if t.get("difficulty", 0) in diff_set]

        if filter_category:
            source_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if str(t.get("source", "")).lower() in source_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("name", "") in task_id_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            name = task.get("name", str(idx))
            augmented["instance_id"] = f"codecontests_{name}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert CodeContests task to normalized format.

        Args:
            task: CodeContests task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "codecontests_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="codecontests/competitive",
            commit="HEAD",
            metadata={
                "description": task.get("description", ""),
                "difficulty": task.get("difficulty", 0),
                "source": task.get("source", ""),
                "time_limit": task.get("time_limit", {}),
                "memory_limit": task.get("memory_limit_bytes", 0),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: CodeContests task dictionary.

        Returns:
            Problem statement for the agent.
        """
        description = task.get("description", "No description provided")
        difficulty = task.get("difficulty", "unknown")

        statement = (
            f"Solve the following competitive programming problem "
            f"(difficulty: {difficulty}):\n\n"
            f"{description}\n\n"
            f"Your solution should read from stdin and write to stdout.\n"
            f"Save your solution to a file named 'solution.py'."
        )

        # Add sample test cases if available
        public_tests = task.get("public_tests", {})
        if public_tests:
            inputs = public_tests.get("input", [])
            outputs = public_tests.get("output", [])
            if inputs and outputs:
                statement += "\n\nSample test cases:\n"
                for i, (inp, out) in enumerate(zip(inputs[:3], outputs[:3])):
                    statement += f"\nInput {i + 1}:\n{inp}\nExpected Output {i + 1}:\n{out}\n"

        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for CodeContests task.

        Args:
            task: CodeContests task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "codecontests_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "codecontests/competitive",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for CodeContests task.

        Runs the solution against both public and private test cases.

        Args:
            env: Task environment.
            task: CodeContests task dictionary.
            solution: Solution code to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        import base64

        # Gather test cases from both public and generated tests
        all_inputs: list[str] = []
        all_outputs: list[str] = []

        for test_key in ["public_tests", "private_tests", "generated_tests"]:
            tests = task.get(test_key, {})
            if isinstance(tests, str):
                try:
                    tests = json.loads(tests)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(tests, dict):
                all_inputs.extend(tests.get("input", []))
                all_outputs.extend(tests.get("output", []))

        if not all_inputs or not all_outputs:
            return {"resolved": False, "error": "No test cases available"}

        passed = 0
        total = min(len(all_inputs), len(all_outputs))

        for inp, expected in zip(all_inputs[:total], all_outputs[:total]):
            encoded_input = base64.b64encode(str(inp).encode()).decode()
            exit_code, stdout, stderr = await env.exec_command(
                f"echo '{encoded_input}' | base64 -d | timeout 10 python3 solution.py",
                timeout=15,
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

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            task: CodeContests task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get CodeContests prompt template.

        Returns:
            Prompt template for competitive programming problems.
        """
        return (
            "Solve the following competitive programming problem:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Read input from stdin and write output to stdout\n"
            "- Pay attention to time and memory constraints\n"
            "- Handle all edge cases\n"
            "- Save your solution to a file named 'solution.py'"
        )
