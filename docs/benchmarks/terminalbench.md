---
description: "TerminalBench evaluates AI agents on practical terminal and shell tasks including file manipulation, system administration, scripting, and command-line tool usage with validation-command-based evaluation."
benchmark_howto:
  name: "TerminalBench"
  description: "Terminal/shell task completion benchmark testing file manipulation, system administration, scripting, and tool usage with validation-command-based evaluation."
  benchmark_id: "terminalbench"
faq:
  - q: "How does TerminalBench evaluate task completion?"
    a: "After the agent completes its work, a validation command is executed in the Docker environment. If the validation command exits with code 0, the task is marked as resolved. This approach checks the actual terminal state rather than the agent's textual output."
  - q: "Can I filter TerminalBench tasks by difficulty or category?"
    a: "Yes. Use --filter-difficulty to select tasks by difficulty level (e.g., easy, medium, hard) and --filter-category to select tasks by category (e.g., file-manipulation, system-admin, scripting). Both filters can be combined."
  - q: "Does TerminalBench support setup commands?"
    a: "Yes. Tasks can include a setup_command field that runs before the agent begins its work. This prepares the environment with necessary files, directories, or configurations that the task requires."
  - q: "What makes TerminalBench different from InterCode?"
    a: "TerminalBench focuses on practical terminal competency with real-world shell tasks, validated by checking the actual environment state. InterCode tests interactive code execution across multiple environments (bash, SQL, etc.) with output comparison. TerminalBench is more focused on DevOps and system administration skills."
  - q: "What kind of MCP server works best with TerminalBench?"
    a: "MCP servers that provide shell execution capabilities are essential. The agent must actually run commands in the terminal, not just describe them. Filesystem MCP servers work well for file manipulation tasks, while tasks involving system administration may benefit from servers with broader system access."
---

# TerminalBench

## Overview

| Property | Value |
|----------|-------|
| **Benchmark ID** | `terminalbench` |
| **Dataset** | [ia03/terminal-bench](https://huggingface.co/datasets/ia03/terminal-bench) |
| **Tasks** | Terminal/shell tasks across file manipulation, system administration, scripting, and tool usage |
| **Evaluation** | Executes validation command, checks exit code (0 = success) |
| **Output Type** | Shell command result (environment state verification) |
| **Timeout** | 120-300s recommended |
| **Pre-built Images** | No |
| **Difficulty Levels** | easy, medium, hard |

!!! tip "Quick Start"
    ```bash
    mcpbr run -c config.yaml --benchmark terminalbench -n 20
    ```

## Overview

[TerminalBench](https://huggingface.co/datasets/ia03/terminal-bench) is a benchmark that evaluates AI agents' ability to complete practical tasks in a terminal/shell environment. Tasks cover a wide range of command-line competencies -- from basic file manipulation and text processing to system administration, shell scripting, and effective use of Unix tools.

Unlike benchmarks that evaluate code generation in isolation, TerminalBench tests whether an agent can interact with a real shell environment to achieve concrete outcomes. The evaluation does not inspect the agent's textual response; instead, it runs a validation command that checks the actual state of the environment after the agent has finished working. This means the agent must execute real commands that produce lasting changes, not just describe what should be done.

TerminalBench is well-suited for evaluating MCP servers that provide shell access, filesystem operations, or system administration capabilities. It tests practical command-line competency rather than abstract code generation.

## What It Measures

TerminalBench evaluates practical terminal and system administration skills:

- **File manipulation**: Creating, copying, moving, renaming, and modifying files and directories with correct permissions and ownership
- **Text processing**: Using tools like `grep`, `sed`, `awk`, `sort`, `cut`, and `tr` to transform and extract data from files
- **Shell scripting**: Writing and executing bash scripts that automate multi-step operations
- **System administration**: Managing services, users, permissions, and system configurations
- **Tool proficiency**: Effective use of standard Unix utilities (`find`, `xargs`, `tar`, `curl`, `jq`, etc.)
- **Environment state management**: Ensuring commands produce persistent, verifiable changes in the filesystem and system state

TerminalBench does **not** test:

- Code generation or programming in languages other than shell
- GUI-based interactions
- Network security or exploitation
- Long-running service orchestration

## Task Structure

Each TerminalBench task contains the following fields:

| Field | Description |
|-------|-------------|
| **task_id** | Unique identifier for the task |
| **instruction** | Natural language description of the terminal task to complete |
| **category** | Task category (e.g., file-manipulation, system-admin, scripting, tool-usage) |
| **difficulty** | Difficulty level of the task (easy, medium, hard) |
| **validation_command** | Shell command that verifies task completion (exit code 0 = success) |
| **setup_command** | Optional command to prepare the environment before the agent starts |

**Example task:**

The agent receives a problem statement like:

```text
Complete the following terminal task (file-manipulation):

Create a directory called 'backup' in /workspace, then copy all .log files
from /var/log into it, preserving file permissions.
```

After the agent executes its commands, the validation command (e.g., `test -d /workspace/backup && ls /workspace/backup/*.log > /dev/null 2>&1`) checks whether the task was completed correctly.

### Task Categories

| Category | Description | Example Tasks |
|----------|-------------|---------------|
| **file-manipulation** | File and directory operations | Create directory structures, copy files with permissions, rename patterns |
| **system-admin** | System configuration and management | User management, service configuration, permission changes |
| **scripting** | Shell script creation and execution | Write scripts that process data, automate tasks, handle errors |
| **tool-usage** | Effective use of Unix utilities | Text processing pipelines, archive operations, data extraction |

## Configuration

### Basic Configuration

=== "CLI"

    ```bash
    # Run TerminalBench with default settings
    mcpbr run -c config.yaml --benchmark terminalbench

    # Run a sample of 20 tasks
    mcpbr run -c config.yaml --benchmark terminalbench -n 20

    # Filter by difficulty
    mcpbr run -c config.yaml --benchmark terminalbench --filter-difficulty easy

    # Filter by category
    mcpbr run -c config.yaml --benchmark terminalbench --filter-category scripting

    # Combine difficulty and category filters
    mcpbr run -c config.yaml --benchmark terminalbench \
      --filter-difficulty medium --filter-category file-manipulation

    # Run with verbose output
    mcpbr run -c config.yaml --benchmark terminalbench -n 10 -v

    # Save results to JSON
    mcpbr run -c config.yaml --benchmark terminalbench -n 20 -o results.json
    ```

=== "YAML"

    ```yaml
    benchmark: "terminalbench"
    sample_size: 10
    timeout_seconds: 120

    mcp_server:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

    model: "sonnet"

    # Optional: Filter by difficulty and category
    filter_difficulty:
      - "easy"
      - "medium"
    filter_category:
      - "file-manipulation"
    ```

### Advanced Options

Configuration for advanced system administration tasks:

```yaml
benchmark: "terminalbench"
sample_size: 10
timeout_seconds: 300
max_iterations: 25

filter_category:
  - "system-admin"
  - "scripting"

model: "sonnet"
```

Configuration for easy tasks with high throughput:

```yaml
benchmark: "terminalbench"
sample_size: 50
timeout_seconds: 120
max_iterations: 10
max_concurrent: 8       # Lightweight containers support high concurrency

filter_difficulty:
  - "easy"

model: "sonnet"
```

## Evaluation Methodology

TerminalBench evaluation focuses on the actual state of the environment rather than the agent's textual output:

1. **Environment Setup**: If the task includes a `setup_command`, it is executed first to prepare the environment (e.g., creating test files, configuring services). The setup command must succeed (exit code 0) or the task preparation fails with a `RuntimeError`.

2. **Agent Execution**: The agent receives the task instruction as a problem statement and interacts with the terminal environment using available shell tools. The agent's textual response is not directly evaluated.

3. **Validation**: After the agent completes its work, the task's `validation_command` is executed in the same environment with a 30-second timeout. This command inspects the environment state to verify the task was completed correctly.

4. **Resolution**: The task is marked as **resolved** if the validation command exits with code 0. Any non-zero exit code means the task was not completed successfully. Both stdout and stderr from the validation command are captured in the results for debugging.

Tasks without a validation command are marked as unresolved since there is no way to verify completion.

## Interpreting Results

### Key Metrics

| Metric | Description |
|--------|-------------|
| **Overall resolve rate** | Percentage of tasks where the validation command passed |
| **Per-difficulty resolve rate** | Accuracy broken down by easy, medium, and hard tasks |
| **Per-category resolve rate** | Accuracy broken down by task category |
| **Setup failure rate** | Percentage of tasks where the setup command failed (environment issues) |

### What Good Results Look Like

| Difficulty | Score Range | Assessment |
|------------|-------------|------------|
| **Easy** | 80-95%+ | Good -- agent handles basic file and directory operations reliably |
| **Easy** | 60-80% | Adequate -- some tool usage gaps, review failures for patterns |
| **Medium** | 60-80% | Good -- agent manages multi-step tasks and text processing |
| **Medium** | 40-60% | Adequate -- struggles with more complex command combinations |
| **Hard** | 40-60%+ | Good -- agent handles system administration and complex scripting |
| **Hard** | 20-40% | Expected -- hard tasks require advanced shell knowledge |

!!! note "Category-Specific Expectations"
    Performance varies significantly by category. **File manipulation** tasks tend to have the highest resolve rates since they involve well-known commands. **System administration** tasks are typically hardest because they involve less common operations and require understanding of system configuration details.

### Common Failure Patterns

| Pattern | Cause | Solution |
|---------|-------|----------|
| Agent describes commands but does not execute them | Agent outputs shell snippets instead of running them | Ensure MCP server provides shell execution tools; instruct agent to run commands |
| Validation fails despite correct-looking output | Validation checks very specific conditions (exact permissions, contents) | Run with `-vv` to see the exact validation command; review its specific checks |
| Setup command fails | Docker environment missing required base tools | Verify Docker image includes necessary packages; increase setup timeout |
| Permission denied errors | Agent does not use `sudo` or correct user context | Check if task requires elevated permissions; configure container accordingly |
| Partial completion | Agent completes main task but misses a detail (e.g., wrong permissions) | Review validation command to understand all checked conditions |

## Example Output

**Successful resolution:**

```json
{
  "resolved": true,
  "exit_code": 0,
  "stdout": "backup directory exists with 5 log files",
  "stderr": ""
}
```

**Failed resolution (validation check failed):**

```json
{
  "resolved": false,
  "exit_code": 1,
  "stdout": "",
  "stderr": "/workspace/backup: No such file or directory"
}
```

**Failed resolution (no validation command):**

```json
{
  "resolved": false,
  "error": "No validation command provided"
}
```

## Best Practices

### Recommended Workflow

1. **Start with easy tasks** (`--filter-difficulty easy`) to verify your MCP server provides working shell execution
2. **Test each category separately** to identify which types of terminal tasks your setup handles well
3. **Progress to medium and hard tasks** once easy tasks achieve 80%+ resolve rates
4. **Review failed validations** to understand exactly what the validation command checks and where the agent falls short

### Performance Tips

- **Provide shell execution tools** through your MCP server, as TerminalBench fundamentally requires running commands in a real terminal environment
- **Use shorter timeouts** (120s) for file manipulation tasks and longer timeouts (300s) for system administration tasks
- **Run with higher concurrency** (`max_concurrent: 8`) since terminal tasks use lightweight environments and typically complete quickly
- **Set `max_iterations` appropriately**: Simple file operations need only 5-10 iterations, while scripting tasks may require 15-20
- **Inspect validation commands** to understand exactly what constitutes success for each task -- this helps debug unexpected failures

### Cost Optimization

- **TerminalBench is cost-efficient**: Tasks typically require short interactions with few tokens compared to code generation or reasoning benchmarks
- **Easy tasks are cheapest**: Few iterations, simple commands, fast completion
- **Use `sonnet` for all difficulty levels**: Terminal tasks rarely benefit from more expensive models since they test practical knowledge rather than deep reasoning
- **High concurrency reduces wall-clock time**: Lightweight containers make parallel execution efficient
- **Filter by category** to focus evaluation on your MCP server's specific capabilities rather than running all tasks

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Setup command fails | Docker environment lacks necessary base tools | Check that the base image includes required packages. Some setup commands may need tools not present in the default image. |
| Validation passes but should not | Edge case in validation logic | This is rare; report the task ID if you suspect a validation bug in the dataset. |
| Agent does not execute shell commands | MCP server does not provide execution tools | TerminalBench requires actual command execution. Ensure your MCP server exposes shell/exec capabilities. |
| Timeout during task execution | Complex system administration tasks | Increase `timeout_seconds` to 300 for complex tasks. The validation command itself has a separate 30-second timeout. |
| Inconsistent results between runs | Environment state changes due to package updates or time-sensitive operations | Re-run specific tasks with `-t` flag for isolated testing. |

## Comparison with Similar Benchmarks

| Aspect | TerminalBench | InterCode | CyberGym | AgentBench | SWE-bench |
|--------|---------------|-----------|----------|------------|-----------|
| **Goal** | Complete shell tasks | Interactive code tasks | Exploit vulnerabilities | Multi-environment agent tasks | Fix real bugs |
| **Environment** | Unix terminal | Bash, SQL, Python | C/C++ build environment | Multiple environments | Python repositories |
| **Task Types** | File ops, sysadmin, scripting | Code execution, DB queries | Security exploitation | Web, DB, OS, coding | Bug fixing |
| **Evaluation** | Validation command (exit code) | Output comparison | Crash detection (ASAN) | String matching | Test suite pass/fail |
| **Difficulty** | easy/medium/hard | Varies | 0-3 (context levels) | Varies by environment | Uniform |
| **Setup Required** | Minimal | Environment-specific | Heavy (build toolchain) | Environment-specific | Pre-built images available |
| **Typical Timeout** | 120-300s | 120-300s | 600-900s | 120-300s | 300-600s |
| **Best For** | CLI capability testing | Multi-environment code interaction | Security research | Broad agent evaluation | Software engineering |

!!! tip "When to Use TerminalBench"
    Use TerminalBench when you want to evaluate an MCP server's effectiveness for **practical command-line and system administration tasks**. It is the best benchmark for testing whether an agent can reliably execute shell commands to produce real-world outcomes. For code-focused evaluation, use HumanEval or SWE-bench. For security-focused shell interaction, use CyberGym.

## References

- [TerminalBench Dataset on HuggingFace](https://huggingface.co/datasets/ia03/terminal-bench)
- [InterCode](intercode.md) -- interactive code environment benchmark
- [CyberGym](cybergym.md) -- security exploitation benchmark
- [AgentBench](agentbench.md) -- multi-environment agent benchmark
- [Benchmarks Overview](index.md)
- [Configuration Reference](../configuration.md)
- [CLI Reference](../cli.md)
