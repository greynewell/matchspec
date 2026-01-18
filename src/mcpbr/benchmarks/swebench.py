"""SWE-bench benchmark implementation."""

from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment, get_swebench_image_name
from ..evaluation import EvaluationResult, evaluate_patch
from .base import BenchmarkTask


class SWEBenchmark:
    """SWE-bench benchmark implementation.

    Tasks involve generating patches to fix bugs in GitHub repositories.
    Evaluation runs pytest tests to verify the fix works.
    """

    name = "swe-bench"

    def __init__(self, dataset: str = "SWE-bench/SWE-bench_Lite"):
        """Initialize SWE-bench benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
        """
        self.dataset = dataset

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from SWE-bench dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for SWE-bench (no difficulty levels).

        Returns:
            List of SWE-bench task dictionaries.
        """
        dataset = load_dataset(self.dataset, split="test")

        if task_ids:
            # Use set for O(1) lookup performance
            task_id_set = set(task_ids)
            tasks = []
            for item in dataset:
                if item["instance_id"] in task_id_set:
                    tasks.append(item)
        else:
            tasks = list(dataset)

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        return tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert SWE-bench task to normalized format.

        Args:
            task: SWE-bench task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        return BenchmarkTask(
            task_id=task["instance_id"],
            problem_statement=task["problem_statement"],
            repo=task["repo"],
            commit=task["base_commit"],
            metadata={
                "fail_to_pass": task.get("FAIL_TO_PASS", "[]"),
                "pass_to_pass": task.get("PASS_TO_PASS", "[]"),
                "test_patch": task.get("test_patch", ""),
            },
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for SWE-bench task.

        Delegates to DockerEnvironmentManager which handles pre-built images
        and fallback to building from scratch.

        Args:
            task: SWE-bench task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        return await docker_manager.create_environment(task)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a patch for SWE-bench task.

        Applies the patch and runs pytest tests to verify the fix.

        Args:
            env: Task environment.
            task: SWE-bench task dictionary.
            solution: Unified diff patch to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        # Evaluate using the existing evaluation logic
        eval_result: EvaluationResult = await evaluate_patch(env, task, solution)

        # Convert to dictionary format expected by harness
        result: dict[str, Any] = {
            "resolved": eval_result.resolved,
            "patch_applied": eval_result.patch_applied,
        }

        if eval_result.fail_to_pass:
            result["fail_to_pass"] = {
                "passed": eval_result.fail_to_pass.passed,
                "total": eval_result.fail_to_pass.total,
            }

        if eval_result.pass_to_pass:
            result["pass_to_pass"] = {
                "passed": eval_result.pass_to_pass.passed,
                "total": eval_result.pass_to_pass.total,
            }

        if eval_result.error:
            result["eval_error"] = eval_result.error

        return result

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built SWE-bench image name for the task.

        Args:
            task: SWE-bench task dictionary.

        Returns:
            Pre-built image name (always returns a name; may not exist in registry).
        """
        instance_id = task["instance_id"]
        return get_swebench_image_name(instance_id)

    def get_prompt_template(self) -> str:
        """Get SWE-bench prompt template.

        Returns:
            Prompt template for fixing bugs.
        """
        return (
            "Fix the following bug in this repository:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT CONSTRAINTS:\n"
            "- Only modify the minimum files necessary to fix the bug\n"
            "- Do NOT create new test files\n"
            "- Do NOT create documentation files\n"
            "- Do NOT create reproduction scripts\n"
            "- Focus solely on the fix in existing source files"
        )
