"""Benchmark registry and factory for mcpbr."""

from typing import Any

from .base import Benchmark, BenchmarkTask
from .cybergym import CyberGymBenchmark
from .swebench import SWEBenchmark

__all__ = [
    "Benchmark",
    "BenchmarkTask",
    "SWEBenchmark",
    "CyberGymBenchmark",
    "BENCHMARK_REGISTRY",
    "create_benchmark",
    "list_benchmarks",
]


BENCHMARK_REGISTRY: dict[str, type[SWEBenchmark | CyberGymBenchmark]] = {
    "swe-bench": SWEBenchmark,
    "cybergym": CyberGymBenchmark,
}


def create_benchmark(name: str, **kwargs: Any) -> Benchmark:
    """Create a benchmark instance from the registry.

    Args:
        name: Benchmark name (e.g., 'swe-bench', 'cybergym').
        **kwargs: Arguments to pass to the benchmark constructor.

    Returns:
        Benchmark instance.

    Raises:
        ValueError: If benchmark name is not recognized.
    """
    if name not in BENCHMARK_REGISTRY:
        available = ", ".join(BENCHMARK_REGISTRY.keys())
        raise ValueError(f"Unknown benchmark: {name}. Available: {available}")

    benchmark_class = BENCHMARK_REGISTRY[name]
    return benchmark_class(**kwargs)


def list_benchmarks() -> list[str]:
    """List available benchmark names.

    Returns:
        List of benchmark names.
    """
    return list(BENCHMARK_REGISTRY.keys())
