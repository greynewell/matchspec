"""WebArena benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class WebArenaBenchmark:
    """WebArena benchmark implementation.

    WebArena is a realistic web environment for evaluating autonomous agents.
    It includes functional websites (e-commerce, forums, content management,
    maps, etc.) with tasks that require web navigation, form filling,
    information retrieval, and multi-step interactions.

    Evaluation checks task completion by verifying the final browser state
    or extracted information against expected outcomes.
    """

    name = "webarena"

    def __init__(self, dataset: str = "WebArena/WebArena"):
        """Initialize WebArena benchmark.

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
        """Load tasks from WebArena dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for WebArena.
            filter_difficulty: Filter by difficulty.
            filter_category: Filter by website/domain type.
            filter_tags: Unused for WebArena.

        Returns:
            List of WebArena task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        dataset = load_dataset(self.dataset, split="test")
        tasks = list(dataset)

        if filter_category:
            site_set = {c.lower() for c in filter_category}
            tasks = [
                t for t in tasks if any(s in str(t.get("sites", [])).lower() for s in site_set)
            ]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if str(t.get("task_id", "")) in task_id_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            task_id = task.get("task_id", str(idx))
            augmented["instance_id"] = f"webarena_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert WebArena task to normalized format.

        Args:
            task: WebArena task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "webarena_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="webarena/web",
            commit="HEAD",
            metadata={
                "intent": task.get("intent", ""),
                "sites": task.get("sites", []),
                "eval_type": task.get("eval", {}).get("eval_types", []),
                "reference_answer": task.get("eval", {}).get("reference_answers", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: WebArena task dictionary.

        Returns:
            Problem statement for the agent.
        """
        intent = task.get("intent", task.get("description", "No task description provided"))
        sites = task.get("sites", [])

        statement = f"Complete the following web task:\n\n{intent}\n\n"
        if sites:
            statement += f"Available websites: {', '.join(str(s) for s in sites)}\n"
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for WebArena task.

        Args:
            task: WebArena task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "webarena_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "webarena/web",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for WebArena task.

        Verifies task completion against expected outcomes.

        Args:
            env: Task environment.
            task: WebArena task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        eval_info = task.get("eval", {})
        reference = eval_info.get("reference_answers", "")

        if not reference:
            return {"resolved": False, "error": "No reference answer available"}

        # Basic evaluation: check if reference answer appears in solution
        if isinstance(reference, str):
            resolved = reference.strip().lower() in solution.strip().lower()
        elif isinstance(reference, dict):
            # Handle structured reference answers
            must_include = reference.get("must_include", [])
            resolved = all(
                item.lower() in solution.lower() for item in must_include if isinstance(item, str)
            )
        else:
            resolved = False

        return {
            "resolved": resolved,
            "agent_output": solution[:500],
            "reference": str(reference)[:500],
        }

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: WebArena task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get WebArena prompt template.

        Returns:
            Prompt template for web navigation tasks.
        """
        return (
            "Complete the following web browsing task:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Navigate the web interface to complete the task\n"
            "- Interact with forms, buttons, and links as needed\n"
            "- Provide any requested information in your response\n"
            "- Be precise with your final answer"
        )
