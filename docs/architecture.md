---
description: "mcpbr architecture overview covering the evaluation pipeline, Docker orchestration, benchmark abstraction, and agent harness design."
faq:
  - q: "How does mcpbr work internally?"
    a: "mcpbr loads SWE-bench tasks from HuggingFace, creates Docker containers with pre-built environments for each task, runs Claude Code CLI inside the container with and without MCP tools, applies the generated patches, runs tests, and aggregates the results."
  - q: "Why does mcpbr run the agent inside Docker?"
    a: "Running inside Docker ensures Python imports work correctly (e.g., 'from astropy import ...'), the agent can run tests and verify fixes, and there are no dependency conflicts with the host machine."
  - q: "What are pre-built SWE-bench images?"
    a: "Pre-built images from Epoch AI's registry contain the repository at the correct commit with all dependencies pre-installed and validated, providing a consistent environment for reproducible evaluations."
  - q: "What is the architecture of mcpbr?"
    a: "mcpbr consists of several modules: cli.py (CLI), config.py (configuration models), harness.py (orchestrator), harnesses.py (agent implementations), docker_env.py (container management), evaluation.py (patch testing), and reporting.py (output formatting)."
---

# Architecture

This page explains how mcpbr works internally and the design decisions behind it.

## Overview

mcpbr is a benchmark runner that evaluates MCP (Model Context Protocol) servers by comparing agent performance with and without MCP tools on real GitHub issues from the SWE-bench dataset.

A key architectural principle is that **MCP servers should be tested like APIs, not like plugins** — meaning mcpbr measures defined contracts, handles non-deterministic agent behavior statistically, and prioritizes reproducibility. For the full design rationale, read [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/) and the [Testing Philosophy](philosophy.md) page.

## Execution Flow

```
                         +-----------------+
                         |  mcpbr run      |
                         +--------+--------+
                                  |
                   +--------------v--------------+
                   |  Load SWE-bench tasks from  |
                   |  HuggingFace datasets       |
                   +--------------+--------------+
                                  |
          +-----------------------v-----------------------+
          |           For each task (parallel)           |
          |  +----------------------------------------+  |
          |  |  1. Pull pre-built Docker image        |  |
          |  |  2. Create container with repo         |  |
          |  |  3. Install Claude CLI                 |  |
          |  |  4. Run MCP agent (if enabled)         |  |
          |  |  5. Run baseline agent (if enabled)    |  |
          |  |  6. Extract patches                    |  |
          |  |  7. Apply patches and run tests        |  |
          |  |  8. Record results                     |  |
          |  +----------------------------------------+  |
          +----------------------+-----------------------+
                                 |
                   +-------------v-------------+
                   |  Aggregate results        |
                   |  Generate reports         |
                   +---------------------------+
```

## Module Structure

```
src/mcpbr/
├── cli.py           # Command-line interface (Click-based)
├── config.py        # Configuration models (Pydantic)
├── models.py        # Supported model registry
├── providers.py     # LLM provider abstractions
├── harnesses.py     # Agent harness implementations
├── harness.py       # Main orchestrator
├── agent.py         # Legacy baseline agent
├── docker_env.py    # Docker environment management
├── evaluation.py    # Patch application and testing
├── log_formatter.py # Streaming output formatting
└── reporting.py     # Results formatting (JSON, Markdown)
```

### Key Components

#### `harness.py` - Orchestrator

The main entry point that:

- Loads SWE-bench tasks from HuggingFace
- Creates Docker environments for each task
- Runs agents (MCP and baseline) in parallel
- Collects and aggregates results

```python
async def run_evaluation(
    config: HarnessConfig,
    run_mcp: bool = True,
    run_baseline: bool = True,
    ...
) -> EvaluationResults:
```

#### `docker_env.py` - Container Management

Manages Docker containers for isolated task execution:

- `DockerEnvironmentManager`: Creates and manages containers
- `TaskEnvironment`: Represents a single task's environment
- Handles pre-built image pulling from Epoch AI's registry
- Installs Node.js and Claude CLI inside containers

#### `harnesses.py` - Agent Implementation

Contains the `ClaudeCodeHarness` class that:

- Shells out to Claude Code CLI
- Registers MCP servers with `claude mcp add`
- Streams agent output for real-time logging
- Extracts git diffs for patches

#### `evaluation.py` - Patch Testing

Handles the evaluation phase:

- `apply_patch()`: Applies unified diff patches via git
- `run_tests()`: Executes pytest with SWE-bench test specs
- `evaluate_patch()`: Full evaluation workflow

## Container Architecture

```
+----------------------------------------------------------------+
|                        Host Machine                             |
|  +----------------------------------------------------------+  |
|  |                 mcpbr Harness (Python)                   |  |
|  |  - Loads SWE-bench tasks from HuggingFace                |  |
|  |  - Pulls pre-built Docker images                         |  |
|  |  - Orchestrates agent runs                               |  |
|  |  - Collects results and generates reports                |  |
|  +----------------------------+-----------------------------+  |
|                               | docker exec                    |
|  +----------------------------v-----------------------------+  |
|  |               Docker Container (per task)                |  |
|  |  +----------------------------------------------------+  |  |
|  |  |  Pre-built SWE-bench Image                         |  |  |
|  |  |  - Repository at correct commit                    |  |  |
|  |  |  - All dependencies installed (astropy, django...) |  |  |
|  |  |  - Conda environment with testbed                  |  |  |
|  |  +----------------------------------------------------+  |  |
|  |                                                          |  |
|  |  Runtime Setup:                                          |  |
|  |  - Node.js installed                                     |  |
|  |  - Claude CLI installed globally                         |  |
|  |  - Non-root user (mcpbr) created                        |  |
|  |                                                          |  |
|  |  Agent Execution:                                        |  |
|  |  - Claude CLI runs as mcpbr user                        |  |
|  |  - Makes API calls to Anthropic                          |  |
|  |  - Executes Bash commands (imports work!)                |  |
|  |  - Reads/writes files                                    |  |
|  |  - Generates patches                                     |  |
|  |                                                          |  |
|  |  Evaluation:                                             |  |
|  |  - Patches applied via git                               |  |
|  |  - pytest runs in conda testbed environment              |  |
|  +----------------------------------------------------------+  |
+----------------------------------------------------------------+
```

## Why Run Inside Docker?

The agent (Claude Code CLI) runs **inside** the Docker container rather than on the host. This design choice provides:

1. **Working Imports**: Python imports work correctly (e.g., `from astropy import ...`)
2. **Test Execution**: The agent can run tests and verify fixes
3. **No Conflicts**: No dependency conflicts with the host machine
4. **Reproducibility**: Identical environment across runs

## Pre-built Images

mcpbr uses pre-built SWE-bench Docker images from [Epoch AI's registry](https://github.com/orgs/Epoch-Research/packages):

```
ghcr.io/epoch-research/swe-bench.eval.x86_64.{instance_id}
```

These images contain:

- Repository checked out at the correct (buggy) commit
- All project dependencies pre-installed and validated
- Conda environment named `testbed` with correct Python version

### Fallback Path

If a pre-built image isn't available, mcpbr falls back to:

1. Using a generic Python 3.11 image
2. Cloning the repository at the correct commit
3. Attempting dependency installation (less reliable)

## Protocol-Based Design

mcpbr uses Python Protocols for extensibility:

```python
@runtime_checkable
class AgentHarness(Protocol):
    async def solve(
        self,
        task: dict[str, Any],
        workdir: str,
        timeout: int = 300,
        verbose: bool = False,
        task_id: str | None = None,
        env: TaskEnvironment | None = None,
    ) -> AgentResult:
        ...
```

This allows future addition of:

- New agent backends (e.g., other coding agents)
- New LLM providers
- Custom evaluation pipelines

## Signal Handling

mcpbr registers signal handlers for graceful cleanup:

```python
def register_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
```

On interrupt:

1. Running agents are terminated
2. Docker containers are stopped and removed
3. Temporary directories are cleaned up

This prevents orphaned containers from accumulating.

## Next Steps

- [About mcpbr](about.md) - The project story and vision
- [Testing Philosophy](philosophy.md) - Why MCP servers should be tested like APIs
- [MCP Integration](mcp-integration.md) - How to test your MCP server
- [API Reference](api/index.md) - Detailed module documentation
- [Contributing](contributing.md) - How to extend mcpbr
