"""Task batching with smart scheduling for efficient batch execution.

Groups similar benchmark tasks to minimize Docker container restarts and
maximize resource reuse. Supports multiple batching strategies including
repo-based, image-based, category-based, fixed-size, and adaptive grouping.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Estimated overhead per Docker container restart in seconds
_CONTAINER_RESTART_OVERHEAD_SECONDS = 30.0


class BatchStrategy(Enum):
    """Strategy for grouping tasks into batches.

    Attributes:
        BY_REPO: Group tasks that share the same repository.
        BY_IMAGE: Group tasks that require the same Docker image.
        BY_CATEGORY: Group tasks that belong to the same benchmark category.
        FIXED_SIZE: Split tasks into fixed-size chunks regardless of similarity.
        ADAPTIVE: Dynamically size batches based on task similarity signals.
    """

    BY_REPO = "by_repo"
    BY_IMAGE = "by_image"
    BY_CATEGORY = "by_category"
    FIXED_SIZE = "fixed_size"
    ADAPTIVE = "adaptive"


@dataclass
class TaskBatch:
    """A batch of grouped tasks for efficient execution.

    Attributes:
        batch_id: Unique identifier for this batch.
        tasks: List of task dictionaries in this batch.
        common_image: Shared Docker image if all tasks use the same one, else None.
        common_repo: Shared repository if all tasks target the same repo, else None.
        batch_size: Number of tasks in this batch.
        estimated_savings_seconds: Estimated time saved by batching vs individual execution.
    """

    batch_id: str
    tasks: list[dict[str, Any]]
    common_image: str | None = None
    common_repo: str | None = None
    batch_size: int = 0
    estimated_savings_seconds: float = 0.0

    def __post_init__(self) -> None:
        """Compute batch_size from tasks if not explicitly set."""
        if self.batch_size == 0 and self.tasks:
            self.batch_size = len(self.tasks)


@dataclass
class BatchSavings:
    """Estimated savings from batching tasks.

    Attributes:
        total_batches: Total number of batches created.
        avg_batch_size: Average number of tasks per batch.
        estimated_container_reuse: Number of container restarts avoided.
        estimated_time_saved_seconds: Total estimated time saved in seconds.
    """

    total_batches: int = 0
    avg_batch_size: float = 0.0
    estimated_container_reuse: int = 0
    estimated_time_saved_seconds: float = 0.0


class TaskBatcher:
    """Groups benchmark tasks into batches for efficient execution.

    Batching reduces Docker container restarts by grouping tasks that share
    common requirements (repository, image, category). Supports multiple
    strategies and configurable batch sizes.

    Args:
        strategy: Batching strategy to use.
        max_batch_size: Maximum number of tasks per batch.
        min_batch_size: Minimum number of tasks to form a batch. Groups smaller
            than this are still returned as batches (no tasks are dropped).

    Example:
        >>> batcher = TaskBatcher(strategy=BatchStrategy.BY_REPO, max_batch_size=5)
        >>> tasks = [{"instance_id": "t1", "repo": "org/repo1"}, ...]
        >>> batches = batcher.batch(tasks)
        >>> print(batcher.preview(batches))
    """

    def __init__(
        self,
        strategy: BatchStrategy = BatchStrategy.BY_REPO,
        max_batch_size: int = 10,
        min_batch_size: int = 2,
    ) -> None:
        """Initialize the TaskBatcher.

        Args:
            strategy: Batching strategy to use.
            max_batch_size: Maximum number of tasks per batch.
            min_batch_size: Minimum number of tasks to form a batch.

        Raises:
            ValueError: If max_batch_size < 1 or min_batch_size < 1 or
                min_batch_size > max_batch_size.
        """
        if max_batch_size < 1:
            raise ValueError(f"max_batch_size must be >= 1, got {max_batch_size}")
        if min_batch_size < 1:
            raise ValueError(f"min_batch_size must be >= 1, got {min_batch_size}")
        if min_batch_size > max_batch_size:
            raise ValueError(
                f"min_batch_size ({min_batch_size}) must be <= max_batch_size ({max_batch_size})"
            )
        self.strategy = strategy
        self.max_batch_size = max_batch_size
        self.min_batch_size = min_batch_size

    def batch(self, tasks: list[dict[str, Any]]) -> list[TaskBatch]:
        """Group tasks into batches using the configured strategy.

        Args:
            tasks: List of task dictionaries to batch. Each task should have
                at minimum an ``instance_id`` key. Depending on the strategy,
                ``repo``, ``image``, and ``category`` fields are also used.

        Returns:
            List of TaskBatch objects. Every input task appears in exactly one
            batch. Batches are sorted by descending size for scheduling efficiency.
        """
        if not tasks:
            return []

        if self.strategy == BatchStrategy.BY_REPO:
            return self._batch_by_field(tasks, "repo")
        elif self.strategy == BatchStrategy.BY_IMAGE:
            return self._batch_by_field(tasks, "image")
        elif self.strategy == BatchStrategy.BY_CATEGORY:
            return self._batch_by_field(tasks, "category")
        elif self.strategy == BatchStrategy.FIXED_SIZE:
            return self._batch_fixed_size(tasks)
        elif self.strategy == BatchStrategy.ADAPTIVE:
            return self._batch_adaptive(tasks)
        else:
            raise ValueError(f"Unknown batch strategy: {self.strategy}")

    def estimate_savings(self, batches: list[TaskBatch]) -> BatchSavings:
        """Estimate time saved by batching compared to individual execution.

        The savings come primarily from container reuse: tasks in the same batch
        can share a Docker container instead of each requiring a fresh one.

        Args:
            batches: List of TaskBatch objects to analyze.

        Returns:
            BatchSavings with estimated metrics.
        """
        if not batches:
            return BatchSavings()

        total_tasks = sum(b.batch_size for b in batches)
        total_batches = len(batches)
        avg_batch_size = total_tasks / total_batches if total_batches > 0 else 0.0

        # Without batching, each task needs its own container restart.
        # With batching, only the first task in each batch needs a restart.
        container_reuse = total_tasks - total_batches
        time_saved = container_reuse * _CONTAINER_RESTART_OVERHEAD_SECONDS

        return BatchSavings(
            total_batches=total_batches,
            avg_batch_size=round(avg_batch_size, 2),
            estimated_container_reuse=container_reuse,
            estimated_time_saved_seconds=round(time_saved, 2),
        )

    def preview(self, batches: list[TaskBatch]) -> str:
        """Generate a formatted preview of the batching plan.

        Args:
            batches: List of TaskBatch objects to preview.

        Returns:
            Human-readable string summarizing the batches and estimated savings.
        """
        if not batches:
            return "No batches to preview."

        savings = self.estimate_savings(batches)
        lines: list[str] = []
        lines.append(f"Batch Plan ({self.strategy.value})")
        lines.append("=" * 50)
        lines.append(f"Total batches: {savings.total_batches}")
        lines.append(f"Average batch size: {savings.avg_batch_size}")
        lines.append(f"Estimated container reuse: {savings.estimated_container_reuse}")
        lines.append(f"Estimated time saved: {savings.estimated_time_saved_seconds:.1f}s")
        lines.append("")

        for i, b in enumerate(batches, 1):
            label_parts: list[str] = []
            if b.common_repo:
                label_parts.append(f"repo={b.common_repo}")
            if b.common_image:
                label_parts.append(f"image={b.common_image}")
            label = ", ".join(label_parts) if label_parts else "mixed"

            lines.append(f"  Batch {i}: {b.batch_size} tasks ({label})")
            task_ids = [t.get("instance_id", "?") for t in b.tasks[:5]]
            if b.batch_size > 5:
                task_ids.append(f"... +{b.batch_size - 5} more")
            for tid in task_ids:
                lines.append(f"    - {tid}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _batch_by_field(self, tasks: list[dict[str, Any]], field_name: str) -> list[TaskBatch]:
        """Group tasks by a shared field, then split into max-sized chunks.

        Args:
            tasks: List of task dictionaries.
            field_name: Key to group tasks by (e.g. "repo", "image", "category").

        Returns:
            Sorted list of TaskBatch objects.
        """
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            key = str(task.get(field_name, "_ungrouped_"))
            groups[key].append(task)

        batches: list[TaskBatch] = []
        for _key, group_tasks in sorted(groups.items()):
            for chunk in self._split_into_chunks(group_tasks):
                common_image = self._common_value(chunk, "image")
                common_repo = self._common_value(chunk, "repo")
                savings = self._estimate_batch_savings(len(chunk))
                batches.append(
                    TaskBatch(
                        batch_id=str(uuid.uuid4()),
                        tasks=chunk,
                        common_image=common_image,
                        common_repo=common_repo,
                        batch_size=len(chunk),
                        estimated_savings_seconds=savings,
                    )
                )

        # Sort largest first for better scheduling
        batches.sort(key=lambda b: b.batch_size, reverse=True)
        return batches

    def _batch_fixed_size(self, tasks: list[dict[str, Any]]) -> list[TaskBatch]:
        """Split tasks into fixed-size chunks.

        Args:
            tasks: List of task dictionaries.

        Returns:
            Sorted list of TaskBatch objects.
        """
        batches: list[TaskBatch] = []
        for chunk in self._split_into_chunks(tasks):
            common_image = self._common_value(chunk, "image")
            common_repo = self._common_value(chunk, "repo")
            savings = self._estimate_batch_savings(len(chunk))
            batches.append(
                TaskBatch(
                    batch_id=str(uuid.uuid4()),
                    tasks=chunk,
                    common_image=common_image,
                    common_repo=common_repo,
                    batch_size=len(chunk),
                    estimated_savings_seconds=savings,
                )
            )
        return batches

    def _batch_adaptive(self, tasks: list[dict[str, Any]]) -> list[TaskBatch]:
        """Adaptively group tasks based on multi-field similarity.

        Tasks are first grouped by a composite key of all available grouping
        fields (repo, image, category). Groups that share more fields get
        larger batch sizes (up to max_batch_size). Groups with no shared
        fields get smaller batches (down toward min_batch_size).

        Args:
            tasks: List of task dictionaries.

        Returns:
            Sorted list of TaskBatch objects.
        """
        # Build composite similarity groups
        similarity_fields = ["repo", "image", "category"]
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            parts = []
            for f in similarity_fields:
                parts.append(str(task.get(f, "_")))
            key = "|".join(parts)
            groups[key].append(task)

        batches: list[TaskBatch] = []
        for key, group_tasks in sorted(groups.items()):
            # Determine how many fields are shared (non-default)
            key_parts = key.split("|")
            shared_count = sum(1 for p in key_parts if p != "_")

            # Scale batch size based on similarity: more shared fields -> larger batches
            similarity_ratio = shared_count / len(similarity_fields) if similarity_fields else 0
            adaptive_max = self.min_batch_size + int(
                (self.max_batch_size - self.min_batch_size) * similarity_ratio
            )
            adaptive_max = max(adaptive_max, self.min_batch_size)

            for chunk in self._split_into_chunks(group_tasks, max_size=adaptive_max):
                common_image = self._common_value(chunk, "image")
                common_repo = self._common_value(chunk, "repo")
                savings = self._estimate_batch_savings(len(chunk))
                batches.append(
                    TaskBatch(
                        batch_id=str(uuid.uuid4()),
                        tasks=chunk,
                        common_image=common_image,
                        common_repo=common_repo,
                        batch_size=len(chunk),
                        estimated_savings_seconds=savings,
                    )
                )

        batches.sort(key=lambda b: b.batch_size, reverse=True)
        return batches

    def _split_into_chunks(
        self,
        tasks: list[dict[str, Any]],
        max_size: int | None = None,
    ) -> list[list[dict[str, Any]]]:
        """Split a list of tasks into chunks of at most max_size.

        Args:
            tasks: Tasks to split.
            max_size: Override for maximum chunk size. Defaults to self.max_batch_size.

        Returns:
            List of task sublists.
        """
        size = max_size if max_size is not None else self.max_batch_size
        if size < 1:
            size = 1
        chunks: list[list[dict[str, Any]]] = []
        for i in range(0, len(tasks), size):
            chunks.append(tasks[i : i + size])
        return chunks

    @staticmethod
    def _common_value(tasks: list[dict[str, Any]], field_name: str) -> str | None:
        """Return the shared value for a field if all tasks agree, else None.

        Args:
            tasks: List of task dictionaries.
            field_name: Key to check.

        Returns:
            The common value string, or None if tasks differ or field is absent.
        """
        if not tasks:
            return None
        values = {t.get(field_name) for t in tasks}
        values.discard(None)
        if len(values) == 1:
            return str(values.pop())
        return None

    @staticmethod
    def _estimate_batch_savings(batch_size: int) -> float:
        """Estimate time saved for a single batch.

        Each additional task in a batch beyond the first avoids one container
        restart.

        Args:
            batch_size: Number of tasks in the batch.

        Returns:
            Estimated time saved in seconds.
        """
        if batch_size <= 1:
            return 0.0
        return (batch_size - 1) * _CONTAINER_RESTART_OVERHEAD_SECONDS
