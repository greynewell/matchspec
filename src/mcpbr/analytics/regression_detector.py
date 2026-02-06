"""Enhanced regression detection with statistical significance testing.

Compares a current evaluation run against a baseline to detect regressions
(and improvements) in resolution rate, cost, latency, and token usage.
Uses chi-squared testing for resolution rate significance.
"""

from __future__ import annotations

import math
from typing import Any


def _normal_cdf(x: float) -> float:
    """Approximate the standard normal cumulative distribution function.

    Uses the Abramowitz & Stegun rational approximation (formula 26.2.17)
    which is accurate to about 1e-5.

    Args:
        x: The z-score value.

    Returns:
        Probability that a standard normal variable is less than or equal to *x*.
    """
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0

    sign = 1.0
    if x < 0:
        sign = -1.0
        x = -x

    t = 1.0 / (1.0 + 0.2316419 * x)
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    t5 = t4 * t

    pdf = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
    cdf_upper = pdf * (
        0.319381530 * t - 0.356563782 * t2 + 1.781477937 * t3 - 1.821255978 * t4 + 1.330274429 * t5
    )

    if sign > 0:
        return 1.0 - cdf_upper
    else:
        return cdf_upper


def _chi_squared_test(
    resolved_a: int,
    total_a: int,
    resolved_b: int,
    total_b: int,
    significance_level: float = 0.05,
) -> dict[str, Any]:
    """Perform a chi-squared test for independence on two resolution rates.

    Constructs a 2x2 contingency table and computes the chi-squared statistic
    with Yates' continuity correction.

    Args:
        resolved_a: Number of resolved tasks in group A (current).
        total_a: Total tasks in group A.
        resolved_b: Number of resolved tasks in group B (baseline).
        total_b: Total tasks in group B.
        significance_level: Alpha threshold for significance (default 0.05).

    Returns:
        Dictionary with ``chi_squared``, ``p_value``, ``significant``,
        and ``degrees_of_freedom``.
    """
    unresolved_a = total_a - resolved_a
    unresolved_b = total_b - resolved_b
    grand_total = total_a + total_b

    if grand_total == 0:
        return {
            "chi_squared": 0.0,
            "p_value": 1.0,
            "significant": False,
            "degrees_of_freedom": 1,
        }

    total_resolved = resolved_a + resolved_b
    total_unresolved = unresolved_a + unresolved_b

    expected = [
        [total_resolved * total_a / grand_total, total_unresolved * total_a / grand_total],
        [total_resolved * total_b / grand_total, total_unresolved * total_b / grand_total],
    ]

    observed = [
        [resolved_a, unresolved_a],
        [resolved_b, unresolved_b],
    ]

    chi2 = 0.0
    for i in range(2):
        for j in range(2):
            e = expected[i][j]
            if e > 0:
                diff = abs(observed[i][j] - e) - 0.5
                if diff < 0:
                    diff = 0.0
                chi2 += (diff * diff) / e

    if chi2 > 0:
        z = math.sqrt(chi2)
        p_value = 2.0 * (1.0 - _normal_cdf(z))
    else:
        p_value = 1.0

    return {
        "chi_squared": round(chi2, 6),
        "p_value": round(p_value, 6),
        "significant": p_value < significance_level,
        "degrees_of_freedom": 1,
    }


def _extract_task_map(results_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a mapping from instance_id to task-level MCP metrics.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        Dictionary mapping ``instance_id`` to the task's ``mcp`` sub-dict.
    """
    task_map: dict[str, dict[str, Any]] = {}
    for task in results_data.get("tasks", []):
        instance_id = task.get("instance_id", "")
        mcp = task.get("mcp", {})
        task_map[instance_id] = mcp
    return task_map


def _compute_task_averages(results_data: dict[str, Any]) -> dict[str, float]:
    """Compute average tokens and runtime across all tasks.

    Args:
        results_data: Evaluation results dictionary.

    Returns:
        Dictionary with ``avg_tokens`` and ``avg_runtime``.
    """
    tasks = results_data.get("tasks", [])
    total_tokens = 0
    total_runtime = 0.0
    count = len(tasks)

    for task in tasks:
        mcp = task.get("mcp", {})
        tokens = mcp.get("tokens", {})
        total_tokens += tokens.get("input", 0) + tokens.get("output", 0)
        total_runtime += mcp.get("runtime_seconds", 0.0)

    return {
        "avg_tokens": total_tokens / count if count > 0 else 0.0,
        "avg_runtime": total_runtime / count if count > 0 else 0.0,
    }


class RegressionDetector:
    """Detect performance regressions between evaluation runs.

    Compares a current run against a baseline across multiple dimensions:
    resolution rate (with statistical significance testing), cost, latency,
    and token usage. Also reports per-task regressions and improvements.

    Example::

        detector = RegressionDetector(threshold=0.05)
        result = detector.detect(current_results, baseline_results)
        if result["overall_status"] == "fail":
            print("Regression detected!")
        print(detector.format_report())
    """

    def __init__(
        self,
        threshold: float = 0.05,
        significance_level: float = 0.05,
    ) -> None:
        """Configure the regression detector.

        Args:
            threshold: Minimum absolute change in resolution rate to consider
                as a potential regression. Defaults to 0.05 (5 percentage
                points).
            significance_level: Alpha level for statistical significance
                testing. Defaults to 0.05.
        """
        self.threshold = threshold
        self.significance_level = significance_level
        self._last_result: dict[str, Any] | None = None

    def detect(
        self,
        current: dict[str, Any],
        baseline: dict[str, Any],
    ) -> dict[str, Any]:
        """Detect regressions between current and baseline results.

        Analyzes resolution rate, cost, latency, and token usage, plus
        per-task changes.

        Args:
            current: Current evaluation results dictionary.
            baseline: Baseline evaluation results dictionary to compare against.

        Returns:
            Dictionary containing:
                - ``score_regression``: Resolution rate regression analysis
                  with ``detected``, ``current_rate``, ``baseline_rate``,
                  ``delta``, and ``significant``.
                - ``cost_regression``: Cost change analysis with ``detected``,
                  ``current_cost``, ``baseline_cost``, and ``delta_pct``.
                - ``latency_regression``: Latency change analysis.
                - ``token_regression``: Token usage change analysis.
                - ``task_regressions``: List of tasks that regressed.
                - ``task_improvements``: List of tasks that improved.
                - ``overall_status``: ``"pass"``, ``"warning"``, or ``"fail"``.
                - ``summary``: Human-readable summary string.
        """
        current_summary = current.get("summary", {}).get("mcp", {})
        baseline_summary = baseline.get("summary", {}).get("mcp", {})

        # -- Resolution rate regression --
        current_rate = current_summary.get("rate", 0.0)
        baseline_rate = baseline_summary.get("rate", 0.0)
        rate_delta = current_rate - baseline_rate

        current_resolved = current_summary.get("resolved", 0)
        current_total = current_summary.get("total", 0)
        baseline_resolved = baseline_summary.get("resolved", 0)
        baseline_total = baseline_summary.get("total", 0)

        sig_test = _chi_squared_test(
            current_resolved,
            current_total,
            baseline_resolved,
            baseline_total,
            self.significance_level,
        )

        score_regression_detected = rate_delta < -self.threshold and sig_test["significant"]

        score_regression = {
            "detected": score_regression_detected,
            "current_rate": current_rate,
            "baseline_rate": baseline_rate,
            "delta": round(rate_delta, 6),
            "significant": sig_test["significant"],
        }

        # -- Cost regression --
        current_cost = current_summary.get("total_cost", 0.0)
        baseline_cost = baseline_summary.get("total_cost", 0.0)
        cost_delta_pct = (
            ((current_cost - baseline_cost) / baseline_cost * 100.0) if baseline_cost > 0 else 0.0
        )
        cost_regression_detected = cost_delta_pct > 20.0  # >20% cost increase

        cost_regression = {
            "detected": cost_regression_detected,
            "current_cost": current_cost,
            "baseline_cost": baseline_cost,
            "delta_pct": round(cost_delta_pct, 2),
        }

        # -- Latency regression --
        current_avgs = _compute_task_averages(current)
        baseline_avgs = _compute_task_averages(baseline)

        current_avg_runtime = current_avgs["avg_runtime"]
        baseline_avg_runtime = baseline_avgs["avg_runtime"]
        latency_delta_pct = (
            ((current_avg_runtime - baseline_avg_runtime) / baseline_avg_runtime * 100.0)
            if baseline_avg_runtime > 0
            else 0.0
        )
        latency_regression_detected = latency_delta_pct > 25.0  # >25% slower

        latency_regression = {
            "detected": latency_regression_detected,
            "current_avg": round(current_avg_runtime, 2),
            "baseline_avg": round(baseline_avg_runtime, 2),
            "delta_pct": round(latency_delta_pct, 2),
        }

        # -- Token regression --
        current_avg_tokens = current_avgs["avg_tokens"]
        baseline_avg_tokens = baseline_avgs["avg_tokens"]
        token_delta_pct = (
            ((current_avg_tokens - baseline_avg_tokens) / baseline_avg_tokens * 100.0)
            if baseline_avg_tokens > 0
            else 0.0
        )
        token_regression_detected = token_delta_pct > 25.0  # >25% more tokens

        token_regression = {
            "detected": token_regression_detected,
            "current_avg": round(current_avg_tokens, 2),
            "baseline_avg": round(baseline_avg_tokens, 2),
            "delta_pct": round(token_delta_pct, 2),
        }

        # -- Per-task regressions and improvements --
        current_tasks = _extract_task_map(current)
        baseline_tasks = _extract_task_map(baseline)

        task_regressions: list[dict[str, Any]] = []
        task_improvements: list[dict[str, Any]] = []

        all_ids = set(current_tasks.keys()) | set(baseline_tasks.keys())
        for instance_id in sorted(all_ids):
            curr_mcp = current_tasks.get(instance_id, {})
            base_mcp = baseline_tasks.get(instance_id, {})

            curr_resolved = bool(curr_mcp.get("resolved", False))
            base_resolved = bool(base_mcp.get("resolved", False))

            if base_resolved and not curr_resolved:
                task_regressions.append(
                    {
                        "instance_id": instance_id,
                        "baseline_resolved": True,
                        "current_resolved": False,
                    }
                )
            elif not base_resolved and curr_resolved:
                task_improvements.append(
                    {
                        "instance_id": instance_id,
                        "baseline_resolved": False,
                        "current_resolved": True,
                    }
                )

        # -- Overall status --
        if score_regression_detected:
            overall_status = "fail"
        elif cost_regression_detected or latency_regression_detected or token_regression_detected:
            overall_status = "warning"
        elif len(task_regressions) > 0:
            overall_status = "warning"
        else:
            overall_status = "pass"

        # -- Summary --
        summary_parts: list[str] = []
        if score_regression_detected:
            summary_parts.append(
                f"Resolution rate regression: {baseline_rate:.1%} -> {current_rate:.1%} "
                f"(delta={rate_delta:+.4f}, p={sig_test['p_value']:.4f})"
            )
        if cost_regression_detected:
            summary_parts.append(
                f"Cost increase: ${baseline_cost:.4f} -> ${current_cost:.4f} "
                f"({cost_delta_pct:+.1f}%)"
            )
        if latency_regression_detected:
            summary_parts.append(
                f"Latency increase: {baseline_avg_runtime:.1f}s -> {current_avg_runtime:.1f}s "
                f"({latency_delta_pct:+.1f}%)"
            )
        if token_regression_detected:
            summary_parts.append(
                f"Token usage increase: {baseline_avg_tokens:.0f} -> {current_avg_tokens:.0f} "
                f"({token_delta_pct:+.1f}%)"
            )
        if task_regressions:
            summary_parts.append(f"{len(task_regressions)} task(s) regressed")
        if task_improvements:
            summary_parts.append(f"{len(task_improvements)} task(s) improved")

        if not summary_parts:
            summary = "No regressions detected. All metrics are within acceptable thresholds."
        else:
            summary = "; ".join(summary_parts) + "."

        self._last_result = {
            "score_regression": score_regression,
            "cost_regression": cost_regression,
            "latency_regression": latency_regression,
            "token_regression": token_regression,
            "task_regressions": task_regressions,
            "task_improvements": task_improvements,
            "overall_status": overall_status,
            "summary": summary,
        }

        return self._last_result

    def format_report(self) -> str:
        """Format the last detection result as a human-readable report.

        Returns:
            Multi-line string containing the formatted regression report.

        Raises:
            ValueError: If :meth:`detect` has not been called yet.
        """
        if self._last_result is None:
            raise ValueError("No detection results available. Call detect() first.")

        r = self._last_result
        score = r["score_regression"]
        cost = r["cost_regression"]
        latency = r["latency_regression"]
        tokens = r["token_regression"]

        status_symbol = {
            "pass": "PASS",
            "warning": "WARNING",
            "fail": "FAIL",
        }.get(r["overall_status"], "UNKNOWN")

        lines = [
            f"{'=' * 60}",
            "Regression Detection Report",
            f"{'=' * 60}",
            f"Overall Status: {status_symbol}",
            "",
            "Resolution Rate:",
            f"  Baseline: {score['baseline_rate']:.1%}",
            f"  Current:  {score['current_rate']:.1%}",
            f"  Delta:    {score['delta']:+.4f}",
            f"  Significant: {'Yes' if score['significant'] else 'No'}",
            f"  Regression:  {'DETECTED' if score['detected'] else 'None'}",
            "",
            "Cost:",
            f"  Baseline: ${cost['baseline_cost']:.4f}",
            f"  Current:  ${cost['current_cost']:.4f}",
            f"  Change:   {cost['delta_pct']:+.1f}%",
            f"  Regression: {'DETECTED' if cost['detected'] else 'None'}",
            "",
            "Latency (avg per task):",
            f"  Baseline: {latency['baseline_avg']:.1f}s",
            f"  Current:  {latency['current_avg']:.1f}s",
            f"  Change:   {latency['delta_pct']:+.1f}%",
            f"  Regression: {'DETECTED' if latency['detected'] else 'None'}",
            "",
            "Token Usage (avg per task):",
            f"  Baseline: {tokens['baseline_avg']:.0f}",
            f"  Current:  {tokens['current_avg']:.0f}",
            f"  Change:   {tokens['delta_pct']:+.1f}%",
            f"  Regression: {'DETECTED' if tokens['detected'] else 'None'}",
        ]

        if r["task_regressions"]:
            lines.append("")
            lines.append(f"Task Regressions ({len(r['task_regressions'])}):")
            for task in r["task_regressions"]:
                lines.append(f"  - {task['instance_id']}: resolved -> unresolved")

        if r["task_improvements"]:
            lines.append("")
            lines.append(f"Task Improvements ({len(r['task_improvements'])}):")
            for task in r["task_improvements"]:
                lines.append(f"  - {task['instance_id']}: unresolved -> resolved")

        lines.append("")
        lines.append(f"Summary: {r['summary']}")
        lines.append(f"{'=' * 60}")

        return "\n".join(lines)
