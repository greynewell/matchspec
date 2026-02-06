---
faq:
  - q: "How do I configure mcpbr?"
    a: "Create a YAML configuration file or build a HarnessConfig object programmatically. The config specifies the MCP server, model, benchmark, and runtime settings like timeout, concurrency, and budget."
  - q: "What environment variables does mcpbr support in config files?"
    a: "mcpbr supports ${VAR} and ${VAR:-default} syntax in YAML config files. It automatically loads .env files from the current directory. Environment variables can be referenced in any string value."
  - q: "How do I run evaluations on Azure?"
    a: "Set infrastructure.mode to 'azure' and provide an infrastructure.azure block with resource_group, location, vm_size, and other Azure-specific settings. mcpbr will provision a VM, run the evaluation, and optionally shut it down."
  - q: "What is comparison mode?"
    a: "Comparison mode runs two MCP servers side-by-side on the same tasks, producing a detailed comparison of resolution rates, costs, and per-task outcomes. Enable it with comparison_mode: true and provide mcp_server_a and mcp_server_b configs."
---

# Configuration Reference

The `mcpbr.config` module provides Pydantic-based configuration models for the evaluation harness. All configuration can be specified via YAML files or constructed programmatically.

---

## HarnessConfig

The main configuration class for the evaluation harness. Every field has a sensible default except `mcp_server` (required in single-server mode).

::: mcpbr.config.HarnessConfig
    options:
      show_root_heading: true
      show_source: false

### Fields

#### MCP Server Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mcp_server` | `MCPServerConfig \| None` | `None` | MCP server configuration (required when `comparison_mode` is `false`) |
| `mcp_server_a` | `MCPServerConfig \| None` | `None` | First MCP server for comparison mode |
| `mcp_server_b` | `MCPServerConfig \| None` | `None` | Second MCP server for comparison mode |
| `comparison_mode` | `bool` | `false` | Enable side-by-side comparison mode |

#### Model and Provider

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `str` | `"anthropic"` | Model provider. Valid: `anthropic`, `openai`, `gemini`, `qwen` |
| `model` | `str` | `"sonnet"` | Model ID for the selected provider |
| `agent_harness` | `str` | `"claude-code"` | Agent harness to use. Valid: `claude-code` |
| `agent_prompt` | `str \| None` | `None` | Custom prompt template. Use `{problem_statement}` as placeholder |

#### Benchmark Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `benchmark` | `str` | `"swe-bench-verified"` | Benchmark to run. Use `mcpbr benchmarks` for the full list |
| `sample_size` | `int \| None` | `None` | Number of tasks to evaluate (`None` for full dataset) |
| `cybergym_level` | `int` | `1` | CyberGym difficulty level (0-3) |
| `filter_difficulty` | `list[str] \| None` | `None` | Filter by difficulty (e.g., `["easy", "medium"]`) |
| `filter_category` | `list[str] \| None` | `None` | Filter by category (e.g., `["django", "flask"]`) |
| `filter_tags` | `list[str] \| None` | `None` | Filter by tags (all tags must match) |

#### Runtime Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timeout_seconds` | `int` | `300` | Timeout for each task in seconds (minimum: 30) |
| `max_concurrent` | `int` | `4` | Maximum concurrent task evaluations (minimum: 1) |
| `max_iterations` | `int` | `10` | Maximum agent iterations per task |
| `thinking_budget` | `int \| None` | `None` | Extended thinking token budget (1024-31999 if set) |
| `budget` | `float \| None` | `None` | Maximum budget in USD (halts when reached) |
| `continue_on_error` | `bool` | `true` | Continue evaluation when individual tasks fail |
| `max_failures` | `int \| None` | `None` | Maximum task failures before halting (`None` for unlimited) |

#### Caching and Checkpointing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cache_enabled` | `bool` | `false` | Enable result caching to avoid re-running identical evaluations |
| `cache_dir` | `Path \| None` | `None` | Cache directory (default: `~/.cache/mcpbr`) |
| `checkpoint_interval` | `int` | `1` | Save checkpoint every N completed tasks (minimum: 1) |
| `resume_from_checkpoint` | `Path \| None` | `None` | Path to checkpoint file to resume from |

#### Docker and Infrastructure

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_prebuilt_images` | `bool` | `true` | Use pre-built Docker images when available |
| `volumes` | `dict[str, str]` | `{}` | Additional volume mounts (`host_path: container_path`) |
| `infrastructure` | `InfrastructureConfig` | `InfrastructureConfig()` | Infrastructure configuration (local or azure) |

#### Output

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output_dir` | `str \| None` | `None` | Directory for outputs (default: `.mcpbr_run_TIMESTAMP`) |
| `disable_logs` | `bool` | `false` | Disable detailed execution logs |
| `enable_profiling` | `bool` | `false` | Enable performance profiling (tool latency, memory) |

### Validators

HarnessConfig includes automatic validation:

- **provider**: Must be one of `VALID_PROVIDERS`
- **agent_harness**: Must be one of `VALID_HARNESSES`
- **benchmark**: Must be one of `VALID_BENCHMARKS`
- **timeout_seconds**: Must be at least 30
- **max_concurrent**: Must be at least 1
- **budget**: Must be positive if set
- **thinking_budget**: Must be between 1024 and 31999 if set
- **Server config consistency**: `comparison_mode` requires both `mcp_server_a` and `mcp_server_b`; single mode requires `mcp_server`

---

## MCPServerConfig

Configuration for an MCP server process.

::: mcpbr.config.MCPServerConfig
    options:
      show_root_heading: true
      show_source: false
      members:
        - name
        - command
        - args
        - env
        - startup_timeout_ms
        - tool_timeout_ms
        - setup_command
        - setup_timeout_ms
        - get_args_for_workdir
        - get_setup_command_for_workdir
        - get_expanded_env

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `"mcpbr"` | Name to register the MCP server as (appears in tool names) |
| `command` | `str` | (required) | Command to start the MCP server (e.g., `npx`, `uvx`, `python`) |
| `args` | `list[str]` | `[]` | Arguments to pass to the command. Use `{workdir}` as placeholder |
| `env` | `dict[str, str]` | `{}` | Environment variables for the MCP server |
| `startup_timeout_ms` | `int` | `60000` | Timeout for MCP server startup (default: 60s) |
| `tool_timeout_ms` | `int` | `900000` | Timeout for MCP tool execution (default: 15 min) |
| `setup_command` | `str \| None` | `None` | Shell command to run inside the container before the agent starts |
| `setup_timeout_ms` | `int` | `900000` | Timeout for the setup_command (default: 15 min) |

### Methods

#### get_args_for_workdir(workdir: str) -> list[str]

Replace `{workdir}` placeholder in args with the actual working directory path.

```python
server = MCPServerConfig(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
)
resolved_args = server.get_args_for_workdir("/tmp/task-repo")
# ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/task-repo"]
```

#### get_setup_command_for_workdir(workdir: str) -> str | None

Replace `{workdir}` placeholder in setup_command.

```python
server = MCPServerConfig(
    command="my-server",
    setup_command="cd {workdir} && pip install -e .",
)
cmd = server.get_setup_command_for_workdir("/tmp/task-repo")
# "cd /tmp/task-repo && pip install -e ."
```

#### get_expanded_env() -> dict[str, str]

Expand `${VAR}` references in env values using `os.environ`.

```python
import os
os.environ["MY_API_KEY"] = "sk-123"

server = MCPServerConfig(
    command="my-server",
    env={"API_KEY": "${MY_API_KEY}"},
)
expanded = server.get_expanded_env()
# {"API_KEY": "sk-123"}
```

---

## AzureConfig

Configuration for Azure cloud infrastructure.

::: mcpbr.config.AzureConfig
    options:
      show_root_heading: true
      show_source: false

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `resource_group` | `str` | (required) | Azure resource group name (alphanumeric, dash, underscore, 1-90 chars) |
| `location` | `str` | `"eastus"` | Azure region (e.g., `eastus`, `westus2`, `northeurope`) |
| `vm_size` | `str \| None` | `None` | Azure VM size (e.g., `Standard_D4s_v3`). Alternative to `cpu_cores`/`memory_gb` |
| `cpu_cores` | `int` | `8` | Number of CPU cores (used if `vm_size` not specified) |
| `memory_gb` | `int` | `32` | Memory in GB (used if `vm_size` not specified) |
| `disk_gb` | `int` | `250` | Disk size in GB (minimum: 30) |
| `auto_shutdown` | `bool` | `true` | Automatically shutdown VM after evaluation completes |
| `preserve_on_error` | `bool` | `true` | Keep VM running if evaluation fails for debugging |
| `env_keys_to_export` | `list[str]` | `["ANTHROPIC_API_KEY"]` | Environment variables to export to Azure VM |
| `ssh_key_path` | `Path \| None` | `None` | Path to SSH key (auto-generated if not provided) |
| `zone` | `str \| None` | `None` | Azure availability zone (`"1"`, `"2"`, or `"3"`) |
| `python_version` | `str` | `"3.11"` | Python version to install on VM |

---

## InfrastructureConfig

Configuration for the infrastructure mode selector.

::: mcpbr.config.InfrastructureConfig
    options:
      show_root_heading: true
      show_source: false

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `Literal["local", "azure"]` | `"local"` | Infrastructure mode |
| `azure` | `AzureConfig \| None` | `None` | Azure configuration (required when `mode="azure"`) |

!!! warning "Azure Validation"
    When `mode` is set to `"azure"`, the `azure` field is required. Omitting it raises a `ValueError`.

---

## load_config()

Load configuration from a YAML file with environment variable expansion and inheritance support.

::: mcpbr.config.load_config
    options:
      show_root_heading: true
      show_source: false

### Signature

```python
def load_config(
    config_path: str | Path,
    warn_security: bool = True,
) -> HarnessConfig
```

### Features

- Automatically loads `.env` file from the current directory
- Supports `${VAR}` and `${VAR:-default}` syntax for environment variables
- Supports config inheritance via the `extends` field
- Validates all fields with Pydantic
- Warns about hardcoded secrets when `warn_security=True`

### Example

```python
from mcpbr.config import load_config

# Load from YAML file
config = load_config("mcpbr.yaml")

# Suppress security warnings (e.g., in CI)
config = load_config("mcpbr.yaml", warn_security=False)
```

### Exceptions

| Exception | When |
|-----------|------|
| `FileNotFoundError` | Config file does not exist |
| `ValueError` | Invalid config or missing required environment variables |
| `CircularInheritanceError` | Circular inheritance chain detected |
| `ConfigInheritanceError` | Error loading or merging inherited configs |

---

## YAML Configuration Format

### Minimal Configuration

```yaml
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"

benchmark: humaneval
model: sonnet
```

### Full Configuration

```yaml
# MCP Server
mcp_server:
  name: my-mcp-server
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
  env:
    API_KEY: "${MY_API_KEY}"
  startup_timeout_ms: 60000
  tool_timeout_ms: 900000
  setup_command: "cd {workdir} && npm install"
  setup_timeout_ms: 300000

# Model and Provider
provider: anthropic
model: sonnet
agent_harness: claude-code
agent_prompt: |
  You are a software engineer. Fix the following bug:
  {problem_statement}

# Benchmark
benchmark: swe-bench-verified
sample_size: 20
filter_category:
  - django
  - flask

# Runtime
timeout_seconds: 600
max_concurrent: 4
max_iterations: 15
thinking_budget: 10000
budget: 50.0

# Error Handling
continue_on_error: true
max_failures: 10

# Caching
cache_enabled: true
cache_dir: ~/.cache/mcpbr

# Checkpointing
checkpoint_interval: 5

# Docker
use_prebuilt_images: true
volumes:
  /host/cache: /container/cache

# Output
output_dir: ./results
disable_logs: false
enable_profiling: true
```

### Comparison Mode Configuration

```yaml
comparison_mode: true

mcp_server_a:
  name: server-v1
  command: npx
  args: ["-y", "mcp-server-v1", "{workdir}"]

mcp_server_b:
  name: server-v2
  command: npx
  args: ["-y", "mcp-server-v2", "{workdir}"]

benchmark: swe-bench-verified
model: sonnet
sample_size: 50
```

### Azure Infrastructure Configuration

```yaml
mcp_server:
  command: npx
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

benchmark: swe-bench-verified
model: sonnet
sample_size: 100

infrastructure:
  mode: azure
  azure:
    resource_group: mcpbr-eval-rg
    location: eastus2
    vm_size: Standard_D8s_v3
    disk_gb: 500
    auto_shutdown: true
    preserve_on_error: true
    env_keys_to_export:
      - ANTHROPIC_API_KEY
      - GITHUB_TOKEN
    python_version: "3.11"
```

### Config Inheritance

Configs can extend other configs using the `extends` field:

```yaml
# base.yaml
mcp_server:
  command: npx
  args: ["-y", "my-server", "{workdir}"]
model: sonnet
timeout_seconds: 300
```

```yaml
# production.yaml
extends: base.yaml
benchmark: swe-bench-verified
sample_size: 500
budget: 100.0
```

---

## Environment Variable Support

### Syntax

| Syntax | Description |
|--------|-------------|
| `${VAR}` | Required variable (error if not set) |
| `${VAR:-default}` | Optional variable with default value |

### .env File

mcpbr automatically loads a `.env` file from the current directory:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
MY_CUSTOM_VAR=some-value
```

### Usage in YAML

```yaml
mcp_server:
  command: my-server
  env:
    API_KEY: "${ANTHROPIC_API_KEY}"
    DEBUG: "${DEBUG:-false}"
    REGION: "${AWS_REGION:-us-east-1}"
```

!!! warning "Security"
    Do not hardcode API keys or secrets directly in YAML config files. Use environment variables or a `.env` file instead. mcpbr will warn about potential hardcoded secrets when `warn_security=True` (the default).

---

## Programmatic Configuration

### Creating a Default Config

```python
from mcpbr.config import create_default_config

config = create_default_config()
# Uses default MCP server (filesystem), anthropic provider, sonnet model
```

### Building Config Programmatically

```python
from mcpbr.config import HarnessConfig, MCPServerConfig, InfrastructureConfig, AzureConfig

config = HarnessConfig(
    mcp_server=MCPServerConfig(
        name="my-server",
        command="uvx",
        args=["my-mcp-server", "--workdir", "{workdir}"],
        env={"API_KEY": "from-env"},
    ),
    provider="anthropic",
    model="sonnet",
    benchmark="swe-bench-verified",
    sample_size=10,
    timeout_seconds=600,
    max_concurrent=2,
    budget=25.0,
    infrastructure=InfrastructureConfig(
        mode="azure",
        azure=AzureConfig(
            resource_group="my-eval-rg",
            location="eastus2",
            cpu_cores=8,
            memory_gb=32,
        ),
    ),
)
```
