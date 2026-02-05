"""Task prioritization and scheduling for benchmark evaluations.

Provides intelligent task ordering strategies to optimize benchmark runs
for speed, cost, coverage diversity, or custom scoring functions. Tasks
can be reordered before execution to get faster feedback, reduce costs,
or ensure diverse coverage across repositories and categories.

Addresses GitHub issue #92: Task Prioritization and Scheduling.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SchedulingStrategy(Enum):
    """Strategy for ordering benchmark tasks before execution.

    Attributes:
        DEFAULT: Preserve original task order (no reordering).
        SPEED_FIRST: Run fastest tasks first for quick feedback.
        COST_FIRST: Run cheapest tasks first to minimize early spend.
        COVERAGE_FIRST: Round-robin across categories/repos for diverse early results.
        CUSTOM: Use a user-provided scoring function.
    """

    DEFAULT = "default"
    SPEED_FIRST = "speed"
    COST_FIRST = "cost"
    COVERAGE_FIRST = "coverage"
    CUSTOM = "custom"


@dataclass
class TaskPriority:
    """Priority metadata for a single benchmark task.

    Attributes:
        task_id: Unique identifier for the task (e.g., instance_id).
        priority_score: Computed priority score (lower = higher priority / runs first).
        estimated_time_seconds: Rough estimate of task execution time in seconds.
        estimated_cost_usd: Rough estimate of task cost in USD.
        category: Category or grouping key (e.g., repo name, difficulty level).
        metadata: Additional metadata associated with the task.
    """

    task_id: str
    priority_score: float = 0.0
    estimated_time_seconds: float | None = None
    estimated_cost_usd: float | None = None
    category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Default token-per-character ratio for cost estimation.
# Based on empirical observation that ~4 characters is roughly 1 token for English text.
_DEFAULT_CHARS_PER_TOKEN = 4

# Default assumed output-to-input token ratio for agent tasks.
# Agents typically produce 3-5x more output than input for coding tasks.
_DEFAULT_OUTPUT_INPUT_RATIO = 4.0

# Baseline seconds per 1000 characters of problem statement.
# Longer problems tend to require more exploration and tool calls.
_DEFAULT_SECONDS_PER_KCHAR = 30.0

# Minimum estimated time for any task (seconds).
_MIN_ESTIMATED_TIME = 30.0

# Minimum estimated cost for any task (USD).
_MIN_ESTIMATED_COST = 0.001


class TaskScheduler:
    """Scheduler that reorders benchmark tasks based on a chosen strategy.

    The scheduler assigns priority scores to tasks and returns them in
    sorted order. It supports preset strategies (speed, cost, coverage)
    and custom scoring functions.

    Args:
        strategy: The scheduling strategy to use.
        custom_scorer: A callable that takes a task dict and returns a float
            priority score (lower = runs first). Required when strategy is CUSTOM.

    Raises:
        ValueError: If strategy is CUSTOM but no custom_scorer is provided.

    Example:
        >>> scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        >>> ordered = scheduler.schedule(tasks)
        >>> print(scheduler.preview(tasks))
    """

    def __init__(
        self,
        strategy: SchedulingStrategy = SchedulingStrategy.DEFAULT,
        custom_scorer: Callable[[dict[str, Any]], float] | None = None,
    ) -> None:
        if strategy == SchedulingStrategy.CUSTOM and custom_scorer is None:
            raise ValueError(
                "custom_scorer is required when strategy is CUSTOM. "
                "Provide a callable that takes a task dict and returns a float score."
            )
        self._strategy = strategy
        self._custom_scorer = custom_scorer

    @property
    def strategy(self) -> SchedulingStrategy:
        """The active scheduling strategy."""
        return self._strategy

    def schedule(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reorder tasks according to the active scheduling strategy.

        Args:
            tasks: List of task dictionaries to schedule. Each task should have
                at least an ``instance_id`` key. Additional keys like
                ``problem_statement``, ``repo``, and ``category`` improve
                estimation accuracy.

        Returns:
            A new list of task dictionaries in the scheduled order.
            The original list is not mutated.
        """
        if not tasks:
            return []

        if self._strategy == SchedulingStrategy.DEFAULT:
            return list(tasks)

        priorities = self._compute_priorities(tasks)

        # Sort by priority_score ascending (lower = runs first)
        priorities.sort(key=lambda p: p.priority_score)

        # Build task lookup by id for efficient reordering
        task_by_id: dict[str, dict[str, Any]] = {}
        for task in tasks:
            tid = task.get("instance_id", str(id(task)))
            task_by_id[tid] = task

        return [task_by_id[p.task_id] for p in priorities]

    def preview(self, tasks: list[dict[str, Any]]) -> str:
        """Generate a human-readable preview of the scheduled task order.

        Args:
            tasks: List of task dictionaries to preview.

        Returns:
            A formatted string showing the scheduled order with priority
            details, suitable for display before execution.
        """
        if not tasks:
            return "No tasks to schedule."

        scheduled = self.schedule(tasks)
        priorities = self._compute_priorities(tasks)
        priorities.sort(key=lambda p: p.priority_score)

        # Build a lookup for priority info
        priority_by_id: dict[str, TaskPriority] = {p.task_id: p for p in priorities}

        lines: list[str] = []
        lines.append(f"Schedule Preview (strategy: {self._strategy.value})")
        lines.append(f"Total tasks: {len(scheduled)}")
        lines.append("-" * 70)
        lines.append(f"{'#':<4} {'Task ID':<35} {'Score':<8} {'Est. Time':<12} {'Est. Cost':<10}")
        lines.append("-" * 70)

        for i, task in enumerate(scheduled, start=1):
            tid = task.get("instance_id", str(id(task)))
            priority = priority_by_id.get(tid)

            if priority is not None:
                score_str = f"{priority.priority_score:.2f}"
                time_str = (
                    f"{priority.estimated_time_seconds:.0f}s"
                    if priority.estimated_time_seconds is not None
                    else "N/A"
                )
                cost_str = (
                    f"${priority.estimated_cost_usd:.4f}"
                    if priority.estimated_cost_usd is not None
                    else "N/A"
                )
            else:
                score_str = "N/A"
                time_str = "N/A"
                cost_str = "N/A"

            lines.append(f"{i:<4} {tid:<35} {score_str:<8} {time_str:<12} {cost_str:<10}")

        lines.append("-" * 70)
        return "\n".join(lines)

    def estimate_task_cost(self, task: dict[str, Any], model: str = "sonnet") -> float:
        """Estimate the cost of running a single task in USD.

        The estimate is based on the length of the problem statement and
        the model's pricing. Longer problems produce more tokens and cost more.

        Args:
            task: Task dictionary, ideally containing a ``problem_statement`` key.
            model: Model identifier used for pricing lookup (default: ``"sonnet"``).

        Returns:
            Estimated cost in USD. Returns ``_MIN_ESTIMATED_COST`` if pricing
            data is unavailable or the problem statement is missing.
        """
        from .pricing import get_model_pricing

        problem = task.get("problem_statement", "")
        problem_len = len(problem) if isinstance(problem, str) else 0

        pricing = get_model_pricing(model)
        if pricing is None:
            return _MIN_ESTIMATED_COST

        # Estimate input tokens from problem length
        input_tokens = max(problem_len / _DEFAULT_CHARS_PER_TOKEN, 100)

        # Estimate output tokens as a multiple of input
        output_tokens = input_tokens * _DEFAULT_OUTPUT_INPUT_RATIO

        # Calculate cost in USD
        input_cost = (input_tokens / 1_000_000) * pricing.input_price_per_mtok
        output_cost = (output_tokens / 1_000_000) * pricing.output_price_per_mtok

        return max(input_cost + output_cost, _MIN_ESTIMATED_COST)

    def estimate_task_time(self, task: dict[str, Any]) -> float:
        """Estimate the execution time for a single task in seconds.

        The estimate is based on the length of the problem statement.
        Longer problems typically require more exploration time.

        Args:
            task: Task dictionary, ideally containing a ``problem_statement`` key.

        Returns:
            Estimated execution time in seconds (minimum ``_MIN_ESTIMATED_TIME``).
        """
        problem = task.get("problem_statement", "")
        problem_len = len(problem) if isinstance(problem, str) else 0

        # Scale linearly with problem length
        estimated = (problem_len / 1000) * _DEFAULT_SECONDS_PER_KCHAR

        return max(estimated, _MIN_ESTIMATED_TIME)

    def _compute_priorities(self, tasks: list[dict[str, Any]]) -> list[TaskPriority]:
        """Compute priority scores for all tasks based on the active strategy.

        Args:
            tasks: List of task dictionaries.

        Returns:
            List of TaskPriority objects with computed scores.
        """
        if self._strategy == SchedulingStrategy.SPEED_FIRST:
            return self._prioritize_by_speed(tasks)
        elif self._strategy == SchedulingStrategy.COST_FIRST:
            return self._prioritize_by_cost(tasks)
        elif self._strategy == SchedulingStrategy.COVERAGE_FIRST:
            return self._prioritize_by_coverage(tasks)
        elif self._strategy == SchedulingStrategy.CUSTOM:
            return self._prioritize_by_custom(tasks)
        else:
            # DEFAULT: preserve original order via index-based scoring
            return [
                TaskPriority(
                    task_id=task.get("instance_id", str(id(task))),
                    priority_score=float(i),
                )
                for i, task in enumerate(tasks)
            ]

    def _prioritize_by_speed(self, tasks: list[dict[str, Any]]) -> list[TaskPriority]:
        """Assign priority scores based on estimated execution time (ascending).

        Args:
            tasks: List of task dictionaries.

        Returns:
            List of TaskPriority objects scored by estimated time.
        """
        priorities: list[TaskPriority] = []
        for task in tasks:
            tid = task.get("instance_id", str(id(task)))
            est_time = self.estimate_task_time(task)
            est_cost = self.estimate_task_cost(task)
            category = _extract_category(task)

            priorities.append(
                TaskPriority(
                    task_id=tid,
                    priority_score=est_time,
                    estimated_time_seconds=est_time,
                    estimated_cost_usd=est_cost,
                    category=category,
                )
            )
        return priorities

    def _prioritize_by_cost(self, tasks: list[dict[str, Any]]) -> list[TaskPriority]:
        """Assign priority scores based on estimated cost (ascending).

        Args:
            tasks: List of task dictionaries.

        Returns:
            List of TaskPriority objects scored by estimated cost.
        """
        priorities: list[TaskPriority] = []
        for task in tasks:
            tid = task.get("instance_id", str(id(task)))
            est_time = self.estimate_task_time(task)
            est_cost = self.estimate_task_cost(task)
            category = _extract_category(task)

            priorities.append(
                TaskPriority(
                    task_id=tid,
                    priority_score=est_cost,
                    estimated_time_seconds=est_time,
                    estimated_cost_usd=est_cost,
                    category=category,
                )
            )
        return priorities

    def _prioritize_by_coverage(self, tasks: list[dict[str, Any]]) -> list[TaskPriority]:
        """Assign priority scores using round-robin across categories.

        Tasks are grouped by category (repo, difficulty, or explicit category),
        then interleaved so that early execution covers diverse categories.

        Args:
            tasks: List of task dictionaries.

        Returns:
            List of TaskPriority objects with interleaved category ordering.
        """
        # Group tasks by category
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            category = _extract_category(task) or "_uncategorized_"
            groups[category].append(task)

        # Sort group keys for deterministic ordering
        sorted_keys = sorted(groups.keys())

        # Round-robin interleave: take one task from each category in turn
        result: list[TaskPriority] = []
        score = 0.0
        max_group_len = max(len(g) for g in groups.values()) if groups else 0

        for round_idx in range(max_group_len):
            for key in sorted_keys:
                group = groups[key]
                if round_idx < len(group):
                    task = group[round_idx]
                    tid = task.get("instance_id", str(id(task)))
                    est_time = self.estimate_task_time(task)
                    est_cost = self.estimate_task_cost(task)

                    result.append(
                        TaskPriority(
                            task_id=tid,
                            priority_score=score,
                            estimated_time_seconds=est_time,
                            estimated_cost_usd=est_cost,
                            category=key,
                        )
                    )
                    score += 1.0

        return result

    def _prioritize_by_custom(self, tasks: list[dict[str, Any]]) -> list[TaskPriority]:
        """Assign priority scores using the user-provided custom scorer.

        Args:
            tasks: List of task dictionaries.

        Returns:
            List of TaskPriority objects scored by the custom function.

        Raises:
            RuntimeError: If custom_scorer is None (should not happen due to
                __init__ validation).
        """
        if self._custom_scorer is None:
            raise RuntimeError("custom_scorer is None but strategy is CUSTOM")

        priorities: list[TaskPriority] = []
        for task in tasks:
            tid = task.get("instance_id", str(id(task)))
            score = self._custom_scorer(task)
            est_time = self.estimate_task_time(task)
            est_cost = self.estimate_task_cost(task)
            category = _extract_category(task)

            priorities.append(
                TaskPriority(
                    task_id=tid,
                    priority_score=score,
                    estimated_time_seconds=est_time,
                    estimated_cost_usd=est_cost,
                    category=category,
                )
            )
        return priorities


def _extract_category(task: dict[str, Any]) -> str | None:
    """Extract a category label from a task dictionary.

    Checks common fields in order of preference: ``category``, ``repo``,
    ``difficulty``. Returns the first non-empty string found, or None.

    Args:
        task: Task dictionary.

    Returns:
        Category string, or None if no category field is found.
    """
    for key in ("category", "repo", "difficulty"):
        value = task.get(key)
        if value is not None:
            return str(value)
    return None


def create_scheduler(preset: str, **kwargs: Any) -> TaskScheduler:
    """Create a TaskScheduler from a preset name.

    Convenience factory function that maps human-readable preset names to
    scheduling strategies.

    Args:
        preset: One of ``"default"``, ``"speed"``, ``"cost"``, ``"coverage"``.
        **kwargs: Additional keyword arguments passed to TaskScheduler
            (e.g., ``custom_scorer``).

    Returns:
        Configured TaskScheduler instance.

    Raises:
        ValueError: If the preset name is not recognized.
    """
    preset_map: dict[str, SchedulingStrategy] = {
        "default": SchedulingStrategy.DEFAULT,
        "speed": SchedulingStrategy.SPEED_FIRST,
        "cost": SchedulingStrategy.COST_FIRST,
        "coverage": SchedulingStrategy.COVERAGE_FIRST,
    }

    strategy = preset_map.get(preset.lower())
    if strategy is None:
        valid_presets = ", ".join(sorted(preset_map.keys()))
        raise ValueError(f"Unknown scheduling preset: '{preset}'. Valid presets: {valid_presets}")

    return TaskScheduler(strategy=strategy, **kwargs)
