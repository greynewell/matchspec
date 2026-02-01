"""ToolBench benchmark implementation."""

import json
import re
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class ToolBenchBenchmark:
    """ToolBench benchmark implementation.

    ToolBench evaluates tool-use capabilities of language models with a
    collection of real-world APIs. Tasks require models to select and
    invoke the correct API tools with proper parameters to fulfill
    user requests.

    Evaluation compares tool call sequences against ground truth.
    """

    name = "toolbench"

    def __init__(self, dataset: str = "tuandunghcmut/toolbench-v1") -> None:
        """Initialize ToolBench benchmark.

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
        """Load tasks from ToolBench dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for ToolBench.
            filter_difficulty: Filter by difficulty level.
            filter_category: Filter by API category.
            filter_tags: Filter by tool tags.

        Returns:
            List of ToolBench task dictionaries.
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
                if all(tag.lower() in str(t.get("tools", "")).lower() for tag in filter_tags)
            ]

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if str(t.get("id", "")) in task_id_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            augmented["instance_id"] = f"toolbench_{idx}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert ToolBench task to normalized format.

        Args:
            task: ToolBench task dictionary.

        Returns:
            Normalized BenchmarkTask.
        """
        instance_id = task.get("instance_id", "toolbench_unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=self._generate_problem_statement(task),
            repo="toolbench/apis",
            commit="HEAD",
            metadata={
                "query": task.get("query", ""),
                "tools": task.get("tools", []),
                "category": task.get("category", ""),
                "ground_truth": task.get("ground_truth", []),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: ToolBench task dictionary.

        Returns:
            Problem statement for the agent.
        """
        query = task.get("query", "No query provided")
        tools = task.get("tools", [])

        statement = f"Complete the following task using the available tools:\n\n{query}\n\n"
        if tools:
            statement += "Available tools:\n"
            for tool in tools[:10]:
                if isinstance(tool, dict):
                    name = tool.get("name", "unknown")
                    desc = tool.get("description", "")
                    statement += f"  - {name}: {desc}\n"
                else:
                    statement += f"  - {tool}\n"
        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for ToolBench task.

        Args:
            task: ToolBench task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "toolbench_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "toolbench/apis",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        _env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for ToolBench task.

        Compares tool call sequences against ground truth.

        Args:
            _env: Task environment (unused; evaluation is offline).
            task: ToolBench task dictionary.
            solution: Solution to evaluate (tool call sequence).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        ground_truth = task.get("ground_truth", [])
        if not ground_truth:
            return {"resolved": False, "error": "No ground truth available"}

        # Extract tool calls from solution
        agent_calls = self._extract_tool_calls(solution)

        if not agent_calls:
            return {
                "resolved": False,
                "error": "Could not extract tool calls from solution",
            }

        # Compare tool selections
        gt_tools = [call.get("name", "") for call in ground_truth if isinstance(call, dict)]
        agent_tools = [call.get("name", "") for call in agent_calls]

        tool_match = gt_tools == agent_tools
        tool_overlap = len(set(gt_tools) & set(agent_tools)) / max(len(set(gt_tools)), 1)

        return {
            "resolved": tool_match,
            "tool_selection_accuracy": tool_overlap,
            "expected_tools": gt_tools,
            "agent_tools": agent_tools,
        }

    def _extract_tool_calls(self, solution: str) -> list[dict[str, Any]]:
        """Extract tool calls from solution text.

        Args:
            solution: Solution text containing tool calls.

        Returns:
            List of tool call dictionaries.
        """
        # Try JSON parsing first
        try:
            calls = json.loads(solution)
            if isinstance(calls, list):
                return [c for c in calls if isinstance(c, dict)]
            if isinstance(calls, dict):
                return [calls]
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting from markdown code blocks
        json_blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", solution, re.DOTALL)
        for block in json_blocks:
            try:
                calls = json.loads(block)
                if isinstance(calls, list):
                    return calls
                if isinstance(calls, dict):
                    return [calls]
            except (json.JSONDecodeError, TypeError):
                continue

        return []

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name.

        Args:
            _task: ToolBench task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get ToolBench prompt template.

        Returns:
            Prompt template for tool-use tasks.
        """
        return (
            "Complete the following task using the available tools:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Select the appropriate tool(s) for the task\n"
            "- Provide correct parameters for each tool call\n"
            "- Output your tool calls as a JSON array\n"
            "- Each tool call should have 'name' and 'parameters' fields"
        )
