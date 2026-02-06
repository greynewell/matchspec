"""Statistical significance testing for mcpbr evaluation results.

Provides hypothesis tests and effect size calculations for comparing
benchmark results across different MCP server configurations, models,
or evaluation runs. Uses only Python standard library (no NumPy/SciPy).

Example usage::

    from mcpbr.analytics.statistical import chi_squared_test, bootstrap_confidence_interval

    # Compare resolution rates between two configurations
    result = chi_squared_test(success_a=45, total_a=100, success_b=60, total_b=100)
    print(result["significant"])  # True/False

    # Get confidence interval for a metric
    ci = bootstrap_confidence_interval([0.85, 0.90, 0.78, 0.92, 0.88])
    print(f"{ci['mean']:.3f} [{ci['ci_lower']:.3f}, {ci['ci_upper']:.3f}]")
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Any


def _chi2_p_value(chi2_stat: float) -> float:
    """Approximate p-value for chi-squared with 1 degree of freedom.

    Uses the relationship between chi-squared(1) and the standard normal
    distribution, with the Abramowitz and Stegun approximation for the
    normal CDF.

    Args:
        chi2_stat: The chi-squared test statistic.

    Returns:
        Approximate two-tailed p-value.
    """
    if chi2_stat <= 0:
        return 1.0
    # chi2 with 1 df: p-value = 2 * (1 - Phi(sqrt(chi2)))
    z = math.sqrt(chi2_stat)
    # Standard normal CDF approximation (Abramowitz and Stegun 26.2.17)
    t = 1.0 / (1.0 + 0.2316419 * z)
    d = 0.3989422804014327  # 1 / sqrt(2 * pi)
    p = (
        d
        * math.exp(-z * z / 2.0)
        * (t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.8212560 + t * 1.330274)))))
    )
    return 2 * p  # Two-tailed


def _normal_cdf(z: float) -> float:
    """Approximate the standard normal CDF using Abramowitz and Stegun.

    Args:
        z: The z-score.

    Returns:
        Approximate P(Z <= z) for standard normal Z.
    """
    if z < 0:
        return 1.0 - _normal_cdf(-z)
    t = 1.0 / (1.0 + 0.2316419 * z)
    d = 0.3989422804014327  # 1 / sqrt(2 * pi)
    p = (
        d
        * math.exp(-z * z / 2.0)
        * (t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.8212560 + t * 1.330274)))))
    )
    return 1.0 - p


def chi_squared_test(
    success_a: int,
    total_a: int,
    success_b: int,
    total_b: int,
    significance_level: float = 0.05,
) -> dict[str, Any]:
    """Chi-squared test for comparing two proportions (resolution rates).

    Performs a 2x2 chi-squared test to determine whether the difference in
    success rates between two groups is statistically significant.

    Args:
        success_a: Number of successes in group A.
        total_a: Total observations in group A.
        success_b: Number of successes in group B.
        total_b: Total observations in group B.
        significance_level: Threshold for statistical significance (default 0.05).

    Returns:
        Dictionary with keys:
            - chi2: The chi-squared test statistic.
            - p_value: Approximate p-value (1 degree of freedom).
            - significant: Whether the result is significant at the given level.
            - effect_size: Phi coefficient (effect size for 2x2 tables).

    Raises:
        ValueError: If totals are zero or successes exceed totals.
    """
    if total_a <= 0 or total_b <= 0:
        raise ValueError("Totals must be positive integers.")
    if success_a < 0 or success_b < 0:
        raise ValueError("Successes must be non-negative.")
    if success_a > total_a or success_b > total_b:
        raise ValueError("Successes cannot exceed totals.")

    fail_a = total_a - success_a
    fail_b = total_b - success_b
    n = total_a + total_b

    # Observed counts: [[success_a, fail_a], [success_b, fail_b]]
    # Expected counts from marginals
    total_success = success_a + success_b
    total_fail = fail_a + fail_b

    # Expected values for each cell
    expected = [
        [total_success * total_a / n, total_fail * total_a / n],
        [total_success * total_b / n, total_fail * total_b / n],
    ]

    observed = [[success_a, fail_a], [success_b, fail_b]]

    # Chi-squared statistic
    chi2 = 0.0
    for i in range(2):
        for j in range(2):
            if expected[i][j] > 0:
                chi2 += (observed[i][j] - expected[i][j]) ** 2 / expected[i][j]

    p_value = _chi2_p_value(chi2)

    # Phi coefficient as effect size for 2x2 table
    effect_size = math.sqrt(chi2 / n) if n > 0 else 0.0

    return {
        "chi2": chi2,
        "p_value": p_value,
        "significant": p_value < significance_level,
        "effect_size": effect_size,
    }


def bootstrap_confidence_interval(
    values: list[float],
    confidence: float = 0.95,
    n_bootstrap: int = 1000,
) -> dict[str, Any]:
    """Bootstrap confidence interval for a metric.

    Generates bootstrap resamples to estimate the sampling distribution
    of the mean and constructs a percentile confidence interval.

    Args:
        values: Observed metric values to bootstrap.
        confidence: Confidence level (default 0.95 for 95% CI).
        n_bootstrap: Number of bootstrap resamples (default 1000).

    Returns:
        Dictionary with keys:
            - mean: Sample mean of the original values.
            - ci_lower: Lower bound of the confidence interval.
            - ci_upper: Upper bound of the confidence interval.
            - std_error: Bootstrap standard error of the mean.

    Raises:
        ValueError: If values is empty or confidence is not in (0, 1).
    """
    if not values:
        raise ValueError("Values list must not be empty.")
    if not 0.0 < confidence < 1.0:
        raise ValueError("Confidence must be between 0 and 1 (exclusive).")

    sample_mean = statistics.mean(values)
    n = len(values)

    # Generate bootstrap resamples
    bootstrap_means = []
    for _ in range(n_bootstrap):
        resample = random.choices(values, k=n)
        bootstrap_means.append(statistics.mean(resample))

    bootstrap_means.sort()

    # Percentile method
    alpha = 1.0 - confidence
    lower_idx = int(math.floor((alpha / 2) * n_bootstrap))
    upper_idx = int(math.floor((1.0 - alpha / 2) * n_bootstrap)) - 1

    # Clamp indices
    lower_idx = max(0, min(lower_idx, n_bootstrap - 1))
    upper_idx = max(0, min(upper_idx, n_bootstrap - 1))

    std_error = statistics.stdev(bootstrap_means) if len(bootstrap_means) > 1 else 0.0

    return {
        "mean": sample_mean,
        "ci_lower": bootstrap_means[lower_idx],
        "ci_upper": bootstrap_means[upper_idx],
        "std_error": std_error,
    }


def effect_size_cohens_d(group_a: list[float], group_b: list[float]) -> float:
    """Compute Cohen's d effect size between two groups.

    Cohen's d measures the standardized difference between two group means.
    Uses the pooled standard deviation as the denominator.

    Interpretation guidelines (Cohen, 1988):
        - |d| < 0.2: negligible
        - 0.2 <= |d| < 0.5: small
        - 0.5 <= |d| < 0.8: medium
        - |d| >= 0.8: large

    Args:
        group_a: Metric values for group A.
        group_b: Metric values for group B.

    Returns:
        Cohen's d effect size (positive means group_a > group_b).

    Raises:
        ValueError: If either group has fewer than 2 observations.
    """
    if len(group_a) < 2 or len(group_b) < 2:
        raise ValueError("Each group must have at least 2 observations.")

    mean_a = statistics.mean(group_a)
    mean_b = statistics.mean(group_b)
    n_a = len(group_a)
    n_b = len(group_b)

    var_a = statistics.variance(group_a)
    var_b = statistics.variance(group_b)

    # Pooled standard deviation
    pooled_var = ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)
    pooled_std = math.sqrt(pooled_var)

    if pooled_std == 0:
        return 0.0

    return (mean_a - mean_b) / pooled_std


def mann_whitney_u(
    group_a: list[float],
    group_b: list[float],
    significance_level: float = 0.05,
) -> dict[str, Any]:
    """Mann-Whitney U test for comparing two independent samples.

    A non-parametric test that compares the distributions of two groups
    without assuming normality. Uses the normal approximation for the
    U statistic, which is appropriate for sample sizes greater than ~20.

    Args:
        group_a: Metric values for group A.
        group_b: Metric values for group B.
        significance_level: Threshold for statistical significance (default 0.05).

    Returns:
        Dictionary with keys:
            - u_statistic: The Mann-Whitney U statistic.
            - p_value: Approximate two-tailed p-value (normal approximation).
            - significant: Whether the result is significant at the given level.

    Raises:
        ValueError: If either group is empty.
    """
    if not group_a or not group_b:
        raise ValueError("Both groups must be non-empty.")

    n_a = len(group_a)
    n_b = len(group_b)

    # Rank all observations together
    combined = [(val, "a") for val in group_a] + [(val, "b") for val in group_b]
    combined.sort(key=lambda x: x[0])

    # Assign ranks with tie handling (average rank for ties)
    n_total = n_a + n_b
    ranks: list[float] = [0.0] * n_total
    i = 0
    while i < n_total:
        j = i
        # Find the end of the tie group
        while j < n_total and combined[j][0] == combined[i][0]:
            j += 1
        # Average rank for this tie group (ranks are 1-based)
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j

    # Sum of ranks for group A
    rank_sum_a = sum(ranks[k] for k in range(n_total) if combined[k][1] == "a")

    # U statistic for group A
    u_a = rank_sum_a - n_a * (n_a + 1) / 2.0
    # U statistic for group B (for reporting the smaller)
    u_b = n_a * n_b - u_a
    u_statistic = min(u_a, u_b)

    # Normal approximation
    mu_u = n_a * n_b / 2.0
    sigma_u = math.sqrt(n_a * n_b * (n_a + n_b + 1) / 12.0)

    if sigma_u == 0:
        return {
            "u_statistic": u_statistic,
            "p_value": 1.0,
            "significant": False,
        }

    z = (u_a - mu_u) / sigma_u
    # Two-tailed p-value
    p_value = 2.0 * (1.0 - _normal_cdf(abs(z)))

    return {
        "u_statistic": u_statistic,
        "p_value": p_value,
        "significant": p_value < significance_level,
    }


def permutation_test(
    group_a: list[float],
    group_b: list[float],
    n_permutations: int = 1000,
    significance_level: float = 0.05,
) -> dict[str, Any]:
    """Permutation test for difference in means between two groups.

    Estimates the p-value by randomly shuffling group labels and computing
    how often the permuted difference is as extreme as the observed one.

    Args:
        group_a: Metric values for group A.
        group_b: Metric values for group B.
        n_permutations: Number of random permutations (default 1000).
        significance_level: Threshold for statistical significance (default 0.05).

    Returns:
        Dictionary with keys:
            - observed_diff: Observed difference in means (mean_a - mean_b).
            - p_value: Proportion of permutations with |diff| >= |observed_diff|.
            - significant: Whether the result is significant at the given level.

    Raises:
        ValueError: If either group is empty.
    """
    if not group_a or not group_b:
        raise ValueError("Both groups must be non-empty.")

    observed_diff = statistics.mean(group_a) - statistics.mean(group_b)
    abs_observed = abs(observed_diff)

    combined = group_a + group_b
    n_a = len(group_a)
    count_extreme = 0

    for _ in range(n_permutations):
        random.shuffle(combined)
        perm_a = combined[:n_a]
        perm_b = combined[n_a:]
        perm_diff = abs(statistics.mean(perm_a) - statistics.mean(perm_b))
        if perm_diff >= abs_observed:
            count_extreme += 1

    p_value = count_extreme / n_permutations

    return {
        "observed_diff": observed_diff,
        "p_value": p_value,
        "significant": p_value < significance_level,
    }


def compare_resolution_rates(
    results_a: dict[str, Any],
    results_b: dict[str, Any],
) -> dict[str, Any]:
    """Compare resolution rates from two benchmark result sets.

    Performs a comprehensive statistical comparison of two result sets,
    including a chi-squared test on resolution rates, effect size
    calculation, and a human-readable summary.

    The input dictionaries are expected to contain at minimum:
        - ``resolved`` (int): Number of successfully resolved tasks.
        - ``total`` (int): Total number of tasks attempted.

    Optional fields used if present:
        - ``scores`` (list[float]): Per-task scores for additional analyses.
        - ``name`` or ``label`` (str): Label for the result set.

    Args:
        results_a: First result set dictionary.
        results_b: Second result set dictionary.

    Returns:
        Dictionary with keys:
            - rate_a: Resolution rate for group A.
            - rate_b: Resolution rate for group B.
            - chi2_test: Full chi-squared test result dict.
            - effect_size: Phi coefficient from the chi-squared test.
            - scores_comparison: Cohen's d and Mann-Whitney results
              (only if both result sets contain ``scores``).
            - summary: Human-readable summary string.

    Raises:
        KeyError: If required keys are missing from result dicts.
    """
    resolved_a = results_a["resolved"]
    total_a = results_a["total"]
    resolved_b = results_b["resolved"]
    total_b = results_b["total"]

    rate_a = resolved_a / total_a if total_a > 0 else 0.0
    rate_b = resolved_b / total_b if total_b > 0 else 0.0

    chi2_result = chi_squared_test(resolved_a, total_a, resolved_b, total_b)

    label_a = results_a.get("name", results_a.get("label", "A"))
    label_b = results_b.get("name", results_b.get("label", "B"))

    output: dict[str, Any] = {
        "rate_a": rate_a,
        "rate_b": rate_b,
        "chi2_test": chi2_result,
        "effect_size": chi2_result["effect_size"],
    }

    # If per-task scores are available, add deeper comparison
    scores_a = results_a.get("scores")
    scores_b = results_b.get("scores")
    if scores_a and scores_b and len(scores_a) >= 2 and len(scores_b) >= 2:
        cohens_d = effect_size_cohens_d(scores_a, scores_b)
        mwu = mann_whitney_u(scores_a, scores_b)
        output["scores_comparison"] = {
            "cohens_d": cohens_d,
            "mann_whitney": mwu,
        }

    # Build summary
    diff_pct = abs(rate_a - rate_b) * 100
    if rate_a > rate_b:
        direction = "higher"
    elif rate_a < rate_b:
        direction = "lower"
    else:
        direction = "equal"
    sig_text = "statistically significant" if chi2_result["significant"] else "not significant"

    if direction == "equal":
        diff_text = "No difference"
    else:
        diff_text = f"{label_a} is {diff_pct:.1f}pp {direction}"

    summary = (
        f"{label_a} ({rate_a:.1%}) vs {label_b} ({rate_b:.1%}): "
        f"{diff_text}. "
        f"Difference is {sig_text} (p={chi2_result['p_value']:.4f}, "
        f"phi={chi2_result['effect_size']:.3f})."
    )
    output["summary"] = summary

    return output
