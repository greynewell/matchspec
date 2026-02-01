"""GAIA benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class GAIABenchmark:
    """GAIA benchmark implementation.

    GAIA (General AI Assistants) is a benchmark proposing real-world questions
    that require a set of fundamental abilities such as reasoning, multi-modality
    handling, web browsing, and tool use. Questions have unambiguous, fact-based
    answers that are easy to verify.

    Tasks are categorized into three difficulty levels (1-3).
    Evaluation uses exact match on the final answer.
    """

    name = "gaia"

    def __init__(self, dataset: str = "gaia-benchmark/GAIA", subset: str = "2023_all"):
        """Initialize GAIA benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
            subset: Dataset subset/version.
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
        """Load tasks from GAIA dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Filter by difficulty level (1, 2, or 3).
            filter_difficulty: Filter by difficulty level strings.
            filter_category: Unused for GAIA.
            filter_tags: Unused for GAIA.

        Returns:
            List of GAIA task dictionaries.
        """
        _ = filter_category
        _ = filter_tags

        dataset = load_dataset(self.dataset, self.subset, split="validation")
        tasks = list(dataset)

        if level is not None:
            tasks = [t for t in tasks if t.get("Level", 0) == level]

        if filter_difficulty:
            diff_set = {int(d) for d in filter_difficulty if d.isdigit()}
            if diff_set:
                tasks = [t for t in tasks if t.get("Level", 0) in diff_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("task_id", "") in task_id_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for task in tasks:
            augmented = dict(task)
            task_id = task.get("task_id", str(len(augmented_tasks)))
            augmented["instance_id"] = f"gaia_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert GAIA task to normalized format.

        Args:
            task: GAIA task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "gaia_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="gaia/assistant",
            commit="HEAD",
            metadata={
                "question": task.get("Question", ""),
                "level": task.get("Level", 0),
                "final_answer": task.get("Final answer", ""),
                "annotator_metadata": task.get("Annotator Metadata", {}),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: GAIA task dictionary.

        Returns:
            Problem statement for the agent.
        """
        question = task.get("Question", "No question provided")
        level = task.get("Level", "unknown")

        return (
            f"Answer the following question (difficulty level {level}):\n\n"
            f"{question}\n\n"
            f"Provide a concise, factual answer."
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for GAIA task.

        Args:
            task: GAIA task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "gaia_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "gaia/assistant",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for GAIA task.

        Uses exact match on the final answer.

        Args:
            env: Task environment.
            task: GAIA task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        final_answer = task.get("Final answer", "")
        if not final_answer:
            return {"resolved": False, "error": "No ground truth answer available"}

        # Normalize both answers for comparison
        gt_normalized = final_answer.strip().lower()
        solution_normalized = solution.strip().lower()

        # Check for exact match or containment
        resolved = gt_normalized == solution_normalized or gt_normalized in solution_normalized

        return {
            "resolved": resolved,
            "agent_answer": solution[:500],
            "ground_truth": final_answer,
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: GAIA task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get GAIA prompt template.

        Returns:
            Prompt template for general AI assistant tasks.
        """
        return (
            "Answer the following question:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Provide a precise, factual answer\n"
            "- Use tools and web search if needed\n"
            "- Show your reasoning but be concise in your final answer\n"
            "- The answer should be unambiguous"
        )
