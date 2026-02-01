"""Benchmark registry and factory for mcpbr."""

from typing import Any

from .base import Benchmark, BenchmarkTask
from .cybergym import CyberGymBenchmark
from .gsm8k import GSM8KBenchmark
from .humaneval import HumanEvalBenchmark
from .mcptoolbench import MCPToolBenchmark
from .swebench import SWEBenchmark

__all__ = [
    "Benchmark",
    "BenchmarkTask",
    "SWEBenchmark",
    "CyberGymBenchmark",
    "HumanEvalBenchmark",
    "MCPToolBenchmark",
    "GSM8KBenchmark",
    "BENCHMARK_REGISTRY",
    "create_benchmark",
    "list_benchmarks",
]


BENCHMARK_REGISTRY: dict[
    str,
    type[SWEBenchmark | CyberGymBenchmark | HumanEvalBenchmark | MCPToolBenchmark | GSM8KBenchmark],
] = {
    "swe-bench-lite": SWEBenchmark,
    "swe-bench-verified": SWEBenchmark,
    "swe-bench-full": SWEBenchmark,
    "cybergym": CyberGymBenchmark,
    "humaneval": HumanEvalBenchmark,
    "mcptoolbench": MCPToolBenchmark,
    "gsm8k": GSM8KBenchmark,
}


def create_benchmark(name: str, **kwargs: Any) -> Benchmark:
    """Create a benchmark instance from the registry.

    Args:
        name: Benchmark name (e.g., 'swe-bench-lite', 'cybergym').
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

    # Auto-set dataset for SWE-bench variants based on benchmark name
    swebench_datasets = {
        "swe-bench-lite": "SWE-bench/SWE-bench_Lite",
        "swe-bench-verified": "SWE-bench/SWE-bench_Verified",
        "swe-bench-full": "SWE-bench/SWE-bench",
    }
    if name in swebench_datasets:
        kwargs["dataset"] = swebench_datasets[name]

    return benchmark_class(**kwargs)


def list_benchmarks() -> list[str]:
    """List available benchmark names.

    Returns:
        List of benchmark names.
    """
    return list(BENCHMARK_REGISTRY.keys())
