"""Custom metrics framework for flexible evaluation beyond standard accuracy/pass rates.

This module provides:
- MetricDefinition dataclass for declaring metrics with name, description, compute
  function, aggregation strategy, and direction (higher_is_better).
- MetricRegistry for registering, looking up, and managing metrics.
- Built-in metrics: accuracy, pass_rate, avg_tokens, avg_cost, avg_time,
  tool_call_rate, failure_rate.
- Support for composite metrics (e.g., cost_efficiency = pass_rate / avg_cost).
- compute_metrics() to evaluate a set of metrics against result data.
- validate_metric() to check metric definition validity.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class MetricDefinition:
    """Definition of a single evaluation metric.

    Attributes:
        name: Unique identifier for the metric.
        description: Human-readable description of what the metric measures.
        compute_fn: Either a callable ``(list[dict]) -> float`` that computes the
            metric from a list of result dicts, or a string expression referencing
            other metric names (for composite metrics).
        aggregation: Aggregation strategy used when summarising per-task values.
            One of ``"mean"``, ``"sum"``, ``"min"``, ``"max"``, ``"median"``.
        higher_is_better: Whether a higher value is considered better.
    """

    name: str
    description: str
    compute_fn: Callable[[list[dict[str, Any]]], float] | str
    aggregation: str = "mean"
    higher_is_better: bool = True


_VALID_AGGREGATIONS = frozenset({"mean", "sum", "min", "max", "median"})


class MetricRegistry:
    """Registry for looking up and managing metric definitions.

    Provides ``register``, ``get``, ``list_metrics``, and ``unregister`` operations.
    """

    def __init__(self) -> None:
        self._metrics: dict[str, MetricDefinition] = {}

    # -- public API ----------------------------------------------------------

    def register(self, metric: MetricDefinition) -> None:
        """Register a metric definition.

        Args:
            metric: The metric to register.

        Raises:
            ValueError: If a metric with the same name is already registered.
        """
        if metric.name in self._metrics:
            raise ValueError(f"Metric '{metric.name}' is already registered")
        self._metrics[metric.name] = metric

    def get(self, name: str) -> MetricDefinition | None:
        """Look up a metric by name.

        Args:
            name: Metric name.

        Returns:
            The MetricDefinition if found, otherwise ``None``.
        """
        return self._metrics.get(name)

    def list_metrics(self) -> list[str]:
        """Return a sorted list of all registered metric names."""
        return sorted(self._metrics.keys())

    def unregister(self, name: str) -> bool:
        """Remove a metric from the registry.

        Args:
            name: Metric name to remove.

        Returns:
            ``True`` if the metric was removed, ``False`` if it was not found.
        """
        if name in self._metrics:
            del self._metrics[name]
            return True
        return False

    def __contains__(self, name: str) -> bool:
        return name in self._metrics

    def __len__(self) -> int:
        return len(self._metrics)


# ---------------------------------------------------------------------------
# Built-in metric compute functions
# ---------------------------------------------------------------------------


def _compute_accuracy(results: list[dict[str, Any]]) -> float:
    """Fraction of results where ``resolved`` is truthy."""
    if not results:
        return 0.0
    resolved = sum(1 for r in results if r.get("resolved"))
    return resolved / len(results)


def _compute_pass_rate(results: list[dict[str, Any]]) -> float:
    """Fraction of results where ``resolved`` is truthy (alias of accuracy)."""
    return _compute_accuracy(results)


def _compute_avg_tokens(results: list[dict[str, Any]]) -> float:
    """Average total token count per result."""
    token_counts: list[int] = []
    for r in results:
        tokens = r.get("tokens", {})
        total = tokens.get("input", 0) + tokens.get("output", 0)
        token_counts.append(total)
    if not token_counts:
        return 0.0
    return float(statistics.mean(token_counts))


def _compute_avg_cost(results: list[dict[str, Any]]) -> float:
    """Average cost per result."""
    costs: list[float] = [r.get("cost", 0.0) for r in results]
    if not costs:
        return 0.0
    return statistics.mean(costs)


def _compute_avg_time(results: list[dict[str, Any]]) -> float:
    """Average runtime in seconds per result."""
    runtimes: list[float] = [r.get("runtime_seconds", 0.0) for r in results]
    if not runtimes:
        return 0.0
    return statistics.mean(runtimes)


def _compute_tool_call_rate(results: list[dict[str, Any]]) -> float:
    """Fraction of results that contain at least one tool call."""
    if not results:
        return 0.0
    with_tools = sum(1 for r in results if r.get("tool_usage"))
    return with_tools / len(results)


def _compute_failure_rate(results: list[dict[str, Any]]) -> float:
    """Fraction of results where ``error`` is present and non-empty."""
    if not results:
        return 0.0
    with_errors = sum(1 for r in results if r.get("error"))
    return with_errors / len(results)


# ---------------------------------------------------------------------------
# Built-in metric definitions
# ---------------------------------------------------------------------------

BUILTIN_METRICS: list[MetricDefinition] = [
    MetricDefinition(
        name="accuracy",
        description="Fraction of tasks resolved successfully",
        compute_fn=_compute_accuracy,
        aggregation="mean",
        higher_is_better=True,
    ),
    MetricDefinition(
        name="pass_rate",
        description="Fraction of tasks that pass (alias for accuracy)",
        compute_fn=_compute_pass_rate,
        aggregation="mean",
        higher_is_better=True,
    ),
    MetricDefinition(
        name="avg_tokens",
        description="Average total tokens (input + output) per task",
        compute_fn=_compute_avg_tokens,
        aggregation="mean",
        higher_is_better=False,
    ),
    MetricDefinition(
        name="avg_cost",
        description="Average API cost per task in USD",
        compute_fn=_compute_avg_cost,
        aggregation="mean",
        higher_is_better=False,
    ),
    MetricDefinition(
        name="avg_time",
        description="Average runtime per task in seconds",
        compute_fn=_compute_avg_time,
        aggregation="mean",
        higher_is_better=False,
    ),
    MetricDefinition(
        name="tool_call_rate",
        description="Fraction of tasks that used at least one tool",
        compute_fn=_compute_tool_call_rate,
        aggregation="mean",
        higher_is_better=True,
    ),
    MetricDefinition(
        name="failure_rate",
        description="Fraction of tasks that encountered an error",
        compute_fn=_compute_failure_rate,
        aggregation="mean",
        higher_is_better=False,
    ),
]


def create_default_registry() -> MetricRegistry:
    """Create a MetricRegistry pre-populated with all built-in metrics.

    Returns:
        A MetricRegistry instance containing the built-in metrics.
    """
    registry = MetricRegistry()
    for metric in BUILTIN_METRICS:
        registry.register(metric)
    return registry


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate(values: list[float], method: str) -> float:
    """Aggregate a list of floats using the specified method.

    Args:
        values: Numeric values to aggregate.
        method: One of ``"mean"``, ``"sum"``, ``"min"``, ``"max"``, ``"median"``.

    Returns:
        Aggregated value.

    Raises:
        ValueError: If the method is unrecognised.
    """
    if not values:
        return 0.0
    if method == "mean":
        return statistics.mean(values)
    elif method == "sum":
        return math.fsum(values)
    elif method == "min":
        return min(values)
    elif method == "max":
        return max(values)
    elif method == "median":
        return statistics.median(values)
    else:
        raise ValueError(f"Unknown aggregation method: {method!r}")


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------


def compute_metrics(
    results: list[dict[str, Any]],
    metrics: list[str],
    registry: MetricRegistry | None = None,
) -> dict[str, float]:
    """Compute the requested metrics over a list of result dicts.

    Each result dict is expected to follow the structure used elsewhere in mcpbr
    (keys such as ``resolved``, ``tokens``, ``cost``, ``runtime_seconds``,
    ``tool_usage``, ``error``).

    Composite metrics (whose ``compute_fn`` is a string expression) are resolved
    by first computing all non-composite metrics they reference, then evaluating the
    expression in a restricted namespace.

    Args:
        results: List of per-task result dictionaries.
        metrics: List of metric names to compute.
        registry: Optional MetricRegistry. If ``None``, the default registry
            (containing built-in metrics) is used.

    Returns:
        Dictionary mapping metric names to their computed float values.

    Raises:
        KeyError: If a requested metric is not found in the registry.
        ValueError: If a composite expression references an unknown metric or
            fails to evaluate.
    """
    if registry is None:
        registry = create_default_registry()

    computed: dict[str, float] = {}

    # Separate callable and composite (expression-based) metrics
    callable_names: list[str] = []
    composite_names: list[str] = []

    for name in metrics:
        metric_def = registry.get(name)
        if metric_def is None:
            raise KeyError(f"Metric '{name}' is not registered")
        if callable(metric_def.compute_fn):
            callable_names.append(name)
        else:
            composite_names.append(name)

    # Phase 1: compute all callable metrics
    for name in callable_names:
        metric_def = registry.get(name)
        assert metric_def is not None
        assert callable(metric_def.compute_fn)
        computed[name] = metric_def.compute_fn(results)

    # Phase 2: resolve composite metrics
    for name in composite_names:
        metric_def = registry.get(name)
        assert metric_def is not None
        assert isinstance(metric_def.compute_fn, str)

        # Build a namespace of already-computed values.  If the expression
        # references a metric that hasn't been computed yet, compute it now.
        ns: dict[str, float] = {}
        for existing_name, existing_val in computed.items():
            ns[existing_name] = existing_val

        # Evaluate the expression.  We deliberately restrict the namespace to
        # only contain computed metric values (no builtins).
        try:
            value = float(eval(metric_def.compute_fn, {"__builtins__": {}}, ns))  # noqa: S307
        except ZeroDivisionError:
            value = 0.0
        except Exception as exc:
            raise ValueError(
                f"Failed to evaluate composite metric '{name}' "
                f"expression '{metric_def.compute_fn}': {exc}"
            ) from exc

        computed[name] = value

    return computed


def validate_metric(metric_def: dict[str, Any]) -> bool:
    """Validate a metric definition dictionary.

    Checks that the definition contains all required fields with correct types
    and valid values.

    Required keys:
        - ``name`` (str, non-empty)
        - ``description`` (str)
        - ``compute_fn`` (callable or str)

    Optional keys (with defaults):
        - ``aggregation`` (str, one of mean/sum/min/max/median)
        - ``higher_is_better`` (bool)

    Args:
        metric_def: Dictionary representing a metric definition.

    Returns:
        ``True`` if the definition is valid, ``False`` otherwise.
    """
    # Required fields
    if not isinstance(metric_def.get("name"), str) or not metric_def["name"].strip():
        return False

    if not isinstance(metric_def.get("description"), str):
        return False

    compute_fn = metric_def.get("compute_fn")
    if compute_fn is None:
        return False
    if not callable(compute_fn) and not isinstance(compute_fn, str):
        return False
    if isinstance(compute_fn, str) and not compute_fn.strip():
        return False

    # Optional fields
    aggregation = metric_def.get("aggregation", "mean")
    if aggregation not in _VALID_AGGREGATIONS:
        return False

    higher_is_better = metric_def.get("higher_is_better", True)
    return isinstance(higher_is_better, bool)
