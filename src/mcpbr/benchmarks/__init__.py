"""Benchmark registry and factory for mcpbr."""

from typing import Any

from .agentbench import AgentBenchBenchmark
from .aider_polyglot import AiderPolyglotBenchmark
from .apps import APPSBenchmark
from .arc import ARCBenchmark
from .base import Benchmark, BenchmarkTask
from .bigbench_hard import BigBenchHardBenchmark
from .bigcodebench import BigCodeBenchBenchmark
from .codecontests import CodeContestsBenchmark
from .codereval import CoderEvalBenchmark
from .cybergym import CyberGymBenchmark
from .gaia import GAIABenchmark
from .gsm8k import GSM8KBenchmark
from .hellaswag import HellaSwagBenchmark
from .humaneval import HumanEvalBenchmark
from .intercode import InterCodeBenchmark
from .leetcode import LeetCodeBenchmark
from .math_benchmark import MATHBenchmark
from .mbpp import MBPPBenchmark
from .mcptoolbench import MCPToolBenchmark
from .mlagentbench import MLAgentBenchBenchmark
from .repoqa import RepoQABenchmark
from .swebench import SWEBenchmark
from .terminalbench import TerminalBenchBenchmark
from .toolbench import ToolBenchBenchmark
from .truthfulqa import TruthfulQABenchmark
from .webarena import WebArenaBenchmark

__all__ = [
    "Benchmark",
    "BenchmarkTask",
    "SWEBenchmark",
    "CyberGymBenchmark",
    "HumanEvalBenchmark",
    "MCPToolBenchmark",
    "GSM8KBenchmark",
    "MBPPBenchmark",
    "MATHBenchmark",
    "TruthfulQABenchmark",
    "BigBenchHardBenchmark",
    "HellaSwagBenchmark",
    "ARCBenchmark",
    "APPSBenchmark",
    "CodeContestsBenchmark",
    "BigCodeBenchBenchmark",
    "LeetCodeBenchmark",
    "CoderEvalBenchmark",
    "RepoQABenchmark",
    "ToolBenchBenchmark",
    "AiderPolyglotBenchmark",
    "TerminalBenchBenchmark",
    "GAIABenchmark",
    "AgentBenchBenchmark",
    "WebArenaBenchmark",
    "MLAgentBenchBenchmark",
    "InterCodeBenchmark",
    "BENCHMARK_REGISTRY",
    "create_benchmark",
    "list_benchmarks",
]


BENCHMARK_REGISTRY: dict[str, type] = {
    "swe-bench-lite": SWEBenchmark,
    "swe-bench-verified": SWEBenchmark,
    "swe-bench-full": SWEBenchmark,
    "cybergym": CyberGymBenchmark,
    "humaneval": HumanEvalBenchmark,
    "mcptoolbench": MCPToolBenchmark,
    "gsm8k": GSM8KBenchmark,
    "mbpp": MBPPBenchmark,
    "math": MATHBenchmark,
    "truthfulqa": TruthfulQABenchmark,
    "bigbench-hard": BigBenchHardBenchmark,
    "hellaswag": HellaSwagBenchmark,
    "arc": ARCBenchmark,
    "apps": APPSBenchmark,
    "codecontests": CodeContestsBenchmark,
    "bigcodebench": BigCodeBenchBenchmark,
    "leetcode": LeetCodeBenchmark,
    "codereval": CoderEvalBenchmark,
    "repoqa": RepoQABenchmark,
    "toolbench": ToolBenchBenchmark,
    "aider-polyglot": AiderPolyglotBenchmark,
    "terminalbench": TerminalBenchBenchmark,
    "gaia": GAIABenchmark,
    "agentbench": AgentBenchBenchmark,
    "webarena": WebArenaBenchmark,
    "mlagentbench": MLAgentBenchBenchmark,
    "intercode": InterCodeBenchmark,
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
