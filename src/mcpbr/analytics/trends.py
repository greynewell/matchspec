"""Time-series trend analysis for mcpbr evaluation results.

Provides utilities for detecting performance trends (improving, declining,
stable) across historical evaluation runs using only the Python standard
library.
"""

from __future__ import annotations

import math
from typing import Any


def calculate_trends(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate trend information from a list of run summaries.

    Expects each run dict to contain at least ``timestamp``,
    ``resolution_rate``, ``total_cost``, and ``total_tokens`` keys
    (matching the output of :meth:`ResultsDatabase.get_trends`).

    Args:
        runs: List of run summary dicts ordered by timestamp ascending.

    Returns:
        A dictionary with the following keys:

        - ``resolution_rate_trend``: list of ``{timestamp, rate}`` pairs
        - ``cost_trend``: list of ``{timestamp, cost}`` pairs
        - ``token_trend``: list of ``{timestamp, tokens}`` pairs
        - ``direction``: overall direction based on resolution rate
          (``"improving"``, ``"declining"``, or ``"stable"``)
        - ``moving_averages``: dict with ``resolution_rate``, ``cost``,
          and ``tokens`` moving averages (window=3)
    """
    resolution_rate_trend: list[dict[str, Any]] = []
    cost_trend: list[dict[str, Any]] = []
    token_trend: list[dict[str, Any]] = []

    rates: list[float] = []
    costs: list[float] = []
    tokens: list[float] = []

    for run in runs:
        ts = run.get("timestamp", "")

        rate = run.get("resolution_rate")
        rate = float(rate) if rate is not None else 0.0
        resolution_rate_trend.append({"timestamp": ts, "rate": rate})
        rates.append(rate)

        cost = run.get("total_cost")
        cost = float(cost) if cost is not None else 0.0
        cost_trend.append({"timestamp": ts, "cost": cost})
        costs.append(cost)

        tok = run.get("total_tokens")
        tok = int(tok) if tok is not None else 0
        token_trend.append({"timestamp": ts, "tokens": tok})
        tokens.append(float(tok))

    direction = detect_trend_direction(rates)

    moving_averages = {
        "resolution_rate": calculate_moving_average(rates, window=3),
        "cost": calculate_moving_average(costs, window=3),
        "tokens": calculate_moving_average(tokens, window=3),
    }

    return {
        "resolution_rate_trend": resolution_rate_trend,
        "cost_trend": cost_trend,
        "token_trend": token_trend,
        "direction": direction,
        "moving_averages": moving_averages,
    }


def detect_trend_direction(values: list[float], threshold: float = 0.01) -> str:
    """Determine whether a series of values is improving, declining, or stable.

    Uses ordinary-least-squares linear regression on the index positions
    to compute a slope. A positive slope above *threshold* is considered
    ``"improving"``; a negative slope below ``-threshold`` is
    ``"declining"``; otherwise the trend is ``"stable"``.

    Args:
        values: Ordered list of numeric values (e.g., resolution rates
            from oldest to newest).
        threshold: Minimum absolute slope to classify as non-stable.
            Defaults to ``0.01``.

    Returns:
        One of ``"improving"``, ``"declining"``, or ``"stable"``.
    """
    n = len(values)
    if n < 2:
        return "stable"

    # Simple linear regression: y = a + b*x, solve for b (slope)
    # using index positions 0..n-1 as x values.
    mean_x = (n - 1) / 2.0
    mean_y = math.fsum(values) / n

    numerator = 0.0
    denominator = 0.0
    for i, y in enumerate(values):
        dx = i - mean_x
        numerator += dx * (y - mean_y)
        denominator += dx * dx

    if denominator == 0.0:
        return "stable"

    slope = numerator / denominator

    if slope > threshold:
        return "improving"
    elif slope < -threshold:
        return "declining"
    else:
        return "stable"


def calculate_moving_average(values: list[float], window: int = 3) -> list[float | None]:
    """Compute a simple moving average over a list of values.

    For positions where fewer than *window* preceding values exist the
    result is ``None``.

    Args:
        values: Ordered list of numeric values.
        window: Number of consecutive values to average. Must be at
            least 1.

    Returns:
        A list the same length as *values*. The first ``window - 1``
        entries are ``None``; subsequent entries are the mean of the
        preceding *window* values (inclusive of the current position).

    Raises:
        ValueError: If *window* is less than 1.
    """
    if window < 1:
        raise ValueError("window must be at least 1")

    n = len(values)
    result: list[float | None] = []

    for i in range(n):
        if i < window - 1:
            result.append(None)
        else:
            window_values = values[i - window + 1 : i + 1]
            result.append(math.fsum(window_values) / window)

    return result
