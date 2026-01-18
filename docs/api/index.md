---
faq:
  - q: "What is the mcpbr Python API?"
    a: "mcpbr provides a Python API for programmatic access to evaluation functionality, including configuration management, harness creation, Docker environment management, and result processing."
  - q: "How do I run mcpbr evaluations programmatically?"
    a: "Import the run_evaluation function from mcpbr.harness, create a HarnessConfig object, and call await run_evaluation(config). This returns an EvaluationResults object with all task results."
  - q: "What protocols does mcpbr define for extensibility?"
    a: "mcpbr defines AgentHarness (for agent backends) and ModelProvider (for LLM providers) protocols, allowing you to add custom implementations by creating classes that implement these interfaces."
---

# API Reference

This page documents the mcpbr Python API for programmatic usage.

## Quick Example

```python
import asyncio
from mcpbr.config import HarnessConfig, MCPServerConfig, load_config
from mcpbr.harness import run_evaluation

async def main():
    # Load config from file
    config = load_config("mcpbr.yaml")

    # Or create programmatically
    config = HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        model="sonnet",
        sample_size=5,
    )

    # Run evaluation
    results = await run_evaluation(
        config=config,
        run_mcp=True,
        run_baseline=True,
        verbose=True,
    )

    # Process results
    print(f"MCP resolved: {results.summary['mcp']['resolved']}")
    print(f"Baseline resolved: {results.summary['baseline']['resolved']}")

asyncio.run(main())
```

---

## Configuration

### MCPServerConfig

::: mcpbr.config.MCPServerConfig
    options:
      show_root_heading: true
      show_source: false
      members:
        - name
        - command
        - args
        - env
        - get_args_for_workdir
        - get_expanded_env

### HarnessConfig

::: mcpbr.config.HarnessConfig
    options:
      show_root_heading: true
      show_source: false

### load_config

::: mcpbr.config.load_config
    options:
      show_root_heading: true
      show_source: false

---

## Harness

### run_evaluation

::: mcpbr.harness.run_evaluation
    options:
      show_root_heading: true
      show_source: false

### EvaluationResults

::: mcpbr.harness.EvaluationResults
    options:
      show_root_heading: true
      show_source: false

### TaskResult

::: mcpbr.harness.TaskResult
    options:
      show_root_heading: true
      show_source: false

---

## Agent Harnesses

### AgentHarness Protocol

::: mcpbr.harnesses.AgentHarness
    options:
      show_root_heading: true
      show_source: false

### AgentResult

::: mcpbr.harnesses.AgentResult
    options:
      show_root_heading: true
      show_source: false

### create_harness

::: mcpbr.harnesses.create_harness
    options:
      show_root_heading: true
      show_source: false

### ClaudeCodeHarness

::: mcpbr.harnesses.ClaudeCodeHarness
    options:
      show_root_heading: true
      show_source: false

---

## Docker Environment

### DockerEnvironmentManager

::: mcpbr.docker_env.DockerEnvironmentManager
    options:
      show_root_heading: true
      show_source: false

### TaskEnvironment

::: mcpbr.docker_env.TaskEnvironment
    options:
      show_root_heading: true
      show_source: false
      members:
        - container
        - workdir
        - host_workdir
        - instance_id
        - uses_prebuilt
        - claude_cli_installed
        - exec_command
        - exec_command_streaming
        - write_file
        - read_file
        - cleanup

---

## Evaluation

### evaluate_patch

::: mcpbr.evaluation.evaluate_patch
    options:
      show_root_heading: true
      show_source: false

### EvaluationResult

::: mcpbr.evaluation.EvaluationResult
    options:
      show_root_heading: true
      show_source: false

### TestResults

::: mcpbr.evaluation.TestResults
    options:
      show_root_heading: true
      show_source: false

---

## Models

### ModelInfo

::: mcpbr.models.ModelInfo
    options:
      show_root_heading: true
      show_source: false

### list_supported_models

::: mcpbr.models.list_supported_models
    options:
      show_root_heading: true
      show_source: false

### get_model_info

::: mcpbr.models.get_model_info
    options:
      show_root_heading: true
      show_source: false

### is_model_supported

::: mcpbr.models.is_model_supported
    options:
      show_root_heading: true
      show_source: false

---

## Constants

### Default Values

```python
from mcpbr.models import DEFAULT_MODEL
from mcpbr.config import VALID_PROVIDERS, VALID_HARNESSES

print(DEFAULT_MODEL)       # "sonnet"
print(VALID_PROVIDERS)     # ("anthropic",)
print(VALID_HARNESSES)     # ("claude-code",)
```

### Docker Registry

```python
from mcpbr.docker_env import SWEBENCH_IMAGE_REGISTRY

# Pre-built images from Epoch AI
print(SWEBENCH_IMAGE_REGISTRY)
# "ghcr.io/epoch-research/swe-bench.eval"
```
