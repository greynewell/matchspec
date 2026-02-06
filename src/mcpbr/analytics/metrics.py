"""Custom metrics definition and calculation for evaluation results.

Provides a ``MetricDefinition`` dataclass for declaring named metrics and a
``MetricsRegistry`` that ships with a set of built-in metrics (resolution rate,
cost per resolution, average tokens per task, tool failure rate, and an
efficiency score). Additional metrics can be registered at runtime.

All calculations use only the Python standard library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class MetricDefinition:
    """Definition of a single evaluation metric.

    Attributes:
        name: Unique identifier for the metric.
        description: Human-readable description of what the metric measures.
        unit: Unit of measurement (e.g., ``"ratio"``, ``"USD"``, ``"tokens"``).
        calculate: Callable that accepts a results_data dict and returns a
            float value for the metric.
        higher_is_better: Whether a higher value is considered better.
    """

    name: str
    description: str
    unit: str
    calculate: Callable[[dict[str, Any]], float]
    higher_is_better: bool = True


class MetricsRegistry:
    """Registry of metric definitions with built-in defaults.

    Built-in metrics registered on initialisation:
    - ``resolution_rate``: Fraction of tasks resolved.
    - ``cost_per_resolution``: Total cost divided by resolved count (inf if
      none resolved).
    - ``avg_tokens_per_task``: Mean total token count per task.
    - ``tool_failure_rate``: Ratio of tool failures to total tool calls.
    - ``efficiency_score``: Composite score: rate / (cost + 0.01).
    """

    def __init__(self) -> None:
        """Initialise the registry with built-in metrics."""
        self._metrics: dict[str, MetricDefinition] = {}
        self._register_builtins()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, metric: MetricDefinition) -> None:
        """Register a custom metric definition.

        Args:
            metric: The metric to register.

        Raises:
            ValueError: If a metric with the same name is already registered.
        """
        if metric.name in self._metrics:
            raise ValueError(f"Metric '{metric.name}' is already registered")
        self._metrics[metric.name] = metric

    def calculate_all(self, results_data: dict[str, Any]) -> dict[str, float]:
        """Calculate all registered metrics against the given results.

        Args:
            results_data: Evaluation results dictionary with ``metadata``,
                ``summary``, and ``tasks`` keys.

        Returns:
            Dictionary mapping metric name to its computed float value.
            If a metric calculation raises an exception the value is
            ``float('nan')``.
        """
        values: dict[str, float] = {}
        for name, metric in self._metrics.items():
            try:
                values[name] = metric.calculate(results_data)
            except Exception:
                values[name] = float("nan")
        return values

    def get_metric(self, name: str) -> MetricDefinition | None:
        """Look up a metric by name.

        Args:
            name: Metric identifier.

        Returns:
            The ``MetricDefinition`` if found, otherwise ``None``.
        """
        return self._metrics.get(name)

    def list_metrics(self) -> list[str]:
        """Return a sorted list of all registered metric names."""
        return sorted(self._metrics.keys())

    # ------------------------------------------------------------------
    # Built-in registration
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        """Register the default set of built-in metrics."""
        builtins = [
            MetricDefinition(
                name="resolution_rate",
                description="Fraction of tasks resolved successfully",
                unit="ratio",
                calculate=_calc_resolution_rate,
                higher_is_better=True,
            ),
            MetricDefinition(
                name="cost_per_resolution",
                description="Total cost divided by number of resolved tasks",
                unit="USD",
                calculate=_calc_cost_per_resolution,
                higher_is_better=False,
            ),
            MetricDefinition(
                name="avg_tokens_per_task",
                description="Average total tokens (input + output) per task",
                unit="tokens",
                calculate=_calc_avg_tokens_per_task,
                higher_is_better=False,
            ),
            MetricDefinition(
                name="tool_failure_rate",
                description="Ratio of tool failures to total tool calls",
                unit="ratio",
                calculate=_calc_tool_failure_rate,
                higher_is_better=False,
            ),
            MetricDefinition(
                name="efficiency_score",
                description="Composite efficiency: resolution_rate / (total_cost + 0.01)",
                unit="score",
                calculate=_calc_efficiency_score,
                higher_is_better=True,
            ),
        ]
        for metric in builtins:
            self._metrics[metric.name] = metric


# ---------------------------------------------------------------------------
# Built-in metric calculation functions
# ---------------------------------------------------------------------------


def _extract_tasks(results_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the list of task dicts from results_data.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        List of task dictionaries (possibly empty).
    """
    return results_data.get("tasks", [])


def _calc_resolution_rate(results_data: dict[str, Any]) -> float:
    """Compute resolved / total tasks.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        Resolution rate as a float between 0 and 1, or 0 if no tasks.
    """
    tasks = _extract_tasks(results_data)
    if not tasks:
        return 0.0
    resolved = sum(1 for t in tasks if t.get("mcp", {}).get("resolved"))
    return resolved / len(tasks)


def _calc_cost_per_resolution(results_data: dict[str, Any]) -> float:
    """Compute total_cost / resolved count.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        Cost per resolution in USD, or ``inf`` if no tasks were resolved.
    """
    tasks = _extract_tasks(results_data)
    if not tasks:
        return math.inf

    total_cost = math.fsum(t.get("mcp", {}).get("cost", 0.0) for t in tasks)
    resolved = sum(1 for t in tasks if t.get("mcp", {}).get("resolved"))
    if resolved == 0:
        return math.inf
    return total_cost / resolved


def _calc_avg_tokens_per_task(results_data: dict[str, Any]) -> float:
    """Compute average total tokens (input + output) per task.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        Average token count, or 0 if no tasks.
    """
    tasks = _extract_tasks(results_data)
    if not tasks:
        return 0.0

    total_tokens = 0
    for t in tasks:
        tokens = t.get("mcp", {}).get("tokens", {})
        total_tokens += int(tokens.get("input", 0)) + int(tokens.get("output", 0))
    return total_tokens / len(tasks)


def _calc_tool_failure_rate(results_data: dict[str, Any]) -> float:
    """Compute total tool failures / total tool calls.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        Tool failure rate (0-1), or 0 if no tool calls were made.
    """
    tasks = _extract_tasks(results_data)
    total_calls = 0
    total_failures = 0

    for t in tasks:
        mcp = t.get("mcp", {})

        # Sum tool_usage for total calls
        tool_usage = mcp.get("tool_usage", {})
        if tool_usage:
            total_calls += sum(tool_usage.values())
        else:
            total_calls += int(mcp.get("tool_calls", 0))

        # Sum tool_failures
        tool_failures = mcp.get("tool_failures", {})
        if tool_failures:
            total_failures += sum(tool_failures.values())

    if total_calls == 0:
        return 0.0
    return total_failures / total_calls


def _calc_efficiency_score(results_data: dict[str, Any]) -> float:
    """Compute composite efficiency: resolution_rate / (total_cost + 0.01).

    The small constant (0.01) prevents division by zero and rewards low-cost
    runs even when cost is near zero.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        Efficiency score (higher is better).
    """
    tasks = _extract_tasks(results_data)
    if not tasks:
        return 0.0

    resolved = sum(1 for t in tasks if t.get("mcp", {}).get("resolved"))
    rate = resolved / len(tasks)
    total_cost = math.fsum(t.get("mcp", {}).get("cost", 0.0) for t in tasks)
    return rate / (total_cost + 0.01)
