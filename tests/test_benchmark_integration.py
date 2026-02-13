"""Integration tests for benchmark data loading.

These tests verify that each benchmark can successfully:
1. Load tasks from its HuggingFace dataset
2. Normalize tasks to the standard BenchmarkTask format
3. Generate valid prompt templates

These tests are marked as integration tests and are disabled by default.
Run with: uv run pytest -m integration tests/test_benchmark_integration.py
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest

from mcpbr.benchmarks import BENCHMARK_REGISTRY, create_benchmark
from mcpbr.benchmarks.base import BenchmarkTask


def _load_single_benchmark(name: str) -> dict[str, Any]:
    """Load a single task from a benchmark and return results.

    Args:
        name: Benchmark name from the registry.

    Returns:
        Dictionary with test results for this benchmark.
    """
    result: dict[str, Any] = {
        "benchmark": name,
        "create": False,
        "load_tasks": False,
        "normalize_task": False,
        "prompt_template": False,
        "task_count": 0,
        "sample_task_id": None,
        "error": None,
    }

    try:
        benchmark = create_benchmark(name)
        result["create"] = True

        # Verify prompt template
        template = benchmark.get_prompt_template()
        result["prompt_template"] = "{problem_statement}" in template

        # Load 1 task
        tasks = benchmark.load_tasks(sample_size=1)
        result["task_count"] = len(tasks)

        if tasks:
            result["load_tasks"] = True
            task = tasks[0]
            result["sample_task_id"] = task.get("instance_id", "unknown")

            # Normalize
            normalized = benchmark.normalize_task(task)
            if isinstance(normalized, BenchmarkTask):
                result["normalize_task"] = True
        else:
            result["error"] = "load_tasks returned empty list"

    except Exception as e:  # noqa: BLE001 - intentionally broad for reporting
        result["error"] = f"{type(e).__name__}: {str(e)[:300]}"

    return result


@pytest.mark.integration
class TestBenchmarkDataLoading:
    """Integration tests that verify each benchmark can load from its dataset.

    These tests require network access to download datasets from HuggingFace.
    """

    # Benchmarks that require authentication for gated HuggingFace datasets
    _GATED_BENCHMARKS = {"adversarial", "gaia", "webarena", "mlagentbench"}

    @pytest.mark.parametrize("benchmark_name", sorted(BENCHMARK_REGISTRY.keys()))
    def test_load_single_task(self, benchmark_name: str) -> None:
        """Test that a benchmark can load at least one task."""
        result = _load_single_benchmark(benchmark_name)
        assert result["create"], f"Failed to create benchmark: {result['error']}"
        assert result["prompt_template"], "Prompt template missing {{problem_statement}}"

        if benchmark_name in self._GATED_BENCHMARKS and not result["load_tasks"]:
            pytest.skip(f"Gated dataset for {benchmark_name} requires authentication")

        assert result["load_tasks"], f"Failed to load tasks: {result['error']}"
        assert result["normalize_task"], f"Failed to normalize task: {result['error']}"

    def test_all_benchmarks_parallel(self) -> None:
        """Test loading 1 task from every benchmark in parallel.

        This is the comprehensive smoke test that verifies all registered
        benchmarks can load their datasets concurrently.
        """
        benchmark_names = sorted(BENCHMARK_REGISTRY.keys())
        results: dict[str, dict[str, Any]] = {}

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(_load_single_benchmark, name): name for name in benchmark_names
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:  # noqa: BLE001 - intentionally broad for reporting
                    results[name] = {
                        "benchmark": name,
                        "error": f"Thread error: {e}",
                        "load_tasks": False,
                    }

        # Report results
        passed = [r for r in results.values() if r.get("load_tasks")]
        failed = [r for r in results.values() if not r.get("load_tasks")]

        # Print summary for debugging
        print(f"\n{'=' * 60}")
        print(f"Parallel Benchmark Loading: {len(passed)}/{len(results)} passed")
        print(f"{'=' * 60}")
        for r in sorted(passed, key=lambda x: x["benchmark"]):
            print(f"  PASS: {r['benchmark']} (task: {r.get('sample_task_id', '?')})")
        for r in sorted(failed, key=lambda x: x["benchmark"]):
            print(f"  FAIL: {r['benchmark']}: {r.get('error', 'unknown')[:100]}")

        # Exclude gated benchmarks from failure count
        real_failures = [r for r in failed if r["benchmark"] not in self._GATED_BENCHMARKS]
        assert not real_failures, (
            f"{len(real_failures)} benchmark(s) failed to load:\n"
            + "\n".join(
                f"  - {r['benchmark']}: {r.get('error', 'unknown')[:200]}" for r in real_failures
            )
        )
