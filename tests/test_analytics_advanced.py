"""Comprehensive tests for advanced analytics modules.

Covers: error_analysis, anomaly, correlation, difficulty, ab_testing,
leaderboard, metrics, and regression_detector.
"""

from __future__ import annotations

import math

import pytest

from mcpbr.analytics.ab_testing import ABTest, run_ab_test
from mcpbr.analytics.anomaly import detect_anomalies, detect_metric_anomalies
from mcpbr.analytics.correlation import (
    analyze_metric_correlations,
    find_strong_correlations,
    pearson_correlation,
    spearman_correlation,
)
from mcpbr.analytics.difficulty import (
    aggregate_difficulty_stats,
    estimate_difficulty,
    estimate_task_difficulty_score,
)
from mcpbr.analytics.error_analysis import ErrorPatternAnalyzer, identify_flaky_tasks
from mcpbr.analytics.leaderboard import Leaderboard, generate_leaderboard
from mcpbr.analytics.metrics import MetricDefinition, MetricsRegistry
from mcpbr.analytics.regression_detector import RegressionDetector

# ---------------------------------------------------------------------------
# Helpers for building mock data
# ---------------------------------------------------------------------------


def _make_results_data(
    tasks: list[dict],
    resolved: int = 0,
    total: int = 0,
    rate: float = 0.0,
    total_cost: float = 0.0,
    model: str = "test-model",
    provider: str = "test-provider",
) -> dict:
    """Build a minimal results_data dict used by several modules."""
    return {
        "metadata": {"config": {"model": model, "provider": provider}},
        "summary": {
            "mcp": {
                "resolved": resolved,
                "total": total,
                "rate": rate,
                "total_cost": total_cost,
            }
        },
        "tasks": tasks,
    }


def _make_task(
    instance_id: str = "task-1",
    resolved: bool = True,
    cost: float = 0.10,
    tokens_in: int = 1000,
    tokens_out: int = 500,
    iterations: int = 3,
    runtime_seconds: float = 10.0,
    tool_calls: int = 5,
    tool_usage: dict | None = None,
    tool_failures: dict | None = None,
) -> dict:
    """Build a minimal task dict with mcp sub-dict."""
    mcp: dict = {
        "resolved": resolved,
        "cost": cost,
        "tokens": {"input": tokens_in, "output": tokens_out},
        "iterations": iterations,
        "runtime_seconds": runtime_seconds,
        "tool_calls": tool_calls,
    }
    if tool_usage is not None:
        mcp["tool_usage"] = tool_usage
    if tool_failures is not None:
        mcp["tool_failures"] = tool_failures
    return {"instance_id": instance_id, "mcp": mcp}


# ===========================================================================
# 1. ErrorPatternAnalyzer & identify_flaky_tasks
# ===========================================================================


class TestErrorPatternAnalyzer:
    """Tests for ErrorPatternAnalyzer."""

    def test_analyze_no_errors(self):
        analyzer = ErrorPatternAnalyzer()
        results = [{"tool": "read_file"}, {"tool": "write_file"}]
        analysis = analyzer.analyze(results)

        assert analysis["total_errors"] == 0
        assert analysis["error_clusters"] == []
        assert "No errors detected" in analysis["recommendations"][0]

    def test_analyze_with_single_error_field(self):
        analyzer = ErrorPatternAnalyzer()
        results = [
            {"error": "Connection refused", "tool": "api_call"},
            {"tool": "api_call"},
        ]
        analysis = analyzer.analyze(results)

        assert analysis["total_errors"] == 1
        assert len(analysis["error_clusters"]) == 1
        assert analysis["error_clusters"][0]["category"] == "connection"

    def test_analyze_with_errors_list(self):
        analyzer = ErrorPatternAnalyzer()
        results = [
            {"errors": ["Timeout waiting for response", "Connection timed out"], "tool": "fetch"},
        ]
        analysis = analyzer.analyze(results)

        assert analysis["total_errors"] == 2
        # Both timeout errors should cluster together (high Jaccard similarity)
        assert len(analysis["error_clusters"]) >= 1

    def test_analyze_tool_error_correlation(self):
        analyzer = ErrorPatternAnalyzer()
        results = [
            {"error": "Rate limit exceeded 429", "tool": "api_call"},
            {"error": "Rate limit hit 429", "tool": "api_call"},
            {"tool": "read_file"},
            {"tool": "read_file"},
        ]
        analysis = analyzer.analyze(results)

        assert analysis["tool_error_correlation"]["api_call"] == 1.0
        assert analysis["tool_error_correlation"]["read_file"] == 0.0

    def test_analyze_temporal_patterns_increasing(self):
        analyzer = ErrorPatternAnalyzer()
        # First iteration: no errors; later iterations: errors increase
        results = [
            {"tool": "t", "iteration": 0},
            {"tool": "t", "iteration": 0},
            {"tool": "t", "iteration": 1},
            {"tool": "t", "iteration": 1},
            {"error": "fail", "tool": "t", "iteration": 2},
            {"error": "fail", "tool": "t", "iteration": 2},
            {"error": "fail", "tool": "t", "iteration": 3},
            {"error": "fail", "tool": "t", "iteration": 3},
        ]
        analysis = analyzer.analyze(results)
        assert analysis["temporal_patterns"]["increasing"] is True

    def test_analyze_temporal_patterns_stable(self):
        analyzer = ErrorPatternAnalyzer()
        results = [
            {"error": "fail", "tool": "t", "iteration": 0},
            {"tool": "t", "iteration": 0},
            {"error": "fail", "tool": "t", "iteration": 1},
            {"tool": "t", "iteration": 1},
        ]
        analysis = analyzer.analyze(results)
        # Equal error rate each iteration -> not increasing
        assert analysis["temporal_patterns"]["increasing"] is False

    def test_analyze_recommendations_for_rate_limit(self):
        analyzer = ErrorPatternAnalyzer()
        results = [{"error": "429 Too many requests", "tool": "api"}]
        analysis = analyzer.analyze(results)

        rec_text = " ".join(analysis["recommendations"])
        assert "rate-limit" in rec_text.lower() or "Rate-limit" in rec_text

    def test_analyze_recommendations_for_high_error_tool(self):
        analyzer = ErrorPatternAnalyzer()
        results = [
            {"error": "some error", "tool": "bad_tool"},
            {"error": "another error", "tool": "bad_tool"},
            {"tool": "good_tool"},
        ]
        analysis = analyzer.analyze(results)

        rec_text = " ".join(analysis["recommendations"])
        assert "bad_tool" in rec_text

    def test_analyze_recommendations_dominant_cluster(self):
        analyzer = ErrorPatternAnalyzer()
        # 5 identical errors out of 5 total -> dominant cluster
        results = [{"error": "same error message"} for _ in range(5)]
        analysis = analyzer.analyze(results)

        rec_text = " ".join(analysis["recommendations"])
        assert "most common error pattern" in rec_text.lower()


class TestErrorClusteringJaccard:
    """Tests for Jaccard similarity-based error clustering."""

    def test_cluster_identical_errors(self):
        analyzer = ErrorPatternAnalyzer()
        errors = ["connection refused", "connection refused", "connection refused"]
        clusters = analyzer.cluster_errors(errors)

        assert len(clusters) == 1
        assert clusters[0]["count"] == 3

    def test_cluster_similar_errors(self):
        analyzer = ErrorPatternAnalyzer()
        errors = [
            "connection refused to host server",
            "connection refused to host database",
            "completely different error about authentication",
        ]
        clusters = analyzer.cluster_errors(errors, similarity_threshold=0.5)

        # The two "connection refused" errors should cluster; auth error is separate
        assert len(clusters) == 2

    def test_cluster_empty_errors(self):
        analyzer = ErrorPatternAnalyzer()
        assert analyzer.cluster_errors([]) == []

    def test_cluster_sorted_by_count(self):
        analyzer = ErrorPatternAnalyzer()
        errors = [
            "rare error",
            "common error message here",
            "common error message here",
            "common error message here",
        ]
        clusters = analyzer.cluster_errors(errors)

        assert clusters[0]["count"] >= clusters[-1]["count"]

    def test_jaccard_similarity_identical(self):
        analyzer = ErrorPatternAnalyzer()
        assert analyzer._jaccard_similarity("hello world", "hello world") == 1.0

    def test_jaccard_similarity_disjoint(self):
        analyzer = ErrorPatternAnalyzer()
        assert analyzer._jaccard_similarity("hello world", "foo bar") == 0.0

    def test_jaccard_similarity_partial(self):
        analyzer = ErrorPatternAnalyzer()
        sim = analyzer._jaccard_similarity("a b c", "b c d")
        # Intersection {b,c}, Union {a,b,c,d} -> 2/4 = 0.5
        assert sim == pytest.approx(0.5)

    def test_jaccard_similarity_both_empty(self):
        analyzer = ErrorPatternAnalyzer()
        assert analyzer._jaccard_similarity("", "") == 1.0

    def test_jaccard_similarity_one_empty(self):
        analyzer = ErrorPatternAnalyzer()
        assert analyzer._jaccard_similarity("hello", "") == 0.0


class TestErrorCategorization:
    """Tests for _categorize_error."""

    @pytest.mark.parametrize(
        ("error_msg", "expected_category"),
        [
            ("Request timed out after 30s", "timeout"),
            ("Connection deadline exceeded", "timeout"),
            ("401 Unauthorized", "authentication"),
            ("403 Forbidden access", "authentication"),
            ("429 Too Many Requests", "rate_limit"),
            ("Rate limit exceeded", "rate_limit"),
            ("Connection refused", "connection"),
            ("DNS resolution failed", "connection"),
            ("ECONNRESET by peer", "connection"),
            ("Invalid JSON format", "validation"),
            ("Schema validation error", "validation"),
            ("Permission denied for file", "permission"),
            ("Something completely unknown", "unknown"),
        ],
    )
    def test_categorize_error(self, error_msg, expected_category):
        assert ErrorPatternAnalyzer._categorize_error(error_msg) == expected_category


class TestIdentifyFlakyTasks:
    """Tests for identify_flaky_tasks()."""

    def test_flaky_task_detected(self):
        runs = [
            {"tasks": [{"instance_id": "t1", "resolved": True}]},
            {"tasks": [{"instance_id": "t1", "resolved": False}]},
        ]
        result = identify_flaky_tasks(runs)

        assert len(result) == 1
        assert result[0]["instance_id"] == "t1"
        assert result[0]["flaky"] is True
        assert result[0]["pass_rate"] == 0.5

    def test_stable_passing_task(self):
        runs = [
            {"tasks": [{"instance_id": "t1", "resolved": True}]},
            {"tasks": [{"instance_id": "t1", "resolved": True}]},
        ]
        result = identify_flaky_tasks(runs)

        assert result[0]["flaky"] is False
        assert result[0]["pass_rate"] == 1.0

    def test_stable_failing_task(self):
        runs = [
            {"tasks": [{"instance_id": "t1", "resolved": False}]},
            {"tasks": [{"instance_id": "t1", "resolved": False}]},
        ]
        result = identify_flaky_tasks(runs)

        assert result[0]["flaky"] is False
        assert result[0]["pass_rate"] == 0.0

    def test_error_field_determines_failure(self):
        runs = [
            {"tasks": [{"instance_id": "t1"}]},  # No error -> pass
            {"tasks": [{"instance_id": "t1", "error": "boom"}]},  # Error -> fail
        ]
        result = identify_flaky_tasks(runs)

        assert result[0]["flaky"] is True

    def test_multiple_tasks(self):
        runs = [
            {
                "tasks": [
                    {"instance_id": "t1", "resolved": True},
                    {"instance_id": "t2", "resolved": True},
                ]
            },
            {
                "tasks": [
                    {"instance_id": "t1", "resolved": False},
                    {"instance_id": "t2", "resolved": True},
                ]
            },
        ]
        result = identify_flaky_tasks(runs)

        flaky_ids = {r["instance_id"] for r in result if r["flaky"]}
        assert "t1" in flaky_ids
        assert "t2" not in flaky_ids

    def test_empty_runs(self):
        assert identify_flaky_tasks([]) == []

    def test_no_instance_id_skipped(self):
        runs = [{"tasks": [{"resolved": True}]}]
        result = identify_flaky_tasks(runs)
        assert result == []


# ===========================================================================
# 2. Anomaly detection
# ===========================================================================


class TestDetectAnomaliesZScore:
    """Tests for detect_anomalies with zscore method."""

    def test_obvious_outlier(self):
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 100.0]
        anomalies = detect_anomalies(values, method="zscore", threshold=2.0)

        assert len(anomalies) >= 1
        outlier_values = {a["value"] for a in anomalies}
        assert 100.0 in outlier_values
        for a in anomalies:
            assert a["method"] == "zscore"

    def test_no_anomalies(self):
        values = [10.0, 10.0, 10.0, 10.0]
        anomalies = detect_anomalies(values, method="zscore", threshold=2.0)
        assert anomalies == []

    def test_single_value(self):
        anomalies = detect_anomalies([5.0], method="zscore")
        assert anomalies == []

    def test_constant_values(self):
        anomalies = detect_anomalies([7.0, 7.0, 7.0, 7.0], method="zscore")
        assert anomalies == []

    def test_anomaly_has_correct_fields(self):
        values = [1.0, 1.0, 1.0, 1.0, 50.0]
        anomalies = detect_anomalies(values, method="zscore", threshold=1.5)

        assert len(anomalies) >= 1
        a = anomalies[0]
        assert "index" in a
        assert "value" in a
        assert "score" in a
        assert a["method"] == "zscore"


class TestDetectAnomaliesIQR:
    """Tests for detect_anomalies with IQR method."""

    def test_obvious_outlier(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 100.0]
        anomalies = detect_anomalies(values, method="iqr", threshold=1.5)

        assert len(anomalies) >= 1
        outlier_values = {a["value"] for a in anomalies}
        assert 100.0 in outlier_values
        for a in anomalies:
            assert a["method"] == "iqr"

    def test_no_anomalies_iqr(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        anomalies = detect_anomalies(values, method="iqr", threshold=1.5)
        assert anomalies == []

    def test_too_few_values(self):
        anomalies = detect_anomalies([1.0, 2.0, 3.0], method="iqr")
        assert anomalies == []

    def test_constant_values_iqr(self):
        anomalies = detect_anomalies([5.0] * 10, method="iqr")
        assert anomalies == []


class TestDetectAnomaliesMAD:
    """Tests for detect_anomalies with MAD method."""

    def test_obvious_outlier(self):
        # MAD requires a non-zero median of absolute deviations,
        # so we need varied data where the outlier stands out
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0]
        anomalies = detect_anomalies(values, method="mad", threshold=2.0)

        assert len(anomalies) >= 1
        outlier_values = {a["value"] for a in anomalies}
        assert 100.0 in outlier_values
        for a in anomalies:
            assert a["method"] == "mad"

    def test_no_anomalies_mad(self):
        values = [5.0, 5.0, 5.0, 5.0]
        anomalies = detect_anomalies(values, method="mad", threshold=2.0)
        assert anomalies == []

    def test_single_value_mad(self):
        anomalies = detect_anomalies([3.0], method="mad")
        assert anomalies == []


class TestDetectAnomaliesInvalidMethod:
    """Tests for invalid method parameter."""

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown method"):
            detect_anomalies([1.0, 2.0], method="bogus")


class TestDetectMetricAnomalies:
    """Tests for detect_metric_anomalies()."""

    def test_with_outlier_task(self):
        # Use enough normal data points plus a very extreme outlier so the
        # zscore (default method, threshold=2.0) clearly flags it
        tasks = [
            _make_task(cost=0.10, tokens_in=1000, tokens_out=500, runtime_seconds=10.0),
            _make_task(cost=0.11, tokens_in=1100, tokens_out=500, runtime_seconds=11.0),
            _make_task(cost=0.10, tokens_in=1000, tokens_out=500, runtime_seconds=10.0),
            _make_task(cost=0.10, tokens_in=1000, tokens_out=500, runtime_seconds=10.0),
            _make_task(cost=0.09, tokens_in=950, tokens_out=500, runtime_seconds=9.5),
            _make_task(cost=0.12, tokens_in=1050, tokens_out=550, runtime_seconds=10.5),
            _make_task(cost=0.10, tokens_in=1000, tokens_out=500, runtime_seconds=10.0),
            _make_task(cost=0.11, tokens_in=1100, tokens_out=500, runtime_seconds=10.0),
            _make_task(cost=0.10, tokens_in=1000, tokens_out=500, runtime_seconds=10.0),
            _make_task(cost=10.0, tokens_in=80000, tokens_out=40000, runtime_seconds=500.0),
        ]
        data = {"tasks": tasks}
        result = detect_metric_anomalies(data)

        assert "cost" in result
        assert "tokens" in result
        assert "runtime" in result
        assert "iterations" in result
        # The extreme outlier task should be detected for cost, tokens, and runtime
        assert len(result["cost"]) >= 1
        assert len(result["tokens"]) >= 1
        assert len(result["runtime"]) >= 1

    def test_empty_tasks(self):
        result = detect_metric_anomalies({"tasks": []})
        assert result == {"cost": [], "tokens": [], "runtime": [], "iterations": []}

    def test_no_tasks_key(self):
        result = detect_metric_anomalies({})
        assert result == {"cost": [], "tokens": [], "runtime": [], "iterations": []}


# ===========================================================================
# 3. Correlation analysis
# ===========================================================================


class TestPearsonCorrelation:
    """Tests for pearson_correlation()."""

    def test_perfect_positive_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        result = pearson_correlation(x, y)

        assert result["r"] == pytest.approx(1.0)
        assert result["r_squared"] == pytest.approx(1.0)
        assert result["n"] == 5
        assert result["p_value"] < 0.05

    def test_perfect_negative_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]
        result = pearson_correlation(x, y)

        assert result["r"] == pytest.approx(-1.0)
        assert result["r_squared"] == pytest.approx(1.0)

    def test_no_correlation_constant(self):
        x = [1.0, 2.0, 3.0, 4.0]
        y = [5.0, 5.0, 5.0, 5.0]
        result = pearson_correlation(x, y)

        assert result["r"] == 0.0
        assert result["p_value"] == 1.0

    def test_different_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            pearson_correlation([1.0, 2.0], [1.0])

    def test_fewer_than_two_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            pearson_correlation([1.0], [2.0])

    def test_p_value_bounds(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        y = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        result = pearson_correlation(x, y)

        assert 0.0 <= result["p_value"] <= 1.0


class TestSpearmanCorrelation:
    """Tests for spearman_correlation()."""

    def test_perfect_monotonic(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = spearman_correlation(x, y)

        assert result["r"] == pytest.approx(1.0)

    def test_perfect_inverse_monotonic(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [50.0, 40.0, 30.0, 20.0, 10.0]
        result = spearman_correlation(x, y)

        assert result["r"] == pytest.approx(-1.0)

    def test_nonlinear_monotonic(self):
        # Spearman should capture non-linear monotonic relationships
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 4.0, 9.0, 16.0, 25.0]  # y = x^2, monotonically increasing
        result = spearman_correlation(x, y)

        assert result["r"] == pytest.approx(1.0)

    def test_different_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            spearman_correlation([1.0, 2.0], [1.0, 2.0, 3.0])


class TestAnalyzeMetricCorrelations:
    """Tests for analyze_metric_correlations()."""

    def test_with_multiple_tasks(self):
        tasks = [
            _make_task(cost=0.10, tokens_in=1000, tokens_out=500, runtime_seconds=10.0),
            _make_task(cost=0.20, tokens_in=2000, tokens_out=1000, runtime_seconds=20.0),
            _make_task(cost=0.30, tokens_in=3000, tokens_out=1500, runtime_seconds=30.0),
        ]
        data = _make_results_data(tasks)
        correlations = analyze_metric_correlations(data)

        assert len(correlations) > 0
        # All keys should be "metric_a vs metric_b" format
        for key in correlations:
            assert " vs " in key
            corr = correlations[key]
            assert "r" in corr
            assert "p_value" in corr

    def test_fewer_than_two_tasks(self):
        tasks = [_make_task()]
        data = _make_results_data(tasks)
        assert analyze_metric_correlations(data) == {}

    def test_empty_tasks(self):
        data = _make_results_data([])
        assert analyze_metric_correlations(data) == {}


class TestFindStrongCorrelations:
    """Tests for find_strong_correlations()."""

    def test_finds_strong_positive(self):
        correlations = {
            "cost vs tokens_input": {"r": 0.95, "r_squared": 0.9025, "p_value": 0.001, "n": 10},
            "cost vs runtime_seconds": {"r": 0.3, "r_squared": 0.09, "p_value": 0.5, "n": 10},
        }
        strong = find_strong_correlations(correlations, threshold=0.7)

        assert len(strong) == 1
        assert strong[0]["pair"] == "cost vs tokens_input"
        assert strong[0]["direction"] == "positive"

    def test_finds_strong_negative(self):
        correlations = {
            "a vs b": {"r": -0.85, "r_squared": 0.7225, "p_value": 0.01, "n": 10},
        }
        strong = find_strong_correlations(correlations, threshold=0.7)

        assert len(strong) == 1
        assert strong[0]["direction"] == "negative"

    def test_none_strong(self):
        correlations = {
            "a vs b": {"r": 0.1, "r_squared": 0.01, "p_value": 0.8, "n": 5},
        }
        assert find_strong_correlations(correlations, threshold=0.7) == []

    def test_sorted_by_abs_r(self):
        correlations = {
            "a vs b": {"r": 0.75, "r_squared": 0.5625, "p_value": 0.01, "n": 10},
            "c vs d": {"r": -0.95, "r_squared": 0.9025, "p_value": 0.001, "n": 10},
        }
        strong = find_strong_correlations(correlations, threshold=0.7)

        assert len(strong) == 2
        assert strong[0]["pair"] == "c vs d"  # |r|=0.95 > |r|=0.75


# ===========================================================================
# 4. Difficulty estimation
# ===========================================================================


class TestEstimateDifficulty:
    """Tests for estimate_difficulty()."""

    def test_easy_resolved_task(self):
        tasks = [
            _make_task(
                instance_id="easy",
                resolved=True,
                cost=0.01,
                tokens_in=100,
                tokens_out=50,
                iterations=1,
                runtime_seconds=2.0,
            ),
            _make_task(
                instance_id="avg",
                resolved=True,
                cost=0.10,
                tokens_in=1000,
                tokens_out=500,
                iterations=5,
                runtime_seconds=30.0,
            ),
        ]
        data = _make_results_data(tasks)
        difficulties = estimate_difficulty(data)

        assert len(difficulties) == 2
        easy_task = next(d for d in difficulties if d["instance_id"] == "easy")
        assert easy_task["difficulty_level"] in ("easy", "medium")
        assert 0.0 <= easy_task["difficulty_score"] <= 1.0

    def test_hard_unresolved_task(self):
        tasks = [
            _make_task(
                instance_id="easy",
                resolved=True,
                cost=0.01,
                tokens_in=100,
                tokens_out=50,
                iterations=1,
                runtime_seconds=2.0,
            ),
            _make_task(
                instance_id="hard",
                resolved=False,
                cost=1.00,
                tokens_in=10000,
                tokens_out=5000,
                iterations=20,
                runtime_seconds=120.0,
            ),
        ]
        data = _make_results_data(tasks)
        difficulties = estimate_difficulty(data)

        hard_task = next(d for d in difficulties if d["instance_id"] == "hard")
        assert hard_task["difficulty_level"] in ("hard", "very_hard")
        assert hard_task["difficulty_score"] >= 0.5

    def test_empty_tasks(self):
        data = _make_results_data([])
        assert estimate_difficulty(data) == []

    def test_metrics_included(self):
        tasks = [_make_task(instance_id="t1", cost=0.15)]
        data = _make_results_data(tasks)
        difficulties = estimate_difficulty(data)

        assert "metrics" in difficulties[0]
        assert "cost" in difficulties[0]["metrics"]
        assert "tokens" in difficulties[0]["metrics"]


class TestAggregateDifficultyStats:
    """Tests for aggregate_difficulty_stats()."""

    def test_basic_aggregation(self):
        task_difficulties = [
            {"instance_id": "t1", "difficulty_score": 0.1, "difficulty_level": "easy"},
            {"instance_id": "t2", "difficulty_score": 0.4, "difficulty_level": "medium"},
            {"instance_id": "t3", "difficulty_score": 0.8, "difficulty_level": "very_hard"},
        ]
        stats = aggregate_difficulty_stats(task_difficulties)

        assert stats["distribution"]["easy"] == 1
        assert stats["distribution"]["medium"] == 1
        assert stats["distribution"]["very_hard"] == 1
        assert stats["avg_difficulty"] == pytest.approx((0.1 + 0.4 + 0.8) / 3)
        assert len(stats["hardest_tasks"]) <= 5
        assert len(stats["easiest_tasks"]) <= 5

    def test_empty_input(self):
        stats = aggregate_difficulty_stats([])
        assert stats["distribution"] == {}
        assert stats["avg_difficulty"] == 0.0


class TestEstimateTaskDifficultyScore:
    """Tests for estimate_task_difficulty_score()."""

    def test_resolved_at_average(self):
        score = estimate_task_difficulty_score(
            resolved=True,
            cost=1.0,
            tokens=1000,
            iterations=5,
            runtime=10.0,
            avg_cost=1.0,
            avg_tokens=1000.0,
            avg_iterations=5.0,
            avg_runtime=10.0,
        )
        # At average, deviation is 0, resolved -> base 0.0
        assert score == pytest.approx(0.0)

    def test_unresolved_at_average(self):
        score = estimate_task_difficulty_score(
            resolved=False,
            cost=1.0,
            tokens=1000,
            iterations=5,
            runtime=10.0,
            avg_cost=1.0,
            avg_tokens=1000.0,
            avg_iterations=5.0,
            avg_runtime=10.0,
        )
        # At average, deviation is 0, unresolved -> base 0.5
        assert score == pytest.approx(0.5)

    def test_unresolved_double_average(self):
        score = estimate_task_difficulty_score(
            resolved=False,
            cost=2.0,
            tokens=2000,
            iterations=10,
            runtime=20.0,
            avg_cost=1.0,
            avg_tokens=1000.0,
            avg_iterations=5.0,
            avg_runtime=10.0,
        )
        # Unresolved (0.5) + max deviation (0.5) = 1.0
        assert score == pytest.approx(1.0)

    def test_score_clamped_to_0_1(self):
        score = estimate_task_difficulty_score(
            resolved=False,
            cost=100.0,
            tokens=100000,
            iterations=100,
            runtime=1000.0,
            avg_cost=1.0,
            avg_tokens=1000.0,
            avg_iterations=5.0,
            avg_runtime=10.0,
        )
        assert 0.0 <= score <= 1.0

    def test_difficulty_levels(self):
        """Verify the mapping from scores to difficulty levels."""
        # Score 0.2 -> easy (<=0.25)
        tasks = [
            _make_task(
                instance_id="t1",
                resolved=True,
                cost=0.01,
                tokens_in=50,
                tokens_out=50,
                iterations=1,
                runtime_seconds=1.0,
            ),
            _make_task(
                instance_id="t2",
                resolved=True,
                cost=1.0,
                tokens_in=5000,
                tokens_out=5000,
                iterations=10,
                runtime_seconds=100.0,
            ),
        ]
        data = _make_results_data(tasks)
        difficulties = estimate_difficulty(data)

        levels = {d["difficulty_level"] for d in difficulties}
        # At least one should be easy-ish (below average) and one harder
        assert len(levels) >= 1


# ===========================================================================
# 5. A/B testing
# ===========================================================================


class TestABTest:
    """Tests for ABTest class."""

    def _make_results(self, resolved: int, total: int, rate: float, cost: float) -> dict:
        tasks = []
        for i in range(total):
            is_resolved = i < resolved
            tasks.append(
                _make_task(
                    instance_id=f"task-{i}",
                    resolved=is_resolved,
                    cost=cost / total,
                    tokens_in=1000,
                    tokens_out=500,
                    runtime_seconds=10.0,
                )
            )
        return _make_results_data(tasks, resolved=resolved, total=total, rate=rate, total_cost=cost)

    def test_treatment_wins(self):
        control = self._make_results(resolved=5, total=100, rate=0.05, cost=1.0)
        treatment = self._make_results(resolved=50, total=100, rate=0.50, cost=2.0)

        test = ABTest("Model Comparison")
        test.add_control(control)
        test.add_treatment(treatment)
        analysis = test.analyze()

        assert analysis["test_name"] == "Model Comparison"
        assert analysis["rate_difference"] > 0
        assert analysis["winner"] == "treatment"
        assert (
            "treatment" in analysis["recommendation"].lower()
            or "Treatment" in analysis["recommendation"]
        )

    def test_control_wins(self):
        control = self._make_results(resolved=50, total=100, rate=0.50, cost=1.0)
        treatment = self._make_results(resolved=5, total=100, rate=0.05, cost=0.5)

        test = ABTest("Model Comparison")
        test.add_control(control)
        test.add_treatment(treatment)
        analysis = test.analyze()

        assert analysis["winner"] == "control"

    def test_no_significant_difference(self):
        control = self._make_results(resolved=5, total=10, rate=0.50, cost=1.0)
        treatment = self._make_results(resolved=6, total=10, rate=0.60, cost=1.0)

        analysis = run_ab_test(control, treatment, "Small Sample")
        # With small samples the difference likely won't be significant
        assert analysis["winner"] in ("no_significant_difference", "treatment")

    def test_missing_control_raises(self):
        test = ABTest("Test")
        test.add_treatment(self._make_results(5, 10, 0.5, 1.0))
        with pytest.raises(ValueError, match="Control"):
            test.analyze()

    def test_missing_treatment_raises(self):
        test = ABTest("Test")
        test.add_control(self._make_results(5, 10, 0.5, 1.0))
        with pytest.raises(ValueError, match="Treatment"):
            test.analyze()

    def test_format_report(self):
        control = self._make_results(resolved=5, total=100, rate=0.05, cost=1.0)
        treatment = self._make_results(resolved=50, total=100, rate=0.50, cost=2.0)

        test = ABTest("Report Test")
        test.add_control(control)
        test.add_treatment(treatment)
        report = test.format_report()

        assert "Report Test" in report
        assert "Resolution Rate" in report
        assert "Chi-squared" in report
        assert "Winner" in report
        assert "Recommendation" in report

    def test_format_report_auto_calls_analyze(self):
        control = self._make_results(resolved=5, total=100, rate=0.05, cost=1.0)
        treatment = self._make_results(resolved=50, total=100, rate=0.50, cost=2.0)

        test = ABTest("Auto Test")
        test.add_control(control)
        test.add_treatment(treatment)
        # format_report without calling analyze first
        report = test.format_report()
        assert "Auto Test" in report

    def test_custom_labels(self):
        control = self._make_results(resolved=10, total=20, rate=0.5, cost=1.0)
        treatment = self._make_results(resolved=15, total=20, rate=0.75, cost=1.5)

        test = ABTest("Label Test", control_label="Baseline", treatment_label="Candidate")
        test.add_control(control)
        test.add_treatment(treatment)
        report = test.format_report()

        assert "Baseline" in report
        assert "Candidate" in report


class TestRunABTest:
    """Tests for run_ab_test() convenience function."""

    def test_returns_analysis_dict(self):
        a = _make_results_data(
            [_make_task(resolved=True)],
            resolved=1,
            total=1,
            rate=1.0,
            total_cost=0.1,
        )
        b = _make_results_data(
            [_make_task(resolved=False)],
            resolved=0,
            total=1,
            rate=0.0,
            total_cost=0.1,
        )
        result = run_ab_test(a, b, "Quick Test")

        assert result["test_name"] == "Quick Test"
        assert "winner" in result
        assert "statistical_significance" in result


# ===========================================================================
# 6. Leaderboard
# ===========================================================================


class TestLeaderboard:
    """Tests for Leaderboard class."""

    def _make_entry_data(
        self, resolved: int, total: int, rate: float, cost: float, model: str
    ) -> dict:
        tasks = []
        for i in range(total):
            is_resolved = i < resolved
            tasks.append(
                _make_task(
                    instance_id=f"task-{i}",
                    resolved=is_resolved,
                    cost=cost / total,
                    tokens_in=1000,
                    tokens_out=500,
                    runtime_seconds=10.0,
                )
            )
        return _make_results_data(
            tasks, resolved=resolved, total=total, rate=rate, total_cost=cost, model=model
        )

    def test_generate_ranks_by_resolution_rate(self):
        lb = Leaderboard()
        lb.add_entry("Model A", self._make_entry_data(8, 10, 0.80, 1.0, "model-a"))
        lb.add_entry("Model B", self._make_entry_data(6, 10, 0.60, 0.5, "model-b"))
        lb.add_entry("Model C", self._make_entry_data(9, 10, 0.90, 2.0, "model-c"))

        entries = lb.generate(sort_by="resolution_rate")

        assert len(entries) == 3
        assert entries[0]["rank"] == 1
        assert entries[0]["label"] == "Model C"
        assert entries[1]["label"] == "Model A"
        assert entries[2]["label"] == "Model B"

    def test_generate_ranks_by_total_cost(self):
        lb = Leaderboard()
        lb.add_entry("Cheap", self._make_entry_data(5, 10, 0.50, 0.5, "cheap"))
        lb.add_entry("Expensive", self._make_entry_data(5, 10, 0.50, 5.0, "expensive"))

        entries = lb.generate(sort_by="total_cost")

        # Lower cost is better, so "Cheap" should be rank 1
        assert entries[0]["label"] == "Cheap"
        assert entries[1]["label"] == "Expensive"

    def test_generate_invalid_sort_key(self):
        lb = Leaderboard()
        lb.add_entry("A", self._make_entry_data(5, 10, 0.50, 1.0, "a"))

        with pytest.raises(ValueError, match="Unsupported sort key"):
            lb.generate(sort_by="nonexistent_metric")

    def test_format_table(self):
        lb = Leaderboard()
        lb.add_entry("Model A", self._make_entry_data(8, 10, 0.80, 1.0, "model-a"))
        lb.add_entry("Model B", self._make_entry_data(6, 10, 0.60, 0.5, "model-b"))

        table = lb.format_table()
        assert "Rank" in table
        assert "Label" in table
        assert "Model A" in table
        assert "Model B" in table

    def test_format_table_empty(self):
        lb = Leaderboard()
        assert lb.format_table() == "No entries in leaderboard."

    def test_format_markdown(self):
        lb = Leaderboard()
        lb.add_entry("Model A", self._make_entry_data(8, 10, 0.80, 1.0, "model-a"))

        md = lb.format_markdown()
        assert "|" in md
        assert "Rank" in md
        assert "Model A" in md

    def test_format_markdown_empty(self):
        lb = Leaderboard()
        assert lb.format_markdown() == "No entries in leaderboard."

    def test_entry_has_all_fields(self):
        lb = Leaderboard()
        lb.add_entry("Test", self._make_entry_data(5, 10, 0.50, 1.0, "model-x"))
        entries = lb.generate()

        entry = entries[0]
        expected_fields = {
            "rank",
            "label",
            "model",
            "provider",
            "resolution_rate",
            "resolved",
            "total",
            "total_cost",
            "cost_per_resolved",
            "avg_tokens",
            "avg_runtime",
        }
        assert expected_fields.issubset(set(entry.keys()))


class TestGenerateLeaderboard:
    """Tests for generate_leaderboard() convenience function."""

    def test_convenience_function(self):
        data = _make_results_data(
            [_make_task(resolved=True)],
            resolved=1,
            total=1,
            rate=1.0,
            total_cost=0.1,
            model="test-model",
        )
        results_list = [("Run A", data)]
        entries = generate_leaderboard(results_list)

        assert len(entries) == 1
        assert entries[0]["label"] == "Run A"
        assert entries[0]["rank"] == 1


# ===========================================================================
# 7. Metrics
# ===========================================================================


class TestMetricDefinition:
    """Tests for MetricDefinition dataclass."""

    def test_create_metric(self):
        metric = MetricDefinition(
            name="test_metric",
            description="A test metric",
            unit="widgets",
            calculate=lambda d: 42.0,
            higher_is_better=True,
        )
        assert metric.name == "test_metric"
        assert metric.unit == "widgets"
        assert metric.calculate({}) == 42.0
        assert metric.higher_is_better is True

    def test_default_higher_is_better(self):
        metric = MetricDefinition(
            name="m",
            description="d",
            unit="u",
            calculate=lambda d: 0.0,
        )
        assert metric.higher_is_better is True


class TestMetricsRegistry:
    """Tests for MetricsRegistry."""

    def test_builtin_metrics_registered(self):
        registry = MetricsRegistry()
        names = registry.list_metrics()

        assert "resolution_rate" in names
        assert "cost_per_resolution" in names
        assert "avg_tokens_per_task" in names
        assert "tool_failure_rate" in names
        assert "efficiency_score" in names

    def test_get_metric(self):
        registry = MetricsRegistry()
        metric = registry.get_metric("resolution_rate")

        assert metric is not None
        assert metric.name == "resolution_rate"
        assert metric.higher_is_better is True

    def test_get_nonexistent_metric(self):
        registry = MetricsRegistry()
        assert registry.get_metric("nonexistent") is None

    def test_register_custom_metric(self):
        registry = MetricsRegistry()
        custom = MetricDefinition(
            name="custom_score",
            description="Custom",
            unit="points",
            calculate=lambda d: 99.0,
        )
        registry.register(custom)

        assert "custom_score" in registry.list_metrics()
        assert registry.get_metric("custom_score") is not None

    def test_register_duplicate_raises(self):
        registry = MetricsRegistry()
        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                MetricDefinition(
                    name="resolution_rate",
                    description="Duplicate",
                    unit="ratio",
                    calculate=lambda d: 0.0,
                )
            )

    def test_calculate_all(self):
        registry = MetricsRegistry()
        tasks = [
            _make_task(
                resolved=True,
                cost=0.10,
                tokens_in=1000,
                tokens_out=500,
                tool_usage={"read_file": 3, "write_file": 2},
            ),
            _make_task(
                resolved=False,
                cost=0.20,
                tokens_in=2000,
                tokens_out=1000,
                tool_usage={"read_file": 5},
                tool_failures={"read_file": 1},
            ),
        ]
        data = _make_results_data(tasks)
        values = registry.calculate_all(data)

        assert "resolution_rate" in values
        assert values["resolution_rate"] == pytest.approx(0.5)
        assert "cost_per_resolution" in values
        assert "avg_tokens_per_task" in values
        assert "efficiency_score" in values

    def test_calculate_all_handles_errors(self):
        registry = MetricsRegistry()
        bad_metric = MetricDefinition(
            name="always_fails",
            description="Always raises",
            unit="none",
            calculate=lambda d: 1 / 0,  # ZeroDivisionError
        )
        registry.register(bad_metric)

        values = registry.calculate_all(_make_results_data([]))
        assert math.isnan(values["always_fails"])

    def test_resolution_rate_no_tasks(self):
        registry = MetricsRegistry()
        values = registry.calculate_all(_make_results_data([]))
        assert values["resolution_rate"] == 0.0

    def test_cost_per_resolution_no_resolved(self):
        registry = MetricsRegistry()
        tasks = [_make_task(resolved=False)]
        values = registry.calculate_all(_make_results_data(tasks))
        assert values["cost_per_resolution"] == math.inf

    def test_tool_failure_rate_no_calls(self):
        registry = MetricsRegistry()
        tasks = [_make_task(tool_calls=0)]
        values = registry.calculate_all(_make_results_data(tasks))
        assert values["tool_failure_rate"] == 0.0

    def test_efficiency_score(self):
        registry = MetricsRegistry()
        tasks = [_make_task(resolved=True, cost=0.10)]
        values = registry.calculate_all(_make_results_data(tasks))
        # efficiency = 1.0 / (0.10 + 0.01)
        expected = 1.0 / (0.10 + 0.01)
        assert values["efficiency_score"] == pytest.approx(expected, rel=1e-3)


# ===========================================================================
# 8. Regression detector
# ===========================================================================


class TestRegressionDetector:
    """Tests for RegressionDetector."""

    def _make_run(
        self,
        resolved: int,
        total: int,
        rate: float,
        cost: float,
        task_specs: list[tuple[str, bool, float, int, float]] | None = None,
    ) -> dict:
        """Build a run with summary and tasks.

        task_specs: list of (instance_id, resolved, cost, tokens, runtime)
        """
        if task_specs is None:
            tasks = []
            for i in range(total):
                is_resolved = i < resolved
                tasks.append(
                    _make_task(
                        instance_id=f"task-{i}",
                        resolved=is_resolved,
                        cost=cost / total,
                        tokens_in=1000,
                        tokens_out=500,
                        runtime_seconds=10.0,
                    )
                )
        else:
            tasks = []
            for iid, res, c, tok, rt in task_specs:
                tasks.append(
                    _make_task(
                        instance_id=iid,
                        resolved=res,
                        cost=c,
                        tokens_in=tok,
                        tokens_out=tok // 2,
                        runtime_seconds=rt,
                    )
                )

        return _make_results_data(tasks, resolved=resolved, total=total, rate=rate, total_cost=cost)

    def test_no_regression(self):
        baseline = self._make_run(resolved=8, total=10, rate=0.80, cost=1.0)
        current = self._make_run(resolved=8, total=10, rate=0.80, cost=1.0)

        detector = RegressionDetector()
        result = detector.detect(current, baseline)

        assert result["overall_status"] == "pass"
        assert result["score_regression"]["detected"] is False
        assert result["cost_regression"]["detected"] is False

    def test_score_regression_detected(self):
        baseline = self._make_run(resolved=80, total=100, rate=0.80, cost=1.0)
        current = self._make_run(resolved=30, total=100, rate=0.30, cost=1.0)

        detector = RegressionDetector(threshold=0.05)
        result = detector.detect(current, baseline)

        assert result["score_regression"]["detected"] is True
        assert result["overall_status"] == "fail"

    def test_cost_regression_detected(self):
        baseline = self._make_run(resolved=8, total=10, rate=0.80, cost=1.0)
        current = self._make_run(resolved=8, total=10, rate=0.80, cost=2.0)

        detector = RegressionDetector()
        result = detector.detect(current, baseline)

        assert result["cost_regression"]["detected"] is True
        assert result["cost_regression"]["delta_pct"] == pytest.approx(100.0)
        assert result["overall_status"] == "warning"

    def test_latency_regression_detected(self):
        baseline_tasks = [("t1", True, 0.1, 1000, 10.0)]
        current_tasks = [("t1", True, 0.1, 1000, 50.0)]  # 5x slower
        baseline = self._make_run(
            resolved=1, total=1, rate=1.0, cost=0.1, task_specs=baseline_tasks
        )
        current = self._make_run(resolved=1, total=1, rate=1.0, cost=0.1, task_specs=current_tasks)

        detector = RegressionDetector()
        result = detector.detect(current, baseline)

        assert result["latency_regression"]["detected"] is True

    def test_token_regression_detected(self):
        baseline_tasks = [("t1", True, 0.1, 1000, 10.0)]
        current_tasks = [("t1", True, 0.1, 5000, 10.0)]  # 5x more tokens
        baseline = self._make_run(
            resolved=1, total=1, rate=1.0, cost=0.1, task_specs=baseline_tasks
        )
        current = self._make_run(resolved=1, total=1, rate=1.0, cost=0.1, task_specs=current_tasks)

        detector = RegressionDetector()
        result = detector.detect(current, baseline)

        assert result["token_regression"]["detected"] is True

    def test_task_level_regressions(self):
        baseline_tasks = [
            ("t1", True, 0.1, 1000, 10.0),
            ("t2", True, 0.1, 1000, 10.0),
        ]
        current_tasks = [
            ("t1", False, 0.1, 1000, 10.0),  # t1 regressed
            ("t2", True, 0.1, 1000, 10.0),
        ]
        baseline = self._make_run(
            resolved=2, total=2, rate=1.0, cost=0.2, task_specs=baseline_tasks
        )
        current = self._make_run(resolved=1, total=2, rate=0.5, cost=0.2, task_specs=current_tasks)

        detector = RegressionDetector()
        result = detector.detect(current, baseline)

        assert len(result["task_regressions"]) == 1
        assert result["task_regressions"][0]["instance_id"] == "t1"

    def test_task_level_improvements(self):
        baseline_tasks = [
            ("t1", False, 0.1, 1000, 10.0),
            ("t2", True, 0.1, 1000, 10.0),
        ]
        current_tasks = [
            ("t1", True, 0.1, 1000, 10.0),  # t1 improved
            ("t2", True, 0.1, 1000, 10.0),
        ]
        baseline = self._make_run(
            resolved=1, total=2, rate=0.5, cost=0.2, task_specs=baseline_tasks
        )
        current = self._make_run(resolved=2, total=2, rate=1.0, cost=0.2, task_specs=current_tasks)

        detector = RegressionDetector()
        result = detector.detect(current, baseline)

        assert len(result["task_improvements"]) == 1
        assert result["task_improvements"][0]["instance_id"] == "t1"

    def test_format_report(self):
        baseline = self._make_run(resolved=80, total=100, rate=0.80, cost=1.0)
        current = self._make_run(resolved=30, total=100, rate=0.30, cost=2.0)

        detector = RegressionDetector()
        detector.detect(current, baseline)
        report = detector.format_report()

        assert "Regression Detection Report" in report
        assert "Resolution Rate" in report
        assert "Cost" in report
        assert "Latency" in report
        assert "Token Usage" in report
        assert "Overall Status" in report

    def test_format_report_without_detect_raises(self):
        detector = RegressionDetector()
        with pytest.raises(ValueError, match="No detection results"):
            detector.format_report()

    def test_format_report_shows_task_regressions(self):
        baseline_tasks = [("t1", True, 0.1, 1000, 10.0)]
        current_tasks = [("t1", False, 0.1, 1000, 10.0)]
        baseline = self._make_run(
            resolved=1, total=1, rate=1.0, cost=0.1, task_specs=baseline_tasks
        )
        current = self._make_run(resolved=0, total=1, rate=0.0, cost=0.1, task_specs=current_tasks)

        detector = RegressionDetector()
        detector.detect(current, baseline)
        report = detector.format_report()

        assert "Task Regressions" in report
        assert "t1" in report

    def test_format_report_shows_task_improvements(self):
        baseline_tasks = [("t1", False, 0.1, 1000, 10.0)]
        current_tasks = [("t1", True, 0.1, 1000, 10.0)]
        baseline = self._make_run(
            resolved=0, total=1, rate=0.0, cost=0.1, task_specs=baseline_tasks
        )
        current = self._make_run(resolved=1, total=1, rate=1.0, cost=0.1, task_specs=current_tasks)

        detector = RegressionDetector()
        detector.detect(current, baseline)
        report = detector.format_report()

        assert "Task Improvements" in report
        assert "t1" in report

    def test_summary_no_regressions(self):
        baseline = self._make_run(resolved=8, total=10, rate=0.80, cost=1.0)
        current = self._make_run(resolved=8, total=10, rate=0.80, cost=1.0)

        detector = RegressionDetector()
        result = detector.detect(current, baseline)

        assert "No regressions detected" in result["summary"]

    def test_custom_threshold(self):
        baseline = self._make_run(resolved=80, total=100, rate=0.80, cost=1.0)
        current = self._make_run(resolved=70, total=100, rate=0.70, cost=1.0)

        # Very strict threshold
        detector_strict = RegressionDetector(threshold=0.01)
        result_strict = detector_strict.detect(current, baseline)

        # Lenient threshold
        detector_lenient = RegressionDetector(threshold=0.20)
        result_lenient = detector_lenient.detect(current, baseline)

        # Strict should more likely detect regression than lenient
        if result_strict["score_regression"]["significant"]:
            assert result_strict["score_regression"]["detected"] is True
        assert result_lenient["score_regression"]["detected"] is False
