---
faq:
  - q: "How do I implement a custom benchmark for mcpbr?"
    a: "Implement the Benchmark protocol from mcpbr.benchmarks.base. Your class must define load_tasks(), normalize_task(), create_environment(), evaluate(), get_prebuilt_image(), and get_prompt_template() methods. Register it in the BENCHMARK_REGISTRY."
  - q: "What benchmarks does mcpbr support out of the box?"
    a: "mcpbr ships with 29 benchmarks including SWE-bench (3 variants), HumanEval, MBPP, GSM8K, MATH, CyberGym, BigCodeBench, APPS, CodeContests, ARC, HellaSwag, TruthfulQA, GAIA, AgentBench, WebArena, and more."
  - q: "What is BenchmarkTask?"
    a: "BenchmarkTask is a normalized dataclass representing a task across different benchmarks. It contains task_id, problem_statement, repo, commit, and metadata fields, providing a common interface regardless of the underlying benchmark format."
---

# Benchmarks API Reference

The `mcpbr.benchmarks` package defines the benchmark abstraction layer and provides implementations for 29 benchmarks. Use the `Benchmark` protocol to add custom benchmarks or interact with existing ones programmatically.

```python
from mcpbr.benchmarks import (
    Benchmark,
    BenchmarkTask,
    BENCHMARK_REGISTRY,
    create_benchmark,
    list_benchmarks,
)
```

---

## Benchmark Protocol

The `Benchmark` protocol defines the interface that all benchmark implementations must satisfy. It is decorated with `@runtime_checkable`, so you can use `isinstance()` checks.

::: mcpbr.benchmarks.base.Benchmark
    options:
      show_root_heading: true
      show_source: false

### Required Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Human-readable benchmark name |

### Required Methods

#### load_tasks()

Load tasks from the benchmark dataset with optional filtering.

```python
def load_tasks(
    self,
    sample_size: int | None = None,
    task_ids: list[str] | None = None,
    level: int | None = None,
    filter_difficulty: list[str] | None = None,
    filter_category: list[str] | None = None,
    filter_tags: list[str] | None = None,
) -> list[dict[str, Any]]
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `sample_size` | `int \| None` | Maximum number of tasks to load (`None` for all) |
| `task_ids` | `list[str] \| None` | Specific task IDs to load (`None` for all) |
| `level` | `int \| None` | Difficulty/context level (benchmark-specific, e.g., CyberGym 0-3) |
| `filter_difficulty` | `list[str] \| None` | Filter by difficulty levels |
| `filter_category` | `list[str] \| None` | Filter by categories |
| `filter_tags` | `list[str] \| None` | Filter by tags (all must match) |

**Returns:** `list[dict[str, Any]]` -- Task dictionaries in benchmark-specific format.

#### normalize_task()

Convert a benchmark-specific task dictionary to the normalized `BenchmarkTask` format.

```python
def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask
```

**Returns:** `BenchmarkTask` with standardized fields.

#### create_environment()

Create an isolated Docker environment for the task.

```python
async def create_environment(
    self,
    task: dict[str, Any],
    docker_manager: DockerEnvironmentManager,
) -> TaskEnvironment
```

**Returns:** `TaskEnvironment` with the Docker container and working directory.

#### evaluate()

Evaluate a solution (e.g., a patch or generated code) against the task.

```python
async def evaluate(
    self,
    env: TaskEnvironment,
    task: dict[str, Any],
    solution: str,
) -> dict[str, Any]
```

**Returns:** Dictionary with evaluation results including a `resolved` boolean.

#### get_prebuilt_image()

Get the pre-built Docker image name for a task, if available.

```python
def get_prebuilt_image(self, task: dict[str, Any]) -> str | None
```

**Returns:** Docker image name or `None`.

#### get_prompt_template()

Get the benchmark-specific prompt template for agents.

```python
def get_prompt_template(self) -> str
```

**Returns:** Prompt template string with `{problem_statement}` placeholder.

---

## BenchmarkTask

Normalized task representation across different benchmarks.

::: mcpbr.benchmarks.base.BenchmarkTask
    options:
      show_root_heading: true
      show_source: false

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task_id` | `str` | (required) | Unique task identifier |
| `problem_statement` | `str` | (required) | The problem description given to the agent |
| `repo` | `str` | (required) | Repository name or path |
| `commit` | `str` | (required) | Git commit hash for the task environment |
| `metadata` | `dict[str, Any]` | `{}` | Additional benchmark-specific metadata |

!!! example "BenchmarkTask Example"
    ```python
    from mcpbr.benchmarks import BenchmarkTask

    task = BenchmarkTask(
        task_id="django__django-11099",
        problem_statement="Fix the bug in QuerySet.union() that drops ORDER BY...",
        repo="django/django",
        commit="abc123def456",
        metadata={
            "difficulty": "medium",
            "fail_to_pass": ["tests.queries.test_qs_combinators.QuerySetSetOperationTests"],
        },
    )
    ```

---

## TaskEnvironment

The Docker-based execution environment for benchmark tasks. This is returned by `create_environment()` and provides methods for interacting with the container.

### Key Properties

| Property | Type | Description |
|----------|------|-------------|
| `container` | `Container` | Docker container object |
| `workdir` | `str` | Working directory inside the container |
| `host_workdir` | `str` | Working directory on the host |
| `instance_id` | `str` | Task instance identifier |
| `uses_prebuilt` | `bool` | Whether a pre-built image was used |

### Key Methods

| Method | Description |
|--------|-------------|
| `exec_command(cmd)` | Execute a command in the container |
| `exec_command_streaming(cmd)` | Execute with streaming output |
| `write_file(path, content)` | Write a file inside the container |
| `read_file(path)` | Read a file from the container |
| `cleanup()` | Remove the container and clean up resources |

---

## create_benchmark()

Factory function to create benchmark instances from the registry.

```python
from mcpbr.benchmarks import create_benchmark

# Create a benchmark by name
benchmark = create_benchmark("humaneval")

# SWE-bench variants auto-set the dataset
benchmark = create_benchmark("swe-bench-verified")
# Internally sets dataset="SWE-bench/SWE-bench_Verified"

# Pass additional kwargs to the constructor
benchmark = create_benchmark("cybergym", level=2)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Benchmark name from the registry |
| `**kwargs` | `Any` | Arguments passed to the benchmark constructor |

**Raises:** `ValueError` if the benchmark name is not recognized.

---

## BENCHMARK_REGISTRY

Dictionary mapping benchmark IDs to their implementation classes.

```python
from mcpbr.benchmarks import BENCHMARK_REGISTRY

# List all registered benchmarks
for name, cls in BENCHMARK_REGISTRY.items():
    print(f"{name:25s} -> {cls.__name__}")
```

---

## Available Benchmarks

mcpbr ships with 29 benchmark implementations:

### Software Engineering

| Benchmark ID | Class | Description |
|-------------|-------|-------------|
| `swe-bench-lite` | `SWEBenchmark` | SWE-bench Lite -- 300 curated GitHub bug fixes |
| `swe-bench-verified` | `SWEBenchmark` | SWE-bench Verified -- 500 manually validated bug fixes |
| `swe-bench-full` | `SWEBenchmark` | SWE-bench Full -- 2,294 complete dataset |
| `aider-polyglot` | `AiderPolyglotBenchmark` | Aider polyglot coding benchmark |

### Code Generation

| Benchmark ID | Class | Description |
|-------------|-------|-------------|
| `humaneval` | `HumanEvalBenchmark` | OpenAI HumanEval -- function-level code generation |
| `mbpp` | `MBPPBenchmark` | Mostly Basic Python Problems |
| `apps` | `APPSBenchmark` | APPS competitive programming |
| `codecontests` | `CodeContestsBenchmark` | Google CodeContests |
| `bigcodebench` | `BigCodeBenchBenchmark` | BigCodeBench |
| `leetcode` | `LeetCodeBenchmark` | LeetCode-style problems |
| `codereval` | `CoderEvalBenchmark` | CoderEval repository-level code generation |
| `repoqa` | `RepoQABenchmark` | Repository-level code QA |

### Reasoning and Knowledge

| Benchmark ID | Class | Description |
|-------------|-------|-------------|
| `gsm8k` | `GSM8KBenchmark` | GSM8K grade-school math word problems |
| `math` | `MATHBenchmark` | MATH competition-level mathematics |
| `truthfulqa` | `TruthfulQABenchmark` | TruthfulQA truthfulness evaluation |
| `bigbench-hard` | `BigBenchHardBenchmark` | BIG-bench Hard challenging tasks |
| `hellaswag` | `HellaSwagBenchmark` | HellaSwag commonsense reasoning |
| `arc` | `ARCBenchmark` | AI2 Reasoning Challenge |
| `mmmu` | `MMMUBenchmark` | Massive Multi-discipline Multimodal Understanding |
| `longbench` | `LongBenchBenchmark` | Long-context understanding |

### Agent and Tool Use

| Benchmark ID | Class | Description |
|-------------|-------|-------------|
| `mcptoolbench` | `MCPToolBenchmark` | MCP Tool Bench -- MCP-specific tool usage |
| `toolbench` | `ToolBenchBenchmark` | ToolBench general tool usage |
| `gaia` | `GAIABenchmark` | GAIA general AI assistant |
| `agentbench` | `AgentBenchBenchmark` | AgentBench multi-domain agent |
| `webarena` | `WebArenaBenchmark` | WebArena web browsing tasks |
| `mlagentbench` | `MLAgentBenchBenchmark` | ML Agent Bench |
| `intercode` | `InterCodeBenchmark` | InterCode interactive coding |
| `terminalbench` | `TerminalBenchBenchmark` | TerminalBench terminal operations |

### Security

| Benchmark ID | Class | Description |
|-------------|-------|-------------|
| `cybergym` | `CyberGymBenchmark` | CyberGym security challenges (levels 0-3) |
| `adversarial` | `AdversarialBenchmark` | Adversarial robustness testing |

### Custom

| Benchmark ID | Class | Description |
|-------------|-------|-------------|
| `custom` | `CustomBenchmark` | User-defined custom benchmark |

---

## Implementing a Custom Benchmark

To add a new benchmark, implement the `Benchmark` protocol:

```python
from typing import Any
from mcpbr.benchmarks.base import Benchmark, BenchmarkTask
from mcpbr.docker_env import DockerEnvironmentManager, TaskEnvironment


class MyBenchmark:
    """Custom benchmark implementation."""

    name: str = "my-benchmark"

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from your dataset."""
        tasks = [
            {
                "instance_id": "task-001",
                "problem_statement": "Implement a function that...",
                "repo": "my-org/my-repo",
                "base_commit": "abc123",
                "difficulty": "easy",
            },
            # ... more tasks
        ]

        # Apply filters
        if task_ids:
            tasks = [t for t in tasks if t["instance_id"] in task_ids]
        if filter_difficulty:
            tasks = [t for t in tasks if t.get("difficulty") in filter_difficulty]
        if sample_size:
            tasks = tasks[:sample_size]

        return tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert to normalized format."""
        return BenchmarkTask(
            task_id=task["instance_id"],
            problem_statement=task["problem_statement"],
            repo=task["repo"],
            commit=task["base_commit"],
            metadata={"difficulty": task.get("difficulty")},
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create a Docker environment for the task."""
        image = self.get_prebuilt_image(task)
        return await docker_manager.create_environment(
            image=image or "python:3.11-slim",
            instance_id=task["instance_id"],
            repo=task["repo"],
            commit=task["base_commit"],
        )

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate the agent's solution."""
        # Apply the solution and run tests
        await env.write_file("/tmp/solution.py", solution)
        exit_code, output = await env.exec_command(
            "cd /workspace && python -m pytest tests/ -v"
        )
        return {
            "resolved": exit_code == 0,
            "test_output": output,
        }

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Return pre-built Docker image if available."""
        return None  # No pre-built images

    def get_prompt_template(self) -> str:
        """Return the prompt template for agents."""
        return (
            "You are a software engineer. Solve the following problem:\n\n"
            "{problem_statement}\n\n"
            "Provide your solution as a Python implementation."
        )
```

### Registering Your Benchmark

To make your benchmark available via `create_benchmark()` and the CLI, register it in `BENCHMARK_REGISTRY`:

```python
# In mcpbr/benchmarks/__init__.py
from .my_benchmark import MyBenchmark

BENCHMARK_REGISTRY["my-benchmark"] = MyBenchmark
```

And add the benchmark ID to `VALID_BENCHMARKS` in `mcpbr/config.py`:

```python
VALID_BENCHMARKS = (
    # ... existing benchmarks ...
    "my-benchmark",
)
```

!!! tip "Protocol Compliance"
    You can verify your implementation satisfies the protocol at runtime:
    ```python
    from mcpbr.benchmarks import Benchmark

    my_bench = MyBenchmark()
    assert isinstance(my_bench, Benchmark)  # Runtime check
    ```

---

## list_benchmarks()

List all available benchmark names from the registry.

```python
from mcpbr.benchmarks import list_benchmarks

names = list_benchmarks()
print(names)
# ['swe-bench-lite', 'swe-bench-verified', 'swe-bench-full', 'cybergym',
#  'humaneval', 'mcptoolbench', 'gsm8k', 'mbpp', 'math', ...]
```

**Returns:** `list[str]` -- Sorted list of benchmark identifier strings.
