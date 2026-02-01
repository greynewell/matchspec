"""BigBench-Hard benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class BigBenchHardBenchmark:
    """BigBench-Hard benchmark implementation.

    BigBench-Hard (BBH) consists of 23 challenging tasks from the BIG-Bench
    suite where prior language model evaluations fell below average human
    performance. Tasks include boolean expressions, causal judgement,
    date understanding, disambiguation QA, formal fallacies, and more.

    Evaluation uses exact match on the extracted answer.
    """

    name = "bigbench-hard"

    def __init__(self, dataset: str = "lukaemon/bbh"):
        """Initialize BigBench-Hard benchmark.

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
        """Load tasks from BigBench-Hard dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for BBH.
            filter_difficulty: Unused for BBH.
            filter_category: Filter by BBH subtask name.
            filter_tags: Unused for BBH.

        Returns:
            List of BBH task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        # BBH has multiple subtasks; load a default or filter by category
        subtasks = [
            "boolean_expressions",
            "causal_judgement",
            "date_understanding",
            "disambiguation_qa",
            "formal_fallacies",
            "geometric_shapes",
            "hyperbaton",
            "logical_deduction_five_objects",
            "movie_recommendation",
            "navigate",
            "object_counting",
            "penguins_in_a_table",
            "reasoning_about_colored_objects",
            "ruin_names",
            "salient_translation_error_detection",
            "snarks",
            "sports_understanding",
            "temporal_sequences",
            "tracking_shuffled_objects_five_objects",
            "web_of_lies",
            "word_sorting",
        ]

        if filter_category:
            subtasks = [s for s in subtasks if s in filter_category]

        all_tasks: list[dict[str, Any]] = []
        for subtask in subtasks:
            try:
                ds = load_dataset(self.dataset, subtask, split="test")
                for idx, item in enumerate(ds):
                    task = dict(item)
                    task["subtask"] = subtask
                    task["instance_id"] = f"bbh_{subtask}_{idx}"
                    all_tasks.append(task)
            except Exception:
                continue

        if task_ids:
            task_id_set = set(task_ids)
            all_tasks = [t for t in all_tasks if t["instance_id"] in task_id_set]

        if sample_size and len(all_tasks) > sample_size:
            all_tasks = all_tasks[:sample_size]

        for task in all_tasks:
            task["problem_statement"] = self._generate_problem_statement(task)

        return all_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert BBH task to normalized format.

        Args:
            task: BBH task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "bbh_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="bigbench/hard",
            commit="HEAD",
            metadata={
                "input": task.get("input", ""),
                "target": task.get("target", ""),
                "subtask": task.get("subtask", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: BBH task dictionary.

        Returns:
            Problem statement for the agent.
        """
        input_text = task.get("input", "No input provided")
        subtask = task.get("subtask", "unknown")

        return (
            f"Solve the following reasoning task ({subtask}):\n\n"
            f"{input_text}\n\n"
            f"Think step-by-step and provide your final answer."
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for BBH task.

        Args:
            task: BBH task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "bbh_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "bigbench/hard",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for BBH task.

        Uses exact match on the extracted answer.

        Args:
            env: Task environment.
            task: BBH task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        target = task.get("target", "")
        if not target:
            return {"resolved": False, "error": "No target answer available"}

        # Normalize both for comparison
        target_norm = target.strip().lower()
        solution_norm = solution.strip().lower()

        # Check if target appears in solution (exact substring match)
        resolved = target_norm in solution_norm
        return {
            "resolved": resolved,
            "agent_answer": solution[:500],
            "target": target,
        }

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            task: BBH task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get BBH prompt template.

        Returns:
            Prompt template for reasoning tasks.
        """
        return (
            "Solve the following reasoning challenge:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Think carefully step-by-step\n"
            "- Show your reasoning process\n"
            "- Provide a clear, definitive final answer"
        )
