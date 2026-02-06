"""A/B testing framework for comparing MCP server configurations.

Provides tools for statistically comparing two evaluation runs (control vs.
treatment) to determine which configuration performs better on resolution rate,
cost, and other metrics.
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
) -> dict[str, Any]:
    """Perform a chi-squared test for independence on two resolution rates.

    Constructs a 2x2 contingency table of resolved/unresolved counts for
    groups A and B and computes the chi-squared statistic with Yates'
    continuity correction.  The p-value is derived from the chi-squared
    distribution with 1 degree of freedom using a normal CDF approximation.

    Args:
        resolved_a: Number of resolved tasks in group A.
        total_a: Total tasks in group A.
        resolved_b: Number of resolved tasks in group B.
        total_b: Total tasks in group B.

    Returns:
        Dictionary with ``chi_squared``, ``p_value``, ``significant``
        (at alpha = 0.05), and ``degrees_of_freedom``.
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

    # Expected values for the 2x2 table
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
                # Yates' continuity correction
                diff = abs(observed[i][j] - e) - 0.5
                if diff < 0:
                    diff = 0.0
                chi2 += (diff * diff) / e

    # Convert chi-squared (1 df) to p-value via normal approximation:
    # If X ~ chi2(1), then sqrt(X) ~ N(0,1) approximately.
    if chi2 > 0:
        z = math.sqrt(chi2)
        p_value = 2.0 * (1.0 - _normal_cdf(z))
    else:
        p_value = 1.0

    return {
        "chi_squared": round(chi2, 6),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "degrees_of_freedom": 1,
    }


def _extract_metrics(results_data: dict[str, Any]) -> dict[str, Any]:
    """Extract key metrics from a results_data dictionary.

    Args:
        results_data: Evaluation results with ``summary.mcp`` and ``tasks``.

    Returns:
        Dictionary with ``resolved``, ``total``, ``rate``, ``cost``,
        ``model``, ``provider``, ``avg_tokens``, and ``avg_runtime``.
    """
    summary = results_data.get("summary", {}).get("mcp", {})
    tasks = results_data.get("tasks", [])
    metadata = results_data.get("metadata", {})
    config = metadata.get("config", {})

    resolved = summary.get("resolved", 0)
    total = summary.get("total", 0)
    rate = summary.get("rate", 0.0)
    cost = summary.get("total_cost", 0.0)

    total_tokens = 0
    total_runtime = 0.0
    task_count = len(tasks)

    for task in tasks:
        mcp = task.get("mcp", {})
        tokens = mcp.get("tokens", {})
        total_tokens += tokens.get("input", 0) + tokens.get("output", 0)
        total_runtime += mcp.get("runtime_seconds", 0.0)

    avg_tokens = total_tokens // task_count if task_count > 0 else 0
    avg_runtime = total_runtime / task_count if task_count > 0 else 0.0

    return {
        "resolved": resolved,
        "total": total,
        "rate": rate,
        "cost": cost,
        "model": config.get("model", "unknown"),
        "provider": config.get("provider", "unknown"),
        "avg_tokens": avg_tokens,
        "avg_runtime": round(avg_runtime, 2),
    }


class ABTest:
    """A/B testing framework for comparing two MCP server configurations.

    Creates a structured comparison between a control group (A) and treatment
    group (B), running chi-squared significance testing on resolution rates
    and comparing cost metrics.

    Example::

        test = ABTest("Model Comparison")
        test.add_control(results_baseline)
        test.add_treatment(results_candidate)
        analysis = test.analyze()
        print(test.format_report())
    """

    def __init__(
        self,
        name: str,
        control_label: str = "A",
        treatment_label: str = "B",
    ) -> None:
        """Initialize the A/B test.

        Args:
            name: Human-readable name for this test.
            control_label: Label for the control group (default ``"A"``).
            treatment_label: Label for the treatment group (default ``"B"``).
        """
        self.name = name
        self.control_label = control_label
        self.treatment_label = treatment_label
        self._control: dict[str, Any] | None = None
        self._treatment: dict[str, Any] | None = None
        self._analysis: dict[str, Any] | None = None

    def add_control(self, results_data: dict[str, Any]) -> None:
        """Add the control group results.

        Args:
            results_data: Evaluation results dictionary for the control
                configuration.
        """
        self._control = results_data
        self._analysis = None

    def add_treatment(self, results_data: dict[str, Any]) -> None:
        """Add the treatment group results.

        Args:
            results_data: Evaluation results dictionary for the treatment
                configuration.
        """
        self._treatment = results_data
        self._analysis = None

    def analyze(self) -> dict[str, Any]:
        """Run the A/B test analysis.

        Compares resolution rates using a chi-squared test, and reports
        differences in cost and other metrics.

        Returns:
            Dictionary containing:
                - ``test_name``: The test name.
                - ``control``: Metrics for the control group.
                - ``treatment``: Metrics for the treatment group.
                - ``rate_difference``: Absolute difference in resolution rates.
                - ``rate_relative_change``: Percentage change in resolution rate.
                - ``cost_difference``: Difference in total cost.
                - ``statistical_significance``: Chi-squared test results.
                - ``winner``: ``"control"``, ``"treatment"``, or
                  ``"no_significant_difference"``.
                - ``recommendation``: Human-readable recommendation.

        Raises:
            ValueError: If control or treatment data has not been added.
        """
        if self._control is None:
            raise ValueError("Control group results not set. Call add_control() first.")
        if self._treatment is None:
            raise ValueError("Treatment group results not set. Call add_treatment() first.")

        ctrl = _extract_metrics(self._control)
        treat = _extract_metrics(self._treatment)

        rate_diff = treat["rate"] - ctrl["rate"]
        rate_relative = (rate_diff / ctrl["rate"] * 100.0) if ctrl["rate"] > 0 else 0.0
        cost_diff = treat["cost"] - ctrl["cost"]

        significance = _chi_squared_test(
            ctrl["resolved"],
            ctrl["total"],
            treat["resolved"],
            treat["total"],
        )

        # Determine winner
        if significance["significant"]:
            if treat["rate"] > ctrl["rate"]:
                winner = "treatment"
            elif treat["rate"] < ctrl["rate"]:
                winner = "control"
            else:
                winner = "no_significant_difference"
        else:
            winner = "no_significant_difference"

        # Build recommendation
        if winner == "treatment":
            recommendation = (
                f"Treatment ({self.treatment_label}) shows a statistically significant "
                f"improvement of {rate_relative:+.1f}% in resolution rate. "
                f"Recommend adopting the treatment configuration."
            )
        elif winner == "control":
            recommendation = (
                f"Control ({self.control_label}) performs significantly better. "
                f"Treatment ({self.treatment_label}) shows a {rate_relative:+.1f}% change "
                f"in resolution rate. Recommend keeping the control configuration."
            )
        else:
            recommendation = (
                f"No statistically significant difference detected between "
                f"{self.control_label} and {self.treatment_label} "
                f"(p={significance['p_value']:.4f}). Consider increasing sample size "
                f"or testing with a larger effect."
            )

        self._analysis = {
            "test_name": self.name,
            "control": {
                "label": self.control_label,
                "resolved": ctrl["resolved"],
                "total": ctrl["total"],
                "rate": ctrl["rate"],
                "cost": ctrl["cost"],
            },
            "treatment": {
                "label": self.treatment_label,
                "resolved": treat["resolved"],
                "total": treat["total"],
                "rate": treat["rate"],
                "cost": treat["cost"],
            },
            "rate_difference": round(rate_diff, 6),
            "rate_relative_change": round(rate_relative, 2),
            "cost_difference": round(cost_diff, 4),
            "statistical_significance": significance,
            "winner": winner,
            "recommendation": recommendation,
        }

        return self._analysis

    def format_report(self) -> str:
        """Format the analysis results as a human-readable report.

        Calls :meth:`analyze` automatically if it has not been called yet.

        Returns:
            Multi-line string containing the formatted A/B test report.

        Raises:
            ValueError: If control or treatment data has not been added.
        """
        if self._analysis is None:
            self.analyze()

        assert self._analysis is not None  # for type checker
        a = self._analysis

        ctrl = a["control"]
        treat = a["treatment"]
        sig = a["statistical_significance"]

        lines = [
            f"{'=' * 60}",
            f"A/B Test Report: {a['test_name']}",
            f"{'=' * 60}",
            "",
            f"Control ({ctrl['label']}):",
            f"  Resolution Rate: {ctrl['rate']:.1%} ({ctrl['resolved']}/{ctrl['total']})",
            f"  Total Cost:      ${ctrl['cost']:.4f}",
            "",
            f"Treatment ({treat['label']}):",
            f"  Resolution Rate: {treat['rate']:.1%} ({treat['resolved']}/{treat['total']})",
            f"  Total Cost:      ${treat['cost']:.4f}",
            "",
            "Comparison:",
            f"  Rate Difference:     {a['rate_difference']:+.4f} "
            f"({a['rate_relative_change']:+.1f}%)",
            f"  Cost Difference:     ${a['cost_difference']:+.4f}",
            "",
            "Statistical Significance:",
            f"  Chi-squared: {sig['chi_squared']:.4f}",
            f"  p-value:     {sig['p_value']:.6f}",
            f"  Significant: {'Yes' if sig['significant'] else 'No'} (alpha=0.05)",
            "",
            f"Winner: {a['winner']}",
            "",
            f"Recommendation: {a['recommendation']}",
            f"{'=' * 60}",
        ]

        return "\n".join(lines)


def run_ab_test(
    results_a: dict[str, Any],
    results_b: dict[str, Any],
    test_name: str = "A/B Test",
) -> dict[str, Any]:
    """Convenience function to run a quick A/B test comparison.

    Creates an :class:`ABTest` instance, adds the control and treatment
    data, and returns the analysis results.

    Args:
        results_a: Evaluation results for the control (A) group.
        results_b: Evaluation results for the treatment (B) group.
        test_name: Name for the test (default ``"A/B Test"``).

    Returns:
        Analysis dictionary from :meth:`ABTest.analyze`.
    """
    test = ABTest(test_name)
    test.add_control(results_a)
    test.add_treatment(results_b)
    return test.analyze()
