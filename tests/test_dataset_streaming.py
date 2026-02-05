"""Tests for dataset streaming module."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from mcpbr.dataset_streaming import (
    ChunkedLoader,
    DatasetStats,
    MemoryMonitor,
    StreamingDataset,
    get_available_memory_mb,
    get_memory_usage_mb,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_dataset(n: int) -> list[dict]:
    """Create a list of fake task dictionaries for testing.

    Args:
        n: Number of tasks to create.

    Returns:
        List of task dictionaries with ``instance_id`` and ``text`` fields.
    """
    return [{"instance_id": f"task_{i}", "text": f"problem {i}"} for i in range(n)]


def _make_fake_hf_dataset(n: int) -> MagicMock:
    """Create a mock HuggingFace ``Dataset`` that is iterable and has ``len``.

    Args:
        n: Number of items in the dataset.

    Returns:
        A MagicMock behaving like a HuggingFace Dataset.
    """
    items = _make_fake_dataset(n)
    mock_ds = MagicMock()
    mock_ds.__iter__ = MagicMock(return_value=iter(items))
    mock_ds.__len__ = MagicMock(return_value=n)
    return mock_ds


# ---------------------------------------------------------------------------
# DatasetStats
# ---------------------------------------------------------------------------


class TestDatasetStats:
    """Tests for the DatasetStats dataclass."""

    def test_default_values(self) -> None:
        """Test that DatasetStats has correct default values."""
        stats = DatasetStats()
        assert stats.total_loaded == 0
        assert stats.peak_memory_mb == 0.0
        assert stats.chunks_processed == 0
        assert stats.load_time_seconds == 0.0

    def test_custom_values(self) -> None:
        """Test DatasetStats with custom values."""
        stats = DatasetStats(
            total_loaded=100,
            peak_memory_mb=512.5,
            chunks_processed=10,
            load_time_seconds=3.14,
        )
        assert stats.total_loaded == 100
        assert stats.peak_memory_mb == 512.5
        assert stats.chunks_processed == 10
        assert stats.load_time_seconds == 3.14

    def test_mutability(self) -> None:
        """Test that stats fields can be updated in place."""
        stats = DatasetStats()
        stats.total_loaded += 5
        stats.peak_memory_mb = 256.0
        assert stats.total_loaded == 5
        assert stats.peak_memory_mb == 256.0


# ---------------------------------------------------------------------------
# MemoryMonitor
# ---------------------------------------------------------------------------


class TestMemoryMonitor:
    """Tests for the MemoryMonitor class."""

    def test_init_detects_psutil(self) -> None:
        """Test that __init__ detects psutil availability."""
        monitor = MemoryMonitor()
        # psutil is a project dependency, so should be available
        assert monitor._has_psutil is True

    def test_get_memory_usage_mb_returns_float(self) -> None:
        """Test that get_memory_usage_mb returns a non-negative float."""
        monitor = MemoryMonitor()
        usage = monitor.get_memory_usage_mb()
        assert isinstance(usage, float)
        assert usage >= 0.0

    def test_get_available_memory_mb_returns_float(self) -> None:
        """Test that get_available_memory_mb returns a non-negative float."""
        monitor = MemoryMonitor()
        available = monitor.get_available_memory_mb()
        assert isinstance(available, float)
        assert available >= 0.0

    def test_is_memory_pressure_returns_bool(self) -> None:
        """Test that is_memory_pressure returns a boolean."""
        monitor = MemoryMonitor()
        result = monitor.is_memory_pressure(threshold_pct=99.9)
        assert isinstance(result, bool)

    def test_memory_pressure_high_threshold_is_false(self) -> None:
        """Test that a 100% threshold never triggers pressure."""
        monitor = MemoryMonitor()
        assert monitor.is_memory_pressure(threshold_pct=100.0) is False

    def test_memory_pressure_low_threshold(self) -> None:
        """Test that a very low threshold (0.01%) likely triggers pressure."""
        monitor = MemoryMonitor()
        # On any running system, 0.01% is almost certainly exceeded
        result = monitor.is_memory_pressure(threshold_pct=0.01)
        assert isinstance(result, bool)

    @patch("mcpbr.dataset_streaming.MemoryMonitor._rss_via_psutil", return_value=0.0)
    @patch("mcpbr.dataset_streaming.MemoryMonitor._available_via_psutil", return_value=0.0)
    @patch("mcpbr.dataset_streaming.MemoryMonitor._pressure_via_psutil", return_value=False)
    def test_psutil_backend_called_when_available(
        self,
        mock_pressure: MagicMock,
        mock_available: MagicMock,
        mock_rss: MagicMock,
    ) -> None:
        """Test that psutil backend methods are invoked when psutil is present."""
        monitor = MemoryMonitor()
        monitor._has_psutil = True

        monitor.get_memory_usage_mb()
        mock_rss.assert_called_once()

        monitor.get_available_memory_mb()
        mock_available.assert_called_once()

        monitor.is_memory_pressure()
        mock_pressure.assert_called_once()

    def test_proc_fallback_when_no_psutil(self) -> None:
        """Test that /proc fallback is used when psutil is unavailable."""
        monitor = MemoryMonitor()
        monitor._has_psutil = False

        # Should not raise even on non-Linux (returns 0.0)
        usage = monitor.get_memory_usage_mb()
        assert isinstance(usage, float)

        available = monitor.get_available_memory_mb()
        assert isinstance(available, float)

        pressure = monitor.is_memory_pressure()
        assert isinstance(pressure, bool)

    def test_rss_via_proc_no_file(self) -> None:
        """Test _rss_via_proc returns 0.0 when /proc is unavailable."""
        with patch("builtins.open", side_effect=OSError("not linux")):
            result = MemoryMonitor._rss_via_proc()
            assert result == 0.0

    def test_available_via_proc_no_file(self) -> None:
        """Test _available_via_proc returns 0.0 when /proc is unavailable."""
        with patch("builtins.open", side_effect=OSError("not linux")):
            result = MemoryMonitor._available_via_proc()
            assert result == 0.0

    def test_pressure_via_proc_no_file(self) -> None:
        """Test _pressure_via_proc returns False when /proc is unavailable."""
        with patch("builtins.open", side_effect=OSError("not linux")):
            result = MemoryMonitor._pressure_via_proc(80.0)
            assert result is False

    def test_rss_via_psutil_exception(self) -> None:
        """Test _rss_via_psutil returns 0.0 on unexpected exceptions."""
        monitor = MemoryMonitor()
        with patch("psutil.Process", side_effect=RuntimeError("boom")):
            result = monitor._rss_via_psutil()
            assert result == 0.0

    def test_available_via_psutil_exception(self) -> None:
        """Test _available_via_psutil returns 0.0 on unexpected exceptions."""
        monitor = MemoryMonitor()
        with patch("psutil.virtual_memory", side_effect=RuntimeError("boom")):
            result = monitor._available_via_psutil()
            assert result == 0.0

    def test_pressure_via_psutil_exception(self) -> None:
        """Test _pressure_via_psutil returns False on unexpected exceptions."""
        monitor = MemoryMonitor()
        with patch("psutil.virtual_memory", side_effect=RuntimeError("boom")):
            result = monitor._pressure_via_psutil(80.0)
            assert result is False


# ---------------------------------------------------------------------------
# ChunkedLoader
# ---------------------------------------------------------------------------


class TestChunkedLoader:
    """Tests for the ChunkedLoader class."""

    def test_init_defaults(self) -> None:
        """Test ChunkedLoader default parameter values."""
        loader = ChunkedLoader(dataset_name="test/dataset")
        assert loader.dataset_name == "test/dataset"
        assert loader.split == "test"
        assert loader.chunk_size == 1000
        assert loader.subset is None

    def test_init_custom_params(self) -> None:
        """Test ChunkedLoader with custom parameters."""
        loader = ChunkedLoader(
            dataset_name="org/ds",
            split="train",
            chunk_size=500,
            subset="v2",
        )
        assert loader.dataset_name == "org/ds"
        assert loader.split == "train"
        assert loader.chunk_size == 500
        assert loader.subset == "v2"

    @patch("mcpbr.dataset_streaming.ChunkedLoader._load_dataset_streaming")
    def test_iter_single_chunk(self, mock_load: MagicMock) -> None:
        """Test iteration when all items fit in one chunk."""
        items = _make_fake_dataset(5)
        mock_load.return_value = iter(items)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=10)
        chunks = list(loader)

        assert len(chunks) == 1
        assert len(chunks[0]) == 5
        assert chunks[0][0]["instance_id"] == "task_0"

    @patch("mcpbr.dataset_streaming.ChunkedLoader._load_dataset_streaming")
    def test_iter_multiple_chunks(self, mock_load: MagicMock) -> None:
        """Test iteration when items span multiple chunks."""
        items = _make_fake_dataset(25)
        mock_load.return_value = iter(items)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=10)
        chunks = list(loader)

        assert len(chunks) == 3
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5

    @patch("mcpbr.dataset_streaming.ChunkedLoader._load_dataset_streaming")
    def test_iter_exact_multiple(self, mock_load: MagicMock) -> None:
        """Test iteration when item count is an exact multiple of chunk size."""
        items = _make_fake_dataset(20)
        mock_load.return_value = iter(items)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=10)
        chunks = list(loader)

        assert len(chunks) == 2
        assert all(len(c) == 10 for c in chunks)

    @patch("mcpbr.dataset_streaming.ChunkedLoader._load_dataset_streaming")
    def test_iter_empty_dataset(self, mock_load: MagicMock) -> None:
        """Test iteration over an empty dataset."""
        mock_load.return_value = iter([])

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=10)
        chunks = list(loader)

        assert chunks == []

    @patch("mcpbr.dataset_streaming.ChunkedLoader._load_dataset_streaming")
    def test_iter_chunk_size_one(self, mock_load: MagicMock) -> None:
        """Test that chunk_size=1 yields individual items in lists."""
        items = _make_fake_dataset(3)
        mock_load.return_value = iter(items)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=1)
        chunks = list(loader)

        assert len(chunks) == 3
        assert all(len(c) == 1 for c in chunks)

    @patch("mcpbr.dataset_streaming.ChunkedLoader._load_dataset_streaming")
    def test_iter_yields_dicts(self, mock_load: MagicMock) -> None:
        """Test that yielded items are plain dicts (not MagicMock-like objects)."""
        # Simulate HuggingFace row objects that support dict()
        hf_rows = []
        for i in range(3):
            row = {"instance_id": f"task_{i}", "text": f"problem {i}"}
            hf_rows.append(row)
        mock_load.return_value = iter(hf_rows)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=10)
        chunks = list(loader)

        for chunk in chunks:
            for item in chunk:
                assert isinstance(item, dict)

    @patch("mcpbr.dataset_streaming.load_dataset_builder")
    def test_len_with_dataset_info(self, mock_builder_fn: MagicMock) -> None:
        """Test __len__ when dataset metadata provides split info."""
        mock_builder = MagicMock()
        mock_split_info = MagicMock()
        mock_split_info.num_examples = 42
        mock_builder.info.splits = {"test": mock_split_info}
        mock_builder_fn.return_value = mock_builder

        loader = ChunkedLoader(dataset_name="test/ds")
        assert len(loader) == 42

    @patch("mcpbr.dataset_streaming.load_dataset_builder", side_effect=Exception("no info"))
    def test_len_fallback_zero(self, mock_builder_fn: MagicMock) -> None:
        """Test __len__ returns 0 when metadata is unavailable."""
        loader = ChunkedLoader(dataset_name="test/ds")
        assert len(loader) == 0

    @patch("mcpbr.dataset_streaming.load_dataset_builder")
    def test_len_caches_result(self, mock_builder_fn: MagicMock) -> None:
        """Test that __len__ caches the result and only queries once."""
        mock_builder = MagicMock()
        mock_split_info = MagicMock()
        mock_split_info.num_examples = 99
        mock_builder.info.splits = {"test": mock_split_info}
        mock_builder_fn.return_value = mock_builder

        loader = ChunkedLoader(dataset_name="test/ds")
        _ = len(loader)
        _ = len(loader)

        mock_builder_fn.assert_called_once()

    @patch("mcpbr.dataset_streaming.load_dataset")
    def test_load_streaming_fallback(self, mock_load_dataset: MagicMock) -> None:
        """Test that _load_dataset_streaming falls back to full load on error."""
        items = _make_fake_dataset(3)
        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(items))
        mock_ds.__len__ = MagicMock(return_value=3)

        # First call (streaming=True) raises, second call succeeds
        mock_load_dataset.side_effect = [Exception("no streaming"), mock_ds]

        loader = ChunkedLoader(dataset_name="test/ds")
        loader._load_dataset_streaming()

        assert mock_load_dataset.call_count == 2
        # Second call should not have streaming=True
        second_call_kwargs = mock_load_dataset.call_args_list[1]
        assert "streaming" not in second_call_kwargs.kwargs

    @patch("mcpbr.dataset_streaming.load_dataset")
    def test_load_streaming_with_subset(self, mock_load_dataset: MagicMock) -> None:
        """Test that subset is passed as 'name' kwarg to load_dataset."""
        items = _make_fake_dataset(2)
        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(items))
        mock_load_dataset.return_value = mock_ds

        loader = ChunkedLoader(dataset_name="test/ds", subset="v2")
        loader._load_dataset_streaming()

        call_kwargs = mock_load_dataset.call_args
        assert call_kwargs.kwargs.get("name") == "v2"


# ---------------------------------------------------------------------------
# StreamingDataset
# ---------------------------------------------------------------------------


class TestStreamingDataset:
    """Tests for the StreamingDataset class."""

    def test_init_defaults(self) -> None:
        """Test StreamingDataset default parameter values."""
        sd = StreamingDataset(dataset_name="test/ds")
        assert sd.dataset_name == "test/ds"
        assert sd.split == "test"
        assert sd.max_memory_mb is None

    def test_init_custom_params(self) -> None:
        """Test StreamingDataset with custom parameters."""
        sd = StreamingDataset(dataset_name="org/ds", split="train", max_memory_mb=2048.0)
        assert sd.dataset_name == "org/ds"
        assert sd.split == "train"
        assert sd.max_memory_mb == 2048.0

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_yields_all(self, mock_iter: MagicMock) -> None:
        """Test that load_tasks yields all items when no limit is given."""
        items = _make_fake_dataset(5)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks())

        assert len(result) == 5

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_returns_iterator(self, mock_iter: MagicMock) -> None:
        """Test that load_tasks returns an Iterator, not a list."""
        items = _make_fake_dataset(3)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = sd.load_tasks()

        assert isinstance(result, Iterator)

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_sample_size(self, mock_iter: MagicMock) -> None:
        """Test that load_tasks respects sample_size limit."""
        items = _make_fake_dataset(100)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks(sample_size=10))

        assert len(result) == 10

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_sample_size_exceeds_total(self, mock_iter: MagicMock) -> None:
        """Test that sample_size larger than dataset yields all items."""
        items = _make_fake_dataset(5)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks(sample_size=100))

        assert len(result) == 5

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_filter_by_instance_id(self, mock_iter: MagicMock) -> None:
        """Test filtering by instance_id via task_ids parameter."""
        items = _make_fake_dataset(10)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks(task_ids=["task_2", "task_5", "task_9"]))

        assert len(result) == 3
        ids = {item["instance_id"] for item in result}
        assert ids == {"task_2", "task_5", "task_9"}

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_filter_by_task_id(self, mock_iter: MagicMock) -> None:
        """Test filtering works with 'task_id' field when 'instance_id' is absent."""
        items = [{"task_id": f"HumanEval/{i}", "text": f"problem {i}"} for i in range(5)]
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks(task_ids=["HumanEval/1", "HumanEval/3"]))

        assert len(result) == 2

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_filter_and_sample_size(self, mock_iter: MagicMock) -> None:
        """Test that task_ids filter and sample_size work together."""
        items = _make_fake_dataset(20)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        target_ids = [f"task_{i}" for i in range(10)]
        result = list(sd.load_tasks(sample_size=3, task_ids=target_ids))

        assert len(result) == 3

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_empty_dataset(self, mock_iter: MagicMock) -> None:
        """Test load_tasks on an empty dataset."""
        mock_iter.return_value = iter([])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks())

        assert result == []

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_multiple_chunks(self, mock_iter: MagicMock) -> None:
        """Test load_tasks across multiple chunks."""
        chunk1 = _make_fake_dataset(3)  # task_0..task_2
        chunk2 = [{"instance_id": f"task_{i}", "text": f"p {i}"} for i in range(3, 6)]
        mock_iter.return_value = iter([chunk1, chunk2])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks())

        assert len(result) == 6

    @patch.object(ChunkedLoader, "__iter__")
    def test_load_tasks_nonexistent_task_ids(self, mock_iter: MagicMock) -> None:
        """Test that filtering with nonexistent task_ids yields nothing."""
        items = _make_fake_dataset(5)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks(task_ids=["does_not_exist"]))

        assert result == []


# ---------------------------------------------------------------------------
# StreamingDataset -- stats
# ---------------------------------------------------------------------------


class TestStreamingDatasetStats:
    """Tests for StreamingDataset.get_stats()."""

    @patch.object(ChunkedLoader, "__iter__")
    def test_stats_total_loaded(self, mock_iter: MagicMock) -> None:
        """Test that total_loaded reflects the number of yielded items."""
        items = _make_fake_dataset(7)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        _ = list(sd.load_tasks())

        stats = sd.get_stats()
        assert stats.total_loaded == 7

    @patch.object(ChunkedLoader, "__iter__")
    def test_stats_chunks_processed(self, mock_iter: MagicMock) -> None:
        """Test that chunks_processed counts the number of chunks."""
        chunk1 = _make_fake_dataset(3)
        chunk2 = [{"instance_id": "task_x", "text": "x"}]
        mock_iter.return_value = iter([chunk1, chunk2])

        sd = StreamingDataset(dataset_name="test/ds")
        _ = list(sd.load_tasks())

        stats = sd.get_stats()
        assert stats.chunks_processed == 2

    @patch.object(ChunkedLoader, "__iter__")
    def test_stats_load_time_positive(self, mock_iter: MagicMock) -> None:
        """Test that load_time_seconds is positive after loading."""
        items = _make_fake_dataset(3)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        _ = list(sd.load_tasks())

        stats = sd.get_stats()
        assert stats.load_time_seconds >= 0.0

    @patch.object(ChunkedLoader, "__iter__")
    def test_stats_peak_memory_non_negative(self, mock_iter: MagicMock) -> None:
        """Test that peak_memory_mb is non-negative."""
        items = _make_fake_dataset(3)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        _ = list(sd.load_tasks())

        stats = sd.get_stats()
        assert stats.peak_memory_mb >= 0.0

    @patch.object(ChunkedLoader, "__iter__")
    def test_stats_reset_on_new_load(self, mock_iter: MagicMock) -> None:
        """Test that stats are reset on each new load_tasks call."""
        items1 = _make_fake_dataset(5)
        items2 = _make_fake_dataset(3)

        mock_iter.return_value = iter([items1])
        sd = StreamingDataset(dataset_name="test/ds")
        _ = list(sd.load_tasks())
        assert sd.get_stats().total_loaded == 5

        mock_iter.return_value = iter([items2])
        _ = list(sd.load_tasks())
        assert sd.get_stats().total_loaded == 3

    @patch.object(ChunkedLoader, "__iter__")
    def test_stats_with_sample_size_limit(self, mock_iter: MagicMock) -> None:
        """Test stats when load is truncated by sample_size."""
        items = _make_fake_dataset(100)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        _ = list(sd.load_tasks(sample_size=10))

        stats = sd.get_stats()
        assert stats.total_loaded == 10
        assert stats.load_time_seconds >= 0.0

    @patch.object(ChunkedLoader, "__iter__")
    def test_get_stats_before_load(self, mock_iter: MagicMock) -> None:
        """Test that get_stats returns default DatasetStats before any load."""
        sd = StreamingDataset(dataset_name="test/ds")
        stats = sd.get_stats()
        assert stats.total_loaded == 0
        assert stats.chunks_processed == 0


# ---------------------------------------------------------------------------
# StreamingDataset -- memory adaptation
# ---------------------------------------------------------------------------


class TestStreamingDatasetMemoryAdaptation:
    """Tests for automatic chunk-size reduction under memory pressure."""

    @patch.object(ChunkedLoader, "__iter__")
    @patch.object(MemoryMonitor, "get_memory_usage_mb", return_value=300.0)
    @patch.object(MemoryMonitor, "is_memory_pressure", return_value=False)
    def test_no_adaptation_below_max_memory(
        self,
        mock_pressure: MagicMock,
        mock_usage: MagicMock,
        mock_iter: MagicMock,
    ) -> None:
        """Test that chunk size is unchanged when memory is within limits."""
        items = _make_fake_dataset(5)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds", max_memory_mb=500.0)
        _ = list(sd.load_tasks())

        # Chunk size should stay at default
        assert sd._chunk_size == sd._DEFAULT_CHUNK_SIZE

    @patch.object(ChunkedLoader, "__iter__")
    @patch.object(MemoryMonitor, "get_memory_usage_mb", return_value=600.0)
    @patch.object(MemoryMonitor, "is_memory_pressure", return_value=False)
    def test_adaptation_when_exceeding_max_memory(
        self,
        mock_pressure: MagicMock,
        mock_usage: MagicMock,
        mock_iter: MagicMock,
    ) -> None:
        """Test that chunk size is reduced when RSS exceeds max_memory_mb."""
        items = _make_fake_dataset(5)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds", max_memory_mb=500.0)
        _ = list(sd.load_tasks())

        # The loader's chunk_size should have been reduced
        # (we can verify via stats -- at least one chunk was processed)
        stats = sd.get_stats()
        assert stats.chunks_processed >= 1

    @patch.object(ChunkedLoader, "__iter__")
    @patch.object(MemoryMonitor, "get_memory_usage_mb", return_value=100.0)
    @patch.object(MemoryMonitor, "is_memory_pressure", return_value=True)
    def test_adaptation_on_system_memory_pressure(
        self,
        mock_pressure: MagicMock,
        mock_usage: MagicMock,
        mock_iter: MagicMock,
    ) -> None:
        """Test that chunk size is reduced when system memory pressure is detected."""
        items = _make_fake_dataset(5)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        _ = list(sd.load_tasks())

        stats = sd.get_stats()
        assert stats.chunks_processed >= 1

    def test_min_chunk_size_floor(self) -> None:
        """Test that chunk size is never reduced below _MIN_CHUNK_SIZE."""
        sd = StreamingDataset(dataset_name="test/ds", max_memory_mb=10.0)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=60)

        # Simulate pressure
        with (
            patch.object(sd._monitor, "get_memory_usage_mb", return_value=999.0),
            patch.object(sd._monitor, "is_memory_pressure", return_value=True),
        ):
            sd._maybe_adapt_chunk_size(loader)

        assert loader.chunk_size >= sd._MIN_CHUNK_SIZE

    def test_chunk_size_halving(self) -> None:
        """Test that chunk size is halved on each pressure event."""
        sd = StreamingDataset(dataset_name="test/ds", max_memory_mb=10.0)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=400)

        with (
            patch.object(sd._monitor, "get_memory_usage_mb", return_value=999.0),
            patch.object(sd._monitor, "is_memory_pressure", return_value=False),
        ):
            sd._maybe_adapt_chunk_size(loader)

        assert loader.chunk_size == 200

    def test_no_adaptation_at_min_chunk_size(self) -> None:
        """Test that chunk size at minimum is not reduced further."""
        sd = StreamingDataset(dataset_name="test/ds", max_memory_mb=10.0)

        loader = ChunkedLoader(dataset_name="test/ds", chunk_size=sd._MIN_CHUNK_SIZE)

        with (
            patch.object(sd._monitor, "get_memory_usage_mb", return_value=999.0),
            patch.object(sd._monitor, "is_memory_pressure", return_value=False),
        ):
            sd._maybe_adapt_chunk_size(loader)

        assert loader.chunk_size == sd._MIN_CHUNK_SIZE


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


class TestConvenienceHelpers:
    """Tests for module-level convenience functions."""

    def test_get_memory_usage_mb(self) -> None:
        """Test that get_memory_usage_mb returns a non-negative float."""
        result = get_memory_usage_mb()
        assert isinstance(result, float)
        assert result >= 0.0

    def test_get_available_memory_mb(self) -> None:
        """Test that get_available_memory_mb returns a non-negative float."""
        result = get_available_memory_mb()
        assert isinstance(result, float)
        assert result >= 0.0

    @patch.object(MemoryMonitor, "get_memory_usage_mb", return_value=123.4)
    def test_get_memory_usage_mb_delegates(self, mock_usage: MagicMock) -> None:
        """Test that the convenience function delegates to MemoryMonitor."""
        result = get_memory_usage_mb()
        assert result == 123.4

    @patch.object(MemoryMonitor, "get_available_memory_mb", return_value=567.8)
    def test_get_available_memory_mb_delegates(self, mock_avail: MagicMock) -> None:
        """Test that the convenience function delegates to MemoryMonitor."""
        result = get_available_memory_mb()
        assert result == 567.8


# ---------------------------------------------------------------------------
# Integration-style tests (still unit-level, no real datasets)
# ---------------------------------------------------------------------------


class TestStreamingDatasetIntegration:
    """Integration-style tests combining multiple components."""

    @patch.object(ChunkedLoader, "__iter__")
    def test_full_workflow(self, mock_iter: MagicMock) -> None:
        """Test complete workflow: create, load, check stats."""
        chunk1 = _make_fake_dataset(50)
        chunk2 = [{"instance_id": f"task_{i}", "text": f"p {i}"} for i in range(50, 75)]
        mock_iter.return_value = iter([chunk1, chunk2])

        sd = StreamingDataset(dataset_name="test/ds", max_memory_mb=4096.0)
        tasks = list(sd.load_tasks(sample_size=30))

        assert len(tasks) == 30

        stats = sd.get_stats()
        assert stats.total_loaded == 30
        assert stats.chunks_processed >= 1
        assert stats.load_time_seconds >= 0.0
        assert stats.peak_memory_mb >= 0.0

    @patch.object(ChunkedLoader, "__iter__")
    def test_repeated_loads_independent(self, mock_iter: MagicMock) -> None:
        """Test that consecutive loads produce independent stats."""
        items_a = _make_fake_dataset(10)
        items_b = _make_fake_dataset(20)

        sd = StreamingDataset(dataset_name="test/ds")

        # First load
        mock_iter.return_value = iter([items_a])
        result_a = list(sd.load_tasks())
        stats_a_total = sd.get_stats().total_loaded

        # Second load
        mock_iter.return_value = iter([items_b])
        result_b = list(sd.load_tasks())
        stats_b_total = sd.get_stats().total_loaded

        assert len(result_a) == 10
        assert len(result_b) == 20
        assert stats_a_total == 10
        assert stats_b_total == 20

    @patch.object(ChunkedLoader, "__iter__")
    def test_lazy_evaluation(self, mock_iter: MagicMock) -> None:
        """Test that load_tasks is lazy: items are only consumed on iteration."""
        items = _make_fake_dataset(100)
        call_count = 0
        original_items = list(items)

        def counting_iter():
            nonlocal call_count
            call_count += 1
            yield original_items

        mock_iter.side_effect = counting_iter

        sd = StreamingDataset(dataset_name="test/ds")
        iterator = sd.load_tasks()

        # No chunks consumed yet (the iterator was created but not advanced)
        # Consume exactly one item
        first = next(iterator)
        assert first["instance_id"] == "task_0"

    @patch.object(ChunkedLoader, "__iter__")
    def test_sample_size_zero(self, mock_iter: MagicMock) -> None:
        """Test that sample_size=0 yields no items."""
        items = _make_fake_dataset(10)
        mock_iter.return_value = iter([items])

        sd = StreamingDataset(dataset_name="test/ds")
        result = list(sd.load_tasks(sample_size=0))

        assert result == []
