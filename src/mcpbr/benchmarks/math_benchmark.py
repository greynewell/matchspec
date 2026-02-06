"""MATH benchmark implementation."""

import re
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class MATHBenchmark:
    """MATH benchmark implementation.

    The MATH dataset contains 12,500 competition mathematics problems from
    AMC, AIME, and other competitions. Problems span 7 subjects (algebra,
    counting/probability, geometry, intermediate algebra, number theory,
    prealgebra, precalculus) and 5 difficulty levels.

    Evaluation compares the final answer against ground truth, supporting
    LaTeX and numeric formats.
    """

    name = "math"

    def __init__(self, dataset: str = "DigitalLearningGmbH/MATH-lighteval"):
        """Initialize MATH benchmark.

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
        """Load tasks from MATH dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Filter by difficulty level (1-5).
            filter_difficulty: Filter by difficulty level strings.
            filter_category: Filter by math subject (algebra, geometry, etc.).
            filter_tags: Unused for MATH.

        Returns:
            List of MATH task dictionaries.
        """
        _ = filter_tags

        dataset = load_dataset(self.dataset, "default", split="test")

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = (
            bool(task_ids) or bool(filter_difficulty) or bool(filter_category) or bool(level)
        )
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        tasks = list(dataset)

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for i, t in enumerate(tasks) if str(i) in task_id_set]

        if level is not None:
            tasks = [t for t in tasks if t.get("level", "").endswith(str(level))]

        if filter_difficulty:
            tasks = [t for t in tasks if any(d in t.get("level", "") for d in filter_difficulty)]

        if filter_category:
            category_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("type", "").lower() in category_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            augmented["instance_id"] = f"math_{idx}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert MATH task to normalized format.

        Args:
            task: MATH task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "math_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="math/competition",
            commit="HEAD",
            metadata={
                "problem": task.get("problem", ""),
                "solution": task.get("solution", ""),
                "level": task.get("level", ""),
                "type": task.get("type", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: MATH task dictionary.

        Returns:
            Problem statement for the agent.
        """
        problem = task.get("problem", "No problem provided")
        level = task.get("level", "Unknown")
        subject = task.get("type", "Unknown")

        return (
            f"Solve the following competition math problem.\n"
            f"Subject: {subject} | Difficulty: {level}\n\n"
            f"{problem}\n\n"
            f"Show your work step-by-step and provide your final answer "
            f"in the format: \\boxed{{answer}}"
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for MATH task.

        Args:
            task: MATH task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "math_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "math/competition",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        _env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for MATH task.

        Extracts the answer from the solution and compares it to ground truth.

        Args:
            _env: Task environment (unused; evaluation is offline).
            task: MATH task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        ground_truth = task.get("solution", "")
        gt_answer = self._extract_boxed_answer(ground_truth)
        agent_answer = self._extract_boxed_answer(solution)

        if gt_answer is None:
            return {"resolved": False, "error": "Could not parse ground truth answer"}
        if agent_answer is None:
            return {"resolved": False, "error": "Could not extract answer from solution"}

        resolved = self._normalize_answer(agent_answer) == self._normalize_answer(gt_answer)
        return {
            "resolved": resolved,
            "agent_answer": agent_answer,
            "ground_truth_answer": gt_answer,
        }

    def _extract_boxed_answer(self, text: str) -> str | None:
        """Extract answer from \\boxed{} or last line.

        Args:
            text: Text containing the answer.

        Returns:
            Extracted answer string or None.
        """
        if not text:
            return None

        # Try \\boxed{...} pattern (handles nested braces up to 2 levels)
        match = re.search(r"\\boxed\{([^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}[^{}]*)*)\}", text)
        if match:
            return match.group(1).strip()

        # Fallback: look for "answer is" pattern
        match = re.search(r"(?:the\s+)?(?:final\s+)?answer\s*(?:is|:)\s*(.+?)(?:\.|$)", text, re.I)
        if match:
            return match.group(1).strip()

        return None

    def _normalize_answer(self, answer: str) -> str:
        """Normalize answer for comparison.

        Args:
            answer: Answer string.

        Returns:
            Normalized answer string.
        """
        # Remove whitespace, convert fractions, normalize LaTeX
        normalized = answer.strip()
        normalized = re.sub(r"\s+", "", normalized)
        normalized = normalized.replace("\\left", "").replace("\\right", "")
        normalized = normalized.replace("\\,", "")
        return normalized

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: MATH task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get MATH prompt template.

        Returns:
            Prompt template for competition math problems.
        """
        return (
            "Solve the following competition math problem:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Show your complete reasoning step-by-step\n"
            "- Use rigorous mathematical notation\n"
            "- Provide your final answer in \\boxed{answer} format\n"
            "- You may use Python/SymPy for verification"
        )
