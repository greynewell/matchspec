---
faq:
  - q: "How do I use the mcpbr Python SDK?"
    a: "Import MCPBenchmark from mcpbr, create an instance with a config dict, YAML path, or HarnessConfig object, then call validate(), dry_run(), or run() to interact with benchmarks programmatically."
  - q: "Can I run benchmarks from Python without the CLI?"
    a: "Yes. The MCPBenchmark class provides validate() and dry_run() for configuration checking and execution planning. Full benchmark execution via run() is planned; currently use the CLI for actual runs."
  - q: "What discovery functions does the SDK provide?"
    a: "The SDK exports list_benchmarks() to enumerate available benchmarks, list_models() for supported models with metadata, list_providers() for provider names, and get_version() for the package version."
---

# SDK Reference

The `mcpbr.sdk` module provides the public Python SDK for programmatic access to MCP server benchmarking. It is the primary entry point for Python users who want to configure, validate, and execute benchmarks without the CLI.

All public symbols are re-exported from the top-level `mcpbr` package.

```python
from mcpbr import MCPBenchmark, BenchmarkResult
from mcpbr import list_benchmarks, list_models, list_providers, get_version
```

---

## MCPBenchmark

The main class for configuring and running MCP benchmarks.

::: mcpbr.sdk.MCPBenchmark
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - validate
        - dry_run
        - run

### Initialization

`MCPBenchmark` accepts three types of configuration input:

=== "From a dict"

    ```python
    from mcpbr import MCPBenchmark

    bench = MCPBenchmark({
        "mcp_server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        },
        "benchmark": "humaneval",
        "model": "sonnet",
        "sample_size": 10,
        "timeout_seconds": 300,
    })
    ```

=== "From a YAML file"

    ```python
    from mcpbr import MCPBenchmark

    bench = MCPBenchmark("mcpbr.yaml")
    # or with a Path object
    from pathlib import Path
    bench = MCPBenchmark(Path("configs/production.yaml"))
    ```

=== "From a HarnessConfig"

    ```python
    from mcpbr import MCPBenchmark
    from mcpbr.config import HarnessConfig, MCPServerConfig

    config = HarnessConfig(
        mcp_server=MCPServerConfig(
            command="uvx",
            args=["my-mcp-server", "--workdir", "{workdir}"],
        ),
        benchmark="swe-bench-verified",
        model="sonnet",
        sample_size=5,
    )
    bench = MCPBenchmark(config)
    ```

!!! warning "File Not Found"
    When passing a file path, `MCPBenchmark` raises `FileNotFoundError` if the file does not exist. When passing a dict, it raises `ValueError` if the configuration is invalid.

### validate()

Check that the configuration is internally consistent before running.

```python
bench = MCPBenchmark({
    "mcp_server": {"command": "npx", "args": ["my-server"]},
    "benchmark": "humaneval",
    "model": "sonnet",
})

is_valid, errors = bench.validate()
if not is_valid:
    for error in errors:
        print(f"Validation error: {error}")
else:
    print("Configuration is valid")
```

**Returns:** `tuple[bool, list[str]]` -- A tuple of `(is_valid, list_of_warnings_or_errors)`.

Validation checks include:

| Check | Description |
|-------|-------------|
| Model registry | Warns if the model ID is not in `SUPPORTED_MODELS` |
| Benchmark registry | Errors if the benchmark name is not in `BENCHMARK_REGISTRY` |
| Provider | Errors if the provider is not in `VALID_PROVIDERS` |

### dry_run()

Generate an execution plan without running anything. Useful for previewing what would happen.

```python
plan = bench.dry_run()
print(plan)
# {
#     "benchmark": "humaneval",
#     "model": "sonnet",
#     "provider": "anthropic",
#     "agent_harness": "claude-code",
#     "timeout_seconds": 300,
#     "max_concurrent": 4,
#     "max_iterations": 10,
#     "sample_size": 10,
#     "mcp_server": {
#         "command": "npx",
#         "args": ["my-server"],
#         "name": "mcpbr",
#     },
# }
```

**Returns:** `dict[str, Any]` -- A dictionary describing the execution plan, including benchmark, model, provider, MCP server config, and runtime settings.

The plan includes comparison mode information when `comparison_mode` is enabled:

```python
bench = MCPBenchmark({
    "comparison_mode": True,
    "mcp_server_a": {"command": "server-a", "name": "Server A"},
    "mcp_server_b": {"command": "server-b", "name": "Server B"},
    "benchmark": "humaneval",
    "model": "sonnet",
})
plan = bench.dry_run()
# plan["comparison_mode"] == True
# plan["mcp_server_a"] and plan["mcp_server_b"] are present
```

### run()

Execute the benchmark asynchronously.

```python
import asyncio
from mcpbr import MCPBenchmark

bench = MCPBenchmark({
    "mcp_server": {"command": "npx", "args": ["my-server", "{workdir}"]},
    "benchmark": "humaneval",
    "model": "sonnet",
})

# Run asynchronously
result = asyncio.run(bench.run())
print(result.success, result.summary)
```

!!! note "Execution Status"
    Full benchmark execution via the SDK `run()` method delegates to an internal `_execute()` method. Currently, `_execute()` raises `NotImplementedError` -- use the `mcpbr` CLI for actual benchmark runs, or mock `MCPBenchmark._execute` for testing.

**Returns:** `BenchmarkResult` -- A dataclass with the evaluation results.

---

## BenchmarkResult

Dataclass representing the result of a benchmark run.

::: mcpbr.sdk.BenchmarkResult
    options:
      show_root_heading: true
      show_source: false

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | `bool` | (required) | Whether the benchmark completed successfully |
| `summary` | `dict[str, Any]` | (required) | Aggregated results (e.g., pass rate, resolved count) |
| `tasks` | `list[dict[str, Any]]` | (required) | Per-task results as a list of dicts |
| `metadata` | `dict[str, Any]` | (required) | Run metadata (benchmark name, model, timestamps, etc.) |
| `total_cost` | `float` | `0.0` | Total API cost in USD |
| `total_tokens` | `int` | `0` | Total tokens consumed |
| `duration_seconds` | `float` | `0.0` | Wall-clock duration of the run |

!!! example "Working with BenchmarkResult"
    ```python
    result = BenchmarkResult(
        success=True,
        summary={"pass_rate": 0.85, "resolved": 17, "total": 20},
        tasks=[{"task_id": "task_1", "resolved": True}, ...],
        metadata={"benchmark": "humaneval", "model": "sonnet"},
        total_cost=1.23,
        total_tokens=150000,
        duration_seconds=245.7,
    )

    if result.success:
        print(f"Pass rate: {result.summary['pass_rate']:.0%}")
        print(f"Cost: ${result.total_cost:.2f}")
        print(f"Duration: {result.duration_seconds:.0f}s")
    ```

---

## Discovery Functions

### list_benchmarks()

List all available benchmarks registered in the system.

```python
from mcpbr import list_benchmarks

benchmarks = list_benchmarks()
for b in benchmarks:
    print(f"{b['name']:25s} {b['class']}")
```

**Returns:** `list[dict[str, str]]` -- Each dict contains `name` (the benchmark identifier) and `class` (the benchmark class name).

!!! example "Sample Output"
    ```
    swe-bench-lite            SWEBenchmark
    swe-bench-verified        SWEBenchmark
    swe-bench-full            SWEBenchmark
    cybergym                  CyberGymBenchmark
    humaneval                 HumanEvalBenchmark
    mcptoolbench              MCPToolBenchmark
    gsm8k                     GSM8KBenchmark
    ...
    ```

### list_providers()

List all supported model providers.

```python
from mcpbr import list_providers

providers = list_providers()
print(providers)
# ['anthropic', 'openai', 'gemini', 'qwen']
```

**Returns:** `list[str]` -- A list of provider name strings.

### list_models()

List all supported models with their metadata.

```python
from mcpbr import list_models

models = list_models()
for m in models:
    print(f"{m['id']:35s} {m['provider']:10s} {m['context_window']:>10,}")
```

**Returns:** `list[dict[str, str]]` -- Each dict contains:

| Key | Type | Description |
|-----|------|-------------|
| `id` | `str` | Model identifier (e.g., `"sonnet"`, `"gpt-4o"`) |
| `provider` | `str` | Provider name (e.g., `"Anthropic"`, `"OpenAI"`) |
| `display_name` | `str` | Human-readable model name |
| `context_window` | `int` | Maximum context window in tokens |
| `supports_tools` | `bool` | Whether the model supports tool calling |
| `notes` | `str` | Additional notes (e.g., alias information) |

### get_version()

Get the current mcpbr version string.

```python
from mcpbr import get_version

version = get_version()
print(version)  # e.g., "0.8.0"
```

**Returns:** `str` -- The version string.

---

## Error Handling

The SDK raises standard Python exceptions:

| Exception | When |
|-----------|------|
| `FileNotFoundError` | Config file path does not exist |
| `ValueError` | Invalid config dict (Pydantic validation failure) |
| `TypeError` | Config argument is not a dict, str, Path, or HarnessConfig |
| `NotImplementedError` | `MCPBenchmark.run()` called (full execution not yet wired into SDK) |

!!! example "Error Handling Pattern"
    ```python
    from mcpbr import MCPBenchmark

    try:
        bench = MCPBenchmark("nonexistent.yaml")
    except FileNotFoundError as e:
        print(f"Config file not found: {e}")

    try:
        bench = MCPBenchmark({"benchmark": "invalid-benchmark"})
    except ValueError as e:
        print(f"Invalid configuration: {e}")
    ```

---

## Testing with the SDK

The SDK is designed to be easily mockable for testing:

```python
import asyncio
from unittest.mock import AsyncMock
from mcpbr import MCPBenchmark, BenchmarkResult

# Create a benchmark instance
bench = MCPBenchmark({
    "mcp_server": {"command": "test-server", "args": []},
    "benchmark": "humaneval",
    "model": "sonnet",
})

# Mock the internal _execute method
bench._execute = AsyncMock(return_value=BenchmarkResult(
    success=True,
    summary={"pass_rate": 0.90},
    tasks=[],
    metadata={},
    total_cost=0.50,
    total_tokens=10000,
    duration_seconds=60.0,
))

# Run the benchmark (uses the mock)
result = asyncio.run(bench.run())
assert result.success
assert result.total_cost == 0.50
```
