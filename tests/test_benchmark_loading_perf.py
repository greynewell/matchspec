"""Tests for dataset loading performance — dataset.select() optimization."""

from unittest.mock import MagicMock, patch


class TestDatasetSelectOptimization:
    """Verify benchmarks use dataset.select(range(n)) when sample_size is set."""

    def _make_mock_dataset(self, size=100, id_field="instance_id"):
        """Create a mock HuggingFace dataset with select() support."""
        items = [
            {
                id_field: f"task-{i}",
                "instance_id": f"task-{i}",
                "task_id": f"HumanEval/{i}",
                "text": f"problem {i}",
                "prompt": f"def f{i}():",
                "canonical_solution": "pass",
                "test": "",
                "entry_point": f"f{i}",
                "problem_statement": f"problem {i}",
                "repo": "test/repo",
                "base_commit": "abc123",
            }
            for i in range(size)
        ]
        dataset = MagicMock()
        dataset.__len__ = MagicMock(return_value=size)
        dataset.__iter__ = MagicMock(return_value=iter(items))

        def select_fn(indices):
            selected = [items[i] for i in indices]
            sub_ds = MagicMock()
            sub_ds.__iter__ = MagicMock(return_value=iter(selected))
            sub_ds.__len__ = MagicMock(return_value=len(selected))
            return sub_ds

        dataset.select = MagicMock(side_effect=select_fn)
        return dataset

    @patch("mcpbr.benchmarks.swebench.load_dataset")
    def test_swebench_uses_select_with_sample_size(self, mock_load):
        """SWE-bench should use dataset.select() when sample_size is set."""
        from mcpbr.benchmarks.swebench import SWEBenchmark

        mock_ds = self._make_mock_dataset(100)
        mock_load.return_value = mock_ds

        benchmark = SWEBenchmark()
        tasks = benchmark.load_tasks(sample_size=5)

        # select() should have been called
        mock_ds.select.assert_called_once_with(range(5))
        assert len(tasks) == 5

    @patch("mcpbr.benchmarks.swebench.load_dataset")
    def test_swebench_full_load_without_sample_size(self, mock_load):
        """SWE-bench should NOT use select() when sample_size is None."""
        from mcpbr.benchmarks.swebench import SWEBenchmark

        mock_ds = self._make_mock_dataset(100)
        mock_load.return_value = mock_ds

        benchmark = SWEBenchmark()
        benchmark.load_tasks(sample_size=None)

        # select() should NOT have been called
        mock_ds.select.assert_not_called()

    @patch("mcpbr.benchmarks.swebench.load_dataset")
    def test_swebench_full_load_with_task_ids(self, mock_load):
        """When task_ids are provided, should load all then filter by ID."""
        from mcpbr.benchmarks.swebench import SWEBenchmark

        mock_ds = self._make_mock_dataset(100)
        mock_load.return_value = mock_ds

        benchmark = SWEBenchmark()
        benchmark.load_tasks(sample_size=5, task_ids=["task-0", "task-1"])

        # With task_ids, select() should NOT be called — we need full scan for ID matching
        mock_ds.select.assert_not_called()

    @patch("mcpbr.benchmarks.humaneval.load_dataset")
    def test_humaneval_uses_select_with_sample_size(self, mock_load):
        """HumanEval should use dataset.select() when sample_size is set."""
        from mcpbr.benchmarks.humaneval import HumanEvalBenchmark

        mock_ds = self._make_mock_dataset(164)
        mock_load.return_value = mock_ds

        benchmark = HumanEvalBenchmark()
        tasks = benchmark.load_tasks(sample_size=3)

        mock_ds.select.assert_called_once_with(range(3))
        assert len(tasks) == 3

    @patch("mcpbr.benchmarks.humaneval.load_dataset")
    def test_humaneval_full_load_without_sample_size(self, mock_load):
        """HumanEval should NOT use select() when sample_size is None."""
        from mcpbr.benchmarks.humaneval import HumanEvalBenchmark

        mock_ds = self._make_mock_dataset(164)
        mock_load.return_value = mock_ds

        benchmark = HumanEvalBenchmark()
        benchmark.load_tasks(sample_size=None)

        mock_ds.select.assert_not_called()
