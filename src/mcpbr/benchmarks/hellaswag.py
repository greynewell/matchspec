"""HellaSwag benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class HellaSwagBenchmark:
    """HellaSwag benchmark implementation.

    HellaSwag is a commonsense reasoning benchmark where the model must
    choose the most plausible continuation of a given scenario from four
    options. The dataset was adversarially filtered to be challenging for
    language models while easy for humans (~95% accuracy).

    Evaluation checks if the model selects the correct continuation.
    """

    name = "hellaswag"

    def __init__(self, dataset: str = "Rowan/hellaswag"):
        """Initialize HellaSwag benchmark.

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
        """Load tasks from HellaSwag dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for HellaSwag.
            filter_difficulty: Unused for HellaSwag.
            filter_category: Filter by activity label.
            filter_tags: Unused for HellaSwag.

        Returns:
            List of HellaSwag task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="validation")
        tasks = list(dataset)

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("ind", "") in task_id_set]

        if filter_category:
            category_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("activity_label", "").lower() in category_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for task in tasks:
            augmented = dict(task)
            augmented["instance_id"] = f"hellaswag_{task.get('ind', len(augmented_tasks))}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert HellaSwag task to normalized format.

        Args:
            task: HellaSwag task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "hellaswag_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="hellaswag/commonsense",
            commit="HEAD",
            metadata={
                "ctx": task.get("ctx", ""),
                "endings": task.get("endings", []),
                "label": task.get("label", ""),
                "activity_label": task.get("activity_label", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: HellaSwag task dictionary.

        Returns:
            Problem statement for the agent.
        """
        ctx = task.get("ctx", "No context provided")
        endings = task.get("endings", [])

        statement = "Read the following scenario and choose the most plausible continuation.\n\n"
        statement += f"Scenario: {ctx}\n\n"
        statement += "Options:\n"
        for i, ending in enumerate(endings):
            statement += f"  ({i}) {ending}\n"
        statement += "\nProvide only the number of the correct option (0, 1, 2, or 3)."
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for HellaSwag task.

        Args:
            task: HellaSwag task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "hellaswag_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "hellaswag/commonsense",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for HellaSwag task.

        Checks if the selected option matches the correct label.

        Args:
            env: Task environment.
            task: HellaSwag task dictionary.
            solution: Solution to evaluate (should contain option number).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        label = task.get("label", "")
        if label == "":
            return {"resolved": False, "error": "No label available"}

        correct_label = str(label)

        # Extract the selected option from the solution
        import re

        # Look for a single digit that represents the answer
        matches = re.findall(r"\b([0-3])\b", solution)
        if not matches:
            return {"resolved": False, "error": "Could not extract option number from solution"}

        # Use the last mentioned number as the answer
        agent_answer = matches[-1]
        resolved = agent_answer == correct_label

        return {
            "resolved": resolved,
            "agent_answer": agent_answer,
            "correct_label": correct_label,
        }

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            task: HellaSwag task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get HellaSwag prompt template.

        Returns:
            Prompt template for commonsense reasoning.
        """
        return (
            "Choose the most plausible continuation:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Read the scenario carefully\n"
            "- Consider what would most likely happen next\n"
            "- Respond with ONLY the option number (0, 1, 2, or 3)"
        )
