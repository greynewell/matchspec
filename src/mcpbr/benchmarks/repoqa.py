"""RepoQA benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class RepoQABenchmark:
    """RepoQA benchmark implementation.

    RepoQA evaluates long-context code understanding by testing whether
    models can find and describe specific functions within large repositories.
    The "Searching Needle Function" task requires identifying a target function
    from a full repository context.

    Evaluation checks if the model correctly identifies the target function
    by name (substring match).
    """

    name = "repoqa"

    def __init__(self, dataset: str = "evaluating/RepoQA"):
        """Initialize RepoQA benchmark.

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
        """Load tasks from RepoQA dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for RepoQA.
            filter_difficulty: Unused for RepoQA.
            filter_category: Filter by programming language.
            filter_tags: Unused for RepoQA.

        Returns:
            List of RepoQA task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")
        tasks = list(dataset)

        if filter_category:
            lang_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("language", "").lower() in lang_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for i, t in enumerate(tasks) if str(i) in task_id_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            augmented["instance_id"] = f"repoqa_{idx}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert RepoQA task to normalized format.

        Args:
            task: RepoQA task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "repoqa_unknown")
        repo = task.get("repo", "repoqa/code")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo=repo,
            commit="HEAD",
            metadata={
                "function_name": task.get("function_name", ""),
                "language": task.get("language", ""),
                "description": task.get("description", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: RepoQA task dictionary.

        Returns:
            Problem statement for the agent.
        """
        description = task.get("description", "")
        repo = task.get("repo", "the repository")
        language = task.get("language", "")

        return (
            f"Find and describe the function in {repo} ({language}) that matches "
            f"the following description:\n\n"
            f"{description}\n\n"
            f"Identify the function name and explain what it does."
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for RepoQA task.

        Args:
            task: RepoQA task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "repoqa_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": task.get("repo", "repoqa/code"),
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for RepoQA task.

        Checks if the model correctly identified the target function.

        Args:
            env: Task environment.
            task: RepoQA task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        target_function = task.get("function_name", "")
        if not target_function:
            return {"resolved": False, "error": "No target function specified"}

        # Check if the function name appears in the solution
        resolved = target_function.lower() in solution.lower()
        return {
            "resolved": resolved,
            "target_function": target_function,
            "function_found": resolved,
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: RepoQA task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get RepoQA prompt template.

        Returns:
            Prompt template for repository QA.
        """
        return (
            "Find and describe the target function in the repository:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Search through the repository code\n"
            "- Identify the function matching the description\n"
            "- Provide the exact function name\n"
            "- Explain what the function does"
        )
