"""Memory-efficient large dataset handling for benchmark evaluations.

This module provides streaming and chunked loading of large HuggingFace datasets,
enabling benchmark runs on datasets that would otherwise exceed available memory.
It includes memory monitoring, automatic chunking under memory pressure, and
iterator-based APIs compatible with existing benchmark ``load_tasks`` patterns.

Key components:
- ``MemoryMonitor``: Tracks RSS and available memory, detects memory pressure.
- ``ChunkedLoader``: Iterates over a HuggingFace dataset in configurable chunks.
- ``StreamingDataset``: High-level API that yields tasks lazily with memory awareness.
- ``DatasetStats``: Summary statistics for a streaming load session.
"""

import logging
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from datasets import load_dataset, load_dataset_builder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DatasetStats
# ---------------------------------------------------------------------------


@dataclass
class DatasetStats:
    """Summary statistics for a streaming dataset load session.

    Attributes:
        total_loaded: Number of individual task items yielded so far.
        peak_memory_mb: Peak RSS observed during loading (in megabytes).
        chunks_processed: Number of chunks fetched from the underlying loader.
        load_time_seconds: Wall-clock seconds elapsed during loading.
    """

    total_loaded: int = 0
    peak_memory_mb: float = 0.0
    chunks_processed: int = 0
    load_time_seconds: float = 0.0


# ---------------------------------------------------------------------------
# MemoryMonitor
# ---------------------------------------------------------------------------


class MemoryMonitor:
    """Lightweight monitor for process and system memory usage.

    Uses ``psutil`` when available, falling back to reading ``/proc/self/status``
    and ``/proc/meminfo`` on Linux. On platforms where neither is available the
    methods return ``0.0`` and memory-pressure detection is disabled.
    """

    def __init__(self) -> None:
        """Initialize the memory monitor and detect available backends."""
        self._has_psutil = False
        try:
            import psutil  # noqa: F401

            self._has_psutil = True
        except ImportError:
            pass

    # -- public API ---------------------------------------------------------

    def get_memory_usage_mb(self) -> float:
        """Return the current Resident Set Size (RSS) in megabytes.

        Returns:
            RSS in MB, or ``0.0`` if measurement is unavailable.
        """
        if self._has_psutil:
            return self._rss_via_psutil()
        return self._rss_via_proc()

    def get_available_memory_mb(self) -> float:
        """Return available system memory in megabytes.

        Returns:
            Available memory in MB, or ``0.0`` if measurement is unavailable.
        """
        if self._has_psutil:
            return self._available_via_psutil()
        return self._available_via_proc()

    def is_memory_pressure(self, threshold_pct: float = 80.0) -> bool:
        """Check whether system memory usage exceeds a threshold.

        Args:
            threshold_pct: Percentage (0--100) of total memory above which
                the system is considered under pressure.

        Returns:
            ``True`` if memory usage exceeds *threshold_pct*, ``False``
            otherwise or if measurement is unavailable.
        """
        if self._has_psutil:
            return self._pressure_via_psutil(threshold_pct)
        return self._pressure_via_proc(threshold_pct)

    # -- psutil backend -----------------------------------------------------

    def _rss_via_psutil(self) -> float:
        """Get RSS using psutil."""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def _available_via_psutil(self) -> float:
        """Get available system memory using psutil."""
        try:
            import psutil

            return psutil.virtual_memory().available / (1024 * 1024)
        except Exception:
            return 0.0

    def _pressure_via_psutil(self, threshold_pct: float) -> bool:
        """Check memory pressure using psutil."""
        try:
            import psutil

            return psutil.virtual_memory().percent >= threshold_pct
        except Exception:
            return False

    # -- /proc fallback -----------------------------------------------------

    @staticmethod
    def _rss_via_proc() -> float:
        """Get RSS by parsing ``/proc/self/status``."""
        try:
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        # Value is in kB
                        return int(line.split()[1]) / 1024
        except (OSError, ValueError, IndexError):
            pass
        return 0.0

    @staticmethod
    def _available_via_proc() -> float:
        """Get available memory by parsing ``/proc/meminfo``."""
        try:
            with open("/proc/meminfo") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) / 1024
        except (OSError, ValueError, IndexError):
            pass
        return 0.0

    @staticmethod
    def _pressure_via_proc(threshold_pct: float) -> bool:
        """Check memory pressure using ``/proc/meminfo``."""
        try:
            mem_total = 0.0
            mem_available = 0.0
            with open("/proc/meminfo") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1]) / 1024
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1]) / 1024
            if mem_total > 0:
                used_pct = ((mem_total - mem_available) / mem_total) * 100
                return used_pct >= threshold_pct
        except (OSError, ValueError, IndexError):
            pass
        return False


# ---------------------------------------------------------------------------
# ChunkedLoader
# ---------------------------------------------------------------------------


class ChunkedLoader:
    """Iterate over a HuggingFace dataset in fixed-size chunks.

    Each iteration yields a ``list[dict]`` containing up to *chunk_size*
    records. When the HuggingFace ``datasets`` library supports it, the
    dataset is loaded with ``streaming=True`` to avoid downloading the
    entire dataset at once.

    Args:
        dataset_name: HuggingFace dataset identifier (e.g. ``"openai_humaneval"``).
        split: Dataset split to load (default ``"test"``).
        chunk_size: Maximum number of records per chunk.
        subset: Optional dataset subset / configuration name.
    """

    def __init__(
        self,
        dataset_name: str,
        split: str = "test",
        chunk_size: int = 1000,
        subset: str | None = None,
    ) -> None:
        self.dataset_name = dataset_name
        self.split = split
        self.chunk_size = chunk_size
        self.subset = subset
        self._total_items: int | None = None

    # -- public API ---------------------------------------------------------

    def __len__(self) -> int:
        """Return the total number of items in the dataset.

        This may trigger a metadata fetch the first time it is called.

        Returns:
            Total number of items, or ``0`` if the count cannot be determined.
        """
        if self._total_items is None:
            self._total_items = self._fetch_total_items()
        return self._total_items

    def __iter__(self) -> Iterator[list[dict[str, Any]]]:
        """Yield successive chunks of dataset records.

        Yields:
            Lists of up to *chunk_size* task dictionaries.
        """
        dataset_iter = self._load_dataset_streaming()

        chunk: list[dict[str, Any]] = []
        for item in dataset_iter:
            chunk.append(dict(item))
            if len(chunk) >= self.chunk_size:
                yield chunk
                chunk = []

        # Yield any remaining items
        if chunk:
            yield chunk

    # -- internal helpers ---------------------------------------------------

    def _load_dataset_streaming(self) -> Any:
        """Load the dataset, preferring streaming mode.

        Returns:
            An iterable of dataset records (either a streaming
            ``IterableDataset`` or a regular ``Dataset``).
        """
        load_kwargs: dict[str, Any] = {}
        if self.subset is not None:
            load_kwargs["name"] = self.subset

        # Try streaming first for memory efficiency
        try:
            ds = load_dataset(
                self.dataset_name,
                split=self.split,
                streaming=True,
                **load_kwargs,
            )
            logger.info(
                "Loaded dataset %s (split=%s) in streaming mode",
                self.dataset_name,
                self.split,
            )
            return ds
        except Exception:
            logger.debug(
                "Streaming not supported for %s; falling back to full load",
                self.dataset_name,
            )

        # Fallback: load the full dataset into memory
        ds = load_dataset(
            self.dataset_name,
            split=self.split,
            **load_kwargs,
        )
        logger.info(
            "Loaded dataset %s (split=%s) fully into memory (%d items)",
            self.dataset_name,
            self.split,
            len(ds),
        )
        return ds

    def _fetch_total_items(self) -> int:
        """Fetch the total item count from dataset metadata.

        Returns:
            The number of items, or ``0`` if it cannot be determined.
        """
        try:
            load_kwargs: dict[str, Any] = {}
            if self.subset is not None:
                load_kwargs["name"] = self.subset

            builder = load_dataset_builder(self.dataset_name, **load_kwargs)
            info = builder.info
            if info.splits and self.split in info.splits:
                return int(info.splits[self.split].num_examples)
        except Exception:
            logger.debug(
                "Could not determine total items for %s/%s",
                self.dataset_name,
                self.split,
            )
        return 0


# ---------------------------------------------------------------------------
# StreamingDataset
# ---------------------------------------------------------------------------


class StreamingDataset:
    """High-level memory-aware dataset loader.

    Wraps :class:`ChunkedLoader` with automatic memory monitoring and
    adaptive chunk sizing. Provides an iterator-based ``load_tasks`` method
    compatible with the existing :class:`~mcpbr.benchmarks.base.Benchmark`
    protocol (callers can materialise with ``list(...)`` when needed).

    Args:
        dataset_name: HuggingFace dataset identifier.
        split: Dataset split (default ``"test"``).
        max_memory_mb: Optional soft memory cap. When the process RSS exceeds
            this value the chunk size is halved to reduce pressure.
    """

    # Default and minimum chunk sizes
    _DEFAULT_CHUNK_SIZE = 1000
    _MIN_CHUNK_SIZE = 50

    def __init__(
        self,
        dataset_name: str,
        split: str = "test",
        max_memory_mb: float | None = None,
    ) -> None:
        self.dataset_name = dataset_name
        self.split = split
        self.max_memory_mb = max_memory_mb

        self._monitor = MemoryMonitor()
        self._stats = DatasetStats()
        self._chunk_size = self._DEFAULT_CHUNK_SIZE
        self._start_time: float | None = None

    # -- public API ---------------------------------------------------------

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Lazily yield task dictionaries from the dataset.

        Args:
            sample_size: Maximum number of tasks to yield (``None`` for all).
            task_ids: If provided, only yield tasks whose ``instance_id`` or
                ``task_id`` is in this set.

        Yields:
            Individual task dictionaries.
        """
        self._start_time = time.monotonic()
        self._stats = DatasetStats()

        if sample_size is not None and sample_size <= 0:
            self._stats.load_time_seconds = time.monotonic() - self._start_time
            return

        task_id_set: set[str] | None = set(task_ids) if task_ids else None

        loader = ChunkedLoader(
            dataset_name=self.dataset_name,
            split=self.split,
            chunk_size=self._chunk_size,
        )

        yielded = 0

        for chunk in loader:
            self._stats.chunks_processed += 1

            # Adapt chunk size under memory pressure
            self._maybe_adapt_chunk_size(loader)

            for item in chunk:
                # Apply task_id filter
                if task_id_set is not None:
                    item_id = item.get("instance_id") or item.get("task_id")
                    if item_id not in task_id_set:
                        continue

                self._stats.total_loaded += 1
                yielded += 1

                # Track peak memory
                current_mb = self._monitor.get_memory_usage_mb()
                if current_mb > self._stats.peak_memory_mb:
                    self._stats.peak_memory_mb = current_mb

                yield item

                if sample_size is not None and yielded >= sample_size:
                    self._stats.load_time_seconds = time.monotonic() - self._start_time
                    return

        self._stats.load_time_seconds = time.monotonic() - self._start_time

    def get_stats(self) -> DatasetStats:
        """Return statistics collected during the most recent ``load_tasks`` call.

        Returns:
            A :class:`DatasetStats` instance with current metrics.
        """
        # Update load_time if still in progress
        if self._start_time is not None and self._stats.load_time_seconds == 0.0:
            self._stats.load_time_seconds = time.monotonic() - self._start_time
        return self._stats

    # -- internal helpers ---------------------------------------------------

    def _maybe_adapt_chunk_size(self, loader: ChunkedLoader) -> None:
        """Reduce the chunk size if memory pressure is detected.

        Args:
            loader: The active :class:`ChunkedLoader` whose chunk size will be
                updated in place.
        """
        under_pressure = False

        if self.max_memory_mb is not None:
            current_mb = self._monitor.get_memory_usage_mb()
            if current_mb > self.max_memory_mb:
                under_pressure = True
                logger.warning(
                    "RSS %.1f MB exceeds max_memory_mb %.1f MB; reducing chunk size",
                    current_mb,
                    self.max_memory_mb,
                )

        if not under_pressure and self._monitor.is_memory_pressure():
            under_pressure = True
            logger.warning("System memory pressure detected; reducing chunk size")

        if under_pressure and loader.chunk_size > self._MIN_CHUNK_SIZE:
            new_size = max(loader.chunk_size // 2, self._MIN_CHUNK_SIZE)
            logger.info("Chunk size reduced from %d to %d", loader.chunk_size, new_size)
            loader.chunk_size = new_size


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def get_memory_usage_mb() -> float:
    """Return current process RSS in megabytes.

    Convenience wrapper around :meth:`MemoryMonitor.get_memory_usage_mb`.

    Returns:
        RSS in MB, or ``0.0`` if measurement is unavailable.
    """
    return MemoryMonitor().get_memory_usage_mb()


def get_available_memory_mb() -> float:
    """Return available system memory in megabytes.

    Convenience wrapper around :meth:`MemoryMonitor.get_available_memory_mb`.

    Returns:
        Available memory in MB, or ``0.0`` if measurement is unavailable.
    """
    return MemoryMonitor().get_available_memory_mb()
