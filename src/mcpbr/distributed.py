"""Distributed execution coordinator for running evaluations across multiple workers.

Splits evaluation tasks across multiple machines/processes, coordinates execution,
and merges results. Supports local multi-process and cloud infrastructure providers
(AWS, GCP, Kubernetes, Azure) via the existing InfrastructureConfig.

See: https://github.com/greynewell/mcpbr/issues/116
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .config import HarnessConfig
from .harness import EvaluationResults, TaskResult

logger = logging.getLogger(__name__)

# Valid infrastructure providers for distributed execution.
SUPPORTED_PROVIDERS = ("local", "aws", "gcp", "kubernetes", "azure")


class TaskPartitioner:
    """Splits evaluation tasks into chunks for distribution across workers."""

    @staticmethod
    def partition(task_ids: list[str], num_workers: int) -> list[list[str]]:
        """Split task IDs evenly across workers using round-robin assignment.

        Each worker receives approximately the same number of tasks. When the
        number of tasks does not divide evenly, earlier workers receive one
        extra task.

        Args:
            task_ids: List of task instance IDs to distribute.
            num_workers: Number of workers to distribute across. Must be >= 1.

        Returns:
            List of lists, one per worker, containing that worker's task IDs.
            Empty workers are omitted (e.g., 2 tasks across 5 workers yields
            2 non-empty partitions).

        Raises:
            ValueError: If num_workers < 1.
        """
        if num_workers < 1:
            raise ValueError("num_workers must be at least 1")

        if not task_ids:
            return [[] for _ in range(num_workers)]

        # Cap effective workers at the number of tasks to avoid empty partitions.
        effective_workers = min(num_workers, len(task_ids))
        partitions: list[list[str]] = [[] for _ in range(effective_workers)]

        for i, task_id in enumerate(task_ids):
            partitions[i % effective_workers].append(task_id)

        return partitions

    @staticmethod
    def partition_by_difficulty(tasks: list[dict[str, Any]], num_workers: int) -> list[list[str]]:
        """Split tasks trying to balance estimated difficulty/cost across workers.

        Tasks are sorted by a difficulty heuristic (derived from the ``difficulty``
        or ``estimated_cost`` fields when present, falling back to 1.0) and then
        assigned to the worker with the current lowest total weight. This is a
        classic greedy multiprocessor scheduling approximation (LPT algorithm).

        Args:
            tasks: List of task dictionaries. Each must have an ``instance_id``
                key. Optionally ``difficulty`` (numeric) or ``estimated_cost``
                (numeric) for weighting.
            num_workers: Number of workers to distribute across. Must be >= 1.

        Returns:
            List of lists of task IDs, one per worker, balanced by estimated
            difficulty. Empty workers are omitted when there are fewer tasks
            than workers.

        Raises:
            ValueError: If num_workers < 1.
        """
        if num_workers < 1:
            raise ValueError("num_workers must be at least 1")

        if not tasks:
            return [[] for _ in range(num_workers)]

        effective_workers = min(num_workers, len(tasks))

        # Assign a weight to each task for balancing.
        weighted: list[tuple[str, float]] = []
        for task in tasks:
            task_id = task["instance_id"]
            weight = float(task.get("difficulty", task.get("estimated_cost", 1.0)))
            weighted.append((task_id, weight))

        # Sort heaviest first for best greedy approximation (LPT).
        weighted.sort(key=lambda x: x[1], reverse=True)

        # Greedy assignment: always give the next task to the lightest worker.
        partitions: list[list[str]] = [[] for _ in range(effective_workers)]
        loads: list[float] = [0.0] * effective_workers

        for task_id, weight in weighted:
            lightest = loads.index(min(loads))
            partitions[lightest].append(task_id)
            loads[lightest] += weight

        return partitions


@dataclass
class WorkerResult:
    """Result returned by a single distributed worker.

    Attributes:
        worker_id: Unique identifier for the worker.
        task_results: List of per-task result dictionaries produced by the worker.
        duration_seconds: Wall-clock seconds the worker spent executing.
        error: Error message if the worker failed, None on success.
    """

    worker_id: str
    task_results: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str | None = None


class DistributedCoordinator:
    """Coordinates distributed evaluation across multiple infrastructure providers.

    The coordinator partitions the evaluation workload, launches workers
    concurrently, and merges the results into a single ``EvaluationResults``
    object that is compatible with the rest of the reporting pipeline.

    Args:
        config: The harness configuration. Must include an ``mcp_server`` (or
            comparison-mode servers) and a valid ``infrastructure`` section.
        num_workers: Number of parallel workers to use. Defaults to 2.
    """

    def __init__(self, config: HarnessConfig, num_workers: int = 2) -> None:
        if num_workers < 1:
            raise ValueError("num_workers must be at least 1")

        self.config = config
        self.num_workers = num_workers
        self._provider = config.infrastructure.mode

    @property
    def provider(self) -> str:
        """Return the infrastructure provider name (e.g. 'local', 'aws')."""
        return self._provider

    async def run(
        self,
        run_mcp: bool = True,
        run_baseline: bool = False,
        task_ids: list[str] | None = None,
    ) -> EvaluationResults:
        """Run a distributed evaluation.

        Steps:
            1. Determine the task list (from ``task_ids`` or ``config.task_ids``).
            2. Partition tasks across ``num_workers``.
            3. Create a per-worker config clone with the assigned subset.
            4. Launch all workers concurrently via ``asyncio.gather``.
            5. Collect and merge results into a unified ``EvaluationResults``.

        Args:
            run_mcp: Whether to run the MCP evaluation pass.
            run_baseline: Whether to run the baseline (no-MCP) evaluation pass.
            task_ids: Explicit list of task IDs. Falls back to
                ``self.config.task_ids`` if not provided.

        Returns:
            Merged ``EvaluationResults`` combining output from all workers.
        """
        ids = task_ids or self.config.task_ids or []

        if not ids:
            logger.warning(
                "No task_ids provided to DistributedCoordinator.run(); returning empty results."
            )
            return EvaluationResults(
                metadata={"distributed": True, "num_workers": self.num_workers},
                summary={},
                tasks=[],
            )

        partitions = TaskPartitioner.partition(ids, self.num_workers)

        logger.info(
            "Distributing %d tasks across %d workers (provider=%s)",
            len(ids),
            len(partitions),
            self._provider,
        )

        worker_coros = []
        for idx, partition in enumerate(partitions):
            worker_id = f"worker-{idx}"
            worker_coros.append(
                self._launch_worker(
                    worker_id=worker_id,
                    task_ids=partition,
                    run_mcp=run_mcp,
                    run_baseline=run_baseline,
                )
            )

        worker_results: list[WorkerResult] = await asyncio.gather(*worker_coros)

        merged = self.merge_results(worker_results)

        # Build final EvaluationResults
        task_result_objects: list[TaskResult] = []
        for wr in worker_results:
            for tr in wr.task_results:
                instance_id = tr.get("instance_id", "unknown")
                task_result_objects.append(
                    TaskResult(
                        instance_id=instance_id,
                        mcp=tr.get("mcp"),
                        baseline=tr.get("baseline"),
                    )
                )

        return EvaluationResults(
            metadata={
                "distributed": True,
                "num_workers": self.num_workers,
                "provider": self._provider,
                "total_tasks": len(ids),
                "worker_durations": {wr.worker_id: wr.duration_seconds for wr in worker_results},
                "worker_errors": {
                    wr.worker_id: wr.error for wr in worker_results if wr.error is not None
                },
            },
            summary=merged,
            tasks=task_result_objects,
        )

    async def _launch_worker(
        self,
        worker_id: str,
        task_ids: list[str],
        run_mcp: bool = True,
        run_baseline: bool = False,
    ) -> WorkerResult:
        """Launch a single worker with its assigned subset of tasks.

        In the current local-provider implementation this delegates to
        ``harness.run_evaluation`` in-process. Cloud providers will spawn
        remote jobs and poll for results.

        Args:
            worker_id: Unique identifier for the worker.
            task_ids: Task IDs assigned to this worker.
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            ``WorkerResult`` with per-task outputs and timing info.
        """
        if not task_ids:
            return WorkerResult(worker_id=worker_id, duration_seconds=0.0)

        # Build a per-worker config with the assigned task subset.
        worker_config = self._create_worker_config(task_ids)

        start = time.monotonic()
        try:
            from .harness import run_evaluation

            eval_results: EvaluationResults = await run_evaluation(
                worker_config,
                run_mcp=run_mcp,
                run_baseline=run_baseline,
                task_ids=task_ids,
            )

            task_dicts: list[dict[str, Any]] = []
            for tr in eval_results.tasks:
                task_dicts.append(
                    {
                        "instance_id": tr.instance_id,
                        "mcp": tr.mcp,
                        "baseline": tr.baseline,
                    }
                )

            elapsed = time.monotonic() - start
            return WorkerResult(
                worker_id=worker_id,
                task_results=task_dicts,
                duration_seconds=elapsed,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("Worker %s failed: %s", worker_id, exc)
            return WorkerResult(
                worker_id=worker_id,
                duration_seconds=elapsed,
                error=str(exc),
            )

    def _create_worker_config(self, task_ids: list[str]) -> HarnessConfig:
        """Create a deep copy of the coordinator config scoped to specific tasks.

        Args:
            task_ids: The subset of task IDs for this worker.

        Returns:
            A new ``HarnessConfig`` with ``task_ids`` set to the given subset.
        """
        data = self.config.model_dump()
        data["task_ids"] = list(task_ids)
        return HarnessConfig(**data)

    @staticmethod
    def merge_results(worker_results: list[WorkerResult]) -> dict[str, Any]:
        """Merge results from multiple workers into a single summary dictionary.

        Aggregates resolution counts, costs, and token usage across all workers.

        Args:
            worker_results: List of ``WorkerResult`` objects from completed workers.

        Returns:
            Dictionary with merged summary statistics including:
            - total_tasks: Total tasks processed across all workers.
            - total_resolved: Tasks marked as resolved.
            - total_cost: Summed cost across all tasks.
            - total_tokens_in: Summed input tokens.
            - total_tokens_out: Summed output tokens.
            - worker_count: Number of workers that contributed results.
            - total_duration_seconds: Sum of all worker durations.
            - max_duration_seconds: Duration of the slowest worker.
            - errors: List of (worker_id, error) for failed workers.
        """
        total_tasks = 0
        total_resolved = 0
        total_cost = 0.0
        total_tokens_in = 0
        total_tokens_out = 0
        errors: list[dict[str, str]] = []
        durations: list[float] = []

        for wr in worker_results:
            durations.append(wr.duration_seconds)

            if wr.error:
                errors.append({"worker_id": wr.worker_id, "error": wr.error})

            for tr in wr.task_results:
                total_tasks += 1

                # Aggregate from MCP result if present.
                mcp = tr.get("mcp")
                if mcp and isinstance(mcp, dict):
                    if mcp.get("resolved"):
                        total_resolved += 1
                    total_cost += mcp.get("cost", 0.0) or 0.0
                    tokens = mcp.get("tokens", {})
                    total_tokens_in += tokens.get("input", 0)
                    total_tokens_out += tokens.get("output", 0)

                # Also aggregate from baseline if present.
                baseline = tr.get("baseline")
                if baseline and isinstance(baseline, dict):
                    total_cost += baseline.get("cost", 0.0) or 0.0
                    tokens = baseline.get("tokens", {})
                    total_tokens_in += tokens.get("input", 0)
                    total_tokens_out += tokens.get("output", 0)

        return {
            "total_tasks": total_tasks,
            "total_resolved": total_resolved,
            "resolution_rate": (total_resolved / total_tasks if total_tasks > 0 else 0.0),
            "total_cost": total_cost,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "worker_count": len(worker_results),
            "total_duration_seconds": sum(durations),
            "max_duration_seconds": max(durations) if durations else 0.0,
            "errors": errors,
        }
