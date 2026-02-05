"""Tests for task scheduling and prioritization module."""

import pytest

from mcpbr.task_scheduler import (
    SchedulingStrategy,
    TaskPriority,
    TaskScheduler,
    _extract_category,
    create_scheduler,
)


def _make_tasks(
    n: int,
    problem_lengths: list[int] | None = None,
    categories: list[str] | None = None,
    repos: list[str] | None = None,
) -> list[dict]:
    """Create a list of test task dictionaries.

    Args:
        n: Number of tasks to create.
        problem_lengths: If provided, cycle through these lengths to generate
            problem_statement strings of varying size.
        categories: If provided, cycle through these category values.
        repos: If provided, cycle through these repo values.

    Returns:
        List of task dictionaries with ``instance_id`` and optional fields.
    """
    tasks = []
    for i in range(n):
        task: dict = {"instance_id": f"task_{i}"}
        if problem_lengths:
            length = problem_lengths[i % len(problem_lengths)]
            task["problem_statement"] = "x" * length
        if categories:
            task["category"] = categories[i % len(categories)]
        if repos:
            task["repo"] = repos[i % len(repos)]
        tasks.append(task)
    return tasks


class TestSchedulingStrategy:
    """Tests for the SchedulingStrategy enum."""

    def test_enum_values(self) -> None:
        """Test that all expected strategies exist with correct string values."""
        assert SchedulingStrategy.DEFAULT.value == "default"
        assert SchedulingStrategy.SPEED_FIRST.value == "speed"
        assert SchedulingStrategy.COST_FIRST.value == "cost"
        assert SchedulingStrategy.COVERAGE_FIRST.value == "coverage"
        assert SchedulingStrategy.CUSTOM.value == "custom"

    def test_enum_from_string(self) -> None:
        """Test creating enum from string values."""
        assert SchedulingStrategy("default") == SchedulingStrategy.DEFAULT
        assert SchedulingStrategy("speed") == SchedulingStrategy.SPEED_FIRST
        assert SchedulingStrategy("cost") == SchedulingStrategy.COST_FIRST
        assert SchedulingStrategy("coverage") == SchedulingStrategy.COVERAGE_FIRST
        assert SchedulingStrategy("custom") == SchedulingStrategy.CUSTOM

    def test_invalid_strategy_raises(self) -> None:
        """Test that invalid strategy string raises ValueError."""
        with pytest.raises(ValueError):
            SchedulingStrategy("invalid")


class TestTaskPriority:
    """Tests for the TaskPriority dataclass."""

    def test_default_values(self) -> None:
        """Test that TaskPriority has correct defaults."""
        p = TaskPriority(task_id="test-1")
        assert p.task_id == "test-1"
        assert p.priority_score == 0.0
        assert p.estimated_time_seconds is None
        assert p.estimated_cost_usd is None
        assert p.category is None
        assert p.metadata == {}

    def test_custom_values(self) -> None:
        """Test that TaskPriority stores provided values."""
        p = TaskPriority(
            task_id="test-2",
            priority_score=5.5,
            estimated_time_seconds=120.0,
            estimated_cost_usd=0.05,
            category="django",
            metadata={"difficulty": "hard"},
        )
        assert p.task_id == "test-2"
        assert p.priority_score == 5.5
        assert p.estimated_time_seconds == 120.0
        assert p.estimated_cost_usd == 0.05
        assert p.category == "django"
        assert p.metadata == {"difficulty": "hard"}

    def test_metadata_not_shared(self) -> None:
        """Test that metadata default is not shared between instances."""
        p1 = TaskPriority(task_id="a")
        p2 = TaskPriority(task_id="b")
        p1.metadata["key"] = "value"
        assert "key" not in p2.metadata


class TestTaskSchedulerInit:
    """Tests for TaskScheduler initialization."""

    def test_default_strategy(self) -> None:
        """Test that default strategy is DEFAULT."""
        scheduler = TaskScheduler()
        assert scheduler.strategy == SchedulingStrategy.DEFAULT

    def test_explicit_strategy(self) -> None:
        """Test setting an explicit strategy."""
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        assert scheduler.strategy == SchedulingStrategy.SPEED_FIRST

    def test_custom_strategy_requires_scorer(self) -> None:
        """Test that CUSTOM strategy without scorer raises ValueError."""
        with pytest.raises(ValueError, match="custom_scorer is required"):
            TaskScheduler(strategy=SchedulingStrategy.CUSTOM)

    def test_custom_strategy_with_scorer(self) -> None:
        """Test that CUSTOM strategy with scorer succeeds."""
        scorer = lambda task: 1.0  # noqa: E731
        scheduler = TaskScheduler(strategy=SchedulingStrategy.CUSTOM, custom_scorer=scorer)
        assert scheduler.strategy == SchedulingStrategy.CUSTOM


class TestDefaultStrategy:
    """Tests for DEFAULT scheduling strategy (preserve original order)."""

    def test_preserves_order(self) -> None:
        """Test that DEFAULT returns tasks in original order."""
        tasks = _make_tasks(10)
        scheduler = TaskScheduler(strategy=SchedulingStrategy.DEFAULT)
        result = scheduler.schedule(tasks)
        assert [t["instance_id"] for t in result] == [f"task_{i}" for i in range(10)]

    def test_returns_new_list(self) -> None:
        """Test that DEFAULT returns a new list, not the original reference."""
        tasks = _make_tasks(5)
        scheduler = TaskScheduler(strategy=SchedulingStrategy.DEFAULT)
        result = scheduler.schedule(tasks)
        assert result is not tasks
        assert result == tasks

    def test_does_not_mutate_input(self) -> None:
        """Test that scheduling does not mutate the input list."""
        tasks = _make_tasks(10)
        original_ids = [t["instance_id"] for t in tasks]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.DEFAULT)
        _ = scheduler.schedule(tasks)
        assert [t["instance_id"] for t in tasks] == original_ids


class TestSpeedFirstStrategy:
    """Tests for SPEED_FIRST scheduling strategy."""

    def test_short_problems_first(self) -> None:
        """Test that tasks with shorter problem statements come first."""
        # Use lengths above 1000 so estimates exceed _MIN_ESTIMATED_TIME and differ
        tasks = _make_tasks(5, problem_lengths=[10000, 2000, 8000, 1500, 5000])
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        result = scheduler.schedule(tasks)

        # Tasks with shorter problems should come first
        result_ids = [t["instance_id"] for t in result]
        # Shortest problems first: 1500, 2000, 5000, 8000, 10000
        assert result_ids[0] == "task_3"  # 1500 chars
        assert result_ids[1] == "task_1"  # 2000 chars

    def test_empty_problems_are_fast(self) -> None:
        """Test that tasks without problem statements are considered fast."""
        tasks = [
            {"instance_id": "long", "problem_statement": "x" * 10000},
            {"instance_id": "empty"},
            {"instance_id": "short", "problem_statement": "x" * 100},
        ]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        result = scheduler.schedule(tasks)

        # Empty and short should come before long
        result_ids = [t["instance_id"] for t in result]
        assert result_ids.index("empty") < result_ids.index("long")
        assert result_ids.index("short") < result_ids.index("long")

    def test_all_same_length_preserves_relative_order(self) -> None:
        """Test that tasks with equal estimated time maintain stable order."""
        tasks = _make_tasks(5, problem_lengths=[500])
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        result = scheduler.schedule(tasks)
        # All have the same length, so order should be stable
        assert len(result) == 5


class TestCostFirstStrategy:
    """Tests for COST_FIRST scheduling strategy."""

    def test_cheap_problems_first(self) -> None:
        """Test that tasks with shorter problem statements (cheaper) come first."""
        # Use lengths well above minimum so cost estimates differ meaningfully
        tasks = _make_tasks(4, problem_lengths=[10000, 2000, 8000, 1500])
        scheduler = TaskScheduler(strategy=SchedulingStrategy.COST_FIRST)
        result = scheduler.schedule(tasks)

        result_ids = [t["instance_id"] for t in result]
        # Shortest (cheapest) problems first: 1500, 2000, 8000, 10000
        assert result_ids[0] == "task_3"  # 1500 chars
        assert result_ids[1] == "task_1"  # 2000 chars

    def test_cost_estimate_increases_with_length(self) -> None:
        """Test that cost estimates increase with problem statement length."""
        scheduler = TaskScheduler(strategy=SchedulingStrategy.COST_FIRST)
        short_task = {"instance_id": "short", "problem_statement": "x" * 100}
        long_task = {"instance_id": "long", "problem_statement": "x" * 10000}

        short_cost = scheduler.estimate_task_cost(short_task)
        long_cost = scheduler.estimate_task_cost(long_task)
        assert long_cost > short_cost


class TestCoverageFirstStrategy:
    """Tests for COVERAGE_FIRST scheduling strategy."""

    def test_round_robin_categories(self) -> None:
        """Test that tasks from different categories are interleaved."""
        tasks = [
            {"instance_id": "a1", "category": "alpha"},
            {"instance_id": "a2", "category": "alpha"},
            {"instance_id": "a3", "category": "alpha"},
            {"instance_id": "b1", "category": "beta"},
            {"instance_id": "b2", "category": "beta"},
            {"instance_id": "b3", "category": "beta"},
        ]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.COVERAGE_FIRST)
        result = scheduler.schedule(tasks)

        result_ids = [t["instance_id"] for t in result]
        # Round-robin: alpha, beta, alpha, beta, alpha, beta
        assert result_ids == ["a1", "b1", "a2", "b2", "a3", "b3"]

    def test_round_robin_with_repos(self) -> None:
        """Test that round-robin works using the repo field."""
        tasks = [
            {"instance_id": "d1", "repo": "django"},
            {"instance_id": "d2", "repo": "django"},
            {"instance_id": "f1", "repo": "flask"},
            {"instance_id": "f2", "repo": "flask"},
        ]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.COVERAGE_FIRST)
        result = scheduler.schedule(tasks)

        result_ids = [t["instance_id"] for t in result]
        # Round-robin: django, flask, django, flask
        assert result_ids == ["d1", "f1", "d2", "f2"]

    def test_round_robin_uneven_groups(self) -> None:
        """Test round-robin with uneven group sizes."""
        tasks = [
            {"instance_id": "a1", "category": "alpha"},
            {"instance_id": "a2", "category": "alpha"},
            {"instance_id": "a3", "category": "alpha"},
            {"instance_id": "a4", "category": "alpha"},
            {"instance_id": "b1", "category": "beta"},
        ]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.COVERAGE_FIRST)
        result = scheduler.schedule(tasks)

        result_ids = [t["instance_id"] for t in result]
        # Round 0: a1, b1; Round 1: a2; Round 2: a3; Round 3: a4
        assert result_ids == ["a1", "b1", "a2", "a3", "a4"]

    def test_round_robin_no_categories(self) -> None:
        """Test round-robin when tasks have no category fields."""
        tasks = _make_tasks(3)
        scheduler = TaskScheduler(strategy=SchedulingStrategy.COVERAGE_FIRST)
        result = scheduler.schedule(tasks)

        # All tasks fall into _uncategorized_, so order is preserved
        assert len(result) == 3

    def test_coverage_diverse_early_results(self) -> None:
        """Test that early tasks span multiple categories."""
        tasks = [
            {"instance_id": f"{cat}_{i}", "category": cat}
            for cat in ["repo_a", "repo_b", "repo_c"]
            for i in range(5)
        ]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.COVERAGE_FIRST)
        result = scheduler.schedule(tasks)

        # First 3 tasks should each be from a different category
        first_3_categories = {t.get("category") for t in result[:3]}
        assert len(first_3_categories) == 3


class TestCustomStrategy:
    """Tests for CUSTOM scheduling strategy."""

    def test_custom_scorer_is_used(self) -> None:
        """Test that the custom scorer function determines order."""
        tasks = [
            {"instance_id": "high", "priority": 100},
            {"instance_id": "low", "priority": 1},
            {"instance_id": "mid", "priority": 50},
        ]
        # Score by the 'priority' field
        scorer = lambda task: float(task.get("priority", 0))  # noqa: E731
        scheduler = TaskScheduler(strategy=SchedulingStrategy.CUSTOM, custom_scorer=scorer)
        result = scheduler.schedule(tasks)

        result_ids = [t["instance_id"] for t in result]
        assert result_ids == ["low", "mid", "high"]

    def test_custom_scorer_reverse_order(self) -> None:
        """Test custom scorer that reverses original order."""
        tasks = _make_tasks(5)
        # Score by negative index (so last task has lowest score)
        scorer = lambda task: -float(task["instance_id"].split("_")[1])  # noqa: E731
        scheduler = TaskScheduler(strategy=SchedulingStrategy.CUSTOM, custom_scorer=scorer)
        result = scheduler.schedule(tasks)

        result_ids = [t["instance_id"] for t in result]
        assert result_ids == ["task_4", "task_3", "task_2", "task_1", "task_0"]

    def test_custom_scorer_with_problem_length(self) -> None:
        """Test custom scorer that combines multiple task attributes."""
        tasks = [
            {"instance_id": "t1", "problem_statement": "x" * 100, "priority": 10},
            {"instance_id": "t2", "problem_statement": "x" * 1000, "priority": 1},
            {"instance_id": "t3", "problem_statement": "x" * 500, "priority": 5},
        ]

        def scorer(task: dict) -> float:
            length = len(task.get("problem_statement", ""))
            priority = task.get("priority", 0)
            return length * priority  # Higher product = lower priority

        scheduler = TaskScheduler(strategy=SchedulingStrategy.CUSTOM, custom_scorer=scorer)
        result = scheduler.schedule(tasks)

        result_ids = [t["instance_id"] for t in result]
        # t1: 100*10=1000, t2: 1000*1=1000, t3: 500*5=2500
        # t1 and t2 tie at 1000 (stable sort preserves their order), then t3
        assert result_ids[2] == "t3"


class TestEstimateTaskCost:
    """Tests for the estimate_task_cost method."""

    def test_empty_problem_returns_minimum(self) -> None:
        """Test that a task without a problem statement returns minimum cost."""
        scheduler = TaskScheduler()
        cost = scheduler.estimate_task_cost({"instance_id": "empty"})
        assert cost >= 0.001

    def test_longer_problem_costs_more(self) -> None:
        """Test that longer problem statements produce higher cost estimates."""
        scheduler = TaskScheduler()
        short_cost = scheduler.estimate_task_cost(
            {"instance_id": "short", "problem_statement": "x" * 100}
        )
        long_cost = scheduler.estimate_task_cost(
            {"instance_id": "long", "problem_statement": "x" * 10000}
        )
        assert long_cost > short_cost

    def test_unknown_model_returns_minimum(self) -> None:
        """Test that an unknown model returns minimum cost."""
        scheduler = TaskScheduler()
        cost = scheduler.estimate_task_cost(
            {"instance_id": "t1", "problem_statement": "x" * 1000},
            model="totally-unknown-model",
        )
        assert cost == 0.001

    def test_cost_is_positive(self) -> None:
        """Test that cost estimates are always positive."""
        scheduler = TaskScheduler()
        for length in [0, 10, 100, 1000, 10000]:
            cost = scheduler.estimate_task_cost(
                {"instance_id": f"t_{length}", "problem_statement": "x" * length}
            )
            assert cost > 0


class TestEstimateTaskTime:
    """Tests for the estimate_task_time method."""

    def test_empty_problem_returns_minimum(self) -> None:
        """Test that a task without a problem statement returns minimum time."""
        scheduler = TaskScheduler()
        time = scheduler.estimate_task_time({"instance_id": "empty"})
        assert time == 30.0  # _MIN_ESTIMATED_TIME

    def test_longer_problem_takes_more_time(self) -> None:
        """Test that longer problem statements produce higher time estimates."""
        scheduler = TaskScheduler()
        short_time = scheduler.estimate_task_time(
            {"instance_id": "short", "problem_statement": "x" * 100}
        )
        long_time = scheduler.estimate_task_time(
            {"instance_id": "long", "problem_statement": "x" * 10000}
        )
        assert long_time > short_time

    def test_time_is_positive(self) -> None:
        """Test that time estimates are always positive."""
        scheduler = TaskScheduler()
        for length in [0, 10, 100, 1000, 10000]:
            time = scheduler.estimate_task_time(
                {"instance_id": f"t_{length}", "problem_statement": "x" * length}
            )
            assert time > 0

    def test_time_scales_linearly(self) -> None:
        """Test that time scales roughly linearly with problem length."""
        scheduler = TaskScheduler()
        time_2k = scheduler.estimate_task_time(
            {"instance_id": "t1", "problem_statement": "x" * 2000}
        )
        time_4k = scheduler.estimate_task_time(
            {"instance_id": "t2", "problem_statement": "x" * 4000}
        )
        # 4k should be roughly 2x of 2k
        assert time_4k == pytest.approx(time_2k * 2, rel=0.01)


class TestPreview:
    """Tests for the schedule preview formatting."""

    def test_preview_empty_tasks(self) -> None:
        """Test preview with no tasks."""
        scheduler = TaskScheduler()
        result = scheduler.preview([])
        assert result == "No tasks to schedule."

    def test_preview_contains_header(self) -> None:
        """Test that preview contains strategy information."""
        tasks = _make_tasks(3, problem_lengths=[100, 200, 300])
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        result = scheduler.preview(tasks)
        assert "Schedule Preview" in result
        assert "speed" in result
        assert "Total tasks: 3" in result

    def test_preview_contains_task_ids(self) -> None:
        """Test that preview lists all task IDs."""
        tasks = _make_tasks(3)
        scheduler = TaskScheduler(strategy=SchedulingStrategy.DEFAULT)
        result = scheduler.preview(tasks)
        for i in range(3):
            assert f"task_{i}" in result

    def test_preview_contains_estimates(self) -> None:
        """Test that preview includes time and cost estimates."""
        tasks = _make_tasks(2, problem_lengths=[1000, 5000])
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        result = scheduler.preview(tasks)
        # Should contain time estimates (e.g., "30s") and cost estimates (e.g., "$0.0010")
        assert "s" in result  # Time estimates end with 's'
        assert "$" in result  # Cost estimates start with '$'

    def test_preview_matches_schedule_order(self) -> None:
        """Test that preview order matches actual schedule order."""
        tasks = _make_tasks(5, problem_lengths=[5000, 100, 3000, 50, 2000])
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)

        scheduled = scheduler.schedule(tasks)
        preview = scheduler.preview(tasks)

        scheduled_ids = [t["instance_id"] for t in scheduled]
        # Verify first task in schedule appears first in preview (after header)
        lines = preview.split("\n")
        # Find the first data line (after headers and separators)
        data_lines = [line for line in lines if line.strip().startswith(("1 ", "1\t"))]
        if data_lines:
            assert scheduled_ids[0] in data_lines[0]


class TestExtractCategory:
    """Tests for the _extract_category helper function."""

    def test_category_field(self) -> None:
        """Test extracting from 'category' field."""
        assert _extract_category({"category": "web"}) == "web"

    def test_repo_field(self) -> None:
        """Test extracting from 'repo' field when category is absent."""
        assert _extract_category({"repo": "django/django"}) == "django/django"

    def test_difficulty_field(self) -> None:
        """Test extracting from 'difficulty' field when others are absent."""
        assert _extract_category({"difficulty": "hard"}) == "hard"

    def test_category_takes_precedence(self) -> None:
        """Test that 'category' takes precedence over 'repo' and 'difficulty'."""
        task = {"category": "web", "repo": "django", "difficulty": "easy"}
        assert _extract_category(task) == "web"

    def test_repo_takes_precedence_over_difficulty(self) -> None:
        """Test that 'repo' takes precedence over 'difficulty'."""
        task = {"repo": "flask", "difficulty": "medium"}
        assert _extract_category(task) == "flask"

    def test_no_category_returns_none(self) -> None:
        """Test that task without category fields returns None."""
        assert _extract_category({"instance_id": "t1"}) is None

    def test_numeric_category_is_string(self) -> None:
        """Test that numeric category values are converted to string."""
        assert _extract_category({"difficulty": 3}) == "3"


class TestCreateScheduler:
    """Tests for the create_scheduler factory function."""

    def test_default_preset(self) -> None:
        """Test creating scheduler with 'default' preset."""
        scheduler = create_scheduler("default")
        assert scheduler.strategy == SchedulingStrategy.DEFAULT

    def test_speed_preset(self) -> None:
        """Test creating scheduler with 'speed' preset."""
        scheduler = create_scheduler("speed")
        assert scheduler.strategy == SchedulingStrategy.SPEED_FIRST

    def test_cost_preset(self) -> None:
        """Test creating scheduler with 'cost' preset."""
        scheduler = create_scheduler("cost")
        assert scheduler.strategy == SchedulingStrategy.COST_FIRST

    def test_coverage_preset(self) -> None:
        """Test creating scheduler with 'coverage' preset."""
        scheduler = create_scheduler("coverage")
        assert scheduler.strategy == SchedulingStrategy.COVERAGE_FIRST

    def test_case_insensitive(self) -> None:
        """Test that preset names are case-insensitive."""
        scheduler = create_scheduler("SPEED")
        assert scheduler.strategy == SchedulingStrategy.SPEED_FIRST

        scheduler = create_scheduler("Cost")
        assert scheduler.strategy == SchedulingStrategy.COST_FIRST

    def test_invalid_preset_raises(self) -> None:
        """Test that invalid preset name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown scheduling preset"):
            create_scheduler("invalid")

    def test_invalid_preset_lists_valid_options(self) -> None:
        """Test that error message lists valid preset names."""
        with pytest.raises(ValueError, match="cost") as exc_info:
            create_scheduler("bogus")
        error_msg = str(exc_info.value)
        assert "default" in error_msg
        assert "speed" in error_msg
        assert "cost" in error_msg
        assert "coverage" in error_msg


class TestEdgeCases:
    """Tests for edge cases across all scheduling strategies."""

    def test_empty_tasks_all_strategies(self) -> None:
        """Test that all strategies handle empty task list."""
        for strategy in SchedulingStrategy:
            kwargs: dict = {"strategy": strategy}
            if strategy == SchedulingStrategy.CUSTOM:
                kwargs["custom_scorer"] = lambda t: 0.0
            scheduler = TaskScheduler(**kwargs)
            result = scheduler.schedule([])
            assert result == []

    def test_single_task_all_strategies(self) -> None:
        """Test that all strategies handle a single task."""
        tasks = _make_tasks(1, problem_lengths=[500], categories=["test"])
        for strategy in SchedulingStrategy:
            kwargs: dict = {"strategy": strategy}
            if strategy == SchedulingStrategy.CUSTOM:
                kwargs["custom_scorer"] = lambda t: 0.0
            scheduler = TaskScheduler(**kwargs)
            result = scheduler.schedule(tasks)
            assert len(result) == 1
            assert result[0]["instance_id"] == "task_0"

    def test_tasks_without_instance_id(self) -> None:
        """Test handling tasks that lack instance_id field."""
        tasks = [{"name": "task_a"}, {"name": "task_b"}]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.DEFAULT)
        result = scheduler.schedule(tasks)
        assert len(result) == 2

    def test_large_task_list(self) -> None:
        """Test scheduling with a large number of tasks."""
        tasks = _make_tasks(1000, problem_lengths=[100, 500, 1000, 5000, 10000])
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        result = scheduler.schedule(tasks)
        assert len(result) == 1000

        # Verify ordering: first task should have shortest problem
        first_problem_len = len(result[0].get("problem_statement", ""))
        last_problem_len = len(result[-1].get("problem_statement", ""))
        assert first_problem_len <= last_problem_len

    def test_schedule_does_not_lose_tasks(self) -> None:
        """Test that scheduling preserves all tasks (no duplicates or losses)."""
        tasks = _make_tasks(20, categories=["a", "b", "c"])
        for strategy in SchedulingStrategy:
            kwargs: dict = {"strategy": strategy}
            if strategy == SchedulingStrategy.CUSTOM:
                kwargs["custom_scorer"] = lambda t: 0.0
            scheduler = TaskScheduler(**kwargs)
            result = scheduler.schedule(tasks)
            original_ids = sorted(t["instance_id"] for t in tasks)
            result_ids = sorted(t["instance_id"] for t in result)
            assert original_ids == result_ids

    def test_schedule_does_not_mutate_input(self) -> None:
        """Test that scheduling does not modify the input task list."""
        tasks = _make_tasks(10, problem_lengths=[100, 500, 1000])
        original_ids = [t["instance_id"] for t in tasks]
        scheduler = TaskScheduler(strategy=SchedulingStrategy.SPEED_FIRST)
        _ = scheduler.schedule(tasks)
        assert [t["instance_id"] for t in tasks] == original_ids

    def test_preview_all_strategies(self) -> None:
        """Test that preview works for all strategies without errors."""
        tasks = _make_tasks(5, problem_lengths=[100, 500], categories=["a", "b"])
        for strategy in SchedulingStrategy:
            kwargs: dict = {"strategy": strategy}
            if strategy == SchedulingStrategy.CUSTOM:
                kwargs["custom_scorer"] = lambda t: 0.0
            scheduler = TaskScheduler(**kwargs)
            result = scheduler.preview(tasks)
            assert isinstance(result, str)
            assert len(result) > 0
            assert "Schedule Preview" in result
