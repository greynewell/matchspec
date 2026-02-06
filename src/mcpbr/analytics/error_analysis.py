"""Enhanced error pattern analysis for benchmark results.

Provides clustering of similar errors, temporal pattern detection,
tool-error correlation, and identification of flaky tasks across runs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


class ErrorPatternAnalyzer:
    """Analyzes error patterns across benchmark results.

    Clusters similar errors, detects temporal patterns, correlates errors
    with specific tools, and produces actionable recommendations.
    """

    def __init__(self) -> None:
        """Initialize the ErrorPatternAnalyzer."""

    def analyze(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze error patterns across benchmark results.

        Args:
            results: List of task result dicts. Each may contain keys like
                ``error``, ``errors`` (list), ``tool``, ``iteration``,
                and ``instance_id``.

        Returns:
            Dictionary with keys:
                - total_errors: Total number of errors found.
                - error_clusters: List of cluster dicts with pattern, count,
                  examples, and category.
                - temporal_patterns: Dict describing whether errors increase
                  over iterations.
                - tool_error_correlation: Dict mapping tool names to error rates.
                - recommendations: List of actionable recommendation strings.
        """
        errors: list[str] = []
        tool_results: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "errors": 0})
        iteration_errors: dict[int, int] = defaultdict(int)
        iteration_totals: dict[int, int] = defaultdict(int)

        for result in results:
            # Collect errors from the result
            task_errors = self._extract_errors(result)
            errors.extend(task_errors)

            # Track tool-level statistics
            tool_name = result.get("tool", result.get("tool_name", "unknown"))
            tool_results[tool_name]["total"] += 1
            if task_errors:
                tool_results[tool_name]["errors"] += 1

            # Track iteration-level statistics
            iteration = result.get("iteration", 0)
            iteration_totals[iteration] += 1
            if task_errors:
                iteration_errors[iteration] += 1

        clusters = self.cluster_errors(errors)
        temporal = self._analyze_temporal_patterns(iteration_errors, iteration_totals)
        tool_correlation = self._compute_tool_error_correlation(tool_results)
        recommendations = self._generate_recommendations(
            clusters, temporal, tool_correlation, len(errors)
        )

        return {
            "total_errors": len(errors),
            "error_clusters": clusters,
            "temporal_patterns": temporal,
            "tool_error_correlation": tool_correlation,
            "recommendations": recommendations,
        }

    def cluster_errors(
        self,
        errors: list[str],
        similarity_threshold: float = 0.6,
    ) -> list[dict[str, Any]]:
        """Cluster similar error messages using token-overlap similarity.

        Groups errors whose Jaccard similarity exceeds the given threshold,
        then categorises each cluster.

        Args:
            errors: List of raw error message strings.
            similarity_threshold: Minimum Jaccard similarity to merge two
                errors into the same cluster. Defaults to 0.6.

        Returns:
            List of cluster dicts, each containing:
                - pattern: Representative error string (most common).
                - count: Number of errors in the cluster.
                - examples: Up to 3 distinct example messages.
                - category: High-level category string.
        """
        if not errors:
            return []

        # Each cluster is a list of error strings
        clusters: list[list[str]] = []

        for error in errors:
            merged = False
            for cluster in clusters:
                # Compare against the first element as the cluster representative
                if self._jaccard_similarity(error, cluster[0]) >= similarity_threshold:
                    cluster.append(error)
                    merged = True
                    break
            if not merged:
                clusters.append([error])

        result: list[dict[str, Any]] = []
        for cluster in clusters:
            counter = Counter(cluster)
            most_common_msg = counter.most_common(1)[0][0]
            unique_examples = list(dict.fromkeys(cluster))[:3]
            result.append(
                {
                    "pattern": most_common_msg,
                    "count": len(cluster),
                    "examples": unique_examples,
                    "category": self._categorize_error(most_common_msg),
                }
            )

        # Sort by count descending
        result.sort(key=lambda c: c["count"], reverse=True)
        return result

    def _jaccard_similarity(self, a: str, b: str) -> float:
        """Compute word-level Jaccard similarity between two strings.

        Args:
            a: First string.
            b: Second string.

        Returns:
            Jaccard similarity coefficient in [0.0, 1.0].
        """
        tokens_a = set(a.lower().split())
        tokens_b = set(b.lower().split())
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_errors(result: dict[str, Any]) -> list[str]:
        """Extract error strings from a single task result.

        Args:
            result: A task result dict.

        Returns:
            List of error message strings found in the result.
        """
        errors: list[str] = []
        if "error" in result and result["error"]:
            errors.append(str(result["error"]))
        if "errors" in result and isinstance(result["errors"], list):
            errors.extend(str(e) for e in result["errors"] if e)
        return errors

    @staticmethod
    def _analyze_temporal_patterns(
        iteration_errors: dict[int, int],
        iteration_totals: dict[int, int],
    ) -> dict[str, Any]:
        """Determine whether errors increase over iterations.

        Args:
            iteration_errors: Mapping of iteration number to error count.
            iteration_totals: Mapping of iteration number to total task count.

        Returns:
            Dict with ``increasing``, ``error_rates_by_iteration``, and
            ``description`` keys.
        """
        if not iteration_totals:
            return {
                "increasing": False,
                "error_rates_by_iteration": {},
                "description": "No iteration data available.",
            }

        sorted_iters = sorted(iteration_totals.keys())
        rates: dict[int, float] = {}
        for it in sorted_iters:
            total = iteration_totals[it]
            errs = iteration_errors.get(it, 0)
            rates[it] = errs / total if total else 0.0

        # Determine trend: compare first half average to second half average
        rate_values = [rates[it] for it in sorted_iters]
        if len(rate_values) < 2:
            increasing = False
            description = "Insufficient iterations to determine trend."
        else:
            mid = len(rate_values) // 2
            first_half_avg = sum(rate_values[:mid]) / mid
            second_half_avg = sum(rate_values[mid:]) / (len(rate_values) - mid)
            increasing = second_half_avg > first_half_avg * 1.1  # 10% margin
            if increasing:
                description = (
                    "Error rate is increasing over iterations "
                    f"({first_half_avg:.1%} -> {second_half_avg:.1%})."
                )
            else:
                description = "Error rate is stable or decreasing over iterations."

        return {
            "increasing": increasing,
            "error_rates_by_iteration": rates,
            "description": description,
        }

    @staticmethod
    def _compute_tool_error_correlation(
        tool_results: dict[str, dict[str, int]],
    ) -> dict[str, float]:
        """Compute error rate per tool.

        Args:
            tool_results: Mapping of tool name to dict with ``total`` and
                ``errors`` counts.

        Returns:
            Dict mapping tool name to error rate (0.0 - 1.0).
        """
        correlation: dict[str, float] = {}
        for tool, stats in tool_results.items():
            total = stats["total"]
            correlation[tool] = stats["errors"] / total if total else 0.0
        return correlation

    @staticmethod
    def _categorize_error(error: str) -> str:
        """Assign a high-level category to an error message.

        Args:
            error: The error message string.

        Returns:
            A category string such as ``"timeout"``, ``"authentication"``,
            ``"rate_limit"``, ``"connection"``, ``"validation"``,
            ``"permission"``, or ``"unknown"``.
        """
        lower = error.lower()
        if any(kw in lower for kw in ("timeout", "timed out", "deadline")):
            return "timeout"
        if any(kw in lower for kw in ("auth", "unauthorized", "forbidden", "401", "403")):
            return "authentication"
        if any(kw in lower for kw in ("rate limit", "429", "too many requests", "throttl")):
            return "rate_limit"
        if any(
            kw in lower
            for kw in ("connection", "refused", "unreachable", "dns", "network", "econnreset")
        ):
            return "connection"
        if any(kw in lower for kw in ("invalid", "validation", "schema", "parse", "format")):
            return "validation"
        if any(kw in lower for kw in ("permission", "denied", "access")):
            return "permission"
        return "unknown"

    @staticmethod
    def _generate_recommendations(
        clusters: list[dict[str, Any]],
        temporal: dict[str, Any],
        tool_correlation: dict[str, float],
        total_errors: int,
    ) -> list[str]:
        """Generate actionable recommendations based on analysis results.

        Args:
            clusters: Error clusters from ``cluster_errors``.
            temporal: Temporal pattern analysis results.
            tool_correlation: Tool-to-error-rate mapping.
            total_errors: Total number of errors observed.

        Returns:
            List of recommendation strings.
        """
        recommendations: list[str] = []

        if total_errors == 0:
            recommendations.append("No errors detected. Results look healthy.")
            return recommendations

        # Recommend based on dominant error categories
        category_counts: dict[str, int] = defaultdict(int)
        for cluster in clusters:
            category_counts[cluster["category"]] += cluster["count"]

        if category_counts.get("timeout", 0) > 0:
            recommendations.append(
                "Timeout errors detected. Consider increasing timeout limits "
                "or optimising slow operations."
            )
        if category_counts.get("rate_limit", 0) > 0:
            recommendations.append(
                "Rate-limit errors detected. Add retry logic with exponential "
                "backoff or reduce request concurrency."
            )
        if category_counts.get("connection", 0) > 0:
            recommendations.append(
                "Connection errors detected. Verify network connectivity and server availability."
            )
        if category_counts.get("authentication", 0) > 0:
            recommendations.append(
                "Authentication errors detected. Check API keys and credential configuration."
            )
        if category_counts.get("validation", 0) > 0:
            recommendations.append(
                "Validation errors detected. Review input data and schema compatibility."
            )

        # Temporal recommendation
        if temporal.get("increasing"):
            recommendations.append(
                "Error rate increases over iterations. This may indicate "
                "resource exhaustion or degrading service health."
            )

        # Tool-specific recommendation
        high_error_tools = [tool for tool, rate in tool_correlation.items() if rate > 0.5]
        if high_error_tools:
            tools_str = ", ".join(sorted(high_error_tools))
            recommendations.append(
                f"Tools with >50% error rate: {tools_str}. "
                "Investigate these tools for systemic issues."
            )

        # Dominant cluster recommendation
        if clusters and clusters[0]["count"] > total_errors * 0.5:
            recommendations.append(
                f"The most common error pattern accounts for "
                f"{clusters[0]['count']}/{total_errors} errors. "
                f"Fixing this pattern would significantly reduce failures."
            )

        return recommendations


def identify_flaky_tasks(
    results_runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify tasks with inconsistent outcomes across multiple runs.

    A task is considered *flaky* if it passes in some runs and fails in
    others (i.e., its pass rate is strictly between 0 and 1).

    Args:
        results_runs: List of run result dicts. Each run should contain a
            ``tasks`` key holding a list of task dicts with at least
            ``instance_id`` and one of ``resolved`` (bool) or ``error``
            (truthy on failure).

    Returns:
        List of dicts, one per unique ``instance_id``, with keys:
            - instance_id: The task identifier.
            - pass_rate: Fraction of runs where the task passed.
            - run_count: Number of runs the task appeared in.
            - flaky: True if 0 < pass_rate < 1.
    """
    task_outcomes: dict[str, list[bool]] = defaultdict(list)

    for run in results_runs:
        tasks = run.get("tasks", [])
        for task in tasks:
            instance_id = task.get("instance_id", "")
            if not instance_id:
                continue
            # Determine pass/fail: explicit 'resolved' flag or absence of error
            if "resolved" in task:
                passed = bool(task["resolved"])
            else:
                passed = not bool(task.get("error"))
            task_outcomes[instance_id].append(passed)

    result: list[dict[str, Any]] = []
    for instance_id, outcomes in sorted(task_outcomes.items()):
        run_count = len(outcomes)
        pass_count = sum(outcomes)
        pass_rate = pass_count / run_count if run_count else 0.0
        flaky = 0.0 < pass_rate < 1.0
        result.append(
            {
                "instance_id": instance_id,
                "pass_rate": pass_rate,
                "run_count": run_count,
                "flaky": flaky,
            }
        )

    return result
