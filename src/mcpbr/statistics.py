"""Comprehensive statistics collection and aggregation for evaluation results.

This module provides detailed statistics beyond basic success rates, including:
- Token usage (per task, total, average)
- Cost breakdown (per task, total, average)
- Tool use statistics (total calls, per-tool breakdown, success/error rates)
- Timing information (wall time, per-task breakdown)
- Error analysis (categorization, common failures)
- Iteration statistics (average, max, distribution)
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .harness import EvaluationResults, TaskResult


@dataclass
class TokenStatistics:
    """Token usage statistics."""

    total_input: int = 0
    total_output: int = 0
    total_tokens: int = 0
    avg_input_per_task: float = 0.0
    avg_output_per_task: float = 0.0
    avg_tokens_per_task: float = 0.0
    max_input_per_task: int = 0
    max_output_per_task: int = 0
    min_input_per_task: int = 0
    min_output_per_task: int = 0
    per_task: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_input": self.total_input,
            "total_output": self.total_output,
            "total_tokens": self.total_tokens,
            "avg_input_per_task": round(self.avg_input_per_task, 2),
            "avg_output_per_task": round(self.avg_output_per_task, 2),
            "avg_tokens_per_task": round(self.avg_tokens_per_task, 2),
            "max_input_per_task": self.max_input_per_task,
            "max_output_per_task": self.max_output_per_task,
            "min_input_per_task": self.min_input_per_task,
            "min_output_per_task": self.min_output_per_task,
            "per_task": self.per_task,
        }


@dataclass
class CostStatistics:
    """Cost breakdown statistics."""

    total_cost: float = 0.0
    avg_cost_per_task: float = 0.0
    max_cost_per_task: float = 0.0
    min_cost_per_task: float = 0.0
    cost_per_resolved: float | None = None
    per_task: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_cost": round(self.total_cost, 4),
            "avg_cost_per_task": round(self.avg_cost_per_task, 4),
            "max_cost_per_task": round(self.max_cost_per_task, 4),
            "min_cost_per_task": round(self.min_cost_per_task, 4),
            "cost_per_resolved": round(self.cost_per_resolved, 4)
            if self.cost_per_resolved is not None
            else None,
            "per_task": {k: round(v, 4) for k, v in self.per_task.items()},
        }


@dataclass
class ToolStatistics:
    """Tool usage statistics."""

    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    failure_rate: float = 0.0
    unique_tools_used: int = 0
    avg_calls_per_task: float = 0.0
    per_tool: dict[str, dict[str, Any]] = field(default_factory=dict)
    most_used_tools: list[tuple[str, int]] = field(default_factory=list)
    most_failed_tools: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "failure_rate": round(self.failure_rate, 4),
            "unique_tools_used": self.unique_tools_used,
            "avg_calls_per_task": round(self.avg_calls_per_task, 2),
            "per_tool": self.per_tool,
            "most_used_tools": dict(self.most_used_tools[:10]),
            "most_failed_tools": dict(self.most_failed_tools[:10]),
        }


@dataclass
class ErrorStatistics:
    """Error analysis statistics."""

    total_errors: int = 0
    error_rate: float = 0.0
    timeout_count: int = 0
    timeout_rate: float = 0.0
    error_categories: dict[str, int] = field(default_factory=dict)
    most_common_errors: list[tuple[str, int]] = field(default_factory=list)
    sample_errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_errors": self.total_errors,
            "error_rate": round(self.error_rate, 4),
            "timeout_count": self.timeout_count,
            "timeout_rate": round(self.timeout_rate, 4),
            "error_categories": self.error_categories,
            "most_common_errors": dict(self.most_common_errors[:10]),
            "sample_errors": self.sample_errors[:10],
        }


@dataclass
class IterationStatistics:
    """Iteration statistics."""

    total_iterations: int = 0
    avg_iterations: float = 0.0
    max_iterations: int = 0
    min_iterations: int = 0
    distribution: dict[int, int] = field(default_factory=dict)
    per_task: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_iterations": self.total_iterations,
            "avg_iterations": round(self.avg_iterations, 2),
            "max_iterations": self.max_iterations,
            "min_iterations": self.min_iterations,
            "distribution": self.distribution,
            "per_task": self.per_task,
        }


@dataclass
class ComprehensiveStatistics:
    """Complete statistics for an evaluation run."""

    mcp_tokens: TokenStatistics = field(default_factory=TokenStatistics)
    baseline_tokens: TokenStatistics = field(default_factory=TokenStatistics)
    mcp_costs: CostStatistics = field(default_factory=CostStatistics)
    baseline_costs: CostStatistics = field(default_factory=CostStatistics)
    mcp_tools: ToolStatistics = field(default_factory=ToolStatistics)
    mcp_errors: ErrorStatistics = field(default_factory=ErrorStatistics)
    baseline_errors: ErrorStatistics = field(default_factory=ErrorStatistics)
    mcp_iterations: IterationStatistics = field(default_factory=IterationStatistics)
    baseline_iterations: IterationStatistics = field(default_factory=IterationStatistics)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mcp_tokens": self.mcp_tokens.to_dict(),
            "baseline_tokens": self.baseline_tokens.to_dict(),
            "mcp_costs": self.mcp_costs.to_dict(),
            "baseline_costs": self.baseline_costs.to_dict(),
            "mcp_tools": self.mcp_tools.to_dict(),
            "mcp_errors": self.mcp_errors.to_dict(),
            "baseline_errors": self.baseline_errors.to_dict(),
            "mcp_iterations": self.mcp_iterations.to_dict(),
            "baseline_iterations": self.baseline_iterations.to_dict(),
        }


def _categorize_error(error_msg: str) -> str:
    """Categorize an error message into a general category.

    Args:
        error_msg: The error message to categorize.

    Returns:
        Category name.
    """
    error_lower = error_msg.lower()

    # Check MCP errors first (more specific)
    if "mcp" in error_lower:
        return "mcp_server"
    elif "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    elif "connection" in error_lower or "network" in error_lower:
        return "network"
    elif "permission" in error_lower or "access denied" in error_lower:
        return "permission"
    elif "not found" in error_lower or "no such" in error_lower:
        return "not_found"
    elif "syntax" in error_lower or "parse" in error_lower:
        return "syntax"
    elif "memory" in error_lower or "out of memory" in error_lower:
        return "memory"
    elif "docker" in error_lower or "container" in error_lower:
        return "docker"
    else:
        return "other"


def _calculate_token_stats(results: list[TaskResult], agent_type: str) -> TokenStatistics:
    """Calculate token usage statistics for an agent type.

    Args:
        results: List of task results.
        agent_type: "mcp" or "baseline".

    Returns:
        TokenStatistics object.
    """
    stats = TokenStatistics()
    input_tokens = []
    output_tokens = []

    for task in results:
        agent_data = task.mcp if agent_type == "mcp" else task.baseline
        if not agent_data:
            continue

        tokens = agent_data.get("tokens", {})
        input_tok = tokens.get("input", 0)
        output_tok = tokens.get("output", 0)

        input_tokens.append(input_tok)
        output_tokens.append(output_tok)

        stats.total_input += input_tok
        stats.total_output += output_tok
        stats.per_task[task.instance_id] = {
            "input": input_tok,
            "output": output_tok,
            "total": input_tok + output_tok,
        }

    stats.total_tokens = stats.total_input + stats.total_output

    if input_tokens:
        stats.avg_input_per_task = stats.total_input / len(input_tokens)
        stats.max_input_per_task = max(input_tokens)
        stats.min_input_per_task = min(input_tokens)

    if output_tokens:
        stats.avg_output_per_task = stats.total_output / len(output_tokens)
        stats.max_output_per_task = max(output_tokens)
        stats.min_output_per_task = min(output_tokens)

    if input_tokens or output_tokens:
        task_count = max(len(input_tokens), len(output_tokens))
        stats.avg_tokens_per_task = stats.total_tokens / task_count

    return stats


def _calculate_cost_stats(results: list[TaskResult], agent_type: str) -> CostStatistics:
    """Calculate cost statistics for an agent type.

    Args:
        results: List of task results.
        agent_type: "mcp" or "baseline".

    Returns:
        CostStatistics object.
    """
    stats = CostStatistics()
    costs = []
    resolved_count = 0

    for task in results:
        agent_data = task.mcp if agent_type == "mcp" else task.baseline
        if not agent_data:
            continue

        cost = agent_data.get("cost", 0.0)
        costs.append(cost)
        stats.total_cost += cost
        stats.per_task[task.instance_id] = cost

        if agent_data.get("resolved"):
            resolved_count += 1

    if costs:
        stats.avg_cost_per_task = stats.total_cost / len(costs)
        stats.max_cost_per_task = max(costs)
        stats.min_cost_per_task = min(costs)

    if resolved_count > 0:
        stats.cost_per_resolved = stats.total_cost / resolved_count

    return stats


def _calculate_tool_stats(results: list[TaskResult]) -> ToolStatistics:
    """Calculate tool usage statistics for MCP agent.

    Args:
        results: List of task results.

    Returns:
        ToolStatistics object.
    """
    stats = ToolStatistics()
    tool_usage_counter: Counter[str] = Counter()
    tool_failure_counter: Counter[str] = Counter()
    per_tool_stats: dict[str, dict[str, int]] = {}
    task_count = 0

    for task in results:
        if not task.mcp:
            continue

        task_count += 1

        # Aggregate tool usage (total calls)
        if "tool_usage" in task.mcp:
            for tool_name, count in task.mcp["tool_usage"].items():
                tool_usage_counter[tool_name] += count
                stats.total_calls += count

        # Aggregate tool failures
        if "tool_failures" in task.mcp:
            for tool_name, count in task.mcp["tool_failures"].items():
                tool_failure_counter[tool_name] += count
                stats.total_failures += count

    # Calculate per-tool statistics
    all_tools = set(tool_usage_counter.keys()) | set(tool_failure_counter.keys())
    for tool_name in all_tools:
        total_calls = tool_usage_counter.get(tool_name, 0)
        failures = tool_failure_counter.get(tool_name, 0)
        successes = max(total_calls - failures, 0)

        per_tool_stats[tool_name] = {
            "total": total_calls,
            "succeeded": successes,
            "failed": failures,
            "failure_rate": failures / total_calls if total_calls > 0 else 0.0,
        }

    stats.total_successes = stats.total_calls - stats.total_failures
    stats.failure_rate = stats.total_failures / stats.total_calls if stats.total_calls > 0 else 0.0
    stats.unique_tools_used = len(all_tools)
    stats.avg_calls_per_task = stats.total_calls / task_count if task_count > 0 else 0.0
    stats.per_tool = per_tool_stats
    stats.most_used_tools = tool_usage_counter.most_common(10)
    stats.most_failed_tools = tool_failure_counter.most_common(10)

    return stats


def _calculate_error_stats(results: list[TaskResult], agent_type: str) -> ErrorStatistics:
    """Calculate error statistics for an agent type.

    Args:
        results: List of task results.
        agent_type: "mcp" or "baseline".

    Returns:
        ErrorStatistics object.
    """
    stats = ErrorStatistics()
    error_counter: Counter[str] = Counter()
    error_category_counter: Counter[str] = Counter()
    task_count = 0

    for task in results:
        agent_data = task.mcp if agent_type == "mcp" else task.baseline
        if not agent_data:
            continue

        task_count += 1

        error = agent_data.get("error")
        if error:
            stats.total_errors += 1
            error_counter[error] += 1

            # Categorize error
            category = _categorize_error(error)
            error_category_counter[category] += 1

            if category == "timeout":
                stats.timeout_count += 1

            # Add to sample errors (first 10 unique)
            if len(stats.sample_errors) < 10:
                sample = {
                    "instance_id": task.instance_id,
                    "error": error,
                    "category": category,
                }
                if sample not in stats.sample_errors:
                    stats.sample_errors.append(sample)

    if task_count > 0:
        stats.error_rate = stats.total_errors / task_count
        stats.timeout_rate = stats.timeout_count / task_count

    stats.error_categories = dict(error_category_counter)
    stats.most_common_errors = error_counter.most_common(10)

    return stats


def _calculate_iteration_stats(results: list[TaskResult], agent_type: str) -> IterationStatistics:
    """Calculate iteration statistics for an agent type.

    Args:
        results: List of task results.
        agent_type: "mcp" or "baseline".

    Returns:
        IterationStatistics object.
    """
    stats = IterationStatistics()
    iterations_list = []
    distribution_counter: Counter[int] = Counter()

    for task in results:
        agent_data = task.mcp if agent_type == "mcp" else task.baseline
        if not agent_data:
            continue

        iterations = agent_data.get("iterations", 0)
        iterations_list.append(iterations)
        stats.total_iterations += iterations
        stats.per_task[task.instance_id] = iterations
        distribution_counter[iterations] += 1

    if iterations_list:
        stats.avg_iterations = stats.total_iterations / len(iterations_list)
        stats.max_iterations = max(iterations_list)
        stats.min_iterations = min(iterations_list)

    stats.distribution = dict(distribution_counter)

    return stats


def calculate_comprehensive_statistics(
    results: EvaluationResults,
) -> ComprehensiveStatistics:
    """Calculate comprehensive statistics from evaluation results.

    Args:
        results: Evaluation results containing task data.

    Returns:
        ComprehensiveStatistics object with all metrics.
    """
    stats = ComprehensiveStatistics()

    # Calculate token statistics
    stats.mcp_tokens = _calculate_token_stats(results.tasks, "mcp")
    stats.baseline_tokens = _calculate_token_stats(results.tasks, "baseline")

    # Calculate cost statistics
    stats.mcp_costs = _calculate_cost_stats(results.tasks, "mcp")
    stats.baseline_costs = _calculate_cost_stats(results.tasks, "baseline")

    # Calculate tool statistics (MCP only)
    stats.mcp_tools = _calculate_tool_stats(results.tasks)

    # Calculate error statistics
    stats.mcp_errors = _calculate_error_stats(results.tasks, "mcp")
    stats.baseline_errors = _calculate_error_stats(results.tasks, "baseline")

    # Calculate iteration statistics
    stats.mcp_iterations = _calculate_iteration_stats(results.tasks, "mcp")
    stats.baseline_iterations = _calculate_iteration_stats(results.tasks, "baseline")

    return stats
