"""Main evaluation harness orchestrating parallel task execution."""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .benchmarks import Benchmark, create_benchmark
from .cache import ResultCache
from .config import HarnessConfig
from .docker_env import DockerEnvironmentManager, TaskEnvironment
from .evaluation import EvaluationResult
from .harnesses import AgentHarness, AgentResult, create_harness
from .incremental_save import save_task_result_incremental
from .log_formatter import InstanceLogWriter
from .pricing import calculate_cost
from .profiler import PerformanceProfiler

console = Console()


class SimpleNamespace:
    """Simple object to hold attributes from a dictionary."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with keyword arguments as attributes."""
        self.__dict__.update(kwargs)


def dict_to_namespace(data: Any) -> Any:
    """Recursively convert dict to SimpleNamespace for attribute access.

    Args:
        data: Data to convert (dict, list, or primitive).

    Returns:
        Converted data with dicts as SimpleNamespace objects.
    """
    if isinstance(data, dict):
        return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in data.items()})
    elif isinstance(data, list):
        return [dict_to_namespace(item) for item in data]
    else:
        return data


@dataclass
class TaskResult:
    """Result for a single task."""

    instance_id: str
    mcp: dict[str, Any] | None = None  # Legacy single server
    mcp_server_a: dict[str, Any] | None = None  # Comparison mode: first server
    mcp_server_b: dict[str, Any] | None = None  # Comparison mode: second server
    baseline: dict[str, Any] | None = None

    @property
    def comparison_mode(self) -> bool:
        """Check if this result is from comparison mode."""
        return self.mcp_server_a is not None and self.mcp_server_b is not None


@dataclass
class EvaluationResults:
    """Complete evaluation results."""

    metadata: dict[str, Any]
    summary: dict[str, Any]
    tasks: list[TaskResult]


def agent_result_to_dict(
    result: AgentResult,
    eval_result: EvaluationResult | None,
    model_id: str,
    runtime_seconds: float | None = None,
) -> dict[str, Any]:
    """Convert agent and evaluation results to dictionary.

    Args:
        result: Agent result with token usage.
        eval_result: Evaluation result (if patch was generated).
        model_id: Model ID for cost calculation.
        runtime_seconds: Wall-clock runtime in seconds (optional).

    Returns:
        Dictionary with agent results including cost information.
    """
    data: dict[str, Any] = {
        "patch_generated": bool(result.patch),
        "tokens": {
            "input": result.tokens_input,
            "output": result.tokens_output,
        },
        "iterations": result.iterations,
        "tool_calls": result.tool_calls,
    }

    # Add runtime if provided
    if runtime_seconds is not None:
        data["runtime_seconds"] = runtime_seconds

    # Use cost from API if available (includes cache tokens)
    # Otherwise fall back to calculation for backward compatibility
    if result.cost_usd is not None:
        data["cost"] = result.cost_usd
    else:
        cost = calculate_cost(
            model_id=model_id,
            input_tokens=result.tokens_input,
            output_tokens=result.tokens_output,
        )
        if cost is not None:
            data["cost"] = cost

    if result.tool_usage:
        data["tool_usage"] = result.tool_usage

    if result.tool_failures:
        data["tool_failures"] = result.tool_failures

    if result.tool_errors:
        data["tool_errors"] = result.tool_errors

    if result.profiling_report:
        data["profiling"] = result.profiling_report

    if result.error:
        data["error"] = result.error
        # Add status field to distinguish timeouts from other errors
        if "timed out" in result.error.lower() or "timeout" in result.error.lower():
            data["status"] = "timeout"

    if result.messages:
        data["messages"] = result.messages

    if eval_result:
        data["resolved"] = getattr(eval_result, "resolved", False)
        data["patch_applied"] = getattr(
            eval_result, "patch_applied", True
        )  # Default True for successful evals

        if getattr(eval_result, "fail_to_pass", None):
            data["fail_to_pass"] = {
                "passed": eval_result.fail_to_pass.passed,
                "total": eval_result.fail_to_pass.total,
            }

        if getattr(eval_result, "pass_to_pass", None):
            data["pass_to_pass"] = {
                "passed": eval_result.pass_to_pass.passed,
                "total": eval_result.pass_to_pass.total,
            }

        if getattr(eval_result, "error", None):
            data["eval_error"] = eval_result.error
    else:
        data["resolved"] = False
        data["patch_applied"] = False

    return data


def _create_mcp_agent(
    config: HarnessConfig,
    benchmark: Benchmark,
    verbosity: int = 1,
    log_file: TextIO | InstanceLogWriter | None = None,
    mcp_logs_dir: Path | None = None,
    mcp_server_config: Any = None,
) -> AgentHarness:
    """Create the agent harness based on config.

    Args:
        config: Harness configuration.
        benchmark: Benchmark instance for getting default prompt.
        verbosity: Verbosity level (0=silent, 1=summary, 2=detailed).
        log_file: Optional file handle for writing raw JSON logs.
        mcp_logs_dir: Directory for MCP server logs.
        mcp_server_config: Optional explicit MCP server config (for comparison mode).

    Returns:
        Configured AgentHarness.
    """
    # Use custom prompt if provided, otherwise use benchmark's default prompt
    prompt = config.agent_prompt if config.agent_prompt else benchmark.get_prompt_template()

    # Use explicit server config if provided, otherwise fall back to config.mcp_server
    server_config = mcp_server_config if mcp_server_config is not None else config.mcp_server

    return create_harness(
        config.agent_harness,
        model=config.model,
        mcp_server=server_config,
        prompt=prompt,
        max_iterations=config.max_iterations,
        verbosity=verbosity,
        log_file=log_file,
        mcp_logs_dir=mcp_logs_dir,
        thinking_budget=config.thinking_budget,
    )


def _create_baseline_agent(
    config: HarnessConfig,
    benchmark: Benchmark,
    verbosity: int = 1,
    log_file: TextIO | InstanceLogWriter | None = None,
) -> AgentHarness:
    """Create a baseline agent (same as MCP agent, but without MCP server).

    Args:
        config: Harness configuration.
        benchmark: Benchmark instance for getting default prompt.
        verbosity: Verbosity level (0=silent, 1=summary, 2=detailed).
        log_file: Optional file handle for writing raw JSON logs.

    Returns:
        Configured AgentHarness without MCP server.
    """
    # Use custom prompt if provided, otherwise use benchmark's default prompt
    prompt = config.agent_prompt if config.agent_prompt else benchmark.get_prompt_template()

    return create_harness(
        config.agent_harness,
        model=config.model,
        mcp_server=None,
        prompt=prompt,
        max_iterations=config.max_iterations,
        verbosity=verbosity,
        log_file=log_file,
        thinking_budget=config.thinking_budget,
    )


async def run_single_task(
    task: dict[str, Any],
    config: HarnessConfig,
    docker_manager: DockerEnvironmentManager,
    benchmark: Benchmark,
    run_mcp: bool,
    run_baseline: bool,
    verbose: bool,
    verbosity: int = 1,
    log_file: TextIO | None = None,
    log_dir: Path | None = None,
    cache: ResultCache | None = None,
    mcp_logs_dir: Path | None = None,
) -> TaskResult:
    """Run evaluation for a single task.

    Args:
        task: Task dictionary from benchmark.
        config: Harness configuration.
        docker_manager: Docker environment manager.
        benchmark: Benchmark instance for evaluation.
        run_mcp: Whether to run MCP evaluation.
        run_baseline: Whether to run baseline evaluation.
        verbose: Enable verbose output.
        verbosity: Verbosity level (0=silent, 1=summary, 2=detailed).
        log_file: Optional file handle for writing raw JSON logs.
        log_dir: Optional directory for per-instance JSON log files.
        cache: Optional result cache.
        mcp_logs_dir: Directory for MCP server logs.

    Returns:
        TaskResult with results for both runs.
    """
    instance_id = task["instance_id"]
    result = TaskResult(instance_id=instance_id)

    if run_mcp:
        if config.comparison_mode:
            # Run both servers in comparison mode
            # Run server A
            mcp_log_writer_a: InstanceLogWriter | None = None
            if log_dir:
                mcp_log_writer_a = InstanceLogWriter(log_dir, instance_id, "mcp_server_a")
            try:
                result.mcp_server_a = await _run_mcp_evaluation(
                    task,
                    config,
                    docker_manager,
                    benchmark,
                    verbose,
                    verbosity,
                    mcp_log_writer_a if mcp_log_writer_a else log_file,
                    cache,
                    mcp_logs_dir,
                    mcp_server_config=config.mcp_server_a,
                    server_name="server_a",
                )
            finally:
                if mcp_log_writer_a:
                    mcp_log_writer_a.close()

            # Run server B
            mcp_log_writer_b: InstanceLogWriter | None = None
            if log_dir:
                mcp_log_writer_b = InstanceLogWriter(log_dir, instance_id, "mcp_server_b")
            try:
                result.mcp_server_b = await _run_mcp_evaluation(
                    task,
                    config,
                    docker_manager,
                    benchmark,
                    verbose,
                    verbosity,
                    mcp_log_writer_b if mcp_log_writer_b else log_file,
                    cache,
                    mcp_logs_dir,
                    mcp_server_config=config.mcp_server_b,
                    server_name="server_b",
                )
            finally:
                if mcp_log_writer_b:
                    mcp_log_writer_b.close()
        else:
            # Single server mode (legacy)
            mcp_log_writer: InstanceLogWriter | None = None
            if log_dir:
                mcp_log_writer = InstanceLogWriter(log_dir, instance_id, "mcp")
            try:
                result.mcp = await _run_mcp_evaluation(
                    task,
                    config,
                    docker_manager,
                    benchmark,
                    verbose,
                    verbosity,
                    mcp_log_writer if mcp_log_writer else log_file,
                    cache,
                    mcp_logs_dir,
                )
            finally:
                if mcp_log_writer:
                    mcp_log_writer.close()

    if run_baseline:
        baseline_log_writer: InstanceLogWriter | None = None
        if log_dir:
            baseline_log_writer = InstanceLogWriter(log_dir, instance_id, "baseline")
        try:
            result.baseline = await _run_baseline_evaluation(
                task,
                config,
                docker_manager,
                benchmark,
                verbose,
                verbosity,
                baseline_log_writer if baseline_log_writer else log_file,
                cache,
            )
        finally:
            if baseline_log_writer:
                baseline_log_writer.close()

    return result


async def _run_mcp_evaluation(
    task: dict[str, Any],
    config: HarnessConfig,
    docker_manager: DockerEnvironmentManager,
    benchmark: Benchmark,
    verbose: bool,
    verbosity: int = 1,
    log_file: TextIO | InstanceLogWriter | None = None,
    cache: ResultCache | None = None,
    mcp_logs_dir: Path | None = None,
    mcp_server_config: Any = None,
    server_name: str = "mcp",
) -> dict[str, Any]:
    """Run MCP agent evaluation with optional caching.

    Args:
        task: Task dictionary from benchmark.
        config: Harness configuration.
        docker_manager: Docker environment manager.
        benchmark: Benchmark instance.
        verbose: Enable verbose output.
        verbosity: Verbosity level.
        log_file: Optional log file writer.
        cache: Optional result cache.
        mcp_logs_dir: Directory for MCP server logs.
        mcp_server_config: Optional explicit MCP server config (for comparison mode).
        server_name: Server name for logging/identification (default: "mcp").

    Returns:
        Dictionary with evaluation results.
    """
    # Check cache first if enabled
    if cache and cache.enabled:
        prompt = config.agent_prompt if config.agent_prompt else benchmark.get_prompt_template()
        cached_result = cache.get(task, config, prompt, is_mcp=True)
        if cached_result is not None:
            # Add cache hit marker to result
            cached_result["cache_hit"] = True
            return cached_result

    # Initialize profiler if enabled
    profiler = None
    if config.enable_profiling:
        profiler = PerformanceProfiler(enable_memory_profiling=True)
        profiler.start_task()

    start_time = time.time()
    env: TaskEnvironment | None = None
    try:
        # Track Docker environment creation time
        docker_start = time.time()
        env = await benchmark.create_environment(task, docker_manager)
        docker_end = time.time()
        if profiler:
            profiler.record_docker_startup(docker_end - docker_start)

        agent = _create_mcp_agent(
            config, benchmark, verbosity, log_file, mcp_logs_dir, mcp_server_config
        )

        # Sample memory before agent execution
        if profiler:
            profiler.sample_memory()

        instance_id = task.get(
            "instance_id", f"{task.get('project', 'unknown')}_{task.get('bug_id', 'unknown')}"
        )
        agent_result = await asyncio.wait_for(
            agent.solve(
                task,
                env.host_workdir,
                timeout=config.timeout_seconds,
                verbose=verbose,
                task_id=f"{instance_id}:{server_name}",
                env=env,  # Pass Docker environment for in-container execution
            ),
            timeout=config.timeout_seconds + 60,
        )

        # Sample memory after agent execution
        if profiler:
            profiler.sample_memory()

        if agent_result.patch:
            eval_result_dict = await benchmark.evaluate(env, task, agent_result.patch)
            # Convert benchmark result format to EvaluationResult-like object
            eval_result = dict_to_namespace(eval_result_dict)
        else:
            eval_result = None

        end_time = time.time()
        runtime_seconds = end_time - start_time

        # Finalize profiling report
        if profiler:
            profiler.end_task()
            # Use agent_result's profiling_report if available, otherwise generate from profiler
            if not agent_result.profiling_report:
                agent_result.profiling_report = profiler.generate_report()

        result = agent_result_to_dict(agent_result, eval_result, config.model, runtime_seconds)

        # Store in cache if enabled
        if cache and cache.enabled:
            prompt = config.agent_prompt if config.agent_prompt else benchmark.get_prompt_template()
            cache.put(task, config, prompt, is_mcp=True, result=result)

        return result

    except asyncio.TimeoutError:
        # Note: The agent harness should have captured partial statistics in the AgentResult
        # before raising TimeoutError, but this is a fallback for unexpected timeout locations
        end_time = time.time()
        runtime_seconds = end_time - start_time
        cost = calculate_cost(config.model, 0, 0)
        return {
            "resolved": False,
            "patch_applied": False,
            "status": "timeout",
            "error": "Timeout",
            "tokens": {"input": 0, "output": 0},
            "iterations": 0,
            "tool_calls": 0,
            "cost": cost if cost is not None else 0.0,
            "runtime_seconds": runtime_seconds,
        }
    except Exception as e:
        end_time = time.time()
        runtime_seconds = end_time - start_time
        cost = calculate_cost(config.model, 0, 0)
        return {
            "resolved": False,
            "patch_applied": False,
            "error": str(e),
            "tokens": {"input": 0, "output": 0},
            "iterations": 0,
            "tool_calls": 0,
            "cost": cost if cost is not None else 0.0,
            "runtime_seconds": runtime_seconds,
        }
    finally:
        if env:
            # Track Docker teardown time
            teardown_start = time.time()
            await env.cleanup()
            if profiler:
                teardown_end = time.time()
                profiler.record_docker_teardown(teardown_end - teardown_start)


async def _run_baseline_evaluation(
    task: dict[str, Any],
    config: HarnessConfig,
    docker_manager: DockerEnvironmentManager,
    benchmark: Benchmark,
    verbose: bool,
    verbosity: int = 1,
    log_file: TextIO | InstanceLogWriter | None = None,
    cache: ResultCache | None = None,
) -> dict[str, Any]:
    """Run baseline agent evaluation (same harness as MCP, but without MCP server).

    Args:
        task: Task dictionary from benchmark.
        config: Harness configuration.
        docker_manager: Docker environment manager.
        benchmark: Benchmark instance.
        verbose: Enable verbose output.
        verbosity: Verbosity level.
        log_file: Optional log file writer.
        cache: Optional result cache.

    Returns:
        Dictionary with evaluation results.
    """
    # Check cache first if enabled
    if cache and cache.enabled:
        prompt = config.agent_prompt if config.agent_prompt else benchmark.get_prompt_template()
        cached_result = cache.get(task, config, prompt, is_mcp=False)
        if cached_result is not None:
            # Add cache hit marker to result
            cached_result["cache_hit"] = True
            return cached_result

    # Initialize profiler if enabled
    profiler = None
    if config.enable_profiling:
        profiler = PerformanceProfiler(enable_memory_profiling=True)
        profiler.start_task()

    start_time = time.time()
    env: TaskEnvironment | None = None
    try:
        # Track Docker environment creation time
        docker_start = time.time()
        env = await benchmark.create_environment(task, docker_manager)
        docker_end = time.time()
        if profiler:
            profiler.record_docker_startup(docker_end - docker_start)

        agent = _create_baseline_agent(config, benchmark, verbosity, log_file)

        # Sample memory before agent execution
        if profiler:
            profiler.sample_memory()

        instance_id = task.get(
            "instance_id", f"{task.get('project', 'unknown')}_{task.get('bug_id', 'unknown')}"
        )
        agent_result = await asyncio.wait_for(
            agent.solve(
                task,
                env.host_workdir,
                timeout=config.timeout_seconds,
                verbose=verbose,
                task_id=f"{instance_id}:baseline",
                env=env,  # Pass Docker environment for in-container execution
            ),
            timeout=config.timeout_seconds + 60,
        )

        # Sample memory after agent execution
        if profiler:
            profiler.sample_memory()

        if agent_result.patch:
            eval_result_dict = await benchmark.evaluate(env, task, agent_result.patch)
            # Convert benchmark result format to EvaluationResult-like object
            eval_result = dict_to_namespace(eval_result_dict)
        else:
            eval_result = None

        end_time = time.time()
        runtime_seconds = end_time - start_time

        # Finalize profiling report
        if profiler:
            profiler.end_task()
            # Use agent_result's profiling_report if available, otherwise generate from profiler
            if not agent_result.profiling_report:
                agent_result.profiling_report = profiler.generate_report()

        result = agent_result_to_dict(agent_result, eval_result, config.model, runtime_seconds)

        # Store in cache if enabled
        if cache and cache.enabled:
            prompt = config.agent_prompt if config.agent_prompt else benchmark.get_prompt_template()
            cache.put(task, config, prompt, is_mcp=False, result=result)

        return result

    except asyncio.TimeoutError:
        # Note: The agent harness should have captured partial statistics in the AgentResult
        # before raising TimeoutError, but this is a fallback for unexpected timeout locations
        end_time = time.time()
        runtime_seconds = end_time - start_time
        cost = calculate_cost(config.model, 0, 0)
        return {
            "resolved": False,
            "patch_applied": False,
            "status": "timeout",
            "error": "Timeout",
            "tokens": {"input": 0, "output": 0},
            "iterations": 0,
            "tool_calls": 0,
            "cost": cost if cost is not None else 0.0,
            "runtime_seconds": runtime_seconds,
        }
    except Exception as e:
        end_time = time.time()
        runtime_seconds = end_time - start_time
        cost = calculate_cost(config.model, 0, 0)
        return {
            "resolved": False,
            "patch_applied": False,
            "error": str(e),
            "tokens": {"input": 0, "output": 0},
            "iterations": 0,
            "tool_calls": 0,
            "cost": cost if cost is not None else 0.0,
            "runtime_seconds": runtime_seconds,
        }
    finally:
        if env:
            # Track Docker teardown time
            teardown_start = time.time()
            await env.cleanup()
            if profiler:
                teardown_end = time.time()
                profiler.record_docker_teardown(teardown_end - teardown_start)


def _calculate_mcp_tool_stats(results: list[TaskResult]) -> dict[str, Any]:
    """Calculate MCP tool call failure statistics across all tasks.

    Args:
        results: List of task results.

    Returns:
        Dictionary with MCP tool statistics including total calls, failures, and per-tool breakdown.
    """
    total_calls = 0
    total_failures = 0
    tool_usage: dict[str, int] = {}
    tool_failures: dict[str, int] = {}
    tool_errors: dict[str, list[str]] = {}

    for r in results:
        if r.mcp:
            # Aggregate total tool calls (successful + failed)
            if "tool_usage" in r.mcp:
                for tool_name, count in r.mcp["tool_usage"].items():
                    tool_usage[tool_name] = tool_usage.get(tool_name, 0) + count
                    total_calls += count

            # Aggregate failed tool calls
            if "tool_failures" in r.mcp:
                for tool_name, count in r.mcp["tool_failures"].items():
                    tool_failures[tool_name] = tool_failures.get(tool_name, 0) + count
                    total_failures += count

            # Collect error messages (sample only, not all)
            if "tool_errors" in r.mcp:
                for tool_name, errors in r.mcp["tool_errors"].items():
                    if tool_name not in tool_errors:
                        tool_errors[tool_name] = []
                    # Keep only first few unique errors per tool
                    for error in errors:
                        if error not in tool_errors[tool_name] and len(tool_errors[tool_name]) < 3:
                            tool_errors[tool_name].append(error)

    failure_rate = total_failures / total_calls if total_calls > 0 else 0.0

    # Build per-tool breakdown
    # Note: tool_usage contains total calls (successful + failed)
    # tool_failures contains only failed calls
    # So succeeded = total - failed, not total + failed
    by_tool = {}
    for tool_name in set(list(tool_usage.keys()) + list(tool_failures.keys())):
        total_calls_for_tool = tool_usage.get(tool_name, 0)
        failure_count = tool_failures.get(tool_name, 0)
        # Derive success count (avoid negative values in edge cases)
        success_count = max(total_calls_for_tool - failure_count, 0)
        tool_failure_rate = (
            failure_count / total_calls_for_tool if total_calls_for_tool > 0 else 0.0
        )

        by_tool[tool_name] = {
            "total": total_calls_for_tool,
            "succeeded": success_count,
            "failed": failure_count,
            "failure_rate": tool_failure_rate,
        }

        # Add sample errors if available
        if tool_name in tool_errors and tool_errors[tool_name]:
            by_tool[tool_name]["sample_errors"] = tool_errors[tool_name]

    return {
        "total_tool_calls": total_calls,
        "total_failures": total_failures,
        "failure_rate": failure_rate,
        "by_tool": by_tool,
        "has_failures": total_failures > 0,
        "high_failure_rate": failure_rate > 0.1,  # Flag if >10% failure rate
    }


def _aggregate_comparison_results(results: list[TaskResult]) -> dict[str, Any]:
    """Aggregate results for side-by-side comparison.

    Args:
        results: List of task results from comparison mode evaluation.

    Returns:
        Dictionary with aggregated comparison statistics.
    """
    stats_a = {"total": 0, "resolved": 0, "cost": 0.0, "tool_calls": 0}
    stats_b = {"total": 0, "resolved": 0, "cost": 0.0, "tool_calls": 0}

    a_unique_wins: list[str] = []  # Tasks where only A resolved
    b_unique_wins: list[str] = []  # Tasks where only B resolved
    both_wins: list[str] = []  # Tasks where both resolved
    both_fail: list[str] = []  # Tasks where both failed

    for r in results:
        if r.mcp_server_a:
            stats_a["total"] += 1
            if r.mcp_server_a.get("resolved"):
                stats_a["resolved"] += 1
            stats_a["cost"] += r.mcp_server_a.get("cost", 0.0)
            stats_a["tool_calls"] += r.mcp_server_a.get("tool_calls", 0)

        if r.mcp_server_b:
            stats_b["total"] += 1
            if r.mcp_server_b.get("resolved"):
                stats_b["resolved"] += 1
            stats_b["cost"] += r.mcp_server_b.get("cost", 0.0)
            stats_b["tool_calls"] += r.mcp_server_b.get("tool_calls", 0)

        # Categorize outcomes
        a_resolved = r.mcp_server_a and r.mcp_server_a.get("resolved")
        b_resolved = r.mcp_server_b and r.mcp_server_b.get("resolved")

        if a_resolved and not b_resolved:
            a_unique_wins.append(r.instance_id)
        elif b_resolved and not a_resolved:
            b_unique_wins.append(r.instance_id)
        elif a_resolved and b_resolved:
            both_wins.append(r.instance_id)
        elif r.mcp_server_a and r.mcp_server_b:
            both_fail.append(r.instance_id)

    # Calculate rates and improvements
    rate_a = stats_a["resolved"] / stats_a["total"] if stats_a["total"] > 0 else 0
    rate_b = stats_b["resolved"] / stats_b["total"] if stats_b["total"] > 0 else 0

    improvement_pct = 0.0
    if rate_b > 0:
        improvement_pct = ((rate_a - rate_b) / rate_b) * 100

    return {
        "stats_a": stats_a,
        "stats_b": stats_b,
        "resolution_rate_a": rate_a,
        "resolution_rate_b": rate_b,
        "a_vs_b_delta": stats_a["resolved"] - stats_b["resolved"],
        "a_vs_b_improvement_pct": improvement_pct,
        "a_unique_wins": a_unique_wins,
        "b_unique_wins": b_unique_wins,
        "both_wins": both_wins,
        "both_fail": both_fail,
    }


async def run_evaluation(
    config: HarnessConfig,
    run_mcp: bool = True,
    run_baseline: bool = True,
    verbose: bool = False,
    verbosity: int = 1,
    log_file: TextIO | None = None,
    log_dir: Path | None = None,
    task_ids: list[str] | None = None,
    state_tracker: Any | None = None,
    from_task: str | None = None,
    incremental_save_path: Path | None = None,
    mcp_logs_dir: Path | None = None,
) -> EvaluationResults:
    """Run the full evaluation.

    Args:
        config: Harness configuration.
        run_mcp: Whether to run MCP evaluation.
        run_baseline: Whether to run baseline evaluation.
        verbose: Enable verbose output.
        verbosity: Verbosity level (0=silent, 1=summary, 2=detailed).
        log_file: Optional file handle for writing raw JSON logs.
        log_dir: Optional directory for per-instance JSON log files.
        task_ids: Specific task IDs to run (None for all).
        state_tracker: Optional state tracker for incremental evaluation.
        from_task: Optional task ID to resume from.
        incremental_save_path: Optional path to save results incrementally for crash recovery.
        mcp_logs_dir: Directory for MCP server logs.

    Returns:
        EvaluationResults with all results.
    """
    # Create benchmark instance
    benchmark_kwargs: dict[str, Any] = {}
    if config.benchmark == "cybergym":
        benchmark_kwargs["level"] = config.cybergym_level

    benchmark = create_benchmark(config.benchmark, **benchmark_kwargs)

    # Display benchmark name
    dataset_name = getattr(benchmark, "dataset", "unknown")
    console.print(f"[dim]Loading benchmark: {config.benchmark} (dataset: {dataset_name})[/dim]")

    # Load tasks from benchmark
    tasks = benchmark.load_tasks(
        sample_size=config.sample_size,
        task_ids=task_ids,
        filter_difficulty=config.filter_difficulty,
        filter_category=config.filter_category,
        filter_tags=config.filter_tags,
    )

    # Apply state tracker filtering and resume logic
    tasks_to_run = tasks
    skipped_count = 0
    resumed_from = False

    if state_tracker:
        from .state_tracker import compute_task_hash

        # Load existing results from state
        state_tracker.load_state()

        # Handle from_task: find starting position and run from there
        if from_task:
            found = False
            for i, task in enumerate(tasks):
                if task["instance_id"] == from_task:
                    tasks_to_run = tasks[i:]
                    skipped_count = i
                    resumed_from = True
                    found = True
                    break
            if not found:
                console.print(
                    f"[yellow]Warning: Task {from_task} not found, running all tasks[/yellow]"
                )
        else:
            # Filter out already completed tasks (if config unchanged)
            filtered_tasks = []
            cached_results: list[TaskResult] = []

            for task in tasks:
                instance_id = task["instance_id"]
                task_hash = compute_task_hash(task)

                if state_tracker.is_task_completed(instance_id, task_hash):
                    # Task is completed and unchanged, use cached result
                    cached_state = state_tracker.get_task_result(instance_id)
                    if cached_state:
                        cached_results.append(
                            TaskResult(
                                instance_id=instance_id,
                                mcp=cached_state.mcp_result,
                                baseline=cached_state.baseline_result,
                            )
                        )
                        skipped_count += 1
                else:
                    filtered_tasks.append(task)

            tasks_to_run = filtered_tasks

        if skipped_count > 0:
            if resumed_from:
                console.print(
                    f"[cyan]Resuming from task {from_task}, skipping {skipped_count} tasks[/cyan]"
                )
            else:
                console.print(
                    f"[cyan]Using cached results for {skipped_count} completed tasks[/cyan]"
                )

    console.print(f"[dim]Evaluating {len(tasks_to_run)} tasks[/dim]")
    console.print(f"[dim]Provider: {config.provider}, Harness: {config.agent_harness}[/dim]")

    # Initialize cache if enabled
    cache: ResultCache | None = None
    if config.cache_enabled:
        cache = ResultCache(cache_dir=config.cache_dir, enabled=True)
        console.print(f"[dim]Cache enabled: {cache.cache_dir}[/dim]")

    # Prepare metadata for incremental saves
    metadata_for_save = None
    if incremental_save_path:
        metadata_for_save = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "provider": config.provider,
                "agent_harness": config.agent_harness,
                "model": config.model,
                "dataset": dataset_name,
                "sample_size": len(tasks),
                "timeout_seconds": config.timeout_seconds,
                "max_concurrent": config.max_concurrent,
                "comparison_mode": config.comparison_mode,
            },
        }
        # Add MCP server config based on mode
        if config.comparison_mode:
            metadata_for_save["mcp_server_a"] = {
                "name": config.mcp_server_a.name if config.mcp_server_a else "unknown",
                "command": config.mcp_server_a.command if config.mcp_server_a else "",
                "args": config.mcp_server_a.args if config.mcp_server_a else [],
            }
            metadata_for_save["mcp_server_b"] = {
                "name": config.mcp_server_b.name if config.mcp_server_b else "unknown",
                "command": config.mcp_server_b.command if config.mcp_server_b else "",
                "args": config.mcp_server_b.args if config.mcp_server_b else [],
            }
        else:
            metadata_for_save["mcp_server"] = {
                "command": config.mcp_server.command if config.mcp_server else "",
                "args": config.mcp_server.args if config.mcp_server else [],
            }

    docker_manager = DockerEnvironmentManager(use_prebuilt=config.use_prebuilt_images)

    results: list[TaskResult] = []
    # Add cached results if using state tracker
    if state_tracker and "cached_results" in locals():
        results.extend(cached_results)
    semaphore = asyncio.Semaphore(config.max_concurrent)
    budget_exceeded = False
    current_cost = 0.0

    async def run_with_semaphore(task: dict[str, Any]) -> TaskResult | None:
        nonlocal current_cost, budget_exceeded

        # Check budget before running task
        if config.budget and current_cost >= config.budget:
            budget_exceeded = True
            return None

        async with semaphore:
            result = await run_single_task(
                task,
                config,
                docker_manager,
                benchmark,
                run_mcp,
                run_baseline,
                verbose,
                verbosity,
                log_file,
                log_dir,
                cache,
                mcp_logs_dir,
            )

            # Update current cost
            if config.comparison_mode:
                if result.mcp_server_a and result.mcp_server_a.get("cost"):
                    current_cost += result.mcp_server_a.get("cost", 0.0)
                if result.mcp_server_b and result.mcp_server_b.get("cost"):
                    current_cost += result.mcp_server_b.get("cost", 0.0)
            else:
                if result.mcp and result.mcp.get("cost"):
                    current_cost += result.mcp.get("cost", 0.0)
            if result.baseline and result.baseline.get("cost"):
                current_cost += result.baseline.get("cost", 0.0)

            # Save state after task completion
            if state_tracker:
                from .state_tracker import compute_task_hash

                task_hash = compute_task_hash(task)
                error = None
                if result.mcp and result.mcp.get("error"):
                    error = result.mcp.get("error")
                elif result.baseline and result.baseline.get("error"):
                    error = result.baseline.get("error")

                state_tracker.mark_task_completed(
                    instance_id=result.instance_id,
                    task_hash=task_hash,
                    mcp_result=result.mcp,
                    baseline_result=result.baseline,
                    error=error,
                )
                state_tracker.save_state()

            return result

    progress_console = Console(force_terminal=True)

    # Track currently running tasks with progress indicators
    task_progress_items: dict[str, Any] = {}

    async def run_with_progress_tracking(
        task: dict[str, Any], progress: Progress
    ) -> TaskResult | None:
        """Run a task with progress tracking."""
        instance_id = task["instance_id"]

        # Add progress indicator for this specific task
        task_progress = progress.add_task(
            f"[cyan]Running {instance_id}...",
            total=None,  # Indeterminate progress for individual tasks
        )
        task_progress_items[instance_id] = task_progress

        try:
            result = await run_with_semaphore(task)

            # Update progress to show completion or skip status
            if instance_id in task_progress_items:
                if result is not None:
                    # Task completed successfully
                    progress.update(
                        task_progress_items[instance_id],
                        description=f"[green]✓ {instance_id}",
                    )
                    # Remove completed task to avoid clutter
                    progress.remove_task(task_progress_items[instance_id])
                    del task_progress_items[instance_id]
                else:
                    # Task was skipped (budget exceeded)
                    progress.update(
                        task_progress_items[instance_id],
                        description=f"[yellow]⊘ {instance_id} (skipped)",
                    )

            return result
        except Exception as e:
            # Update progress to show error
            if instance_id in task_progress_items:
                progress.update(
                    task_progress_items[instance_id],
                    description=f"[red]✗ {instance_id}: {str(e)[:50]}",
                )
                progress.remove_task(task_progress_items[instance_id])
                del task_progress_items[instance_id]
            raise

    try:
        if verbose:
            # In verbose mode, show per-task progress with spinners (no overall bar)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=progress_console,
            ) as progress:
                # Create async tasks for all work items
                async_tasks = [
                    asyncio.create_task(run_with_progress_tracking(task, progress))
                    for task in tasks_to_run
                ]

                for coro in asyncio.as_completed(async_tasks):
                    result = await coro
                    if result is not None:
                        results.append(result)

                        # Save result incrementally for crash recovery
                        if incremental_save_path:
                            save_task_result_incremental(
                                result, incremental_save_path, metadata_for_save
                            )
                            # Only include metadata on first save
                            metadata_for_save = None

                    if budget_exceeded:
                        progress.stop()
                        console.print(
                            f"\n[yellow]Budget limit of ${config.budget:.2f} reached. "
                            f"Stopping evaluation (spent ${current_cost:.4f}).[/yellow]"
                        )
                        # Cancel all pending tasks
                        for task in async_tasks:
                            if not task.done():
                                task.cancel()
                        # Wait for cancellation to complete
                        await asyncio.gather(*async_tasks, return_exceptions=True)
                        break
        else:
            # In non-verbose mode, show overall progress bar + per-task spinners
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=progress_console,
            ) as progress:
                main_task = progress.add_task(
                    "Evaluating tasks...", total=len(tasks_to_run), completed=0
                )

                # Create async tasks for all work items
                async_tasks = [
                    asyncio.create_task(run_with_progress_tracking(task, progress))
                    for task in tasks_to_run
                ]

                for coro in asyncio.as_completed(async_tasks):
                    result = await coro
                    if result is not None:
                        results.append(result)
                        progress.update(main_task, advance=1)

                        # Save result incrementally for crash recovery
                        if incremental_save_path:
                            save_task_result_incremental(
                                result, incremental_save_path, metadata_for_save
                            )
                            # Only include metadata on first save
                            metadata_for_save = None

                    if budget_exceeded:
                        progress.stop()
                        console.print(
                            f"\n[yellow]Budget limit of ${config.budget:.2f} reached. "
                            f"Stopping evaluation (spent ${current_cost:.4f}).[/yellow]"
                        )
                        # Cancel all pending tasks
                        for task in async_tasks:
                            if not task.done():
                                task.cancel()
                        # Wait for cancellation to complete
                        await asyncio.gather(*async_tasks, return_exceptions=True)
                        break
    finally:
        await docker_manager.cleanup_all()

    # Check if we're in comparison mode
    if config.comparison_mode:
        # Use comparison aggregation
        comparison_summary = _aggregate_comparison_results(results)
    else:
        # Standard single-server aggregation
        mcp_resolved = 0
        baseline_resolved = 0
        mcp_total = 0
        baseline_total = 0
        mcp_cost = 0.0
        baseline_cost = 0.0

        for r in results:
            if r.mcp:
                mcp_total += 1
                if r.mcp.get("resolved"):
                    mcp_resolved += 1
                if r.mcp.get("cost"):
                    mcp_cost += r.mcp.get("cost", 0.0)
            if r.baseline:
                baseline_total += 1
                if r.baseline.get("resolved"):
                    baseline_resolved += 1
                if r.baseline.get("cost"):
                    baseline_cost += r.baseline.get("cost", 0.0)

        mcp_rate = mcp_resolved / mcp_total if mcp_total > 0 else 0
        baseline_rate = baseline_resolved / baseline_total if baseline_total > 0 else 0

        if baseline_rate > 0:
            improvement = ((mcp_rate - baseline_rate) / baseline_rate) * 100
            improvement_str = f"{improvement:+.1f}%"
        else:
            improvement_str = "N/A"

    # Calculate cost-effectiveness metrics and statistics
    from .pricing import calculate_cost_effectiveness
    from .reporting import calculate_tool_coverage
    from .statistics import calculate_comprehensive_statistics

    # Create temporary results object for coverage and stats calculation
    temp_results = EvaluationResults(
        metadata={},
        summary={},
        tasks=results,
    )

    if not config.comparison_mode:
        cost_effectiveness = calculate_cost_effectiveness(
            mcp_cost=mcp_cost,
            baseline_cost=baseline_cost,
            mcp_resolved=mcp_resolved,
            baseline_resolved=baseline_resolved,
        )
        tool_coverage = calculate_tool_coverage(temp_results)
        comprehensive_stats = calculate_comprehensive_statistics(temp_results)
        mcp_tool_stats = _calculate_mcp_tool_stats(results)
    else:
        # For comparison mode, we'll skip some of these advanced stats for now
        # They can be added later if needed
        cost_effectiveness = None
        tool_coverage = None
        comprehensive_stats = None
        mcp_tool_stats = None

    # Build metadata with incremental evaluation stats
    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "model": config.model,
            "provider": config.provider,
            "agent_harness": config.agent_harness,
            "benchmark": config.benchmark,
            "dataset": dataset_name,
            "sample_size": config.sample_size,
            "timeout_seconds": config.timeout_seconds,
            "max_iterations": config.max_iterations,
            "cybergym_level": config.cybergym_level if config.benchmark == "cybergym" else None,
            "budget": config.budget,
            "budget_exceeded": budget_exceeded,
            "comparison_mode": config.comparison_mode,
        },
    }

    # Add MCP server config(s) to metadata
    if config.comparison_mode:
        metadata["mcp_server_a"] = {
            "name": config.mcp_server_a.name if config.mcp_server_a else "unknown",
            "command": config.mcp_server_a.command if config.mcp_server_a else "",
            "args": config.mcp_server_a.args if config.mcp_server_a else [],
            "args_note": "{workdir} is replaced with task repository path at runtime",
        }
        metadata["mcp_server_b"] = {
            "name": config.mcp_server_b.name if config.mcp_server_b else "unknown",
            "command": config.mcp_server_b.command if config.mcp_server_b else "",
            "args": config.mcp_server_b.args if config.mcp_server_b else [],
            "args_note": "{workdir} is replaced with task repository path at runtime",
        }
    else:
        metadata["mcp_server"] = {
            "command": config.mcp_server.command if config.mcp_server else "",
            "args": config.mcp_server.args if config.mcp_server else [],
            "args_note": "{workdir} is replaced with task repository path at runtime",
        }

    # Add incremental evaluation stats if state tracker was used
    if state_tracker:
        metadata["incremental"] = {
            "enabled": True,
            "total_tasks": len(tasks),
            "cached_tasks": skipped_count,
            "evaluated_tasks": len(tasks_to_run),
            "resumed_from": from_task if from_task and resumed_from else None,
        }
    else:
        metadata["incremental"] = {
            "enabled": False,
        }

    # Build summary based on mode
    if config.comparison_mode:
        # Comparison mode summary
        summary = {
            "mcp_server_a": {
                "name": config.mcp_server_a.name if config.mcp_server_a else "unknown",
                "resolved": comparison_summary["stats_a"]["resolved"],
                "total": comparison_summary["stats_a"]["total"],
                "resolution_rate": comparison_summary["resolution_rate_a"],
                "cost": comparison_summary["stats_a"]["cost"],
                "tool_calls": comparison_summary["stats_a"]["tool_calls"],
            },
            "mcp_server_b": {
                "name": config.mcp_server_b.name if config.mcp_server_b else "unknown",
                "resolved": comparison_summary["stats_b"]["resolved"],
                "total": comparison_summary["stats_b"]["total"],
                "resolution_rate": comparison_summary["resolution_rate_b"],
                "cost": comparison_summary["stats_b"]["cost"],
                "tool_calls": comparison_summary["stats_b"]["tool_calls"],
            },
            "comparison": {
                "a_vs_b_delta": comparison_summary["a_vs_b_delta"],
                "a_vs_b_improvement_pct": comparison_summary["a_vs_b_improvement_pct"],
                "a_unique_wins": comparison_summary["a_unique_wins"],
                "b_unique_wins": comparison_summary["b_unique_wins"],
                "both_wins": comparison_summary["both_wins"],
                "both_fail": comparison_summary["both_fail"],
            },
        }
    else:
        # Single server mode summary (original)
        summary = {
            "mcp": {
                "resolved": mcp_resolved,
                "total": mcp_total,
                "rate": mcp_rate,
                "total_cost": mcp_cost,
                "cost_per_task": mcp_cost / mcp_total if mcp_total > 0 else 0.0,
                "cost_per_resolved": cost_effectiveness["mcp_cost_per_resolved"],
            },
            "baseline": {
                "resolved": baseline_resolved,
                "total": baseline_total,
                "rate": baseline_rate,
                "total_cost": baseline_cost,
                "cost_per_task": baseline_cost / baseline_total if baseline_total > 0 else 0.0,
                "cost_per_resolved": cost_effectiveness["baseline_cost_per_resolved"],
            },
            "improvement": improvement_str,
            "cost_comparison": {
                "total_difference": mcp_cost - baseline_cost,
                "cost_per_additional_resolution": cost_effectiveness[
                    "cost_per_additional_resolution"
                ],
            },
            "tool_coverage": tool_coverage,
            "mcp_tool_stats": mcp_tool_stats,
            "comprehensive_stats": comprehensive_stats.to_dict(),
        }

    return EvaluationResults(
        metadata=metadata,
        summary=summary,
        tasks=results,
    )
