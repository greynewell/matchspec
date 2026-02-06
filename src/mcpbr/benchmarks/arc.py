"""ARC (AI2 Reasoning Challenge) benchmark implementation."""

import re
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class ARCBenchmark:
    """ARC benchmark implementation.

    The AI2 Reasoning Challenge (ARC) consists of 7,787 genuine grade-school
    level science questions. It is partitioned into a Challenge Set (hard
    questions that require reasoning) and an Easy Set. Questions are
    multiple-choice with 3-5 answer options.

    Evaluation checks if the model selects the correct answer label.
    """

    name = "arc"

    def __init__(self, dataset: str = "allenai/ai2_arc", subset: str = "ARC-Challenge"):
        """Initialize ARC benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
            subset: Dataset subset ('ARC-Challenge' or 'ARC-Easy').
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
        """Load tasks from ARC dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for ARC.
            filter_difficulty: Filter by 'challenge' or 'easy'.
            filter_category: Unused for ARC.
            filter_tags: Unused for ARC.

        Returns:
            List of ARC task dictionaries.
        """
        _ = level
        _ = filter_category
        _ = filter_tags

        subset = self.subset
        if filter_difficulty:
            if "easy" in [d.lower() for d in filter_difficulty]:
                subset = "ARC-Easy"
            elif "challenge" in [d.lower() for d in filter_difficulty]:
                subset = "ARC-Challenge"

        dataset = load_dataset(self.dataset, subset, split="test")

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = bool(task_ids)
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        tasks = list(dataset)

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("id", "") in task_id_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for task in tasks:
            augmented = dict(task)
            augmented["instance_id"] = f"arc_{task.get('id', len(augmented_tasks))}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert ARC task to normalized format.

        Args:
            task: ARC task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", f"arc_{task.get('id', 'unknown')}")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="arc/science",
            commit="HEAD",
            metadata={
                "question": task.get("question", ""),
                "choices": task.get("choices", {}),
                "answerKey": task.get("answerKey", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: ARC task dictionary.

        Returns:
            Problem statement for the agent.
        """
        question = task.get("question", "No question provided")
        choices = task.get("choices", {})

        statement = f"Answer the following science question:\n\n{question}\n\n"

        labels = choices.get("label", [])
        texts = choices.get("text", [])
        if labels and texts:
            statement += "Options:\n"
            for label, text in zip(labels, texts, strict=True):
                statement += f"  ({label}) {text}\n"

        statement += "\nProvide only the letter of the correct answer."
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for ARC task.

        Args:
            task: ARC task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "arc_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "arc/science",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        _env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for ARC task.

        Checks if the selected answer matches the correct answer key.

        Args:
            _env: Task environment (unused; evaluation is offline).
            task: ARC task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        answer_key = task.get("answerKey", "")
        if not answer_key:
            return {"resolved": False, "error": "No answer key available"}

        # Look for a single letter answer (A, B, C, D, E or 1, 2, 3, 4)
        matches = re.findall(r"\b([A-E1-5])\b", solution.upper())
        if not matches:
            return {"resolved": False, "error": "Could not extract answer from solution"}

        agent_answer = matches[-1]
        resolved = agent_answer.upper() == answer_key.upper()

        return {
            "resolved": resolved,
            "agent_answer": agent_answer,
            "correct_answer": answer_key,
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: ARC task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get ARC prompt template.

        Returns:
            Prompt template for science questions.
        """
        return (
            "Answer the following science question:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Think about the scientific concepts involved\n"
            "- Consider each answer option carefully\n"
            "- Respond with ONLY the letter of the correct answer (A, B, C, D, or E)"
        )
