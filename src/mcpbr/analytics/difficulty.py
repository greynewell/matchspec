"""Benchmark difficulty estimation.

Provides functions to estimate per-task difficulty based on resolution rates,
token usage, iteration counts, and runtime. All calculations use only the
Python standard library.
"""

from __future__ import annotations

import math
from typing import Any

_DIFFICULTY_LEVELS: list[tuple[float, str]] = [
    (0.25, "easy"),
    (0.50, "medium"),
    (0.75, "hard"),
    (1.00, "very_hard"),
]


def estimate_difficulty(results_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Estimate the difficulty of each task in the evaluation results.

    Difficulty is scored on a 0-1 scale derived from:
    - Whether the task was resolved (unresolved tasks score higher).
    - Normalised distance of cost, token usage, iterations, and runtime from
      the per-run averages.

    Args:
        results_data: Evaluation results dictionary with ``tasks`` list. Each
            task is expected to have an ``mcp`` sub-dict containing
            ``resolved``, ``cost``, ``tokens`` (with ``input``/``output``),
            ``iterations``, and ``runtime_seconds``.

    Returns:
        List of per-task difficulty dictionaries, each containing:
        - instance_id: The task identifier.
        - difficulty_score: Float between 0 (easy) and 1 (hard).
        - difficulty_level: One of ``"easy"``, ``"medium"``, ``"hard"``,
          ``"very_hard"``.
        - metrics: Dictionary of the raw metric values used for scoring.
    """
    tasks = results_data.get("tasks", [])
    if not tasks:
        return []

    # Collect per-task raw metrics
    task_metrics: list[dict[str, Any]] = []
    for task in tasks:
        mcp = task.get("mcp", {})
        tokens = mcp.get("tokens", {})
        total_tokens = int(tokens.get("input", 0)) + int(tokens.get("output", 0))

        task_metrics.append(
            {
                "instance_id": task.get("instance_id", ""),
                "resolved": bool(mcp.get("resolved")),
                "cost": float(mcp.get("cost", 0.0)),
                "tokens": total_tokens,
                "iterations": int(mcp.get("iterations", 0)),
                "runtime": float(mcp.get("runtime_seconds", 0.0)),
            }
        )

    # Compute averages for normalisation
    n = len(task_metrics)
    avg_cost = math.fsum(t["cost"] for t in task_metrics) / n
    avg_tokens = math.fsum(t["tokens"] for t in task_metrics) / n
    avg_iterations = math.fsum(t["iterations"] for t in task_metrics) / n
    avg_runtime = math.fsum(t["runtime"] for t in task_metrics) / n

    # Score each task
    difficulties: list[dict[str, Any]] = []
    for t in task_metrics:
        score = estimate_task_difficulty_score(
            resolved=t["resolved"],
            cost=t["cost"],
            tokens=t["tokens"],
            iterations=t["iterations"],
            runtime=t["runtime"],
            avg_cost=avg_cost,
            avg_tokens=avg_tokens,
            avg_iterations=avg_iterations,
            avg_runtime=avg_runtime,
        )
        difficulties.append(
            {
                "instance_id": t["instance_id"],
                "difficulty_score": score,
                "difficulty_level": _score_to_level(score),
                "metrics": {
                    "resolved": t["resolved"],
                    "cost": t["cost"],
                    "tokens": t["tokens"],
                    "iterations": t["iterations"],
                    "runtime": t["runtime"],
                },
            }
        )

    return difficulties


def aggregate_difficulty_stats(
    task_difficulties: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate difficulty statistics across tasks.

    Args:
        task_difficulties: List of per-task difficulty dicts as returned by
            :func:`estimate_difficulty`.

    Returns:
        Dictionary containing:
        - distribution: Mapping of difficulty level to count.
        - avg_difficulty: Mean difficulty score across all tasks.
        - hardest_tasks: Up to 5 tasks with the highest difficulty scores.
        - easiest_tasks: Up to 5 tasks with the lowest difficulty scores.
    """
    if not task_difficulties:
        return {
            "distribution": {},
            "avg_difficulty": 0.0,
            "hardest_tasks": [],
            "easiest_tasks": [],
        }

    distribution: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0, "very_hard": 0}
    for t in task_difficulties:
        level = t.get("difficulty_level", "medium")
        distribution[level] = distribution.get(level, 0) + 1

    scores = [t["difficulty_score"] for t in task_difficulties]
    avg_difficulty = math.fsum(scores) / len(scores)

    sorted_by_score = sorted(task_difficulties, key=lambda t: t["difficulty_score"], reverse=True)
    hardest_tasks = sorted_by_score[:5]
    easiest_tasks = sorted_by_score[-5:][::-1]  # Reverse so easiest first

    return {
        "distribution": distribution,
        "avg_difficulty": avg_difficulty,
        "hardest_tasks": hardest_tasks,
        "easiest_tasks": easiest_tasks,
    }


def estimate_task_difficulty_score(
    resolved: bool,
    cost: float,
    tokens: int,
    iterations: int,
    runtime: float,
    avg_cost: float,
    avg_tokens: float,
    avg_iterations: float,
    avg_runtime: float,
) -> float:
    """Score a single task's difficulty on a 0-1 scale.

    Scoring logic:
    - Unresolved tasks receive a base penalty of 0.5.
    - Additional difficulty is derived from how far each metric deviates
      above the run average (normalised and clamped).
    - The four metric deviations (cost, tokens, iterations, runtime) are
      weighted equally and combined with the resolution penalty.

    Args:
        resolved: Whether the task was resolved.
        cost: Task cost in USD.
        tokens: Total token count (input + output).
        iterations: Number of agent iterations.
        runtime: Task runtime in seconds.
        avg_cost: Average cost across all tasks in the run.
        avg_tokens: Average total tokens across all tasks.
        avg_iterations: Average iterations across all tasks.
        avg_runtime: Average runtime across all tasks.

    Returns:
        Difficulty score between 0.0 (easy) and 1.0 (hard).
    """
    # Base score from resolution status
    base = 0.0 if resolved else 0.5

    # Normalised deviations: how much above average each metric is.
    # A value of 0 means at or below average; 1 means double the average.
    cost_dev = _normalised_deviation(cost, avg_cost)
    tokens_dev = _normalised_deviation(float(tokens), avg_tokens)
    iterations_dev = _normalised_deviation(float(iterations), avg_iterations)
    runtime_dev = _normalised_deviation(runtime, avg_runtime)

    # Combine deviations (equal weight, scaled to fill remaining 0.5 range)
    deviation_score = (cost_dev + tokens_dev + iterations_dev + runtime_dev) / 4.0
    # Scale deviation contribution: max 0.5 on top of base
    deviation_contribution = min(deviation_score, 1.0) * 0.5

    score = base + deviation_contribution
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalised_deviation(value: float, average: float) -> float:
    """Compute how far above the average a value is, normalised to [0, 1].

    Returns 0.0 when the value is at or below average, and approaches 1.0
    as the value reaches double the average. Values more than double the
    average are clamped to 1.0.

    Args:
        value: Observed metric value.
        average: Run-wide average for this metric.

    Returns:
        Normalised deviation clamped to [0, 1].
    """
    if average <= 0.0:
        return 0.0
    deviation = (value - average) / average
    return max(0.0, min(1.0, deviation))


def _score_to_level(score: float) -> str:
    """Convert a numeric difficulty score to a categorical level.

    Args:
        score: Difficulty score between 0 and 1.

    Returns:
        One of ``"easy"``, ``"medium"``, ``"hard"``, ``"very_hard"``.
    """
    for threshold, level in _DIFFICULTY_LEVELS:
        if score <= threshold:
            return level
    return "very_hard"
