---
description: "Guide for developing custom benchmarks and extensions for mcpbr, including the Benchmark protocol, model providers, custom metrics, and end-to-end examples."
faq:
  - q: "How do I create a custom benchmark for mcpbr?"
    a: "Implement the Benchmark protocol from mcpbr.benchmarks.base by creating a class with load_tasks(), normalize_task(), create_environment(), evaluate(), get_prompt_template(), and get_prebuilt_image() methods. Then register it in BENCHMARK_REGISTRY in benchmarks/__init__.py and VALID_BENCHMARKS in config.py."
  - q: "What is the Benchmark protocol?"
    a: "The Benchmark protocol is a Python Protocol (structural typing) defined in mcpbr.benchmarks.base that specifies the interface every benchmark must implement. It includes methods for loading tasks from datasets, normalizing them to a common format, creating Docker environments, evaluating solutions, and providing prompt templates."
  - q: "Can I add a new model provider?"
    a: "Yes. Implement the ModelProvider protocol from mcpbr.providers by creating a class with chat(), get_tool_format(), and a model property. Then add it to PROVIDER_REGISTRY in providers.py and VALID_PROVIDERS in config.py."
  - q: "Can I define a benchmark without writing Python code?"
    a: "Yes. mcpbr supports YAML-defined custom benchmarks via the CustomBenchmark class. Create a YAML file specifying your dataset, field mappings, and evaluation type (exact_match, numeric, regex, or script), then reference it in your mcpbr configuration."
  - q: "How do I test my custom benchmark?"
    a: "Write pytest tests covering task loading, normalization, problem statement generation, and evaluation logic. Use fixtures for sample task data and mock Docker environments for integration tests. Run tests with 'uv run pytest tests/test_my_benchmark.py -m \"not integration\"'."
---

# Plugin Development Guide

This guide covers how to extend mcpbr with custom benchmarks, model providers, and metrics. Whether you want to evaluate agents on a new dataset, integrate a new LLM API, or define custom evaluation criteria, this document walks through the process from architecture to publication.

## Overview

mcpbr is designed around **protocol-based extensibility**. Rather than requiring inheritance from base classes, mcpbr uses Python's `Protocol` type (structural typing) to define interfaces. Any class that implements the required methods is automatically compatible -- no registration in a class hierarchy needed.

The three primary extension points are:

| Extension Point | Protocol | Registry | Location |
|----------------|----------|----------|----------|
| Benchmarks | `Benchmark` | `BENCHMARK_REGISTRY` | `src/mcpbr/benchmarks/` |
| Model Providers | `ModelProvider` | `PROVIDER_REGISTRY` | `src/mcpbr/providers.py` |
| Custom Metrics | `ToolCoverageReport` | N/A | `src/mcpbr/reporting.py` |

## Architecture Overview

mcpbr's plugin system follows a **registry pattern** backed by **protocol-based interfaces**:

```
                   +-----------------+
                   |   config.py     |
                   | VALID_BENCHMARKS|
                   | VALID_PROVIDERS |
                   +--------+--------+
                            |
               +------------+------------+
               |                         |
   +-----------v-----------+ +-----------v-----------+
   | benchmarks/__init__.py| |    providers.py       |
   | BENCHMARK_REGISTRY    | |  PROVIDER_REGISTRY    |
   | create_benchmark()    | |  create_provider()    |
   +----------+------------+ +-----------+-----------+
              |                          |
    +---------v----------+     +---------v----------+
    |  Benchmark Protocol|     | ModelProvider       |
    |  (base.py)         |     | Protocol            |
    +--------------------+     +---------------------+
              |                          |
    +---------v----------+     +---------v----------+
    | HumanEvalBenchmark |     | AnthropicProvider  |
    | CyberGymBenchmark  |     | OpenAIProvider     |
    | CustomBenchmark     |     | GeminiProvider     |
    | YourBenchmark       |     | YourProvider       |
    +--------------------+     +---------------------+
```

When mcpbr runs an evaluation, the flow is:

1. Configuration is loaded and validated (benchmark name checked against `VALID_BENCHMARKS`)
2. `create_benchmark()` looks up the class in `BENCHMARK_REGISTRY` and instantiates it
3. `load_tasks()` fetches data from the benchmark's dataset
4. For each task, `create_environment()` spins up a Docker container
5. The agent runs inside the container and produces a solution
6. `evaluate()` checks the solution against expected results

---

## Creating a Custom Benchmark

### The Benchmark Protocol

Every benchmark must satisfy the `Benchmark` protocol defined in `src/mcpbr/benchmarks/base.py`:

```python
@runtime_checkable
class Benchmark(Protocol):
    name: str

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask: ...

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment: ...

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]: ...

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None: ...

    def get_prompt_template(self) -> str: ...
```

The `BenchmarkTask` dataclass provides a normalized representation:

```python
@dataclass
class BenchmarkTask:
    task_id: str
    problem_statement: str
    repo: str
    commit: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

#### Protocol Method Reference

| Method | Purpose | Returns |
|--------|---------|---------|
| `load_tasks()` | Fetch and filter tasks from the dataset | `list[dict[str, Any]]` -- augmented task dicts with `instance_id` and `problem_statement` |
| `normalize_task()` | Convert raw task dict to `BenchmarkTask` | `BenchmarkTask` |
| `create_environment()` | Spin up a Docker container for one task | `TaskEnvironment` |
| `evaluate()` | Check a solution against expected results | `dict` with at least `{"resolved": bool}` |
| `get_prebuilt_image()` | Return a Docker image name if one exists | `str | None` |
| `get_prompt_template()` | Return the prompt template for agents | `str` with `{problem_statement}` placeholder |

### Step-by-Step Guide

#### 1. Create the Benchmark Class

Create a new file in `src/mcpbr/benchmarks/`. The filename should match the benchmark name in lowercase (e.g., `code_review.py`).

```python
"""Code review benchmark implementation."""

import base64
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class CodeReviewBenchmark:
    """Benchmark that evaluates an agent's ability to find bugs in code.

    Each task presents a code snippet with a known bug. The agent must
    identify the bug, explain it, and provide a corrected version.
    """

    name = "code-review"

    def __init__(self, dataset: str = "your-org/code-review-dataset"):
        """Initialize Code Review benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
        """
        self.dataset = dataset
```

!!! tip "Naming Convention"
    The `name` class attribute must match the key you will use in `BENCHMARK_REGISTRY`. Use lowercase with hyphens for multi-word names (e.g., `"code-review"`, `"bigbench-hard"`).

#### 2. Implement `load_tasks()`

This method fetches tasks from your dataset and augments them with `instance_id` and `problem_statement` fields that the harness requires.

```python
def load_tasks(
    self,
    sample_size: int | None = None,
    task_ids: list[str] | None = None,
    level: int | None = None,
    filter_difficulty: list[str] | None = None,
    filter_category: list[str] | None = None,
    filter_tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Load tasks from the code review dataset.

    Args:
        sample_size: Maximum number of tasks to load (None for all).
        task_ids: Specific task IDs to load (None for all).
        level: Unused for this benchmark.
        filter_difficulty: Filter by difficulty (e.g., ["easy", "hard"]).
        filter_category: Filter by category (e.g., ["python", "javascript"]).
        filter_tags: Filter by tags (requires all tags to match).

    Returns:
        List of augmented task dictionaries.
    """
    # Silence unused parameter warnings for protocol compliance
    _ = level

    dataset = load_dataset(self.dataset, split="test")

    # Filter by specific task IDs if provided
    if task_ids:
        task_id_set = set(task_ids)
        tasks = [item for item in dataset if item["id"] in task_id_set]
    else:
        tasks = list(dataset)

    # Apply optional filters
    if filter_difficulty:
        difficulty_set = set(filter_difficulty)
        tasks = [t for t in tasks if t.get("difficulty") in difficulty_set]

    if filter_category:
        category_set = set(filter_category)
        tasks = [t for t in tasks if t.get("category") in category_set]

    if filter_tags:
        tasks = [
            t for t in tasks
            if all(tag in t.get("tags", []) for tag in filter_tags)
        ]

    # Apply sample size limit
    if sample_size is not None and len(tasks) > sample_size:
        tasks = tasks[:sample_size]

    # Augment tasks with required fields
    augmented_tasks = []
    for task in tasks:
        augmented = dict(task)
        augmented["instance_id"] = f"code_review_{task['id']}"
        augmented["problem_statement"] = self._generate_problem_statement(augmented)
        augmented_tasks.append(augmented)

    return augmented_tasks
```

!!! warning "Required Fields"
    Every task dict returned by `load_tasks()` **must** include `instance_id` and `problem_statement`. The `instance_id` is used for Docker container naming and must be filesystem-safe (no slashes, spaces, or special characters).

#### 3. Implement `normalize_task()`

Convert a raw task dictionary into the standardized `BenchmarkTask` format:

```python
def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
    """Convert code review task to normalized format.

    Args:
        task: Task dictionary from load_tasks().

    Returns:
        Normalized BenchmarkTask.

    Raises:
        ValueError: If required fields are missing.
    """
    instance_id = task.get("instance_id")
    if not instance_id:
        task_id = task.get("id")
        if not task_id:
            msg = f"Task missing 'id' or 'instance_id': {list(task.keys())}"
            raise ValueError(msg)
        instance_id = f"code_review_{task_id}"

    return BenchmarkTask(
        task_id=instance_id,
        problem_statement=task.get("problem_statement", ""),
        repo="code-review/tasks",
        commit="HEAD",
        metadata={
            "buggy_code": task.get("buggy_code", ""),
            "fixed_code": task.get("fixed_code", ""),
            "bug_description": task.get("bug_description", ""),
            "language": task.get("language", "python"),
        },
    )
```

#### 4. Implement `create_environment()`

Set up an isolated Docker container for each task. For lightweight benchmarks, use the Docker manager's fallback image:

```python
async def create_environment(
    self,
    task: dict[str, Any],
    docker_manager: DockerEnvironmentManager,
) -> TaskEnvironment:
    """Create environment for a code review task.

    Args:
        task: Task dictionary.
        docker_manager: Docker environment manager.

    Returns:
        TaskEnvironment for the task.
    """
    instance_id = task.get("instance_id", "code_review_unknown")

    # Use the Docker manager's standard environment creation
    temp_task = {
        "instance_id": instance_id,
        "repo": "code-review/tasks",
        "base_commit": "HEAD",
    }

    env = await docker_manager.create_environment(temp_task)

    # Write the buggy code file into the container
    buggy_code = task.get("buggy_code", "")
    if buggy_code:
        encoded = base64.b64encode(buggy_code.encode()).decode()
        await env.exec_command(
            f"echo '{encoded}' | base64 -d > /workspace/code_to_review.py",
            timeout=10,
        )

    return env
```

!!! note "Base64 Encoding"
    Always use base64 encoding when writing user-supplied content into Docker containers. This prevents shell injection vulnerabilities that could arise from special characters in code snippets.

#### 5. Implement `evaluate()`

Check whether the agent's solution is correct. The returned dict **must** include a `"resolved"` boolean:

```python
async def evaluate(
    self,
    env: TaskEnvironment,
    task: dict[str, Any],
    solution: str,
) -> dict[str, Any]:
    """Evaluate the agent's code review.

    Checks whether the agent identified the bug and produced
    a valid fix.

    Args:
        env: Task environment.
        task: Task dictionary.
        solution: Agent's solution text.

    Returns:
        Dictionary with 'resolved' boolean and evaluation details.
    """
    expected_fix = task.get("fixed_code", "")
    bug_description = task.get("bug_description", "")

    if not expected_fix:
        return {
            "resolved": False,
            "error": "No expected fix available for evaluation",
        }

    # Check if the agent identified the bug
    bug_identified = bug_description.lower() in solution.lower()

    # Check if the agent produced a working fix
    # Write solution and expected fix, then run a comparison script
    solution_b64 = base64.b64encode(solution.encode()).decode()
    fix_b64 = base64.b64encode(expected_fix.encode()).decode()

    await env.exec_command(
        f"echo '{solution_b64}' | base64 -d > /tmp/agent_solution.py",
        timeout=10,
    )
    await env.exec_command(
        f"echo '{fix_b64}' | base64 -d > /tmp/expected_fix.py",
        timeout=10,
    )

    # Run the corrected code's test suite
    exit_code, stdout, stderr = await env.exec_command(
        "python3 /tmp/agent_solution.py",
        timeout=30,
    )

    code_works = exit_code == 0

    return {
        "resolved": bug_identified and code_works,
        "bug_identified": bug_identified,
        "code_works": code_works,
        "exit_code": exit_code,
        "stdout": stdout[:1000] if stdout else "",
        "stderr": stderr[:1000] if stderr else "",
    }
```

!!! warning "The `resolved` Key"
    The `"resolved"` key in the returned dictionary is **required**. The harness uses this boolean to compute pass rates and aggregate statistics. All other keys are optional metadata.

#### 6. Implement `get_prompt_template()`

Return a prompt template that guides the agent. Use `{problem_statement}` as a placeholder:

```python
def get_prompt_template(self) -> str:
    """Get the prompt template for code review tasks.

    Returns:
        Prompt template string with {problem_statement} placeholder.
    """
    return (
        "You are an expert code reviewer. Review the following code and "
        "identify any bugs.\n\n"
        "{problem_statement}\n\n"
        "INSTRUCTIONS:\n"
        "- Identify the bug in the code\n"
        "- Explain what the bug is and why it's wrong\n"
        "- Provide a corrected version of the code\n"
        "- Save the corrected code to 'solution.py'\n"
        "- Ensure the corrected code passes all test cases"
    )
```

#### 7. Optional: Implement `get_prebuilt_image()`

If your benchmark has pre-built Docker images available (e.g., on a container registry), return the image name. Otherwise, return `None`:

```python
def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
    """Get pre-built Docker image for the task.

    Code review tasks use lightweight Python environments,
    so no pre-built images are needed.

    Args:
        task: Task dictionary.

    Returns:
        None (no pre-built images).
    """
    return None
```

!!! tip "When to Use Pre-built Images"
    Pre-built images are useful when tasks require complex dependencies (specific library versions, OS packages, large datasets). For lightweight benchmarks that only need Python, returning `None` lets mcpbr use its generic fallback image.

### Complete Example

Here is the full benchmark file for the code review example, combining all methods:

??? example "Full `code_review.py` (click to expand)"

    ```python
    """Code review benchmark implementation."""

    import base64
    from typing import Any

    from datasets import load_dataset

    from ..docker_env import DockerEnvironmentManager, TaskEnvironment
    from .base import BenchmarkTask


    class CodeReviewBenchmark:
        """Benchmark for evaluating agent code review capabilities.

        Each task presents a code snippet containing a known bug.
        The agent must identify the bug and provide a corrected version.
        """

        name = "code-review"

        def __init__(self, dataset: str = "your-org/code-review-dataset"):
            """Initialize Code Review benchmark.

            Args:
                dataset: HuggingFace dataset identifier.
            """
            self.dataset = dataset

        def load_tasks(
            self,
            sample_size: int | None = None,
            task_ids: list[str] | None = None,
            level: int | None = None,
            filter_difficulty: list[str] | None = None,
            filter_category: list[str] | None = None,
            filter_tags: list[str] | None = None,
        ) -> list[dict[str, Any]]:
            """Load tasks from the code review dataset."""
            _ = level
            dataset = load_dataset(self.dataset, split="test")

            if task_ids:
                task_id_set = set(task_ids)
                tasks = [item for item in dataset if item["id"] in task_id_set]
            else:
                tasks = list(dataset)

            if filter_difficulty:
                difficulty_set = set(filter_difficulty)
                tasks = [t for t in tasks if t.get("difficulty") in difficulty_set]

            if filter_category:
                category_set = set(filter_category)
                tasks = [t for t in tasks if t.get("category") in category_set]

            if filter_tags:
                tasks = [
                    t for t in tasks
                    if all(tag in t.get("tags", []) for tag in filter_tags)
                ]

            if sample_size is not None and len(tasks) > sample_size:
                tasks = tasks[:sample_size]

            augmented_tasks = []
            for task in tasks:
                augmented = dict(task)
                augmented["instance_id"] = f"code_review_{task['id']}"
                augmented["problem_statement"] = self._generate_problem_statement(
                    augmented
                )
                augmented_tasks.append(augmented)

            return augmented_tasks

        def _generate_problem_statement(self, task: dict[str, Any]) -> str:
            """Generate problem statement from task fields."""
            code = task.get("buggy_code", "")
            language = task.get("language", "python")
            return (
                f"Review the following {language} code and find the bug:\n\n"
                f"```{language}\n{code}\n```\n\n"
                f"Fix the bug and save the corrected code to 'solution.py'."
            )

        def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
            """Convert code review task to normalized format."""
            instance_id = task.get("instance_id")
            if not instance_id:
                task_id = task.get("id")
                if not task_id:
                    msg = f"Task missing 'id' or 'instance_id': {list(task.keys())}"
                    raise ValueError(msg)
                instance_id = f"code_review_{task_id}"

            return BenchmarkTask(
                task_id=instance_id,
                problem_statement=task.get(
                    "problem_statement",
                    self._generate_problem_statement(task),
                ),
                repo="code-review/tasks",
                commit="HEAD",
                metadata={
                    "buggy_code": task.get("buggy_code", ""),
                    "fixed_code": task.get("fixed_code", ""),
                    "bug_description": task.get("bug_description", ""),
                    "language": task.get("language", "python"),
                },
            )

        async def create_environment(
            self,
            task: dict[str, Any],
            docker_manager: DockerEnvironmentManager,
        ) -> TaskEnvironment:
            """Create environment for a code review task."""
            instance_id = task.get("instance_id", "code_review_unknown")
            temp_task = {
                "instance_id": instance_id,
                "repo": "code-review/tasks",
                "base_commit": "HEAD",
            }
            env = await docker_manager.create_environment(temp_task)

            buggy_code = task.get("buggy_code", "")
            if buggy_code:
                encoded = base64.b64encode(buggy_code.encode()).decode()
                await env.exec_command(
                    f"echo '{encoded}' | base64 -d > /workspace/code_to_review.py",
                    timeout=10,
                )

            return env

        async def evaluate(
            self,
            env: TaskEnvironment,
            task: dict[str, Any],
            solution: str,
        ) -> dict[str, Any]:
            """Evaluate the agent's code review solution."""
            expected_fix = task.get("fixed_code", "")
            bug_description = task.get("bug_description", "")

            if not expected_fix:
                return {
                    "resolved": False,
                    "error": "No expected fix available",
                }

            bug_identified = bug_description.lower() in solution.lower()

            solution_b64 = base64.b64encode(solution.encode()).decode()
            fix_b64 = base64.b64encode(expected_fix.encode()).decode()

            await env.exec_command(
                f"echo '{solution_b64}' | base64 -d > /tmp/agent_solution.py",
                timeout=10,
            )
            await env.exec_command(
                f"echo '{fix_b64}' | base64 -d > /tmp/expected_fix.py",
                timeout=10,
            )

            exit_code, stdout, stderr = await env.exec_command(
                "python3 /tmp/agent_solution.py",
                timeout=30,
            )

            code_works = exit_code == 0

            return {
                "resolved": bug_identified and code_works,
                "bug_identified": bug_identified,
                "code_works": code_works,
                "exit_code": exit_code,
                "stdout": stdout[:1000] if stdout else "",
                "stderr": stderr[:1000] if stderr else "",
            }

        def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
            """No pre-built images for code review tasks."""
            return None

        def get_prompt_template(self) -> str:
            """Get the code review prompt template."""
            return (
                "You are an expert code reviewer. Review the following code "
                "and identify any bugs.\n\n"
                "{problem_statement}\n\n"
                "INSTRUCTIONS:\n"
                "- Identify the bug in the code\n"
                "- Explain what the bug is and why it's wrong\n"
                "- Provide a corrected version of the code\n"
                "- Save the corrected code to 'solution.py'\n"
                "- Ensure the corrected code passes all test cases"
            )
    ```

### Registration

After creating your benchmark class, register it in three places:

#### 1. `src/mcpbr/benchmarks/__init__.py`

Add the import and update the registry:

```python
# Add import at the top
from .code_review import CodeReviewBenchmark

# Add to __all__
__all__ = [
    # ... existing entries ...
    "CodeReviewBenchmark",
]

# Add to BENCHMARK_REGISTRY
BENCHMARK_REGISTRY: dict[str, type[Benchmark]] = {
    # ... existing entries ...
    "code-review": CodeReviewBenchmark,
}
```

#### 2. `src/mcpbr/config.py`

Add the benchmark name to the `VALID_BENCHMARKS` tuple:

```python
VALID_BENCHMARKS = (
    "swe-bench-lite",
    "swe-bench-verified",
    # ... existing entries ...
    "code-review",  # Add your benchmark
)
```

#### 3. Verify Protocol Compliance

You can verify your class satisfies the protocol at runtime:

```python
from mcpbr.benchmarks import Benchmark

benchmark = CodeReviewBenchmark()
assert isinstance(benchmark, Benchmark), "Does not satisfy Benchmark protocol"
```

!!! warning "All Three Registrations Required"
    Missing any of the three registration steps will cause failures:

    - Missing from `BENCHMARK_REGISTRY`: `create_benchmark()` raises `ValueError`
    - Missing from `VALID_BENCHMARKS`: config validation rejects the benchmark name
    - Missing from `__init__.py` imports: the class is not importable from the package

### Testing Your Benchmark

Create a test file at `tests/test_code_review.py`:

```python
"""Tests for code review benchmark implementation."""

import pytest

from mcpbr.benchmarks import Benchmark, create_benchmark
from mcpbr.benchmarks.code_review import CodeReviewBenchmark


class TestCodeReviewBenchmarkInit:
    """Tests for benchmark initialization."""

    def test_initialization(self) -> None:
        """Test default initialization."""
        benchmark = CodeReviewBenchmark()
        assert benchmark.name == "code-review"
        assert benchmark.dataset == "your-org/code-review-dataset"

    def test_custom_dataset(self) -> None:
        """Test initialization with custom dataset."""
        benchmark = CodeReviewBenchmark(dataset="other/dataset")
        assert benchmark.dataset == "other/dataset"

    def test_protocol_compliance(self) -> None:
        """Verify the class satisfies the Benchmark protocol."""
        benchmark = CodeReviewBenchmark()
        assert isinstance(benchmark, Benchmark)

    def test_registry_creation(self) -> None:
        """Test creating via the benchmark registry."""
        benchmark = create_benchmark("code-review")
        assert isinstance(benchmark, CodeReviewBenchmark)


class TestCodeReviewNormalization:
    """Tests for task normalization."""

    def test_normalize_task(self) -> None:
        """Test normalizing a code review task."""
        benchmark = CodeReviewBenchmark()
        task = {
            "id": "42",
            "instance_id": "code_review_42",
            "buggy_code": "def add(a, b):\n    return a - b",
            "fixed_code": "def add(a, b):\n    return a + b",
            "bug_description": "Uses subtraction instead of addition",
            "language": "python",
            "problem_statement": "Review the code and find the bug.",
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "code_review_42"
        assert normalized.repo == "code-review/tasks"
        assert normalized.commit == "HEAD"
        assert normalized.metadata["language"] == "python"

    def test_normalize_task_missing_id_raises(self) -> None:
        """Test that missing ID raises ValueError."""
        benchmark = CodeReviewBenchmark()
        with pytest.raises(ValueError, match="missing"):
            benchmark.normalize_task({"buggy_code": "x = 1"})


class TestCodeReviewPrompt:
    """Tests for prompt template."""

    def test_prompt_contains_placeholder(self) -> None:
        """Test that the prompt template includes the required placeholder."""
        benchmark = CodeReviewBenchmark()
        template = benchmark.get_prompt_template()
        assert "{problem_statement}" in template

    def test_prompt_template_is_nonempty(self) -> None:
        """Test that the prompt template is not empty."""
        benchmark = CodeReviewBenchmark()
        assert len(benchmark.get_prompt_template()) > 0


class TestCodeReviewPrebuiltImage:
    """Tests for pre-built image support."""

    def test_no_prebuilt_image(self) -> None:
        """Verify no pre-built images for code review tasks."""
        benchmark = CodeReviewBenchmark()
        assert benchmark.get_prebuilt_image({"id": "1"}) is None


class TestCodeReviewEvaluation:
    """Tests for evaluation logic (unit tests without Docker)."""

    @pytest.mark.asyncio
    async def test_evaluate_no_expected_fix(self) -> None:
        """Test evaluation when no expected fix is available."""
        benchmark = CodeReviewBenchmark()
        # Mock environment -- evaluation should handle missing fix gracefully
        task = {"buggy_code": "x = 1", "bug_description": "wrong value"}

        # Since evaluate needs a real TaskEnvironment, this tests
        # the early return path for missing ground truth
        result = await benchmark.evaluate(
            env=None,  # Would need mock for full test
            task=task,
            solution="The bug is wrong value",
        )
        assert result["resolved"] is False
        assert "error" in result
```

Run the tests:

```bash
uv run pytest tests/test_code_review.py -m "not integration" -v
```

### YAML-Based Custom Benchmarks (No Code Required)

For simpler benchmarks, mcpbr supports YAML-defined benchmarks via the `CustomBenchmark` class. This avoids writing any Python code.

Create a YAML definition file (e.g., `my_benchmark.yaml`):

```yaml
name: trivia-qa
dataset: trivia_qa
subset: rc.nocontext
split: validation
task_id_field: question_id
problem_statement_field: question
answer_field: answer
evaluation_type: exact_match  # or: numeric, regex, script
prompt_template: |
  Answer the following trivia question:

  {problem_statement}

  Provide a clear, concise answer.
```

Then reference it in your mcpbr config:

```yaml
benchmark: custom
custom_benchmark_definition: my_benchmark.yaml
```

#### Supported Evaluation Types

| Type | Description | Extra Config |
|------|-------------|--------------|
| `exact_match` | Case-insensitive substring match | None |
| `numeric` | Numeric comparison with tolerance | `numeric_rtol`, `numeric_atol` |
| `regex` | Regex extraction and comparison | `regex_pattern` (required) |
| `script` | Run a custom evaluation script | `evaluation_script` (required) |

!!! example "Regex Evaluation Example"

    ```yaml
    name: extract-answer
    dataset: my-org/answer-extraction
    evaluation_type: regex
    regex_pattern: "(?:answer|result)\\s*(?:is|:)\\s*(.+)"
    problem_statement_field: question
    answer_field: expected_answer
    ```

!!! example "Script Evaluation Example"

    ```yaml
    name: code-execution
    dataset: my-org/code-tasks
    evaluation_type: script
    evaluation_script: |
      python3 -c "
      with open('/tmp/solution.txt') as f:
          solution = f.read()
      with open('/tmp/ground_truth.txt') as f:
          truth = f.read()
      exit(0 if solution.strip() == truth.strip() else 1)
      "
    docker_image: python:3.11-slim
    setup_commands:
      - "pip install numpy pandas"
    ```

---

## Creating a Custom Provider

### The ModelProvider Protocol

Model providers are defined in `src/mcpbr/providers.py`:

```python
@runtime_checkable
class ModelProvider(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> ChatResponse: ...

    def get_tool_format(self) -> str: ...

    @property
    def model(self) -> str: ...
```

Supporting data classes:

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON-encoded string

@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

@dataclass
class ChatResponse:
    message: ChatMessage
    finish_reason: str          # "stop", "tool_calls", or "length"
    input_tokens: int = 0
    output_tokens: int = 0
```

#### Provider Method Reference

| Method | Purpose | Returns |
|--------|---------|---------|
| `chat()` | Send a chat completion request with optional tools | `ChatResponse` |
| `get_tool_format()` | Return the tool definition format (`"openai"` or `"anthropic"`) | `str` |
| `model` (property) | Return the model identifier | `str` |

### Step-by-Step Guide

#### 1. Create the Provider Class

Add your provider to `src/mcpbr/providers.py`:

```python
class MistralProvider:
    """Provider for Mistral AI API."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize Mistral provider.

        Args:
            model: Mistral model ID (e.g., 'mistral-large-latest').
            api_key: API key. If None, uses MISTRAL_API_KEY env var.
        """
        self._model = model
        self._api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Mistral API key required. Set MISTRAL_API_KEY environment "
                "variable or pass api_key parameter."
            )
        from mistralai import Mistral

        self._client = Mistral(api_key=self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def get_tool_format(self) -> str:
        return "openai"  # Mistral uses OpenAI-compatible tool format

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.complete(**kwargs)

        if not response.choices:
            raise RuntimeError("Mistral API returned empty response")

        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                )

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=choice.message.content,
                tool_calls=tool_calls,
            ),
            finish_reason=choice.finish_reason or "stop",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
```

#### 2. Register the Provider

Update the registry and config:

```python
# In src/mcpbr/providers.py
PROVIDER_REGISTRY: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "qwen": QwenProvider,
    "mistral": MistralProvider,  # Add new provider
}
```

```python
# In src/mcpbr/config.py
VALID_PROVIDERS = ("anthropic", "openai", "gemini", "qwen", "mistral")
```

!!! note "Tool Format Compatibility"
    The `get_tool_format()` method must return either `"openai"` or `"anthropic"`. Most providers use OpenAI-compatible tool definitions. Only the Anthropic API uses its own format. Choose the one that matches your provider's API.

#### 3. Add Pricing Data (Optional)

If you want cost tracking, add your provider's models to `src/mcpbr/pricing.py`:

```python
MODEL_PRICING: dict[str, ModelPricing] = {
    # ... existing entries ...
    "mistral-large-latest": ModelPricing(
        model_id="mistral-large-latest",
        provider="Mistral",
        input_price_per_mtok=2.00,
        output_price_per_mtok=6.00,
        notes="Mistral Large - flagship model",
    ),
}
```

---

## Creating Custom Metrics

mcpbr collects evaluation metrics through the `ToolCoverageReport` class and the evaluation results pipeline. You can extend metrics collection in several ways.

### Adding Fields to Evaluation Results

The simplest way to add custom metrics is to return extra fields from your benchmark's `evaluate()` method:

```python
async def evaluate(self, env, task, solution) -> dict[str, Any]:
    # ... evaluation logic ...

    return {
        "resolved": passed,
        # Standard fields
        "exit_code": exit_code,
        "stdout": stdout[:1000],
        "stderr": stderr[:1000],
        # Custom metrics
        "lines_changed": count_changed_lines(solution),
        "bug_category": task.get("bug_category", "unknown"),
        "time_to_first_fix": measure_first_fix_time(),
        "tools_used_count": len(tools_invoked),
    }
```

These custom fields are preserved in the JSON output and can be analyzed with post-processing scripts.

### Analyzing Tool Coverage

mcpbr provides the `ToolCoverageReport` class for tracking which MCP tools agents actually use:

```python
from mcpbr.reporting import ToolCoverageReport

# Initialize with known available tools
report = ToolCoverageReport(
    available_tools=["read_file", "write_file", "search_code", "run_tests"]
)

# After each task, add the tool usage data
report.add_task_usage({"read_file": 5, "search_code": 3})
report.add_task_usage({"read_file": 2, "write_file": 1})

# Get coverage metrics
metrics = report.get_coverage_metrics()
# Returns:
# {
#     "total_available": 4,
#     "total_used": 3,
#     "coverage_rate": 0.75,
#     "unused_tools": ["run_tests"],
#     "most_used": [("read_file", 7), ("search_code", 3), ...],
#     ...
# }
```

### Post-Processing Results

For advanced custom metrics, write a post-processing script that reads mcpbr's JSON output:

```python
"""Post-process mcpbr results to compute custom metrics."""

import json
import sys
from collections import defaultdict
from pathlib import Path


def compute_category_breakdown(results_path: str) -> dict:
    """Compute pass rates broken down by custom categories."""
    with open(results_path) as f:
        results = json.load(f)

    categories = defaultdict(lambda: {"total": 0, "resolved": 0})

    for task_result in results.get("task_results", []):
        category = task_result.get("metadata", {}).get("bug_category", "unknown")
        categories[category]["total"] += 1
        if task_result.get("resolved"):
            categories[category]["resolved"] += 1

    # Compute rates
    for cat, data in categories.items():
        data["rate"] = data["resolved"] / data["total"] if data["total"] > 0 else 0

    return dict(categories)


if __name__ == "__main__":
    breakdown = compute_category_breakdown(sys.argv[1])
    for category, data in sorted(breakdown.items()):
        print(f"  {category}: {data['resolved']}/{data['total']} ({data['rate']:.1%})")
```

Run it:

```bash
python analyze_results.py results.json
```

---

## Best Practices

### Error Handling

!!! tip "Graceful Failure"
    Your benchmark's `evaluate()` method should never raise exceptions. Always return a dict with `"resolved": False` and an `"error"` key explaining what went wrong:

    ```python
    async def evaluate(self, env, task, solution) -> dict[str, Any]:
        try:
            # ... evaluation logic ...
            return {"resolved": passed, ...}
        except Exception as e:
            return {
                "resolved": False,
                "error": f"Evaluation failed: {e}",
            }
    ```

### Docker Environment Management

- Use `base64` encoding for all data written to containers (prevents shell injection)
- Set reasonable timeouts on `exec_command()` calls (default is 60 seconds)
- Clean up temporary files inside containers to conserve disk space
- Use the Docker manager's fallback image for lightweight benchmarks rather than pulling custom images

### Dataset Loading Patterns

- Always support the `sample_size` parameter for development/testing workflows
- Support `task_ids` for reproducing specific results
- Use HuggingFace `datasets` for standard dataset access
- Cache datasets locally when possible (HuggingFace handles this automatically)
- Augment every task dict with `instance_id` (filesystem-safe) and `problem_statement`

### Evaluation Accuracy

- Normalize text before comparison (strip whitespace, normalize case)
- For numeric answers, use tolerance-based comparison, not exact equality
- For code solutions, run actual tests rather than string matching when possible
- Return rich metadata beyond `resolved` to aid in debugging and analysis

### Performance Considerations

- Keep `load_tasks()` fast; avoid expensive computation during task loading
- Use async methods for I/O-bound operations in `create_environment()` and `evaluate()`
- Limit output capture size (truncate stdout/stderr to prevent memory issues)
- Consider pre-built Docker images for benchmarks with complex dependencies

---

## Testing Guidelines

### Unit Tests for Task Loading

Test that tasks load correctly, filters work, and normalization produces valid output:

```python
class TestTaskLoading:
    def test_load_returns_list(self) -> None:
        benchmark = MyBenchmark()
        # Mock dataset loading for unit tests
        tasks = benchmark.load_tasks(sample_size=5)
        assert isinstance(tasks, list)

    def test_sample_size_respected(self) -> None:
        benchmark = MyBenchmark()
        tasks = benchmark.load_tasks(sample_size=3)
        assert len(tasks) <= 3

    def test_tasks_have_required_fields(self) -> None:
        benchmark = MyBenchmark()
        tasks = benchmark.load_tasks(sample_size=1)
        for task in tasks:
            assert "instance_id" in task
            assert "problem_statement" in task
```

### Integration Tests for Evaluation

Mark tests that need Docker or network access with `@pytest.mark.integration`:

```python
@pytest.mark.integration
class TestEvaluationIntegration:
    @pytest.mark.asyncio
    async def test_full_evaluation_flow(self) -> None:
        """Test the complete evaluation pipeline end-to-end."""
        benchmark = MyBenchmark()
        tasks = benchmark.load_tasks(sample_size=1)

        docker_manager = DockerEnvironmentManager()
        try:
            env = await benchmark.create_environment(tasks[0], docker_manager)
            result = await benchmark.evaluate(env, tasks[0], "test solution")
            assert "resolved" in result
        finally:
            await docker_manager.cleanup_all()
```

### Mocking Docker Environments

For unit tests that do not require Docker, mock the `TaskEnvironment`:

```python
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_env():
    """Create a mock TaskEnvironment for unit tests."""
    env = MagicMock()
    env.exec_command = AsyncMock(return_value=(0, "success", ""))
    env.workdir = "/workspace"
    env.host_workdir = "/tmp/mcpbr_test"
    env.instance_id = "test_instance"
    return env


class TestEvaluationUnit:
    @pytest.mark.asyncio
    async def test_evaluate_correct_solution(self, mock_env) -> None:
        benchmark = MyBenchmark()
        task = {"instance_id": "test_1", "expected_answer": "42"}

        mock_env.exec_command = AsyncMock(return_value=(0, "42", ""))

        result = await benchmark.evaluate(mock_env, task, "42")
        assert result["resolved"] is True
```

### Test Fixtures

Use shared fixtures for common benchmark test patterns:

```python
@pytest.fixture
def benchmark():
    """Create a benchmark instance for testing."""
    return MyBenchmark(dataset="test/dataset")


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return {
        "id": "test_001",
        "instance_id": "mybench_test_001",
        "problem_statement": "What is 2 + 2?",
        "expected_answer": "4",
    }
```

---

## Publishing Your Plugin

### As a Contribution to mcpbr

If your benchmark or provider is broadly useful, consider contributing it upstream:

1. Fork the [mcpbr repository](https://github.com/greynewell/mcpbr)
2. Create a feature branch: `git checkout -b feat/my-benchmark`
3. Add your benchmark file, tests, and registration code
4. Update `CHANGELOG.md` under the `[Unreleased]` section
5. Run the full pre-commit checklist:
    ```bash
    uvx ruff check --fix src/ tests/ && uvx ruff format src/ tests/ && uv run pytest -m "not integration"
    ```
6. Submit a pull request following the [contributing guide](contributing.md)

### As a Standalone Package

You can also distribute your benchmark as a separate Python package:

1. Create a package that depends on `mcpbr`
2. Implement the `Benchmark` protocol
3. Provide installation instructions that include registration steps (users must add the benchmark to `BENCHMARK_REGISTRY` and `VALID_BENCHMARKS` in their local mcpbr installation)

!!! note "Future Plugin System"
    A formal plugin discovery mechanism (e.g., via `entry_points`) is on the roadmap. This will allow external packages to register benchmarks and providers automatically without modifying mcpbr source code.

### Sharing YAML Benchmarks

YAML-based custom benchmarks are the easiest to share:

1. Publish your YAML definition file (e.g., as a GitHub Gist or in a repository)
2. Upload your dataset to HuggingFace Hub
3. Users simply download the YAML file and run:
    ```bash
    mcpbr run -c config.yaml
    ```

No code changes to mcpbr are required when using the `custom` benchmark type.
