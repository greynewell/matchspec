"""Tests for the task batching module."""

import pytest

from mcpbr.task_batching import (
    _CONTAINER_RESTART_OVERHEAD_SECONDS,
    BatchSavings,
    BatchStrategy,
    TaskBatch,
    TaskBatcher,
)

# ---------------------------------------------------------------------------
# Helper: build mock task dicts
# ---------------------------------------------------------------------------


def _make_tasks(
    n: int,
    repo: str | None = None,
    image: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Create a list of test task dictionaries with optional shared fields.

    Args:
        n: Number of tasks to create.
        repo: If provided, all tasks share this repo value.
        image: If provided, all tasks share this image value.
        category: If provided, all tasks share this category value.

    Returns:
        List of task dictionaries.
    """
    tasks = []
    for i in range(n):
        task: dict = {"instance_id": f"task_{i}"}
        if repo is not None:
            task["repo"] = repo
        if image is not None:
            task["image"] = image
        if category is not None:
            task["category"] = category
        tasks.append(task)
    return tasks


def _make_varied_tasks() -> list[dict]:
    """Create a realistic set of tasks with varied repos, images, and categories.

    Returns:
        List of 12 task dictionaries spread across 3 repos, 2 images, 2 categories.
    """
    tasks = []
    repos = [
        "astropy/astropy",
        "astropy/astropy",
        "django/django",
        "django/django",
        "django/django",
        "sympy/sympy",
        "sympy/sympy",
        "sympy/sympy",
        "astropy/astropy",
        "django/django",
        "sympy/sympy",
        "django/django",
    ]
    images = [
        "img-astropy",
        "img-astropy",
        "img-django",
        "img-django",
        "img-django",
        "img-sympy",
        "img-sympy",
        "img-sympy",
        "img-astropy",
        "img-django",
        "img-sympy",
        "img-django",
    ]
    categories = [
        "astronomy",
        "astronomy",
        "web",
        "web",
        "web",
        "math",
        "math",
        "math",
        "astronomy",
        "web",
        "math",
        "web",
    ]

    for i in range(12):
        tasks.append(
            {
                "instance_id": f"task_{i}",
                "repo": repos[i],
                "image": images[i],
                "category": categories[i],
            }
        )
    return tasks


# ===========================================================================
# BatchStrategy enum tests
# ===========================================================================


class TestBatchStrategy:
    """Tests for the BatchStrategy enum."""

    def test_enum_values(self) -> None:
        """Test that all expected strategies exist with correct string values."""
        assert BatchStrategy.BY_REPO.value == "by_repo"
        assert BatchStrategy.BY_IMAGE.value == "by_image"
        assert BatchStrategy.BY_CATEGORY.value == "by_category"
        assert BatchStrategy.FIXED_SIZE.value == "fixed_size"
        assert BatchStrategy.ADAPTIVE.value == "adaptive"

    def test_enum_from_string(self) -> None:
        """Test creating enum from string values."""
        assert BatchStrategy("by_repo") == BatchStrategy.BY_REPO
        assert BatchStrategy("by_image") == BatchStrategy.BY_IMAGE
        assert BatchStrategy("by_category") == BatchStrategy.BY_CATEGORY
        assert BatchStrategy("fixed_size") == BatchStrategy.FIXED_SIZE
        assert BatchStrategy("adaptive") == BatchStrategy.ADAPTIVE

    def test_invalid_strategy_raises(self) -> None:
        """Test that invalid strategy string raises ValueError."""
        with pytest.raises(ValueError):
            BatchStrategy("invalid_strategy")

    def test_all_strategies_count(self) -> None:
        """Test that we have exactly 5 strategies."""
        assert len(BatchStrategy) == 5


# ===========================================================================
# TaskBatch dataclass tests
# ===========================================================================


class TestTaskBatch:
    """Tests for the TaskBatch dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a TaskBatch with all fields."""
        tasks = _make_tasks(3, repo="org/repo")
        batch = TaskBatch(
            batch_id="test-id",
            tasks=tasks,
            common_image=None,
            common_repo="org/repo",
            batch_size=3,
            estimated_savings_seconds=60.0,
        )
        assert batch.batch_id == "test-id"
        assert len(batch.tasks) == 3
        assert batch.common_repo == "org/repo"
        assert batch.common_image is None
        assert batch.batch_size == 3
        assert batch.estimated_savings_seconds == 60.0

    def test_post_init_computes_batch_size(self) -> None:
        """Test that batch_size is auto-computed from tasks when left at 0."""
        tasks = _make_tasks(5)
        batch = TaskBatch(batch_id="auto", tasks=tasks)
        assert batch.batch_size == 5

    def test_post_init_preserves_explicit_size(self) -> None:
        """Test that explicitly provided batch_size is not overridden."""
        tasks = _make_tasks(3)
        batch = TaskBatch(batch_id="explicit", tasks=tasks, batch_size=3)
        assert batch.batch_size == 3

    def test_empty_tasks(self) -> None:
        """Test TaskBatch with empty task list."""
        batch = TaskBatch(batch_id="empty", tasks=[])
        assert batch.batch_size == 0
        assert batch.common_image is None
        assert batch.common_repo is None


# ===========================================================================
# BatchSavings dataclass tests
# ===========================================================================


class TestBatchSavings:
    """Tests for the BatchSavings dataclass."""

    def test_default_values(self) -> None:
        """Test that defaults are all zeros."""
        savings = BatchSavings()
        assert savings.total_batches == 0
        assert savings.avg_batch_size == 0.0
        assert savings.estimated_container_reuse == 0
        assert savings.estimated_time_saved_seconds == 0.0

    def test_custom_values(self) -> None:
        """Test creation with custom values."""
        savings = BatchSavings(
            total_batches=5,
            avg_batch_size=4.0,
            estimated_container_reuse=15,
            estimated_time_saved_seconds=450.0,
        )
        assert savings.total_batches == 5
        assert savings.avg_batch_size == 4.0
        assert savings.estimated_container_reuse == 15
        assert savings.estimated_time_saved_seconds == 450.0


# ===========================================================================
# TaskBatcher initialization tests
# ===========================================================================


class TestTaskBatcherInit:
    """Tests for TaskBatcher initialization and validation."""

    def test_default_init(self) -> None:
        """Test default initialization values."""
        batcher = TaskBatcher()
        assert batcher.strategy == BatchStrategy.BY_REPO
        assert batcher.max_batch_size == 10
        assert batcher.min_batch_size == 2

    def test_custom_init(self) -> None:
        """Test custom initialization values."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.BY_IMAGE,
            max_batch_size=20,
            min_batch_size=5,
        )
        assert batcher.strategy == BatchStrategy.BY_IMAGE
        assert batcher.max_batch_size == 20
        assert batcher.min_batch_size == 5

    def test_max_batch_size_below_one_raises(self) -> None:
        """Test that max_batch_size < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_batch_size must be >= 1"):
            TaskBatcher(max_batch_size=0)

    def test_min_batch_size_below_one_raises(self) -> None:
        """Test that min_batch_size < 1 raises ValueError."""
        with pytest.raises(ValueError, match="min_batch_size must be >= 1"):
            TaskBatcher(min_batch_size=0)

    def test_min_exceeds_max_raises(self) -> None:
        """Test that min_batch_size > max_batch_size raises ValueError."""
        with pytest.raises(ValueError, match="min_batch_size.*must be <= max_batch_size"):
            TaskBatcher(max_batch_size=3, min_batch_size=5)

    def test_min_equals_max_ok(self) -> None:
        """Test that min_batch_size == max_batch_size is valid."""
        batcher = TaskBatcher(max_batch_size=5, min_batch_size=5)
        assert batcher.min_batch_size == 5
        assert batcher.max_batch_size == 5


# ===========================================================================
# BY_REPO strategy tests
# ===========================================================================


class TestBatchByRepo:
    """Tests for BY_REPO batching strategy."""

    def test_empty_tasks(self) -> None:
        """Test batching empty task list returns empty."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO)
        assert batcher.batch([]) == []

    def test_single_repo(self) -> None:
        """Test all tasks with same repo go into one batch."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=20)
        tasks = _make_tasks(5, repo="org/repo1")
        batches = batcher.batch(tasks)
        assert len(batches) == 1
        assert batches[0].batch_size == 5
        assert batches[0].common_repo == "org/repo1"

    def test_multiple_repos(self) -> None:
        """Test tasks with different repos go into separate batches."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=20)
        tasks = _make_tasks(3, repo="org/repo1") + _make_tasks(2, repo="org/repo2")
        batches = batcher.batch(tasks)
        assert len(batches) == 2
        # Sorted by size descending
        assert batches[0].batch_size == 3
        assert batches[0].common_repo == "org/repo1"
        assert batches[1].batch_size == 2
        assert batches[1].common_repo == "org/repo2"

    def test_repo_batch_respects_max_size(self) -> None:
        """Test that large repo groups are split into multiple batches."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=3)
        tasks = _make_tasks(7, repo="org/big-repo")
        batches = batcher.batch(tasks)
        # 7 tasks / max 3 = 3 batches (3, 3, 1)
        assert len(batches) == 3
        sizes = sorted([b.batch_size for b in batches], reverse=True)
        assert sizes == [3, 3, 1]

    def test_missing_repo_field_groups_as_ungrouped(self) -> None:
        """Test tasks without repo field are grouped under _ungrouped_."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=20)
        tasks = _make_tasks(3)  # no repo field
        batches = batcher.batch(tasks)
        assert len(batches) == 1
        assert batches[0].common_repo is None

    def test_all_tasks_preserved(self) -> None:
        """Test that every input task appears in exactly one batch."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=3)
        tasks = _make_varied_tasks()
        batches = batcher.batch(tasks)
        all_ids = set()
        for b in batches:
            for t in b.tasks:
                all_ids.add(t["instance_id"])
        original_ids = {t["instance_id"] for t in tasks}
        assert all_ids == original_ids

    def test_batches_sorted_by_size_descending(self) -> None:
        """Test batches are returned largest first."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=20)
        tasks = (
            _make_tasks(2, repo="small/repo")
            + _make_tasks(5, repo="big/repo")
            + _make_tasks(3, repo="mid/repo")
        )
        batches = batcher.batch(tasks)
        sizes = [b.batch_size for b in batches]
        assert sizes == sorted(sizes, reverse=True)


# ===========================================================================
# BY_IMAGE strategy tests
# ===========================================================================


class TestBatchByImage:
    """Tests for BY_IMAGE batching strategy."""

    def test_single_image(self) -> None:
        """Test all tasks sharing an image grouped together."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_IMAGE, max_batch_size=20)
        tasks = _make_tasks(4, image="python:3.11-slim")
        batches = batcher.batch(tasks)
        assert len(batches) == 1
        assert batches[0].common_image == "python:3.11-slim"

    def test_multiple_images(self) -> None:
        """Test tasks with different images go into separate batches."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_IMAGE, max_batch_size=20)
        tasks = _make_tasks(3, image="python:3.11") + _make_tasks(2, image="python:3.12")
        batches = batcher.batch(tasks)
        assert len(batches) == 2
        images = {b.common_image for b in batches}
        assert images == {"python:3.11", "python:3.12"}

    def test_image_split_on_max_size(self) -> None:
        """Test that large image groups are split correctly."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_IMAGE, max_batch_size=4)
        tasks = _make_tasks(9, image="ubuntu:22.04")
        batches = batcher.batch(tasks)
        # 9 / 4 = 3 batches (4, 4, 1)
        assert len(batches) == 3
        assert all(b.common_image == "ubuntu:22.04" for b in batches)


# ===========================================================================
# BY_CATEGORY strategy tests
# ===========================================================================


class TestBatchByCategory:
    """Tests for BY_CATEGORY batching strategy."""

    def test_single_category(self) -> None:
        """Test all tasks in same category grouped together."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_CATEGORY, max_batch_size=20)
        tasks = _make_tasks(3, category="web")
        batches = batcher.batch(tasks)
        assert len(batches) == 1

    def test_multiple_categories(self) -> None:
        """Test tasks in different categories form separate batches."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_CATEGORY, max_batch_size=20)
        tasks = (
            _make_tasks(2, category="web")
            + _make_tasks(3, category="math")
            + _make_tasks(1, category="astronomy")
        )
        batches = batcher.batch(tasks)
        assert len(batches) == 3

    def test_missing_category_groups_together(self) -> None:
        """Test tasks without category field are grouped under _ungrouped_."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_CATEGORY, max_batch_size=20)
        tasks = _make_tasks(4)  # no category
        batches = batcher.batch(tasks)
        assert len(batches) == 1


# ===========================================================================
# FIXED_SIZE strategy tests
# ===========================================================================


class TestBatchFixedSize:
    """Tests for FIXED_SIZE batching strategy."""

    def test_exact_split(self) -> None:
        """Test tasks that divide evenly into max_batch_size chunks."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=5)
        tasks = _make_tasks(10)
        batches = batcher.batch(tasks)
        assert len(batches) == 2
        assert all(b.batch_size == 5 for b in batches)

    def test_remainder(self) -> None:
        """Test tasks that don't divide evenly produce a smaller final batch."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=4)
        tasks = _make_tasks(7)
        batches = batcher.batch(tasks)
        assert len(batches) == 2
        sizes = sorted([b.batch_size for b in batches], reverse=True)
        assert sizes == [4, 3]

    def test_single_task(self) -> None:
        """Test a single task produces a single batch of size 1."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=5)
        tasks = _make_tasks(1)
        batches = batcher.batch(tasks)
        assert len(batches) == 1
        assert batches[0].batch_size == 1

    def test_max_batch_size_one(self) -> None:
        """Test max_batch_size=1 puts each task in its own batch."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.FIXED_SIZE,
            max_batch_size=1,
            min_batch_size=1,
        )
        tasks = _make_tasks(4)
        batches = batcher.batch(tasks)
        assert len(batches) == 4
        assert all(b.batch_size == 1 for b in batches)

    def test_preserves_task_order(self) -> None:
        """Test that FIXED_SIZE preserves the original task order within batches."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=3)
        tasks = _make_tasks(6)
        batches = batcher.batch(tasks)
        all_ids = []
        for b in batches:
            for t in b.tasks:
                all_ids.append(t["instance_id"])
        expected = [f"task_{i}" for i in range(6)]
        assert all_ids == expected

    def test_common_fields_detected(self) -> None:
        """Test common_repo and common_image detected when tasks happen to share them."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=3)
        tasks = _make_tasks(3, repo="org/repo", image="img:latest")
        batches = batcher.batch(tasks)
        assert len(batches) == 1
        assert batches[0].common_repo == "org/repo"
        assert batches[0].common_image == "img:latest"

    def test_mixed_fields_no_common(self) -> None:
        """Test that mixed fields result in None for common_repo/common_image."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=10)
        tasks = _make_varied_tasks()  # 12 tasks with mixed repos/images
        batches = batcher.batch(tasks)
        # 12 tasks with max_batch_size=10 produces 2 batches (10 + 2)
        assert len(batches) == 2
        # First batch of 10 has mixed repos/images
        assert batches[0].common_repo is None
        assert batches[0].common_image is None


# ===========================================================================
# ADAPTIVE strategy tests
# ===========================================================================


class TestBatchAdaptive:
    """Tests for ADAPTIVE batching strategy."""

    def test_high_similarity_larger_batches(self) -> None:
        """Test that tasks sharing all fields get larger batch sizes."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.ADAPTIVE,
            max_batch_size=10,
            min_batch_size=2,
        )
        # All share repo, image, and category (3/3 similarity)
        tasks = _make_tasks(8, repo="org/repo", image="img:v1", category="web")
        batches = batcher.batch(tasks)
        # With 3/3 similarity, adaptive_max = max_batch_size = 10
        # 8 tasks fit in 1 batch
        assert len(batches) == 1
        assert batches[0].batch_size == 8

    def test_low_similarity_smaller_batches(self) -> None:
        """Test that tasks with no shared fields get min-sized batches."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.ADAPTIVE,
            max_batch_size=10,
            min_batch_size=2,
        )
        # No repo, image, or category -> 0/3 similarity -> adaptive_max = min_batch_size = 2
        tasks = _make_tasks(6)
        batches = batcher.batch(tasks)
        # All tasks map to the same composite key "_|_|_" with adaptive_max=2
        # 6 tasks / 2 = 3 batches
        assert len(batches) == 3
        assert all(b.batch_size == 2 for b in batches)

    def test_partial_similarity_medium_batches(self) -> None:
        """Test tasks sharing some fields get medium-sized batches."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.ADAPTIVE,
            max_batch_size=12,
            min_batch_size=2,
        )
        # Share repo only (1/3 similarity) -> adaptive_max = 2 + (12-2)*1/3 ~= 5
        tasks = _make_tasks(10, repo="org/repo")
        batches = batcher.batch(tasks)
        # adaptive_max = 2 + int(10 * 1/3) = 2 + 3 = 5
        # 10 tasks / 5 = 2 batches
        assert len(batches) == 2
        assert all(b.batch_size == 5 for b in batches)

    def test_adaptive_all_tasks_preserved(self) -> None:
        """Test that adaptive batching preserves all tasks."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.ADAPTIVE,
            max_batch_size=10,
            min_batch_size=2,
        )
        tasks = _make_varied_tasks()
        batches = batcher.batch(tasks)
        all_ids = set()
        for b in batches:
            for t in b.tasks:
                all_ids.add(t["instance_id"])
        original_ids = {t["instance_id"] for t in tasks}
        assert all_ids == original_ids

    def test_adaptive_sorted_by_size(self) -> None:
        """Test that adaptive batches are sorted largest first."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.ADAPTIVE,
            max_batch_size=10,
            min_batch_size=2,
        )
        tasks = _make_varied_tasks()
        batches = batcher.batch(tasks)
        sizes = [b.batch_size for b in batches]
        assert sizes == sorted(sizes, reverse=True)

    def test_adaptive_mixed_groups(self) -> None:
        """Test adaptive with tasks forming multiple composite groups."""
        batcher = TaskBatcher(
            strategy=BatchStrategy.ADAPTIVE,
            max_batch_size=10,
            min_batch_size=2,
        )
        # Create tasks that form different composite groups
        tasks = [
            {"instance_id": "t1", "repo": "r1", "image": "i1", "category": "c1"},
            {"instance_id": "t2", "repo": "r1", "image": "i1", "category": "c1"},
            {"instance_id": "t3", "repo": "r2", "image": "i2", "category": "c2"},
            {"instance_id": "t4", "repo": "r2", "image": "i2", "category": "c2"},
        ]
        batches = batcher.batch(tasks)
        # Each group has 3/3 similarity -> adaptive_max = 10
        # 2 groups of 2 tasks each
        assert len(batches) == 2
        assert all(b.batch_size == 2 for b in batches)


# ===========================================================================
# estimate_savings tests
# ===========================================================================


class TestEstimateSavings:
    """Tests for the estimate_savings method."""

    def test_empty_batches(self) -> None:
        """Test savings estimation with no batches."""
        batcher = TaskBatcher()
        savings = batcher.estimate_savings([])
        assert savings == BatchSavings()

    def test_single_batch_of_one(self) -> None:
        """Test no savings for a single task in a single batch."""
        batcher = TaskBatcher()
        batch = TaskBatch(batch_id="b1", tasks=_make_tasks(1), batch_size=1)
        savings = batcher.estimate_savings([batch])
        assert savings.total_batches == 1
        assert savings.avg_batch_size == 1.0
        assert savings.estimated_container_reuse == 0
        assert savings.estimated_time_saved_seconds == 0.0

    def test_savings_calculation(self) -> None:
        """Test correct savings calculation for multiple batches."""
        batcher = TaskBatcher()
        batches = [
            TaskBatch(batch_id="b1", tasks=_make_tasks(5), batch_size=5),
            TaskBatch(batch_id="b2", tasks=_make_tasks(3), batch_size=3),
        ]
        savings = batcher.estimate_savings(batches)
        assert savings.total_batches == 2
        assert savings.avg_batch_size == 4.0
        # 8 total tasks - 2 batches = 6 container reuses
        assert savings.estimated_container_reuse == 6
        expected_time = 6 * _CONTAINER_RESTART_OVERHEAD_SECONDS
        assert savings.estimated_time_saved_seconds == expected_time

    def test_all_single_task_batches_no_savings(self) -> None:
        """Test that single-task batches yield zero savings."""
        batcher = TaskBatcher()
        batches = [
            TaskBatch(batch_id=f"b{i}", tasks=_make_tasks(1), batch_size=1) for i in range(5)
        ]
        savings = batcher.estimate_savings(batches)
        assert savings.estimated_container_reuse == 0
        assert savings.estimated_time_saved_seconds == 0.0
        assert savings.total_batches == 5
        assert savings.avg_batch_size == 1.0


# ===========================================================================
# preview tests
# ===========================================================================


class TestPreview:
    """Tests for the preview method."""

    def test_empty_preview(self) -> None:
        """Test preview with no batches."""
        batcher = TaskBatcher()
        assert batcher.preview([]) == "No batches to preview."

    def test_preview_contains_strategy(self) -> None:
        """Test that preview output includes the strategy name."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO)
        batches = [TaskBatch(batch_id="b1", tasks=_make_tasks(3), batch_size=3)]
        preview = batcher.preview(batches)
        assert "by_repo" in preview

    def test_preview_contains_batch_info(self) -> None:
        """Test that preview contains batch count and size info."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE)
        batches = [
            TaskBatch(
                batch_id="b1",
                tasks=_make_tasks(3, repo="org/repo"),
                batch_size=3,
                common_repo="org/repo",
            ),
        ]
        preview = batcher.preview(batches)
        assert "Total batches: 1" in preview
        assert "Batch 1: 3 tasks" in preview
        assert "repo=org/repo" in preview

    def test_preview_truncates_long_batches(self) -> None:
        """Test that batches with more than 5 tasks show truncation."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE)
        tasks = _make_tasks(8)
        batches = [TaskBatch(batch_id="b1", tasks=tasks, batch_size=8)]
        preview = batcher.preview(batches)
        assert "+3 more" in preview

    def test_preview_shows_savings(self) -> None:
        """Test that preview includes time saved information."""
        batcher = TaskBatcher()
        batches = [
            TaskBatch(batch_id="b1", tasks=_make_tasks(5), batch_size=5),
        ]
        preview = batcher.preview(batches)
        assert "Estimated time saved:" in preview
        assert "Estimated container reuse:" in preview

    def test_preview_mixed_label(self) -> None:
        """Test that batches with no common fields show 'mixed'."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE)
        tasks = [
            {"instance_id": "t1", "repo": "r1"},
            {"instance_id": "t2", "repo": "r2"},
        ]
        batches = [TaskBatch(batch_id="b1", tasks=tasks, batch_size=2)]
        preview = batcher.preview(batches)
        assert "mixed" in preview


# ===========================================================================
# Batch ID uniqueness tests
# ===========================================================================


class TestBatchIdUniqueness:
    """Tests to verify batch IDs are unique."""

    def test_unique_ids_by_repo(self) -> None:
        """Test that BY_REPO batches have unique IDs."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=2)
        tasks = _make_varied_tasks()
        batches = batcher.batch(tasks)
        ids = [b.batch_id for b in batches]
        assert len(ids) == len(set(ids))

    def test_unique_ids_fixed_size(self) -> None:
        """Test that FIXED_SIZE batches have unique IDs."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=2)
        tasks = _make_tasks(10)
        batches = batcher.batch(tasks)
        ids = [b.batch_id for b in batches]
        assert len(ids) == len(set(ids))


# ===========================================================================
# Edge cases and fallback tests
# ===========================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_task(self) -> None:
        """Test batching a single task."""
        for strategy in BatchStrategy:
            batcher = TaskBatcher(strategy=strategy, max_batch_size=10, min_batch_size=1)
            tasks = _make_tasks(1, repo="org/r", image="img", category="cat")
            batches = batcher.batch(tasks)
            assert len(batches) >= 1
            total = sum(b.batch_size for b in batches)
            assert total == 1

    def test_large_task_list(self) -> None:
        """Test batching a large number of tasks."""
        batcher = TaskBatcher(strategy=BatchStrategy.FIXED_SIZE, max_batch_size=50)
        tasks = _make_tasks(500)
        batches = batcher.batch(tasks)
        assert len(batches) == 10
        total = sum(b.batch_size for b in batches)
        assert total == 500

    def test_all_strategies_preserve_task_count(self) -> None:
        """Test every strategy preserves the total task count."""
        tasks = _make_varied_tasks()
        for strategy in BatchStrategy:
            batcher = TaskBatcher(strategy=strategy, max_batch_size=5, min_batch_size=1)
            batches = batcher.batch(tasks)
            total = sum(b.batch_size for b in batches)
            assert total == len(tasks), f"Strategy {strategy.value} lost tasks"

    def test_batch_estimated_savings_per_batch(self) -> None:
        """Test that individual batch savings are set correctly."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=20)
        tasks = _make_tasks(5, repo="org/repo")
        batches = batcher.batch(tasks)
        assert len(batches) == 1
        # 5 tasks in one batch -> 4 restarts avoided
        expected = 4 * _CONTAINER_RESTART_OVERHEAD_SECONDS
        assert batches[0].estimated_savings_seconds == expected

    def test_single_task_no_savings(self) -> None:
        """Test that a single-task batch has zero estimated savings."""
        batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=20)
        tasks = _make_tasks(1, repo="org/repo")
        batches = batcher.batch(tasks)
        assert len(batches) == 1
        assert batches[0].estimated_savings_seconds == 0.0

    def test_tasks_without_any_grouping_fields(self) -> None:
        """Test that tasks with no grouping fields are handled gracefully."""
        for strategy in BatchStrategy:
            batcher = TaskBatcher(strategy=strategy, max_batch_size=5, min_batch_size=1)
            tasks = [{"instance_id": f"t{i}"} for i in range(8)]
            batches = batcher.batch(tasks)
            total = sum(b.batch_size for b in batches)
            assert total == 8, f"Strategy {strategy.value} lost tasks with no fields"

    def test_common_value_with_all_none(self) -> None:
        """Test _common_value returns None when no tasks have the field."""
        result = TaskBatcher._common_value([{"a": 1}, {"b": 2}], "missing")
        assert result is None

    def test_common_value_with_single_task(self) -> None:
        """Test _common_value with a single task."""
        result = TaskBatcher._common_value([{"repo": "org/r"}], "repo")
        assert result == "org/r"

    def test_common_value_with_mixed_values(self) -> None:
        """Test _common_value returns None when values differ."""
        tasks = [{"repo": "r1"}, {"repo": "r2"}]
        result = TaskBatcher._common_value(tasks, "repo")
        assert result is None

    def test_common_value_empty_list(self) -> None:
        """Test _common_value returns None for empty list."""
        result = TaskBatcher._common_value([], "repo")
        assert result is None
