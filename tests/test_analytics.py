"""Comprehensive tests for mcpbr analytics modules.

Covers database.py, trends.py, statistical.py, and comparison.py from
the mcpbr.analytics package.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mcpbr.analytics.comparison import (
    ComparisonEngine,
    compare_results_files,
    format_comparison_table,
)
from mcpbr.analytics.database import ResultsDatabase
from mcpbr.analytics.statistical import (
    bootstrap_confidence_interval,
    chi_squared_test,
    compare_resolution_rates,
    effect_size_cohens_d,
    mann_whitney_u,
    permutation_test,
)
from mcpbr.analytics.trends import (
    calculate_moving_average,
    calculate_trends,
    detect_trend_direction,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_results_data(
    *,
    benchmark: str = "swe-bench-verified",
    model: str = "claude-sonnet",
    provider: str = "anthropic",
    agent_harness: str = "default",
    sample_size: int = 5,
    timeout_seconds: int = 300,
    max_iterations: int = 10,
    rate: float = 0.6,
    total_cost: float = 1.25,
    total: int = 5,
    resolved: int = 3,
    timestamp: str | None = None,
    tasks: list | None = None,
) -> dict:
    """Build a minimal results data dict suitable for store_run / ComparisonEngine."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    if tasks is None:
        tasks = []
        for i in range(total):
            is_resolved = i < resolved
            tasks.append(
                {
                    "instance_id": f"task-{i}",
                    "mcp": {
                        "resolved": is_resolved,
                        "cost": total_cost / total,
                        "tokens": {"input": 500, "output": 200},
                        "iterations": 3,
                        "tool_calls": 5,
                        "runtime_seconds": 30.0,
                    },
                }
            )

    return {
        "metadata": {
            "timestamp": timestamp,
            "config": {
                "benchmark": benchmark,
                "model": model,
                "provider": provider,
                "agent_harness": agent_harness,
                "sample_size": sample_size,
                "timeout_seconds": timeout_seconds,
                "max_iterations": max_iterations,
            },
        },
        "summary": {
            "mcp": {
                "rate": rate,
                "total_cost": total_cost,
                "total": total,
                "resolved": resolved,
            },
        },
        "tasks": tasks,
    }


# ===================================================================
# database.py Tests
# ===================================================================


class TestResultsDatabase:
    """Tests for ResultsDatabase with SQLite backend."""

    def test_create_database(self, tmp_path: Path) -> None:
        """Database file is created on initialisation."""
        db_path = tmp_path / "test.db"
        db = ResultsDatabase(db_path)
        assert db_path.exists()
        db.close()

    def test_create_database_nested_directory(self, tmp_path: Path) -> None:
        """Parent directories are created automatically."""
        db_path = tmp_path / "a" / "b" / "c" / "test.db"
        db = ResultsDatabase(db_path)
        assert db_path.exists()
        db.close()

    def test_context_manager(self, tmp_path: Path) -> None:
        """Database works as a context manager and closes cleanly."""
        db_path = tmp_path / "ctx.db"
        with ResultsDatabase(db_path) as db:
            run_id = db.store_run(_make_results_data())
            assert run_id >= 1

    def test_store_and_get_run(self, tmp_path: Path) -> None:
        """store_run persists data that get_run can retrieve."""
        with ResultsDatabase(tmp_path / "sg.db") as db:
            data = _make_results_data(model="claude-opus", rate=0.8, resolved=4, total=5)
            run_id = db.store_run(data)

            run = db.get_run(run_id)
            assert run is not None
            assert run["model"] == "claude-opus"
            assert run["resolution_rate"] == pytest.approx(0.8)
            assert run["resolved_tasks"] == 4
            assert run["total_tasks"] == 5

    def test_get_run_returns_none_for_missing(self, tmp_path: Path) -> None:
        """get_run returns None when the run ID does not exist."""
        with ResultsDatabase(tmp_path / "miss.db") as db:
            assert db.get_run(9999) is None

    def test_store_run_returns_incrementing_ids(self, tmp_path: Path) -> None:
        """Successive store_run calls return incrementing run IDs."""
        with ResultsDatabase(tmp_path / "inc.db") as db:
            id1 = db.store_run(_make_results_data())
            id2 = db.store_run(_make_results_data())
            assert id2 > id1

    def test_metadata_json_deserialized(self, tmp_path: Path) -> None:
        """metadata_json column is deserialized back to a dict on retrieval."""
        with ResultsDatabase(tmp_path / "meta.db") as db:
            data = _make_results_data()
            run_id = db.store_run(data)
            run = db.get_run(run_id)
            assert isinstance(run["metadata_json"], dict)
            assert run["metadata_json"]["config"]["model"] == "claude-sonnet"

    def test_list_runs_default(self, tmp_path: Path) -> None:
        """list_runs returns all stored runs ordered by timestamp descending."""
        with ResultsDatabase(tmp_path / "list.db") as db:
            ts1 = "2024-01-01T00:00:00+00:00"
            ts2 = "2024-06-01T00:00:00+00:00"
            db.store_run(_make_results_data(timestamp=ts1))
            db.store_run(_make_results_data(timestamp=ts2))

            runs = db.list_runs()
            assert len(runs) == 2
            # Most recent first
            assert runs[0]["timestamp"] == ts2
            assert runs[1]["timestamp"] == ts1

    def test_list_runs_with_limit(self, tmp_path: Path) -> None:
        """list_runs honours the limit parameter."""
        with ResultsDatabase(tmp_path / "limit.db") as db:
            for i in range(10):
                db.store_run(_make_results_data(timestamp=f"2024-{i + 1:02d}-01T00:00:00+00:00"))

            runs = db.list_runs(limit=3)
            assert len(runs) == 3

    def test_list_runs_filter_benchmark(self, tmp_path: Path) -> None:
        """list_runs filters by benchmark name."""
        with ResultsDatabase(tmp_path / "fbench.db") as db:
            db.store_run(_make_results_data(benchmark="swe-bench-verified"))
            db.store_run(_make_results_data(benchmark="polyglot"))
            db.store_run(_make_results_data(benchmark="swe-bench-verified"))

            runs = db.list_runs(benchmark="swe-bench-verified")
            assert len(runs) == 2
            assert all(r["benchmark"] == "swe-bench-verified" for r in runs)

    def test_list_runs_filter_model(self, tmp_path: Path) -> None:
        """list_runs filters by model."""
        with ResultsDatabase(tmp_path / "fmodel.db") as db:
            db.store_run(_make_results_data(model="gpt-4o"))
            db.store_run(_make_results_data(model="claude-sonnet"))

            runs = db.list_runs(model="gpt-4o")
            assert len(runs) == 1
            assert runs[0]["model"] == "gpt-4o"

    def test_list_runs_filter_provider(self, tmp_path: Path) -> None:
        """list_runs filters by provider."""
        with ResultsDatabase(tmp_path / "fprov.db") as db:
            db.store_run(_make_results_data(provider="anthropic"))
            db.store_run(_make_results_data(provider="openai"))

            runs = db.list_runs(provider="anthropic")
            assert len(runs) == 1
            assert runs[0]["provider"] == "anthropic"

    def test_list_runs_combined_filters(self, tmp_path: Path) -> None:
        """list_runs supports combined benchmark + model + provider filters."""
        with ResultsDatabase(tmp_path / "combo.db") as db:
            db.store_run(
                _make_results_data(
                    benchmark="swe-bench-verified", model="claude-sonnet", provider="anthropic"
                )
            )
            db.store_run(
                _make_results_data(
                    benchmark="swe-bench-verified", model="gpt-4o", provider="openai"
                )
            )
            db.store_run(
                _make_results_data(
                    benchmark="polyglot", model="claude-sonnet", provider="anthropic"
                )
            )

            runs = db.list_runs(
                benchmark="swe-bench-verified", model="claude-sonnet", provider="anthropic"
            )
            assert len(runs) == 1

    def test_get_task_results(self, tmp_path: Path) -> None:
        """get_task_results returns task-level rows for a given run."""
        with ResultsDatabase(tmp_path / "tasks.db") as db:
            data = _make_results_data(total=3, resolved=2)
            run_id = db.store_run(data)

            task_results = db.get_task_results(run_id)
            assert len(task_results) == 3

            # First two resolved, third not
            assert task_results[0]["resolved"] == 1
            assert task_results[1]["resolved"] == 1
            assert task_results[2]["resolved"] == 0

    def test_get_task_results_empty_for_missing_run(self, tmp_path: Path) -> None:
        """get_task_results returns empty list for non-existent run ID."""
        with ResultsDatabase(tmp_path / "noid.db") as db:
            assert db.get_task_results(9999) == []

    def test_get_task_results_preserves_fields(self, tmp_path: Path) -> None:
        """Task result rows include cost, tokens, iterations, and other fields."""
        with ResultsDatabase(tmp_path / "fields.db") as db:
            data = _make_results_data(total=1, resolved=1, total_cost=0.50)
            run_id = db.store_run(data)

            tasks = db.get_task_results(run_id)
            assert len(tasks) == 1
            t = tasks[0]
            assert t["tokens_input"] == 500
            assert t["tokens_output"] == 200
            assert t["iterations"] == 3
            assert t["tool_calls"] == 5
            assert t["runtime_seconds"] == pytest.approx(30.0)

    def test_delete_run(self, tmp_path: Path) -> None:
        """delete_run removes the run and returns True."""
        with ResultsDatabase(tmp_path / "del.db") as db:
            run_id = db.store_run(_make_results_data())
            assert db.delete_run(run_id) is True
            assert db.get_run(run_id) is None

    def test_delete_run_cascades_to_tasks(self, tmp_path: Path) -> None:
        """Deleting a run also removes its task results."""
        with ResultsDatabase(tmp_path / "cascade.db") as db:
            run_id = db.store_run(_make_results_data(total=3, resolved=2))
            assert len(db.get_task_results(run_id)) == 3

            db.delete_run(run_id)
            assert db.get_task_results(run_id) == []

    def test_delete_run_returns_false_for_missing(self, tmp_path: Path) -> None:
        """delete_run returns False when the run does not exist."""
        with ResultsDatabase(tmp_path / "delmiss.db") as db:
            assert db.delete_run(9999) is False

    def test_get_trends_returns_ordered_data(self, tmp_path: Path) -> None:
        """get_trends returns rows ordered by timestamp ascending."""
        with ResultsDatabase(tmp_path / "trends.db") as db:
            db.store_run(_make_results_data(timestamp="2024-03-01T00:00:00+00:00", rate=0.5))
            db.store_run(_make_results_data(timestamp="2024-01-01T00:00:00+00:00", rate=0.3))
            db.store_run(_make_results_data(timestamp="2024-02-01T00:00:00+00:00", rate=0.4))

            trends = db.get_trends()
            assert len(trends) == 3
            # Ascending order
            assert trends[0]["resolution_rate"] == pytest.approx(0.3)
            assert trends[1]["resolution_rate"] == pytest.approx(0.4)
            assert trends[2]["resolution_rate"] == pytest.approx(0.5)

    def test_get_trends_filter_by_benchmark(self, tmp_path: Path) -> None:
        """get_trends filters by benchmark."""
        with ResultsDatabase(tmp_path / "tbench.db") as db:
            db.store_run(_make_results_data(benchmark="swe-bench-verified", rate=0.5))
            db.store_run(_make_results_data(benchmark="polyglot", rate=0.3))

            trends = db.get_trends(benchmark="swe-bench-verified")
            assert len(trends) == 1
            assert trends[0]["resolution_rate"] == pytest.approx(0.5)

    def test_get_trends_filter_by_model(self, tmp_path: Path) -> None:
        """get_trends filters by model."""
        with ResultsDatabase(tmp_path / "tmodel.db") as db:
            db.store_run(_make_results_data(model="claude-sonnet", rate=0.6))
            db.store_run(_make_results_data(model="gpt-4o", rate=0.7))

            trends = db.get_trends(model="gpt-4o")
            assert len(trends) == 1
            assert trends[0]["resolution_rate"] == pytest.approx(0.7)

    def test_get_trends_includes_total_tokens(self, tmp_path: Path) -> None:
        """get_trends aggregates total_tokens from task_results."""
        with ResultsDatabase(tmp_path / "ttokens.db") as db:
            data = _make_results_data(total=2, resolved=1)
            db.store_run(data)

            trends = db.get_trends()
            assert len(trends) == 1
            # Each task has 500 input + 200 output = 700, two tasks = 1400
            assert trends[0]["total_tokens"] == 1400

    def test_get_trends_limit(self, tmp_path: Path) -> None:
        """get_trends honours the limit parameter."""
        with ResultsDatabase(tmp_path / "tlimit.db") as db:
            for i in range(10):
                db.store_run(_make_results_data(timestamp=f"2024-{i + 1:02d}-01T00:00:00+00:00"))

            trends = db.get_trends(limit=5)
            assert len(trends) == 5

    def test_cleanup_removes_old_runs(self, tmp_path: Path) -> None:
        """cleanup deletes runs older than max_age_days."""
        with ResultsDatabase(tmp_path / "clean.db") as db:
            old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
            recent_ts = datetime.now(timezone.utc).isoformat()

            db.store_run(_make_results_data(timestamp=old_ts))
            db.store_run(_make_results_data(timestamp=recent_ts))

            deleted = db.cleanup(max_age_days=90)
            assert deleted == 1

            runs = db.list_runs()
            assert len(runs) == 1

    def test_cleanup_returns_zero_when_nothing_to_delete(self, tmp_path: Path) -> None:
        """cleanup returns 0 when all runs are within the age limit."""
        with ResultsDatabase(tmp_path / "nodl.db") as db:
            db.store_run(_make_results_data())
            deleted = db.cleanup(max_age_days=1)
            assert deleted == 0

    def test_store_run_with_empty_tasks(self, tmp_path: Path) -> None:
        """store_run handles results with no tasks."""
        with ResultsDatabase(tmp_path / "notasks.db") as db:
            data = _make_results_data(total=0, resolved=0, tasks=[])
            run_id = db.store_run(data)
            assert db.get_task_results(run_id) == []

    def test_store_run_with_missing_metadata(self, tmp_path: Path) -> None:
        """store_run handles results with minimal / missing metadata gracefully."""
        with ResultsDatabase(tmp_path / "sparse.db") as db:
            run_id = db.store_run({"summary": {"mcp": {"rate": 0.5}}})
            run = db.get_run(run_id)
            assert run is not None
            assert run["benchmark"] is None
            assert run["model"] is None


# ===================================================================
# trends.py Tests
# ===================================================================


class TestDetectTrendDirection:
    """Tests for detect_trend_direction()."""

    def test_improving_trend(self) -> None:
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        assert detect_trend_direction(values) == "improving"

    def test_declining_trend(self) -> None:
        values = [0.9, 0.7, 0.5, 0.3, 0.1]
        assert detect_trend_direction(values) == "declining"

    def test_stable_trend(self) -> None:
        values = [0.5, 0.5, 0.5, 0.5, 0.5]
        assert detect_trend_direction(values) == "stable"

    def test_single_value(self) -> None:
        assert detect_trend_direction([0.5]) == "stable"

    def test_empty_values(self) -> None:
        assert detect_trend_direction([]) == "stable"

    def test_two_values_improving(self) -> None:
        assert detect_trend_direction([0.0, 1.0]) == "improving"

    def test_two_values_declining(self) -> None:
        assert detect_trend_direction([1.0, 0.0]) == "declining"

    def test_custom_threshold(self) -> None:
        """A small slope below a large threshold is classified as stable."""
        values = [0.5, 0.51, 0.52]
        assert detect_trend_direction(values, threshold=0.1) == "stable"

    def test_noisy_but_improving(self) -> None:
        """General upward trend despite noise."""
        values = [0.1, 0.3, 0.2, 0.4, 0.3, 0.5, 0.6]
        assert detect_trend_direction(values) == "improving"


class TestCalculateMovingAverage:
    """Tests for calculate_moving_average()."""

    def test_basic_window_3(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_moving_average(values, window=3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_window_1(self) -> None:
        """Window of 1 returns the values themselves."""
        values = [10.0, 20.0, 30.0]
        result = calculate_moving_average(values, window=1)
        assert result == [pytest.approx(10.0), pytest.approx(20.0), pytest.approx(30.0)]

    def test_window_equals_length(self) -> None:
        """When window equals list length, only last element has a value."""
        values = [1.0, 2.0, 3.0]
        result = calculate_moving_average(values, window=3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == pytest.approx(2.0)

    def test_window_exceeds_length(self) -> None:
        """When window is larger than the list, all entries are None."""
        values = [1.0, 2.0]
        result = calculate_moving_average(values, window=5)
        assert all(v is None for v in result)

    def test_empty_values(self) -> None:
        result = calculate_moving_average([], window=3)
        assert result == []

    def test_invalid_window_raises(self) -> None:
        with pytest.raises(ValueError, match="window must be at least 1"):
            calculate_moving_average([1.0], window=0)

    def test_preserves_length(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        result = calculate_moving_average(values, window=4)
        assert len(result) == len(values)


class TestCalculateTrends:
    """Tests for calculate_trends()."""

    def test_structure_of_output(self) -> None:
        runs = [
            {
                "timestamp": "2024-01-01",
                "resolution_rate": 0.4,
                "total_cost": 1.0,
                "total_tokens": 1000,
            },
            {
                "timestamp": "2024-02-01",
                "resolution_rate": 0.5,
                "total_cost": 1.5,
                "total_tokens": 1200,
            },
            {
                "timestamp": "2024-03-01",
                "resolution_rate": 0.6,
                "total_cost": 2.0,
                "total_tokens": 1400,
            },
        ]
        result = calculate_trends(runs)

        assert "resolution_rate_trend" in result
        assert "cost_trend" in result
        assert "token_trend" in result
        assert "direction" in result
        assert "moving_averages" in result

        assert len(result["resolution_rate_trend"]) == 3
        assert result["direction"] == "improving"

    def test_declining_resolution_rate(self) -> None:
        runs = [
            {
                "timestamp": f"2024-0{i + 1}-01",
                "resolution_rate": 0.9 - 0.2 * i,
                "total_cost": 1.0,
                "total_tokens": 1000,
            }
            for i in range(5)
        ]
        result = calculate_trends(runs)
        assert result["direction"] == "declining"

    def test_empty_runs(self) -> None:
        result = calculate_trends([])
        assert result["resolution_rate_trend"] == []
        assert result["direction"] == "stable"
        assert result["moving_averages"]["resolution_rate"] == []

    def test_single_run(self) -> None:
        runs = [
            {
                "timestamp": "2024-01-01",
                "resolution_rate": 0.5,
                "total_cost": 1.0,
                "total_tokens": 1000,
            }
        ]
        result = calculate_trends(runs)
        assert result["direction"] == "stable"
        assert len(result["resolution_rate_trend"]) == 1

    def test_none_values_treated_as_zero(self) -> None:
        """None values for rate, cost, and tokens default to zero."""
        runs = [
            {
                "timestamp": "2024-01-01",
                "resolution_rate": None,
                "total_cost": None,
                "total_tokens": None,
            }
        ]
        result = calculate_trends(runs)
        assert result["resolution_rate_trend"][0]["rate"] == 0.0
        assert result["cost_trend"][0]["cost"] == 0.0
        assert result["token_trend"][0]["tokens"] == 0

    def test_moving_averages_have_correct_length(self) -> None:
        runs = [
            {
                "timestamp": f"2024-0{i + 1}-01",
                "resolution_rate": 0.5,
                "total_cost": 1.0,
                "total_tokens": 1000,
            }
            for i in range(5)
        ]
        result = calculate_trends(runs)
        for key in ("resolution_rate", "cost", "tokens"):
            assert len(result["moving_averages"][key]) == 5


# ===================================================================
# statistical.py Tests
# ===================================================================


class TestChiSquaredTest:
    """Tests for chi_squared_test()."""

    def test_significant_difference(self) -> None:
        """Large difference in rates should be significant."""
        result = chi_squared_test(success_a=80, total_a=100, success_b=20, total_b=100)
        assert result["significant"] is True
        assert result["p_value"] < 0.05
        assert result["chi2"] > 0

    def test_no_significant_difference(self) -> None:
        """Very similar rates should not be significant."""
        result = chi_squared_test(success_a=50, total_a=100, success_b=52, total_b=100)
        assert result["significant"] is False

    def test_identical_rates(self) -> None:
        """Identical rates yield chi2 of 0 and p-value of 1."""
        result = chi_squared_test(success_a=50, total_a=100, success_b=50, total_b=100)
        assert result["chi2"] == pytest.approx(0.0)
        assert result["p_value"] == pytest.approx(1.0)
        assert result["significant"] is False

    def test_effect_size_is_phi_coefficient(self) -> None:
        """Effect size should be the phi coefficient (sqrt(chi2/N))."""
        result = chi_squared_test(success_a=70, total_a=100, success_b=30, total_b=100)
        expected_phi = math.sqrt(result["chi2"] / 200)
        assert result["effect_size"] == pytest.approx(expected_phi)

    def test_zero_total_raises(self) -> None:
        with pytest.raises(ValueError, match="Totals must be positive"):
            chi_squared_test(success_a=0, total_a=0, success_b=5, total_b=10)

    def test_negative_success_raises(self) -> None:
        with pytest.raises(ValueError, match="Successes must be non-negative"):
            chi_squared_test(success_a=-1, total_a=10, success_b=5, total_b=10)

    def test_success_exceeds_total_raises(self) -> None:
        with pytest.raises(ValueError, match="Successes cannot exceed totals"):
            chi_squared_test(success_a=15, total_a=10, success_b=5, total_b=10)

    def test_custom_significance_level(self) -> None:
        """A very strict significance level changes the conclusion."""
        result = chi_squared_test(
            success_a=60, total_a=100, success_b=45, total_b=100, significance_level=0.001
        )
        # With moderate difference, p may be above 0.001
        assert isinstance(result["significant"], bool)

    def test_all_success(self) -> None:
        """Edge case: both groups have 100% success rate."""
        result = chi_squared_test(success_a=100, total_a=100, success_b=100, total_b=100)
        assert result["chi2"] == pytest.approx(0.0)


class TestBootstrapConfidenceInterval:
    """Tests for bootstrap_confidence_interval()."""

    def test_basic_confidence_interval(self) -> None:
        random.seed(42)
        values = [0.80, 0.85, 0.90, 0.78, 0.92, 0.88, 0.84, 0.91]
        result = bootstrap_confidence_interval(values, n_bootstrap=2000)

        assert "mean" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "std_error" in result
        assert result["ci_lower"] <= result["mean"] <= result["ci_upper"]

    def test_narrow_interval_with_low_variance(self) -> None:
        """Identical values should produce a very tight CI."""
        random.seed(42)
        values = [0.5] * 20
        result = bootstrap_confidence_interval(values, n_bootstrap=500)
        assert result["ci_lower"] == pytest.approx(0.5)
        assert result["ci_upper"] == pytest.approx(0.5)

    def test_empty_values_raises(self) -> None:
        with pytest.raises(ValueError, match="Values list must not be empty"):
            bootstrap_confidence_interval([])

    def test_invalid_confidence_raises(self) -> None:
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            bootstrap_confidence_interval([1.0, 2.0], confidence=0.0)

        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            bootstrap_confidence_interval([1.0, 2.0], confidence=1.0)

    def test_single_value(self) -> None:
        """A single value still returns a valid (degenerate) interval."""
        random.seed(42)
        result = bootstrap_confidence_interval([0.75])
        assert result["mean"] == pytest.approx(0.75)
        assert result["ci_lower"] == pytest.approx(0.75)
        assert result["ci_upper"] == pytest.approx(0.75)

    def test_90_percent_confidence(self) -> None:
        """A narrower confidence level should give a tighter interval."""
        random.seed(42)
        values = [0.5, 0.6, 0.7, 0.8, 0.9, 0.55, 0.65, 0.75, 0.85, 0.95]
        ci_95 = bootstrap_confidence_interval(values, confidence=0.95, n_bootstrap=5000)

        random.seed(42)
        ci_90 = bootstrap_confidence_interval(values, confidence=0.90, n_bootstrap=5000)

        width_95 = ci_95["ci_upper"] - ci_95["ci_lower"]
        width_90 = ci_90["ci_upper"] - ci_90["ci_lower"]
        assert width_90 <= width_95 + 0.01  # Allow small tolerance for randomness


class TestEffectSizeCohensD:
    """Tests for effect_size_cohens_d()."""

    def test_positive_effect(self) -> None:
        """group_a > group_b should give positive Cohen's d."""
        group_a = [10.0, 11.0, 12.0, 13.0, 14.0]
        group_b = [1.0, 2.0, 3.0, 4.0, 5.0]
        d = effect_size_cohens_d(group_a, group_b)
        assert d > 0

    def test_negative_effect(self) -> None:
        """group_a < group_b should give negative Cohen's d."""
        group_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        group_b = [10.0, 11.0, 12.0, 13.0, 14.0]
        d = effect_size_cohens_d(group_a, group_b)
        assert d < 0

    def test_identical_groups(self) -> None:
        """Identical groups should give d = 0."""
        group = [5.0, 5.0, 5.0, 5.0, 5.0]
        d = effect_size_cohens_d(group, group)
        assert d == pytest.approx(0.0)

    def test_large_effect_size(self) -> None:
        """Well-separated groups should have |d| >= 0.8 (large effect)."""
        group_a = [100.0, 101.0, 102.0, 103.0, 104.0]
        group_b = [1.0, 2.0, 3.0, 4.0, 5.0]
        d = effect_size_cohens_d(group_a, group_b)
        assert abs(d) >= 0.8

    def test_too_few_observations_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 2 observations"):
            effect_size_cohens_d([1.0], [2.0, 3.0])

        with pytest.raises(ValueError, match="at least 2 observations"):
            effect_size_cohens_d([1.0, 2.0], [3.0])


class TestMannWhitneyU:
    """Tests for mann_whitney_u()."""

    def test_significantly_different_groups(self) -> None:
        """Well-separated groups should be significant."""
        group_a = [
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
            16.0,
            17.0,
            18.0,
            19.0,
            20.0,
            21.0,
            22.0,
            23.0,
            24.0,
            25.0,
            26.0,
            27.0,
            28.0,
            29.0,
        ]
        group_b = [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
            9.0,
            0.0,
            0.5,
            1.5,
            2.5,
            3.5,
            4.5,
            5.5,
            6.5,
            7.5,
            8.5,
            9.5,
        ]
        result = mann_whitney_u(group_a, group_b)
        assert result["significant"] is True
        assert result["p_value"] < 0.05

    def test_identical_groups_not_significant(self) -> None:
        """Identical groups should not be significant."""
        group = [5.0, 5.0, 5.0, 5.0, 5.0]
        result = mann_whitney_u(group, group)
        assert result["significant"] is False

    def test_empty_group_raises(self) -> None:
        with pytest.raises(ValueError, match="Both groups must be non-empty"):
            mann_whitney_u([], [1.0, 2.0])

        with pytest.raises(ValueError, match="Both groups must be non-empty"):
            mann_whitney_u([1.0, 2.0], [])

    def test_result_keys(self) -> None:
        result = mann_whitney_u([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
        assert "u_statistic" in result
        assert "p_value" in result
        assert "significant" in result

    def test_u_statistic_range(self) -> None:
        """U statistic should be between 0 and n_a * n_b."""
        group_a = [1.0, 2.0, 3.0, 4.0]
        group_b = [5.0, 6.0, 7.0]
        result = mann_whitney_u(group_a, group_b)
        assert 0 <= result["u_statistic"] <= len(group_a) * len(group_b)


class TestPermutationTest:
    """Tests for permutation_test()."""

    def test_significantly_different_groups(self) -> None:
        """Well-separated groups should yield a small p-value."""
        random.seed(42)
        group_a = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
        group_b = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 0.0]
        result = permutation_test(group_a, group_b, n_permutations=5000)
        assert result["significant"] is True
        assert result["observed_diff"] > 0

    def test_identical_groups_not_significant(self) -> None:
        """Identical groups should not be significant."""
        random.seed(42)
        group = [5.0, 5.0, 5.0, 5.0, 5.0]
        result = permutation_test(group, list(group), n_permutations=500)
        # p_value should be 1.0 since all permutations produce diff >= 0
        assert result["significant"] is False

    def test_empty_group_raises(self) -> None:
        with pytest.raises(ValueError, match="Both groups must be non-empty"):
            permutation_test([], [1.0])

        with pytest.raises(ValueError, match="Both groups must be non-empty"):
            permutation_test([1.0], [])

    def test_observed_diff_sign(self) -> None:
        """observed_diff should be mean_a - mean_b."""
        random.seed(42)
        group_a = [1.0, 2.0, 3.0]
        group_b = [10.0, 20.0, 30.0]
        result = permutation_test(group_a, group_b, n_permutations=100)
        assert result["observed_diff"] < 0

    def test_result_keys(self) -> None:
        random.seed(42)
        result = permutation_test([1.0, 2.0], [3.0, 4.0], n_permutations=100)
        assert "observed_diff" in result
        assert "p_value" in result
        assert "significant" in result


class TestCompareResolutionRates:
    """Tests for compare_resolution_rates()."""

    def test_basic_comparison(self) -> None:
        results_a = {"resolved": 80, "total": 100, "name": "Model A"}
        results_b = {"resolved": 40, "total": 100, "name": "Model B"}
        result = compare_resolution_rates(results_a, results_b)

        assert result["rate_a"] == pytest.approx(0.8)
        assert result["rate_b"] == pytest.approx(0.4)
        assert "chi2_test" in result
        assert "effect_size" in result
        assert "summary" in result
        assert "Model A" in result["summary"]
        assert "Model B" in result["summary"]

    def test_with_scores(self) -> None:
        """When scores are provided, scores_comparison is included."""
        results_a = {
            "resolved": 5,
            "total": 10,
            "scores": [0.9, 0.8, 0.7, 0.85, 0.95],
        }
        results_b = {
            "resolved": 3,
            "total": 10,
            "scores": [0.3, 0.4, 0.35, 0.45, 0.5],
        }
        result = compare_resolution_rates(results_a, results_b)
        assert "scores_comparison" in result
        assert "cohens_d" in result["scores_comparison"]
        assert "mann_whitney" in result["scores_comparison"]

    def test_without_scores(self) -> None:
        """Without scores, scores_comparison is not present."""
        results_a = {"resolved": 5, "total": 10}
        results_b = {"resolved": 3, "total": 10}
        result = compare_resolution_rates(results_a, results_b)
        assert "scores_comparison" not in result

    def test_label_fallback(self) -> None:
        """Falls back to 'label' key then to 'A'/'B' defaults."""
        results_a = {"resolved": 5, "total": 10, "label": "Config1"}
        results_b = {"resolved": 3, "total": 10}
        result = compare_resolution_rates(results_a, results_b)
        assert "Config1" in result["summary"]
        assert "B" in result["summary"]

    def test_missing_required_key_raises(self) -> None:
        with pytest.raises(KeyError):
            compare_resolution_rates({"resolved": 5}, {"resolved": 3, "total": 10})

    def test_summary_mentions_significance(self) -> None:
        results_a = {"resolved": 90, "total": 100}
        results_b = {"resolved": 10, "total": 100}
        result = compare_resolution_rates(results_a, results_b)
        assert "significant" in result["summary"]


# ===================================================================
# comparison.py Tests
# ===================================================================


class TestComparisonEngine:
    """Tests for ComparisonEngine."""

    def _make_engine_with_two_models(self) -> ComparisonEngine:
        """Helper to build an engine with two distinct result sets."""
        engine = ComparisonEngine()
        engine.add_results(
            "model-a",
            _make_results_data(
                model="claude-sonnet",
                provider="anthropic",
                rate=0.6,
                total_cost=2.0,
                total=5,
                resolved=3,
            ),
        )
        engine.add_results(
            "model-b",
            _make_results_data(
                model="gpt-4o",
                provider="openai",
                rate=0.8,
                total_cost=3.0,
                total=5,
                resolved=4,
            ),
        )
        return engine

    def test_compare_requires_at_least_two(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("only-one", _make_results_data())
        with pytest.raises(ValueError, match="At least 2 result sets required"):
            engine.compare()

    def test_compare_basic_structure(self) -> None:
        engine = self._make_engine_with_two_models()
        comparison = engine.compare()

        assert "models" in comparison
        assert "summary_table" in comparison
        assert "task_matrix" in comparison
        assert "unique_wins" in comparison
        assert "rankings" in comparison
        assert "pairwise" in comparison

        assert comparison["models"] == ["model-a", "model-b"]

    def test_summary_table_rows(self) -> None:
        engine = self._make_engine_with_two_models()
        comparison = engine.compare()

        table = comparison["summary_table"]
        assert len(table) == 2

        labels = {row["label"] for row in table}
        assert labels == {"model-a", "model-b"}

        for row in table:
            assert "rate" in row
            assert "cost" in row
            assert "resolved" in row
            assert "total" in row
            assert "avg_cost_per_task" in row
            assert "avg_tokens" in row

    def test_task_matrix(self) -> None:
        engine = self._make_engine_with_two_models()
        comparison = engine.compare()
        matrix = comparison["task_matrix"]

        # Both models have tasks task-0 through task-4
        assert "task-0" in matrix
        assert "model-a" in matrix["task-0"]
        assert "model-b" in matrix["task-0"]

    def test_unique_wins(self) -> None:
        """A task resolved by only one model counts as a unique win."""
        engine = ComparisonEngine()

        # model-a resolves task-0 only; model-b resolves nothing
        tasks_a = [
            {
                "instance_id": "task-0",
                "mcp": {"resolved": True, "cost": 0.1, "tokens": {"input": 100, "output": 50}},
            },
            {
                "instance_id": "task-1",
                "mcp": {"resolved": False, "cost": 0.1, "tokens": {"input": 100, "output": 50}},
            },
        ]
        tasks_b = [
            {
                "instance_id": "task-0",
                "mcp": {"resolved": False, "cost": 0.2, "tokens": {"input": 200, "output": 100}},
            },
            {
                "instance_id": "task-1",
                "mcp": {"resolved": False, "cost": 0.2, "tokens": {"input": 200, "output": 100}},
            },
        ]

        engine.add_results(
            "a",
            _make_results_data(total=2, resolved=1, tasks=tasks_a),
        )
        engine.add_results(
            "b",
            _make_results_data(total=2, resolved=0, tasks=tasks_b),
        )

        comparison = engine.compare()
        assert "task-0" in comparison["unique_wins"]["a"]
        assert comparison["unique_wins"]["b"] == []

    def test_rankings(self) -> None:
        engine = self._make_engine_with_two_models()
        comparison = engine.compare()
        rankings = comparison["rankings"]

        assert "by_rate" in rankings
        assert "by_cost_efficiency" in rankings
        assert "by_speed" in rankings

        # model-b has rate 0.8 > model-a 0.6
        assert rankings["by_rate"][0] == "model-b"

    def test_pairwise_comparisons(self) -> None:
        engine = self._make_engine_with_two_models()
        comparison = engine.compare()
        pairwise = comparison["pairwise"]

        assert len(pairwise) == 1
        pair = pairwise[0]
        assert pair["model_a"] == "model-a"
        assert pair["model_b"] == "model-b"
        assert pair["better"] == "model-b"
        assert pair["rate_difference"] == pytest.approx(0.2)

    def test_three_models_pairwise(self) -> None:
        """Three models should produce 3 pairwise comparisons."""
        engine = ComparisonEngine()
        for label in ("m1", "m2", "m3"):
            engine.add_results(label, _make_results_data())

        comparison = engine.compare()
        assert len(comparison["pairwise"]) == 3


class TestCostPerformanceFrontier:
    """Tests for ComparisonEngine.get_cost_performance_frontier()."""

    def test_basic_frontier(self) -> None:
        engine = ComparisonEngine()
        # cheap-low: cost=1, rate=0.3 (on frontier - cheapest)
        engine.add_results(
            "cheap-low",
            _make_results_data(total_cost=1.0, rate=0.3),
        )
        # mid: cost=2, rate=0.7 (on frontier)
        engine.add_results(
            "mid",
            _make_results_data(total_cost=2.0, rate=0.7),
        )
        # expensive-high: cost=5, rate=0.9 (on frontier)
        engine.add_results(
            "expensive-high",
            _make_results_data(total_cost=5.0, rate=0.9),
        )
        # dominated: cost=3, rate=0.5 (dominated by mid: more expensive, lower rate)
        engine.add_results(
            "dominated",
            _make_results_data(total_cost=3.0, rate=0.5),
        )

        frontier = engine.get_cost_performance_frontier()
        frontier_labels = [p["label"] for p in frontier]
        assert "dominated" not in frontier_labels
        assert "cheap-low" in frontier_labels
        assert "mid" in frontier_labels
        assert "expensive-high" in frontier_labels

    def test_frontier_requires_two_entries(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("solo", _make_results_data())
        with pytest.raises(ValueError, match="At least 2 result sets required"):
            engine.get_cost_performance_frontier()

    def test_frontier_sorted_by_cost(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("expensive", _make_results_data(total_cost=10.0, rate=0.9))
        engine.add_results("cheap", _make_results_data(total_cost=1.0, rate=0.5))

        frontier = engine.get_cost_performance_frontier()
        costs = [p["cost"] for p in frontier]
        assert costs == sorted(costs)


class TestGetWinnerAnalysis:
    """Tests for ComparisonEngine.get_winner_analysis()."""

    def test_winner_analysis_keys(self) -> None:
        engine = ComparisonEngine()
        engine.add_results(
            "fast-cheap",
            _make_results_data(rate=0.4, total_cost=1.0, total=5, resolved=2),
        )
        engine.add_results(
            "slow-expensive",
            _make_results_data(rate=0.8, total_cost=5.0, total=5, resolved=4),
        )

        winners = engine.get_winner_analysis()
        assert "highest_resolution_rate" in winners
        assert "lowest_total_cost" in winners

    def test_highest_resolution_rate_winner(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("low", _make_results_data(rate=0.3, total=5, resolved=1))
        engine.add_results("high", _make_results_data(rate=0.9, total=5, resolved=4))

        winners = engine.get_winner_analysis()
        assert winners["highest_resolution_rate"]["winner"] == "high"
        assert winners["highest_resolution_rate"]["value"] == pytest.approx(0.9)

    def test_lowest_cost_winner(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("cheap", _make_results_data(total_cost=0.50))
        engine.add_results("pricey", _make_results_data(total_cost=10.00))

        winners = engine.get_winner_analysis()
        assert winners["lowest_total_cost"]["winner"] == "cheap"

    def test_winner_analysis_requires_two_entries(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("solo", _make_results_data())
        with pytest.raises(ValueError, match="At least 2 result sets required"):
            engine.get_winner_analysis()


class TestCompareResultsFiles:
    """Tests for compare_results_files()."""

    def test_compare_two_files(self, tmp_path: Path) -> None:
        file_a = tmp_path / "result_a.json"
        file_b = tmp_path / "result_b.json"

        file_a.write_text(
            json.dumps(_make_results_data(model="claude-sonnet", rate=0.6, total=5, resolved=3))
        )
        file_b.write_text(
            json.dumps(_make_results_data(model="gpt-4o", rate=0.8, total=5, resolved=4))
        )

        comparison = compare_results_files([file_a, file_b])
        assert len(comparison["models"]) == 2
        # Labels derived from file stems
        assert "result_a" in comparison["models"]
        assert "result_b" in comparison["models"]

    def test_compare_with_custom_labels(self, tmp_path: Path) -> None:
        file_a = tmp_path / "a.json"
        file_b = tmp_path / "b.json"
        file_a.write_text(json.dumps(_make_results_data()))
        file_b.write_text(json.dumps(_make_results_data()))

        comparison = compare_results_files([file_a, file_b], labels=["Alpha", "Beta"])
        assert comparison["models"] == ["Alpha", "Beta"]

    def test_fewer_than_two_files_raises(self, tmp_path: Path) -> None:
        file_a = tmp_path / "a.json"
        file_a.write_text(json.dumps(_make_results_data()))
        with pytest.raises(ValueError, match="At least 2 file paths required"):
            compare_results_files([file_a])

    def test_mismatched_labels_raises(self, tmp_path: Path) -> None:
        file_a = tmp_path / "a.json"
        file_b = tmp_path / "b.json"
        file_a.write_text(json.dumps(_make_results_data()))
        file_b.write_text(json.dumps(_make_results_data()))

        with pytest.raises(ValueError, match="Labels length"):
            compare_results_files([file_a, file_b], labels=["one"])

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        existing = tmp_path / "exists.json"
        existing.write_text(json.dumps(_make_results_data()))

        with pytest.raises(FileNotFoundError):
            compare_results_files([existing, missing])


class TestFormatComparisonTable:
    """Tests for format_comparison_table()."""

    def test_output_is_string(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("m1", _make_results_data(rate=0.5, total=5, resolved=2))
        engine.add_results("m2", _make_results_data(rate=0.7, total=5, resolved=3))

        comparison = engine.compare()
        output = format_comparison_table(comparison)
        assert isinstance(output, str)

    def test_contains_header(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("m1", _make_results_data())
        engine.add_results("m2", _make_results_data())

        comparison = engine.compare()
        output = format_comparison_table(comparison)
        assert "MULTI-MODEL COMPARISON" in output

    def test_contains_model_labels(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("alpha-model", _make_results_data())
        engine.add_results("beta-model", _make_results_data())

        comparison = engine.compare()
        output = format_comparison_table(comparison)
        assert "alpha-model" in output
        assert "beta-model" in output

    def test_contains_sections(self) -> None:
        engine = ComparisonEngine()
        engine.add_results("m1", _make_results_data(rate=0.5, total=5, resolved=2))
        engine.add_results("m2", _make_results_data(rate=0.7, total=5, resolved=3))

        comparison = engine.compare()
        output = format_comparison_table(comparison)

        assert "SUMMARY" in output
        assert "RANKINGS" in output
        assert "PAIRWISE COMPARISONS" in output

    def test_empty_comparison_table(self) -> None:
        """format_comparison_table handles a comparison with empty summary_table."""
        output = format_comparison_table({"summary_table": [], "unique_wins": {}, "rankings": {}})
        assert "MULTI-MODEL COMPARISON" in output
