"""Correlation analysis for benchmark metrics.

Provides functions to compute Pearson and Spearman correlation coefficients
between evaluation metrics, identify pairwise correlations, and filter for
strong relationships. All calculations use only the Python standard library.
"""

from __future__ import annotations

import math
from typing import Any


def pearson_correlation(x: list[float], y: list[float]) -> dict[str, Any]:
    """Compute the Pearson correlation coefficient between two sequences.

    Uses the standard formula for Pearson's r:
        r = sum((xi - x_mean)(yi - y_mean)) /
            sqrt(sum((xi - x_mean)^2) * sum((yi - y_mean)^2))

    The p-value is approximated using the t-distribution relationship:
        t = r * sqrt((n - 2) / (1 - r^2))
    with a rough two-tailed approximation suitable for exploratory analysis.

    Args:
        x: First sequence of numeric values.
        y: Second sequence of numeric values, same length as x.

    Returns:
        Dictionary with keys:
        - r: Pearson correlation coefficient (-1 to 1).
        - r_squared: Coefficient of determination (0 to 1).
        - p_value: Approximate two-tailed p-value.
        - n: Number of paired observations.

    Raises:
        ValueError: If x and y have different lengths or fewer than 2 elements.
    """
    if len(x) != len(y):
        raise ValueError(
            f"Input sequences must have the same length: len(x)={len(x)}, len(y)={len(y)}"
        )
    n = len(x)
    if n < 2:
        raise ValueError(f"Need at least 2 data points, got {n}")

    x_mean = math.fsum(x) / n
    y_mean = math.fsum(y) / n

    numerator = math.fsum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y, strict=False))
    denom_x = math.fsum((xi - x_mean) ** 2 for xi in x)
    denom_y = math.fsum((yi - y_mean) ** 2 for yi in y)

    denominator = math.sqrt(denom_x * denom_y)

    if denominator == 0.0:
        # Constant input -- no meaningful correlation
        return {"r": 0.0, "r_squared": 0.0, "p_value": 1.0, "n": n}

    r = numerator / denominator
    # Clamp to [-1, 1] to guard against floating-point drift
    r = max(-1.0, min(1.0, r))
    r_squared = r * r
    p_value = _approximate_p_value(r, n)

    return {"r": r, "r_squared": r_squared, "p_value": p_value, "n": n}


def spearman_correlation(x: list[float], y: list[float]) -> dict[str, Any]:
    """Compute the Spearman rank correlation coefficient between two sequences.

    Converts both sequences to ranks (with average ranks for ties) and then
    computes the Pearson correlation on those ranks.

    Args:
        x: First sequence of numeric values.
        y: Second sequence of numeric values, same length as x.

    Returns:
        Dictionary with the same keys as :func:`pearson_correlation`.

    Raises:
        ValueError: If x and y have different lengths or fewer than 2 elements.
    """
    if len(x) != len(y):
        raise ValueError(
            f"Input sequences must have the same length: len(x)={len(x)}, len(y)={len(y)}"
        )
    if len(x) < 2:
        raise ValueError(f"Need at least 2 data points, got {len(x)}")

    x_ranks = _compute_ranks(x)
    y_ranks = _compute_ranks(y)
    return pearson_correlation(x_ranks, y_ranks)


def analyze_metric_correlations(
    results_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Compute all pairwise Pearson correlations between standard metrics.

    Extracts per-task values for cost, tokens_input, tokens_output, iterations,
    runtime_seconds, and tool_calls from the results data, then computes the
    correlation between every unique pair.

    Args:
        results_data: Evaluation results dictionary with ``tasks`` list.
            Each task is expected to have an ``mcp`` sub-dict containing
            ``cost``, ``tokens`` (with ``input``/``output``), ``iterations``,
            ``runtime_seconds``, and ``tool_calls``.

    Returns:
        Nested dictionary keyed by ``"metric_a vs metric_b"`` containing the
        Pearson correlation result for that pair. Returns an empty dict if
        there are fewer than 2 tasks.
    """
    tasks = results_data.get("tasks", [])
    if len(tasks) < 2:
        return {}

    # Extract metric vectors from task data
    metric_vectors: dict[str, list[float]] = {
        "cost": [],
        "tokens_input": [],
        "tokens_output": [],
        "iterations": [],
        "runtime_seconds": [],
        "tool_calls": [],
    }

    for task in tasks:
        mcp = task.get("mcp", {})
        tokens = mcp.get("tokens", {})

        metric_vectors["cost"].append(float(mcp.get("cost", 0.0)))
        metric_vectors["tokens_input"].append(float(tokens.get("input", 0)))
        metric_vectors["tokens_output"].append(float(tokens.get("output", 0)))
        metric_vectors["iterations"].append(float(mcp.get("iterations", 0)))
        metric_vectors["runtime_seconds"].append(float(mcp.get("runtime_seconds", 0.0)))

        # tool_calls may be an int or derived from tool_usage
        tool_calls = mcp.get("tool_calls", 0)
        if not tool_calls and mcp.get("tool_usage"):
            tool_calls = sum(mcp["tool_usage"].values())
        metric_vectors["tool_calls"].append(float(tool_calls))

    metric_names = sorted(metric_vectors.keys())
    correlations: dict[str, dict[str, Any]] = {}

    for i, name_a in enumerate(metric_names):
        for name_b in metric_names[i + 1 :]:
            pair_key = f"{name_a} vs {name_b}"
            try:
                result = pearson_correlation(metric_vectors[name_a], metric_vectors[name_b])
            except ValueError:
                # Not enough data or constant values
                result = {"r": 0.0, "r_squared": 0.0, "p_value": 1.0, "n": 0}
            correlations[pair_key] = result

    return correlations


def find_strong_correlations(
    correlations: dict[str, dict[str, Any]],
    threshold: float = 0.7,
) -> list[dict[str, Any]]:
    """Filter correlation results to only those with strong relationships.

    A correlation is considered strong when ``|r| > threshold``.

    Args:
        correlations: Dictionary of correlation results as returned by
            :func:`analyze_metric_correlations`.
        threshold: Minimum absolute value of r to consider strong.
            Defaults to 0.7.

    Returns:
        List of dictionaries, each containing:
        - pair: The metric pair key string.
        - r: The correlation coefficient.
        - r_squared: Coefficient of determination.
        - p_value: Approximate p-value.
        - n: Number of observations.
        - direction: ``"positive"`` or ``"negative"``.

        Sorted by descending ``|r|``.
    """
    strong: list[dict[str, Any]] = []
    for pair_key, result in correlations.items():
        r = result.get("r", 0.0)
        if abs(r) > threshold:
            strong.append(
                {
                    "pair": pair_key,
                    "r": r,
                    "r_squared": result.get("r_squared", 0.0),
                    "p_value": result.get("p_value", 1.0),
                    "n": result.get("n", 0),
                    "direction": "positive" if r > 0 else "negative",
                }
            )

    strong.sort(key=lambda item: abs(item["r"]), reverse=True)
    return strong


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_ranks(values: list[float]) -> list[float]:
    """Convert values to ranks with average ranking for ties.

    Args:
        values: Sequence of numeric values.

    Returns:
        List of ranks (1-based) corresponding to each input value.
    """
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * n

    i = 0
    while i < n:
        # Find the run of tied values
        j = i + 1
        while j < n and indexed[j][1] == indexed[i][1]:
            j += 1

        # Average rank for the tied group (1-based)
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank

        i = j

    return ranks


def _approximate_p_value(r: float, n: int) -> float:
    """Approximate the two-tailed p-value for a Pearson correlation.

    Uses the t-statistic ``t = r * sqrt((n-2) / (1-r^2))`` and a rough
    normal approximation for the tail probability. This is suitable for
    exploratory analysis; for precise inference use a statistics library.

    Args:
        r: Correlation coefficient.
        n: Sample size.

    Returns:
        Approximate two-tailed p-value (clamped to [0, 1]).
    """
    if n <= 2:
        return 1.0
    if abs(r) >= 1.0:
        return 0.0

    df = n - 2
    t_stat = r * math.sqrt(df / (1.0 - r * r))
    # Approximate the survival function of t-distribution using a normal CDF
    # approximation (adequate for df > ~10; rough but usable otherwise)
    p = 2.0 * _normal_survival(abs(t_stat))
    return max(0.0, min(1.0, p))


def _normal_survival(x: float) -> float:
    """Approximate the survival function (1 - CDF) of the standard normal.

    Uses the complementary error function available in the math module.

    Args:
        x: Standard normal quantile.

    Returns:
        Approximate probability P(Z > x).
    """
    return 0.5 * math.erfc(x / math.sqrt(2.0))
