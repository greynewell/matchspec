"""CoderEval benchmark implementation."""

import base64
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class CoderEvalBenchmark:
    """CoderEval benchmark implementation.

    CoderEval evaluates pragmatic code generation from real-world open-source
    projects. Unlike standalone function generation benchmarks, CoderEval tests
    generation in the context of an actual codebase with dependencies on
    project-specific types, functions, and libraries.

    Evaluation runs project-specific test cases against generated code.
    """

    name = "codereval"

    def __init__(self, dataset: str = "CoderEval/CoderEval"):
        """Initialize CoderEval benchmark.

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
        """Load tasks from CoderEval dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Filter by dependency level.
            filter_difficulty: Filter by difficulty level.
            filter_category: Filter by programming language.
            filter_tags: Unused for CoderEval.

        Returns:
            List of CoderEval task dictionaries.
        """
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")
        tasks = list(dataset)

        if level is not None:
            tasks = [t for t in tasks if t.get("level", 0) == level]

        if filter_difficulty:
            diff_set = {d.lower() for d in filter_difficulty}
            tasks = [t for t in tasks if t.get("difficulty", "").lower() in diff_set]

        if filter_category:
            lang_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("language", "").lower() in lang_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("task_id", "") in task_id_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            task_id = task.get("task_id", str(idx))
            augmented["instance_id"] = f"codereval_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert CoderEval task to normalized format.

        Args:
            task: CoderEval task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "codereval_unknown")
        repo = task.get("repo", "codereval/code")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo=repo,
            commit=task.get("commit", "HEAD"),
            metadata={
                "function_name": task.get("function_name", ""),
                "language": task.get("language", ""),
                "context": task.get("context", ""),
                "test": task.get("test", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: CoderEval task dictionary.

        Returns:
            Problem statement for the agent.
        """
        function_name = task.get("function_name", "unknown")
        language = task.get("language", "Python")
        context = task.get("context", "")
        docstring = task.get("docstring", "")

        statement = f"Implement the function '{function_name}' in {language}.\n\n"
        if docstring:
            statement += f"Documentation:\n{docstring}\n\n"
        if context:
            statement += f"Context (surrounding code):\n```\n{context[:2000]}\n```\n\n"
        extensions = {"python": "py", "java": "java", "c": "c", "cpp": "cpp", "go": "go"}
        ext = extensions.get(language.lower(), "py")
        filename = f"solution.{ext}"
        statement += f"Save your implementation to a file named '{filename}'."
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for CoderEval task.

        Args:
            task: CoderEval task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "codereval_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": task.get("repo", "codereval/code"),
            "base_commit": task.get("commit", "HEAD"),
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for CoderEval task.

        Runs project-specific tests against the generated code.

        Args:
            env: Task environment.
            task: CoderEval task dictionary.
            solution: Solution code to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        test_code = task.get("test", "")
        if not test_code:
            return {"resolved": False, "error": "No test code provided"}

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
            task: CoderEval task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get CoderEval prompt template.

        Returns:
            Prompt template for pragmatic code generation.
        """
        return (
            "Implement the following function in the context of a real-world project:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Consider the project context and dependencies\n"
            "- Follow the existing code style\n"
            "- Ensure compatibility with project-specific types\n"
            "- Save your implementation to 'solution.py'"
        )
