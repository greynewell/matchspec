"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class StorageBackend(ABC):
    """Abstract base class for result storage backends.

    Storage backends persist benchmark evaluation results for querying,
    comparison, and historical analysis.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend (create tables, etc.)."""
        pass

    @abstractmethod
    async def store_run(
        self,
        run_id: str,
        config: dict[str, Any],
        results: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store an evaluation run and its results.

        Args:
            run_id: Unique identifier for this run.
            config: Configuration used for the run.
            results: Evaluation results (summary + tasks).
            metadata: Additional metadata (timestamps, git info, etc.).

        Returns:
            The run_id of the stored run.
        """
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve a specific evaluation run.

        Args:
            run_id: Run identifier.

        Returns:
            Run data dictionary, or None if not found.
        """
        pass

    @abstractmethod
    async def list_runs(
        self,
        benchmark: str | None = None,
        model: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List evaluation runs with optional filtering.

        Args:
            benchmark: Filter by benchmark name.
            model: Filter by model name.
            since: Only include runs after this timestamp.
            limit: Maximum number of runs to return.

        Returns:
            List of run summary dictionaries.
        """
        pass

    @abstractmethod
    async def store_task_result(
        self,
        run_id: str,
        task_id: str,
        result: dict[str, Any],
    ) -> None:
        """Store a single task result within a run.

        Args:
            run_id: Parent run identifier.
            task_id: Task instance identifier.
            result: Task result data.
        """
        pass

    @abstractmethod
    async def get_task_results(
        self,
        run_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get task results for a run.

        Args:
            run_id: Run identifier.
            status: Filter by task status (resolved, failed, timeout, error).

        Returns:
            List of task result dictionaries.
        """
        pass

    @abstractmethod
    async def delete_run(self, run_id: str) -> bool:
        """Delete a run and its task results.

        Args:
            run_id: Run identifier.

        Returns:
            True if run was deleted, False if not found.
        """
        pass

    @abstractmethod
    async def get_stats(self, benchmark: str | None = None) -> dict[str, Any]:
        """Get aggregate statistics.

        Args:
            benchmark: Filter by benchmark name.

        Returns:
            Dictionary with aggregate statistics (total runs, avg pass rate, etc.).
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the storage backend and release resources."""
        pass
