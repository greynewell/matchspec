"""MLAgentBench benchmark implementation."""

import re
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class MLAgentBenchBenchmark:
    """MLAgentBench benchmark implementation.

    MLAgentBench evaluates AI agents' ability to perform ML research tasks
    including training models, improving performance, debugging ML pipelines,
    and analyzing experimental results. Tasks are based on real Kaggle
    competitions and ML research challenges.

    Evaluation measures improvement in the target metric (accuracy, loss, etc.)
    compared to a baseline.
    """

    name = "mlagentbench"

    def __init__(self, dataset: str = "MLAgentBench/MLAgentBench"):
        """Initialize MLAgentBench benchmark.

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
        """Load tasks from MLAgentBench dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for MLAgentBench.
            filter_difficulty: Filter by difficulty.
            filter_category: Filter by ML domain (nlp, cv, tabular, etc.).
            filter_tags: Unused for MLAgentBench.

        Returns:
            List of MLAgentBench task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")
        tasks = list(dataset)

        if filter_category:
            cat_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if t.get("domain", "").lower() in cat_set]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("task_id", "") in task_id_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            task_id = task.get("task_id", str(idx))
            augmented["instance_id"] = f"mlagentbench_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert MLAgentBench task to normalized format.

        Args:
            task: MLAgentBench task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "mlagentbench_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo=task.get("repo", "mlagentbench/ml"),
            commit="HEAD",
            metadata={
                "research_problem": task.get("research_problem", ""),
                "domain": task.get("domain", ""),
                "metric": task.get("metric", ""),
                "baseline_score": task.get("baseline_score", None),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: MLAgentBench task dictionary.

        Returns:
            Problem statement for the agent.
        """
        research_problem = task.get(
            "research_problem", task.get("description", "No problem description provided")
        )
        metric = task.get("metric", "")
        baseline = task.get("baseline_score", "")

        statement = f"Complete the following ML research task:\n\n{research_problem}\n\n"
        if metric:
            statement += f"Target metric: {metric}\n"
        if baseline:
            statement += f"Baseline score: {baseline}\n"
        statement += "\nImprove upon the baseline and save your results."
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for MLAgentBench task.

        Args:
            task: MLAgentBench task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "mlagentbench_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": task.get("repo", "mlagentbench/ml"),
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for MLAgentBench task.

        Checks if the model achieved an improvement over baseline.

        Args:
            env: Task environment.
            task: MLAgentBench task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        # Try running the evaluation script if present
        eval_cmd = task.get("eval_command", "python3 evaluate.py")
        exit_code, stdout, stderr = await env.exec_command(eval_cmd, timeout=300)

        if exit_code != 0:
            return {
                "resolved": False,
                "error": f"Evaluation script failed: {stderr[:500]}",
            }

        score_match = re.search(r"(?:score|accuracy|loss|metric)\s*[=:]\s*([0-9.]+)", stdout, re.I)
        if score_match:
            score = float(score_match.group(1))
            baseline = task.get("baseline_score", 0)
            try:
                baseline_val = float(baseline) if baseline else 0.0
                resolved = score > baseline_val
            except (ValueError, TypeError):
                baseline_val = 0.0
                resolved = True
            return {
                "resolved": resolved,
                "score": score,
                "baseline": baseline_val,
            }

        return {
            "resolved": exit_code == 0,
            "stdout": stdout[:1000],
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: MLAgentBench task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get MLAgentBench prompt template.

        Returns:
            Prompt template for ML research tasks.
        """
        return (
            "Complete the following ML research task:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Analyze the existing code and data\n"
            "- Develop and test your approach\n"
            "- Improve upon the baseline performance\n"
            "- Save your implementation and results"
        )
