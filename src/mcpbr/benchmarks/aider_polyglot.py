"""Aider Polyglot benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class AiderPolyglotBenchmark:
    """Aider Polyglot benchmark implementation.

    The Aider Polyglot benchmark evaluates code editing capabilities across
    multiple programming languages. Based on Exercism coding exercises,
    it tests whether an AI can correctly modify existing code to pass
    provided test suites across Python, JavaScript, Go, Rust, and more.

    Evaluation runs language-specific test suites against the edited code.
    """

    name = "aider-polyglot"

    def __init__(self, dataset: str = "aider-ai/polyglot-benchmark"):
        """Initialize Aider Polyglot benchmark.

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
        """Load tasks from Aider Polyglot benchmark.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for Aider Polyglot.
            filter_difficulty: Unused for Aider Polyglot.
            filter_category: Filter by programming language.
            filter_tags: Unused for Aider Polyglot.

        Returns:
            List of Aider Polyglot task dictionaries.
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
            lang_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("language", "").lower() in lang_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("task_id", "") in task_id_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            task_id = task.get("task_id", str(idx))
            augmented["instance_id"] = f"aider_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert Aider Polyglot task to normalized format.

        Args:
            task: Aider Polyglot task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "aider_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo=task.get("repo", "aider/polyglot"),
            commit="HEAD",
            metadata={
                "language": task.get("language", ""),
                "exercise": task.get("exercise", ""),
                "source_file": task.get("source_file", ""),
                "test_file": task.get("test_file", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: Aider Polyglot task dictionary.

        Returns:
            Problem statement for the agent.
        """
        exercise = task.get("exercise", "unknown exercise")
        language = task.get("language", "unknown language")
        instructions = task.get("instructions", task.get("description", ""))
        source_file = task.get("source_file", "")

        statement = f"Edit the {language} code to solve the '{exercise}' exercise.\n\n"
        if instructions:
            statement += f"Instructions:\n{instructions}\n\n"
        if source_file:
            statement += f"Edit the file: {source_file}\n"
        statement += "Make the code pass all provided test cases."
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for Aider Polyglot task.

        Args:
            task: Aider Polyglot task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "aider_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": task.get("repo", "aider/polyglot"),
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for Aider Polyglot task.

        Runs the language-specific test suite against the edited code.

        Args:
            env: Task environment.
            task: Aider Polyglot task dictionary.
            solution: Solution (edited code) to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        test_cmd = task.get("test_command", "")
        if not test_cmd:
            language = task.get("language", "python").lower()
            test_cmds = {
                "python": "python3 -m pytest -xvs",
                "javascript": "npm test",
                "go": "go test ./...",
                "rust": "cargo test",
                "java": "mvn test",
            }
            test_cmd = test_cmds.get(language, "python3 -m pytest -xvs")

        exit_code, stdout, stderr = await env.exec_command(test_cmd, timeout=60)

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
            _task: Aider Polyglot task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get Aider Polyglot prompt template.

        Returns:
            Prompt template for code editing tasks.
        """
        return (
            "Edit the code to solve the following exercise:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Edit the existing source file to implement the solution\n"
            "- Ensure all tests pass\n"
            "- Follow the language's idiomatic patterns\n"
            "- Do not modify the test files"
        )
