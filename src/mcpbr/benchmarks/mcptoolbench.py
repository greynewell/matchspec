"""MCPToolBench++ benchmark implementation."""

import json
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class MCPToolBenchmark:
    """MCPToolBench++ benchmark implementation.

    Tasks involve evaluating AI agents' ability to use MCP tools effectively.
    Tests four key capabilities:
    1. Tool Discovery - Understanding available MCP tools
    2. Tool Selection - Choosing appropriate tools for tasks
    3. Tool Invocation - Calling tools with correct parameters
    4. Result Interpretation - Understanding and using tool outputs

    Evaluation compares agent's tool use against labeled ground truth.
    """

    name = "mcptoolbench"

    def __init__(self, dataset: str = "MCPToolBench/MCPToolBenchPP"):
        """Initialize MCPToolBench++ benchmark.

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
        """Load tasks from MCPToolBench++ dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs (uuids) to load (None for all).
            level: Unused for MCPToolBench++ (no difficulty levels).
            filter_difficulty: Filter by difficulty (call_type: single, multi).
            filter_category: Filter by task categories (e.g., browser, finance, web).
            filter_tags: Filter by tags (not supported for MCPToolBench++ base dataset).

        Returns:
            List of MCPToolBench++ task dictionaries.
        """
        dataset = load_dataset(self.dataset, split="train")

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = bool(task_ids) or bool(filter_difficulty) or bool(filter_category)
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        if task_ids:
            # Use set for O(1) lookup performance
            task_id_set = set(task_ids)
            tasks = []
            for item in dataset:
                if item["uuid"] in task_id_set:
                    tasks.append(item)
        else:
            tasks = list(dataset)

        # Apply filters
        if filter_difficulty:
            # For MCPToolBench++, difficulty can map to call_type
            # "easy" or "single" -> single-step tasks
            # "hard", "multi", or "medium" -> multi-step tasks
            # Note: MCPToolBench++ only has two complexity levels (single/multi),
            # so "medium" maps to "multi" for backward compatibility
            call_types = set()
            for diff in filter_difficulty:
                diff_lower = diff.lower()
                if diff_lower in ("easy", "single"):
                    call_types.add("single")
                elif diff_lower in ("hard", "multi", "medium"):
                    call_types.add("multi")
                else:
                    # Try to use as-is if it's a valid call_type
                    call_types.add(diff)

            if call_types:
                filtered = []
                for task in tasks:
                    call_type = task.get("call_type", "")
                    if call_type in call_types:
                        filtered.append(task)
                tasks = filtered

        if filter_category:
            # Filter by category field
            filtered = []
            category_set = {cat.lower() for cat in filter_category}
            for task in tasks:
                task_category = task.get("category", "").lower()
                if task_category in category_set:
                    filtered.append(task)
            tasks = filtered

        # Note: filter_tags not applicable to base MCPToolBench++ dataset
        # Parameter required by Benchmark protocol
        _ = filter_tags  # Silence unused parameter warning

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        # Augment tasks with instance_id for compatibility with harness
        augmented_tasks = []
        for task in tasks:
            augmented = dict(task)
            # Use uuid as instance_id
            augmented["instance_id"] = task["uuid"]
            # Generate problem_statement from query
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert MCPToolBench++ task to normalized format.

        Args:
            task: MCPToolBench++ task dictionary.

        Returns:
            Normalized BenchmarkTask.

        Raises:
            ValueError: If uuid is missing from task.
        """
        task_id = task.get("uuid")
        if not task_id:
            # Fallback to instance_id if available
            task_id = task.get("instance_id")
            if not task_id:
                msg = f"Task missing required 'uuid' field: {task.keys()}"
                raise ValueError(msg)

        problem_statement = self._generate_problem_statement(task)

        # MCPToolBench++ doesn't have a specific repo - use category as context
        category = task.get("category", "unknown")
        repo = f"mcptoolbench/{category}"

        return BenchmarkTask(
            task_id=task_id,
            problem_statement=problem_statement,
            repo=repo,
            commit="HEAD",
            metadata={
                "category": category,
                "call_type": task.get("call_type", ""),
                "tools": task.get("tools", []),
                "mcp_tools_dict": task.get("mcp_tools_dict", {}),
                "function_call_label": task.get("function_call_label", []),
                "query": task.get("query", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: MCPToolBench++ task dictionary.

        Returns:
            Problem statement for the agent.
        """
        query = task.get("query", "No query provided")
        category = task.get("category", "unknown")
        call_type = task.get("call_type", "single")

        # Get available tools
        tools = task.get("tools", [])
        tools_str = ", ".join(tools) if tools else "no tools specified"

        statement = (
            f"Complete the following task using MCP tools:\n\n"
            f"Category: {category}\n"
            f"Task Type: {call_type}-step tool call\n"
            f"Available Tools: {tools_str}\n\n"
            f"Task:\n{query}\n\n"
            f"Use the available MCP tools to complete this task. "
            f"Ensure you select the appropriate tools and invoke them with correct parameters."
        )

        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for MCPToolBench++ task.

        For MCPToolBench++, we create a minimal environment since the focus
        is on tool use evaluation, not repository setup.

        Args:
            task: MCPToolBench++ task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        # Create minimal environment
        # MCPToolBench++ doesn't require specific repository setup
        category = task.get("category", "unknown")
        instance_id = task.get("instance_id", task.get("uuid", "unknown"))

        temp_task = {
            "instance_id": instance_id,
            "repo": f"mcptoolbench/{category}",
            "base_commit": "HEAD",
        }

        env = await docker_manager.create_environment(temp_task)

        # Install any necessary dependencies for the category
        await self._setup_environment(env, task)

        return env

    async def _setup_environment(self, env: TaskEnvironment, task: dict[str, Any]) -> None:
        """Setup environment based on task category.

        Args:
            env: Task environment.
            task: MCPToolBench++ task dictionary.
        """
        category = task.get("category", "")

        # Install common dependencies
        install_cmd = "apt-get update -qq && apt-get install -y -qq curl wget jq"
        _exit_code, _stdout, _stderr = await env.exec_command(
            install_cmd,
            timeout=300,
        )
        # Don't fail if installation has issues - proceed anyway

        # Category-specific setup
        if category in ("browser", "web"):
            # Install browser tools if needed
            browser_cmd = "apt-get install -y -qq chromium-browser 2>&1 || true"
            await env.exec_command(browser_cmd, timeout=300)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for MCPToolBench++ task.

        Compares agent's tool use against labeled ground truth.

        Evaluation criteria:
        1. Tool Selection - Did agent choose correct tools?
        2. Tool Invocation - Were tools called with correct parameters?
        3. Result Interpretation - Did agent use tool outputs correctly?

        Args:
            env: Task environment.
            task: MCPToolBench++ task dictionary.
            solution: Solution to evaluate (agent's tool call sequence).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        # Get ground truth function calls
        function_call_label = task.get("function_call_label", [])

        if not function_call_label:
            return {
                "resolved": False,
                "error": "No ground truth function calls provided for evaluation",
            }

        # Parse solution to extract function calls
        # Solution may contain agent's reasoning and tool calls
        agent_calls = self._extract_tool_calls(solution)

        # Evaluate tool selection and invocation
        evaluation_result = self._evaluate_tool_calls(agent_calls, function_call_label)

        return {
            "resolved": evaluation_result["correct"],
            "tool_selection_accuracy": evaluation_result["tool_selection_accuracy"],
            "parameter_accuracy": evaluation_result["parameter_accuracy"],
            "sequence_match": evaluation_result["sequence_match"],
            "details": evaluation_result.get("details", ""),
        }

    def _extract_tool_calls(self, solution: str) -> list[dict[str, Any]]:
        """Extract tool calls from agent's solution.

        Args:
            solution: Agent's solution text.

        Returns:
            List of tool call dictionaries.
        """
        tool_calls = []

        # Try to parse as JSON first (if agent returned structured output)
        try:
            parsed = json.loads(solution)
            if isinstance(parsed, list):
                tool_calls = parsed
            elif isinstance(parsed, dict) and "tool_calls" in parsed:
                tool_calls = parsed["tool_calls"]
        except json.JSONDecodeError:
            # If not JSON, look for tool call patterns in text
            # This is a simplified extraction - in practice would need more robust parsing
            pass

        return tool_calls

    def _evaluate_tool_calls(
        self,
        agent_calls: list[dict[str, Any]],
        ground_truth: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate agent's tool calls against ground truth.

        Args:
            agent_calls: List of tool calls made by agent.
            ground_truth: List of expected tool calls.

        Returns:
            Evaluation metrics dictionary.
        """
        if not ground_truth:
            return {
                "correct": False,
                "tool_selection_accuracy": 0.0,
                "parameter_accuracy": 0.0,
                "sequence_match": False,
                "details": "No ground truth available",
            }

        if not agent_calls:
            return {
                "correct": False,
                "tool_selection_accuracy": 0.0,
                "parameter_accuracy": 0.0,
                "sequence_match": False,
                "details": "Agent made no tool calls",
            }

        # Calculate tool selection accuracy
        # Count how many tools were correctly selected
        correct_tools = 0
        for gt_call in ground_truth:
            gt_tool = gt_call.get("name", "")
            for agent_call in agent_calls:
                if agent_call.get("name", "") == gt_tool:
                    correct_tools += 1
                    break

        tool_selection_accuracy = correct_tools / len(ground_truth) if ground_truth else 0.0

        # Calculate parameter accuracy (simplified)
        # In practice, would need more sophisticated parameter matching
        correct_params = 0
        total_params = 0

        for gt_call in ground_truth:
            gt_params = gt_call.get("parameters", {})
            total_params += len(gt_params)

            # Find matching agent call
            for agent_call in agent_calls:
                if agent_call.get("name", "") == gt_call.get("name", ""):
                    agent_params = agent_call.get("parameters", {})
                    for param_name, param_value in gt_params.items():
                        if agent_params.get(param_name) == param_value:
                            correct_params += 1
                    break

        parameter_accuracy = correct_params / total_params if total_params > 0 else 0.0

        # Check sequence match (exact order and tools)
        sequence_match = len(agent_calls) == len(ground_truth)
        if sequence_match:
            for _i, (agent_call, gt_call) in enumerate(
                zip(agent_calls, ground_truth, strict=False)
            ):
                if agent_call.get("name", "") != gt_call.get("name", ""):
                    sequence_match = False
                    break

        # Overall correctness: high tool selection and parameter accuracy
        correct = (
            tool_selection_accuracy >= 0.8
            and parameter_accuracy >= 0.7
            and len(agent_calls) <= len(ground_truth) * 1.5  # Allow some extra calls
        )

        details = (
            f"Tool selection: {tool_selection_accuracy:.1%}, "
            f"Parameter accuracy: {parameter_accuracy:.1%}, "
            f"Sequence match: {sequence_match}"
        )

        return {
            "correct": correct,
            "tool_selection_accuracy": tool_selection_accuracy,
            "parameter_accuracy": parameter_accuracy,
            "sequence_match": sequence_match,
            "details": details,
        }

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for MCPToolBench++ task.

        MCPToolBench++ doesn't use pre-built images - builds minimal environments.

        Args:
            task: MCPToolBench++ task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get MCPToolBench++ prompt template.

        Returns:
            Prompt template for MCP tool use tasks.
        """
        return (
            "Complete the following task using the available MCP tools:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Carefully review the available MCP tools and their capabilities\n"
            "- Select the appropriate tools for this task\n"
            "- Call tools with correct parameters as specified in their schemas\n"
            "- Use tool outputs to inform subsequent actions\n"
            "- If multiple tools are needed, call them in the correct sequence\n"
            "- Focus on completing the task efficiently and accurately"
        )

    def get_default_sandbox_level(self) -> str | None:
        return None
