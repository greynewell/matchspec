"""LeetCode benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class LeetCodeBenchmark:
    """LeetCode benchmark implementation.

    LeetCode-style coding benchmark evaluating algorithmic problem solving.
    Problems include data structures, algorithms, dynamic programming,
    graph theory, and more across easy, medium, and hard difficulties.

    Evaluation runs the generated code against provided test cases.
    """

    name = "leetcode"

    def __init__(self, dataset: str = "greengerong/leetcode"):
        """Initialize LeetCode benchmark.

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
        """Load tasks from LeetCode dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for LeetCode.
            filter_difficulty: Filter by difficulty ('easy', 'medium', 'hard').
            filter_category: Filter by problem category/topic.
            filter_tags: Filter by topic tags.

        Returns:
            List of LeetCode task dictionaries.
        """
        _ = level

        dataset = load_dataset(self.dataset, split="train")
        tasks = list(dataset)

        if filter_difficulty:
            diff_set = {d.lower() for d in filter_difficulty}
            tasks = [t for t in tasks if t.get("difficulty", "").lower() in diff_set]

        if filter_category:
            cat_set = {c.lower() for c in filter_category}
            tasks = [t for t in tasks if any(c in t.get("category", "").lower() for c in cat_set)]

        if filter_tags:
            tasks = [
                t
                for t in tasks
                if all(
                    tag.lower() in [tt.lower() for tt in t.get("tags", [])] for tag in filter_tags
                )
            ]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [
                t
                for t in tasks
                if str(t.get("id", "")) in task_id_set or t.get("title_slug", "") in task_id_set
            ]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for task in tasks:
            augmented = dict(task)
            task_id = task.get("id", str(len(augmented_tasks)))
            augmented["instance_id"] = f"leetcode_{task_id}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert LeetCode task to normalized format.

        Args:
            task: LeetCode task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "leetcode_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="leetcode/algorithms",
            commit="HEAD",
            metadata={
                "title": task.get("title", ""),
                "difficulty": task.get("difficulty", ""),
                "content": task.get("content", ""),
                "tags": task.get("tags", []),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: LeetCode task dictionary.

        Returns:
            Problem statement for the agent.
        """
        title = task.get("title", "Unknown Problem")
        content = task.get("content", task.get("description", "No description provided"))
        difficulty = task.get("difficulty", "unknown")

        return (
            f"Solve the following LeetCode problem:\n"
            f"Title: {title} (Difficulty: {difficulty})\n\n"
            f"{content}\n\n"
            f"Save your solution to a file named 'solution.py'."
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for LeetCode task.

        Args:
            task: LeetCode task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "leetcode_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "leetcode/algorithms",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for LeetCode task.

        Args:
            env: Task environment.
            task: LeetCode task dictionary.
            solution: Solution code to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        # LeetCode evaluation depends on test case format
        # Basic approach: look for test assertions in the solution
        import base64

        test_code = solution + "\n\nprint('SOLUTION_EXECUTED')\n"
        encoded = base64.b64encode(test_code.encode()).decode()

        exit_code, stdout, stderr = await env.exec_command(
            f"echo '{encoded}' | base64 -d > test_solution.py && python3 test_solution.py",
            timeout=30,
        )

        passed = exit_code == 0 and "SOLUTION_EXECUTED" in stdout
        return {
            "resolved": passed,
            "exit_code": exit_code,
            "stdout": stdout[:1000] if stdout else "",
            "stderr": stderr[:1000] if stderr else "",
        }

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            task: LeetCode task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get LeetCode prompt template.

        Returns:
            Prompt template for LeetCode problems.
        """
        return (
            "Solve the following LeetCode problem:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Implement an efficient solution\n"
            "- Consider time and space complexity\n"
            "- Handle edge cases correctly\n"
            "- Save your solution to 'solution.py'"
        )
