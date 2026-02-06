"""Anomaly detection for benchmark metrics.

Provides statistical methods (z-score, IQR, MAD) to identify outlier
values in benchmark cost, token, runtime, and iteration metrics.
"""

from __future__ import annotations

import statistics
from typing import Any


def detect_anomalies(
    values: list[float],
    method: str = "zscore",
    threshold: float = 2.0,
) -> list[dict[str, Any]]:
    """Detect anomalous values in a list of numeric measurements.

    Args:
        values: List of numeric values to analyse.
        method: Detection method. One of ``"zscore"`` (z-score exceeds
            threshold), ``"iqr"`` (IQR fence method), or ``"mad"``
            (median absolute deviation). Defaults to ``"zscore"``.
        threshold: Sensitivity threshold whose meaning depends on the
            method. For ``"zscore"`` and ``"mad"`` it is the number of
            standard deviations / MADs; for ``"iqr"`` it is the fence
            multiplier (commonly 1.5). Defaults to 2.0.

    Returns:
        List of anomaly dicts, each containing:
            - index: Position in the input list.
            - value: The anomalous value.
            - score: Computed score (z-score, IQR distance, or MAD score).
            - method: The detection method used.

    Raises:
        ValueError: If *method* is not one of the supported methods.
    """
    dispatch = {
        "zscore": _zscore_detect,
        "iqr": _iqr_detect,
        "mad": _mad_detect,
    }
    if method not in dispatch:
        raise ValueError(f"Unknown method '{method}'. Supported: {', '.join(sorted(dispatch))}.")
    return dispatch[method](values, threshold)


def detect_metric_anomalies(
    results_data: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Detect anomalies across standard benchmark metrics.

    Extracts cost, total tokens, runtime, and iteration counts from the
    results data and runs z-score anomaly detection on each metric.

    Args:
        results_data: Benchmark results dict with a ``tasks`` key
            containing a list of task dicts. Each task should have an
            ``mcp`` dict with ``cost``, ``tokens`` (with ``input`` and
            ``output``), ``runtime_seconds``, and ``iterations``.

    Returns:
        Dict mapping metric name (``"cost"``, ``"tokens"``,
        ``"runtime"``, ``"iterations"``) to a list of anomaly dicts
        returned by :func:`detect_anomalies`.
    """
    tasks = results_data.get("tasks", [])
    if not tasks:
        return {
            "cost": [],
            "tokens": [],
            "runtime": [],
            "iterations": [],
        }

    costs: list[float] = []
    tokens: list[float] = []
    runtimes: list[float] = []
    iterations: list[float] = []

    for task in tasks:
        mcp = task.get("mcp", {})
        costs.append(float(mcp.get("cost", 0.0)))
        token_info = mcp.get("tokens", {})
        total_tokens = float(token_info.get("input", 0)) + float(token_info.get("output", 0))
        tokens.append(total_tokens)
        runtimes.append(float(mcp.get("runtime_seconds", 0.0)))
        iterations.append(float(mcp.get("iterations", 0)))

    return {
        "cost": detect_anomalies(costs),
        "tokens": detect_anomalies(tokens),
        "runtime": detect_anomalies(runtimes),
        "iterations": detect_anomalies(iterations),
    }


# ------------------------------------------------------------------
# Detection method implementations
# ------------------------------------------------------------------


def _zscore_detect(
    values: list[float],
    threshold: float,
) -> list[dict[str, Any]]:
    """Detect anomalies using z-score.

    A value is anomalous if its absolute z-score exceeds *threshold*.

    Args:
        values: Numeric values to analyse.
        threshold: Z-score cutoff.

    Returns:
        List of anomaly dicts with index, value, score, and method.
    """
    if len(values) < 2:
        return []

    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return []

    anomalies: list[dict[str, Any]] = []
    for i, v in enumerate(values):
        z = abs(v - mean) / stdev
        if z > threshold:
            anomalies.append({"index": i, "value": v, "score": z, "method": "zscore"})
    return anomalies


def _iqr_detect(
    values: list[float],
    threshold: float,
) -> list[dict[str, Any]]:
    """Detect anomalies using the interquartile range (IQR) method.

    Values outside ``[Q1 - threshold*IQR, Q3 + threshold*IQR]`` are
    flagged. The score represents how many IQRs the value lies beyond
    the nearest fence.

    Args:
        values: Numeric values to analyse.
        threshold: IQR multiplier for the fence (commonly 1.5).

    Returns:
        List of anomaly dicts with index, value, score, and method.
    """
    if len(values) < 4:
        return []

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = statistics.median(sorted_vals[: n // 2])
    q3 = statistics.median(sorted_vals[(n + 1) // 2 :])
    iqr = q3 - q1
    if iqr == 0:
        return []

    lower_fence = q1 - threshold * iqr
    upper_fence = q3 + threshold * iqr

    anomalies: list[dict[str, Any]] = []
    for i, v in enumerate(values):
        if v < lower_fence:
            score = (lower_fence - v) / iqr
            anomalies.append({"index": i, "value": v, "score": score, "method": "iqr"})
        elif v > upper_fence:
            score = (v - upper_fence) / iqr
            anomalies.append({"index": i, "value": v, "score": score, "method": "iqr"})
    return anomalies


def _mad_detect(
    values: list[float],
    threshold: float,
) -> list[dict[str, Any]]:
    """Detect anomalies using median absolute deviation (MAD).

    The modified z-score is computed as ``0.6745 * (x - median) / MAD``.
    Values whose absolute modified z-score exceeds *threshold* are
    flagged.

    Args:
        values: Numeric values to analyse.
        threshold: Modified z-score cutoff.

    Returns:
        List of anomaly dicts with index, value, score, and method.
    """
    if len(values) < 2:
        return []

    med = statistics.median(values)
    abs_devs = [abs(v - med) for v in values]
    mad = statistics.median(abs_devs)
    if mad == 0:
        return []

    # 0.6745 is the 0.75th quantile of the standard normal distribution,
    # used to make MAD consistent with standard deviation for normal data.
    consistency_constant = 0.6745

    anomalies: list[dict[str, Any]] = []
    for i, v in enumerate(values):
        modified_z = consistency_constant * abs(v - med) / mad
        if modified_z > threshold:
            anomalies.append({"index": i, "value": v, "score": modified_z, "method": "mad"})
    return anomalies
