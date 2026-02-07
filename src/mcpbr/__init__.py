"""mcpbr - Model Context Protocol Benchmark Runner.

A benchmark runner for evaluating MCP servers against SWE-bench tasks.
"""

__version__ = "0.12.3"

from .sdk import (
    BenchmarkResult,
    MCPBenchmark,
    get_version,
    list_benchmarks,
    list_models,
    list_providers,
)

__all__ = [
    "__version__",
    "BenchmarkResult",
    "MCPBenchmark",
    "get_version",
    "list_benchmarks",
    "list_models",
    "list_providers",
]
