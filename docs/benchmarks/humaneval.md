---
description: "HumanEval evaluates AI agents on 164 Python programming problems from OpenAI, testing code generation from function signatures and docstrings with unit test verification."
benchmark_howto:
  name: "HumanEval"
  description: "Evaluate MCP server-assisted code generation on 164 Python function completion tasks from OpenAI's HumanEval dataset."
  benchmark_id: "humaneval"
faq:
  - q: "What is HumanEval and how does mcpbr use it?"
    a: "HumanEval is a benchmark of 164 Python programming problems created by OpenAI. Each task requires completing a function given its signature and docstring. mcpbr uses it to evaluate how well MCP servers assist language models in generating correct Python code."
  - q: "How are HumanEval tasks evaluated in mcpbr?"
    a: "The agent's solution is saved to solution.py, combined with the task's unit tests, and executed with Python. A task is resolved if all unit tests pass without assertion errors."
  - q: "Do I need Docker pre-built images for HumanEval?"
    a: "No. HumanEval uses lightweight Python environments created on the fly. No git repository cloning or pre-built Docker images are needed, making it fast to set up and run."
  - q: "How does HumanEval compare to MBPP?"
    a: "Both test Python code generation, but HumanEval problems are hand-crafted by researchers with detailed docstrings, while MBPP uses crowd-sourced entry-level problems. HumanEval has 164 tasks; MBPP has roughly 1,000. HumanEval is the standard quick-evaluation choice."
  - q: "What pass@k metric should I target?"
    a: "State-of-the-art models typically achieve 85-95% pass@1 on HumanEval. A good MCP server integration should help maintain or improve upon the base model's pass rate. Scores below 70% suggest configuration issues or prompt problems."
---

# HumanEval

## Overview

| Property | Value |
|----------|-------|
| **Benchmark ID** | `humaneval` |
| **Dataset** | [openai_humaneval](https://huggingface.co/datasets/openai_humaneval) |
| **Tasks** | 164 Python programming problems |
| **Evaluation** | Unit tests combined with solution, exit code 0 = pass |
| **Output Type** | Function code (saved to `solution.py`) |
| **Timeout** | 60-180s recommended |
| **Pre-built Images** | No (lightweight Python container) |
| **Difficulty Levels** | None (uniform difficulty) |

!!! tip "Quick Start"
    ```bash
    mcpbr run -c config.yaml --benchmark humaneval -n 20
    ```

## Overview

[HumanEval](https://github.com/openai/human-eval) is a code generation benchmark created by OpenAI consisting of 164 hand-written Python programming problems. Each task provides a function signature with a descriptive docstring, and the agent must produce a correct implementation that passes all accompanying unit tests.

HumanEval is widely used as a baseline measure of code generation capability. Problems range from simple string manipulation and list operations to moderate algorithmic challenges. Because tasks are self-contained single functions with no external dependencies, HumanEval is an excellent choice for quick evaluations and smoke testing before running more expensive benchmarks like SWE-bench.

In mcpbr, HumanEval evaluates how effectively an MCP server assists the language model in generating correct, test-passing Python code within lightweight Docker containers.

## What It Measures

HumanEval tests a focused set of code generation capabilities:

- **Function-level code synthesis**: The ability to translate a natural language specification (docstring) into correct Python code
- **Type-aware programming**: Functions include type hints that the agent must respect and leverage
- **Edge case handling**: Unit tests cover boundary conditions, empty inputs, and special cases that require careful implementation
- **Standard library fluency**: All problems use only the Python standard library, testing the agent's knowledge of built-in data structures, string operations, and mathematical functions
- **Docstring comprehension**: The agent must correctly interpret examples, constraints, and expected behavior described in the docstring

HumanEval does **not** test:

- Multi-file or multi-class code generation
- External library usage (numpy, pandas, etc.)
- Bug fixing or debugging existing code
- Long-context repository understanding

## Task Structure

Each HumanEval task contains the following fields:

| Field | Description |
|-------|-------------|
| **task_id** | Unique identifier such as `HumanEval/0`, `HumanEval/1`, etc. |
| **prompt** | Function signature with docstring describing the requirements and examples |
| **entry_point** | Name of the function to implement (e.g., `has_close_elements`) |
| **canonical_solution** | Reference implementation (not shown to the agent) |
| **test** | Unit tests to verify correctness |

**Example task prompt:**

```python
def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """ Check if in given list of numbers, are any two numbers closer to each other than
    given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
    True
    """
```

The agent receives the function signature and docstring, implements the function body, and saves the result to `solution.py`. Task IDs are converted to Docker-safe names by replacing slashes with underscores (e.g., `HumanEval/0` becomes `HumanEval_0`).

## Configuration

### Basic Configuration

=== "CLI"

    ```bash
    # Run HumanEval with default settings
    mcpbr run -c config.yaml --benchmark humaneval

    # Run a small sample for quick testing
    mcpbr run -c config.yaml --benchmark humaneval -n 20

    # Run specific tasks by ID
    mcpbr run -c config.yaml --benchmark humaneval -t HumanEval/0 -t HumanEval/1

    # Run with verbose output
    mcpbr run -c config.yaml --benchmark humaneval -n 10 -v

    # Save results to JSON
    mcpbr run -c config.yaml --benchmark humaneval -n 20 -o results.json
    ```

=== "YAML Configuration"

    ```yaml
    benchmark: "humaneval"
    sample_size: 10
    timeout_seconds: 180
    max_iterations: 15

    mcp_server:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

    model: "sonnet"
    ```

### Advanced Options

HumanEval does not support difficulty or category filtering since all 164 tasks are uniform Python function completions. However, you can select specific tasks by ID:

```bash
# Run specific tasks for targeted testing
mcpbr run -c config.yaml --benchmark humaneval \
  -t HumanEval/0 -t HumanEval/10 -t HumanEval/50

# Run all tasks with extended timeout and results
mcpbr run -c config.yaml --benchmark humaneval \
  -o results.json -r report.md -v
```

Configuration optimized for throughput:

```yaml
benchmark: "humaneval"
sample_size: 164       # All tasks
timeout_seconds: 120
max_iterations: 10
max_concurrent: 8      # High concurrency -- lightweight containers

mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "sonnet"
```

## Evaluation Methodology

HumanEval evaluation follows a straightforward test-execution pipeline:

1. **Solution discovery**: The evaluator looks for the agent's solution file. It checks several candidate filenames in order: `solution.py`, `answer.py`, `code.py`, `implementation.py`, `main.py`. If no file is found, it attempts to extract code from the agent's raw response (markdown code blocks or inline function definitions).

2. **Test assembly**: The solution code is combined with the task's unit test code and a `check()` call that invokes the tests against the implemented entry point function.

3. **Execution**: The combined file is executed with `python3` inside the Docker container with a 30-second timeout.

4. **Verdict**: The task is marked as **resolved** if the Python process exits with code 0 and no `AssertionError` appears in stderr.

The evaluation does not require any external packages. All HumanEval tasks use only the Python standard library.

## Interpreting Results

### Key Metrics

| Metric | Description |
|--------|-------------|
| **pass@1** | Percentage of tasks resolved on the first attempt (primary metric) |
| **Resolve rate** | Equivalent to pass@1 in mcpbr's single-attempt evaluation |
| **Error breakdown** | Distribution of failure types: assertion errors vs. runtime errors vs. no solution |

### What Good Results Look Like

| Score Range | Assessment |
|-------------|------------|
| **90-100%** | Excellent -- state-of-the-art code generation with effective MCP assistance |
| **80-90%** | Good -- strong code generation, may struggle with complex algorithmic problems |
| **70-80%** | Adequate -- baseline capability, check for prompt or configuration improvements |
| **Below 70%** | Needs investigation -- likely configuration issues, poor prompting, or MCP server problems |

!!! note "Context: Industry Benchmarks"
    Leading models (Claude, GPT-4, etc.) achieve 85-95% on HumanEval without MCP assistance. An effective MCP server integration should maintain or slightly improve these scores. Significant drops below the base model's capability suggest integration issues rather than model limitations.

### Common Failure Patterns

| Pattern | Cause | Solution |
|---------|-------|----------|
| High assertion errors | Incorrect logic or edge case handling | Review failed tasks; consider enabling extended thinking |
| No solution file found | Agent describes code but does not save it | Strengthen prompt to emphasize saving to `solution.py` |
| Import errors | Agent uses third-party libraries | Add instruction to use only standard library |
| Timeout failures | Infinite loops or extremely slow algorithms | Set `timeout_seconds: 180`; review algorithmic complexity |
| Signature modification | Agent changes function name or parameters | Emphasize preserving the exact function signature |

## Example Output

**Successful resolution:**

```json
{
  "resolved": true,
  "exit_code": 0,
  "stdout": "",
  "stderr": ""
}
```

**Failed resolution (assertion error):**

```json
{
  "resolved": false,
  "exit_code": 1,
  "stdout": "",
  "stderr": "Traceback (most recent call last):\n  File \"test_solution.py\", line 12, in <module>\n    check(has_close_elements)\n  File \"test_solution.py\", line 8, in check\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True\nAssertionError",
  "error": "Test assertions failed"
}
```

**Failed resolution (no solution found):**

```json
{
  "resolved": false,
  "error": "No solution file found and could not extract code from solution"
}
```

## Best Practices

### Recommended Workflow

1. **Start with a small sample** (10-20 tasks) to verify your setup before running all 164 tasks
2. **Review the first few results** to confirm the agent saves solutions to `solution.py`
3. **Run the full benchmark** once configuration is validated
4. **Compare across models** by running with different model configurations

### Performance Tips

- **Use shorter timeouts** (60-180s) since HumanEval tasks are quick and well-defined
- **Run high concurrency** (`max_concurrent: 8` or higher) since each task uses a lightweight Python container with minimal resource requirements
- **Set `max_iterations` lower** (10-15) since tasks are simpler than SWE-bench and require fewer agent turns
- **Run HumanEval first** before expensive benchmarks like SWE-bench as a smoke test for your MCP server integration

### Cost Optimization

- **164 tasks is manageable**: Running all tasks is feasible and recommended for consistent benchmarking
- **Low token usage**: Function completion typically requires fewer tokens than bug-fixing or multi-step reasoning tasks
- **Quick turnaround**: Most tasks complete in under 2 minutes, making full-suite runs practical even for iteration
- **Use `sonnet` for cost efficiency**: HumanEval tasks rarely benefit from the additional reasoning capability of more expensive models

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Agent does not create `solution.py` | Agent outputs code in response but does not save a file | Ensure your agent prompt explicitly instructs saving to `solution.py`. The evaluator falls back to response extraction, but file-based solutions are more reliable. |
| Tests fail with import errors | Agent imports third-party packages (e.g., `numpy`) | HumanEval tasks use only the Python standard library. Verify that the agent prompt discourages external dependencies. |
| Timeout during evaluation | Agent's implementation contains infinite loops or slow algorithms | Individual test execution has a 30-second timeout. Set `timeout_seconds: 180` in configuration for the overall task timeout. |
| Function signature is modified | Agent changes function name, parameters, or type hints | The test harness calls the original `entry_point` function name. The agent must preserve the exact signature. |
| Low scores despite correct logic | Agent wraps code in a class or adds extra boilerplate | HumanEval expects bare function definitions. Instruct the agent to write only the function implementation. |

## Comparison with Similar Benchmarks

| Aspect | HumanEval | MBPP | SWE-bench | APPS |
|--------|-----------|------|-----------|------|
| **Goal** | Complete a function | Solve a coding problem | Fix a real bug | Solve coding challenges |
| **Task Count** | 164 | ~1,000 | 300-2,294 | 10,000 |
| **Difficulty** | Moderate (uniform) | Easy-moderate | High | Easy-competition |
| **Languages** | Python only | Python only | Python only | Python only |
| **Output** | Function body | Function/program | Unified diff patch | Full program |
| **Dependencies** | Standard library only | Standard library only | Project-specific | Varies |
| **Pre-built Images** | No | No | Yes (Epoch AI) | No |
| **Typical Runtime** | 1-2 min/task | 1-2 min/task | 5-10 min/task | 2-5 min/task |
| **Best For** | Quick smoke tests, baseline metrics | Larger-scale code generation evaluation | Real-world software engineering | Broad code generation across difficulty levels |

!!! tip "When to Use HumanEval"
    Use HumanEval when you need a **quick, reliable baseline** for code generation capability. It is the standard first benchmark to run when setting up a new MCP server or model configuration. For more comprehensive evaluation, follow up with SWE-bench or APPS.

## References

- [HumanEval Repository](https://github.com/openai/human-eval)
- [HumanEval Paper (Evaluating Large Language Models Trained on Code)](https://arxiv.org/abs/2107.03374)
- [HumanEval Dataset on HuggingFace](https://huggingface.co/datasets/openai_humaneval)
- [MBPP Benchmark](mbpp.md) -- related code generation benchmark with more tasks
- [SWE-bench](swe-bench.md) -- real-world bug fixing benchmark
- [Benchmarks Overview](index.md)
- [Configuration Reference](../configuration.md)
- [CLI Reference](../cli.md)
