---
faq:
  - q: "How do I configure mcpbr to use my MCP server?"
    a: "Configure the mcp_server section in your YAML config file with the command to start your server, args (using {workdir} as placeholder for the task repository path), and any required environment variables."
  - q: "What configuration parameters are available in mcpbr?"
    a: "Key parameters include mcp_server (command, args, env), provider (anthropic), model, dataset, sample_size, timeout_seconds, max_concurrent, and max_iterations."
  - q: "How do I use environment variables in mcpbr config?"
    a: "Reference environment variables in the env section using ${VAR_NAME} syntax, e.g., SUPERMODEL_API_KEY: '${SUPERMODEL_API_KEY}'. The variable will be expanded from your shell environment at runtime."
  - q: "What is the {workdir} placeholder in mcpbr?"
    a: "The {workdir} placeholder is replaced at runtime with the path to the task repository inside the Docker container. Use it in your MCP server args to point to the workspace."
---

# Configuration

mcpbr uses YAML configuration files to define your MCP server settings and evaluation parameters.

## Generating a Config File

Create a starter configuration:

```bash
mcpbr init
```

This creates `mcpbr.yaml` with sensible defaults.

## Configuration Reference

### Full Example

```yaml
# MCP Server Configuration
mcp_server:
  name: "mcpbr"  # Name for the MCP server (appears in tool names)
  command: "npx"
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
  env: {}

# Provider and Harness
provider: "anthropic"
agent_harness: "claude-code"

# Custom Agent Prompt (optional)
agent_prompt: |
  Fix the following bug in this repository:

  {problem_statement}

  Make the minimal changes necessary to fix the issue.
  Focus on the root cause, not symptoms.

# Model Configuration (use alias or full name)
model: "sonnet"  # or "claude-sonnet-4-5-20250929"

# Dataset Configuration
dataset: "SWE-bench/SWE-bench_Lite"
sample_size: 10  # null for full dataset

# Execution Parameters
timeout_seconds: 300
max_concurrent: 4
max_iterations: 10

# Docker Configuration
use_prebuilt_images: true
```

### MCP Server Section

The `mcp_server` section defines how to start your MCP server:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Name to register the MCP server as (default: `mcpbr`) |
| `command` | string | Executable to run (e.g., `npx`, `uvx`, `python`) |
| `args` | list | Command arguments. Use `{workdir}` as placeholder |
| `env` | dict | Additional environment variables |

#### The `{workdir}` Placeholder

The `{workdir}` placeholder is replaced at runtime with the path to the task repository inside the Docker container (typically `/workspace`). This allows your MCP server to access the codebase.

#### Environment Variables

Reference environment variables using `${VAR_NAME}` syntax:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server"]
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

### Provider and Harness

| Field | Values | Description |
|-------|--------|-------------|
| `provider` | `anthropic` | LLM provider (currently only Anthropic is supported) |
| `agent_harness` | `claude-code` | Agent backend (currently only Claude Code CLI is supported) |

### Custom Agent Prompt

Customize the prompt sent to the agent:

```yaml
agent_prompt: |
  Fix the following bug in this repository:

  {problem_statement}

  Make the minimal changes necessary to fix the issue.
  Focus on the root cause, not symptoms.
```

Use `{problem_statement}` as a placeholder for the SWE-bench issue text.

!!! tip "CLI Override"
    Override the prompt at runtime with `--prompt`:
    ```bash
    mcpbr run -c config.yaml --prompt "Fix this: {problem_statement}"
    ```

### Model Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `model` | `sonnet` | Model alias or full Anthropic model ID |

You can use either aliases (`sonnet`, `opus`, `haiku`) or full model names (`claude-sonnet-4-5-20250929`).
Aliases automatically resolve to the latest model version.

See [Installation](installation.md#supported-models) for the full list of supported models.

### Benchmark Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `benchmark` | `swe-bench` | Benchmark to run (`swe-bench` or `cybergym`) |
| `cybergym_level` | `1` | CyberGym difficulty level (0-3, only used for CyberGym) |

!!! info "Benchmark Selection"
    - **SWE-bench**: Bug fixing in Python repositories, evaluated with test suites
    - **CyberGym**: Security exploit generation in C/C++ projects, evaluated by crash detection

    See the [Benchmarks guide](benchmarks.md) for detailed information.

!!! tip "CLI Override"
    Override the benchmark at runtime:
    ```bash
    # Run CyberGym instead of SWE-bench
    mcpbr run -c config.yaml --benchmark cybergym --level 2
    ```

### Dataset Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `dataset` | `null` | HuggingFace dataset (optional, benchmark provides default) |
| `sample_size` | `null` | Number of tasks (`null` = full dataset) |

The `dataset` field is optional. If not specified, each benchmark uses its default dataset:

- **SWE-bench**: `SWE-bench/SWE-bench_Lite`
- **CyberGym**: `sunblaze-ucb/cybergym`

### Execution Parameters

| Field | Default | Description |
|-------|---------|-------------|
| `timeout_seconds` | `300` | Timeout per task in seconds |
| `max_concurrent` | `4` | Maximum parallel task evaluations |
| `max_iterations` | `10` | Maximum agent iterations (turns) per task |

### Docker Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `use_prebuilt_images` | `true` | Use pre-built SWE-bench Docker images when available |

## Example Configurations

### Anthropic Filesystem Server

Basic file system access:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]
```

### Custom Python MCP Server

```yaml
mcp_server:
  command: "python"
  args: ["-m", "my_mcp_server", "--workspace", "{workdir}"]
  env:
    LOG_LEVEL: "debug"
```

### Supermodel Codebase Analysis

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server"]
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

### Fast Iteration (Development)

Small sample size with single concurrency for debugging:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "haiku"  # Faster, cheaper
sample_size: 3
max_concurrent: 1
timeout_seconds: 180
max_iterations: 5
```

### Full Benchmark Run

Comprehensive evaluation with maximum parallelism:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "sonnet"
sample_size: null  # Full dataset
max_concurrent: 8
timeout_seconds: 600
max_iterations: 30
```

## Configuration Validation

mcpbr validates your configuration on startup:

- `provider` must be one of: `anthropic`
- `agent_harness` must be one of: `claude-code`
- `max_concurrent` must be at least 1
- `timeout_seconds` must be at least 30

Invalid configurations will produce clear error messages.

## Next Steps

- [CLI Reference](cli.md) - Command options that override config values
- [MCP Integration](mcp-integration.md) - Tips for testing your MCP server
- [Evaluation Results](evaluation-results.md) - Understanding output formats
